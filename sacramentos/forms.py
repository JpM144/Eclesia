"""Formulario de registro de bautismos.

El formulario es un ``forms.Form`` plano (no un ``ModelForm``): reúne datos de
varias tablas (``Sacramento``, ``Bautismo`` y las personas ``Fiel``, ``Padre``,
``Madre`` y ``Padrino``) y valida aquí, con mensajes en español, todas las
reglas que después vuelven a comprobar los modelos (``full_clean``): rango de
fechas, tipo de libro, can. 875 (testigo cuando no hay padrino ni madrina) y
unicidad del número de partida. ``datos_para_servicio()`` entrega el diccionario
anidado que consume ``registrar_bautismo``.
"""

from django import forms
from django.core.exceptions import ValidationError

from core.choices import (
    EstadoLibro,
    EstadoRegistro,
    FinalidadCertificado,
    RelacionCertificado,
    Sexo,
    TipoDocumento,
    TipoHijo,
    TipoLibro,
)
from core.forms import widget_cascada
from core.validators import (
    normalizar_documento,
    normalizar_telefono,
    solo_letras,
    validar_documento,
    validar_telefono,
)
from parroquias.models import Libro, Ministro
from personas.consultas import FIEL, contar_partidas
from personas.models import Fiel
from ubicacion.models import Departamento, Municipio, Pais


class LibroBautismoChoiceField(forms.ModelChoiceField):
    """Select de los libros de bautismos abiertos de las parroquias."""

    def __init__(self, **kwargs):
        kwargs.setdefault(
            "queryset",
            Libro.objects.filter(
                tipo_libro=TipoLibro.BAUTISMOS, estado=EstadoLibro.ABIERTO
            ).select_related("parroquia"),
        )
        kwargs.setdefault("label", "Libro de bautismos")
        kwargs.setdefault("empty_label", "---------")
        super().__init__(**kwargs)


