import shutil
import tempfile
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

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
from parroquias.models import Folio, Libro, Ministro, Parroquia
from parroquias.services import (
    cerrar_libro,
    indice_libro,
    siguiente_numero_partida,
)
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from ubicacion.models import Departamento, Municipio, Pais

from .forms import BautismoEditarForm, BautismoForm
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
    PartidaEliminada,
    PrimeraComunion,
    ProclamaMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)
from .services import (
    anular_bautismo,
    corregir_bautismo,
    eliminar_bautismo,
    motivo_no_eliminable,
    puede_eliminarse,
    registrar_bautismo,
    registrar_historial,
)


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
            documento=self._crear_documento("1234567890"),
            nombre="Carlos",
            apellido="Gómez",
            cargo=CargoMinisterial.PARROCO,
        )
        self.padre = Padre.objects.create(
            documento=self._crear_documento("11111111"), nombre="José", apellido="Pérez"
        )
        self.madre = Madre.objects.create(
            documento=self._crear_documento("22222222"), nombre="María", apellido="Gómez"
        )
        self.padrino = Padrino.objects.create(
            documento=self._crear_documento("33333333"), nombre="Pedro López"
        )
        self.fiel = self._crear_fiel()

    def _crear_documento(self, numero_documento, tipo_documento=TipoDocumento.CC):
        documento, _ = Documento.objects.get_or_create(
            tipo_documento=tipo_documento, numero_documento=numero_documento
        )
        return documento

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
            municipio_bautismo=self.municipio,
            libro_bautismo=2,
            folio_bautismo=5,
            numero_bautismo=12,
            observaciones_bautismo="Bautizado en la capilla",
        )
        self.assertEqual(confirmacion.fecha_bautismo, date(2000, 6, 10))
        self.assertEqual(confirmacion.parroquia_bautismo, "Parroquia La Catedral")
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
            municipio_bautismo=self.municipio,
            libro_bautismo=2,
            folio_bautismo=8,
            numero_bautismo=12,
        )
        self.assertEqual(primera.fecha_bautismo, date(2018, 8, 30))
        self.assertEqual(primera.parroquia_bautismo, "Parroquia San José")
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


class BautismoBaseTests(TestCase):
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
            estado=EstadoLibro.ABIERTO,
            parroquia=self.parroquia,
        )
        self.folio = Folio.objects.create(libro=self.libro, numero_folio=1)
        self.ministro = Ministro.objects.create(
            documento=self._crear_documento("1234567890"),
            nombre="Carlos",
            apellido="Gómez",
            cargo=CargoMinisterial.PARROCO,
        )
        self.parroco = Ministro.objects.create(
            documento=self._crear_documento("7777777777"),
            nombre="Pedro",
            apellido="Ruiz",
            cargo=CargoMinisterial.PARROCO,
            parroquia=self.parroquia,
        )
        self.libro.parroco_responsable = self.parroco
        self.libro.save()
        self.padre = Padre.objects.create(
            documento=self._crear_documento("11111111"), nombre="José", apellido="Pérez"
        )
        self.madre = Madre.objects.create(
            documento=self._crear_documento("22222222"), nombre="María", apellido="Gómez"
        )
        self.padrino = Padrino.objects.create(
            documento=self._crear_documento("33333333"), nombre="Pedro López"
        )
        self.usuario = self._crear_usuario()

    def _crear_documento(self, numero_documento, tipo_documento=TipoDocumento.CC):
        documento, _ = Documento.objects.get_or_create(
            tipo_documento=tipo_documento, numero_documento=numero_documento
        )
        return documento

    def _crear_usuario(self, username="admin", password="admin123", **kwargs):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User(username=username, **kwargs)
        user.set_password(password)
        user.save()
        return user

    def _datos_completos(self, **extra):
        return {
            "fiel_nombres": "Luis",
            "fiel_apellidos": "Martínez Díaz",
            "fiel_tipo_documento": TipoDocumento.CC,
            "fiel_numero_documento": "12345678",
            "fiel_fecha_nacimiento": date(2015, 5, 10),
            "fiel_sexo": Sexo.HOMBRE,
            "fiel_municipio_nacimiento": self.municipio.id,
            "padre_tipo_documento": TipoDocumento.CC,
            "padre_numero_documento": "11111111",
            "padre_nombre": "José",
            "padre_apellido": "Pérez",
            "madre_tipo_documento": TipoDocumento.CC,
            "madre_numero_documento": "22222222",
            "madre_nombre": "María",
            "madre_apellido": "Gómez",
            "padrino_tipo_documento": TipoDocumento.CC,
            "padrino_numero_documento": "33333333",
            "padrino_nombre": "Pedro López",
            "libro": self.libro,
            "fecha": date(2026, 6, 15),
            "ministro": self.ministro,
            "quien_firma": self.parroco,
            "doy_fe": self.parroco,
            "tipo_hijo": TipoHijo.BIOLOGICO,
            "testigo_nombre": "",
            "abuelo_paterno": "",
            "abuela_paterna": "",
            "abuelo_materno": "",
            "abuela_materna": "",
            "padre_biologico_nombre": "",
            "madre_biologica_nombre": "",
            "observaciones": "",
            **extra,
        }

    def _datos_post(self, **extra):
        """Igual que ``_datos_completos`` pero con PK en los campos de modelo."""
        datos = self._datos_completos(**extra)
        for campo in ("libro", "ministro", "quien_firma", "doy_fe"):
            if hasattr(datos[campo], "pk"):
                datos[campo] = datos[campo].pk
        return datos

    def _registrar_bautismo_desde_form(self, **extra):
        form = BautismoForm(self._datos_completos(**extra))
        self.assertTrue(form.is_valid(), form.errors)
        return registrar_bautismo(form.datos_para_servicio(), self.usuario)


