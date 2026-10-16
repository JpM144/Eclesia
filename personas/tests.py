from datetime import date
from urllib.parse import quote

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.choices import (
    AccionHistorial,
    CargoMinisterial,
    EstadoAnotacion,
    EstadoCivil,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from parroquias.models import Folio, Libro, Ministro, Parroquia
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    HistorialSacramento,
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
        self.assertEqual(persona["total_partidas"], 2)
        self.assertEqual(
            {partida["rol"] for partida in persona["partidas"]}, {"bautizado", "confirmado"}
        )
        self.assertEqual({papel["tipo"] for papel in persona["papeles"]}, {"fiel"})
        self.assertContains(respuesta, "Fiel")
        self.assertContains(respuesta, "2 partidas")
        self.assertNotContains(respuesta, "Bautizado")

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
        papeles = [papel for persona in personas for papel in persona["papeles"]]
        tipos = {papel["tipo"] for papel in papeles}
        self.assertEqual(tipos, {"fiel", "padre", "madre", "padrino"})
        self.assertTrue(all(papel["editable"] for papel in papeles))
        urls_esperadas = {
            reverse("personas:fiel_editar", args=[fiel.pk]),
            reverse("personas:padre_editar", args=[padre.pk]),
            reverse("personas:madre_editar", args=[madre.pk]),
            reverse("personas:padrino_editar", args=[padrino.pk]),
        }
        self.assertEqual({papel["url_editar"] for papel in papeles}, urls_esperadas)
        for persona in personas:
            ficha = self.client.get(reverse("personas:ficha", args=[persona["documento_id"]]))
            self.assertContains(ficha, persona["papeles"][0]["url_editar"])

    def test_persona_fiel_padre_y_ministro_se_muestra_una_sola_vez_con_tres_insignias(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="333"
        )
        Fiel.objects.create(
            documento=documento,
            nombres="Pedro",
            apellidos="Suárez",
            fecha_nacimiento=date(1985, 2, 10),
        )
        Padre.objects.create(documento=documento, nombre="Pedro", apellido="Suárez")
        Ministro.objects.create(
            documento=documento,
            nombre="Pedro",
            apellido="Suárez",
            cargo=CargoMinisterial.VICARIO,
        )
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Suárez"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 1)
        self.assertEqual(
            {papel["tipo"] for papel in personas[0]["papeles"]},
            {"fiel", "padre", "ministro"},
        )
        html = respuesta.content.decode()
        for insignia in ("insignia--fiel", "insignia--padre", "insignia--ministro"):
            self.assertEqual(html.count(insignia), 1)

    def test_testigo_de_matrimonio_cuyo_documento_coincide_se_une_a_esa_persona(self):
        fiel = self.crear_fiel("555", nombres="Ana", apellidos="Vargas")
        TestigoMatrimonio.objects.create(
            matrimonio=self.crear_matrimonio(),
            tipo_documento=TipoDocumento.CC,
            cedula="555",
            nombre="Roberto Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Abogado",
        )
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Vargas"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 1)
        self.assertEqual(personas[0]["documento_id"], fiel.documento_id)
        self.assertEqual(
            {papel["tipo"] for papel in personas[0]["papeles"]},
            {"fiel", "testigo"},
        )
        self.assertEqual(respuesta.context["menciones"], [])

    def test_testigos_y_padrinos_de_matrimonio_no_tienen_boton_editar(self):
        testigo = TestigoMatrimonio.objects.create(
            matrimonio=self.crear_matrimonio(),
            tipo_documento=TipoDocumento.CC,
            cedula="555",
            nombre="Roberto Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Abogado",
        )
        padrino = PadrinoMatrimonio.objects.create(
            matrimonio=testigo.matrimonio,
            tipo_documento=TipoDocumento.CC,
            cedula="666",
            nombre="Clara Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Doctora",
        )
        Documento.objects.create(tipo_documento=TipoDocumento.CC, numero_documento=testigo.cedula)
        Documento.objects.create(tipo_documento=TipoDocumento.CC, numero_documento=padrino.cedula)
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Vargas"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 2)
        papeles = [papel for persona in personas for papel in persona["papeles"]]
        self.assertEqual({papel["tipo"] for papel in papeles}, {"testigo", "padrino_matrimonio"})
        self.assertTrue(all(not papel["editable"] for papel in papeles))
        self.assertTrue(all(papel["url_editar"] is None for papel in papeles))
        roles = {partida["rol"] for persona in personas for partida in persona["partidas"]}
        self.assertEqual(roles, {"testigo", "padrino"})
        self.assertContains(respuesta, "Roberto Vargas")
        self.assertContains(respuesta, "Clara Vargas")
        self.assertNotContains(respuesta, "fa-pencil-alt")
        self.assertEqual(respuesta.context["menciones"], [])


# ---------------------------------------------------------------------------
# Menciones sin documento
# ---------------------------------------------------------------------------


class MencionesTests(BasePersonasWebTests):
    def test_mencion_de_bautismo_sin_documento(self):
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="López")
        bautismo = self.crear_bautismo(fiel, abuelo_paterno="Anacleto Suárez")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Anacleto"})
        self.assertEqual(respuesta.context["personas"], [])
        menciones = respuesta.context["menciones"]
        self.assertEqual(len(menciones), 1)
        self.assertEqual(menciones[0]["texto"], "Anacleto Suárez")
        self.assertEqual(menciones[0]["rol"], "Abuelo paterno")
        self.assertEqual(menciones[0]["partida"]["id"], bautismo.sacramento_id)
        self.assertContains(respuesta, "Anacleto Suárez")

    def test_menciones_iguales_en_distintas_partidas_se_agrupan(self):
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="López")
        otro = self.crear_fiel("222", nombres="Otro", apellidos="Niño")
        self.crear_bautismo(fiel, abuelo_paterno="Anacleto Suárez")
        self.crear_bautismo(otro, abuelo_paterno="Anacleto Suárez")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Anacleto"})
        self.assertEqual(len(respuesta.context["menciones"]), 1)

    def test_testigo_de_matrimonio_sin_documento_es_mencion(self):
        testigo = TestigoMatrimonio.objects.create(
            matrimonio=self.crear_matrimonio(),
            tipo_documento=TipoDocumento.CC,
            cedula="555",
            nombre="Roberto Vargas",
            religion="Católica",
            estado_civil=EstadoCivil.CASADO,
            profesion="Abogado",
        )
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Vargas"})
        self.assertEqual(respuesta.context["personas"], [])
        menciones = respuesta.context["menciones"]
        self.assertEqual(len(menciones), 1)
        self.assertEqual(menciones[0]["rol"], "Testigo de matrimonio")
        self.assertEqual(menciones[0]["partida"]["id"], testigo.matrimonio.sacramento_id)

    def test_busqueda_por_documento_no_genera_menciones(self):
        fiel = self.crear_fiel("111", nombres="Ana", apellidos="López")
        self.crear_bautismo(fiel, abuelo_paterno="Anacleto Suárez")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "111"})
        self.assertEqual(respuesta.context["menciones"], [])


