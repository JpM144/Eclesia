"""Carga (o borra) un volumen grande de partidas de prueba para desarrollo.

El comando solo funciona con ``DEBUG=True``. Crea una parroquia propia,
«Parroquia de Pruebas», con su párroco, un vicario y un diácono, y registra en
ella bautismos y primeras comuniones realistas (por defecto 650 y 350) con todas
sus personas. Los documentos de todas las personas empiezan por ``9991``, así
no se confunden con los datos reales ni con los del demo (``9990``).

Las partidas se registran con los servicios de la app (``registrar_bautismo``,
``registrar_primera_comunion``, ``corregir_*`` y ``anular_*``), que asignan el
folio y el número y validan cada modelo. Las reglas que la app aplica en los
formularios (B1, B2, sexo de padrino y madrina, P1 a P3) se comprueban aquí
antes de llamar al servicio. Los servicios fijan la fecha de registro en «hoy»:
justo después de crear cada partida se mueve a una fecha realista (de 0 a 15
días después del sacramento, nunca futura ni de hoy, y sin retroceder respecto
de la partida anterior del libro) y se valida otra vez con ``full_clean()``.

Todo el plan se genera primero en memoria con ``random.Random(semilla)``, así que
la misma semilla produce los mismos datos. Cada libro guarda como máximo 300
partidas: al llenarse se cierra con ``cerrar_libro`` y se abre el siguiente.

``--borrar`` elimina solo lo de la Parroquia de Pruebas y las personas ``9991``,
y los municipios de la lista del comando que ya nadie use.

Uso:
    .\\.venv\\Scripts\\python manage.py cargar_datos_masivos
    .\\.venv\\Scripts\\python manage.py cargar_datos_masivos --bautismos 100 --semilla 7
    .\\.venv\\Scripts\\python manage.py cargar_datos_masivos --borrar
"""

import math
import random
import time as reloj
from collections import Counter
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from core.choices import (
    AccionHistorial,
    CargoMinisterial,
    EstadoRegistro,
    Sexo,
    TipoAnotacionMarginal,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
    TipoSacramento,
)
from parroquias.models import Folio, Libro, Ministro, Parroquia
from parroquias.services import cerrar_libro
from personas.models import Documento, Fiel, Madre, Padre, Padrino
from sacramentos.models import (
    AnotacionMarginal,
    Bautismo,
    HistorialSacramento,
    PartidaEliminada,
    PrimeraComunion,
    Sacramento,
)
from sacramentos.reglas import edad_en_fecha
from sacramentos.services import (
    anular_bautismo,
    anular_primera_comunion,
    corregir_bautismo,
    corregir_primera_comunion,
    registrar_bautismo,
    registrar_primera_comunion,
)
from ubicacion.models import Departamento, Municipio, Pais

PREFIJO_DOCUMENTO = "9991"
NOMBRE_PARROQUIA = "Parroquia de Pruebas"
DIRECCION_PARROQUIA = "Calle de Pruebas # 1-23"

BAUTISMOS_DEFECTO = 650
PRIMERAS_DEFECTO = 350
SEMILLA_DEFECTO = 2026
TAMANO_LOTE = 100
MAX_PARTIDAS_POR_LIBRO = 300
PARTIDAS_POR_FOLIO = 3

INICIO_BAUTISMOS = date(2012, 1, 1)
FIN_BAUTISMOS = date(2025, 12, 31)
INICIO_PRIMERAS = date(2020, 1, 1)
EDAD_MINIMA_PRIMERA = 8
EDAD_MAXIMA_PRIMERA = 12

PROPORCION_ENLAZADAS = 0.85
PROPORCION_CORREGIDAS = 0.03
PROPORCION_ANULADAS = 0.01
PROBABILIDAD_ADOPTIVO = 0.015
PROBABILIDAD_ADOPCION_SIN_PADRE = 0.35
PROBABILIDAD_REPETIR_PADRINO = 0.3

PAIS = "Colombia"
# (departamento, municipios). El primero es la sede de la Parroquia de Pruebas.
MUNICIPIOS = (
    (
        "Norte de Santander",
        (
            "Ocaña",
            "Ábrego",
            "La Playa de Belén",
            "Convención",
            "Teorama",
            "El Carmen",
            "Hacarí",
            "San Calixto",
            "González",
            "Cúcuta",
        ),
    ),
    ("Cesar", ("Aguachica", "Río de Oro")),
)
DIOCESIS_POR_MUNICIPIO = {"Cúcuta": "Cúcuta"}  # el resto: Ocaña

