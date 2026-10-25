# Normas para las partidas: Conferencia Episcopal de Colombia y Código de Derecho Canónico

Este documento es la referencia normativa del sistema. Antes de construir o cambiar cualquier libro, partida, aviso o certificado, se lee junto con `docs/requisitos_sacramentos.md` y `docs/libros_parroquiales.md`. Si algo de esos dos choca con este, manda este.

## 0. Orden de prioridad de las fuentes

1. **Código de Derecho Canónico (CIC 1983)**: obligaciones universales de registro.
2. **Conferencia Episcopal de Colombia (CEC)**: modelos de partidas, instrucciones de libros parroquiales y normas complementarias para Colombia.
3. **Diócesis** (en este caso, Ocaña): procedimientos concretos de corrección, inserción y expedición. Se configuran, no se programan fijos.
4. **Ley colombiana**: Concordato de 1973 (efectos civiles del matrimonio) y Ley 1581 de 2012 (datos personales).

Aclaración importante: la CEC no expide partidas. Las expide la parroquia donde está el libro, y las autentica la curia de la diócesis.

## 1. Fuentes consultadas

| Fuente | Qué aporta | Estado |
|---|---|---|
| CEC, *Libros parroquiales* (instrucciones de 1913, modelos de la Conferencia de 1930), nn. 302-336 | Libros obligatorios, reglas de escritura, modelos de partida de bautismo, confirmación, información matrimonial, proclamas, matrimonio, **aviso de matrimonio**, defunción y certificación de partidas | Leído completo (PDF de la CEC) |
| CEC, *Subsanación de omisiones o errores en los registros parroquiales* (Conferencia de 1927), arts. 1-8 | Cómo se corrige una partida o se inserta una omitida: solo por decisión de la curia, con nota marginal | Leído completo (incluido en el mismo PDF) |
| CEC, *Normas complementarias para Colombia* (1986; versión vigente aprobada en 2012 y promulgada en febrero de 2015: un decreto de 43 artículos, uno por canon) | Concreciones para Colombia de los cánones que remiten a la Conferencia (c. 535 §1, 788, 877 §3, 891, 1067, 1083 §2, 1126…) | **El texto completo no está publicado en internet.** Hay que conseguir el libro *Legislación canónica: Normas complementarias para Colombia* (CEC, 105 págs.) en la librería de la CEC o en la curia de Ocaña |
| CEC, *Expediente matrimonial* (aprobado en la Asamblea Plenaria de julio de 2019, con base en el art. 26 de las Normas complementarias y el c. 1067) | Formularios del expediente previo al matrimonio | Se vende en la librería de la CEC; su contenido no está en línea |
| CEC, *Política de tratamiento y protección de datos personales* (2 de septiembre de 2024) | Principios, autorización, datos sensibles, menores, seguridad, conservación | Leído completo (PDF de la CEC) |
| CIC cc. 535, 875-878, 894-896, 1108, 1121-1123, 1182 | Datos obligatorios y anotaciones | Verificado en vatican.va |
| Arquidiócesis de Medellín, *Reforma de partidas* | Documentos que exige la curia para reformar o insertar cada tipo de partida; "certificado de no existencia" | Consultado |
| Diócesis de Jericó, *Curia* | Inscripción de partidas omitidas, reconocimiento, legitimación, adopción | Consultado |
| Arquidiócesis de Bogotá, Delegación para las causas de partidas | Historia del procedimiento (decreto CEC 1927, decretos arquidiocesanos 1980-1986) | Consultado |
| Concordato Colombia-Santa Sede (1973), art. VII y Protocolo final | Efectos civiles del matrimonio canónico y su inscripción en el registro civil | Consultado |
| Ley 1581 de 2012, arts. 5, 6, 7, 10, 17 | Datos sensibles (creencias religiosas), excepción para organismos religiosos, menores, seguridad | Consultado |

## 2. Reglas generales de los libros (CEC 1913, n. 303; c. 535)

**Libros obligatorios.** El c. 535 §1 exige como mínimo bautizados, matrimonios y difuntos, más los que mande la Conferencia o el obispo. La CEC (1913) enumera como principales: Bautismos, Confirmaciones, Informaciones (matrimoniales), Matrimonios, Defunciones, Padrón e Inventarios; y como auxiliar, entre otros, el **Copiador de comunicaciones**.

