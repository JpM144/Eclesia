=== ESPECIFICACIÓN ===
1. core/choices.py
   - TipoAnotacionMarginal: CONFIRMACION, MATRIMONIO, ORDEN_SAGRADO, PROFESION_RELIGIOSA, CAMBIO_RITO, ADOPCION, DEFUNCION, CORRECCION, OTRO.
   - EstadoAnotacion: ANOTADA ("Anotada"), POR_COMUNICAR ("Por comunicar"), COMUNICADA ("Comunicada"). Nada más.
   - AccionHistorial y ResultadoProclama: como están.
2. DatosBautismoMixin (abstracto), todo opcional:
   - bautismo: FK a Bautismo, null/blank, PROTECT, related_name="%(class)s_set". Se usa cuando el bautismo está registrado en este sistema.
   - Para bautismos de otra parroquia: fecha_bautismo (DateField), parroquia_bautismo (CharField, texto), municipio_bautismo (FK a Municipio, null/blank, PROTECT), libro_bautismo, folio_bautismo, numero_bautismo, observaciones_bautismo.
   - SIN el campo "bautizado".
3. Confirmacion: usa el mixin. padre, madre, padrino y madrina opcionales (null=True, blank=True, PROTECT). Conserva edad y doy_fe. Sin ningún campo de grupo de catequesis.
4. PrimeraComunion: OneToOne primary_key hacia Sacramento (CASCADE), usa el mixin, padre y madre opcionales (PROTECT), conserva edad y doy_fe si los tiene. SIN padrino, madrina, catequista ni grupo de catequesis.
5. AnotacionMarginal:
   - sacramento: FK a Sacramento, CASCADE, null/blank (el bautismo donde se anota, si está en este sistema).
   - sacramento_origen: FK a Sacramento, SET_NULL, null/blank, related_name="anotaciones_generadas" (reemplaza a sacramento_relacionado).
   - tipo (TipoAnotacionMarginal), fecha, descripcion, estado (EstadoAnotacion, default POR_COMUNICAR).
   - parroquia_destino (FK a Parroquia, null/blank, PROTECT), parroquia_destino_texto (CharField blank), fecha_comunicacion (DateField null/blank), creado_en (auto_now_add).
   - CheckConstraints: si estado es ANOTADA, sacramento no puede ser nulo; si estado es COMUNICADA, fecha_comunicacion no puede ser nula.
6. HistorialSacramento y sacramentos/services.py: se quedan como están, incluida la firma registrar_historial(sacramento, accion, descripcion="", usuario=None).
7. DocumentoSacramento: sacramento (CASCADE), descripcion, archivo (upload_to="documentos_sacramentos/"), subido_por (FK a User, SET_NULL, null/blank), subido_en (auto_now_add; reemplaza al campo fecha). DocumentoMatrimonio desaparece: migración de datos que copia sus filas a DocumentoSacramento (el Sacramento es el mismo PK del Matrimonio) y después elimina el modelo, su admin y sus tests. NotaMarginalMatrimonio NO se toca.
8. ProclamaMatrimonio: id propio, matrimonio (FK CASCADE, related_name="proclamas"), numero (PositiveIntegerField), fecha_proclama, resultado (ResultadoProclama), observaciones (TextField blank). UniqueConstraint (matrimonio, numero).
9. Matrimonio: conserva dispensa_impedimento, impedimentos, dispensa_autoridad y fecha_dispensa. Agrega documento_dispensa (FileField null/blank, upload_to="dispensas/"). clean(): si hay dispensa, impedimentos y dispensa_autoridad son obligatorios.
10. Grupos de catequesis: eliminar parroquias.GrupoCatequesis por completo (modelo, constraint, admin, tests, menciones en README) y cualquier campo que lo referencie.
11. Admin registrado para PrimeraComunion, AnotacionMarginal, HistorialSacramento y DocumentoSacramento. El dashboard sigue contando Primera Comunión.
12. Sacramento libros parroquiales: libro y folio son FK obligatorias a parroquias.Libro/parroquias.Folio con on_delete=PROTECT; el número de la partida es «numero». Unicidad con `unico_numero_por_libro` (libro, numero) con mensaje en español ya definido. El `clean()` de Sacramento (sacramentos/models.py) valida: el folio pertenece al libro, no se inscriben partidas en libros cerrados (solo al crear), la fecha_registro está entre fecha_apertura y fecha_cierre del libro y el tipo de libro corresponde al tipo de sacramento. La gestión de libros (apertura, cierre, diligencias, índice y folios) se describe en docs/libros_parroquiales.md.
=== FIN ESPECIFICACIÓN ===

=== IMPLEMENTADO: REGISTRO DE BAUTISMOS ===
Pantallas (namespace `sacramentos`):
- Lista `sacramentos:bautismo_lista` = `/sacramentos/bautismos/` (BautismoListView, paginado 25, `?q=` por fiel/número, sin N+1).
- Registro `sacramentos:bautismo_crear` = `/sacramentos/bautismos/nuevo/` (BautismoCreateView + BautismoForm).
- Ficha `sacramentos:bautismo_detalle` = `/sacramentos/bautismos/<pk>/` (BautismoDetailView; el pk es el del Bautismo = pk del Sacramento).
- Corregir `sacramentos:bautismo_editar` = `/sacramentos/bautismos/<pk>/editar/` (BautismoUpdateView + BautismoEditarForm, motivo obligatorio).
- Anular `sacramentos:bautismo_anular` = `/sacramentos/bautismos/<pk>/anular/` (BautismoAnularView + MotivoForm).
- Eliminar `sacramentos:bautismo_eliminar` = `/sacramentos/bautismos/<pk>/eliminar/` (BautismoEliminarView + MotivoForm; solo si `puede_eliminarse`).

