"""Búsqueda de personas y ficha individual.

La pantalla "Consultar personas" busca por documento o por nombre y agrupa
por ``Documento``: cada resultado es una persona con todos sus papeles
(fiel, padre, madre, padrino, ministro y testigos/padrinos de matrimonio).
La ficha de persona reúne sus sacramentos, familia y relaciones, sus
actuaciones como ministro o testigo y el historial de las partidas donde
aparece. Todo se consulta por lote (``select_related`` y ``__in``), sin
consultas N+1.
"""

from collections import defaultdict
from datetime import date
from functools import reduce
from operator import or_

from django.db.models import Q
from django.urls import reverse

from core.choices import TipoSacramento
from core.management.commands.cargar_datos_demo import PREFIJO_DOCUMENTO
from parroquias.models import Libro, Ministro, Parroquia
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    HistorialSacramento,
    PadrinoMatrimonio,
    PrimeraComunion,
    Sacramento,
    TestigoMatrimonio,
)

from .models import Documento, Fiel, Madre, Padre, Padrino

LIMITE_PERSONAS = 50

FIEL = "fiel"
PADRE = "padre"
MADRE = "madre"
PADRINO = "padrino"
TESTIGO = "testigo"
PADRINO_MATRIMONIO = "padrino_matrimonio"
MINISTRO = "ministro"

ETIQUETAS_TIPO = {
    FIEL: "Fiel",
    PADRE: "Padre",
    MADRE: "Madre",
    PADRINO: "Padrino",
    MINISTRO: "Ministro",
    TESTIGO: "Testigo de matrimonio",
    PADRINO_MATRIMONIO: "Padrino de matrimonio",
}

# Orden de presentación y prioridad del nombre principal por documento.
ORDEN_PAPELES = (FIEL, PADRE, MADRE, MINISTRO, PADRINO, TESTIGO, PADRINO_MATRIMONIO)

# Roles editables: se corrigen desde la ficha de persona.
PAPELES_EDITABLES = (FIEL, PADRE, MADRE, PADRINO)

# Rol que se muestra según el tipo de sacramento del que la persona es titular.
ROL_TITULAR = {
    TipoSacramento.BAUTISMO: "bautizado",
    TipoSacramento.CONFIRMACION: "confirmado",
    TipoSacramento.PRIMERA_COMUNION: "primera comunión",
}

# Campos de texto libre del Bautismo que mencionan a una persona sin documento.
CAMPOS_MENCION_BAUTISMO = (
    ("abuelo_paterno", "Abuelo paterno"),
    ("abuela_paterna", "Abuela paterna"),
    ("abuelo_materno", "Abuelo materno"),
    ("abuela_materna", "Abuela materna"),
    ("testigo_nombre", "Testigo"),
    ("padre_biologico_nombre", "Padre biológico"),
    ("madre_biologica_nombre", "Madre biológica"),
)


def es_busqueda_por_documento(q):
    """True si ``q`` (ya recortado) es solo dígitos, con puntos o espacios."""
    return q.replace(".", "").replace(" ", "").isdigit()


def buscar_personas(q):
    """Devuelve ``(personas, hay_mas)`` para el término ``q``.

    Cada elemento de ``personas`` es un diccionario con los datos de una
    persona agrupada por su ``Documento``: nombre principal, registros
    alternativos, documento, papeles (con insignia y, para los editables, su
    enlace) y el total de partidas en que aparece.
    """
    q = q.strip()
    if es_busqueda_por_documento(q):
        valor = q.replace(".", "").replace(" ", "")
        documentos = list(Documento.objects.filter(numero_documento=valor))
        if not documentos:
            documentos = list(
                Documento.objects.filter(numero_documento__icontains=valor).order_by(
                    "numero_documento"
                )[: LIMITE_PERSONAS + 1]
            )
    else:
        documentos = _documentos_por_nombre(q)

    roles = _roles_por_documento(documentos)
    personas = [
        _persona_por_documento(documento, roles[documento.pk])
        for documento in documentos
        if roles[documento.pk]
    ]
    personas.sort(key=lambda persona: persona["nombre"].lower())
    hay_mas = len(personas) > LIMITE_PERSONAS
    personas = personas[:LIMITE_PERSONAS]
    _cargar_partidas(personas)
    return personas, hay_mas