class BautismoForm(forms.Form):
    """Registro de un bautismo completo (partida, bautizado, filiación y padrinos)."""

    # --- Partida ---
    libro = LibroBautismoChoiceField()
    fecha = forms.DateField(
        label="Fecha del bautismo",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ministro = forms.ModelChoiceField(
        queryset=Ministro.objects.all(),
        label="Ministro que bautizó",
    )
    doy_fe = forms.ModelChoiceField(
        queryset=Ministro.objects.all(),
        label="Párroco que da fe",
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    # --- Bautizado (fiel) ---
    fiel_tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento del bautizado",
        required=False,
    )
    fiel_numero_documento = forms.CharField(
        max_length=30, label="Número de documento del bautizado", required=False
    )
    fiel_nombres = forms.CharField(max_length=255, label="Nombres del bautizado")
    fiel_apellidos = forms.CharField(max_length=255, label="Apellidos del bautizado")
    fiel_fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fiel_pais = forms.ModelChoiceField(
        queryset=Pais.objects.all(),
        label="País de nacimiento",
        required=False,
        widget=widget_cascada("pais"),
    )
    fiel_departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        label="Departamento de nacimiento",
        required=False,
        widget=widget_cascada("departamento", url="/ubicacion/api/departamentos/"),
    )
    fiel_municipio_nacimiento = forms.ModelChoiceField(
        queryset=Municipio.objects.all(),
        label="Municipio de nacimiento",
        required=False,
        widget=widget_cascada("municipio", url="/ubicacion/api/municipios/"),
    )
    fiel_telefono = forms.CharField(max_length=20, label="Teléfono", required=False)
    fiel_sexo = forms.ChoiceField(
        choices=[("", "---------"), *Sexo.choices],
        label="Sexo",
        required=False,
    )

    # --- Filiación ---
    tipo_hijo = forms.ChoiceField(choices=TipoHijo.choices, label="Tipo de hijo")
    padre_biologico_nombre = forms.CharField(
        max_length=255, label="Nombre del padre biológico", required=False
    )
    madre_biologica_nombre = forms.CharField(
        max_length=255, label="Nombre de la madre biológica", required=False
    )

    # --- Padres ---
    padre_tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento del padre",
        required=False,
    )
    padre_numero_documento = forms.CharField(
        max_length=30, label="Número de documento del padre", required=False
    )
    padre_nombre = forms.CharField(max_length=100, label="Nombre del padre", required=False)
    padre_apellido = forms.CharField(max_length=100, label="Apellido del padre", required=False)

    madre_tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento de la madre",
        required=False,
    )
    madre_numero_documento = forms.CharField(
        max_length=30, label="Número de documento de la madre", required=False
    )
    madre_nombre = forms.CharField(max_length=100, label="Nombre de la madre", required=False)
    madre_apellido = forms.CharField(max_length=100, label="Apellido de la madre", required=False)

    # --- Abuelos ---
    abuelo_paterno = forms.CharField(max_length=255, label="Abuelo paterno", required=False)
    abuela_paterna = forms.CharField(max_length=255, label="Abuela paterna", required=False)
    abuelo_materno = forms.CharField(max_length=255, label="Abuelo materno", required=False)
    abuela_materna = forms.CharField(max_length=255, label="Abuela materna", required=False)

    # --- Padrinos o testigo ---
    padrino_tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento del padrino",
        required=False,
    )
    padrino_numero_documento = forms.CharField(
        max_length=30, label="Número de documento del padrino", required=False
    )
    padrino_nombre = forms.CharField(max_length=255, label="Nombre del padrino", required=False)

    madrina_tipo_documento = forms.ChoiceField(
        choices=[("", "---------"), *TipoDocumento.choices],
        label="Tipo de documento de la madrina",
        required=False,
    )
    madrina_numero_documento = forms.CharField(
        max_length=30, label="Número de documento de la madrina", required=False
    )
    madrina_nombre = forms.CharField(max_length=255, label="Nombre de la madrina", required=False)

    testigo_nombre = forms.CharField(max_length=255, label="Nombre del testigo", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            clases = campo.widget.attrs.get("class", "")
            campo.widget.attrs["class"] = f"{clases} form-control".strip()
        # Documentos validados durante clean(); se inicializan para poder
        # consultarlos aunque el clean() no llegue a asignarlos.
        self.documento_fiel = None
        self.documento_padre = None
        self.documento_madre = None
        self.documento_padrino = None
        self.documento_madrina = None
        # Sacramento que se está corrigiendo (para no marcarlo como duplicado).
        self.excluir_sacramento = None
        self._marcar_campos_persona()
        self._marcar_tipos_dato()
        libro = self.initial.get("libro")
        if libro is not None and hasattr(libro, "parroquia") and not self.initial.get("doy_fe"):
            parroco = getattr(libro.parroquia, "parroco", None)
            if parroco is not None:
                self.initial["doy_fe"] = parroco.pk

    def _marcar_campos_persona(self):
        """Marca los campos que usa ``buscar_persona.js`` para autocompletar."""
        for prefijo in ("fiel", "padre", "madre", "padrino", "madrina"):
            self.fields[f"{prefijo}_tipo_documento"].widget.attrs["data-documento-tipo"] = "tipo"
            self.fields[f"{prefijo}_numero_documento"].widget.attrs["data-documento-numero"] = (
                "numero"
            )
        for campo, nombre in {
            "fiel_nombres": "nombres",
            "fiel_apellidos": "apellidos",
            "fiel_fecha_nacimiento": "fecha_nacimiento",
            "fiel_municipio_nacimiento": "municipio",
            "fiel_sexo": "sexo",
            "padre_nombre": "nombres",
            "padre_apellido": "apellidos",
            "madre_nombre": "nombres",
            "madre_apellido": "apellidos",
            "padrino_nombre": "nombres",
            "madrina_nombre": "nombres",
        }.items():
            self.fields[campo].widget.attrs["data-campo-persona"] = nombre

    CAMPOS_NOMBRE = (
        "fiel_nombres",
        "fiel_apellidos",
        "padre_nombre",
        "padre_apellido",
        "madre_nombre",
        "madre_apellido",
        "padrino_nombre",
        "madrina_nombre",
        "abuelo_paterno",
        "abuela_paterna",
        "abuelo_materno",
        "abuela_materna",
        "testigo_nombre",
        "padre_biologico_nombre",
        "madre_biologica_nombre",
    )

    def _marcar_tipos_dato(self):
        """Añade a los widgets los atributos que usa ``formularios.js``."""
        for campo in self.CAMPOS_NOMBRE:
            self.fields[campo].widget.attrs["data-solo-letras"] = "si"
        self.fields["fiel_telefono"].widget.attrs["data-solo-numeros"] = "si"
        self.fields["fiel_telefono"].widget.attrs["inputmode"] = "numeric"
        for prefijo in ("fiel", "padre", "madre", "padrino", "madrina"):
            widget = self.fields[f"{prefijo}_numero_documento"].widget
            widget.attrs["data-solo-numeros"] = "si"
            widget.attrs["inputmode"] = "numeric"

    def clean(self):
        datos = super().clean()
        self._validar_partida(datos)
        self._validar_fiel(datos)
        self._validar_padres(datos)
        self._validar_padrinos_o_testigo(datos)
        self._validar_nombres_y_telefono(datos)
        return datos

    def _validar_nombres_y_telefono(self, datos):
        for campo in self.CAMPOS_NOMBRE:
            valor = datos.get(campo)
            if not valor:
                continue
            try:
                solo_letras(valor)
            except ValidationError as error:
                self.add_error(campo, error.messages)
        telefono = datos.get("fiel_telefono")
        if telefono:
            try:
                validar_telefono(telefono)
            except ValidationError as error:
                self.add_error("fiel_telefono", error.messages)
                return
            datos["fiel_telefono"] = normalizar_telefono(telefono)
            self.cleaned_data["fiel_telefono"] = datos["fiel_telefono"]

    def _validar_partida(self, datos):
        libro = datos.get("libro")
        if libro is not None and libro.estado != EstadoLibro.ABIERTO:
            self.add_error("libro", "No se pueden inscribir partidas en un libro cerrado.")

    def _validar_fiel(self, datos):
        documento = self._validar_documento(
            datos, "fiel", "El documento del bautizado", requerido=True
        )
        if documento:
            self.documento_fiel = documento
        # Sexo obligatorio
        if not datos.get("fiel_sexo"):
            self.add_error("fiel_sexo", "Indique el sexo del bautizado.")
        # Fechas: nacimiento, bautismo o registro en el futuro
        from django.utils import timezone

        hoy = timezone.localdate() if hasattr(timezone, "localdate") else timezone.now().date()
        fecha_nac = datos.get("fiel_fecha_nacimiento")
        fecha_baut = datos.get("fecha")
        if fecha_nac and fecha_nac > hoy:
            self.add_error(
                "fiel_fecha_nacimiento",
                "La fecha de nacimiento no puede ser en el futuro.",
            )
        if fecha_baut and fecha_baut > hoy:
            self.add_error("fecha", "La fecha del bautismo no puede ser en el futuro.")
        # Nacimiento posterior al bautismo
        if fecha_nac and fecha_baut and fecha_nac > fecha_baut:
            self.add_error(
                "fiel_fecha_nacimiento",
                "La fecha de nacimiento no puede ser posterior al bautismo.",
            )
        # can. 864: un fiel no puede tener dos bautismos activos ni corregidos.
        if documento:
            fiel = Fiel.objects.filter(
                documento__tipo_documento=documento["tipo_documento"],
                documento__numero_documento=documento["numero_documento"],
            ).first()
            if fiel is not None:
                from .models import Bautismo

                duplicados = Bautismo.objects.filter(
                    sacramento__fiel=fiel,
                    sacramento__estado__in=[
                        EstadoRegistro.ACTIVO,
                        EstadoRegistro.CORREGIDO,
                    ],
                )
                if self.excluir_sacramento is not None:
                    duplicados = duplicados.exclude(pk=self.excluir_sacramento.pk)
                if duplicados.exists():
                    self.add_error(
                        "fiel_numero_documento",
                        "Este fiel ya tiene un bautismo registrado.",
                    )

    def _validar_padres(self, datos):
        tipo_hijo = datos.get("tipo_hijo")
        es_adoptivo = tipo_hijo == TipoHijo.ADOPTIVO

        # Padres biológicos: solo se aceptan (y son obligatorios) si el tipo de
        # hijo es adoptivo; con otro tipo se ignoran y se guardan vacíos.
        if es_adoptivo:
            if not datos.get("padre_biologico_nombre"):
                self.add_error(
                    "padre_biologico_nombre",
                    "Indique el nombre del padre biológico.",
                )
            if not datos.get("madre_biologica_nombre"):
                self.add_error(
                    "madre_biologica_nombre",
                    "Indique el nombre de la madre biológica.",
                )
        else:
            datos["padre_biologico_nombre"] = ""
            datos["madre_biologica_nombre"] = ""

        padre = self._validar_documento(datos, "padre", "El documento del padre", requerido=True)
        if padre:
            if not datos.get("padre_nombre"):
                self.add_error("padre_nombre", "Indique el nombre del padre.")
            if not datos.get("padre_apellido"):
                self.add_error("padre_apellido", "Indique el apellido del padre.")
            padre["nombre"] = datos.get("padre_nombre", "")
            padre["apellido"] = datos.get("padre_apellido", "")
            self.documento_padre = padre

        madre = self._validar_documento(datos, "madre", "El documento de la madre", requerido=True)
        if madre:
            if not datos.get("madre_nombre"):
                self.add_error("madre_nombre", "Indique el nombre de la madre.")
            if not datos.get("madre_apellido"):
                self.add_error("madre_apellido", "Indique el apellido de la madre.")
            madre["nombre"] = datos.get("madre_nombre", "")
            madre["apellido"] = datos.get("madre_apellido", "")
            self.documento_madre = madre

        # Documentos distintos entre padre, madre y bautizado
        self._comparar_documentos(
            self.documento_padre,
            self.documento_madre,
            "madre_numero_documento",
            "El padre y la madre deben tener documentos distintos.",
        )
        self._comparar_documentos(
            self.documento_padre,
            self.documento_fiel,
            "padre_numero_documento",
            "El padre y el bautizado no pueden tener el mismo documento.",
        )
        self._comparar_documentos(
            self.documento_madre,
            self.documento_fiel,
            "madre_numero_documento",
            "La madre y el bautizado no pueden tener el mismo documento.",
        )

    @staticmethod
    def _documentos_iguales(uno, otro):
        return bool(uno and otro) and (
            uno["tipo_documento"] == otro["tipo_documento"]
            and uno["numero_documento"] == otro["numero_documento"]
        )

    def _comparar_documentos(self, uno, otro, campo, mensaje):
        if self._documentos_iguales(uno, otro):
            self.add_error(campo, mensaje)

    def _validar_padrinos_o_testigo(self, datos):
        padrino = self._validar_documento(
            datos, "padrino", "El documento del padrino", requerido=False
        )
        if padrino:
            if not datos.get("padrino_nombre"):
                self.add_error("padrino_nombre", "Indique el nombre del padrino.")
            padrino["nombre"] = datos.get("padrino_nombre", "")
            self.documento_padrino = padrino

        madrina = self._validar_documento(
            datos, "madrina", "El documento de la madrina", requerido=False
        )
        if madrina:
            if not datos.get("madrina_nombre"):
                self.add_error("madrina_nombre", "Indique el nombre de la madrina.")
            madrina["nombre"] = datos.get("madrina_nombre", "")
            self.documento_madrina = madrina

        if not self.documento_padrino and not self.documento_madrina:
            if not datos.get("testigo_nombre"):
                self.add_error(
                    "testigo_nombre",
                    "Debe especificar un testigo cuando no hay padrino ni madrina.",
                )

        # can. 874: ni el padrino ni la madrina pueden ser el bautizado, su
        # padre o su madre; y padrino y madrina deben tener documentos distintos.
        prohibidos = (
            (self.documento_fiel, "El padrino no puede ser el bautizado."),
            (self.documento_padre, "El padrino no puede ser el padre del bautizado."),
            (self.documento_madre, "El padrino no puede ser la madre del bautizado."),
        )
        for documento, mensaje in prohibidos:
            if self._documentos_iguales(self.documento_padrino, documento):
                self.add_error("padrino_numero_documento", mensaje)
        prohibidos_madrina = (
            (self.documento_fiel, "La madrina no puede ser el bautizado."),
            (self.documento_padre, "La madrina no puede ser el padre del bautizado."),
            (self.documento_madre, "La madrina no puede ser la madre del bautizado."),
        )
        for documento, mensaje in prohibidos_madrina:
            if self._documentos_iguales(self.documento_madrina, documento):
                self.add_error("madrina_numero_documento", mensaje)
        self._comparar_documentos(
            self.documento_padrino,
            self.documento_madrina,
            "madrina_numero_documento",
            "El padrino y la madrina no pueden tener el mismo documento.",
        )

    def _validar_documento(self, datos, prefijo, etiqueta, requerido):
        campo_tipo = f"{prefijo}_tipo_documento"
        campo_numero = f"{prefijo}_numero_documento"
        tipo = datos.get(campo_tipo)
        numero = (datos.get(campo_numero) or "").strip()

        if not tipo and not numero:
            if requerido:
                self.add_error(campo_tipo, f"{etiqueta} es obligatorio.")
            return None
        if tipo and not numero:
            self.add_error(campo_numero, "Indique el número del documento.")
            return None
        if numero and not tipo:
            self.add_error(campo_tipo, "Seleccione el tipo de documento.")
            return None

        numero = normalizar_documento(tipo, numero)
        try:
            validar_documento(tipo, numero)
        except ValidationError as error:
            self.add_error(campo_numero, error.messages)
            return None

        datos[campo_numero] = numero
        self.cleaned_data[campo_numero] = numero
        return {"tipo_documento": tipo, "numero_documento": numero}

    def datos_para_servicio(self):
        """Diccionario anidado que consume ``sacramentos.services.registrar_bautismo``."""
        libro = self.cleaned_data["libro"]
        return {
            "partida": {
                "libro": libro,
                "fecha": self.cleaned_data["fecha"],
                "parroquia": libro.parroquia,
                "ministro": self.cleaned_data["ministro"],
                "observaciones": self.cleaned_data.get("observaciones", ""),
            },
            "fiel": {
                "tipo_documento": self.cleaned_data.get("fiel_tipo_documento"),
                "numero_documento": self.cleaned_data.get("fiel_numero_documento"),
                "nombres": self.cleaned_data.get("fiel_nombres", ""),
                "apellidos": self.cleaned_data.get("fiel_apellidos", ""),
                "fecha_nacimiento": self.cleaned_data.get("fiel_fecha_nacimiento"),
                "municipio_nacimiento": self.cleaned_data.get("fiel_municipio_nacimiento"),
                "telefono": self.cleaned_data.get("fiel_telefono", ""),
                "sexo": self.cleaned_data.get("fiel_sexo") or None,
            },
            "padre": getattr(self, "documento_padre", None),
            "madre": getattr(self, "documento_madre", None),
            "padrino": getattr(self, "documento_padrino", None),
            "madrina": getattr(self, "documento_madrina", None),
            "abuelo_paterno": self.cleaned_data.get("abuelo_paterno", ""),
            "abuela_paterna": self.cleaned_data.get("abuela_paterna", ""),
            "abuelo_materno": self.cleaned_data.get("abuelo_materno", ""),
            "abuela_materna": self.cleaned_data.get("abuela_materna", ""),
            "tipo_hijo": self.cleaned_data.get("tipo_hijo"),
            "testigo_nombre": self.cleaned_data.get("testigo_nombre", ""),
            "padre_biologico_nombre": self.cleaned_data.get("padre_biologico_nombre", ""),
            "madre_biologica_nombre": self.cleaned_data.get("madre_biologica_nombre", ""),
            "doy_fe": self.cleaned_data.get("doy_fe"),
        }


class MotivoForm(forms.Form):
    """Pide el motivo de una corrección, anulación o eliminación de partida."""

    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        help_text="Explique brevemente el motivo. Queda registrado en el historial.",
    )


