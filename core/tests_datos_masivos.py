"""Pruebas del comando ``cargar_datos_masivos`` (con cantidades pequeñas)."""

import io
from datetime import date, timedelta
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, Max, Q
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.choices import (
    EstadoLibro,
    EstadoRegistro,
    Sexo,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoLibro,
    TipoSacramento,
)
from core.management.commands import cargar_datos_masivos as masivos
from core.management.commands.exportar_datos_demo import recolectar_datos_demo
from parroquias.models import Folio, Libro, Ministro, Parroquia
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    HistorialSacramento,
    PrimeraComunion,
    Sacramento,
)
from sacramentos.reglas import edad_en_fecha
from ubicacion.models import Departamento, Municipio, Pais

PREFIJO = masivos.PREFIJO_DOCUMENTO
VIGENTES = (EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO)
PRIMEROS_NOMBRES_HOMBRE = {nombre.split()[0] for nombre in masivos.NOMBRES_HOMBRE}
PRIMEROS_NOMBRES_MUJER = {nombre.split()[0] for nombre in masivos.NOMBRES_MUJER}


def cargar(bautismos=30, primeras=10, semilla=11):
    salida = io.StringIO()
    call_command(
        "cargar_datos_masivos",
        bautismos=bautismos,
        primeras=primeras,
        semilla=semilla,
        stdout=salida,
    )
    return salida.getvalue()


def borrar():
    salida = io.StringIO()
    call_command("cargar_datos_masivos", borrar=True, stdout=salida)
    return salida.getvalue()


def partidas_de_prueba():
    return Sacramento.objects.filter(libro__parroquia__nombre=masivos.NOMBRE_PARROQUIA)


def instantanea():
    """Datos comparables de lo creado (sin claves primarias)."""
    partidas = list(
        partidas_de_prueba()
        .order_by("tipo", "libro__numero_libro", "numero")
        .values_list(
            "tipo",
            "libro__nombre",
            "folio__numero_folio",
            "numero",
            "fecha",
            "fecha_registro",
            "estado",
            "ministro__nombre",
            "fiel__nombres",
            "fiel__apellidos",
            "fiel__fecha_nacimiento",
            "fiel__documento__numero_documento",
            "bautismo__padre__nombre",
            "bautismo__madre__nombre",
            "bautismo__padrino__nombre",
            "bautismo__madrina__nombre",
            "bautismo__abuela_materna",
            "primera_comunion__parroquia_bautismo",
        )
    )
    anotaciones = list(
        AnotacionMarginal.objects.filter(sacramento__in=partidas_de_prueba())
        .order_by("sacramento__tipo", "sacramento__numero", "tipo")
        .values_list("sacramento__numero", "tipo", "fecha", "descripcion")
    )
    return partidas, anotaciones


def conteos():
    modelos = (
        Pais,
        Departamento,
        Municipio,
        Documento,
        Fiel,
        Padre,
        Madre,
        Padrino,
        Ministro,
        Parroquia,
        Libro,
        Folio,
        Sacramento,
        Bautismo,
        PrimeraComunion,
        AnotacionMarginal,
        HistorialSacramento,
    )
    return {modelo.__name__: modelo.objects.count() for modelo in modelos}


