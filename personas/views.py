import re

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from core.choices import EstadoRegistro, TipoDocumento
from core.validators import normalizar_documento, validar_documento
from core.views import CrudUpdateView

from . import consultas
from .forms import DocumentoMixin, FielForm, MadreForm, PadreForm, PadrinoForm
from .models import Documento, Fiel, Madre, Padre, Padrino

# ---------------------------------------------------------------------------
# Consultar personas (solo lectura)
# ---------------------------------------------------------------------------


def consultar_personas(request):
    """Busca personas por documento o nombre y muestra sus partidas."""
    q = request.GET.get("q", "").strip()
    contexto = {"q": q, "personas": [], "menciones": [], "aviso": "", "hay_mas": False}
    if q and len(q) < 3:
        contexto["aviso"] = "Ingrese al menos 3 caracteres para buscar."
    elif q:
        personas, hay_mas = consultas.buscar_personas(q)
        contexto["personas"] = personas
        contexto["hay_mas"] = hay_mas
        contexto["menciones"] = consultas.buscar_menciones(q)
    return render(request, "personas/consultar.html", contexto)


def ficha_persona_view(request, pk):
    """Ficha de la persona dueña del ``Documento`` con ese identificador."""
    documento = get_object_or_404(Documento, pk=pk)
    ficha = consultas.ficha_persona(documento)
    if ficha is None:
        raise Http404("Ese documento no corresponde a ninguna persona registrada.")
    parroquia_nombre = (settings.NOMBRE_PARROQUIA or "").strip()
    return render(
        request,
        "personas/ficha.html",
        {
            "ficha": ficha,
            "parroquia_nombre": parroquia_nombre or "Sistema de Gestión Parroquial",
            "ahora": timezone.now(),
        },
    )


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
# Un único endpoint para todos los formularios de sacramentos: busca el
# documento entre todos los roles (Fiel, Padre, Madre y Padrino) y devuelve
# solo los datos que el formulario necesita, sin ids internos. Solo acepta
# GET, valida el documento en el servidor y limita las consultas por usuario.


def _persona_por_documento(request, modelo):
    """Endpoints heredados ``api_padre``/``api_madre`` (solo nombre y apellido)."""
    tipo = request.GET.get("tipo", TipoDocumento.CC).strip() or TipoDocumento.CC
    numero = request.GET.get("numero", "").strip()
    if not numero:
        return JsonResponse({"error": "El parámetro 'numero' es obligatorio."}, status=400)
    numero = DocumentoMixin.normalizar_numero(tipo, numero)
    documento = Documento.objects.filter(tipo_documento=tipo, numero_documento=numero).first()
    persona = modelo.objects.filter(documento=documento).first() if documento else None
    if persona is None:
        return JsonResponse({"error": "No se encontró la persona."}, status=404)
    return JsonResponse(
        {
            "tipo_documento": documento.tipo_documento,
            "numero_documento": documento.numero_documento,
            "nombre": persona.nombre,
            "apellido": persona.apellido,
        }
    )


LIMITE_CONSULTAS_API_PERSONA = 60  # por usuario
VENTANA_LIMITE_API_PERSONA = 60  # segundos
MENSAJE_LIMITE_API_PERSONA = "Demasiadas consultas. Espere un minuto y vuelva a intentarlo."
MENSAJE_VARIAS_PERSONAS = "Hay varias personas con ese número; elige el tipo de documento."


def _limite_de_consultas_agotado(usuario):
    """True si el usuario ya agotó su límite; la caché de Django hace de contador."""
    clave = f"api-persona:{usuario.pk}"
    intentos = cache.get(clave, 0)
    if intentos >= LIMITE_CONSULTAS_API_PERSONA:
        return True
    cache.set(clave, intentos + 1, timeout=VENTANA_LIMITE_API_PERSONA)
    return False