- La Primera Comunión **no** es libro canónico obligatorio. Muchas parroquias la llevan, pero su constancia es más sencilla.
- El libro de Defunciones **sí** es obligatorio (c. 535 §1 y c. 1182). Hoy la app no lo tiene.

**Reglas de escritura (CEC 1913, n. 303, letras c-h):**

| Regla | Qué significa en la app |
|---|---|
| c) Partidas numeradas en orden cronológico | Ya está: número correlativo por libro |
| d) Sin abreviaturas ni enmendaduras; si hay enmienda, se salva con nota al final antes de la firma | Corrección el mismo día = enmienda salvada (queda en historial). Otro día = ya no es enmienda: va por la curia (ver §9) |
| e) Margen izquierdo para anotaciones | Las anotaciones marginales son un bloque propio de la partida, no un campo de texto libre |
| g) **El libro no contiene observaciones ni datos de otro género** | **Se elimina el campo "Observaciones".** Lo que antes iba ahí se registra como anotación marginal con tipo |
| h) Prohibido el facsímil de firma | Las copias impresas llevan línea de firma en blanco y sello; nunca una imagen de firma |
| Fechas con todas sus letras (advertencia 1 del modelo de bautismo) | En la copia impresa, la fecha del sacramento va en letras ("veintiocho de abril de dos mil veintiséis") |

**Firma de la partida.** Los modelos terminan en "Doy fe. (Firma del Párroco)". Quien firma la partida es quien da fe. **En la app, "ministro que firma" y "quien da fe" son el mismo dato: un solo campo, "Da fe".** El ministro que celebró el sacramento es otro campo distinto.

**Sello y firma de certificados (c. 535 §3).** Todo certificado sobre el estado canónico lleva firma del párroco o su delegado y el sello parroquial.

**Archivo (c. 535 §4-5).** Los libros se guardan en archivo y no pueden caer en manos ajenas. En la app esto se traduce en acceso solo con sesión, permisos y respaldo (ver §11).

## 3. Bautismo

**Datos obligatorios (c. 877 §1):** nombre del bautizado, ministro, padres, padrinos y testigos si los hubo, lugar y fecha del bautismo, y lugar y fecha de nacimiento.

**Decisión del proyecto: el bautismo solo lleva padrinos, no testigo.** El testigo es propio del matrimonio (c. 1108). El c. 875 admite un testigo cuando falta padrino, pero el modelo de la CEC (n. 304) solo nombra padrinos. Por eso la regla B4 cambia a: **BLOQUEA si no hay padrino ni madrina**. Lo mismo para Confirmación: solo padrino o madrina.

**Modelo CEC (1913/1930, n. 304):** "En la Parroquia de… a… de… de…, fue bautizado (solemnemente / privadamente / supliéronse las ceremonias) por… un niño a quien se llamó N…, nacido el…, hijo de N.N. y N.N. Abuelos paternos… Maternos… Padrinos… Doy fe. (Firma del Párroco)".

- Los **abuelos** forman parte del modelo colombiano. La app ya los tiene.
- Se indica si fue **bajo condición** o si **solo se suplieron las ceremonias** (n. 304, advertencia d).
- Hijo de madre soltera: el padre se inscribe solo si la paternidad consta por documento público o declaración ante el párroco y dos testigos (c. 877 §2). Las palabras "ilegítimo" o "natural" no se escriben (CEC n. 304 b).
- Adopción: se inscriben los adoptantes y, si el registro civil lo hace, los padres naturales según la Conferencia (c. 877 §3). La app ya oculta los biológicos en las copias.
- Si el bautismo no lo hizo el párroco, el ministro le avisa para que lo anote (c. 878).

**Anotaciones obligatorias en la partida de bautismo (c. 535 §2):** confirmación, matrimonio, adopción, orden sagrado, profesión perpetua y adscripción a otra Iglesia *sui iuris*. También la nulidad, disolución o convalidación del matrimonio (c. 1123) y las legitimaciones (CEC 1927, art. 7).

## 4. Confirmación

**Datos (c. 895):** nombre del confirmado, ministro, padres, padrinos, lugar y día.

**Modelo CEC (n. 305):** como se confirma en tandas durante la visita pastoral, la CEC usó **una sola partida por celebración** con tabla: N.°, nombre del confirmado, padres, padrino y **lugar del bautismo**. La app puede seguir con partidas individuales, pero conviene permitir registrar una celebración con varios confirmados a la vez.