class CargarDatosMasivosTests(TestCase):
    """El comando carga partidas de prueba que respetan las reglas de la app."""

    @override_settings(DEBUG=False)
    def test_sin_debug_sale_con_error_y_no_crea_nada(self):
        antes = conteos()
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            cargar()
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            borrar()
        self.assertEqual(conteos(), antes)
        self.assertFalse(Parroquia.objects.filter(nombre=masivos.NOMBRE_PARROQUIA).exists())

    @override_settings(DEBUG=True)
    def test_crea_la_cantidad_pedida_en_la_parroquia_de_pruebas(self):
        salida = cargar()
        self.assertIn("Tiempo total", salida)
        self.assertEqual(Sacramento.objects.filter(tipo=TipoSacramento.BAUTISMO).count(), 30)
        self.assertEqual(
            Sacramento.objects.filter(tipo=TipoSacramento.PRIMERA_COMUNION).count(), 10
        )
        self.assertEqual(Sacramento.objects.count(), partidas_de_prueba().count())
        self.assertFalse(
            Documento.objects.exclude(numero_documento__startswith=PREFIJO).exists(),
            "Todas las personas creadas deben tener documento 9991",
        )
        parroquia = Parroquia.objects.get(nombre=masivos.NOMBRE_PARROQUIA)
        cargos = set(Ministro.objects.filter(parroquia=parroquia).values_list("cargo", flat=True))
        self.assertEqual(cargos, {"Párroco", "Vicario", "Diácono"})
        self.assertEqual(parroquia.parroco.cargo, "Párroco")
        self.assertEqual(
            set(partidas_de_prueba().values_list("ministro__parroquia", flat=True)),
            {parroquia.pk},
        )

    @override_settings(DEBUG=True)
    def test_la_misma_semilla_produce_los_mismos_datos(self):
        cargar(semilla=5)
        primera = instantanea()
        borrar()
        cargar(semilla=5)
        self.assertEqual(instantanea(), primera)
        borrar()
        cargar(semilla=6)
        self.assertNotEqual(instantanea(), primera)

    @override_settings(DEBUG=True)
    def test_padrino_varon_madrina_mujer_y_distintos_de_los_padres(self):
        cargar(bautismos=60, primeras=0)
        bautismos = Bautismo.objects.select_related(
            "sacramento__fiel", "padre", "madre", "padrino", "madrina"
        )
        self.assertEqual(bautismos.count(), 60)
        for bautismo in bautismos:
            with self.subTest(numero=bautismo.sacramento.numero):
                self.assertTrue(bautismo.padrino or bautismo.madrina)
                familia = {
                    bautismo.sacramento.fiel.documento_id,
                    bautismo.padre.documento_id if bautismo.padre else None,
                    bautismo.madre.documento_id if bautismo.madre else None,
                }
                if bautismo.padrino:
                    self.assertIn(bautismo.padrino.nombre.split()[0], PRIMEROS_NOMBRES_HOMBRE)
                    self.assertNotIn(bautismo.padrino.documento_id, familia)
                if bautismo.madrina:
                    self.assertIn(bautismo.madrina.nombre.split()[0], PRIMEROS_NOMBRES_MUJER)
                    self.assertNotIn(bautismo.madrina.documento_id, familia)
                if bautismo.padre:
                    self.assertIn(bautismo.padre.nombre.split()[0], PRIMEROS_NOMBRES_HOMBRE)
                self.assertIn(bautismo.madre.nombre.split()[0], PRIMEROS_NOMBRES_MUJER)
        # Ningún padrino ni madrina coincide con un fiel del sexo contrario.
        self.assertFalse(
            Bautismo.objects.filter(
                Q(padrino__documento__fiel__sexo=Sexo.MUJER)
                | Q(madrina__documento__fiel__sexo=Sexo.HOMBRE)
            ).exists()
        )
        # Algunos padrinos repiten en varias partidas.
        self.assertTrue(
            Padrino.objects.annotate(
                usos=Count("bautismos_como_padrino") + Count("bautismos_como_madrina")
            )
            .filter(usos__gt=1)
            .exists()
        )

    @override_settings(DEBUG=True)
    def test_primeras_comuniones_enlazadas_con_8_a_12_anios_y_sin_duplicados(self):
        cargar(bautismos=60, primeras=20)
        primeras = PrimeraComunion.objects.select_related(
            "sacramento__fiel", "bautismo__sacramento"
        )
        self.assertEqual(primeras.count(), 20)
        enlazadas = [primera for primera in primeras if primera.bautismo_id]
        self.assertEqual(len(enlazadas), 17)  # 85 % de 20
        for primera in primeras:
            sacramento = primera.sacramento
            edad = edad_en_fecha(sacramento.fiel.fecha_nacimiento, sacramento.fecha)
            with self.subTest(numero=sacramento.numero):
                self.assertTrue(8 <= edad <= 12)
                self.assertEqual(primera.edad, edad)
                if primera.bautismo_id:
                    self.assertEqual(primera.bautismo.sacramento.fiel_id, sacramento.fiel_id)
                    self.assertGreater(sacramento.fecha, primera.bautismo.sacramento.fecha)
                    self.assertIn(primera.bautismo.sacramento.estado, VIGENTES)
                else:
                    self.assertTrue(primera.parroquia_bautismo)
                    self.assertIsNotNone(primera.libro_bautismo)
                    self.assertIsNotNone(primera.folio_bautismo)
                    self.assertIsNotNone(primera.numero_bautismo)
                    self.assertLess(primera.fecha_bautismo, sacramento.fecha)
                    self.assertIsNotNone(primera.padre)
                    self.assertIsNotNone(primera.madre)
        repetidas = (
            PrimeraComunion.objects.filter(sacramento__estado__in=VIGENTES)
            .values("sacramento__fiel")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
        )
        self.assertFalse(repetidas.exists())

    @override_settings(DEBUG=True)
    def test_numeracion_correlativa_libros_de_maximo_300_y_uno_abierto(self):
        cargar()
        for libro in Libro.objects.all():
            numeros = list(libro.sacramentos.order_by("numero").values_list("numero", flat=True))
            self.assertEqual(numeros, list(range(1, len(numeros) + 1)))
            self.assertLessEqual(len(numeros), 300)
            self.assertEqual(libro.total_folios * libro.partidas_por_folio, 300)

    @override_settings(DEBUG=True)
    def test_libro_lleno_se_cierra_y_se_abre_el_siguiente(self):
        with mock.patch.object(masivos, "MAX_PARTIDAS_POR_LIBRO", 12):
            cargar(bautismos=30, primeras=10)
        libros = Libro.objects.filter(tipo_libro=TipoLibro.BAUTISMOS).order_by("numero_libro")
        self.assertEqual([libro.numero_libro for libro in libros], [1, 2, 3])
        anterior = None
        for libro in libros:
            partidas = libro.sacramentos.order_by("numero")
            numeros = list(partidas.values_list("numero", flat=True))
            with self.subTest(libro=libro.nombre):
                self.assertEqual(numeros, list(range(1, len(numeros) + 1)))
                self.assertLessEqual(len(numeros), 12)
                registros = list(partidas.values_list("fecha_registro", flat=True))
                self.assertEqual(registros, sorted(registros))
                self.assertGreaterEqual(min(registros), libro.fecha_apertura)
                if libro.estado == EstadoLibro.CERRADO:
                    self.assertEqual(len(numeros), 12)
                    self.assertEqual(libro.fecha_cierre, max(registros))
                if anterior is not None:
                    self.assertEqual(libro.fecha_apertura, anterior.fecha_cierre)
            anterior = libro
        for tipo in (TipoLibro.BAUTISMOS, TipoLibro.PRIMERA_COMUNION):
            self.assertEqual(
                Libro.objects.filter(tipo_libro=tipo, estado=EstadoLibro.ABIERTO).count(), 1
            )

    @override_settings(DEBUG=True)
    def test_ninguna_fecha_de_registro_futura_ni_de_hoy(self):
        cargar()
        hoy = timezone.localdate()
        for sacramento in partidas_de_prueba():
            with self.subTest(numero=sacramento.numero, tipo=sacramento.tipo):
                self.assertLess(sacramento.fecha_registro, hoy)
                self.assertGreaterEqual(sacramento.fecha_registro, sacramento.fecha)
                self.assertLessEqual(
                    sacramento.fecha_registro - sacramento.fecha, timedelta(days=15)
                )
                self.assertLess(sacramento.creado_en.date(), hoy)
        self.assertFalse(AnotacionMarginal.objects.filter(fecha__gte=hoy).exists())
        self.assertFalse(
            Sacramento.objects.filter(
                tipo=TipoSacramento.BAUTISMO, fecha__lt=date(2012, 1, 1)
            ).exists()
        )
        self.assertFalse(
            Sacramento.objects.filter(
                tipo=TipoSacramento.PRIMERA_COMUNION, fecha__lt=date(2020, 1, 1)
            ).exists()
        )

    @override_settings(DEBUG=True)
    def test_correcciones_y_anulaciones_con_sus_anotaciones(self):
        cargar()
        for tipo in (TipoSacramento.BAUTISMO, TipoSacramento.PRIMERA_COMUNION):
            partidas = partidas_de_prueba().filter(tipo=tipo)
            corregidas = partidas.filter(estado=EstadoRegistro.CORREGIDO)
            anuladas = partidas.filter(estado=EstadoRegistro.ANULADO)
            with self.subTest(tipo=tipo):
                self.assertEqual(corregidas.count(), 1)
                self.assertEqual(anuladas.count(), 1)
                for sacramento in corregidas:
                    anotacion = sacramento.anotaciones_marginales.get()
                    self.assertEqual(anotacion.tipo, TipoAnotacionMarginal.CORRECCION)
                    self.assertGreaterEqual(anotacion.fecha, sacramento.fecha_registro)
                for sacramento in anuladas:
                    anotacion = sacramento.anotaciones_marginales.get()
                    self.assertEqual(anotacion.tipo, TipoAnotacionMarginal.ANULACION)
                    self.assertTrue(anotacion.descripcion.startswith("Partida anulada: "))
        # Un bautismo anulado nunca queda enlazado a una primera comunión.
        self.assertFalse(
            PrimeraComunion.objects.filter(
                bautismo__sacramento__estado=EstadoRegistro.ANULADO
            ).exists()
        )

    @override_settings(DEBUG=True)
    def test_segunda_carga_sin_borrar_no_duplica(self):
        cargar()
        total = Sacramento.objects.count()
        with self.assertRaisesMessage(CommandError, "--borrar"):
            cargar()
        self.assertEqual(Sacramento.objects.count(), total)

    @override_settings(DEBUG=True)
    def test_borrar_deja_la_base_como_estaba(self):
        call_command("cargar_datos_demo", stdout=io.StringIO())
        antes = conteos()
        demo = Documento.objects.filter(numero_documento__startswith="9990").count()
        cargar()
        self.assertGreater(Sacramento.objects.count(), antes["Sacramento"])
        salida = borrar()
        self.assertIn("Datos masivos eliminados", salida)
        self.assertEqual(conteos(), antes)
        self.assertEqual(
            Documento.objects.filter(numero_documento__startswith="9990").count(), demo
        )
        # Se puede volver a cargar después de borrar.
        cargar()
        self.assertEqual(partidas_de_prueba().count(), 40)

    @override_settings(DEBUG=True)
    def test_borrar_conserva_los_municipios_que_existian_y_se_usan(self):
        pais = Pais.objects.create(nombre="Colombia")
        norte = Departamento.objects.create(nombre="Norte de Santander", pais=pais)
        ocana = Municipio.objects.create(nombre="Ocaña", departamento=norte)
        abrego = Municipio.objects.create(nombre="Ábrego", departamento=norte)
        Parroquia.objects.create(nombre="San Rafael", municipio=ocana, direccion="Calle 1 # 2-3")
        documento = Documento.objects.create(
            tipo_documento=TipoDocumento.CC, numero_documento="1234567890"
        )
        Fiel.objects.create(
            documento=documento,
            nombres="Persona",
            apellidos="Real",
            fecha_nacimiento=date(1990, 1, 1),
            municipio_nacimiento=abrego,
        )

        cargar()
        self.assertEqual(Municipio.objects.filter(nombre="Ocaña").count(), 1)
        self.assertEqual(Municipio.objects.filter(nombre="Ábrego").count(), 1)
        self.assertTrue(Municipio.objects.filter(nombre="Aguachica").exists())
        borrar()

        self.assertTrue(Municipio.objects.filter(pk=ocana.pk).exists())
        self.assertTrue(Municipio.objects.filter(pk=abrego.pk).exists())
        self.assertTrue(Departamento.objects.filter(pk=norte.pk).exists())
        self.assertTrue(Pais.objects.filter(pk=pais.pk).exists())
        self.assertFalse(Municipio.objects.filter(nombre="La Playa de Belén").exists())
        self.assertFalse(Municipio.objects.filter(nombre="Aguachica").exists())
        self.assertFalse(Departamento.objects.filter(nombre="Cesar").exists())
        self.assertEqual(Municipio.objects.count(), 2)
        self.assertTrue(Fiel.objects.filter(documento=documento).exists())

    @override_settings(DEBUG=True)
    def test_exportar_datos_demo_no_incluye_datos_9991(self):
        call_command("cargar_datos_demo", stdout=io.StringIO())
        cargar()
        objetos = recolectar_datos_demo()
        self.assertTrue(objetos)
        pruebas = Parroquia.objects.get(nombre=masivos.NOMBRE_PARROQUIA)
        for objeto in objetos:
            with self.subTest(objeto=repr(objeto)):
                if isinstance(objeto, Documento):
                    self.assertFalse(objeto.numero_documento.startswith(PREFIJO))
                if isinstance(objeto, Parroquia):
                    self.assertNotEqual(objeto.pk, pruebas.pk)
                if isinstance(objeto, (Libro, Sacramento)):
                    self.assertNotEqual(objeto.parroquia_id, pruebas.pk)
        ids = {(type(objeto), objeto.pk) for objeto in objetos}
        maximo = partidas_de_prueba().aggregate(Max("pk"))["pk__max"]
        self.assertNotIn((Sacramento, maximo), ids)


