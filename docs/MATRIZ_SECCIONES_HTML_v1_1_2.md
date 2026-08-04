# MATRIZ_SECCIONES_HTML_v1_1_2.md

**TZ Analyzer — Diagnóstico v1.1-Nacional**
**Estado: APROBADA — diagnóstico base de v1.1-Nacional**
**Fecha: Agosto 2026**
**Bitácora de referencia: TEL_[REFERENCIA]**
**Revisión GPT: aprobada con observaciones (incorporadas)**
**Aprobación Tony: confirmada**

> **Nota de cierre (agosto 2026):** Este documento es el diagnóstico base de
> v1.1-Nacional y se conserva como referencia histórica.
> — Versión B (omisión silenciosa) cerrada: commits 88764c6, f463781, 6c93b15,
>   8776f7d, fe5273c, 5650904, ddb11ff.
> — P0-B (clasificación de contacto) cerrado: commits 8da0541, caedc0b, 2bc42db.
> — P0-A (normalización de tipo de evento) continúa congelado: Decisiones 3–7 pendientes.
> Los cierres posteriores están documentados en `BACKLOG_MAESTRO_TZ_ANALYZER_v1_1.md`.
> La tabla de estados refleja el diagnóstico original.

---

## Instrucciones de lectura

- **Promesa analítica**: qué dice el reporte que esta sección responde.
- **Campos requeridos**: columnas del DataFrame que la sección necesita.
- **Módulo productor**: módulo y función exactos verificados contra código real (commit 42ad760).
- **Estado**: clasificación para v1.1-Nacional (ver escala abajo).
- **Riesgo si se presenta sin ajuste**: consecuencia forense directa.
- **Sin datos — comportamiento actual**: lo que el código hace hoy.
- **Sin datos — comportamiento requerido**: principio Versión B (nunca omisión silenciosa).

### Escala de estado

| Estado | Definición |
|---|---|
| `mantener` | Funciona correctamente. No tocar en v1.1. |
| `ajustar` | Lógica central válida, pero requiere cambios en lógica de cálculo, contenido o comportamiento. |
| `condicionar` | Debe declarar explícitamente cuándo aparece y qué muestra cuando faltan datos. Hoy tiene omisión silenciosa. |
| `congelar` | Problema conocido, fuera de alcance de v1.1. No tocar. |
| `eliminar` | Sacar del reporte en v1.1. |

---

## Matriz

