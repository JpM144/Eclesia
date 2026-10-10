from django.urls import path

from . import views

app_name = "personas"

urlpatterns = [
    # Consulta de personas (solo lectura)
    path("consultar/", views.consultar_personas, name="consultar"),
    # Edición individual de personas (se crean desde las partidas)
    path("padres/<int:pk>/editar/", views.PadreUpdateView.as_view(), name="padre_editar"),
    path("madres/<int:pk>/editar/", views.MadreUpdateView.as_view(), name="madre_editar"),
    path("padrinos/<int:pk>/editar/", views.PadrinoUpdateView.as_view(), name="padrino_editar"),
    path("fieles/<int:pk>/editar/", views.FielUpdateView.as_view(), name="fiel_editar"),
    # API
    path("api/padre/", views.api_padre, name="api_padre"),
    path("api/madre/", views.api_madre, name="api_madre"),
]
