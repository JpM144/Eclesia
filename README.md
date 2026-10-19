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

Cuando se agregue una ruta nueva se usa el mismo patrón con el nombre de esa ruta.
**Bautismos** y **Primera Comunión** ya tienen pantalla y enlazan a
`sacramentos:bautismo_lista` y `sacramentos:primera_comunion_lista` (cada uno queda activo
por su propio nombre: `{% if 'bautismo' in actual %}` y `{% if 'primera_comunion' in actual %}`).
Los dos sacramentos restantes (Confirmaciones y Matrimonios) aún no tienen pantalla:
aparecen atenuados (clase `deshabilitado`, `aria-disabled="true"`, sin `href`), con la
etiqueta **Pronto** y con los mismos íconos SVG del dashboard; llevan el comentario
`{# TODO: enlazar cuando exista la pantalla #}`. Su etiqueta se maqueta como
`<p class="p-con-etiqueta"><span class="texto-item">…</span>
<span class="etiqueta-pronto">Pronto</span></p>`: el texto se recorta con puntos y la
píldora **Pronto** nunca se comprime ni se corta, aun en ítems largos.

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
los de terceros se cargan por CDN. Además de `tema.css` (global) están `dashboard.css`
(dashboard), `bautismo_lista.css` y `hoja_partida.css` (sacramentos), y los scripts
`tema.js`, `formularios.js`, `ubicacion.js`, `buscar_persona.js` y `filas_clicables.js`
(este último hace clicables las filas `tr[data-href]` de las listas).

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
  `cruz.svg` y el estado vacío de actividades usa `documento-reloj.svg`. La hoja de partida usa
  `cruz_certificado.svg` (cruz latina) en el encabezado y `gota.svg` como marca de agua. Varias
  partes llevan relleno con opacidad baja (el agua de la gota, la copa del cáliz, el ala de la
  paloma) para dar peso visual. Los mismos SVG se usan en el sidebar, a tamaño de ícono de menú
  (clase `nav-icon icono-menu`).
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
  ancho máximo. Para los estados de las partidas hay además `--gp-corregido` /
  `--gp-corregido-fondo` (ámbar) y `--gp-archivado` / `--gp-archivado-fondo` (azul grisáceo),
  y para la hoja de partida `--gp-azul-hoja` y `--gp-dorado`. Las hojas de partida usan
  **Cinzel** (títulos) y **EB Garamond** (texto) desde Google Fonts, con respaldo
  Georgia/"Times New Roman"/serif (`static/css/hoja_partida.css`).
- La tipografía general es **Inter** desde Google Fonts (pesos 400, 500, 600 y 700) con respaldo
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

### Estados de interfaz

La interfaz trata de forma consistente el vacío, la carga, la interacción de botones y los
errores.

**Botones y enlaces.** Las reglas viven en `static/css/tema.css`. `.btn` y `.btn-tema`
tienen `transition` de 0.18 s; `.btn-tema:hover` y `.btn-tema:active` oscurecen el fondo,
los botones de Bootstrap aclaran u oscurecen con `filter: brightness()`, los botones
deshabilitados (`:disabled`/`.disabled`) se pintan en gris y con `cursor: not-allowed`, y
`:focus-visible` dibuja un contorno azul accesible. Con `prefers-reduced-motion` se anulan
las transiciones.

**Estado vacío.** El parcial `core/templates/includes/estado_vacio.html` dibuja un ícono en
un círculo, un título, un texto y un botón opcional. Se incluye con parámetros:

```html
{% include "includes/estado_vacio.html" with icono="core/iconos/documento-reloj.svg" titulo="Aún no hay registros" texto="..." boton_texto="Crear registro" boton_url=url_crear %}
```