| # | Sección | Promesa analítica | Campos requeridos | Módulo productor | Estado | Riesgo si se presenta sin ajuste | Sin datos — comportamiento actual | Sin datos — comportamiento requerido |
|---|---|---|---|---|---|---|---|---|
| 1 | Resumen ejecutivo | Síntesis narrativa del período: total de interacciones, contacto dominante, hora pico | `contacto`, `hora`, `len(df)` | `assembler.py` → `generar_informe_html()` líneas 180–226 | `ajustar` | MEDIO: narrativa basada en métricas de contactos sin filtrar — puede presentar IPs o códigos técnicos como "contacto dominante" | Omisión silenciosa — `resumen_ejecutivo_html = ""` | Mostrar con datos disponibles + nota "análisis parcial: campo X no disponible" |
| 2 | Metadatos | Contexto del análisis: archivo procesado, número investigado, período cubierto, total de registros | `fecha`, `tel` | `metadata.py` → `generate_metadata_section()` | `mantener` | BAJO | No aplica — campo de contexto, no analítico | Si falta fecha: "Período no calculable". Si falta tel: "Número investigado no especificado" |
| 3 | Indicadores | Métricas cuantitativas del período: totales por tipo, duración acumulada, contactos únicos, antenas únicas | `tipo`, `duración`, `fecha/hora`, `contacto`, `antena` | `kpi.py` → `generate_kpi_section()` | `ajustar` | ALTO: mezcla voz, SMS y datos como eventos equivalentes; totales inflados por sesiones de datos sin declararlo | Si faltan campos: KPIs se calculan sobre base incompleta sin advertencia | tipo no normalizado → advertencia visible. duración ausente → omitir KPIs de duración con nota |
| 4 | Antenas más activadas (Top N) | Identifica las N antenas con más activaciones para orientar el análisis geográfico | `antena`, `lat`, `lon` | `antennas.py` → `build_top_antennas_section()` | `ajustar` | MEDIO: el ranking no declara el universo analítico — el analista no puede distinguir si la activación es voz, SMS o datos | `return ""` — omisión silenciosa si `dfv.empty` o sin coordenadas válidas | Declarar universo analítico (voz/SMS/datos/todos). Si no hay antena: "No se registraron datos de antena en esta bitácora" |
| 5 | Contactos con más comunicación | Ranking de contactos por frecuencia y duración para identificar relaciones principales | `contacto`, `tipo`, `duración` | `contacts.py` → `build_top_contacts_sections()` | `ajustar` | ALTO: puede presentar IPs (4D4, 6C0, DC7A53935A605A), servidores o códigos técnicos como contactos principales | Sin fallback explícito verificado | Declarar: "No se registraron contactos telefónicos válidos en esta bitácora" |
| 6 | Antenas por rango horario | Distribución horaria de activaciones por franja (Madrugada/Mañana/Tarde/Noche) | `antena`, `hora` o `fecha_hora` | `antennas.py` → `build_antennas_by_hour_section()` línea 279 | `condicionar` | MEDIO: el análisis no declara si incluye activaciones de voz, SMS, datos o todas — el analista no puede interpretar el patrón horario con certeza | `return ""` en tres condiciones: df vacío, `col_ant` ausente, `hours is None` — todas silenciosas | Declarar en cada caso el motivo: "Hora no disponible — análisis temporal no generado" |
| 7 | Filtrar interacciones por fecha | Herramienta interactiva para explorar interacciones por día (dropdown `<select>`) | `fecha`/`hora` para datetime; todas las columnas del registro | `interacciones_builder.py` → `construir_seccion_interacciones()` línea 153 | `ajustar` | MEDIO: si el datetime interno no está ordenado correctamente, el filtro puede mostrar interacciones fuera de secuencia | `return ""` — omisión silenciosa si `fechas_ord` vacío | Declarar: "Fecha no disponible — filtro no generado". Verificar ordenamiento por datetime interno |
| 8 | Limitaciones del análisis | Documenta campos ausentes o incompletos que afectan la interpretación del informe | Generado por el sistema; detecta "?" en columnas de objeto (mojibake) | `assembler.py` → `generar_informe_html()` líneas 237–258 | `ajustar` | ALTO: no advierte sobre ausencia de normalización de tipo ni de contacto; los 2 ítems fijos siempre se muestran aunque los datos sean perfectos | Siempre aparece con 2 ítems fijos + 1 condicional por mojibake | Agregar ítems condicionales por: tipo no normalizado, contacto no clasificado, hora ausente |
| 9 | Todas las antenas | Inventario completo de antenas activadas con mapa interactivo y detalle cronológico | `antena`, `lat`, `lon`, `fecha/hora` | `antennas.py` → `build_antennas_table()` + ensamblaje en `assembler.py` | `ajustar` | MEDIO: el mapa no declara el universo analítico — activaciones de voz, datos y SMS se muestran sin distinción | Omisión silenciosa si no hay coordenadas válidas | Declarar universo analítico. Si no hay antenas: "No se registraron antenas con coordenadas válidas en el período analizado" |
| 10 | Todos los contactos | Directorio completo de contactos con métricas individuales | `contacto`, `tipo`, `duración`, `fecha/hora` | `contacts.py` → `_construir_seccion_todos_contactos()` | `ajustar` | ALTO: directorio incluye IPs, códigos técnicos y valores no telefónicos sin distinción ni advertencia | Sin fallback explícito verificado | Declarar: "No se registraron contactos en el período analizado" |

---

## Notas de diagnóstico

### Distribución de estado (aprobada)

| Estado | Secciones | Cantidad |
|---|---|---|
| `mantener` | Metadatos | 1 |
| `ajustar` | Resumen ejecutivo, Indicadores, Antenas Top N, Contactos Top N, Filtrar por fecha, Limitaciones, Todas las antenas, Todos los contactos | 8 |
| `condicionar` | Antenas por rango horario | 1 |
| `congelar` | — | 0 |
| `eliminar` | — | 0 |

