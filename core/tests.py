import re
from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from core.choices import CargoMinisterial, TipoDocumento, TipoLibro, TipoSacramento
from parroquias.models import Folio, Libro, Ministro, Parroquia
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import Sacramento
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
        self.ministro = Ministro.objects.create(
            cedula="1234567890",
            nombre="Carlos",
            apellido="Gómez",
            cargo=CargoMinisterial.PARROCO,
        )
        self.padre = Padre.objects.create(cedula="1111111111", nombre="José", apellido="Pérez")
        self.madre = Madre.objects.create(cedula="2222222222", nombre="María", apellido="Gómez")
        self.padrino = Padrino.objects.create(nombre="Pedro López")

    def _crear_fiel(self, numero_documento, nombres="Ana María", apellidos="López Sánchez"):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento=numero_documento
        )
        return Fiel.objects.create(
            documento=documento,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=date(1990, 5, 20),
        )

    def _crear_sacramento(self, tipo, numero, fiel, fecha=date(2026, 3, 15)):
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
        )


class DashboardTests(EscenarioBase):
    def test_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get("/")
        self.assertRedirects(respuesta, f"{reverse('login')}?next=/")

    def test_dashboard_muestra_totales_correctos(self):
        fiel_ana = self._crear_fiel("1111111111")
        fiel_luis = self._crear_fiel("3333333333", nombres="Luis", apellidos="Pérez")
        self._crear_sacramento(TipoSacramento.BAUTISMO, 1, fiel_ana)
        self._crear_sacramento(TipoSacramento.BAUTISMO, 2, fiel_luis)
        self._crear_sacramento(TipoSacramento.PRIMERA_COMUNION, 3, fiel_ana)
        self._crear_sacramento(TipoSacramento.CONFIRMACION, 4, fiel_ana)
        self._crear_sacramento(TipoSacramento.MATRIMONIO, 5, None)

        self.client.force_login(self.usuario)
        respuesta = self.client.get("/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "base.html")
        self.assertTemplateUsed(respuesta, "core/dashboard.html")
        self.assertEqual(
            respuesta.context["totales"],
            {"bautismos": 2, "primeras_comuniones": 1, "confirmaciones": 1, "matrimonios": 1},
        )
        self.assertEqual(len(respuesta.context["ultimos_sacramentos"]), 5)
        self.assertContains(respuesta, "Folio 1 - Bautismos 2026")
        self.assertContains(respuesta, "Luis Pérez")
        self.assertContains(respuesta, "—")

    def test_dashboard_sin_sacramentos_muestra_ceros(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context["totales"],
            {
                "bautismos": 0,
                "primeras_comuniones": 0,
                "confirmaciones": 0,
                "matrimonios": 0,
            },
        )
        self.assertContains(respuesta, "Sin sacramentos registrados")


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

    def test_ubicacion_no_abre_el_desplegable(self):
        self.client.force_login(self.usuario)
        contenido = self._contenido(reverse("ubicacion:pais_lista"))
        self.assertNotIn("menu-open", contenido)
        self.assertEqual(self._subenlaces_activos(self._bloque_treeview(contenido)), [])

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

    def test_iglesias_marca_su_subenlace(self):
        self.client.force_login(self.usuario)
        contenido = self._contenido(reverse("parroquias:iglesia_lista"))
        self.assertIn("menu-open", contenido)
        self.assertIn('class="nav-item menu-open active"', contenido)
        self.assertIn('<a href="#" class="nav-link active">', contenido)
        self.assertEqual(self._subenlaces_activos(self._bloque_treeview(contenido)), ["Iglesias"])

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
