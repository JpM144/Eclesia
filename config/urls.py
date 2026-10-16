"""URL configuration for config project.

See https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("ubicacion/", include("ubicacion.urls")),
    path("parroquias/", include("parroquias.urls")),
    path("personas/", include("personas.urls")),
    path("sacramentos/", include("sacramentos.urls")),
    path("cuentas/", include("cuentas.urls")),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