class BautismoEditarForm(BautismoForm):
    """Corrección de una partida de bautismo ya registrada.

    Reutiliza los campos y las validaciones de ``BautismoForm``. El libro queda
    fijo (solo lectura) y se añade el ``motivo`` de la corrección; el folio, el
    número de partida y la fecha de registro no se editan.
    """

    motivo = forms.CharField(
        label="Motivo de la corrección",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explique qué se corrige. Queda registrado en el historial de la partida.",
    )

    # Campos de identidad que quedan en solo lectura para las personas ya
    # vinculadas a la partida (se corrigen desde la ficha de la persona).
    CAMPOS_IDENTIDAD = {
        "fiel": (
            "fiel_tipo_documento",
            "fiel_numero_documento",
            "fiel_nombres",
            "fiel_apellidos",
        ),
        "padre": (
            "padre_tipo_documento",
            "padre_numero_documento",
            "padre_nombre",
            "padre_apellido",
        ),
        "madre": (
            "madre_tipo_documento",
            "madre_numero_documento",
            "madre_nombre",
            "madre_apellido",
        ),
        "padrino": ("padrino_tipo_documento", "padrino_numero_documento", "padrino_nombre"),
        "madrina": ("madrina_tipo_documento", "madrina_numero_documento", "madrina_nombre"),
    }

    def __init__(self, *args, bautismo=None, **kwargs):
        self.bautismo = bautismo
        if bautismo is not None and not kwargs.get("initial"):
            kwargs["initial"] = self._initial_desde_bautismo(bautismo)
        super().__init__(*args, **kwargs)
        self.excluir_sacramento = bautismo.sacramento if bautismo is not None else None
        if bautismo is not None:
            libro = bautismo.sacramento.libro
            self.fields["libro"].queryset = Libro.objects.filter(pk=libro.pk)
            self.fields["libro"].initial = libro
            self.fields["libro"].disabled = True
            self._bloquear_personas_vinculadas(bautismo)
        self.aviso_partidas = self._contar_otras_partidas(bautismo)

    def _bloquear_personas_vinculadas(self, bautismo):
        """Deja en solo lectura el nombre y el documento de las personas ya vinculadas."""
        vinculadas = {
            "fiel": bautismo.sacramento.fiel_id,
            "padre": bautismo.padre_id,
            "madre": bautismo.madre_id,
            "padrino": bautismo.padrino_id,
            "madrina": bautismo.madrina_id,
        }
        for prefijo, vinculada in vinculadas.items():
            if not vinculada:
                continue
            for campo in self.CAMPOS_IDENTIDAD[prefijo]:
                if campo in self.fields:
                    self.fields[campo].disabled = True

    @staticmethod
    def _contar_otras_partidas(bautismo):
        """Partidas distintas de esta en las que aparece el bautizado (0 si no hay)."""
        if bautismo is None or not bautismo.sacramento.fiel_id:
            return 0
        return max(contar_partidas(FIEL, bautismo.sacramento.fiel_id) - 1, 0)

    def _validar_partida(self, datos):
        # Al corregir no se inscribe una partida nueva: el libro puede estar cerrado.
        return

    @staticmethod
    def _inicial_persona(inicial, prefijo, persona):
        if persona is None:
            return
        documento = getattr(persona, "documento", None)
        if documento is not None:
            inicial[f"{prefijo}_tipo_documento"] = documento.tipo_documento
            inicial[f"{prefijo}_numero_documento"] = documento.numero_documento
        inicial[f"{prefijo}_nombre"] = getattr(persona, "nombre", "")
        inicial[f"{prefijo}_apellido"] = getattr(persona, "apellido", "")

    def _initial_desde_bautismo(self, bautismo):
        sacramento = bautismo.sacramento
        fiel = sacramento.fiel
        inicial = {
            "libro": sacramento.libro_id,
            "fecha": sacramento.fecha,
            "ministro": sacramento.ministro_id,
            "doy_fe": bautismo.doy_fe_id,
            "observaciones": sacramento.observaciones,
            "tipo_hijo": bautismo.tipo_hijo,
            "padre_biologico_nombre": bautismo.padre_biologico_nombre,
            "madre_biologica_nombre": bautismo.madre_biologica_nombre,
            "abuelo_paterno": bautismo.abuelo_paterno,
            "abuela_paterna": bautismo.abuela_paterna,
            "abuelo_materno": bautismo.abuelo_materno,
            "abuela_materna": bautismo.abuela_materna,
            "testigo_nombre": bautismo.testigo_nombre,
        }
        if fiel is not None:
            documento = fiel.documento if fiel.documento_id else None
            inicial.update(
                {
                    "fiel_tipo_documento": documento.tipo_documento if documento else "",
                    "fiel_numero_documento": documento.numero_documento if documento else "",
                    "fiel_nombres": fiel.nombres,
                    "fiel_apellidos": fiel.apellidos,
                    "fiel_fecha_nacimiento": fiel.fecha_nacimiento,
                    "fiel_telefono": fiel.telefono,
                    "fiel_sexo": fiel.sexo,
                }
            )
            municipio = fiel.municipio_nacimiento if fiel.municipio_nacimiento_id else None
            if municipio is not None:
                inicial["fiel_municipio_nacimiento"] = municipio.pk
                inicial["fiel_departamento"] = municipio.departamento_id
                inicial["fiel_pais"] = municipio.departamento.pais_id
        for prefijo, persona in (
            ("padre", bautismo.padre),
            ("madre", bautismo.madre),
            ("padrino", bautismo.padrino),
            ("madrina", bautismo.madrina),
        ):
            self._inicial_persona(inicial, prefijo, persona)
        return inicial


