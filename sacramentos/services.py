from .models import HistorialSacramento


def registrar_historial(sacramento, accion, descripcion="", usuario=None):
    """Registra un movimiento en el historial de un sacramento."""
    return HistorialSacramento.objects.create(
        sacramento=sacramento,
        accion=accion,
        descripcion=descripcion,
        usuario=usuario,
    )
