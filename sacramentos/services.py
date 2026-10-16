from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.choices import (
    AccionHistorial,
    EstadoAnotacion,
    EstadoRegistro,
    TipoAnotacionMarginal,
    TipoHijo,
    TipoSacramento,
)
from parroquias.services import folio_para_nueva_partida, siguiente_numero_partida
from personas.models import Documento, Fiel, Madre, Padre, Padrino

from .models import AnotacionMarginal, Bautismo, HistorialSacramento, PartidaEliminada, Sacramento


def registrar_historial(sacramento, accion, descripcion="", usuario=None):
    """Registra un movimiento en el historial de un sacramento."""
    return HistorialSacramento.objects.create(
        sacramento=sacramento,
        accion=accion,
        descripcion=descripcion,
        usuario=usuario,
    )


def _crear_o_reutilizar_fiel(datos_fiel):
    """Crea o reutiliza un Fiel según el documento."""
    tipo_doc = datos_fiel.get("tipo_documento")
    numero_doc = datos_fiel.get("numero_documento")
    if not tipo_doc or not numero_doc:
        return None, False

    documento, _ = Documento.objects.get_or_create(
        tipo_documento=tipo_doc,
        numero_documento=numero_doc,
    )
    fiel = Fiel.objects.filter(documento=documento).first()
    if fiel:
        # Reutilizar sin sobrescribir: solo rellenar campos vacíos
        if not fiel.nombres and datos_fiel.get("nombres"):
            fiel.nombres = datos_fiel.get("nombres")
        if not fiel.apellidos and datos_fiel.get("apellidos"):
            fiel.apellidos = datos_fiel.get("apellidos")
        if not fiel.fecha_nacimiento and datos_fiel.get("fecha_nacimiento"):
            fiel.fecha_nacimiento = datos_fiel.get("fecha_nacimiento")
        if not fiel.municipio_nacimiento and datos_fiel.get("municipio_nacimiento"):
            fiel.municipio_nacimiento = datos_fiel.get("municipio_nacimiento")
        if not fiel.telefono and datos_fiel.get("telefono"):
            fiel.telefono = datos_fiel.get("telefono")
        if not fiel.sexo and datos_fiel.get("sexo"):
            fiel.sexo = datos_fiel.get("sexo")
        fiel.save()
        return fiel, True
    fiel = Fiel.objects.create(
        documento=documento,
        nombres=datos_fiel.get("nombres", ""),
        apellidos=datos_fiel.get("apellidos", ""),
        fecha_nacimiento=datos_fiel.get("fecha_nacimiento"),
        municipio_nacimiento=datos_fiel.get("municipio_nacimiento"),
        telefono=datos_fiel.get("telefono", ""),
        sexo=datos_fiel.get("sexo"),
    )
    return fiel, False


def _crear_o_reutilizar_padre(datos_padre):
    if not datos_padre:
        return None
    tipo_doc = datos_padre.get("tipo_documento")
    numero_doc = datos_padre.get("numero_documento")
    if not tipo_doc or not numero_doc:
        return None
    documento, _ = Documento.objects.get_or_create(
        tipo_documento=tipo_doc,
        numero_documento=numero_doc,
    )
    padre = Padre.objects.filter(documento=documento).first()
    if padre:
        if not padre.nombre and datos_padre.get("nombre"):
            padre.nombre = datos_padre.get("nombre")
        if not padre.apellido and datos_padre.get("apellido"):
            padre.apellido = datos_padre.get("apellido")
        padre.save()
        return padre
    padre = Padre.objects.create(
        documento=documento,
        nombre=datos_padre.get("nombre", ""),
        apellido=datos_padre.get("apellido", ""),
    )
    return padre


def _crear_o_reutilizar_madre(datos_madre):
    if not datos_madre:
        return None
    tipo_doc = datos_madre.get("tipo_documento")
    numero_doc = datos_madre.get("numero_documento")
    if not tipo_doc or not numero_doc:
        return None
    documento, _ = Documento.objects.get_or_create(
        tipo_documento=tipo_doc,
        numero_documento=numero_doc,
    )
    madre = Madre.objects.filter(documento=documento).first()
    if madre:
        if not madre.nombre and datos_madre.get("nombre"):
            madre.nombre = datos_madre.get("nombre")
        if not madre.apellido and datos_madre.get("apellido"):
            madre.apellido = datos_madre.get("apellido")
        madre.save()
        return madre
    madre = Madre.objects.create(
        documento=documento,
        nombre=datos_madre.get("nombre", ""),
        apellido=datos_madre.get("apellido", ""),
    )
    return madre


