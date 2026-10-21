# Tablas de la base de datos

Fecha de generación: 2026-10-19 15:27:49 -05.

Generado con `python manage.py exportar_esquema; no editar a mano`.

Total: 38 tablas.

## `admin` — Administración

### `django_admin_log`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | integer(32,0) | No | Sí |  |
| action_time | timestamp with time zone | No |  |  |
| object_id | text | Sí |  |  |
| object_repr | character varying(200) | No |  |  |
| action_flag | smallint(16,0) | No |  |  |
| change_message | text | No |  |  |
| content_type_id | integer(32,0) | Sí |  | django_content_type.id |
| user_id | integer(32,0) | No |  | auth_user.id |

## `auth` — Autenticación y autorización

### `auth_group`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | integer(32,0) | No | Sí |  |
| name | character varying(150) | No |  |  |

### `auth_group_permissions`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| group_id | integer(32,0) | No |  | auth_group.id |
| permission_id | integer(32,0) | No |  | auth_permission.id |

### `auth_permission`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | integer(32,0) | No | Sí |  |
| name | character varying(255) | No |  |  |
| content_type_id | integer(32,0) | No |  | django_content_type.id |
| codename | character varying(100) | No |  |  |

### `auth_user`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | integer(32,0) | No | Sí |  |
| password | character varying(128) | No |  |  |
| last_login | timestamp with time zone | Sí |  |  |
| is_superuser | boolean | No |  |  |
| username | character varying(150) | No |  |  |
| first_name | character varying(150) | No |  |  |
| last_name | character varying(150) | No |  |  |
| email | character varying(254) | No |  |  |
| is_staff | boolean | No |  |  |
| is_active | boolean | No |  |  |
| date_joined | timestamp with time zone | No |  |  |

### `auth_user_groups`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| user_id | integer(32,0) | No |  | auth_user.id |
| group_id | integer(32,0) | No |  | auth_group.id |

### `auth_user_user_permissions`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| user_id | integer(32,0) | No |  | auth_user.id |
| permission_id | integer(32,0) | No |  | auth_permission.id |

## `contenttypes` — Tipos de contenido

### `django_content_type`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | integer(32,0) | No | Sí |  |
| app_label | character varying(100) | No |  |  |
| model | character varying(100) | No |  |  |

## `cuentas` — Cuentas

### `cuentas_perfilusuario`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| rol | character varying(20) | No |  |  |
| usuario_id | integer(32,0) | No |  | auth_user.id |

## `django` — infraestructura interna

### `django_migrations`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| app | character varying(255) | No |  |  |
| name | character varying(255) | No |  |  |
| applied | timestamp with time zone | No |  |  |

## `parroquias` — Parroquias

### `parroquias_folio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| numero_folio | integer(32,0) | No |  |  |
| fecha_creacion | date | Sí |  |  |
| observaciones | text | No |  |  |
| libro_id | bigint(64,0) | No |  | parroquias_libro.id |

### `parroquias_libro`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| detalle | text | No |  |  |
| numero_libro | integer(32,0) | Sí |  |  |
| fecha_apertura | date | No |  |  |
| observaciones | text | No |  |  |
| parroquia_id | bigint(64,0) | No |  | parroquias_parroquia.id |
| tipo_libro | character varying(20) | No |  |  |
| total_folios | integer(32,0) | Sí |  |  |
| ministro_apertura_id | bigint(64,0) | Sí |  | parroquias_ministro.id |
| estado | character varying(10) | No |  |  |
| fecha_cierre | date | Sí |  |  |
| ministro_cierre_id | bigint(64,0) | Sí |  | parroquias_ministro.id |
| nota_cierre | text | No |  |  |
| partidas_por_folio | smallint(16,0) | No |  |  |

### `parroquias_ministro`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| apellido | character varying(100) | No |  |  |
| cargo | character varying(50) | No |  |  |
| fecha_nacimiento | date | Sí |  |  |
| telefono | character varying(20) | No |  |  |
| email | character varying(254) | Sí |  |  |
| documento_id | bigint(64,0) | No |  | personas_documento.id |
| parroquia_id | bigint(64,0) | Sí |  | parroquias_parroquia.id |

