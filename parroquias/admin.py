from django.contrib import admin

from .models import Folio, Libro, Ministro, Parroquia


@admin.register(Parroquia)
class ParroquiaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "municipio", "direccion", "telefono", "email", "parroco"]
    search_fields = ["nombre", "direccion"]
    list_filter = ["municipio__departamento__pais"]


@admin.register(Ministro)
class MinistroAdmin(admin.ModelAdmin):
    list_display = ["documento", "nombre", "apellido", "cargo", "parroquia", "telefono", "email"]
    search_fields = ["documento__numero_documento", "nombre", "apellido"]
    list_filter = ["cargo"]


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ["nombre", "numero_libro", "parroquia", "fecha_apertura", "estado"]
    search_fields = ["nombre"]
    list_filter = ["parroquia", "estado"]


@admin.register(Folio)
class FolioAdmin(admin.ModelAdmin):
    list_display = ["libro", "numero_folio", "fecha_creacion"]
    search_fields = ["libro__nombre"]
    list_filter = ["libro"]