NOMBRES_HOMBRE = (
    "Juan",
    "Carlos",
    "Luis",
    "José",
    "Andrés",
    "Jorge",
    "Diego",
    "Miguel",
    "Santiago",
    "Sebastián",
    "Samuel",
    "Mateo",
    "Nicolás",
    "Alejandro",
    "Daniel",
    "David",
    "Felipe",
    "Julián",
    "Camilo",
    "Esteban",
    "Gabriel",
    "Tomás",
    "Martín",
    "Emmanuel",
    "Jerónimo",
    "Matías",
    "Óscar",
    "Fernando",
    "Ricardo",
    "Javier",
    "Hernán",
    "Wilson",
    "Édgar",
    "Fabián",
    "Brayan",
    "Kevin",
    "Cristian",
    "Iván",
    "Rafael",
    "Manuel",
    "Pedro",
    "Pablo",
    "Francisco",
    "Álvaro",
    "Germán",
    "Hugo",
    "Mauricio",
    "Orlando",
    "Juan José",
    "Juan David",
    "Juan Pablo",
    "Juan Sebastián",
    "Luis Alberto",
    "José Luis",
    "Carlos Andrés",
    "Miguel Ángel",
)
NOMBRES_MUJER = (
    "María",
    "Ana",
    "Laura",
    "Valentina",
    "Sofía",
    "Isabella",
    "Mariana",
    "Daniela",
    "Camila",
    "Gabriela",
    "Salomé",
    "Sara",
    "Luciana",
    "Valeria",
    "Natalia",
    "Paula",
    "Andrea",
    "Carolina",
    "Diana",
    "Sandra",
    "Claudia",
    "Patricia",
    "Martha",
    "Luz",
    "Gloria",
    "Yolanda",
    "Yuliana",
    "Leidy",
    "Karen",
    "Paola",
    "Juliana",
    "Manuela",
    "Antonella",
    "Emilia",
    "Victoria",
    "Ximena",
    "Lorena",
    "Mónica",
    "Adriana",
    "Rosa",
    "Carmen",
    "Teresa",
    "Esperanza",
    "Nubia",
    "Yesenia",
    "Tatiana",
    "Liliana",
    "María José",
    "María Fernanda",
    "Ana María",
    "Luz Marina",
    "María Camila",
    "Laura Sofía",
    "María Alejandra",
)
APELLIDOS = (
    "Rodríguez",
    "Gómez",
    "González",
    "Martínez",
    "García",
    "López",
    "Hernández",
    "Sánchez",
    "Ramírez",
    "Pérez",
    "Díaz",
    "Muñoz",
    "Rojas",
    "Moreno",
    "Jiménez",
    "Torres",
    "Vargas",
    "Álvarez",
    "Castro",
    "Ruiz",
    "Romero",
    "Suárez",
    "Ortiz",
    "Gutiérrez",
    "Mendoza",
    "Herrera",
    "Medina",
    "Castillo",
    "Guerrero",
    "Quintero",
    "Pacheco",
    "Navarro",
    "Ríos",
    "Cárdenas",
    "Acosta",
    "Ospina",
    "Arias",
    "Rincón",
    "Pabón",
    "Carrascal",
    "Arévalo",
    "Pallares",
    "Jaime",
    "Ascanio",
    "Sanguino",
    "Bayona",
    "Vergel",
    "Lobo",
    "Durán",
    "Claro",
    "Barbosa",
    "Contreras",
    "Velásquez",
    "Peñaranda",
    "Trigos",
    "Ovallos",
    "Ibáñez",
    "Manzano",
    "Coronel",
    "Picón",
    "Vega",
    "Angarita",
    "Galvis",
    "Carvajal",
    "Prado",
    "Sepúlveda",
)
PARROQUIAS_EXTERNAS = (
    "San José",
    "Santa Ana",
    "San Francisco de Asís",
    "Nuestra Señora del Carmen",
    "Santa Rita",
    "San Antonio de Padua",
    "Sagrado Corazón de Jesús",
    "San Pedro Apóstol",
)

MOTIVOS_ANULACION = {
    TipoSacramento.BAUTISMO: (
        "Partida inscrita por error: el bautismo se celebró en otra parroquia.",
        "Error de inscripción: la familia presentó constancia de bautismo anterior.",
    ),
    TipoSacramento.PRIMERA_COMUNION: (
        "Partida inscrita por error: la primera comunión se celebró en otra parroquia.",
        "Error de inscripción: el comulgante no se presentó a la celebración.",
    ),
}

MINISTROS = (
    ("parroco", "Gustavo", "Pallares Rincón", CargoMinisterial.PARROCO, date(1968, 4, 9)),
    ("vicario", "Edwin", "Ascanio Vergel", CargoMinisterial.VICARIO, date(1984, 11, 21)),
    ("diacono", "Leonardo", "Trigos Claro", CargoMinisterial.DIACONO, date(1990, 2, 14)),
)


def _aware(una_fecha, hora=10, minuto=0):
    momento = datetime.combine(una_fecha, time(hora, minuto))
    return timezone.make_aware(momento, timezone.get_current_timezone())


def _sumar_anios(fecha, anios):
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:  # 29 de febrero
        return fecha.replace(year=fecha.year + anios, day=28)


def _cantidad(total, proporcion):
    return math.ceil(total * proporcion) if total else 0


def _en_uso(objeto):
    """¿Alguna fila de cualquier modelo apunta a este objeto?"""
    for relacion in objeto._meta.related_objects:
        modelo = relacion.related_model
        if modelo._default_manager.filter(**{relacion.field.name: objeto}).exists():
            return True
    return False