### `parroquias_parroquia`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(255) | No |  |  |
| direccion | character varying(255) | No |  |  |
| telefono | character varying(20) | Sí |  |  |
| email | character varying(254) | Sí |  |  |
| municipio_id | bigint(64,0) | No |  | ubicacion_municipio.id |
| parroco_id | bigint(64,0) | Sí |  | parroquias_ministro.id |

## `personas` — Personas

### `personas_documento`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo_documento | character varying(2) | No |  |  |
| numero_documento | character varying(30) | No |  |  |

### `personas_fiel`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombres | character varying(255) | No |  |  |
| apellidos | character varying(255) | No |  |  |
| fecha_nacimiento | date | No |  |  |
| telefono | character varying(20) | No |  |  |
| documento_id | bigint(64,0) | No |  | personas_documento.id |
| municipio_nacimiento_id | bigint(64,0) | Sí |  | ubicacion_municipio.id |
| sexo | character varying(1) | Sí |  |  |

### `personas_madre`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| apellido | character varying(100) | No |  |  |
| documento_id | bigint(64,0) | No |  | personas_documento.id |

### `personas_padre`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| apellido | character varying(100) | No |  |  |
| documento_id | bigint(64,0) | No |  | personas_documento.id |

### `personas_padrino`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(255) | No |  |  |
| documento_id | bigint(64,0) | No |  | personas_documento.id |

## `sacramentos` — Sacramentos

### `sacramentos_anotacionmarginal`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo | character varying(20) | No |  |  |
| fecha | date | No |  |  |
| descripcion | text | No |  |  |
| estado | character varying(20) | No |  |  |
| parroquia_destino_texto | character varying(255) | No |  |  |
| fecha_comunicacion | date | Sí |  |  |
| creado_en | timestamp with time zone | No |  |  |
| parroquia_destino_id | bigint(64,0) | Sí |  | parroquias_parroquia.id |
| sacramento_id | bigint(64,0) | Sí |  | sacramentos_sacramento.id |
| sacramento_origen_id | bigint(64,0) | Sí |  | sacramentos_sacramento.id |

### `sacramentos_bautismo`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| sacramento_id | bigint(64,0) | No | Sí | sacramentos_sacramento.id |
| abuelo_paterno | character varying(255) | No |  |  |
| abuela_paterna | character varying(255) | No |  |  |
| abuelo_materno | character varying(255) | No |  |  |
| abuela_materna | character varying(255) | No |  |  |
| tipo_hijo | character varying(20) | No |  |  |
| doy_fe_id | bigint(64,0) | No |  | parroquias_ministro.id |
| madre_id | bigint(64,0) | Sí |  | personas_madre.id |
| madrina_id | bigint(64,0) | Sí |  | personas_padrino.id |
| padre_id | bigint(64,0) | Sí |  | personas_padre.id |
| padrino_id | bigint(64,0) | Sí |  | personas_padrino.id |
| quien_firma_id | bigint(64,0) | No |  | parroquias_ministro.id |
| testigo_nombre | character varying(255) | No |  |  |
| padre_biologico_nombre | character varying(255) | No |  |  |
| madre_biologica_nombre | character varying(255) | No |  |  |

### `sacramentos_confirmacion`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| sacramento_id | bigint(64,0) | No | Sí | sacramentos_sacramento.id |
| edad | integer(32,0) | No |  |  |
| doy_fe_id | bigint(64,0) | No |  | parroquias_ministro.id |
| madre_id | bigint(64,0) | Sí |  | personas_madre.id |
| municipio_bautismo_id | bigint(64,0) | Sí |  | ubicacion_municipio.id |
| padre_id | bigint(64,0) | Sí |  | personas_padre.id |
| padrino_id | bigint(64,0) | Sí |  | personas_padrino.id |
| bautismo_id | bigint(64,0) | Sí |  | sacramentos_bautismo.sacramento_id |
| fecha_bautismo | date | Sí |  |  |
| folio_bautismo | integer(32,0) | Sí |  |  |
| libro_bautismo | integer(32,0) | Sí |  |  |
| madrina_id | bigint(64,0) | Sí |  | personas_padrino.id |
| numero_bautismo | integer(32,0) | Sí |  |  |
| observaciones_bautismo | text | No |  |  |
| parroquia_bautismo | character varying(255) | No |  |  |

