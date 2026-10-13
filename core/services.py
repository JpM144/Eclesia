"""Datos del dashboard.

Todo el cálculo se concentra aquí para que la vista quede fina y para poder
probar la lógica de negocio (variaciones, serie mensual, historial) con fechas
fijas. Las consultas están pensadas para no crecer con el tamaño de los datos:
agregados, una sola consulta agrupada por mes y una lista de historial.
"""

from datetime import date

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.choices import AccionHistorial, EstadoRegistro, TipoSacramento
from sacramentos.models import HistorialSacramento, Sacramento

# Orden con el que se muestran las series y las tarjetas.
TIPOS_SACRAMENTO = (
    TipoSacramento.BAUTISMO,
    TipoSacramento.PRIMERA_COMUNION,
    TipoSacramento.CONFIRMACION,
    TipoSacramento.MATRIMONIO,
)

MESES_ABREVIADOS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

# Clase CSS con el color de cada sacramento (ver static/css/dashboard.css).
CLASES_TIPO = {
    TipoSacramento.BAUTISMO: "bautismo",
    TipoSacramento.PRIMERA_COMUNION: "primera-comunion",
    TipoSacramento.CONFIRMACION: "confirmacion",
    TipoSacramento.MATRIMONIO: "matrimonio",
}

# Participio con el que se redacta cada movimiento del historial.
VERBOS_HISTORIAL = {
    AccionHistorial.CREACION: "creado",
    AccionHistorial.MODIFICACION: "modificado",
    AccionHistorial.ANULACION: "anulado",
    AccionHistorial.CORRECCION: "corregido",
    AccionHistorial.ARCHIVADO: "archivado",
}


def _primer_dia_mes(una_fecha):
    return date(una_fecha.year, una_fecha.month, 1)


def _sumar_meses(una_fecha, meses):
    indice = una_fecha.year * 12 + (una_fecha.month - 1) + meses
    return date(indice // 12, indice % 12 + 1, 1)


def _ultimos_doce_meses(hoy):
    primer_dia = _primer_dia_mes(hoy)
    return [_sumar_meses(primer_dia, desplazamiento) for desplazamiento in range(-11, 1)]


def _variacion(actual, anterior):
    """Compara el mes actual con el anterior.

    Devuelve el texto de la variación y la dirección para elegir el ícono
    (verde hacia arriba, rojo hacia abajo o gris si es igual).
    """
    if anterior == 0:
        if actual == 0:
            return {"valor": "Sin cambios", "direccion": "igual"}
        return {"valor": "Nuevo", "direccion": "sube"}
    if actual == anterior:
        return {"valor": "0%", "direccion": "igual"}
    porcentaje = round((actual - anterior) / anterior * 100)
    if actual > anterior:
        return {"valor": f"+{porcentaje}%", "direccion": "sube"}
    return {"valor": f"{porcentaje}%", "direccion": "baja"}


def _nombre_usuario(usuario):
    if usuario is None:
        return "el sistema"
    return usuario.get_full_name().strip() or usuario.username


def _ultimas_actividades(limite=5):
    registros = HistorialSacramento.objects.select_related("sacramento", "usuario").order_by(
        "-fecha", "-id"
    )[:limite]
    actividades = []
    for registro in registros:
        sacramento = registro.sacramento
        actividades.append(
            {
                "tipo": sacramento.tipo,
                "tipo_css": CLASES_TIPO.get(sacramento.tipo, "otro"),
                "texto": (
                    f"{sacramento.get_tipo_display()} "
                    f"{VERBOS_HISTORIAL.get(registro.accion, 'actualizado')} "
                    f"por {_nombre_usuario(registro.usuario)}"
                ),
                "fecha": registro.fecha,
            }
        )
    return actividades


def resumen_dashboard(hoy=None):
    """Devuelve todo el contexto del dashboard."""
    if hoy is None:
        hoy = timezone.localdate()
    meses = _ultimos_doce_meses(hoy)
    inicio = meses[0]
    limite = _sumar_meses(meses[-1], 1)

    activos = Sacramento.objects.exclude(estado=EstadoRegistro.ANULADO)
    totales = activos.aggregate(
        bautismos=Count("pk", filter=Q(tipo=TipoSacramento.BAUTISMO)),
        primeras_comuniones=Count("pk", filter=Q(tipo=TipoSacramento.PRIMERA_COMUNION)),
        confirmaciones=Count("pk", filter=Q(tipo=TipoSacramento.CONFIRMACION)),
        matrimonios=Count("pk", filter=Q(tipo=TipoSacramento.MATRIMONIO)),
    )

    filas = (
        activos.filter(fecha__gte=inicio, fecha__lt=limite)
        .annotate(mes=TruncMonth("fecha"))
        .values("mes", "tipo")
        .annotate(total=Count("pk"))
    )
    conteos = {(fila["mes"].year, fila["mes"].month, fila["tipo"]): fila["total"] for fila in filas}

    series = {}
    for tipo in TIPOS_SACRAMENTO:
        series[tipo.value] = [conteos.get((mes.year, mes.month, tipo.value), 0) for mes in meses]

    etiquetas = [f"{MESES_ABREVIADOS[mes.month - 1]} {mes.year}" for mes in meses]
    variaciones = {
        tipo.value: _variacion(series[tipo.value][-1], series[tipo.value][-2])
        for tipo in TIPOS_SACRAMENTO
    }

    return {
        "totales": totales,
        "series": series,
        "etiquetas": etiquetas,
        "variaciones": variaciones,
        "actividades": _ultimas_actividades(),
        "datos_grafico": {"etiquetas": etiquetas, "series": series},
        "hay_datos_grafico": any(any(valores) for valores in series.values()),
    }