def _documentos_por_nombre(q):
    """Documentos cuyas personas coinciden con las palabras de ``q``."""
    palabras = q.split()
    ids = set()
    for modelo, campos in (
        (Fiel, ["nombres", "apellidos"]),
        (Padre, ["nombre", "apellido"]),
        (Madre, ["nombre", "apellido"]),
        (Padrino, ["nombre"]),
        (Ministro, ["nombre", "apellido"]),
    ):
        queryset = _filtrar_palabras(modelo.objects, campos, palabras)
        ids.update(queryset.values_list("documento_id", flat=True)[: LIMITE_PERSONAS + 1])

    pares = set()
    for modelo in (TestigoMatrimonio, PadrinoMatrimonio):
        queryset = _filtrar_palabras(modelo.objects, ["nombre"], palabras)
        pares.update(queryset.values_list("tipo_documento", "cedula")[: LIMITE_PERSONAS + 1])

    if pares:
        condicion = reduce(
            or_, [Q(tipo_documento=tipo, numero_documento=numero) for tipo, numero in pares]
        )
        ids.update(Documento.objects.filter(condicion).values_list("id", flat=True))

    if not ids:
        return []
    return list(Documento.objects.filter(id__in=ids))


def _roles_por_documento(documentos):
    """Personas de cada ``Documento`` agrupadas por papel, sin N+1.

    Devuelve ``{documento_id: {tipo_papel: [instancia, ...], ...}}``. Los
    testigos y padrinos de matrimonio se asocian al documento por
    ``(tipo_documento, cedula)``.
    """
    doctos = [documento for documento in documentos if documento is not None]
    roles = {documento.pk: defaultdict(list) for documento in doctos}
    if doctos:
        ids = [documento.pk for documento in doctos]
        for fiel in Fiel.objects.filter(documento_id__in=ids).select_related(
            "municipio_nacimiento"
        ):
            roles[fiel.documento_id][FIEL].append(fiel)
        for padre in Padre.objects.filter(documento_id__in=ids):
            roles[padre.documento_id][PADRE].append(padre)
        for madre in Madre.objects.filter(documento_id__in=ids):
            roles[madre.documento_id][MADRE].append(madre)
        for padrino in Padrino.objects.filter(documento_id__in=ids):
            roles[padrino.documento_id][PADRINO].append(padrino)
        for ministro in Ministro.objects.filter(documento_id__in=ids).select_related("parroquia"):
            roles[ministro.documento_id][MINISTRO].append(ministro)

    pares = {
        (documento.tipo_documento, documento.numero_documento): documento.pk for documento in doctos
    }
    if pares:
        condicion = reduce(
            or_,
            [Q(tipo_documento=tipo, cedula=cedula) for tipo, cedula in pares],
        )
        for testigo in TestigoMatrimonio.objects.filter(condicion):
            roles[pares[(testigo.tipo_documento, testigo.cedula)]][TESTIGO].append(testigo)
        for padrino in PadrinoMatrimonio.objects.filter(condicion):
            roles[pares[(padrino.tipo_documento, padrino.cedula)]][PADRINO_MATRIMONIO].append(
                padrino
            )
    return roles


def _nombre_de(instancia, tipo):
    if tipo in (PADRINO, TESTIGO, PADRINO_MATRIMONIO):
        return instancia.nombre
    if tipo == MINISTRO:
        return f"{instancia.nombre} {instancia.apellido}".strip()
    return str(instancia)


def _url_editar(tipo, pk):
    return reverse(f"personas:{tipo}_editar", args=[pk])


def _persona_por_documento(documento, roles):
    """Diccionario de una persona con sus papeles a partir de sus roles."""
    papeles = []
    claves = []
    nombre_principal = ""
    for tipo in ORDEN_PAPELES:
        instancias = roles.get(tipo, [])
        if not instancias:
            continue
        primera = instancias[0]
        nombre = _nombre_de(primera, tipo)
        if not nombre_principal:
            nombre_principal = nombre
        papel = {
            "tipo": tipo,
            "pk": primera.pk,
            "nombre": nombre,
            "etiqueta_tipo": ETIQUETAS_TIPO[tipo],
            "editable": tipo in PAPELES_EDITABLES,
            "url_editar": _url_editar(tipo, primera.pk) if tipo in PAPELES_EDITABLES else None,
            "ministro_cargo": (
                primera.get_cargo_display() if tipo == MINISTRO and primera.cargo else ""
            ),
            "ministro_parroquia": (
                primera.parroquia.nombre if tipo == MINISTRO and primera.parroquia else ""
            ),
        }
        papeles.append(papel)
        claves.extend((tipo, instancia.pk) for instancia in instancias)

    registros = [
        {"nombre": papel["nombre"], "etiqueta_tipo": papel["etiqueta_tipo"]}
        for papel in papeles
        if papel["nombre"].casefold() != nombre_principal.casefold()
    ]
    ministro = next((papel for papel in papeles if papel["tipo"] == MINISTRO), None)
    return {
        "documento_id": documento.pk,
        "nombre": nombre_principal,
        "registros": registros,
        "documento": _documento_texto(documento),
        "papeles": papeles,
        "claves": claves,
        "ministro": ministro,
        "partidas": [],
        "total_partidas": 0,
    }


