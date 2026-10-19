"""Mecanismo reutilizable de reglas sacramentales (docs/requisitos_sacramentos.md).

Tres niveles de regla:

- BLOQUEA: el formulario no se puede guardar mientras la regla se cumpla.
- ADVIERTE: la primera vez no se guarda; hay que marcar
  «Verificado / excepción autorizada» y escribir el motivo. Cada advertencia
  aceptada queda después en el historial del sacramento con el código de la
  regla, el motivo y el usuario.
- RECUERDA: solo informa; no impide guardar.

Las reglas se evalúan SIEMPRE en el servidor, en ``MixinReglas.clean()``, a
partir de los datos ya limpios y de la base de datos: manipular el POST
(quitar campos o enviar la casilla sin motivo) no puede saltárselas. El mismo
mecanismo sirve para Confirmación y Matrimonio; cada sacramento solo define su
propia lista de reglas en ``reglas_de``.
"""

from dataclasses import dataclass, field

from django import forms

BLOQUEA = "BLOQUEA"
ADVIERTE = "ADVIERTE"
RECUERDA = "RECUERDA"
NIVELES = (BLOQUEA, ADVIERTE, RECUERDA)


@dataclass(frozen=True)
class Regla:
    """Una regla sacramental concreta, con su código canónico y su mensaje."""

    codigo: str
    nivel: str
    mensaje: str

    def __post_init__(self):
        if self.nivel not in NIVELES:
            raise ValueError(f"Nivel de regla desconocido: {self.nivel!r}")

    def texto(self):
        return f"[{self.codigo}] {self.mensaje}"


@dataclass
class ResultadoReglas:
    """Reglas evaluadas, separadas por nivel."""

    bloqueos: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)
    recuerdos: list = field(default_factory=list)

    def agregar(self, regla):
        destino = {
            BLOQUEA: self.bloqueos,
            ADVIERTE: self.advertencias,
            RECUERDA: self.recuerdos,
        }[regla.nivel]
        destino.append(regla)

    def __iter__(self):
        return iter([*self.bloqueos, *self.advertencias, *self.recuerdos])


def evaluar_reglas(reglas):
    """Evalúa una lista de ``Regla`` y devuelve el ``ResultadoReglas``."""
    resultado = ResultadoReglas()
    for regla in reglas or ():
        resultado.agregar(regla)
    return resultado


def edad_en_fecha(nacimiento, referencia):
    """Años cumplidos en una fecha, o ``None`` si falta alguno de los datos."""
    if not nacimiento or not referencia:
        return None
    return (
        referencia.year
        - nacimiento.year
        - ((referencia.month, referencia.day) < (nacimiento.month, nacimiento.day))
    )


class MixinReglas(forms.Form):
    """Formulario que evalúa reglas sacramentales al validar.

    Cada formulario que usa el mixin sobrescribe ``reglas_de(datos)`` con sus
    reglas y, si hace falta, ``preparar_reglas(datos)`` para resolver personas
    o partidas antes de evaluarlas (p. ej. el bautismo enlazado). Las reglas
    fijas que se informan desde el primer GET (un RECUERDA que no depende de
    los datos) se declaran en ``reglas_iniciales``.

    Con una advertencia pendiente el formulario no es válido: hay que marcar
    «Verificado / excepción autorizada» y escribir el motivo; ambas cosas se
    revalidan en el servidor. Los bloqueos se agregan como error sin campo.
    """

    reglas_verificadas = forms.BooleanField(
        required=False,
        label="Verificado / excepción autorizada",
        help_text=(
            "Marque la casilla solo después de verificar la advertencia "
            "o si la excepción está autorizada por el párroco."
        ),
    )
    reglas_motivo = forms.CharField(
        label="Motivo de la verificación",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resultado_reglas = None
        self.advertencias_pendientes = []
        self.advertencias_aceptadas = []

    def reglas_de(self, datos):
        """Reglas aplicables a los datos ya limpios; lo sobrescribe cada formulario."""
        return []

    def reglas_iniciales(self):
        """Reglas que se muestran ya desde el GET, antes de evaluar nada."""
        return []

    @property
    def recuerdos_visibles(self):
        """Recuerdos a mostrar en pantalla (tras validar, o los iniciales en el GET)."""
        if self.resultado_reglas is None:
            return self.reglas_iniciales()
        return self.resultado_reglas.recuerdos

    def preparar_reglas(self, datos):
        """Hook: resuelve personas, bautismos, etc. antes de evaluar las reglas."""

    def clean(self):
        datos = super().clean()
        self.preparar_reglas(datos)
        resultado = evaluar_reglas(self.reglas_de(datos))
        self.resultado_reglas = resultado

        verificada = bool(datos.get("reglas_verificadas"))
        motivo = (datos.get("reglas_motivo") or "").strip()
        for regla in resultado.bloqueos:
            self.add_error(None, regla.texto())
        for regla in resultado.advertencias:
            if not verificada:
                self.advertencias_pendientes.append(regla)
                self.add_error(
                    None,
                    f"{regla.texto()} Marque «Verificado / excepción autorizada» y "
                    "escriba el motivo para continuar.",
                )
            elif not motivo:
                self.advertencias_pendientes.append(regla)
                self.add_error(
                    None,
                    f"{regla.texto()} Escriba el motivo de la verificación para continuar.",
                )
            else:
                self.advertencias_aceptadas.append((regla, motivo))
        return datos
