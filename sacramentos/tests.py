import shutil
import tempfile
from datetime import date, time

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from core.choices import (
    AccionHistorial,
    CargoMinisterial,
    EstadoAnotacion,
    EstadoCivil,
    EstadoLibro,
    EstadoRegistro,
    RespuestaDoctrina,
    ResultadoProclama,
    Sexo,
    SiNo,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from parroquias.models import Folio, Iglesia, Libro, Ministro, Parroquia
from parroquias.services import (
    cerrar_libro,
    folio_sugerido,
    indice_libro,
    siguiente_numero_partida,
)
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from ubicacion.models import Departamento, Municipio, Pais

from .models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    DocumentoSacramento,
    HijoReconocidoMatrimonio,
    HistorialSacramento,
    Matrimonio,
    NotaMarginalMatrimonio,
    PadrinoMatrimonio,
    PrimeraComunion,
    ProclamaMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)
from .services import registrar_historial


class BaseSacramentosTests(TestCase):
    def setUp(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver",
            municipio=self.municipio,
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
        self.fiel = self._crear_fiel()

    def _media_temporal(self):
        ruta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, ruta, ignore_errors=True)
        return override_settings(MEDIA_ROOT=ruta)

    def _crear_fiel(self, numero_documento="1111111111", **kwargs):
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento=numero_documento
        )
        datos = {
            "documento": documento,
            "nombres": "Ana María",
            "apellidos": "López Sánchez",
            "fecha_nacimiento": date(1992, 4, 10),
        }
        datos.update(kwargs)
        return Fiel.objects.create(**datos)

    def _crear_sacramento(self, **kwargs):
        datos = {
            "tipo": TipoSacramento.BAUTISMO,
            "fiel": self.fiel,
            "libro": self.libro,
            "folio": self.folio,
            "numero": 1,
            "fecha": date(2026, 3, 15),
            "fecha_registro": date(2026, 3, 15),
            "parroquia": self.parroquia,
            "ministro": self.ministro,
        }
        datos.update(kwargs)
        return Sacramento.objects.create(**datos)

    def _crear_bautismo(self, **kwargs):
        sacramento = kwargs.pop("sacramento", None)
        if sacramento is None:
            sacramento = self._crear_sacramento()
        datos = {
            "sacramento": sacramento,
            "padre": self.padre,
            "madre": self.madre,
            "abuelo_paterno": "Luis Pérez",
            "abuela_paterna": "Rosa Díaz",
            "abuelo_materno": "Alonso Gómez",
            "abuela_materna": "Clara Ruiz",
            "tipo_hijo": TipoHijo.BIOLOGICO,
            "padrino": self.padrino,
            "madrina": self.padrino,
            "quien_firma": self.ministro,
            "doy_fe": self.ministro,
        }
        datos.update(kwargs)
        return Bautismo.objects.create(**datos)

    def _crear_confirmacion(self, **kwargs):
        sacramento = kwargs.pop("sacramento", None)
        if sacramento is None:
            sacramento = self._crear_sacramento(tipo=TipoSacramento.CONFIRMACION)
        datos = {
            "sacramento": sacramento,
            "edad": 12,
            "doy_fe": self.ministro,
        }
        datos.update(kwargs)
        return Confirmacion.objects.create(**datos)

    def _crear_primera_comunion(self, **kwargs):
        sacramento = kwargs.pop("sacramento", None)
        if sacramento is None:
            sacramento = self._crear_sacramento(tipo=TipoSacramento.PRIMERA_COMUNION)
        datos = {
            "sacramento": sacramento,
            "edad": 9,
            "doy_fe": self.ministro,
        }
        datos.update(kwargs)
        return PrimeraComunion.objects.create(**datos)

    def _crear_matrimonio(self, sacramento=None, **kwargs):
        if sacramento is None:
            sacramento = self._crear_sacramento(tipo=TipoSacramento.MATRIMONIO, fiel=None)
        datos = {
            "sacramento": sacramento,
            "expediente": 100,
            "fecha_declaracion": date(2026, 5, 20),
        }
        datos.update(kwargs)
        return Matrimonio.objects.create(**datos)

    def _crear_contrayente(self, matrimonio, fiel, sexo, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "fiel": fiel,
            "sexo": sexo,
            "parroquia_bautismo": self.parroquia,
            "libro_bautismo": 1,
            "folio_bautismo": 2,
            "numero_bautismo": 3,
            "parroquia_confirmacion": self.parroquia,
            "fecha_confirmacion": date(2010, 6, 20),
            "direccion_residencia": "Calle 5 # 6-7",
            "nombre_padre": "José Pérez",
            "nombre_madre": "María Gómez",
            "edad": 30,
            "estado_civil": EstadoCivil.SOLTERO,
            "religion": "Católica",
            "profesion": "Ingeniero",
            "acepta_libertad_matrimonio": RespuestaDoctrina.SI,
            "conoce_unidad_indisolubilidad": RespuestaDoctrina.SI,
            "conoce_obligaciones_familia": RespuestaDoctrina.SI,
            "impedimentos_anteriores": RespuestaDoctrina.NO,
            "dispuesto_cumplir": RespuestaDoctrina.SI,
            "lugar_despues_matrimonio": "Vivirá en arriendo en Bogotá",
        }
        datos.update(kwargs)
        return Contrayente.objects.create(**datos)

    def _crear_testigo(self, matrimonio, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "tipo_documento": TipoDocumento.CC,
            "cedula": "987654321",
            "nombre": "Roberto Díaz",
            "religion": "Católica",
            "estado_civil": EstadoCivil.CASADO,
            "profesion": "Abogado",
        }
        datos.update(kwargs)
        return TestigoMatrimonio.objects.create(**datos)

    def _crear_padrino_matrimonio(self, matrimonio, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "tipo_documento": TipoDocumento.CC,
            "cedula": "456789123",
            "nombre": "Clara Ruiz",
            "religion": "Católica",
            "estado_civil": EstadoCivil.CASADO,
            "profesion": "Doctora",
        }
        datos.update(kwargs)
        return PadrinoMatrimonio.objects.create(**datos)

    def _crear_proclama(self, matrimonio, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "numero": 1,
            "fecha_proclama": date(2026, 5, 1),
            "resultado": ResultadoProclama.PUBLICADA,
            "observaciones": "",
        }
        datos.update(kwargs)
        return ProclamaMatrimonio.objects.create(**datos)

    def _crear_hijo_reconocido(self, matrimonio, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "tipo_documento": TipoDocumento.CC,
            "numero_documento": "123123123",
            "nombre": "Juan Pérez",
            "fecha_nacimiento": date(2015, 1, 20),
            "edad": 10,
            "bautizado": SiNo.SI,
        }
        datos.update(kwargs)
        return HijoReconocidoMatrimonio.objects.create(**datos)

    def _crear_nota_marginal(self, matrimonio, **kwargs):
        datos = {
            "matrimonio": matrimonio,
            "parroquia_licencia": "San Pedro Claver",
            "delegacion_licencia": "Vicaría foránea",
            "parroco_delega": "Carlos Gómez",
            "presencio": "Testigo parroquial",
            "doy_fe": "Carlos Gómez",
            "parroco": "Carlos Gómez",
            "fecha_licencia": date(2026, 5, 1),
            "fecha_matrimonio": date(2026, 5, 20),
            "fecha_envio_acta": date(2026, 5, 25),
            "hora_matrimonio": time(15, 30),
        }
        datos.update(kwargs)
        return NotaMarginalMatrimonio.objects.create(**datos)

    def _crear_anotacion(self, sacramento=None, **kwargs):
        datos = {
            "sacramento": sacramento,
            "tipo": TipoAnotacionMarginal.CONFIRMACION,
            "descripcion": "Se anota la confirmación recibida",
            "fecha": date(2026, 4, 1),
        }
        datos.update(kwargs)
        return AnotacionMarginal.objects.create(**datos)

    def _crear_documento_sacramento(self, sacramento, **kwargs):
        datos = {
            "sacramento": sacramento,
            "archivo": ContentFile(b"contenido del documento", name="documento.txt"),
            "descripcion": "Certificado",
        }
        datos.update(kwargs)
        return DocumentoSacramento.objects.create(**datos)

    def _crear_historial(self, sacramento, **kwargs):
        accion = kwargs.pop("accion", AccionHistorial.CREACION)
        descripcion = kwargs.pop("descripcion", "Registro creado")
        usuario = kwargs.pop("usuario", None)
        return registrar_historial(sacramento, accion, descripcion, usuario)


