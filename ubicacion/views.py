from django.http import JsonResponse

from core.views import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView

from .forms import DepartamentoForm, MunicipioForm, PaisForm
from .models import Departamento, Municipio, Pais

# ---------------------------------------------------------------------------
# Países
# ---------------------------------------------------------------------------


class PaisListView(CrudListView):
    model = Pais
    nombre_singular = "país"
    nombre_plural = "países"
    search_fields = ["nombre"]
    columnas = [{"campo": "nombre", "etiqueta": "Nombre"}]
    url_lista = "ubicacion:pais_lista"
    url_crear = "ubicacion:pais_crear"
    url_editar = "ubicacion:pais_editar"
    url_eliminar = "ubicacion:pais_eliminar"


class PaisCreateView(CrudCreateView):
    model = Pais
    form_class = PaisForm
    nombre_singular = "país"
    nombre_plural = "países"
    url_lista = "ubicacion:pais_lista"


class PaisUpdateView(CrudUpdateView):
    model = Pais
    form_class = PaisForm
    nombre_singular = "país"
    nombre_plural = "países"
    url_lista = "ubicacion:pais_lista"


class PaisDeleteView(CrudDeleteView):
    model = Pais
    nombre_singular = "país"
    nombre_plural = "países"
    url_lista = "ubicacion:pais_lista"


# ---------------------------------------------------------------------------
# Departamentos
# ---------------------------------------------------------------------------


class DepartamentoListView(CrudListView):
    model = Departamento
    nombre_singular = "departamento"
    nombre_plural = "departamentos"
    search_fields = ["nombre", "pais__nombre"]
    columnas = [
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "pais__nombre", "etiqueta": "País"},
    ]
    select_related = ("pais",)
    url_lista = "ubicacion:departamento_lista"
    url_crear = "ubicacion:departamento_crear"
    url_editar = "ubicacion:departamento_editar"
    url_eliminar = "ubicacion:departamento_eliminar"


class DepartamentoCreateView(CrudCreateView):
    model = Departamento
    form_class = DepartamentoForm
    nombre_singular = "departamento"
    nombre_plural = "departamentos"
    url_lista = "ubicacion:departamento_lista"


class DepartamentoUpdateView(CrudUpdateView):
    model = Departamento
    form_class = DepartamentoForm
    nombre_singular = "departamento"
    nombre_plural = "departamentos"
    url_lista = "ubicacion:departamento_lista"


class DepartamentoDeleteView(CrudDeleteView):
    model = Departamento
    nombre_singular = "departamento"
    nombre_plural = "departamentos"
    url_lista = "ubicacion:departamento_lista"


# ---------------------------------------------------------------------------
# Municipios
# ---------------------------------------------------------------------------


class MunicipioListView(CrudListView):
    model = Municipio
    nombre_singular = "municipio"
    nombre_plural = "municipios"
    search_fields = ["nombre", "departamento__nombre", "departamento__pais__nombre"]
    columnas = [
        {"campo": "nombre", "etiqueta": "Nombre"},
        {"campo": "departamento__nombre", "etiqueta": "Departamento"},
        {"campo": "departamento__pais__nombre", "etiqueta": "País"},
    ]
    select_related = ("departamento", "departamento__pais")
    url_lista = "ubicacion:municipio_lista"
    url_crear = "ubicacion:municipio_crear"
    url_editar = "ubicacion:municipio_editar"
    url_eliminar = "ubicacion:municipio_eliminar"


class MunicipioCreateView(CrudCreateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = "ubicacion/municipio_form.html"
    nombre_singular = "municipio"
    nombre_plural = "municipios"
    url_lista = "ubicacion:municipio_lista"


class MunicipioUpdateView(CrudUpdateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = "ubicacion/municipio_form.html"
    nombre_singular = "municipio"
    nombre_plural = "municipios"
    url_lista = "ubicacion:municipio_lista"


class MunicipioDeleteView(CrudDeleteView):
    model = Municipio
    nombre_singular = "municipio"
    nombre_plural = "municipios"
    url_lista = "ubicacion:municipio_lista"


# ---------------------------------------------------------------------------
# Endpoints JSON para selects encadenados
# ---------------------------------------------------------------------------


def _id_de_parametro(request, parametro):
    """Devuelve el entero del parámetro GET o ``None`` si falta o no es válido."""
    valor = request.GET.get(parametro, "")
    if not valor or not valor.isdigit():
        return None
    return int(valor)


def api_departamentos(request):
    pais_id = _id_de_parametro(request, "pais")
    if pais_id is None:
        return JsonResponse({"error": "El parámetro 'pais' es obligatorio"}, status=400)
    departamentos = Departamento.objects.filter(pais_id=pais_id).order_by("nombre")
    datos = [{"id": d.pk, "nombre": d.nombre} for d in departamentos]
    return JsonResponse(datos, safe=False)


def api_municipios(request):
    departamento_id = _id_de_parametro(request, "departamento")
    if departamento_id is None:
        return JsonResponse({"error": "El parámetro 'departamento' es obligatorio"}, status=400)
    municipios = Municipio.objects.filter(departamento_id=departamento_id).order_by("nombre")
    datos = [{"id": m.pk, "nombre": m.nombre} for m in municipios]
    return JsonResponse(datos, safe=False)
