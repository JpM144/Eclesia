# Sistema de Gestión Parroquial

Esqueleto del proyecto Django 5.2 + PostgreSQL para la gestión de partidas y actividades parroquiales.

## Requisitos

- Python 3.13+
- PostgreSQL 17 (servicio corriendo en localhost:5432)

## Crear la base de datos

```powershell
$env:PGPASSWORD = "<tu contraseña>"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE DATABASE partidas_parroquias;"
```

## Configurar el entorno

```powershell
Copy-Item .env.example .env   # y completar los valores reales
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Migraciones

```powershell
.\.venv\Scripts\python manage.py migrate
```

## Levantar el servidor

```powershell
.\.venv\Scripts\python manage.py runserver
```

## Convención visual

La interfaz usa **AdminLTE 3.2.0** con Bootstrap 4, Font Awesome 5 y jQuery, cargados por CDN.

### Plantilla base

Todas las páginas deben extender `templates/base.html`:

```html
{% extends "base.html" %}

{% block title %}Título de la pestaña{% endblock %}
{% block heading %}Encabezado de la página{% endblock %}

{% block content %}
  ...
{% endblock %}
```

Bloques disponibles en `base.html`:

| Bloque      | Para qué sirve                                        |
| ----------- | ----------------------------------------------------- |
| `title`     | Contenido de la etiqueta `<title>`                    |
| `heading`   | Título visible en la cabecera del content-wrapper     |
| `content`   | Cuerpo de la página (obligatorio)                     |
| `extra_css` | CSS adicional, se inserta después de AdminLTE         |
| `extra_js`  | JavaScript adicional, se inserta al final del `body`  |

`base.html` ya incluye la barra superior (nombre completo y rol del usuario, más el botón
**Cerrar sesión**), el sidebar con Inicio, Bautismos, Confirmaciones, Matrimonios, la sección **Catálogos**,
el desplegable **Parroquias** con Parroquias, Iglesias, Ministros y Libros, y el ítem **Consultar personas**,
y el pie de página. El ítem del sidebar queda activo automáticamente comparando
`request.resolver_match.url_name` con el nombre de la ruta:

```html
<a href="{% url 'dashboard' %}" class="nav-link{% if actual == 'dashboard' %} active{% endif %}">
```

Cuando se agregue una ruta nueva se reemplaza `href="#"` por su `{% url %}` y se usa el
mismo patrón con el nombre de esa ruta. Las rutas aún inexistentes llevan el comentario
`{# TODO: ruta pendiente #}`. Los ítems del sidebar que tienen CRUD (Países,
Departamentos y Municipios) guardan la URL en una variable y se marcan activos cuando el
`request.path` empieza por ella, de modo que también quedan resaltados al crear o editar:

```html
{% url 'ubicacion:pais_lista' as url_paises %}
<a href="{{ url_paises }}" class="nav-link{% if url_paises in request.path %} active{% endif %}">
```

### Ítems desplegables (treeview)

El sidebar vive en `templates/includes/sidebar.html` (incluido desde `base.html`) y admite
desplegables de AdminLTE 3. La `<ul>` principal lleva `data-widget="treeview"`, `role="menu"`
y `data-accordion="false"`. Un desplegable se arma así:

```html
<li class="nav-item{% if ns == 'mi_app' %} menu-open active{% endif %}">
  <a href="#" class="nav-link{% if ns == 'mi_app' %} active{% endif %}">
    <i class="nav-icon fas fa-church"></i>
    <p>Mi sección<i class="right fas fa-angle-left"></i></p>
  </a>
  <ul class="nav nav-treeview">
    <li class="nav-item">
      {% url 'mi_app:entidad_lista' as url_entidad %}
      <a href="{{ url_entidad }}" class="nav-link{% if 'entidad_' in actual %} active{% endif %}">
        <i class="far fa-circle nav-icon"></i>
        <p>Entidad</p>
      </a>
    </li>
  </ul>
</li>
```

Reglas:

- El ítem padre abre y se resalta cuando su namespace es el actual (`ns`, tomado de
  `request.resolver_match.namespace`): `menu-open active` en el `<li>` y `active` en el `<a>`.