### `sacramentos_contrayente`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| sexo | character varying(1) | No |  |  |
| libro_bautismo | integer(32,0) | No |  |  |
| folio_bautismo | integer(32,0) | No |  |  |
| numero_bautismo | integer(32,0) | No |  |  |
| fecha_confirmacion | date | No |  |  |
| direccion_residencia | character varying(255) | No |  |  |
| nombre_padre | character varying(255) | No |  |  |
| nombre_madre | character varying(255) | No |  |  |
| edad | integer(32,0) | No |  |  |
| estado_civil | character varying(20) | No |  |  |
| fecha_defuncion_conyuge | date | Sí |  |  |
| certificado_parroquia | character varying(100) | Sí |  |  |
| religion | character varying(50) | No |  |  |
| profesion | character varying(255) | No |  |  |
| acepta_libertad_matrimonio | character varying(2) | No |  |  |
| conoce_unidad_indisolubilidad | character varying(2) | No |  |  |
| conoce_obligaciones_familia | character varying(2) | No |  |  |
| impedimentos_anteriores | character varying(2) | No |  |  |
| dispuesto_cumplir | character varying(2) | No |  |  |
| lugar_despues_matrimonio | text | No |  |  |
| fiel_id | bigint(64,0) | No |  | personas_fiel.id |
| parroquia_bautismo_id | bigint(64,0) | No |  | parroquias_parroquia.id |
| parroquia_confirmacion_id | bigint(64,0) | No |  | parroquias_parroquia.id |
| matrimonio_id | bigint(64,0) | No |  | sacramentos_matrimonio.sacramento_id |

### `sacramentos_documentosacramento`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| descripcion | character varying(255) | No |  |  |
| archivo | character varying(100) | No |  |  |
| subido_en | timestamp with time zone | No |  |  |
| sacramento_id | bigint(64,0) | No |  | sacramentos_sacramento.id |
| subido_por_id | integer(32,0) | Sí |  | auth_user.id |

### `sacramentos_hijoreconocidomatrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo_documento | character varying(2) | No |  |  |
| numero_documento | character varying(30) | No |  |  |
| nombre | character varying(255) | No |  |  |
| fecha_nacimiento | date | Sí |  |  |
| edad | integer(32,0) | No |  |  |
| bautizado | character varying(2) | No |  |  |
| matrimonio_id | bigint(64,0) | No |  | sacramentos_matrimonio.sacramento_id |

### `sacramentos_historialsacramento`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| accion | character varying(20) | No |  |  |
| descripcion | text | No |  |  |
| fecha | timestamp with time zone | No |  |  |
| sacramento_id | bigint(64,0) | No |  | sacramentos_sacramento.id |
| usuario_id | integer(32,0) | Sí |  | auth_user.id |

### `sacramentos_matrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| sacramento_id | bigint(64,0) | No | Sí | sacramentos_sacramento.id |
| expediente | integer(32,0) | No |  |  |
| fecha_declaracion | date | No |  |  |
| dispensa_autoridad | character varying(255) | No |  |  |
| dispensa_impedimento | character varying(2) | No |  |  |
| documento_dispensa | character varying(100) | Sí |  |  |
| fecha_dispensa | date | Sí |  |  |
| impedimentos | text | No |  |  |

### `sacramentos_notamarginalmatrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| matrimonio_id | bigint(64,0) | No | Sí | sacramentos_matrimonio.sacramento_id |
| parroquia_licencia | character varying(255) | No |  |  |
| delegacion_licencia | character varying(255) | No |  |  |
| parroco_delega | character varying(255) | No |  |  |
| presencio | character varying(255) | No |  |  |
| doy_fe | character varying(255) | No |  |  |
| parroco | character varying(255) | No |  |  |
| fecha_licencia | date | No |  |  |
| fecha_matrimonio | date | No |  |  |
| fecha_envio_acta | date | No |  |  |
| hora_matrimonio | time without time zone | No |  |  |

### `sacramentos_padrinomatrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo_documento | character varying(2) | No |  |  |
| cedula | character varying(30) | No |  |  |
| nombre | character varying(255) | No |  |  |
| religion | character varying(100) | No |  |  |
| estado_civil | character varying(20) | No |  |  |
| profesion | character varying(100) | No |  |  |
| matrimonio_id | bigint(64,0) | No |  | sacramentos_matrimonio.sacramento_id |

