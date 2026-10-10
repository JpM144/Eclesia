from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.choices import (
    AccionHistorial,
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
from personas.models import Fiel, Madre, Padre, Padrino
from ubicacion.models import Municipio

User = get_user_model()


class Sacramento(models.Model):
    tipo = models.CharField(max_length=20, choices=TipoSacramento.choices, verbose_name="tipo")
    fiel = models.ForeignKey(
        Fiel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sacramentos",
    )
    libro = models.ForeignKey(
        Libro, on_delete=models.PROTECT, related_name="sacramentos", verbose_name="libro"
    )
    folio = models.ForeignKey(Folio, on_delete=models.PROTECT, related_name="sacramentos")
    numero = models.PositiveIntegerField(verbose_name="número")
    fecha = models.DateField()
    fecha_registro = models.DateField(verbose_name="fecha de registro")
    parroquia = models.ForeignKey(
        Parroquia, on_delete=models.PROTECT, null=True, blank=True, related_name="sacramentos"
    )
    ministro = models.ForeignKey(
        Ministro, on_delete=models.PROTECT, null=True, blank=True, related_name="sacramentos"
    )
    iglesia = models.ForeignKey(
        Iglesia,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sacramentos",
        verbose_name="iglesia",
    )
    estado = models.CharField(
        max_length=10,
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
        verbose_name="estado",
    )
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sacramentos_creados",
    )
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sacramentos_modificados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "sacramento"
        verbose_name_plural = "sacramentos"
        ordering = ["fecha", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["libro", "numero"],
                name="unico_numero_por_libro",
                violation_error_message="Ya existe una partida con ese número en este libro",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(tipo=TipoSacramento.MATRIMONIO, fiel__isnull=True)
                    | models.Q(
                        tipo__in=[
                            TipoSacramento.BAUTISMO,
                            TipoSacramento.CONFIRMACION,
                            TipoSacramento.PRIMERA_COMUNION,
                        ],
                        fiel__isnull=False,
                    )
                ),
                name="sacramento_fiel_segun_tipo",
            ),
            models.CheckConstraint(
                condition=models.Q(fecha_registro__gte=models.F("fecha")),
                name="sacramento_fecha_registro_mayor_o_igual_fecha",
            ),
        ]

    def clean(self):
        super().clean()
        libro = self.libro if self.libro_id else None
        if libro:
            if self.folio_id and self.folio.libro_id != libro.pk:
                raise ValidationError({"folio": "El folio debe pertenecer al libro de la partida."})
            if self.pk is None and libro.estado != EstadoLibro.ABIERTO:
                raise ValidationError(
                    {"libro": "No se pueden inscribir partidas en un libro cerrado."}
                )
            if self.fecha_registro:
                if libro.fecha_apertura and self.fecha_registro < libro.fecha_apertura:
                    raise ValidationError(
                        {
                            "fecha_registro": (
                                "La fecha de registro no puede ser anterior a la apertura "
                                "del libro."
                            )
                        }
                    )
                if libro.fecha_cierre and self.fecha_registro > libro.fecha_cierre:
                    raise ValidationError(
                        {
                            "fecha_registro": (
                                "La fecha de registro no puede ser posterior al cierre del libro."
                            )
                        }
                    )
            tipo_libro_esperado = {
                TipoSacramento.BAUTISMO: TipoLibro.BAUTISMOS,
                TipoSacramento.CONFIRMACION: TipoLibro.CONFIRMACIONES,
                TipoSacramento.MATRIMONIO: TipoLibro.MATRIMONIOS,
                TipoSacramento.PRIMERA_COMUNION: TipoLibro.PRIMERA_COMUNION,
            }.get(self.tipo)
            if tipo_libro_esperado and libro.tipo_libro != tipo_libro_esperado:
                raise ValidationError(
                    {
                        "folio": (
                            "El tipo de libro no corresponde al tipo de sacramento "
                            f"(se esperaba {tipo_libro_esperado.label})."
                        )
                    }
                )
            if self.iglesia and self.iglesia.parroquia_id != libro.parroquia_id:
                raise ValidationError(
                    {"iglesia": "La iglesia debe pertenecer a la parroquia del libro."}
                )

    def __str__(self):
        return f"{self.get_tipo_display()} N.° {self.numero} - {self.folio}"


