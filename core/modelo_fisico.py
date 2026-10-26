"""Construcción del documento del modelo físico de la base de datos.

Lee la estructura del esquema ``public`` directamente del catálogo de
PostgreSQL (``information_schema`` y ``pg_catalog``): tablas, columnas con su
tipo exacto, nulos, valores por defecto, llaves primarias y foráneas (con su
``ON DELETE``), restricciones ``UNIQUE`` y ``CHECK`` e índices. Nunca lee filas
de datos, así que el documento no lleva información de personas.

Las descripciones de tablas y columnas salen de los modelos de Django
(``verbose_name``, ``help_text`` y docstring), cruzando ``db_table`` y
``db_column``; donde el modelo no trae descripción se usa un texto redactado
aquí. El diagrama entidad-relación se escribe en Mermaid (``erDiagram``) y se
renderiza, junto con el PDF, con Playwright y Chromium.

La conexión a Supabase es de solo lectura y su cadena de conexión nunca se
imprime ni se guarda: los mensajes de error se limpian antes de mostrarse.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import re
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.apps import apps
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, models

from core import respaldos

PREFIJOS_PROPIOS = ("cuentas_", "personas_", "parroquias_", "sacramentos_", "ubicacion_")
PREFIJOS_DJANGO = ("auth_", "django_")

# Módulos (aplicaciones) en el orden en que se presentan en el diccionario.
MODULOS = [
    ("ubicacion", "Ubicación"),
    ("personas", "Personas"),
    ("parroquias", "Parroquias"),
    ("cuentas", "Cuentas"),
    ("sacramentos", "Sacramentos"),
]

# Colores suaves de la app (tema.css) para distinguir módulos en la vista general.
COLORES_MODULO = {
    "ubicacion": "#e7ebf2",
    "personas": "#e4edf8",
    "parroquias": "#e3f0ea",
    "cuentas": "#f6ecd6",
    "sacramentos": "#ece6f6",
}

# Tamaño de letra (px) con que Mermaid dibuja cada diagrama antes de escalarlo.
LETRA_DIAGRAMA = 14
LETRA_GENERAL = 32

MATRIMONIO_CONTRAYENTES = (
    "sacramentos_matrimonio",
    "sacramentos_contrayente",
    "sacramentos_notamarginalmatrimonio",
)
MATRIMONIO_EXPEDIENTE = (
    "sacramentos_matrimonio",
    "sacramentos_testigomatrimonio",
    "sacramentos_padrinomatrimonio",
    "sacramentos_proclamamatrimonio",
    "sacramentos_hijoreconocidomatrimonio",
)

# Diagramas por módulo: (identificador, título, aplicaciones, tablas que se
# excluyen, tablas a las que se limita). Sacramentos va en tres diagramas
# porque completo no cabe legible en una página; la tabla del matrimonio se
# repite en los dos últimos para que se vean sus relaciones.
DIAGRAMAS_MODULO = [
    ("personas-ubicacion", "Personas y ubicación", ("personas", "ubicacion"), (), ()),
    ("parroquias-cuentas", "Parroquias y cuentas", ("parroquias", "cuentas"), (), ()),
    (
        "sacramentos-partidas",
        "Sacramentos: partida, bautismo, confirmación y primera comunión",
        ("sacramentos",),
        MATRIMONIO_CONTRAYENTES + MATRIMONIO_EXPEDIENTE,
        (),
    ),
    (
        "sacramentos-matrimonio",
        "Sacramentos: matrimonio, contrayentes y nota marginal",
        ("sacramentos",),
        (),
        MATRIMONIO_CONTRAYENTES,
    ),
    (
        "sacramentos-expediente",
        "Sacramentos: testigos, padrinos, proclamas e hijos del matrimonio",
        ("sacramentos",),
        (),
        MATRIMONIO_EXPEDIENTE,
    ),
]

# Recursos de terceros con versión y huella fijas; se descargan una sola vez.
VERSION_MERMAID = "11.4.1"
URL_CDN = "https://cdn.jsdelivr.net/npm/"
RECURSOS = {
    "mermaid": (
        f"mermaid@{VERSION_MERMAID}/dist/mermaid.min.js",
        f"mermaid-{VERSION_MERMAID}.min.js",
        "a43bc1afd446f9c4cc66ac5dd45d02e8d65e26fc5344ec0ef787f88d6ddb6f9e",
    ),
    "inter-400": (
        "@fontsource/inter@5.1.0/files/inter-latin-400-normal.woff2",
        "inter-latin-400-normal.woff2",
        "dd05e326cf8eac3b55acecf29c842ed73e6e6dd06491cf47f7e8800680ab3e33",
    ),
    "inter-500": (
        "@fontsource/inter@5.1.0/files/inter-latin-500-normal.woff2",
        "inter-latin-500-normal.woff2",
        "b0e7558f4710a1e255b93e3deefe3aebb19f3bb41c150f685a74d3b1a1c79e87",
    ),
    "inter-600": (
        "@fontsource/inter@5.1.0/files/inter-latin-600-normal.woff2",
        "inter-latin-600-normal.woff2",
        "62553d159189834af73c9a6264704be5b2bee9a08da66a14768d8e5c6ffd2cdb",
    ),
    "inter-700": (
        "@fontsource/inter@5.1.0/files/inter-latin-700-normal.woff2",
        "inter-latin-700-normal.woff2",
        "aac638f7503cebb084ec494cf00f75f7d8260d50c2f4e7820bccabba09626a3a",
    ),
    "mono-400": (
        "@fontsource/jetbrains-mono@5.1.0/files/jetbrains-mono-latin-400-normal.woff2",
        "jetbrains-mono-latin-400-normal.woff2",
        "7c53386f55c866c1b4c9309c4bcf74eda10896aab3a1780b0af5cc4976e27a27",
    ),
}

REGLAS_ON_DELETE = {
    "a": "NO ACTION",
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}

TIPOS_RESTRICCION = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "u": "UNIQUE", "c": "CHECK"}

TIPOS_CORTOS = {
    "character varying": "varchar",
    "timestamp with time zone": "timestamptz",
    "timestamp without time zone": "timestamp",
    "time without time zone": "time",
    "time with time zone": "timetz",
    "double precision": "float8",
}

DESCRIPCIONES_TABLAS = {
    "ubicacion_pais": "Catálogo de países.",
    "ubicacion_departamento": "Departamentos (o divisiones equivalentes) de cada país.",
    "ubicacion_municipio": (
        "Municipios de cada departamento. Se usan para el lugar de nacimiento del fiel, el "
        "lugar de bautismo y la sede de cada parroquia."
    ),
    "personas_documento": (
        "Documentos de identidad. Es la tabla central de personas: cada fiel, padre, madre, "
        "padrino o ministro tiene uno, y la pareja tipo-número no se repite."
    ),
    "personas_padre": "Padres de los fieles; un mismo padre se reutiliza en varias partidas.",
    "personas_madre": "Madres de los fieles; una misma madre se reutiliza en varias partidas.",
    "personas_padrino": "Padrinos y madrinas de bautismo y de confirmación.",
    "personas_fiel": "Fieles que reciben los sacramentos.",
    "parroquias_parroquia": (
        "Parroquias que usan el sistema y parroquias de referencia (por ejemplo, donde se "
        "bautizó un contrayente)."
    ),
    "parroquias_ministro": (
        "Ministros (párrocos, vicarios, diáconos y otros servidores) que celebran o firman "
        "las partidas."
    ),
    "parroquias_libro": (
        "Libros parroquiales por tipo de sacramento. En cada parroquia solo puede haber un "
        "libro abierto por tipo."
    ),
    "parroquias_folio": "Folios (hojas) de cada libro; cada partida se inscribe en un folio.",
    "sacramentos_sacramento": (
        "Partida común a todos los sacramentos: libro, folio, número, fechas, ministro, "
        "estado y auditoría. Cada tipo guarda sus datos propios en una tabla 1:1."
    ),
    "sacramentos_bautismo": (
        "Datos propios de la partida de bautismo (relación 1:1 con la partida)."
    ),
    "sacramentos_confirmacion": (
        "Datos propios de la partida de confirmación, incluidos los del bautismo previo."
    ),
    "sacramentos_primeracomunion": (
        "Datos propios de la partida de primera comunión, incluidos los del bautismo previo."
    ),
    "sacramentos_matrimonio": (
        "Datos propios de la partida de matrimonio: expediente, declaración y dispensas."
    ),
    "sacramentos_contrayente": (
        "Los dos contrayentes de cada matrimonio, con sus datos de bautismo y confirmación y "
        "las respuestas del expediente matrimonial."
    ),
    "sacramentos_testigomatrimonio": "Testigos del matrimonio.",
    "sacramentos_padrinomatrimonio": "Padrinos del matrimonio.",
    "sacramentos_proclamamatrimonio": (
        "Proclamas (amonestaciones) que se publican antes del matrimonio."
    ),
    "sacramentos_hijoreconocidomatrimonio": (
        "Hijos que los contrayentes reconocen en el expediente matrimonial."
    ),
    "sacramentos_notamarginalmatrimonio": (
        "Nota marginal de la partida de matrimonio, con los datos de licencia y delegación."
    ),
    "sacramentos_documentosacramento": "Archivos adjuntos a una partida (escaneos y soportes).",
    "sacramentos_anotacionmarginal": (
        "Anotaciones marginales de una partida (confirmación, matrimonio, defunción, "
        "correcciones) y su estado de comunicación a otras parroquias."
    ),
    "sacramentos_historialsacramento": (
        "Bitácora de las acciones sobre cada partida (creación, modificación, anulación, "
        "certificados expedidos)."
    ),
}

# Descripciones redactadas para columnas sin verbose_name ni help_text explícitos.
DESCRIPCIONES_GENERICAS = {
    "observaciones": "Observaciones o notas libres.",
    "religion": "Religión que declara.",
    "estado_civil": "Estado civil.",
    "tipo_documento": "Tipo de documento de identidad.",
    "creado_en": "Fecha y hora de creación del registro; la asigna el sistema.",
    "modificado_en": "Fecha y hora de la última modificación; la asigna el sistema.",
}

DESCRIPCIONES_COLUMNAS = {
    ("cuentas_perfilusuario", "usuario_id"): (
        "Usuario de Django (auth_user) dueño del perfil; relación 1:1."
    ),
    ("ubicacion_pais", "nombre"): "Nombre del país; no se repite.",
    ("ubicacion_departamento", "nombre"): "Nombre del departamento.",
    ("ubicacion_departamento", "pais_id"): "País al que pertenece el departamento.",
    ("ubicacion_municipio", "nombre"): "Nombre del municipio.",
    ("ubicacion_municipio", "departamento_id"): "Departamento al que pertenece el municipio.",
    ("personas_documento", "numero_documento"): (
        "Número del documento; único junto con el tipo de documento."
    ),
    ("personas_padre", "nombre"): "Nombres del padre.",
    ("personas_padre", "apellido"): "Apellidos del padre.",
    ("personas_madre", "nombre"): "Nombres de la madre.",
    ("personas_madre", "apellido"): "Apellidos de la madre.",
    ("personas_padrino", "nombre"): "Nombre completo del padrino o madrina.",
    ("personas_fiel", "nombres"): "Nombres del fiel.",
    ("personas_fiel", "apellidos"): "Apellidos del fiel.",
    ("parroquias_parroquia", "nombre"): "Nombre de la parroquia; no se repite.",
    ("parroquias_parroquia", "municipio_id"): "Municipio donde está la parroquia.",
    ("parroquias_parroquia", "direccion"): "Dirección de la sede parroquial.",
    ("parroquias_parroquia", "email"): "Correo electrónico de la parroquia.",
    ("parroquias_ministro", "nombre"): "Nombres del ministro.",
    ("parroquias_ministro", "apellido"): "Apellidos del ministro.",
    ("parroquias_ministro", "email"): "Correo electrónico del ministro.",
    ("parroquias_ministro", "parroquia_id"): "Parroquia a la que está asignado.",
    ("parroquias_libro", "nombre"): "Nombre del libro; único dentro de la parroquia.",
    ("parroquias_libro", "parroquia_id"): "Parroquia dueña del libro.",
    ("parroquias_folio", "libro_id"): "Libro al que pertenece el folio.",
    ("sacramentos_sacramento", "fiel_id"): (
        "Fiel que recibe el sacramento; vacío en los matrimonios, que usan contrayentes."
    ),
    ("sacramentos_sacramento", "folio_id"): "Folio del libro donde se inscribe la partida.",
    ("sacramentos_sacramento", "fecha"): "Fecha en que se celebró el sacramento.",
    ("sacramentos_sacramento", "parroquia_id"): "Parroquia donde se celebró.",
    ("sacramentos_sacramento", "ministro_id"): "Ministro que celebró el sacramento.",
    ("sacramentos_sacramento", "creado_por_id"): "Usuario que inscribió la partida.",
    ("sacramentos_sacramento", "modificado_por_id"): "Usuario que la modificó por última vez.",
    ("sacramentos_bautismo", "sacramento_id"): (
        "Partida del sacramento; es a la vez llave primaria y foránea (relación 1:1)."
    ),
    ("sacramentos_bautismo", "padre_id"): "Padre del bautizado.",
    ("sacramentos_bautismo", "madre_id"): "Madre del bautizado.",
    ("sacramentos_bautismo", "padrino_id"): "Padrino del bautizado.",
    ("sacramentos_bautismo", "madrina_id"): "Madrina del bautizado.",
    ("sacramentos_bautismo", "quien_firma_id"): "Ministro que firma la partida.",
    ("sacramentos_bautismo", "doy_fe_id"): "Ministro que da fe de la partida.",
    ("sacramentos_confirmacion", "sacramento_id"): (
        "Partida del sacramento; es a la vez llave primaria y foránea (relación 1:1)."
    ),
    ("sacramentos_confirmacion", "padre_id"): "Padre del confirmado.",
    ("sacramentos_confirmacion", "madre_id"): "Madre del confirmado.",
    ("sacramentos_confirmacion", "padrino_id"): "Padrino de confirmación.",
    ("sacramentos_confirmacion", "madrina_id"): "Madrina de confirmación.",
    ("sacramentos_confirmacion", "doy_fe_id"): "Ministro que da fe de la partida.",
    ("sacramentos_primeracomunion", "sacramento_id"): (
        "Partida del sacramento; es a la vez llave primaria y foránea (relación 1:1)."
    ),
    ("sacramentos_primeracomunion", "padre_id"): "Padre del comulgante.",
    ("sacramentos_primeracomunion", "madre_id"): "Madre del comulgante.",
    ("sacramentos_primeracomunion", "doy_fe_id"): "Ministro que da fe de la partida.",
    ("sacramentos_matrimonio", "sacramento_id"): (
        "Partida del sacramento; es a la vez llave primaria y foránea (relación 1:1)."
    ),
    ("sacramentos_contrayente", "matrimonio_id"): "Matrimonio del que hace parte.",
    ("sacramentos_contrayente", "fiel_id"): "Fiel que contrae matrimonio.",
    ("sacramentos_contrayente", "sexo"): "Sexo del contrayente; uno de cada sexo por matrimonio.",
    ("sacramentos_contrayente", "estado_civil"): "Estado civil antes del matrimonio.",
    ("sacramentos_testigomatrimonio", "matrimonio_id"): "Matrimonio en el que es testigo.",
    ("sacramentos_testigomatrimonio", "nombre"): "Nombre completo del testigo.",
    ("sacramentos_padrinomatrimonio", "matrimonio_id"): "Matrimonio en el que es padrino.",
    ("sacramentos_padrinomatrimonio", "nombre"): "Nombre completo del padrino.",
    ("sacramentos_proclamamatrimonio", "matrimonio_id"): "Matrimonio al que corresponde.",
    ("sacramentos_hijoreconocidomatrimonio", "matrimonio_id"): "Matrimonio que reconoce al hijo.",
    ("sacramentos_hijoreconocidomatrimonio", "nombre"): "Nombre completo del hijo.",
    ("sacramentos_hijoreconocidomatrimonio", "bautizado"): "Indica si el hijo está bautizado.",
    ("sacramentos_notamarginalmatrimonio", "matrimonio_id"): (
        "Matrimonio al que corresponde la nota; es a la vez llave primaria y foránea (1:1)."
    ),
    ("sacramentos_notamarginalmatrimonio", "presencio"): "Ministro que presenció el matrimonio.",
    ("sacramentos_notamarginalmatrimonio", "doy_fe"): "Ministro que da fe de la nota.",
    ("sacramentos_documentosacramento", "sacramento_id"): "Partida a la que se adjunta.",
    ("sacramentos_documentosacramento", "descripcion"): "Descripción del documento adjunto.",
    ("sacramentos_documentosacramento", "archivo"): (
        "Ruta relativa del archivo guardado en la carpeta de medios del servidor."
    ),
    ("sacramentos_documentosacramento", "subido_por_id"): "Usuario que subió el archivo.",
    ("sacramentos_documentosacramento", "subido_en"): "Fecha y hora en que se subió.",
    ("sacramentos_anotacionmarginal", "fecha"): "Fecha de la anotación.",
    ("sacramentos_anotacionmarginal", "descripcion"): "Texto de la anotación marginal.",
    ("sacramentos_partidaeliminada", "eliminado_en"): "Fecha y hora de la eliminación.",
    ("sacramentos_historialsacramento", "sacramento_id"): "Partida sobre la que se actuó.",
    ("sacramentos_historialsacramento", "descripcion"): "Detalle de la acción.",
    ("sacramentos_historialsacramento", "usuario_id"): "Usuario que realizó la acción.",
    ("sacramentos_historialsacramento", "fecha"): "Fecha y hora de la acción.",
}

DESCRIPCIONES_DJANGO = {
    "auth_group": "Grupos de usuarios para asignar permisos en bloque.",
    "auth_group_permissions": "Relación muchos a muchos entre grupos y permisos.",
    "auth_permission": "Permisos por modelo (agregar, cambiar, eliminar y ver).",
    "auth_user": "Usuarios que inician sesión en el sistema, con su contraseña cifrada.",
    "auth_user_groups": "Relación muchos a muchos entre usuarios y grupos.",
    "auth_user_user_permissions": "Permisos asignados directamente a un usuario.",
    "django_admin_log": "Bitácora de los cambios hechos desde el panel de administración.",
    "django_content_type": "Catálogo de los modelos instalados; lo usan permisos y bitácora.",
    "django_migrations": "Registro de las migraciones aplicadas a la base.",
    "django_session": "Sesiones abiertas de los usuarios (cookie de sesión).",
}


@dataclass
class LlaveForanea:
    nombre: str
    tabla: str
    columna: str
    on_delete: str
    diferible: bool
    regla_django: str = ""


@dataclass
class Columna:
    nombre: str
    tipo: str
    nulo: bool
    defecto: str
    defecto_django: str = ""
    pk: bool = False
    unica: bool = False
    fk: LlaveForanea | None = None
    descripcion: str = ""

    @property
    def marcas(self):
        marcas = []
        if self.pk:
            marcas.append("PK")
        if self.fk:
            marcas.append("FK")
        if self.unica and not self.pk:
            marcas.append("UQ")
        return marcas


@dataclass
class Restriccion:
    nombre: str
    tipo: str
    definicion: str
    nota: str = ""


@dataclass
class Indice:
    nombre: str
    definicion: str
    unico: bool
    primario: bool
    restriccion: str

    @property
    def clase(self):
        if self.primario:
            return "Llave primaria"
        if self.restriccion:
            return "Único (restricción)"
        if self.unico:
            return "Único parcial" if " WHERE " in self.definicion else "Único"
        return "Parcial" if " WHERE " in self.definicion else "Normal"


@dataclass
class Tabla:
    nombre: str
    modulo: str = ""
    titulo: str = ""
    descripcion: str = ""
    columnas: list[Columna] = field(default_factory=list)
    restricciones: list[Restriccion] = field(default_factory=list)
    indices: list[Indice] = field(default_factory=list)

    @property
    def ancla(self):
        return "t-" + self.nombre.replace("_", "-")


def es_propia(nombre):
    return nombre.startswith(PREFIJOS_PROPIOS)


def es_django(nombre):
    return nombre.startswith(PREFIJOS_DJANGO)


# ---------------------------------------------------------------------------
# Conexión de solo lectura
# ---------------------------------------------------------------------------


def limpiar_mensaje(texto, url):
    """Quita de un mensaje el usuario, la contraseña y la URL de conexión."""
    texto = str(texto)
    if not url:
        return texto
    partida = urlparse(url)
    secretos = [url, partida.password, partida.username]
    secretos += [unquote(s) for s in (partida.password, partida.username) if s]
    for secreto in sorted({s for s in secretos if s}, key=len, reverse=True):
        texto = texto.replace(secreto, "***")
    return texto


@contextmanager
def consultor_local():
    """Ejecuta consultas en la base del proyecto y devuelve las filas."""

    def consultar(sql, parametros=()):
        with connection.cursor() as cursor:
            cursor.execute(sql, list(parametros))
            return cursor.fetchall()

    yield consultar


@contextmanager
def consultor_supabase(url):
    """Abre una conexión de solo lectura a Supabase a partir de la URL."""
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - psycopg viene en requirements
        raise CommandError("Falta el paquete psycopg para conectarse a Supabase.") from error

    try:
        conexion = psycopg.connect(
            url,
            sslmode="require",
            connect_timeout=20,
            application_name="generar_modelo_fisico",
        )
    except psycopg.Error as error:
        raise CommandError(
            f"No se pudo conectar a Supabase ({respaldos.enmascarar_url(url)}): "
            + limpiar_mensaje(error, url)
        ) from None
    try:
        conexion.read_only = True
        with conexion.cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            if cursor.fetchone()[0] != "on":
                raise CommandError("La conexión a Supabase no quedó en modo de solo lectura.")

        def consultar(sql, parametros=()):
            try:
                with conexion.cursor() as cursor:
                    cursor.execute(sql, list(parametros))
                    return cursor.fetchall()
            except psycopg.Error as error:
                raise CommandError(
                    "Falló una consulta al catálogo de Supabase: " + limpiar_mensaje(error, url)
                ) from None

        yield consultar
    finally:
        conexion.rollback()
        conexion.close()


# ---------------------------------------------------------------------------
# Lectura del catálogo (sin filas de datos)
# ---------------------------------------------------------------------------

SQL_VERSION = "SELECT current_setting('server_version'), version()"

SQL_TABLAS = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = %s AND table_type = 'BASE TABLE'
ORDER BY table_name
"""

