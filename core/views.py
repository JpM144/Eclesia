from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.services import resumen_dashboard


def dashboard(request):
    return render(request, "core/dashboard.html", resumen_dashboard())


# ---------------------------------------------------------------------------
# Patrón CRUD reutilizable
# ---------------------------------------------------------------------------
# Cada entidad con CRUD se define con cuatro vistas que heredan de estas
# clases base: CrudListView, CrudCreateView, CrudUpdateView y CrudDeleteView.
# Ver la sección "Patrón CRUD" del README.


class CrudBaseMixin:
    """Atributos y contexto comunes a las vistas CRUD genéricas.

    Atributos que reciben las subclases:
        nombre_singular: nombre de la entidad en singular (p. ej. "país").
        nombre_plural:   nombre de la entidad en plural (p. ej. "países").
        search_fields:   campos sobre los que busca el parámetro GET "q".
        columnas:        columnas de la lista: [{"campo": ..., "etiqueta": ...}].
                         El campo admite rutas con doble guion bajo
                         (p. ej. "departamento__pais__nombre").
        url_lista:       nombre de la ruta de la lista; es la URL de retorno.
        select_related:  tupla de relaciones a precargar (evita consultas de más).
    """

    nombre_singular = ""
    nombre_plural = ""
    search_fields = []
    columnas = []
    url_lista = ""
    select_related = ()

    def get_nombre_singular(self):
        return self.nombre_singular

    def get_nombre_plural(self):
        return self.nombre_plural

    def get_url_lista(self):
        return reverse(self.url_lista)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            nombre_singular=self.get_nombre_singular(),
            nombre_plural=self.get_nombre_plural(),
            url_lista=self.get_url_lista(),
        )
        return contexto


class CrudListView(CrudBaseMixin, ListView):
    """Listado con buscador, paginación de 20 y acciones Editar/Eliminar.

    Atributos adicionales:
        url_crear, url_editar, url_eliminar: nombres de ruta de esas acciones.
    """

    template_name = "crud/lista.html"
    paginate_by = 20
    url_crear = ""
    url_editar = ""
    url_eliminar = ""

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        termino = self.request.GET.get("q", "").strip()
        if termino and self.search_fields:
            condiciones = Q()
            for campo in self.search_fields:
                condiciones |= Q(**{f"{campo}__icontains": termino})
            queryset = queryset.filter(condiciones)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            columnas=self.columnas,
            busqueda=self.request.GET.get("q", "").strip(),
            tiene_busqueda=bool(self.search_fields),
            url_crear=self.url_crear,
            url_editar=self.url_editar,
            url_eliminar=self.url_eliminar,
        )
        return contexto


class CrudFormMixin(CrudBaseMixin):
    """Base de los formularios de creación y edición."""

    template_name = "crud/formulario.html"
    mensaje_exito = ""

    def get_success_url(self):
        return self.get_url_lista()

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, self.mensaje_exito)
        return respuesta


class CrudCreateView(CrudFormMixin, CreateView):
    """Crea un registro, avisa y vuelve a la lista."""

    mensaje_exito = "Registro creado correctamente"


class CrudUpdateView(CrudFormMixin, UpdateView):
    """Edita un registro, avisa y vuelve a la lista."""

    mensaje_exito = "Registro actualizado correctamente"


class CrudDeleteView(CrudBaseMixin, DeleteView):
    """Pide confirmación para eliminar.

    Si el registro está protegido (ProtectedError) muestra un mensaje de error
    y vuelve a la lista en lugar de devolver un error 500.
    """

    template_name = "crud/confirmar_eliminar.html"
    mensaje_exito = "Registro eliminado correctamente"
    mensaje_protegido = "No se puede eliminar porque tiene registros asociados"

    def get_success_url(self):
        return self.get_url_lista()

    def form_valid(self, form):
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.mensaje_protegido)
            return redirect(self.get_url_lista())
        messages.success(self.request, self.mensaje_exito)
        return respuesta
