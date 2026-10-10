import secrets

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.choices import RolUsuario

CAMPOS = [
    "nombres",
    "apellidos",
    "username",
    "correo",
    "rol",
    "password1",
    "password2",
    "codigo",
]


class RegistroForm(UserCreationForm):
    """Autorregistro de usuarios con el código de la parroquia.

    Parte de ``UserCreationForm`` para reutilizar los validadores de contraseña
    de Django. El código se compara con ``settings.CODIGO_REGISTRO``.
    """

    nombres = forms.CharField(label="Nombres", max_length=150)
    apellidos = forms.CharField(label="Apellidos", max_length=150)
    correo = forms.EmailField(label="Correo electrónico")
    rol = forms.ChoiceField(label="Rol", choices=RolUsuario.choices)
    codigo = forms.CharField(
        label="Código de la parroquia",
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )

    field_order = CAMPOS

    class Meta:
        model = User
        fields = ["username"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuario"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control"

    def clean_correo(self):
        correo = self.cleaned_data["correo"]
        if User.objects.filter(email__iexact=correo).exists():
            raise ValidationError("Ya existe una cuenta con este correo electrónico.")
        return correo

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"]
        esperado = settings.CODIGO_REGISTRO
        if not esperado or not secrets.compare_digest(
            codigo.encode("utf-8"), esperado.encode("utf-8")
        ):
            raise ValidationError("El código de la parroquia no es correcto.")
        return codigo

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.first_name = self.cleaned_data["nombres"]
        usuario.last_name = self.cleaned_data["apellidos"]
        usuario.email = self.cleaned_data["correo"]
        if commit:
            usuario.save()
        return usuario
