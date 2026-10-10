from datetime import date
from urllib.parse import quote

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.choices import (
    CargoMinisterial,
    EstadoCivil,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from parroquias.models import Folio, Libro, Ministro, Parroquia
from sacramentos.models import (
    Bautismo,
    Confirmacion,
    Matrimonio,
    PadrinoMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)
from ubicacion.models import Departamento, Municipio, Pais

from .forms import PadreForm
from .models import Documento, Fiel, Madre, Padre, Padrino

# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class DocumentoTests(TestCase):
    def test_str(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
        )
        self.assertEqual(str(documento), "Cédula de Ciudadanía 1234567890")

    def test_unicidad_tipo_y_numero(self):
        Documento.objects.create(tipo_documento=TipoDocumento.CC, numero_documento="1234567890")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Documento.objects.create(
                    tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
                )

    def test_mismo_numero_en_distinto_tipo_permitido(self):
        Documento.objects.create(tipo_documento=TipoDocumento.CC, numero_documento="1234567890")
        Documento.objects.create(tipo_documento=TipoDocumento.CE, numero_documento="1234567890")
        self.assertEqual(Documento.objects.count(), 2)

    def test_un_documento_puede_pertenecer_a_varios_modelos(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="999"
        )
        Padre.objects.create(documento=documento, nombre="Ana", apellido="Uno")
        Madre.objects.create(documento=documento, nombre="Ana", apellido="Uno")
        Padrino.objects.create(documento=documento, nombre="Ana Uno")
        self.assertEqual(Documento.objects.count(), 1)


class DocumentoMixinFormTests(TestCase):
    def _datos(self, numero, tipo=TipoDocumento.CC):
        return {
            "tipo_documento": tipo,
            "numero_documento": numero,
            "nombre": "Luis",
            "apellido": "Pérez",
        }

    def test_normaliza_puntos_y_espacios(self):
        form = PadreForm(data=self._datos("1.234 5678"))
        self.assertTrue(form.is_valid(), form.errors)
        padre = form.save()
        self.assertEqual(padre.documento.numero_documento, "12345678")

    def test_pasaporte_se_guarda_en_mayusculas(self):
        form = PadreForm(data=self._datos("ab 12-cd", TipoDocumento.PA))
        self.assertTrue(form.is_valid(), form.errors)
        padre = form.save()
        self.assertEqual(padre.documento.numero_documento, "AB12CD")

    def test_cedula_con_letras_es_rechazada(self):
        form = PadreForm(data=self._datos("12a34"))
        self.assertFalse(form.is_valid())
        self.assertIn("numero_documento", form.errors)
        self.assertIn("solo números", form.errors["numero_documento"][0])


class FielTests(TestCase):
    def setUp(self):
        self.documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
        )
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)

    def _crear_fiel(self, **kwargs):
        datos = {
            "documento": self.documento,
            "nombres": "Juan Carlos",
            "apellidos": "Pérez Gómez",
            "fecha_nacimiento": "1990-05-15",
            "municipio_nacimiento": self.municipio,
            "telefono": "3001234567",
        }
        datos.update(kwargs)
        return Fiel.objects.create(**datos)

    def test_str(self):
        fiel = self._crear_fiel()
        self.assertEqual(str(fiel), "Juan Carlos Pérez Gómez")

    def test_protect_impide_borrar_documento_con_fiel(self):
        self._crear_fiel()
        with self.assertRaises(ProtectedError):
            self.documento.delete()
        self.assertTrue(Documento.objects.filter(pk=self.documento.pk).exists())

    def test_protect_impide_borrar_municipio_con_fieles(self):
        fiel = self._crear_fiel()
        with self.assertRaises(ProtectedError):
            self.municipio.delete()
        self.assertTrue(Fiel.objects.filter(pk=fiel.pk).exists())


class PadreTests(TestCase):
    def test_str(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
        )
        padre = Padre.objects.create(documento=documento, nombre="José", apellido="Pérez")
        self.assertEqual(str(padre), "José Pérez")

    def test_documento_unico(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
        )
        Padre.objects.create(documento=documento, nombre="José", apellido="Pérez")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Padre.objects.create(documento=documento, nombre="Otro", apellido="Gómez")


class MadreTests(TestCase):
    def test_str(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="0987654321"
        )
        madre = Madre.objects.create(documento=documento, nombre="María", apellido="Gómez")
        self.assertEqual(str(madre), "María Gómez")

    def test_documento_unico(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="0987654321"
        )
        Madre.objects.create(documento=documento, nombre="María", apellido="Gómez")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Madre.objects.create(documento=documento, nombre="Otra", apellido="Pérez")