def _documento_texto(documento):
    """Formato corto del documento, p. ej. ``CC 1065870446``."""
    if documento is None:
        return "—"
    return f"{documento.tipo_documento} {documento.numero_documento}"


def _filtrar_palabras(queryset, campos, palabras):
    for palabra in palabras:
        condicion = Q()
        for campo in campos:
            condicion |= Q(**{f"{campo}__icontains": palabra})
        queryset = queryset.filter(condicion)
    return queryset


def _fila(sacramento, rol):
    return {
        "id": sacramento.pk,
        "rol": rol,
        "tipo_sacramento": sacramento.get_tipo_display(),
        "fecha": sacramento.fecha,
        "libro": str(sacramento.folio.libro),
        "folio": sacramento.folio.numero_folio,
        "numero": sacramento.numero,
    }


def _cargar_partidas(personas):
    """Rellena ``partidas`` y ``total_partidas`` de cada persona por lote."""
    por_persona = defaultdict(list)
    fieles = set()
    padres = set()
    madres = set()
    padrinos = set()
    testigos = set()
    padrinos_matrimonio = set()
    for persona in personas:
        for tipo, pk in persona["claves"]:
            if tipo == FIEL:
                fieles.add(pk)
            elif tipo == PADRE:
                padres.add(pk)
            elif tipo == MADRE:
                madres.add(pk)
            elif tipo == PADRINO:
                padrinos.add(pk)
            elif tipo == TESTIGO:
                testigos.add(pk)
            elif tipo == PADRINO_MATRIMONIO:
                padrinos_matrimonio.add(pk)

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
        conjuntos = (padres, madres, padrinos)
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
        filas = []
        vistos = set()
        for tipo, pk in persona["claves"]:
            for fila in por_persona.get((tipo, pk), []):
                if fila["id"] in vistos:
                    continue
                vistos.add(fila["id"])
                filas.append(fila)
        filas.sort(key=lambda fila: (fila["fecha"], fila["numero"]))
        persona["partidas"] = filas
        persona["total_partidas"] = len(filas)


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


def buscar_menciones(q):
    """Menciones sin documento coincidente para búsquedas por nombre.

    Son textos libres dentro de un bautismo (abuelos, testigos, padres
    biológicos) o testigos/padrinos de matrimonio cuyo documento (o cédula)
    no corresponde a ningún ``Documento``.
    """
    q = q.strip()
    if es_busqueda_por_documento(q) or len(q) < 3:
        return []

    palabras = q.split()
    menciones = _menciones_bautismo(palabras)
    menciones += _menciones_matrimonio(palabras)

    unicas = []
    vistos = set()
    for mencion in menciones:
        clave = (mencion["texto"].casefold(), mencion["rol"])
        if clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(mencion)

    unicas.sort(key=lambda mencion: mencion["texto"].lower())
    return unicas[:50]


def _menciones_bautismo(palabras):
    menciones = []
    for campo, rol in CAMPOS_MENCION_BAUTISMO:
        queryset = _filtrar_palabras(
            Bautismo.objects.exclude(**{f"{campo}__exact": ""}), [campo], palabras
        )
        for bautismo in queryset.select_related("sacramento__folio__libro")[: LIMITE_PERSONAS + 1]:
            texto = getattr(bautismo, campo).strip()
            if texto:
                menciones.append(
                    {"texto": texto, "rol": rol, "partida": _fila(bautismo.sacramento, rol)}
                )
    return menciones


def _menciones_matrimonio(palabras):
    pares_documentados = set(Documento.objects.values_list("tipo_documento", "numero_documento"))
    menciones = []
    for modelo, rol in (
        (TestigoMatrimonio, "Testigo de matrimonio"),
        (PadrinoMatrimonio, "Padrino de matrimonio"),
    ):
        queryset = _filtrar_palabras(modelo.objects, ["nombre"], palabras)
        for instancia in queryset.select_related("matrimonio__sacramento__folio__libro")[
            : LIMITE_PERSONAS + 1
        ]:
            par = (instancia.tipo_documento, instancia.cedula)
            if par in pares_documentados:
                continue
            menciones.append(
                {
                    "texto": instancia.nombre,
                    "rol": rol,
                    "partida": _fila(instancia.matrimonio.sacramento, rol),
                }
            )
    return menciones


