"""Validadores reutilizables con mensajes en español.

Se usan tanto en los modelos (``full_clean``) como en los formularios para que
los nombres y apellidos solo admitan letras, y los documentos y teléfonos solo
los caracteres que corresponden a su tipo.
"""

import re

from django.core.exceptions import ValidationError

from core.choices import TipoDocumento

LETRAS_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'.\- ]+$")
DOCUMENTO_SOLO_DIGITOS = (TipoDocumento.CC, TipoDocumento.TI, TipoDocumento.RC)
NUIP = getattr(TipoDocumento, "NUIP", None)
if NUIP is not None:
    DOCUMENTO_SOLO_DIGITOS = (*DOCUMENTO_SOLO_DIGITOS, NUIP)
DOCUMENTO_ALFANUMERICO = (TipoDocumento.CE, TipoDocumento.PA)

MENSAJE_SOLO_LETRAS = "Este campo solo admite letras, espacios, apóstrofo, guion y punto."
MENSAJE_MINIMO_LETRAS = "Este campo debe tener al menos 2 caracteres."
MENSAJE_DOCUMENTO_NUMEROS = "El documento debe contener solo números."
MENSAJE_DOCUMENTO_RANGO_DIGITOS = "El documento debe tener entre 5 y 15 dígitos."
MENSAJE_DOCUMENTO_ALFANUMERICO = "El documento solo admite letras y números."
MENSAJE_DOCUMENTO_RANGO_ALFANUMERICO = "El documento debe tener entre 5 y 20 caracteres."
MENSAJE_TELEFONO_NUMEROS = "El teléfono debe contener solo números."
MENSAJE_TELEFONO_RANGO = "El teléfono debe tener entre 7 y 10 dígitos."


def solo_letras(valor):
    """Acepta letras (con tildes, ü y ñ), espacios, apóstrofo, guion y punto.

    Exige al menos dos caracteres y rechaza cualquier dígito.
    """
    valor = (valor or "").strip()
    if not valor:
        return
    if not LETRAS_RE.match(valor):
        raise ValidationError(MENSAJE_SOLO_LETRAS)
    if len(valor) < 2:
        raise ValidationError(MENSAJE_MINIMO_LETRAS)


def normalizar_documento(tipo, numero):
    """Quita separadores y ajusta mayúsculas/dígitos según el tipo."""
    limpio = (numero or "").replace(".", "").replace(" ", "").replace("-", "")
    if tipo in DOCUMENTO_ALFANUMERICO:
        return limpio.upper()
    return limpio


def validar_documento(tipo, numero):
    """Valida el número de documento según su tipo.

    CC, TI, RC (y NUIP si existe) solo admiten dígitos, de 5 a 15. CE y PA
    admiten letras y dígitos, de 5 a 20. Si no se reconoce el tipo, no valida.
    """
    numero = (numero or "").strip()
    if not numero or not tipo:
        return
    normalizado = normalizar_documento(tipo, numero)
    if tipo in DOCUMENTO_SOLO_DIGITOS:
        if not normalizado.isdigit():
            raise ValidationError(MENSAJE_DOCUMENTO_NUMEROS)
        if not 5 <= len(normalizado) <= 15:
            raise ValidationError(MENSAJE_DOCUMENTO_RANGO_DIGITOS)
    elif tipo in DOCUMENTO_ALFANUMERICO:
        if not re.fullmatch(r"[A-Za-z0-9]+", normalizado):
            raise ValidationError(MENSAJE_DOCUMENTO_ALFANUMERICO)
        if not 5 <= len(normalizado) <= 20:
            raise ValidationError(MENSAJE_DOCUMENTO_RANGO_ALFANUMERICO)


def validador_documento(tipo):
    """Devuelve un validador de Django para el número de documento del tipo."""

    def _validador(valor):
        return validar_documento(tipo, valor)

    return _validador


def normalizar_telefono(valor):
    """Deja solo los dígitos del teléfono (quita espacios y guiones)."""
    return re.sub(r"[^0-9]", "", valor or "")


def validar_telefono(valor):
    """Acepta espacios y guiones al escribir, pero exige de 7 a 10 dígitos."""
    valor = (valor or "").strip()
    if not valor:
        return
    limpio = normalizar_telefono(valor)
    if not limpio.isdigit():
        raise ValidationError(MENSAJE_TELEFONO_NUMEROS)
    if not 7 <= len(limpio) <= 10:
        raise ValidationError(MENSAJE_TELEFONO_RANGO)