**Aviso (c. 895; CEC n. 305):** si el confirmado fue bautizado en otra parroquia, se avisa al párroco del bautismo para que haga la anotación. Si fue bautizado en la misma parroquia, la anotación se hace directamente.

## 5. Primera Comunión

No tiene libro obligatorio (c. 535 §1) ni modelo de partida en la CEC: **no hay partida de Primera Comunión.** Por decisión del proyecto, **la app no maneja Primera Comunión**: no hay libro, registro, partida ni copia.

Consecuencia en las reglas: el c. 874 §1, 3° pide que el padrino haya recibido la Eucaristía. Como la app no lo registra, esa parte de la regla B6 pasa a RECUERDA ("Verifica que el padrino haya recibido la Primera Comunión"). La parte de la confirmación sigue como ADVIERTE.

## 6. Matrimonio

**Datos (c. 1121 §1):** nombres de los cónyuges, del asistente y de los testigos, lugar y fecha.

**Modelo CEC (n. 329):** "En la Parroquia de… a… de… de…, cumplidas las prescripciones canónicas (y dispensado el impedimento de…, si lo hubo), presencié el matrimonio que contrajo N.N. (viudo de…, si es el caso), hijo de N.N. y N.N., bautizado en… el…, con N.N., hija de N.N. y N.N., bautizada en… el… Testigos… Doy fe."

- Cada contrayente lleva **lugar y fecha de su bautismo** (o su edad, si no se sabe la fecha).
- Si hubo **dispensa**, se dice cuál.
- **Legitimación de hijos:** si los contrayentes declaran hijos nacidos antes, se escriben en el acta y se avisa a la parroquia de bautismo de cada hijo (CEC n. 329 nota 4; CEC 1927, art. 7).
- Hay que expedir **libertad canónica** y la **información matrimonial** previa (nn. 306-309, 323). Hoy el expediente vigente es el de la CEC de 2019.
- **Proclamas:** tres días festivos; si los contrayentes son de distintas parroquias, en ambas; si no se casan en dos meses, se repiten (nn. 310-316). La app ya registra proclamas.

**Aviso de matrimonio, obligatorio (c. 1122; CEC n. 330).** Modelo: "En cumplimiento de lo prescrito en el canon…, aviso a usted que N.N., hijo de N.N. y N.N., bautizado en… el…, contrajo matrimonio en esta parroquia el día… con N.N., hija de N.N. y N.N., bautizada en… el día… Fueron testigos N.N. y N.N. (Firma del Párroco) (Sello parroquial)".

- Por cada contrayente bautizado en **otra** parroquia se genera un aviso dirigido a su párroco.
- Si fue bautizado en **esta** parroquia, se hace la anotación marginal en su partida de bautismo.

**Efectos civiles (Concordato 1973, art. VII y Protocolo final).** El Estado reconoce efectos civiles al matrimonio canónico. La autoridad eclesiástica envía copia auténtica del acta al funcionario del registro civil para que la inscriba. Si no se inscribió a tiempo, cualquiera de los cónyuges o un interesado puede pedir la inscripción después. La app debe permitir registrar si se envió la copia al registro civil, cuándo y a qué notaría o registraduría.

**Edad.** Canónicamente: varón 16, mujer 14 (c. 1083 §1), y la Conferencia puede fijar una edad mayor para la licitud (c. 1083 §2). En lo civil, la Corte Constitucional declaró inexequibles en febrero de 2025 los artículos del Código Civil que permitían casarse a menores de 18. Como el matrimonio canónico tiene efectos civiles, la app debe advertir con fuerza a cualquier contrayente menor de 18.

## 7. Defunción (libro nuevo)

**Base:** c. 535 §1 (libro de difuntos obligatorio) y c. 1182 (terminado el entierro, se anota en el libro según el derecho particular).

**Modelo CEC (n. 331):** "En la Parroquia de…, a…, fue sepultado canónicamente el cadáver de…, de… años de edad, hijo de… (viudo de…, casado con… o soltero). Murió de… en esta parroquia (o en la Parroquia de…), el… El Pbro. N.N. le administró los sacramentos de… Doy fe."

**Notas del modelo:**
- a) Si es párvulo, se omiten los datos que no aplican.
- b) La partida se asienta **aunque no se hayan celebrado exequias**.
- c) Si la persona murió ahogada y no apareció el cuerpo, se asienta si consta la muerte.
- d) También se asienta la de quienes mueren fuera de la Iglesia.

