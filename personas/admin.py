from django.contrib import admin

from .models import Documento, Fiel, Madre, Padre, Padrino


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ["tipo_documento", "numero_documento"]
    list_filter = ["tipo_documento"]
    search_fields = ["numero_documento"]


@admin.register(Fiel)
class FielAdmin(admin.ModelAdmin):
    list_display = ["nombres", "apellidos", "documento", "sexo", "fecha_nacimiento", "telefono"]
    search_fields = ["nombres", "apellidos", "documento__numero_documento"]
    list_filter = ["documento__tipo_documento", "sexo"]


@admin.register(Padre)
class PadreAdmin(admin.ModelAdmin):
    list_display = ["cedula", "nombre", "apellido"]
    search_fields = ["cedula", "nombre", "apellido"]


@admin.register(Madre)
class MadreAdmin(admin.ModelAdmin):
    list_display = ["cedula", "nombre", "apellido"]
    search_fields = ["cedula", "nombre", "apellido"]


@admin.register(Padrino)
class PadrinoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "documento"]
    search_fields = ["nombre"]
