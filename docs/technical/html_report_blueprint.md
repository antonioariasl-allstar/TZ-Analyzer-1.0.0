# HTML Report Generator Blueprint

## Progress
- 04/01/2026: Se eliminó el helper/HTML de "Contactos recientes"; sección desactivada en el monolito y tests retirados.
- 28/12/2025: Top contactos extraído a helper `build_top_contacts_sections` en `tz_core/html_generator.py`.
- 28/12/2025: Monolito delega la sección "Contactos con más comunicación" al helper (conteo y duración) usando overrides/config.
- 28/12/2025: Output HTML validado por usuario (prueba manual) sin regresiones visibles.

## 1. Scope

### 1.1 Objective

- Remove manual HTML construction from script_principal_bitacoras_refactory.py.
- Provide a deterministic API for html report generation inside tz_core/html_generator.py.
- Preserve identical HTML output (golden) for all supported datasets.

### 1.2 Current State (Baseline)

- Function `generar_informe_html()` in script_principal_bitacoras_refactory.py spans ~2,100 lines, mixing:
  - Metrics collection (KPI, antennas, contacts).
  - Branding/theme logic using CONFIG.
  - DOM assembly with inline CSS/JS.
  - Injection of sections computed elsewhere (HTML_SECCION_INTERACCIONES, etc.).
- Partial extraction exists for header/body/KPI via `generate_html_header/body_header/metadata/kpi` functions.
- Many helpers (fmt_dt, row_html, generar_historial_cambios_antena) are already in tz_core modules.

### 1.3 Critical Requirements
- **No functional regression**: golden HTML `tests/golden/html_normalized.txt` must remain identical.
- **Hybrid fallback**: if modular generator fails, legacy path must still work (Strangler Fig pattern).
- **Same inputs/outputs**: new API must accept a plain DataFrame + metadata and return HTML path (string) like current function.
- **Config integration**: use `CONFIG` (global) for style, branding, overrides, geografía, etc.

## 2. Dependency Map

### 2.1 Inputs
1. `df` (pandas.DataFrame): columns (fecha, hora, lat, long, antena, tel_contacto, duracion, etc.)
2. `archivo_kml`: absolute path to generated KML (used for relative links)
3. `carpeta_salida`: output directory (HTML, KML, KMZ, TXT, hashes)
4. `nombre_salida`: base name for outputs (prefix for HTML file)
5. Optional metadata: `hoja`, `nombre_bitacora`
6. Global `CONFIG`: branding, style, top lists, geografía, salida, html overrides
7. Globals produced earlier in script:
   - `OVERRIDE_TOPS`: overrides for top N
   - `HTML_SECCION_*` (interacciones, todos_contactos, antenas serializadas) built by tz_core helpers

### 2.2 Internal Data Dependencies (per section)

| Section | Input columns | Extra dependencies |
| --- | --- | --- |
| Validations (df empty, None) | — | logging_utils.log |
| KPI totals | `lat`, `long`, `antena`, `celda/cid`, `lac`, `fecha`, `hora` | pandas, fmt_dt |
| Identification table | tel/alias/usuario/abonado/imei/imsi columns | html_helpers: `row_html`, `fmt_imei_item`, `is_valid_imei`, `luhn_check`, `unique_values_in`, `first_nonempty_in`, `nunique_in` |
| Top contactos | `tel_contacto/contacto`, `duracion` | CONFIG overrides, `_to_seconds_any` helper |
| Antennas section | `antena`, `lat`, `long`, `azimut`, `fecha`, `hora` | numpy, Google Maps links |
| Heatmap + markers | `antena`, `lat`, `long`, `azimut` | json, Leaflet JS, `_valid_latlon` |
| Antenas por rango | `antena`, `lat`, `long`, `azimut`, `fecha`/`hora` | numpy, pandas datetime |
| Historial cambios antena | DataFrame full | tz_core.analytics.generar_historial_cambios_antena |
| Contactos recientes (deprecated, removido 04/01/2026) | — | — |
| Branding / H1 / logos | CONFIG.brand / CONFIG.branding | base64, mimetypes |
| TOC / Sticky nav | HTML string manipulations | CSS/JS injection |
| Watermark | CONFIG.branding | CSS injection |
| Todos los contactos | Provided by tz_core contact module (HTML string) |
| Interacciones (últimos días) | Provided by tz_core html_helpers | inserted via global |
| JS enhancements | default | manipulates `html` string before writing |
| Final assembly | `carpeta_salida`, `nombre_salida` | writes HTML file |

### 2.3 External Modules Referenced
- `tz_core.html_helpers`: `fmt_dt`, `row_html`, `first_nonempty_in`, `unique_values_in`, `fmt_imei_item`, `luhn_check`, `is_valid_imei`, `nunique_in`.
- `tz_core.analytics`: `generar_historial_cambios_antena`.
- `tz_core.ui_utils`: may supply HTML sections via globals.
- `tz_core.config_manager`: `CONFIG`, `cargar_config` wrappers.
- `tz_core.utils` & `format_utils`: general formatting helpers.
- `logging_utils.log`: error/warning reporting.

