# P0-B — Contrato de clasificación de contactos

Estado: **Hito 1 — investigación técnica y contrato cerrado, corrección legacy pendiente**
Fecha de consulta de fuentes: 2026-08-05
Autor: auditoría técnica TZ Analyzer (asistida)

## 1. Objeto y alcance

Este documento fija el contrato de clasificación de valores de la columna
`contacto` (y, por extensión, `tel` del número investigado) en TZ Analyzer,
con fundamento en especificaciones técnicas primarias — no en convención de
producto arbitraria. Cubre:

- qué constituye un número telefónico plausible para efectos de ranking,
  perfiles y concentración;
- cómo se distingue de identificadores técnicos (IMEI, IMSI, IP, dominio,
  URL, APN, identificador de sesión DATOS);
- el tratamiento de numeración salvadoreña e internacional;
- el tratamiento de autocontacto;
- las limitaciones conocidas de la implementación actual frente al ideal
  normativo.

No cubre la implementación (eso vive en `tz_core/bitacora_normalization.py`
y se referencia aquí solo para trazar cumplimiento). No sustituye criterio
investigativo humano: el sistema clasifica *plausibilidad estructural*, no
identidad real del titular de un número.

## 2. Fuentes consultadas

| Fuente | Título | Uso en este contrato |
|---|---|---|
| ITU-T E.164 | *The international public telecommunication numbering plan* | longitud máxima 15 dígitos, estructura CC+NSN, formato `+CC` |
| ITU-T E.212 | *The international identification plan for public networks and subscriptions* | estructura del IMSI (MCC+MNC+MSIN, 15 dígitos), distinción frente a MSISDN |
| SIGET (El Salvador) | Plan de Numeración Nacional, Resolución T-0001-2025 (modificación vigente desde 29/10/2025) y migración histórica a 8 dígitos (2005) | numeración nacional SV: 8 dígitos, NDC móvil 5/6/7, NDC fijo 2, código de país +503 |
| 3GPP TS 32.298 | *Telecommunication management; Charging management; Charging Data Record (CDR) parameter description* | distinción MSISDN (número marcable) vs. IMSI (suscripción) vs. IMEI (equipo) en un CDR real |
| 3GPP TS 32.297 | *Charging Data Record (CDR) file format and transfer* | contexto de generación de CDR — no aporta reglas de formato de número adicionales al 32.298 para este contrato |
| RFC 3986 (IETF/RFC Editor) | *Uniform Resource Identifier (URI): Generic Syntax* | estructura `scheme://authority/path` de una URI; el componente `host` de la autoridad como base de "dominio" |
| RFC 791 (IETF/RFC Editor) | *Internet Protocol* | IPv4 como 4 octetos de 32 bits en notación decimal punteada |
| RFC 4291 (IETF/RFC Editor) | *IP Version 6 Addressing Architecture* | IPv6 como notación hexadecimal separada por `:`, 128 bits |

**Nota de honestidad metodológica**: los documentos ITU-T E.164/E.212 y RFC
3986/791/4291 se consultaron en su versión pública/resumen oficial
disponible en itu.int y rfc-editor.org/ietf.org respectivamente, y se
verificó el contenido normativo citado (longitud máxima, estructura de
campos). El PDF del Plan de Numeración Nacional de SIGET se localizó en
`siget.gob.sv` pero el archivo está en un formato de imagen/binario que no
permitió extracción de texto exacta por sección/página en este ciclo; los
datos citados (8 dígitos, NDC 5/6/7 móvil, NDC 2 fijo, vigencia 29/10/2025)
están corroborados de forma consistente por la página oficial
`siget.gob.sv/plan-de-numeracion/` y por cobertura periodística que cita
directamente la resolución T-0001-2025. Los documentos 3GPP TS 32.297/298
se distribuyen en formato `.doc` versionado sin URL de texto plano estable;
se citan a nivel de recomendación y campo (MSISDN/IMSI/IMEI), no de número
de sección exacto, por la misma razón. Si se requiere cita exacta de
sección/página para auditoría regulatoria, debe descargarse el `.doc`/PDF
original y verificarse manualmente — se señala explícitamente para no
aparentar una precisión que esta investigación no pudo verificar
programáticamente.

