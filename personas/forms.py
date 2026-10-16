from django import forms
from django.core.exceptions import ValidationError

from core.choices import TipoDocumento
from core.forms import (
    FormularioBase,
    marcar_documento,
    marcar_solo_letras,
    marcar_solo_numeros,
)
from core.validators import normalizar_documento, validar_documento
from personas.models import Documento, Fiel, Madre, Padre, Padrino

SOLO_DIGITOS = (TipoDocumento.CC, TipoDocumento.TI, TipoDocumento.RC)
CON_MAYUSCULAS = (TipoDocumento.PA, TipoDocumento.CE)


class DocumentoMixin(forms.ModelForm):
    """Añade el par ``tipo_documento`` + ``numero_documento`` a un ModelForm.

    Reúne en un único par de campos la identificación de una persona y lo
    resuelve contra el catálogo ``personas.Documento``; así ningún formulario
    pide la misma información dos veces (no hay un campo ``documento`` propio
    además de los auxiliares):

    * ``tipo_documento`` y ``numero_documento`` se guardan como
      ``Documento(tipo_documento, numero_documento)`` reutilizando el registro
      si ya existe (``get_or_create``).
    * El número se normaliza: se quitan puntos, espacios y guiones; para los
      tipos ``PA`` (pasaporte) y ``CE`` (cédula de extranjería) se pasa a
      mayúsculas y para ``CC``, ``TI`` y ``RC`` se exige que sean solo dígitos.
    * Si el mismo documento ya pertenece a otra fila del mismo modelo
      (``documento_unico``), se muestra un error en ``numero_documento`` en
      español, nunca un error 500. El mismo ``Documento`` sí puede pertenecer a
      una fila de otro modelo (p. ej. un fiel y una madre a la vez).
    * ``documento_requerido`` indica si el documento es obligatorio. Al editar
      se precargan los valores desde el documento enlazado.

    Se combina con ``FormularioBase`` (``class MiForm(DocumentoMixin,
    FormularioBase)``). El modelo destino debe tener un campo ``documento``.
    """

    documento_requerido = True
    documento_unico = True

    tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento",
        required=False,
    )
    numero_documento = forms.CharField(
        max_length=30,
        label="Número de documento",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        marcar_documento(self.fields["tipo_documento"], self.fields["numero_documento"])
        for nombre in ("nombre", "apellido", "nombres", "apellidos"):
            if nombre in self.fields:
                marcar_solo_letras(self.fields[nombre])
        if "telefono" in self.fields:
            marcar_solo_numeros(self.fields["telefono"])
        if self.instance.pk and self.instance.documento_id:
            documento = self.instance.documento
            self.fields["tipo_documento"].initial = documento.tipo_documento
            self.fields["numero_documento"].initial = documento.numero_documento

    @staticmethod
    def normalizar_numero(tipo, numero):
        """Quita separadores y ajusta mayúsculas/dígitos según el tipo."""
        return normalizar_documento(tipo, numero)

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_documento")
        numero = (datos.get("numero_documento") or "").strip()

        if not tipo and not numero:
            if self.documento_requerido:
                self.add_error("tipo_documento", "Indique el documento de la persona.")
            return datos
        if tipo and not numero:
            self.add_error("numero_documento", "Indique el número del documento.")
            return datos
        if numero and not tipo:
            self.add_error("tipo_documento", "Seleccione el tipo de documento.")
            return datos

        numero = self.normalizar_numero(tipo, numero)
        try:
            validar_documento(tipo, numero)
        except ValidationError as error:
            self.add_error("numero_documento", error.messages)
            return datos

        datos["numero_documento"] = numero
        self.cleaned_data["numero_documento"] = numero

        documento = Documento.objects.filter(tipo_documento=tipo, numero_documento=numero).first()
        self.documento_existente = documento
        if documento is not None and self.documento_unico:
            duplicados = self._meta.model.objects.filter(documento=documento)
            if self.instance.pk:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                self.add_error("numero_documento", "Este documento ya pertenece a otra persona.")
        return datos

    def save(self, commit=True):
        obj = super().save(commit=False)
        tipo = self.cleaned_data.get("tipo_documento")
        numero = self.cleaned_data.get("numero_documento", "")
        if tipo and numero:
            documento = getattr(self, "documento_existente", None)
            if documento is None:
                documento, _ = Documento.objects.get_or_create(
                    tipo_documento=tipo, numero_documento=numero
                )
            obj.documento = documento
        elif not self.documento_requerido:
            obj.documento = None
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class PadreForm(DocumentoMixin, FormularioBase):
    class Meta:
        model = Padre
        fields = ["nombre", "apellido"]
        field_order = ["tipo_documento", "numero_documento", "nombre", "apellido"]


class MadreForm(DocumentoMixin, FormularioBase):
    class Meta:
        model = Madre
        fields = ["nombre", "apellido"]
        field_order = ["tipo_documento", "numero_documento", "nombre", "apellido"]


class FielForm(DocumentoMixin, FormularioBase):
    """Formulario de fiel con documento obligatorio (tipo + número auxiliares)."""

    class Meta:
        model = Fiel
        fields = [
            "nombres",
            "apellidos",
            "fecha_nacimiento",
            "municipio_nacimiento",
            "telefono",
            "sexo",
        ]
        field_order = [
            "tipo_documento",
            "numero_documento",
            "nombres",
            "apellidos",
            "fecha_nacimiento",
            "municipio_nacimiento",
            "telefono",
            "sexo",
        ]


class PadrinoForm(DocumentoMixin, FormularioBase):
    """Formulario de padrino con documento obligatorio (tipo + número auxiliares)."""

    class Meta:
        model = Padrino
        fields = ["nombre"]
        field_order = ["nombre", "tipo_documento", "numero_documento"]