class BaseMatrimonioTests(BaseSacramentosTests):
    def setUp(self):
        super().setUp()
        self.matrimonio = self._crear_matrimonio()


class SacramentoTests(BaseSacramentosTests):
    def test_str(self):
        sacramento = self._crear_sacramento()
        self.assertEqual(str(sacramento), "Bautismo N.° 1 - Folio 1 - Bautismos 2026")

    def test_unicidad_libro_y_numero(self):
        self._crear_sacramento()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_sacramento()

    def test_mismo_numero_en_otro_folio_permitido(self):
        self._crear_sacramento()
        otro_libro = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        otro_folio = Folio.objects.create(libro=otro_libro, numero_folio=1)
        self._crear_sacramento(libro=otro_libro, folio=otro_folio)
        self.assertEqual(Sacramento.objects.count(), 2)

    def test_bautismo_requiere_fiel(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_sacramento(tipo=TipoSacramento.BAUTISMO, fiel=None)

    def test_confirmacion_requiere_fiel(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_sacramento(tipo=TipoSacramento.CONFIRMACION, fiel=None)

    def test_matrimonio_no_permite_fiel(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_sacramento(tipo=TipoSacramento.MATRIMONIO, fiel=self.fiel)

    def test_bautismo_con_fiel_es_valido(self):
        sacramento = self._crear_sacramento(tipo=TipoSacramento.BAUTISMO)
        self.assertEqual(sacramento.fiel, self.fiel)

    def test_matrimonio_sin_fiel_es_valido(self):
        sacramento = self._crear_sacramento(tipo=TipoSacramento.MATRIMONIO, fiel=None)
        self.assertIsNone(sacramento.fiel)

    def test_protect_impide_borrar_folio_con_sacramentos(self):
        sacramento = self._crear_sacramento()
        with self.assertRaises(ProtectedError):
            self.folio.delete()
        self.assertTrue(Sacramento.objects.filter(pk=sacramento.pk).exists())

    def test_protect_impide_borrar_fiel_con_sacramentos(self):
        sacramento = self._crear_sacramento()
        with self.assertRaises(ProtectedError):
            self.fiel.delete()
        self.assertTrue(Sacramento.objects.filter(pk=sacramento.pk).exists())


class BautismoTests(BaseSacramentosTests):
    def test_str(self):
        bautismo = self._crear_bautismo()
        self.assertEqual(str(bautismo), "Bautismo de Ana María López Sánchez")

    def test_comparte_pk_con_su_sacramento(self):
        bautismo = self._crear_bautismo()
        self.assertEqual(bautismo.pk, bautismo.sacramento.pk)
        self.assertEqual(bautismo.sacramento_id, bautismo.pk)
        sacramento = Sacramento.objects.get(pk=bautismo.pk)
        self.assertEqual(sacramento.tipo, TipoSacramento.BAUTISMO)
        self.assertEqual(sacramento.bautismo, bautismo)

    def test_borrar_sacramento_borra_el_bautismo(self):
        bautismo = self._crear_bautismo()
        bautismo.sacramento.delete()
        self.assertFalse(Bautismo.objects.filter(pk=bautismo.pk).exists())


class ConfirmacionTests(BaseSacramentosTests):
    def test_str(self):
        confirmacion = self._crear_confirmacion()
        self.assertEqual(str(confirmacion), "Confirmación de Ana María López Sánchez")

    def test_comparte_pk_con_su_sacramento(self):
        confirmacion = self._crear_confirmacion()
        self.assertEqual(confirmacion.pk, confirmacion.sacramento.pk)
        sacramento = Sacramento.objects.get(pk=confirmacion.pk)
        self.assertEqual(sacramento.tipo, TipoSacramento.CONFIRMACION)
        self.assertEqual(sacramento.confirmacion, confirmacion)

    def test_valida_sin_padres_ni_padrinos(self):
        confirmacion = Confirmacion(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.CONFIRMACION),
            edad=12,
            doy_fe=self.ministro,
        )
        confirmacion.clean()
        confirmacion.save()
        self.assertIsNone(confirmacion.padre)
        self.assertIsNone(confirmacion.madre)
        self.assertIsNone(confirmacion.padrino)
        self.assertIsNone(confirmacion.madrina)

    def test_mixin_con_bautismo_registrado(self):
        bautismo = self._crear_bautismo()
        confirmacion = self._crear_confirmacion(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.CONFIRMACION, numero=2),
            bautismo=bautismo,
        )
        self.assertEqual(confirmacion.bautismo, bautismo)
        self.assertIn(confirmacion, bautismo.confirmacion_set.all())

    def test_mixin_con_datos_de_bautismo_externo(self):
        confirmacion = self._crear_confirmacion(
            fecha_bautismo=date(2000, 6, 10),
            parroquia_bautismo="Parroquia La Catedral",
            iglesia_bautismo="Capilla del Sagrario",
            municipio_bautismo=self.municipio,
            libro_bautismo=2,
            folio_bautismo=5,
            numero_bautismo=12,
            observaciones_bautismo="Bautizado en la capilla",
        )
        self.assertEqual(confirmacion.fecha_bautismo, date(2000, 6, 10))
        self.assertEqual(confirmacion.parroquia_bautismo, "Parroquia La Catedral")
        self.assertEqual(confirmacion.iglesia_bautismo, "Capilla del Sagrario")
        self.assertEqual(confirmacion.municipio_bautismo, self.municipio)
        self.assertEqual(confirmacion.numero_bautismo, 12)
        self.assertEqual(confirmacion.observaciones_bautismo, "Bautizado en la capilla")


class PrimeraComunionTests(BaseSacramentosTests):
    def test_str(self):
        primera = self._crear_primera_comunion()
        self.assertEqual(str(primera), "Primera comunión de Ana María López Sánchez")

    def test_comparte_pk_con_su_sacramento(self):
        primera = self._crear_primera_comunion()
        self.assertEqual(primera.pk, primera.sacramento.pk)
        sacramento = Sacramento.objects.get(pk=primera.pk)
        self.assertEqual(sacramento.tipo, TipoSacramento.PRIMERA_COMUNION)
        self.assertEqual(sacramento.primera_comunion, primera)

    def test_padres_opcionales(self):
        primera = self._crear_primera_comunion(padre=self.padre, madre=self.madre)
        self.assertEqual(primera.padre, self.padre)
        self.assertEqual(primera.madre, self.madre)
        primera_sin_padres = self._crear_primera_comunion(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.PRIMERA_COMUNION, numero=2)
        )
        self.assertIsNone(primera_sin_padres.padre)
        self.assertIsNone(primera_sin_padres.madre)

    def test_mixin_con_bautismo_registrado(self):
        bautismo = self._crear_bautismo()
        primera = self._crear_primera_comunion(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.PRIMERA_COMUNION, numero=2),
            bautismo=bautismo,
        )
        self.assertEqual(primera.bautismo, bautismo)
        self.assertIn(primera, bautismo.primeracomunion_set.all())

    def test_mixin_con_datos_de_bautismo_externo(self):
        primera = self._crear_primera_comunion(
            fecha_bautismo=date(2018, 8, 30),
            parroquia_bautismo="Parroquia San José",
            iglesia_bautismo="Iglesia principal",
            municipio_bautismo=self.municipio,
            libro_bautismo=2,
            folio_bautismo=8,
            numero_bautismo=12,
        )
        self.assertEqual(primera.fecha_bautismo, date(2018, 8, 30))
        self.assertEqual(primera.parroquia_bautismo, "Parroquia San José")
        self.assertEqual(primera.iglesia_bautismo, "Iglesia principal")
        self.assertEqual(primera.municipio_bautismo, self.municipio)
        self.assertEqual(primera.numero_bautismo, 12)