class SolicitudCertificadoForm(forms.Form):
    """Solicitud de un certificado: quién lo pide, con qué documento, relación y finalidad.

    Todos los campos son obligatorios. El nombre solo admite letras y el
    documento se valida según su tipo. Cuando la finalidad es ``Otro`` se exige
    explicarla; en caso contrario ese texto se descarta.
    """

    solicitante = forms.CharField(
        max_length=255,
        label="Nombre de quien solicita el certificado",
    )
    tipo_documento = forms.ChoiceField(
        choices=TipoDocumento.choices,
        label="Tipo de documento",
    )
    numero_documento = forms.CharField(
        max_length=30,
        label="Número de documento",
    )
    relacion = forms.ChoiceField(
        choices=RelacionCertificado.choices,
        label="Relación con el titular",
    )
    finalidad = forms.ChoiceField(
        choices=FinalidadCertificado.choices,
        label="Finalidad del certificado",
    )
    finalidad_otro = forms.CharField(
        max_length=255,
        label="Especifique la finalidad",
        required=False,
        help_text="Obligatorio cuando la finalidad es «Otro».",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            clases = campo.widget.attrs.get("class", "")
            campo.widget.attrs["class"] = f"{clases} form-control".strip()
        self.fields["numero_documento"].widget.attrs["inputmode"] = "numeric"
        self.fields["solicitante"].widget.attrs["data-solo-letras"] = "si"

    def clean_solicitante(self):
        valor = (self.cleaned_data.get("solicitante") or "").strip()
        try:
            solo_letras(valor)
        except ValidationError as error:
            raise ValidationError(error.messages)
        return valor

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_documento")
        numero = (datos.get("numero_documento") or "").strip()
        if tipo and numero:
            numero = normalizar_documento(tipo, numero)
            try:
                validar_documento(tipo, numero)
            except ValidationError as error:
                self.add_error("numero_documento", error.messages)
            else:
                datos["numero_documento"] = numero
                self.cleaned_data["numero_documento"] = numero
        if datos.get("finalidad") == FinalidadCertificado.OTRO:
            if not (datos.get("finalidad_otro") or "").strip():
                self.add_error(
                    "finalidad_otro",
                    "Indique la finalidad del certificado.",
                )
        else:
            datos["finalidad_otro"] = ""
            self.cleaned_data["finalidad_otro"] = ""
        return datos

    def _finalidad_display(self):
        finalidad = self.cleaned_data.get("finalidad")
        if finalidad == FinalidadCertificado.OTRO:
            return self.cleaned_data.get("finalidad_otro", "")
        return self.fields["finalidad"].choices and dict(FinalidadCertificado.choices).get(
            finalidad, finalidad
        )

    def datos_para_servicio(self):
        """Diccionario con la solicitud ya validada y su descripción para el historial."""
        relacion_display = dict(RelacionCertificado.choices).get(
            self.cleaned_data["relacion"], self.cleaned_data["relacion"]
        )
        finalidad_display = self._finalidad_display()
        return {
            "solicitante": self.cleaned_data["solicitante"],
            "tipo_documento": self.cleaned_data["tipo_documento"],
            "numero_documento": self.cleaned_data["numero_documento"],
            "relacion": self.cleaned_data["relacion"],
            "relacion_display": relacion_display,
            "finalidad": self.cleaned_data["finalidad"],
            "finalidad_display": finalidad_display,
            "finalidad_otro": self.cleaned_data.get("finalidad_otro", ""),
            "descripcion_historial": (
                f"Certificado expedido a {self.cleaned_data['solicitante']} "
                f"({relacion_display}) para {finalidad_display}."
            ),
        }
