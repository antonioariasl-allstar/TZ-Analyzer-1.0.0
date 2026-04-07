# PLAN MAESTRO DE CONSOLIDACIÓN — TZ Analyzer v1.0.0

**Versión:** 1.0  
**Fecha:** 07 de abril de 2026  
**Autores:** Tony (lead), Claude (Anthropic), GPT-4o (OpenAI) — consenso entre los 3  
**Estado:** APROBADO — Listo para ejecución  

---

## Propósito de este documento

Este documento es la **fuente única de verdad** para cualquier chat, agente o sesión de Copilot que trabaje sobre TZ Analyzer a partir de abril 2026. Contiene el diagnóstico consensuado, las decisiones tomadas, la ruta de ejecución aprobada y los protocolos de trabajo.

**Si estás leyendo esto al inicio de un chat nuevo:** este documento te dice exactamente en qué estado está el proyecto, qué viene después y cómo ejecutar. No necesitas analizar el repo desde cero.

---

## 1. Diagnóstico del proyecto (estado al 07 abril 2026)

### 1.1 Métricas clave

| Métrica | Valor |
|---------|-------|
| Líneas de producción (sin tests/tools/docs) | 15,422 |
| Módulos en `tz_core/` | 38 |
| Monolito (`script_principal_bitacoras_refactory.py`) | 856 líneas |
| Reducción del monolito original | 87% (de ~6,500 a 856) |
| Archivos de test | 24 (18 unit + 3 integration + 3 helpers) |
| Dependencias en requirements.txt | 13 |
| Ramas remotas | 19 (solo 3 con commits no mergeados) |

### 1.2 Arquitectura actual

El proyecto completó exitosamente la **Fase 1 de modularización** (romper el monolito). Toda la lógica vive ahora en `tz_core/`. El monolito solo orquesta.

El pipeline real del sistema es:

```
DATA (entrada) → TRANSFORM (normalización) → OUTPUT (HTML + KML)
```

Estado por capa:

| Capa | Estado | Notas |
|------|--------|-------|
| DATA (I/O, carga, config) | Modular y estable | `bitacora_io`, `data_loader`, `config_loader`, `config_manager` |
| TRANSFORM (schema, normalización, analytics) | Modular y estable | `schema_utils`, `data_normalizer`, `analytics`, `time_utils` |
| OUTPUT (HTML, KML) | **Parcialmente monolítico** | `kml_generator` OK (884 ln), pero `html_generator.py` = 3,482 líneas |

### 1.3 El problema central

`html_generator.py` no es un "archivo grande". Es un **subsistema comprimido en un archivo**:

- 3,482 líneas = **25% de todo el código de producción**
- 18+ funciones públicas
- Mezcla 4 responsabilidades distintas:
  - Construcción de secciones individuales (KPI, contactos, antenas, metadata)
  - Lógica de datos dentro de las secciones
  - Ensamblado del documento HTML final
  - Inyección de metadata técnica

Este es el **cuello de botella real** del proyecto. Todo lo demás está sano.

### 1.4 Deuda técnica secundaria

| Issue | Severidad | Esfuerzo |
|-------|-----------|----------|
| `html_generator.py` como segundo monolito | ALTA | Grande |
| Variables globales con `globals()` en el orquestador | ALTA | Medio |
| `validaciones.py` y `utilidades.py` siguen en raíz | MEDIA | Bajo |
| `requirements.txt` en UTF-16LE (rompe CI) | MEDIA | Trivial |
| Mojibake en comentarios del monolito (línea 218+) | MEDIA | Trivial |
| `__init__.py` exporta aliases obsoletos (`_hhmmss_to_time_or_none`, etc.) | MEDIA | Bajo |
| 16+ ramas remotas muertas | MEDIA | Trivial |
| `python-pptx` en requirements sin usarse | BAJA | Trivial |
| `schema.fields` vacío en config.json | BAJA | Medio |

---

## 2. Decisiones tomadas

### D1: ¿Qué hacer con html_generator.py?

**Decisión: SUBDIVIDIR en sub-paquete `tz_core/html/` con estructura plana.**

