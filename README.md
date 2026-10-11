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

`base.html` incluye la barra superior (botón hamburguesa con el título de la página, la
campana de anotaciones y el menú de usuario con avatar, nombre y cierre de sesión), el
sidebar con **Inicio**, los cuatro sacramentos (Bautismos, Primera Comunión, Confirmaciones
y Matrimonios, aún sin pantalla), el desplegable **Parroquias** (Parroquias, Ministros y
Libros), el desplegable **Ubicación** (Países, Departamentos y Municipios), el ítem
**Consultar personas** y el pie de página. El ítem del sidebar queda activo automáticamente
comparando `request.resolver_match.url_name` con el nombre de la ruta:

```html
<a href="{% url 'dashboard' %}" class="nav-link{% if actual == 'dashboard' %} active{% endif %}">
```

Cuando se agregue una ruta nueva se usa el mismo patrón con el nombre de esa ruta. Los
cuatro sacramentos no tienen pantalla todavía: aparecen atenuados (clase `deshabilitado`,
`aria-disabled="true"`, sin `href`), con la etiqueta **Pronto** y con los mismos íconos SVG
del dashboard; llevan el comentario `{# TODO: enlazar cuando exista la pantalla #}`.

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
- El desplegable "Parroquias" agrupa solo el namespace `parroquias` (Parroquias,
  Ministros y Libros), por lo que su condición es `ns == 'parroquias'`. Los folios de un
  libro activan "Libros" (`'folio_' in actual`).
- El desplegable "Ubicación" agrupa el namespace `ubicacion` (Países, Departamentos y
  Municipios) y marca sus subenlaces por prefijo del nombre de la ruta:
  `'pais_' in actual`, `'departamento_' in actual` y `'municipio_' in actual`.
- "Consultar personas" es un ítem propio del sidebar, fuera del desplegable, que enlaza
  `/personas/consultar/` y se marca activo en cualquier página del namespace `personas`
  (`ns == 'personas'`), incluidas las vistas de edición de personas.
- En cualquier otra página (Inicio, Parroquias, Personas…) los controles arrancan cerrados.

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

### Dashboard

La pantalla de inicio (`core/views.py`, `templates/core/dashboard.html`) se apoya en
`core.services.resumen_dashboard`, que concentra los datos con pocas consultas: un
agregado para los totales, una sola consulta agrupada por mes (`TruncMonth` + `values` +
`Count`, excluyendo los sacramentos anulados) para la serie de los últimos 12 meses y una
lista con el historial. La variación mensual se deriva de la misma serie (si el mes
anterior tiene 0 muestra **Nuevo** o **Sin cambios** según haya registros este mes).

- Colores por sacramento (clases `.tarjeta-*` y `.punto-*`):

| Sacramento       | Color   | Suave   | Ícono (`templates/core/iconos/`) |
| ---------------- | ------- | ------- | -------------------------------- |
| Bautismo         | #2563EB | #E3EEFF | `gota.svg`                       |
| Primera Comunión | #16A34A | #DCFCE7 | `caliz.svg`                      |
| Confirmación     | #7C3AED | #EDE9FE | `paloma.svg`                     |
| Matrimonio       | #E11D48 | #FFE4E6 | `anillos.svg`                    |

- Los íconos son SVG propios (trazo uniforme de 2.5 en el `viewBox` de 48, sin texto,
  heredan el color con `currentColor`). Se insertan en línea con
  `{% include "core/iconos/<nombre>.svg" %}` para poder colorearlos con CSS y llevan
  `aria-hidden="true"`. La cruz del pie es `cruz.svg`. Varias partes llevan relleno con
  opacidad baja (el agua de la gota, la copa del cáliz, el ala de la paloma) para dar peso
  visual. Los mismos SVG se usan en el sidebar, a tamaño de ícono de menú (clase
  `nav-icon icono-menu`).
- Cada tarjeta muestra el ícono en un círculo de **84 px** con el color suave del
  sacramento (`.icono-circulo`) y el SVG a **44 px**; el total va en `.tarjeta-total`.
  Las tarjetas usan `col-12 col-md-6 col-lg-3`: una columna en móvil, dos en tablet y
  cuatro en escritorio.
- Los estilos propios del dashboard viven en `static/css/dashboard.css`, cargado solo en
  esa pantalla con `{% block extra_css %}`. La barra superior (título, campana y menú de
  usuario), el sidebar y el pie de página se estilan dentro de `base.html`.
- El gráfico usa **Chart.js 4.5.1** desde cdnjs
  (`https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js`). Los datos se
  pasan al navegador con `{{ datos_grafico|json_script:"datos-grafico" }}` (nunca
  concatenados en JS) y el filtro por tipo muestra u oculta series sin recargar
  (`static/js/dashboard.js`).
- La campana muestra las anotaciones marginales `POR_COMUNICAR` con el context processor
  `core.context_processors.anotaciones_pendientes` (dos consultas: el total y las cinco
  más recientes; solo para usuarios autenticados).

### Barra superior y menú de usuario

- A la izquierda, el botón hamburguesa de AdminLTE (`data-widget="pushmenu"`, ícono
  `fa-bars`, con `aria-label="Mostrar u ocultar el menú"`), que permite abrir y cerrar el
  menú lateral, especialmente en móvil. Junto a él, el título de la página actual, que cada
  vista define con el bloque `{% block heading %}` (p. ej. **Inicio** en el dashboard).
- A la derecha, la campana de anotaciones y el menú de usuario: avatar circular con las
  iniciales del usuario (filtro `iniciales` de `core/templatetags/interfaz_extras.py`, que
  toma la primera letra de la primera y la última palabra del nombre) sobre fondo azul, el
  texto **Hola, {nombre}** y una flecha. El desplegable muestra el nombre completo, el rol
  (del `PerfilUsuario`, o "Administrador" si no hay perfil) y un formulario **POST** hacia
  `{% url 'logout' %}` para cerrar sesión.
- En móvil el texto "Hola, {nombre}" se oculta (`d-none d-md-inline`) y queda solo el avatar.

### Cita del encabezado y pie de página

- La cita del dashboard no lleva fondo ni recuadro: estilizada en cursiva, alineada a la
  derecha, con la línea vertical dorada a su **derecha** (`border-right`), y "Colosenses
  3:23" en gris debajo.
- El pie usa el layout fijo de AdminLTE y un `min-height` en `.content-wrapper`
  (`calc(100vh - 3.5rem - 3.4rem)` en `base.html`) para que quede visible al fondo incluso
  en páginas cortas.

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

## Parroquias y Libros

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
(`mensaje_protegido`, personalizable). Aplica a Libros con
folios o partidas y Parroquias con libros o sacramentos. Los ministros usan
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