En las listas del patrón CRUD (`core/templates/crud/lista.html`) se distingue el caso de
**lista vacía** (con el botón de creación) del de **filtro sin resultados** ("No hay
resultados con estos filtros" y un botón **Limpiar filtros**). Los textos por defecto salen
de `CrudListView` (`titulo_vacio`, `texto_vacio`, `texto_boton_vacio`, `icono_vacio`) y cada
vista puede sobrescribir `get_texto_vacio`, `get_texto_boton_vacio` y `get_url_crear_vacio`;
`hay_filtros_activos` decide cuál rama se muestra. El dashboard usa el mismo parcial para la
actividad reciente y para la gráfica.

**Insignias de estado.** Las partidas muestran su estado con `.insignia-estado` (definida en
`static/css/tema.css`): `--activo` (verde), `--corregido` (ámbar), `--anulado` (gris) y
`--archivado` (azul grisáceo). La clase se arma como `insignia-estado--{{ estado|lower }}` y el
texto sale de `get_estado_display`. La hoja de partida usa la misma insignia y añade la franja
en diagonal **ANULADA** cuando la partida está anulada.

**Carga.** Los formularios marcados con `data-evitar-doble-envio` (los del CRUD, el de
cuentas y el de eliminación; el registro de usuarios lo añade a mano) usan
`static/js/formularios.js`: al enviar un formulario válido se deshabilitan sus botones y se
muestra un spinner con "Guardando…", y al volver con el botón atrás se restaura el estado.
Mientras Chart.js dibuja la gráfica del dashboard se muestra un esqueleto
(`.esqueleto-grafico`, con brillo animado y respeto por `prefers-reduced-motion`) que se
retira al terminar la animación; si no hay partidas se muestra el estado vacío en su lugar.

**Errores.** `templates/404.html`, `templates/403.html` y `templates/500.html` son páginas
autónomas (sin `base.html` ni barra lateral) con la paleta del sistema y un botón para
volver al inicio. La 500 no usa context processors ni consultas a la base de datos y lleva
sus estilos dentro de la misma página. No muestran trazas, rutas del servidor ni detalles
internos.

### NOMBRE_PARROQUIA

La variable de entorno `NOMBRE_PARROQUIA` (leída con `python-decouple`, con default vacío)
se muestra en gris claro, en una línea más pequeña, bajo "Gestión Parroquial" en el
encabezado del menú lateral. Si queda vacía no se muestra nada. Se expone a las plantillas
con el context processor `core.context_processors.nombre_parroquia`, que no consulta la base
de datos; en los tests se fija con `override_settings(NOMBRE_PARROQUIA=...)`. La línea de
ejemplo está en `.env.example` con un comentario.

### NOMBRE_DIOCESIS

La variable de entorno `NOMBRE_DIOCESIS` (leída con `python-decouple`, con default vacío) es el
nombre de la diócesis que consta en las hojas de partida y en los certificados. `datos_hoja_bautismo`
la expone como `diocesis` y el parcial `hoja_partida.html` la pinta bajo el nombre de la parroquia
solo si no está vacía. La línea de ejemplo está en `.env.example` con un comentario.

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
folios, **partidas por folio** (cuántas partidas caben en cada folio, de 1 a 20;
por defecto 3), ministro que abre (los de la parroquia del libro; en la creación, si
aún no hay parroquia elegida, se ofrecen todos ordenados por parroquia), detalle y
observaciones. Los campos de cierre **no** están en este formulario.

El valor **partidas por folio** determina cómo se reparten automáticamente las
partidas en el libro: `parroquias.services.folio_para_nueva_partida(libro)` reutiliza
el último folio mientras le queden espacios y, al llenarse, pasa al siguiente creando
el `Folio` si hace falta. Las partidas anuladas siguen ocupando su lugar, y si se
supera el total de folios declarado el registro se rechaza con
**“El libro está lleno: ciérralo y abre uno nuevo para seguir registrando.”**

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

## Sacramentos: Bautismos

Primer sacramento con pantalla completa. La app `sacramentos` expone tres vistas y un servicio
transaccional; las rutas viven en `sacramentos/urls.py` bajo el namespace `sacramentos`.

| Vista                     | URL                                     | Ruta                            |
| ------------------------- | --------------------------------------- | ------------------------------- |
| Lista de bautismos        | `/sacramentos/bautismos/`               | `sacramentos:bautismo_lista`    |
| Registrar bautismo        | `/sacramentos/bautismos/nuevo/`         | `sacramentos:bautismo_crear`    |
| Ficha de la partida       | `/sacramentos/bautismos/<pk>/`          | `sacramentos:bautismo_detalle`  |
| Corregir la partida       | `/sacramentos/bautismos/<pk>/editar/`   | `sacramentos:bautismo_editar`   |
| Anular la partida         | `/sacramentos/bautismos/<pk>/anular/`   | `sacramentos:bautismo_anular`   |
| Eliminar la partida       | `/sacramentos/bautismos/<pk>/eliminar/` | `sacramentos:bautismo_eliminar` |
| Certificado de la partida | `/sacramentos/bautismos/<pk>/certificado/` | `sacramentos:bautismo_certificado` |

El `<pk>` de la ficha es el `pk` del `Bautismo`, que es a la vez el del `Sacramento`
(`OneToOneField(primary_key=True)`). Todas las vistas exigen sesión
(`LoginRequiredMiddleware`).

### Lista y ficha

- **Lista** (`BautismoListView`, plantilla `bautismo_lista.html`): pagina de 25 en 25 y ordena
  por libro y número de partida descendentes (`-libro__numero_libro`, `-libro__nombre`,
  `-numero`). Muestra las columnas N.° de partida, folio, libro, fecha del bautismo, bautizado
  (con su documento en gris), padres, parroquia y estado. Acepta los filtros combinables
  `?q=` (nombres/apellidos del fiel o número de partida), `?libro=`, `?anio=`, `?estado=` y
  `?parroquia=`; **Parroquia** (columna y filtro) solo aparece cuando hay más de una parroquia
  con libros de bautismos, y los filtros se conservan al paginar (`consulta_filtros`). Cada fila
  es clicable (`static/js/filas_clicables.js`, filas `tr[data-href]`) y ofrece además el enlace
  **Ver partida**; el estado se pinta con `.insignia-estado` (`--activo`, `--corregido`,
  `--anulado`, `--archivado`). Usa `select_related` (fiel, folio, libro, parroquia, padre,
  madre) para no provocar consultas N+1 y mantiene un número constante de consultas.
- **Ficha** (`BautismoDetailView`, plantilla `bautismo_detalle.html`): muestra la partida como
  una hoja del libro mediante el parcial reutilizable
  `sacramentos/templates/sacramentos/partials/hoja_partida.html` (estilo `hoja_partida.css`,
  tipografías Cinzel + EB Garamond, marca de agua con la gota, insignia de estado y franja
  **ANULADA** si procede), más una barra de acciones (editar/anular/eliminar según las reglas,
  volver e **Imprimir** con `window.print()`) y, fuera de la hoja (`.no-print`), el historial y
  los enlaces a las fichas de las personas de la partida. El parcial recibe `titulo`,
  `tipo_libro`, `referencia`, `parroquia`, `diocesis`, `filas`, `icono_agua`, `notas`, `estado`,
  `estado_etiqueta` y, opcionalmente, `ocultar_estado` (oculta la insignia de estado) e
  `incluir_cierre` (añade el pie del certificado), y está pensado para reutilizarse en el
  certificado y en los demás sacramentos. Los datos los arma
  `datos_hoja_bautismo(bautismo)` (`sacramentos/services.py`);
  los padres biológicos de un hijo adoptivo nunca se incluyen en la hoja. Un `pk` inexistente
  (o que no sea un bautismo) responde `404`. El enlace a la ficha aparece en **Consultar
  personas** y en la ficha de la persona cuando la partida de bautismo existe (`url_detalle`).

### Formulario de registro

`BautismoForm` (`sacramentos/forms.py`) es un `forms.Form` plano: reúne datos de `Sacramento`,
`Bautismo`, `Fiel`, `Padre`, `Madre` y `Padrino`. El select de libro solo ofrece libros de
**bautismos abiertos**. Valida, con mensajes en español, lo mismo que luego revalida
`full_clean()` de los modelos:

- La `fecha` del bautismo no puede ser futura ni anterior al nacimiento.
- El libro debe estar abierto (`_validar_partida` se omite al corregir, porque no se
  inscribe una partida nueva) y ser de tipo `BAUTISMOS`.
- **Can. 875**: si no hay padrino ni madrina, el testigo es obligatorio.
- Documentos normalizados (`DocumentoMixin.normalizar_numero`); `CC`, `TI` y `RC` solo dígitos.
- Padre y madre obligatorios con documento, nombre y apellido.

El folio y la fecha de registro **no** son campos del formulario: el folio lo calcula
el servicio y la fecha de registro es la fecha actual (`timezone.localdate()`).

El mapeo de ministros es: `ministro` → `Sacramento.ministro`, `quien_firma` →
`Bautismo.quien_firma` y `doy_fe` → `Bautismo.doy_fe` (por defecto, el párroco de la parroquia
del libro). `observaciones` va a `Sacramento.observaciones`. La plantilla incluye
`static/js/buscar_persona.js` y `static/js/ubicacion.js`, y usa `data-evitar-doble-envio` para
no reenviar el formulario.

### Servicio y numeración

`registrar_bautismo(datos, usuario)` (`sacramentos/services.py`) corre dentro de
`transaction.atomic`. Crea o **reutiliza** (sin sobrescribir; solo rellena campos vacíos) las
personas `Fiel`, `Padre`, `Madre`, `Padrino` y, si aplica, `Madrina`. El número de partida sale
de `siguiente_numero_partida(libro)`, el folio de `folio_para_nueva_partida(libro)` y la fecha
de registro es la fecha actual. Registra la creación en `HistorialSacramento` con
`AccionHistorial.CREACION` y devuelve `(bautismo, reutilizadas)`. Al guardar, muestra
**“Partida registrada: Libro X, Folio Y, N.° Z”** y, si reutilizó personas, un aviso
informativo.

### Corregir, anular y eliminar partidas

Siguiendo las reglas de los libros parroquiales (las partidas no se borran ni se
sobrescriben), la ficha ofrece acciones según el estado:

- **Corregir** (`corregir_bautismo`): vuelca los datos editados
  —incluidos los datos mutables del bautizado (los nombres y documentos de las personas ya
  vinculadas son de solo lectura y se corrigen desde su ficha)— sin cambiar libro, folio,
  número ni fecha de registro; exige `motivo` y guarda historial `CORRECCION`. Regla del mismo
  día: si se registró **hoy** el cambio queda solo en el historial y la partida sigue `ACTIVO`
  (aún eliminable); **otro día** pasa a `CORREGIDO` y añade una anotación marginal de tipo
  `CORRECCION`. No se puede corregir una partida anulada.
- **Anular** (`anular_bautismo`, estado `ANULADO`): conserva la partida en el libro, exige
  `motivo` y guarda historial `ANULACION` y anotación `ANULACION` («Partida anulada: {motivo}»).
- **Eliminar** (`eliminar_bautismo`): solo si la partida está **ACTIVA**, es la **última del
  libro**, se registró **hoy** y **no tiene anotaciones marginales** (ni como partida anotada
  ni como origen); las partidas anuladas o corregidas nunca se eliminan (quedan como
  constancia). Guarda una copia en `PartidaEliminada` (snapshot con motivo y usuario, visible
  en el admin en solo lectura) antes de borrar el `Sacramento` y, en cascada, el `Bautismo`,
  el historial y las anotaciones. Al borrar la última partida se liberan su número y folio, y
  el siguiente registro los reutiliza.

Las partidas anuladas no cuentan en el dashboard ni aparecen en el índice del libro. La ficha
muestra Editar/Anular solo en estados editables y Eliminar únicamente cuando se cumple
`puede_eliminarse(bautismo)` (la misma regla que valida el servidor).

### Certificado

La ficha ofrece **Certificado** (excepto en partidas anuladas), que lleva a
`sacramentos:bautismo_certificado` = `/sacramentos/bautismos/<pk>/certificado/`
(`BautismoCertificadoView`, un `FormView` con `SolicitudCertificadoForm`). El GET muestra la
solicitud (solicitante, tipo y número de documento, relación con el titular y finalidad); el
POST valida —nombre solo con letras, documento validado según su tipo, y texto obligatorio
cuando la finalidad es «Otro»—, registra `AccionHistorial.CERTIFICADO` en el historial
(«Certificado expedido a … (relación) para …») y renderiza el certificado imprimible con
`certificados/certificado.html`. Una partida anulada redirige a la ficha con un mensaje.

El certificado reutiliza el parcial de la hoja (`hoja_partida.html` con
`ocultar_estado=True` e `incluir_cierre=True`): sin la insignia de estado, con las notas
marginales y con el pie `certificados/partials/cierre_certificado.html` dentro del marco
(texto de expedición firmado por el párroco, sello y, solo cuando quien expide tiene rol
Secretario(a), su firma). Los datos del pie los arma
`datos_certificado_bautismo(bautismo, solicitud, usuario)` en `sacramentos/services.py`,
usando `fecha_en_letras` para la fecha de expedición. Fuera del marco, en cursiva gris y con
líneas finas a los lados, va el pie `{Parroquia} · Fe que une, sacramentos que dan vida`. La
hoja la estiliza `static/css/hoja_partida.css` y la página (barra Imprimir/Volver y pie) el
nuevo `static/css/certificado.css`.

### Autocompletado de personas

Los campos de documento de cada bloque (`.bloque-persona[data-rol]`) consultan
`personas:api_persona` (ver **Endpoint de búsqueda por documento**). Si la persona ya existe en
cualquier rol, el formulario rellena sus datos, bloquea **solo** nombres y apellidos (solo
lectura) y muestra «Persona registrada. Para corregir sus datos usa Consultar personas» con un
enlace a su ficha (se abre en otra pestaña). Si cambias el número después de buscar, se
desbloquean y se limpian los datos rellenados.

Si el documento no existe se avisa («No está registrada. Llena sus datos y se guardará con la
partida») y los campos quedan editables: al guardar, las personas nuevas se crean
validadas (`full_clean`) dentro de la misma transacción que la partida. Si el fiel ya tiene un
bautismo activo o corregido, o el sexo no corresponde al rol (padre varón, madre mujer, padrino
varón, madrina mujer), el aviso aparece **al buscar**, no solo al guardar. El comportamiento se
configura con atributos `data-` (rol del bloque, par tipo/número y `data-campo-persona` de cada
campo rellenable); el relleno se hace siempre con `textContent`/`value`.

## Sacramentos: Primera Comunión

Registro, edición, anulación, eliminación y certificado de partidas de Primera Comunión
(prompts 9a y 9b).

### Pantallas

- **Lista** `sacramentos:primera_comunion_lista` = `/sacramentos/primeras-comuniones/`
  (`PrimeraComunionListView`): columnas N.°, Folio, Libro, Fecha, Comulgante, Bautismo
  («Enlazado»/«Externo»), Parroquia, Estado y acciones; mismos filtros que la lista de
  bautismos (`?q=`, `?libro=`, `?anio=`), paginado 25 y sin N+1. Reutiliza
  `static/css/bautismo_lista.css`, `includes/estado_vacio.html` y `filas_clicables.js`.
- **Registro** `sacramentos:primera_comunion_crear` = `/sacramentos/primeras-comuniones/nueva/`
  (`PrimeraComunionCreateView` + `PrimeraComunionForm`; acepta `?libro=` para precargar el
  libro). Tras guardar redirige a la ficha con mensaje «Partida registrada: Libro X, Folio Y,
  N.° Z».
- **Ficha** `sacramentos:primera_comunion_detalle` = `/sacramentos/primeras-comuniones/<pk>/`
  (`PrimeraComunionDetailView`): hoja de partida (`datos_hoja_primera_comunion`, icono
  `caliz.svg`), tarjeta «Constancia del bautismo» con enlace a la partida enlazada cuando
  existe, historial y personas de la partida. Barra de acciones con Editar/Anular solo en
  estados editables, Eliminar únicamente cuando se cumple `puede_eliminarse` (deshabilitado con
  el motivo en caso contrario), Certificado salvo en partidas anuladas, y Volver/Imprimir.

### Reglas sacramentales P1–P5

Mecanismo reutilizable en `sacramentos/reglas.py` (también servirá para Confirmación y
Matrimonio). Tres niveles: **BLOQUEA** (error sin campo, no guarda), **ADVIERTE** (no guarda
hasta marcar «Verificado / excepción autorizada» y escribir el motivo; ambas cosas se
revalidan en el servidor y cada aceptación queda en el historial con código, motivo y
usuario) y **RECUERDA** (solo informa). Las reglas se evalúan **siempre** en el servidor
(`MixinReglas.clean()`): manipular el POST no las saltea.

| Regla | Nivel | Condición                                                    |
| ----- | ----- | ------------------------------------------------------------ |
| P1    | BLOQUEA | Sin bautismo (ni enlazado ni externo completo) (c. 842).    |
| P2    | BLOQUEA | Ya tiene Primera Comunión activa o corregida (con referencia). |
| P3    | BLOQUEA | Fecha futura, anterior al nacimiento o anterior al bautismo. |
| P4    | ADVIERTE | Edad < `EDAD_USO_RAZON` (7) en la fecha (c. 914; c. 97 §2). |
| P5    | RECUERDA | Confesión sacramental previa (c. 914); no bloquea.          |

El bautismo puede venir **enlazado** (la casilla oculta `bautismo` que llena
`buscar_persona.js` con `data-mostrar-bautismo`, o la búsqueda por documento) o registrado
con sus **datos externos** (fecha, parroquia, libro, folio y número obligatorios; la diócesis
viaja en `observaciones_bautismo` como «Diócesis: X.», sin migración).

### Servicio

`sacramentos.services.registrar_primera_comunion(datos, usuario)` (transacción única): crea
el Sacramento PRIMERA_COMUNION con folio, número y fecha de registro automáticos y la
PrimeraComunion con la **edad calculada en el servidor** (sin campo de migración), copia
padre y madre del bautismo enlazado si existe, guarda los datos externos si no, y registra en
el historial la CREACION más una entrada «Regla {codigo} verificada: {motivo}» por cada
advertencia aceptada. No se usa AnotacionMarginal (el tipo no existe para PC; ver
docs/libros_parroquiales.md regla 7).

### Editar, anular y eliminar partidas

Las mismas reglas de los libros parroquiales que en Bautismo (la regla de corrección es
común a ambos):

- **Editar** `sacramentos:primera_comunion_editar` = `/sacramentos/primeras-comuniones/<pk>/editar/`
  (`PrimeraComunionUpdateView` + `PrimeraComunionEditarForm`): exige `motivo` y permite cambiar
  la constancia del bautismo (enlazada o externa), la fecha, el ministro, los padres (solo con
  bautismo externo) y las observaciones. El libro, el folio, el número, la fecha de registro y
  la identidad del comulgante (tipo/número de documento, nombres y apellidos) quedan fijos
  (`disabled`): para corregir a la persona se usa su ficha o, si está mal, se anula la partida y
  se registra otra. Si se corrige el **mismo día** del registro el cambio queda solo en el
  historial (la partida sigue `ACTIVO`); **otro día** la partida pasa a `CORREGIDO` y se añade
  una anotación marginal de tipo `CORRECCION`. Se revalidan P1–P5 (P2 excluye la propia partida)
  y cada advertencia aceptada queda en el historial. No se puede editar una partida anulada.
- **Anular** `sacramentos:primera_comunion_anular` = `/sacramentos/primeras-comuniones/<pk>/anular/`
  (`PrimeraComunionAnularView`): exige `motivo`, conserva la partida y su número, la deja en
  `ANULADO` y guarda historial `ANULACION` más anotación `ANULACION` («Partida anulada: {motivo}»).
- **Eliminar** `sacramentos:primera_comunion_eliminar` = `/sacramentos/primeras-comuniones/<pk>/eliminar/`
  (`PrimeraComunionEliminarView`): solo si `puede_eliminarse` (ACTIVA, última del libro,
  registrada hoy y sin anotaciones marginales); guarda la copia en `PartidaEliminada` (tipo
  `PRIMERA_COMUNION`) con el resumen y el motivo antes de borrar el `Sacramento` y, en cascada,
  la partida, el historial y las anotaciones. Las partidas anuladas o corregidas nunca se
  eliminan (quedan como constancia). Al borrar la última partida se liberan número y folio.

### Certificado

La ficha ofrece **Certificado** (excepto en partidas anuladas), que lleva a
`sacramentos:primera_comunion_certificado` =
`/sacramentos/primeras-comuniones/<pk>/certificado/` (`PrimeraComunionCertificadoView`, un
`FormView` con `SolicitudCertificadoForm`). El GET muestra la solicitud —sin registrar nada en
el historial—; el POST válido registra `AccionHistorial.CERTIFICADO` («Certificado expedido a …
(relación) para …») y renderiza el certificado imprimible con `certificados/certificado.html`.
Una partida anulada redirige a la ficha con el mensaje «No se puede expedir un certificado de
una partida anulada.».

El certificado reutiliza el parcial de la hoja (`hoja_partida.html` con `ocultar_estado=True` e
`incluir_cierre=True`) y el mismo `certificados/base_certificado.html` que el de bautismo: título
«CERTIFICADO DE PRIMERA COMUNIÓN», frase «El suscrito párroco certifica que en el Libro de
Primera Comunión de {parroquia} se encuentra la siguiente partida:», marca de agua con el cáliz,
personas solo con su nombre (sin documento) y sin los padres biológicos de una adopción. Los
datos los arman `datos_hoja_primera_comunion(primera, para_certificado=True)` y
`datos_certificado_primera_comunion(primera, solicitud, usuario)`, ambos sobre el
`datos_cierre_certificado` compartido. El PDF cabe en **una hoja carta** (`@page size: letter`
en `static/css/certificado.css`).

## Personas

Padres, madres, padrinos y fieles no se administran desde el menú: se crean dentro de cada
partida. Desde el sidebar solo se accede a **Consultar personas** y, desde ahí, a la edición
individual de una persona.

- **Consultar personas** (`/personas/consultar/`, ruta `personas:consultar`): busca por
  documento o por nombre con el parámetro GET `q`. Si `q` son solo dígitos (se permiten
  puntos y espacios), busca por número de documento (coincidencia exacta primero y, si no
  hay, por contenido); si no, cada palabra de `q` debe aparecer en nombres o apellidos
  (`icontains`). Con menos de 3 caracteres no busca y muestra un aviso.
- Cada resultado es una **persona agrupada por su `Documento`** con todos sus papeles:
  `Fiel`, `Padre`, `Madre`, `Padrino`, `Ministro`, `TestigoMatrimonio` y
  `PadrinoMatrimonio` (estos dos últimos se asocian al documento por su par
  `tipo_documento` + cédula). La tarjeta muestra el nombre principal (con prioridad
  Fiel > Padre > Madre > Ministro > Padrino > Testigo > PadrinoMatrimonio), los registros
  alternativos con otro nombre, el documento, una insignia por papel, el total de partidas
  en que aparece y la línea de ministro. Limita a 50 personas (con aviso si hay más) y carga
  las partidas por lote (`select_related` y `__in`), con un número de consultas fijo.
- **Menciones sin documento**: además de las personas, al buscar por nombre aparecen los
  textos libres que la mencionan dentro de una partida sin que exista persona con ese
  documento: abuelos, testigos y padres biológicos del bautismo, y testigos o padrinos de
  matrimonio cuya cédula no corresponde a ningún `Documento`. Se muestran en una tabla
  (`rol`, sacramento, fecha, libro, folio y número).
- **Ficha de persona** (`/personas/<documento_id>/`, ruta `personas:ficha`): reúne los
  papeles e insignias (con botones "Editar datos como …" para los que son editables), los
  datos personales, los sacramentos recibidos (con sus anotaciones marginales), la familia
  y relaciones (padres, cónyuges, hijos, ahijados y matrimonios apadrinados), sus
  actuaciones como ministro o testigo de matrimonio y el **historial**: las 10 entradas de
  `HistorialSacramento` más recientes de las partidas donde aparece (fecha, partida, acción
  y quién: nombre con su rol, o Administrador). Las secciones vacías se ocultan y el
  documento sin ninguna persona registrada responde 404.
- **Editar persona** (`personas:padre_editar`, `personas:madre_editar`,
  `personas:padrino_editar`, `personas:fiel_editar`): corrige la ficha de una persona creada
  desde una partida. Arriba del formulario avisa en cuántas partidas se verá el cambio y, al
  guardar, vuelve al `next` indicado (solo si es un destino seguro según
  `url_has_allowed_host_and_scheme`) o a "Consultar personas". No hay creación ni eliminación
  y, si el documento o la cédula ya pertenecen a otra persona, el error se muestra en el campo
  (nunca un error 500).

`Contrayente` no se lista por separado porque no guarda documento ni nombre propios: usa el
`Fiel` asociado, que aparece con el rol "contrayente" en sus partidas y sacramentos recibidos.

### Endpoint de búsqueda por documento

`GET /personas/api/persona/` (ruta `personas:api_persona`) alimenta el autocompletado de los
formularios de partidas. Exige sesión (lo cubre `LoginRequiredMiddleware`), **solo acepta GET**
(responde `405` con `Allow: GET` en otro caso) y limita cada usuario a **60 consultas por
minuto** (responde `429` al superarlo; el contador vive en la caché de Django). Parámetros:

| Parámetro | Valores                          | Descripción                                     |
| --------- | -------------------------------- | ----------------------------------------------- |
| `rol`     | `fiel`, `padre`, `madre`, `padrino`, `madrina` | Tipo de persona a buscar.                    |
| `tipo`    | p. ej. `CC`, `TI`, `RC`           | Tipo de documento (se normaliza y se valida con `validar_documento`). Opcional. |
| `numero`  | dígitos o alfanumérico            | Número de documento.                            |

La búsqueda **no está limitada al rol pedido**: se resuelve el `Documento` y se miran todas las
filas (`Fiel`, `Padre`, `Madre`, `Padrino`) con prioridad Fiel > Padre > Madre > Padrino para
los nombres. Si se omite `tipo`, se busca solo por número: con una sola coincidencia se
completa el tipo en la respuesta; con varias se responde `200` con
`{"encontrado": false, "varios": true, "mensaje": …}` pidiendo elegir el tipo.

Respuestas:

- `400` si falta `numero`, el `rol` no es válido o el número no pasa `validar_documento` para su
  tipo.
- `404` con `{"error": "No se encontró la persona."}` si el documento no existe o no
  corresponde a ninguna persona de los cuatro roles.
- `200` con, para cualquier rol: `{"encontrado", "tipo_documento", "numero_documento",
  "nombres", "apellidos", "sexo_fiel", "editar_url"}` (la URL de edición de la persona
  encontrada, para corregirla desde Consultar personas). Solo para `rol=fiel` se añaden
  `{"fecha_nacimiento", "municipio", "sexo", "telefono", "bautismo_activo",
  "bautismo_referencia"}`; `bautismo_referencia` es «Libro X · Folio Y · N.° Z» del bautismo
  activo o corregido (vacío si no tiene). Si `bautismo_activo` es `true` se añaden además
  `bautismo_id` (pk de la partida, para enlazarla en el formulario de Primera Comunión),
  `bautismo_url` (URL de su ficha), `bautismo_parroquia`, `bautismo_fecha` (ISO) y
  `bautismo_padre`/`bautismo_madre`; un fiel sin bautismo responde exactamente con los campos
  de siempre. No se devuelve ningún id interno salvo los del bautismo enlazado. El consumo
  desde el navegador se hace en `static/js/buscar_persona.js`, que escribe siempre con
  `textContent`/`value` (nunca `innerHTML`).

Se conservan los endpoints heredados `personas:api_padre` (`/personas/api/padre/`) y
`personas:api_madre` (`/personas/api/madre/`).

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

## Datos de demostración

`cargar_datos_demo` crea un conjunto completo de datos de ejemplo en la base de **desarrollo**
para probar el dashboard, los libros y la consulta de personas. Solo funciona con `DEBUG=True`;
si no, avisa y no toca nada. Cada modelo se valida con `full_clean()` antes de guardarse y todo
el proceso va en una transacción: si algo no es válido, no queda ningún dato a medias.

```powershell
.\.venv\Scripts\python manage.py cargar_datos_demo
.\.venv\Scripts\python manage.py cargar_datos_demo --borrar
```

- La carga crea una parroquia con su ubicación (reutiliza un municipio existente y, si no hay
  ninguno, crea Colombia / Cundinamarca / Bogotá), tres ministros (párroco, vicario y diácono)
  y un **libro abierto por tipo** de sacramento, con la apertura 13 meses atrás.
- Personas y partidas: 40 fieles, 6 padres, 6 madres y 8 padrinos; 26 bautismos (uno
  **anulado**, para ver la diferencia en el dashboard) de los que salen 8 primeras comuniones,
  6 confirmaciones (incluida una persona bautizada en otra parroquia) y 3 matrimonios con sus
  contrayentes, testigos y proclamas.
- La parroquia demo toma el nombre de `NOMBRE_PARROQUIA` de `.env` (si no está vacío y no ya
  existe otra con ese nombre) y, si no, usa "Parroquia Demo". Todas las personas y ministros
  del demo tienen documentos que empiezan por **9990**.
- Las **anotaciones marginales** quedan en los tres estados (11 anotadas, 2 por comunicar y 1
  comunicada), y el **historial** de cada partida registra su creación con la fecha de la
  partida (no la de hoy), más cinco correcciones y una anulación: así el dashboard muestra
  actividad con fechas variadas.
- Si ya hay datos de demostración, un segundo `cargar_datos_demo` avisa y no crea nada. Sin
  `DEBUG=True`, o si el nombre de la parroquia ya existe, también avisa y no modifica la base.

`--borrar` elimina **solo** los datos de demostración (identificados por la parroquia de los
ministros con documento `9990` y por los documentos `9990`), siguiendo el orden que exigen las
protecciones (`on_delete=PROTECT`), y deja intactos los datos reales. Si la ubicación creada
por el demo queda sin uso, también la borra.

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
