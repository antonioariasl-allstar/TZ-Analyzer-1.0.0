# Mapa del pipeline

## 1) Contrato de arranque
- Invariante: `bootstrap_config()` → `main()` (orquestación).
- Qué inicializa `bootstrap_config`:
  - Globals: `CONFIG`, `RENAME_MAP`.
  - Carga de config vía `tz_core.config_loader.get_config` (`core_get_config`).
  - Construcción de mapa de sinónimos vía `tz_core.config_loader.cfg_build_rename_map`.
  - Banner básico (stdout). No cambios de rutas.
  - Logging adicional: no en `bootstrap_config`; logging básico se arma en `run.py`.
- Entry points y rol:
  - `run.py`: entry principal para usuarios finales; configura `logging.basicConfig` y maneja errores; invoca `tz_core.app_runner.run`.
  - `tz_core/app_runner.py`: fachada mínima; importa perezosamente `bootstrap_config` y `main` desde `script_principal_bitacoras_refactory.py`; llama `bootstrap_config()` y luego `main()`.
  - `script_principal_bitacoras_refactory.py`: contiene `bootstrap_config` y `main` (orquestador monolítico).

## 2) Etapas del pipeline (ordenadas)
1. **Contexto / selección de modo**
   - Función: `main`
   - Módulo: `script_principal_bitacoras_refactory.py`
   - Inputs: `CONFIG` global ya cargado; `input/print`; helpers UI.
   - Outputs: `context` (modo/option), `CONFIG` (posible ajuste de colores), logs en memoria.

2. **Carga dataset**
   - Función: `gather_dataset_metadata`
   - Módulo: `tz_core/ui_utils.py`
   - Inputs: prompt `input`, `seleccionar_archivo`, `seleccionar_hoja_visible`, `cargar_excel_con_normalizacion`.
   - Outputs: `dataset` (archivo, hoja, dataframe, columnas originales); logs via `log_dataset_stats`.

3. **Validación inicial / schema + mapeo columnas**
   - Función: `run_ingestion_pipeline`
   - Módulo: `tz_core/manual_flow.py`
   - Inputs: `df`, `CONFIG`, `original_columns`, `MANUAL_QC_MAPPING`, `ALIAS_VISIBLES`, `wizard_io_factory`, `persist_synonym_fn`, `validate_schema_fn`, `validar_datos_fn`, `time_filter_option`, `_solicitar_filtros_tiempo`, `_aplicar_filtros_tiempo`, `_run_manual_mapping`.
   - Outputs: `ingestion.dataframe` (normalizado/renombrado), `ingestion.errores`, `ingestion.time_filters`; logs de errores/filtros; puede abortar si schema inválido.

4. **Health checks**
   - Función: `run_health_checks`
   - Módulo: `tz_core/health_utils.py`
   - Inputs: dataframe post-ingestión, `CONFIG`, logger/output.
   - Outputs: boolean (continúa o aborta); logs con métricas básicas.

5. **Setup de salidas / identidad de caso**
   - Función: `prepare_output_setup`
   - Módulo: `tz_core/output_flow.py`
   - Inputs: `df`, `CONFIG`, `time_filters`, `nombre_base`, prompts (`prompt_case_identity`, `suggest_case_name`, `collect_top_overrides`, `prompt_output_routing`), selección de carpeta (`seleccionar_carpeta_salida`), `ensure_dir`, `sanear_nombre_archivo`.
   - Outputs: `output_setup` (identity, sugerencias, `nombre_salida`, `carpeta_base`, `carpeta_salida`, `archivo_kml`, `archivo_kmz`, `top_antenas`, `top_contactos`). Side effects: crea carpeta destino si aplica.

6. **HTML manual preliminar (cuando corresponde)**
   - Función: `handle_manual_html_generation`
   - Módulo: `tz_core/manual_flow.py`
   - Inputs: `CONFIG`, `df`, rutas de salida, `generar_informe_html`, `relocate_kmz_file`, logger/output.
   - Outputs: `informe_html` (ruta/metadata); side effect: posible KMZ reubicado.

7. **Log mínimo de filtros (opcional)**
   - Función: `write_minimal_filter_log_if_needed`
   - Módulo: `tz_core/manual_flow.py`
   - Inputs: `time_filters`, `df`, carpeta de salida, logger.
   - Outputs: archivo de log mínimo (si aplica).

8. **Prep meta para KML**
   - Función: `prep_meta_unicos`
   - Módulo: `tz_core/schema_utils.py`
   - Inputs: `df`, columnas objetivo (`alias`, `nombre_usuario`, `abonado`), logger.
   - Outputs: dataframe con placeholders “SinInf” cuando faltan; listo para KML.

9. **Generación KML**
   - Función: `generar_kml`
   - Módulo: `tz_core/kml_generator.py`
   - Inputs: dataframe normalizado, `archivo_kml`, flags de flatten.
   - Outputs: `archivo_kml` escrito en disco; `desc_coords` (coordenadas descartadas); logs.