def _crear_o_reutilizar_padrino(datos_padrino):
    if not datos_padrino:
        return None
    tipo_doc = datos_padrino.get("tipo_documento")
    numero_doc = datos_padrino.get("numero_documento")
    if not tipo_doc or not numero_doc:
        return None
    documento, _ = Documento.objects.get_or_create(
        tipo_documento=tipo_doc,
        numero_documento=numero_doc,
    )
    padrino = Padrino.objects.filter(documento=documento).first()
    if padrino:
        if not padrino.nombre and datos_padrino.get("nombre"):
            padrino.nombre = datos_padrino.get("nombre")
        padrino.save()
        return padrino
    padrino = Padrino.objects.create(
        documento=documento,
        nombre=datos_padrino.get("nombre", ""),
    )
    return padrino


def _personas_desde_datos(datos):
    """Crea o reutiliza las personas de una partida y devuelve también las reutilizadas."""
    reutilizadas = []
    fiel, fue_reutilizado = _crear_o_reutilizar_fiel(datos.get("fiel", {}))
    if fue_reutilizado:
        reutilizadas.append("fiel")
    padre = _crear_o_reutilizar_padre(datos.get("padre", {}))
    madre = _crear_o_reutilizar_madre(datos.get("madre", {}))
    padrino = _crear_o_reutilizar_padrino(datos.get("padrino", {}))
    madrina = _crear_o_reutilizar_padrino(datos.get("madrina", {}))
    return fiel, padre, madre, padrino, madrina, reutilizadas


def _sincronizar_personas(datos, fiel):
    """Actualiza los datos mutables del bautizado al corregir una partida.

    Los nombres y documentos de las personas ya vinculadas son de solo lectura en
    el formulario de corrección (se corrigen desde su ficha), así que aquí solo se
    sincronizan los datos del fiel que sí se editan en la partida: fecha y
    municipio de nacimiento, teléfono y sexo. Como el ``Fiel`` puede aparecer en
    otras partidas, el formulario avisa de cuántas se verán afectadas.
    """
    datos_fiel = datos.get("fiel", {})
    if fiel is None:
        return
    fiel.fecha_nacimiento = datos_fiel.get("fecha_nacimiento") or fiel.fecha_nacimiento
    fiel.municipio_nacimiento = datos_fiel.get("municipio_nacimiento") or fiel.municipio_nacimiento
    fiel.telefono = datos_fiel.get("telefono", fiel.telefono)
    fiel.sexo = datos_fiel.get("sexo") or fiel.sexo
    fiel.save()


def _aplicar_datos_bautismo(bautismo, fiel, padre, madre, padrino, madrina, datos):
    """Vuelca los datos editables del formulario sobre el ``Sacramento`` y el ``Bautismo``.

    No toca la ubicación en el libro (libro, folio, número) ni la fecha de
    registro: esos datos quedan fijos desde que se creó la partida.
    """
    sacramento = bautismo.sacramento
    partida = datos.get("partida", {})
    parroquia = sacramento.parroquia

    sacramento.fiel = fiel
    sacramento.fecha = partida.get("fecha")
    sacramento.ministro = partida.get("ministro")
    sacramento.observaciones = partida.get("observaciones", "")

    doy_fe = datos.get("doy_fe") or getattr(parroquia, "parroco", None)
    tipo_hijo = datos.get("tipo_hijo")
    if tipo_hijo != TipoHijo.ADOPTIVO:
        # Los nombres de los padres biológicos solo se aceptan para hijos adoptivos.
        padre_biologico_nombre = ""
        madre_biologica_nombre = ""
    else:
        padre_biologico_nombre = datos.get("padre_biologico_nombre", "")
        madre_biologica_nombre = datos.get("madre_biologica_nombre", "")

    bautismo.padre = padre
    bautismo.madre = madre
    bautismo.abuelo_paterno = datos.get("abuelo_paterno", "")
    bautismo.abuela_paterna = datos.get("abuela_paterna", "")
    bautismo.abuelo_materno = datos.get("abuelo_materno", "")
    bautismo.abuela_materna = datos.get("abuela_materna", "")
    bautismo.tipo_hijo = tipo_hijo
    bautismo.testigo_nombre = datos.get("testigo_nombre", "")
    bautismo.padre_biologico_nombre = padre_biologico_nombre
    bautismo.madre_biologica_nombre = madre_biologica_nombre
    bautismo.padrino = padrino
    bautismo.madrina = madrina
    bautismo.quien_firma = datos.get("quien_firma") or doy_fe
    bautismo.doy_fe = doy_fe


