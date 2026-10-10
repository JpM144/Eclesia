from django.contrib import admin

from .models import Departamento, Municipio, Pais


@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ["nombre"]
    search_fields = ["nombre"]


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "pais"]
    list_filter = ["pais"]
    search_fields = ["nombre"]


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "departamento"]
    list_filter = ["departamento__pais"]
    search_fields = ["nombre"]
