from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from core.choices import AccionHistorial, EstadoRegistro, TipoLibro, TipoSacramento
from parroquias.models import Libro, Parroquia

from .forms import BautismoEditarForm, BautismoForm, MotivoForm, SolicitudCertificadoForm
from .models import Bautismo, Sacramento
from .services import (
    datos_certificado_bautismo,
    datos_hoja_bautismo,
    motivo_no_eliminable,
    puede_eliminarse,
    registrar_historial,
)

# Estados en los que aún se puede editar o anular una partida.
ESTADOS_EDITABLES = (EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO)

PAGINAR_POR = 25


class BautismoListView(ListView):
    """Listado paginado de bautismos, con filtros y sin consultas N+1."""

    template_name = "sacramentos/bautismo_lista.html"
    context_object_name = "bautismos"
    paginate_by = PAGINAR_POR

    def _parametro(self, nombre):
        return self.request.GET.get(nombre, "").strip()

    def _filtros_activos(self):
        return {
            nombre: valor
            for nombre in ("q", "libro", "anio", "estado", "parroquia")
            if (valor := self._parametro(nombre))
        }

    def get_queryset(self):
        queryset = Bautismo.objects.select_related(
            "sacramento__fiel",
            "sacramento__fiel__documento",
            "sacramento__folio",
            "sacramento__folio__libro",
            "sacramento__folio__libro__parroquia",
            "sacramento__parroquia",
            "padre",
            "madre",
        ).order_by(
            "-sacramento__libro__numero_libro",
            "-sacramento__libro__nombre",
            "-sacramento__numero",
        )
        termino = self._parametro("q")
        if termino:
            queryset = queryset.filter(
                Q(sacramento__fiel__nombres__icontains=termino)
                | Q(sacramento__fiel__apellidos__icontains=termino)
                | Q(sacramento__numero__icontains=termino)
            )
        libro = self._parametro("libro")
        if libro.isdigit():
            queryset = queryset.filter(sacramento__libro_id=libro)
        anio = self._parametro("anio")
        if anio.isdigit():
            queryset = queryset.filter(sacramento__fecha__year=anio)
        estado = self._parametro("estado")
        if estado in EstadoRegistro.values:
            queryset = queryset.filter(sacramento__estado=estado)
        parroquia = self._parametro("parroquia")
        if parroquia.isdigit():
            queryset = queryset.filter(sacramento__folio__libro__parroquia_id=parroquia)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parroquias_con_libros = Parroquia.objects.filter(
            libros__tipo_libro=TipoLibro.BAUTISMOS
        ).distinct()
        anios = sorted(
            {
                anio.year
                for anio in Sacramento.objects.filter(tipo=TipoSacramento.BAUTISMO).dates(
                    "fecha", "year"
                )
            },
            reverse=True,
        )
        contexto.update(
            q=self._parametro("q"),
            total=self.get_queryset().count(),
            libros=Libro.objects.filter(tipo_libro=TipoLibro.BAUTISMOS).select_related("parroquia"),
            anios=anios,
            estados=EstadoRegistro.choices,
            filtro_libro=self._parametro("libro"),
            filtro_anio=self._parametro("anio"),
            filtro_estado=self._parametro("estado"),
            filtro_parroquia=self._parametro("parroquia"),
            hay_filtros=bool(self._filtros_activos()),
            consulta_filtros=urlencode(self._filtros_activos()),
            mostrar_parroquia=parroquias_con_libros.count() > 1,
            parroquias_con_libros=parroquias_con_libros,
        )
        return contexto