def _registrar_anotacion_correccion(sacramento, motivo):
    """Anota en el margen de la partida la corrección o anulación (tipo CORRECCION)."""
    return AnotacionMarginal.objects.create(
        sacramento=sacramento,
        tipo=TipoAnotacionMarginal.CORRECCION,
        fecha=timezone.localdate(),
        descripcion=motivo,
        estado=EstadoAnotacion.ANOTADA,
    )


@transaction.atomic
def registrar_bautismo(datos, usuario):
    """
    Registra un bautismo con los datos proporcionados.

    El folio y la fecha de registro son automáticos: el folio sale de la
    capacidad del libro (``folio_para_nueva_partida``) y la fecha de registro es
    la fecha actual del sistema.

    Args:
        datos: Dict anidado con la estructura definida por BautismoForm.datos_para_servicio()
        usuario: Usuario que realiza el registro

    Returns:
        (bautismo, reutilizadas): Tuple con el bautismo creado y lista de personas reutilizadas
    """
    fiel, padre, madre, padrino, madrina, reutilizadas = _personas_desde_datos(datos)

    partida = datos.get("partida", {})
    libro = partida.get("libro")

    sacramento = Sacramento(
        tipo=TipoSacramento.BAUTISMO,
        fiel=fiel,
        libro=libro,
        folio=folio_para_nueva_partida(libro),
        numero=siguiente_numero_partida(libro),
        fecha=partida.get("fecha"),
        fecha_registro=timezone.localdate(),
        parroquia=partida.get("parroquia"),
        ministro=partida.get("ministro"),
        estado=EstadoRegistro.ACTIVO,
        observaciones=partida.get("observaciones", ""),
        creado_por=usuario,
    )
    sacramento.full_clean()
    sacramento.save()

    bautismo = Bautismo(sacramento=sacramento)
    _aplicar_datos_bautismo(bautismo, fiel, padre, madre, padrino, madrina, datos)
    bautismo.full_clean()
    bautismo.save()

    registrar_historial(
        sacramento,
        AccionHistorial.CREACION,
        descripcion="Registro de bautismo creado",
        usuario=usuario,
    )

    return bautismo, reutilizadas


@transaction.atomic
def corregir_bautismo(bautismo, datos, usuario, motivo):
    """Corrige los datos de una partida de bautismo (no cambia su lugar en el libro).

    Guarda la corrección con el motivo en el historial y anota la corrección en el
    margen de la partida. La partida pasa a estado ``CORREGIDO`` si estaba activa.
    """
    sacramento = bautismo.sacramento
    if sacramento.estado == EstadoRegistro.ANULADO:
        raise ValidationError("No se puede corregir una partida anulada.")

    fiel, padre, madre, padrino, madrina, _ = _personas_desde_datos(datos)
    _sincronizar_personas(datos, fiel)
    _aplicar_datos_bautismo(bautismo, fiel, padre, madre, padrino, madrina, datos)

    if sacramento.estado == EstadoRegistro.ACTIVO:
        sacramento.estado = EstadoRegistro.CORREGIDO
    sacramento.modificado_por = usuario

    sacramento.full_clean()
    sacramento.save()
    bautismo.full_clean()
    bautismo.save()

    registrar_historial(sacramento, AccionHistorial.CORRECCION, motivo, usuario)
    _registrar_anotacion_correccion(sacramento, motivo)
    return bautismo


