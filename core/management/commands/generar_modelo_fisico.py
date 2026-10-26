"""Genera el documento del modelo físico de la base de datos (PDF y HTML).

Produce ``docs/base_de_datos/modelo_fisico.pdf`` y
``docs/base_de_datos/modelo_fisico.html`` con portada, información general,
diagrama entidad-relación físico (Mermaid), diccionario de datos de las tablas
propias, lista de las tablas internas de Django y, como anexo, el DDL de las
tablas propias sacado de ``pg_dump --schema-only``.

La estructura se lee del catálogo de PostgreSQL (``information_schema`` y
``pg_catalog``); nunca se leen filas de datos. Con ``--origen supabase`` (por
defecto) la conexión a ``SUPABASE_DB_URL`` es de solo lectura y la cadena de
conexión solo aparece enmascarada; con ``--origen local`` se usa la base del
proyecto.

Uso:
    .\\.venv\\Scripts\\python manage.py generar_modelo_fisico
    .\\.venv\\Scripts\\python manage.py generar_modelo_fisico --origen local
    .\\.venv\\Scripts\\python manage.py generar_modelo_fisico --asignatura "Bases de datos" \\
        --profesor "Nombre del profesor"
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.formats import date_format

from core import modelo_fisico, respaldos

AUTOR = "Juan José Mier Rincón — Código 0192253"
NOMBRE_HTML = "modelo_fisico.html"
NOMBRE_PDF = "modelo_fisico.pdf"


def directorio_salida():
    return Path(settings.BASE_DIR) / "docs" / "base_de_datos"


class Command(BaseCommand):
    help = "Genera docs/base_de_datos/modelo_fisico.pdf y modelo_fisico.html"

    def add_arguments(self, parser):
        parser.add_argument(
            "--origen",
            choices=["supabase", "local"],
            default="supabase",
            help="Base de la que se lee el esquema public (por defecto, supabase)",
        )
        parser.add_argument("--asignatura", default="", help="Asignatura para la portada")
        parser.add_argument("--profesor", default="", help="Profesor para la portada")

    def handle(self, *args, **options):
        origen = options["origen"]
        url = ""
        if origen == "supabase":
            url = getattr(settings, "SUPABASE_DB_URL", "") or ""
            if not url:
                raise CommandError(
                    "Falta SUPABASE_DB_URL en el entorno (.env). Configúrala o usa "
                    "--origen local para leer la base del proyecto."
                )
            self.stdout.write(f"Leyendo el esquema de Supabase: {respaldos.enmascarar_url(url)}")
            consultor = modelo_fisico.consultor_supabase(url)
        else:
            self.stdout.write("Leyendo el esquema de la base local.")
            consultor = modelo_fisico.consultor_local()

        with consultor as consultar:
            version, tablas = modelo_fisico.leer_catalogo(consultar)
        modelo_fisico.aplicar_modelos(tablas)
        propias, django, otras = modelo_fisico.clasificar(tablas)
        if not propias:
            raise CommandError("El esquema public no tiene tablas propias del sistema.")

        ddl = modelo_fisico.obtener_ddl([tabla.nombre for tabla in propias], url or None)
        contexto = self.contexto(origen, version, propias, django, otras, ddl, options)
        html = render_to_string("modelo_fisico/documento.html", contexto)

        directorio = directorio_salida()
        directorio.mkdir(parents=True, exist_ok=True)
        resultado = modelo_fisico.renderizar(
            html, directorio / NOMBRE_HTML, directorio / NOMBRE_PDF
        )

        self.stdout.write(f"Tablas propias: {len(propias)}; tablas de Django: {len(django)}.")
        for figura in resultado.get("diagramas", []):
            self.stdout.write(
                f"Diagrama {figura['id']}: página {figura['orientacion']}, "
                f"dirección {figura['direccion']}, escala {figura['escala']:.2f} "
                f"(letra de {figura['letra_pt']:.1f} pt)"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Modelo físico generado en {directorio} ({resultado.get('paginas', 0)} páginas)."
            )
        )

    @staticmethod
    def contexto(origen, version, propias, django, otras, ddl, options):
        with translation.override("es"):
            fecha = date_format(timezone.localdate(), r"j \d\e F \d\e Y")
        modulos = modelo_fisico.modulos_con_tablas(propias)
        resumen = [
            {
                "titulo": modulo["titulo"],
                "tablas": len(modulo["tablas"]),
                "columnas": sum(len(t.columnas) for t in modulo["tablas"]),
                "foraneas": sum(1 for t in modulo["tablas"] for c in t.columnas if c.fk),
                "indices": sum(len(t.indices) for t in modulo["tablas"]),
            }
            for modulo in modulos
        ]
        return {
            "autor": AUTOR,
            "fecha": fecha,
            "asignatura": (options.get("asignatura") or "").strip(),
            "profesor": (options.get("profesor") or "").strip(),
            "origen": origen,
            "version": version,
            "propias": propias,
            "django": [
                {
                    "nombre": t.nombre,
                    "descripcion": modelo_fisico.DESCRIPCIONES_DJANGO.get(t.nombre),
                }
                for t in django
            ],
            "otras": otras,
            "modulos": modulos,
            "resumen": resumen,
            "total_columnas": sum(r["columnas"] for r in resumen),
            "total_foraneas": sum(r["foraneas"] for r in resumen),
            "total_indices": sum(r["indices"] for r in resumen),
            "diagramas": modelo_fisico.diagramas(propias),
            "foraneas_django": modelo_fisico.foraneas_a_django(propias),
            "ddl": ddl,
        }
