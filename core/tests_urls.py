"""URLconf reducido para probar el manejo de 403 (no se usa en producción)."""

from django.core.exceptions import PermissionDenied
from django.urls import path


def solo_prohibido(request):
    raise PermissionDenied


urlpatterns = [
    path("prohibido/", solo_prohibido),
]
