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