SQL_COLUMNAS = """
SELECT col.table_name, col.column_name,
       pg_catalog.format_type(att.atttypid, att.atttypmod),
       col.is_nullable, col.column_default, col.is_identity, col.identity_generation
FROM information_schema.columns col
JOIN pg_catalog.pg_namespace nsp ON nsp.nspname = col.table_schema
JOIN pg_catalog.pg_class cls ON cls.relnamespace = nsp.oid AND cls.relname = col.table_name
JOIN pg_catalog.pg_attribute att ON att.attrelid = cls.oid AND att.attname = col.column_name
WHERE col.table_schema = %s AND cls.relkind IN ('r', 'p')
ORDER BY col.table_name, col.ordinal_position
"""

SQL_RESTRICCIONES = """
SELECT rel.relname, con.conname, con.contype, pg_catalog.pg_get_constraintdef(con.oid),
       ARRAY(
           SELECT att.attname::text
           FROM unnest(con.conkey) WITH ORDINALITY AS llave(num, orden)
           JOIN pg_catalog.pg_attribute att
             ON att.attrelid = con.conrelid AND att.attnum = llave.num
           ORDER BY llave.orden
       ),
       ref.relname,
       ARRAY(
           SELECT att.attname::text
           FROM unnest(con.confkey) WITH ORDINALITY AS llave(num, orden)
           JOIN pg_catalog.pg_attribute att
             ON att.attrelid = con.confrelid AND att.attnum = llave.num
           ORDER BY llave.orden
       ),
       con.confdeltype, con.condeferrable
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
LEFT JOIN pg_catalog.pg_class ref ON ref.oid = con.confrelid
WHERE nsp.nspname = %s AND con.contype IN ('p', 'f', 'u', 'c')
ORDER BY rel.relname, con.contype, con.conname
"""

