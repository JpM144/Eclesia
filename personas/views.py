from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.views import CrudUpdateView

from . import consultas
from .forms import FielForm, MadreForm, PadreForm, PadrinoForm
from .models import Fiel, Madre, Padre, Padrino

# ---------------------------------------------------------------------------
# Consultar personas (solo lectura)
# ---------------------------------------------------------------------------


def consultar_personas(request):
    """Busca personas por documento o nombre y muestra sus partidas."""
    q = request.GET.get("q", "").strip()
    contexto = {"q": q, "personas": [], "aviso": "", "hay_mas": False}
    if q and len(q) < 3:
        contexto["aviso"] = "Ingrese al menos 3 caracteres para buscar."
    elif q:
        personas, hay_mas = consultas.buscar_personas(q)
        contexto["personas"] = personas
        contexto["hay_mas"] = hay_mas
    return render(request, "personas/consultar.html", contexto)


# ---------------------------------------------------------------------------
# Editar persona
# ---------------------------------------------------------------------------
# Cada persona se crea desde la partida correspondiente; aquí solo se corrige
# su ficha. No hay listas, creación ni eliminación.


class PersonaUpdateMixin:
    """Edición individual: aviso de partidas y retorno seguro."""

    tipo_persona = ""
    mensaje_exito = "Persona actualizada correctamente"

    def get_url_lista(self):
        destino = self.request.GET.get("next", "")
        if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={self.request.get_host()}
        ):
            return destino
        return reverse("personas:consultar")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_partidas"] = consultas.contar_partidas(self.tipo_persona, self.object.pk)
        return contexto


class PadreUpdateView(PersonaUpdateMixin, CrudUpdateView):
    model = Padre
    form_class = PadreForm
    nombre_singular = "padre"
    nombre_plural = "padres"
    tipo_persona = consultas.PADRE
    template_name = "personas/formulario_persona.html"


class MadreUpdateView(PersonaUpdateMixin, CrudUpdateView):
    model = Madre
    form_class = MadreForm
    nombre_singular = "madre"
    nombre_plural = "madres"
    tipo_persona = consultas.MADRE
    template_name = "personas/formulario_persona.html"


class PadrinoUpdateView(PersonaUpdateMixin, CrudUpdateView):
    model = Padrino
    form_class = PadrinoForm
    nombre_singular = "padrino"
    nombre_plural = "padrinos"
    tipo_persona = consultas.PADRINO
    template_name = "personas/formulario_persona.html"


class FielUpdateView(PersonaUpdateMixin, CrudUpdateView):
    model = Fiel
    form_class = FielForm
    nombre_singular = "fiel"
    nombre_plural = "fieles"
    tipo_persona = consultas.FIEL
    template_name = "personas/formulario_persona.html"


# ---------------------------------------------------------------------------
# API para autocompletar
# ---------------------------------------------------------------------------


def _persona_por_cedula(request, modelo):
    cedula = request.GET.get("cedula", "").strip()
    if not cedula:
        return JsonResponse({"error": "El parámetro 'cedula' es obligatorio."}, status=400)
    persona = modelo.objects.filter(cedula=cedula).first()
    if persona is None:
        return JsonResponse({"error": "No se encontró la persona."}, status=404)
    return JsonResponse(
        {"cedula": persona.cedula, "nombre": persona.nombre, "apellido": persona.apellido}
    )


def api_padre(request):
    return _persona_por_cedula(request, Padre)


def api_madre(request):
    return _persona_por_cedula(request, Madre)
