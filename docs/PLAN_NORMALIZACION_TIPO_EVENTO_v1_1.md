# PLAN_NORMALIZACION_TIPO_EVENTO_v1_1.md

**TZ Analyzer — Diseño arquitectural**
**Estado: CONGELADO — solo diseño, no implementar**
**Fecha: Mayo 2026**
**Autores: Tony (Omar Arias) + Claude + GPT**

---

## 1. Problema

Las bitácoras telefónicas reales presentan múltiples vocabularios para el campo
tipo de evento. Cada operadora — nacional o internacional — usa su propio formato
sin estándar común.

**Ejemplos documentados de bitácoras reales:**

| Bitácora | Valores observados |
|---|---|
| 1 | `LLAMADA ENTRANTE`, `LLAMADA SALIENTE`, `MENSAJE ENTRANTE` |
| 2 | `E`, `S`, `I` |
| 3 | `Llamada Entrante`, `Llamada Saliente` |
| 4 | `Llamada Entrante`, `Llamada Saliente`, `SMS Entrante`, `SMS Saliente` |
| 5 (internacional) | `voice` |

**Consecuencia directa:** si el sistema no normaliza este campo antes de procesar,
los rankings de contactos, duración acumulada, activaciones de antena y KPIs se
calculan sobre un conjunto de eventos heterogéneos sin discriminación. Un registro
de datos móviles puede aparecer como el contacto más frecuente del sujeto.

Este riesgo está documentado formalmente en la Auditoría Técnica TZ Analyzer
(Abril 2026), secciones 3.1, 3.3 y 6.

---

## 2. Decisión arquitectural

**Separar el valor original del evento de su interpretación normalizada.**

El sistema dejará de operar directamente sobre el campo `tipo` tal como llega de
la bitácora. En su lugar, el pipeline generará dos columnas internas derivadas:

```
tipo_normalizado      → categoría semántica del evento
direccion_normalizada → sentido de la comunicación
```

El campo original se conserva sin modificar para trazabilidad.

**Motivación:** el valor `LLAMADA ENTRANTE` contiene dos datos distintos (tipo =
voz, dirección = entrante). El valor `voice` contiene solo uno (tipo = voz,
dirección = desconocida). Tratar ambos como equivalentes sin separación introduce
ambigüedad en métricas que dependen de dirección.

---

## 3. Categorías normalizadas

### tipo_normalizado

| Valor | Descripción |
|---|---|
| `voz` | Llamada telefónica de voz |
| `sms` | Mensaje de texto SMS o MMS |
| `datos` | Sesión de datos móviles / navegación |
| `otro` | Evento válido reconocido pero no clasificable en las categorías anteriores — se incluye en el análisis |
| `ignorar` | Evento que el analista decide excluir conscientemente del análisis |
| `desconocido` | Valor no reconocido por el sistema ni confirmado por el analista |

> **Distinción importante entre `otro` e `ignorar`:** `otro` preserva el evento
> en el análisis como dato válido de categoría indefinida. `ignorar` lo excluye
> deliberadamente. Mezclarlos ocultaría decisiones de exclusión que deben ser
> trazables.

### direccion_normalizada

| Valor | Descripción |
|---|---|
| `entrante` | Comunicación recibida por el sujeto investigado |
| `saliente` | Comunicación iniciada por el sujeto investigado |
| `desconocida` | El valor original no permite inferir dirección |

---

## 4. Catálogo base de valores conocidos

El sistema mantendrá un catálogo interno de valores conocidos con su mapeo
predefinido. Este catálogo se aplica automáticamente sin intervención del analista.

**Ubicación en código:** `tz_core/normalizacion/tipo_evento.py` — constante
Python `CATALOGO_TIPO_EVENTO`. No se usa archivo JSON externo. El catálogo base
es parte del código versionado; las clasificaciones por caso van en `mapeo_manual`.

**Lookup:** `valor.strip().lower()` antes de buscar en el catálogo.

### 4.1 Valores reconocidos automáticamente

