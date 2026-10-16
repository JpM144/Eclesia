from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import InlineForeignKeyField, construct_instance


def widget_cascada(rol, url=None):
    """Devuelve un ``Select`` marcado con los atributos de ``ubicacion.js``.

    ``rol`` es uno de ``pais``, ``departamento`` o ``municipio`` y ``url`` la
    ruta del endpoint JSON que llena ese select (solo para departamento/municipio).
    """
    atributos = {f"data-cascada-{rol}": rol}
    if url:
        atributos["data-url"] = url
    return forms.Select(attrs=atributos)


def marcar_solo_letras(campo):
    """Marca el widget de ``campo`` con ``data-solo-letras`` (lo lee formularios.js)."""
    campo.widget.attrs["data-solo-letras"] = "si"


def marcar_solo_numeros(campo, numerico=True):
    """Marca el widget de ``campo`` con ``data-solo-numeros`` e ``inputmode``."""
    campo.widget.attrs["data-solo-numeros"] = "si"
    if numerico:
        campo.widget.attrs["inputmode"] = "numeric"


def marcar_documento(campo_tipo, campo_numero):
    """Marca el par tipo/número de documento para ``buscar_persona.js``."""
    campo_tipo.widget.attrs["data-documento-tipo"] = "tipo"
    campo_numero.widget.attrs["data-documento-numero"] = "numero"
    marcar_solo_numeros(campo_numero)


class FormularioBase(forms.ModelForm):
    """ModelForm que aplica la clase CSS ``form-control`` a todos los widgets.

    Los formularios concretos solo declaran ``Meta`` (model, fields, widgets con
    atributos extra) y heredan de aquí el estilo de Bootstrap.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            clases = campo.widget.attrs.get("class", "")
            campo.widget.attrs["class"] = f"{clases} form-control".strip()


class FormularioSinConstraints(FormularioBase):
    """ModelForm que no deja que las ``Constraint`` del modelo generen mensajes.

    Django valida también las restricciones del modelo (``validate_constraints``)
    dentro del ``ModelForm``. Para las unicidades condicionales el mensaje por
    defecto es genérico y en inglés; estos formularios las revisan en ``clean()``
    y muestran un mensaje claro en español. Las unicidades de campo o
    ``unique_together`` siguen validándose con ``validate_unique``.
    """

    def _post_clean(self):
        opts = self._meta
        exclude = self._get_validation_exclusions()
        for name, field in self.fields.items():
            if isinstance(field, InlineForeignKeyField):
                exclude.add(name)

        try:
            self.instance = construct_instance(self, self.instance, opts.fields, opts.exclude)
        except ValidationError as error:
            self._update_errors(error)

        try:
            self.instance.full_clean(
                exclude=exclude, validate_unique=False, validate_constraints=False
            )
        except ValidationError as error:
            self._update_errors(error)

        if self._validate_unique:
            self.validate_unique()
