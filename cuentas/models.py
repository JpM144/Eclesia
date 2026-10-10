from django.conf import settings
from django.db import models

from core.choices import RolUsuario


class PerfilUsuario(models.Model):
    """Datos extra de cada usuario del sistema.

    El rol es informativo: hoy ambos roles (Secretario(a) y Sacerdote) tienen
    exactamente los mismos permisos. Los usuarios creados desde el admin pueden
    no tener perfil; en ese caso se muestran como "Administrador".
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    rol = models.CharField(max_length=20, choices=RolUsuario.choices, verbose_name="rol")

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"{self.usuario} - {self.get_rol_display()}"