## 3. Diferencia entre identificadores (fundamento técnico)

| Identificador | Definición técnica | Longitud típica | ¿Es "contacto interpersonal"? |
|---|---|---|---|
| **Número telefónico / MSISDN** | E.164: número marcable, CC (1-3 dígitos) + NSN (hasta 15 dígitos totales). 3GPP TS 32.298 lo registra como el campo MSISDN del CDR ("mobile station ISDN number of the served party") | 7–15 dígitos, opcionalmente con `+` | **Sí** — es el objeto de este contrato |
| **IMSI** | E.212: MCC (3 dígitos) + MNC (2-3 dígitos) + MSIN (9-10 dígitos) = 15 dígitos fijos. Identifica la *suscripción/SIM*, no es marcable, no es un número de contacto | 15 dígitos exactos | No — identificador de red, no de interlocutor |
| **IMEI** | Identifica el *equipo físico*, no la suscripción ni el interlocutor; se registra en CDR (TS 32.298) como Subscriber Equipment Number | 14-16 dígitos (con o sin Luhn check digit) | No |
| **Identificador de sesión de datos** | Campo interno del operador para una sesión PDP/APN; no representa a un interlocutor humano | variable, a menudo numérico | No — por eso el contrato prioriza `tipo_evento == DATOS` sobre la apariencia numérica (ver §6-D) |
| **IP (IPv4)** | RFC 791: 4 octetos en notación decimal punteada (`a.b.c.d`, 0-255 cada uno) | formato fijo con puntos | No |
| **IP (IPv6)** | RFC 4291: 128 bits en notación hexadecimal separada por `:` | formato fijo con dos puntos | No |
| **Dominio** | RFC 3986: subcomponente `host` de la `authority` de una URI; nombre registrado, no numérico | variable, con puntos y letras | No |
| **URL/URI** | RFC 3986: `scheme:[//authority]path[?query][#fragment]` | variable, con `://` o `scheme:` | No |
| **APN** | Nombre de punto de acceso de red de datos (identifica la red de destino de una sesión PDP, no una persona) | variable, alfanumérico con puntos | No |
| **Código corto** | Numeración especial de servicios (SMS premium, IVR, notificaciones) fuera del rango de numeración de abonado; en El Salvador estos rangos son administrados por SIGET fuera del bloque de 8 dígitos de abonado | típicamente 3-6 dígitos | No — es un servicio, no un interlocutor humano |

## 4. Numeración salvadoreña (SIGET, vigente)

- Número nacional de abonado: **8 dígitos**, sin código de área adicional
  (formato interno `XYZ-MCDU` según SIGET).
- Código Nacional de Destino (NDC) móvil: **5, 6, 7** (el prefijo "5" se
  habilitó a partir del 29/10/2025 por ampliación del plan; antes de esa
  fecha solo 6 y 7 eran NDC móviles activos).
- NDC fijo: **2**.
- Código de país: **+503** (sin cambios).
- Consecuencia para P0-B: un número SV plausible de 8 dígitos que comienza
  con 2, 5, 6 o 7 es estructuralmente válido tanto para móvil como fijo. El
  sistema **no debe** usar el primer dígito para distinguir "contacto real"
  de "no contacto" — solo para *anotar* (si se decide en el futuro) si es
  aparentemente móvil o fijo, nunca para excluir.

## 5. Numeración internacional (E.164)

- Longitud máxima total: **15 dígitos** (código de país + número nacional
  significativo).
- No hay longitud mínima normativa fija; el contrato de producto adopta
  **8 dígitos** como piso conservador tanto para nacional como
  internacional, igual al piso ya usado por El Salvador, para no inventar
  un umbral distinto por tipo de número.
- Formatos de entrada esperables en bitácoras: `+CC...`, `00CC...` (prefijo
  de discado internacional, uso extendido pero no normado por E.164 mismo),
  o el bloque de dígitos sin prefijo cuando el contexto de la columna lo
  deja claro.