class MatrimonioTests(BaseMatrimonioTests):
    def test_str(self):
        self.assertEqual(str(self.matrimonio), "Matrimonio - Expediente 100")

    def test_borrar_matrimonio_borra_tablas_hijas_pero_no_el_fiel(self):
        fiel_hombre = self._crear_fiel(numero_documento="3333333333")
        fiel_mujer = self._crear_fiel(
            numero_documento="4444444444", nombres="Luis", apellidos="Pérez"
        )
        self._crear_contrayente(self.matrimonio, fiel_hombre, Sexo.HOMBRE)
        self._crear_contrayente(self.matrimonio, fiel_mujer, Sexo.MUJER)
        self._crear_testigo(self.matrimonio)
        self._crear_padrino_matrimonio(self.matrimonio)
        self._crear_proclama(self.matrimonio)
        self._crear_hijo_reconocido(self.matrimonio)
        self._crear_nota_marginal(self.matrimonio)

        self.matrimonio.delete()

        self.assertFalse(Contrayente.objects.exists())
        self.assertFalse(TestigoMatrimonio.objects.exists())
        self.assertFalse(PadrinoMatrimonio.objects.exists())
        self.assertFalse(ProclamaMatrimonio.objects.exists())
        self.assertFalse(HijoReconocidoMatrimonio.objects.exists())
        self.assertFalse(NotaMarginalMatrimonio.objects.exists())
        self.assertTrue(Fiel.objects.filter(pk=fiel_hombre.pk).exists())
        self.assertTrue(Fiel.objects.filter(pk=fiel_mujer.pk).exists())


