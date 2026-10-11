import json
import re
from datetime import date, datetime, timedelta

from django.contrib.auth.models import AnonymousUser, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.choices import (
    AccionHistorial,
    CargoMinisterial,
    EstadoAnotacion,
    EstadoRegistro,
    RolUsuario,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoLibro,
    TipoSacramento,
)
from core.services import resumen_dashboard
from core.templatetags.dashboard_extras import fecha_relativa
from core.templatetags.interfaz_extras import iniciales
from cuentas.models import PerfilUsuario
from parroquias.models import Folio, Libro, Ministro, Parroquia
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import AnotacionMarginal, HistorialSacramento, Sacramento
from ubicacion.models import Departamento, Municipio, Pais


class ConexionBaseDeDatosTests(TestCase):
    def test_conexion_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")


class EscenarioBase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="prueba", password="ClaveDePrueba123*")
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver",
            municipio=municipio,
            direccion="Calle 1 # 2-34",
        )
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        self.folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        self._documento_ministro = self._crear_documento("1234567890")
        self.ministro = Ministro.objects.create(
            documento=self._documento_ministro,
            nombre="Carlos",
            apellido="Gómez",
            cargo=CargoMinisterial.PARROCO,
        )
        self.padre = Padre.objects.create(
            documento=self._crear_documento("1111111111"), nombre="José", apellido="Pérez"
        )
        self.madre = Madre.objects.create(
            documento=self._crear_documento("2222222222"), nombre="María", apellido="Gómez"
        )
        self.padrino = Padrino.objects.create(
            documento=self._crear_documento("3333333333"), nombre="Pedro López"
        )

    def _crear_documento(self, numero_documento, tipo_documento=TipoDocumento.CC):
        documento, _ = Documento.objects.get_or_create(
            tipo_documento=tipo_documento, numero_documento=numero_documento
        )
        return documento

    def _crear_fiel(self, numero_documento, nombres="Ana María", apellidos="López Sánchez"):
        documento = self._crear_documento(numero_documento)
        return Fiel.objects.create(
            documento=documento,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=date(1990, 5, 20),
        )

    def _fiel(self):
        if not hasattr(self, "_fiel_cache"):
            self._fiel_cache = self._crear_fiel("5555555555")
        return self._fiel_cache

    def _crear_sacramento(self, tipo, numero, fiel, fecha=date(2026, 3, 15), estado=None):
        return Sacramento.objects.create(
            tipo=tipo,
            fiel=fiel,
            libro=self.libro,
            folio=self.folio,
            numero=numero,
            fecha=fecha,
            fecha_registro=fecha,
            parroquia=self.parroquia,
            ministro=self.ministro,
            estado=estado or EstadoRegistro.ACTIVO,
        )


