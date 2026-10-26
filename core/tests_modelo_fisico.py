"""Tests del comando generar_modelo_fisico (sin Supabase real ni Chromium).

El renderizado con Playwright y pg_dump se simulan: se comprueba el HTML que
arma el comando a partir del catálogo de la base de pruebas.
"""

import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core import modelo_fisico
from personas.models import Documento, Fiel

URL_SUPABASE_PRUEBA = (
    "postgresql://postgres.usuariosecreto_x:ClaveSecretaXYZ123"
    "@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
)
DDL_FALSO = (
    b"--\n-- PostgreSQL database dump\n--\nSET statement_timeout = 0;\n"
    b"\\restrict abc\n\nCREATE TABLE public.ubicacion_pais (\n    id bigint NOT NULL\n);\n"
)


def renderizar_falso(html, destino_html, destino_pdf):
    Path(destino_html).write_text(html, encoding="utf-8")
    Path(destino_pdf).write_bytes(b"%PDF-falso")
    return {"paginas": 0, "diagramas": []}


def tablas_propias_de_modelos():
    return {
        modelo._meta.db_table
        for modelo in apps.get_models()
        if modelo._meta.db_table.startswith(modelo_fisico.PREFIJOS_PROPIOS)
    }


class GenerarModeloFisicoLocalTests(TestCase):
    def generar(self, **opciones):
        with tempfile.TemporaryDirectory() as temporal:
            with (
                mock.patch(
                    "core.management.commands.generar_modelo_fisico.directorio_salida",
                    return_value=Path(temporal),
                ),
                mock.patch("core.modelo_fisico.renderizar", side_effect=renderizar_falso),
                mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
                mock.patch(
                    "core.respaldos.ejecutar",
                    side_effect=lambda comando, env=None: subprocess.CompletedProcess(
                        comando, 0, DDL_FALSO, b""
                    ),
                ),
            ):
                call_command(
                    "generar_modelo_fisico", origen="local", stdout=mock.Mock(), **opciones
                )
            return (Path(temporal) / "modelo_fisico.html").read_text(encoding="utf-8")

    def test_genera_html_con_las_secciones_esperadas(self):
        html = self.generar()
        for texto in (
            "Modelo físico de la base de datos",
            "Sistema de Gestión Parroquial",
            "Juan José Mier Rincón — Código 0192253",
            "1. Información general",
            "2. Diagrama entidad-relación físico",
            "3. Diccionario de datos",
            "4. Tablas internas de Django",
            "5. Anexo: DDL de las tablas propias",
            "Convenciones de nombres",
        ):
            self.assertIn(texto, html)
        self.assertIn("CREATE TABLE public.ubicacion_pais", html)
        self.assertNotIn("SET statement_timeout", html)

    def test_diccionario_incluye_todas_las_tablas_propias_y_ningun_dato(self):
        documento = Documento.objects.create(tipo_documento="CC", numero_documento="9990123456")
        Fiel.objects.create(
            documento=documento,
            nombres="Zacarías Prueba",
            apellidos="Datosreales",
            fecha_nacimiento=date(1990, 1, 1),
        )
        Documento.objects.create(tipo_documento="CC", numero_documento="9991765432")
        html = self.generar()
        for tabla in tablas_propias_de_modelos():
            self.assertIn(f'id="t-{tabla.replace("_", "-")}"', html, tabla)
        for dato in ("9990", "9991", "Zacarías", "Datosreales"):
            self.assertNotIn(dato, html)

    def test_las_tablas_de_django_no_aparecen_en_el_diagrama(self):
        html = self.generar()
        diagramas = re.findall(r'<div class="mermaid">(.*?)</div>', html, re.S)
        self.assertTrue(diagramas)
        for codigo in diagramas:
            self.assertNotRegex(codigo, r"\b(auth|django)_")
        self.assertIn("auth_user", html)  # sí aparece en la sección 4

    def test_portada_sin_asignatura_ni_profesor(self):
        html = self.generar()
        self.assertNotIn("Asignatura", html)
        self.assertNotIn("Profesor", html)
        self.assertNotIn("____", html)

    def test_portada_con_asignatura_y_profesor(self):
        html = self.generar(asignatura="Bases de Datos II", profesor="Docente <Prueba>")
        self.assertIn('<dd class="asignatura">Bases de Datos II</dd>', html)
        self.assertIn("Docente &lt;Prueba&gt;", html)