- El subenlace activo se decide con `request.resolver_match.url_name` (la variable `actual`)
  comparando el prefijo del nombre de la ruta (p. ej. `'entidad_' in actual`). **No** se usa
  `in request.path` dentro del árbol: la URL corta de la lista (p. ej. `/parroquias/`) es
  prefijo de las demás y marcaría varios subenlaces a la vez.
- El desplegable "Parroquias" agrupa solo el namespace `parroquias` (Parroquias, Iglesias,
  Ministros y Libros), por lo que su condición es `ns == 'parroquias'`. Los folios de un
  libro activan "Libros" (`'folio_' in actual`).
- "Consultar personas" es un ítem propio del sidebar, fuera del desplegable, que enlaza
  `/personas/consultar/` y se marca activo en cualquier página del namespace `personas`
  (`ns == 'personas'`), incluidas las vistas de edición de personas.
- En cualquier otra página (Inicio, Países, Bautismos…) los controles arrancan cerrados.

### Mensajes

Los mensajes de `django.messages` se muestran automáticamente como alertas de Bootstrap
dentro del content-wrapper. `MESSAGE_TAGS` en `settings.py` mapea los niveles a las
clases de Bootstrap: `success`, `info`, `warning`, `danger` (errores) y `secondary` (debug).

### Login obligatorio

`django.contrib.auth.middleware.LoginRequiredMiddleware` está activo: **todas las vistas
exigen sesión salvo las marcadas con `login_not_required`**, y en la práctica las únicas
vistas públicas son `/login/` y `/cuentas/registro/`. Las vistas nuevas no necesitan ningún
decorado adicional.

- `LOGIN_URL = "/login/"` (plantilla `templates/registration/login.html`)
- `LOGIN_REDIRECT_URL = "/"` y `LOGOUT_REDIRECT_URL = "/login/"`
- **Cerrar sesión es solo por POST** (`LogoutView` no acepta GET).

### Estaticos

Los archivos estáticos propios van en `static/` (configurado con `STATICFILES_DIRS`);
los de terceros se cargan por CDN.

## Patrón CRUD

Todo el CRUD del proyecto se construye con cuatro vistas genéricas definidas en
`core/views.py` y tres plantillas genéricas en `core/templates/crud/`. Para una entidad
nueva solo hay que crear el `ModelForm`, cuatro vistas y las rutas.

### Clases base

| Clase              | Hereda de              | Atributos que recibe |
| ------------------ | ---------------------- | -------------------- |
| `CrudListView`     | `ListView`             | `nombre_singular`, `nombre_plural`, `search_fields`, `columnas`, `select_related`, `url_lista`, `url_crear`, `url_editar`, `url_eliminar` |
| `CrudCreateView`   | `CreateView`           | `nombre_singular`, `nombre_plural`, `url_lista` (más `model`/`form_class`) |
| `CrudUpdateView`   | `UpdateView`           | `nombre_singular`, `nombre_plural`, `url_lista` (más `model`/`form_class`) |
| `CrudDeleteView`   | `DeleteView`           | `nombre_singular`, `nombre_plural`, `url_lista` (`mensaje_protegido` opcional) |

Atributos comunes (definidos en `CrudBaseMixin`):

- `nombre_singular` / `nombre_plural`: nombre de la entidad, usado en títulos y botones.
- `search_fields`: campos para el buscador; el parámetro GET es `q` y usa `icontains`.
- `columnas`: columnas de la lista, `[{"campo": "nombre", "etiqueta": "Nombre"}]`.
  El campo admite rutas con doble guion bajo (`"departamento__pais__nombre"`).
- `select_related`: tupla de relaciones a precargar (evita consultas de más).
- `url_lista`: **nombre de la ruta** de la lista, es la URL de retorno.
- `url_crear` / `url_editar` / `url_eliminar`: nombres de las demás rutas (solo se usan
  en `CrudListView`).

Comportamiento automático: paginación de 20, mensajes de éxito
(`"Registro creado/actualizado/eliminado correctamente"`) y, en el borrado, captura de
`ProtectedError` → mensaje `"No se puede eliminar porque tiene registros asociados"` y
vuelta a la lista (nunca un error 500).

### Ejemplo mínimo

