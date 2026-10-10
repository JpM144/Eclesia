from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import Departamento, Municipio, Pais


class PaisTests(TestCase):
    def test_str(self):
        pais = Pais.objects.create(nombre="Colombia")
        self.assertEqual(str(pais), "Colombia")

    def test_nombre_es_unico(self):
        Pais.objects.create(nombre="Colombia")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Pais.objects.create(nombre="Colombia")


class DepartamentoTests(TestCase):
    def setUp(self):
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.ecuador = Pais.objects.create(nombre="Ecuador")

    def test_str(self):
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        self.assertEqual(str(departamento), "Cundinamarca - Colombia")

    def test_mismo_nombre_en_distinto_pais_permitido(self):
        Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        Departamento.objects.create(nombre="Cundinamarca", pais=self.ecuador)
        self.assertEqual(Departamento.objects.count(), 2)

    def test_unicidad_departamento_por_pais(self):
        Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)

    def test_protect_impide_borrar_pais_con_departamentos(self):
        Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        with self.assertRaises(ProtectedError):
            self.colombia.delete()
        self.assertTrue(Pais.objects.filter(pk=self.colombia.pk).exists())


class MunicipioTests(TestCase):
    def setUp(self):
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.cundinamarca = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        self.nariño = Departamento.objects.create(nombre="Nariño", pais=self.colombia)

    def test_str(self):
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        self.assertEqual(str(municipio), "Bogotá - Cundinamarca - Colombia")

    def test_mismo_nombre_en_distinto_departamento_permitido(self):
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        Municipio.objects.create(nombre="Bogotá", departamento=self.nariño)
        self.assertEqual(Municipio.objects.count(), 2)

    def test_unicidad_municipio_por_departamento(self):
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)

    def test_protect_impide_borrar_departamento_con_municipios(self):
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        with self.assertRaises(ProtectedError):
            self.cundinamarca.delete()
        self.assertTrue(Departamento.objects.filter(pk=self.cundinamarca.pk).exists())


# ---------------------------------------------------------------------------
# Patrón CRUD
# ---------------------------------------------------------------------------


class CrudBaseTests(TestCase):
    """Base para las pruebas de las vistas CRUD con un usuario autenticado."""

    def setUp(self):
        self.usuario = User.objects.create_user(username="tester", password="ClaveDePrueba123*")
        self.client.force_login(self.usuario)