class GenerarModeloFisicoSupabaseTests(TestCase):
    @override_settings(SUPABASE_DB_URL="")
    def test_sin_url_sale_con_mensaje_claro(self):
        with mock.patch("core.modelo_fisico.renderizar") as renderizar:
            with self.assertRaisesMessage(CommandError, "Falta SUPABASE_DB_URL"):
                call_command("generar_modelo_fisico", origen="supabase", stdout=mock.Mock())
            renderizar.assert_not_called()

    def test_error_de_conexion_no_muestra_credenciales(self):
        import psycopg

        error = psycopg.OperationalError(
            'password authentication failed for user "postgres.usuariosecreto_x" '
            "(ClaveSecretaXYZ123)"
        )
        with mock.patch("psycopg.connect", side_effect=error):
            with self.assertRaises(CommandError) as contexto:
                with modelo_fisico.consultor_supabase(URL_SUPABASE_PRUEBA):
                    pass
        mensaje = str(contexto.exception)
        self.assertNotIn("ClaveSecretaXYZ123", mensaje)
        self.assertNotIn("usuariosecreto_x", mensaje)
        self.assertIn("postgres.***@", mensaje)

    def test_pg_dump_remoto_es_de_solo_lectura_y_sin_credenciales_en_argumentos(self):
        with (
            mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
            mock.patch(
                "core.respaldos.ejecutar",
                side_effect=lambda comando, env=None: subprocess.CompletedProcess(
                    comando, 0, DDL_FALSO, b""
                ),
            ) as ejecutar,
        ):
            ddl = modelo_fisico.obtener_ddl(["ubicacion_pais"], URL_SUPABASE_PRUEBA)
        comando, entorno = ejecutar.call_args.args
        argumentos = " ".join(comando)
        self.assertIn("--schema-only", comando)
        self.assertIn("public.ubicacion_pais", comando)
        self.assertNotIn("ClaveSecretaXYZ123", argumentos)
        self.assertNotIn(URL_SUPABASE_PRUEBA, argumentos)
        self.assertEqual(entorno["PGOPTIONS"], "-c default_transaction_read_only=on")
        self.assertTrue(ddl.startswith("CREATE TABLE public.ubicacion_pais"))


class UtilidadesModeloFisicoTests(TestCase):
    def test_paginas_de_destinos_lee_el_arbol_de_paginas(self):
        pdf = (
            b"1 0 obj\n<</Type /Catalog /Pages 2 0 R /Dests 9 0 R>>\nendobj\n"
            b"2 0 obj\n<</Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3>>\nendobj\n"
            b"3 0 obj\n<</Type /Page /Parent 2 0 R>>\nendobj\n"
            b"4 0 obj\n<</Type /Page /Parent 2 0 R>>\nendobj\n"
            b"5 0 obj\n<</Type /Page /Parent 2 0 R>>\nendobj\n"
            b"9 0 obj\n<</s-general [4 0 R /XYZ 6 776 0]\n/t-personas-fiel [5 0 R /XYZ 6 7 0]>>"
            b"\nendobj\n"
        )
        self.assertEqual(
            modelo_fisico.paginas_de_destinos(pdf), {"s-general": 2, "t-personas-fiel": 3}
        )
        self.assertEqual(modelo_fisico.paginas_de_destinos(b"no es un pdf"), {})

    def test_cardinalidad_segun_nulos_y_unicidad(self):
        columna = modelo_fisico.Columna("fiel_id", "bigint", nulo=False, defecto="")
        self.assertEqual(modelo_fisico.cardinalidad(columna), "||--o{")
        columna.nulo, columna.unica = True, True
        self.assertEqual(modelo_fisico.cardinalidad(columna), "|o--o|")

    def test_filtrar_ddl_quita_ruido_y_junta_sentencias_cortas(self):
        texto = (
            "--\n-- Name: x\n--\nSET lock_timeout = 0;\n\\restrict k\n\n"
            "CREATE TABLE public.a (\n    id bigint\n);\n\n"
            "ALTER TABLE public.a ENABLE ROW LEVEL SECURITY;\n\n"
            "ALTER TABLE public.b ENABLE ROW LEVEL SECURITY;\n\n\n"
            "CREATE INDEX i ON public.a USING btree (id);\n"
        )
        self.assertEqual(
            modelo_fisico.filtrar_ddl(texto),
            "CREATE TABLE public.a (\n    id bigint\n);\n\n"
            "ALTER TABLE public.a ENABLE ROW LEVEL SECURITY;\n"
            "ALTER TABLE public.b ENABLE ROW LEVEL SECURITY;\n"
            "CREATE INDEX i ON public.a USING btree (id);\n",
        )

    def test_tipo_corto_para_mermaid(self):
        self.assertEqual(modelo_fisico.tipo_corto("character varying(255)"), "varchar(255)")
        self.assertEqual(modelo_fisico.tipo_corto("timestamp with time zone"), "timestamptz")
