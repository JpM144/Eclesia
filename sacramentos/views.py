from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from core.choices import EstadoRegistro, TipoSacramento
from parroquias.models import Libro

from .forms import BautismoEditarForm, BautismoForm, MotivoForm
from .models import Bautismo
from .services import motivo_no_eliminable, puede_eliminarse

# Estados en los que aún se puede editar o anular una partida.
ESTADOS_EDITABLES = (EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO)

PAGINAR_POR = 25


class BautismoListView(ListView):
    """Listado paginado de bautismos, sin consultas N+1."""

    template_name = "sacramentos/bautismo_lista.html"
    context_object_name = "bautismos"
    paginate_by = PAGINAR_POR

    def get_queryset(self):
        queryset = Bautismo.objects.select_related(
            "sacramento__fiel",
            "sacramento__folio__libro",
            "sacramento__parroquia",
        ).order_by("-sacramento__fecha", "-sacramento__numero")
        termino = self.request.GET.get("q", "").strip()
        if termino:
            queryset = queryset.filter(
                Q(sacramento__fiel__nombres__icontains=termino)
                | Q(sacramento__fiel__apellidos__icontains=termino)
                | Q(sacramento__numero__icontains=termino)
            )
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["total"] = self.get_queryset().count()
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
    """Ficha de una partida de bautismo."""

    template_name = "sacramentos/bautismo_detalle.html"
    context_object_name = "bautismo"

    def get_queryset(self):
        return Bautismo.objects.select_related(
            "sacramento__fiel__documento",
            "sacramento__fiel__municipio_nacimiento",
            "sacramento__folio__libro__parroquia",
            "sacramento__parroquia",
            "sacramento__ministro",
            "padre__documento",
            "madre__documento",
            "padrino__documento",
            "madrina__documento",
            "quien_firma",
            "doy_fe",
        ).filter(sacramento__tipo=TipoSacramento.BAUTISMO)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        sacramento = self.object.sacramento
        contexto["sacramento"] = sacramento
        contexto["anotaciones"] = sacramento.anotaciones_marginales.select_related(
            "parroquia_destino"
        )
        contexto["historial"] = sacramento.historial.select_related("usuario__perfil")
        contexto["puede_editar"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_anular"] = sacramento.estado in ESTADOS_EDITABLES
        contexto["puede_eliminar"] = puede_eliminarse(self.object)
        return contexto


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
