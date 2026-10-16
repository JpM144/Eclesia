from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.choices import CargoMinisterial, EstadoLibro, TipoLibro
from core.validators import normalizar_telefono, solo_letras, validar_telefono
from personas.models import Documento
from ubicacion.models import Municipio


class Parroquia(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="parroquias")
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, null=True, blank=True, verbose_name="teléfono")
    email = models.EmailField(null=True, blank=True)
    parroco = models.ForeignKey(
        "Ministro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="párroco",
    )

    class Meta:
        verbose_name = "parroquia"
        verbose_name_plural = "parroquias"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Ministro(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True)
    cargo = models.CharField(
        max_length=50, choices=CargoMinisterial.choices, verbose_name="cargo ministerial"
    )
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="fecha de nacimiento")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="teléfono")
    email = models.EmailField(null=True, blank=True)
    documento = models.OneToOneField(
        Documento, on_delete=models.PROTECT, related_name="ministro", verbose_name="documento"
    )
    parroquia = models.ForeignKey(
        Parroquia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ministros",
    )

    class Meta:
        verbose_name = "ministro"
        verbose_name_plural = "ministros"
        ordering = ["apellido", "nombre"]

    def clean(self):
        super().clean()
        errores = {}
        for campo in ("nombre", "apellido"):
            valor = getattr(self, campo)
            if valor:
                try:
                    solo_letras(valor)
                except ValidationError as error:
                    errores[campo] = error.messages
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
        return f"{self.nombre} {self.apellido} - {self.get_cargo_display()}"


class Libro(models.Model):
    nombre = models.CharField(max_length=100)
    tipo_libro = models.CharField(
        max_length=20, choices=TipoLibro.choices, verbose_name="tipo de libro"
    )
    detalle = models.TextField(verbose_name="detalle")
    numero_libro = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="número de libro"
    )
    fecha_apertura = models.DateField(verbose_name="fecha de apertura")
    total_folios = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="total de folios"
    )
    partidas_por_folio = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name="partidas por folio",
        help_text="Cuántas partidas caben en cada folio (entre 1 y 20).",
    )
    ministro_apertura = models.ForeignKey(
        "Ministro",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="libros_abiertos",
        verbose_name="ministro que abre",
    )
    estado = models.CharField(
        max_length=10,
        choices=EstadoLibro.choices,
        default=EstadoLibro.ABIERTO,
        verbose_name="estado",
    )
    fecha_cierre = models.DateField(null=True, blank=True, verbose_name="fecha de cierre")
    ministro_cierre = models.ForeignKey(
        "Ministro",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="libros_cerrados",
        verbose_name="ministro que cierra",
    )
    nota_cierre = models.TextField(blank=True, verbose_name="nota de cierre")
    observaciones = models.TextField(blank=True)
    parroquia = models.ForeignKey(Parroquia, on_delete=models.PROTECT, related_name="libros")

    class Meta:
        verbose_name = "libro"
        verbose_name_plural = "libros"
        ordering = ["parroquia", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["parroquia", "nombre"],
                name="unico_libro_por_parroquia",
            ),
            models.UniqueConstraint(
                fields=["parroquia", "tipo_libro", "numero_libro"],
                condition=Q(numero_libro__isnull=False),
                name="unico_libro_tipo_numero_parroquia",
            ),
            models.UniqueConstraint(
                fields=["parroquia", "tipo_libro"],
                condition=Q(estado=EstadoLibro.ABIERTO),
                name="un_libro_abierto_por_tipo",
                violation_error_message=(
                    "Ya existe un libro abierto de este tipo en la parroquia."
                ),
            ),
            models.CheckConstraint(
                condition=~Q(estado=EstadoLibro.CERRADO, fecha_cierre__isnull=True),
                name="libro_cerrado_requiere_fecha_cierre",
            ),
            models.CheckConstraint(
                condition=Q(fecha_cierre__isnull=True)
                | Q(fecha_cierre__gte=models.F("fecha_apertura")),
                name="libro_cierre_no_anterior_a_apertura",
            ),
            models.CheckConstraint(
                condition=Q(total_folios__isnull=True) | Q(total_folios__gt=0),
                name="libro_total_folios_positivo",
            ),
            models.CheckConstraint(
                condition=Q(partidas_por_folio__gt=0),
                name="libro_partidas_por_folio_positivo",
            ),
        ]

    def __str__(self):
        return self.nombre


class Folio(models.Model):
    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, related_name="folios")
    numero_folio = models.PositiveIntegerField(verbose_name="número de folio")
    fecha_creacion = models.DateField(null=True, blank=True, verbose_name="fecha de creación")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "folio"
        verbose_name_plural = "folios"
        ordering = ["libro", "numero_folio"]
        constraints = [
            models.UniqueConstraint(fields=["libro", "numero_folio"], name="unico_folio_por_libro")
        ]

    def clean(self):
        super().clean()
        libro = self.libro if self.libro_id else None
        if libro and libro.total_folios and self.numero_folio > libro.total_folios:
            raise ValidationError(
                {
                    "numero_folio": (
                        f"El folio {self.numero_folio} supera el total declarado "
                        f"del libro ({libro.total_folios})."
                    )
                }
            )

    def __str__(self):
        return f"Folio {self.numero_folio} - {self.libro}"
