from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import RegistroForm
from .models import PerfilUsuario

SIN_REGISTRO = "El registro de usuarios no está habilitado. Pide tu cuenta al administrador."


@login_not_required
def registro(request):
    """Autorregistro público (salvo si ya hay sesión)."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if not settings.CODIGO_REGISTRO:
        return render(
            request,
            "cuentas/registro.html",
            {"habilitado": False, "aviso": SIN_REGISTRO},
        )

    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                usuario = form.save()
                PerfilUsuario.objects.create(usuario=usuario, rol=form.cleaned_data["rol"])
        except IntegrityError:
            form.add_error(None, "No se pudo crear la cuenta. Inténtalo de nuevo.")
        else:
            login(request, usuario)
            nombre = usuario.get_full_name() or usuario.username
            messages.success(request, f"¡Bienvenido, {nombre}!")
            return redirect("dashboard")

    return render(request, "cuentas/registro.html", {"habilitado": True, "form": form})