## 3. Proposed API (HTMLReportGenerator)

### 3.1 Entry Point
```python
from tz_core.html_generator import HTMLReportBuilder

builder = HTMLReportBuilder(config=CONFIG)
html_path = builder.generate(
    df=df,
    archivo_kml=archivo_kml,
    carpeta_salida=carpeta_salida,
    nombre_salida=nombre_salida,
    hoja=hoja,
    nombre_bitacora=nombre_bitacora,
    extras={
        "kml_exists": bool,
        "kmz_exists": bool,
        "sections": {
            "interacciones": HTML string,
            "todos_contactos": HTML string,
            "antenas_serializadas": HTML string,
        },
        "overrides": OVERRIDE_TOPS
    }
)
```
- `generate()` returns absolute path to `{nombre_salida}_informe.html` (existing behavior).
- `extras` is a flexible dict for precomputed sections/global flags (keeps compatibility while migrating).

### 3.2 Internal Structure
```
HTMLReportBuilder
├── __init__(config, logger=log)
├── generate(inputs)
│   ├── _prepare_context(df, metadata, overrides)
│   ├── _build_sections(context)
│   │   ├── _section_metadata
│   │   ├── _section_kpis
│   │   ├── _section_antenas_resumen
│   │   ├── _section_heatmap
│   │   ├── _section_antenas_rangos
│   │   ├── _section_historial
│   │   ├── _section_contactos_top
│   │   └── _inject_external_sections
│   ├── _assemble_html(sections, branding)
│   └── _write_file(html, output_path)
└── _fallback_legacy(error)
```
- Each `_section_*` returns HTML strings, using helpers already in module or imported.
- `_assemble_html` orchestrates header/body/TOC/JS injection (currently inline string operations).
- `_write_file` handles encoding and returns path.
- `_fallback_legacy` can call original `generar_informe_html` body (kept in legacy module) if something explodes.

### 3.3 Required Context Object
```python
@dataclass
class ReportContext:
    df: pd.DataFrame
    archivo_kml: str
    carpeta_salida: str
    nombre_salida: str
    hoja: str | None
    nombre_bitacora: str | None
    overrides: dict
    config: dict
    metrics: dict   # filled by _prepare_context
    sections: dict  # references to precomputed global sections
```
- `metrics` holds computed values (totals, antena stats, contact lists) to avoid recomputing in each section.

## 4. Migration Steps

### Step 1 – Context Builder
1. Extract metrics calculation (totals, KPIs, identification lists) into `_prepare_context` returning `metrics` dict.
2. Keep legacy function but delegate metrics to new builder; confirm golden tests.

### Step 2 – Section Extraction (incremental)
1. Move “Top contactos” block into `_section_contactos_top` (use metrics).
2. Move “Antenas más activadas” block into `_section_antenas_resumen`.
3. Continue with heatmap, rangos, historial. (Contactos recientes se eliminó del alcance.)
4. Each move: run `pytest tests/test_e2e_regresion.py` to ensure no diff.

### Step 3 – Assembly & Branding
1. Centralize CSS/JS injections in `_assemble_html`.
2. Parameterize theme, watermark, TOC logic.
3. Drop code duplication (e.g., repeated H1 logic) once centralized.

### Step 4 – Legacy Wrapper
1. Replace current body of `generar_informe_html()` with:
   ```python
   def generar_informe_html(...):
       builder = HTMLReportBuilder(CONFIG)
       try:
           return builder.generate(...)
       except Exception:
           log("[ERROR] HTML builder failed; falling back to legacy path")
           return _generar_informe_html_legacy(...)
   ```
2. Keep `_generar_informe_html_legacy` as private function (copy of current implementation) until we trust builder fully.

## 5. Validation Strategy

1. After each section extraction, run:
   - `pytest tests/test_e2e_regresion.py`
   - Manual diff vs `tests/golden/html_normalized.txt` if needed.
2. Optionally add unit tests for `_prepare_context` and `_section_*` using synthetic DataFrames in `tests/unit/test_html_generator.py`.
3. Document progress in [ESTADO_ACTUAL_MODULARIZACION.md](../ESTADO_ACTUAL_MODULARIZACION.md).

## 6. Risk Mitigations

- **Encoding issues**: ensure builder writes file with `encoding='utf-8'` same as legacy.
- **CONFIG dependencies**: pass config explicitly to builder; avoid global reads inside modules whenever possible.
- **External sections**: treat `HTML_SECCION_*` as optional extras; builder just injects them if provided.
- **Large HTML string manipulations**: consider using BeautifulSoup or template engine later, but not during migration to avoid diff noise.

## 7. Next Actions

1. Implement `HTMLReportBuilder` skeleton with `_prepare_context` placeholder.
2. Move KPI + metadata + basic structure assembly first (the part already partially modularized) to ensure builder pipeline works end-to-end.
3. Gradually migrate each section per plan; update docs/tests after each milestone.
