Fuente: Código de Derecho Canónico (vatican.va). Tipos de regla en la app:
- BLOQUEA: no se puede guardar.
- BLOQUEA SALVO DISPENSA: solo se guarda si se registra la dispensa.
- ADVIERTE: se guarda solo si el usuario marca "Verificado / excepción autorizada" y escribe el motivo; queda en HistorialSacramento.
- RECUERDA: solo informa.
Las edades son configurables en settings (desde .env) porque la Conferencia Episcopal o la diócesis pueden fijar otras.

## General
- Quien no ha recibido el bautismo no puede ser admitido válidamente a los demás sacramentos (c. 842 §1). Para Primera Comunión, Confirmación y Matrimonio, el bautismo debe constar: enlazado a una partida de este sistema o con los datos externos completos (fecha, parroquia, libro, folio y número).
- Bautismo y confirmación no se repiten (c. 845 §1).

## Bautismo
- B1 BLOQUEA: la persona ya tiene un bautismo ACTIVO o CORREGIDO (c. 864). [ya implementado]
- B2 BLOQUEA: padrino o madrina que sea el padre o la madre del bautizado, o el bautizado mismo (c. 874 §1, 5°). [ya implementado]
- B3 BLOQUEA: más de un padrino o más de una madrina (c. 873). [estructural]
- B4 BLOQUEA: sin padrino ni madrina y sin testigo (c. 875). [ya implementado]
- B5 ADVIERTE: padrino o madrina con menos de EDAD_MINIMA_PADRINO (16) en la fecha del bautismo, si se conoce su fecha de nacimiento (c. 874 §1, 2°: el párroco puede admitir excepción por causa justa).
- B6 ADVIERTE: padrino o madrina que esté en el sistema sin confirmación o sin primera comunión registradas (c. 874 §1, 3°; puede haberlas recibido en otra parroquia).
- B7 ADVIERTE: bautizado menor de EDAD_USO_RAZON (7) sin padre ni madre registrados (c. 868 §1, 1°).
- B8 RECUERDA: bautizado de EDAD_USO_RAZON o más es bautismo de adulto: requiere catecumenado (c. 865 §1) y debe confirmarse y comulgar enseguida (c. 866).

## Primera Comunión
- P1 BLOQUEA: sin bautismo que conste (c. 842, 912).
- P2 BLOQUEA: ya tiene una primera comunión ACTIVA o CORREGIDA.
- P3 BLOQUEA: fecha anterior a la del bautismo o a la de nacimiento.
- P4 ADVIERTE: menor de EDAD_USO_RAZON (7) en la fecha (c. 914; c. 97 §2).
- P5 RECUERDA: confesión sacramental previa (c. 914); la app no registra confesiones.

## Confirmación
- C1 BLOQUEA: sin bautismo que conste (c. 889 §1).
- C2 BLOQUEA: ya tiene una confirmación ACTIVA o CORREGIDA (c. 889 §1, 845).
- C3 BLOQUEA: fecha anterior a la del bautismo.
- C4 ADVIERTE: menor de EDAD_MINIMA_CONFIRMACION (por defecto 7, edad de la discreción; c. 891).
- C5 Padrino: mismas reglas B2, B5 y B6 (c. 893 §1). RECUERDA y sugiere como padrino al del bautismo si existe (c. 893 §2).
- La primera comunión NO es requisito para confirmarse; no se valida el orden.

## Matrimonio (cada contrayente)
- M1 BLOQUEA: tiene un matrimonio ACTIVO o CORREGIDO registrado sin constancia de nulidad, disolución o muerte del cónyuge (ligamen, c. 1085).
- M2 BLOQUEA: es ministro con cargo de diácono, presbítero u obispo (orden sagrado, c. 1087).
- M3 BLOQUEA: consanguinidad detectable con los bautismos registrados: hermanos (mismo padre o misma madre) o padre/madre e hijo (c. 1091). Otros grados no se detectan.
- M4 BLOQUEA SALVO DISPENSA: varón menor de 16 o mujer menor de 14 en la fecha (c. 1083 §1).
- M5 ADVIERTE: menor de EDAD_LICITA_MATRIMONIO (configurable, por defecto 18; c. 1083 §2 y c. 1072; además rige la ley civil).
- M6 BLOQUEA SALVO DISPENSA: uno de los contrayentes sin bautismo que conste (disparidad de cultos, c. 1086).
- M7 ADVIERTE: contrayente sin confirmación que conste (c. 1065 §1).
- M8 ADVIERTE: sin proclamas registradas ni dispensa de proclamas (c. 1067).
- M9 BLOQUEA: menos de dos testigos (c. 1108). Contrayentes de distinto sexo (ya existe).
- RECUERDA: se recomienda la penitencia y la Eucaristía antes del matrimonio (c. 1065 §2).

Al registrar cada sacramento, las anotaciones marginales siguen las reglas de docs/libros_parroquiales.md (c. 535 §2, 895, 1122).