No mantenerlo como archivo único (error estratégico a mediano plazo). No subdividir con carpetas anidadas (`sections/`, `templates/`) — innecesario para el volumen actual.

Estructura objetivo:

```
tz_core/html/
    __init__.py          ← re-exporta todo para compatibilidad de imports
    assembler.py         ← generar_informe_html() — punto único de ensamblaje
    kpi.py               ← generate_kpi_section, prepare_report_metrics
    contacts.py          ← build_top_contacts_sections
    antennas.py          ← build_antennas_table, build_top_antennas_section, build_antennas_by_hour_section
    metadata.py          ← generate_metadata_section, inject_technical_metadata, build_identification_rows
    header.py            ← generate_html_header, generate_body_header, build_logo_html
    helpers.py           ← html_helpers reutilizables, funciones internas compartidas
```

Notas:
- `interacciones_builder.py` ya existe como módulo separado (673 líneas). No se re-extrae, se integra por referencia.
- `html_helpers.py`, `html_toc.py` y `html_utils.py` ya existen en `tz_core/`. Se evaluará si se absorben en `tz_core/html/helpers.py` o se mantienen aparte.
- Cada módulo debe cumplir la regla: **"puedo generar esta sección sin conocer el resto del HTML"**.

### D2: ¿Qué hacer con las variables globales?

**Decisión: Eliminar globals secundarios de forma incremental. NO tocar CONFIG aún.**

Eliminar primero:
- `globals()["OVERRIDE_TOPS"]` → convertir en return value del pipeline
- `globals().get("HTML_SECCION_TODOS_CONTACTOS")` → return value
- `globals().get("HTML_SECCION_INTERACCIONES")` → return value

`CONFIG` como global se mantiene temporalmente. Introducir un context object (dataclass) implicaría cambiar firmas en cascada y el beneficio no justifica el riesgo antes de completar el split HTML.

### D3: ¿Migrar los archivos legacy en raíz?

**Decisión: SÍ, absorber ahora.**

- `validaciones.py` (367 líneas): `validar_datos()` → absorber en `tz_core/` (módulo a definir). `guardar_errores()` → a `tz_core/file_utils.py` o similar.
- `utilidades.py` (190 líneas): funciones de Tkinter file dialog. `bitacora_io.py` ya importa de aquí con fallback condicional. Absorber y eliminar.

No aporta nada dejarlos pendientes.

---

## 3. Ruta de ejecución aprobada

### Tabla de fases

| Fase | Acción | Riesgo | Validación | Rama |
|------|--------|--------|------------|------|
| **F0** | Limpieza: encoding requirements.txt, eliminar python-pptx de deps, borrar ramas muertas, fix mojibake en monolito | Nulo | `pip install -r requirements.txt` limpio, repo sin ramas obsoletas | `chore/cleanup-f0` |
| **F1** | Absorber `validaciones.py` y `utilidades.py` en `tz_core/`. Eliminar archivos raíz | Bajo | `pytest` completo + smoke manual del flujo | `refactor/absorb-legacy-f1` |
| **F2** | Eliminar `globals()` secundarios (`OVERRIDE_TOPS`, secciones HTML). Reemplazar por return values en el pipeline | Bajo-Medio | `pytest` completo + golden output | `refactor/remove-globals-f2` |
| **F3** | Mapear dependencias internas de `html_generator.py`. Producir documento/matriz de dependencias | Nulo (solo análisis) | Documento entregado y revisado | `docs/html-deps-map-f3` |
| **F4** | Split `html_generator.py` → `tz_core/html/` con estructura plana | Medio | **Golden output byte-identical** | `refactor/html-split-f4` |
| **F5** | Limpiar exports obsoletos en `__init__.py` | Bajo | `pytest` completo | `chore/clean-exports-f5` |

### Diagrama de dependencias entre fases

```
F0 (limpieza)
 └→ F1 (legacy)
     └→ F2 (globals)
         └→ F3 (mapa de deps)
             └→ F4 (split HTML)     ← requiere golden output capturado PRE-split
                 └→ F5 (exports)
```

Cada fase depende de la anterior. No se salta. No se ejecutan en paralelo.

---

