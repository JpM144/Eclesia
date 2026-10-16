from django import forms

from core.choices import CargoMinisterial, EstadoLibro, TipoLibro
from core.forms import FormularioBase, FormularioSinConstraints, widget_cascada
from personas.forms import DocumentoMixin
from ubicacion.models import Departamento, Pais

from .models import Folio, Libro, Ministro, Parroquia


class ParroquiaForm(FormularioBase):
    """Formulario de parroquia con los selects encadenados de ``ubicacion.js``.

    Solo se guarda ``municipio``; ``pais`` y ``departamento`` son auxiliares que
    sirven para filtrar las opciones. Al editar se precargan a partir del
    departamento del municipio de la parroquia.
    """

    pais = forms.ModelChoiceField(
        queryset=Pais.objects.all(),
        label="País",
        required=False,
        widget=widget_cascada("pais"),
    )
    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        label="Departamento",
        required=False,
        widget=widget_cascada("departamento", url="/ubicacion/api/departamentos/"),
    )

    class Meta:
        model = Parroquia
        fields = ["nombre", "municipio", "direccion", "telefono", "email", "parroco"]
        widgets = {
            "municipio": widget_cascada("municipio", url="/ubicacion/api/municipios/"),
        }
        field_order = [
            "nombre",
            "pais",
            "departamento",
            "municipio",
            "direccion",
            "telefono",
            "email",
            "parroco",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parroco"].queryset = Ministro.objects.filter(cargo=CargoMinisterial.PARROCO)
        if self.instance.pk and self.instance.municipio_id:
            municipio = self.instance.municipio
            self.fields["pais"].initial = municipio.departamento.pais_id
            self.fields["departamento"].initial = municipio.departamento_id


class MinistroForm(DocumentoMixin, FormularioBase):
    """Formulario de ministro con tipo/número de documento como campos auxiliares.

    El par tipo+número se resuelve contra ``personas.Documento`` mediante
    ``DocumentoMixin``: se reutiliza el documento si ya existe y no pertenece a
    otro ministro. El documento es obligatorio.
    """

    class Meta:
        model = Ministro
        fields = [
            "nombre",
            "apellido",
            "cargo",
            "fecha_nacimiento",
            "telefono",
            "email",
            "parroquia",
        ]
        field_order = [
            "tipo_documento",
            "numero_documento",
            "nombre",
            "apellido",
            "cargo",
            "fecha_nacimiento",
            "telefono",
            "email",
            "parroquia",
        ]


class LibroForm(FormularioSinConstraints):
    """Formulario de apertura y edición de un libro.

    Los campos de la diligencia de cierre (fecha, ministro y nota) no forman
    parte del formulario: el cierre se hace aparte con la acción "Cerrar libro".
    Si el libro ya está cerrado, todos los campos quedan en solo lectura.
    """

    class Meta:
        model = Libro
        fields = [
            "parroquia",
            "tipo_libro",
            "nombre",
            "numero_libro",
            "fecha_apertura",
            "total_folios",
            "partidas_por_folio",
            "ministro_apertura",
            "detalle",
            "observaciones",
        ]
        field_order = [
            "parroquia",
            "tipo_libro",
            "nombre",
            "numero_libro",
            "fecha_apertura",
            "total_folios",
            "partidas_por_folio",
            "ministro_apertura",
            "detalle",
            "observaciones",
        ]
        widgets = {
            "fecha_apertura": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["ministro_apertura"]
        if self.instance.pk:
            campo.queryset = Ministro.objects.filter(parroquia=self.instance.parroquia).order_by(
                "apellido", "nombre"
            )
        else:
            campo.queryset = Ministro.objects.all().order_by(
                "parroquia__nombre", "apellido", "nombre"
            )
        if self.is_bound and not self.instance.pk:
            parroquia_id = self.data.get("parroquia")
            if parroquia_id:
                campo.queryset = campo.queryset.filter(parroquia_id=parroquia_id)
        if self.instance.pk and self.instance.estado == EstadoLibro.CERRADO:
            for f in self.fields.values():
                f.disabled = True

    def clean(self):
        datos = super().clean()
        parroquia = datos.get("parroquia")
        tipo = datos.get("tipo_libro")
        nombre = datos.get("nombre")
        numero = datos.get("numero_libro")
        total_folios = datos.get("total_folios")

        if total_folios is not None and total_folios <= 0:
            self.add_error("total_folios", "El total de folios debe ser mayor que cero.")

        otros = Libro.objects.all()
        if self.instance.pk:
            otros = otros.exclude(pk=self.instance.pk)

        if parroquia and nombre and otros.filter(parroquia=parroquia, nombre=nombre).exists():
            self.add_error("nombre", "Ya existe un libro con ese nombre en esta parroquia.")

        if (
            parroquia
            and tipo
            and numero is not None
            and otros.filter(parroquia=parroquia, tipo_libro=tipo, numero_libro=numero).exists()
        ):
            self.add_error(
                "numero_libro",
                "Ya existe un libro de ese tipo con ese número en esta parroquia.",
            )

        if (
            parroquia
            and tipo
            and otros.filter(
                parroquia=parroquia, tipo_libro=tipo, estado=EstadoLibro.ABIERTO
            ).exists()
        ):
            etiqueta = TipoLibro(tipo).label
            self.add_error(
                "tipo_libro",
                f"Ya hay un libro de {etiqueta} abierto en esta parroquia. "
                "Ciérralo antes de abrir otro",
            )
        return datos


class CerrarLibroForm(forms.Form):
    """Diligencia de cierre de un libro (fecha, ministro que firma y nota)."""

    fecha_cierre = forms.DateField(
        label="Fecha de cierre",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    ministro_cierre = forms.ModelChoiceField(
        queryset=Ministro.objects.none(),
        label="Ministro que firma",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    nota_cierre = forms.CharField(
        label="Nota de cierre",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )

    def __init__(self, *args, libro=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.libro = libro
        if libro is not None:
            self.fields["ministro_cierre"].queryset = Ministro.objects.filter(
                parroquia=libro.parroquia
            ).order_by("apellido", "nombre")


class FolioForm(FormularioBase):
    """Formulario de folio; el libro se asigna desde la vista (CRUD anidado)."""

    class Meta:
        model = Folio
        fields = ["numero_folio", "fecha_creacion", "observaciones"]

    def __init__(self, *args, libro=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.libro = libro

    def clean_numero_folio(self):
        numero = self.cleaned_data["numero_folio"]
        if self.libro is None:
            return numero
        existentes = Folio.objects.filter(libro=self.libro, numero_folio=numero)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Ya existe un folio con ese número en este libro.")
        return numero