class Planificador:
    """Genera en memoria todas las partidas y personas a partir de una semilla.

    No toca la base de datos: el resultado son diccionarios que luego se
    convierten en llamadas a los servicios. Así la misma semilla produce
    siempre los mismos datos.
    """

    def __init__(self, semilla, bautismos, primeras, hoy):
        self.rng = random.Random(semilla)
        self.n_bautismos = bautismos
        self.n_primeras = primeras
        self.hoy = hoy
        self.ayer = hoy - timedelta(days=1)
        # Los tres primeros números de documento son los de los ministros.
        self._contador = len(MINISTROS)
        self._padrinos = {Sexo.HOMBRE: [], Sexo.MUJER: []}
        self.primeras_externas_por_falta = 0

    # Personas ---------------------------------------------------------
    def _numero(self):
        self._contador += 1
        return f"{PREFIJO_DOCUMENTO}{self._contador:06d}"

    def _nombre(self, sexo):
        return self.rng.choice(NOMBRES_HOMBRE if sexo == Sexo.HOMBRE else NOMBRES_MUJER)

    def _apellidos(self):
        primero, segundo = self.rng.sample(APELLIDOS, 2)
        return f"{primero} {segundo}"

    def _adulto(self, sexo):
        return {
            "tipo_documento": TipoDocumento.CC,
            "numero_documento": self._numero(),
            "nombre": self._nombre(sexo),
            "apellido": self._apellidos(),
            "sexo": sexo,
        }

    def _padrino(self, sexo):
        """Padrino (varón) o madrina (mujer); a veces repite uno ya usado."""
        pool = self._padrinos[sexo]
        if pool and self.rng.random() < PROBABILIDAD_REPETIR_PADRINO:
            return self.rng.choice(pool)
        persona = self._adulto(sexo)
        pool.append(persona)
        return persona

    def _municipio(self):
        departamento, municipios = MUNICIPIOS[0]
        if self.rng.random() < 0.5:
            return departamento, municipios[0]
        todos = [(depto, nombre) for depto, nombres in MUNICIPIOS for nombre in nombres]
        return self.rng.choice(todos)

    def _tipo_documento_menor(self, nacimiento):
        edad = edad_en_fecha(nacimiento, self.hoy)
        if edad < 7:
            return TipoDocumento.RC
        if edad < 18:
            return TipoDocumento.TI
        return TipoDocumento.CC

    def _fiel(self, nombres, apellidos, nacimiento, sexo):
        return {
            "tipo_documento": self._tipo_documento_menor(nacimiento),
            "numero_documento": self._numero(),
            "nombres": nombres,
            "apellidos": apellidos,
            "fecha_nacimiento": nacimiento,
            "municipio": self._municipio(),
            "sexo": sexo,
        }

    @staticmethod
    def _primer_apellido(persona):
        return persona["apellido"].split()[0]

    def _abuelos(self, padre, madre):
        """Abuelos coherentes con los apellidos de los padres (comunes a los hermanos)."""
        abuelos = {
            "abuelo_paterno": "",
            "abuela_paterna": "",
            "abuelo_materno": "",
            "abuela_materna": "",
        }
        for persona, abuelo, abuela in (
            (padre, "abuelo_paterno", "abuela_paterna"),
            (madre, "abuelo_materno", "abuela_materna"),
        ):
            if persona is None:
                continue
            primero, segundo = persona["apellido"].split()
            abuelos[abuelo] = f"{self._nombre(Sexo.HOMBRE)} {primero} {self.rng.choice(APELLIDOS)}"
            apellidos_abuela = f"{segundo} {self.rng.choice(APELLIDOS)}"
            abuelos[abuela] = f"{self._nombre(Sexo.MUJER)} {apellidos_abuela}"
            abuelos[f"apellidos_{abuela}"] = apellidos_abuela
        return abuelos

    def _demora_bautismo(self):
        """Edad al bautizarse: casi siempre de 1 a 12 meses."""
        sorteo = self.rng.random()
        if sorteo < 0.88:
            return timedelta(days=self.rng.randint(30, 364))
        if sorteo < 0.97:
            return timedelta(days=self.rng.randint(365, 6 * 365 + 364))
        return timedelta(days=self.rng.randint(7 * 365, 12 * 365))

    def _fecha(self, inicio, fin):
        return inicio + timedelta(days=self.rng.randint(0, (fin - inicio).days))

    def _padrinos_de_partida(self):
        sorteo = self.rng.random()
        if sorteo < 0.03:
            return self._padrino(Sexo.HOMBRE), None
        if sorteo < 0.06:
            return None, self._padrino(Sexo.MUJER)
        return self._padrino(Sexo.HOMBRE), self._padrino(Sexo.MUJER)

    def _plan_bautismo(self, fiel, padre, madre, abuelos, fecha, tipo_hijo, biologicos=None):
        padrino, madrina = self._padrinos_de_partida()
        biologicos = biologicos or ("", "")
        return {
            "tipo": TipoSacramento.BAUTISMO,
            "fiel": fiel,
            "padre": padre,
            "madre": madre,
            "padrino": padrino,
            "madrina": madrina,
            "tipo_hijo": tipo_hijo,
            "padre_biologico_nombre": biologicos[0],
            "madre_biologica_nombre": biologicos[1],
            "fecha": fecha,
            "ministro": self.rng.choices(("parroco", "vicario", "diacono"), (50, 30, 20))[0],
            "quien_firma": self.rng.choices(("parroco", "vicario"), (80, 20))[0],
            **abuelos,
        }

    # Bautismos --------------------------------------------------------
    def _familia(self, planes):
        padre = self._adulto(Sexo.HOMBRE)
        madre = self._adulto(Sexo.MUJER)
        abuelos = self._abuelos(padre, madre)
        apellidos = f"{self._primer_apellido(padre)} {self._primer_apellido(madre)}"
        hijos = self.rng.choices((1, 2, 3, 4), (35, 35, 20, 10))[0]
        bautismo = self._fecha(INICIO_BAUTISMOS, FIN_BAUTISMOS)
        nacimiento = bautismo - self._demora_bautismo()
        for orden in range(hijos):
            if len(planes) >= self.n_bautismos:
                return
            if orden:
                # Hermanos con 1 a 4 años de diferencia.
                nacimiento += timedelta(days=self.rng.randint(365, 4 * 365))
                bautismo = nacimiento + self._demora_bautismo()
                if bautismo > FIN_BAUTISMOS:
                    return
                if bautismo < INICIO_BAUTISMOS:
                    # Hermano bautizado antes del periodo (no consta en esta parroquia).
                    continue
            sexo = self.rng.choice((Sexo.HOMBRE, Sexo.MUJER))
            fiel = self._fiel(self._nombre(sexo), apellidos, nacimiento, sexo)
            planes.append(
                self._plan_bautismo(fiel, padre, madre, abuelos, bautismo, TipoHijo.BIOLOGICO)
            )

    def _adopcion(self, planes):
        """Hijo adoptivo: constan los padres adoptantes (a veces solo la madre)."""
        sin_padre = self.rng.random() < PROBABILIDAD_ADOPCION_SIN_PADRE
        padre = None if sin_padre else self._adulto(Sexo.HOMBRE)
        madre = self._adulto(Sexo.MUJER)
        if padre is None:
            apellidos = madre["apellido"]
        else:
            apellidos = f"{self._primer_apellido(padre)} {self._primer_apellido(madre)}"
        biologicos = (
            f"{self._nombre(Sexo.HOMBRE)} {self._apellidos()}",
            f"{self._nombre(Sexo.MUJER)} {self._apellidos()}",
        )
        bautismo = self._fecha(INICIO_BAUTISMOS, FIN_BAUTISMOS)
        nacimiento = bautismo - timedelta(days=self.rng.randint(180, 6 * 365))
        sexo = self.rng.choice((Sexo.HOMBRE, Sexo.MUJER))
        fiel = self._fiel(self._nombre(sexo), apellidos, nacimiento, sexo)
        planes.append(
            self._plan_bautismo(
                fiel,
                padre,
                madre,
                self._abuelos(padre, madre),
                bautismo,
                TipoHijo.ADOPTIVO,
                biologicos,
            )
        )

    def planear_bautismos(self):
        planes = []
        while len(planes) < self.n_bautismos:
            if self.rng.random() < PROBABILIDAD_ADOPTIVO:
                self._adopcion(planes)
            else:
                self._familia(planes)
        planes.sort(key=lambda plan: plan["fecha"])
        for indice, plan in enumerate(planes):
            plan["indice"] = indice
        self._fechas_de_registro(planes)
        self._marcar_novedades(planes, TipoSacramento.BAUTISMO)
        return planes

    # Primeras comuniones ----------------------------------------------
    def _ventana_primera(self, plan):
        """Fechas posibles de primera comunión (8 a 12 años, después del bautismo)."""
        nacimiento = plan["fiel"]["fecha_nacimiento"]
        inicio = max(
            _sumar_anios(nacimiento, EDAD_MINIMA_PRIMERA),
            plan["fecha"] + timedelta(days=1),
            INICIO_PRIMERAS,
        )
        fin = min(_sumar_anios(nacimiento, EDAD_MAXIMA_PRIMERA + 1) - timedelta(days=1), self.ayer)
        return (inicio, fin) if inicio <= fin else None

    def _domingo(self, inicio, fin):
        """Un domingo al azar dentro de la ventana (o cualquier día si no hay)."""
        fecha = self._fecha(inicio, fin)
        domingo = fecha - timedelta(days=(fecha.weekday() + 1) % 7)
        if domingo < inicio:
            domingo += timedelta(days=7)
        return domingo if domingo <= fin else fecha

    def _plan_primera(self, fiel, fecha, bautismo=None, externo=None, padre=None, madre=None):
        return {
            "tipo": TipoSacramento.PRIMERA_COMUNION,
            "fiel": fiel,
            "fecha": fecha,
            "bautismo": bautismo,
            "externo": externo,
            "padre": padre,
            "madre": madre,
            "ministro": self.rng.choices(("parroco", "vicario"), (60, 40))[0],
        }

    def _primera_externa(self):
        fecha = self._domingo(INICIO_PRIMERAS, self.ayer)
        edad = self.rng.randint(EDAD_MINIMA_PRIMERA, EDAD_MAXIMA_PRIMERA)
        nacimiento = _sumar_anios(fecha, -edad) - timedelta(days=self.rng.randint(0, 360))
        padre = self._adulto(Sexo.HOMBRE)
        madre = self._adulto(Sexo.MUJER)
        sexo = self.rng.choice((Sexo.HOMBRE, Sexo.MUJER))
        apellidos = f"{self._primer_apellido(padre)} {self._primer_apellido(madre)}"
        fiel = self._fiel(self._nombre(sexo), apellidos, nacimiento, sexo)
        _, municipio = fiel["municipio"]
        externo = {
            "fecha": nacimiento + timedelta(days=self.rng.randint(30, 364)),
            "parroquia": f"{self.rng.choice(PARROQUIAS_EXTERNAS)} ({municipio})",
            "libro": self.rng.randint(1, 25),
            "folio": self.rng.randint(1, 200),
            "numero": self.rng.randint(1, 600),
            "observaciones": f"Diócesis: {DIOCESIS_POR_MUNICIPIO.get(municipio, 'Ocaña')}.",
        }
        return self._plan_primera(fiel, fecha, externo=externo, padre=padre, madre=madre)

    def planear_primeras(self, bautismos):
        candidatos = []
        for indice, plan in enumerate(bautismos):
            if plan["anular"]:
                continue
            ventana = self._ventana_primera(plan)
            if ventana:
                candidatos.append((indice, ventana))
        self.rng.shuffle(candidatos)
        enlazadas = round(self.n_primeras * PROPORCION_ENLAZADAS)
        elegidos = candidatos[:enlazadas]
        self.primeras_externas_por_falta = enlazadas - len(elegidos)

        planes = []
        for indice, (inicio, fin) in elegidos:
            plan_bautismo = bautismos[indice]
            planes.append(
                self._plan_primera(
                    plan_bautismo["fiel"], self._domingo(inicio, fin), bautismo=indice
                )
            )
        while len(planes) < self.n_primeras:
            planes.append(self._primera_externa())
        planes.sort(key=lambda plan: plan["fecha"])
        self._fechas_de_registro(planes)
        self._marcar_novedades(planes, TipoSacramento.PRIMERA_COMUNION)
        return planes

    # Fechas de registro y novedades -----------------------------------
    def _fechas_de_registro(self, planes):
        """De 0 a 15 días después del sacramento, sin retroceder y nunca hoy ni después."""
        anterior = None
        for plan in planes:
            registro = plan["fecha"] + timedelta(days=self.rng.randint(0, 15))
            if anterior and registro < anterior:
                registro = anterior
            registro = min(registro, self.ayer)
            plan["fecha_registro"] = registro
            anterior = registro

    def _fecha_novedad(self, plan, dias):
        return min(plan["fecha_registro"] + timedelta(days=self.rng.randint(1, dias)), self.ayer)

    def _marcar_novedades(self, planes, tipo):
        for plan in planes:
            plan["anular"] = None
            plan["corregir"] = None
        indices = list(range(len(planes)))
        anuladas = self.rng.sample(indices, _cantidad(len(planes), PROPORCION_ANULADAS))
        for indice in anuladas:
            planes[indice]["anular"] = {
                "fecha": self._fecha_novedad(planes[indice], 60),
                "motivo": self.rng.choice(MOTIVOS_ANULACION[tipo]),
            }
        excluidas = set(anuladas)
        restantes = [indice for indice in indices if indice not in excluidas]
        corregidas = self.rng.sample(
            restantes, min(len(restantes), _cantidad(len(planes), PROPORCION_CORREGIDAS))
        )
        for indice in corregidas:
            planes[indice]["corregir"] = {
                "fecha": self._fecha_novedad(planes[indice], 120),
                "opcion": self.rng.randint(0, 1),
                "nombre": self._nombre(Sexo.MUJER),
            }