def _documento_buscado(request):
    """Documento exacto buscado, o ``varios`` si hay más de una coincidencia.

    Con tipo se valida el número con ``validar_documento``; sin tipo se busca
    solo por número y, si hay exactamente una coincidencia, se completa el
    tipo. Devuelve ``(documento, varios, error)``.
    """
    tipo = (request.GET.get("tipo") or "").strip()
    numero = (request.GET.get("numero") or "").strip()
    if not numero:
        return (
            None,
            False,
            JsonResponse({"error": "El parámetro 'numero' es obligatorio."}, status=400),
        )
    if tipo:
        numero = normalizar_documento(tipo, numero)
        try:
            validar_documento(tipo, numero)
        except ValidationError as error:
            return None, False, JsonResponse({"error": " ".join(error.messages)}, status=400)
        documento = Documento.objects.filter(tipo_documento=tipo, numero_documento=numero).first()
        return documento, False, None
    limpio = re.sub(r"[.\s-]", "", numero)
    candidatos = list(
        Documento.objects.filter(numero_documento__in={limpio, limpio.upper()}).order_by("pk")[:2]
    )
    if len(candidatos) > 1:
        return None, True, None
    return (candidatos[0] if candidatos else None), False, None


def _personas_del_documento(documento):
    """Fila de cada rol que usa ese ``Documento`` (cualquier combinación)."""
    return (
        Fiel.objects.filter(documento=documento).first(),
        Padre.objects.filter(documento=documento).first(),
        Madre.objects.filter(documento=documento).first(),
        Padrino.objects.filter(documento=documento).first(),
    )


def _nombre_y_apellido(fiel, padre, madre, padrino):
    """Mejor par nombre/apellidos disponible (prioridad Fiel > Padre > Madre > Padrino)."""
    if fiel:
        return fiel.nombres, fiel.apellidos
    if padre:
        return padre.nombre, padre.apellido
    if madre:
        return madre.nombre, madre.apellido
    if padrino:
        return padrino.nombre, ""
    return "", ""


def _editar_url(rol, fiel, padre, madre, padrino):
    """URL de edición del rol pedido o de la persona más completa disponible."""
    preferido = {
        "fiel": ("personas:fiel_editar", fiel),
        "padre": ("personas:padre_editar", padre),
        "madre": ("personas:madre_editar", madre),
        "padrino": ("personas:padrino_editar", padrino),
        "madrina": ("personas:padrino_editar", padrino),
    }[rol]
    if preferido[1] is not None:
        return reverse(preferido[0], args=[preferido[1].pk])
    for ruta, persona in (
        ("personas:fiel_editar", fiel),
        ("personas:padre_editar", padre),
        ("personas:madre_editar", madre),
        ("personas:padrino_editar", padrino),
    ):
        if persona is not None:
            return reverse(ruta, args=[persona.pk])
    return ""


def _datos_bautismo(fiel):
    """Datos del bautismo activo o corregido del fiel, o ``None`` si no consta.

    Devuelve el pk (para enlazar la partida), la referencia «Libro · Folio ·
    N.°», la parroquia, la fecha (ISO) y los padres de la partida de bautismo,
    que los formularios de los demás sacramentos muestran como dato
    informativo sin volverlos a pedir.
    """
    if fiel is None:
        return None
    from sacramentos.models import Bautismo

    bautismo = (
        Bautismo.objects.filter(
            sacramento__fiel=fiel,
            sacramento__estado__in=[EstadoRegistro.ACTIVO, EstadoRegistro.CORREGIDO],
        )
        .select_related("sacramento__folio__libro")
        .first()
    )
    if bautismo is None:
        return None
    sacramento = bautismo.sacramento
    libro = sacramento.folio.libro
    return {
        "id": bautismo.pk,
        "referencia": (
            f"Libro {libro.numero_libro or libro.nombre} · "
            f"Folio {sacramento.folio.numero_folio} · N.° {sacramento.numero}"
        ),
        "parroquia": str(libro.parroquia),
        "fecha": sacramento.fecha.isoformat() if sacramento.fecha else "",
        "padre": str(bautismo.padre) if bautismo.padre else "",
        "madre": str(bautismo.madre) if bautismo.madre else "",
    }