- Un valor de 15 dígitos **no es automáticamente un MSISDN plausible**: un
  IMSI también tiene 15 dígitos (E.212) y un IMEI puede tener 15-16. El
  contrato exige prudencia: sin evidencia adicional (columna de tipo de
  evento = VOZ/SMS, o un prefijo `+`/`00` reconocible), un bloque de 15
  dígitos debe quedar **indeterminado**, no ascender automáticamente a
  `telefonico_plausible`.

## 6. Criterios de clasificación (contrato de producto aprobado)

### A. `telefonico_plausible`

Entra a ranking, perfiles y concentración cuando **todas** las condiciones
se cumplen:

1. el evento es VOZ o SMS (o su tipo es DESCONOCIDO pero el valor tiene
   entre 8 y 15 dígitos con evidencia de formato `+`/`00`/nacional SV — ver
   matriz §9);
2. `contacto_limpio` se normaliza a una cadena de solo dígitos (con `+`
   opcional) de **8 a 15** dígitos;
3. no es autocontacto (`contacto_limpio != tel_limpio`);
4. no cae en ninguna de las exclusiones técnicas de §6-D/E (DATOS, IP,
   dominio, URL, APN, alfanumérico, código corto/servicio).

Incluye explícitamente: móviles SV plausibles, fijos SV plausibles,
internacionales plausibles con o sin `+`. **No se usa "ocho dígitos" como
único criterio** — es el piso, no el techo ni la única condición.

### B. Números internacionales

- No se excluye un número por superar 8 dígitos.
- `+<CC><NSN>` y `<CC><NSN>` sin `+` (cuando el contexto — columna de
  contacto en una bitácora de VOZ/SMS — permite asumir que es un número, no
  otro identificador) se tratan igual.
- `00<CC><NSN>` (prefijo IDD): el contrato lo reconoce como equivalente,
  pero **el código actual no lo implementa** (`normalize_msisdn` no
  despoja el prefijo `00`). Esto se documenta como brecha de
  implementación conocida, no como decisión de excluirlo — ver §8 y prueba
  roja/documentada en Tarea 7.
- Un bloque de 11-15 dígitos sin `+`/`00` y sin evidencia de tipo VOZ/SMS
  no se asciende automáticamente a `telefonico_plausible`: podría ser IMSI
  o IMEI. Ver matriz §9.
- Si no hay evidencia suficiente → `indeterminado`, fuera de ranking, con
  trazabilidad conservada.

### C. Autocontacto

Cuando `contacto_limpio == tel_limpio` (número investigado marcándose a sí
mismo):

- motivo dedicado: **`autocontacto`**, categoría **`tecnico_no_personal`**;
- no entra a ranking (ni por conteo ni por duración);
- no cuenta como contacto único válido;
- no genera perfil (`interpretar_contactos`) ni participa en concentración;
- se conserva en la sección de control técnico/analítico con valor
  original, normalizado, tipo de evento, conteo y motivo;
- el sistema **no afirma la causa** (reenvío, desvío, error de operador,
  prueba del propio investigado) — solo documenta el hecho estructural.

### D. DATOS

El tipo de evento **prevalece** sobre la apariencia numérica del contacto:

- `tipo_evento_normalizado == "DATOS"` → siempre `tecnico_no_personal`,
  motivo `tipo_datos`, incluso si el valor tiene 8-15 dígitos;
- no entra a ranking;
- conserva trazabilidad completa.

### E. Códigos y servicios

- Códigos cortos (típicamente 3-6 dígitos) y números de servicio no se
  tratan como contacto interpersonal.
- Quedan en `indeterminado` (por longitud insuficiente, motivo
  `longitud_insuficiente` o `voz_longitud_corta`/`sms_longitud_ambigua`
  según el caso) — el sistema actual no tiene un motivo dedicado
  `codigo_corto`; se resuelve indirectamente por el umbral de longitud.
  Se documenta como simplificación aceptable: el efecto (fuera de ranking,
  trazabilidad conservada) es el exigido por el contrato, aunque la
  etiqueta de motivo no sea semánticamente específica.
- Conservan valor y conteo en la sección correspondiente.

### F. Fijos

