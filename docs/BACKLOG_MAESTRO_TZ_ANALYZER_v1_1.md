# BACKLOG_MAESTRO_TZ_ANALYZER_v1_1.md

**TZ Analyzer — Backlog depurado post-auditoría**
**Estado: APROBADO — documento rector del cierre v1.1**
**Fecha: Agosto 2026**
**Basado en: auditoría consolidada de TODO.md, README.md, docs/, comentarios de código, tests y friction points**
**HEAD al momento de auditoría: 2bc42db | Tests: 427 passed, 2 skipped**

---

## 1. Bloqueantes pre-empaquetado

> Deben resolverse antes de etiquetar versión estable. No son bloqueantes funcionales, pero comprometen la credibilidad documental del release.

---

### B1 — README.md desactualizado (4 puntos)

| Atributo | Detalle |
|---|---|
| **Estado** | Stale |
| **Prioridad** | Alta |
| **Riesgo** | Credibilidad del proyecto ante terceros |
| **Archivos afectados** | `README.md` |
| **Evidencia** | Verificado durante auditoría agosto 2026 |

**Puntos específicos a corregir:**

1. **Conteo de tests:** `"332 tests"` aparece en tres lugares → corregir a `427`
2. **Descripción KMZ:** describe `"subcarpetas por fecha (día del año + fecha ISO)"` → incorrecto; ahora es numeración secuencial `001 — YYYY-MM-DD`, con subcarpetas por activación, carpeta "LEA PRIMERO" y ScreenOverlay
3. **Estado de P0-B y Versión B:** la sección de estado o pendientes no refleja el cierre de P0-B ni de Versión B; actualizar para indicar que ambos están cerrados
4. **Estructura de tests de integración:** listado de archivos en la sección de estructura del proyecto está incompleto; faltan archivos de P0-B

**Requiere validación (no corrección obligatoria):**
- Conteo de módulos ("46 módulos") — sin verificar desde la consolidación
- Cifra aproximada de líneas del orquestador ("~825 líneas") — sin verificar desde la consolidación

**Acción:** editar solo los bloques afectados. No reescribir el README completo.

**Criterio de cierre:** `grep "332" README.md` devuelve 0 resultados; descripción KMZ refleja estructura real; P0-B y Versión B marcados como cerrados; listado de tests actualizado.

---

### B2 — ESPECIFICACION_KMZ: tabla de estado desactualizada

| Atributo | Detalle |
|---|---|
| **Estado** | Stale |
| **Prioridad** | Media |
| **Riesgo** | Confusión si alguien lee el doc como referencia futura |
| **Archivos afectados** | `docs/ESPECIFICACION_KMZ_ANTENAS_ACTIVACIONES_v1_1_1.md` |
| **Evidencia** | Tabla de estado dice "⏸ Pendiente" para Implementación y Tests |

**Cambio específico:**

```
| Implementación | ⏸ Pendiente |  →  | ✅ Cerrado — implementación y tests completos |
| Tests          | ⏸ Pendiente |  →  | ✅ Cerrado — implementación y tests completos |
```

**Criterio de cierre:** tabla refleja estado real; resto del documento sin modificar.

---

### B3 — TODO.md: ítems cerrados o descartados no marcados

| Atributo | Detalle |
|---|---|
| **Estado** | Stale |
| **Prioridad** | Media |
| **Riesgo** | Arrastres históricos dificultan lectura del backlog real |
| **Archivos afectados** | `TODO.md` |
| **Evidencia** | Verificado durante auditoría agosto 2026 |

**Cambios específicos:**

| Ítem en TODO.md | Acción |
|---|---|
| F5-ALIASES (aliases `_`-prefijados) | Marcar ✅ cerrado — cd4ec85 |
| README del repo | Ya marcado ✅ — sin cambio |
| F6 — opción R=Remapear | Marcar ✅ cerrado — documentado y testeado |
| F7 — integración IMEI | Marcar como descartado — IMEI ya aparece como campo esencial |
| F9 — artefactos de encoding | Marcar como descartado — provenían del Excel original de la operadora |
| F10 — lista de columnas no visible | Marcar como mitigado — `? ver columnas` cubre el riesgo principal |
| Decisión estratégica v1.1 (Caminos A/B/C) | Actualizar: "Camino adoptado de facto: v1.1-Nacional. Decisión no documentada formalmente." |
| Mejoras HTML | Actualizar para reflejar que Versión B está cerrada; listar mejoras pendientes reales |