class BautismoServiceTests(BautismoBaseTests):
    def test_registrar_bautismo_crea_sacramento_y_bautismo(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)
        bautismo, reutilizadas = registrar_bautismo(form.datos_para_servicio(), self.usuario)
        self.assertIsNotNone(bautismo)
        self.assertEqual(bautismo.sacramento.tipo, TipoSacramento.BAUTISMO)
        self.assertEqual(bautismo.sacramento.fiel.nombres, "Luis")
        self.assertIsInstance(reutilizadas, list)

    def test_registrar_bautismo_reutiliza_personas_existentes(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)
        registrar_bautismo(form.datos_para_servicio(), self.usuario)
        total_padres = Padre.objects.count()
        total_madres = Madre.objects.count()
        total_padrinos = Padrino.objects.count()

        # Otro bautizado (nuevo fiel) con los mismos padres y padrino: se
        # reutilizan las personas ya registradas sin duplicarlas.
        form2 = BautismoForm(
            self._datos_completos(
                fiel_numero_documento="87654321",
                fiel_nombres="Sofia",
                fiel_apellidos="Martínez Díaz",
            )
        )
        self.assertTrue(form2.is_valid(), form2.errors)
        bautismo2, _ = registrar_bautismo(form2.datos_para_servicio(), self.usuario)

        self.assertEqual(bautismo2.padre, self.padre)
        self.assertEqual(bautismo2.madre, self.madre)
        self.assertEqual(bautismo2.padrino, self.padrino)
        self.assertEqual(Padre.objects.count(), total_padres)
        self.assertEqual(Madre.objects.count(), total_madres)
        self.assertEqual(Padrino.objects.count(), total_padrinos)

    def test_registrar_bautismo_guarda_historial_creacion(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)
        bautismo, _ = registrar_bautismo(form.datos_para_servicio(), self.usuario)
        hist = HistorialSacramento.objects.filter(sacramento=bautismo.sacramento).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.accion, AccionHistorial.CREACION)
        self.assertEqual(hist.usuario, self.usuario)

    def test_registrar_bautismo_asigna_numero_y_folio(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)
        bautismo, _ = registrar_bautismo(form.datos_para_servicio(), self.usuario)
        self.assertIsNotNone(bautismo.sacramento.numero)
        self.assertIsNotNone(bautismo.sacramento.folio)

    def test_registrar_bautismo_full_clean_ejecutado(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)
        datos = form.datos_para_servicio()
        datos["partida"]["fecha"] = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            registrar_bautismo(datos, self.usuario)