- No se excluye un número únicamente porque no inicie con un NDC móvil
  (5/6/7). Un fijo SV plausible de 8 dígitos en un evento VOZ es
  `telefonico_plausible` igual que un móvil — el sistema no distingue
  fijo/móvil y el contrato prohíbe expresamente introducir esa
  distinción como criterio de exclusión.

## 7. Tratamiento de autocontacto — resumen ejecutivo

Ver §6-C. Contrato cerrado: exclusión activa vía motivo dedicado
`autocontacto`, con conservación de trazabilidad. Pendiente de
implementación en `tz_core/bitacora_normalization.py::_classify_contact_category`
(requiere pasar `tel_limpio` como parámetro adicional) y de propagación a
`interacciones_builder.py` y `logging_utils.py` (rutas legacy, ver auditoría
previa).

## 8. Limitaciones

0. **[CRÍTICO — hallazgo de este hito, verificado por ejecución directa de
   código, no por lectura] Un valor `"X.0"`/`"X.00"` decimal simple
   (no notación científica) queda mal clasificado como
   `tecnico_no_personal/formato_alfanumerico`, EXCLUIDO del ranking, aun
   cuando `contacto_limpio` lo normaliza correctamente al número sin el
   sufijo.** Causa raíz: `_classify_contact_category` (paso 5,
   `bitacora_normalization.py:420-423`) construye `raw_phone_stripped`
   aplicando `re.sub(r"[\s\+\-\(\)]", "", raw_str)` sobre el valor
   **crudo**, cuyo patrón no incluye el punto decimal (`.`); como
   `"70011111.0".isdigit()` es `False` y el valor no matchea el patrón de
   notación científica (no tiene `e`/`E`), la función retorna
   `formato_alfanumerico` antes de llegar al paso 7, que sí usa
   `contacto_limpio` (ya saneado por `normalize_msisdn`/
   `_normalize_decimal_string`, que si elimina el `.0` correctamente).
   Efecto verificado: para `contacto = 70011111.0` (float real o string),
   con evento VOZ, `contacto_limpio == "70011111"` (correcto),
   `contacto_valido == True` (correcto, calculado sobre `contacto_limpio`),
   pero `contacto_categoria == "tecnico_no_personal"` y
   `contacto_motivo == "formato_alfanumerico"` (incorrecto) — hay una
   **contradicción interna** entre `contacto_valido` y `contacto_categoria`
   para la misma fila. La notación científica (`7.0011111E7`) sí se
   clasifica correctamente porque el chequeo de científica ocurre *antes*
   del gate alfanumérico y lo evita. Este defecto es del núcleo del
   clasificador (`bitacora_normalization.py`), no de una ruta legacy —
   afecta a **todos** los consumidores P0-B por igual (`contacts.py`,
   `analytics.py`, `assembler.py`) cada vez que una bitácora entrega la
   columna `contacto` como columna numérica de Excel/CSV con decimales
   simples, el escenario exacto que la sanitización `.0` fue construida
   para resolver. Ver prueba roja dedicada en Tarea 6/FX-03.

1. **Prefijo `00` internacional**: verificado por ejecución directa que
   **sí se normaliza como equivalente hoy**, aunque no por diseño
   intencional: `_normalize_decimal_string` construye el valor con
   `Decimal(s)`, cuyo formateo elimina ceros a la izquierda, de modo que
   `"0050255551234"` y `"+50255551234"` ambos terminan en
   `contacto_limpio == "50255551234"`. Es un efecto colateral frágil (no
   una regla explícita de reconocimiento de prefijo IDD `00`), documentado
   así para no atribuirle una robustez que el código no garantiza
   deliberadamente — un número nacional legítimo que por algún error de
   captura comenzara con `0` sufriría la misma pérdida silenciosa del
   dígito inicial.
1b. **Prefijo `+` no siempre se conserva en `contacto_limpio`**: verificado
   por ejecución directa que `normalize_msisdn("+50255551234")` (sin
   espacios/guiones) retorna `"50255551234"` **sin** el `+`, porque
   `_normalize_decimal_string` intenta primero `Decimal("+50255551234")`
   (que Python acepta y formatea sin el signo) antes de que el chequeo de
   `prefix_plus` tenga oportunidad de actuar. Si el mismo valor trae
   separadores (`"+503 5555-1234"`), `Decimal()` falla, se usa la rama de
   texto, y el `+` sí se preserva. No afecta la clasificación (`contacto_categoria`
   usa `limpio_str.lstrip("+")`), pero sí genera inconsistencia en cómo se
   *muestra* `contacto_limpio` en las tablas HTML según si el valor de
   origen tenía separadores o no.