class Bautismo(models.Model):
    sacramento = models.OneToOneField(
        Sacramento, on_delete=models.CASCADE, primary_key=True, related_name="bautismo"
    )
    padre = models.ForeignKey(
        Padre, on_delete=models.PROTECT, related_name="bautismos", null=True, blank=True
    )
    madre = models.ForeignKey(
        Madre, on_delete=models.PROTECT, related_name="bautismos", null=True, blank=True
    )
    abuelo_paterno = models.CharField(max_length=255, verbose_name="abuelo paterno", blank=True)
    abuela_paterna = models.CharField(max_length=255, verbose_name="abuela paterna", blank=True)
    abuelo_materno = models.CharField(max_length=255, verbose_name="abuelo materno", blank=True)
    abuela_materna = models.CharField(max_length=255, verbose_name="abuela materna", blank=True)
    tipo_hijo = models.CharField(
        max_length=20, choices=TipoHijo.choices, verbose_name="tipo de hijo"
    )
    testigo_nombre = models.CharField(max_length=255, blank=True, verbose_name="nombre del testigo")
    padre_biologico_nombre = models.CharField(
        max_length=255, blank=True, verbose_name="nombre del padre biológico"
    )
    madre_biologica_nombre = models.CharField(
        max_length=255, blank=True, verbose_name="nombre de la madre biológica"
    )
    padrino = models.ForeignKey(
        Padrino,
        on_delete=models.PROTECT,
        related_name="bautismos_como_padrino",
        null=True,
        blank=True,
    )
    madrina = models.ForeignKey(
        Padrino,
        on_delete=models.PROTECT,
        related_name="bautismos_como_madrina",
        null=True,
        blank=True,
    )
    quien_firma = models.ForeignKey(
        Ministro, on_delete=models.PROTECT, related_name="bautismos_firmados"
    )
    doy_fe = models.ForeignKey(Ministro, on_delete=models.PROTECT, related_name="bautismos_doy_fe")

    class Meta:
        verbose_name = "bautismo"
        verbose_name_plural = "bautismos"
        ordering = ["sacramento"]

    def clean(self):
        super().clean()
        # can. 875: si no hay padrino ni madrina, testigo_nombre es obligatorio
        if not self.padrino and not self.madrina and not self.testigo_nombre:
            raise ValidationError(
                {"testigo_nombre": ("Debe especificar un testigo cuando no hay padrino ni madrina")}
            )

    def __str__(self):
        return f"Bautismo de {self.sacramento.fiel}"


class DatosBautismoMixin(models.Model):
    """Datos del bautismo de quien recibe otro sacramento (confirmación, comunión)."""

    bautismo = models.ForeignKey(
        Bautismo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_set",
        verbose_name="bautismo",
    )
    fecha_bautismo = models.DateField(null=True, blank=True, verbose_name="fecha de bautismo")
    parroquia_bautismo = models.CharField(
        max_length=255, blank=True, verbose_name="parroquia de bautismo"
    )
    iglesia_bautismo = models.CharField(
        max_length=255, blank=True, verbose_name="iglesia de bautismo"
    )
    municipio_bautismo = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="municipio de bautismo",
    )
    libro_bautismo = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="libro de bautismo"
    )
    folio_bautismo = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="folio de bautismo"
    )
    numero_bautismo = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="número de bautismo"
    )
    observaciones_bautismo = models.TextField(blank=True, verbose_name="observaciones del bautismo")

    class Meta:
        abstract = True


class Confirmacion(DatosBautismoMixin):
    sacramento = models.OneToOneField(
        Sacramento, on_delete=models.CASCADE, primary_key=True, related_name="confirmacion"
    )
    edad = models.PositiveIntegerField(verbose_name="edad")
    padre = models.ForeignKey(
        Padre,
        on_delete=models.PROTECT,
        related_name="confirmaciones",
        null=True,
        blank=True,
    )
    madre = models.ForeignKey(
        Madre,
        on_delete=models.PROTECT,
        related_name="confirmaciones",
        null=True,
        blank=True,
    )
    padrino = models.ForeignKey(
        Padrino,
        on_delete=models.PROTECT,
        related_name="confirmaciones_como_padrino",
        null=True,
        blank=True,
    )
    madrina = models.ForeignKey(
        Padrino,
        on_delete=models.PROTECT,
        related_name="confirmaciones_como_madrina",
        null=True,
        blank=True,
    )
    doy_fe = models.ForeignKey(
        Ministro, on_delete=models.PROTECT, related_name="confirmaciones_doy_fe"
    )

    class Meta:
        verbose_name = "confirmación"
        verbose_name_plural = "confirmaciones"
        ordering = ["sacramento"]

    def __str__(self):
        return f"Confirmación de {self.sacramento.fiel}"