SQL_INDICES = """
SELECT tab.relname, idx.relname, pg_catalog.pg_get_indexdef(idx.oid),
       ind.indisunique, ind.indisprimary,
       COALESCE((
           SELECT con.conname FROM pg_catalog.pg_constraint con
           WHERE con.conindid = idx.oid AND con.conrelid = tab.oid
             AND con.contype IN ('p', 'u')
           LIMIT 1
       ), '')
FROM pg_catalog.pg_index ind
JOIN pg_catalog.pg_class idx ON idx.oid = ind.indexrelid
JOIN pg_catalog.pg_class tab ON tab.oid = ind.indrelid
JOIN pg_catalog.pg_namespace nsp ON nsp.oid = tab.relnamespace
WHERE nsp.nspname = %s
ORDER BY tab.relname, ind.indisprimary DESC, idx.relname
"""


def _texto(valor):
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    return "" if valor is None else str(valor)


def leer_catalogo(consultar, esquema=respaldos.ESQUEMA_PUBLICO):
    """Lee la estructura del esquema y devuelve ``(version, tablas)``."""
    version_corta, version_larga = consultar(SQL_VERSION)[0]
    tablas = {nombre: Tabla(nombre) for (nombre,) in consultar(SQL_TABLAS, [esquema])}

    for tabla, nombre, tipo, nulo, defecto, identidad, generacion in consultar(
        SQL_COLUMNAS, [esquema]
    ):
        if tabla not in tablas:
            continue
        if identidad == "YES":
            defecto = f"Identidad ({generacion or 'BY DEFAULT'})"
        tablas[tabla].columnas.append(
            Columna(nombre=nombre, tipo=tipo, nulo=nulo == "YES", defecto=_texto(defecto))
        )

    for fila in consultar(SQL_RESTRICCIONES, [esquema]):
        tabla, nombre, tipo, definicion, columnas, ref, columnas_ref, borrado, diferible = fila
        if tabla not in tablas:
            continue
        tipo = _texto(tipo)
        objeto = tablas[tabla]
        por_nombre = {columna.nombre: columna for columna in objeto.columnas}
        columnas = list(columnas or [])
        if tipo == "p":
            for nombre_columna in columnas:
                if nombre_columna in por_nombre:
                    por_nombre[nombre_columna].pk = True
        elif tipo == "u" and len(columnas) == 1 and columnas[0] in por_nombre:
            por_nombre[columnas[0]].unica = True
        elif tipo == "f" and len(columnas) == 1 and columnas[0] in por_nombre:
            columnas_ref = list(columnas_ref or [])
            por_nombre[columnas[0]].fk = LlaveForanea(
                nombre=nombre,
                tabla=ref,
                columna=columnas_ref[0] if columnas_ref else "",
                on_delete=REGLAS_ON_DELETE.get(_texto(borrado), _texto(borrado)),
                diferible=bool(diferible),
            )
        objeto.restricciones.append(
            Restriccion(nombre=nombre, tipo=TIPOS_RESTRICCION[tipo], definicion=definicion)
        )

    for tabla, nombre, definicion, unico, primario, restriccion in consultar(
        SQL_INDICES, [esquema]
    ):
        if tabla in tablas:
            tablas[tabla].indices.append(
                Indice(
                    nombre=nombre,
                    definicion=_definicion_indice(definicion),
                    unico=bool(unico),
                    primario=bool(primario),
                    restriccion=restriccion,
                )
            )
    return {"corta": version_corta, "larga": version_larga}, tablas