class ContrayenteTests(BaseMatrimonioTests):
    def test_str(self):
        contrayente = self._crear_contrayente(self.matrimonio, self.fiel, Sexo.MUJER)
        self.assertEqual(str(contrayente), "Ana María López Sánchez (Mujer)")

    def test_unicidad_sexo_por_matrimonio(self):
        fiel_hombre = self._crear_fiel(numero_documento="3333333333")
        otro_fiel_hombre = self._crear_fiel(numero_documento="4444444444")
        self._crear_contrayente(self.matrimonio, fiel_hombre, Sexo.HOMBRE)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_contrayente(self.matrimonio, otro_fiel_hombre, Sexo.HOMBRE)

    def test_unicidad_fiel_por_matrimonio(self):
        self._crear_contrayente(self.matrimonio, self.fiel, Sexo.MUJER)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_contrayente(self.matrimonio, self.fiel, Sexo.HOMBRE)

    def test_mismo_sexo_en_otro_matrimonio_permitido(self):
        otro_fiel = self._crear_fiel(numero_documento="3333333333")
        otro_matrimonio = self._crear_matrimonio(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.MATRIMONIO, fiel=None, numero=2),
            expediente=101,
        )
        self._crear_contrayente(self.matrimonio, self.fiel, Sexo.HOMBRE)
        self._crear_contrayente(otro_matrimonio, otro_fiel, Sexo.HOMBRE)
        self.assertEqual(Contrayente.objects.count(), 2)


class TablasHijasMatrimonioTests(BaseMatrimonioTests):
    def test_str_testigo_matrimonio(self):
        testigo = self._crear_testigo(self.matrimonio)
        self.assertEqual(str(testigo), "Roberto Díaz (Cédula de Ciudadanía 987654321)")

    def test_str_padrino_matrimonio(self):
        padrino = self._crear_padrino_matrimonio(self.matrimonio)
        self.assertEqual(str(padrino), "Clara Ruiz (Cédula de Ciudadanía 456789123)")

    def test_str_proclama_matrimonio(self):
        proclama = self._crear_proclama(self.matrimonio)
        self.assertEqual(str(proclama), "Proclama N.° 1 - Matrimonio 100")

    def test_str_hijo_reconocido(self):
        hijo = self._crear_hijo_reconocido(self.matrimonio)
        self.assertEqual(str(hijo), "Juan Pérez (Cédula de Ciudadanía 123123123)")

    def test_str_nota_marginal_matrimonio(self):
        nota = self._crear_nota_marginal(self.matrimonio)
        self.assertEqual(str(nota), "Nota marginal - Matrimonio 100")


class ProclamaMatrimonioTests(BaseMatrimonioTests):
    def test_permite_varias_proclamas_por_matrimonio(self):
        self._crear_proclama(self.matrimonio)
        self._crear_proclama(self.matrimonio, numero=2)
        self.assertEqual(ProclamaMatrimonio.objects.filter(matrimonio=self.matrimonio).count(), 2)

    def test_unicidad_numero_por_matrimonio(self):
        self._crear_proclama(self.matrimonio, numero=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_proclama(self.matrimonio, numero=1)

    def test_mismo_numero_en_otro_matrimonio_permitido(self):
        otro_matrimonio = self._crear_matrimonio(
            sacramento=self._crear_sacramento(tipo=TipoSacramento.MATRIMONIO, fiel=None, numero=2),
            expediente=101,
        )
        self._crear_proclama(self.matrimonio, numero=1)
        self._crear_proclama(otro_matrimonio, numero=1)
        self.assertEqual(ProclamaMatrimonio.objects.count(), 2)

    def test_guarda_resultado_y_observaciones(self):
        proclama = self._crear_proclama(
            self.matrimonio,
            resultado=ResultadoProclama.CON_IMPEDIMENTO,
            observaciones="Se detectó un impedimento",
        )
        self.assertEqual(proclama.resultado, ResultadoProclama.CON_IMPEDIMENTO)
        self.assertEqual(proclama.observaciones, "Se detectó un impedimento")


class SacramentosNuevasReglasTests(BaseSacramentosTests):
    def test_fecha_registro_anterior_a_fecha_falla(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_sacramento(fecha_registro=date(2026, 3, 14))

    def test_fecha_registro_igual_a_fecha_es_valida(self):
        sacramento = self._crear_sacramento(fecha_registro=date(2026, 3, 15))
        self.assertEqual(sacramento.fecha_registro, date(2026, 3, 15))

    def test_clean_rechaza_libro_de_tipo_equivocado(self):
        sacramento = Sacramento(
            tipo=TipoSacramento.CONFIRMACION,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=1,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2026, 3, 15),
            parroquia=self.parroquia,
        )
        with self.assertRaises(ValidationError):
            sacramento.clean()

    def test_clean_acepta_libro_del_tipo_correcto(self):
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=1,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2026, 3, 15),
            parroquia=self.parroquia,
        )
        sacramento.clean()

    def test_clean_rechaza_iglesia_de_otra_parroquia(self):
        otra_parroquia = Parroquia.objects.create(
            nombre="Otra Parroquia", municipio=self.municipio, direccion="Otra"
        )
        iglesia = Iglesia.objects.create(parroquia=otra_parroquia, nombre="Iglesia ajena")
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=1,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2026, 3, 15),
            parroquia=self.parroquia,
            iglesia=iglesia,
        )
        with self.assertRaises(ValidationError):
            sacramento.clean()

    def test_clean_acepta_iglesia_de_la_parroquia_del_libro(self):
        iglesia = Iglesia.objects.create(parroquia=self.parroquia, nombre="Iglesia propia")
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=1,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2026, 3, 15),
            parroquia=self.parroquia,
            iglesia=iglesia,
        )
        sacramento.clean()


