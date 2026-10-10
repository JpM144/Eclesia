"""Búsqueda de personas y recuento de las partidas en que aparecen.

La pantalla "Consultar personas" usa estas funciones para localizar personas
por documento o por nombre y para reunir, sin consultas N+1, las partidas
(\"sacramentos\") donde cada una aparece.
"""

from collections import defaultdict

from django.db.models import Q
from django.urls import reverse

from core.choices import TipoSacramento
from sacramentos.models import (
    Bautismo,
    Confirmacion,
    Contrayente,
    PadrinoMatrimonio,
    PrimeraComunion,
    Sacramento,
    TestigoMatrimonio,
)

from .models import Fiel, Madre, Padre, Padrino

LIMITE_PERSONAS = 50

FIEL = "fiel"
PADRE = "padre"
MADRE = "madre"
PADRINO = "padrino"
TESTIGO = "testigo"
PADRINO_MATRIMONIO = "padrino_matrimonio"

ETIQUETAS_TIPO = {
    FIEL: "Fiel",
    PADRE: "Padre",
    MADRE: "Madre",
    PADRINO: "Padrino",
    TESTIGO: "Testigo de matrimonio",
    PADRINO_MATRIMONIO: "Padrino de matrimonio",
}

# Rol que se muestra según el tipo de sacramento del que la persona es titular.
ROL_TITULAR = {
    TipoSacramento.BAUTISMO: "bautizado",
    TipoSacramento.CONFIRMACION: "confirmado",
    TipoSacramento.PRIMERA_COMUNION: "primera comunión",
}


def es_busqueda_por_documento(q):
    """True si ``q`` (ya recortado) es solo dígitos, con puntos o espacios."""
    return q.replace(".", "").replace(" ", "").isdigit()


def buscar_personas(q):
    """Devuelve ``(personas, hay_mas)`` para el término ``q``.

    ``personas`` es una lista de diccionarios (máximo ``LIMITE_PERSONAS``),
    ordenada por nombre. ``hay_mas`` indica si existen más resultados.
    """
    if es_busqueda_por_documento(q):
        valor = q.replace(".", "").replace(" ", "")
        personas = _buscar_por_documento(valor, exacto=True)
        if not personas:
            personas = _buscar_por_documento(valor, exacto=False)
    else:
        personas = _buscar_por_nombre(q)

    personas.sort(key=lambda persona: persona["nombre"].lower())
    hay_mas = len(personas) > LIMITE_PERSONAS
    personas = personas[:LIMITE_PERSONAS]
    _cargar_partidas(personas)
    return personas, hay_mas


def _buscar_por_documento(valor, exacto):
    sufijo = "exact" if exacto else "icontains"
    personas = []
    fieles = (
        Fiel.objects.filter(**{f"documento__numero_documento__{sufijo}": valor})
        .select_related("documento")
        .order_by("nombres", "apellidos")[: LIMITE_PERSONAS + 1]
    )
    personas += [_persona_fiel(fiel) for fiel in fieles]

    padres = Padre.objects.filter(**{f"cedula__{sufijo}": valor}).order_by("nombre", "apellido")[
        : LIMITE_PERSONAS + 1
    ]
    personas += [_persona_simple(PADRE, padre) for padre in padres]

    madres = Madre.objects.filter(**{f"cedula__{sufijo}": valor}).order_by("nombre", "apellido")[
        : LIMITE_PERSONAS + 1
    ]
    personas += [_persona_simple(MADRE, madre) for madre in madres]

    padrinos = (
        Padrino.objects.filter(**{f"documento__numero_documento__{sufijo}": valor})
        .select_related("documento")
        .order_by("nombre")[: LIMITE_PERSONAS + 1]
    )
    personas += [_persona_padrino(padrino) for padrino in padrinos]

    testigos = TestigoMatrimonio.objects.filter(**{f"cedula__{sufijo}": valor}).order_by("nombre")[
        : LIMITE_PERSONAS + 1
    ]
    personas += [_persona_testigo(testigo) for testigo in testigos]

    padrinos_matrimonio = PadrinoMatrimonio.objects.filter(**{f"cedula__{sufijo}": valor}).order_by(
        "nombre"
    )[: LIMITE_PERSONAS + 1]
    personas += [_persona_padrino_matrimonio(padrino) for padrino in padrinos_matrimonio]
    return personas