# ---------------------------------------------------------------------------
# Ficha de persona
# ---------------------------------------------------------------------------


class FichaPersonaTests(BasePersonasWebTests):
    def _crear_contrayente(self, matrimonio, fiel, sexo):
        return Contrayente.objects.create(
            matrimonio=matrimonio,
            fiel=fiel,
            sexo=sexo,
            parroquia_bautismo=self.parroquia,
            libro_bautismo=1,
            folio_bautismo=2,
            numero_bautismo=3,
            parroquia_confirmacion=self.parroquia,
            fecha_confirmacion=date(2010, 6, 20),
            direccion_residencia="Calle 5 # 6-7",
            nombre_padre="José Pérez",
            nombre_madre="María Gómez",
            edad=30,
            estado_civil=EstadoCivil.SOLTERO,
            religion="Católica",
            profesion="Ingeniero",
            acepta_libertad_matrimonio="SI",
            conoce_unidad_indisolubilidad="SI",
            conoce_obligaciones_familia="SI",
            impedimentos_anteriores="NO",
            dispuesto_cumplir="SI",
            lugar_despues_matrimonio="Bogotá",
        )

    def _escenario_ana(self):
        """Ana es a la vez Fiel, Madre y Ministro con el mismo documento."""
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="333"
        )
        ana = Fiel.objects.create(
            documento=documento,
            nombres="Ana María",
            apellidos="López Pérez",
            fecha_nacimiento=date(1990, 5, 20),
            telefono="3001234567",
        )
        como_madre = Madre.objects.create(documento=documento, nombre="Ana María", apellido="López")
        Ministro.objects.create(
            documento=documento, nombre="Ana", apellido="López", cargo=CargoMinisterial.VICARIO
        )
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="222"
            ),
            nombre="Luis",
            apellido="García",
        )
        madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="777"
            ),
            nombre="Marta",
            apellido="García",
        )
        padrino = Padrino.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="888"
            ),
            nombre="Pedro López",
        )
        bautismo = self.crear_bautismo(ana, padre=padre, madre=madre, padrino=padrino)
        self.crear_confirmacion(ana)
        AnotacionMarginal.objects.create(
            sacramento=bautismo.sacramento,
            tipo=TipoAnotacionMarginal.CONFIRMACION,
            descripcion="Se anotó la confirmación.",
            fecha=date(2026, 4, 10),
            parroquia_destino_texto="Parroquia San Juan",
            estado=EstadoAnotacion.ANOTADA,
        )
        esposo = self.crear_fiel("444", nombres="Luis", apellidos="Pérez")
        matrimonio = self.crear_matrimonio()
        self._crear_contrayente(matrimonio, ana, "M")
        self._crear_contrayente(matrimonio, esposo, "H")
        hijo = self.crear_fiel("555", nombres="Carlos", apellidos="López")
        self.crear_bautismo(hijo, madre=como_madre)
        HistorialSacramento.objects.create(
            sacramento=bautismo.sacramento, accion=AccionHistorial.CREACION, usuario=self.usuario
        )
        return ana

    def test_documento_sin_persona_devuelve_404(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="999"
        )
        self.assertEqual(
            self.client.get(reverse("personas:ficha", args=[documento.pk])).status_code, 404
        )

    def test_ficha_muestra_sacramentos_papeles_familia_ministro_y_anotaciones(self):
        ana = self._escenario_ana()
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertEqual(respuesta.status_code, 200)
        for insignia in ("insignia--fiel", "insignia--madre", "insignia--ministro"):
            self.assertContains(respuesta, insignia)
        for texto in (
            "Bautismo",
            "Confirmación",
            "Matrimonio",
            "Contrayente",
            "Anotación marginal",
            "Luis García",
            "Marta García",
            "Carlos López",
            "Luis Pérez",
            "Vicario",
        ):
            self.assertContains(respuesta, texto)

    def test_ficha_muestra_el_historial_de_sus_partidas(self):
        ana = self._escenario_ana()
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertContains(respuesta, "Historial")
        self.assertContains(respuesta, "Creación")
        self.assertContains(respuesta, "tester (Administrador)")

    def test_ficha_muestra_botones_editar_segun_los_papeles(self):
        ana = self._escenario_ana()
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertContains(respuesta, "Editar datos como fiel")
        self.assertContains(respuesta, "Editar datos como madre")
        self.assertNotContains(respuesta, "Editar datos como ministro")

    def test_secciones_vacias_no_se_muestran(self):
        fiel = self.crear_fiel("333", nombres="Ana", apellidos="López")
        respuesta = self.client.get(reverse("personas:ficha", args=[fiel.documento_id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "CC 333")
        self.assertNotContains(respuesta, "Sacramentos recibidos")
        self.assertNotContains(respuesta, "Familia y relaciones")
        self.assertNotContains(respuesta, "Como ministro")
        self.assertNotContains(respuesta, "Testimonios en matrimonios")
        self.assertNotContains(respuesta, "Historial")

    def test_ministro_sin_partidas_por_documento_y_por_nombre(self):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="333"
        )
        Ministro.objects.create(
            documento=documento, nombre="Ana", apellido="López", cargo=CargoMinisterial.VICARIO
        )
        ficha = self.client.get(reverse("personas:ficha", args=[documento.pk]))
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, "insignia--ministro")
        self.assertContains(ficha, "Vicario")
        self.assertNotContains(ficha, "Sacramentos recibidos")
        self.assertNotContains(ficha, "Historial")
        respuesta = self.client.get(reverse("personas:consultar"), {"q": "Ana"})
        personas = respuesta.context["personas"]
        self.assertEqual(len(personas), 1)
        self.assertEqual(personas[0]["total_partidas"], 0)
        self.assertEqual({papel["tipo"] for papel in personas[0]["papeles"]}, {"ministro"})

    def test_numero_de_consultas_de_la_ficha_no_depende_del_tamano(self):
        ana = self._escenario_ana()
        with CaptureQueriesContext(connection) as captura:
            self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        consultas_pequeno = len(captura)

        esposo2 = self.crear_fiel("666", nombres="Otro", apellidos="Esposo")
        matrimonio = self.crear_matrimonio()
        self._crear_contrayente(matrimonio, ana, "M")
        self._crear_contrayente(matrimonio, esposo2, "H")

        with CaptureQueriesContext(connection) as captura:
            respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(captura), consultas_pequeno)

    @override_settings(NOMBRE_PARROQUIA="")
    def test_ficha_incluye_el_nombre_en_el_bloque_que_se_imprime(self):
        ana = self._escenario_ana()
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        contenido = respuesta.content.decode()
        self.assertContains(respuesta, '<h1 class="print-nombre">Ana María López Pérez</h1>')
        self.assertContains(respuesta, '<p class="print-documento">CC 333</p>')
        self.assertContains(respuesta, "Ficha de persona · Sistema de Gestión Parroquial")
        self.assertContains(respuesta, "Impreso el")
        inicio = contenido.index('class="print-encabezado"')
        bloque = contenido[inicio:]
        for insignia in ("insignia--fiel", "insignia--madre", "insignia--ministro"):
            self.assertIn(insignia, bloque)

    def test_botones_llevan_la_clase_que_se_oculta_al_imprimir(self):
        ana = self._escenario_ana()
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertContains(respuesta, 'class="btn btn-default btn-sm no-print"')
        self.assertContains(respuesta, 'class="btn btn-tema btn-sm no-print"')

    def test_historial_sin_usuario_muestra_datos_de_demostracion(self):
        parroco_demo = Ministro.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="9990000001"
            ),
            nombre="Rafael",
            apellido="Betancur",
            cargo=CargoMinisterial.PARROCO,
        )
        self.parroquia.parroco = parroco_demo
        self.parroquia.save(update_fields=["parroco"])
        ana = self._escenario_ana()
        confirmacion = Sacramento.objects.filter(fiel=ana, tipo=TipoSacramento.CONFIRMACION).first()
        HistorialSacramento.objects.create(
            sacramento=confirmacion, accion=AccionHistorial.CREACION, descripcion="Sin usuario"
        )
        respuesta = self.client.get(reverse("personas:ficha", args=[ana.documento_id]))
        self.assertContains(respuesta, "<td>Datos de demostración</td>")
        self.assertContains(respuesta, "tester (Administrador)")

    def test_historial_sin_usuario_en_parroquia_no_demo_muestra_sistema(self):
        fiel = self.crear_fiel("333", nombres="Ana", apellidos="Prueba")
        sacramento = self.crear_sacramento(TipoSacramento.BAUTISMO, fiel)
        HistorialSacramento.objects.create(
            sacramento=sacramento, accion=AccionHistorial.CREACION, descripcion="Sin usuario"
        )
        respuesta = self.client.get(reverse("personas:ficha", args=[fiel.documento_id]))
        self.assertContains(respuesta, "<td>Sistema</td>")
        self.assertNotContains(respuesta, "Datos de demostración")


