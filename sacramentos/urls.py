from django.urls import path

from . import views

app_name = "sacramentos"

urlpatterns = [
    path("bautismos/", views.BautismoListView.as_view(), name="bautismo_lista"),
    path("bautismos/nuevo/", views.BautismoCreateView.as_view(), name="bautismo_crear"),
    path("bautismos/<int:pk>/", views.BautismoDetailView.as_view(), name="bautismo_detalle"),
    path(
        "bautismos/<int:pk>/certificado/",
        views.BautismoCertificadoView.as_view(),
        name="bautismo_certificado",
    ),
    path("bautismos/<int:pk>/editar/", views.BautismoUpdateView.as_view(), name="bautismo_editar"),
    path("bautismos/<int:pk>/anular/", views.BautismoAnularView.as_view(), name="bautismo_anular"),
    path(
        "bautismos/<int:pk>/eliminar/",
        views.BautismoEliminarView.as_view(),
        name="bautismo_eliminar",
    ),
]