def ficha_persona(documento):
    """Datos de la ficha de la persona dueña de ``documento``, o ``None``.

    La ficha reúne los papeles, datos personales, sacramentos recibidos,
    familia y relaciones, actuaciones como ministro o testigo de matrimonio y
    el historial reciente de las partidas donde aparece.
    """
    roles = _roles_por_documento([documento]).get(documento.pk, {})
    if not roles:
        return None
    persona = _persona_por_documento(documento, roles)
    _cargar_partidas([persona])
    return {
        "documento_id": persona["documento_id"],
        "nombre": persona["nombre"],
        "registros": persona["registros"],
        "documento": persona["documento"],
        "papeles": persona["papeles"],
        "ministro": persona["ministro"],
        "datos_personales": _datos_personales(roles),
        "sacramentos": _sacramentos_recibidos(roles),
        "familia": _familia(roles),
        "como_ministro": _como_ministro(roles.get(MINISTRO, [])),
        "testigos": _filas_testigos(TestigoMatrimonio, roles.get(TESTIGO, []), "Testigo"),
        "padrinos_matrimonio": _filas_testigos(
            PadrinoMatrimonio, roles.get(PADRINO_MATRIMONIO, []), "Padrino"
        ),
        "historial": _historial(persona["partidas"]),
    }


def _formatear_dato(valor):
    """Convierte un valor para mostrar, con las fechas en formato d/m/Y."""
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _datos_personales(roles):
    datos = []
    fieles = roles.get(FIEL, [])
    if fieles:
        fiel = fieles[0]
        for etiqueta, valor in (
            ("Fecha de nacimiento", fiel.fecha_nacimiento),
            (
                "Municipio de nacimiento",
                fiel.municipio_nacimiento.nombre if fiel.municipio_nacimiento else "",
            ),
            ("Sexo", fiel.get_sexo_display() if fiel.sexo else ""),
            ("Teléfono", fiel.telefono),
        ):
            if valor:
                datos.append({"etiqueta": etiqueta, "valor": _formatear_dato(valor)})
    ministros = roles.get(MINISTRO, [])
    if ministros:
        ministro = ministros[0]
        for etiqueta, valor in (
            ("Fecha de nacimiento", ministro.fecha_nacimiento),
            ("Correo", ministro.email),
            ("Teléfono", ministro.telefono),
        ):
            if valor and etiqueta not in [dato["etiqueta"] for dato in datos]:
                datos.append({"etiqueta": etiqueta, "valor": _formatear_dato(valor)})
    return datos


def _fila_sacramento(sacramento, rol):
    return {
        "id": sacramento.pk,
        "rol": rol,
        "tipo_sacramento": sacramento.get_tipo_display(),
        "fecha": sacramento.fecha,
        "parroquia": sacramento.parroquia.nombre if sacramento.parroquia else "",
        "libro": str(sacramento.folio.libro),
        "folio": sacramento.folio.numero_folio,
        "numero": sacramento.numero,
        "estado": sacramento.get_estado_display(),
        "anotaciones": [],
    }


def _sacramentos_recibidos(roles):
    fieles = roles.get(FIEL, [])
    if not fieles:
        return []
    fiel = fieles[0]
    filas = []
    ids_bautismo = set()
    for sacramento in Sacramento.objects.filter(fiel_id=fiel.pk).select_related(
        "folio__libro", "parroquia"
    ):
        rol = ROL_TITULAR.get(sacramento.tipo)
        if not rol:
            continue
        if sacramento.tipo == TipoSacramento.BAUTISMO:
            ids_bautismo.add(sacramento.pk)
        filas.append(_fila_sacramento(sacramento, rol))

    anotaciones = defaultdict(list)
    if ids_bautismo:
        for anotacion in AnotacionMarginal.objects.filter(
            sacramento_id__in=ids_bautismo
        ).select_related("parroquia_destino"):
            anotaciones[anotacion.sacramento_id].append(
                {
                    "tipo": anotacion.get_tipo_display(),
                    "fecha": anotacion.fecha,
                    "estado": anotacion.get_estado_display(),
                    "destino": (
                        anotacion.parroquia_destino.nombre
                        if anotacion.parroquia_destino
                        else anotacion.parroquia_destino_texto
                    ),
                }
            )

    for contrayente in Contrayente.objects.filter(fiel_id=fiel.pk).select_related(
        "matrimonio__sacramento__folio__libro", "matrimonio__sacramento__parroquia"
    ):
        filas.append(_fila_sacramento(contrayente.matrimonio.sacramento, "contrayente"))

    for fila in filas:
        fila["anotaciones"] = anotaciones.get(fila["id"], [])
    filas.sort(key=lambda fila: (fila["fecha"], fila["numero"]))
    return filas


