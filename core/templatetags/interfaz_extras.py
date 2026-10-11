from django import template

register = template.Library()


@register.filter
def iniciales(usuario):
    """Iniciales del usuario para el avatar.

    Toma la primera letra de la primera y de la última palabra del nombre
    completo; si no hay apellido, las dos primeras letras de la unica palabra.
    """
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return ""
    nombre = usuario.get_full_name().strip() or usuario.get_username() or ""
    partes = [parte for parte in nombre.split() if parte]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()