class DashboardResumenTests(EscenarioBase):
    """Lógica del resumen: totales, serie mensual y variaciones."""

    HOY = date(2026, 6, 15)

    def _bautismo(self, numero, fecha, estado=None):
        return self._crear_sacramento(TipoSacramento.BAUTISMO, numero, self._fiel(), fecha, estado)

    def test_totales_por_tipo_excluye_anulados(self):
        self._bautismo(1, date(2026, 6, 10))
        self._bautismo(2, date(2026, 6, 11), EstadoRegistro.ANULADO)
        self._crear_sacramento(TipoSacramento.PRIMERA_COMUNION, 3, self._fiel(), date(2026, 6, 12))
        self._crear_sacramento(TipoSacramento.MATRIMONIO, 4, None, date(2026, 6, 13))
        resumen = resumen_dashboard(hoy=self.HOY)
        self.assertEqual(
            resumen["totales"],
            {"bautismos": 1, "primeras_comuniones": 1, "confirmaciones": 0, "matrimonios": 1},
        )

    def test_variacion_sube(self):
        for numero in (1, 2):
            self._bautismo(numero, date(2026, 5, 10))
        for numero in (3, 4, 5):
            self._bautismo(numero, date(2026, 6, 10))
        variacion = resumen_dashboard(hoy=self.HOY)["variaciones"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(variacion, {"valor": "+50%", "direccion": "sube"})

    def test_variacion_baja(self):
        for numero in range(1, 5):
            self._bautismo(numero, date(2026, 5, 10))
        self._bautismo(5, date(2026, 6, 10))
        variacion = resumen_dashboard(hoy=self.HOY)["variaciones"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(variacion, {"valor": "-75%", "direccion": "baja"})

    def test_variacion_igual(self):
        for numero in (1, 2):
            self._bautismo(numero, date(2026, 5, 10))
        for numero in (3, 4):
            self._bautismo(numero, date(2026, 6, 10))
        variacion = resumen_dashboard(hoy=self.HOY)["variaciones"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(variacion, {"valor": "0%", "direccion": "igual"})

    def test_variacion_mes_anterior_cero_es_nuevo(self):
        self._bautismo(1, date(2026, 6, 10))
        variacion = resumen_dashboard(hoy=self.HOY)["variaciones"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(variacion, {"valor": "Nuevo", "direccion": "sube"})

    def test_variacion_meses_sin_registros_es_sin_cambios(self):
        variacion = resumen_dashboard(hoy=self.HOY)["variaciones"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(variacion, {"valor": "Sin cambios", "direccion": "igual"})

    def test_serie_tiene_doce_meses_y_rellena_con_ceros(self):
        self._bautismo(1, date(2025, 8, 10))
        self._bautismo(2, date(2026, 6, 10))
        resumen = resumen_dashboard(hoy=self.HOY)
        serie = resumen["series"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(len(serie), 12)
        self.assertEqual(len(resumen["etiquetas"]), 12)
        self.assertEqual(serie[0], 0)
        self.assertEqual(serie[1], 1)
        self.assertEqual(serie[-1], 1)
        self.assertEqual(sum(serie), 2)

    def test_serie_excluye_anulados(self):
        self._bautismo(1, date(2026, 6, 10))
        self._bautismo(2, date(2026, 6, 11), EstadoRegistro.ANULADO)
        serie = resumen_dashboard(hoy=self.HOY)["series"][TipoSacramento.BAUTISMO.value]
        self.assertEqual(serie[-1], 1)


class DashboardVistaTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        respuesta = self.client.get("/")
        self.assertRedirects(respuesta, f"{reverse('login')}?next=/")

    def test_plantilla_del_dashboard(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "base.html")
        self.assertTemplateUsed(respuesta, "core/dashboard.html")

    def test_datos_del_grafico_van_con_json_script(self):
        self._crear_sacramento(TipoSacramento.BAUTISMO, 1, self._fiel(), fecha=timezone.localdate())
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, '<script id="datos-grafico" type="application/json">')
        coincidencia = re.search(
            r'<script id="datos-grafico" type="application/json">(.*?)</script>',
            respuesta.content.decode(),
            re.S,
        )
        self.assertIsNotNone(coincidencia)
        datos = json.loads(coincidencia.group(1))
        self.assertEqual(len(datos["etiquetas"]), 12)
        self.assertEqual(datos["series"][TipoSacramento.BAUTISMO.value][-1], 1)

    def test_ultimas_actividades_cinco_mas_recientes(self):
        acciones = (
            AccionHistorial.CREACION,
            AccionHistorial.MODIFICACION,
            AccionHistorial.ANULACION,
            AccionHistorial.CORRECCION,
            AccionHistorial.ARCHIVADO,
        )
        for indice, accion in enumerate(acciones, start=1):
            sacramento = self._crear_sacramento(TipoSacramento.BAUTISMO, indice, self._fiel())
            HistorialSacramento.objects.create(
                sacramento=sacramento, accion=accion, usuario=self.usuario
            )
        sacramento_matrimonio = self._crear_sacramento(TipoSacramento.MATRIMONIO, 6, None)
        HistorialSacramento.objects.create(
            sacramento=sacramento_matrimonio,
            accion=AccionHistorial.CREACION,
            usuario=self.usuario,
        )
        respuesta = self.client.get(reverse("dashboard"))
        actividades = respuesta.context["actividades"]
        self.assertEqual(len(actividades), 5)
        self.assertTrue(actividades[0]["texto"].startswith("Matrimonio"))
        self.assertNotIn(
            "Bautismo creado por prueba",
            [actividad["texto"] for actividad in actividades],
        )
        self.assertContains(respuesta, "Matrimonio creado por prueba")

    def test_ultimas_actividades_sin_registros_muestra_mensaje(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.context["actividades"], [])
        self.assertContains(respuesta, "Aún no hay actividad registrada")

    def test_acceso_rapido(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "Crear Bautismo")
        self.assertContains(respuesta, "Disponible pronto")
        self.assertIn('boton-acceso--azul" disabled', respuesta.content.decode())
        self.assertContains(respuesta, f'href="{reverse("parroquias:libro_lista")}"')
        self.assertContains(respuesta, f'href="{reverse("personas:consultar")}"')

    def test_encabezado_con_cita(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "Bienvenido al")
        self.assertContains(respuesta, "Sistema de Gestión Parroquial")
        self.assertContains(respuesta, "Colosenses 3:23")


class DashboardCampanaTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_sin_anotaciones_pendientes_no_muestra_badge(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.context["anotaciones_pendientes_total"], 0)
        self.assertNotIn('class="badge badge-warning navbar-badge"', respuesta.content.decode())
        self.assertContains(respuesta, "Sin anotaciones pendientes")

    def test_con_anotaciones_pendientes_muestra_badge_y_lista(self):
        sacramento = self._crear_sacramento(TipoSacramento.BAUTISMO, 1, self._fiel())
        AnotacionMarginal.objects.create(
            sacramento=sacramento,
            tipo=TipoAnotacionMarginal.CONFIRMACION,
            descripcion="Confirmación para anotar",
            fecha=date(2026, 1, 1),
            parroquia_destino_texto="Parroquia San Juan",
            estado=EstadoAnotacion.POR_COMUNICAR,
        )
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.context["anotaciones_pendientes_total"], 1)
        self.assertEqual(len(respuesta.context["anotaciones_pendientes_recientes"]), 1)
        self.assertIn('class="badge badge-warning navbar-badge"', respuesta.content.decode())
        self.assertContains(respuesta, "Comunicar confirmación a")
        self.assertContains(respuesta, "Parroquia San Juan")


class DashboardConteoConsultasTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _crear_escenario(self, cantidad, offset=0):
        for indice in range(cantidad):
            sacramento = self._crear_sacramento(
                TipoSacramento.BAUTISMO, offset + indice + 1, self._fiel()
            )
            HistorialSacramento.objects.create(
                sacramento=sacramento,
                accion=AccionHistorial.CREACION,
                usuario=self.usuario,
            )

    def _consultar(self):
        with CaptureQueriesContext(connection) as captura:
            respuesta = self.client.get(reverse("dashboard"))
            self.assertEqual(respuesta.status_code, 200)
        return len(captura.captured_queries)

    def test_numero_de_consultas_constante_entre_dos_tamanos(self):
        self._crear_escenario(2)
        pequeno = self._consultar()
        self._crear_escenario(8, offset=100)
        grande = self._consultar()
        self.assertEqual(pequeno, grande)


class FechaRelativaTests(TestCase):
    def test_hoy_y_ayer(self):
        ahora = timezone.localtime(timezone.now())
        self.assertTrue(fecha_relativa(ahora).startswith("Hoy, "))
        self.assertTrue(fecha_relativa(ahora - timedelta(days=1)).startswith("Ayer, "))

    def test_fecha_completa(self):
        valor = timezone.make_aware(datetime(2026, 3, 3, 15, 5))
        self.assertEqual(fecha_relativa(valor), "3 de marzo de 2026")

    def test_vacio(self):
        self.assertEqual(fecha_relativa(None), "")


class LoginTests(EscenarioBase):
    def test_login_con_credenciales_correctas_redirige_a_inicio(self):
        respuesta = self.client.post(
            reverse("login"),
            {"username": "prueba", "password": "ClaveDePrueba123*"},
        )
        self.assertRedirects(respuesta, reverse("dashboard"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_con_credenciales_erroneas_muestra_el_error(self):
        respuesta = self.client.post(
            reverse("login"),
            {"username": "prueba", "password": "clave incorrecta"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "registration/login.html")
        self.assertTrue(respuesta.context["form"].errors)
        self.assertContains(respuesta, "alert-danger")

    def test_get_a_login_esta_permitido_sin_sesion(self):
        respuesta = self.client.get(reverse("login"))
        self.assertEqual(respuesta.status_code, 200)

    def test_logout_por_post_cierra_la_sesion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("logout"))
        self.assertRedirects(respuesta, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_a_logout_no_cierra_la_sesion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("logout"))
        self.assertEqual(respuesta.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class SidebarTreeviewTests(EscenarioBase):
    """El desplegable "Parroquias" reúne los catálogos del sistema."""

    ETIQUETAS = ["Parroquias", "Ministros", "Libros"]
    AJENAS = ["Países", "Departamentos", "Municipios"]

    def _contenido(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    @staticmethod
    def _bloque_treeview(contenido):
        coincidencia = re.search(r'<ul class="nav nav-treeview">(.*?)</ul>', contenido, re.S)
        return coincidencia.group(1) if coincidencia else ""

    @staticmethod
    def _bloques_treeview(contenido):
        return re.findall(r'<ul class="nav nav-treeview">(.*?)</ul>', contenido, re.S)

    @staticmethod
    def _subenlaces_activos(bloque):
        etiquetas = []
        for clases, etiqueta in re.findall(
            r'<a[^>]*class="([^"]*)"[^>]*>\s*<i class="far fa-circle[^"]*"></i>\s*<p>([^<]+)</p>',
            bloque,
        ):
            if "active" in clases.split():
                etiquetas.append(etiqueta)
        return etiquetas

    def test_estructura_del_treeview(self):
        self.client.force_login(self.usuario)
        contenido = self._contenido(reverse("dashboard"))
        self.assertIn('data-widget="treeview"', contenido)
        self.assertIn('data-accordion="false"', contenido)
        self.assertIn('class="nav nav-treeview"', contenido)
        self.assertIn('class="right fas fa-angle-left"', contenido)

    def test_inicio_no_abre_el_desplegable(self):
        self.client.force_login(self.usuario)
        self.assertNotIn("menu-open", self._contenido(reverse("dashboard")))

    def test_ubicacion_abre_y_marca_sus_enlaces(self):
        self.client.force_login(self.usuario)
        casos = [
            (reverse("ubicacion:pais_lista"), "Países"),
            (reverse("ubicacion:departamento_lista"), "Departamentos"),
            (reverse("ubicacion:municipio_lista"), "Municipios"),
        ]
        for url, esperado in casos:
            with self.subTest(url=url):
                contenido = self._contenido(url)
                self.assertIn("menu-open", contenido)
                self.assertIn('class="nav-item menu-open active"', contenido)
                self.assertIn('<a href="#" class="nav-link active">', contenido)
                bloques = self._bloques_treeview(contenido)
                activos = [
                    etiqueta for bloque in bloques for etiqueta in self._subenlaces_activos(bloque)
                ]
                self.assertEqual(activos, [esperado])
                self.assertNotIn("Catálogos", contenido)

    def test_paginas_propias_abren_y_marcan_el_subenlace(self):
        self.client.force_login(self.usuario)
        casos = [
            (reverse("parroquias:parroquia_lista"), "Parroquias"),
            (reverse("parroquias:ministro_lista"), "Ministros"),
            (reverse("parroquias:libro_lista"), "Libros"),
            (reverse("parroquias:folio_lista", args=[self.folio.libro_id]), "Libros"),
        ]
        for url, esperado in casos:
            with self.subTest(url=url):
                contenido = self._contenido(url)
                self.assertIn("menu-open", contenido)
                self.assertIn('class="nav-item menu-open active"', contenido)
                self.assertIn('<a href="#" class="nav-link active">', contenido)
                self.assertEqual(
                    self._subenlaces_activos(self._bloque_treeview(contenido)), [esperado]
                )

    @staticmethod
    def _clases_del_enlace(contenido, url):
        coincidencia = re.search(r'<a href="' + re.escape(url) + r'" class="([^"]*)"', contenido)
        return coincidencia.group(1).split() if coincidencia else []

    def test_consultar_personas_es_item_propio_y_activo_al_editar(self):
        self.client.force_login(self.usuario)
        consultar = reverse("personas:consultar")
        casos = [
            consultar,
            reverse("personas:padre_editar", args=[self.padre.pk]),
        ]
        for url in casos:
            with self.subTest(url=url):
                contenido = self._contenido(url)
                self.assertNotIn("menu-open", contenido)
                self.assertIn("active", self._clases_del_enlace(contenido, consultar))

    def test_subenlaces_dentro_del_treeview_y_ubicacion_fuera(self):
        self.client.force_login(self.usuario)
        bloque = self._bloque_treeview(self._contenido(reverse("dashboard")))
        self.assertTrue(bloque, "No se encontró el <ul class='nav nav-treeview'>")
        for etiqueta in self.ETIQUETAS:
            with self.subTest(etiqueta=etiqueta):
                self.assertIn(f"<p>{etiqueta}</p>", bloque)
        for etiqueta in self.AJENAS:
            with self.subTest(etiqueta=etiqueta):
                self.assertNotIn(etiqueta, bloque)


class BarraSuperiorTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _contenido(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_boton_pushmenu_con_aria_label(self):
        contenido = self._contenido(reverse("dashboard"))
        self.assertIn('data-widget="pushmenu"', contenido)
        self.assertIn('aria-label="Mostrar u ocultar el menú"', contenido)
        self.assertIn("fa-bars", contenido)

    def test_titulo_de_pagina_aparece_en_la_barra(self):
        self.assertContains(
            self.client.get(reverse("dashboard")),
            '<span class="titulo-pagina">Inicio</span>',
        )
        self.assertContains(
            self.client.get(reverse("ubicacion:pais_lista")),
            '<span class="titulo-pagina">Países</span>',
        )


class MenuUsuarioTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.usuario.first_name = "Ana"
        self.usuario.last_name = "Pérez"
        self.usuario.save()
        self.client.force_login(self.usuario)

    def _contenido(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_avatar_con_iniciales_nombre_y_rol(self):
        contenido = self._contenido()
        self.assertIn('<span class="usuario-avatar" aria-hidden="true">AP</span>', contenido)
        self.assertIn("Hola, Ana", contenido)
        self.assertIn("Ana Pérez", contenido)
        self.assertIn("Administrador", contenido)

    def test_formulario_post_de_cierre_de_sesion(self):
        contenido = self._contenido()
        self.assertIn(f'action="{reverse("logout")}"', contenido)
        self.assertIn('method="post"', contenido)
        self.assertIn("Cerrar sesión", contenido)
        self.assertIn("csrfmiddlewaretoken", contenido)

    def test_en_movil_el_nombre_se_oculta(self):
        contenido = self._contenido()
        self.assertIn('<span class="d-none d-md-inline ml-2">', contenido)

    def test_muestra_el_rol_del_perfil(self):
        PerfilUsuario.objects.create(usuario=self.usuario, rol=RolUsuario.SACERDOTE)
        contenido = self._contenido()
        self.assertIn("Sacerdote", contenido)

    def test_iniciales_del_filtro(self):
        self.assertEqual(iniciales(self.usuario), "AP")
        self.usuario.last_name = ""
        self.usuario.save()
        self.assertEqual(iniciales(self.usuario), "AN")
        self.assertEqual(iniciales(AnonymousUser()), "")
        self.assertEqual(iniciales(None), "")


class MenuLateralSacramentosTests(EscenarioBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        self.contenido = self._contenido(reverse("parroquias:parroquia_lista"))

    def _contenido(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_primera_comunion_entre_bautismos_y_confirmaciones(self):
        etiquetas = ["Bautismos", "Primera Comunión", "Confirmaciones", "Matrimonios"]
        posiciones = [self.contenido.index(f"<p>{etiqueta} <span") for etiqueta in etiquetas]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_items_de_sacramentos_atenuados_sin_href_con_pronto(self):
        self.assertEqual(
            self.contenido.count('<a class="nav-link deshabilitado" aria-disabled="true">'),
            4,
        )
        self.assertEqual(self.contenido.count('class="etiqueta-pronto"'), 4)
        self.assertNotIn('<a href="#" class="nav-link deshabilitado"', self.contenido)

    def test_items_de_sacramentos_usan_iconos_svg(self):
        self.assertEqual(self.contenido.count('class="nav-icon icono-menu"'), 4)
        self.assertNotIn("fas fa-water", self.contenido)
        self.assertNotIn("fas fa-dove", self.contenido)
        self.assertNotIn("fas fa-ring", self.contenido)
        self.assertNotIn("Catálogos", self.contenido)