class BautismoFormTests(BautismoBaseTests):
    def test_formulario_valido(self):
        form = BautismoForm(self._datos_completos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_requiere_testigo_si_no_hay_padrino_ni_madrina(self):
        datos = self._datos_completos(
            padrino_numero_documento="",
            padrino_nombre="",
            testigo_nombre="",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())

    def test_form_normaliza_documentos(self):
        datos = self._datos_completos(fiel_numero_documento="12345678-")
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["fiel_numero_documento"], "12345678")

    def test_form_requiere_datos_padres(self):
        datos = self._datos_completos(padre_nombre="")
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())

    def test_form_sexo_obligatorio(self):
        datos = self._datos_completos(fiel_sexo="")
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())

    def test_form_fechas_futuras_rechazadas(self):
        hoy = timezone.localdate()
        futuro = hoy.replace(year=hoy.year + 1)
        datos1 = self._datos_completos(fiel_fecha_nacimiento=futuro)
        form1 = BautismoForm(datos1)
        self.assertFalse(form1.is_valid())
        datos2 = self._datos_completos(fecha=futuro)
        form2 = BautismoForm(datos2)
        self.assertFalse(form2.is_valid())

    def test_form_nacimiento_posterior_bautismo(self):
        datos = self._datos_completos(
            fiel_fecha_nacimiento=date(2026, 6, 15), fecha=date(2026, 6, 10)
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())

    def test_form_tipo_hijo_adoptivo_requiere_biologicos(self):
        datos = self._datos_completos(
            tipo_hijo=TipoHijo.ADOPTIVO,
            padre_biologico_nombre="",
            madre_biologica_nombre="",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        datos2 = self._datos_completos(
            tipo_hijo=TipoHijo.ADOPTIVO,
            padre_biologico_nombre="Pedro Pérez",
            madre_biologica_nombre="María Gómez",
        )
        form2 = BautismoForm(datos2)
        self.assertTrue(form2.is_valid(), form2.errors)

    def test_form_tipo_hijo_biologico_no_requiere_biologicos(self):
        datos = self._datos_completos(
            tipo_hijo=TipoHijo.BIOLOGICO,
            padre_biologico_nombre="",
            madre_biologica_nombre="",
        )
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["padre_biologico_nombre"], "")
        self.assertEqual(form.cleaned_data["madre_biologica_nombre"], "")

    def test_form_padrino_madrina_distintos(self):
        datos = self._datos_completos(
            padrino_numero_documento="999000001",
            madrina_numero_documento="999000001",
            madrina_nombre="Ana López",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())

    def test_form_padrino_no_puede_ser_padre(self):
        datos = self._datos_completos(
            padre_numero_documento="999000001",
            padrino_numero_documento="999000001",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())