**Criterio de cierre:** TODO.md refleja solo ítems abiertos reales; ítems cerrados o descartados marcados como tales.

---

## 2. Pendientes funcionales menores

> No bloquean el uso operativo, pero tienen gaps de comportamiento documentados.

---

### F2 — Fecha/hora: columna fecha-sola asignada a ambos campos sin advertencia

| Atributo | Detalle |
|---|---|
| **Estado** | Pendiente menor |
| **Prioridad** | Baja |
| **Riesgo** | Bajo — el caso crítico (columna datetime completo) ya está cubierto |
| **Archivos afectados** | `tz_core/mapping_wizard.py` (función `_detect_shared_datetime`) |
| **Evidencia** | Análisis de código agosto 2026; sin test que cubra el gap |

**Comportamiento actual:**
- Misma columna asignada a fecha y hora, con componente datetime → advertencia + 3 opciones ✅
- Misma columna asignada a fecha y hora, sin componente datetime (fecha sola) → retorno silencioso ⚠️

**Gap:** si la columna parece solo fecha (sin hora), `_detect_shared_datetime` retorna sin advertir. El usuario queda con la misma columna en ambos campos sin saberlo.

**Acción:** agregar advertencia en el caso de retorno silencioso. Agregar test que confirme que una columna de fecha sin hora asignada simultáneamente a `fecha` y `hora` genera advertencia.

**Criterio de cierre:** test que cubra el caso fecha-sola; comportamiento documentado o corregido.

---

### F3 — Columna asignada a dos campos: mensaje minimiza sin ofrecer remediación

| Atributo | Detalle |
|---|---|
| **Estado** | Pendiente menor |
| **Prioridad** | Baja |
| **Riesgo** | Bajo — el aviso existe; el riesgo es de UX, no de integridad |
| **Archivos afectados** | `tz_core/mapping_wizard.py` (función `_check_duplicate_column_assignments`) |
| **Evidencia** | Análisis de código agosto 2026; sin test que cubra remediación |

**Comportamiento actual:**
- Detecta duplicado → muestra aviso
- Mensaje dice: "Esto es normal cuando, por ejemplo, la dirección y la antena provienen de la misma columna."

**Gap:** el mensaje normaliza el duplicado antes de que el usuario evalúe si es intencional. No ofrece opción de remapear. Sin test que evalúe claridad o flujo de corrección.

**Acción:** revisar mensaje para que oriente sin asumir intencionalidad. Evaluar si ofrecer remapeo inmediato. Agregar test de escenario de duplicado no intencional.

**Criterio de cierre:** mensaje no normaliza automáticamente; test documenta comportamiento esperado.

---

## 3. Deuda documental

> No afectan el comportamiento del sistema, pero deben resolverse antes de publicar o entregar el proyecto.

---

### D1 — SPEC_OPERATIVA_KMZ: baseline de tests y estado de implementación desactualizados

| Atributo | Detalle |
|---|---|
| **Estado** | Stale menor |
| **Prioridad** | Muy baja |
| **Riesgo** | Confusión si alguien usa la spec como referencia |
| **Archivos afectados** | `docs/SPEC_OPERATIVA_KMZ_IMPLEMENTACION_v1_1_2.md` |

**Cambios:**

1. Sección 9, bloque de validación — no reemplazar el baseline histórico; agregar nota:
   > Baseline al redactar esta especificación: 342 passing.
   > Estado posterior verificado en agosto de 2026: 427 passed, 2 skipped.

2. Encabezado del documento — agregar nota de cierre:
   > Estado: IMPLEMENTADA — implementación y tests completos (agosto 2026).

**Criterio de cierre:** baseline histórico preservado; nota de estado posterior y de implementación agregadas.

---

### D2 — MATRIZ_SECCIONES_HTML: ausente del repositorio

| Atributo | Detalle |
|---|---|
| **Estado** | Gap documental — pendiente evaluación |
| **Prioridad** | Media |
| **Riesgo** | Pérdida de referencia diagnóstica base de v1.1-Nacional |
| **Archivos afectados** | `docs/` (archivo ausente) |

**Contexto:** `MATRIZ_SECCIONES_HTML_v1_1_2.md` existe fuera del repo pero no está en `docs/`. Es el documento diagnóstico base de v1.1-Nacional que motivó el patrón Versión B y la estructura de secciones HTML.

**Antes de agregar, verificar:**
1. Es la versión final canónica (v1_1_2)
2. No contiene rutas locales, datos reales ni información sensible
3. No contradice el estado posterior de Versión B y P0-B