class BautismoCreateView(FormView):
    """Registra un bautismo nuevo a través de ``registrar_bautismo``."""

    template_name = "sacramentos/bautismo_form.html"
    form_class = BautismoForm

    def get_initial(self):
        inicial = super().get_initial()
        libro_id = self.request.GET.get("libro")
        if libro_id and libro_id.isdigit():
            libro = Libro.objects.filter(pk=libro_id).select_related("parroquia").first()
            if libro is not None:
                inicial["libro"] = libro
        return inicial

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = "Registrar bautismo"
        return contexto

    def form_valid(self, form):
        from .services import registrar_bautismo

        try:
            bautismo, reutilizadas = registrar_bautismo(
                form.datos_para_servicio(), self.request.user
            )
        except ValidationError as error:
            for campo, mensajes in error.message_dict.items():
                destino = campo if campo in form.fields else None
                for mensaje in mensajes:
                    form.add_error(destino, mensaje)
            return self.form_invalid(form)

        sacramento = bautismo.sacramento
        libro = sacramento.folio.libro
        referencia = libro.numero_libro or libro.nombre
        messages.success(
            self.request,
            (
                f"Partida registrada: Libro {referencia}, "
                f"Folio {sacramento.folio.numero_folio}, N.° {sacramento.numero}"
            ),
        )
        if reutilizadas:
            messages.info(
                self.request,
                "Se reutilizaron datos de personas ya registradas: "
                + ", ".join(reutilizadas)
                + ".",
            )
        return redirect(reverse("sacramentos:bautismo_detalle", args=[bautismo.pk]))


class BautismoDetailView(DetailView):
    """Ficha de una partida de bautismo, con el aspecto de partida del libro."""

    template_name = "sacramentos/bautismo_detalle.html"
    context_object_name = "bautismo"

    def get_queryset(self):
        return Bautismo.objects.select_related(
            "sacramento__fiel__documento",
            "sacramento__fiel__municipio_nacimiento__departamento__pais",
            "sacramento__folio__libro__parroquia",
            "sacramento__parroquia",
            "sacramento__ministro",
            "sacramento__ministro__documento",
            "padre__documento",
            "madre__documento",
            "padrino__documento",
            "madrina__documento",
            "quien_firma",
            "quien_firma__documento",
            "doy_fe",
            "doy_fe__documento",
        ).filter(sacramento__tipo=TipoSacramento.BAUTISMO)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        sacramento = self.object.sacramento
        contexto["sacramento"] = sacramento
        contexto["hoja"] = datos_hoja_bautismo(self.object)
        contexto["historial"] = sacramento.historial.select_related("usuario__perfil")
        contexto["personas_partida"] = _personas_de_la_partida(self.object)
        contexto["puede_editar"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_anular"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_eliminar"] = puede_eliminarse(self.object)
        contexto["puede_certificar"] = sacramento.estado != EstadoRegistro.ANULADO
        return contexto


def _personas_de_la_partida(bautismo):
    """Enlaces a las fichas de las personas de la partida (sin consultas extra)."""
    sacramento = bautismo.sacramento
    personas = [
        ("Bautizado", sacramento.fiel),
        ("Padre", bautismo.padre),
        ("Madre", bautismo.madre),
        ("Padrino", bautismo.padrino),
        ("Madrina", bautismo.madrina),
        ("Ministro que bautizó", sacramento.ministro),
        ("Ministro que firma", bautismo.quien_firma),
        ("Quien da fe", bautismo.doy_fe),
    ]
    return [
        {"rol": rol, "nombre": str(persona), "documento_id": persona.documento_id}
        for rol, persona in personas
        if persona is not None
    ]