class BautismoViewsTests(BautismoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_lista_bautismos_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertNotEqual(response.status_code, 200)

    def test_lista_muestra_bautismos(self):
        self._registrar_bautismo_desde_form()
        response = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis")

    def test_crear_bautismo_get(self):
        response = self.client.get(reverse("sacramentos:bautismo_crear"))
        self.assertEqual(response.status_code, 200)

    def test_crear_bautismo_post_valido(self):
        response = self.client.post(reverse("sacramentos:bautismo_crear"), self._datos_post())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Bautismo.objects.exists())

    def test_crear_bautismo_post_invalido(self):
        response = self.client.post(reverse("sacramentos:bautismo_crear"), {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Bautismo.objects.exists())

    def test_detalle_bautismo(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        response = self.client.get(reverse("sacramentos:bautismo_detalle", args=[bautismo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis")

    def test_detalle_bautismo_404(self):
        response = self.client.get(reverse("sacramentos:bautismo_detalle", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_api_persona_sesion_requerida(self):
        self.client.logout()
        response = self.client.get(reverse("personas:api_persona"))
        self.assertNotEqual(response.status_code, 200)

    def test_api_persona_falta_datos(self):
        response = self.client.get(reverse("personas:api_persona"))
        self.assertEqual(response.status_code, 400)

    def test_api_persona_no_encontrado(self):
        response = self.client.get(
            reverse("personas:api_persona"),
            {"rol": "fiel", "tipo": TipoDocumento.CC, "numero": "00000000"},
        )
        self.assertEqual(response.status_code, 404)

    def test_api_persona_fiel_encontrado_solo_campos_indicados(self):
        Fiel.objects.create(
            documento=self._crear_documento("55555555"),
            nombres="Juan",
            apellidos="Pérez",
            fecha_nacimiento=date(2000, 1, 1),
            municipio_nacimiento=self.municipio,
            sexo=Sexo.HOMBRE,
        )
        response = self.client.get(
            reverse("personas:api_persona"),
            {"rol": "fiel", "tipo": TipoDocumento.CC, "numero": "55555555"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["encontrado"])
        self.assertEqual(
            set(payload.keys()),
            {"encontrado", "nombres", "apellidos", "fecha_nacimiento", "municipio", "sexo"},
        )

    def test_lista_bautismos_n1(self):
        self._registrar_bautismo_desde_form()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 12)


class BautismoN1Tests(BautismoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_detalle_bautismos_n1(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("sacramentos:bautismo_detalle", args=[bautismo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 20)


class BautismoPartidaAutomaticaTests(BautismoBaseTests):
    def test_registro_asigna_fecha_registro_de_hoy(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.assertEqual(bautismo.sacramento.fecha_registro, timezone.localdate())

    def test_registro_asigna_el_primer_folio_del_libro(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.assertEqual(bautismo.sacramento.folio.numero_folio, 1)

    def test_usa_el_mismo_folio_hasta_llenarlo(self):
        self.libro.partidas_por_folio = 2
        self.libro.save()
        primero, _ = self._registrar_bautismo_desde_form()
        segundo, _ = self._registrar_bautismo_desde_form(fiel_numero_documento="87654321")
        tercero, _ = self._registrar_bautismo_desde_form(fiel_numero_documento="55555555")
        self.assertEqual(primero.sacramento.folio.numero_folio, 1)
        self.assertEqual(segundo.sacramento.folio.numero_folio, 1)
        self.assertEqual(tercero.sacramento.folio.numero_folio, 2)

    def test_libro_lleno_lanza_error_y_no_crea_nada(self):
        self.libro.total_folios = 1
        self.libro.partidas_por_folio = 1
        self.libro.save()
        self._registrar_bautismo_desde_form()
        with self.assertRaises(ValidationError):
            self._registrar_bautismo_desde_form(fiel_numero_documento="87654321")
        self.assertEqual(Sacramento.objects.filter(libro=self.libro).count(), 1)


class BautismoCorreccionTests(BautismoBaseTests):
    def _corregir(self, bautismo, motivo="Se corrige el nombre", **extra):
        datos = self._datos_completos(**extra)
        datos["motivo"] = motivo
        form = BautismoEditarForm(datos, bautismo=bautismo)
        self.assertTrue(form.is_valid(), form.errors)
        return corregir_bautismo(
            bautismo,
            form.datos_para_servicio(),
            self.usuario,
            form.cleaned_data["motivo"],
        )

    def test_corregir_actualiza_datos_y_marca_corregido(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo, fiel_fecha_nacimiento=date(2016, 1, 1))
        bautismo.refresh_from_db()
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.fiel.fecha_nacimiento, date(2016, 1, 1))
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.CORREGIDO)

    def test_corregir_no_permite_cambiar_el_nombre_del_fiel(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo, fiel_nombres="Otro Nombre")
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.fiel.nombres, "Luis")

    def test_corregir_no_cambia_ubicacion_en_el_libro_ni_fecha_registro(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        folio = bautismo.sacramento.folio
        numero = bautismo.sacramento.numero
        fecha_registro = bautismo.sacramento.fecha_registro
        self._corregir(bautismo, fiel_fecha_nacimiento=date(2016, 1, 1))
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.folio, folio)
        self.assertEqual(bautismo.sacramento.numero, numero)
        self.assertEqual(bautismo.sacramento.fecha_registro, fecha_registro)

    def test_corregir_guarda_historial_y_anotacion(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo, motivo="Error en el apellido")
        historial = HistorialSacramento.objects.filter(
            sacramento=bautismo.sacramento, accion=AccionHistorial.CORRECCION
        )
        self.assertTrue(historial.exists())
        self.assertEqual(historial.first().descripcion, "Error en el apellido")
        self.assertEqual(historial.first().usuario, self.usuario)
        anotacion = AnotacionMarginal.objects.filter(
            sacramento=bautismo.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
        )
        self.assertTrue(anotacion.exists())

    def test_corregir_partida_anulada_lanza_error(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        with self.assertRaises(ValidationError):
            self._corregir(bautismo)


class BautismoEditarFormTests(BautismoBaseTests):
    def _crear_otra_partida_del_mismo_fiel(self, fiel):
        return Sacramento.objects.create(
            tipo=TipoSacramento.CONFIRMACION,
            fiel=fiel,
            libro=self.libro,
            folio=self.folio,
            numero=99,
            fecha=date(2026, 6, 16),
            fecha_registro=date(2026, 6, 16),
            parroquia=self.parroquia,
        )

    def test_bloquea_nombres_y_documentos_de_personas_vinculadas(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        form = BautismoEditarForm(bautismo=bautismo)
        bloqueados = (
            "fiel_tipo_documento",
            "fiel_numero_documento",
            "fiel_nombres",
            "fiel_apellidos",
            "padre_tipo_documento",
            "padre_numero_documento",
            "padre_nombre",
            "padre_apellido",
            "madre_tipo_documento",
            "madre_numero_documento",
            "madre_nombre",
            "madre_apellido",
            "padrino_tipo_documento",
            "padrino_numero_documento",
            "padrino_nombre",
        )
        for campo in bloqueados:
            self.assertTrue(form.fields[campo].disabled, campo)

    def test_datos_no_identitarios_del_fiel_siguen_editables(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        form = BautismoEditarForm(bautismo=bautismo)
        for campo in ("fiel_fecha_nacimiento", "fiel_sexo", "fiel_telefono"):
            self.assertFalse(form.fields[campo].disabled, campo)

    def test_persona_no_vinculada_queda_editable(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.assertIsNone(bautismo.madrina_id)
        form = BautismoEditarForm(bautismo=bautismo)
        self.assertFalse(form.fields["madrina_nombre"].disabled)
        self.assertFalse(form.fields["madrina_tipo_documento"].disabled)

    def test_aviso_partidas_sin_otras_partidas(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        form = BautismoEditarForm(bautismo=bautismo)
        self.assertEqual(form.aviso_partidas, 0)

    def test_aviso_partidas_cuenta_otras_partidas(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._crear_otra_partida_del_mismo_fiel(bautismo.sacramento.fiel)
        form = BautismoEditarForm(bautismo=bautismo)
        self.assertEqual(form.aviso_partidas, 1)


class BautismoAnulacionTests(BautismoBaseTests):
    def test_anular_marca_estado_y_guarda_historial_y_anotacion(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Partida duplicada")
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ANULADO)
        self.assertTrue(
            HistorialSacramento.objects.filter(
                sacramento=bautismo.sacramento, accion=AccionHistorial.ANULACION
            ).exists()
        )
        self.assertTrue(
            AnotacionMarginal.objects.filter(
                sacramento=bautismo.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
            ).exists()
        )

    def test_anular_partida_ya_anulada_lanza_error(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        with self.assertRaises(ValidationError):
            anular_bautismo(bautismo, self.usuario, "Otra vez")

    def test_anulada_no_aparece_en_el_indice_del_libro(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        indice_antes = indice_libro(self.libro)
        self.assertEqual(len(indice_antes), 1)
        anular_bautismo(bautismo, self.usuario, "Anulada")
        self.assertEqual(indice_libro(self.libro), [])


class BautismoEliminacionTests(BautismoBaseTests):
    def _corregir(self, bautismo):
        datos = self._datos_completos(fiel_fecha_nacimiento=date(2016, 1, 1))
        datos["motivo"] = "Corrección"
        form = BautismoEditarForm(datos, bautismo=bautismo)
        self.assertTrue(form.is_valid(), form.errors)
        return corregir_bautismo(
            bautismo, form.datos_para_servicio(), self.usuario, form.cleaned_data["motivo"]
        )

    def _crear_anotacion(self, **extra):
        datos = {
            "tipo": TipoAnotacionMarginal.CORRECCION,
            "fecha": timezone.localdate(),
            "descripcion": "Nota",
            **extra,
        }
        return AnotacionMarginal.objects.create(**datos)

    def test_eliminar_ultima_activa_de_hoy_crea_snapshot_y_libera_numero(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        sacramento = bautismo.sacramento
        numero = sacramento.numero
        folio_numero = sacramento.folio.numero_folio
        pk = bautismo.pk
        sacramento_pk = sacramento.pk
        self.assertTrue(puede_eliminarse(bautismo))
        self.assertIsNone(motivo_no_eliminable(bautismo))

        eliminar_bautismo(bautismo, self.usuario, "Partida duplicada")

        self.assertFalse(Sacramento.objects.filter(pk=sacramento_pk).exists())
        self.assertFalse(Bautismo.objects.filter(pk=pk).exists())
        partida = PartidaEliminada.objects.get()
        self.assertEqual(partida.numero, numero)
        self.assertEqual(partida.folio_numero, folio_numero)
        self.assertEqual(partida.motivo, "Partida duplicada")
        self.assertEqual(partida.eliminado_por, self.usuario)
        self.assertIn("Luis", partida.resumen)

        # El siguiente registro reutiliza el número y el folio liberados.
        nuevo, _ = self._registrar_bautismo_desde_form()
        self.assertEqual(nuevo.sacramento.numero, numero)
        self.assertEqual(nuevo.sacramento.folio.numero_folio, folio_numero)

    def test_no_elimina_partida_anulada(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        with self.assertRaisesMessage(ValidationError, "Las partidas anuladas no se eliminan"):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_partida_corregida(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo)
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertEqual(
            motivo_no_eliminable(bautismo),
            "Las partidas corregidas no se eliminan, quedan como constancia",
        )
        with self.assertRaisesMessage(ValidationError, "Las partidas corregidas no se eliminan"):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_no_es_la_ultima(self):
        primero, _ = self._registrar_bautismo_desde_form()
        self._registrar_bautismo_desde_form(fiel_numero_documento="87654321", fiel_nombres="Sofia")
        with self.assertRaisesMessage(ValidationError, "última partida del libro"):
            eliminar_bautismo(primero, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=primero.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_no_se_registro_hoy(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        Sacramento.objects.filter(pk=bautismo.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        bautismo = Bautismo.objects.get(pk=bautismo.pk)
        with self.assertRaisesMessage(ValidationError, "registrada hoy"):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_tiene_anotacion_como_partida_anotada(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._crear_anotacion(sacramento=bautismo.sacramento, estado=EstadoAnotacion.ANOTADA)
        with self.assertRaisesMessage(ValidationError, "notas marginales"):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_es_origen_de_una_anotacion(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._crear_anotacion(sacramento_origen=bautismo.sacramento)
        with self.assertRaisesMessage(ValidationError, "notas marginales"):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())


class BautismoAccionesViewsTests(BautismoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _url(self, nombre, bautismo):
        return reverse(f"sacramentos:{nombre}", args=[bautismo.pk])

    def test_detalle_activo_elegible_muestra_editar_anular_y_eliminar(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        respuesta = self.client.get(self._url("bautismo_detalle", bautismo))
        self.assertContains(respuesta, self._url("bautismo_editar", bautismo))
        self.assertContains(respuesta, self._url("bautismo_anular", bautismo))
        self.assertContains(respuesta, self._url("bautismo_eliminar", bautismo))

    def test_detalle_anulado_no_permite_ninguna_accion(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("bautismo_detalle", bautismo))
        self.assertNotContains(respuesta, self._url("bautismo_editar", bautismo))
        self.assertNotContains(respuesta, self._url("bautismo_anular", bautismo))
        self.assertNotContains(respuesta, self._url("bautismo_eliminar", bautismo))

    def test_editar_get_y_post(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.assertEqual(self.client.get(self._url("bautismo_editar", bautismo)).status_code, 200)
        datos = self._datos_post(fiel_fecha_nacimiento=date(2016, 1, 1))
        datos["motivo"] = "Corrección de la fecha de nacimiento"
        respuesta = self.client.post(self._url("bautismo_editar", bautismo), datos)
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))
        bautismo.refresh_from_db()
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.fiel.fecha_nacimiento, date(2016, 1, 1))
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.CORREGIDO)

    def test_editar_partida_anulada_redirige(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("bautismo_editar", bautismo))
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))

    def test_editar_muestra_aviso_de_partidas_compartidas(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        Sacramento.objects.create(
            tipo=TipoSacramento.CONFIRMACION,
            fiel=bautismo.sacramento.fiel,
            libro=self.libro,
            folio=self.folio,
            numero=99,
            fecha=date(2026, 6, 16),
            fecha_registro=date(2026, 6, 16),
            parroquia=self.parroquia,
        )
        respuesta = self.client.get(self._url("bautismo_editar", bautismo))
        self.assertContains(
            respuesta,
            "Este cambio también se verá en las 1 partidas donde aparece esta persona.",
        )

    def test_acciones_inexistentes_dan_404(self):
        for nombre in ("bautismo_editar", "bautismo_anular", "bautismo_eliminar"):
            url = reverse(f"sacramentos:{nombre}", args=[999999])
            self.assertEqual(self.client.get(url).status_code, 404, nombre)

    def test_acciones_requieren_login(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.client.logout()
        for nombre in ("bautismo_editar", "bautismo_anular", "bautismo_eliminar"):
            url = self._url(nombre, bautismo)
            self.assertNotEqual(self.client.get(url).status_code, 200, nombre)
            self.assertNotEqual(self.client.post(url, {}).status_code, 200, nombre)

    def test_get_no_ejecuta_la_anulacion_ni_la_eliminacion(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.client.get(self._url("bautismo_anular", bautismo))
        self.client.get(self._url("bautismo_eliminar", bautismo))
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())

    def test_anular_post_sin_csrf_falla(self):
        from django.test import Client

        bautismo, _ = self._registrar_bautismo_desde_form()
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self._url("bautismo_anular", bautismo), {"motivo": "x"})
        self.assertEqual(respuesta.status_code, 403)
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ACTIVO)

    def test_editar_ignora_campos_protegidos_del_post(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        sacramento = bautismo.sacramento
        original = (
            sacramento.libro_id,
            sacramento.folio_id,
            sacramento.numero,
            sacramento.fecha_registro,
            sacramento.creado_por_id,
        )
        datos = self._datos_post(fiel_fecha_nacimiento=date(2016, 1, 1))
        datos["motivo"] = "Intento de manipular campos del sistema"
        datos.update(
            {
                "numero": 999,
                "folio": 999,
                "fecha_registro": date(2020, 1, 1),
                "estado": EstadoRegistro.ANULADO,
                "creado_por": 999,
                "modificado_por": 999,
            }
        )
        respuesta = self.client.post(self._url("bautismo_editar", bautismo), datos)
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))
        sacramento.refresh_from_db()
        self.assertEqual(
            (
                sacramento.libro_id,
                sacramento.folio_id,
                sacramento.numero,
                sacramento.fecha_registro,
                sacramento.creado_por_id,
            ),
            original,
        )
        self.assertEqual(sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertEqual(sacramento.modificado_por_id, self.usuario.pk)

    def test_anular_get_y_post(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self.assertEqual(self.client.get(self._url("bautismo_anular", bautismo)).status_code, 200)
        respuesta = self.client.post(
            self._url("bautismo_anular", bautismo), {"motivo": "Partida duplicada"}
        )
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ANULADO)

    def test_eliminar_partida_elegible_borra_y_redirige_a_la_lista(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        pk = bautismo.pk
        self.assertEqual(self.client.get(self._url("bautismo_eliminar", bautismo)).status_code, 200)
        respuesta = self.client.post(
            self._url("bautismo_eliminar", bautismo), {"motivo": "Se elimina"}
        )
        self.assertRedirects(respuesta, reverse("sacramentos:bautismo_lista"))
        self.assertFalse(Bautismo.objects.filter(pk=pk).exists())
        self.assertTrue(PartidaEliminada.objects.exists())

    def test_eliminar_partida_anulada_redirige_sin_borrar(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        anular_bautismo(bautismo, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("bautismo_eliminar", bautismo))
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))
        respuesta = self.client.post(
            self._url("bautismo_eliminar", bautismo), {"motivo": "Se intenta"}
        )
        self.assertRedirects(respuesta, self._url("bautismo_detalle", bautismo))
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_eliminar_partida_no_ultima_redirige_sin_borrar(self):
        primero, _ = self._registrar_bautismo_desde_form()
        self._registrar_bautismo_desde_form(fiel_numero_documento="87654321", fiel_nombres="Sofia")
        respuesta = self.client.post(
            self._url("bautismo_eliminar", primero), {"motivo": "Se intenta"}
        )
        self.assertRedirects(respuesta, self._url("bautismo_detalle", primero))
        self.assertTrue(Bautismo.objects.filter(pk=primero.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())