def _buscar_por_nombre(q):
    palabras = q.split()
    return [
        *(
            _persona_fiel(fiel)
            for fiel in _filtrar_palabras(Fiel.objects, ["nombres", "apellidos"], palabras)
            .select_related("documento")
            .order_by("nombres", "apellidos")[: LIMITE_PERSONAS + 1]
        ),
        *(
            _persona_simple(PADRE, padre)
            for padre in _filtrar_palabras(
                Padre.objects, ["nombre", "apellido"], palabras
            ).order_by("nombre", "apellido")[: LIMITE_PERSONAS + 1]
        ),
        *(
            _persona_simple(MADRE, madre)
            for madre in _filtrar_palabras(
                Madre.objects, ["nombre", "apellido"], palabras
            ).order_by("nombre", "apellido")[: LIMITE_PERSONAS + 1]
        ),
        *(
            _persona_padrino(padrino)
            for padrino in _filtrar_palabras(Padrino.objects, ["nombre"], palabras).order_by(
                "nombre"
            )[: LIMITE_PERSONAS + 1]
        ),
        *(
            _persona_testigo(testigo)
            for testigo in _filtrar_palabras(
                TestigoMatrimonio.objects, ["nombre"], palabras
            ).order_by("nombre")[: LIMITE_PERSONAS + 1]
        ),
        *(
            _persona_padrino_matrimonio(padrino)
            for padrino in _filtrar_palabras(
                PadrinoMatrimonio.objects, ["nombre"], palabras
            ).order_by("nombre")[: LIMITE_PERSONAS + 1]
        ),
    ]


def _filtrar_palabras(queryset, campos, palabras):
    for palabra in palabras:
        condicion = Q()
        for campo in campos:
            condicion |= Q(**{f"{campo}__icontains": palabra})
        queryset = queryset.filter(condicion)
    return queryset


def _persona_fiel(fiel):
    return {
        "tipo": FIEL,
        "etiqueta_tipo": ETIQUETAS_TIPO[FIEL],
        "pk": fiel.pk,
        "nombre": str(fiel),
        "documento": str(fiel.documento),
        "editable": True,
        "url_editar": reverse("personas:fiel_editar", args=[fiel.pk]),
        "partidas": [],
    }


def _persona_simple(tipo, persona):
    return {
        "tipo": tipo,
        "etiqueta_tipo": ETIQUETAS_TIPO[tipo],
        "pk": persona.pk,
        "nombre": str(persona),
        "documento": persona.cedula,
        "editable": True,
        "url_editar": reverse(f"personas:{tipo}_editar", args=[persona.pk]),
        "partidas": [],
    }


def _persona_padrino(padrino):
    return {
        "tipo": PADRINO,
        "etiqueta_tipo": ETIQUETAS_TIPO[PADRINO],
        "pk": padrino.pk,
        "nombre": str(padrino),
        "documento": str(padrino.documento) if padrino.documento_id else "—",
        "editable": True,
        "url_editar": reverse("personas:padrino_editar", args=[padrino.pk]),
        "partidas": [],
    }


def _persona_testigo(testigo):
    return {
        "tipo": TESTIGO,
        "etiqueta_tipo": ETIQUETAS_TIPO[TESTIGO],
        "pk": testigo.pk,
        "nombre": testigo.nombre,
        "documento": f"{testigo.get_tipo_documento_display()} {testigo.cedula}",
        "editable": False,
        "url_editar": None,
        "partidas": [],
    }


def _persona_padrino_matrimonio(padrino):
    return {
        "tipo": PADRINO_MATRIMONIO,
        "etiqueta_tipo": ETIQUETAS_TIPO[PADRINO_MATRIMONIO],
        "pk": padrino.pk,
        "nombre": padrino.nombre,
        "documento": f"{padrino.get_tipo_documento_display()} {padrino.cedula}",
        "editable": False,
        "url_editar": None,
        "partidas": [],
    }


def _fila(sacramento, rol):
    return {
        "rol": rol,
        "tipo_sacramento": sacramento.get_tipo_display(),
        "fecha": sacramento.fecha,
        "libro": str(sacramento.folio.libro),
        "folio": sacramento.folio.numero_folio,
        "numero": sacramento.numero,
    }