class PadrinoTests(TestCase):
    def test_str(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="777777"
        )
        padrino = Padrino.objects.create(nombre="Pedro López", documento=documento)
        self.assertEqual(str(padrino), "Pedro López")

    def test_documento_es_protegido(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="555555"
        )
        Padrino.objects.create(nombre="Pedro López", documento=documento)
        with self.assertRaises(ProtectedError):
            documento.delete()
        self.assertTrue(Documento.objects.filter(pk=documento.pk).exists())


# ---------------------------------------------------------------------------
# Base para las vistas web de personas
# ---------------------------------------------------------------------------


class BasePersonasWebTests(TestCase):
    LIBRO_POR_TIPO = {
        TipoSacramento.BAUTISMO: TipoLibro.BAUTISMOS,
        TipoSacramento.CONFIRMACION: TipoLibro.CONFIRMACIONES,
        TipoSacramento.PRIMERA_COMUNION: TipoLibro.PRIMERA_COMUNION,
        TipoSacramento.MATRIMONIO: TipoLibro.MATRIMONIOS,
    }
    NOMBRE_LIBRO = {
        TipoLibro.BAUTISMOS: "Bautismos 2026",
        TipoLibro.CONFIRMACIONES: "Confirmaciones 2026",
        TipoLibro.PRIMERA_COMUNION: "Primeras comuniones 2026",
        TipoLibro.MATRIMONIOS: "Matrimonios 2026",
    }

    def setUp(self):
        self.usuario = User.objects.create_user(username="tester", password="ClaveDePrueba123*")
        self.client.force_login(self.usuario)
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver", municipio=self.municipio, direccion="Calle 1 # 2-34"
        )
        self.folios = {}
        self.libros = {}
        for tipo_libro, nombre in self.NOMBRE_LIBRO.items():
            libro = Libro.objects.create(
                nombre=nombre,
                tipo_libro=tipo_libro,
                detalle="Registro",
                fecha_apertura=date(2026, 1, 1),
                parroquia=self.parroquia,
            )
            self.libros[tipo_libro] = libro
            self.folios[tipo_libro] = Folio.objects.create(libro=libro, numero_folio=1)
        self.ministro = Ministro.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="9999999999"
            ),
            nombre="Carlos",
            apellido="Gómez",
            cargo=CargoMinisterial.PARROCO,
        )
        self.contadores = {}
        self.expedientes = 0

    def crear_fiel(self, numero="1111111111", nombres="Ana María", apellidos="López Sánchez"):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento=numero
        )
        return Fiel.objects.create(
            documento=documento,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=date(1990, 5, 20),
        )

    def _siguiente_numero(self, tipo):
        self.contadores[tipo] = self.contadores.get(tipo, 0) + 1
        return self.contadores[tipo]

    def crear_sacramento(self, tipo, fiel, fecha=date(2026, 3, 15), numero=None):
        libro = self.libros[self.LIBRO_POR_TIPO[tipo]]
        folio = self.folios[self.LIBRO_POR_TIPO[tipo]]
        return Sacramento.objects.create(
            tipo=tipo,
            fiel=fiel,
            libro=libro,
            folio=folio,
            numero=numero or self._siguiente_numero(tipo),
            fecha=fecha,
            fecha_registro=fecha,
            parroquia=self.parroquia,
            ministro=self.ministro,
        )

    def crear_bautismo(self, fiel, **kwargs):
        sacramento = kwargs.pop("sacramento", None) or self.crear_sacramento(
            TipoSacramento.BAUTISMO, fiel
        )
        datos = {
            "sacramento": sacramento,
            "tipo_hijo": TipoHijo.BIOLOGICO,
            "testigo_nombre": "Testigo",
            "quien_firma": self.ministro,
            "doy_fe": self.ministro,
        }
        datos.update(kwargs)
        return Bautismo.objects.create(**datos)

    def crear_confirmacion(self, fiel, **kwargs):
        sacramento = kwargs.pop("sacramento", None) or self.crear_sacramento(
            TipoSacramento.CONFIRMACION, fiel
        )
        datos = {"sacramento": sacramento, "edad": 12, "doy_fe": self.ministro}
        datos.update(kwargs)
        return Confirmacion.objects.create(**datos)

    def crear_matrimonio(self, **kwargs):
        self.expedientes += 1
        sacramento = self.crear_sacramento(TipoSacramento.MATRIMONIO, None)
        datos = {
            "sacramento": sacramento,
            "expediente": self.expedientes,
            "fecha_declaracion": date(2026, 5, 20),
        }
        datos.update(kwargs)
        return Matrimonio.objects.create(**datos)


