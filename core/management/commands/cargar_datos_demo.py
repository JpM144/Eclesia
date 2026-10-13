"""Carga y borra datos de demostración para desarrollo.

El comando solo funciona con ``DEBUG=True``. En el modo de carga crea una
parroquia, tres ministros, un libro abierto por tipo, unas cuarenta personas con
documentos marcados con el prefijo ``9990`` y partidas de ejemplo, todo dentro
de una transacción y validando cada modelo con ``full_clean()`` antes de
guardarlo. La numeración de partidas se toma de ``parroquias.services``.

``--borrar`` elimina únicamente los datos de demostración (identificados por la
parroquia de los ministros marcados y por los documentos ``9990``) en el orden
que exigen las relaciones ``PROTECT``.

Uso:
    .\\.venv\\Scripts\\python manage.py cargar_datos_demo
    .\\.venv\\Scripts\\python manage.py cargar_datos_demo --borrar
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
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
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from parroquias.models import Folio, Libro, Ministro, Parroquia
from parroquias.services import siguiente_numero_partida
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    HistorialSacramento,
    Matrimonio,
    PrimeraComunion,
    ProclamaMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)
from ubicacion.models import Departamento, Municipio, Pais

PREFIJO_DOCUMENTO = "9990"
NOMBRE_PARROQUIA_DEFECTO = "Parroquia Demo"
DIRECCION_DEMO = "Carrera 7 # 12-34, Barrio Centro"
TELEFONO_DEMO = "601 742 0000"
EMAIL_DEMO = "parroquia.demo@ejemplo.co"

# Seis familias del demo. Cada familia tiene un padre y una madre (que también
# existen como fieles, para poder bautizarlos y casarlos) y dos hijos que
# comparten padres y se bautizan en la parroquia.
FAMILIAS = (
    {
        "padre": ("José Aníbal", "Restrepo", date(1986, 3, 12), Sexo.HOMBRE),
        "madre": ("Marta Lucía", "Gómez", date(1988, 7, 25), Sexo.MUJER),
        "hijos": (
            ("Juan José", "Restrepo Gómez", date(2010, 5, 3), Sexo.HOMBRE),
            ("Laura Sofía", "Restrepo Gómez", date(2013, 9, 14), Sexo.MUJER),
        ),
    },
    {
        "padre": ("Carlos Eduardo", "Zapata", date(1985, 1, 20), Sexo.HOMBRE),
        "madre": ("Diana Carolina", "Ruiz", date(1987, 11, 2), Sexo.MUJER),
        "hijos": (
            ("Andrés Felipe", "Zapata Ruiz", date(2011, 4, 18), Sexo.HOMBRE),
            ("Valentina", "Zapata Ruiz", date(2014, 2, 27), Sexo.MUJER),
        ),
    },
    {
        "padre": ("Luis Alberto", "Cárdenas", date(1983, 6, 9), Sexo.HOMBRE),
        "madre": ("Sandra Milena", "Torres", date(1984, 10, 30), Sexo.MUJER),
        "hijos": (
            ("Santiago", "Cárdenas Torres", date(2012, 8, 5), Sexo.HOMBRE),
            ("Isabella", "Cárdenas Torres", date(2015, 12, 1), Sexo.MUJER),
        ),
    },
    {
        "padre": ("Óscar Iván", "Herrera", date(1989, 2, 14), Sexo.HOMBRE),
        "madre": ("Paola Andrea", "Muñoz", date(1990, 5, 21), Sexo.MUJER),
        "hijos": (
            ("Samuel", "Herrera Muñoz", date(2016, 7, 11), Sexo.HOMBRE),
            ("Mariana", "Herrera Muñoz", date(2018, 3, 30), Sexo.MUJER),
        ),
    },
    {
        "padre": ("Jorge Hernán", "Ospina", date(1982, 9, 3), Sexo.HOMBRE),
        "madre": ("Claudia Patricia", "Ríos", date(1983, 12, 19), Sexo.MUJER),
        "hijos": (
            ("Tomás", "Ospina Ríos", date(2016, 1, 23), Sexo.HOMBRE),
            ("Salomé", "Ospina Ríos", date(2019, 6, 8), Sexo.MUJER),
        ),
    },
    {
        "padre": ("Diego Fernando", "Arango", date(1981, 4, 28), Sexo.HOMBRE),
        "madre": ("Yuliana Andrea", "Vélez", date(1984, 8, 16), Sexo.MUJER),
        "hijos": (
            ("Martín", "Arango Vélez", date(2015, 10, 4), Sexo.HOMBRE),
            ("Gabriela", "Arango Vélez", date(2018, 2, 12), Sexo.MUJER),
        ),
    },
)

# Fieles sueltos. Los dos primeros se bautizan en otra parroquia (solo tienen
# los datos externos), de los índices 2 a 9 salen los padrinos y los dos últimos
# se bautizan aquí (uno de ellos queda anulado).
EXTRAS = (
    ("Juan Esteban", "Pérez Mora", date(2015, 3, 9), Sexo.HOMBRE),
    ("Ricardo Andrés", "Salazar Nieto", date(1995, 6, 30), Sexo.HOMBRE),
    ("Camila", "Vargas Lozano", date(1992, 1, 15), Sexo.MUJER),
    ("Andrés Mauricio", "Jiménez Peña", date(1989, 11, 7), Sexo.HOMBRE),
    ("Natalia", "Cardona Mejía", date(1991, 4, 22), Sexo.MUJER),
    ("Felipe", "Quintero Rojas", date(1994, 8, 3), Sexo.HOMBRE),
    ("Daniela", "Moreno Castaño", date(1996, 12, 11), Sexo.MUJER),
    ("Alejandro", "Ramírez Cano", date(1987, 5, 26), Sexo.HOMBRE),
    ("Gabriela", "Castro Duarte", date(1998, 2, 18), Sexo.MUJER),
    ("Esteban", "Bedoya Salazar", date(1993, 9, 29), Sexo.HOMBRE),
    ("Sara", "Agudelo Marín", date(1997, 7, 13), Sexo.MUJER),
    ("Cristian", "Pineda Gómez", date(1990, 3, 6), Sexo.HOMBRE),
    ("Andrea Carolina", "López Castro", date(1988, 10, 24), Sexo.MUJER),
    ("Santiago", "Molina Herrera", date(2012, 6, 17), Sexo.HOMBRE),
    ("Manuela", "Betancur Ríos", date(2013, 12, 5), Sexo.MUJER),
    ("Julián", "Zuluaga Ospina", date(2009, 4, 11), Sexo.HOMBRE),
)

# Días transcurridos desde hoy para cada bautismo (26 en total). Los doce
# primeros son los padres (los más antiguos, para que su matrimonio sea
# posterior), después los doce hijos y al final los dos fieles sueltos. Así
# quedan repartidos por todo el último año y algunos meses concentran más.
DIAS_BAUTISMO = (
    360,
    345,
    330,
    318,
    300,
    288,
    270,
    255,
    240,
    228,
    210,
    198,
    185,
    170,
    155,
    140,
    125,
    110,
    95,
    80,
    66,
    52,
    38,
    25,
    15,
    8,
)

PADRES_MARIDOS = (0, 1, 2)  # familias que se casan (índices bajos)
DIAS_MATRIMONIO = (40, 25, 12)
PARTIDAS_POR_FOLIO = 3


def _fecha_hace_meses(hoy, meses):
    indice = hoy.year * 12 + (hoy.month - 1) - meses
    return date(indice // 12, indice % 12 + 1, 1)


def _aware(una_fecha, hora=10):
    momento = datetime.combine(una_fecha, time(hora, 0))
    return timezone.make_aware(momento, timezone.get_current_timezone())


class Command(BaseCommand):
    help = "Carga (o borra, con --borrar) datos de demostración en la base de desarrollo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--borrar",
            action="store_true",
            help="Elimina los datos de demostración en lugar de crearlos",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR(
                    "cargar_datos_demo solo funciona con DEBUG=True. "
                    "No se ha modificado la base de datos."
                )
            )
            return
        if options.get("borrar"):
            self._borrar()
        else:
            self._cargar()

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def _cargar(self):
        if Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO).exists():
            self.stdout.write(
                self.style.WARNING("Ya existen datos de demostración en la base; no se crea nada.")
            )
            return

        nombre = (settings.NOMBRE_PARROQUIA or "").strip()
        if not nombre or Parroquia.objects.filter(nombre=nombre).exists():
            nombre = NOMBRE_PARROQUIA_DEFECTO
        if Parroquia.objects.filter(nombre=nombre).exists():
            self.stdout.write(
                self.style.ERROR(f"Ya existe una parroquia llamada «{nombre}»; no se crea nada.")
            )
            return

        with transaction.atomic():
            self._construir(nombre)
        self._resumen_carga(nombre)

    def _construir(self, nombre_parroquia):
        hoy = timezone.localdate()
        self._hoy = hoy
        self._contador = 0
        self._padrinos = []

        municipio = Municipio.objects.order_by("pk").first()
        self._ubicacion_creada = municipio is None
        if municipio is None:
            pais = self._guardar(Pais(nombre="Colombia"))
            departamento = self._guardar(Departamento(nombre="Cundinamarca", pais=pais))
            municipio = self._guardar(Municipio(nombre="Bogotá", departamento=departamento))
        self._municipio = municipio

        parroquia = self._guardar(
            Parroquia(
                nombre=nombre_parroquia,
                municipio=municipio,
                direccion=DIRECCION_DEMO,
                telefono=TELEFONO_DEMO,
                email=EMAIL_DEMO,
            )
        )
        self._parroquia = parroquia

        parroco = self._guardar(
            Ministro(
                documento=self._documento(),
                nombre="Rafael",
                apellido="Betancur Restrepo",
                cargo=CargoMinisterial.PARROCO,
                fecha_nacimiento=date(1965, 6, 12),
                telefono="300 000 0001",
                email="parroco.demo@ejemplo.co",
                parroquia=parroquia,
            )
        )
        vicario = self._guardar(
            Ministro(
                documento=self._documento(),
                nombre="Andrés",
                apellido="Salgado Medina",
                cargo=CargoMinisterial.VICARIO,
                fecha_nacimiento=date(1978, 2, 3),
                telefono="300 000 0002",
                email="vicario.demo@ejemplo.co",
                parroquia=parroquia,
            )
        )
        diacono = self._guardar(
            Ministro(
                documento=self._documento(),
                nombre="Hernán",
                apellido="Quiroga Peña",
                cargo=CargoMinisterial.DIACONO,
                fecha_nacimiento=date(1980, 9, 25),
                telefono="300 000 0003",
                email="diacono.demo@ejemplo.co",
                parroquia=parroquia,
            )
        )
        parroquia.parroco = parroco
        parroquia.save(update_fields=["parroco"])
        self._ministros = (parroco, vicario, diacono)

        apertura = _fecha_hace_meses(hoy, 13)
        self._libros = {}
        for tipo, etiqueta in (
            (TipoLibro.BAUTISMOS, "Bautismos"),
            (TipoLibro.PRIMERA_COMUNION, "Primera Comunión"),
            (TipoLibro.CONFIRMACIONES, "Confirmaciones"),
            (TipoLibro.MATRIMONIOS, "Matrimonios"),
        ):
            self._libros[tipo] = self._guardar(
                Libro(
                    nombre=f"{etiqueta} 1",
                    tipo_libro=tipo,
                    detalle=f"Libro de {etiqueta.lower()} de {nombre_parroquia}.",
                    numero_libro=1,
                    fecha_apertura=apertura,
                    total_folios=200,
                    ministro_apertura=parroco,
                    estado=EstadoLibro.ABIERTO,
                    parroquia=parroquia,
                )
            )

        self._crear_personas()
        self._crear_bautismos()
        self._crear_primeras_comuniones()
        self._crear_confirmaciones()
        self._crear_matrimonios()
        self._crear_anotaciones()

    def _crear_personas(self):
        self._familias = []
        for familia in FAMILIAS:
            padre = self._crear_persona_con_fila(familia["padre"], es_padre=True)
            madre = self._crear_persona_con_fila(familia["madre"], es_padre=False)
            hijos = []
            for nombres, apellidos, nacimiento, sexo in familia["hijos"]:
                documento = self._documento(TipoDocumento.RC)
                fiel = self._guardar(
                    Fiel(
                        documento=documento,
                        nombres=nombres,
                        apellidos=apellidos,
                        fecha_nacimiento=nacimiento,
                        municipio_nacimiento=self._municipio,
                        sexo=sexo,
                    )
                )
                hijos.append({"fiel": fiel, "documento": documento})
            self._familias.append({"padre": padre, "madre": madre, "hijos": hijos})

        self._extras = []
        for nombres, apellidos, nacimiento, sexo in EXTRAS:
            edad = self._hoy.year - nacimiento.year
            tipo = TipoDocumento.RC if edad < 18 else TipoDocumento.CC
            documento = self._documento(tipo)
            fiel = self._guardar(
                Fiel(
                    documento=documento,
                    nombres=nombres,
                    apellidos=apellidos,
                    fecha_nacimiento=nacimiento,
                    municipio_nacimiento=self._municipio,
                    sexo=sexo,
                )
            )
            self._extras.append({"fiel": fiel, "documento": documento})

        for extra in self._extras[2:10]:
            self._padrinos.append(
                self._guardar(
                    Padrino(
                        documento=extra["documento"],
                        nombre=f"{extra['fiel'].nombres} {extra['fiel'].apellidos}",
                    )
                )
            )

    def _crear_persona_con_fila(self, datos, es_padre):
        nombres, apellido, nacimiento, sexo = datos
        documento = self._documento(TipoDocumento.CC)
        fiel = self._guardar(
            Fiel(
                documento=documento,
                nombres=nombres,
                apellidos=apellido,
                fecha_nacimiento=nacimiento,
                municipio_nacimiento=self._municipio,
                sexo=sexo,
            )
        )
        modelo = Padre if es_padre else Madre
        fila = self._guardar(modelo(documento=documento, nombre=nombres, apellido=apellido))
        return {"fiel": fiel, "fila": fila, "documento": documento}

    # ------------------------------------------------------------------
    # Partidas
    # ------------------------------------------------------------------
    def _crear_bautismos(self):
        bautizables = []
        for familia in self._familias:
            bautizables.append({"fiel": familia["padre"]["fiel"], "padre": None, "madre": None})
            bautizables.append({"fiel": familia["madre"]["fiel"], "padre": None, "madre": None})
        for familia in self._familias:
            for hijo in familia["hijos"]:
                bautizables.append(
                    {
                        "fiel": hijo["fiel"],
                        "padre": familia["padre"]["fila"],
                        "madre": familia["madre"]["fila"],
                    }
                )
        bautizables.append({"fiel": self._extras[-1]["fiel"], "padre": None, "madre": None})
        bautizables.append(
            {
                "fiel": self._extras[-2]["fiel"],
                "padre": None,
                "madre": None,
                "anulado": True,
            }
        )

        libro = self._libros[TipoLibro.BAUTISMOS]
        folio, en_folio = None, 0
        self._bautismo_de = {}
        for indice, item in enumerate(bautizables):
            fecha = self._hoy - timedelta(days=DIAS_BAUTISMO[indice])
            if folio is None or en_folio >= PARTIDAS_POR_FOLIO:
                numero_folio = folio.numero_folio + 1 if folio else 1
                folio = self._crear_folio(libro, numero_folio)
                en_folio = 1
            else:
                en_folio += 1
            anulado = item.get("anulado", False)
            sacramento = self._crear_sacramento(
                tipo=TipoSacramento.BAUTISMO,
                libro=libro,
                folio=folio,
                fecha=fecha,
                fiel=item["fiel"],
                estado=EstadoRegistro.ANULADO if anulado else EstadoRegistro.ACTIVO,
                observaciones=(
                    "Partida anulada por error en el nombre del bautizado; "
                    "se levantó una nueva partida. (dato de demostración)"
                    if anulado
                    else ""
                ),
                ministro=self._ministros[indice % len(self._ministros)],
            )
            padrino = self._padrinos[indice % len(self._padrinos)]
            madrina = self._padrinos[(indice + 3) % len(self._padrinos)]
            bautismo = self._guardar(
                Bautismo(
                    sacramento=sacramento,
                    padre=item["padre"],
                    madre=item["madre"],
                    abuelo_paterno="Hernán " + (item["padre"].apellido if item["padre"] else ""),
                    abuela_paterna="Rosa " + (item["padre"].apellido if item["padre"] else ""),
                    abuelo_materno="Alonso " + (item["madre"].apellido if item["madre"] else ""),
                    abuela_materna="Clara " + (item["madre"].apellido if item["madre"] else ""),
                    tipo_hijo=TipoHijo.BIOLOGICO,
                    padrino=padrino,
                    madrina=madrina,
                    quien_firma=self._ministros[0],
                    doy_fe=self._ministros[0],
                )
            )
            self._registrar_historial(
                sacramento,
                AccionHistorial.CREACION,
                "Registro creado en el libro de bautismos.",
                fecha,
            )
            if anulado:
                self._registrar_historial(
                    sacramento,
                    AccionHistorial.ANULACION,
                    "Partida anulada por error en el nombre del bautizado.",
                    min(fecha + timedelta(days=15), self._hoy),
                )
            self._bautismo_de[item["fiel"].pk] = {
                "sacramento": sacramento,
                "bautismo": bautismo,
                "fecha": fecha,
                "anulado": anulado,
            }

        # Algunas modificaciones coherentes posteriores al registro.
        for registro in list(self._bautismo_de.values())[:5]:
            self._registrar_historial(
                registro["sacramento"],
                AccionHistorial.MODIFICACION,
                "Corrección de datos del padre o la madre.",
                min(registro["fecha"] + timedelta(days=30), self._hoy),
            )

    def _crear_primeras_comuniones(self):
        libro = self._libros[TipoLibro.PRIMERA_COMUNION]
        hijas = [hijo["fiel"] for familia in self._familias for hijo in familia["hijos"]]
        recipientes = [self._bautismo_de[fiel.pk] for fiel in hijas[:7]]

        folio, en_folio = None, 0
        for indice, registro in enumerate(recipientes):
            fecha = min(registro["fecha"] + timedelta(days=120), self._hoy - timedelta(days=10))
            folio, en_folio = self._siguiente_folio(libro, folio, en_folio, 4)
            sacramento = self._crear_sacramento(
                tipo=TipoSacramento.PRIMERA_COMUNION,
                libro=libro,
                folio=folio,
                fecha=fecha,
                fiel=registro["bautismo"].sacramento.fiel,
                ministro=self._ministros[indice % len(self._ministros)],
            )
            fiel = registro["bautismo"].sacramento.fiel
            self._guardar(
                PrimeraComunion(
                    sacramento=sacramento,
                    edad=self._edad(fiel.fecha_nacimiento, fecha),
                    bautismo=registro["bautismo"],
                    doy_fe=self._ministros[0],
                )
            )
            self._registrar_historial(
                sacramento,
                AccionHistorial.CREACION,
                "Registro creado en el libro de primeras comuniones.",
                fecha,
            )

        # Una persona bautizada en otra parroquia (sin bautismo en el sistema).
        externa = self._extras[0]["fiel"]
        fecha = self._hoy - timedelta(days=45)
        folio, en_folio = self._siguiente_folio(libro, folio, en_folio, 4)
        sacramento = self._crear_sacramento(
            tipo=TipoSacramento.PRIMERA_COMUNION,
            libro=libro,
            folio=folio,
            fecha=fecha,
            fiel=externa,
            ministro=self._ministros[0],
        )
        primera = self._guardar(
            PrimeraComunion(
                sacramento=sacramento,
                edad=self._edad(externa.fecha_nacimiento, fecha),
                fecha_bautismo=date(2016, 11, 20),
                parroquia_bautismo="Parroquia San Francisco de Asís",
                municipio_bautismo=self._municipio,
                libro_bautismo=3,
                folio_bautismo=42,
                numero_bautismo=215,
                observaciones_bautismo="Bautizado en la parroquia de su barrio.",
                doy_fe=self._ministros[0],
            )
        )
        self._registrar_historial(
            sacramento,
            AccionHistorial.CREACION,
            "Registro creado en el libro de primeras comuniones.",
            fecha,
        )
        self._primera_externa = primera

    def _crear_confirmaciones(self):
        libro = self._libros[TipoLibro.CONFIRMACIONES]
        self._confirmacion_de = {}
        padrinos_fieles = [familia["padre"]["fiel"] for familia in self._familias[:5]]
        recipientes = [self._bautismo_de[fiel.pk] for fiel in padrinos_fieles]

        folio, en_folio = None, 0
        for indice, registro in enumerate(recipientes):
            fecha = min(registro["fecha"] + timedelta(days=180), self._hoy - timedelta(days=8))
            folio, en_folio = self._siguiente_folio(libro, folio, en_folio, PARTIDAS_POR_FOLIO)
            fiel = registro["bautismo"].sacramento.fiel
            sacramento = self._crear_sacramento(
                tipo=TipoSacramento.CONFIRMACION,
                libro=libro,
                folio=folio,
                fecha=fecha,
                fiel=fiel,
                ministro=self._ministros[1],
            )
            confirmacion = self._guardar(
                Confirmacion(
                    sacramento=sacramento,
                    edad=self._edad(fiel.fecha_nacimiento, fecha),
                    bautismo=registro["bautismo"],
                    padrino=self._padrinos[(indice + 1) % len(self._padrinos)],
                    doy_fe=self._ministros[1],
                )
            )
            self._registrar_historial(
                sacramento,
                AccionHistorial.CREACION,
                "Registro creado en el libro de confirmaciones.",
                fecha,
            )
            self._confirmacion_de[fiel.pk] = confirmacion

        externa = self._extras[1]["fiel"]
        fecha = self._hoy - timedelta(days=20)
        folio, en_folio = self._siguiente_folio(libro, folio, en_folio, PARTIDAS_POR_FOLIO)
        sacramento = self._crear_sacramento(
            tipo=TipoSacramento.CONFIRMACION,
            libro=libro,
            folio=folio,
            fecha=fecha,
            fiel=externa,
            ministro=self._ministros[1],
        )
        confirmacion = self._guardar(
            Confirmacion(
                sacramento=sacramento,
                edad=self._edad(externa.fecha_nacimiento, fecha),
                fecha_bautismo=date(2004, 4, 18),
                parroquia_bautismo="Parroquia Nuestra Señora del Carmen",
                municipio_bautismo=self._municipio,
                libro_bautismo=1,
                folio_bautismo=88,
                numero_bautismo=134,
                doy_fe=self._ministros[1],
            )
        )
        self._registrar_historial(
            sacramento,
            AccionHistorial.CREACION,
            "Registro creado en el libro de confirmaciones.",
            fecha,
        )
        self._confirmacion_externa = confirmacion

    def _crear_matrimonios(self):
        libro = self._libros[TipoLibro.MATRIMONIOS]
        self._matrimonios = []
        for numero, indice in enumerate(PADRES_MARIDOS):
            familia = self._familias[indice]
            fecha = self._hoy - timedelta(days=DIAS_MATRIMONIO[numero])
            folio = self._crear_folio(libro, numero + 1)
            sacramento = self._crear_sacramento(
                tipo=TipoSacramento.MATRIMONIO,
                libro=libro,
                folio=folio,
                fecha=fecha,
                fiel=None,
                ministro=self._ministros[0],
            )
            matrimonio = self._guardar(
                Matrimonio(
                    sacramento=sacramento,
                    expediente=100 + numero,
                    fecha_declaracion=fecha - timedelta(days=60),
                )
            )
            for persona in (familia["padre"], familia["madre"]):
                bautismo = self._bautismo_de[persona["fiel"].pk]
                self._guardar(
                    Contrayente(
                        matrimonio=matrimonio,
                        fiel=persona["fiel"],
                        sexo=persona["fiel"].sexo,
                        parroquia_bautismo=self._parroquia,
                        libro_bautismo=bautismo["sacramento"].folio.libro.numero_libro or 1,
                        folio_bautismo=bautismo["sacramento"].folio.numero_folio,
                        numero_bautismo=bautismo["sacramento"].numero,
                        parroquia_confirmacion=self._parroquia,
                        fecha_confirmacion=bautismo["fecha"] + timedelta(days=150),
                        direccion_residencia=DIRECCION_DEMO,
                        nombre_padre="José " + persona["fiel"].apellidos.split()[0],
                        nombre_madre="María " + persona["fiel"].apellidos.split()[0],
                        edad=self._edad(persona["fiel"].fecha_nacimiento, fecha),
                        estado_civil=EstadoCivil.SOLTERO,
                        religion="Católica",
                        profesion="Docente",
                        acepta_libertad_matrimonio=RespuestaDoctrina.SI,
                        conoce_unidad_indisolubilidad=RespuestaDoctrina.SI,
                        conoce_obligaciones_familia=RespuestaDoctrina.SI,
                        impedimentos_anteriores=RespuestaDoctrina.NO,
                        dispuesto_cumplir=RespuestaDoctrina.SI,
                        lugar_despues_matrimonio="Fijará su residencia en el barrio Centro.",
                    )
                )

            for testigo_numero in range(2):
                extra = self._extras[10 + numero * 2 + testigo_numero]
                self._guardar(
                    TestigoMatrimonio(
                        matrimonio=matrimonio,
                        tipo_documento=extra["documento"].tipo_documento,
                        cedula=extra["documento"].numero_documento,
                        nombre=f"{extra['fiel'].nombres} {extra['fiel'].apellidos}",
                        religion="Católica",
                        estado_civil=EstadoCivil.CASADO,
                        profesion="Comerciante",
                    )
                )

            for proclama_numero in (1, 2):
                self._guardar(
                    ProclamaMatrimonio(
                        matrimonio=matrimonio,
                        numero=proclama_numero,
                        fecha_proclama=fecha - timedelta(days=21 - (proclama_numero - 1) * 7),
                        resultado=(
                            ResultadoProclama.PUBLICADA
                            if proclama_numero == 1
                            else ResultadoProclama.SIN_IMPEDIMENTOS
                        ),
                    )
                )

            self._registrar_historial(
                sacramento,
                AccionHistorial.CREACION,
                "Registro creado en el libro de matrimonios.",
                fecha,
            )
            self._matrimonios.append({"matrimonio": matrimonio, "familia": familia})

    def _crear_anotaciones(self):
        # Confirmaciones de bautizados en la demo -> ANOTADA en su bautismo.
        for fiel_pk, confirmacion in self._confirmacion_de.items():
            bautismo = self._bautismo_de[fiel_pk]
            self._guardar(
                AnotacionMarginal(
                    sacramento=bautismo["sacramento"],
                    sacramento_origen=confirmacion.sacramento,
                    tipo=TipoAnotacionMarginal.CONFIRMACION,
                    fecha=confirmacion.sacramento.fecha,
                    descripcion=(
                        "Se anota la confirmación recibida en esta parroquia, "
                        "con la referencia de la partida."
                    ),
                    estado=EstadoAnotacion.ANOTADA,
                )
            )

        # Matrimonios de bautizados en la demo -> ANOTADA en cada bautismo.
        for registro in self._matrimonios:
            matrimonio = registro["matrimonio"]
            for persona in (registro["familia"]["padre"], registro["familia"]["madre"]):
                bautismo = self._bautismo_de[persona["fiel"].pk]
                self._guardar(
                    AnotacionMarginal(
                        sacramento=bautismo["sacramento"],
                        sacramento_origen=matrimonio.sacramento,
                        tipo=TipoAnotacionMarginal.MATRIMONIO,
                        fecha=matrimonio.sacramento.fecha,
                        descripcion=(
                            "Se anota el matrimonio celebrado en esta parroquia, "
                            "con el número de expediente y partida."
                        ),
                        estado=EstadoAnotacion.ANOTADA,
                    )
                )

        # Bautizados en otra parroquia: dos por comunicar.
        primera = self._primera_externa
        self._guardar(
            AnotacionMarginal(
                sacramento=None,
                sacramento_origen=primera.sacramento,
                tipo=TipoAnotacionMarginal.OTRO,
                fecha=primera.sacramento.fecha,
                descripcion="Comunicar la primera comunión a la parroquia de bautismo.",
                estado=EstadoAnotacion.POR_COMUNICAR,
                parroquia_destino_texto="Parroquia San Francisco de Asís",
            )
        )
        externa = self._confirmacion_externa
        self._guardar(
            AnotacionMarginal(
                sacramento=None,
                sacramento_origen=externa.sacramento,
                tipo=TipoAnotacionMarginal.CONFIRMACION,
                fecha=externa.sacramento.fecha,
                descripcion="Comunicar la confirmación a la parroquia de bautismo.",
                estado=EstadoAnotacion.POR_COMUNICAR,
                parroquia_destino_texto="Parroquia Nuestra Señora del Carmen",
            )
        )

        # Una anotación ya comunicada, con fecha.
        self._guardar(
            AnotacionMarginal(
                sacramento=None,
                sacramento_origen=externa.sacramento,
                tipo=TipoAnotacionMarginal.CONFIRMACION,
                fecha=externa.sacramento.fecha,
                descripcion="Notificación de la confirmación enviada y confirmada.",
                estado=EstadoAnotacion.COMUNICADA,
                parroquia_destino_texto="Parroquia Nuestra Señora del Carmen",
                fecha_comunicacion=min(externa.sacramento.fecha + timedelta(days=7), self._hoy),
            )
        )

    # ------------------------------------------------------------------
    # Utilidades de creación
    # ------------------------------------------------------------------
    def _documento(self, tipo=TipoDocumento.CC):
        self._contador += 1
        numero = f"{PREFIJO_DOCUMENTO}{self._contador:06d}"
        return self._guardar(Documento(tipo_documento=tipo, numero_documento=numero))

    def _guardar(self, objeto):
        objeto.full_clean()
        objeto.save()
        return objeto

    def _crear_folio(self, libro, numero_folio):
        return self._guardar(
            Folio(libro=libro, numero_folio=numero_folio, fecha_creacion=libro.fecha_apertura)
        )

    def _siguiente_folio(self, libro, folio, en_folio, por_folio):
        if folio is None or en_folio >= por_folio:
            numero_folio = folio.numero_folio + 1 if folio else 1
            folio = self._crear_folio(libro, numero_folio)
            en_folio = 0
        return folio, en_folio + 1

    def _crear_sacramento(self, **datos):
        datos.setdefault("estado", EstadoRegistro.ACTIVO)
        datos.setdefault("observaciones", "")
        datos["parroquia"] = self._parroquia
        sacramento = Sacramento(
            numero=siguiente_numero_partida(datos["libro"]),
            fecha_registro=datos["fecha"],
            **datos,
        )
        return self._guardar(sacramento)

    def _registrar_historial(self, sacramento, accion, descripcion, fecha):
        entrada = HistorialSacramento(sacramento=sacramento, accion=accion, descripcion=descripcion)
        self._guardar(entrada)
        HistorialSacramento.objects.filter(pk=entrada.pk).update(fecha=_aware(fecha))
        return entrada

    @staticmethod
    def _edad(nacimiento, referencia):
        cumplio_este_ano = (referencia.month, referencia.day) >= (nacimiento.month, nacimiento.day)
        return max(referencia.year - nacimiento.year - (0 if cumplio_este_ano else 1), 0)

    # ------------------------------------------------------------------
    # Resumen de la carga
    # ------------------------------------------------------------------
    def _resumen_carga(self, nombre_parroquia):
        documentos = Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO)
        bautismos = Bautismo.objects.filter(sacramento__libro__parroquia__nombre=nombre_parroquia)
        anotaciones = AnotacionMarginal.objects.filter(
            Q(sacramento__libro__parroquia__nombre=nombre_parroquia)
            | Q(sacramento_origen__libro__parroquia__nombre=nombre_parroquia)
        ).distinct()
        historial = HistorialSacramento.objects.filter(
            sacramento__libro__parroquia__nombre=nombre_parroquia
        )
        partidas_demo = Sacramento.objects.filter(libro__parroquia__nombre=nombre_parroquia)

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados:"))
        self.stdout.write(f"  Parroquia: {nombre_parroquia}")
        self.stdout.write(f"  Documentos demo (9990…): {documentos.count()}")
        self.stdout.write(f"  Fieles: {Fiel.objects.filter(documento__in=documentos).count()}")
        self.stdout.write(f"  Padres: {Padre.objects.filter(documento__in=documentos).count()}")
        self.stdout.write(f"  Madres: {Madre.objects.filter(documento__in=documentos).count()}")
        self.stdout.write(f"  Padrinos: {Padrino.objects.filter(documento__in=documentos).count()}")
        self.stdout.write(
            f"  Ministros: {Ministro.objects.filter(documento__in=documentos).count()}"
        )
        self.stdout.write(
            f"  Libros abiertos: {Libro.objects.filter(parroquia__nombre=nombre_parroquia).count()}"
        )
        self.stdout.write(
            "  Bautismos: "
            f"{bautismos.exclude(sacramento__estado=EstadoRegistro.ANULADO).count()} activos, "
            f"{bautismos.filter(sacramento__estado=EstadoRegistro.ANULADO).count()} anulados"
        )
        totales = {
            TipoSacramento.PRIMERA_COMUNION: "Primeras comuniones",
            TipoSacramento.CONFIRMACION: "Confirmaciones",
            TipoSacramento.MATRIMONIO: "Matrimonios",
        }
        for tipo, etiqueta in totales.items():
            self.stdout.write(f"  {etiqueta}: {partidas_demo.filter(tipo=tipo).count()}")
        for estado, etiqueta in (
            (EstadoAnotacion.ANOTADA, "Anotadas"),
            (EstadoAnotacion.POR_COMUNICAR, "Por comunicar"),
            (EstadoAnotacion.COMUNICADA, "Comunicadas"),
        ):
            self.stdout.write(
                f"  Anotaciones {etiqueta}: {anotaciones.filter(estado=estado).count()}"
            )
        self.stdout.write(
            "  Historial: "
            f"{historial.count()} entradas "
            f"(creación {historial.filter(accion=AccionHistorial.CREACION).count()}, "
            f"modificación {historial.filter(accion=AccionHistorial.MODIFICACION).count()}, "
            f"anulación {historial.filter(accion=AccionHistorial.ANULACION).count()})"
        )

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def _borrar(self):
        documentos = Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO)
        ministros = Ministro.objects.filter(documento__in=documentos)
        if not documentos.exists() and not ministros.exists():
            self.stdout.write(self.style.WARNING("No hay datos de demostración que borrar."))
            return

        parroquia = Parroquia.objects.filter(
            pk__in=ministros.values_list("parroquia_id", flat=True)
        ).first()
        libros = Libro.objects.filter(parroquia=parroquia) if parroquia else Libro.objects.none()
        partidas = (
            Sacramento.objects.filter(Q(parroquia=parroquia) | Q(libro__parroquia=parroquia))
            if parroquia
            else Sacramento.objects.none()
        )
        ids = list(partidas.values_list("pk", flat=True))
        anotaciones = AnotacionMarginal.objects.filter(
            Q(sacramento_id__in=ids) | Q(sacramento_origen_id__in=ids)
        )
        historial = HistorialSacramento.objects.filter(sacramento_id__in=ids)
        bautismos = Bautismo.objects.filter(sacramento_id__in=ids)
        primeras = PrimeraComunion.objects.filter(sacramento_id__in=ids)
        confirmaciones = Confirmacion.objects.filter(sacramento_id__in=ids)
        matrimonios = Matrimonio.objects.filter(sacramento_id__in=ids)
        folios = Folio.objects.filter(libro__in=libros)
        fieles = Fiel.objects.filter(documento__in=documentos)
        padres = Padre.objects.filter(documento__in=documentos)
        madres = Madre.objects.filter(documento__in=documentos)
        padrinos = Padrino.objects.filter(documento__in=documentos)
        municipio = parroquia.municipio if parroquia else None

        conteos = {
            "partidas": len(ids),
            "bautismos": bautismos.count(),
            "primeras_comuniones": primeras.count(),
            "confirmaciones": confirmaciones.count(),
            "matrimonios": matrimonios.count(),
            "anotaciones": anotaciones.count(),
            "historial": historial.count(),
            "folios": folios.count(),
            "libros": libros.count(),
            "fieles": fieles.count(),
            "padres": padres.count(),
            "madres": madres.count(),
            "padrinos": padrinos.count(),
            "documentos": documentos.count(),
            "ministros": ministros.count(),
            "parroquias": 1 if parroquia else 0,
        }

        with transaction.atomic():
            anotaciones.delete()
            historial.delete()
            confirmaciones.delete()
            primeras.delete()
            matrimonios.delete()
            bautismos.delete()
            partidas.delete()
            folios.delete()
            libros.delete()
            padrinos.delete()
            padres.delete()
            madres.delete()
            fieles.delete()
            ministros.delete()
            if parroquia:
                parroquia.delete()
            documentos.delete()
            conteos["ubicacion"] = self._borrar_ubicacion_si_sin_uso(municipio)

        self.stdout.write(self.style.SUCCESS("Datos de demostración eliminados:"))
        self.stdout.write(f"  Partidas: {conteos['partidas']}")
        self.stdout.write(f"  Bautismos: {conteos['bautismos']}")
        self.stdout.write(f"  Primeras comuniones: {conteos['primeras_comuniones']}")
        self.stdout.write(f"  Confirmaciones: {conteos['confirmaciones']}")
        self.stdout.write(f"  Matrimonios: {conteos['matrimonios']}")
        self.stdout.write(f"  Anotaciones marginales: {conteos['anotaciones']}")
        self.stdout.write(f"  Entradas de historial: {conteos['historial']}")
        self.stdout.write(f"  Folios: {conteos['folios']}")
        self.stdout.write(f"  Libros: {conteos['libros']}")
        self.stdout.write(f"  Fieles: {conteos['fieles']}")
        self.stdout.write(f"  Padres: {conteos['padres']}")
        self.stdout.write(f"  Madres: {conteos['madres']}")
        self.stdout.write(f"  Padrinos: {conteos['padrinos']}")
        self.stdout.write(f"  Documentos: {conteos['documentos']}")
        self.stdout.write(f"  Ministros: {conteos['ministros']}")
        self.stdout.write(f"  Parroquias: {conteos['parroquias']}")
        if conteos["ubicacion"]:
            self.stdout.write(f"  Ubicación (país/departamento/municipio): {conteos['ubicacion']}")

    def _borrar_ubicacion_si_sin_uso(self, municipio):
        if municipio is None:
            return 0
        en_uso = (
            Parroquia.objects.filter(municipio=municipio).exists()
            or Fiel.objects.filter(municipio_nacimiento=municipio).exists()
            or Confirmacion.objects.filter(municipio_bautismo=municipio).exists()
            or PrimeraComunion.objects.filter(municipio_bautismo=municipio).exists()
        )
        if en_uso:
            return 0
        borrados = 0
        departamento = municipio.departamento
        pais = departamento.pais
        municipio.delete()
        borrados += 1
        if not Municipio.objects.filter(departamento=departamento).exists():
            departamento.delete()
            borrados += 1
            if not Departamento.objects.filter(pais=pais).exists():
                pais.delete()
                borrados += 1
        return borrados