class Command(BaseCommand):
    help = (
        "Carga (o borra, con --borrar) bautismos y primeras comuniones masivos de prueba "
        "en la «Parroquia de Pruebas»"
    )

    def add_arguments(self, parser):
        parser.add_argument("--bautismos", type=int, default=BAUTISMOS_DEFECTO)
        parser.add_argument(
            "--primeras-comuniones", dest="primeras", type=int, default=PRIMERAS_DEFECTO
        )
        parser.add_argument(
            "--semilla",
            type=int,
            default=SEMILLA_DEFECTO,
            help="Semilla del generador: la misma semilla produce los mismos datos",
        )
        parser.add_argument(
            "--borrar",
            action="store_true",
            help="Elimina solo los datos creados por este comando",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "cargar_datos_masivos solo funciona con DEBUG=True. "
                "No se ha modificado la base de datos."
            )
        if options["borrar"]:
            self._borrar()
            return
        if options["bautismos"] < 0 or options["primeras"] < 0:
            raise CommandError("Las cantidades no pueden ser negativas.")
        self._cargar(options["bautismos"], options["primeras"], options["semilla"])

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def _cargar(self, n_bautismos, n_primeras, semilla):
        if Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO).exists():
            raise CommandError(
                "Ya existen datos masivos (documentos 9991) en la base; "
                "ejecuta primero «cargar_datos_masivos --borrar»."
            )
        existente = Parroquia.objects.filter(nombre=NOMBRE_PARROQUIA).first()
        if existente and (existente.libros.exists() or existente.sacramentos.exists()):
            raise CommandError(
                f"La parroquia «{NOMBRE_PARROQUIA}» ya tiene libros o partidas; "
                "ejecuta primero «cargar_datos_masivos --borrar»."
            )

        inicio = reloj.monotonic()
        self._hoy = timezone.localdate()
        planificador = Planificador(semilla, n_bautismos, n_primeras, self._hoy)
        bautismos = planificador.planear_bautismos()
        primeras = planificador.planear_primeras(bautismos)

        with transaction.atomic():
            self._preparar_parroquia(existente)

        self._libros = {}
        self._en_libro = {}
        self._bautismo_de = {}
        self._partida_de = {}
        operaciones = [("crear", plan) for plan in bautismos + primeras]
        self._ejecutar_por_lotes(operaciones, "partidas")

        novedades = [
            (plan[clave]["fecha"], clave, plan)
            for plan in bautismos + primeras
            for clave in ("corregir", "anular")
            if plan[clave]
        ]
        novedades.sort(key=lambda fila: fila[0])
        self._ejecutar_por_lotes([(clave, plan) for _, clave, plan in novedades], "novedades")

        self._resumen(planificador, reloj.monotonic() - inicio)

    def _ejecutar_por_lotes(self, operaciones, etiqueta):
        total = len(operaciones)
        for desde in range(0, total, TAMANO_LOTE):
            lote = operaciones[desde : desde + TAMANO_LOTE]
            with transaction.atomic():
                for accion, plan in lote:
                    if accion == "crear":
                        self._crear_partida(plan)
                    elif accion == "corregir":
                        self._corregir(plan)
                    else:
                        self._anular(plan)
            self.stdout.write(f"  {min(desde + TAMANO_LOTE, total)}/{total} {etiqueta}")

    def _guardar(self, objeto):
        objeto.full_clean()
        objeto.save()
        return objeto

    def _preparar_parroquia(self, existente):
        self._municipios = {}
        pais = Pais.objects.filter(nombre=PAIS).first() or self._guardar(Pais(nombre=PAIS))
        for nombre_departamento, municipios in MUNICIPIOS:
            departamento = Departamento.objects.filter(
                pais=pais, nombre=nombre_departamento
            ).first() or self._guardar(Departamento(pais=pais, nombre=nombre_departamento))
            for nombre in municipios:
                municipio = Municipio.objects.filter(
                    departamento=departamento, nombre=nombre
                ).first() or self._guardar(Municipio(departamento=departamento, nombre=nombre))
                self._municipios[(nombre_departamento, nombre)] = municipio

        sede = self._municipios[(MUNICIPIOS[0][0], MUNICIPIOS[0][1][0])]
        parroquia = existente or self._guardar(
            Parroquia(nombre=NOMBRE_PARROQUIA, municipio=sede, direccion=DIRECCION_PARROQUIA)
        )
        self._parroquia = parroquia

        self._ministros = {}
        for numero, (clave, nombre, apellido, cargo, nacimiento) in enumerate(MINISTROS, 1):
            documento = self._guardar(
                Documento(
                    tipo_documento=TipoDocumento.CC,
                    numero_documento=f"{PREFIJO_DOCUMENTO}{numero:06d}",
                )
            )
            self._ministros[clave] = self._guardar(
                Ministro(
                    documento=documento,
                    nombre=nombre,
                    apellido=apellido,
                    cargo=cargo,
                    fecha_nacimiento=nacimiento,
                    parroquia=parroquia,
                )
            )
        parroquia.parroco = self._ministros["parroco"]
        parroquia.save(update_fields=["parroco"])

    # Libros -----------------------------------------------------------
    def _libro_para(self, tipo_libro, plan):
        """Libro abierto del tipo; cierra el actual y abre otro si ya está lleno."""
        libro = self._libros.get(tipo_libro)
        if libro is not None and self._en_libro[libro.pk] < MAX_PARTIDAS_POR_LIBRO:
            return libro
        apertura = plan["fecha"]
        numero = 1
        if libro is not None:
            cierre = libro.sacramentos.aggregate(Max("fecha_registro"))["fecha_registro__max"]
            cerrar_libro(
                libro,
                self._ministros["parroco"],
                cierre,
                nota=f"Se cierra con {self._en_libro[libro.pk]} partidas; sin folios anulados.",
            )
            apertura = cierre
            numero = libro.numero_libro + 1
        etiqueta = TipoLibro(tipo_libro).label
        libro = self._guardar(
            Libro(
                nombre=f"{etiqueta} {numero}",
                tipo_libro=tipo_libro,
                detalle=f"Libro {numero} de {etiqueta.lower()} de {NOMBRE_PARROQUIA}.",
                numero_libro=numero,
                fecha_apertura=apertura,
                total_folios=math.ceil(MAX_PARTIDAS_POR_LIBRO / PARTIDAS_POR_FOLIO),
                partidas_por_folio=PARTIDAS_POR_FOLIO,
                ministro_apertura=self._ministros["parroco"],
                parroquia=self._parroquia,
            )
        )
        self._libros[tipo_libro] = libro
        self._en_libro[libro.pk] = 0
        return libro

    # Partidas ---------------------------------------------------------
    @staticmethod
    def _persona(datos):
        if datos is None:
            return None
        return {
            "tipo_documento": datos["tipo_documento"],
            "numero_documento": datos["numero_documento"],
            "nombre": datos["nombre"],
            "apellido": datos["apellido"],
        }

    @staticmethod
    def _padrino(datos):
        if datos is None:
            return None
        return {
            "tipo_documento": datos["tipo_documento"],
            "numero_documento": datos["numero_documento"],
            "nombre": f"{datos['nombre']} {datos['apellido']}",
        }

    def _fiel(self, datos):
        return {
            "tipo_documento": datos["tipo_documento"],
            "numero_documento": datos["numero_documento"],
            "nombres": datos["nombres"],
            "apellidos": datos["apellidos"],
            "fecha_nacimiento": datos["fecha_nacimiento"],
            "municipio_nacimiento": self._municipios[datos["municipio"]],
            "telefono": "",
            "sexo": datos["sexo"],
        }

    def _datos_bautismo(self, plan, libro):
        return {
            "partida": {
                "libro": libro,
                "fecha": plan["fecha"],
                "parroquia": self._parroquia,
                "ministro": self._ministros[plan["ministro"]],
                "observaciones": plan.get("observaciones", ""),
            },
            "fiel": self._fiel(plan["fiel"]),
            "padre": self._persona(plan["padre"]),
            "madre": self._persona(plan["madre"]),
            "padrino": self._padrino(plan["padrino"]),
            "madrina": self._padrino(plan["madrina"]),
            "abuelo_paterno": plan["abuelo_paterno"],
            "abuela_paterna": plan["abuela_paterna"],
            "abuelo_materno": plan["abuelo_materno"],
            "abuela_materna": plan["abuela_materna"],
            "tipo_hijo": plan["tipo_hijo"],
            "testigo_nombre": "",
            "padre_biologico_nombre": plan["padre_biologico_nombre"],
            "madre_biologica_nombre": plan["madre_biologica_nombre"],
            "doy_fe": self._ministros["parroco"],
            "quien_firma": self._ministros[plan["quien_firma"]],
        }

    def _datos_primera(self, plan, libro):
        bautismo = None
        if plan["bautismo"] is not None:
            bautismo = self._bautismo_de[plan["bautismo"]]
        return {
            "partida": {
                "libro": libro,
                "fecha": plan["fecha"],
                "parroquia": self._parroquia,
                "ministro": self._ministros[plan["ministro"]],
                "observaciones": plan.get("observaciones", ""),
            },
            "fiel": self._fiel(plan["fiel"]),
            "bautismo_sistema": bautismo,
            "bautismo_externo": plan["externo"] or {},
            "padre": self._persona(plan["padre"]),
            "madre": self._persona(plan["madre"]),
            "doy_fe": self._ministros["parroco"],
            "reglas_aceptadas": [],
        }

    def _verificar_bautismo(self, plan):
        """Reglas que la app aplica en ``BautismoForm`` (B1, B2 y sexo)."""
        fiel = plan["fiel"]
        documentos_familia = {
            persona["numero_documento"]
            for persona in (plan["padre"], plan["madre"])
            if persona is not None
        } | {fiel["numero_documento"]}
        for rol, sexo in (("padrino", Sexo.HOMBRE), ("madrina", Sexo.MUJER)):
            persona = plan[rol]
            if persona is None:
                continue
            if persona["numero_documento"] in documentos_familia:
                raise CommandError(f"B2: el {rol} no puede ser el bautizado ni sus padres.")
            if persona["sexo"] != sexo:
                raise CommandError(f"El {rol} no tiene el sexo que exige el c. 873.")
        if not plan["padrino"] and not plan["madrina"]:
            raise CommandError("B4: falta padrino o madrina.")
        if Bautismo.objects.filter(
            sacramento__fiel__documento__numero_documento=fiel["numero_documento"],
            sacramento__estado__in=(EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO),
        ).exists():
            raise CommandError("B1: el fiel ya tiene un bautismo registrado.")

    def _verificar_primera(self, plan):
        """Reglas P1 a P3 de ``PrimeraComunionForm`` y la edad de 8 a 12 años."""
        fecha = plan["fecha"]
        nacimiento = plan["fiel"]["fecha_nacimiento"]
        if plan["bautismo"] is not None:
            bautismo = self._bautismo_de[plan["bautismo"]]
            if bautismo.sacramento.estado not in (EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO):
                raise CommandError("P1: el bautismo enlazado no está vigente.")
            fecha_bautismo = bautismo.sacramento.fecha
        else:
            externo = plan["externo"] or {}
            campos = ("fecha", "parroquia", "libro", "folio", "numero")
            if not all(externo.get(campo) for campo in campos):
                raise CommandError("P1: faltan datos del bautismo externo.")
            fecha_bautismo = externo["fecha"]
        if PrimeraComunion.objects.filter(
            sacramento__fiel__documento__numero_documento=plan["fiel"]["numero_documento"],
            sacramento__estado__in=(EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO),
        ).exists():
            raise CommandError("P2: el comulgante ya tiene primera comunión.")
        if fecha > self._hoy or fecha < nacimiento or fecha < fecha_bautismo:
            raise CommandError("P3: fecha de primera comunión no válida.")
        edad = edad_en_fecha(nacimiento, fecha)
        if not EDAD_MINIMA_PRIMERA <= edad <= EDAD_MAXIMA_PRIMERA:
            raise CommandError(f"La edad de primera comunión ({edad}) está fuera de 8 a 12.")

    def _crear_partida(self, plan):
        if plan["tipo"] == TipoSacramento.BAUTISMO:
            self._verificar_bautismo(plan)
            libro = self._libro_para(TipoLibro.BAUTISMOS, plan)
            bautismo, _ = registrar_bautismo(self._datos_bautismo(plan, libro), None)
            self._bautismo_de[plan["indice"]] = bautismo
            partida = bautismo
        else:
            self._verificar_primera(plan)
            libro = self._libro_para(TipoLibro.PRIMERA_COMUNION, plan)
            partida, _ = registrar_primera_comunion(self._datos_primera(plan, libro), None)
        self._en_libro[libro.pk] += 1
        self._fijar_fecha_registro(partida.sacramento, plan["fecha_registro"])
        self._partida_de[id(plan)] = partida

    def _fijar_fecha_registro(self, sacramento, fecha_registro):
        """Mueve la fecha de registro (que el servicio pone en hoy) a la del plan.

        Se valida antes con ``full_clean()`` (rango del libro y fecha no anterior
        al sacramento) y se guarda con ``update()`` para no tocar nada más. La
        hora de creación y el historial de creación se alinean con esa fecha.
        """
        sacramento.fecha_registro = fecha_registro
        sacramento.full_clean()
        momento = _aware(fecha_registro, 9 + sacramento.numero % 8, sacramento.numero % 60)
        Sacramento.objects.filter(pk=sacramento.pk).update(
            fecha_registro=fecha_registro, creado_en=momento, modificado_en=momento
        )
        HistorialSacramento.objects.filter(sacramento=sacramento).update(fecha=momento)

    # Novedades --------------------------------------------------------
    def _partida_actual(self, plan):
        """La partida recargada de la base (con la fecha de registro ya movida)."""
        partida = self._partida_de[id(plan)]
        return type(partida).objects.select_related("sacramento").get(pk=partida.pk)

    def _fechar_novedad(self, sacramento, accion, tipo_anotacion, fecha):
        momento = _aware(fecha, 16)
        HistorialSacramento.objects.filter(sacramento=sacramento, accion=accion).update(
            fecha=momento
        )
        AnotacionMarginal.objects.filter(sacramento=sacramento, tipo=tipo_anotacion).update(
            fecha=fecha
        )
        Sacramento.objects.filter(pk=sacramento.pk).update(modificado_en=momento)

    def _corregir(self, plan):
        partida = self._partida_actual(plan)
        sacramento = partida.sacramento
        novedad = plan["corregir"]
        otro_ministro = "vicario" if plan["ministro"] == "parroco" else "parroco"
        if plan["tipo"] == TipoSacramento.BAUTISMO:
            datos = self._datos_bautismo(plan, sacramento.libro)
            if novedad["opcion"] == 0 and plan["madre"] is not None:
                datos["abuela_materna"] = f"{novedad['nombre']} {plan['apellidos_abuela_materna']}"
                motivo = (
                    "Se corrige el nombre de la abuela materna según el registro civil "
                    "presentado por la familia."
                )
            else:
                datos["partida"]["ministro"] = self._ministros[otro_ministro]
                motivo = "Se corrige el ministro que celebró el bautismo según el libro de turnos."
            corregir_bautismo(partida, datos, None, motivo)
        else:
            datos = self._datos_primera(plan, sacramento.libro)
            if novedad["opcion"] == 0:
                datos["partida"]["observaciones"] = (
                    "Celebrada en la jornada parroquial de primeras comuniones."
                )
                motivo = "Se completa la observación de la partida."
            else:
                datos["partida"]["ministro"] = self._ministros[otro_ministro]
                motivo = "Se corrige el ministro que celebró la primera comunión."
            corregir_primera_comunion(partida, datos, None, motivo)
        self._fechar_novedad(
            sacramento,
            AccionHistorial.CORRECCION,
            TipoAnotacionMarginal.CORRECCION,
            novedad["fecha"],
        )

    def _anular(self, plan):
        partida = self._partida_actual(plan)
        novedad = plan["anular"]
        if plan["tipo"] == TipoSacramento.BAUTISMO:
            anular_bautismo(partida, None, novedad["motivo"])
        else:
            anular_primera_comunion(partida, None, novedad["motivo"])
        self._fechar_novedad(
            partida.sacramento,
            AccionHistorial.ANULACION,
            TipoAnotacionMarginal.ANULACION,
            novedad["fecha"],
        )

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------
    def _resumen(self, planificador, segundos):
        partidas = Sacramento.objects.filter(libro__parroquia=self._parroquia)
        documentos = Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO)
        escribir = self.stdout.write

        escribir(self.style.SUCCESS(f"Datos masivos cargados en «{NOMBRE_PARROQUIA}»:"))
        escribir("  Partidas por tipo:")
        for fila in partidas.values("tipo").annotate(total=Count("id")).order_by("tipo"):
            escribir(f"    {TipoSacramento(fila['tipo']).label}: {fila['total']}")
        escribir("  Partidas por estado:")
        for fila in partidas.values("estado").annotate(total=Count("id")).order_by("estado"):
            escribir(f"    {EstadoRegistro(fila['estado']).label}: {fila['total']}")
        escribir("  Partidas por libro:")
        libros = (
            Libro.objects.filter(parroquia=self._parroquia)
            .annotate(
                total=Count("sacramentos"),
                primero=Min("sacramentos__numero"),
                ultimo=Max("sacramentos__numero"),
            )
            .order_by("tipo_libro", "numero_libro")
        )
        for libro in libros:
            cierre = f" → {libro.fecha_cierre}" if libro.fecha_cierre else " → (abierto)"
            escribir(
                f"    {libro.nombre}: {libro.total} partidas (N.° {libro.primero}–{libro.ultimo}), "
                f"{libro.get_estado_display().lower()}, {libro.fecha_apertura}{cierre}"
            )
        fieles = Fiel.objects.filter(documento__in=documentos).count()
        escribir(
            "  Personas creadas (documentos 9991): "
            f"{documentos.count()} — fieles {fieles}, "
            f"padres {Padre.objects.filter(documento__in=documentos).count()}, "
            f"madres {Madre.objects.filter(documento__in=documentos).count()}, "
            f"padrinos/madrinas {Padrino.objects.filter(documento__in=documentos).count()}, "
            f"ministros {Ministro.objects.filter(documento__in=documentos).count()}"
        )
        anotaciones = Counter(
            AnotacionMarginal.objects.filter(sacramento__in=partidas).values_list("tipo", flat=True)
        )
        detalle = ", ".join(
            f"{TipoAnotacionMarginal(tipo).label.lower()} {total}"
            for tipo, total in sorted(anotaciones.items())
        )
        escribir(f"  Anotaciones marginales: {sum(anotaciones.values())} ({detalle or '—'})")
        escribir(
            "  Historial: "
            f"{HistorialSacramento.objects.filter(sacramento__in=partidas).count()} entradas"
        )
        if planificador.primeras_externas_por_falta:
            escribir(
                self.style.WARNING(
                    f"  {planificador.primeras_externas_por_falta} primeras comuniones pasaron a "
                    "bautismo externo por falta de niños bautizados aquí con 8 a 12 años."
                )
            )
        escribir(f"  Tiempo total: {segundos:.1f} s")

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def _borrar(self):
        documentos = Documento.objects.filter(numero_documento__startswith=PREFIJO_DOCUMENTO)
        parroquia = Parroquia.objects.filter(nombre=NOMBRE_PARROQUIA).first()
        if parroquia is None and not documentos.exists():
            self.stdout.write(self.style.WARNING("No hay datos masivos que borrar."))
            return

        libros = Libro.objects.filter(parroquia=parroquia) if parroquia else Libro.objects.none()
        partidas = (
            Sacramento.objects.filter(Q(parroquia=parroquia) | Q(libro__parroquia=parroquia))
            if parroquia
            else Sacramento.objects.none()
        )
        ids = list(partidas.values_list("pk", flat=True))
        fieles = Fiel.objects.filter(documento__in=documentos)
        padres = Padre.objects.filter(documento__in=documentos)
        madres = Madre.objects.filter(documento__in=documentos)
        padrinos = Padrino.objects.filter(documento__in=documentos)
        ministros = Ministro.objects.filter(documento__in=documentos)

        # Si una partida ajena usa alguna persona 9991 no se borra nada.
        ajenas = Sacramento.objects.exclude(pk__in=ids).filter(
            Q(fiel__in=fieles)
            | Q(ministro__in=ministros)
            | Q(bautismo__padre__in=padres)
            | Q(bautismo__madre__in=madres)
            | Q(bautismo__padrino__in=padrinos)
            | Q(bautismo__madrina__in=padrinos)
            | Q(primera_comunion__padre__in=padres)
            | Q(primera_comunion__madre__in=madres)
        )
        if ajenas.exists():
            raise CommandError(
                "Hay partidas fuera de la Parroquia de Pruebas que usan personas 9991; "
                "no se borra nada."
            )

        anotaciones = AnotacionMarginal.objects.filter(
            Q(sacramento_id__in=ids) | Q(sacramento_origen_id__in=ids)
        )
        historial = HistorialSacramento.objects.filter(sacramento_id__in=ids)
        bautismos = Bautismo.objects.filter(sacramento_id__in=ids)
        primeras = PrimeraComunion.objects.filter(sacramento_id__in=ids)
        eliminadas = PartidaEliminada.objects.filter(Q(libro__in=libros) | Q(parroquia=parroquia))
        folios = Folio.objects.filter(libro__in=libros)

        conteos = {
            "Partidas": len(ids),
            "Bautismos": bautismos.count(),
            "Primeras comuniones": primeras.count(),
            "Anotaciones marginales": anotaciones.count(),
            "Entradas de historial": historial.count(),
            "Partidas eliminadas (rastro)": eliminadas.count(),
            "Folios": folios.count(),
            "Libros": libros.count(),
            "Fieles": fieles.count(),
            "Padres": padres.count(),
            "Madres": madres.count(),
            "Padrinos y madrinas": padrinos.count(),
            "Ministros": ministros.count(),
            "Documentos": documentos.count(),
            "Parroquias": 1 if parroquia else 0,
        }

        with transaction.atomic():
            anotaciones.delete()
            historial.delete()
            primeras.delete()
            bautismos.delete()
            eliminadas.delete()
            Sacramento.objects.filter(pk__in=ids).delete()
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
            conteos["Ubicaciones sin uso (país/departamento/municipio)"] = (
                self._borrar_ubicacion_sin_uso()
            )

        self.stdout.write(self.style.SUCCESS("Datos masivos eliminados:"))
        for etiqueta, total in conteos.items():
            self.stdout.write(f"  {etiqueta}: {total}")

    def _borrar_ubicacion_sin_uso(self):
        """Borra los municipios de la lista del comando que ya nadie use.

        Un municipio (o su departamento, o el país) que use cualquier persona,
        parroquia o partida se conserva, así que los que ya existían y están en
        uso (como Ocaña, sede de las parroquias reales) nunca se borran.
        """
        borrados = 0
        pais = Pais.objects.filter(nombre=PAIS).first()
        if pais is None:
            return 0
        for nombre_departamento, municipios in MUNICIPIOS:
            departamento = Departamento.objects.filter(
                pais=pais, nombre=nombre_departamento
            ).first()
            if departamento is None:
                continue
            for municipio in Municipio.objects.filter(
                departamento=departamento, nombre__in=municipios
            ):
                if not _en_uso(municipio):
                    municipio.delete()
                    borrados += 1
            if not _en_uso(departamento):
                departamento.delete()
                borrados += 1
        if not _en_uso(pais):
            pais.delete()
            borrados += 1
        return borrados