# ---------------------------------------------------------------------------
# Consultar personas
# ---------------------------------------------------------------------------


class ConsultarPersonasTests(BasePersonasWebTests):
    def test_busqueda_por_documento_exacto(self):
        self.crear_fiel("12345678", nombres="Ana", apellidos="López")
        self.crear_fiel("99999999", nombres="Otro", apellidos="Gómez")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "12345678"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ana López")
        self.assertNotContains(respuesta, "Otro Gómez")

    def test_busqueda_por_documento_parcial(self):
        self.crear_fiel("12345678", nombres="Ana", apellidos="López")
        self.crear_fiel("99999999", nombres="Otro", apellidos="Gómez")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "4567"})
        self.assertContains(respuesta, "Ana López")
        self.assertNotContains(respuesta, "Otro Gómez")

    def test_busqueda_por_nombre_en_cualquier_orden(self):
        self.crear_fiel("111", nombres="Ana María", apellidos="López Sánchez")
        for termino in ("López Ana", "Ana López", "María Sánchez"):
            with self.subTest(termino=termino):
                respuesta = self.client.get(reverse("personas:consultar"), {"q": termino})
                self.assertContains(respuesta, "Ana María López Sánchez")

    def test_q_corto_muestra_aviso_y_no_busca(self):
        self.crear_fiel("111", nombres="Ana", apellidos="López")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "ab"})
        self.assertContains(respuesta, "Ingrese al menos 3 caracteres")
        self.assertEqual(respuesta.context["personas"], [])

    def test_sin_resultados(self):
        self.crear_fiel("111", nombres="Ana", apellidos="López")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "zzzzzzz"})
        self.assertContains(respuesta, "No se encontraron personas")
        self.assertEqual(respuesta.context["personas"], [])

    def test_fiel_en_dos_partidas_con_roles_distintos(self):
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="López")
        self.crear_sacramento(TipoSacramento.BAUTISMO, fiel)
        self.crear_sacramento(TipoSacramento.CONFIRMACION, fiel)
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Ana López"})
        persona = respuesta.context["personas"][0]
        self.assertEqual(
            {partida["rol"] for partida in persona["partidas"]}, {"bautizado", "confirmado"}
        )
        self.assertContains(respuesta, "Bautizado")
        self.assertContains(respuesta, "Confirmado")

    def test_madre_en_dos_partidas(self):
        madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Marta",
            apellido="Gómez",
        )
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="López")
        self.crear_bautismo(fiel, madre=madre)
        self.crear_confirmacion(fiel, madre=madre)
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Marta"})
        persona = respuesta.context["personas"][0]
        self.assertEqual(len(persona["partidas"]), 2)
        self.assertEqual({partida["rol"] for partida in persona["partidas"]}, {"madre"})

    def test_boton_editar_presente_para_los_cuatro_tipos(self):
        fiel = self.crear_fiel("111", nombres="Ana García", apellidos="Uno")
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis García",
            apellido="Dos",
        )
        madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="333"
            ),
            nombre="Marta García",
            apellido="Tres",
        )
        padrino = Padrino.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="444"
            ),
            nombre="Pedro García",
        )
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "García"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 4)
        self.assertTrue(all(persona["editable"] for persona in personas))
        for url in (
            reverse("personas:fiel_editar", args=[fiel.pk]),
            reverse("personas:padre_editar", args=[padre.pk]),
            reverse("personas:madre_editar", args=[madre.pk]),
            reverse("personas:padrino_editar", args=[padrino.pk]),
        ):
            self.assertContains(respuesta, url)

    def test_testigos_y_padrinos_de_matrimonio_no_tienen_boton_editar(self):
        matrimonio = self.crear_matrimonio()
        TestigoMatrimonio.objects.create(
            matrimonio=matrimonio,
            tipo_documento=TipoDocumento.CC,
            cedula="555",
            nombre="Roberto Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Abogado",
        )
        PadrinoMatrimonio.objects.create(
            matrimonio=matrimonio,
            tipo_documento=TipoDocumento.CC,
            cedula="666",
            nombre="Clara Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Doctora",
        )
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Vargas"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 2)
        self.assertTrue(all(not persona["editable"] for persona in personas))
        self.assertTrue(all(persona["url_editar"] is None for persona in personas))
        roles = {partida["rol"] for persona in personas for partida in persona["partidas"]}
        self.assertEqual(roles, {"testigo", "padrino"})
        self.assertContains(respuesta, "Roberto Vargas")
        self.assertContains(respuesta, "Clara Vargas")
        self.assertNotContains(respuesta, "fa-pencil-alt")