def _definicion_indice(definicion):
    """Deja solo la parte útil de ``CREATE INDEX ... USING btree (col)``."""
    _, separador, resto = definicion.partition(" USING ")
    return resto if separador else definicion


# ---------------------------------------------------------------------------
# Descripciones desde los modelos de Django
# ---------------------------------------------------------------------------


def oracion(texto):
    """Pone en mayúscula la primera letra y cierra con punto si hace falta."""
    texto = " ".join(str(texto).split())
    if not texto:
        return ""
    for posicion, caracter in enumerate(texto):
        if caracter.isalpha():
            texto = texto[:posicion] + caracter.upper() + texto[posicion + 1 :]
            break
    if texto[-1] not in ".?!":
        texto += "."
    return texto


def docstring_propio(modelo):
    """Docstring escrito en el modelo (Django genera uno automático si falta)."""
    documento = modelo.__dict__.get("__doc__") or ""
    if not documento or documento.startswith(f"{modelo.__name__}("):
        return ""
    return " ".join(inspect.cleandoc(documento).split())


def describir_campo(tabla, campo):
    """Descripción de una columna a partir de su campo de Django."""
    if campo.help_text:
        texto = oracion(campo.help_text)
    elif (tabla, campo.column) in DESCRIPCIONES_COLUMNAS:
        texto = DESCRIPCIONES_COLUMNAS[(tabla, campo.column)]
    elif campo.primary_key and campo.auto_created:
        texto = "Identificador de la fila; lo genera la base de datos."
    elif campo._verbose_name:
        texto = oracion(campo._verbose_name)
        if campo.one_to_one:
            texto += " Relación 1:1."
    elif campo.column in DESCRIPCIONES_GENERICAS:
        texto = DESCRIPCIONES_GENERICAS[campo.column]
    elif campo.is_relation:
        texto = oracion(f"referencia a {campo.related_model._meta.verbose_name}")
    else:
        texto = oracion(campo.verbose_name)
    if campo.choices:
        valores = ", ".join(str(valor) for valor, _ in campo.flatchoices)
        texto += f" Valores: {valores}."
    return texto


