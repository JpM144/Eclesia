from django import template

register = template.Library()


@register.filter
def atributo(objeto, ruta):
    """Devuelve el valor de una ruta con doble guion bajo.

    Se usa en la plantilla genérica ``crud/lista.html`` para mostrar cualquier
    columna declarada en la vista, por ejemplo ``{{ objeto|atributo:"pais__nombre" }}``.
    Si el valor final es un método o propiedad, se invoca.
    """
    if objeto is None:
        return ""
    for parte in str(ruta).split("__"):
        objeto = getattr(objeto, parte, None)
        if objeto is None:
            return ""
    if callable(objeto):
        return objeto()
    return objeto


@register.simple_tag(takes_context=True)
def url_con_page(context, numero):
    """Devuelve la URL actual cambiando solo el parámetro ``page``.

    Conserva la búsqueda y los filtros (``q``, ``parroquia``, ``tipo``, ...) al
    paginar, de modo que las listas filtradas no pierdan el filtro.
    """
    consulta = context["request"].GET.copy()
    consulta["page"] = numero
    return f"?{consulta.urlencode()}"
