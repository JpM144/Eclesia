from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.choices import CargoMinisterial, EstadoLibro, TipoDocumento, TipoLibro, TipoSacramento
from personas.models import Documento, Fiel
from sacramentos.models import Sacramento
from ubicacion.models import Departamento, Municipio, Pais

from .models import Folio, Libro, Ministro, Parroquia


class BaseParroquiasTests(TestCase):
    def setUp(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver",
            municipio=self.municipio,
            direccion="Calle 1 # 2-34",
            telefono="6012345678",
            email="contacto@sanpedro.co",
        )

    def _crear_ministro(self, documento=None, numero_documento="1234567890", **kwargs):
        if documento is None:
            documento, _ = Documento.objects.get_or_create(
                tipo_documento=TipoDocumento.CC, numero_documento=numero_documento
            )
        datos = {
            "documento": documento,
            "nombre": "Carlos",
            "apellido": "Gómez",
            "cargo": CargoMinisterial.PARROCO,
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Ministro.objects.create(**datos)


class ParroquiaTests(BaseParroquiasTests):
    def test_str(self):
        self.assertEqual(str(self.parroquia), "San Pedro Claver")

    def test_nombre_unico(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Parroquia.objects.create(
                    nombre="San Pedro Claver",
                    municipio=self.municipio,
                    direccion="Otra dirección",
                )

    def test_borrar_parroquia_no_borra_ministro(self):
        ministro = self._crear_ministro()
        self.parroquia.delete()
        ministro.refresh_from_db()
        self.assertIsNone(ministro.parroquia)
        self.assertTrue(Ministro.objects.filter(pk=ministro.pk).exists())

    def test_borrar_ministro_parroco_deja_parroco_en_null(self):
        ministro = self._crear_ministro()
        self.parroquia.parroco = ministro
        self.parroquia.save()
        ministro.delete()
        self.parroquia.refresh_from_db()
        self.assertIsNone(self.parroquia.parroco)

    def test_referencia_circular(self):
        ministro = self._crear_ministro()
        self.parroquia.parroco = ministro
        self.parroquia.save()
        ministro.refresh_from_db()
        self.assertEqual(ministro.parroquia, self.parroquia)
        self.assertEqual(self.parroquia.parroco, ministro)
        self.assertEqual(str(ministro), "Carlos Gómez - Párroco")

    def test_protect_impide_borrar_municipio_con_parroquias(self):
        with self.assertRaises(ProtectedError):
            self.municipio.delete()
        self.assertTrue(Parroquia.objects.filter(pk=self.parroquia.pk).exists())


class MinistroTests(BaseParroquiasTests):
    def test_str_con_apellido(self):
        ministro = self._crear_ministro()
        self.assertEqual(str(ministro), "Carlos Gómez - Párroco")

    def test_str_sin_apellido(self):
        ministro = self._crear_ministro(apellido="")
        self.assertEqual(str(ministro), "Carlos  - Párroco")

    def test_documento_unico(self):
        self._crear_ministro()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_ministro(nombre="Otro", apellido="Diferente")

    def test_protect_impide_borrar_documento_con_ministro(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="987654321"
        )
        ministro = self._crear_ministro(documento=documento)
        with self.assertRaises(ProtectedError):
            documento.delete()
        self.assertTrue(Ministro.objects.filter(pk=ministro.pk).exists())


class LibroTests(BaseParroquiasTests):
    def _crear_libro(self, **kwargs):
        datos = {
            "nombre": "Bautismos 2026",
            "tipo_libro": TipoLibro.BAUTISMOS,
            "detalle": "Registro de bautismos",
            "fecha_apertura": date(2026, 1, 1),
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Libro.objects.create(**datos)

    def test_str(self):
        libro = self._crear_libro(numero_libro=1)
        self.assertEqual(str(libro), "Bautismos 2026")

    def test_nombre_unico_por_parroquia(self):
        self._crear_libro()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_libro(detalle="Otro registro")

    def test_mismo_nombre_en_otra_parroquia_permitido(self):
        self._crear_libro()
        otra_parroquia = Parroquia.objects.create(
            nombre="Otra Parroquia", municipio=self.municipio, direccion="Otra"
        )
        self._crear_libro(parroquia=otra_parroquia)
        self.assertEqual(Libro.objects.filter(nombre="Bautismos 2026").count(), 2)

    def test_unicidad_parroquia_tipo_numero(self):
        self._crear_libro(numero_libro=1, estado=EstadoLibro.CERRADO, fecha_cierre=date(2026, 6, 1))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_libro(nombre="Bautismos 2027", numero_libro=1, detalle="Registro")

    def test_numero_nulo_no_es_unico(self):
        self._crear_libro(
            nombre="Bautismos A",
            numero_libro=None,
            estado=EstadoLibro.CERRADO,
            fecha_cierre=date(2026, 6, 1),
        )
        self._crear_libro(nombre="Bautismos B", numero_libro=None)
        self.assertEqual(Libro.objects.filter(numero_libro__isnull=True).count(), 2)

    def test_protect_impide_borrar_parroquia_con_libros(self):
        libro = self._crear_libro()
        with self.assertRaises(ProtectedError):
            self.parroquia.delete()
        self.assertTrue(Libro.objects.filter(pk=libro.pk).exists())


class FolioTests(BaseParroquiasTests):
    def setUp(self):
        super().setUp()
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            numero_libro=1,
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )

    def test_str(self):
        folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        self.assertEqual(str(folio), "Folio 1 - Bautismos 2026")

    def test_unicidad_folio_por_libro(self):
        Folio.objects.create(libro=self.libro, numero_folio=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Folio.objects.create(libro=self.libro, numero_folio=1)

    def test_mismo_numero_en_otro_libro_permitido(self):
        otro_libro = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        Folio.objects.create(libro=self.libro, numero_folio=1)
        Folio.objects.create(libro=otro_libro, numero_folio=1)
        self.assertEqual(Folio.objects.count(), 2)

    def test_protect_impide_borrar_libro_con_folios(self):
        folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        with self.assertRaises(ProtectedError):
            self.libro.delete()
        self.assertTrue(Folio.objects.filter(pk=folio.pk).exists())


class LibroReglasTests(BaseParroquiasTests):
    """Regla 3 y cierre: un solo libro abierto por tipo y diligencias de cierre."""

    def _crear_libro(self, **kwargs):
        datos = {
            "nombre": "Bautismos 2026",
            "tipo_libro": TipoLibro.BAUTISMOS,
            "detalle": "Registro de bautismos",
            "fecha_apertura": date(2026, 1, 1),
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Libro.objects.create(**datos)

    def test_estado_por_defecto_abierto(self):
        libro = self._crear_libro()
        self.assertEqual(libro.estado, EstadoLibro.ABIERTO)

    def test_cerrado_sin_fecha_de_cierre_falla(self):
        self._crear_libro()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_libro(
                    nombre="Bautismos 2026 B",
                    estado=EstadoLibro.CERRADO,
                    fecha_cierre=None,
                )

    def test_cierre_anterior_a_la_apertura_falla(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_libro(
                    nombre="Bautismos 2026 B",
                    estado=EstadoLibro.CERRADO,
                    fecha_cierre=date(2025, 12, 31),
                )

    def test_dos_abiertos_del_mismo_tipo_en_la_misma_parroquia_fallan(self):
        self._crear_libro()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_libro(nombre="Bautismos 2027", detalle="Otro registro")

    def test_abierto_y_cerrado_del_mismo_tipo_se_permiten(self):
        self._crear_libro()
        self._crear_libro(
            nombre="Bautismos 2025",
            fecha_apertura=date(2025, 1, 1),
            estado=EstadoLibro.CERRADO,
            fecha_cierre=date(2025, 12, 31),
        )
        self.assertEqual(Libro.objects.filter(parroquia=self.parroquia).count(), 2)

    def test_mismo_tipo_abierto_en_otra_parroquia_se_permite(self):
        self._crear_libro()
        otra_parroquia = Parroquia.objects.create(
            nombre="Otra Parroquia", municipio=self.municipio, direccion="Otra"
        )
        self._crear_libro(parroquia=otra_parroquia, nombre="Bautismos de Otra")
        self.assertEqual(Libro.objects.filter(tipo_libro=TipoLibro.BAUTISMOS).count(), 2)


class FolioTotalFoliosTests(BaseParroquiasTests):
    """Los folios respetan el total declarado en la apertura del libro."""

    def setUp(self):
        super().setUp()
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            fecha_apertura=date(2026, 1, 1),
            total_folios=10,
            parroquia=self.parroquia,
        )

    def test_folio_dentro_del_total_pasa(self):
        folio = Folio(libro=self.libro, numero_folio=10)
        folio.full_clean()
        folio.save()
        self.assertTrue(Folio.objects.filter(libro=self.libro, numero_folio=10).exists())

    def test_folio_fuera_del_total_falla(self):
        folio = Folio(libro=self.libro, numero_folio=11)
        with self.assertRaises(ValidationError) as contexto:
            folio.full_clean()
        self.assertIn("numero_folio", contexto.exception.message_dict)

    def test_sin_total_declarado_no_limita(self):
        libro = Libro.objects.create(
            nombre="Confirmaciones 2026",
            tipo_libro=TipoLibro.CONFIRMACIONES,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        folio = Folio(libro=libro, numero_folio=500)
        folio.full_clean()
        folio.save()
        self.assertTrue(Folio.objects.filter(libro=libro, numero_folio=500).exists())


# ---------------------------------------------------------------------------
# Patrón CRUD
# ---------------------------------------------------------------------------


class CrudParroquiasBaseTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="tester", password="ClaveDePrueba123*")
        self.client.force_login(self.usuario)
        pais = Pais.objects.create(nombre="Colombia")
        self.departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=self.departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver",
            municipio=self.municipio,
            direccion="Calle 1 # 2-34",
        )

    def _crear_ministro(self, documento=None, numero_documento="1234567890", **kwargs):
        if documento is None:
            documento, _ = Documento.objects.get_or_create(
                tipo_documento=TipoDocumento.CC, numero_documento=numero_documento
            )
        datos = {
            "documento": documento,
            "nombre": "Carlos",
            "apellido": "Gómez",
            "cargo": CargoMinisterial.PARROCO,
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Ministro.objects.create(**datos)

    def _crear_fiel(self, numero_documento="1111111111", nombres="Ana", apellidos="López"):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento=numero_documento
        )
        return Fiel.objects.create(
            documento=documento,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=date(1990, 1, 1),
        )

    def _crear_partida(self, libro, numero=1, fiel=None):
        folio, _ = Folio.objects.get_or_create(libro=libro, numero_folio=1)
        if fiel is None:
            fiel = self._crear_fiel(numero_documento=f"DOC{numero}")
        return Sacramento.objects.create(
            tipo=TipoSacramento.BAUTISMO,
            fiel=fiel,
            libro=libro,
            folio=folio,
            numero=numero,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2026, 3, 15),
            parroquia=self.parroquia,
        )


class ParroquiaCrudTests(CrudParroquiasBaseTests):
    def test_lista_muestra_las_parroquias(self):
        respuesta = self.client.get(reverse("parroquias:parroquia_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "crud/lista.html")
        self.assertContains(respuesta, "San Pedro Claver")
        self.assertContains(respuesta, "Bogotá")

    def test_crear_parroquia_con_selects_encadenados(self):
        respuesta = self.client.post(
            reverse("parroquias:parroquia_crear"),
            {
                "nombre": "Sagrado Corazón",
                "pais": self.departamento.pais_id,
                "departamento": self.departamento.pk,
                "municipio": self.municipio.pk,
                "direccion": "Carrera 5 # 10-20",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:parroquia_lista"))
        parroquia = Parroquia.objects.get(nombre="Sagrado Corazón")
        self.assertEqual(parroquia.municipio, self.municipio)
        self.assertContains(respuesta, "Registro creado correctamente")

    def test_formulario_de_parroquia_usa_su_plantilla_con_ubicacion_js(self):
        respuesta = self.client.get(reverse("parroquias:parroquia_crear"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "parroquias/parroquia_form.html")
        self.assertContains(respuesta, "js/ubicacion.js")

    def test_precarga_pais_y_departamento_al_editar(self):
        respuesta = self.client.get(
            reverse("parroquias:parroquia_editar", args=[self.parroquia.pk])
        )
        formulario = respuesta.context["form"]
        self.assertEqual(formulario.fields["pais"].initial, self.departamento.pais_id)
        self.assertEqual(formulario.fields["departamento"].initial, self.departamento.pk)

    def test_parroco_solo_ofrece_ministros_con_cargo_parroco(self):
        parroco = self._crear_ministro()
        vicario = self._crear_ministro(
            numero_documento="999", nombre="Luis", apellido="Díaz", cargo=CargoMinisterial.VICARIO
        )
        respuesta = self.client.get(reverse("parroquias:parroquia_crear"))
        queryset = respuesta.context["form"].fields["parroco"].queryset
        self.assertIn(parroco, queryset)
        self.assertNotIn(vicario, queryset)

    def test_editar_parroquia(self):
        respuesta = self.client.post(
            reverse("parroquias:parroquia_editar", args=[self.parroquia.pk]),
            {
                "nombre": "San Pedro Apóstol",
                "municipio": self.municipio.pk,
                "direccion": "Calle 1 # 2-34",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:parroquia_lista"))
        self.parroquia.refresh_from_db()
        self.assertEqual(self.parroquia.nombre, "San Pedro Apóstol")

    def test_eliminar_parroquia_con_libros_muestra_mensaje_y_no_la_borra(self):
        Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        respuesta = self.client.post(
            reverse("parroquias:parroquia_eliminar", args=[self.parroquia.pk]), follow=True
        )
        self.assertTrue(Parroquia.objects.filter(pk=self.parroquia.pk).exists())
        self.assertContains(respuesta, "No se puede eliminar porque tiene registros asociados")

    def test_buscador_filtra_parroquias(self):
        Parroquia.objects.create(
            nombre="Inmaculada Concepción", municipio=self.municipio, direccion="Otra"
        )
        respuesta = self.client.get(reverse("parroquias:parroquia_lista"), {"q": "inmaculada"})
        self.assertContains(respuesta, "Inmaculada Concepción")
        self.assertNotContains(respuesta, "San Pedro Claver")


class MinistroCrudTests(CrudParroquiasBaseTests):
    def test_lista_muestra_los_ministros(self):
        self._crear_ministro()
        respuesta = self.client.get(reverse("parroquias:ministro_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Carlos")
        self.assertContains(respuesta, "Párroco")

    def test_crear_ministro_sin_documento_muestra_error(self):
        respuesta = self.client.post(
            reverse("parroquias:ministro_crear"),
            {
                "nombre": "Ana",
                "apellido": "Rojas",
                "cargo": CargoMinisterial.VICARIO,
                "parroquia": self.parroquia.pk,
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Indique el documento de la persona.")
        self.assertFalse(Ministro.objects.filter(nombre="Ana").exists())

    def test_crear_ministro_con_documento_lo_crea_una_sola_vez(self):
        direccion = reverse("parroquias:ministro_crear")
        datos = {
            "nombre": "Pedro",
            "apellido": "López",
            "cargo": CargoMinisterial.DIACONO,
            "tipo_documento": TipoDocumento.CC,
            "numero_documento": "12345",
        }
        self.client.post(direccion, datos, follow=True)
        self.assertEqual(Documento.objects.count(), 1)
        ministro = Ministro.objects.get(documento__numero_documento="12345")
        self.assertEqual(ministro.documento.numero_documento, "12345")

        respuesta = self.client.post(
            reverse("parroquias:ministro_editar", args=[ministro.pk]),
            {**datos, "apellido": "López Renombrado"},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:ministro_lista"))
        self.assertEqual(Documento.objects.count(), 1)
        ministro.refresh_from_db()
        self.assertEqual(ministro.documento.numero_documento, "12345")

    def test_reutiliza_un_documento_existente(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="888"
        )
        respuesta = self.client.post(
            reverse("parroquias:ministro_crear"),
            {
                "nombre": "Lucía",
                "apellido": "Vargas",
                "cargo": CargoMinisterial.CATEQUISTA,
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "888",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:ministro_lista"))
        self.assertEqual(Documento.objects.count(), 1)
        self.assertEqual(
            Ministro.objects.get(documento__numero_documento="888").documento, documento
        )

    def test_rechaza_documento_de_otro_ministro(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="111"
        )
        self._crear_ministro(documento=documento)
        respuesta = self.client.post(
            reverse("parroquias:ministro_crear"),
            {
                "nombre": "Otro",
                "apellido": "Ministro",
                "cargo": CargoMinisterial.VICARIO,
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "111",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este documento ya pertenece a otra persona.")
        self.assertFalse(Ministro.objects.filter(nombre="Otro").exists())

    def test_tipo_de_documento_sin_numero_es_error(self):
        respuesta = self.client.post(
            reverse("parroquias:ministro_crear"),
            {
                "nombre": "Incompleto",
                "cargo": CargoMinisterial.VICARIO,
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Indique el número del documento.")
        self.assertFalse(Ministro.objects.filter(nombre="Incompleto").exists())

    def test_precarga_documento_al_editar(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CE, numero_documento="444"
        )
        ministro = self._crear_ministro(documento=documento)
        respuesta = self.client.get(reverse("parroquias:ministro_editar", args=[ministro.pk]))
        formulario = respuesta.context["form"]
        self.assertEqual(formulario.fields["tipo_documento"].initial, TipoDocumento.CE)
        self.assertEqual(formulario.fields["numero_documento"].initial, "444")

    def test_eliminar_ministro(self):
        ministro = self._crear_ministro()
        respuesta = self.client.post(
            reverse("parroquias:ministro_eliminar", args=[ministro.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("parroquias:ministro_lista"))
        self.assertFalse(Ministro.objects.filter(pk=ministro.pk).exists())


class LibroCrudTests(CrudParroquiasBaseTests):
    def setUp(self):
        super().setUp()
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )

    def test_lista_incluye_las_acciones(self):
        respuesta = self.client.get(reverse("parroquias:libro_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "parroquias/libro_lista.html")
        self.assertContains(respuesta, "Bautismos 2026")
        self.assertContains(respuesta, reverse("parroquias:libro_editar", args=[self.libro.pk]))
        self.assertContains(respuesta, reverse("parroquias:libro_indice", args=[self.libro.pk]))
        self.assertContains(respuesta, reverse("parroquias:libro_cerrar", args=[self.libro.pk]))

    def test_crear_libro(self):
        respuesta = self.client.post(
            reverse("parroquias:libro_crear"),
            {
                "nombre": "Matrimonios 2026",
                "tipo_libro": TipoLibro.MATRIMONIOS,
                "detalle": "Registro de matrimonios",
                "fecha_apertura": "2026-01-01",
                "parroquia": self.parroquia.pk,
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        self.assertTrue(Libro.objects.filter(nombre="Matrimonios 2026").exists())

    def test_editar_libro(self):
        respuesta = self.client.post(
            reverse("parroquias:libro_editar", args=[self.libro.pk]),
            {
                "nombre": "Bautismos 2026 (corregido)",
                "tipo_libro": TipoLibro.BAUTISMOS,
                "detalle": "Registro de bautismos",
                "fecha_apertura": "2026-01-01",
                "parroquia": self.parroquia.pk,
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.nombre, "Bautismos 2026 (corregido)")

    def test_eliminar_libro_sin_folios(self):
        respuesta = self.client.post(
            reverse("parroquias:libro_eliminar", args=[self.libro.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        self.assertFalse(Libro.objects.filter(pk=self.libro.pk).exists())

    def test_eliminar_libro_con_folios_muestra_mensaje_y_no_lo_borra(self):
        Folio.objects.create(libro=self.libro, numero_folio=1)
        respuesta = self.client.post(
            reverse("parroquias:libro_eliminar", args=[self.libro.pk]), follow=True
        )
        self.assertTrue(Libro.objects.filter(pk=self.libro.pk).exists())
        self.assertContains(respuesta, "No se puede eliminar porque tiene registros asociados")


class FolioCrudTests(CrudParroquiasBaseTests):
    def setUp(self):
        super().setUp()
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )

    def test_lista_muestra_los_folios_del_libro(self):
        Folio.objects.create(libro=self.libro, numero_folio=7)
        respuesta = self.client.get(reverse("parroquias:folio_lista", args=[self.libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "parroquias/folio_lista.html")
        self.assertContains(respuesta, "Bautismos 2026")
        self.assertContains(respuesta, "7")

    def test_lista_de_libro_inexistente_devuelve_404(self):
        respuesta = self.client.get(reverse("parroquias:folio_lista", args=[99999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_crear_folio_en_el_libro(self):
        respuesta = self.client.post(
            reverse("parroquias:folio_crear", args=[self.libro.pk]),
            {"numero_folio": 1, "fecha_creacion": "2026-01-15"},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:folio_lista", args=[self.libro.pk]))
        folio = Folio.objects.get(libro=self.libro, numero_folio=1)
        self.assertEqual(folio.libro, self.libro)

    def test_folio_duplicado_muestra_mensaje_en_espanol(self):
        Folio.objects.create(libro=self.libro, numero_folio=1)
        respuesta = self.client.post(
            reverse("parroquias:folio_crear", args=[self.libro.pk]),
            {"numero_folio": 1},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un folio con ese número en este libro.")
        self.assertEqual(Folio.objects.filter(libro=self.libro, numero_folio=1).count(), 1)

    def test_mismo_numero_en_otro_libro_es_valido(self):
        otro_libro = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        Folio.objects.create(libro=self.libro, numero_folio=1)
        respuesta = self.client.post(
            reverse("parroquias:folio_crear", args=[otro_libro.pk]),
            {"numero_folio": 1},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:folio_lista", args=[otro_libro.pk]))
        self.assertEqual(Folio.objects.filter(numero_folio=1).count(), 2)

    def test_editar_folio(self):
        folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        respuesta = self.client.post(
            reverse("parroquias:folio_editar", args=[self.libro.pk, folio.pk]),
            {"numero_folio": 2},
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:folio_lista", args=[self.libro.pk]))
        folio.refresh_from_db()
        self.assertEqual(folio.numero_folio, 2)

    def test_eliminar_folio(self):
        folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        respuesta = self.client.post(
            reverse("parroquias:folio_eliminar", args=[self.libro.pk, folio.pk]), follow=True
        )
        self.assertRedirects(respuesta, reverse("parroquias:folio_lista", args=[self.libro.pk]))
        self.assertFalse(Folio.objects.filter(pk=folio.pk).exists())

    def test_no_se_puede_editar_un_folio_de_otro_libro(self):
        otro_libro = Libro.objects.create(
            nombre="Confesiones",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        folio = Folio.objects.create(libro=otro_libro, numero_folio=1)
        respuesta = self.client.get(
            reverse("parroquias:folio_editar", args=[self.libro.pk, folio.pk])
        )
        self.assertEqual(respuesta.status_code, 404)


class LoginRequeridoParroquiasTests(TestCase):
    def setUp(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver", municipio=self.municipio, direccion="Calle 1"
        )
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )

    def test_todas_las_vistas_redirigen_al_login_sin_sesion(self):
        urls = [
            reverse("parroquias:parroquia_lista"),
            reverse("parroquias:parroquia_crear"),
            reverse("parroquias:ministro_lista"),
            reverse("parroquias:libro_lista"),
            reverse("parroquias:libro_cerrar", args=[self.libro.pk]),
            reverse("parroquias:libro_indice", args=[self.libro.pk]),
            reverse("parroquias:folio_lista", args=[self.libro.pk]),
            reverse("parroquias:folio_crear", args=[self.libro.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta.url)


# ---------------------------------------------------------------------------
# Formulario, cierre, filtros e índice de Libros
# ---------------------------------------------------------------------------


class LibroFormularioTests(CrudParroquiasBaseTests):
    def setUp(self):
        super().setUp()
        self.ministro = self._crear_ministro()

    def _crear_libro(self, **kwargs):
        datos = {
            "nombre": "Bautismos 2026",
            "tipo_libro": TipoLibro.BAUTISMOS,
            "detalle": "Registro de bautismos",
            "fecha_apertura": date(2026, 1, 1),
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Libro.objects.create(**datos)

    def test_crear_libro_con_campos_de_apertura(self):
        respuesta = self.client.post(
            reverse("parroquias:libro_crear"),
            {
                "parroquia": self.parroquia.pk,
                "tipo_libro": TipoLibro.MATRIMONIOS,
                "nombre": "Matrimonios 2027",
                "numero_libro": 2,
                "fecha_apertura": "2027-01-01",
                "total_folios": 200,
                "ministro_apertura": self.ministro.pk,
                "detalle": "Registro de matrimonios",
                "observaciones": "Lo abre el párroco",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        libro = Libro.objects.get(nombre="Matrimonios 2027")
        self.assertEqual(libro.fecha_apertura, date(2027, 1, 1))
        self.assertEqual(libro.total_folios, 200)
        self.assertEqual(libro.ministro_apertura, self.ministro)
        self.assertEqual(libro.estado, EstadoLibro.ABIERTO)

    def test_segundo_libro_abierto_del_mismo_tipo_da_error_en_el_formulario(self):
        self._crear_libro()
        respuesta = self.client.post(
            reverse("parroquias:libro_crear"),
            {
                "parroquia": self.parroquia.pk,
                "tipo_libro": TipoLibro.BAUTISMOS,
                "nombre": "Bautismos 2028",
                "fecha_apertura": "2028-01-01",
                "detalle": "Otro registro",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya hay un libro de Bautismos abierto en esta parroquia. Ciérralo antes de abrir otro",
        )
        self.assertNotContains(respuesta, "is violated")
        self.assertFalse(Libro.objects.filter(nombre="Bautismos 2028").exists())

    def test_ministro_apertura_se_limita_a_la_parroquia_al_editar(self):
        otra = Parroquia.objects.create(
            nombre="Inmaculada Concepción", municipio=self.municipio, direccion="Otra"
        )
        otro_ministro = self._crear_ministro(
            numero_documento="999", nombre="Luis", apellido="Díaz", parroquia=otra
        )
        libro = self._crear_libro()
        respuesta = self.client.get(reverse("parroquias:libro_editar", args=[libro.pk]))
        queryset = respuesta.context["form"].fields["ministro_apertura"].queryset
        self.assertIn(self.ministro, queryset)
        self.assertNotIn(otro_ministro, queryset)

    def test_cerrar_libro_correcto(self):
        libro = self._crear_libro()
        respuesta = self.client.post(
            reverse("parroquias:libro_cerrar", args=[libro.pk]),
            {
                "fecha_cierre": "2026-07-01",
                "ministro_cierre": self.ministro.pk,
                "nota_cierre": "Cierre normal",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        libro.refresh_from_db()
        self.assertEqual(libro.estado, EstadoLibro.CERRADO)
        self.assertEqual(libro.fecha_cierre, date(2026, 7, 1))
        self.assertEqual(libro.ministro_cierre, self.ministro)
        self.assertEqual(libro.nota_cierre, "Cierre normal")
        self.assertContains(respuesta, "Libro cerrado correctamente")

    def test_cerrar_libro_con_fecha_invalida_muestra_el_error(self):
        libro = self._crear_libro()
        respuesta = self.client.post(
            reverse("parroquias:libro_cerrar", args=[libro.pk]),
            {"fecha_cierre": "2025-01-01", "ministro_cierre": self.ministro.pk},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "anterior a la apertura")
        libro.refresh_from_db()
        self.assertEqual(libro.estado, EstadoLibro.ABIERTO)

    def test_libro_cerrado_no_ofrece_cerrar_y_la_url_redirige(self):
        libro = self._crear_libro(estado=EstadoLibro.CERRADO, fecha_cierre=date(2026, 7, 1))
        respuesta = self.client.get(reverse("parroquias:libro_lista"))
        self.assertNotContains(respuesta, reverse("parroquias:libro_cerrar", args=[libro.pk]))
        respuesta = self.client.get(reverse("parroquias:libro_cerrar", args=[libro.pk]))
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))

    def test_editar_libro_cerrado_es_solo_lectura_y_no_permite_cambios(self):
        libro = self._crear_libro(estado=EstadoLibro.CERRADO, fecha_cierre=date(2026, 7, 1))
        respuesta = self.client.get(reverse("parroquias:libro_editar", args=[libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["libro_cerrado"])
        self.assertContains(respuesta, "solo lectura")
        self.assertNotContains(respuesta, "Guardar")

        respuesta = self.client.post(
            reverse("parroquias:libro_editar", args=[libro.pk]),
            {
                "parroquia": self.parroquia.pk,
                "tipo_libro": TipoLibro.BAUTISMOS,
                "nombre": "Intento de cambio",
                "fecha_apertura": "2026-01-01",
                "detalle": "Registro",
            },
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("parroquias:libro_lista"))
        libro.refresh_from_db()
        self.assertEqual(libro.nombre, "Bautismos 2026")


class LibroListaFiltrosTests(CrudParroquiasBaseTests):
    def setUp(self):
        super().setUp()
        self.otra = Parroquia.objects.create(
            nombre="Inmaculada Concepción", municipio=self.municipio, direccion="Otra"
        )
        self.bautismos = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        self.matrimonios = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.otra,
        )

    def test_filtro_por_parroquia(self):
        respuesta = self.client.get(reverse("parroquias:libro_lista"), {"parroquia": self.otra.pk})
        self.assertContains(respuesta, "Matrimonios 2026")
        self.assertNotContains(respuesta, "Bautismos 2026")

    def test_filtro_por_tipo(self):
        respuesta = self.client.get(
            reverse("parroquias:libro_lista"), {"tipo": TipoLibro.MATRIMONIOS}
        )
        self.assertContains(respuesta, "Matrimonios 2026")
        self.assertNotContains(respuesta, "Bautismos 2026")

    def test_filtro_por_estado(self):
        self.matrimonios.estado = EstadoLibro.CERRADO
        self.matrimonios.fecha_cierre = date(2026, 7, 1)
        self.matrimonios.save()
        respuesta = self.client.get(
            reverse("parroquias:libro_lista"), {"estado": EstadoLibro.CERRADO}
        )
        self.assertContains(respuesta, "Matrimonios 2026")
        self.assertNotContains(respuesta, "Bautismos 2026")

    def test_filtros_combinables(self):
        respuesta = self.client.get(
            reverse("parroquias:libro_lista"),
            {
                "parroquia": self.otra.pk,
                "tipo": TipoLibro.MATRIMONIOS,
                "estado": EstadoLibro.ABIERTO,
            },
        )
        self.assertContains(respuesta, "Matrimonios 2026")
        self.assertNotContains(respuesta, "Bautismos 2026")

    def test_numero_de_consultas_constante_entre_dos_tamanos(self):
        def consultar():
            with CaptureQueriesContext(connection) as contexto:
                respuesta = self.client.get(reverse("parroquias:libro_lista"))
                self.assertEqual(respuesta.status_code, 200)
            return len(contexto.captured_queries)

        pequeno = consultar()
        for i in range(2, 12):
            Libro.objects.create(
                nombre=f"Libro cerrado {i}",
                tipo_libro=TipoLibro.BAUTISMOS,
                detalle="Registro",
                fecha_apertura=date(2026, 1, 1),
                estado=EstadoLibro.CERRADO,
                fecha_cierre=date(2026, 7, 1),
                parroquia=self.parroquia,
            )
        grande = consultar()
        self.assertEqual(pequeno, grande)


class LibroIndiceTests(CrudParroquiasBaseTests):
    def setUp(self):
        super().setUp()
        self.libro = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )

    def test_indice_vacio(self):
        respuesta = self.client.get(reverse("parroquias:libro_indice", args=[self.libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "parroquias/libro_indice.html")
        self.assertContains(respuesta, "Diligencia de apertura")
        self.assertContains(respuesta, "todavía no tiene partidas")
        self.assertEqual(respuesta.context["entradas"], [])

    def test_indice_ordenado_por_apellidos(self):
        self._crear_partida(self.libro, numero=1, fiel=self._crear_fiel("1", apellidos="Zapata"))
        self._crear_partida(self.libro, numero=2, fiel=self._crear_fiel("2", apellidos="Alvarez"))
        respuesta = self.client.get(reverse("parroquias:libro_indice", args=[self.libro.pk]))
        entradas = respuesta.context["entradas"]
        self.assertEqual([entrada["apellidos"] for entrada in entradas], ["Alvarez", "Zapata"])
        self.assertEqual([entrada["numero"] for entrada in entradas], [2, 1])
        self.assertContains(respuesta, "Bautismo")

    def test_indice_incluye_diligencia_de_cierre(self):
        self.libro.estado = EstadoLibro.CERRADO
        self.libro.fecha_cierre = date(2026, 7, 1)
        self.libro.nota_cierre = "Sin páginas anuladas"
        self.libro.save()
        respuesta = self.client.get(reverse("parroquias:libro_indice", args=[self.libro.pk]))
        self.assertContains(respuesta, "Diligencia de cierre")
        self.assertContains(respuesta, "Sin páginas anuladas")


class BorradoProtegidoCrudTests(CrudParroquiasBaseTests):
    def _crear_libro(self, **kwargs):
        datos = {
            "nombre": "Bautismos 2026",
            "tipo_libro": TipoLibro.BAUTISMOS,
            "detalle": "Registro",
            "fecha_apertura": date(2026, 1, 1),
            "parroquia": self.parroquia,
        }
        datos.update(kwargs)
        return Libro.objects.create(**datos)

    def test_eliminar_libro_con_partidas_muestra_mensaje(self):
        libro = self._crear_libro()
        self._crear_partida(libro)
        respuesta = self.client.post(
            reverse("parroquias:libro_eliminar", args=[libro.pk]), follow=True
        )
        self.assertTrue(Libro.objects.filter(pk=libro.pk).exists())
        self.assertContains(respuesta, "No se puede eliminar porque tiene registros asociados")

    def test_eliminar_parroquia_con_libros_muestra_mensaje(self):
        self._crear_libro()
        respuesta = self.client.post(
            reverse("parroquias:parroquia_eliminar", args=[self.parroquia.pk]), follow=True
        )
        self.assertTrue(Parroquia.objects.filter(pk=self.parroquia.pk).exists())
        self.assertContains(respuesta, "No se puede eliminar porque tiene registros asociados")