Formulario `BautismoForm` (sacramentos/forms.py, forms.Form plano): select de libros de BAUTISMOS abiertos; valida rango apertura/cierre, tipo de libro, can. 875 (testigo obligatorio si no hay padrino ni madrina), documentos normalizados (CC/TI/RC solo dígitos) y padre/madre obligatorios. El folio y la fecha de registro NO son campos del formulario: se asignan automáticamente al guardar. Mapeo: `ministro`→Sacramento.ministro, `quien_firma`→Bautismo.quien_firma, `doy_fe`→Bautismo.doy_fe (por defecto el párroco de la parroquia del libro), `observaciones`→Sacramento.observaciones. `datos_para_servicio()` entrega el diccionario anidado que consume el servicio.

Formularios de corrección/anulación/eliminación: `MotivoForm` (campo `motivo` obligatorio) y `BautismoEditarForm(BautismoForm)` (añade `motivo`, deja el libro fijo/solo lectura y precarga los datos actuales de la partida). Ninguno permite editar libro, folio, número ni fecha_registro.

Servicio `sacramentos.services.registrar_bautismo(datos, usuario)`: dentro de `transaction.atomic`; crea o reutiliza (sin sobrescribir) Fiel/Padre/Madre/Padrino/Madrina; número con `siguiente_numero_partida(libro)`, **folio con `parroquias.services.folio_para_nueva_partida(libro)`** y **`fecha_registro = timezone.localdate()`**; `full_clean()` de Sacramento y Bautismo; historial con `AccionHistorial.CREACION`; devuelve `(bautismo, reutilizadas)`.

Servicios `corregir_bautismo`, `anular_bautismo` y `eliminar_bautismo` (todos `@transaction.atomic`, con motivo obligatorio):
- `corregir_bautismo`: vuelca los datos editados; los nombres y documentos de las personas ya vinculadas son de solo lectura (se corrigen desde su ficha) y `_sincronizar_personas` solo actualiza los datos mutables del bautizado (fecha y municipio de nacimiento, teléfono y sexo); no cambia libro/folio/número/fecha_registro; pasa la partida a `CORREGIDO` si estaba ACTIVO; añade historial `CORRECCION` y una `AnotacionMarginal` de tipo CORRECCION. Bloquea partidas ANULADAS.
- `anular_bautismo`: pasa la partida a `ANULADO` (sigue ocupando su lugar en el libro); añade historial `ANULACION` y anotación CORRECCION. Bloquea partidas ya anuladas.
- `eliminar_bautismo`: solo si `puede_eliminarse(bautismo)` —partida ACTIVA, última del libro (número más alto), con `fecha_registro` de hoy y sin anotaciones marginales (ni como partida anotada ni como origen)—; las partidas anuladas o corregidas nunca se eliminan (quedan como constancia). Guarda una copia en `PartidaEliminada` (snapshot con motivo y usuario) y borra el `Sacramento` (cascada de Bautismo, historial y anotaciones). Al eliminar la última partida se liberan su número y folio, y el siguiente registro los reutiliza sin dejar huecos. La partida eliminada no se puede recuperar desde la app. `motivo_no_eliminable` devuelve el mensaje exacto de cada condición.

Folio automático (parroquias): `Libro.partidas_por_folio` (1–20, por defecto 3) indica cuántas partidas caben en cada folio. `folio_para_nueva_partida(libro)` reutiliza el último folio hasta llenarlo (`partidas_por_folio` alcanzadas, contando también las anuladas), pasa al siguiente y crea el `Folio` si no existe. Si supera `Libro.total_folios`, lanza `ValidationError` ("El libro está lleno…").

Reglas de estado: `ACTIVO` (verde), `CORREGIDO` (info), `ANULADO` (danger) y `ARCHIVADO` (secundario). Las partidas anuladas no cuentan en el dashboard (`resumen_dashboard`) ni aparecen en el índice del libro (`indice_libro`). Desde la ficha solo se muestra Editar/Anular en estados editables y Eliminar únicamente cuando se cumple `puede_eliminarse` (la misma regla que valida la vista y el servicio).

Endpoint de autocompletado `personas:api_persona` = `GET /personas/api/persona/?rol=fiel|padre|madre|padrino&tipo=CC&numero=…`: 400 si faltan datos, 404 si no existe, 200 con `{encontrado, nombres, apellidos}` y, solo para `rol=fiel`, además `{fecha_nacimiento, municipio, sexo}`. El navegador usa `static/js/buscar_persona.js` (solo `textContent`/`value`). Se conservan `personas:api_padre` y `personas:api_madre`.

Integración: sidebar con "Bautismos" habilitado (`sacramentos:bautismo_lista`); dashboard con "Crear Bautismo" (`sacramentos:bautismo_crear`); enlaces al detalle desde `personas/consultas.py` (`url_detalle`), `personas/templates/personas/consultar.html` y `ficha.html`.
=== FIN IMPLEMENTADO ===