class BautismoCleanTests(BaseSacramentosTests):
    def _bautismo_base(self, **kwargs):
        datos = {
            "sacramento": self._crear_sacramento(),
            "tipo_hijo": TipoHijo.BIOLOGICO,
            "quien_firma": self.ministro,
            "doy_fe": self.ministro,
        }
        datos.update(kwargs)
        return Bautismo(**datos)

    def test_sin_padrinos_y_sin_testigo_falla(self):
        bautismo = self._bautismo_base()
        with self.assertRaises(ValidationError):
            bautismo.clean()

    def test_sin_padrinos_con_testigo_pasa(self):
        bautismo = self._bautismo_base(testigo_nombre="Marta Ruiz")
        bautismo.clean()

    def test_con_padrino_sin_testigo_pasa(self):
        bautismo = self._bautismo_base(padrino=self.padrino)
        bautismo.clean()

    def test_con_madrina_sin_testigo_pasa(self):
        bautismo = self._bautismo_base(madrina=self.padrino)
        bautismo.clean()


class MatrimonioDispensasTests(BaseMatrimonioTests):
    def test_dispensa_por_defecto_no(self):
        self.assertEqual(self.matrimonio.dispensa_impedimento, SiNo.NO)

    def test_guarda_datos_de_dispensa(self):
        self.matrimonio.dispensa_impedimento = SiNo.SI
        self.matrimonio.impedimentos = "Parentesco en cuarto grado"
        self.matrimonio.dispensa_autoridad = "Obispo diocesano"
        self.matrimonio.fecha_dispensa = date(2026, 5, 10)
        self.matrimonio.save()
        self.matrimonio.refresh_from_db()
        self.assertEqual(self.matrimonio.dispensa_impedimento, SiNo.SI)
        self.assertEqual(self.matrimonio.impedimentos, "Parentesco en cuarto grado")
        self.assertEqual(self.matrimonio.dispensa_autoridad, "Obispo diocesano")
        self.assertEqual(self.matrimonio.fecha_dispensa, date(2026, 5, 10))

    def test_guarda_documento_dispensa(self):
        with self._media_temporal():
            self.matrimonio.dispensa_impedimento = SiNo.SI
            self.matrimonio.impedimentos = "Parentesco"
            self.matrimonio.dispensa_autoridad = "Obispo"
            self.matrimonio.documento_dispensa = ContentFile(b"dispensa", name="dispensa.pdf")
            self.matrimonio.save()
            self.assertTrue(self.matrimonio.documento_dispensa.name.startswith("dispensas/"))

    def test_clean_sin_dispensa_no_exige_datos(self):
        self.matrimonio.dispensa_impedimento = SiNo.NO
        self.matrimonio.impedimentos = ""
        self.matrimonio.dispensa_autoridad = ""
        self.matrimonio.clean()

    def test_clean_dispensa_sin_impedimentos_falla(self):
        self.matrimonio.dispensa_impedimento = SiNo.SI
        self.matrimonio.impedimentos = ""
        self.matrimonio.dispensa_autoridad = "Obispo diocesano"
        with self.assertRaises(ValidationError) as contexto:
            self.matrimonio.clean()
        self.assertIn("impedimentos", contexto.exception.message_dict)

    def test_clean_dispensa_sin_autoridad_falla(self):
        self.matrimonio.dispensa_impedimento = SiNo.SI
        self.matrimonio.impedimentos = "Parentesco"
        self.matrimonio.dispensa_autoridad = ""
        with self.assertRaises(ValidationError) as contexto:
            self.matrimonio.clean()
        self.assertIn("dispensa_autoridad", contexto.exception.message_dict)

    def test_clean_dispensa_completa_pasa(self):
        self.matrimonio.dispensa_impedimento = SiNo.SI
        self.matrimonio.impedimentos = "Parentesco en cuarto grado"
        self.matrimonio.dispensa_autoridad = "Obispo diocesano"
        self.matrimonio.clean()


