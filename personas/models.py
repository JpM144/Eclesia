from django.core.exceptions import ValidationError
from django.db import models

from core.choices import Sexo, TipoDocumento
from core.validators import (
    normalizar_telefono,
    solo_letras,
    validar_documento,
    validar_telefono,
)
from ubicacion.models import Municipio


def _validar_nombres(campos):
    """Valida con ``solo_letras`` cada campo indicado y devuelve los errores."""
    errores = {}
    for nombre, valor in campos.items():
        try:
            solo_letras(valor)
        except ValidationError as error:
            errores[nombre] = error.messages
    return errores


class Documento(models.Model):
    tipo_documento = models.CharField(max_length=2, choices=TipoDocumento.choices)
    numero_documento = models.CharField(max_length=30)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["tipo_documento", "numero_documento"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "numero_documento"], name="unico_documento"
            )
        ]

    def clean(self):
        super().clean()
        try:
            validar_documento(self.tipo_documento, self.numero_documento)
        except ValidationError as error:
            raise ValidationError({"numero_documento": error.messages}) from error

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero_documento}"


class Padre(models.Model):
    documento = models.OneToOneField(
        Documento, on_delete=models.PROTECT, related_name="padre", verbose_name="documento"
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    class Meta:
        verbose_name = "padre"
        verbose_name_plural = "padres"
        ordering = ["apellido", "nombre"]

    def clean(self):
        super().clean()
        errores = _validar_nombres({"nombre": self.nombre, "apellido": self.apellido})
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Madre(models.Model):
    documento = models.OneToOneField(
        Documento, on_delete=models.PROTECT, related_name="madre", verbose_name="documento"
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    class Meta:
        verbose_name = "madre"
        verbose_name_plural = "madres"
        ordering = ["apellido", "nombre"]

    def clean(self):
        super().clean()
        errores = _validar_nombres({"nombre": self.nombre, "apellido": self.apellido})
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Padrino(models.Model):
    nombre = models.CharField(max_length=255)
    documento = models.OneToOneField(
        Documento, on_delete=models.PROTECT, related_name="padrino", verbose_name="documento"
    )

    class Meta:
        verbose_name = "padrino"
        verbose_name_plural = "padrinos"
        ordering = ["nombre"]

    def clean(self):
        super().clean()
        errores = _validar_nombres({"nombre": self.nombre})
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return self.nombre


class Fiel(models.Model):
    documento = models.OneToOneField(
        Documento, on_delete=models.PROTECT, related_name="fiel", verbose_name="documento"
    )
    nombres = models.CharField(max_length=255)
    apellidos = models.CharField(max_length=255)
    fecha_nacimiento = models.DateField(verbose_name="fecha de nacimiento")
    municipio_nacimiento = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="nacimientos",
        verbose_name="municipio de nacimiento",
    )
    telefono = models.CharField(max_length=20, blank=True, verbose_name="teléfono")
    sexo = models.CharField(
        max_length=1, choices=Sexo.choices, null=True, blank=True, verbose_name="sexo"
    )

    class Meta:
        verbose_name = "fiel"
        verbose_name_plural = "fieles"
        ordering = ["apellidos", "nombres"]

    def clean(self):
        super().clean()
        errores = _validar_nombres({"nombres": self.nombres, "apellidos": self.apellidos})
        if self.telefono:
            try:
                validar_telefono(self.telefono)
            except ValidationError as error:
                errores["telefono"] = error.messages
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.telefono:
            self.telefono = normalizar_telefono(self.telefono)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"