## 4. Protocolo de ramas y commits

### 4.1 Estrategia de branching

Se usa **una rama por fase**, nombrada según la convención:

```
<tipo>/<descripcion-corta>-<fase>
```

Tipos válidos: `chore/`, `refactor/`, `docs/`, `feat/`, `fix/`

Ejemplos concretos:
- `chore/cleanup-f0`
- `refactor/absorb-legacy-f1`
- `refactor/remove-globals-f2`
- `docs/html-deps-map-f3`
- `refactor/html-split-f4`
- `chore/clean-exports-f5`

### 4.2 Ciclo de vida de cada rama

```
1. Crear rama desde main:
   git checkout main
   git pull origin main
   git checkout -b <tipo>/<nombre>-<fase>

2. Trabajar en la rama (commits atómicos)

3. Antes de merge — checklist obligatorio:
   [ ] python -m py_compile <archivos tocados>
   [ ] pytest tests/ -q  (todos pasan)
   [ ] Smoke manual si la fase lo requiere
   [ ] Golden output idéntico (si aplica, F2+)

4. Merge a main:
   git checkout main
   git merge <rama> --no-ff
   git push origin main

5. Eliminar rama después del merge:
   git branch -d <rama>
   git push origin --delete <rama>
```

### 4.3 Reglas de commits

- **Un commit = un cambio lógico**. No mezclar limpieza con refactor.
- **Mensaje con prefijo convencional:**
  - `chore:` para limpieza, deps, ramas
  - `refactor:` para cambios de estructura sin cambio funcional
  - `docs:` para documentación pura
  - `fix:` para corrección de bugs
  - `feat:` para funcionalidad nueva
- **Formato:** `<prefijo>(<scope>): descripción corta`
  - Ejemplo: `refactor(f1): absorber validar_datos en tz_core/data_normalizer`
  - Ejemplo: `chore(f0): convertir requirements.txt a UTF-8`

---

## 5. Protocolo del golden output

### Qué es

Un golden output es un HTML generado con datos de prueba conocidos que se guarda como referencia. Después de cualquier cambio en el pipeline de salida, se regenera el HTML y se compara contra el golden. Si son idénticos, el cambio no introdujo regresión.

### Cuándo es obligatorio

- **F2 en adelante**: cualquier cambio que toque el pipeline de salida.
- **F4 especialmente**: antes de iniciar el split de html_generator.py, el golden debe estar capturado y versionado.

### Cómo capturarlo

El proyecto ya tiene infraestructura para esto:
- `tests/golden/` — directorio de golden outputs existente
- `tools/capture_golden_baseline.py` — script de captura existente

Protocolo:

```
1. ANTES del cambio:
   python tools/capture_golden_baseline.py
   → Guarda output en tests/golden/

2. Hacer el cambio

3. DESPUÉS del cambio:
   python tools/capture_golden_baseline.py --compare
   → Compara contra el golden guardado
   → Si hay diferencias: investigar antes de continuar
```

Si el script de captura necesita ajustes, eso se hace en F2 como parte de la preparación.

### Regla de control de regresión (no negociable)

> **"Ningún cambio en Fase 2+ avanza si el HTML generado no es idéntico byte a byte contra el golden baseline."**

Sin excepción. No hay "se ve igual", no hay "solo cambió un espacio". Si `diff` reporta diferencia, el cambio no se mergea hasta investigar y resolver. Esta regla convierte el plan entero en algo demostrable, no en esperanza.

Complemento para F2 — regla de firmas:

> **"Si un cambio de globals modifica una firma de función, se cambia una sola función a la vez."**

No se agrupan cambios de firma en un solo commit. Cada función tocada se valida individualmente antes de continuar con la siguiente.

---

## 6. Protocolo de sincronización entre chats

### Al iniciar un chat nuevo (Claude, GPT, Copilot)

El asistente debe pedir o recibir esta información antes de ejecutar cualquier cambio:

```
1. Pega el contenido de: docs/PLAN_CONSOLIDACION_CONSENSO.md
   (este documento — fuente de verdad)

2. Pega el estado actual:
   git status
   git diff --stat
   git log --oneline -5
   git branch

3. Indica en qué fase estás trabajando (F0, F1, F2...)
```