```python
# forms.py
from core.forms import FormularioBase


class PaisForm(FormularioBase):
    class Meta:
        model = Pais
        fields = ["nombre"]


# views.py
from core.views import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView


class PaisListView(CrudListView):
    model = Pais
    nombre_singular = "país"
    nombre_plural = "países"
    search_fields = ["nombre"]
    columnas = [{"campo": "nombre", "etiqueta": "Nombre"}]
    url_lista = "ubicacion:pais_lista"
    url_crear = "ubicacion:pais_crear"
    url_editar = "ubicacion:pais_editar"
    url_eliminar = "ubicacion:pais_eliminar"


class PaisCreateView(CrudCreateView):
    model = Pais
    form_class = PaisForm
    nombre_singular = "país"
    nombre_plural = "países"
    url_lista = "ubicacion:pais_lista"


# urls.py
(path("paises/", views.PaisListView.as_view(), name="pais_lista"),)
(path("paises/nuevo/", views.PaisCreateView.as_view(), name="pais_crear"),)
(path("paises/<int:pk>/editar/", views.PaisUpdateView.as_view(), name="pais_editar"),)
(path("paises/<int:pk>/eliminar/", views.PaisDeleteView.as_view(), name="pais_eliminar"),)
```

`FormularioBase` (en `core/forms.py`) es un `ModelForm` que añade `form-control` a todos
los widgets; basta con heredar de él y declarar el `Meta`.

### Plantillas genéricas

- `crud/lista.html`: buscador, tabla con las `columnas` y acciones Editar/Eliminar,
  botón "Nuevo" y paginación.
- `crud/formulario.html`: etiquetas, errores generales y por campo, botones Guardar y
  Cancelar. Expone el bloque `aviso` (vacío por defecto) sobre el formulario y deja el bloque
  `extra_js` reservado.
- `crud/confirmar_eliminar.html`: muestra `{{ object }}` y pide confirmación.

Para añadir JavaScript a un formulario concreto se crea una plantilla propia que extiende
la genérica:

```html
{% extends "crud/formulario.html" %}
{% load static %}
{% block extra_js %}<script src="{% static 'js/ubicacion.js' %}"></script>{% endblock %}
```

### Selects encadenados (`static/js/ubicacion.js`)

Encadena país → departamento → municipio (este último opcional) usando los endpoints
`/ubicacion/api/departamentos/?pais=<id>` y `/ubicacion/api/municipios/?departamento=<id>`
(devuelven `[{"id": ..., "nombre": ...}]` ordenado por nombre; sin parámetro o con un
valor no entero responden 400). Se marca cada select con un atributo `data-`:

```html
<select data-cascada-pais>...</select>
<select data-cascada-departamento data-url="/ubicacion/api/departamentos/">...</select>
<select data-cascada-municipio data-url="/ubicacion/api/municipios/">...</select>
```

Los selects deben estar dentro del mismo `<form>` (o de un contenedor con
`data-cascada-contenedor`). Al cambiar el país se recargan los departamentos y, al cambiar
el departamento, los municipios. Al cargar la página se conserva el valor ya seleccionado,
lo que permite precargar los valores al editar.

### Ejemplo con selects encadenados

El formulario de municipio lo usa: el campo `departamento` cuelga del select auxiliar
**País** (`pais`), que no se guarda. Al editar, `MunicipioForm` precarga el país a partir
del departamento del municipio (`ubicacion/forms.py`). El helper `widget_cascada` que
marca los `select` vive en `core/forms.py` y se reutiliza desde `parroquias/forms.py`
(parroquia: país → departamento → municipio).

### CRUD anidado

Las plantillas genéricas exponen tres bloques en la lista para reutilizarlas cuando una
entidad cuelga de otra:

- `boton_crear`: botón "Nuevo" del encabezado.
- `acciones_extra`: botones adicionales por fila (antes de Editar/Eliminar).
- `acciones_fila`: botones Editar/Eliminar de cada fila.