**Causa de muerte.** El modelo de 1930 pedía la enfermedad. **Por instrucción del proyecto y para no guardar datos de salud (dato sensible, Ley 1581 art. 5), la app solo registra "Natural" o "Violenta".**

**Datos propuestos:** difunto (documento, nombres), edad, estado civil (soltero, casado con…, viudo de…), padres, fecha y lugar de la muerte, causa (natural o violenta), fecha de las exequias o de la sepultura, cementerio, sacramentos recibidos, ministro de las exequias, registro civil de defunción (número de serial) y quien da fe.

**Para reformar o insertar una defunción**, la curia pide el registro civil de defunción y las partidas de bautismo y matrimonio del difunto (Medellín).

## 8. Avisos y correspondencia entre parroquias

La CEC prevé un **Copiador de comunicaciones** (n. 303) y exige que toda comunicación oficial lleve sello (n. 319). Los avisos obligatorios son:

| Hecho | A quién se avisa | Norma |
|---|---|---|
| Confirmación de alguien bautizado en otra parroquia | Párroco del bautismo | c. 895; CEC n. 305 |
| Matrimonio de alguien bautizado en otra parroquia | Párroco del bautismo | c. 1122 §2; CEC n. 330 |
| Bautismo hecho por alguien distinto del párroco | Párroco del lugar | c. 878 |
| Nulidad, disolución o convalidación | Párroco del matrimonio, que anota en matrimonio y bautismo | c. 1123 |
| Legitimación de hijos bautizados en otra parroquia | Párroco del bautismo de cada hijo | CEC n. 329 nota 4 |

**En la app:** un módulo **Correspondencia** con avisos **enviados** (generados automáticamente con su carta imprimible según el modelo, número consecutivo, fecha, parroquia de destino, estado: por enviar, enviado, acuse recibido) y **recibidos** (aviso que llega de otra parroquia: se registra y genera la anotación marginal en la partida de bautismo de aquí).

## 9. Correcciones, inserciones y reformas (CEC 1927)

| Caso | Quién decide | Cómo queda en el libro |
|---|---|---|
| Error detectado **antes de firmar** (mismo día) | El párroco | Enmienda salvada al final, antes de la firma (n. 303 d) |
| Error en una partida ya asentada | El Provisor u Ordinario (curia), a solicitud del párroco o del interesado y con documentos | Se inserta el decreto o sentencia en la fecha de su recepción y se pone **nota al margen** de la partida reformada (art. 4) |
| Partida omitida | La curia, con solicitud, dos testigos y pruebas | Se inscribe la sentencia en la fecha en que se recibe y se anota la referencia al margen del lugar donde debió estar (arts. 1-3) |
| Partida sin firma | Aviso inmediato al prelado | Lo que disponga (art. 6) |

**Decisión del proyecto.** Aunque la CEC (1927) reserva a la curia la corrección de una partida ya asentada, **la app mantiene el flujo actual**: el párroco corrige con motivo obligatorio. Si es el mismo día, queda en el historial. Si es otro día, la partida pasa a CORREGIDA con anotación marginal. Esta diferencia con la norma se explica en el README. Si más adelante se pide, se agrega a la corrección un campo opcional con la referencia del decreto de la curia.

**Documentos que exige la curia** (referencia de Medellín, para la lista de anexos sugeridos):
- Reforma de bautismo: partida original, documento de identidad, registro civil y, según el cambio, escritura o sentencia.
- Inserción: solicitud con dos testigos, declaración juramentada, **certificado de no existencia de la partida**, partidas de los hermanos y registro civil.

## 10. Copias, boletas y certificados

| Documento | Qué es | Fuente |
|---|---|---|
| **Partida (copia certificada)**. Reemplaza lo que la app llamaba "certificado de bautismo" | "El infrascrito Cura de la Parroquia de… certifica que en el libro de… correspondiente al año…, folio… y bajo el número…, se encuentra una partida que a la letra dice: (copia). Expedido en… a…" | CEC n. 332 |
| **Boleta (partida reducida)** | Versión corta con los datos esenciales, para trámites que no exigen la copia completa | Práctica parroquial; instrucción del proyecto. Para Bautismo, Confirmación, Matrimonio y Defunción |
| **Certificado de inexistencia** (no existencia) | Constancia de que, revisados los libros, no se encontró la partida buscada. Lo exigen las curias para insertar partidas | Medellín, Jericó |
| **Certificado de libertad canónica** | Que la persona no ha contraído matrimonio en la parroquia (o enviudó) | CEC n. 323 |