class PaisCrudTests(CrudBaseTests):
    def test_lista_muestra_los_registros(self):
        Pais.objects.create(nombre="Colombia")
        respuesta = self.client.get(reverse("ubicacion:pais_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "crud/lista.html")
        self.assertContains(respuesta, "Colombia")

    def test_crear_pais(self):
        respuesta = self.client.post(
            reverse("ubicacion:pais_crear"), {"nombre": "Perú"}, follow=True
        )
        self.assertRedirects(respuesta, reverse("ubicacion:pais_lista"))
        self.assertTrue(Pais.objects.filter(nombre="Perú").exists())
        self.assertContains(respuesta, "Registro creado correctamente")

    def test_editar_pais(self):
        pais = Pais.objects.create(nombre="Colombia")
        respuesta = self.client.post(
            reverse("ubicacion:pais_editar", args=[pais.pk]),
            {"nombre": "Colombia Renombrada"},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:pais_lista"))
        pais.refresh_from_db()
        self.assertEqual(pais.nombre, "Colombia Renombrada")
        self.assertContains(respuesta, "Registro actualizado correctamente")

    def test_eliminar_pais(self):
        pais = Pais.objects.create(nombre="Colombia")
        respuesta = self.client.post(
            reverse("ubicacion:pais_eliminar", args=[pais.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("ubicacion:pais_lista"))
        self.assertFalse(Pais.objects.filter(pk=pais.pk).exists())
        self.assertContains(respuesta, "Registro eliminado correctamente")

    def test_formulario_de_crear_usa_la_plantilla_generica(self):
        respuesta = self.client.get(reverse("ubicacion:pais_crear"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "crud/formulario.html")

    def test_confirmacion_de_eliminar_muestra_el_nombre(self):
        pais = Pais.objects.create(nombre="Colombia")
        respuesta = self.client.get(reverse("ubicacion:pais_eliminar", args=[pais.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "crud/confirmar_eliminar.html")
        self.assertContains(respuesta, "Colombia")

    def test_eliminar_pais_con_departamentos_muestra_mensaje_y_no_lo_borra(self):
        pais = Pais.objects.create(nombre="Colombia")
        Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        respuesta = self.client.post(
            reverse("ubicacion:pais_eliminar", args=[pais.pk]), follow=True
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Pais.objects.filter(pk=pais.pk).exists())
        self.assertContains(respuesta, "No se puede eliminar porque tiene registros asociados")

    def test_buscador_filtra_paises(self):
        Pais.objects.create(nombre="Colombia")
        Pais.objects.create(nombre="Panamá")
        respuesta = self.client.get(reverse("ubicacion:pais_lista"), {"q": "pana"})
        self.assertContains(respuesta, "Panamá")
        self.assertNotContains(respuesta, "Colombia")

    def test_paginacion_muestra_20_en_la_primera_pagina(self):
        for indice in range(25):
            Pais.objects.create(nombre=f"País {indice:02d}")
        primera = self.client.get(reverse("ubicacion:pais_lista"))
        self.assertTrue(primera.context["is_paginated"])
        self.assertEqual(len(primera.context["object_list"]), 20)
        self.assertEqual(primera.context["paginator"].num_pages, 2)
        segunda = self.client.get(reverse("ubicacion:pais_lista"), {"page": 2})
        self.assertEqual(len(segunda.context["object_list"]), 5)


class DepartamentoCrudTests(CrudBaseTests):
    def setUp(self):
        super().setUp()
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.ecuador = Pais.objects.create(nombre="Ecuador")

    def test_lista_muestra_el_pais(self):
        Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        respuesta = self.client.get(reverse("ubicacion:departamento_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cundinamarca")
        self.assertContains(respuesta, "Colombia")

    def test_crear_departamento(self):
        respuesta = self.client.post(
            reverse("ubicacion:departamento_crear"),
            {"nombre": "Nariño", "pais": self.colombia.pk},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:departamento_lista"))
        self.assertTrue(Departamento.objects.filter(nombre="Nariño", pais=self.colombia).exists())
        self.assertContains(respuesta, "Registro creado correctamente")

    def test_editar_departamento(self):
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        respuesta = self.client.post(
            reverse("ubicacion:departamento_editar", args=[departamento.pk]),
            {"nombre": "Cundinamarca Renombrada", "pais": self.ecuador.pk},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:departamento_lista"))
        departamento.refresh_from_db()
        self.assertEqual(departamento.nombre, "Cundinamarca Renombrada")
        self.assertEqual(departamento.pais, self.ecuador)
        self.assertContains(respuesta, "Registro actualizado correctamente")

    def test_eliminar_departamento(self):
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        respuesta = self.client.post(
            reverse("ubicacion:departamento_eliminar", args=[departamento.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("ubicacion:departamento_lista"))
        self.assertFalse(Departamento.objects.filter(pk=departamento.pk).exists())
        self.assertContains(respuesta, "Registro eliminado correctamente")

    def test_buscador_filtra_por_pais(self):
        Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        Departamento.objects.create(nombre="Pichincha", pais=self.ecuador)
        respuesta = self.client.get(reverse("ubicacion:departamento_lista"), {"q": "ecuador"})
        self.assertContains(respuesta, "Pichincha")
        self.assertNotContains(respuesta, "Cundinamarca")


class MunicipioCrudTests(CrudBaseTests):
    def setUp(self):
        super().setUp()
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.cundinamarca = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)

    def test_lista_muestra_departamento_y_pais(self):
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        respuesta = self.client.get(reverse("ubicacion:municipio_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Bogotá")
        self.assertContains(respuesta, "Cundinamarca")
        self.assertContains(respuesta, "Colombia")

    def test_crear_municipio(self):
        respuesta = self.client.post(
            reverse("ubicacion:municipio_crear"),
            {
                "pais": self.colombia.pk,
                "departamento": self.cundinamarca.pk,
                "nombre": "Bogotá",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:municipio_lista"))
        self.assertTrue(
            Municipio.objects.filter(nombre="Bogotá", departamento=self.cundinamarca).exists()
        )
        self.assertContains(respuesta, "Registro creado correctamente")

    def test_editar_municipio(self):
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        respuesta = self.client.post(
            reverse("ubicacion:municipio_editar", args=[municipio.pk]),
            {
                "pais": self.colombia.pk,
                "departamento": self.cundinamarca.pk,
                "nombre": "Bogotá D.C.",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:municipio_lista"))
        municipio.refresh_from_db()
        self.assertEqual(municipio.nombre, "Bogotá D.C.")
        self.assertContains(respuesta, "Registro actualizado correctamente")

    def test_eliminar_municipio(self):
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        respuesta = self.client.post(
            reverse("ubicacion:municipio_eliminar", args=[municipio.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("ubicacion:municipio_lista"))
        self.assertFalse(Municipio.objects.filter(pk=municipio.pk).exists())
        self.assertContains(respuesta, "Registro eliminado correctamente")

    def test_buscador_filtra_por_departamento(self):
        nariño = Departamento.objects.create(nombre="Nariño", pais=self.colombia)
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        Municipio.objects.create(nombre="Pasto", departamento=nariño)
        respuesta = self.client.get(reverse("ubicacion:municipio_lista"), {"q": "pasto"})
        self.assertContains(respuesta, "Pasto")
        self.assertNotContains(respuesta, "Bogotá")


class MunicipioFormTests(CrudBaseTests):
    def setUp(self):
        super().setUp()
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.cundinamarca = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)

    def test_guardar_municipio_con_pais_auxiliar(self):
        respuesta = self.client.post(
            reverse("ubicacion:municipio_crear"),
            {
                "pais": self.colombia.pk,
                "departamento": self.cundinamarca.pk,
                "nombre": "Bogotá",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("ubicacion:municipio_lista"))
        municipio = Municipio.objects.get(nombre="Bogotá")
        self.assertEqual(municipio.departamento, self.cundinamarca)

    def test_precarga_el_pais_al_editar(self):
        municipio = Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        respuesta = self.client.get(reverse("ubicacion:municipio_editar", args=[municipio.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "ubicacion/municipio_form.html")
        self.assertEqual(respuesta.context["form"].fields["pais"].initial, self.colombia.pk)


class ApiUbicacionTests(CrudBaseTests):
    def setUp(self):
        super().setUp()
        self.colombia = Pais.objects.create(nombre="Colombia")
        self.ecuador = Pais.objects.create(nombre="Ecuador")
        self.cundinamarca = Departamento.objects.create(nombre="Cundinamarca", pais=self.colombia)
        self.antioquia = Departamento.objects.create(nombre="Antioquia", pais=self.colombia)
        self.pichincha = Departamento.objects.create(nombre="Pichincha", pais=self.ecuador)

    def test_api_departamentos_devuelve_solo_los_del_pais_ordenados(self):
        respuesta = self.client.get(
            reverse("ubicacion:api_departamentos"), {"pais": self.colombia.pk}
        )
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual([d["nombre"] for d in datos], ["Antioquia", "Cundinamarca"])

    def test_api_departamentos_sin_parametro_devuelve_400(self):
        respuesta = self.client.get(reverse("ubicacion:api_departamentos"))
        self.assertEqual(respuesta.status_code, 400)

    def test_api_departamentos_con_parametro_invalido_devuelve_400(self):
        respuesta = self.client.get(reverse("ubicacion:api_departamentos"), {"pais": "abc"})
        self.assertEqual(respuesta.status_code, 400)

    def test_api_municipios_devuelve_solo_los_del_departamento(self):
        Municipio.objects.create(nombre="Medellín", departamento=self.antioquia)
        Municipio.objects.create(nombre="Bogotá", departamento=self.cundinamarca)
        Municipio.objects.create(nombre="Quito", departamento=self.pichincha)
        respuesta = self.client.get(
            reverse("ubicacion:api_municipios"), {"departamento": self.cundinamarca.pk}
        )
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual([m["nombre"] for m in datos], ["Bogotá"])

    def test_api_municipios_sin_parametro_devuelve_400(self):
        respuesta = self.client.get(reverse("ubicacion:api_municipios"))
        self.assertEqual(respuesta.status_code, 400)

    def test_api_municipios_con_parametro_invalido_devuelve_400(self):
        respuesta = self.client.get(reverse("ubicacion:api_municipios"), {"departamento": "x"})
        self.assertEqual(respuesta.status_code, 400)


class LoginRequeridoTests(TestCase):
    def test_todas_las_vistas_redirigen_al_login_sin_sesion(self):
        urls = [
            reverse("ubicacion:pais_lista"),
            reverse("ubicacion:pais_crear"),
            reverse("ubicacion:departamento_lista"),
            reverse("ubicacion:municipio_lista"),
            reverse("ubicacion:api_departamentos"),
            reverse("ubicacion:api_municipios"),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta.url)