2. **IPv6**: no tiene un motivo dedicado (`ipv4` existe, `ipv6` no). Hoy
   una dirección IPv6 cae correctamente en `tecnico_no_personal` mediante
   la rama genérica `formato_alfanumerico` (los dos-puntos y letras hex
   hacen que `raw_phone_stripped.isdigit()` sea falso) — el *efecto* es
   correcto, la *trazabilidad específica* ("por qué se excluyó") es menos
   clara que para IPv4.
3. **Dominio/URL/APN**: los tres caen en el mismo motivo genérico
   `formato_alfanumerico`, sin distinguir entre sí. Efecto correcto,
   trazabilidad genérica.
4. **Código corto vs. número corto genuino**: no hay forma de distinguir
   estructuralmente "código de servicio de 5 dígitos" de "número
   corto por defecto de captura" — ambos caen en `indeterminado` por
   longitud. Es una limitación aceptada, no un defecto: el contrato exige
   solo que no entren al ranking, lo cual se cumple.
5. **IMSI/IMEI de 15 dígitos sin contexto**: el sistema no tiene forma de
   distinguir un IMSI de un MSISDN internacional de 15 dígitos sin
   evidencia adicional de formato (`+`/`00`) o de tipo de evento. La
   regla conservadora (→ `indeterminado` sin esa evidencia) prioriza no
   generar falsos positivos de ranking sobre maximizar cobertura — es una
   decisión de producto explícita, no un vacío.
6. **Divergencia de vocabulario DATOS/SMS/VOZ entre `qc_type_classifier.py`
   y `normalize_event_fields`**: ver §10. No afecta el ranking (ningún
   camino de DESCONOCIDO asciende a `telefonico_plausible`), pero sí la
   ubicación de un registro entre el Bloque B y C de "Todos los contactos".

## 9. Matriz regla → fundamento → tratamiento

| Regla | Fundamento | Tratamiento actual |
|---|---|---|
| Máximo 15 dígitos para número plausible | ITU-T E.164 | implementado (`longitud_excesiva` si n>15) |
| Piso de 8 dígitos para plausibilidad VOZ/SMS | Convención SIGET (numeración SV de abonado) elevada a piso general conservador | implementado (`n >= 8`) |
| IMSI de 15 dígitos no es MSISDN | ITU-T E.212 | **no implementado** — un bloque de 15 dígitos sin `+`/tipo reconocible puede clasificar igual que un internacional plausible si el tipo es VOZ/SMS. Riesgo documentado, no corregido en este hito (requeriría heurística adicional de "longitud sospechosa de IMSI/IMEI" fuera de alcance de Hito 1) |
| Evento DATOS excluye sin importar apariencia numérica | Separación conceptual MSISDN (E.164) vs. sesión de datos (3GPP TS 32.298 distingue MSISDN de campos de contexto PDP) | implementado (`tipo_datos` siempre `tecnico_no_personal`) |
| IPv4 se excluye por formato | RFC 791 | implementado (regex `\d{1,3}(\.\d{1,3}){3}`) |
| IPv6 se excluye por formato | RFC 4291 | implementado indirectamente (vía alfanumérico), sin motivo dedicado |
| Dominio/URL se excluyen por formato | RFC 3986 | implementado indirectamente (vía alfanumérico) |
| Autocontacto se excluye con motivo dedicado | Decisión de producto (§6-C), sin fundamento normativo externo — es una regla de negocio forense, no una regla de formato | **no implementado** — brecha activa, ver auditoría de rutas legacy |
| Fijo no se excluye por no ser móvil | Plan de Numeración SIGET no distingue capacidad analítica por tipo de línea | implementado (no hay heurística de exclusión por rango) |
| `00` como prefijo internacional equivalente a `+` | Uso extendido de IDD (no normado por E.164 mismo, sí por convención operativa internacional) | implementado, pero por efecto colateral frágil de `Decimal` (ver §8.1), no por regla explícita |
| Valor numérico con `.0`/`.00` (exportación Excel) debe clasificar igual que su forma entera | Consistencia interna requerida entre `contacto_valido` y `contacto_categoria` — no hay fundamento normativo externo, es corrección de bug de implementación | **no implementado — defecto activo, ver §8.0** |