# ---------------------------------------------------------------------------
# Editar persona
# ---------------------------------------------------------------------------


class EditarPersonaTests(BasePersonasWebTests):
    def test_editar_los_cuatro_tipos_guarda_y_vuelve_a_consultar(self):
        fiel = self.crear_fiel("11111", nombres="Ana", apellidos="Uno")
        padre = Padre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="22222"
            ),
            nombre="Luis",
            apellido="Dos",
        )
        madre = Madre.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="33333"
            ),
            nombre="Marta",
            apellido="Tres",
        )
        padrino = Padrino.objects.create(
            documento=Documento.objects.create(
                tipo_documento=TipoDocumento.CC, numero_documento="44444"
            ),
            nombre="Pedro Cuatro",
        )
        casos = [
            (
                "personas:padre_editar",
                padre,
                {
                    "tipo_documento": TipoDocumento.CC,
                    "numero_documento": "22222",
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
                    "numero_documento": "33333",
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
                    "numero_documento": "44444",
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
                    "numero_documento": "11111",
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
                tipo_documento=TipoDocumento.CC, numero_documento="22222"
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
                "numero_documento": "22222",
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
                tipo_documento=TipoDocumento.CC, numero_documento="22222"
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
                "numero_documento": "22222",
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
            reverse("personas:ficha", args=[1]),
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
