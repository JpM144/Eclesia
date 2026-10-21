"""Utilidades para exportar el esquema y respaldar las bases PostgreSQL.

Reúne la localización de los binarios de PostgreSQL, la construcción de los
entornos de conexión (sin exponer credenciales en la línea de comandos), el
conteo de filas por tabla, las operaciones de Row Level Security sobre el
esquema ``public`` de Supabase y la poda de los respaldos locales.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection

DIRECTORIO_POSTGRES = Path(r"C:\Program Files\PostgreSQL\17\bin")
ESQUEMA_PUBLICO = "public"
RESPALDOS_A_CONSERVAR = 7
_IDENTIFICADOR_SEGURO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def enmascarar_url(url):
    """Devuelve la cadena de conexión con el usuario y la contraseña ocultos."""
    partida = urlparse(url)
    anfitrion = partida.hostname or ""
    puerto = partida.port or 5432
    base = (partida.path or "/postgres").lstrip("/") or "postgres"
    return f"{partida.scheme or 'postgresql'}://postgres.***@{anfitrion}:{puerto}/{base}"


def buscar_binario(nombre):
    """Localiza un ejecutable de PostgreSQL en el PATH o en la instalación 17."""
    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado
    candidato = DIRECTORIO_POSTGRES / f"{nombre}.exe"
    if candidato.exists():
        return str(candidato)
    raise CommandError(
        f"No se encontró «{nombre}». Instálalo o agrégalo al PATH "
        f"(también se buscó en {DIRECTORIO_POSTGRES})."
    )


def entorno_local():
    """Variables de entorno para conectarse a la base local de Django."""
    base = settings.DATABASES["default"]
    return _entorno(
        base.get("HOST") or "localhost",
        str(base.get("PORT") or "5432"),
        base.get("USER") or "",
        base.get("PASSWORD") or "",
        base.get("NAME") or "",
    )


def entorno_desde_url(url, sslmode="require"):
    """Variables de entorno para conectarse a partir de una URL de conexión."""
    partida = urlparse(url)
    return _entorno(
        partida.hostname or "",
        str(partida.port or 5432),
        unquote(partida.username or ""),
        unquote(partida.password or ""),
        base_de_url(url),
        sslmode=sslmode,
    )


def base_de_url(url):
    """Nombre de la base (no secreto) contenido en la cadena de conexión."""
    return (urlparse(url).path or "/postgres").lstrip("/") or "postgres"


def _entorno(anfitrion, puerto, usuario, contrasena, base, sslmode=None):
    entorno = dict(os.environ)
    entorno.update(
        {
            "PGHOST": anfitrion,
            "PGPORT": puerto,
            "PGUSER": usuario,
            "PGPASSWORD": contrasena,
            "PGDATABASE": base,
        }
    )
    if sslmode:
        entorno["PGSSLMODE"] = sslmode
    return entorno


def ejecutar(comando, env=None):
    """Ejecuta un binario sin shell y con los argumentos en una lista."""
    return subprocess.run(comando, env=env, capture_output=True, check=False)


def directorio_respaldos():
    return Path(settings.BASE_DIR) / "respaldos"


def mensaje_error(resultado):
    """Devuelve el stderr de un proceso como texto, sin datos de conexión."""
    error = resultado.stderr or b""
    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    return (error or "Error desconocido al ejecutar PostgreSQL.").strip()


def citar_identificador(nombre):
    """Cita un identificador validado; los nombres vienen del catálogo, no del usuario."""
    if not _IDENTIFICADOR_SEGURO.match(nombre):
        raise CommandError(f"Nombre de tabla inesperado: {nombre!r}")
    return '"' + nombre.replace('"', '""') + '"'


def consulta_conteos(tablas):
    partes = []
    for tabla in tablas:
        etiqueta = tabla.replace("'", "''")
        partes.append(
            f"SELECT '{etiqueta}' AS tabla, count(*) AS filas "
            f"FROM {ESQUEMA_PUBLICO}.{citar_identificador(tabla)}"
        )
    return " UNION ALL ".join(partes)


def listar_tablas_local():
    """Tablas base del esquema public, ordenadas por nombre."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename",
            [ESQUEMA_PUBLICO],
        )
        return [fila[0] for fila in cursor.fetchall()]


def contar_filas_local(tablas):
    if not tablas:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(consulta_conteos(tablas))
        return {tabla: filas for tabla, filas in cursor.fetchall()}


def contar_filas_remoto(url, tablas):
    if not tablas:
        return {}
    resultado = ejecutar(
        [buscar_binario("psql"), "-t", "-A", "-F", "|", "-c", consulta_conteos(tablas)],
        entorno_desde_url(url),
    )
    if resultado.returncode != 0:
        raise CommandError(mensaje_error(resultado))
    return _parsear_pares(resultado.stdout, convertir_filas=True)


def filas_rls_remoto(url):
    resultado = ejecutar(
        [
            buscar_binario("psql"),
            "-t",
            "-A",
            "-F",
            "|",
            "-c",
            "SELECT tablename, rowsecurity FROM pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename",
        ],
        entorno_desde_url(url),
    )
    if resultado.returncode != 0:
        raise CommandError(mensaje_error(resultado))
    filas = _parsear_pares(resultado.stdout)
    return [(tabla, valor == "t") for tabla, valor in filas.items()]


def _parsear_pares(salida, convertir_filas=False):
    valores = {}
    for linea in salida.decode("utf-8", errors="replace").splitlines():
        if "|" not in linea:
            continue
        clave, valor = linea.rsplit("|", 1)
        clave = clave.strip()
        valor = valor.strip()
        valores[clave] = int(valor) if convertir_filas else valor
    return valores


SQL_RLS = """DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format(
        'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon', r.tablename
      );
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format(
        'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM authenticated', r.tablename
      );
    END IF;
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format(
        'REVOKE ALL PRIVILEGES ON SEQUENCE public.%I FROM anon', r.sequencename
      );
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format(
        'REVOKE ALL PRIVILEGES ON SEQUENCE public.%I FROM authenticated',
        r.sequencename
      );
    END IF;
  END LOOP;
END $$;
"""


def aplicar_rls_remoto(url):
    """Activa RLS en public y revoca privilegios de anon/authenticated."""
    resultado = ejecutar(
        [buscar_binario("psql"), "-v", "ON_ERROR_STOP=1", "-c", SQL_RLS],
        entorno_desde_url(url),
    )
    if resultado.returncode != 0:
        raise CommandError(mensaje_error(resultado))
    return resultado


def podar_respaldos(directorio, maximo=RESPALDOS_A_CONSERVAR):
    """Conserva solo los ``maximo`` respaldos más recientes por nombre."""
    directorio = Path(directorio)
    archivos = sorted(directorio.glob("respaldo_*.dump"), key=lambda p: p.name, reverse=True)
    for viejo in archivos[maximo:]:
        viejo.unlink()
    return [archivo.name for archivo in archivos[:maximo]]