## 10. Unificación de eventos VOZ/SMS/DATOS — diseño (no producción)

Comparación de las dos implementaciones existentes:

| Categoría | `normalize_event_fields._classify` (P0-B) | `qc_type_classifier.classify_single` (QC score) |
|---|---|---|
| VOZ | `"VOZ" in text`, `"CALL" in text`, `"LLAMADA" in text` | `CALL, VOICE, LLAMADA, MOC, MTC, MFC, INCOMING, OUTGOING, ENTRANTE, SALIENTE, RING, CONFERENCE, CONF` |
| SMS | `"SMS" in text` | `SMS, MENSAJE, MESSAGE, TEXT, MO-SMS, MT-SMS, SHORT, SMSC` |
| DATOS | `"DATOS" in text` | `DATA, DATOS, GPRS, INTERNET, NAV, NAVEGACION, BROWSE, WAP, APN, PDP` |
| Coincidencia | substring `in` sobre texto en mayúsculas | substring `in` sobre texto en mayúsculas (idéntico mecanismo, vocabulario más amplio) |

**Diferencia real**: `qc_type_classifier` reconoce un vocabulario
sustancialmente más amplio (`GPRS`, `INTERNET`, `NAV`, `BROWSE`, `WAP`,
`APN`, `PDP` para DATOS; `VOICE`, `MOC`, `MTC`, `MFC`, `INCOMING`,
`OUTGOING`, `ENTRANTE`, `SALIENTE`, `RING`, `CONFERENCE` para VOZ;
`MESSAGE`, `TEXT`, `SHORT`, `SMSC` para SMS). `normalize_event_fields`
solo reconoce el término literal de la categoría más `CALL`/`LLAMADA`
(VOZ). Esto significa que un valor como `"GPRS"` es `DATOS` para el score
de completitud pero `DESCONOCIDO` para P0-B.

**Contrato recomendado** (no implementado en este hito): adoptar en
`normalize_event_fields` el mismo vocabulario ya validado en
`qc_type_classifier`, como fuente única de verdad, para que ambos módulos
coincidan. Riesgo de falsos positivos a vigilar antes de fusionar:

- `"WAP"` y `"NAV"` son substrings cortos con más riesgo de coincidir por
  accidente dentro de un valor más largo no relacionado (p.ej. un nombre de
  antena o un texto libre que contuviera esas letras) — requieren
  coincidencia por palabra completa o límites de token, no solo `in`.
- `"TEXT"` (SMS) y `"SHORT"` (SMS) son también genéricos; mismo riesgo.
- `"RING"` (VOZ) podría coincidir dentro de otras palabras compuestas.
- Términos que sí son seguros con coincidencia por substring simple:
  `SMS`, `VOZ`, `LLAMADA`, `DATOS`, `GPRS`, `MTC`, `MOC`, `MFC` (siglas de
  operador poco ambiguas).

Recomendación: al fusionar, usar coincidencia por token completo
(`\bWORD\b` o split por separadores) para los términos de alto riesgo de
falso positivo (`WAP`, `NAV`, `TEXT`, `SHORT`, `RING`), y mantener `in`
simple para el resto. Esto queda fuera de este hito — es diseño, no
implementación.

## 11. Trazabilidad de este documento

- Investigación realizada: 2026-08-05.
- Herramientas: búsqueda web dirigida a fuentes oficiales
  (itu.int, siget.gob.sv, rfc-editor.org/ietf.org, 3gpp.org) — no se
  consultaron blogs, Wikipedia ni validadores comerciales de terceros para
  los hechos normativos citados en las tablas §2-§9.
- Ninguna cifra de este documento contradice el comportamiento verificado
  del código en la auditoría previa (`_classify_contact_category`,
  `normalize_msisdn`, `normalize_event_fields`).
