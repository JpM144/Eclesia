from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from core.choices import AccionHistorial, EstadoRegistro, TipoLibro, TipoSacramento
from parroquias.models import Libro, Parroquia

from .forms import (
    BautismoEditarForm,
    BautismoForm,
    MotivoForm,
    PrimeraComunionEditarForm,
    PrimeraComunionForm,
    SolicitudCertificadoForm,
)
from .models import Bautismo, PrimeraComunion, Sacramento
from .services import (
    datos_certificado_bautismo,
    datos_certificado_primera_comunion,
    datos_hoja_bautismo,
    datos_hoja_primera_comunion,
    motivo_no_eliminable,
    padres_de_primera_comunion,
    puede_eliminarse,
    registrar_historial,
)

# Estados en los que aún se puede editar o anular una partida.
ESTADOS_EDITABLES = (EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO)

PAGINAR_POR = 25


class FiltrosPartidasMixin:
    """Filtros compartidos de los listados de partidas (q, libro, año, estado, parroquia).

    Las subclases fijan ``tipo_libro`` y ``tipo_sacramento``; los nombres del
    contexto son los mismos que usa ``bautismo_lista.html`` y sus réplicas.
    """

    tipo_libro = None
    tipo_sacramento = None

    def _parametro(self, nombre):
        return self.request.GET.get(nombre, "").strip()

    def _filtros_activos(self):
        return {
            nombre: valor
            for nombre in ("q", "libro", "anio", "estado", "parroquia")
            if (valor := self._parametro(nombre))
        }

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parroquias_con_libros = Parroquia.objects.filter(
            libros__tipo_libro=self.tipo_libro
        ).distinct()
        anios = sorted(
            {
                anio.year
                for anio in Sacramento.objects.filter(tipo=self.tipo_sacramento).dates(
                    "fecha", "year"
                )
            },
            reverse=True,
        )
        contexto.update(
            q=self._parametro("q"),
            total=self.get_queryset().count(),
            libros=Libro.objects.filter(tipo_libro=self.tipo_libro).select_related("parroquia"),
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


class BautismoListView(FiltrosPartidasMixin, ListView):
    """Listado paginado de bautismos, con filtros y sin consultas N+1."""

    template_name = "sacramentos/bautismo_lista.html"
    context_object_name = "bautismos"
    paginate_by = PAGINAR_POR
    tipo_libro = TipoLibro.BAUTISMOS
    tipo_sacramento = TipoSacramento.BAUTISMO

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
        contexto["url_detalle"] = reverse("sacramentos:bautismo_detalle", args=[self.bautismo.pk])
        contexto["partida_fiel"] = self.bautismo.sacramento.fiel
        contexto["titulo_solicitud"] = "Certificado de bautismo"
        contexto["titulo_certificado"] = "Certificado de bautismo"
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


class PrimeraComunionListView(FiltrosPartidasMixin, ListView):
    """Listado paginado de primeras comuniones, con los mismos filtros que bautismos."""

    template_name = "sacramentos/primera_comunion_lista.html"
    context_object_name = "primeras_comuniones"
    paginate_by = PAGINAR_POR
    tipo_libro = TipoLibro.PRIMERA_COMUNION
    tipo_sacramento = TipoSacramento.PRIMERA_COMUNION

    def get_queryset(self):
        queryset = PrimeraComunion.objects.select_related(
            "sacramento__fiel",
            "sacramento__fiel__documento",
            "sacramento__folio",
            "sacramento__folio__libro",
            "sacramento__folio__libro__parroquia",
            "sacramento__parroquia",
            "bautismo",
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


class PrimeraComunionCreateView(FormView):
    """Registra una Primera Comunión a través de ``registrar_primera_comunion``."""

    template_name = "sacramentos/primera_comunion_form.html"
    form_class = PrimeraComunionForm

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
        contexto["titulo"] = "Registrar Primera Comunión"
        return contexto

    def form_valid(self, form):
        from .services import registrar_primera_comunion

        try:
            primera, reutilizadas = registrar_primera_comunion(
                form.datos_para_servicio(), self.request.user
            )
        except ValidationError as error:
            for campo, mensajes in error.message_dict.items():
                destino = campo if campo in form.fields else None
                for mensaje in mensajes:
                    form.add_error(destino, mensaje)
            return self.form_invalid(form)

        sacramento = primera.sacramento
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
        return redirect(reverse("sacramentos:primera_comunion_detalle", args=[primera.pk]))


class PrimeraComunionDetailView(DetailView):
    """Ficha de una partida de Primera Comunión, con el aspecto de partida del libro."""

    template_name = "sacramentos/primera_comunion_detalle.html"
    context_object_name = "primera_comunion"

    def get_queryset(self):
        return PrimeraComunion.objects.select_related(
            "sacramento__fiel__documento",
            "sacramento__fiel__municipio_nacimiento__departamento__pais",
            "sacramento__folio__libro__parroquia",
            "sacramento__parroquia",
            "sacramento__ministro",
            "sacramento__ministro__documento",
            "bautismo__sacramento__folio__libro__parroquia",
            "bautismo__padre__documento",
            "bautismo__madre__documento",
            "padre__documento",
            "madre__documento",
            "doy_fe",
            "doy_fe__documento",
        ).filter(sacramento__tipo=TipoSacramento.PRIMERA_COMUNION)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        sacramento = self.object.sacramento
        contexto["sacramento"] = sacramento
        contexto["hoja"] = datos_hoja_primera_comunion(self.object)
        contexto["historial"] = sacramento.historial.select_related("usuario__perfil")
        contexto["personas_partida"] = _personas_de_la_partida_primera_comunion(self.object)
        contexto["puede_editar"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_anular"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_eliminar"] = puede_eliminarse(self.object)
        contexto["motivo_no_eliminable"] = motivo_no_eliminable(self.object)
        contexto["puede_certificar"] = sacramento.estado != EstadoRegistro.ANULADO
        bautismo = self.object.bautismo
        if bautismo is not None:
            bautismo_sacramento = bautismo.sacramento
            bautismo_libro = bautismo_sacramento.folio.libro
            contexto["bautismo_enlace"] = reverse(
                "sacramentos:bautismo_detalle", args=[bautismo.pk]
            )
            contexto["bautismo_referencia"] = (
                f"Libro {bautismo_libro.numero_libro or bautismo_libro.nombre} · "
                f"Folio {bautismo_sacramento.folio.numero_folio} · "
                f"N.° {bautismo_sacramento.numero} · "
                f"{bautismo_sacramento.fecha.strftime('%d/%m/%Y')}"
            )
            contexto["bautismo_parroquia"] = str(bautismo_libro.parroquia)
        return contexto


def _personas_de_la_partida_primera_comunion(primera_comunion):
    """Enlaces a las fichas de las personas de la partida (sin consultas extra)."""
    sacramento = primera_comunion.sacramento
    padre, madre = padres_de_primera_comunion(primera_comunion)
    personas = [
        ("Comulgante", sacramento.fiel),
        ("Padre", padre),
        ("Madre", madre),
        ("Ministro que celebró", sacramento.ministro),
        ("Quien da fe", primera_comunion.doy_fe),
    ]
    return [
        {"rol": rol, "nombre": str(persona), "documento_id": persona.documento_id}
        for rol, persona in personas
        if persona is not None
    ]


class PrimeraComunionBaseMixin:
    """Carga la partida de Primera Comunión (404 si no existe o no es de ese tipo)."""

    def get_primera_comunion(self):
        return get_object_or_404(
            PrimeraComunion.objects.select_related(
                "sacramento__libro__parroquia",
                "sacramento__folio",
                "sacramento__fiel__documento",
                "sacramento__fiel__municipio_nacimiento__departamento__pais",
                "bautismo",
                "padre__documento",
                "madre__documento",
                "doy_fe",
            ).filter(sacramento__tipo=TipoSacramento.PRIMERA_COMUNION),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["primera_comunion"] = self.primera_comunion
        contexto["sacramento"] = self.primera_comunion.sacramento
        return contexto


class PrimeraComunionUpdateView(PrimeraComunionBaseMixin, FormView):
    """Corrige una partida de Primera Comunión (motivo obligatorio)."""

    template_name = "sacramentos/primera_comunion_editar.html"
    form_class = PrimeraComunionEditarForm

    def dispatch(self, request, *args, **kwargs):
        self.primera_comunion = self.get_primera_comunion()
        if self.primera_comunion.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(request, "No se puede editar una partida anulada.")
            return redirect(
                reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["primera"] = self.primera_comunion
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = "Editar Primera Comunión"
        return contexto

    def form_valid(self, form):
        from .services import corregir_primera_comunion

        try:
            corregir_primera_comunion(
                self.primera_comunion,
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
        return redirect(
            reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
        )


class PrimeraComunionAnularView(PrimeraComunionBaseMixin, FormView):
    """Anula una partida de Primera Comunión conservándola en el libro."""

    template_name = "sacramentos/primera_comunion_anular.html"
    form_class = MotivoForm

    def dispatch(self, request, *args, **kwargs):
        self.primera_comunion = self.get_primera_comunion()
        if self.primera_comunion.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(request, "La partida ya está anulada.")
            return redirect(
                reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
            )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .services import anular_primera_comunion

        anular_primera_comunion(
            self.primera_comunion, self.request.user, form.cleaned_data["motivo"]
        )
        messages.success(self.request, "Partida anulada correctamente.")
        return redirect(
            reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
        )


class PrimeraComunionEliminarView(PrimeraComunionBaseMixin, FormView):
    """Elimina definitivamente una partida elegible, guardando una copia."""

    template_name = "sacramentos/primera_comunion_eliminar.html"
    form_class = MotivoForm

    def dispatch(self, request, *args, **kwargs):
        self.primera_comunion = self.get_primera_comunion()
        if not puede_eliminarse(self.primera_comunion):
            messages.error(request, motivo_no_eliminable(self.primera_comunion))
            return redirect(
                reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
            )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .services import eliminar_primera_comunion

        eliminar_primera_comunion(
            self.primera_comunion, self.request.user, form.cleaned_data["motivo"]
        )
        messages.success(self.request, "Partida eliminada correctamente.")
        return redirect(reverse("sacramentos:primera_comunion_lista"))


class PrimeraComunionCertificadoView(PrimeraComunionBaseMixin, FormView):
    """Expide un certificado imprimible de una partida de Primera Comunión.

    El GET muestra el formulario de solicitud (quién lo pide, con qué documento,
    relación y finalidad). Al enviarlo, registra la expedición en el historial y
    devuelve el certificado listo para imprimir. No se puede certificar una
    partida anulada.
    """

    template_name = "certificados/solicitud_certificado.html"
    form_class = SolicitudCertificadoForm

    def dispatch(self, request, *args, **kwargs):
        self.primera_comunion = self.get_primera_comunion()
        self.certificado = None
        if self.primera_comunion.sacramento.estado == EstadoRegistro.ANULADO:
            messages.error(
                self.request,
                "No se puede expedir un certificado de una partida anulada.",
            )
            return redirect(
                reverse("sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk])
            )
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.certificado is not None:
            return ["certificados/certificado.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["url_detalle"] = reverse(
            "sacramentos:primera_comunion_detalle", args=[self.primera_comunion.pk]
        )
        contexto["partida_fiel"] = self.primera_comunion.sacramento.fiel
        contexto["titulo_solicitud"] = "Certificado de Primera Comunión"
        contexto["titulo_certificado"] = "Certificado de Primera Comunión"
        contexto["hoja"] = datos_hoja_primera_comunion(self.primera_comunion)
        if self.certificado is not None:
            contexto["hoja"] = datos_hoja_primera_comunion(
                self.primera_comunion, para_certificado=True
            )
            contexto["hoja"]["ocultar_estado"] = True
            contexto["hoja"]["incluir_cierre"] = True
            contexto["certificado"] = self.certificado
        return contexto

    def form_valid(self, form):
        datos = form.datos_para_servicio()
        registrar_historial(
            self.primera_comunion.sacramento,
            AccionHistorial.CERTIFICADO,
            descripcion=datos["descripcion_historial"],
            usuario=self.request.user,
        )
        self.certificado = datos_certificado_primera_comunion(
            self.primera_comunion, datos, self.request.user
        )
        return self.render_to_response(self.get_context_data(form=form))