**Acción:** revisar contenido, sanear si necesario, agregar a `docs/` con commit `docs:`.

**Criterio de cierre:** archivo en `docs/` o decisión documentada de mantenerlo fuera.

---

### D3 — Decisión estratégica v1.1: adoptada de facto sin doc formal

| Atributo | Detalle |
|---|---|
| **Estado** | Pendiente documental |
| **Prioridad** | Baja |
| **Riesgo** | Bajo — el rumbo es claro; solo falta el cierre formal |
| **Archivos afectados** | `TODO.md` |

**Contexto:** TODO.md describe tres caminos (A/B/C) con "decisión pendiente". En la práctica, el proyecto avanzó como v1.1-Nacional.

**Acción:** documentar en TODO.md que el camino adoptado fue v1.1-Nacional y cerrar la sección de decisión estratégica.

**Criterio de cierre:** TODO.md no presenta los caminos A/B/C como decisión abierta.

---

### D4 — Auditoría técnica (.docx): decisión de control documental

| Atributo | Detalle |
|---|---|
| **Estado** | Decisión tomada — fuera del repo |
| **Prioridad** | Sin acción inmediata |
| **Archivos afectados** | Ninguno en el repo |

**Decisión:** el archivo `auditoria_tecnica_formal_tz_analyzer.docx` se mantiene intencionalmente fuera del repositorio. Razones: puede contener hallazgos sensibles, rutas locales o debilidades técnicas; `.docx` no es formato canónico versionable; GitHub conservaría historial incluso si se elimina.

**Opción futura:** crear versión saneada en Markdown (`docs/AUDITORIA_TECNICA_RESUMEN_v1_1.md`) solo si se requiere documentación pública o interna del proyecto.

---

## 4. Mejoras no bloqueantes

> Mejoran la experiencia del usuario o la calidad del output, pero no bloquean el release.

---

### M1 — F5-UX-WIZARD: instrucción sin ejemplo concreto

| Atributo | Detalle |
|---|---|
| **Estado** | Cosmético |
| **Prioridad** | Muy baja |
| **Archivos afectados** | `tz_core/mapping_wizard.py` (`build_mapping_intro_lines`, ~línea 1320) |

**Cambio:** `"F <valor fijo>"` → `"F <valor fijo> (ej: F Claro)"`.
Una línea de texto. Sin impacto en lógica ni tests.

---

### M2 — F8: label del prompt de nombre de archivo impreciso

| Atributo | Detalle |
|---|---|
| **Estado** | Cosmético |
| **Prioridad** | Muy baja |
| **Archivos afectados** | `tz_core/ui_utils.py` (~línea 376) |

**Cambio:** `"Nombre base del KML (Enter = {base_name}): "` → `"Nombre base de los archivos (Enter = {base_name}): "`.
El prompt controla HTML, KMZ, hashes y errores — no solo el KML.

---

### M3 — Mejoras al informe HTML

| Atributo | Detalle |
|---|---|
| **Estado** | Abierto — no bloqueante |
| **Prioridad** | Baja |
| **Archivos afectados** | `tz_core/html/` (múltiples módulos) |

**Ítems pendientes** (Versión B cerró omisiones silenciosas; estas son mejoras adicionales):

- Resumen analítico automático al inicio del informe
- Indicador de calidad de datos
- Tarjetas resumen por sección
- Resaltado de valores relevantes
- Índice navegable
- Tablas largas colapsables

Recomendados por GPT tras revisar el informe final. Candidatos para v1.1 si hay tiempo, o diferir a v1.2.

---

## 5. Congelados / horizonte de release

> No se tocan en v1.1.

| Ítem | Motivo | Dependencia |
|---|---|---|
| P0-A — Normalización tipo de evento (Decisiones 3–7) | Diseño congelado; requiere decisión formal | Prerequisito para i2 export |
| Exportación IBM i2 / Gephi | Bloqueada en P0-A | P0-A Decisiones 3–7 |
| Mejoras al QC Wizard (contexto, validación, guía tiempo real) | Fuera de alcance v1.1 | — |
| Manual técnico en PDF | Sin prioridad asignada | — |
| Empaquetado ejecutable (PyInstaller) | Paso final — requiere versión estable | Estabilización completa |

**Nota sobre P0-A y P0-B:** P0-B se implementó independientemente de P0-A. Cuando se retome P0-A, revisar si `tz_core/normalizacion/tipo_evento.py` (módulo aún no creado) requiere articulación con lo que P0-B ya implementó.

---

## 6. Horizonte futuro (fuera de alcance v1.1)