def _familiar(rol, nombre, documento_id, tipo_sacramento=""):
    enlace = ""
    if documento_id:
        enlace = reverse("personas:ficha", args=[documento_id])
    return {
        "rol": rol,
        "nombre": nombre,
        "url_ficha": enlace,
        "tipo_sacramento": tipo_sacramento,
    }


def _familia(roles):
    familia = {"padres": [], "hijos": [], "conyuges": [], "ahijados": [], "parejas": []}
    fieles = roles.get(FIEL, [])
    padre_ids = [padre.pk for padre in roles.get(PADRE, [])]
    madre_ids = [madre.pk for madre in roles.get(MADRE, [])]
    padrino_ids = [padrino.pk for padrino in roles.get(PADRINO, [])]

    if fieles:
        fiel = fieles[0]
        bautismo = (
            Bautismo.objects.filter(sacramento__fiel_id=fiel.pk)
            .select_related("padre", "madre", "sacramento")
            .order_by("sacramento__fecha", "sacramento__numero")
            .first()
        )
        if bautismo:
            for rol, persona in (("Padre", bautismo.padre), ("Madre", bautismo.madre)):
                if persona is not None:
                    familia["padres"].append(_familiar(rol, str(persona), persona.documento_id))

        vistos_hijos = set()
        condicion_hijos = Q()
        if padre_ids:
            condicion_hijos |= Q(padre_id__in=padre_ids)
        if madre_ids:
            condicion_hijos |= Q(madre_id__in=madre_ids)
        if condicion_hijos:
            for modelo, tipo in (
                (Bautismo, "Bautismo"),
                (Confirmacion, "Confirmación"),
                (PrimeraComunion, "Primera comunión"),
            ):
                for dato in modelo.objects.filter(condicion_hijos).select_related(
                    "sacramento__fiel__documento"
                ):
                    hijo = dato.sacramento.fiel
                    if hijo.pk in vistos_hijos:
                        continue
                    vistos_hijos.add(hijo.pk)
                    familia["hijos"].append(_familiar("Hijo", str(hijo), hijo.documento_id, tipo))

        ids_matrimonios = list(
            Contrayente.objects.filter(fiel_id=fiel.pk).values_list("matrimonio_id", flat=True)
        )
        if ids_matrimonios:
            otros = (
                Contrayente.objects.filter(matrimonio_id__in=ids_matrimonios)
                .exclude(fiel_id=fiel.pk)
                .select_related("fiel__documento")
            )
            for contrayente in otros:
                familia["conyuges"].append(
                    _familiar("Cónyuge", str(contrayente.fiel), contrayente.fiel.documento_id)
                )

    if padrino_ids:
        vistos_ahijados = set()
        condicion_ahijados = Q(padrino_id__in=padrino_ids) | Q(madrina_id__in=padrino_ids)
        for modelo, tipo in ((Bautismo, "Bautismo"), (Confirmacion, "Confirmación")):
            for dato in modelo.objects.filter(condicion_ahijados).select_related(
                "sacramento__fiel__documento"
            ):
                ahijado = dato.sacramento.fiel
                if ahijado.pk in vistos_ahijados:
                    continue
                vistos_ahijados.add(ahijado.pk)
                familia["ahijados"].append(
                    _familiar("Ahijado", str(ahijado), ahijado.documento_id, tipo)
                )

    padrinos_matrimonio = roles.get(PADRINO_MATRIMONIO, [])
    if padrinos_matrimonio:
        pares = {(padrino.tipo_documento, padrino.cedula) for padrino in padrinos_matrimonio}
        condicion = reduce(or_, [Q(tipo_documento=tipo, cedula=cedula) for tipo, cedula in pares])
        ids_bodas = list(
            PadrinoMatrimonio.objects.filter(condicion).values_list("matrimonio_id", flat=True)
        )
        for contrayente in Contrayente.objects.filter(matrimonio_id__in=ids_bodas).select_related(
            "fiel__documento", "matrimonio__sacramento"
        ):
            familia["parejas"].append(
                {
                    "rol": "Contrayente apadrinado",
                    "nombre": str(contrayente.fiel),
                    "url_ficha": reverse("personas:ficha", args=[contrayente.fiel.documento_id]),
                    "tipo_sacramento": "",
                    "fecha_matrimonio": contrayente.matrimonio.sacramento.fecha,
                }
            )
    return familia