class PrimeraComunion(DatosBautismoMixin):
    sacramento = models.OneToOneField(
        Sacramento, on_delete=models.CASCADE, primary_key=True, related_name="primera_comunion"
    )
    edad = models.PositiveIntegerField(verbose_name="edad")
    padre = models.ForeignKey(
        Padre,
        on_delete=models.PROTECT,
        related_name="primeras_comuniones",
        null=True,
        blank=True,
    )
    madre = models.ForeignKey(
        Madre,
        on_delete=models.PROTECT,
        related_name="primeras_comuniones",
        null=True,
        blank=True,
    )
    doy_fe = models.ForeignKey(
        Ministro, on_delete=models.PROTECT, related_name="primeras_comuniones_doy_fe"
    )

    class Meta:
        verbose_name = "primera comunión"
        verbose_name_plural = "primeras comuniones"
        ordering = ["sacramento"]

    def __str__(self):
        return f"Primera comunión de {self.sacramento.fiel}"


class Matrimonio(models.Model):
    sacramento = models.OneToOneField(
        Sacramento, on_delete=models.CASCADE, primary_key=True, related_name="matrimonio"
    )
    expediente = models.PositiveIntegerField(verbose_name="expediente")
    fecha_declaracion = models.DateField(verbose_name="fecha de declaración")
    dispensa_impedimento = models.CharField(
        max_length=2,
        choices=SiNo.choices,
        default=SiNo.NO,
        verbose_name="¿hubo dispensa de impedimento?",
    )
    impedimentos = models.TextField(blank=True, verbose_name="impedimentos")
    dispensa_autoridad = models.CharField(
        max_length=255, blank=True, verbose_name="autoridad que concede la dispensa"
    )
    fecha_dispensa = models.DateField(null=True, blank=True, verbose_name="fecha de la dispensa")
    documento_dispensa = models.FileField(
        upload_to="dispensas/", null=True, blank=True, verbose_name="documento de la dispensa"
    )

    class Meta:
        verbose_name = "matrimonio"
        verbose_name_plural = "matrimonios"
        ordering = ["expediente"]

    def clean(self):
        super().clean()
        if self.dispensa_impedimento == SiNo.SI:
            errores = {}
            if not self.impedimentos:
                errores["impedimentos"] = "Debe indicar los impedimentos dispensados."
            if not self.dispensa_autoridad:
                errores["dispensa_autoridad"] = "Debe indicar la autoridad que concede la dispensa."
            if errores:
                raise ValidationError(errores)

    def __str__(self):
        return f"Matrimonio - Expediente {self.expediente}"


