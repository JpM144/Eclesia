"""Procesadores de contexto globales."""

from django.conf import settings

from core.choices import EstadoAnotacion
from sacramentos.models import AnotacionMarginal


def anotaciones_pendientes(request):
    """Datos de la campana de la barra superior.

    Solo consulta para usuarios autenticados y hace exactamente dos consultas:
    el total de anotaciones por comunicar y las cinco más recientes.
    """
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}

    pendientes = AnotacionMarginal.objects.filter(estado=EstadoAnotacion.POR_COMUNICAR)
    recientes = pendientes.select_related("parroquia_destino").order_by("-creado_en", "-id")[:5]
    return {
        "anotaciones_pendientes_total": pendientes.count(),
        "anotaciones_pendientes_recientes": list(recientes),
    }


def nombre_parroquia(request):
    """Nombre de la parroquia para las plantillas, sin consultar la base.

    Se lee de la configuración en cada petición para que ``override_settings``
    funcione en los tests.
    """
    return {"nombre_parroquia": settings.NOMBRE_PARROQUIA}