def _como_ministro(ministros):
    if not ministros:
        return None
    ministro = ministros[0]
    datos = {
        "cargo": ministro.get_cargo_display() if ministro.cargo else "",
        "parroquia": ministro.parroquia.nombre if ministro.parroquia else "",
        "celebro": [],
        "dio_fe": [],
        "libros": [],
        "parroquias": [],
    }
    for sacramento in Sacramento.objects.filter(ministro_id=ministro.pk).select_related(
        "folio__libro"
    ):
        datos["celebro"].append(_fila(sacramento, "celebró"))

    for modelo in (Bautismo, Confirmacion, PrimeraComunion):
        for dato in modelo.objects.filter(doy_fe_id=ministro.pk).select_related(
            "sacramento__folio__libro"
        ):
            datos["dio_fe"].append(_fila(dato.sacramento, "Dio fe"))

    for libro in Libro.objects.filter(
        Q(ministro_apertura_id=ministro.pk) | Q(ministro_cierre_id=ministro.pk)
    ).select_related("parroquia"):
        evento = "Apertura" if libro.ministro_apertura_id == ministro.pk else "Cierre"
        datos["libros"].append(
            {
                "nombre": libro.nombre,
                "tipo_libro": libro.get_tipo_libro_display(),
                "parroquia": libro.parroquia.nombre,
                "evento": evento,
                "fecha": libro.fecha_apertura if evento == "Apertura" else libro.fecha_cierre,
            }
        )

    for parroquia in Parroquia.objects.filter(parroco_id=ministro.pk):
        datos["parroquias"].append(parroquia.nombre)
    return datos


def _filas_testigos(modelo, instancias, rol):
    ids = [instancia.pk for instancia in instancias]
    if not ids:
        return []
    filas = []
    for item in modelo.objects.filter(pk__in=ids).select_related(
        "matrimonio__sacramento__folio__libro"
    ):
        filas.append(_fila(item.matrimonio.sacramento, rol))
    filas.sort(key=lambda fila: (fila["fecha"], fila["numero"]))
    return filas


def _parroquias_demo(parroquia_ids):
    """Pks de las parroquias de demostración entre ``parroquia_ids``.

    La parroquia de demostración se reconoce porque su párroco lleva un
    documento con el prefijo ``9990`` que asigna el comando de datos demo.
    """
    if not parroquia_ids:
        return set()
    return set(
        Parroquia.objects.filter(
            pk__in=parroquia_ids,
            parroco__documento__numero_documento__startswith=PREFIJO_DOCUMENTO,
        ).values_list("pk", flat=True)
    )


def _historial(partidas):
    ids = sorted({fila["id"] for fila in partidas})
    if not ids:
        return []
    entradas = (
        HistorialSacramento.objects.filter(sacramento_id__in=ids)
        .select_related("sacramento", "usuario__perfil")
        .order_by("-fecha", "-id")[:10]
    )
    parroquia_ids = {
        entrada.sacramento.parroquia_id for entrada in entradas if entrada.sacramento.parroquia_id
    }
    demo_ids = _parroquias_demo(parroquia_ids)
    return [_entrada_historial(entrada, demo_ids) for entrada in entradas]


def _entrada_historial(entrada, demo_ids):
    sacramento = entrada.sacramento
    usuario = entrada.usuario
    perfil = getattr(usuario, "perfil", None) if usuario else None
    quien = ""
    if usuario:
        quien = usuario.get_full_name() or usuario.username
    if perfil is not None:
        rol = perfil.get_rol_display()
    elif usuario:
        rol = "Administrador"
    else:
        rol = ""
    fallback = "Datos de demostración" if sacramento.parroquia_id in demo_ids else "Sistema"
    return {
        "fecha": entrada.fecha,
        "partida": f"{sacramento.get_tipo_display()} N.° {sacramento.numero} - {sacramento.folio}",
        "accion": entrada.get_accion_display(),
        "descripcion": entrada.descripcion,
        "quien": quien,
        "rol": rol,
        "fallback": fallback,
    }