### Reglas para el asistente

- **No proponer cambios arquitectónicos** que contradigan este documento sin discusión explícita con Tony.
- **No saltar fases**. Si Tony pide trabajar en F4 sin haber completado F2, el asistente debe señalarlo.
- **No tocar CONFIG global** hasta que se decida explícitamente en una fase futura.
- **Seguir la metodología paranoica**: analizar → planificar → ejecutar → probar → commit. Sin atajos.
- **Un cambio a la vez**. No agrupar múltiples refactors en un solo commit.

---

## 7. Lo que NO se toca

Estas decisiones ya están tomadas y no se reabren sin consenso explícito:

| Decisión | Razón |
|----------|-------|
| La arquitectura base (orquestador + tz_core/) es estable | 14 Epics de validación |
| `CONFIG` como global se mantiene por ahora | Cambiar implicaría cascada de firmas |
| `interacciones_builder.py` se mantiene separado | Ya está extraído y funcionando |
| `kml_generator.py` no se toca | Ya está unificado y limpio (884 ln) |
| TZ Analyzer y "Mente Maestra" son proyectos separados | Integración vía outputs, no fusión |
| "Web app" = localhost, no internet | Requisito forense de custodia de datos |

---

## 8. Métricas de éxito por fase

### F0 — Limpieza
- [ ] `requirements.txt` es UTF-8 válido
- [ ] `python-pptx` eliminado de dependencias
- [ ] Ramas remotas reducidas a ≤5 (main + activas)
- [ ] Cero mojibake en el monolito
- [ ] `pip install -r requirements.txt` funciona limpio

### F1 — Absorber legacy
- [ ] `validaciones.py` eliminado de raíz
- [ ] `utilidades.py` eliminado de raíz
- [ ] Cero imports de archivos raíz en `tz_core/`
- [ ] `pytest` completo sin fallos nuevos
- [ ] Smoke manual del flujo completo OK

### F2 — Eliminar globals secundarios
- [ ] Cero uso de `globals()` en el orquestador
- [ ] `OVERRIDE_TOPS` se pasa como parámetro
- [ ] Secciones HTML se devuelven como return values
- [ ] Golden output idéntico al baseline
- [ ] `pytest` completo sin fallos nuevos

### F3 — Mapa de dependencias HTML
- [ ] Documento producido con:
  - Lista de funciones públicas de html_generator.py
  - Qué datos recibe cada función
  - Qué HTML produce cada función
  - Dependencias entre funciones
  - Funciones ya extraídas (interacciones_builder, html_helpers, etc.)
- [ ] Documento revisado y aprobado por Tony

### F4 — Split HTML
- [ ] `html_generator.py` eliminado
- [ ] `tz_core/html/` creado con estructura plana
- [ ] `tz_core/html/__init__.py` re-exporta todas las funciones públicas
- [ ] Todos los imports existentes siguen funcionando
- [ ] **Golden output byte-identical** al capturado pre-split
- [ ] `pytest` completo sin fallos nuevos

### F5 — Limpiar exports
- [ ] Cero aliases con prefijo `_` en `__init__.py`
- [ ] `pytest` completo sin fallos nuevos

---

## 9. Contexto del proyecto (para chats que no lo conocen)

TZ Analyzer es una herramienta forense de análisis de registros telefónicos. Desarrollada por Tony (analista forense e investigador). Procesa bitácoras de llamadas/datos en formato Excel y genera:

- **Reportes HTML** detallados con análisis de contactos, antenas, interacciones y KPIs
- **Archivos KML/KMZ** para visualización geográfica en Google Earth

El proyecto se desarrolla con asistencia de IA (Claude, GPT, Copilot) y sigue una metodología estricta de cambios atómicos con validación manual antes de cada commit.

Stack: Python 3.12, pandas, simplekml, openpyxl. Sin framework web. CLI interactiva con Tkinter para diálogos de archivo.

Repo: `https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0`

---

*Documento generado por consenso entre Claude (Anthropic), GPT-4o (OpenAI) y Tony (lead del proyecto). Abril 2026.*
