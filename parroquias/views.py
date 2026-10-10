from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from core.choices import EstadoLibro, TipoLibro, TipoSacramento
from core.views import CrudBaseMixin, CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView

from .forms import CerrarLibroForm, FolioForm, IglesiaForm, LibroForm, MinistroForm, ParroquiaForm
from .models import Folio, Iglesia, Libro, Ministro, Parroquia
from .services import cerrar_libro, indice_libro

# ---------------------------------------------------------------------------
# Parroquias
# ---------------------------------------------------------------------------


class ParroquiaListView(CrudListView):
    model = Parroquia
    nombre_singular = "parroquia"
    nombre_plural = "parroquias"
    search_fields = ["nombre", "municipio__nombre"]
    columnas = [
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "municipio__nombre", "etiqueta": "Municipio"},
        {"campo": "direccion", "etiqueta": "Dirección"},
        {"campo": "telefono", "etiqueta": "Teléfono"},
    ]
    select_related = ("municipio", "parroco")
    url_lista = "parroquias:parroquia_lista"
    url_crear = "parroquias:parroquia_crear"
    url_editar = "parroquias:parroquia_editar"
    url_eliminar = "parroquias:parroquia_eliminar"


class ParroquiaCreateView(CrudCreateView):
    model = Parroquia
    form_class = ParroquiaForm
    template_name = "parroquias/parroquia_form.html"
    nombre_singular = "parroquia"
    nombre_plural = "parroquias"
    url_lista = "parroquias:parroquia_lista"


class ParroquiaUpdateView(CrudUpdateView):
    model = Parroquia
    form_class = ParroquiaForm
    template_name = "parroquias/parroquia_form.html"
    nombre_singular = "parroquia"
    nombre_plural = "parroquias"
    url_lista = "parroquias:parroquia_lista"


class ParroquiaDeleteView(CrudDeleteView):
    model = Parroquia
    nombre_singular = "parroquia"
    nombre_plural = "parroquias"
    url_lista = "parroquias:parroquia_lista"


# ---------------------------------------------------------------------------
# Ministros
# ---------------------------------------------------------------------------


class MinistroListView(CrudListView):
    model = Ministro
    nombre_singular = "ministro"
    nombre_plural = "ministros"
    search_fields = ["cedula", "nombre", "apellido"]
    columnas = [
        {"campo": "cedula", "etiqueta": "Cédula"},
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "apellido", "etiqueta": "Apellido"},
        {"campo": "cargo", "etiqueta": "Cargo"},
        {"campo": "parroquia__nombre", "etiqueta": "Parroquia"},
    ]
    select_related = ("parroquia", "documento")
    url_lista = "parroquias:ministro_lista"
    url_crear = "parroquias:ministro_crear"
    url_editar = "parroquias:ministro_editar"
    url_eliminar = "parroquias:ministro_eliminar"


class MinistroCreateView(CrudCreateView):
    model = Ministro
    form_class = MinistroForm
    nombre_singular = "ministro"
    nombre_plural = "ministros"
    url_lista = "parroquias:ministro_lista"


class MinistroUpdateView(CrudUpdateView):
    model = Ministro
    form_class = MinistroForm
    nombre_singular = "ministro"
    nombre_plural = "ministros"
    url_lista = "parroquias:ministro_lista"


class MinistroDeleteView(CrudDeleteView):
    model = Ministro
    nombre_singular = "ministro"
    nombre_plural = "ministros"
    url_lista = "parroquias:ministro_lista"


# ---------------------------------------------------------------------------
# Libros
# ---------------------------------------------------------------------------