def defecto_django(campo):
    """Valor por defecto que asigna Django (no la base) cuando existe."""
    if getattr(campo, "auto_now_add", False) or getattr(campo, "auto_now", False):
        return "fecha y hora actual"
    if not campo.has_default() or callable(campo.default):
        return ""
    if isinstance(campo.default, str) and not campo.default:
        return ""
    return str(campo.default)


def aplicar_modelos(tablas):
    """Completa títulos, módulos y descripciones con los modelos de Django."""
    for modelo in apps.get_models():
        tabla = tablas.get(modelo._meta.db_table)
        if tabla is None:
            continue
        tabla.modulo = modelo._meta.app_label
        tabla.titulo = oracion(modelo._meta.verbose_name).rstrip(".")
        tabla.descripcion = docstring_propio(modelo) or DESCRIPCIONES_TABLAS.get(tabla.nombre, "")
        campos = {campo.column: campo for campo in modelo._meta.concrete_fields}
        for columna in tabla.columnas:
            campo = campos.get(columna.nombre)
            if campo is None:
                continue
            columna.descripcion = describir_campo(tabla.nombre, campo)
            columna.defecto_django = defecto_django(campo)
            if columna.fk and isinstance(campo, models.ForeignKey):
                columna.fk.regla_django = campo.remote_field.on_delete.__name__.replace("_", " ")
        foraneas = {c.fk.nombre: c.fk for c in tabla.columnas if c.fk}
        for restriccion in tabla.restricciones:
            fk = foraneas.get(restriccion.nombre)
            if fk:
                restriccion.nota = f"ON DELETE en la base: {fk.on_delete}"
                if fk.regla_django:
                    restriccion.nota += f" · regla en Django: {fk.regla_django}"
    for tabla in tablas.values():
        if not tabla.modulo:
            tabla.modulo = tabla.nombre.split("_", 1)[0]


def orden_de_modelos():
    """Posición de cada tabla según el orden de definición de los modelos."""
    return {modelo._meta.db_table: indice for indice, modelo in enumerate(apps.get_models())}


def clasificar(tablas):
    """Separa las tablas propias, las de Django y cualquier otra del esquema."""
    orden = orden_de_modelos()
    propias = [t for t in tablas.values() if es_propia(t.nombre)]
    propias.sort(key=lambda t: (orden.get(t.nombre, len(orden)), t.nombre))
    django = sorted((t for t in tablas.values() if es_django(t.nombre)), key=lambda t: t.nombre)
    otras = sorted(
        (t for t in tablas.values() if not es_propia(t.nombre) and not es_django(t.nombre)),
        key=lambda t: t.nombre,
    )
    return propias, django, otras


def modulos_con_tablas(propias):
    grupos = []
    for etiqueta, titulo in MODULOS:
        tablas = [t for t in propias if t.modulo == etiqueta]
        if tablas:
            grupos.append({"id": f"m-{etiqueta}", "titulo": titulo, "tablas": tablas})
    return grupos


# ---------------------------------------------------------------------------
# Diagramas Mermaid
# ---------------------------------------------------------------------------


def tipo_corto(tipo):
    """Tipo de PostgreSQL abreviado y sin espacios, como lo pide Mermaid."""
    base, parentesis, resto = tipo.partition("(")
    base = TIPOS_CORTOS.get(base.strip(), base.strip())
    return (base + parentesis + resto).replace(" ", "_")


def cardinalidad(columna):
    """Símbolos Mermaid ``padre--hijo`` según nulos y unicidad de la FK."""
    padre = "|o" if columna.nulo else "||"
    hijo = "o|" if columna.unica or columna.pk else "o{"
    return f"{padre}--{hijo}"