class AnotacionMarginalTests(BaseSacramentosTests):
    def test_str(self):
        anotacion = self._crear_anotacion(self._crear_sacramento())
        self.assertEqual(
            str(anotacion),
            "Anotación marginal - Confirmación (Bautismo N.° 1 - Folio 1 - Bautismos 2026)",
        )

    def test_estado_por_defecto(self):
        anotacion = self._crear_anotacion(self._crear_sacramento())
        self.assertEqual(anotacion.estado, EstadoAnotacion.POR_COMUNICAR)

    def test_permite_varias_anotaciones_por_sacramento(self):
        sacramento = self._crear_sacramento()
        self._crear_anotacion(sacramento)
        self._crear_anotacion(sacramento, tipo=TipoAnotacionMarginal.OTRO)
        self.assertEqual(AnotacionMarginal.objects.count(), 2)

    def test_anotada_sin_sacramento_falla(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_anotacion(None, estado=EstadoAnotacion.ANOTADA)

    def test_anotada_con_sacramento_pasa(self):
        anotacion = self._crear_anotacion(self._crear_sacramento(), estado=EstadoAnotacion.ANOTADA)
        self.assertEqual(anotacion.estado, EstadoAnotacion.ANOTADA)

    def test_comunicada_sin_fecha_falla(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_anotacion(
                    self._crear_sacramento(),
                    estado=EstadoAnotacion.COMUNICADA,
                    fecha_comunicacion=None,
                )

    def test_comunicada_con_fecha_pasa(self):
        anotacion = self._crear_anotacion(
            self._crear_sacramento(),
            estado=EstadoAnotacion.COMUNICADA,
            fecha_comunicacion=date(2026, 4, 15),
        )
        self.assertEqual(anotacion.fecha_comunicacion, date(2026, 4, 15))

    def test_por_comunicar_sin_fecha_ni_sacramento_pasa(self):
        anotacion = self._crear_anotacion(None)
        self.assertIsNone(anotacion.sacramento)
        self.assertIsNone(anotacion.fecha_comunicacion)

    def test_guardar_destino_y_origen(self):
        sacramento = self._crear_sacramento()
        anotacion = self._crear_anotacion(
            sacramento,
            sacramento_origen=None,
            parroquia_destino=self.parroquia,
            parroquia_destino_texto="Parroquia vecina",
        )
        self.assertEqual(anotacion.parroquia_destino, self.parroquia)
        self.assertEqual(anotacion.parroquia_destino_texto, "Parroquia vecina")


class HistorialSacramentoTests(BaseSacramentosTests):
    def test_registrar_historial_crea_registro(self):
        sacramento = self._crear_sacramento()
        historial = registrar_historial(sacramento, AccionHistorial.CREACION, "Alta del registro")
        self.assertEqual(historial.sacramento, sacramento)
        self.assertEqual(historial.accion, AccionHistorial.CREACION)
        self.assertEqual(HistorialSacramento.objects.count(), 1)

    def test_str(self):
        sacramento = self._crear_sacramento()
        historial = self._crear_historial(sacramento, accion=AccionHistorial.CREACION)
        self.assertIn("Creación", str(historial))


class DocumentoSacramentoTests(BaseSacramentosTests):
    def test_str_y_ruta_del_archivo(self):
        with self._media_temporal():
            sacramento = self._crear_sacramento()
            documento = self._crear_documento_sacramento(sacramento)
            self.assertEqual(str(documento), f"Certificado - {sacramento}")
            self.assertTrue(documento.archivo.name.startswith("documentos_sacramentos/"))

    def test_subido_en_automatico_y_subido_por_opcional(self):
        with self._media_temporal():
            sacramento = self._crear_sacramento()
            documento = self._crear_documento_sacramento(sacramento)
            self.assertIsNotNone(documento.subido_en)
            self.assertIsNone(documento.subido_por)


class CascadaSacramentoTests(BaseSacramentosTests):
    def test_borrar_sacramento_borra_subtipos_y_dependientes(self):
        with self._media_temporal():
            sacramento = self._crear_sacramento(tipo=TipoSacramento.PRIMERA_COMUNION)
            primera = self._crear_primera_comunion(sacramento=sacramento)
            anotacion = self._crear_anotacion(sacramento)
            historial = self._crear_historial(sacramento)
            documento = self._crear_documento_sacramento(sacramento)

            sacramento.delete()

            self.assertFalse(PrimeraComunion.objects.filter(pk=primera.pk).exists())
            self.assertFalse(AnotacionMarginal.objects.filter(pk=anotacion.pk).exists())
            self.assertFalse(HistorialSacramento.objects.filter(pk=historial.pk).exists())
            self.assertFalse(DocumentoSacramento.objects.filter(pk=documento.pk).exists())


class MigracionAnotacionesTests(TestCase):
    """Verifica la lógica de la migración de datos de anotaciones a observaciones."""

    def test_concatena_anotaciones_y_anotacion(self):
        import importlib
        from types import SimpleNamespace

        modulo = importlib.import_module(
            "sacramentos.migrations.0002_sacramento_campos_iglesia_estado_auditoria"
        )

        guardados = []

        class SacramentoFalso:
            def __init__(self):
                self.observaciones = ""

            def save(self, **kwargs):
                guardados.append(self.observaciones)

        class BautismoFalso:
            def __init__(self, anotaciones, anotacion):
                self.anotaciones = anotaciones
                self.anotacion = anotacion
                self.sacramento = SacramentoFalso()

        registros = [
            BautismoFalso("primera", "segunda"),
            BautismoFalso("solo una", ""),
            BautismoFalso("", ""),
        ]

        class ManagerFalso:
            def all(self):
                return self

            def iterator(self):
                return iter(registros)

        class AppsFalso:
            def get_model(self, app_label, model_name):
                return SimpleNamespace(objects=ManagerFalso())

        modulo.copiar_anotaciones(AppsFalso(), None)
        self.assertEqual(guardados, ["primera\nsegunda", "solo una"])


class MigracionDocumentosTests(TestCase):
    """Verifica la función de copia de DocumentoMatrimonio a DocumentoSacramento."""

    def test_documento_matrimonio_eliminado(self):
        from . import models

        self.assertFalse(hasattr(models, "DocumentoMatrimonio"))

    def test_copia_documentos_a_documento_sacramento(self):
        import importlib
        from types import SimpleNamespace

        modulo = importlib.import_module(
            "sacramentos.migrations.0003_anotacionmarginal_documentosacramento_and_more"
        )

        creados = []

        class ArchivoFalso:
            def __init__(self, name):
                self.name = name

        class DocumentoMatrimonioFalso:
            def __init__(self, matrimonio_id, descripcion, archivo):
                self.matrimonio_id = matrimonio_id
                self.descripcion = descripcion
                self.archivo = ArchivoFalso(archivo)

        class ManagerDocumentoMatrimonio:
            def all(self):
                return self

            def iterator(self):
                return iter(
                    [
                        DocumentoMatrimonioFalso(7, "Acta", "documentos_matrimonio/acta.txt"),
                        DocumentoMatrimonioFalso(
                            9, "Certificado", "documentos_matrimonio/cert.pdf"
                        ),
                    ]
                )

        class ManagerDocumentoSacramento:
            def create(self, **kwargs):
                creados.append(kwargs)

        modelos = {
            "DocumentoMatrimonio": SimpleNamespace(objects=ManagerDocumentoMatrimonio()),
            "DocumentoSacramento": SimpleNamespace(objects=ManagerDocumentoSacramento()),
        }

        class AppsFalso:
            def get_model(self, app_label, model_name):
                return modelos[model_name]

        modulo.copiar_documentos_matrimonio(AppsFalso(), None)
        self.assertEqual(
            creados,
            [
                {
                    "sacramento_id": 7,
                    "descripcion": "Acta",
                    "archivo": "documentos_matrimonio/acta.txt",
                },
                {
                    "sacramento_id": 9,
                    "descripcion": "Certificado",
                    "archivo": "documentos_matrimonio/cert.pdf",
                },
            ],
        )


class ReglasNumeracionSacramentoTests(BaseSacramentosTests):
    """La numeración es correlativa por libro y el folio pertenece al libro."""

    def test_numero_repetido_en_el_mismo_libro_falla(self):
        self._crear_sacramento(numero=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                otro_folio = Folio.objects.create(libro=self.libro, numero_folio=2)
                self._crear_sacramento(numero=1, folio=otro_folio)

    def test_mismo_numero_en_otro_libro_pasa(self):
        self._crear_sacramento(numero=1)
        otro_libro = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        otro_folio = Folio.objects.create(libro=otro_libro, numero_folio=1)
        self._crear_sacramento(libro=otro_libro, folio=otro_folio, numero=1)
        self.assertEqual(Sacramento.objects.filter(numero=1).count(), 2)

    def test_partida_nueva_en_libro_cerrado_falla(self):
        self._crear_sacramento(numero=1)
        cerrar_libro(self.libro, self.ministro, date(2026, 7, 1))
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=2,
            fecha=date(2026, 3, 16),
            fecha_registro=date(2026, 3, 16),
            parroquia=self.parroquia,
        )
        with self.assertRaises(ValidationError) as contexto:
            sacramento.clean()
        self.assertIn("cerrado", str(contexto.exception))

    def test_partida_existente_en_libro_cerrado_editable(self):
        sacramento = self._crear_sacramento(numero=1)
        cerrar_libro(self.libro, self.ministro, date(2026, 7, 1))
        sacramento.observaciones = "Corrección menor"
        sacramento.clean()
        sacramento.save(update_fields=["observaciones"])
        self.assertEqual(sacramento.observaciones, "Corrección menor")

    def test_fecha_registro_anterior_a_la_apertura_falla(self):
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=2,
            fecha=date(2026, 3, 15),
            fecha_registro=date(2025, 12, 31),
            parroquia=self.parroquia,
        )
        with self.assertRaises(ValidationError) as contexto:
            sacramento.clean()
        self.assertIn("apertura", str(contexto.exception))

    def test_fecha_registro_posterior_al_cierre_falla(self):
        sacramento = self._crear_sacramento(numero=1)
        cerrar_libro(self.libro, self.ministro, date(2026, 7, 1))
        sacramento.fecha = date(2026, 8, 1)
        sacramento.fecha_registro = date(2026, 8, 1)
        with self.assertRaises(ValidationError) as contexto:
            sacramento.clean()
        self.assertIn("cierre", str(contexto.exception))

    def test_folio_de_otro_libro_falla(self):
        otro_libro = Libro.objects.create(
            nombre="Matrimonios 2026",
            tipo_libro=TipoLibro.MATRIMONIOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            parroquia=self.parroquia,
        )
        otro_folio = Folio.objects.create(libro=otro_libro, numero_folio=1)
        sacramento = Sacramento(
            tipo=TipoSacramento.BAUTISMO,
            fiel=self.fiel,
            libro=self.libro,
            folio=otro_folio,
            numero=2,
            fecha=date(2026, 3, 16),
            fecha_registro=date(2026, 3, 16),
            parroquia=self.parroquia,
        )
        with self.assertRaises(ValidationError) as contexto:
            sacramento.clean()
        self.assertIn("pertenecer", str(contexto.exception))


class ServiciosLibroTests(BaseSacramentosTests):
    def test_siguiente_numero_partida_vacio(self):
        self.assertEqual(siguiente_numero_partida(self.libro), 1)

    def test_siguiente_numero_partida_con_datos(self):
        self._crear_sacramento(numero=1)
        self._crear_sacramento(numero=3)
        self.assertEqual(siguiente_numero_partida(self.libro), 4)

    def test_folio_sugerido_vacio(self):
        self.assertEqual(folio_sugerido(self.libro), 1)

    def test_folio_sugerido_con_datos(self):
        folio_2 = Folio.objects.create(libro=self.libro, numero_folio=2)
        self._crear_sacramento(numero=1, folio=self.folio)
        self._crear_sacramento(
            numero=2,
            folio=folio_2,
            fecha=date(2026, 4, 1),
            fecha_registro=date(2026, 4, 1),
        )
        self.assertEqual(folio_sugerido(self.libro), 2)

    def test_cerrar_libro_correcto(self):
        self._crear_sacramento(numero=1)
        libro = cerrar_libro(self.libro, self.ministro, date(2026, 7, 1), nota="Cierre normal")
        self.assertEqual(libro.estado, EstadoLibro.CERRADO)
        self.assertEqual(libro.fecha_cierre, date(2026, 7, 1))
        self.assertEqual(libro.ministro_cierre, self.ministro)
        self.assertEqual(libro.nota_cierre, "Cierre normal")

    def test_cerrar_libro_ya_cerrado_falla(self):
        self._crear_sacramento(numero=1)
        cerrar_libro(self.libro, self.ministro, date(2026, 7, 1))
        with self.assertRaises(ValidationError) as contexto:
            cerrar_libro(self.libro, self.ministro, date(2026, 8, 1))
        self.assertIn("ya está cerrado", str(contexto.exception))

    def test_cerrar_libro_anterior_a_ultima_partida_falla(self):
        self._crear_sacramento(numero=1, fecha_registro=date(2026, 3, 15))
        with self.assertRaises(ValidationError) as contexto:
            cerrar_libro(self.libro, self.ministro, date(2026, 2, 1))
        self.assertIn("anterior", str(contexto.exception))

    def test_cerrar_libro_anterior_a_la_apertura_falla(self):
        with self.assertRaises(ValidationError) as contexto:
            cerrar_libro(self.libro, self.ministro, date(2025, 1, 1))
        self.assertIn("apertura", str(contexto.exception))

    def test_indice_libro_ordenado_sin_anuladas_y_matrimonio_en_dos_entradas(self):
        fiel_alvarez = self._crear_fiel(numero_documento="901", apellidos="Alvarez")
        fiel_zapata = self._crear_fiel(numero_documento="902", apellidos="Zapata")
        fiel_anulado = self._crear_fiel(numero_documento="903", apellidos="Gomez")
        self._crear_sacramento(numero=1, fiel=fiel_alvarez)
        self._crear_sacramento(numero=3, fiel=fiel_zapata)
        self._crear_sacramento(numero=5, fiel=fiel_anulado, estado=EstadoRegistro.ANULADO)

        fiel_castro = self._crear_fiel(numero_documento="904", apellidos="Castro")
        fiel_torres = self._crear_fiel(numero_documento="905", apellidos="Torres")
        sacramento_matrimonio = self._crear_sacramento(
            numero=7, tipo=TipoSacramento.MATRIMONIO, fiel=None
        )
        matrimonio = self._crear_matrimonio(sacramento=sacramento_matrimonio)
        self._crear_contrayente(matrimonio, fiel_castro, Sexo.HOMBRE)
        self._crear_contrayente(matrimonio, fiel_torres, Sexo.MUJER)

        indice = indice_libro(self.libro)
        self.assertEqual(
            [entrada["apellidos"] for entrada in indice],
            ["Alvarez", "Castro", "Torres", "Zapata"],
        )
        self.assertNotIn("Gomez", [entrada["apellidos"] for entrada in indice])
        entradas_matrimonio = [entrada for entrada in indice if entrada["numero"] == 7]
        self.assertEqual(len(entradas_matrimonio), 2)
        self.assertEqual(
            {entrada["apellidos"] for entrada in entradas_matrimonio}, {"Castro", "Torres"}
        )

    def test_indice_libro_numero_de_consultas_constante(self):
        def consultas(libro):
            with CaptureQueriesContext(connection) as contexto:
                indice_libro(libro)
            return len(contexto.captured_queries)

        def crear_libro(nombre, n_bautismos, n_matrimonios, prefijo):
            parroquia = Parroquia.objects.create(
                nombre=nombre, municipio=self.municipio, direccion="Otra"
            )
            libro = Libro.objects.create(
                nombre=nombre,
                tipo_libro=TipoLibro.BAUTISMOS,
                detalle="Registro",
                fecha_apertura=date(2026, 1, 1),
                parroquia=parroquia,
            )
            folio = Folio.objects.create(libro=libro, numero_folio=1)
            for i in range(1, n_bautismos + 1):
                fiel = self._crear_fiel(numero_documento=f"{prefijo}B{i}", apellidos=f"Apellido{i}")
                Sacramento.objects.create(
                    tipo=TipoSacramento.BAUTISMO,
                    fiel=fiel,
                    libro=libro,
                    folio=folio,
                    numero=i,
                    fecha=date(2026, 3, 15),
                    fecha_registro=date(2026, 3, 15),
                    parroquia=parroquia,
                )
            for j in range(1, n_matrimonios + 1):
                numero = n_bautismos + j
                sacramento_matrimonio = Sacramento.objects.create(
                    tipo=TipoSacramento.MATRIMONIO,
                    fiel=None,
                    libro=libro,
                    folio=folio,
                    numero=numero,
                    fecha=date(2026, 5, 20),
                    fecha_registro=date(2026, 5, 20),
                    parroquia=parroquia,
                )
                matrimonio = Matrimonio.objects.create(
                    sacramento=sacramento_matrimonio,
                    expediente=200 + j,
                    fecha_declaracion=date(2026, 5, 20),
                )
                self._crear_contrayente(
                    matrimonio,
                    self._crear_fiel(numero_documento=f"{prefijo}C{j}1", apellidos="Castro"),
                    Sexo.HOMBRE,
                )
                self._crear_contrayente(
                    matrimonio,
                    self._crear_fiel(numero_documento=f"{prefijo}C{j}2", apellidos="Rios"),
                    Sexo.MUJER,
                )
            return libro

        libro_pequeno = crear_libro("Parroquia Pequeña", 1, 0, "1")
        libro_grande = crear_libro("Parroquia Grande", 4, 3, "9")

        self.assertEqual(consultas(libro_pequeno), 2)
        self.assertEqual(consultas(libro_grande), 4)