class LibroListView(CrudListView):
    model = Libro
    template_name = "parroquias/libro_lista.html"
    nombre_singular = "libro"
    nombre_plural = "libros"
    search_fields = ["nombre", "detalle"]
    columnas = [
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "numero_libro", "etiqueta": "Número"},
        {"campo": "get_tipo_libro_display", "etiqueta": "Tipo"},
        {"campo": "parroquia__nombre", "etiqueta": "Parroquia"},
        {"campo": "estado", "etiqueta": "Estado"},
        {"campo": "fecha_apertura", "etiqueta": "Apertura"},
        {"campo": "num_partidas", "etiqueta": "Partidas"},
    ]
    select_related = ("parroquia",)
    url_lista = "parroquias:libro_lista"
    url_crear = "parroquias:libro_crear"
    url_editar = "parroquias:libro_editar"
    url_eliminar = "parroquias:libro_eliminar"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .annotate(num_partidas=Count("sacramentos"))
            .order_by("parroquia__nombre", "nombre")
        )
        parroquia = self.request.GET.get("parroquia", "")
        if parroquia.isdigit():
            queryset = queryset.filter(parroquia_id=parroquia)
        tipo = self.request.GET.get("tipo", "")
        if tipo in TipoLibro.values:
            queryset = queryset.filter(tipo_libro=tipo)
        estado = self.request.GET.get("estado", "")
        if estado in EstadoLibro.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            parroquias=Parroquia.objects.all(),
            tipos=TipoLibro.choices,
            estados=EstadoLibro.choices,
            filtro_parroquia=self.request.GET.get("parroquia", ""),
            filtro_tipo=self.request.GET.get("tipo", ""),
            filtro_estado=self.request.GET.get("estado", ""),
        )
        return contexto


class LibroCreateView(CrudCreateView):
    model = Libro
    form_class = LibroForm
    template_name = "parroquias/libro_form.html"
    nombre_singular = "libro"
    nombre_plural = "libros"
    url_lista = "parroquias:libro_lista"


class LibroUpdateView(CrudUpdateView):
    model = Libro
    form_class = LibroForm
    template_name = "parroquias/libro_form.html"
    nombre_singular = "libro"
    nombre_plural = "libros"
    url_lista = "parroquias:libro_lista"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["libro_cerrado"] = self.object.estado == EstadoLibro.CERRADO
        return contexto

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado == EstadoLibro.CERRADO:
            messages.error(request, "Un libro cerrado no se puede editar.")
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)


class LibroDeleteView(CrudDeleteView):
    model = Libro
    nombre_singular = "libro"
    nombre_plural = "libros"
    url_lista = "parroquias:libro_lista"


class LibroCerrarView(CrudBaseMixin, FormView):
    """Cierra un libro abierto registrando la diligencia de cierre."""

    form_class = CerrarLibroForm
    template_name = "parroquias/libro_cerrar.html"
    nombre_singular = "libro"
    nombre_plural = "libros"
    url_lista = "parroquias:libro_lista"
    libro = None

    def dispatch(self, request, *args, **kwargs):
        self.libro = get_object_or_404(
            Libro.objects.select_related("parroquia", "ministro_apertura"), pk=kwargs["pk"]
        )
        if self.libro.estado != EstadoLibro.ABIERTO:
            messages.error(request, "Este libro ya está cerrado.")
            return redirect(reverse(self.url_lista))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["libro"] = self.libro
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["libro"] = self.libro
        return contexto

    def form_valid(self, form):
        try:
            cerrar_libro(
                self.libro,
                form.cleaned_data["ministro_cierre"],
                form.cleaned_data["fecha_cierre"],
                form.cleaned_data.get("nota_cierre", ""),
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "Libro cerrado correctamente")
        return redirect(self.get_url_lista())