- Todos llevan firma del párroco o su delegado y sello (c. 535 §3).
- La copia certificada incluye las anotaciones marginales.
- Las curias autentican partidas con una vigencia que cada una fija (Medellín: 90 días). La app muestra la fecha de expedición; la vigencia es configurable.
- La partida eclesiástica de bautismo es **prueba supletoria del estado civil** para quienes nacieron antes de la Ley 92 de 1938. Por eso estas copias tienen peso legal y hay que cuidar su exactitud.

## 11. Protección de datos (Ley 1581 de 2012 y política de la CEC de 2024)

- Las partidas revelan **creencias religiosas**, que son **dato sensible** (art. 5).
- La parroquia puede tratarlas sin autorización expresa porque es un organismo sin ánimo de lucro con finalidad religiosa, siempre que se trate de sus fieles y que **no se entreguen a terceros sin autorización del titular** (art. 6 c).
  - De ahí que la copia de una partida se registre con solicitante, relación y finalidad. La app ya lo hace.
- **Menores** (art. 7; política CEC n. 14): se trata su información respondiendo a su interés superior y con autorización del representante legal.
- **Seguridad** (art. 17 d; política CEC n. 17): evitar adulteración, pérdida y acceso no autorizado, con trazabilidad y auditoría.
  - En la app: sesión obligatoria, historial de cambios, respaldo y archivos adjuntos privados.
- **Acceso restringido** (política CEC n. 6): los datos personales no pueden estar disponibles en internet salvo con acceso técnicamente controlado.
  - Respaldo en Supabase con RLS y sin API pública.
- **Encargado fuera de Colombia:** Supabase guarda los datos en Estados Unidos. Eso es una transmisión a un encargado, que la ley permite con un acuerdo que obligue a proteger los datos (política CEC n. 16). Hay que dejarlo documentado.
- **Aviso de privacidad** (Anexo 1 de la política): la app debe mostrarlo en el registro de usuarios y en el pie de la solicitud de copias.
- **Conservación** (política CEC n. 22): los datos se conservan mientras haya deber legal. Los libros parroquiales se conservan siempre (c. 535 §5), así que no se borran partidas; solo se anulan con nota.

## 12. Anexos por persona

Cuando una persona tiene partidas en otras parroquias (bautismo fuera, matrimonio fuera, etc.), se guardan como **anexos de esa persona**: tipo de partida, parroquia, diócesis, libro, folio, número, fecha y el archivo escaneado (PDF o imagen). Sirven de prueba para las reglas C1 y M6 ("bautismo que conste") y para los trámites de la curia.

## 13. Pendiente de confirmar

1. Texto de las **Normas complementarias para Colombia (2015)**, en especial los artículos sobre los cc. 535, 877 §3, 891 (edad de confirmación), 1067 (proclamas y expediente) y 1083 §2 (edad lícita para el matrimonio). Sin ese texto, las edades siguen configurables.
2. Normas de la **Diócesis de Ocaña** sobre corrección de partidas, vigencia de copias y formato de boletas.
3. Formato exacto de la **boleta** que usa la parroquia.

## 14. Decisiones del proyecto (octubre de 2026)

- "Certificado de bautismo" pasa a llamarse **copia de la partida**. Se agrega el **certificado de inexistencia**.
- **Primera Comunión se quita de la app**: no tiene partida (ver §5).
- **Testigos solo en Matrimonio.** Bautismo y Confirmación llevan solo padrino o madrina (ver §3).
- **Boleta = partida reducida**, para Bautismo, Confirmación, Matrimonio y Defunción.
- **Correcciones:** sigue el flujo actual del párroco con motivo (ver §9).
- **Confirmación:** partidas individuales, sin registro por tanda.
- "Ministro que firma" y "Quien da fe" se unen en un solo campo: **Da fe**.
- El campo **Observaciones** desaparece; su contenido pasa a **anotación marginal**.
- **Aviso de matrimonio obligatorio** por cada contrayente bautizado en otra parroquia.
- **Defunción:** causa solo "Natural" o "Violenta".
- **Anexos por persona** con sus partidas de otras parroquias.
- **Filtros de la A a la Z** por apellido en las listas.
