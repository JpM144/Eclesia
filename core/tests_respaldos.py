"""Tests de los comandos de exportación y respaldo (sin tocar Supabase real).

Los tests simulan los procesos de PostgreSQL con ``subprocess`` mockeado, de
modo que se comprueba la forma de las llamadas (argumentos y entorno) sin
conectarse a Supabase ni ejecutar los binarios.
"""

import io
import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core import respaldos
from core.respaldos import enmascarar_url, podar_respaldos

URL_SUPABASE_PRUEBA = (
    "postgresql://postgres.usuariosecreto_x:ClaveSecretaXYZ123"
    "@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
)


def resultado(comando, returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(comando, returncode, stdout, stderr)


def binario_en_llamada(llamada):
    comando = llamada.args[0]
    return Path(str(comando[0])).name


class EnmascararUrlTests(TestCase):
    def test_oculta_usuario_y_contrasena(self):
        enmascarada = enmascarar_url(URL_SUPABASE_PRUEBA)
        self.assertNotIn("usuariosecreto_x", enmascarada)
        self.assertNotIn("ClaveSecretaXYZ123", enmascarada)
        self.assertIn("postgres.***@", enmascarada)
        self.assertIn("aws-0-us-east-1.pooler.supabase.com:5432", enmascarada)
        self.assertTrue(enmascarada.endswith("/postgres"))


class RespaldarSupabaseTests(TestCase):
    @override_settings(SUPABASE_DB_URL="")
    def test_sin_url_sale_sin_llamar_pg_dump(self):
        salida = io.StringIO()
        with mock.patch("core.respaldos.ejecutar") as ejecutar:
            call_command("respaldar_supabase", stdout=salida)
            ejecutar.assert_not_called()
        self.assertIn("SUPABASE_DB_URL", salida.getvalue())

    def test_solo_local_llama_pg_dump_y_no_pg_restore(self):
        with tempfile.TemporaryDirectory() as temporal:
            with (
                mock.patch("core.respaldos.directorio_respaldos", return_value=Path(temporal)),
                mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
                mock.patch(
                    "core.respaldos.ejecutar",
                    side_effect=lambda comando, env=None: resultado(comando),
                ) as ejecutar,
            ):
                call_command("respaldar_supabase", solo_local=True)
        binarios = {binario_en_llamada(llamada) for llamada in ejecutar.call_args_list}
        self.assertIn("pg_dump", binarios)
        self.assertNotIn("pg_restore", binarios)

    @override_settings(SUPABASE_DB_URL=URL_SUPABASE_PRUEBA)
    def test_conserva_solo_los_ultimos_siete_respaldos(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            for dia in range(1, 11):
                (carpeta / f"respaldo_202601{dia:02d}_0101.dump").write_bytes(b"x")
            with (
                mock.patch("core.respaldos.directorio_respaldos", return_value=carpeta),
                mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
                mock.patch(
                    "core.respaldos.ejecutar",
                    side_effect=lambda comando, env=None: resultado(comando),
                ),
            ):
                call_command("respaldar_supabase", solo_local=True)
            archivos = sorted(p.name for p in carpeta.glob("respaldo_*.dump"))
        self.assertEqual(len(archivos), 7)
        self.assertNotIn("respaldo_20260101_0101.dump", archivos)
        self.assertIn("respaldo_20260110_0101.dump", archivos)

    @override_settings(SUPABASE_DB_URL=URL_SUPABASE_PRUEBA)
    def test_password_no_aparece_en_argumentos_ni_en_la_salida(self):
        tablas = ["auth_group", "personas_fiel"]
        conteos = {"auth_group": 3, "personas_fiel": 5}
        salida = io.StringIO()
        with tempfile.TemporaryDirectory() as temporal:
            with (
                mock.patch("core.respaldos.directorio_respaldos", return_value=Path(temporal)),
                mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
                mock.patch(
                    "core.respaldos.ejecutar",
                    side_effect=lambda comando, env=None: resultado(comando),
                ) as ejecutar,
                mock.patch("core.respaldos.listar_tablas_local", return_value=tablas),
                mock.patch("core.respaldos.contar_filas_local", return_value=conteos),
                mock.patch("core.respaldos.contar_filas_remoto", return_value=conteos),
                mock.patch(
                    "core.respaldos.filas_rls_remoto",
                    return_value=[(t, True) for t in tablas],
                ),
            ):
                call_command("respaldar_supabase", stdout=salida)

        argumentos = " ".join(
            " ".join(str(parte) for parte in llamada.args[0]) for llamada in ejecutar.call_args_list
        )
        self.assertNotIn("ClaveSecretaXYZ123", argumentos)
        self.assertNotIn("ClaveSecretaXYZ123", salida.getvalue())
        self.assertNotIn(URL_SUPABASE_PRUEBA, argumentos)
        binarios = {binario_en_llamada(llamada) for llamada in ejecutar.call_args_list}
        self.assertIn("pg_dump", binarios)
        self.assertIn("pg_restore", binarios)
        self.assertIn("postgres.***@", salida.getvalue())


class PodarRespaldosTests(TestCase):
    def test_conserva_los_ultimos_siete(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            for dia in range(1, 11):
                (carpeta / f"respaldo_202601{dia:02d}_0101.dump").write_bytes(b"x")
            conservados = podar_respaldos(carpeta, maximo=7)
            restantes = sorted(p.name for p in carpeta.glob("respaldo_*.dump"))
        self.assertEqual(len(conservados), 7)
        self.assertEqual(restantes, sorted(conservados))
        self.assertNotIn("respaldo_20260101_0101.dump", restantes)


class ExportarEsquemaTests(TestCase):
    def test_escribe_el_encabezado_esperado(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            with (
                mock.patch(
                    "core.management.commands.exportar_esquema.directorio_salida",
                    return_value=carpeta,
                ),
                mock.patch("core.respaldos.buscar_binario", side_effect=lambda n: n),
                mock.patch(
                    "core.respaldos.ejecutar",
                    side_effect=lambda comando, env=None: resultado(
                        comando, stdout=b"-- contenido de prueba\n"
                    ),
                ),
            ):
                call_command("exportar_esquema")
            contenido = (carpeta / "esquema.sql").read_text(encoding="utf-8")
            tablas = (carpeta / "tablas.md").read_text(encoding="utf-8")
        self.assertIn("Fecha de generación", contenido)
        self.assertIn("Generado con python manage.py exportar_esquema; no editar a mano", contenido)
        self.assertIn("-- contenido de prueba", contenido)
        self.assertIn("Generado con `python manage.py exportar_esquema; no editar a mano`", tablas)
        self.assertIn("password", tablas)


class ExportarDatosDemoTests(TestCase):
    @override_settings(DEBUG=True)
    def test_datos_demo_sin_documentos_fuera_de_9990_ni_hashes(self):
        call_command("cargar_datos_demo")
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            with mock.patch(
                "core.management.commands.exportar_datos_demo.directorio_salida",
                return_value=carpeta,
            ):
                call_command("exportar_datos_demo")
            datos = json.loads((carpeta / "datos_demo.json").read_text(encoding="utf-8"))

        self.assertTrue(datos)
        modelos = {registro["model"] for registro in datos}
        self.assertIn("personas.fiel", modelos)
        self.assertNotIn("auth.user", modelos)
        self.assertNotIn("sessions.session", modelos)

        documentos = [registro for registro in datos if registro["model"] == "personas.documento"]
        self.assertTrue(documentos)
        for registro in documentos:
            numero = registro["fields"]["numero_documento"]
            self.assertTrue(numero.startswith("9990"), numero)

        for registro in datos:
            for campo, valor in registro["fields"].items():
                self.assertNotEqual(campo, "password")
                if isinstance(valor, str):
                    self.assertNotIn("pbkdf2_sha256", valor)
                    self.assertNotIn("pbkdf2_", valor)

    @override_settings(DEBUG=True)
    def test_sin_datos_demo_falla_con_mensaje(self):
        with tempfile.TemporaryDirectory() as temporal:
            with mock.patch(
                "core.management.commands.exportar_datos_demo.directorio_salida",
                return_value=Path(temporal),
            ):
                with self.assertRaises(CommandError):
                    call_command("exportar_datos_demo")


class RespaldosHelpersTests(TestCase):
    def test_citar_identificador_rechaza_nombres_peligrosos(self):
        with self.assertRaises(CommandError):
            respaldos.citar_identificador("tabla; DROP TABLE x")

    def test_entorno_desde_url_no_expone_en_argumentos(self):
        entorno = respaldos.entorno_desde_url(URL_SUPABASE_PRUEBA)
        self.assertEqual(entorno["PGUSER"], "postgres.usuariosecreto_x")
        self.assertEqual(entorno["PGPASSWORD"], "ClaveSecretaXYZ123")
        self.assertEqual(entorno["PGHOST"], "aws-0-us-east-1.pooler.supabase.com")
        self.assertEqual(entorno["PGDATABASE"], "postgres")
