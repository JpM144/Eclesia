from django.contrib import admin

from .models import (
    AnotacionMarginal,
    Bautismo,
    Confirmacion,
    Contrayente,
    DocumentoSacramento,
    HijoReconocidoMatrimonio,
    HistorialSacramento,
    Matrimonio,
    NotaMarginalMatrimonio,
    PadrinoMatrimonio,
    PartidaEliminada,
    PrimeraComunion,
    ProclamaMatrimonio,
    Sacramento,
    TestigoMatrimonio,
)


@admin.register(Sacramento)
class SacramentoAdmin(admin.ModelAdmin):
    list_display = [
        "tipo",
        "numero",
        "fecha",
        "fecha_registro",
        "folio",
        "parroquia",
        "estado",
        "ministro",
        "fiel",
    ]
    list_filter = ["tipo", "estado", "fecha"]
    search_fields = ["folio__libro__nombre", "fiel__nombres", "fiel__apellidos"]


@admin.register(Bautismo)
class BautismoAdmin(admin.ModelAdmin):
    list_display = [
        "sacramento",
        "padre",
        "madre",
        "tipo_hijo",
        "padrino",
        "madrina",
        "testigo_nombre",
    ]
    search_fields = ["sacramento__fiel__nombres", "sacramento__fiel__apellidos"]


@admin.register(Confirmacion)
class ConfirmacionAdmin(admin.ModelAdmin):
    list_display = ["sacramento", "edad", "padrino", "madrina", "doy_fe"]
    search_fields = ["sacramento__fiel__nombres", "sacramento__fiel__apellidos"]


@admin.register(PrimeraComunion)
class PrimeraComunionAdmin(admin.ModelAdmin):
    list_display = ["sacramento", "edad", "padre", "madre", "doy_fe"]
    search_fields = ["sacramento__fiel__nombres", "sacramento__fiel__apellidos"]


@admin.register(Matrimonio)
class MatrimonioAdmin(admin.ModelAdmin):
    list_display = ["expediente", "fecha_declaracion", "sacramento"]
    search_fields = ["expediente"]


@admin.register(Contrayente)
class ContrayenteAdmin(admin.ModelAdmin):
    list_display = ["matrimonio", "fiel", "sexo", "estado_civil", "edad", "religion"]
    list_filter = ["sexo", "estado_civil"]
    search_fields = ["fiel__nombres", "fiel__apellidos"]


@admin.register(TestigoMatrimonio)
class TestigoMatrimonioAdmin(admin.ModelAdmin):
    list_display = ["matrimonio", "nombre", "tipo_documento", "cedula", "religion"]
    search_fields = ["nombre", "cedula"]


@admin.register(PadrinoMatrimonio)
class PadrinoMatrimonioAdmin(admin.ModelAdmin):
    list_display = ["matrimonio", "nombre", "tipo_documento", "cedula", "religion"]
    search_fields = ["nombre", "cedula"]


@admin.register(ProclamaMatrimonio)
class ProclamaMatrimonioAdmin(admin.ModelAdmin):
    list_display = ["matrimonio", "numero", "fecha_proclama", "resultado"]
    list_filter = ["resultado"]
    search_fields = ["observaciones"]


@admin.register(HijoReconocidoMatrimonio)
class HijoReconocidoMatrimonioAdmin(admin.ModelAdmin):
    list_display = [
        "matrimonio",
        "nombre",
        "tipo_documento",
        "numero_documento",
        "edad",
        "bautizado",
    ]
    search_fields = ["nombre", "numero_documento"]


@admin.register(NotaMarginalMatrimonio)
class NotaMarginalMatrimonioAdmin(admin.ModelAdmin):
    list_display = [
        "matrimonio",
        "parroquia_licencia",
        "fecha_licencia",
        "fecha_matrimonio",
        "hora_matrimonio",
    ]


@admin.register(DocumentoSacramento)
class DocumentoSacramentoAdmin(admin.ModelAdmin):
    list_display = ["sacramento", "descripcion", "archivo", "subido_por", "subido_en"]
    search_fields = ["descripcion"]


@admin.register(AnotacionMarginal)
class AnotacionMarginalAdmin(admin.ModelAdmin):
    list_display = ["sacramento", "tipo", "fecha", "estado"]
    list_filter = ["tipo", "estado"]
    search_fields = ["descripcion"]


@admin.register(HistorialSacramento)
class HistorialSacramentoAdmin(admin.ModelAdmin):
    list_display = ["sacramento", "accion", "usuario", "fecha"]
    list_filter = ["accion"]
    search_fields = ["descripcion"]


@admin.register(PartidaEliminada)
class PartidaEliminadaAdmin(admin.ModelAdmin):
    list_display = ["tipo", "numero", "folio_numero", "fiel_nombre", "motivo", "eliminado_en"]
    list_filter = ["tipo", "eliminado_en"]
    search_fields = ["fiel_nombre", "resumen", "motivo"]
    readonly_fields = [
        "tipo",
        "libro",
        "folio_numero",
        "numero",
        "fecha",
        "fecha_registro",
        "fiel_nombre",
        "parroquia",
        "resumen",
        "motivo",
        "eliminado_por",
        "eliminado_en",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
