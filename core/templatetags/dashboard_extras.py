from datetime import timedelta

from django import template
from django.utils import timezone

register = template.Library()

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _hora(dt):
    hora = dt.hour % 12 or 12
    sufijo = "a. m." if dt.hour < 12 else "p. m."
    return f"{hora}:{dt.minute:02d} {sufijo}"


@register.filter
def fecha_relativa(valor):
    """Fecha en español: "Hoy, 10:24 a. m.", "Ayer, 4:32 p. m." o la fecha completa."""
    if not valor:
        return ""
    local = timezone.localtime(valor)
    dia = local.date()
    hoy = timezone.localdate()
    if dia == hoy:
        return f"Hoy, {_hora(local)}"
    if dia == hoy - timedelta(days=1):
        return f"Ayer, {_hora(local)}"
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"