Con ellos, un CRUD anidado solo declara una plantilla que extiende `crud/lista.html` y
reescribe los bloques con las rutas que llevan el `pk` del padre (p. ej. los folios de un
libro en `parroquias/templates/parroquias/folio_lista.html`). Para las relaciones que
reciben parámetros extra, `url_lista` en el contexto ya es la **URL resuelta** (no el
nombre de la ruta), de modo que el enlace "Cancelar" de los formularios y la confirmación
de borrado funcionan igual. En la vista, una mezcla sobre `CrudBaseMixin` carga el padre
en `dispatch` (404 si no existe) y sobreescribe `get_url_lista` para construir la ruta
anidada (`parroquias/views.py`, `FolioBaseMixin`).

## Parroquias, Iglesias y Libros

### Iglesias

Las iglesias y capillas de cada parroquia se administran con el CRUD de **Iglesias**
(ítem del desplegable Parroquias, después de Parroquias). La lista muestra nombre,
parroquia y dirección y filtra por parroquia con el parámetro GET `parroquia`; el
filtro se conserva al paginar. El formulario valida la unicidad de nombre dentro de
la misma parroquia con un mensaje claro en español. Una iglesia con sacramentos no se
puede eliminar (ver *Borrado protegido*).

### Apertura y cierre de libros

El formulario de **Libro** (nuevo y editar) recoge los datos de la *diligencia de
apertura*: parroquia, tipo de libro, nombre, número, fecha de apertura, total de
folios, ministro que abre (los de la parroquia del libro; en la creación, si aún no
hay parroquia elegida, se ofrecen todos ordenados por parroquia), detalle y
observaciones. Los campos de cierre **no** están en este formulario.

El cierre es una acción aparte: **Cerrar libro** en
`/parroquias/libros/<pk>/cerrar/` (solo aparece en libros abiertos). Pide la fecha de
cierre, el ministro que firma y la nota de cierre, avisa de que después no se podrán
registrar partidas nuevas y guarda la diligencia con `parroquias/services.cerrar_libro`
(sus errores se muestran en el formulario, nunca como un 500). Un libro cerrado se
muestra en **solo lectura** al editar, con un aviso, y no acepta cambios.

### Lista de libros

La lista muestra nombre, número, tipo, parroquia, estado (badge verde “Abierto” y
gris “Cerrado”), fecha de apertura y número de partidas. Filtra por parroquia, tipo y
estado, combinables entre sí y conservados al paginar; usa `select_related` y
`annotate(Count("sacramentos"))` para no generar consultas N+1. Por fila ofrece
editar, ver índice, cerrar (si el libro está abierto) y eliminar.

### Índice del libro

`/parroquias/libros/<pk>/indice/` muestra el encabezado con los datos del libro y su
diligencia de apertura (y de cierre si existe), seguido de la tabla
`parroquias.services.indice_libro`: apellidos, nombres, número, folio, fecha y tipo,
ordenados alfabéticamente por apellidos. La página estiliza la impresión con
`@media print` (oculta menú y botones) y tiene un botón **Imprimir**.

### Unicidad de libros

Los errores de unicidad se muestran como errores de formulario en español: nombre
repetido en la misma parroquia, mismo tipo+número en la misma parroquia y un solo
libro abierto por tipo (**“Ya hay un libro de Bautismos abierto en esta parroquia.
Ciérralo antes de abrir otro”**). Se validan en `clean()` de los formularios para
evitar los mensajes genéricos de las restricciones de la base de datos.

### Borrado protegido

`CrudDeleteView` captura `django.db.models.ProtectedError` cuando el registro tiene
dependencias protegidas (`on_delete=PROTECT`): en lugar de un error 500 vuelve a la
lista con el mensaje **“No se puede eliminar porque tiene registros asociados”**
(`mensaje_protegido`, personalizable). Aplica a Iglesias con sacramentos, Libros con
folios o partidas y Parroquias con libros, iglesias o sacramentos. Los ministros usan
`on_delete=SET_NULL` en `Parroquia` (se desligan de la parroquia), así que no bloquean
el borrado.

## Personas

Padres, madres, padrinos y fieles no se administran desde el menú: se crean dentro de cada
partida. Desde el sidebar solo se accede a **Consultar personas** y, desde ahí, a la edición
individual de una persona.