### Bloqueantes P0 identificados en el diagnóstico original

**P0-A: Normalización de tipo de evento**
→ Sin clasificación de tipo, los módulos de análisis operan sobre un universo heterogéneo
sin declararlo. El ajuste no es excluir datos/navegación automáticamente — es declarar
qué universo se está analizando (voz, SMS, datos o todos) para que el analista pueda
interpretar correctamente cada sección.
→ Ver diseño congelado: `PLAN_NORMALIZACION_TIPO_EVENTO_v1_1.md`
→ Secciones afectadas: 3, 4, 5, 6, 9, 10

**P0-B: Clasificación de contacto**
→ Aunque se resuelva P0-A, siguen entrando al ranking valores no telefónicos:
IPs (4D4, 6C0, DC7A53935A605A), códigos de sistema, identificadores técnicos.
→ El filtro debe ser doble: tipo de evento válido + contacto telefónico válido.
→ No existe lógica de clasificación de contacto en ningún módulo verificado.
→ Secciones afectadas directas: 5, 10. Por herencia de métricas: 1, 3.

> **Estado posterior:** ✅ Cerrado (agosto 2026). Implementado en commits
> 8da0541, caedc0b y 2bc42db.

### Observación sobre antenas (ajuste de criterio)

Los datos/navegación no "contaminan" el análisis de antenas de la misma forma en que
contaminan el análisis de contactos. Una activación de antena por datos puede representar
desplazamiento real útil para el análisis geográfico.

El ajuste requerido en secciones 4, 6 y 9 no es excluir navegación automáticamente,
sino **declarar el universo analítico**: si el ranking incluye activaciones de voz,
SMS, datos o todas. El analista decide qué excluir con ese contexto.

### Patrón transversal: omisión silenciosa

Siete secciones retornan `""` o no generan contenido cuando faltan datos, sin declararlo:
- Resumen ejecutivo (1)
- Antenas Top N (4) — cuando `dfv.empty`
- Contactos Top N (5) — sin fallback verificado
- Antenas por rango horario (6) — tres condiciones silenciosas
- Filtrar por fecha (7) — cuando `fechas_ord` vacío
- Todas las antenas (9) — sin coordenadas válidas
- Todos los contactos (10) — sin fallback verificado

Este patrón viola el principio Versión B y puede corregirse de forma incremental,
**independientemente de P0-A y P0-B**. Es el candidato natural para el primer commit.

> **Estado posterior:** Patrón resuelto por Versión B. Commits por sección:
> S1 (88764c6, f463781), S5 (6c93b15), S10 (8776f7d), S4/S6/S9/S7 (fe5273c,
> 5650904, ddb11ff).

### Módulos productores — verificación completada (commit 42ad760)

| Sección | Módulo confirmado | Función exacta |
|---|---|---|
| Resumen ejecutivo | `assembler.py` | `generar_informe_html()` líneas 180–226 |
| Limitaciones | `assembler.py` | `generar_informe_html()` líneas 237–258 |
| Filtrar por fecha | `interacciones_builder.py` | `construir_seccion_interacciones()` línea 153 |
| Antenas por rango horario | `antennas.py` | `build_antennas_by_hour_section()` línea 279 |

---

## Estado del documento

| Elemento | Estado |
|---|---|
| Secciones enumeradas | ✅ Completo (10 secciones, bitácora TEL_[REFERENCIA]) |
| Promesa analítica | ✅ Verificada |
| Campos requeridos | ✅ Verificados contra código |
| Módulos productores | ✅ Verificados contra código (commit 42ad760) |
| Estado (clasificación) | ✅ Aprobado por Tony (agosto 2026) |
| Riesgo | ✅ Aprobado |
| Sin datos — comportamiento actual | ✅ Verificado contra código |
| Sin datos — comportamiento requerido | ✅ Aprobado |
| Revisión GPT | ✅ Incorporada |
| Aprobación final Tony | ✅ Agosto 2026 |
