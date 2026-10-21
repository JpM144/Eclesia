"""Respalda la base local completa y la restaura en Supabase.

Genera un volcado en formato custom (``pg_dump --format=custom``) en
``respaldos/`` y, salvo con ``--solo-local``, lo restaura en el esquema
``public`` de Supabase con ``pg_restore --clean --if-exists --no-owner
--no-privileges``. Después activa Row Level Security en todas las tablas de
``public`` y revoca los privilegios de los roles ``anon`` y ``authenticated``;
así la API pública de Supabase no expone nada. Termina comparando el número de
filas por tabla entre la base local y Supabase y con la consulta de RLS.

La cadena de conexión (``SUPABASE_DB_URL``) y las contraseñas nunca viajan por
la línea de comandos ni por la salida del comando: van por variables de entorno
y, en los mensajes, la cadena se muestra enmascarada.

Uso:
    .\\.venv\\Scripts\\python manage.py respaldar_supabase
    .\\.venv\\Scripts\\python manage.py respaldar_supabase --solo-local
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import respaldos


class Command(BaseCommand):
    help = "Respalda la base local y la restaura en Supabase (esquema public)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--solo-local",
            action="store_true",
            help="Genera el .dump local sin subirlo a Supabase",
        )

    def handle(self, *args, **options):
        url = getattr(settings, "SUPABASE_DB_URL", "") or ""
        solo_local = options["solo_local"]
        if not solo_local and not url:
            self.stdout.write(
                self.style.ERROR(
                    "Falta SUPABASE_DB_URL en el entorno (.env). No se ha modificado nada."
                )
            )
            return

        directorio = respaldos.directorio_respaldos()
        directorio.mkdir(parents=True, exist_ok=True)
        destino = self.ruta_destino(directorio)
        self.volcar_local(destino)
        respaldos.podar_respaldos(directorio)
        self.stdout.write(self.style.SUCCESS(f"Respaldo local: {destino}"))

        if solo_local:
            self.stdout.write("Modo --solo-local: no se sube nada a Supabase.")
            return

        self.stdout.write(f"Destino Supabase: {respaldos.enmascarar_url(url)}")
        self.restaurar(destino, url)
        self.aplicar_rls(url)
        self.verificar(url)
        self.stdout.write(self.style.SUCCESS("Respaldo en Supabase completado y verificado."))

    @staticmethod
    def ruta_destino(directorio):
        marca = timezone.localtime().strftime("%Y%m%d_%H%M")
        destino = Path(directorio) / f"respaldo_{marca}.dump"
        contador = 1
        while destino.exists():
            contador += 1
            destino = Path(directorio) / f"respaldo_{marca}_{contador}.dump"
        return destino

    def volcar_local(self, destino):
        base = settings.DATABASES["default"]
        comando = [
            respaldos.buscar_binario("pg_dump"),
            "--format=custom",
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
            "-f",
            str(destino),
        ]
        resultado = respaldos.ejecutar(comando, respaldos.entorno_local())
        if resultado.returncode != 0:
            raise CommandError("pg_dump falló: " + respaldos.mensaje_error(resultado))

    def restaurar(self, dump, url):
        comando = [
            respaldos.buscar_binario("pg_restore"),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            f"--schema={respaldos.ESQUEMA_PUBLICO}",
            "-d",
            respaldos.base_de_url(url),
            str(dump),
        ]
        resultado = respaldos.ejecutar(comando, respaldos.entorno_desde_url(url))
        if resultado.returncode != 0:
            raise CommandError(
                "pg_restore falló al restaurar en Supabase: " + respaldos.mensaje_error(resultado)
            )

    def aplicar_rls(self, url):
        respaldos.aplicar_rls_remoto(url)
        self.stdout.write("RLS activo y privilegios de anon/authenticated revocados.")

    def verificar(self, url):
        tablas = respaldos.listar_tablas_local()
        locales = respaldos.contar_filas_local(tablas)
        remotas = respaldos.contar_filas_remoto(url, tablas)

        self.stdout.write("")
        self.stdout.write("Verificación de filas (local vs Supabase):")
        self.stdout.write(f"{'Tabla':<42}{'Local':>10}{'Supabase':>12}{'OK':>6}")
        todo_ok = True
        for tabla in tablas:
            local = locales.get(tabla)
            remoto = remotas.get(tabla)
            ok = local == remoto
            todo_ok = todo_ok and ok
            remoto_texto = remoto if remoto is not None else "N/D"
            estado = "OK" if ok else "ERROR"
            self.stdout.write(f"{tabla:<42}{local:>10}{remoto_texto:>12}{estado:>6}")

        self.stdout.write("")
        self.stdout.write("RLS en Supabase (pg_tables.rowsecurity):")
        rls = respaldos.filas_rls_remoto(url)
        for tabla, activo in rls:
            self.stdout.write(f"{tabla:<42}{'RLS' if activo else 'SIN RLS':>10}")
        rls_ok = all(activo for _, activo in rls)

        if not todo_ok:
            raise CommandError("Las filas no coinciden entre la base local y Supabase.")
        if not rls_ok:
            raise CommandError("Hay tablas del esquema public sin RLS en Supabase.")