### `sacramentos_partidaeliminada`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo | character varying(20) | No |  |  |
| folio_numero | integer(32,0) | Sí |  |  |
| numero | integer(32,0) | Sí |  |  |
| fecha | date | Sí |  |  |
| fecha_registro | date | Sí |  |  |
| fiel_nombre | character varying(255) | No |  |  |
| resumen | text | No |  |  |
| motivo | text | No |  |  |
| eliminado_en | timestamp with time zone | No |  |  |
| eliminado_por_id | integer(32,0) | Sí |  | auth_user.id |
| libro_id | bigint(64,0) | Sí |  | parroquias_libro.id |
| parroquia_id | bigint(64,0) | Sí |  | parroquias_parroquia.id |

### `sacramentos_primeracomunion`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| fecha_bautismo | date | Sí |  |  |
| parroquia_bautismo | character varying(255) | No |  |  |
| libro_bautismo | integer(32,0) | Sí |  |  |
| folio_bautismo | integer(32,0) | Sí |  |  |
| numero_bautismo | integer(32,0) | Sí |  |  |
| observaciones_bautismo | text | No |  |  |
| sacramento_id | bigint(64,0) | No | Sí | sacramentos_sacramento.id |
| edad | integer(32,0) | No |  |  |
| bautismo_id | bigint(64,0) | Sí |  | sacramentos_bautismo.sacramento_id |
| doy_fe_id | bigint(64,0) | No |  | parroquias_ministro.id |
| madre_id | bigint(64,0) | Sí |  | personas_madre.id |
| municipio_bautismo_id | bigint(64,0) | Sí |  | ubicacion_municipio.id |
| padre_id | bigint(64,0) | Sí |  | personas_padre.id |

### `sacramentos_proclamamatrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| matrimonio_id | bigint(64,0) | No |  | sacramentos_matrimonio.sacramento_id |
| id | bigint(64,0) | No | Sí |  |
| numero | integer(32,0) | No |  |  |
| fecha_proclama | date | No |  |  |
| resultado | character varying(20) | No |  |  |
| observaciones | text | No |  |  |

### `sacramentos_sacramento`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo | character varying(20) | No |  |  |
| numero | integer(32,0) | No |  |  |
| fecha | date | No |  |  |
| fiel_id | bigint(64,0) | Sí |  | personas_fiel.id |
| folio_id | bigint(64,0) | No |  | parroquias_folio.id |
| ministro_id | bigint(64,0) | Sí |  | parroquias_ministro.id |
| parroquia_id | bigint(64,0) | Sí |  | parroquias_parroquia.id |
| fecha_registro | date | No |  |  |
| creado_en | timestamp with time zone | No |  |  |
| modificado_en | timestamp with time zone | No |  |  |
| creado_por_id | integer(32,0) | Sí |  | auth_user.id |
| modificado_por_id | integer(32,0) | Sí |  | auth_user.id |
| estado | character varying(10) | No |  |  |
| observaciones | text | No |  |  |
| libro_id | bigint(64,0) | No |  | parroquias_libro.id |

### `sacramentos_testigomatrimonio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| tipo_documento | character varying(2) | No |  |  |
| cedula | character varying(30) | No |  |  |
| nombre | character varying(255) | No |  |  |
| religion | character varying(100) | No |  |  |
| estado_civil | character varying(20) | No |  |  |
| profesion | character varying(100) | No |  |  |
| matrimonio_id | bigint(64,0) | No |  | sacramentos_matrimonio.sacramento_id |

## `sessions` — Sesiones

### `django_session`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| session_key | character varying(40) | No | Sí |  |
| session_data | text | No |  |  |
| expire_date | timestamp with time zone | No |  |  |

## `ubicacion` — Ubicacion

### `ubicacion_departamento`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| pais_id | bigint(64,0) | No |  | ubicacion_pais.id |

### `ubicacion_municipio`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
| departamento_id | bigint(64,0) | No |  | ubicacion_departamento.id |

### `ubicacion_pais`

| Columna | Tipo | Nulo | PK | FK |
| --- | --- | --- | --- | --- |
| id | bigint(64,0) | No | Sí |  |
| nombre | character varying(100) | No |  |  |
