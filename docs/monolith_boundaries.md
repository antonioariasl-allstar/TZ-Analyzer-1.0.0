# Fronteras del monolito

## 1) Principios de extracción
- Mantener el contrato `bootstrap_config()` → `main()` intacto hasta que exista un reemplazo probado.
- No mover lógica que dependa de `CONFIG`/`RENAME_MAP` globales sin un plan de inicialización equivalente.
- Evitar tocar código con prompts/IO interactivo y efectos de archivos en la misma iteración.
- No mezclar extracción con cambios funcionales; cada extracción debe ser comportamiento-equivalente.
- Señales de alto riesgo: dependencias en globals mutables, side-effects múltiples (print/log/escrituras), mezcla UI+lógica, rutas de salida implícitas, fallback condicional (`validaciones`).

## 2) Clasificación de etapas del pipeline
- 🟢 Contexto / selección de modo (`main`, script_principal_bitacoras_refactory.py): UI ligera y logging; separable a corto plazo si se respeta contrato de retorno.
- 🟢 Carga dataset (`gather_dataset_metadata`, tz_core/ui_utils.py): ya modular; extracción adicional es bajo riesgo.
- 🟢 Health checks (`run_health_checks`, tz_core/health_utils.py): lógico y puro; bajo riesgo.
- 🟢 Prep meta para KML (`prep_meta_unicos`, tz_core/schema_utils.py): puro; bajo riesgo.
- 🟢 Flujo de salidas consolidado (`run_outputs_flow`, tz_core/output_runner.py): ya en módulo separado; bajo riesgo si se mantiene API.

- 🟡 Validación inicial / schema + mapeo (`run_ingestion_pipeline`, tz_core/manual_flow.py): depende de CONFIG, wizard y prompts; riesgo moderado.
- 🟡 Setup de salidas / identidad (`prepare_output_setup`, tz_core/output_flow.py): mezcla prompts y rutas de salida; riesgo moderado.
- 🟡 HTML manual preliminar (`handle_manual_html_generation`, tz_core/manual_flow.py): mueve KMZ y escribe HTML; side-effects, riesgo moderado.
- 🟡 Log mínimo filtros (`write_minimal_filter_log_if_needed`, tz_core/manual_flow.py): pequeño pero escribe disco; moderado.
- 🟡 Construcción secciones HTML (`_construir_seccion_interacciones`, script monolito; `construir_seccion_todos_contactos`, tz_core/analytics.py): mezcla HTML y datos; moderado por dependencias de globals.

- 🔴 Generación KML (`generar_kml`, tz_core/kml_generator.py) + wrapper geo: side-effects de archivos y dependencias geográficas; mantener sin mover hasta estabilizar rutas/CONFIG.
- 🔴 Flujo de menú completo y prompts combinados en `main` (script monolito) más mapeo manual: alto acoplamiento UI+estado; no extraer hasta aislar entradas/salidas.
- 🔴 Fallback `validaciones` y globals LOGS/LOG_PLACEHOLDERS/OVERRIDE_TOPS: alto riesgo por compatibilidad y mutabilidad global; no mover aún.

## 3) Dependencias críticas
- Globals críticos: `CONFIG`, `RENAME_MAP`, `LOGS`, `LOG_PLACEHOLDERS`, `OVERRIDE_TOPS`; su orden de inicialización es frágil.
- Mezcla UI + lógica: `main` y `run_ingestion_pipeline` (prompts, mapeo manual), `prepare_output_setup` (prompts de identidad/ruta), construcción HTML en el monolito.
- Side-effects peligrosos: escritura de HTML/KML/KMZ/hashes/logs, creación de carpetas, `print` y `logging.basicConfig` global, relocation de KMZ, captura de stdout/stderr en `run_outputs_flow` wrapper.

## 4) Orden recomendado de extracción
1) Congelar contrato de entrada (`run.py`/`app_runner.run`) y documentar invariantes (ya hecho en pipeline map). Ganancia: claridad de boundary de arranque.
2) Extraer/documentar adapters de UI para dataset y health checks (etapas 🟢); bajo riesgo y mejora testabilidad.
3) Encapsular salida consolidada (`run_outputs_flow` + produce_case_outputs wrapper) manteniendo API; ganancia: desacople de generación final.
4) Aislar setup de salidas (`prepare_output_setup`) detrás de interfaz que reciba contexto y devuelva DTO; reduce acoplamiento de prompts y rutas.
5) Aislar ingestión/schema + mapeo (`run_ingestion_pipeline`) con contratos explícitos para CONFIG y wizard IO; ganancia: pruebas unitarias sin globals.
6) Recién después, abordar menú/prompt principal y mapeo manual completo; última fase por alto acoplamiento.

## 5) Antipatrones a evitar
- No mover código que muta globals sin reemplazo explícito y probado.
- No mezclar extracción con cambios de lógica o nombres públicos.
- No eliminar fallbacks (`validaciones`) sin plan de compatibilidad.
- No tocar rutas ni nombres de archivos de salida mientras se extrae.
- No introducir dependencias nuevas ni cambiar entradas/salidas de funciones en esta fase.
- Evitar “micro-refactors” en el monolito durante la documentación/plan; primero aislar, luego modificar.