def _cargar_partidas(personas):
    """Rellena ``partidas`` de cada persona con consultas por lote (sin N+1)."""
    por_persona = defaultdict(list)
    fieles = [persona["pk"] for persona in personas if persona["tipo"] == FIEL]
    padres = [persona["pk"] for persona in personas if persona["tipo"] == PADRE]
    madres = [persona["pk"] for persona in personas if persona["tipo"] == MADRE]
    padrinos = [persona["pk"] for persona in personas if persona["tipo"] == PADRINO]
    testigos = [persona["pk"] for persona in personas if persona["tipo"] == TESTIGO]
    padrinos_matrimonio = [
        persona["pk"] for persona in personas if persona["tipo"] == PADRINO_MATRIMONIO
    ]

    if fieles:
        for sacramento in Sacramento.objects.filter(fiel_id__in=fieles).select_related(
            "folio__libro"
        ):
            rol = ROL_TITULAR.get(sacramento.tipo)
            if rol:
                por_persona[(FIEL, sacramento.fiel_id)].append(_fila(sacramento, rol))
        for contrayente in Contrayente.objects.filter(fiel_id__in=fieles).select_related(
            "matrimonio__sacramento__folio__libro"
        ):
            por_persona[(FIEL, contrayente.fiel_id)].append(
                _fila(contrayente.matrimonio.sacramento, "contrayente")
            )

    if padres or madres or padrinos:
        conjuntos = (set(padres), set(madres), set(padrinos))
        for bautismo in Bautismo.objects.filter(
            Q(padre_id__in=padres)
            | Q(madre_id__in=madres)
            | Q(padrino_id__in=padrinos)
            | Q(madrina_id__in=padrinos)
        ).select_related("sacramento__folio__libro"):
            _agregar_padres_padrinos(por_persona, bautismo, *conjuntos)
        for confirmacion in Confirmacion.objects.filter(
            Q(padre_id__in=padres)
            | Q(madre_id__in=madres)
            | Q(padrino_id__in=padrinos)
            | Q(madrina_id__in=padrinos)
        ).select_related("sacramento__folio__libro"):
            _agregar_padres_padrinos(por_persona, confirmacion, *conjuntos)
        for comunion in PrimeraComunion.objects.filter(
            Q(padre_id__in=padres) | Q(madre_id__in=madres)
        ).select_related("sacramento__folio__libro"):
            _agregar_padres_padrinos(por_persona, comunion, *conjuntos)

    if testigos:
        for testigo in TestigoMatrimonio.objects.filter(pk__in=testigos).select_related(
            "matrimonio__sacramento__folio__libro"
        ):
            por_persona[(TESTIGO, testigo.pk)].append(
                _fila(testigo.matrimonio.sacramento, "testigo")
            )

    if padrinos_matrimonio:
        for padrino in PadrinoMatrimonio.objects.filter(pk__in=padrinos_matrimonio).select_related(
            "matrimonio__sacramento__folio__libro"
        ):
            por_persona[(PADRINO_MATRIMONIO, padrino.pk)].append(
                _fila(padrino.matrimonio.sacramento, "padrino")
            )

    for persona in personas:
        claves = (persona["tipo"], persona["pk"])
        filas = por_persona.get(claves, [])
        filas.sort(key=lambda fila: (fila["fecha"], fila["numero"]))
        persona["partidas"] = filas


def _agregar_padres_padrinos(por_persona, datos, padres, madres, padrinos):
    sacramento = datos.sacramento
    if datos.padre_id in padres:
        por_persona[(PADRE, datos.padre_id)].append(_fila(sacramento, "padre"))
    if datos.madre_id in madres:
        por_persona[(MADRE, datos.madre_id)].append(_fila(sacramento, "madre"))
    padrino_id = getattr(datos, "padrino_id", None)
    madrina_id = getattr(datos, "madrina_id", None)
    if padrino_id in padrinos:
        por_persona[(PADRINO, padrino_id)].append(_fila(sacramento, "padrino"))
    if madrina_id in padrinos:
        por_persona[(PADRINO, madrina_id)].append(_fila(sacramento, "madrina"))


def contar_partidas(tipo, pk):
    """Número de partidas distintas en las que aparece la persona."""
    if tipo == FIEL:
        condicion = Q(fiel_id=pk) | Q(matrimonio__contrayentes__fiel_id=pk)
    elif tipo == PADRE:
        condicion = (
            Q(bautismo__padre_id=pk)
            | Q(confirmacion__padre_id=pk)
            | Q(primera_comunion__padre_id=pk)
        )
    elif tipo == MADRE:
        condicion = (
            Q(bautismo__madre_id=pk)
            | Q(confirmacion__madre_id=pk)
            | Q(primera_comunion__madre_id=pk)
        )
    elif tipo == PADRINO:
        condicion = (
            Q(bautismo__padrino_id=pk)
            | Q(bautismo__madrina_id=pk)
            | Q(confirmacion__padrino_id=pk)
            | Q(confirmacion__madrina_id=pk)
        )
    elif tipo == TESTIGO:
        condicion = Q(matrimonio__testigos__id=pk)
    elif tipo == PADRINO_MATRIMONIO:
        condicion = Q(matrimonio__padrinos__id=pk)
    else:
        return 0
    return Sacramento.objects.filter(condicion).distinct().count()