def codigo_mermaid(tablas, nombres, con_columnas=True):
    """Genera el ``erDiagram`` de las tablas indicadas.

    Solo se dibujan las relaciones entre las tablas incluidas; las foráneas
    hacia otras tablas quedan marcadas como FK en su columna. Sin columnas
    (vista general) cada tabla es una caja con su nombre sin el prefijo de la
    aplicación (el módulo se indica con el color) y las relaciones van sin
    etiqueta para que el dibujo quede compacto.
    """
    incluidas = [nombre for nombre in nombres if nombre in tablas]
    # Las tablas sin relaciones dentro del diagrama van primero: así quedan
    # arriba y las líneas de las demás no les pasan por encima.
    relacionadas = {
        nombre
        for nombre in incluidas
        for columna in tablas[nombre].columnas
        if columna.fk and columna.fk.tabla in incluidas
        for nombre in (nombre, columna.fk.tabla)
    }
    incluidas.sort(key=lambda nombre: nombre in relacionadas)
    relaciones = []
    parejas = set()
    lineas = ["erDiagram"]
    for nombre in incluidas:
        if con_columnas:
            lineas.append(f"  {nombre} {{")
        else:
            lineas.append(f"  {nombre}[{nombre.split('_', 1)[1]}]")
        for columna in tablas[nombre].columnas:
            if con_columnas:
                marcas = ",".join("UK" if m == "UQ" else m for m in columna.marcas)
                lineas.append(f"    {tipo_corto(columna.tipo)} {columna.nombre} {marcas}".rstrip())
            if columna.fk and columna.fk.tabla in incluidas:
                # En la vista general basta una línea por pareja de tablas.
                if not con_columnas and (columna.fk.tabla, nombre) in parejas:
                    continue
                parejas.add((columna.fk.tabla, nombre))
                etiqueta = columna.nombre if con_columnas else ""
                relaciones.append(
                    f'  {columna.fk.tabla} {cardinalidad(columna)} {nombre} : "{etiqueta}"'
                )
        if con_columnas:
            lineas.append("  }")
    return "\n".join(lineas + relaciones)


def diagramas(tablas_propias):
    """Lista de diagramas: uno general (solo tablas) y uno por módulo."""
    por_nombre = {tabla.nombre: tabla for tabla in tablas_propias}
    lista = [
        {
            "id": "d-general",
            "titulo": "Vista general",
            "nota": f"Las {len(por_nombre)} tablas propias y todas las relaciones entre ellas. "
            "Cada caja lleva el nombre de la tabla sin el prefijo de su aplicación; el color "
            "indica el módulo. Si dos tablas tienen varias foráneas entre sí se dibuja una sola "
            "línea. Las columnas están en los diagramas por módulo.",
            "codigo": codigo_mermaid(por_nombre, list(por_nombre), con_columnas=False),
            "letra": LETRA_GENERAL,
            "modulos": [
                {"etiqueta": etiqueta, "titulo": titulo, "color": COLORES_MODULO[etiqueta]}
                for etiqueta, titulo in MODULOS
            ],
        }
    ]
    for identificador, titulo, modulos, excluir, limitar in DIAGRAMAS_MODULO:
        nombres = [
            tabla.nombre
            for tabla in tablas_propias
            if tabla.modulo in modulos
            and tabla.nombre not in excluir
            and (not limitar or tabla.nombre in limitar)
        ]
        if not nombres:
            continue
        codigo = codigo_mermaid(por_nombre, nombres)
        etiquetas = re.findall(r': "([^"]*)"$', codigo, re.M)
        lista.append(
            {
                "id": f"d-{identificador}",
                "titulo": titulo,
                "nota": "Todas las columnas con su tipo. Las llaves foráneas hacia tablas que no "
                "están en este diagrama se marcan FK; su destino aparece en la vista general y en "
                "el diccionario de datos.",
                "codigo": codigo,
                "letra": LETRA_DIAGRAMA,
                # De izquierda a derecha, las etiquetas quedan entre columnas de
                # tablas: el espacio entre ellas debe alcanzar para la más larga.
                "separacion_lr": 40 + max((len(e) for e in etiquetas), default=0) * 8,
            }
        )
    return lista


def foraneas_a_django(tablas_propias):
    """Columnas propias que apuntan a tablas de Django (no se dibujan)."""
    return [
        f"{tabla.nombre}.{columna.nombre} → {columna.fk.tabla}"
        for tabla in tablas_propias
        for columna in tabla.columnas
        if columna.fk and es_django(columna.fk.tabla)
    ]


# ---------------------------------------------------------------------------
# DDL con pg_dump
# ---------------------------------------------------------------------------


def comando_pg_dump(tablas, url=None):
    """Arma pg_dump --schema-only con las opciones de exportar_esquema."""
    comando = [
        respaldos.buscar_binario("pg_dump"),
        "--schema-only",
        "--no-owner",
        "--no-privileges",
    ]
    if url:
        comando += ["-d", respaldos.base_de_url(url)]
    else:
        base = settings.DATABASES["default"]
        comando += [
            "-h",
            str(base.get("HOST") or "localhost"),
            "-p",
            str(base.get("PORT") or "5432"),
            "-U",
            str(base.get("USER") or ""),
            "-d",
            str(base.get("NAME") or ""),
        ]
    for tabla in tablas:
        respaldos.citar_identificador(tabla)
        comando += ["-t", f"{respaldos.ESQUEMA_PUBLICO}.{tabla}"]
    return comando


def obtener_ddl(tablas, url=None):
    """DDL de las tablas indicadas, sin comentarios ni ajustes de sesión."""
    if url:
        entorno = respaldos.entorno_desde_url(url)
        entorno["PGOPTIONS"] = "-c default_transaction_read_only=on"
    else:
        entorno = respaldos.entorno_local()
    resultado = respaldos.ejecutar(comando_pg_dump(tablas, url), entorno)
    if resultado.returncode != 0:
        raise CommandError(
            "pg_dump falló: " + limpiar_mensaje(respaldos.mensaje_error(resultado), url)
        )
    return filtrar_ddl(resultado.stdout.decode("utf-8", errors="replace"))


_LINEA_SOBRANTE = re.compile(r"^(--|SET |SELECT pg_catalog\.set_config|\\restrict|\\unrestrict)")


def filtrar_ddl(texto):
    lineas = []
    for linea in texto.splitlines():
        if _LINEA_SOBRANTE.match(linea):
            continue
        if not linea.strip() and (not lineas or not lineas[-1].strip()):
            continue
        lineas.append(linea.rstrip())
    # Las sentencias de una sola línea seguidas (por ejemplo, las de RLS en
    # Supabase) van juntas, sin línea en blanco entre ellas.
    compactas = []
    for indice, linea in enumerate(lineas):
        anterior = compactas[-1] if compactas else ""
        siguiente = lineas[indice + 1] if indice + 1 < len(lineas) else ""
        if (
            not linea
            and _sentencia_corta(anterior)
            and _sentencia_corta(siguiente)
            and (len(compactas) < 2 or not compactas[-2] or _sentencia_corta(compactas[-2]))
        ):
            continue
        compactas.append(linea)
    return "\n".join(compactas).strip() + "\n"


