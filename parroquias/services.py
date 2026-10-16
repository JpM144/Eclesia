from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max

from core.choices import EstadoLibro, EstadoRegistro, TipoSacramento
from sacramentos.models import Sacramento


def siguiente_numero_partida(libro):
    """Devuelve el siguiente número correlativo de partida dentro del libro."""
    ultimo = libro.sacramentos.aggregate(Max("numero"))["numero__max"]
    return (ultimo or 0) + 1


def folio_para_nueva_partida(libro):
    """Folio que corresponde a la siguiente partida del libro, creándolo si falta.

    Cada folio admite ``libro.partidas_por_folio`` partidas. Se continúa en el
    folio de la última partida mientras le queden espacios y, cuando se llena,
    se pasa al siguiente. Las partidas anuladas también cuentan porque siguen
    ocupando su lugar en el libro. Si se agotó el total de folios declarado, no
    se puede registrar otra partida y se lanza ``ValidationError``.
    """
    resumen = (
        Sacramento.objects.filter(libro=libro)
        .values("folio__numero_folio")
        .annotate(total=Count("id"))
    )
    if not resumen:
        numero = 1
    else:
        ultimo = max(fila["folio__numero_folio"] for fila in resumen)
        ocupadas = next(fila["total"] for fila in resumen if fila["folio__numero_folio"] == ultimo)
        numero = ultimo if ocupadas < libro.partidas_por_folio else ultimo + 1

    if libro.total_folios and numero > libro.total_folios:
        raise ValidationError(
            "El libro está lleno: ciérralo y abre uno nuevo para seguir registrando."
        )

    folio, _ = libro.folios.get_or_create(numero_folio=numero)
    return folio


@transaction.atomic
def cerrar_libro(libro, ministro, fecha, nota=""):
    """Cierra un libro abierto guardando la diligencia de cierre.

    Valida que el libro esté abierto y que la fecha de cierre no sea anterior a
    la apertura ni a la última partida registrada. Lanza ``ValidationError`` con
    un mensaje claro cuando no se puede cerrar.
    """
    if libro.estado != EstadoLibro.ABIERTO:
        raise ValidationError("El libro ya está cerrado.")

    ultima = libro.sacramentos.aggregate(Max("fecha_registro"))["fecha_registro__max"]
    if fecha < libro.fecha_apertura:
        raise ValidationError("La fecha de cierre no puede ser anterior a la apertura del libro.")
    if ultima and fecha < ultima:
        raise ValidationError(
            "La fecha de cierre no puede ser anterior a la última partida del libro."
        )

    libro.estado = EstadoLibro.CERRADO
    libro.fecha_cierre = fecha
    libro.ministro_cierre = ministro
    libro.nota_cierre = nota
    libro.save(update_fields=["estado", "fecha_cierre", "ministro_cierre", "nota_cierre"])
    return libro


def _entrada_indice(partida, fiel):
    return {
        "apellidos": fiel.apellidos if fiel else "",
        "nombres": fiel.nombres if fiel else "",
        "numero": partida.numero,
        "folio": partida.folio.numero_folio,
        "fecha": partida.fecha,
        "tipo": partida.tipo,
    }


def indice_libro(libro):
    """Índice alfabético de las partidas no anuladas de un libro.

    En bautismo, primera comunión y confirmación se indexa por el fiel; en
    matrimonio se genera una entrada por cada contrayente. Devuelve una lista de
    diccionarios con apellidos, nombres, número, folio y fecha, ordenada por
    apellidos y nombres y sin consultas N+1.
    """
    partidas = (
        Sacramento.objects.filter(libro=libro)
        .exclude(estado=EstadoRegistro.ANULADO)
        .select_related("fiel", "folio")
        .prefetch_related("matrimonio__contrayentes__fiel")
        .order_by("fecha", "numero")
    )

    entradas = []
    for partida in partidas:
        if partida.tipo == TipoSacramento.MATRIMONIO:
            for contrayente in partida.matrimonio.contrayentes.all():
                entradas.append(_entrada_indice(partida, contrayente.fiel))
        else:
            entradas.append(_entrada_indice(partida, partida.fiel))

    entradas.sort(key=lambda entrada: (entrada["apellidos"], entrada["nombres"], entrada["numero"]))
    return entradas
