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
    FinalidadCertificado,
    RelacionCertificado,
    RespuestaDoctrina,
    ResultadoProclama,
    RolUsuario,
    Sexo,
    SiNo,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from cuentas.models import PerfilUsuario
from parroquias.models import Folio, Libro, Ministro, Parroquia
from parroquias.services import (
    cerrar_libro,
    indice_libro,
    siguiente_numero_partida,
)
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from ubicacion.models import Departamento, Municipio, Pais

from .forms import (
    BautismoEditarForm,
    BautismoForm,
    PrimeraComunionEditarForm,
    PrimeraComunionForm,
)
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
from .reglas import (
    ADVIERTE,
    BLOQUEA,
    RECUERDA,
    MixinReglas,
    Regla,
    edad_en_fecha,
    evaluar_reglas,
)
from .services import (
    anular_bautismo,
    anular_primera_comunion,
    corregir_bautismo,
    corregir_primera_comunion,
    datos_certificado_primera_comunion,
    eliminar_bautismo,
    eliminar_primera_comunion,
    motivo_no_eliminable,
    puede_eliminarse,
    registrar_bautismo,
    registrar_historial,
    registrar_primera_comunion,
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

    def test_servicio_nombre_con_numeros_no_deja_nada_guardado(self):
        # full_clean en cada persona nueva: si una falla, la transacción no
        # deja ni documentos ni personas ni sacramentos a medias.
        documentos_antes = Documento.objects.count()
        with self.assertRaises(ValidationError):
            registrar_bautismo(
                {
                    "partida": {
                        "libro": self.libro,
                        "fecha": date(2026, 6, 15),
                        "parroquia": self.parroquia,
                        "ministro": self.ministro,
                        "observaciones": "",
                    },
                    "fiel": {
                        "tipo_documento": TipoDocumento.CC,
                        "numero_documento": "12345678",
                        "nombres": "Luis",
                        "apellidos": "Martínez Díaz",
                        "fecha_nacimiento": date(2015, 5, 10),
                        "municipio_nacimiento": self.municipio,
                        "telefono": "",
                        "sexo": Sexo.HOMBRE,
                    },
                    "padre": {
                        "tipo_documento": TipoDocumento.CC,
                        "numero_documento": "88888881",
                        "nombre": "Juan123",
                        "apellido": "Nuevo",
                    },
                    "madre": {},
                    "padrino": {},
                    "madrina": {},
                    "tipo_hijo": TipoHijo.BIOLOGICO,
                    "testigo_nombre": "",
                    "doy_fe": self.parroco,
                },
                self.usuario,
            )
        self.assertEqual(Documento.objects.count(), documentos_antes)
        self.assertFalse(Documento.objects.filter(numero_documento="88888881").exists())
        self.assertFalse(Padre.objects.filter(nombre="Juan123").exists())
        self.assertEqual(Sacramento.objects.count(), 0)

    def test_servicio_crea_cada_persona_nueva_una_sola_vez(self):
        form = BautismoForm(
            self._datos_completos(
                fiel_numero_documento="87654321",
                fiel_nombres="Sofia",
                padre_numero_documento="44444444",
                padre_nombre="Nuevo",
                padre_apellido="Padre",
                madre_numero_documento="55555555",
                madre_nombre="Nueva",
                madre_apellido="Madre",
                padrino_numero_documento="66666666",
                padrino_nombre="Nuevo Padrino",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        registrar_bautismo(form.datos_para_servicio(), self.usuario)
        for numero in ("87654321", "44444444", "55555555", "66666666"):
            self.assertEqual(Documento.objects.filter(numero_documento=numero).count(), 1, numero)
        self.assertEqual(Padre.objects.filter(nombre="Nuevo").count(), 1)
        self.assertEqual(Madre.objects.filter(nombre="Nueva").count(), 1)
        self.assertEqual(Padrino.objects.filter(nombre="Nuevo Padrino").count(), 1)

    def test_mismo_documento_como_padre_y_padrino_comparte_un_documento(self):
        self._registrar_bautismo_desde_form(
            fiel_numero_documento="87654321",
            fiel_nombres="Sofia",
            padre_numero_documento="44444444",
            padre_nombre="Compartido",
            padre_apellido="Documento",
        )
        self._registrar_bautismo_desde_form(
            fiel_numero_documento="55555555",
            fiel_nombres="Marta",
            padre_numero_documento="11111111",
            padrino_numero_documento="44444444",
            padrino_nombre="Compartido Documento",
        )
        documentos = Documento.objects.filter(numero_documento="44444444")
        self.assertEqual(documentos.count(), 1)
        self.assertTrue(Padre.objects.filter(documento=documentos.first()).exists())
        self.assertTrue(Padrino.objects.filter(documento=documentos.first()).exists())

    def test_fiel_que_ya_es_padrino_se_puede_bautizar_reutilizando_documento(self):
        Padrino.objects.create(
            documento=self._crear_documento("91111111"), nombre="Carlos Padrino Viejo"
        )
        form = BautismoForm(
            self._datos_completos(
                fiel_numero_documento="91111111",
                fiel_nombres="Carlos",
                fiel_apellidos="Padrino Viejo",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        bautismo, _ = registrar_bautismo(form.datos_para_servicio(), self.usuario)
        fiel = bautismo.sacramento.fiel
        self.assertEqual(fiel.nombres, "Carlos")
        self.assertEqual(fiel.apellidos, "Padrino Viejo")
        self.assertEqual(Documento.objects.filter(numero_documento="91111111").count(), 1)
        # El Padrino conserva su nombre: el servicio no sobrescribe.
        self.assertEqual(
            Padrino.objects.get(documento=fiel.documento).nombre, "Carlos Padrino Viejo"
        )


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
        datos = self._datos_completos(
            padre_numero_documento="88888881", padre_nombre="", padre_apellido=""
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("padre_nombre", form.errors)

    def test_form_no_requiere_nombre_de_padre_ya_registrado(self):
        datos = self._datos_completos(padre_nombre="", padre_apellido="")
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_no_requiere_nombre_de_padrino_ya_registrado(self):
        datos = self._datos_completos(padrino_nombre="")
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)

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

    def _fiel_con_sexo(self, numero, sexo):
        return Fiel.objects.create(
            documento=self._crear_documento(numero),
            nombres="Persona",
            apellidos=f"Conocida {numero}",
            fecha_nacimiento=date(1990, 1, 1),
            sexo=sexo,
        )

    def test_form_padrino_mujer_conocida_falla_en_el_campo(self):
        """c. 874: si el documento del padrino es de una fiel mujer, el form falla."""
        self._fiel_con_sexo("44444444", Sexo.MUJER)
        datos = self._datos_completos(
            padrino_numero_documento="44444444",
            padrino_nombre="Pedro Conocido",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("padrino_numero_documento", form.errors)
        self.assertIn("El padrino debe ser varón.", form.errors["padrino_numero_documento"])

    def test_form_madrina_varon_conocido_falla_en_el_campo(self):
        """c. 874: si el documento de la madrina es de un fiel varón, el form falla."""
        self._fiel_con_sexo("55555555", Sexo.HOMBRE)
        datos = self._datos_completos(
            madrina_tipo_documento=TipoDocumento.CC,
            madrina_numero_documento="55555555",
            madrina_nombre="Maria Conocida",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("madrina_numero_documento", form.errors)
        self.assertIn("La madrina debe ser mujer.", form.errors["madrina_numero_documento"])

    def test_form_padrino_varon_y_madrina_mujer_conocidos_son_validos(self):
        self._fiel_con_sexo("66666666", Sexo.HOMBRE)
        self._fiel_con_sexo("77777777", Sexo.MUJER)
        datos = self._datos_completos(
            padrino_numero_documento="66666666",
            padrino_nombre="Pedro Conocido",
            madrina_tipo_documento=TipoDocumento.CC,
            madrina_numero_documento="77777777",
            madrina_nombre="Maria Conocida",
        )
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_padrino_de_fiel_sin_sexo_no_falla(self):
        Fiel.objects.create(
            documento=self._crear_documento("88888888"),
            nombres="Sin",
            apellidos="Sexo Registrado",
            fecha_nacimiento=date(1990, 1, 1),
        )
        datos = self._datos_completos(
            padrino_numero_documento="88888888",
            padrino_nombre="Sin Sexo Registrado",
        )
        form = BautismoForm(datos)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_padre_mujer_conocida_falla_en_el_campo(self):
        self._fiel_con_sexo("98765432", Sexo.MUJER)
        datos = self._datos_completos(
            padre_numero_documento="98765432",
            padre_nombre="Pedro Conocido",
            padre_apellido="Conocida",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("padre_numero_documento", form.errors)
        self.assertIn("El padre debe ser varón.", form.errors["padre_numero_documento"])

    def test_form_madre_varon_conocido_falla_en_el_campo(self):
        self._fiel_con_sexo("98765431", Sexo.HOMBRE)
        datos = self._datos_completos(
            madre_numero_documento="98765431",
            madre_nombre="María Conocida",
            madre_apellido="Conocido",
        )
        form = BautismoForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("madre_numero_documento", form.errors)
        self.assertIn("La madre debe ser mujer.", form.errors["madre_numero_documento"])


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
            {
                "encontrado",
                "tipo_documento",
                "numero_documento",
                "nombres",
                "apellidos",
                "sexo_fiel",
                "editar_url",
                "fecha_nacimiento",
                "municipio",
                "sexo",
                "telefono",
                "bautismo_activo",
                "bautismo_referencia",
            },
        )
        self.assertFalse(payload["bautismo_activo"])

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

    def test_corregir_mismo_dia_deja_activa_y_solo_historial(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo, fiel_fecha_nacimiento=date(2016, 1, 1))
        bautismo.refresh_from_db()
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.fiel.fecha_nacimiento, date(2016, 1, 1))
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertTrue(
            HistorialSacramento.objects.filter(
                sacramento=bautismo.sacramento, accion=AccionHistorial.CORRECCION
            ).exists()
        )
        self.assertFalse(
            AnotacionMarginal.objects.filter(
                sacramento=bautismo.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
            ).exists()
        )

    def test_corregir_otro_dia_actualiza_datos_y_marca_corregido(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        Sacramento.objects.filter(pk=bautismo.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        bautismo.sacramento.refresh_from_db()
        self._corregir(bautismo, fiel_fecha_nacimiento=date(2016, 1, 1))
        bautismo.refresh_from_db()
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.fiel.fecha_nacimiento, date(2016, 1, 1))
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertTrue(
            AnotacionMarginal.objects.filter(
                sacramento=bautismo.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
            ).exists()
        )

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
        Sacramento.objects.filter(pk=bautismo.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        bautismo.sacramento.refresh_from_db()
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
        anotacion = AnotacionMarginal.objects.get(
            sacramento=bautismo.sacramento, tipo=TipoAnotacionMarginal.ANULACION
        )
        self.assertEqual(anotacion.get_tipo_display(), "Anulación")
        self.assertIn("Partida duplicada", anotacion.descripcion)
        self.assertIn("anulada", anotacion.descripcion)

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
        Sacramento.objects.filter(pk=bautismo.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        bautismo.sacramento.refresh_from_db()
        self._corregir(bautismo)
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertFalse(puede_eliminarse(bautismo))
        self.assertIsNotNone(motivo_no_eliminable(bautismo))
        with self.assertRaises(ValidationError):
            eliminar_bautismo(bautismo, self.usuario, "Se intenta")
        self.assertTrue(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_eliminable_si_se_corrige_el_mismo_dia(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        self._corregir(bautismo)
        bautismo.sacramento.refresh_from_db()
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertIsNone(motivo_no_eliminable(bautismo))
        self.assertTrue(puede_eliminarse(bautismo))
        eliminar_bautismo(bautismo, self.usuario, "Partida duplicada")
        self.assertFalse(Bautismo.objects.filter(pk=bautismo.pk).exists())
        self.assertTrue(PartidaEliminada.objects.exists())

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
        self.assertEqual(bautismo.sacramento.estado, EstadoRegistro.ACTIVO)

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
        self.assertEqual(sacramento.estado, EstadoRegistro.ACTIVO)
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


class BautismoPartidasBaseTests(BautismoBaseTests):
    """Utilidades para crear partidas de bautismo directamente en la base."""

    contador = 0

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _fiel(self, numero=None):
        if numero is None:
            type(self).contador += 1
            numero = f"7000000{type(self).contador}"
        return Fiel.objects.create(
            documento=self._crear_documento(numero),
            nombres="Fiel",
            apellidos=f"Prueba {numero}",
            fecha_nacimiento=date(2000, 1, 1),
        )

    def _crear_partida(
        self,
        *,
        libro=None,
        folio=None,
        numero=1,
        fecha=date(2026, 3, 15),
        estado=EstadoRegistro.ACTIVO,
        fiel=None,
        parroquia=None,
        tipo_hijo=TipoHijo.BIOLOGICO,
        **bautismo_extra,
    ):
        libro = libro or self.libro
        if folio is None:
            if libro == self.libro:
                folio = self.folio
            else:
                folio, _ = Folio.objects.get_or_create(libro=libro, defaults={"numero_folio": 1})
        sacramento = Sacramento.objects.create(
            tipo=TipoSacramento.BAUTISMO,
            fiel=fiel or self._fiel(),
            libro=libro,
            folio=folio,
            numero=numero,
            fecha=fecha,
            fecha_registro=fecha,
            parroquia=parroquia or self.parroquia,
            ministro=self.ministro,
            estado=estado,
        )
        datos = {
            "sacramento": sacramento,
            "padre": self.padre,
            "madre": self.madre,
            "tipo_hijo": tipo_hijo,
            "padrino": self.padrino,
            "quien_firma": self.parroco,
            "doy_fe": self.parroco,
        }
        datos.update(bautismo_extra)
        return Bautismo.objects.create(**datos)

    def _url_lista(self, parametros=None):
        url = reverse("sacramentos:bautismo_lista")
        if parametros:
            from django.utils.http import urlencode

            url += "?" + urlencode(parametros)
        return url


class BautismoListaVistaTests(BautismoPartidasBaseTests):
    def setUp(self):
        super().setUp()
        self.libro.numero_libro = 1
        self.libro.save()

    def test_lista_muestra_columnas_nuevas(self):
        self._crear_partida(numero=4)
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "<th>N.° de partida</th>", html=True)
        self.assertContains(respuesta, "<th>Fecha del bautismo</th>", html=True)
        self.assertContains(respuesta, "Registrar bautismo")
        self.assertContains(respuesta, "Ver partida")
        self.assertContains(respuesta, str(self.padre))

    def test_lista_sin_columna_parroquia_con_una_sola_parroquia(self):
        self._crear_partida()
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertNotContains(respuesta, ">Parroquia</th>")
        self.assertNotContains(respuesta, 'name="parroquia"')

    def test_lista_con_columna_y_filtro_parroquia_con_varias_parroquias(self):
        otra = Parroquia.objects.create(
            nombre="San José", municipio=self.municipio, direccion="Calle 9"
        )
        otro_libro = Libro.objects.create(
            nombre="Bautismos San José",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            numero_libro=2,
            fecha_apertura=date(2026, 1, 1),
            estado=EstadoLibro.ABIERTO,
            parroquia=otra,
        )
        self._crear_partida(numero=1)
        partida_otra = self._crear_partida(libro=otro_libro, numero=1, parroquia=otra)
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertContains(respuesta, ">Parroquia</th>")
        self.assertContains(respuesta, 'name="parroquia"')
        self.assertContains(respuesta, "San José")

        filtrada = self.client.get(self._url_lista({"parroquia": otra.pk}))
        self.assertEqual(list(filtrada.context["bautismos"]), [partida_otra])

    def test_lista_filtra_por_libro(self):
        otra = Parroquia.objects.create(
            nombre="San José", municipio=self.municipio, direccion="Calle 9"
        )
        otro_libro = Libro.objects.create(
            nombre="Bautismos San José",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            fecha_apertura=date(2026, 1, 1),
            estado=EstadoLibro.ABIERTO,
            parroquia=otra,
        )
        propia = self._crear_partida(numero=1)
        ajena = self._crear_partida(libro=otro_libro, numero=1, parroquia=otra)
        respuesta = self.client.get(self._url_lista({"libro": self.libro.pk}))
        self.assertEqual(list(respuesta.context["bautismos"]), [propia])
        self.assertNotIn(ajena, respuesta.context["bautismos"])

    def test_lista_filtra_por_anio(self):
        antigua = self._crear_partida(numero=1, fecha=date(2025, 6, 1))
        reciente = self._crear_partida(numero=2, fecha=date(2026, 6, 1))
        respuesta = self.client.get(self._url_lista({"anio": 2025}))
        self.assertEqual(list(respuesta.context["bautismos"]), [antigua])
        self.assertNotIn(reciente, respuesta.context["bautismos"])

    def test_lista_filtra_por_estado(self):
        activa = self._crear_partida(numero=1, estado=EstadoRegistro.ACTIVO)
        anulada = self._crear_partida(numero=2, estado=EstadoRegistro.ANULADO)
        respuesta = self.client.get(self._url_lista({"estado": EstadoRegistro.ANULADO}))
        self.assertEqual(list(respuesta.context["bautismos"]), [anulada])
        self.assertNotIn(activa, respuesta.context["bautismos"])

    def test_lista_filtros_combinados_y_enlace_limpiar(self):
        self._crear_partida(numero=1, fecha=date(2026, 6, 1), estado=EstadoRegistro.ACTIVO)
        self._crear_partida(numero=2, fecha=date(2026, 6, 2), estado=EstadoRegistro.ANULADO)
        self._crear_partida(numero=3, fecha=date(2025, 6, 3), estado=EstadoRegistro.ACTIVO)
        respuesta = self.client.get(
            self._url_lista({"anio": 2026, "estado": EstadoRegistro.ACTIVO})
        )
        numeros = [b.sacramento.numero for b in respuesta.context["bautismos"]]
        self.assertEqual(numeros, [1])
        self.assertContains(respuesta, "Limpiar filtros")

    def test_lista_estado_vacio_por_filtro(self):
        self._crear_partida(numero=1, fecha=date(2026, 1, 1))
        respuesta = self.client.get(self._url_lista({"anio": 1999}))
        self.assertContains(respuesta, "No hay resultados con estos filtros")

    def test_lista_ordena_por_libro_y_numero_descendente(self):
        otra = Parroquia.objects.create(
            nombre="San José", municipio=self.municipio, direccion="Calle 9"
        )
        libro_dos = Libro.objects.create(
            nombre="Bautismos 2027",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro",
            numero_libro=2,
            fecha_apertura=date(2027, 1, 1),
            estado=EstadoLibro.ABIERTO,
            parroquia=otra,
        )
        libro_dos_folio = Folio.objects.create(libro=libro_dos, numero_folio=1)
        self._crear_partida(numero=1, fecha=date(2026, 2, 1))
        self._crear_partida(numero=3, fecha=date(2026, 3, 1))
        self._crear_partida(numero=2, fecha=date(2026, 1, 1))
        nueva = self._crear_partida(
            libro=libro_dos, folio=libro_dos_folio, numero=1, parroquia=otra
        )
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        bautismos = list(respuesta.context["bautismos"])
        self.assertEqual(bautismos[0].pk, nueva.pk)
        self.assertEqual([b.sacramento.numero for b in bautismos[1:]], [3, 2, 1])

    def test_lista_pagina_de_25(self):
        for numero in range(1, 27):
            self._crear_partida(numero=numero)
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertTrue(respuesta.context["is_paginated"])
        self.assertEqual(len(respuesta.context["bautismos"]), 25)
        segunda = self.client.get(self._url_lista({"page": 2}))
        self.assertEqual(len(segunda.context["bautismos"]), 1)

    def test_lista_paginacion_conserva_los_filtros(self):
        for numero in range(1, 27):
            self._crear_partida(numero=numero, fecha=date(2026, 1, numero))
        respuesta = self.client.get(self._url_lista({"anio": 2026}))
        self.assertTrue(respuesta.context["is_paginated"])
        self.assertContains(respuesta, "anio=2026")

    def test_lista_numero_de_consultas_constante(self):
        self._crear_partida(numero=1)
        with CaptureQueriesContext(connection) as pocas:
            self.client.get(reverse("sacramentos:bautismo_lista"))
        for numero in range(2, 13):
            self._crear_partida(numero=numero)
        with CaptureQueriesContext(connection) as muchas:
            self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertEqual(len(pocas.captured_queries), len(muchas.captured_queries))

    def test_lista_requiere_login(self):
        self.client.logout()
        respuesta = self.client.get(reverse("sacramentos:bautismo_lista"))
        self.assertNotEqual(respuesta.status_code, 200)


class BautismoHojaTests(BautismoPartidasBaseTests):
    def _detalle(self, bautismo):
        return self.client.get(reverse("sacramentos:bautismo_detalle", args=[bautismo.pk]))

    def test_detalle_usa_el_parcial_de_la_hoja(self):
        bautismo = self._crear_partida(numero=5)
        respuesta = self._detalle(bautismo)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "sacramentos/partials/hoja_partida.html")

    def test_detalle_muestra_referencia_y_datos_ausentes(self):
        bautismo = self._crear_partida(numero=5)
        with override_settings(NOMBRE_PARROQUIA="San Pedro Claver"):
            respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, "PARTIDA DE BAUTISMO")
        self.assertContains(respuesta, "Libro de Bautismos")
        self.assertContains(respuesta, "Folio 1 · N.° 5")
        self.assertContains(respuesta, "En la Parroquia San Pedro Claver, se hace constar que:")
        self.assertContains(respuesta, "dato no presentado")
        self.assertContains(respuesta, "Sin notas marginales")

    def test_detalle_muestra_notas_marginales_y_franja_anulada(self):
        bautismo = self._crear_partida(numero=1)
        anular_bautismo(bautismo, self.usuario, "Partida duplicada")
        respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, "Notas marginales")
        self.assertContains(respuesta, "Anulación")
        self.assertContains(respuesta, "Partida duplicada")
        self.assertContains(respuesta, "ANULADA")
        self.assertContains(respuesta, "insignia-estado--anulado")

    def test_detalle_no_muestra_padres_biologicos(self):
        bautismo = self._crear_partida(
            numero=1,
            tipo_hijo=TipoHijo.ADOPTIVO,
            padre_biologico_nombre="Anacleto Biológico",
            madre_biologica_nombre="Berta Biológica",
        )
        respuesta = self._detalle(bautismo)
        self.assertNotContains(respuesta, "Anacleto Biológico")
        self.assertNotContains(respuesta, "Berta Biológica")
        self.assertContains(respuesta, str(self.padre))
        self.assertContains(respuesta, str(self.madre))

    def test_detalle_muestra_enlaces_a_las_fichas(self):
        fiel = self._fiel("80000001")
        bautismo = self._crear_partida(numero=1, fiel=fiel)
        respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, reverse("personas:ficha", args=[fiel.documento_id]))
        self.assertContains(respuesta, reverse("personas:ficha", args=[self.padre.documento_id]))

    def test_detalle_usa_nombre_parroquia_configurado(self):
        bautismo = self._crear_partida(numero=1)
        with override_settings(NOMBRE_PARROQUIA="Parroquia Configurada"):
            respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, "Parroquia Configurada")

    def test_detalle_corregido_muestra_editar_y_anular_sin_eliminar(self):
        bautismo, _ = self._registrar_bautismo_desde_form()
        Sacramento.objects.filter(pk=bautismo.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        bautismo.sacramento.refresh_from_db()
        datos = self._datos_completos()
        datos["motivo"] = "Corrección de datos"
        form = BautismoEditarForm(datos, bautismo=bautismo)
        self.assertTrue(form.is_valid(), form.errors)
        corregir_bautismo(
            bautismo,
            form.datos_para_servicio(),
            self.usuario,
            form.cleaned_data["motivo"],
        )
        respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, reverse("sacramentos:bautismo_editar", args=[bautismo.pk]))
        self.assertContains(respuesta, reverse("sacramentos:bautismo_anular", args=[bautismo.pk]))
        self.assertNotContains(
            respuesta, reverse("sacramentos:bautismo_eliminar", args=[bautismo.pk])
        )

    def test_detalle_muestra_documentos_como_hasta_ahora(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, str(bautismo.sacramento.fiel.documento))
        self.assertContains(respuesta, f"Pedro López ({self.padrino.documento})")
        self.assertContains(respuesta, f"José Pérez ({self.padre.documento})")

    def test_detalle_requiere_login(self):
        bautismo = self._crear_partida(numero=1)
        self.client.logout()
        self.assertNotEqual(self._detalle(bautismo).status_code, 200)


class BautismoCertificadoTests(BautismoPartidasBaseTests):
    """Certificado imprimible de bautismo: solicitud, cierre e historial."""

    def _url(self, bautismo):
        return reverse("sacramentos:bautismo_certificado", args=[bautismo.pk])

    def _detalle(self, bautismo):
        return self.client.get(reverse("sacramentos:bautismo_detalle", args=[bautismo.pk]))

    def _datos_solicitud(self, **extra):
        datos = {
            "solicitante": "María Solicitante",
            "tipo_documento": TipoDocumento.CC,
            "numero_documento": "12345678",
            "relacion": RelacionCertificado.PADRE_MADRE,
            "finalidad": FinalidadCertificado.MATRIMONIO,
            "finalidad_otro": "",
        }
        datos.update(extra)
        return datos

    def _hay_certificado_en_historial(self):
        return HistorialSacramento.objects.filter(accion=AccionHistorial.CERTIFICADO).exists()

    def test_certificado_requiere_login(self):
        bautismo = self._crear_partida(numero=1)
        self.client.logout()
        respuesta = self.client.get(self._url(bautismo))
        self.assertNotEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_404(self):
        respuesta = self.client.get(reverse("sacramentos:bautismo_certificado", args=[9999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_get_muestra_formulario(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.get(self._url(bautismo))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/solicitud_certificado.html")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_post_valido_emite_certificado_y_registra_historial(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/certificado.html")
        self.assertContains(respuesta, "María Solicitante")
        self.assertContains(respuesta, "Matrimonio")
        self.assertContains(respuesta, "Pedro Ruiz")

        historial = HistorialSacramento.objects.get(accion=AccionHistorial.CERTIFICADO)
        self.assertEqual(historial.sacramento, bautismo.sacramento)
        self.assertEqual(historial.usuario, self.usuario)
        self.assertIn("María Solicitante", historial.descripcion)

    def test_post_invalido_no_emite_certificado(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), {})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/solicitud_certificado.html")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_post_sin_csrf_falla(self):
        from django.test import Client

        bautismo = self._crear_partida(numero=1)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self._url(bautismo), self._datos_solicitud())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_solicitante_solo_letras(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(
            self._url(bautismo), self._datos_solicitud(solicitante="María 123")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "solo admite letras")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_valida_documento_segun_tipo(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(
            self._url(bautismo),
            self._datos_solicitud(numero_documento="12"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "5 y 15")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_finalidad_otro_exige_texto(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(
            self._url(bautismo),
            self._datos_solicitud(finalidad=FinalidadCertificado.OTRO),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_finalidad_otro_usa_el_texto(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(
            self._url(bautismo),
            self._datos_solicitud(
                finalidad=FinalidadCertificado.OTRO,
                finalidad_otro="Trámite de visa",
            ),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Trámite de visa")

    def test_partida_anulada_no_emite_certificado(self):
        bautismo = self._crear_partida(numero=1, estado=EstadoRegistro.ANULADO)
        destino = reverse("sacramentos:bautismo_detalle", args=[bautismo.pk])
        self.assertRedirects(self.client.get(self._url(bautismo)), destino)
        self.assertRedirects(
            self.client.post(self._url(bautismo), self._datos_solicitud()), destino
        )
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_no_muestra_padres_biologicos(self):
        bautismo = self._crear_partida(
            numero=1,
            tipo_hijo=TipoHijo.ADOPTIVO,
            padre_biologico_nombre="Anacleto Biológico",
            madre_biologica_nombre="Berta Biológica",
        )
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertNotContains(respuesta, "Anacleto Biológico")
        self.assertNotContains(respuesta, "Berta Biológica")

    def test_certificado_muestra_diocesis_y_pie_configurados(self):
        bautismo = self._crear_partida(numero=1)
        with override_settings(NOMBRE_DIOCESIS="Diócesis de Prueba"):
            respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, "Diócesis de Prueba")
        self.assertContains(respuesta, "Fe que une, sacramentos que dan vida")

    def test_certificado_oculta_insignia_de_estado(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertNotContains(respuesta, "insignia-estado")

    def test_firma_secretario_solo_con_ese_rol(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertNotContains(respuesta, "Secretario(a)")

        PerfilUsuario.objects.create(usuario=self.usuario, rol=RolUsuario.SECRETARIO)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, "Secretario(a)")
        self.assertContains(respuesta, self.usuario.username)

    def test_detalle_muestra_enlace_certificado(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self._detalle(bautismo)
        self.assertContains(respuesta, self._url(bautismo))

    def test_detalle_anulado_no_muestra_enlace_certificado(self):
        bautismo = self._crear_partida(numero=1, estado=EstadoRegistro.ANULADO)
        respuesta = self._detalle(bautismo)
        self.assertNotContains(respuesta, self._url(bautismo))

    def test_certificado_titulo_y_consta_propios(self):
        bautismo = self._crear_partida(numero=3)
        with override_settings(NOMBRE_PARROQUIA="San Pedro Claver"):
            respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, "CERTIFICADO DE BAUTISMO")
        self.assertNotContains(respuesta, "PARTIDA DE BAUTISMO")
        self.assertContains(
            respuesta,
            "El suscrito párroco certifica que en el Libro de Bautismos de "
            "San Pedro Claver se encuentra la siguiente partida:",
        )

    def test_certificado_solo_muestra_el_documento_del_bautizado(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, str(bautismo.sacramento.fiel.documento))
        self.assertContains(respuesta, "Pedro López")
        self.assertNotContains(respuesta, "33333333")  # documento del padrino
        self.assertNotContains(respuesta, "11111111")  # documento del padre
        self.assertNotContains(respuesta, "22222222")  # documento de la madre
        self.assertNotContains(respuesta, "1234567890")  # documento del ministro
        self.assertNotContains(respuesta, "7777777777")  # documento del párroco

    def test_certificado_firma_del_parroco_sin_cargo_pegado(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, '<span class="hoja-firma-nombre">Pedro Ruiz</span>')
        self.assertContains(respuesta, '<span class="hoja-firma-rol">Párroco</span>')

    def test_certificado_ministro_con_cargo_sin_documento(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, "Carlos Gómez - Párroco")
        self.assertNotContains(respuesta, "1234567890")

    def test_certificado_usa_ornamento_nuevo_sin_el_viejo(self):
        bautismo = self._crear_partida(numero=1)
        respuesta = self.client.post(self._url(bautismo), self._datos_solicitud())
        self.assertContains(respuesta, "hoja-ornamento-pie")
        self.assertNotContains(respuesta, "hoja-cierre-ornamento")


# ---------------------------------------------------------------------------
# Mecanismo reutilizable de reglas sacramentales (sacramentos/reglas.py)
# ---------------------------------------------------------------------------


class _FormularioReglasDummy(MixinReglas):
    """Formulario vacío que usa el mecanismo de reglas, para las pruebas."""

    def __init__(self, *args, **kwargs):
        self._reglas = kwargs.pop("reglas", [])
        super().__init__(*args, **kwargs)

    def reglas_de(self, datos):
        return self._reglas


class ReglasMecanismosTests(TestCase):
    def test_regla_con_nivel_desconocido_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            Regla("X1", "INVENTADO", "Mensaje.")

    def test_regla_texto_incluye_codigo_entre_corchetes(self):
        regla = Regla("P1", BLOQUEA, "No consta el bautismo.")
        self.assertEqual(regla.texto(), "[P1] No consta el bautismo.")

    def test_evaluar_reglas_separa_por_nivel(self):
        bloqueo = Regla("B1", BLOQUEA, "Bloqueado.")
        advertencia = Regla("A1", ADVIERTE, "Revisar.")
        recuerdo = Regla("R1", RECUERDA, "Acordar.")
        resultado = evaluar_reglas([recuerdo, bloqueo, advertencia])
        self.assertEqual(resultado.bloqueos, [bloqueo])
        self.assertEqual(resultado.advertencias, [advertencia])
        self.assertEqual(resultado.recuerdos, [recuerdo])

    def test_edad_en_fecha(self):
        nacimiento = date(2015, 5, 10)
        self.assertEqual(edad_en_fecha(nacimiento, date(2026, 5, 9)), 10)
        self.assertEqual(edad_en_fecha(nacimiento, date(2026, 5, 10)), 11)
        self.assertEqual(edad_en_fecha(nacimiento, date(2026, 12, 31)), 11)
        self.assertIsNone(edad_en_fecha(None, date(2026, 1, 1)))
        self.assertIsNone(edad_en_fecha(nacimiento, None))

    def test_bloquea_agrega_error_sin_campo(self):
        regla = Regla("X1", BLOQUEA, "No se puede guardar.")
        formulario = _FormularioReglasDummy({}, reglas=[regla])
        self.assertFalse(formulario.is_valid())
        self.assertIn("[X1] No se puede guardar.", formulario.non_field_errors())
        self.assertEqual(formulario.advertencias_pendientes, [])

    def test_adviete_sin_casilla_no_guarda(self):
        regla = Regla("X1", ADVIERTE, "Revisa la edad.")
        formulario = _FormularioReglasDummy({}, reglas=[regla])
        self.assertFalse(formulario.is_valid())
        self.assertEqual(formulario.advertencias_pendientes, [regla])
        errores = str(formulario.non_field_errors())
        self.assertIn("[X1] Revisa la edad.", errores)
        self.assertIn("Verificado / excepción autorizada", errores)

    def test_adviete_con_casilla_sin_motivo_no_guarda(self):
        regla = Regla("X1", ADVIERTE, "Revisa la edad.")
        formulario = _FormularioReglasDummy({"reglas_verificadas": True}, reglas=[regla])
        self.assertFalse(formulario.is_valid())
        self.assertIn("motivo", str(formulario.non_field_errors()).lower())
        self.assertEqual(formulario.advertencias_aceptadas, [])

    def test_adviete_con_casilla_y_motivo_es_valido(self):
        regla = Regla("X1", ADVIERTE, "Revisa la edad.")
        formulario = _FormularioReglasDummy(
            {"reglas_verificadas": True, "reglas_motivo": "Excepción del párroco."},
            reglas=[regla],
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.advertencias_aceptadas, [(regla, "Excepción del párroco.")])

    def test_recuerda_no_bloquea_el_guardado(self):
        regla = Regla("X1", RECUERDA, "Acordar la confesión.")
        formulario = _FormularioReglasDummy({}, reglas=[regla])
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual([r.codigo for r in formulario.recuerdos_visibles], ["X1"])

    def test_recuerdos_visibles_muestra_los_iniciales_en_el_get(self):
        inicial = Regla("R0", RECUERDA, "Visible desde el GET.")

        class _ConInicial(_FormularioReglasDummy):
            def reglas_iniciales(self):
                return [inicial]

        formulario = _ConInicial()
        self.assertEqual([r.codigo for r in formulario.recuerdos_visibles], ["R0"])


# ---------------------------------------------------------------------------
# Primera Comunión: reglas P1-P5, servicio y vistas (prompt 9a)
# ---------------------------------------------------------------------------


class PrimeraComunionBaseTests(TestCase):
    def setUp(self):
        pais = Pais.objects.create(nombre="Colombia")
        departamento = Departamento.objects.create(nombre="Cundinamarca", pais=pais)
        self.municipio = Municipio.objects.create(nombre="Bogotá", departamento=departamento)
        self.parroquia = Parroquia.objects.create(
            nombre="San Pedro Claver",
            municipio=self.municipio,
            direccion="Calle 1 # 2-34",
        )
        self.libro_pc = Libro.objects.create(
            nombre="Primeras Comuniones 2026",
            tipo_libro=TipoLibro.PRIMERA_COMUNION,
            detalle="Registro de primeras comuniones",
            fecha_apertura=date(2026, 1, 1),
            estado=EstadoLibro.ABIERTO,
            parroquia=self.parroquia,
        )
        self.folio_pc = Folio.objects.create(libro=self.libro_pc, numero_folio=1)
        self.libro_bautismos = Libro.objects.create(
            nombre="Bautismos 2026",
            tipo_libro=TipoLibro.BAUTISMOS,
            detalle="Registro de bautismos",
            fecha_apertura=date(2026, 1, 1),
            estado=EstadoLibro.ABIERTO,
            parroquia=self.parroquia,
        )
        self.folio_bautismos = Folio.objects.create(libro=self.libro_bautismos, numero_folio=1)
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
        self.padre = Padre.objects.create(
            documento=self._crear_documento("11111111"), nombre="José", apellido="Pérez"
        )
        self.madre = Madre.objects.create(
            documento=self._crear_documento("22222222"), nombre="María", apellido="Gómez"
        )
        self.usuario = self._crear_usuario()

    def _crear_documento(self, numero_documento, tipo_documento=TipoDocumento.CC):
        documento, _ = Documento.objects.get_or_create(
            tipo_documento=tipo_documento, numero_documento=numero_documento
        )
        return documento

    def _crear_usuario(self, username="admin", **kwargs):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User(username=username, **kwargs)
        user.set_password("admin123")
        user.save()
        return user

    def _crear_comulgante_bautizado(
        self,
        numero_documento="12345678",
        fecha_nacimiento=date(2015, 5, 10),
        fecha_bautismo=date(2016, 3, 15),
        numero_bautismo=1,
        **kwargs_fiel,
    ):
        """Fiel con partida de bautismo enlazada en el sistema."""
        fiel = Fiel.objects.create(
            documento=self._crear_documento(numero_documento),
            nombres=kwargs_fiel.pop("nombres", "Luis"),
            apellidos=kwargs_fiel.pop("apellidos", "Martínez Díaz"),
            fecha_nacimiento=fecha_nacimiento,
            municipio_nacimiento=self.municipio,
            sexo=Sexo.HOMBRE,
            **kwargs_fiel,
        )
        sacramento = Sacramento.objects.create(
            tipo=TipoSacramento.BAUTISMO,
            fiel=fiel,
            libro=self.libro_bautismos,
            folio=self.folio_bautismos,
            numero=numero_bautismo,
            fecha=fecha_bautismo,
            fecha_registro=fecha_bautismo,
            parroquia=self.parroquia,
            ministro=self.ministro,
        )
        bautismo = Bautismo.objects.create(
            sacramento=sacramento,
            padre=self.padre,
            madre=self.madre,
            tipo_hijo=TipoHijo.BIOLOGICO,
            quien_firma=self.ministro,
            doy_fe=self.ministro,
        )
        return fiel, bautismo

    def _datos(self, **extra):
        """Datos válidos del formulario (comulgante bautizado en el sistema)."""
        return {
            "libro": self.libro_pc,
            "fecha": date(2026, 6, 15),
            "ministro": self.ministro,
            "doy_fe": self.parroco,
            "observaciones": "",
            "fiel_tipo_documento": TipoDocumento.CC,
            "fiel_numero_documento": "12345678",
            "fiel_nombres": "Luis",
            "fiel_apellidos": "Martínez Díaz",
            "fiel_fecha_nacimiento": date(2015, 5, 10),
            "fiel_municipio_nacimiento": self.municipio,
            "fiel_sexo": Sexo.HOMBRE,
            "fiel_telefono": "",
            "bautismo": "",
            "bautismo_fecha": "",
            "bautismo_parroquia": "",
            "bautismo_diocesis": "",
            "bautismo_libro": "",
            "bautismo_folio": "",
            "bautismo_numero": "",
            "bautismo_observaciones": "",
            **extra,
        }

    def _datos_post(self, **extra):
        """Igual que ``_datos`` pero con PK en los campos de modelo (para el cliente)."""
        datos = self._datos(**extra)
        for campo in ("libro", "ministro", "doy_fe", "fiel_municipio_nacimiento"):
            if hasattr(datos.get(campo), "pk"):
                datos[campo] = datos[campo].pk
        return datos

    def _datos_bautismo_externo(self, **extra):
        """Documento sin fiel en el sistema, con bautismo de otra parroquia completo."""
        datos = self._datos(
            fiel_numero_documento="87654321",
            fiel_nombres="Ana",
            fiel_apellidos="García López",
            fiel_fecha_nacimiento=date(2015, 5, 10),
            bautismo_fecha=date(2016, 3, 20),
            bautismo_parroquia="Santa Ana de Chía",
            bautismo_libro=2,
            bautismo_folio=3,
            bautismo_numero=45,
        )
        datos.update(extra)
        return datos

    def _datos_post_externo(self, **extra):
        datos = self._datos_bautismo_externo(**extra)
        for campo in ("libro", "ministro", "doy_fe", "fiel_municipio_nacimiento"):
            if hasattr(datos.get(campo), "pk"):
                datos[campo] = datos[campo].pk
        return datos


class PrimeraComunionReglasTests(PrimeraComunionBaseTests):
    """Reglas P1 a P5 de la Primera Comunión (docs/requisitos_sacramentos.md)."""

    def test_p1_sin_bautismo_bloquea(self):
        self._crear_comulgante_bautizado()
        datos = self._datos()  # sin bautismo enlazado ni externo: documento no coincide
        datos["fiel_numero_documento"] = "99999999"
        formulario = PrimeraComunionForm(datos)
        self.assertFalse(formulario.is_valid())
        errores = str(formulario.non_field_errors())
        self.assertIn("[P1]", errores)
        self.assertIn("No consta el bautismo", errores)

    def test_p1_bautismo_enlazado_por_documento_es_valido(self):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos())
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertIsNotNone(formulario.bautismo_sistema)

    def test_p1_bautismo_enlazado_por_casilla_oculta_es_valido(self):
        fiel, bautismo = self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(bautismo=bautismo.pk))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.bautismo_sistema, bautismo)

    def test_p1_bautismo_externo_completo_es_valido(self):
        formulario = PrimeraComunionForm(self._datos_bautismo_externo())
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertIsNone(formulario.bautismo_sistema)
        self.assertIsNotNone(formulario.datos_bautismo_externo)

    def test_p1_bautismo_externo_incompleto_bloquea(self):
        formulario = PrimeraComunionForm(
            self._datos_bautismo_externo(bautismo_parroquia="", bautismo_libro="")
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("bautismo_parroquia", formulario.errors)
        self.assertIn("bautismo_libro", formulario.errors)
        # sin los cinco datos no hay constancia: P1 sigue bloqueando.
        self.assertIn("[P1]", str(formulario.non_field_errors()))

    def test_p1_casilla_oculta_con_bautismo_inexistente_bloquea(self):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(bautismo=99999))
        self.assertFalse(formulario.is_valid())
        self.assertIn("bautismo", formulario.errors)
        self.assertIn("no existe o no está activo", str(formulario.errors["bautismo"]))

    def test_p1_casilla_oculta_con_bautismo_de_otra_persona_bloquea(self):
        self._crear_comulgante_bautizado(numero_documento="12345678")
        _, bautismo_ajeno = self._crear_comulgante_bautizado(
            numero_documento="55555555",
            fecha_nacimiento=date(2014, 1, 1),
            fecha_bautismo=date(2015, 2, 2),
            numero_bautismo=2,
        )
        datos = self._datos()
        datos["fiel_numero_documento"] = "12345678"
        datos["bautismo"] = bautismo_ajeno.pk
        formulario = PrimeraComunionForm(datos)
        self.assertFalse(formulario.is_valid())
        self.assertIn("no corresponde a esta persona", str(formulario.errors["bautismo"]))

    def test_p2_ya_registrada_bloquea_con_la_referencia(self):
        fiel, bautismo = self._crear_comulgante_bautizado()
        previa = PrimeraComunion.objects.create(
            sacramento=Sacramento.objects.create(
                tipo=TipoSacramento.PRIMERA_COMUNION,
                fiel=fiel,
                libro=self.libro_pc,
                folio=self.folio_pc,
                numero=7,
                fecha=date(2025, 6, 1),
                fecha_registro=date(2025, 6, 1),
                parroquia=self.parroquia,
                ministro=self.ministro,
            ),
            edad=10,
            bautismo=bautismo,
            doy_fe=self.parroco,
        )
        self.assertIsNotNone(previa)
        formulario = PrimeraComunionForm(self._datos())
        self.assertFalse(formulario.is_valid())
        errores = str(formulario.non_field_errors())
        self.assertIn("[P2]", errores)
        self.assertIn("Libro", errores)
        self.assertIn("Folio", errores)
        self.assertIn("N.° 7", errores)

    def test_p3_fecha_futura_bloquea(self):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(
            self._datos(fecha=timezone.localdate() + timedelta(days=10))
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("no puede ser en el futuro", str(formulario.non_field_errors()))

    def test_p3_fecha_anterior_al_nacimiento_bloquea(self):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(fecha=date(2015, 1, 1)))
        self.assertFalse(formulario.is_valid())
        errores = str(formulario.non_field_errors())
        self.assertIn("[P3]", errores)
        self.assertIn("anterior", errores)
        self.assertIn("nacimiento", errores)

    def test_p3_fecha_anterior_al_bautismo_bloquea(self):
        # Bautismo externo posterior a la fecha de la comunión pedida.
        formulario = PrimeraComunionForm(self._datos_bautismo_externo(fecha=date(2016, 1, 10)))
        self.assertFalse(formulario.is_valid())
        errores = str(formulario.non_field_errors())
        self.assertIn("[P3]", errores)
        self.assertIn("anterior a la del bautismo", errores)

    def _datos_nino(self, **extra):
        """Comulgante de dos años con bautismo externo: dispara solo la P4."""
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=730)
        return self._datos_bautismo_externo(
            fiel_numero_documento="44443333",
            fiel_nombres="Mateo",
            fiel_fecha_nacimiento=nacimiento,
            fecha=hoy - timedelta(days=5),
            bautismo_fecha=nacimiento + timedelta(days=20),
            **extra,
        )

    def test_p4_menor_de_edad_advierte_y_no_guarda_sin_casilla(self):
        formulario = PrimeraComunionForm(self._datos_nino())
        self.assertFalse(formulario.is_valid())
        errores = str(formulario.non_field_errors())
        self.assertIn("[P4]", errores)
        self.assertIn("Verificado / excepción autorizada", errores)
        self.assertEqual(len(formulario.advertencias_pendientes), 1)
        self.assertEqual(formulario.advertencias_pendientes[0].codigo, "P4")

    def test_p4_post_manipulado_con_casilla_sin_motivo_no_guarda(self):
        formulario = PrimeraComunionForm(self._datos_nino(reglas_verificadas=True))
        self.assertFalse(formulario.is_valid())
        self.assertIn("motivo", str(formulario.non_field_errors()).lower())
        self.assertEqual(formulario.advertencias_aceptadas, [])

    def test_p4_con_casilla_y_motivo_es_valida_y_queda_registrada(self):
        formulario = PrimeraComunionForm(
            self._datos_nino(
                reglas_verificadas=True,
                reglas_motivo="Excepción autorizada por el párroco: causa justa.",
            )
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(len(formulario.advertencias_aceptadas), 1)
        codigo, motivo = (
            formulario.advertencias_aceptadas[0][0].codigo,
            (formulario.advertencias_aceptadas[0][1]),
        )
        self.assertEqual(codigo, "P4")
        self.assertIn("causa justa", motivo)
        datos = formulario.datos_para_servicio()
        self.assertEqual(datos["reglas_aceptadas"][0][0], "P4")

    def test_p5_se_recuerda_siempre_y_no_bloquea(self):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos())
        self.assertTrue(formulario.is_valid(), formulario.errors)
        codigos = [r.codigo for r in formulario.recuerdos_visibles]
        self.assertIn("P5", codigos)

    def test_bloqueos_no_se_superan_enviando_la_casilla_del_formulario(self):
        # Manipular el POST (casilla + motivo) no saltea un BLOQUEA como P1.
        datos = self._datos(
            fiel_numero_documento="99999999",
            reglas_verificadas=True,
            reglas_motivo="Intento de salteo.",
        )
        formulario = PrimeraComunionForm(datos)
        self.assertFalse(formulario.is_valid())
        self.assertIn("[P1]", str(formulario.non_field_errors()))
        self.assertEqual(formulario.advertencias_aceptadas, [])

    def test_libro_cerrado_no_admite_partidas(self):
        self._crear_comulgante_bautizado()
        self.libro_pc.estado = EstadoLibro.CERRADO
        self.libro_pc.fecha_cierre = timezone.localdate()
        self.libro_pc.save()
        formulario = PrimeraComunionForm(self._datos())
        self.assertFalse(formulario.is_valid())
        # El select solo ofrece libros abiertos: el libro cerrado ni siquiera
        # está en las opciones.
        self.assertIn("libro", formulario.errors)


class PrimeraComunionServicioTests(PrimeraComunionBaseTests):
    def _registrar_desde_form(self, **extra):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(**extra))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        return registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)

    def test_registrar_crea_sacramento_y_primera_comunion(self):
        primera, reutilizadas = self._registrar_desde_form()
        self.assertEqual(primera.sacramento.tipo, TipoSacramento.PRIMERA_COMUNION)
        self.assertEqual(primera.sacramento.fiel.nombres, "Luis")
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertEqual(primera.sacramento.fecha, date(2026, 6, 15))
        self.assertIsNotNone(primera.sacramento.numero)
        self.assertIsNotNone(primera.sacramento.folio)
        self.assertEqual(reutilizadas, ["fiel"])

    def test_registrar_calcula_edad_y_copia_padre_y_madre_del_bautismo(self):
        primera, _ = self._registrar_desde_form()
        self.assertEqual(primera.edad, 11)
        self.assertEqual(primera.padre, self.padre)
        self.assertEqual(primera.madre, self.madre)
        self.assertIsNotNone(primera.bautismo)
        self.assertIsNone(primera.fecha_bautismo)

    def test_registrar_con_bautismo_externo_guarda_los_datos(self):
        formulario = PrimeraComunionForm(
            self._datos_bautismo_externo(bautismo_diocesis="Diócesis de Zipaquirá")
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, reutilizadas = registrar_primera_comunion(
            formulario.datos_para_servicio(), self.usuario
        )
        self.assertIsNone(primera.bautismo)
        self.assertIsNone(primera.padre)
        self.assertEqual(primera.fecha_bautismo, date(2016, 3, 20))
        self.assertEqual(primera.parroquia_bautismo, "Santa Ana de Chía")
        self.assertEqual(primera.libro_bautismo, 2)
        self.assertEqual(primera.folio_bautismo, 3)
        self.assertEqual(primera.numero_bautismo, 45)
        self.assertIn("Diócesis: Diócesis de Zipaquirá.", primera.observaciones_bautismo)
        self.assertEqual(reutilizadas, [])

    def test_advertencia_aceptada_queda_en_el_historial(self):
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=730)
        formulario = PrimeraComunionForm(
            self._datos_bautismo_externo(
                fiel_numero_documento="44443333",
                fiel_nombres="Mateo",
                fiel_fecha_nacimiento=nacimiento,
                fecha=hoy - timedelta(days=5),
                bautismo_fecha=nacimiento + timedelta(days=20),
                reglas_verificadas=True,
                reglas_motivo="Causa justa certificada por el párroco.",
            )
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        historial = HistorialSacramento.objects.filter(sacramento=primera.sacramento)
        entrada = historial.filter(descripcion__contains="Regla P4 verificada").first()
        self.assertIsNotNone(entrada)
        self.assertIn("Causa justa certificada por el párroco.", entrada.descripcion)
        self.assertEqual(entrada.usuario, self.usuario)

    def test_registrar_historial_de_creacion(self):
        primera, _ = self._registrar_desde_form()
        entrada = HistorialSacramento.objects.filter(
            sacramento=primera.sacramento, accion=AccionHistorial.CREACION
        ).first()
        self.assertIsNotNone(entrada)
        self.assertEqual(entrada.usuario, self.usuario)


class PrimeraComunionVistaTests(PrimeraComunionBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _url_crear(self):
        return reverse("sacramentos:primera_comunion_crear")

    def _url_lista(self):
        return reverse("sacramentos:primera_comunion_lista")

    def _url_detalle(self, primera):
        return reverse("sacramentos:primera_comunion_detalle", args=[primera.pk])

    def _registrar(self, **extra):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(**extra))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        return primera

    def test_listas_y_formulario_requieren_sesion(self):
        self.client.logout()
        for url in (
            self._url_lista(),
            self._url_crear(),
            reverse("sacramentos:primera_comunion_detalle", args=[99999]),
        ):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302)

    def test_lista_muestra_los_comulgantes(self):
        self._registrar()
        respuesta = self.client.get(self._url_lista())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Luis")
        self.assertContains(respuesta, "Martínez Díaz")

    def test_crear_get_acepta_libro_por_parametro(self):
        respuesta = self.client.get(self._url_crear(), {"libro": self.libro_pc.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].initial["libro"], self.libro_pc)

    def test_crear_post_valido_redirige_al_detalle(self):
        self._crear_comulgante_bautizado()
        total_antes = PrimeraComunion.objects.count()
        respuesta = self.client.post(self._url_crear(), self._datos_post(), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PrimeraComunion.objects.count(), total_antes + 1)
        self.assertContains(respuesta, "PARTIDA DE PRIMERA COMUNIÓN")
        self.assertContains(respuesta, "Luis")

    def test_crear_post_bloqueado_no_guarda(self):
        total_antes = PrimeraComunion.objects.count()
        datos = self._datos_post(fiel_numero_documento="99999999")
        respuesta = self.client.post(self._url_crear(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PrimeraComunion.objects.count(), total_antes)
        self.assertContains(respuesta, "[P1]")

    def test_las_reglas_se_renderizan_dentro_del_formulario(self):
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=730)
        datos = self._datos_post_externo(
            fiel_numero_documento="44443333",
            fiel_nombres="Mateo",
            fiel_fecha_nacimiento=nacimiento,
            fecha=hoy - timedelta(days=5),
            bautismo_fecha=nacimiento + timedelta(days=20),
        )
        respuesta = self.client.post(self._url_crear(), datos)
        contenido = respuesta.content.decode()
        posicion_libro = contenido.index('name="libro"')
        inicio = contenido.rfind("<form", 0, posicion_libro)
        fin = contenido.index("</form>", posicion_libro)
        bloque = contenido[inicio:fin]
        for campo in ("reglas_verificadas", "reglas_motivo"):
            self.assertIn(f'name="{campo}"', bloque, campo)

    def test_crear_post_con_advertencia_sin_casilla_no_guarda(self):
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=730)
        total_antes = PrimeraComunion.objects.count()
        datos = self._datos_post_externo(
            fiel_numero_documento="44443333",
            fiel_nombres="Mateo",
            fiel_fecha_nacimiento=nacimiento,
            fecha=hoy - timedelta(days=5),
            bautismo_fecha=nacimiento + timedelta(days=20),
        )
        respuesta = self.client.post(self._url_crear(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PrimeraComunion.objects.count(), total_antes)
        self.assertContains(respuesta, "Verificado / excepción autorizada")

    def test_crear_post_advertencia_aceptada_guarda_y_registra_el_motivo(self):
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=730)
        datos = self._datos_post_externo(
            fiel_numero_documento="44443333",
            fiel_nombres="Mateo",
            fiel_fecha_nacimiento=nacimiento,
            fecha=hoy - timedelta(days=5),
            bautismo_fecha=nacimiento + timedelta(days=20),
            reglas_verificadas="on",
            reglas_motivo="Excepción autorizada: causa justa.",
        )
        respuesta = self.client.post(self._url_crear(), datos, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "PARTIDA DE PRIMERA COMUNIÓN")
        historial = HistorialSacramento.objects.filter(descripcion__contains="Regla P4 verificada")
        self.assertEqual(historial.count(), 1)
        self.assertIn("causa justa", historial.first().descripcion)

    def test_detalle_muestra_hoja_y_enlace_al_bautismo(self):
        primera = self._registrar()
        respuesta = self.client.get(self._url_detalle(primera))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "PARTIDA DE PRIMERA COMUNIÓN")
        self.assertContains(respuesta, "Constancia del bautismo")
        self.assertContains(respuesta, "Ver partida de bautismo")
        self.assertContains(
            respuesta, reverse("sacramentos:bautismo_detalle", args=[primera.bautismo.pk])
        )

    def test_detalle_anulada_muestra_nota_de_anulacion(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Partida duplicada")
        respuesta = self.client.get(self._url_detalle(primera))
        self.assertContains(respuesta, "Notas marginales")
        self.assertContains(respuesta, "Anulación")
        self.assertContains(respuesta, "Partida duplicada")

    def test_detalle_404(self):
        respuesta = self.client.get(self._url_detalle(PrimeraComunion(sacramento_id=99999)))
        self.assertEqual(respuesta.status_code, 404)

    def test_api_persona_con_bautismo_incluye_los_datos_extra(self):
        self._crear_comulgante_bautizado(numero_documento="66667777")
        respuesta = self.client.get(
            reverse("personas:api_persona"),
            {"rol": "fiel", "tipo": TipoDocumento.CC, "numero": "66667777"},
        )
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertTrue(payload["bautismo_activo"])
        self.assertIn("bautismo_id", payload)
        self.assertIn("bautismo_url", payload)
        self.assertIn("bautismo_parroquia", payload)
        self.assertIn("bautismo_fecha", payload)
        self.assertIn("bautismo_padre", payload)
        self.assertIn("bautismo_madre", payload)
        self.assertIn("San Pedro Claver", payload["bautismo_parroquia"])
        self.assertIn("José", payload["bautismo_padre"])

    def _filas_de_la_hoja(self, primera):
        respuesta = self.client.get(self._url_detalle(primera))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta, {
            fila["etiqueta"]: fila["valor"] for fila in respuesta.context["hoja"]["filas"]
        }

    def test_hoja_toma_padre_y_madre_de_la_partida_de_bautismo(self):
        primera = self._registrar()
        PrimeraComunion.objects.filter(pk=primera.pk).update(padre=None, madre=None)
        respuesta, filas = self._filas_de_la_hoja(primera)
        self.assertEqual(filas["Padre"], f"{self.padre} ({self.padre.documento})")
        self.assertEqual(filas["Madre"], f"{self.madre} ({self.madre.documento})")
        nombres = [persona["nombre"] for persona in respuesta.context["personas_partida"]]
        self.assertIn(str(self.padre), nombres)
        self.assertIn(str(self.madre), nombres)

    def test_detalle_de_pc_no_muestra_padres_biologicos(self):
        primera = self._registrar()
        bautismo = primera.bautismo
        bautismo.padre_biologico_nombre = "Ramiro Biológico"
        bautismo.madre_biologica_nombre = "Alba Biológica"
        bautismo.save()
        respuesta, filas = self._filas_de_la_hoja(primera)
        self.assertEqual(filas["Padre"], f"{self.padre} ({self.padre.documento})")
        self.assertNotContains(respuesta, "Ramiro Biológico")
        self.assertNotContains(respuesta, "Alba Biológica")

    def test_hoja_padres_del_bautismo_externo_usa_los_escritos_en_el_formulario(self):
        datos = self._datos_post_externo(
            padre_tipo_documento=TipoDocumento.CC,
            padre_numero_documento="33333333",
            padre_nombre="Pedro",
            padre_apellido="Sánchez",
            madre_tipo_documento=TipoDocumento.CC,
            madre_numero_documento="44444444",
            madre_nombre="Laura",
            madre_apellido="Herrera",
        )
        respuesta = self.client.post(self._url_crear(), datos, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "PARTIDA DE PRIMERA COMUNIÓN")
        padre = Padre.objects.get(documento__numero_documento="33333333")
        madre = Madre.objects.get(documento__numero_documento="44444444")
        filas = {fila["etiqueta"]: fila["valor"] for fila in respuesta.context["hoja"]["filas"]}
        self.assertEqual(filas["Padre"], f"{padre} ({padre.documento})")
        self.assertEqual(filas["Madre"], f"{madre} ({madre.documento})")

    def test_con_bautismo_enlazado_se_ignoran_los_padres_escritos(self):
        self._crear_comulgante_bautizado()
        datos = self._datos(
            padre_tipo_documento=TipoDocumento.CC,
            padre_numero_documento="55555555",
            padre_nombre="Impostor",
            padre_apellido="Falso",
        )
        formulario = PrimeraComunionForm(datos)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        self.assertEqual(primera.padre_id, self.padre.pk)
        self.assertEqual(primera.madre_id, self.madre.pk)
        self.assertFalse(Padre.objects.filter(documento__numero_documento="55555555").exists())

    def test_hoja_muestra_la_edad_en_anos(self):
        primera = self._registrar()
        PrimeraComunion.objects.filter(pk=primera.pk).update(edad=12)
        _, filas = self._filas_de_la_hoja(primera)
        self.assertEqual(filas["Edad en la fecha"], "12 años")
        PrimeraComunion.objects.filter(pk=primera.pk).update(edad=1)
        _, filas = self._filas_de_la_hoja(primera)
        self.assertEqual(filas["Edad en la fecha"], "1 año")

    def test_padre_externo_nuevo_sin_nombre_no_guarda(self):
        total_antes = PrimeraComunion.objects.count()
        datos = self._datos_post_externo(
            padre_tipo_documento=TipoDocumento.CC,
            padre_numero_documento="33333333",
        )
        respuesta = self.client.post(self._url_crear(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("padre_nombre", respuesta.context["form"].errors)
        self.assertEqual(PrimeraComunion.objects.count(), total_antes)

    def test_padres_externos_con_el_mismo_documento_no_guardan(self):
        datos = self._datos_post_externo(
            padre_tipo_documento=TipoDocumento.CC,
            padre_numero_documento="33333333",
            padre_nombre="Pedro",
            padre_apellido="Sánchez",
            madre_tipo_documento=TipoDocumento.CC,
            madre_numero_documento="33333333",
            madre_nombre="Laura",
            madre_apellido="Herrera",
        )
        respuesta = self.client.post(self._url_crear(), datos)
        self.assertIn("madre_numero_documento", respuesta.context["form"].errors)

    def test_padre_externo_no_puede_tener_el_documento_del_comulgante(self):
        datos = self._datos_post_externo(
            padre_tipo_documento=TipoDocumento.CC,
            padre_numero_documento="87654321",
            padre_nombre="Pedro",
            padre_apellido="Sánchez",
        )
        respuesta = self.client.post(self._url_crear(), datos)
        self.assertIn("padre_numero_documento", respuesta.context["form"].errors)

    def test_formulario_muestra_los_campos_de_padres_para_bautismo_externo(self):
        respuesta = self.client.get(self._url_crear())
        self.assertEqual(respuesta.status_code, 200)
        for campo in (
            "padre_tipo_documento",
            "padre_numero_documento",
            "padre_nombre",
            "padre_apellido",
            "madre_tipo_documento",
            "madre_numero_documento",
            "madre_nombre",
            "madre_apellido",
        ):
            self.assertContains(respuesta, f'name="{campo}"')
        self.assertContains(respuesta, 'data-campo-persona="padre" readonly')


class PrimeraComunionAccionesBaseTests(PrimeraComunionBaseTests):
    """Utilidades comunes para corregir, anular, eliminar y certificar PC."""

    contador = 0

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _url(self, nombre, primera):
        return reverse(f"sacramentos:{nombre}", args=[primera.pk])

    def _registrar(self, **extra):
        self._crear_comulgante_bautizado()
        formulario = PrimeraComunionForm(self._datos(**extra))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        return primera

    def _registrar_otro(self, numero_documento="87654321"):
        self._crear_comulgante_bautizado(
            numero_documento=numero_documento,
            nombres="Sofia",
            apellidos="Ríos",
            fecha_nacimiento=date(2014, 2, 2),
            fecha_bautismo=date(2015, 3, 3),
            numero_bautismo=2,
        )
        formulario = PrimeraComunionForm(
            self._datos(
                fiel_numero_documento=numero_documento,
                fiel_nombres="Sofia",
                fiel_apellidos="Ríos",
                fiel_fecha_nacimiento=date(2014, 2, 2),
            )
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        return primera

    def _registrar_externo(self, **extra):
        formulario = PrimeraComunionForm(self._datos_bautismo_externo(**extra))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        primera, _ = registrar_primera_comunion(formulario.datos_para_servicio(), self.usuario)
        return primera

    def _datos_editar(self, **extra):
        motivo = extra.pop("motivo", "Corrección de prueba")
        datos = self._datos(**extra)
        datos["motivo"] = motivo
        return datos

    def _datos_editar_post(self, **extra):
        motivo = extra.pop("motivo", "Corrección de prueba")
        datos = self._datos_post(**extra)
        datos["motivo"] = motivo
        return datos

    def _corregir(self, primera, **extra):
        form = PrimeraComunionEditarForm(self._datos_editar(**extra), primera=primera)
        self.assertTrue(form.is_valid(), form.errors)
        return corregir_primera_comunion(
            primera,
            form.datos_para_servicio(),
            self.usuario,
            form.cleaned_data["motivo"],
        )


class PrimeraComunionCorreccionTests(PrimeraComunionAccionesBaseTests):
    def test_corregir_mismo_dia_deja_activa_y_solo_historial(self):
        primera = self._registrar()
        self._corregir(primera, fiel_fecha_nacimiento=date(2016, 1, 1))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertTrue(
            HistorialSacramento.objects.filter(
                sacramento=primera.sacramento, accion=AccionHistorial.CORRECCION
            ).exists()
        )
        self.assertFalse(
            AnotacionMarginal.objects.filter(
                sacramento=primera.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
            ).exists()
        )

    def test_corregir_otro_dia_marca_corregido_y_anota(self):
        primera = self._registrar()
        Sacramento.objects.filter(pk=primera.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        primera.sacramento.refresh_from_db()
        self._corregir(primera, fiel_fecha_nacimiento=date(2016, 1, 1))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertEqual(primera.sacramento.fiel.fecha_nacimiento, date(2016, 1, 1))
        self.assertTrue(
            AnotacionMarginal.objects.filter(
                sacramento=primera.sacramento, tipo=TipoAnotacionMarginal.CORRECCION
            ).exists()
        )

    def test_corregir_no_permite_cambiar_el_nombre_del_comulgante(self):
        primera = self._registrar()
        self._corregir(primera, fiel_nombres="Otro Nombre")
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.fiel.nombres, "Luis")

    def test_corregir_no_cambia_ubicacion_en_el_libro_ni_fecha_registro(self):
        primera = self._registrar()
        folio = primera.sacramento.folio
        numero = primera.sacramento.numero
        fecha_registro = primera.sacramento.fecha_registro
        self._corregir(primera, fiel_fecha_nacimiento=date(2016, 1, 1))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.folio, folio)
        self.assertEqual(primera.sacramento.numero, numero)
        self.assertEqual(primera.sacramento.fecha_registro, fecha_registro)

    def test_corregir_guarda_historial_con_motivo_y_usuario(self):
        primera = self._registrar()
        self._corregir(primera, motivo="Error en la fecha")
        entrada = HistorialSacramento.objects.filter(
            sacramento=primera.sacramento, accion=AccionHistorial.CORRECCION
        ).first()
        self.assertIsNotNone(entrada)
        self.assertEqual(entrada.descripcion, "Error en la fecha")
        self.assertEqual(entrada.usuario, self.usuario)

    def test_corregir_partida_anulada_lanza_error(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        with self.assertRaises(ValidationError):
            self._corregir(primera)


class PrimeraComunionEditarFormTests(PrimeraComunionAccionesBaseTests):
    def _otra_partida_del_mismo_fiel(self, fiel):
        return Sacramento.objects.create(
            tipo=TipoSacramento.CONFIRMACION,
            fiel=fiel,
            libro=self.libro_pc,
            folio=self.folio_pc,
            numero=99,
            fecha=date(2026, 6, 16),
            fecha_registro=date(2026, 6, 16),
            parroquia=self.parroquia,
        )

    def test_bloquea_libro_y_identidad_del_comulgante(self):
        primera = self._registrar()
        form = PrimeraComunionEditarForm(primera=primera)
        for campo in (
            "libro",
            "fiel_tipo_documento",
            "fiel_numero_documento",
            "fiel_nombres",
            "fiel_apellidos",
        ):
            self.assertTrue(form.fields[campo].disabled, campo)

    def test_datos_no_identitarios_del_comulgante_siguen_editables(self):
        primera = self._registrar()
        form = PrimeraComunionEditarForm(primera=primera)
        for campo in ("fiel_fecha_nacimiento", "fiel_sexo", "fiel_telefono"):
            self.assertFalse(form.fields[campo].disabled, campo)

    def test_padres_bloqueados_con_bautismo_enlazado(self):
        primera = self._registrar()
        form = PrimeraComunionEditarForm(primera=primera)
        for campo in ("padre_nombre", "padre_numero_documento", "madre_nombre"):
            self.assertTrue(form.fields[campo].disabled, campo)

    def test_padres_editables_con_bautismo_externo(self):
        primera = self._registrar_externo()
        form = PrimeraComunionEditarForm(primera=primera)
        for campo in ("padre_nombre", "padre_numero_documento", "madre_nombre"):
            self.assertFalse(form.fields[campo].disabled, campo)

    def test_p2_no_bloquea_la_propia_partida(self):
        primera = self._registrar()
        form = PrimeraComunionEditarForm(self._datos_editar(), primera=primera)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.excluir_sacramento, primera.sacramento)

    def test_aviso_partidas_cuenta_otras_partidas(self):
        primera = self._registrar()
        # El comulgante ya tiene su bautismo: una partida distinta a esta.
        self.assertEqual(PrimeraComunionEditarForm(primera=primera).aviso_partidas, 1)
        self._otra_partida_del_mismo_fiel(primera.sacramento.fiel)
        self.assertEqual(PrimeraComunionEditarForm(primera=primera).aviso_partidas, 2)


class PrimeraComunionAnulacionTests(PrimeraComunionAccionesBaseTests):
    def test_anular_marca_estado_y_guarda_historial_y_anotacion(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Partida duplicada")
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ANULADO)
        self.assertTrue(
            HistorialSacramento.objects.filter(
                sacramento=primera.sacramento, accion=AccionHistorial.ANULACION
            ).exists()
        )
        anotacion = AnotacionMarginal.objects.get(
            sacramento=primera.sacramento, tipo=TipoAnotacionMarginal.ANULACION
        )
        self.assertEqual(anotacion.get_tipo_display(), "Anulación")
        self.assertIn("Partida duplicada", anotacion.descripcion)
        self.assertIn("anulada", anotacion.descripcion)
        self.assertIsNotNone(primera.sacramento.numero)

    def test_anular_partida_ya_anulada_lanza_error(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        with self.assertRaises(ValidationError):
            anular_primera_comunion(primera, self.usuario, "Otra vez")

    def test_anulada_no_cuenta_para_p2(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        form = PrimeraComunionForm(self._datos())
        self.assertTrue(form.is_valid(), form.errors)


class PrimeraComunionEliminacionTests(PrimeraComunionAccionesBaseTests):
    def _crear_anotacion(self, **extra):
        datos = {
            "tipo": TipoAnotacionMarginal.CORRECCION,
            "fecha": timezone.localdate(),
            "descripcion": "Nota",
            **extra,
        }
        return AnotacionMarginal.objects.create(**datos)

    def test_eliminar_ultima_activa_de_hoy_crea_snapshot_y_libera_numero(self):
        primera = self._registrar()
        sacramento = primera.sacramento
        numero = sacramento.numero
        folio_numero = sacramento.folio.numero_folio
        pk = primera.pk
        sacramento_pk = sacramento.pk
        self.assertTrue(puede_eliminarse(primera))
        self.assertIsNone(motivo_no_eliminable(primera))

        eliminar_primera_comunion(primera, self.usuario, "Partida duplicada")

        self.assertFalse(Sacramento.objects.filter(pk=sacramento_pk).exists())
        self.assertFalse(PrimeraComunion.objects.filter(pk=pk).exists())
        partida = PartidaEliminada.objects.get()
        self.assertEqual(partida.tipo, TipoSacramento.PRIMERA_COMUNION)
        self.assertEqual(partida.numero, numero)
        self.assertEqual(partida.folio_numero, folio_numero)
        self.assertEqual(partida.motivo, "Partida duplicada")
        self.assertEqual(partida.eliminado_por, self.usuario)
        self.assertIn("Luis", partida.resumen)

        nueva = self._registrar_otro()
        self.assertEqual(nueva.sacramento.numero, numero)
        self.assertEqual(nueva.sacramento.folio.numero_folio, folio_numero)

    def test_no_elimina_partida_anulada(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        with self.assertRaisesMessage(ValidationError, "Las partidas anuladas no se eliminan"):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertTrue(PrimeraComunion.objects.filter(pk=primera.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_partida_corregida(self):
        primera = self._registrar()
        Sacramento.objects.filter(pk=primera.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        primera.sacramento.refresh_from_db()
        self._corregir(primera)
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.CORREGIDO)
        self.assertFalse(puede_eliminarse(primera))
        self.assertIsNotNone(motivo_no_eliminable(primera))
        with self.assertRaises(ValidationError):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertTrue(PrimeraComunion.objects.filter(pk=primera.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_no_es_la_ultima(self):
        primera = self._registrar()
        self._registrar_otro()
        with self.assertRaisesMessage(ValidationError, "última partida del libro"):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertTrue(PrimeraComunion.objects.filter(pk=primera.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_no_se_registro_hoy(self):
        primera = self._registrar()
        Sacramento.objects.filter(pk=primera.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        primera = PrimeraComunion.objects.get(pk=primera.pk)
        with self.assertRaisesMessage(ValidationError, "registrada hoy"):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_tiene_anotacion_como_partida_anotada(self):
        primera = self._registrar()
        self._crear_anotacion(sacramento=primera.sacramento, estado=EstadoAnotacion.ANOTADA)
        with self.assertRaisesMessage(ValidationError, "notas marginales"):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertFalse(PartidaEliminada.objects.exists())

    def test_no_elimina_si_es_origen_de_una_anotacion(self):
        primera = self._registrar()
        self._crear_anotacion(sacramento_origen=primera.sacramento)
        with self.assertRaisesMessage(ValidationError, "notas marginales"):
            eliminar_primera_comunion(primera, self.usuario, "Se intenta")
        self.assertFalse(PartidaEliminada.objects.exists())


class PrimeraComunionAccionesViewsTests(PrimeraComunionAccionesBaseTests):
    def test_detalle_activo_elegible_muestra_editar_anular_y_eliminar(self):
        primera = self._registrar()
        respuesta = self.client.get(self._url("primera_comunion_detalle", primera))
        self.assertContains(respuesta, self._url("primera_comunion_editar", primera))
        self.assertContains(respuesta, self._url("primera_comunion_anular", primera))
        self.assertContains(respuesta, self._url("primera_comunion_eliminar", primera))

    def test_detalle_anulado_no_permite_ninguna_accion(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("primera_comunion_detalle", primera))
        self.assertNotContains(respuesta, self._url("primera_comunion_editar", primera))
        self.assertNotContains(respuesta, self._url("primera_comunion_anular", primera))
        self.assertNotContains(respuesta, self._url("primera_comunion_eliminar", primera))
        self.assertNotContains(respuesta, self._url("primera_comunion_certificado", primera))

    def test_detalle_eliminar_deshabilitado_con_motivo_si_no_puede(self):
        primera = self._registrar()
        self._registrar_otro()
        respuesta = self.client.get(self._url("primera_comunion_detalle", primera))
        self.assertNotContains(respuesta, self._url("primera_comunion_eliminar", primera))
        self.assertContains(respuesta, "No se puede eliminar esta partida:")
        self.assertContains(respuesta, "última partida del libro")

    def test_acciones_inexistentes_dan_404(self):
        for nombre in (
            "primera_comunion_editar",
            "primera_comunion_anular",
            "primera_comunion_eliminar",
            "primera_comunion_certificado",
        ):
            url = reverse(f"sacramentos:{nombre}", args=[999999])
            self.assertEqual(self.client.get(url).status_code, 404, nombre)

    def test_acciones_requieren_login(self):
        primera = self._registrar()
        self.client.logout()
        for nombre in (
            "primera_comunion_editar",
            "primera_comunion_anular",
            "primera_comunion_eliminar",
            "primera_comunion_certificado",
        ):
            url = self._url(nombre, primera)
            self.assertNotEqual(self.client.get(url).status_code, 200, nombre)
            self.assertNotEqual(self.client.post(url, {}).status_code, 200, nombre)

    def test_editar_get_y_post_otro_dia_marca_corregido(self):
        primera = self._registrar()
        Sacramento.objects.filter(pk=primera.sacramento.pk).update(
            fecha_registro=timezone.localdate() - timedelta(days=1)
        )
        primera.refresh_from_db()
        primera.sacramento.refresh_from_db()
        self.assertEqual(
            self.client.get(self._url("primera_comunion_editar", primera)).status_code, 200
        )
        datos = self._datos_editar_post(fiel_fecha_nacimiento=date(2016, 1, 1))
        respuesta = self.client.post(self._url("primera_comunion_editar", primera), datos)
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.CORREGIDO)

    def test_editar_partida_anulada_redirige(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("primera_comunion_editar", primera))
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))

    def test_editar_muestra_aviso_de_partidas_compartidas(self):
        primera = self._registrar()
        Sacramento.objects.create(
            tipo=TipoSacramento.CONFIRMACION,
            fiel=primera.sacramento.fiel,
            libro=self.libro_pc,
            folio=self.folio_pc,
            numero=99,
            fecha=date(2026, 6, 16),
            fecha_registro=date(2026, 6, 16),
            parroquia=self.parroquia,
        )
        respuesta = self.client.get(self._url("primera_comunion_editar", primera))
        self.assertContains(
            respuesta,
            "Este cambio también se verá en las 2 partidas donde aparece el comulgante.",
        )

    def test_editar_ignora_campos_protegidos_del_post(self):
        primera = self._registrar()
        sacramento = primera.sacramento
        original = (
            sacramento.libro_id,
            sacramento.folio_id,
            sacramento.numero,
            sacramento.fecha_registro,
            sacramento.creado_por_id,
        )
        datos = self._datos_editar_post(fiel_fecha_nacimiento=date(2016, 1, 1))
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
        respuesta = self.client.post(self._url("primera_comunion_editar", primera), datos)
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))
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
        self.assertEqual(sacramento.modificado_por_id, self.usuario.pk)

    def test_anular_get_y_post(self):
        primera = self._registrar()
        self.assertEqual(
            self.client.get(self._url("primera_comunion_anular", primera)).status_code, 200
        )
        respuesta = self.client.post(
            self._url("primera_comunion_anular", primera), {"motivo": "Partida duplicada"}
        )
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ANULADO)

    def test_anular_post_sin_csrf_falla(self):
        from django.test import Client

        primera = self._registrar()
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self._url("primera_comunion_anular", primera), {"motivo": "x"})
        self.assertEqual(respuesta.status_code, 403)
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ACTIVO)

    def test_get_no_ejecuta_la_anulacion_ni_la_eliminacion(self):
        primera = self._registrar()
        self.client.get(self._url("primera_comunion_anular", primera))
        self.client.get(self._url("primera_comunion_eliminar", primera))
        primera.sacramento.refresh_from_db()
        self.assertEqual(primera.sacramento.estado, EstadoRegistro.ACTIVO)
        self.assertTrue(PrimeraComunion.objects.filter(pk=primera.pk).exists())

    def test_eliminar_partida_elegible_borra_y_redirige_a_la_lista(self):
        primera = self._registrar()
        pk = primera.pk
        self.assertEqual(
            self.client.get(self._url("primera_comunion_eliminar", primera)).status_code, 200
        )
        respuesta = self.client.post(
            self._url("primera_comunion_eliminar", primera), {"motivo": "Se elimina"}
        )
        self.assertRedirects(respuesta, reverse("sacramentos:primera_comunion_lista"))
        self.assertFalse(PrimeraComunion.objects.filter(pk=pk).exists())
        self.assertTrue(PartidaEliminada.objects.exists())

    def test_eliminar_partida_anulada_redirige_sin_borrar(self):
        primera = self._registrar()
        anular_primera_comunion(primera, self.usuario, "Anulada")
        respuesta = self.client.get(self._url("primera_comunion_eliminar", primera))
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))
        respuesta = self.client.post(
            self._url("primera_comunion_eliminar", primera), {"motivo": "Se intenta"}
        )
        self.assertRedirects(respuesta, self._url("primera_comunion_detalle", primera))
        self.assertTrue(PrimeraComunion.objects.filter(pk=primera.pk).exists())
        self.assertFalse(PartidaEliminada.objects.exists())


class PrimeraComunionCertificadoTests(PrimeraComunionAccionesBaseTests):
    """Certificado imprimible de Primera Comunión: solicitud, cierre e historial."""

    contador = 0

    def _fiel(self):
        type(self).contador += 1
        numero = f"71000000{type(self).contador}"
        return Fiel.objects.create(
            documento=self._crear_documento(numero),
            nombres="Fiel",
            apellidos="Prueba",
            fecha_nacimiento=date(2000, 1, 1),
        )

    def _crear_partida(self, *, numero=1, estado=EstadoRegistro.ACTIVO, fiel=None, bautismo=None):
        sacramento = Sacramento.objects.create(
            tipo=TipoSacramento.PRIMERA_COMUNION,
            fiel=fiel or self._fiel(),
            libro=self.libro_pc,
            folio=self.folio_pc,
            numero=numero,
            fecha=date(2026, 6, 15),
            fecha_registro=date(2026, 6, 15),
            parroquia=self.parroquia,
            ministro=self.ministro,
            estado=estado,
        )
        datos = {
            "sacramento": sacramento,
            "edad": 11,
            "doy_fe": self.parroco,
        }
        if bautismo is not None:
            datos.update(
                {
                    "bautismo": bautismo,
                    "padre": bautismo.padre,
                    "madre": bautismo.madre,
                }
            )
        else:
            datos.update(
                {
                    "padre": self.padre,
                    "madre": self.madre,
                    "fecha_bautismo": date(2016, 3, 15),
                    "parroquia_bautismo": "Santa Ana de Chía",
                    "libro_bautismo": 2,
                    "folio_bautismo": 3,
                    "numero_bautismo": 45,
                }
            )
        return PrimeraComunion.objects.create(**datos)

    def _url(self, primera):
        return reverse("sacramentos:primera_comunion_certificado", args=[primera.pk])

    def _datos_solicitud(self, **extra):
        datos = {
            "solicitante": "María Solicitante",
            "tipo_documento": TipoDocumento.CC,
            "numero_documento": "12345678",
            "relacion": RelacionCertificado.PADRE_MADRE,
            "finalidad": FinalidadCertificado.MATRIMONIO,
            "finalidad_otro": "",
        }
        datos.update(extra)
        return datos

    def _hay_certificado_en_historial(self):
        return HistorialSacramento.objects.filter(accion=AccionHistorial.CERTIFICADO).exists()

    def test_certificado_requiere_login(self):
        primera = self._crear_partida()
        self.client.logout()
        respuesta = self.client.get(self._url(primera))
        self.assertNotEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_404(self):
        respuesta = self.client.get(
            reverse("sacramentos:primera_comunion_certificado", args=[9999])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_get_muestra_formulario(self):
        primera = self._crear_partida()
        respuesta = self.client.get(self._url(primera))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/solicitud_certificado.html")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_post_valido_emite_certificado_y_registra_historial(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/certificado.html")
        self.assertContains(respuesta, "María Solicitante")
        self.assertContains(respuesta, "Matrimonio")
        self.assertContains(respuesta, "Pedro Ruiz")

        historial = HistorialSacramento.objects.get(accion=AccionHistorial.CERTIFICADO)
        self.assertEqual(historial.sacramento, primera.sacramento)
        self.assertEqual(historial.usuario, self.usuario)
        self.assertIn("María Solicitante", historial.descripcion)

    def test_post_invalido_no_emite_certificado(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), {})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "certificados/solicitud_certificado.html")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_solicitante_solo_letras(self):
        primera = self._crear_partida()
        respuesta = self.client.post(
            self._url(primera), self._datos_solicitud(solicitante="María 123")
        )
        self.assertContains(respuesta, "solo admite letras")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_valida_documento_segun_tipo(self):
        primera = self._crear_partida()
        respuesta = self.client.post(
            self._url(primera), self._datos_solicitud(numero_documento="12")
        )
        self.assertContains(respuesta, "5 y 15")
        self.assertFalse(self._hay_certificado_en_historial())

    def test_finalidad_otro_exige_texto(self):
        primera = self._crear_partida()
        respuesta = self.client.post(
            self._url(primera), self._datos_solicitud(finalidad=FinalidadCertificado.OTRO)
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_finalidad_otro_usa_el_texto(self):
        primera = self._crear_partida()
        respuesta = self.client.post(
            self._url(primera),
            self._datos_solicitud(
                finalidad=FinalidadCertificado.OTRO, finalidad_otro="Trámite de visa"
            ),
        )
        self.assertContains(respuesta, "Trámite de visa")

    def test_partida_anulada_no_emite_certificado(self):
        primera = self._crear_partida(estado=EstadoRegistro.ANULADO)
        destino = reverse("sacramentos:primera_comunion_detalle", args=[primera.pk])
        self.assertRedirects(self.client.get(self._url(primera)), destino)
        self.assertRedirects(self.client.post(self._url(primera), self._datos_solicitud()), destino)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_post_sin_csrf_falla(self):
        from django.test import Client

        primera = self._crear_partida()
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self._url(primera), self._datos_solicitud())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self._hay_certificado_en_historial())

    def test_certificado_no_muestra_padres_biologicos(self):
        fiel, bautismo = self._crear_comulgante_bautizado(numero_documento="73111111")
        bautismo.padre_biologico_nombre = "Anacleto Biológico"
        bautismo.madre_biologica_nombre = "Berta Biológica"
        bautismo.save()
        primera = self._crear_partida(fiel=fiel, bautismo=bautismo)
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertNotContains(respuesta, "Anacleto Biológico")
        self.assertNotContains(respuesta, "Berta Biológica")

    def test_certificado_muestra_diocesis_y_pie_configurados(self):
        primera = self._crear_partida()
        with override_settings(NOMBRE_DIOCESIS="Diócesis de Prueba"):
            respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "Diócesis de Prueba")
        self.assertContains(respuesta, "Fe que une, sacramentos que dan vida")

    def test_certificado_oculta_insignia_de_estado(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertNotContains(respuesta, "insignia-estado")

    def test_certificado_usa_el_icono_del_caliz(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "M24 27v9M17 40h14")

    def test_firma_secretario_solo_con_ese_rol(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertNotContains(respuesta, "Secretario(a)")

        PerfilUsuario.objects.create(usuario=self.usuario, rol=RolUsuario.SECRETARIO)
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "Secretario(a)")
        self.assertContains(respuesta, self.usuario.username)

    def test_detalle_muestra_enlace_certificado(self):
        primera = self._crear_partida()
        respuesta = self.client.get(
            reverse("sacramentos:primera_comunion_detalle", args=[primera.pk])
        )
        self.assertContains(respuesta, self._url(primera))

    def test_detalle_anulado_no_muestra_enlace_certificado(self):
        primera = self._crear_partida(estado=EstadoRegistro.ANULADO)
        respuesta = self.client.get(
            reverse("sacramentos:primera_comunion_detalle", args=[primera.pk])
        )
        self.assertNotContains(respuesta, self._url(primera))

    def test_certificado_titulo_y_consta_propios(self):
        primera = self._crear_partida(numero=3)
        with override_settings(NOMBRE_PARROQUIA="San Pedro Claver"):
            respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "CERTIFICADO DE PRIMERA COMUNIÓN")
        self.assertNotContains(respuesta, "PARTIDA DE PRIMERA COMUNIÓN")
        self.assertContains(
            respuesta,
            "El suscrito párroco certifica que en el Libro de Primera Comunión de "
            "San Pedro Claver se encuentra la siguiente partida:",
        )

    def test_certificado_solo_muestra_el_documento_del_comulgante(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, str(primera.sacramento.fiel.documento))
        self.assertNotContains(respuesta, "11111111")  # documento del padre
        self.assertNotContains(respuesta, "22222222")  # documento de la madre
        self.assertNotContains(respuesta, "1234567890")  # documento del ministro
        self.assertNotContains(respuesta, "7777777777")  # documento del párroco

    def test_certificado_firma_del_parroco_sin_cargo_pegado(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, '<span class="hoja-firma-nombre">Pedro Ruiz</span>')
        self.assertContains(respuesta, '<span class="hoja-firma-rol">Párroco</span>')

    def test_certificado_ministro_con_cargo_sin_documento(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "Carlos Gómez - Párroco")
        self.assertNotContains(respuesta, "1234567890")

    def test_certificado_usa_ornamento_nuevo_sin_el_viejo(self):
        primera = self._crear_partida()
        respuesta = self.client.post(self._url(primera), self._datos_solicitud())
        self.assertContains(respuesta, "hoja-ornamento-pie")
        self.assertNotContains(respuesta, "hoja-cierre-ornamento")

    def test_datos_cierre_certificado_primera_comunion(self):
        from .forms import SolicitudCertificadoForm

        primera = self._crear_partida()
        form = SolicitudCertificadoForm(self._datos_solicitud())
        self.assertTrue(form.is_valid(), form.errors)
        cierre = datos_certificado_primera_comunion(
            primera, form.datos_para_servicio(), self.usuario
        )
        self.assertEqual(cierre["parroco"], "Pedro Ruiz")
        self.assertEqual(cierre["solicitante"], "María Solicitante")
        self.assertIn("Matrimonio", cierre["finalidad"])
