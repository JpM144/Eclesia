from django.urls import path

from . import views

app_name = "parroquias"

urlpatterns = [
    # Parroquias
    path("", views.ParroquiaListView.as_view(), name="parroquia_lista"),
    path("nuevo/", views.ParroquiaCreateView.as_view(), name="parroquia_crear"),
    path("<int:pk>/editar/", views.ParroquiaUpdateView.as_view(), name="parroquia_editar"),
    path("<int:pk>/eliminar/", views.ParroquiaDeleteView.as_view(), name="parroquia_eliminar"),
    # Ministros
    path("ministros/", views.MinistroListView.as_view(), name="ministro_lista"),
    path("ministros/nuevo/", views.MinistroCreateView.as_view(), name="ministro_crear"),
    path(
        "ministros/<int:pk>/editar/",
        views.MinistroUpdateView.as_view(),
        name="ministro_editar",
    ),
    path(
        "ministros/<int:pk>/eliminar/",
        views.MinistroDeleteView.as_view(),
        name="ministro_eliminar",
    ),
    # Libros
    path("libros/", views.LibroListView.as_view(), name="libro_lista"),
    path("libros/nuevo/", views.LibroCreateView.as_view(), name="libro_crear"),
    path("libros/<int:pk>/editar/", views.LibroUpdateView.as_view(), name="libro_editar"),
    path("libros/<int:pk>/cerrar/", views.LibroCerrarView.as_view(), name="libro_cerrar"),
    path("libros/<int:pk>/indice/", views.LibroIndiceView.as_view(), name="libro_indice"),
    path("libros/<int:pk>/eliminar/", views.LibroDeleteView.as_view(), name="libro_eliminar"),
    # Iglesias
    path("iglesias/", views.IglesiaListView.as_view(), name="iglesia_lista"),
    path("iglesias/nuevo/", views.IglesiaCreateView.as_view(), name="iglesia_crear"),
    path("iglesias/<int:pk>/editar/", views.IglesiaUpdateView.as_view(), name="iglesia_editar"),
    path(
        "iglesias/<int:pk>/eliminar/",
        views.IglesiaDeleteView.as_view(),
        name="iglesia_eliminar",
    ),
    # Folios (anidados en el libro)
    path(
        "libros/<int:libro_id>/folios/",
        views.FolioListView.as_view(),
        name="folio_lista",
    ),
    path(
        "libros/<int:libro_id>/folios/nuevo/",
        views.FolioCreateView.as_view(),
        name="folio_crear",
    ),
    path(
        "libros/<int:libro_id>/folios/<int:pk>/editar/",
        views.FolioUpdateView.as_view(),
        name="folio_editar",
    ),
    path(
        "libros/<int:libro_id>/folios/<int:pk>/eliminar/",
        views.FolioDeleteView.as_view(),
        name="folio_eliminar",
    ),
]