- **Consultar personas** (`/personas/consultar/`, ruta `personas:consultar`): busca por
  documento o por nombre con el parámetro GET `q`. Si `q` son solo dígitos (se permiten
  puntos y espacios), busca por número de documento (coincidencia exacta primero y, si no
  hay, por contenido); si no, cada palabra de `q` debe aparecer en nombres o apellidos
  (`icontains`). Con menos de 3 caracteres no busca y muestra un aviso. Busca en `Fiel`,
  `Padre`, `Madre`, `Padrino`, `TestigoMatrimonio` y `PadrinoMatrimonio`; por cada persona
  muestra su nombre, documento, tipo y las partidas en que aparece (rol, sacramento, fecha,
  libro, folio y número). Limita el resultado a 50 personas (con aviso si hay más) y carga las
  partidas por lote (`select_related`), sin consultas N+1.
- **Editar persona** (`personas:padre_editar`, `personas:madre_editar`,
  `personas:padrino_editar`, `personas:fiel_editar`): corrige la ficha de una persona creada
  desde una partida. Arriba del formulario avisa en cuántas partidas se verá el cambio y, al
  guardar, vuelve al `next` indicado (solo si es un destino seguro según
  `url_has_allowed_host_and_scheme`) o a "Consultar personas". No hay creación ni eliminación
  y, si el documento o la cédula ya pertenecen a otra persona, el error se muestra en el campo
  (nunca un error 500).

Los testigos y padrinos propios de un matrimonio (`TestigoMatrimonio` y
`PadrinoMatrimonio`) aparecen en la consulta con sus partidas, pero se corrigen desde la
partida de matrimonio: no tienen botón "Editar". `Contrayente` no se lista por separado porque
no guarda documento ni nombre propios: usa el `Fiel` asociado, que aparece con el rol
"contrayente".

## Cuentas y registro

Cada usuario del sistema tiene un `PerfilUsuario` (app `cuentas`) con su **rol**
(`core.choices.RolUsuario`): `Secretario(a)` o `Sacerdote`. El rol es **informativo**:
hoy los dos tienen exactamente los mismos permisos. El perfil se edita como inline dentro
del usuario en el admin. Los usuarios que no tienen perfil (p. ej. el `admin`) se muestran
como **Administrador** en la barra superior; el código tolera su ausencia.

### Autorregistro

En `/cuentas/registro/` (ruta `cuentas:registro`, pública gracias a `login_not_required`)
una persona crea su propia cuenta. Pide nombres, apellidos, usuario, correo (obligatorio y
único sin distinguir mayúsculas), rol, contraseña y confirmación (con los validadores de
Django, ya que el formulario parte de `UserCreationForm`) y el **código de la parroquia**
(campo de contraseña, no visible). Al registrarse, el `User` (sin `is_staff` ni
`is_superuser`) y su `PerfilUsuario` se crean en una sola transacción, se inicia sesión y se
vuelve al dashboard con un mensaje de bienvenida. Si ya hay sesión, se redirige al dashboard;
y el login incluye un enlace **Crear cuenta**. Ningún error del usuario provoca un 500 (los
duplicados y el código incorrecto se muestran como error del campo).

### Código de registro (`CODIGO_REGISTRO`)

El registro solo funciona con el código que la parroquia guarda en la variable de entorno
`CODIGO_REGISTRO` (se lee con `python-decouple` desde `.env`, que no se versiona; el valor
de ejemplo está en `.env.example` con un comentario). Se compara con
`secrets.compare_digest`, así que se distingue mayúsculas y no filtra el código.

- **Para habilitar el registro**: escribe el código en `.env` (`CODIGO_REGISTRO=mi-codigo`)
  y reinicia el servidor.
- **Para cambiarlo**: edita esa línea en `.env` y reinicia; el código anterior deja de valer.
- **Con `CODIGO_REGISTRO=` vacío** el registro queda deshabilitado: la página muestra
  *"El registro de usuarios no está habilitado. Pide tu cuenta al administrador."* sin
  formulario, y un `POST` tampoco crea nada. Solo el administrador crea usuarios desde el
  admin.

En los tests, el valor se fija con `override_settings(CODIGO_REGISTRO=...)`.

## Calidad de código

```powershell
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format .
.\.venv\Scripts\python manage.py test
```