class Contrayente(models.Model):
    matrimonio = models.ForeignKey(
        Matrimonio, on_delete=models.CASCADE, related_name="contrayentes"
    )
    fiel = models.ForeignKey(Fiel, on_delete=models.PROTECT, related_name="contrayentes")
    sexo = models.CharField(max_length=1, choices=Sexo.choices)
    parroquia_bautismo = models.ForeignKey(
        Parroquia, on_delete=models.PROTECT, related_name="+", verbose_name="parroquia de bautismo"
    )
    libro_bautismo = models.PositiveIntegerField(verbose_name="libro de bautismo")
    folio_bautismo = models.PositiveIntegerField(verbose_name="folio de bautismo")
    numero_bautismo = models.PositiveIntegerField(verbose_name="número de bautismo")
    parroquia_confirmacion = models.ForeignKey(
        Parroquia,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="parroquia de confirmación",
    )
    fecha_confirmacion = models.DateField(verbose_name="fecha de confirmación")
    direccion_residencia = models.CharField(max_length=255, verbose_name="dirección de residencia")
    nombre_padre = models.CharField(max_length=255, verbose_name="nombre del padre")
    nombre_madre = models.CharField(max_length=255, verbose_name="nombre de la madre")
    edad = models.PositiveIntegerField(verbose_name="edad")
    estado_civil = models.CharField(max_length=20, choices=EstadoCivil.choices)
    fecha_defuncion_conyuge = models.DateField(
        null=True, blank=True, verbose_name="fecha de defunción del cónyuge"
    )
    certificado_parroquia = models.FileField(
        upload_to="certificados_matrimonio/", null=True, blank=True, verbose_name="certificado"
    )
    religion = models.CharField(max_length=50)
    profesion = models.CharField(max_length=255, verbose_name="profesión")
    acepta_libertad_matrimonio = models.CharField(
        max_length=2,
        choices=RespuestaDoctrina.choices,
        verbose_name=(
            "¿Pide el Matrimonio católico con plena libertad y consciente de los derechos "
            "y deberes que implica el contrato-sacramento?"
        ),
    )
    conoce_unidad_indisolubilidad = models.CharField(
        max_length=2,
        choices=RespuestaDoctrina.choices,
        verbose_name=(
            "¿Sabe que el matrimonio católico tiene como propiedades fundamentales "
            "la unidad e indisolubilidad?"
        ),
    )
    conoce_obligaciones_familia = models.CharField(
        max_length=2,
        choices=RespuestaDoctrina.choices,
        verbose_name=(
            "¿Conoce las obligaciones de esposo y padre de familia: amor, fidelidad, respeto "
            "de la dignidad y derechos de la persona humana, ayuda a la esposa, procreación "
            "y educación cristiana de los hijos?"
        ),
    )
    impedimentos_anteriores = models.CharField(
        max_length=2,
        choices=RespuestaDoctrina.choices,
        verbose_name=(
            "¿Tiene algún impedimento canónico o se ha casado por lo civil anteriormente?"
        ),
    )
    dispuesto_cumplir = models.CharField(
        max_length=2,
        choices=RespuestaDoctrina.choices,
        verbose_name="¿Está dispuesto a cumplir con las condiciones matrimoniales?",
    )
    lugar_despues_matrimonio = models.TextField(
        verbose_name="¿Dónde vivirá después del matrimonio?"
    )

    class Meta:
        verbose_name = "contrayente"
        verbose_name_plural = "contrayentes"
        ordering = ["matrimonio", "sexo"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrimonio", "sexo"], name="unico_sexo_por_matrimonio"
            ),
            models.UniqueConstraint(
                fields=["matrimonio", "fiel"], name="unico_fiel_por_matrimonio"
            ),
        ]

    def __str__(self):
        return f"{self.fiel} ({self.get_sexo_display()})"


class TestigoMatrimonio(models.Model):
    matrimonio = models.ForeignKey(Matrimonio, on_delete=models.CASCADE, related_name="testigos")
    tipo_documento = models.CharField(max_length=2, choices=TipoDocumento.choices)
    cedula = models.CharField(max_length=30, verbose_name="cédula")
    nombre = models.CharField(max_length=255)
    religion = models.CharField(max_length=100)
    estado_civil = models.CharField(max_length=20, choices=EstadoCivil.choices)
    profesion = models.CharField(max_length=100, verbose_name="profesión")

    class Meta:
        verbose_name = "testigo de matrimonio"
        verbose_name_plural = "testigos de matrimonio"
        ordering = ["matrimonio", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_documento_display()} {self.cedula})"


class PadrinoMatrimonio(models.Model):
    matrimonio = models.ForeignKey(Matrimonio, on_delete=models.CASCADE, related_name="padrinos")
    tipo_documento = models.CharField(max_length=2, choices=TipoDocumento.choices)
    cedula = models.CharField(max_length=30, verbose_name="cédula")
    nombre = models.CharField(max_length=255)
    religion = models.CharField(max_length=100)
    estado_civil = models.CharField(max_length=20, choices=EstadoCivil.choices)
    profesion = models.CharField(max_length=100, verbose_name="profesión")

    class Meta:
        verbose_name = "padrino de matrimonio"
        verbose_name_plural = "padrinos de matrimonio"
        ordering = ["matrimonio", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_documento_display()} {self.cedula})"


class ProclamaMatrimonio(models.Model):
    matrimonio = models.ForeignKey(Matrimonio, on_delete=models.CASCADE, related_name="proclamas")
    numero = models.PositiveIntegerField(verbose_name="número")
    fecha_proclama = models.DateField(verbose_name="fecha de la proclama")
    resultado = models.CharField(
        max_length=20, choices=ResultadoProclama.choices, verbose_name="resultado"
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "proclama de matrimonio"
        verbose_name_plural = "proclamas de matrimonio"
        ordering = ["matrimonio", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrimonio", "numero"], name="unico_numero_proclama_por_matrimonio"
            )
        ]

    def __str__(self):
        return f"Proclama N.° {self.numero} - Matrimonio {self.matrimonio.expediente}"


