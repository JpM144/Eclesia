from django import forms

from core.forms import FormularioBase, widget_cascada

from .models import Departamento, Municipio, Pais


class PaisForm(FormularioBase):
    class Meta:
        model = Pais
        fields = ["nombre"]


class DepartamentoForm(FormularioBase):
    class Meta:
        model = Departamento
        fields = ["pais", "nombre"]


class MunicipioForm(FormularioBase):
    """Formulario de municipio con un select auxiliar "País" que no se guarda.

    "País" solo sirve para filtrar las opciones de "Departamento" mediante
    ``static/js/ubicacion.js``. Al editar, se precarga a partir del país del
    departamento del municipio.
    """

    pais = forms.ModelChoiceField(
        queryset=Pais.objects.all(),
        label="País",
        required=False,
        widget=widget_cascada("pais"),
    )

    class Meta:
        model = Municipio
        fields = ["departamento", "nombre"]
        widgets = {
            "departamento": widget_cascada("departamento", url="/ubicacion/api/departamentos/"),
        }
        field_order = ["pais", "departamento", "nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["pais"].initial = self.instance.departamento.pais_id
