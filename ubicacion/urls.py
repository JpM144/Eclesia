from django.urls import path

from . import views

app_name = "ubicacion"

urlpatterns = [
    # Países
    path("paises/", views.PaisListView.as_view(), name="pais_lista"),
    path("paises/nuevo/", views.PaisCreateView.as_view(), name="pais_crear"),
    path("paises/<int:pk>/editar/", views.PaisUpdateView.as_view(), name="pais_editar"),
    path("paises/<int:pk>/eliminar/", views.PaisDeleteView.as_view(), name="pais_eliminar"),
    # Departamentos
    path("departamentos/", views.DepartamentoListView.as_view(), name="departamento_lista"),
    path(
        "departamentos/nuevo/",
        views.DepartamentoCreateView.as_view(),
        name="departamento_crear",
    ),
    path(
        "departamentos/<int:pk>/editar/",
        views.DepartamentoUpdateView.as_view(),
        name="departamento_editar",
    ),
    path(
        "departamentos/<int:pk>/eliminar/",
        views.DepartamentoDeleteView.as_view(),
        name="departamento_eliminar",
    ),
    # Municipios
    path("municipios/", views.MunicipioListView.as_view(), name="municipio_lista"),
    path("municipios/nuevo/", views.MunicipioCreateView.as_view(), name="municipio_crear"),
    path(
        "municipios/<int:pk>/editar/",
        views.MunicipioUpdateView.as_view(),
        name="municipio_editar",
    ),
    path(
        "municipios/<int:pk>/eliminar/",
        views.MunicipioDeleteView.as_view(),
        name="municipio_eliminar",
    ),
    # API para selects encadenados
    path("api/departamentos/", views.api_departamentos, name="api_departamentos"),
    path("api/municipios/", views.api_municipios, name="api_municipios"),
]