10. **Construcción de secciones HTML (interacciones/contactos)**
    - Funciones: `_construir_seccion_interacciones` (monolito) y `construir_seccion_todos_contactos` (`tz_core/analytics.py`)
    - Inputs: dataframe filtrado, CONFIG, parámetros de salida.
    - Outputs: HTML parcial en memoria; almacenado vía callbacks `_store_interacciones` / `_store_contactos`.

11. **Flujo de salidas consolidado (HTML + KMZ + hashes + resumen)**
    - Función: `run_outputs_flow`
    - Módulo: `tz_core/output_runner.py`
    - Inputs: dataframe, CONFIG, rutas (`nombre_salida`, `archivo_kml`, `carpeta_base`, `carpeta_salida`, `archivo_entrada`, `hoja`, `archivo_errores`), `desc_coords`, builders de secciones, `generar_informe_html` (`tz_core/html_generator.py`), `relocate_kmz_file` (`tz_core/file_utils.py`), `escribe_hashes_txt` (`tz_core/file_utils.py`), `produce_case_outputs` (monolito), `summarize_outputs` (`tz_core/ui_utils.py`), logger/output.
    - Outputs: dict con rutas `html`, `kmz`, `hashes`; logs resumen en consola/memoria.

## 3) Salidas del sistema (inventario)
- **HTML principal**: generado por `generar_informe_html` (`tz_core/html_generator.py`); escrito en `carpeta_salida` con base `nombre_salida` (ej.: `<carpeta>/<nombre>.html`).
- **KML**: generado por `generar_kml` (`tz_core/kml_generator.py`); ruta `archivo_kml` dentro de `carpeta_salida`/`carpeta_kml`.
- **KMZ**: reubicado por `relocate_kmz_file` (`tz_core/file_utils.py`); suele terminar junto al HTML/KML en `carpeta_salida`.
- **Hashes**: `escribe_hashes_txt` (`tz_core/file_utils.py`) crea `HASHES.txt` (naming exacto en código; carpeta de salidas).
- **Log de ejecución**: el propio `run_tz_analysis` (wrapper interno) captura stdout/stderr y escribe `ejecucion_log.txt` junto a las salidas detectadas.
- **Log mínimo de filtros** (opcional): `write_minimal_filter_log_if_needed` (`tz_core/manual_flow.py`) en la carpeta de salida.

## 4) Dependencias clave (alto nivel)
- `tz_core/config_loader.py`: carga config y sinónimos (`get_config`, `cfg_build_rename_map`).
- `tz_core/manual_flow.py`: ingestión, filtros de tiempo, generación HTML manual preliminar, log mínimo.
- `tz_core/output_flow.py`: preparación de salidas (nombres, carpetas, top N overrides).
- `tz_core/output_runner.py`: orquesta salidas HTML/KML/HASHES y logging de resumen.
- `tz_core/ui_utils.py`: prompts de identidad, dataset, resumen de outputs.
- `tz_core/mapping_wizard.py` y `tz_core/manual_mapping_helpers.py`: mapeo QC de columnas.
- `tz_core/health_utils.py`: health checks previos a salidas.
- `tz_core/html_generator.py`: render HTML final y secciones auxiliares.
- `tz_core/kml_generator.py`: generación de KML/KMZ.
- `tz_core/file_utils.py`: mover KMZ, escribir hashes.
- `tz_services/geo_tools.py`: wrapper de compatibilidad (reexporta funciones geográficas) usado indirectamente por KML.
- Monolito `script_principal_bitacoras_refactory.py`: orquestador actual; mantiene wrappers de compatibilidad y flujo de menú.

## 5) Riesgos conocidos / puntos frágiles
- Globales: `CONFIG`, `RENAME_MAP`, `LOGS`, `LOG_PLACEHOLDERS`, `OVERRIDE_TOPS` se mutan y dependen de orden de llamada `bootstrap_config() -> main()`.
- Side-effects: impresiones `print`, logging global (`logging.basicConfig` en `run.py`), escritura de archivos (HTML, KML/KMZ, hashes, logs) y creación de carpetas.
- Import paths: CI Windows requiere `PYTHONPATH` con repo root (workaround ya aplicado en workflow). Import perezoso en `tz_core/app_runner.py` evita efectos secundarios en tests.
- Manual mapping/wizard: depende de prompts y globals; errores aquí pueden abortar ingestión.
- KML/HTML generan archivos en disco; fallos de permisos/rutas afectan salidas.
- Filtros de tiempo: si dejan dataframe vacío, salida aborta tras aviso.
- `validaciones` fallback: se carga condicionalmente; comportamientos mínimos podrían diferir si no está presente (anotar “pendiente” en validación exhaustiva).