| Valor original (case-insensitive) | tipo_normalizado | direccion_normalizada |
|---|---|---|
| `LLAMADA ENTRANTE` / `Llamada Entrante` | `voz` | `entrante` |
| `LLAMADA SALIENTE` / `Llamada Saliente` | `voz` | `saliente` |
| `MENSAJE ENTRANTE` / `SMS Entrante` | `sms` | `entrante` |
| `MENSAJE SALIENTE` / `SMS Saliente` | `sms` | `saliente` |
| `voice` | `voz` | `desconocida` |
| `data` / `datos` / `DATOS` / `DATA` | `datos` | `desconocida` |
| `GPRS` / `LTE` / `APN` | `datos` | `desconocida` |
| `navegacion` / `NAVEGACION` | `datos` | `desconocida` |

> `navegacion` agregado en sesión 10 mayo 2026 — valor observado en bitácoras reales.

### 4.2 Valores ambiguos conocidos (siempre requieren confirmación)

Estos valores son reconocidos por el sistema como potencialmente válidos, pero
**nunca se clasifican automáticamente**. El wizard siempre los presenta al
analista para confirmación, independientemente del contexto.

**Motivación:** una sola letra puede significar cosas distintas según operadora,
país o plantilla. Asumir su significado sería un error forense.

| Valor | Por qué es ambiguo |
|---|---|
| `E` | Puede ser Entrante, pero también un código de operadora distinto |
| `S` | Puede ser Saliente, pero también un código de operadora distinto |
| `I` | Significado completamente desconocido — no confirmar sin evidencia |
| Cualquier valor de 1-2 caracteres | Por definición insuficiente para clasificación segura |

### 4.3 Estructura del dict en código

```python
# tz_core/normalizacion/tipo_evento.py

CATALOGO_TIPO_EVENTO = {
    "llamada entrante": ("voz", "entrante"),
    "llamada saliente": ("voz", "saliente"),
    "mensaje entrante": ("sms", "entrante"),
    "mensaje saliente": ("sms", "saliente"),
    "sms entrante":     ("sms", "entrante"),
    "sms saliente":     ("sms", "saliente"),
    "voice":            ("voz", "desconocida"),
    "data":             ("datos", "desconocida"),
    "datos":            ("datos", "desconocida"),
    "gprs":             ("datos", "desconocida"),
    "lte":              ("datos", "desconocida"),
    "apn":              ("datos", "desconocida"),
    "navegacion":       ("datos", "desconocida"),
}

VALORES_AMBIGUOS = {"e", "s", "i"}
```

---

## 5. Punto de inserción en el pipeline

**Archivo:** `ingestion_pipeline.py`

**Posición:** inmediatamente después del renombrado de columnas según mapeo del
wizard, antes de cualquier normalización de campos derivados (fechas, MSISDN,
duración) y antes de cualquier cálculo o salida.

**Regla arquitectural:**
```
1. cargar datos
2. mapear columnas
3. normalizar semántica del evento  ← aquí
4. normalizar/validar campos derivados
5. calcular métricas
```

**Firma de la función:**
```python
normalizar_tipo_evento(df, mapeo_manual=None)
```

- Recibe: DataFrame con columna `tipo` ya renombrada + dict opcional de
  clasificaciones manuales del analista
- Devuelve: mismo DataFrame con columnas `tipo_normalizado` y
  `direccion_normalizada` agregadas
- **No modifica** la columna `tipo` original
- **No filtra** registros — solo etiqueta

---

## 6. Comportamiento del wizard (activación condicional)

El wizard **no interrumpe al analista** cuando todos los valores del campo tipo
son reconocidos por el catálogo base.

El wizard **sí interviene** cuando detecta uno o más valores desconocidos. En ese
caso muestra únicamente los valores no reconocidos y solicita clasificación:

```
Se detectaron tipos de eventos que el sistema no reconoce.
Confirma a qué categoría corresponde cada valor para que los rankings
de contactos, duración y antenas sean correctos.

Valor detectado: "I"
Clasificar como:
  [1] Voz
  [2] SMS
  [3] Datos / Navegación
  [4] Otro (evento válido, categoría indefinida)
  [5] Ignorar / Excluir del análisis
```

El analista selecciona de una lista — no digita texto libre.

**Principio de diseño:** el analista que conoce los datos toma la decisión. El
sistema provee la estructura y el contexto; el humano provee el criterio.

---

## 7. Aprendizaje local por caso

Las clasificaciones manuales del analista se guardan localmente asociadas al
caso o sesión de trabajo. **No se propagan automáticamente como reglas globales
del sistema.**

Flujo:

1. Analista clasifica `I` → `sms` para un caso específico
2. El sistema guarda esa regla en configuración local del caso
3. Si la misma bitácora se reprocesa, el sistema recuerda la clasificación
4. Si una bitácora diferente tiene `I`, el sistema vuelve a preguntar

**Motivación:** el mismo valor puede significar cosas distintas en bitácoras de
operadoras distintas. Asumir equivalencia global sería un error forense.

---

## 8. Trazabilidad

Toda clasificación manual del analista debe quedar documentada. El objetivo es
que cualquier métrica del informe sea reproducible y auditable.

**En el informe HTML:**

```
Normalización del campo tipo de evento:
  Valores reconocidos automáticamente: LLAMADA ENTRANTE, LLAMADA SALIENTE
  Valores clasificados manualmente por el analista:
    - "I" → SMS (entrante)
```

**En log/archivo de trazabilidad:**

```
[2026-05-10] El analista clasificó manualmente 1 valor del campo tipo.
Valor: "I" → tipo_normalizado: sms, direccion_normalizada: entrante
```

**Motivación forense:** si el informe presenta "Top contactos por llamadas de
voz", debe poder demostrarse qué valores del campo tipo fueron considerados voz
y quién tomó esa decisión.

> Decisión pendiente: trazabilidad embebida en HTML vs archivo separado.
> Resolver en próxima sesión de diseño (Decisión 6 del plan de implementación).

---

## 9. Impacto en módulos existentes

Este cambio afecta múltiples capas del sistema. Se documenta aquí como referencia
para la fase de implementación:

| Módulo | Impacto esperado |
|---|---|
| `mapping_wizard.py` | Agregar paso de confirmación condicional |
| `ingestion_pipeline.py` | Llamar `normalizar_tipo_evento()` post-mapeo; generar `tipo_normalizado` y `direccion_normalizada` |
| `analytics.py` | Usar `tipo_normalizado` en lugar de `tipo` original |
| `interacciones_builder.py` | Filtrar por `tipo_normalizado` para rankings |
| `contacts.py` (html) | Usar columnas normalizadas para métricas de contactos |
| `antennas.py` (html) | Separar activaciones por `tipo_normalizado` |
| `kpi.py` | Calcular KPIs sobre base filtrada por tipo |
| HTML general | Agregar sección de trazabilidad de normalización |

Nuevo módulo a crear:

| Módulo | Propósito |
|---|---|
| `tz_core/normalizacion/tipo_evento.py` | Catálogo base + función `normalizar_tipo_evento()` |

---

## 10. Alcance de este documento

**Incluye:**
- Diseño del mecanismo de normalización
- Categorías y catálogo base
- Comportamiento del wizard
- Reglas de aprendizaje y trazabilidad
- Mapa de impacto en módulos
- Decisiones de implementación aprobadas (secciones 4.3 y 5)

**No incluye:**
- Código de implementación final
- Instrucciones para Copilot
- Cambios al repo

**Prerequisito para implementación:**
- Decisión formal de avanzar a v1.1
- Confirmación de que 332 tests siguen pasando como línea base
- Revisión del impacto en golden output antes de cualquier cambio

---

## 11. Estado

| Elemento | Estado |
|---|---|
| Diseño general | ✅ Congelado |
| Validación GPT | ✅ Aprobado (Mayo 2026) |
| Decisión 1 — Punto de inserción en pipeline | ✅ Aprobado (10 mayo 2026) |
| Decisión 2 — Estructura del catálogo base | ✅ Aprobado (10 mayo 2026) |
| Decisión 3 — Wizard condicional (UI exacto) | ⏸ Pendiente |
| Decisión 4 — Subdivisión en sub-fases | ⏸ Pendiente |
| Decisión 5 — Estrategia golden output | ⏸ Pendiente |
| Decisión 6 — Trazabilidad (HTML vs archivo) | ⏸ Pendiente |
| Decisión 7 — Plan de tests | ⏸ Pendiente |
| Implementación | ⏸ Pendiente — no iniciar sin decisión explícita |
| Tests | ⏸ Pendiente |
| Golden output | ⏸ Pendiente |

---

## 12. Historial de sesiones

| Fecha | Qué se decidió |
|---|---|
| Mayo 2026 (inicial) | Diseño completo congelado y validado por GPT |
| 10 mayo 2026 | Decisión 1 y 2 aprobadas; `navegacion` agregado al catálogo; estructura del dict definida; punto exacto de inserción en pipeline confirmado |