> Registrados para referencia. No afectan el cierre de v1.1.

- Google Pinpoint — acceso solicitado, sin respuesta
- "Mente maestra" — herramienta de gestión de casos (proyecto separado)
- Detector de saltos atípicos KMZ — candidato a especificación separada
- KMZ compacto vs detallado — versión futura

---

## 7. Cerrados y falsos positivos

> Excluidos del backlog activo. Documentados para trazabilidad.

| Ítem | Estado | Evidencia |
|---|---|---|
| P0-B — Clasificación de contactos | ✅ Cerrado | Commits 8da0541, caedc0b, 2bc42db |
| Versión B — Patrón omisión silenciosa | ✅ Cerrado | S1: 88764c6+f463781; S5: 6c93b15; S10: 8776f7d |
| KMZ — Implementación completa | ✅ Cerrado | Commits ca31418–e556288; revisión visual aprobada |
| F5-ALIASES — Migración aliases `_`-prefijados | ✅ Cerrado | cd4ec85; 0 ocurrencias verificadas |
| F6 — R=Remapear no documentado | ✅ Cerrado | Documentado en código y testeado |
| F7 — Integración IMEI fuera del wizard | ✅ Descartado | IMEI aparece como campo esencial |
| F9 — Artefactos de encoding en logs | ✅ Descartado | Provenían del Excel original de la operadora |
| F10 — Lista de columnas no visible durante el mapeo | ✅ Mitigado | `? ver columnas` cubre el riesgo principal |
| Skips en pytest | ✅ Intencionales | E2E: golden no inicializado; file_utils: Unix-only |
| Warning dateutil | ✅ Conocido | `validation_utils.py:292`; no bloqueante |
| `# TODO/FIXME/HACK` en código | ✅ Ninguno | Búsqueda agosto 2026: 0 resultados |

---

## 8. Orden recomendado hacia versión estable

```
1.  Actualización documental crítica
    → README (B1): conteo tests, descripción KMZ, estado P0-B/Versión B, listado de tests
    → TODO.md (B3): cerrar F6, F7, F9, F10, F5-ALIASES; actualizar decisión v1.1
    → ESPECIFICACION_KMZ (B2): actualizar tabla de estado

2.  Decisión sobre MATRIZ_SECCIONES (D2)
    → Revisar contenido → sanear si necesario → agregar a docs/ o documentar exclusión

3.  Correcciones cosméticas rápidas
    → F5-UX (M1): una línea en mapping_wizard.py
    → F8 (M2): una línea en ui_utils.py

4.  Evaluación de F2 y F3
    → Decidir si corregir comportamiento o solo agregar tests que documenten los límites
    → Mínimo: tests que cubran los gaps identificados

5.  Revisión macro
    → Arquitectura, modularidad, dependencias entre módulos
    → Verificar que orquestador sigue siendo solo orquestador

6.  Revisión micro
    → Docstrings, mensajes al usuario, manejo de errores
    → Duplicación de lógica entre módulos (analytics.py vs contacts.py para duración)

7.  Regresión completa
    → pytest -x -q → no debe disminuir cobertura ni aparecer ningún fallo
    → Actualizar el baseline al conteo resultante tras tests nuevos de F2/F3
    → Generar informe HTML con bitácora real TEL_61758498
    → Revisión visual del informe y del KMZ

8.  Empaquetado
    → Verificar que todos los assets (PNG, config.json, logo) se incluyen

9.  Prueba en máquina limpia
    → Sin venv preexistente, sin repo clonado
    → Flujo completo desde instalación hasta generación de informe

10. Etiqueta de versión estable
    → git tag v1.1.0
    → Actualizar README con número de versión y fecha
```

---

## Notas de auditoría

- **Auditoría realizada:** agosto 2026
- **Metodología:** revisión secuencial de TODO.md, README.md, docs/, comentarios de código (`# TODO/FIXME/HACK`), tests skipped, warning conocido, y friction points F2–F8 contra código real
- **Commit HEAD auditado:** 2bc42db
- **Tests al momento de auditoría:** 427 passed, 2 skipped, 1 warning
- **Documentos de referencia:** `MATRIZ_SECCIONES_HTML_v1_1_2.md`, `PLAN_NORMALIZACION_TIPO_EVENTO_v1_1.md`, `ESPECIFICACION_KMZ_ANTENAS_ACTIVACIONES_v1_1_1.md`, `SPEC_OPERATIVA_KMZ_IMPLEMENTACION_v1_1_2.md`