@transaction.atomic
def anular_bautismo(bautismo, usuario, motivo):
    """Anula una partida de bautismo conservándola en el libro.

    Solo se anulan partidas activas o corregidas. Guarda el motivo en el historial
    y lo anota en el margen de la partida.
    """
    sacramento = bautismo.sacramento
    if sacramento.estado == EstadoRegistro.ANULADO:
        raise ValidationError("La partida ya está anulada.")

    sacramento.estado = EstadoRegistro.ANULADO
    sacramento.modificado_por = usuario
    sacramento.save(update_fields=["estado", "modificado_por", "modificado_en"])

    registrar_historial(sacramento, AccionHistorial.ANULACION, motivo, usuario)
    _registrar_anotacion_correccion(sacramento, motivo)
    return bautismo


def motivo_no_eliminable(bautismo):
    """Motivo por el que una partida no se puede eliminar, o ``None`` si sí se puede.

    Deben cumplirse TODAS estas condiciones: la partida está ACTIVA (ni anulada ni
    corregida), es la última del libro (el número más alto), se registró hoy y no
    tiene anotaciones marginales, ni como partida anotada ni como origen. Las
    partidas anuladas y las corregidas nunca se eliminan: quedan como constancia.
    """
    sacramento = bautismo.sacramento
    if sacramento.estado == EstadoRegistro.ANULADO:
        return "Las partidas anuladas no se eliminan, quedan como constancia"
    if Sacramento.objects.filter(
        libro_id=sacramento.libro_id, numero__gt=sacramento.numero
    ).exists():
        return "Solo se puede eliminar la última partida del libro"
    if sacramento.fecha_registro != timezone.localdate():
        return "Solo se puede eliminar una partida registrada hoy"
    if sacramento.estado == EstadoRegistro.CORREGIDO:
        return "Las partidas corregidas no se eliminan, quedan como constancia"
    if AnotacionMarginal.objects.filter(
        Q(sacramento=sacramento) | Q(sacramento_origen=sacramento)
    ).exists():
        return "La partida tiene notas marginales; anúlala en su lugar"
    return None


def puede_eliminarse(bautismo):
    """True solo si la partida cumple todas las condiciones para eliminarse."""
    return motivo_no_eliminable(bautismo) is None


@transaction.atomic
def eliminar_bautismo(bautismo, usuario, motivo):
    """Elimina definitivamente una partida del libro, guardando antes una copia.

    Solo se permite cuando se cumplen todas las condiciones de
    ``motivo_no_eliminable``. Antes de borrar se guarda una copia en
    ``PartidaEliminada`` para poder auditar qué había en el libro. Al eliminar la
    última partida quedan libres su número y su folio, y el siguiente registro los
    reutiliza (no se dejan huecos en la numeración).
    """
    motivo_bloqueo = motivo_no_eliminable(bautismo)
    if motivo_bloqueo:
        raise ValidationError(motivo_bloqueo)

    sacramento = bautismo.sacramento
    fiel = sacramento.fiel
    PartidaEliminada.objects.create(
        tipo=sacramento.tipo,
        libro=sacramento.libro,
        folio_numero=sacramento.folio.numero_folio,
        numero=sacramento.numero,
        fecha=sacramento.fecha,
        fecha_registro=sacramento.fecha_registro,
        fiel_nombre=str(fiel) if fiel else "",
        parroquia=sacramento.parroquia,
        resumen=_resumen_partida(bautismo),
        motivo=motivo,
        eliminado_por=usuario,
    )
    # Al borrar el Sacramento se borra en cascada el Bautismo, el historial y las
    # anotaciones marginales.
    sacramento.delete()


def _resumen_partida(bautismo):
    """Texto legible con los datos principales de una partida (para el histórico)."""
    sacramento = bautismo.sacramento
    lineas = [
        f"Fiel: {sacramento.fiel}" if sacramento.fiel else "Fiel: —",
        f"Padre: {bautismo.padre or '—'}",
        f"Madre: {bautismo.madre or '—'}",
        f"Padrino: {bautismo.padrino or '—'}",
        f"Madrina: {bautismo.madrina or '—'}",
        f"Testigo: {bautismo.testigo_nombre or '—'}",
        f"Fecha del bautismo: {sacramento.fecha}",
        f"Fecha de registro: {sacramento.fecha_registro}",
        f"Ministro: {sacramento.ministro or '—'}",
        f"Observaciones: {sacramento.observaciones or '—'}",
    ]
    return "\n".join(lineas)
