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
campana de anotaciones y el menú de usuario con avatar, nombre, rol y cierre de sesión), el
sidebar (ver más abajo) y el pie de página. El ítem del sidebar queda activo automáticamente
comparando `request.resolver_match.url_name` con el nombre de la ruta:

```html
<a href="{% url 'dashboard' %}" class="nav-link{% if actual == 'dashboard' %} active{% endif %}">
```

Cuando se agregue una ruta nueva se usa el mismo patrón con el nombre de esa ruta. Los
cuatro sacramentos no tienen pantalla todavía: aparecen atenuados (clase `deshabilitado`,
`aria-disabled="true"`, sin `href`), con la etiqueta **Pronto** y con los mismos íconos SVG
del dashboard; llevan el comentario `{# TODO: enlazar cuando exista la pantalla #}`.

El orden del menú es: **Inicio**, Bautismos, Primera Comunión, Confirmaciones, Matrimonios,
**Libros**, **Consultar personas** y el desplegable **Catálogos** (Parroquias, Ministros,
Países, Departamentos y Municipios). **Libros** queda activo también en los folios, el cierre
y el índice de un libro (`'libro_' in actual or 'folio_' in actual`).

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
- El desplegable "Catálogos" se abre cuando una de sus páginas está activa; su condición
  comprueba los prefijos de las rutas de sus cinco entradas:
  `'parroquia_' in actual or 'ministro_' in actual or 'pais_' in actual or
  'departamento_' in actual or 'municipio_' in actual`.
- Cada subenlace se marca activo por el prefijo de su nombre de ruta: `'parroquia_' in
  actual` (Parroquias), `'ministro_' in actual` (Ministros), `'pais_' in actual` (Países),
  `'departamento_' in actual` (Departamentos) y `'municipio_' in actual` (Municipios).
- "Libros" es un ítem propio del sidebar, fuera del desplegable, activo con `'libro_' in
  actual or 'folio_' in actual`, de modo que se resalta en la lista, el formulario, el
  índice, el cierre y los folios.
- "Consultar personas" es un ítem propio del sidebar, fuera del desplegable, que enlaza
  `/personas/consultar/` y se marca activo en cualquier página del namespace `personas`
  (`ns == 'personas'`), incluidas las vistas de edición de personas.
- En cualquier otra página (Inicio, Parroquias, Personas…) los controles arrancan cerrados.

El menú se abre sobre el contenido con un fondo oscuro (el `#sidebar-overlay` que crea
AdminLTE) en pantallas menores de 992 px y se cierra al tocar ese fondo, con `Escape` o al
elegir un ítem (`static/js/tema.js`). Al fondo del menú hay una cruz fina, la frase en
cursiva *«La Iglesia es familia, y todos somos parte de ella»* y una línea corta; se oculta
con el menú colapsado o en pantallas de menos de 700 px de alto.

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

| Sacramento       | Color   | Pastel  | Ícono (`templates/core/iconos/`) |
| ---------------- | ------- | ------- | -------------------------------- |
| Bautismo         | #4A78B5 | #E4EDF8 | `gota.svg`                       |
| Primera Comunión | #4E8A6E | #E3F0EA | `caliz.svg`                      |
| Confirmación     | #7650B0 | #ECE6F6 | `paloma.svg`                     |
| Matrimonio       | #D04A5C | #F9E4E7 | `anillos.svg`                    |

- Los íconos son SVG propios (trazo uniforme de 2.5 en el `viewBox` de 48, sin texto,
  heredan el color con `currentColor`). Se insertan en línea con
  `{% include "core/iconos/<nombre>.svg" %}` para poder colorearlos con CSS y llevan
  `aria-hidden="true"`. El ícono de la iglesia del menú es `iglesia.svg`, la cruz del menú es
  `cruz.svg` y el estado vacío de actividades usa `documento-reloj.svg`. Varias partes llevan
  relleno con opacidad baja (el agua de la gota, la copa del cáliz, el ala de la paloma) para
  dar peso visual. Los mismos SVG se usan en el sidebar, a tamaño de ícono de menú (clase
  `nav-icon icono-menu`).
- Cada tarjeta muestra el ícono en un círculo pastel de **64 px** con el color del
  sacramento (`.icono-circulo`) y el SVG a **40 px**; la etiqueta en mayúsculas grises va
  sobre el total grande (`.tarjeta-total`) y debajo, centrado, el indicador de variación
  (guion gris «Sin cambios», flecha verde/roja con porcentaje o «Nuevo») y «vs. mes
  anterior». Las tarjetas usan `col-12 col-md-6 col-xl-3`: una columna en móvil, dos en
  tablet y cuatro a partir de 1200 px.
- La fila inferior coloca la gráfica, el acceso rápido (tres botones a todo el ancho en
  azul pizarra, verde salvia y morado grisáceo) y las últimas actividades: a partir de
  1200 px la gráfica ocupa el 50 % y cada columna lateral el 25 %; entre 992 y 1199 px la
  gráfica va a todo el ancho y las dos columnas al 50 %; por debajo se apilan.
- Los estilos propios del dashboard viven en `static/css/dashboard.css`, cargado solo en
  esa pantalla con `{% block extra_css %}`. La paleta, la tipografía y los estilos globales
  viven en `static/css/tema.css`.
