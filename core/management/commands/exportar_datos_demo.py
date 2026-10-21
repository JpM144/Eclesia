"""Exporta los datos de demostración para versionarlos con el esquema.

Genera ``docs/base_de_datos/datos_demo.json`` con los registros que crea
``cargar_datos_demo`` (documentos con prefijo ``9990`` y todo lo que cuelga de
ellos). Nunca incluye usuarios reales, contraseñas ni sesiones, de modo que el
archivo se puede subir a Git sin datos personales.

Uso:
    .\\.venv\\Scripts\\python manage.py exportar_datos_demo
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.management.commands.cargar_datos_demo import PREFIJO_DOCUMENTO
from parroquias.models import Folio, Libro, Ministro, Parroquia
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    HistorialSacramento,
    Matrimonio,
    PrimeraComunion,
    ProclamaMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)
from ubicacion.models import Departamento, Municipio, Pais


def directorio_salida():
    return Path(settings.BASE_DIR) / "docs" / "base_de_datos"


def recolectar_datos_demo():
    """Devuelve la lista de objetos de demostración en orden de dependencia."""
    documentos = Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO)
    if not documentos.exists():
        return []

    ministros = Ministro.objects.filter(documento__in=documentos)
    parroquias = Parroquia.objects.filter(pk__in=ministros.values_list("parroquia_id", flat=True))
    libros = Libro.objects.filter(parroquia__in=parroquias)
    folios = Folio.objects.filter(libro__in=libros)
    sacramentos = Sacramento.objects.filter(Q(parroquia__in=parroquias) | Q(libro__in=libros))
    fieles = Fiel.objects.filter(documento__in=documentos)
    padres = Padre.objects.filter(documento__in=documentos)
    madres = Madre.objects.filter(documento__in=documentos)
    padrinos = Padrino.objects.filter(documento__in=documentos)
    bautismos = Bautismo.objects.filter(sacramento__in=sacramentos)
    primeras = PrimeraComunion.objects.filter(sacramento__in=sacramentos)
    confirmaciones = Confirmacion.objects.filter(sacramento__in=sacramentos)
    matrimonios = Matrimonio.objects.filter(sacramento__in=sacramentos)
    contrayentes = Contrayente.objects.filter(matrimonio__in=matrimonios)
    testigos = TestigoMatrimonio.objects.filter(matrimonio__in=matrimonios)
    proclamas = ProclamaMatrimonio.objects.filter(matrimonio__in=matrimonios)
    anotaciones = AnotacionMarginal.objects.filter(
        Q(sacramento__in=sacramentos) | Q(sacramento_origen__in=sacramentos)
    )
    historial = HistorialSacramento.objects.filter(sacramento__in=sacramentos)

    ids_municipio = set(parroquias.values_list("municipio_id", flat=True))
    ids_municipio |= set(fieles.values_list("municipio_nacimiento_id", flat=True))
    ids_municipio |= set(primeras.values_list("municipio_bautismo_id", flat=True))
    ids_municipio |= set(confirmaciones.values_list("municipio_bautismo_id", flat=True))
    ids_municipio.discard(None)
    municipios = Municipio.objects.filter(pk__in=ids_municipio)
    departamentos = Departamento.objects.filter(
        pk__in=municipios.values_list("departamento_id", flat=True)
    )
    paises = Pais.objects.filter(pk__in=departamentos.values_list("pais_id", flat=True))

    return [
        *paises,
        *departamentos,
        *municipios,
        *documentos,
        *fieles,
        *padres,
        *madres,
        *padrinos,
        *ministros,
        *parroquias,
        *libros,
        *folios,
        *sacramentos,
        *bautismos,
        *primeras,
        *confirmaciones,
        *matrimonios,
        *contrayentes,
        *testigos,
        *proclamas,
        *anotaciones,
        *historial,
    ]


class Command(BaseCommand):
    help = "Exporta los datos de demostración a docs/base_de_datos/datos_demo.json"

    def handle(self, *args, **options):
        objetos = recolectar_datos_demo()
        if not objetos:
            raise CommandError(
                "No hay datos de demostración en la base; ejecuta "
                "«python manage.py cargar_datos_demo» antes de exportar."
            )
        destino = directorio_salida() / "datos_demo.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        contenido = serializers.serialize("json", objetos, indent=2)
        destino.write_text(contenido, encoding="utf-8", newline="\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"Datos de demostración exportados en {destino} ({len(objetos)} registros)"
            )
        )