# ---------------------------------------------------------------------------
# Editar persona
# ---------------------------------------------------------------------------


class EditarPersonaTests(BasePersonasWebTests):
    def test_editar_los_cuatro_tipos_guarda_y_vuelve_a_consultar(self):
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="Uno")
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="Dos",
        )
        madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="333"
            ),
            nombre="Marta",
            apellido="Tres",
        )
        padrino = Padrino.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="444"
            ),
            nombre="Pedro Cuatro",
        )
        casos = [
            (
                "personas:padre_editar",
                padre,
                {
                    "tipo_documento": TipoDocumento.CC,
                    "numero_documento": "222",
                    "nombre": "Luis Nuevo",
                    "apellido": "Dos",
                },
                "nombre",
                "Luis Nuevo",
            ),
            (
                "personas:madre_editar",
                madre,
                {
                    "tipo_documento": TipoDocumento.CC,
                    "numero_documento": "333",
                    "nombre": "Marta Nueva",
                    "apellido": "Tres",
                },
                "nombre",
                "Marta Nueva",
            ),
            (
                "personas:padrino_editar",
                padrino,
                {
                    "tipo_documento": TipoDocumento.CC,
                    "numero_documento": "444",
                    "nombre": "Pedro Nuevo",
                },
                "nombre",
                "Pedro Nuevo",
            ),
            (
                "personas:fiel_editar",
                fiel,
                {
                    "tipo_documento": TipoDocumento.CC,
                    "numero_documento": "111",
                    "nombres": "Ana Nueva",
                    "apellidos": "Uno",
                    "fecha_nacimiento": "1990-05-20",
                },
                "nombres",
                "Ana Nueva",
            ),
        ]
        for url_name, objeto, datos, campo, valor in casos:
            with self.subTest(url_name=url_name):
                respuesta = self.client.post(reverse(url_name, args=[objeto.pk]), datos)
                self.assertRedirects(respuesta, reverse("personas:consultar"))
                objeto.refresh_from_db()
                self.assertEqual(getattr(objeto, campo), valor)

    def test_editar_guarda_y_redirige_a_next(self):
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="Pérez",
        )
        destino = reverse("personas:consultar") + "?q=perez"
        url = reverse("personas:padre_editar", args=[padre.pk]) + "?next=" + quote(destino)
        respuesta = self.client.post(
            url,
            {
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "222",
                "nombre": "Luis Nuevo",
                "apellido": "Pérez",
            },
        )
        self.assertRedirects(respuesta, destino)
        padre.refresh_from_db()
        self.assertEqual(padre.nombre, "Luis Nuevo")

    def test_next_externo_se_ignora_y_vuelve_a_consultar(self):
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="Pérez",
        )
        url = (
            reverse("personas:padre_editar", args=[padre.pk])
            + "?next="
            + quote("http://otro-sitio.com")
        )
        respuesta = self.client.post(
            url,
            {
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "222",
                "nombre": "Luis Nuevo",
                "apellido": "Pérez",
            },
        )
        self.assertRedirects(respuesta, reverse("personas:consultar"))

    def test_documento_duplicado_de_padre_muestra_error_en_el_campo(self):
        Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="111"
            ),
            nombre="José",
            apellido="Pérez",
        )
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="Gómez",
        )
        respuesta = self.client.post(
            reverse("personas:padre_editar", args=[padre.pk]),
            {
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "111",
                "nombre": "Luis",
                "apellido": "Gómez",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("numero_documento", respuesta.context["form"].errors)

    def test_documento_duplicado_muestra_error_en_el_campo(self):
        self.crear_fiel("111", nombres="Ana", apellidos="Uno")
        fiel = self.crear_fiel("222", nombres="Luis", apellidos="Dos")
        respuesta = self.client.post(
            reverse("personas:fiel_editar", args=[fiel.pk]),
            {
                "tipo_documento": TipoDocumento.CC,
                "numero_documento": "111",
                "nombres": "Luis",
                "apellidos": "Dos",
                "fecha_nacimiento": "1990-05-20",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("numero_documento", respuesta.context["form"].errors)
        fiel.refresh_from_db()
        self.assertEqual(fiel.documento.numero_documento, "222")

    def test_aviso_muestra_el_numero_correcto_de_partidas(self):
        fiel = self.crear_fiel("111")
        self.crear_sacramento(TipoSacramento.BAUTISMO, fiel)
        self.crear_sacramento(TipoSacramento.CONFIRMACION, fiel)
        respuesta = self.client.get(reverse("personas:fiel_editar", args=[fiel.pk]))
        self.assertContains(respuesta, "las 2 partidas")

    def test_formulario_de_edicion_no_tiene_boton_eliminar(self):
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="Pérez",
        )
        respuesta = self.client.get(reverse("personas:padre_editar", args=[padre.pk]))
        self.assertNotContains(respuesta, "Eliminar")


# ---------------------------------------------------------------------------
# Rutas eliminadas
# ---------------------------------------------------------------------------


class RutasEliminadasTests(BasePersonasWebTests):
    def test_rutas_de_lista_creacion_y_eliminacion_devuelven_404(self):
        rutas = [
            "/personas/padres/",
            "/personas/padres/nuevo/",
            "/personas/padres/1/eliminar/",
            "/personas/madres/",
            "/personas/madres/nuevo/",
            "/personas/madres/1/eliminar/",
            "/personas/padrinos/",
            "/personas/padrinos/nuevo/",
            "/personas/padrinos/1/eliminar/",
            "/personas/fieles/",
            "/personas/fieles/1/",
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class ApiPersonasTests(BasePersonasWebTests):
    def setUp(self):
        super().setUp()
        self.padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="123"
            ),
            nombre="José",
            apellido="Pérez",
        )
        self.madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="456"
            ),
            nombre="María",
            apellido="Gómez",
        )

    def test_api_padre_devuelve_los_datos(self):
        respuesta = self.client.get(reverse("personas:api_padre"), {"numero": "123"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], "José")
        self.assertEqual(respuesta.json()["apellido"], "Pérez")

    def test_api_madre_devuelve_los_datos(self):
        respuesta = self.client.get(reverse("personas:api_madre"), {"numero": "456"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], "María")

    def test_api_padre_inexistente_devuelve_404(self):
        respuesta = self.client.get(reverse("personas:api_padre"), {"numero": "999"})
        self.assertEqual(respuesta.status_code, 404)

    def test_api_sin_numero_devuelve_400(self):
        self.assertEqual(self.client.get(reverse("personas:api_padre")).status_code, 400)
        self.assertEqual(self.client.get(reverse("personas:api_madre")).status_code, 400)


