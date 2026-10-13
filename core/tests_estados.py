"""Pruebas de los estados de interfaz: vacío, carga y error.

`tests_urls.py` provee una URL mínima que lanza PermissionDenied para
comprobar la página 403 personalizada.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.views.defaults import server_error

from core.choices import TipoLibro, TipoSacramento
from core.tests import EscenarioBase
from parroquias.models import Libro, Parroquia
from ubicacion.models import Departamento, Municipio, Pais


class ListaEstadoVacioTests(TestCase):
    """Las listas sin datos muestran el parcial de estado vacío."""

    def setUp(self):
        self.usuario = User.objects.create_user(username="estados", password="ClaveDePrueba123*")
        self.client.force_login(self.usuario)

    def test_listas_vacias_muestran_el_estado_vacio_con_su_boton(self):
        casos = [
            (
                reverse("parroquias:parroquia_lista"),
                "Aún no hay parroquias registradas",
                reverse("parroquias:parroquia_crear"),
            ),
            (
                reverse("parroquias:ministro_lista"),
                "Aún no hay ministros registrados",
                reverse("parroquias:ministro_crear"),
            ),
            (
                reverse("parroquias:libro_lista"),
                "Aún no hay libros registrados",
                reverse("parroquias:libro_crear"),
            ),
            (
                reverse("ubicacion:pais_lista"),
                "Aún no hay países registrados",
                reverse("ubicacion:pais_crear"),
            ),
            (
                reverse("ubicacion:departamento_lista"),
                "Aún no hay departamentos registrados",
                reverse("ubicacion:departamento_crear"),
            ),
            (
                reverse("ubicacion:municipio_lista"),
                "Aún no hay municipios registrados",
                reverse("ubicacion:municipio_crear"),
            ),
        ]
        for url, titulo, url_crear in casos:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, "includes/estado_vacio.html")
                self.assertContains(respuesta, 'class="estado-vacio"')
                self.assertContains(respuesta, titulo)
                self.assertContains(respuesta, f'href="{url_crear}"')

    def test_lista_de_folios_vacia_usa_el_boton_anidado_del_libro(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        parroquia = Parroquia.objects.create(nombre="San Pedro", municipio=municipio)
        libro = Libro.objects.create(
            nombre="Bautismos",
            tipo_libro=TipoLibro.BAUTISMOS,
            fecha_apertura=date(2026, 1, 1),
            parroquia=parroquia,
        )
        url = reverse("parroquias:folio_lista", args=[libro.pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este libro todavía no tiene folios")
        url_crear = reverse("parroquias:folio_crear", args=[libro.pk])
        self.assertContains(respuesta, f'href="{url_crear}"')

    def test_lista_vacia_por_filtro_muestra_texto_y_enlace_para_limpiar(self):
        Pais.objects.create(nombre="Colombia")
        url = reverse("ubicacion:pais_lista")
        respuesta = self.client.get(url, {"q": "zzz"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No hay resultados con estos filtros")
        self.assertContains(respuesta, "Limpiar filtros")
        self.assertContains(respuesta, f'href="{url}" class="btn btn-tema btn-sm vacio-boton"')

    def test_lista_con_datos_no_muestra_el_estado_vacio(self):
        Pais.objects.create(nombre="Colombia")
        respuesta = self.client.get(reverse("ubicacion:pais_lista"))
        self.assertNotContains(respuesta, "Aún no hay países registrados")
        self.assertContains(respuesta, "Colombia")

    def test_indice_de_libro_sin_partidas_muestra_estado_vacio(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        parroquia = Parroquia.objects.create(nombre="San Pedro", municipio=municipio)
        libro = Libro.objects.create(
            nombre="Bautismos",
            tipo_libro=TipoLibro.BAUTISMOS,
            fecha_apertura=date(2026, 1, 1),
            parroquia=parroquia,
        )
        respuesta = self.client.get(reverse("parroquias:libro_indice", args=[libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este libro todavía no tiene partidas")
        self.assertContains(respuesta, "table-responsive")


class DashboardEstadoVacioTests(EscenarioBase):
    """El dashboard usa el parcial y controla el esqueleto de la gráfica."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_actividades_usan_el_parcial_de_estado_vacio(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertTemplateUsed(respuesta, "includes/estado_vacio.html")
        self.assertContains(respuesta, "Aún no hay actividad registrada")
        self.assertContains(respuesta, 'class="estado-vacio"')

    def test_sin_partidas_muestra_estado_vacio_de_la_grafica(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "Todavía no hay partidas registradas para graficar")
        self.assertNotContains(respuesta, "<canvas")
        self.assertNotContains(respuesta, "esqueleto-grafico")

    def test_con_partidas_muestra_canvas_y_esqueleto(self):
        self._crear_sacramento(TipoSacramento.BAUTISMO, 1, self._fiel(), fecha=timezone.localdate())
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "<canvas")
        self.assertContains(respuesta, "esqueleto-grafico")
        self.assertNotContains(respuesta, "Todavía no hay partidas registradas para graficar")


class EvitarDobleEnvioTests(EscenarioBase):
    """Los formularios relevantes quedan protegidos contra el doble envío."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_base_carga_formularios_js(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "js/formularios.js")

    def test_formularios_llevan_el_atributo(self):
        pais = Pais.objects.first()
        urls = [
            reverse("ubicacion:pais_crear"),
            reverse("ubicacion:pais_editar", args=[pais.pk]),
            reverse("ubicacion:pais_eliminar", args=[pais.pk]),
            reverse("parroquias:libro_cerrar", args=[self.libro.pk]),
            reverse("personas:padre_editar", args=[self.padre.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "data-evitar-doble-envio")

    @override_settings(CODIGO_REGISTRO="CLAVE-DE-PRUEBA")
    def test_formulario_de_registro_lleva_el_atributo(self):
        self.client.logout()
        respuesta = self.client.get(reverse("cuentas:registro"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-evitar-doble-envio")
        self.assertContains(respuesta, "js/formularios.js")


class PaginasErrorTests(TestCase):
    """Páginas 403, 404 y 500 personalizadas."""

    def setUp(self):
        self.usuario = User.objects.create_user(username="errores", password="ClaveDePrueba123*")
        self.client.force_login(self.usuario)

    @override_settings(DEBUG=False)
    def test_404_personalizada(self):
        respuesta = self.client.get("/ruta-que-no-existe-12345/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTemplateUsed(respuesta, "404.html")
        self.assertContains(respuesta, "Página no encontrada", status_code=404)
        self.assertContains(respuesta, "Volver al inicio", status_code=404)

    @override_settings(DEBUG=False, ROOT_URLCONF="core.tests_urls")
    def test_403_personalizada(self):
        respuesta = self.client.get("/prohibido/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, "403.html")
        self.assertContains(respuesta, "Acceso denegado", status_code=403)
        self.assertContains(respuesta, "Volver al inicio", status_code=403)

    def test_500_se_renderiza_sin_consultas(self):
        peticion = RequestFactory().get("/")
        with self.assertNumQueries(0):
            respuesta = server_error(peticion)
        self.assertEqual(respuesta.status_code, 500)
        self.assertContains(respuesta, "Algo salió mal", status_code=500)
        self.assertContains(respuesta, "Volver al inicio", status_code=500)