class LibroIndiceView(CrudBaseMixin, TemplateView):
    """Índice alfabético de un libro, con su diligencia de apertura y cierre."""

    template_name = "parroquias/libro_indice.html"
    nombre_singular = "libro"
    nombre_plural = "libros"
    url_lista = "parroquias:libro_lista"
    libro = None

    def dispatch(self, request, *args, **kwargs):
        self.libro = get_object_or_404(
            Libro.objects.select_related("parroquia", "ministro_apertura", "ministro_cierre"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        entradas = indice_libro(self.libro)
        for entrada in entradas:
            entrada["tipo_display"] = TipoSacramento(entrada["tipo"]).label
        contexto["libro"] = self.libro
        contexto["entradas"] = entradas
        return contexto


# ---------------------------------------------------------------------------
# Iglesias
# ---------------------------------------------------------------------------


class IglesiaListView(CrudListView):
    model = Iglesia
    template_name = "parroquias/iglesia_lista.html"
    nombre_singular = "iglesia"
    nombre_plural = "iglesias"
    search_fields = ["nombre", "direccion"]
    columnas = [
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "parroquia__nombre", "etiqueta": "Parroquia"},
        {"campo": "direccion", "etiqueta": "Dirección"},
    ]
    select_related = ("parroquia",)
    url_lista = "parroquias:iglesia_lista"
    url_crear = "parroquias:iglesia_crear"
    url_editar = "parroquias:iglesia_editar"
    url_eliminar = "parroquias:iglesia_eliminar"

    def get_queryset(self):
        queryset = super().get_queryset()
        parroquia = self.request.GET.get("parroquia", "")
        if parroquia.isdigit():
            queryset = queryset.filter(parroquia_id=parroquia)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            parroquias=Parroquia.objects.all(),
            filtro_parroquia=self.request.GET.get("parroquia", ""),
        )
        return contexto


class IglesiaCreateView(CrudCreateView):
    model = Iglesia
    form_class = IglesiaForm
    nombre_singular = "iglesia"
    nombre_plural = "iglesias"
    url_lista = "parroquias:iglesia_lista"


class IglesiaUpdateView(CrudUpdateView):
    model = Iglesia
    form_class = IglesiaForm
    nombre_singular = "iglesia"
    nombre_plural = "iglesias"
    url_lista = "parroquias:iglesia_lista"


class IglesiaDeleteView(CrudDeleteView):
    model = Iglesia
    nombre_singular = "iglesia"
    nombre_plural = "iglesias"
    url_lista = "parroquias:iglesia_lista"


# ---------------------------------------------------------------------------
# Folios (CRUD anidado bajo /parroquias/libros/<libro_id>/folios/)
# ---------------------------------------------------------------------------


class FolioBaseMixin(CrudBaseMixin):
    """Carga el libro de la URL (404 si no existe) y construye las rutas anidadas."""

    nombre_singular = "folio"
    nombre_plural = "folios"
    url_lista = "parroquias:folio_lista"
    libro = None

    def dispatch(self, request, *args, **kwargs):
        self.libro = get_object_or_404(Libro, pk=kwargs["libro_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_url_lista(self):
        return reverse(self.url_lista, kwargs={"libro_id": self.libro.pk})

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["libro"] = self.libro
        return contexto


class FolioListView(FolioBaseMixin, CrudListView):
    model = Folio
    template_name = "parroquias/folio_lista.html"
    columnas = [
        {"campo": "numero_folio", "etiqueta": "Número"},
        {"campo": "fecha_creacion", "etiqueta": "Fecha de creación"},
        {"campo": "observaciones", "etiqueta": "Observaciones"},
    ]
    select_related = ("libro",)
    url_crear = "parroquias:folio_crear"
    url_editar = "parroquias:folio_editar"
    url_eliminar = "parroquias:folio_eliminar"

    def get_queryset(self):
        return super().get_queryset().filter(libro=self.libro)


class FolioCreateView(FolioBaseMixin, CrudCreateView):
    model = Folio
    form_class = FolioForm
    template_name = "parroquias/folio_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["libro"] = self.libro
        return kwargs

    def form_valid(self, form):
        form.instance.libro = self.libro
        return super().form_valid(form)


class FolioUpdateView(FolioBaseMixin, CrudUpdateView):
    model = Folio
    form_class = FolioForm
    template_name = "parroquias/folio_form.html"

    def get_queryset(self):
        return super().get_queryset().filter(libro=self.libro)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["libro"] = self.libro
        return kwargs


class FolioDeleteView(FolioBaseMixin, CrudDeleteView):
    model = Folio

    def get_queryset(self):
        return super().get_queryset().filter(libro=self.libro)