def _sentencia_corta(linea):
    return bool(linea) and not linea.startswith(" ") and linea.endswith(";")


# ---------------------------------------------------------------------------
# Recursos (mermaid y fuentes) y renderizado con Playwright
# ---------------------------------------------------------------------------


def directorio_herramientas():
    return Path(settings.BASE_DIR) / "herramientas" / "modelo_fisico"


def obtener_recurso(clave):
    """Ruta local del recurso; lo descarga una vez y verifica su SHA-256."""
    ruta_cdn, archivo, huella = RECURSOS[clave]
    destino = directorio_herramientas() / archivo
    if destino.exists() and hashlib.sha256(destino.read_bytes()).hexdigest() == huella:
        return destino
    url = URL_CDN + ruta_cdn
    try:
        with urllib.request.urlopen(url, timeout=60) as respuesta:
            contenido = respuesta.read()
    except OSError as error:
        raise CommandError(
            f"No se pudo descargar {url} ({error}). Conéctate a internet una vez: el archivo "
            f"queda guardado en {directorio_herramientas()} para usarlo sin conexión."
        ) from None
    if hashlib.sha256(contenido).hexdigest() != huella:
        raise CommandError(f"La huella SHA-256 de {url} no coincide; no se usará el archivo.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".tmp")
    temporal.write_bytes(contenido)
    temporal.replace(destino)
    return destino


def css_fuentes():
    """Reglas @font-face con Inter y JetBrains Mono incrustadas en base64."""
    reglas = []
    for clave, familia, peso in (
        ("inter-400", "Inter", 400),
        ("inter-500", "Inter", 500),
        ("inter-600", "Inter", 600),
        ("inter-700", "Inter", 700),
        ("mono-400", "JetBrains Mono", 400),
    ):
        datos = base64.b64encode(obtener_recurso(clave).read_bytes()).decode("ascii")
        reglas.append(
            f'@font-face {{ font-family: "{familia}"; font-weight: {peso}; font-style: normal; '
            f'src: url("data:font/woff2;base64,{datos}") format("woff2"); }}'
        )
    return "\n".join(reglas)


# Área útil (px CSS) de una página carta con los márgenes del documento
# (16 mm a los lados y arriba, 18 mm abajo). Del alto se resta en el
# navegador lo que ocupan el título y la leyenda de cada diagrama.
AREA_DIAGRAMA = {"vertical": (695, 927), "horizontal": (935, 687)}

JS_DIAGRAMAS = """
async ({ area, colores }) => {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    fontFamily: 'Inter, sans-serif',
    themeVariables: {
      fontFamily: 'Inter, sans-serif',
      fontSize: '14px',
      primaryColor: '#eef2f8',
      primaryBorderColor: '#1e2a4a',
      primaryTextColor: '#1e293b',
      lineColor: '#55677f',
      attributeBackgroundColorOdd: '#ffffff',
      attributeBackgroundColorEven: '#f4f6fa'
    },
    er: {
      useMaxWidth: false,
      entityPadding: 8,
      minEntityWidth: 60,
      minEntityHeight: 30,
      nodeSpacing: 36,
      rankSpacing: 48
    }
  });
  // Cada diagrama se dibuja de arriba abajo (TB) y de izquierda a derecha
  // (LR); se conserva la variante que quede más grande en la página.
  for (const original of document.querySelectorAll('.diagrama .mermaid')) {
    const datos = original.closest('.diagrama').dataset;
    const letra = Number(datos.letra || 14);
    // Con etiquetas, de arriba abajo hace falta hueco para una o dos líneas.
    const separacion = datos.separacionLr
      ? { TB: 72, LR: Number(datos.separacionLr) }
      : { TB: 48, LR: 48 };
    const codigo = original.textContent;
    const directiva = (direccion) => '%%{init: {"themeVariables": {"fontSize": "' + letra +
      'px"}, "er": {"fontSize": ' + letra + ', "layoutDirection": "' + direccion +
      '", "rankSpacing": ' + separacion[direccion] + '}}}%%\\n';
    const copia = original.cloneNode(true);
    original.dataset.direccion = 'TB';
    original.textContent = directiva('TB') + codigo;
    copia.dataset.direccion = 'LR';
    copia.textContent = directiva('LR') + codigo;
    original.after(copia);
  }
  // Mermaid mide el texto al dibujar: Inter tiene que estar cargada antes.
  await Promise.all(['400', '600'].map((peso) => document.fonts.load(peso + ' 14px Inter')));
  await mermaid.run({ querySelector: '.mermaid' });
  // Dos foráneas entre el mismo par de tablas dejan sus etiquetas una sobre
  // otra: se separan por el eje en que se solapan menos.
  for (const svg of document.querySelectorAll('.diagrama svg')) {
    const colocadas = [];
    for (const texto of svg.querySelectorAll('text.relationshipLabel')) {
      const fondo = texto.previousElementSibling;
      const caja = texto.getBBox();
      for (let intento = 0; intento < 6; intento++) {
        const otra = colocadas.find((o) =>
          caja.x < o.x + o.width && o.x < caja.x + caja.width &&
          caja.y < o.y + o.height && o.y < caja.y + caja.height);
        if (!otra) break;
        const enX = Math.min(caja.x + caja.width - otra.x, otra.x + otra.width - caja.x) + 4;
        const enY = Math.min(caja.y + caja.height - otra.y, otra.y + otra.height - caja.y) + 2;
        const mover = (elemento, eje, delta) => {
          if (elemento) elemento.setAttribute(eje, Number(elemento.getAttribute(eje)) + delta);
        };
        const conFondo = fondo && fondo.matches('rect.relationshipLabelBox') ? fondo : null;
        if (enX <= enY) {
          const delta = caja.x + caja.width / 2 >= otra.x + otra.width / 2 ? enX : -enX;
          mover(texto, 'x', delta); mover(conFondo, 'x', delta); caja.x += delta;
        } else {
          const delta = caja.y + caja.height / 2 >= otra.y + otra.height / 2 ? enY : -enY;
          mover(texto, 'y', delta); mover(conFondo, 'y', delta); caja.y += delta;
        }
      }
      colocadas.push(caja);
    }
  }
  const resultado = [];
  for (const figura of document.querySelectorAll('.diagrama')) {
    const seccion = figura.closest('.pagina-diagrama');
    const letra = Number(figura.dataset.letra || 14);
    if (figura.dataset.colorear) {
      // Mermaid arma el id como entity-<tabla sin guiones bajos>-<uuid>.
      for (const grupo of figura.querySelectorAll('g[id^="entity-"]')) {
        const caja = grupo.querySelector('rect.entityBox');
        for (const [prefijo, color] of Object.entries(colores)) {
          if (caja && grupo.id.startsWith('entity-' + prefijo)) {
            caja.style.setProperty('fill', color, 'important');
          }
        }
      }
    }
    let mejor = null;
    for (const variante of figura.querySelectorAll('.mermaid')) {
      const caja = variante.querySelector('svg').viewBox.baseVal;
      variante.style.display = 'none';
      for (const [orientacion, [ancho, alto]] of Object.entries(area)) {
        // Lo que ocupan el título y la leyenda con el ancho real de la página.
        seccion.style.width = ancho + 'px';
        let reserva = 28;
        for (const hijo of seccion.children) {
          if (hijo !== figura) reserva += hijo.getBoundingClientRect().height;
        }
        const escala = Math.min(ancho / caja.width, (alto - reserva) / caja.height, 1.6);
        if (!mejor || escala > mejor.escala) mejor = { variante, caja, orientacion, escala };
      }
    }
    seccion.style.width = '';
    for (const variante of figura.querySelectorAll('.mermaid')) {
      if (variante !== mejor.variante) variante.remove();
    }
    const svg = mejor.variante.querySelector('svg');
    mejor.variante.style.display = '';
    svg.setAttribute('width', (mejor.caja.width * mejor.escala).toFixed(1));
    svg.setAttribute('height', (mejor.caja.height * mejor.escala).toFixed(1));
    svg.style.maxWidth = 'none';
    seccion.classList.add(mejor.orientacion);
    resultado.push({
      id: figura.id,
      orientacion: mejor.orientacion,
      direccion: mejor.variante.dataset.direccion,
      escala: mejor.escala,
      letra_pt: letra * mejor.escala * 0.75
    });
  }
  await document.fonts.ready;
  return resultado;
}
"""

# El diagrama ER de mermaid 11.4.1 fija en 100 px la separación entre tablas y
# no la deja configurar; con 28 tablas el dibujo queda ilegible. Se cambia, en
# memoria, para que lea er.nodeSpacing y er.rankSpacing (con 100 como respaldo).
ESPACIADO_ER_ORIGINAL = (
    "rankdir:Bi.layoutDirection,marginx:20,marginy:20,nodesep:100,edgesep:100,ranksep:100"
)
ESPACIADO_ER_AJUSTADO = (
    "rankdir:Bi.layoutDirection,marginx:20,marginy:20,nodesep:Bi.nodeSpacing??100,"
    "edgesep:Bi.nodeSpacing??100,ranksep:Bi.rankSpacing??100"
)


def ajustar_mermaid(codigo):
    """Hace configurable la separación del diagrama ER (ver arriba)."""
    return codigo.replace(ESPACIADO_ER_ORIGINAL, ESPACIADO_ER_AJUSTADO, 1)


JS_INDICE = """
(paginas) => {
  let cambio = false;
  for (const celda of document.querySelectorAll('.indice-pagina')) {
    const valor = paginas[celda.dataset.destino];
    const texto = valor ? String(valor) : '';
    if (celda.textContent !== texto) { celda.textContent = texto; cambio = true; }
  }
  return cambio;
}
"""


def paginas_de_destinos(pdf):
    """Página (desde 1) de cada destino con nombre de un PDF de Chromium.

    Chromium escribe los destinos de los enlaces internos en ``/Dests`` como
    ``/nombre [N 0 R /XYZ x y z]``. Se recorre el árbol de páginas para
    saber el número de cada objeto ``N``. Si el formato no se reconoce,
    devuelve un diccionario vacío y el índice queda sin números.
    """
    objetos = {
        int(numero): cuerpo
        for numero, cuerpo in re.findall(rb"(\d+) 0 obj\s*(<<.*?>>)\s*(?:endobj|stream)", pdf, re.S)
    }
    catalogo = next((c for c in objetos.values() if re.search(rb"/Type\s*/Catalog", c)), None)
    if catalogo is None:
        return {}
    raiz = re.search(rb"/Pages\s+(\d+) 0 R", catalogo)
    destinos = re.search(rb"/Dests\s+(\d+) 0 R", catalogo)
    if not raiz or not destinos:
        return {}

    orden = []

    def recorrer(numero, profundidad=0):
        cuerpo = objetos.get(numero, b"")
        hijos = re.search(rb"/Kids\s*\[([^\]]*)\]", cuerpo)
        if hijos and profundidad < 50:
            for hijo in re.findall(rb"(\d+) 0 R", hijos.group(1)):
                recorrer(int(hijo), profundidad + 1)
        else:
            orden.append(numero)

    recorrer(int(raiz.group(1)))
    posicion = {numero: indice + 1 for indice, numero in enumerate(orden)}
    paginas = {}
    for nombre, pagina in re.findall(
        rb"/([^\s/\[\]<>()]+)\s*\[\s*(\d+) 0 R", objetos.get(int(destinos.group(1)), b"")
    ):
        nombre = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), nombre)
        if int(pagina) in posicion:
            paginas[nombre.decode("utf-8", errors="replace")] = posicion[int(pagina)]
    return paginas