# ---------------------------------------------------------------------------
# Número de consultas
# ---------------------------------------------------------------------------


class ConteoConsultasTests(BasePersonasWebTests):
    TIPOS = (
        TipoSacramento.BAUTISMO,
        TipoSacramento.CONFIRMACION,
        TipoSacramento.PRIMERA_COMUNION,
    )

    def _crear_escenario(self, cantidad, partidas_por_persona):
        for indice in range(cantidad):
            fiel = self.crear_fiel(
                numero=f"9{indice:08d}",
                nombres=f"Persona {indice}",
                apellidos="García",
            )
            for tipo in self.TIPOS[:partidas_por_persona]:
                self.crear_sacramento(tipo, fiel)

    def _limpiar_escenario(self):
        Sacramento.objects.filter(fiel__isnull=False).delete()
        Fiel.objects.all().delete()
        Documento.objects.exclude(pk=self.ministro.documento_id).delete()

    def _consultar(self):
        with CaptureQueriesContext(connection) as captura:
            respuesta = self.client.get(reverse("personas:consultar"), {"q": "García"})
        return len(captura), respuesta

    def test_el_numero_de_consultas_no_depende_del_tamano(self):
        self._crear_escenario(2, 2)
        consultas_pequeno, respuesta_pequeno = self._consultar()
        personas_pequeno = respuesta_pequeno.context["personas"]
        self.assertEqual(len(personas_pequeno), 2)
        self.assertTrue(all(len(persona["partidas"]) == 2 for persona in personas_pequeno))

        self._limpiar_escenario()

        self._crear_escenario(8, 3)
        consultas_grande, respuesta_grande = self._consultar()
        personas_grande = respuesta_grande.context["personas"]
        self.assertEqual(len(personas_grande), 8)
        self.assertTrue(all(len(persona["partidas"]) == 3 for persona in personas_grande))

        self.assertEqual(consultas_pequeno, consultas_grande)


# ---------------------------------------------------------------------------
# Login obligatorio
# ---------------------------------------------------------------------------


class LoginRequeridoPersonasTests(TestCase):
    def test_todas_las_vistas_redirigen_al_login_sin_sesion(self):
        urls = [
            reverse("personas:consultar"),
            reverse("personas:padre_editar", args=[1]),
            reverse("personas:madre_editar", args=[1]),
            reverse("personas:padrino_editar", args=[1]),
            reverse("personas:fiel_editar", args=[1]),
            reverse("personas:api_padre"),
            reverse("personas:api_madre"),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta.url)