def api_padre(request):
    return _persona_por_documento(request, Padre)


def api_madre(request):
    return _persona_por_documento(request, Madre)


def api_persona(request):
    """Autocompletar los datos de una persona por documento (cualquier rol).

    ``rol`` es uno de ``fiel``, ``padre``, ``madre``, ``padrino`` o ``madrina``
    (``madrina`` usa la entidad ``Padrino``). Solo acepta GET, limita las
    consultas por usuario y busca el documento entre todos los roles: si otra
    persona con ese documento ya tiene nombre y apellidos se usan esos datos.
    Sin tipo de documento se busca solo por número; si hay varias personas con
    ese número se pide elegir el tipo. Si el fiel ya tiene bautismo activo o
    corregido, lo devuelve con su referencia (libro, folio y número), su pk y su
    URL para enlazar la partida, y los padres de la partida de bautismo.
    """
    if request.method != "GET":
        return JsonResponse(
            {"error": "Este endpoint solo acepta GET."},
            status=405,
            headers={"Allow": "GET"},
        )
    roles = {"fiel", "padre", "madre", "padrino", "madrina"}
    rol = request.GET.get("rol", "").strip()
    if rol not in roles:
        return JsonResponse(
            {"error": "El parámetro 'rol' debe ser fiel, padre, madre, padrino o madrina."},
            status=400,
        )
    if _limite_de_consultas_agotado(request.user):
        return JsonResponse({"error": MENSAJE_LIMITE_API_PERSONA}, status=429)

    documento, varios, error = _documento_buscado(request)
    if error is not None:
        return error
    if varios:
        return JsonResponse(
            {"encontrado": False, "varios": True, "mensaje": MENSAJE_VARIAS_PERSONAS}
        )
    if documento is None:
        return JsonResponse({"error": "No se encontró la persona."}, status=404)

    fiel, padre, madre, padrino = _personas_del_documento(documento)
    if fiel is None and padre is None and madre is None and padrino is None:
        return JsonResponse({"error": "No se encontró la persona."}, status=404)

    nombres, apellidos = _nombre_y_apellido(fiel, padre, madre, padrino)
    respuesta = {
        "encontrado": True,
        "tipo_documento": documento.tipo_documento,
        "numero_documento": documento.numero_documento,
        "nombres": nombres,
        "apellidos": apellidos,
        "sexo_fiel": (fiel.sexo or "") if fiel else "",
        "editar_url": _editar_url(rol, fiel, padre, madre, padrino),
    }
    if rol == "fiel":
        datos_bautismo = _datos_bautismo(fiel)
        respuesta.update(
            {
                "fecha_nacimiento": (
                    fiel.fecha_nacimiento.isoformat() if fiel and fiel.fecha_nacimiento else ""
                ),
                "municipio": (fiel.municipio_nacimiento_id or "") if fiel else "",
                "sexo": (fiel.sexo or "") if fiel else "",
                "telefono": (fiel.telefono or "") if fiel else "",
                "bautismo_activo": datos_bautismo is not None,
                "bautismo_referencia": (datos_bautismo["referencia"] if datos_bautismo else ""),
            }
        )
        # Los datos extra del bautismo solo se envían cuando hay bautismo
        # enlazado: así un fiel sin bautismo responde exactamente con los
        # campos de siempre.
        if datos_bautismo:
            respuesta.update(
                {
                    "bautismo_id": datos_bautismo["id"],
                    "bautismo_url": reverse(
                        "sacramentos:bautismo_detalle", args=[datos_bautismo["id"]]
                    ),
                    "bautismo_parroquia": datos_bautismo["parroquia"],
                    "bautismo_fecha": datos_bautismo["fecha"],
                    "bautismo_padre": datos_bautismo["padre"],
                    "bautismo_madre": datos_bautismo["madre"],
                }
            )
    return JsonResponse(respuesta)