def renderizar(html, destino_html, destino_pdf):
    """Renderiza los diagramas, numera el índice y escribe el HTML y el PDF.

    Devuelve un diccionario con el número de páginas y la orientación y
    escala de cada diagrama.
    """
    try:
        from playwright.sync_api import Error as ErrorPlaywright
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise CommandError(
            "Falta Playwright. Instálalo con pip install playwright y "
            "python -m playwright install chromium."
        ) from error

    mermaid_js = ajustar_mermaid(obtener_recurso("mermaid").read_text(encoding="utf-8"))
    fuentes = css_fuentes()
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            try:
                pagina = navegador.new_page()
                # El documento no necesita red: todo va incrustado.
                pagina.route("**/*", lambda ruta: ruta.abort())
                pagina.set_content(html, wait_until="load")
                pagina.add_style_tag(content=fuentes)
                pagina.add_script_tag(content=mermaid_js)
                figuras = pagina.evaluate(
                    JS_DIAGRAMAS, {"area": AREA_DIAGRAMA, "colores": COLORES_MODULO}
                )
                pagina.evaluate("document.querySelectorAll('script').forEach(s => s.remove())")
                pdf = b""
                for _ in range(4):
                    pdf = pagina.pdf(
                        prefer_css_page_size=True,
                        print_background=True,
                        outline=True,
                        tagged=True,
                    )
                    if not pagina.evaluate(JS_INDICE, paginas_de_destinos(pdf)):
                        break
                contenido = pagina.content()
            finally:
                navegador.close()
    except ErrorPlaywright as error:
        raise CommandError(f"Chromium no pudo generar el documento: {error}") from None

    Path(destino_html).write_text(contenido, encoding="utf-8", newline="\n")
    Path(destino_pdf).write_bytes(pdf)
    return {"paginas": contar_paginas(pdf), "diagramas": figuras}


def contar_paginas(pdf):
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))
