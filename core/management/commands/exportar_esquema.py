"""Exporta la estructura de la base de datos para versionarla en Git.

Genera ``docs/base_de_datos/esquema.sql`` con la estructura de la base local
(``pg_dump --schema-only --no-owner --no-privileges``) y
``docs/base_de_datos/tablas.md`` con las tablas, sus columnas, tipos,
nulabilidad, llaves primarias y foráneas, agrupadas por aplicación de Django.
No incluye datos de filas.

La contraseña se pasa al proceso por la variable de entorno ``PGPASSWORD``,
nunca por la línea de comandos.

Uso:
    .\\.venv\\Scripts\\python manage.py exportar_esquema
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from core import respaldos


def directorio_salida():
    return Path(settings.BASE_DIR) / "docs" / "base_de_datos"


class Command(BaseCommand):
    help = "Genera docs/base_de_datos/esquema.sql y docs/base_de_datos/tablas.md"

    def handle(self, *args, **options):
        directorio = directorio_salida()
        directorio.mkdir(parents=True, exist_ok=True)
        self.exportar_esquema(directorio / "esquema.sql")
        self.exportar_tablas(directorio / "tablas.md")
        self.stdout.write(self.style.SUCCESS(f"Esquema exportado en {directorio}"))

    def exportar_esquema(self, destino):
        base = settings.DATABASES["default"]
        comando = [
            respaldos.buscar_binario("pg_dump"),
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "-h",
            str(base.get("HOST") or "localhost"),
            "-p",
            str(base.get("PORT") or "5432"),
            "-U",
            str(base.get("USER") or ""),
            "-d",
            str(base.get("NAME") or ""),
        ]
        resultado = respaldos.ejecutar(comando, respaldos.entorno_local())
        if resultado.returncode != 0:
            raise CommandError("pg_dump falló: " + respaldos.mensaje_error(resultado))
        fecha = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S %Z")
        encabezado = (
            "-- Estructura de la base de datos del Sistema de Gestión Parroquial.\n"
            f"-- Fecha de generación: {fecha}\n"
            "-- Generado con python manage.py exportar_esquema; no editar a mano.\n"
            "\n"
        )
        contenido = encabezado + resultado.stdout.decode("utf-8", errors="replace")
        destino.write_text(contenido, encoding="utf-8", newline="\n")

    def exportar_tablas(self, destino):
        columnas = self.columnas()
        primarias = self.llaves_primarias()
        foraneas = self.llaves_foraneas()
        grupos = self.agrupar(columnas)
        fecha = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S %Z")
        lineas = [
            "# Tablas de la base de datos",
            "",
            f"Fecha de generación: {fecha}.",
            "",
            "Generado con `python manage.py exportar_esquema; no editar a mano`.",
            "",
            f"Total: {len(columnas)} tablas.",
            "",
        ]
        for etiqueta in sorted(grupos):
            lineas.append(f"## {etiqueta}")
            lineas.append("")
            for tabla in sorted(grupos[etiqueta]):
                lineas.append(f"### `{tabla}`")
                lineas.append("")
                lineas.append("| Columna | Tipo | Nulo | PK | FK |")
                lineas.append("| --- | --- | --- | --- | --- |")
                for columna in grupos[etiqueta][tabla]:
                    nombre = columna["columna"]
                    clave = (tabla, nombre)
                    es_pk = "Sí" if clave in primarias else ""
                    referencia = foraneas.get(clave)
                    fk = f"{referencia[0]}.{referencia[1]}" if referencia else ""
                    lineas.append(
                        f"| {nombre} | {columna['tipo']} | "
                        f"{'Sí' if columna['nulo'] else 'No'} | {es_pk} | {fk} |"
                    )
                lineas.append("")
        destino.write_text("\n".join(lineas), encoding="utf-8", newline="\n")

    def columnas(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
                """,
                [respaldos.ESQUEMA_PUBLICO],
            )
            columnas = {}
            for tabla, nombre, tipo, nulo, largo, precision, escala in cursor.fetchall():
                columnas.setdefault(tabla, []).append(
                    {
                        "columna": nombre,
                        "tipo": self.tipo(tipo, largo, precision, escala),
                        "nulo": nulo == "YES",
                    }
                )
            return columnas

    @staticmethod
    def tipo(tipo, largo, precision, escala):
        if largo is not None:
            return f"{tipo}({largo})"
        if precision is not None and escala is not None:
            return f"{tipo}({precision},{escala})"
        return tipo

    def llaves_primarias(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                WHERE tc.table_schema = %s
                  AND tc.constraint_type = 'PRIMARY KEY'
                """,
                [respaldos.ESQUEMA_PUBLICO],
            )
            return {(tabla, columna) for tabla, columna in cursor.fetchall()}

    def llaves_foraneas(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT kcu.table_name, kcu.column_name,
                       ccu.table_name AS tabla_ref, ccu.column_name AS col_ref
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema = %s
                  AND tc.constraint_type = 'FOREIGN KEY'
                """,
                [respaldos.ESQUEMA_PUBLICO],
            )
            return {(tabla, columna): (ref, col) for tabla, columna, ref, col in cursor.fetchall()}

    def agrupar(self, columnas):
        etiquetas = self.etiquetas_apps()
        grupos = {}
        for tabla in columnas:
            etiqueta = etiquetas.get(tabla)
            if etiqueta is None:
                prefijo = tabla.split("_", 1)[0]
                etiqueta = etiquetas.get(f"__prefijo__{prefijo}", "Otros")
            grupos.setdefault(etiqueta, {})[tabla] = columnas[tabla]
        return grupos

    @staticmethod
    def etiquetas_apps():
        etiquetas = {}
        for modelo in apps.get_models():
            app = apps.get_app_config(modelo._meta.app_label)
            etiquetas[modelo._meta.db_table] = f"`{app.label}` — {app.verbose_name}"
        etiquetas["django_migrations"] = "`django` — infraestructura interna"
        for config in apps.get_app_configs():
            etiquetas[f"__prefijo__{config.label}"] = f"`{config.label}` — {config.verbose_name}"
        return etiquetas