- El gráfico usa **Chart.js 4.5.1** desde cdnjs
  (`https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js`). Los datos se
  pasan al navegador con `{{ datos_grafico|json_script:"datos-grafico" }}` (nunca
  concatenados en JS). El selector de periodo («Último año», «Últimos 6 meses», «Este año»)
  filtra en el navegador los 12 meses que entrega el servidor y la leyenda muestra u oculta
  series; si todos los valores son cero el eje Y usa `suggestedMax` de 10
  (`static/js/dashboard.js`).
- La campana muestra las anotaciones marginales `POR_COMUNICAR` con el context processor
  `core.context_processors.anotaciones_pendientes` (dos consultas: el total y las cinco
  más recientes; solo para usuarios autenticados).

### Barra superior y menú de usuario

- A la izquierda, el botón hamburguesa de AdminLTE (`data-widget="pushmenu"`, ícono
  `fa-bars`, con `aria-label="Mostrar u ocultar el menú"`), una línea vertical divisoria y
  el título de la página actual, que cada vista define con el bloque `{% block heading %}`
  (p. ej. **Inicio** en el dashboard).
- A la derecha, la campana de anotaciones, un separador y el menú de usuario: avatar
  circular oscuro con ícono de persona (sin iniciales), el nombre en negrita y el rol en
  gris debajo (del `PerfilUsuario`, o "Administrador" si no hay perfil) y una flecha que
  abre el desplegable con el nombre completo, el rol y un formulario **POST** hacia
  `{% url 'logout' %}`. Además, a la derecha del todo, hay un enlace **Cerrar sesión** con
  su ícono que envía el mismo formulario POST.
- En móvil se ocultan el nombre y el texto "Cerrar sesión" (quedan el avatar y el ícono),
  mediante las reglas de `tema.css`.

### Encabezado y pie del dashboard

- El encabezado muestra "Bienvenido al" en mayúsculas pequeñas y gris con espaciado de
  letras, el título grande en negrita azul oscuro y el subtítulo gris. A su derecha hay una
  tarjeta blanca con una línea vertical azul a la izquierda (`border-left`), la cita en
  cursiva y "Colosenses 3:23" en gris debajo. En móvil la cita pasa debajo del título.
- El pie usa el layout fijo de AdminLTE y un `min-height` en `.content-wrapper`
  (`calc(100vh - 3.5rem - 3.4rem)`, con las variables `--gp-alto-barra` y `--gp-alto-pie`)
  para que quede visible al fondo incluso en páginas cortas. Muestra solo el copyright; la
  cruz está ahora al fondo del menú lateral.

### Paleta, tipografía y responsive

- Los colores y las medidas se definen como variables CSS en `static/css/tema.css` (cargado
  después de AdminLTE): superficies (`--gp-marino`, `--gp-activo`, `--gp-contenido`), texto
  (`--gp-texto`, `--gp-texto-suave`), colores por sacramento y sus pasteles, radio, sombra y
  ancho máximo.
- La tipografía es **Inter** desde Google Fonts (pesos 400, 500, 600 y 700) con respaldo
  `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, de modo que se ve bien incluso
  sin conexión.
- Puntos de corte: a partir de 1200 px (y hasta 2K/4K) el menú es fijo, hay cuatro tarjetas
  por fila y el contenido se centra con un ancho máximo de 1600 px; entre 992 y 1199 px el
  menú puede colapsarse a íconos (`sidebar-mini`), las tarjetas van en 2 × 2, la gráfica a
  todo el ancho y el acceso rápido y las actividades al 50 %; entre 768 y 991 px el menú se
  abre encima del contenido con un fondo oscuro (`#sidebar-overlay` de AdminLTE); por debajo
  de 768 px las
  tarjetas van en una columna, la cita pasa debajo del título, se ocultan el nombre y el
  texto de cierre de sesión, la gráfica baja a 260 px y el selector de periodo ocupa todo el
  ancho.
- En cualquier tamaño no hay scroll horizontal: las tablas de las listas van dentro de
  `.table-responsive`, los formularios ocupan todo el ancho en móvil y los controles
  táctiles mantienen al menos 44 × 44 px.

### NOMBRE_PARROQUIA

La variable de entorno `NOMBRE_PARROQUIA` (leída con `python-decouple`, con default vacío)
se muestra en gris claro, en una línea más pequeña, bajo "Gestión Parroquial" en el
encabezado del menú lateral. Si queda vacía no se muestra nada. Se expone a las plantillas
con el context processor `core.context_processors.nombre_parroquia`, que no consulta la base
de datos; en los tests se fija con `override_settings(NOMBRE_PARROQUIA=...)`. La línea de
ejemplo está en `.env.example` con un comentario.

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

**Menú lateral:**
- Alto de encabezado: 64 px. Logo 32 px, título 16 px semibold, parroquia 12 px con 12 px entre logo y texto.
- Ítem: 44 px alto, radio 8 px, separación 4 px, padding horizontal 12 px. Ícono 24x24 centrado (~20px), gap 12 px con texto (15 px, 1 línea, ellipsis).
- Pronto: píldora 10 px mayúsculas, padding 2px 8px, margin-left auto.
- Activo: #34405A, ícono/texto blancos.
- Deshabilitado: #8B95A7.
- Colapsado (sidebar-mini sidebar-collapse): 72 px, solo íconos; textos ocultos; ítem activo 48x44 centrado.
- Subítems: sangría 36 px, alto 40 px. Flecha gira.
- Frase fondo: margin-top auto, centrada, padding 24 px; cruz 20 px, texto 12.5 px cursiva #94A3B8.
