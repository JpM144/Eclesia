from django import forms

from core.choices import TipoDocumento
from core.forms import FormularioBase
from personas.models import Documento, Fiel, Madre, Padre, Padrino


class PadreForm(FormularioBase):
    class Meta:
        model = Padre
        fields = ["cedula", "nombre", "apellido"]


class MadreForm(FormularioBase):
    class Meta:
        model = Madre
        fields = ["cedula", "nombre", "apellido"]


class FielForm(FormularioBase):
    """Formulario de fiel con documento obligatorio (tipo + número auxiliares)."""

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.documento_id:
            documento = self.instance.documento
            self.fields["tipo_documento"].initial = documento.tipo_documento
            self.fields["numero_documento"].initial = documento.numero_documento

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_documento")
        numero = datos.get("numero_documento", "")
        if tipo and not numero:
            self.add_error("numero_documento", "Indique el número del documento.")
        elif numero and not tipo:
            self.add_error("tipo_documento", "Seleccione el tipo de documento.")
        elif tipo and numero:
            documento, _ = Documento.objects.get_or_create(
                tipo_documento=tipo, numero_documento=numero
            )
            if Fiel.objects.filter(documento=documento).exclude(pk=self.instance.pk).exists():
                self.add_error("numero_documento", "Este documento ya pertenece a otra persona.")
        elif self.instance.pk is None:
            self.add_error("numero_documento", "Indique el documento del fiel.")
        return datos

    def save(self, commit=True):
        fiel = super().save(commit=False)
        tipo = self.cleaned_data.get("tipo_documento")
        numero = self.cleaned_data.get("numero_documento", "")
        if tipo and numero:
            documento, _ = Documento.objects.get_or_create(
                tipo_documento=tipo, numero_documento=numero
            )
            fiel.documento = documento
        if commit:
            fiel.save()
            self.save_m2m()
        return fiel


class PadrinoForm(FormularioBase):
    """Formulario de padrino con documento opcional (tipo + número auxiliares)."""

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

    class Meta:
        model = Padrino
        fields = ["nombre"]
        field_order = ["nombre", "tipo_documento", "numero_documento"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.documento_id:
            documento = self.instance.documento
            self.fields["tipo_documento"].initial = documento.tipo_documento
            self.fields["numero_documento"].initial = documento.numero_documento

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_documento")
        numero = datos.get("numero_documento", "")
        if tipo and not numero:
            self.add_error("numero_documento", "Indique el número del documento.")
        elif numero and not tipo:
            self.add_error("tipo_documento", "Seleccione el tipo de documento.")
        return datos

    def save(self, commit=True):
        padrino = super().save(commit=False)
        tipo = self.cleaned_data.get("tipo_documento")
        numero = self.cleaned_data.get("numero_documento", "")
        if tipo and numero:
            documento, _ = Documento.objects.get_or_create(
                tipo_documento=tipo, numero_documento=numero
            )
            padrino.documento = documento
        else:
            padrino.documento = None
        if commit:
            padrino.save()
            self.save_m2m()
        return padrino
