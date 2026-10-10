from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.choices import RolUsuario

from .models import PerfilUsuario

CODIGO = "codigo-de-prueba"
CLAVE = "ClaveSegura123*"


def datos(**kwargs):
    base = {
        "nombres": "María",
        "apellidos": "Pérez",
        "username": "maria",
        "correo": "maria@example.com",
        "rol": RolUsuario.SECRETARIO,
        "password1": CLAVE,
        "password2": CLAVE,
        "codigo": CODIGO,
    }
    base.update(kwargs)
    return base


@override_settings(CODIGO_REGISTRO=CODIGO)
class RegistroTests(TestCase):
    def test_registro_correcto_con_cada_rol(self):
        for rol in RolUsuario.values:
            with self.subTest(rol=rol):
                self.client.logout()
                respuesta = self.client.post(
                    reverse("cuentas:registro"),
                    datos(username=f"user_{rol}", correo=f"{rol}@example.com", rol=rol),
                )
                self.assertRedirects(respuesta, reverse("dashboard"))
                usuario = User.objects.get(username=f"user_{rol}")
                self.assertEqual(usuario.first_name, "María")
                self.assertEqual(usuario.last_name, "Pérez")
                self.assertEqual(usuario.email, f"{rol}@example.com")
                self.assertFalse(usuario.is_staff)
                self.assertFalse(usuario.is_superuser)
                self.assertEqual(usuario.perfil.rol, rol)
                self.assertIn("_auth_user_id", self.client.session)

    def test_codigo_incorrecto_muestra_error_y_no_crea_usuario(self):
        respuesta = self.client.post(reverse("cuentas:registro"), datos(codigo="otro"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("codigo", respuesta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="maria").exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_repetido_muestra_error_en_el_campo(self):
        User.objects.create_user(username="maria", password=CLAVE)
        respuesta = self.client.post(reverse("cuentas:registro"), datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("username", respuesta.context["form"].errors)

    def test_correo_repetido_sin_importar_mayusculas(self):
        User.objects.create_user(username="otra", password=CLAVE, email="MARIA@example.com")
        respuesta = self.client.post(reverse("cuentas:registro"), datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("correo", respuesta.context["form"].errors)

    def test_contrasenas_distintas_muestra_error(self):
        respuesta = self.client.post(reverse("cuentas:registro"), datos(password2="OtraClave123*"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password2", respuesta.context["form"].errors)

    def test_contrasena_debil_muestra_error(self):
        respuesta = self.client.post(
            reverse("cuentas:registro"), datos(password1="12345678", password2="12345678")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password2", respuesta.context["form"].errors)

    def test_registro_es_publico_sin_sesion(self):
        respuesta = self.client.get(reverse("cuentas:registro"))
        self.assertEqual(respuesta.status_code, 200)

    def test_usuario_con_sesion_es_redirigido_al_dashboard(self):
        usuario = User.objects.create_user(username="logueado", password=CLAVE)
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("cuentas:registro"))
        self.assertRedirects(respuesta, reverse("dashboard"))

    def test_login_muestra_enlace_crear_cuenta(self):
        respuesta = self.client.get(reverse("login"))
        self.assertContains(respuesta, "Crear cuenta")
        self.assertContains(respuesta, reverse("cuentas:registro"))

    def test_barra_muestra_el_rol_del_usuario(self):
        usuario = User.objects.create_user(username="maria", password=CLAVE)
        usuario.first_name = "María"
        usuario.last_name = "Pérez"
        usuario.save()
        PerfilUsuario.objects.create(usuario=usuario, rol=RolUsuario.SECRETARIO)
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "María Pérez · Secretario(a)")

    def test_barra_muestra_administrador_para_usuario_sin_perfil(self):
        usuario = User.objects.create_user(username="sinperfil", password=CLAVE)
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, "Administrador")


class RegistroDeshabilitadoTests(TestCase):
    @override_settings(CODIGO_REGISTRO="")
    def test_sin_codigo_muestra_aviso_y_no_hay_formulario(self):
        respuesta = self.client.get(reverse("cuentas:registro"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El registro de usuarios no está habilitado")
        self.assertNotContains(respuesta, "<form")
        self.assertNotIn("form", respuesta.context)

    @override_settings(CODIGO_REGISTRO="")
    def test_sin_codigo_un_post_no_crea_nada(self):
        respuesta = self.client.post(reverse("cuentas:registro"), datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(PerfilUsuario.objects.count(), 0)