class BautismoBaseMixin:
    """Carga la partida de bautismo (404 si no existe o no es un bautismo)."""

    def get_bautismo(self):
        return get_object_or_404(
            Bautismo.objects.select_related(
                "sacramento__libro__parroquia",
                "sacramento__folio",
                "sacramento__fiel__documento",
                "sacramento__fiel__municipio_nacimiento__departamento__pais",
                "padre__documento",
                "madre__documento",
                "padrino__documento",
                "madrina__documento",
                "doy_fe",
            ).filter(sacramento__tipo=TipoSacramento.BAUTISMO),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["bautismo"] = self.bautismo
        contexto["sacramento"] = self.bautismo.sacramento
        return contexto


class BautismoUpdateView(BautismoBaseMixin, FormView):
    """Corrige una partida de bautismo (motivo obligatorio)."""

    template_name = "sacramentos/bautismo_editar.html"
    form_class = BautismoEditarForm

    def dispatch(self, request, *args, **kwargs):
        self.bautismo = self.get_bautismo()
        if self.bautismo.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(request, "No se puede editar una partida anulada.")
            return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["bautismo"] = self.bautismo
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = "Editar bautismo"
        return contexto

    def form_valid(self, form):
        from .services import corregir_bautismo

        try:
            corregir_bautismo(
                self.bautismo,
                form.datos_para_servicio(),
                self.request.user,
                form.cleaned_data["motivo"],
            )
        except ValidationError as error:
            for campo, mensajes in error.message_dict.items():
                destino = campo if campo in form.fields else None
                for mensaje in mensajes:
                    form.add_error(destino, mensaje)
            return self.form_invalid(form)

        messages.success(self.request, "Partida corregida correctamente.")
        return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))


class BautismoAnularView(BautismoBaseMixin, FormView):
    """Anula una partida de bautismo conservándola en el libro."""

    template_name = "sacramentos/bautismo_anular.html"
    form_class = MotivoForm

    def dispatch(self, request, *args, **kwargs):
        self.bautismo = self.get_bautismo()
        if self.bautismo.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(request, "La partida ya está anulada.")
            return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .services import anular_bautismo

        anular_bautismo(self.bautismo, self.request.user, form.cleaned_data["motivo"])
        messages.success(self.request, "Partida anulada correctamente.")
        return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))


class BautismoEliminarView(BautismoBaseMixin, FormView):
    """Elimina definitivamente una partida elegible, guardando una copia."""

    template_name = "sacramentos/bautismo_eliminar.html"
    form_class = MotivoForm

    def dispatch(self, request, *args, **kwargs):
        self.bautismo = self.get_bautismo()
        if not puede_eliminarse(self.bautismo):
            messages.error(request, motivo_no_eliminable(self.bautismo))
            return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .services import eliminar_bautismo

        eliminar_bautismo(self.bautismo, self.request.user, form.cleaned_data["motivo"])
        messages.success(self.request, "Partida eliminada correctamente.")
        return redirect(reverse("sacramentos:bautismo_lista"))


class BautismoCertificadoView(BautismoBaseMixin, FormView):
    """Expide un certificado imprimible a partir de una partida de bautismo.

    El GET muestra el formulario de solicitud (quién lo pide, con qué documento,
    relación y finalidad). Al enviarlo, registra la expedición en el historial y
    devuelve el certificado listo para imprimir. No se puede certificar una
    partida anulada.
    """

    template_name = "certificados/solicitud_certificado.html"
    form_class = SolicitudCertificadoForm

    def dispatch(self, request, *args, **kwargs):
        self.bautismo = self.get_bautismo()
        self.certificado = None
        if self.bautismo.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(
                self.request,
                "No se puede expedir un certificado de una partida anulada.",
            )
            return redirect(reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk]))
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.certificado is not None:
            return ["certificados/certificado.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["hoja"] = datos_hoja_bautismo(self.bautismo)
        if self.certificado is not None:
            contexto["hoja"] = datos_hoja_bautismo(self.bautismo, para_certificado=True)
            contexto["hoja"]["ocultar_estado"] = True
            contexto["hoja"]["incluir_cierre"] = True
            contexto["certificado"] = self.certificado
        return contexto

    def form_valid(self, form):
        datos = form.datos_para_servicio()
        registrar_historial(
            self.bautismo.sacramento,
            AccionHistorial.CERTIFICADO,
            descripcion=datos["descripcion_historial"],
            usuario=self.request.user,
        )
        self.certificado = datos_certificado_bautismo(self.bautismo, datos, self.request.user)
        return self.render_to_response(self.get_context_data(form=form))