class HijoReconocidoMatrimonio(models.Model):
    matrimonio = models.ForeignKey(Matrimonio, on_delete=models.CASCADE, related_name="hijos")
    tipo_documento = models.CharField(max_length=2, choices=TipoDocumento.choices)
    numero_documento = models.CharField(max_length=30, verbose_name="número de documento")
    nombre = models.CharField(max_length=255)
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="fecha de nacimiento")
    edad = models.PositiveIntegerField(verbose_name="edad")
    bautizado = models.CharField(max_length=2, choices=SiNo.choices)

    class Meta:
        verbose_name = "hijo reconocido"
        verbose_name_plural = "hijos reconocidos"
        ordering = ["matrimonio", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_documento_display()} {self.numero_documento})"


class NotaMarginalMatrimonio(models.Model):
    matrimonio = models.OneToOneField(
        Matrimonio, on_delete=models.CASCADE, primary_key=True, related_name="nota_marginal"
    )
    parroquia_licencia = models.CharField(max_length=255, verbose_name="parroquia que licencia")
    delegacion_licencia = models.CharField(max_length=255, verbose_name="delegación que licencia")
    parroco_delega = models.CharField(max_length=255, verbose_name="párroco que delega")
    presencio = models.CharField(max_length=255)
    doy_fe = models.CharField(max_length=255)
    parroco = models.CharField(max_length=255, verbose_name="párroco")
    fecha_licencia = models.DateField(verbose_name="fecha de licencia")
    fecha_matrimonio = models.DateField(verbose_name="fecha de matrimonio")
    fecha_envio_acta = models.DateField(verbose_name="fecha de envío del acta")
    hora_matrimonio = models.TimeField(verbose_name="hora del matrimonio")

    class Meta:
        verbose_name = "nota marginal de matrimonio"
        verbose_name_plural = "notas marginales de matrimonio"
        ordering = ["matrimonio"]

    def __str__(self):
        return f"Nota marginal - Matrimonio {self.matrimonio.expediente}"


class DocumentoSacramento(models.Model):
    sacramento = models.ForeignKey(Sacramento, on_delete=models.CASCADE, related_name="documentos")
    descripcion = models.CharField(max_length=255)
    archivo = models.FileField(upload_to="documentos_sacramentos/")
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_sacramento_subidos",
    )
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "documento de sacramento"
        verbose_name_plural = "documentos de sacramento"
        ordering = ["sacramento", "descripcion"]

    def __str__(self):
        return f"{self.descripcion} - {self.sacramento}"


class AnotacionMarginal(models.Model):
    sacramento = models.ForeignKey(
        Sacramento,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="anotaciones_marginales",
        verbose_name="sacramento",
    )
    sacramento_origen = models.ForeignKey(
        Sacramento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anotaciones_generadas",
        verbose_name="sacramento de origen",
    )
    tipo = models.CharField(
        max_length=20, choices=TipoAnotacionMarginal.choices, verbose_name="tipo"
    )
    fecha = models.DateField()
    descripcion = models.TextField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoAnotacion.choices,
        default=EstadoAnotacion.POR_COMUNICAR,
        verbose_name="estado",
    )
    parroquia_destino = models.ForeignKey(
        Parroquia,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="parroquia de destino",
    )
    parroquia_destino_texto = models.CharField(
        max_length=255, blank=True, verbose_name="parroquia de destino (texto)"
    )
    fecha_comunicacion = models.DateField(
        null=True, blank=True, verbose_name="fecha de comunicación"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "anotación marginal"
        verbose_name_plural = "anotaciones marginales"
        ordering = ["sacramento", "fecha", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(estado=EstadoAnotacion.ANOTADA, sacramento__isnull=True),
                name="anotacion_anotada_requiere_sacramento",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    estado=EstadoAnotacion.COMUNICADA, fecha_comunicacion__isnull=True
                ),
                name="anotacion_comunicada_requiere_fecha",
            ),
        ]

    def __str__(self):
        return f"Anotación marginal - {self.get_tipo_display()} ({self.sacramento})"


class HistorialSacramento(models.Model):
    sacramento = models.ForeignKey(Sacramento, on_delete=models.CASCADE, related_name="historial")
    accion = models.CharField(max_length=20, choices=AccionHistorial.choices, verbose_name="acción")
    descripcion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historial_sacramentos",
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "historial de sacramento"
        verbose_name_plural = "historial de sacramentos"
        ordering = ["sacramento", "-fecha", "-id"]

    def __str__(self):
        return f"{self.get_accion_display()} - {self.sacramento} ({self.fecha:%Y-%m-%d})"