class PlanificadorMasivoTests(SimpleTestCase):
    """El plan por defecto (650 bautismos y 350 primeras comuniones) es realista."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date(2026, 10, 25)
        planificador = masivos.Planificador(masivos.SEMILLA_DEFECTO, 650, 350, cls.hoy)
        cls.bautismos = planificador.planear_bautismos()
        cls.primeras = planificador.planear_primeras(cls.bautismos)
        cls.faltantes = planificador.primeras_externas_por_falta

    def test_bautismos_entre_2012_y_2025_mayormente_de_bebes(self):
        self.assertEqual(len(self.bautismos), 650)
        edades = []
        for plan in self.bautismos:
            self.assertGreaterEqual(plan["fecha"], date(2012, 1, 1))
            self.assertLessEqual(plan["fecha"], date(2025, 12, 31))
            edades.append(edad_en_fecha(plan["fiel"]["fecha_nacimiento"], plan["fecha"]))
        self.assertGreater(sum(edad == 0 for edad in edades) / len(edades), 0.8)
        self.assertLess(sum(edad >= 7 for edad in edades) / len(edades), 0.06)
        anios = {plan["fecha"].year for plan in self.bautismos}
        self.assertEqual(anios, set(range(2012, 2026)))

    def test_apellidos_de_los_hijos_y_adopciones(self):
        adoptivos = 0
        for plan in self.bautismos:
            apellidos = plan["fiel"]["apellidos"]
            madre = plan["madre"]["apellido"].split()
            if plan["padre"] is None:
                self.assertEqual(apellidos.split(), madre)
            else:
                padre = plan["padre"]["apellido"].split()
                self.assertEqual(apellidos.split(), [padre[0], madre[0]])
                self.assertTrue(plan["abuelo_paterno"].split()[-2] == padre[0])
            if plan["tipo_hijo"] == "Adoptivo":
                adoptivos += 1
                self.assertTrue(plan["padre_biologico_nombre"])
                self.assertTrue(plan["madre_biologica_nombre"])
            else:
                self.assertIsNotNone(plan["padre"])
        self.assertTrue(1 <= adoptivos <= 20)

    def test_primeras_comuniones_enlazadas_alcanzan_sin_pasar_a_externas(self):
        self.assertEqual(len(self.primeras), 350)
        self.assertEqual(self.faltantes, 0)
        enlazadas = [plan for plan in self.primeras if plan["bautismo"] is not None]
        self.assertEqual(len(enlazadas), round(350 * 0.85))
        for plan in self.primeras:
            edad = edad_en_fecha(plan["fiel"]["fecha_nacimiento"], plan["fecha"])
            self.assertTrue(8 <= edad <= 12)
            self.assertGreaterEqual(plan["fecha"], date(2020, 1, 1))
            self.assertLess(plan["fecha_registro"], self.hoy)
