# Manual Flow Split Plan (Epic 16E)

## Contexto

El flujo interactivo posterior al mapeo dentro de `script_principal_bitacoras_refactory.py` sigue concentrado en un bloque monolítico de ~400 líneas (ver [script_principal_bitacoras_refactory.py#L3601-L4275](script_principal_bitacoras_refactory.py#L3601-L4275)). Ahí conviven prompts de configuración, heurísticas de nombres, preparación de carpetas y propagación de overrides, lo que dificulta:

- Reutilizar lógica desde GUI/CLI (necesita `input()` y estado global).
- Escribir pruebas unitarias sin monkeypatch masivo.
- Extraer piezas a `tz_core` o reutilizarlas en `run_tz_analysis()`.

## Objetivo

Diseñar helpers modulares (puros o con IO inyectable) que dividan la orquestación manual en responsabilidades pequeñas con firmas claras:

1. Recolección de metadatos interactivos (modo, filtros, top-N, alias/abonado).
2. Generación de nombres base y determinación de carpetas destino.
3. Consolidación de parámetros de salida (paths de HTML/KML/KMZ, flags `solo_kmz`, overrides).

## Propuesta de Helpers

| Helper | Rol | Inputs | Outputs | Referencias | Comentarios |
| --- | --- | --- | --- | --- | --- |
| `collect_manual_mode_context()` | Ejecuta menú principal (modos 1/2/3) y color picker. | `config`, `io` (prompt/write) | `ManualModeContext` (`opcion`, `config_actualizada`) | [script_principal_bitacoras_refactory.py#L3608-L3665](script_principal_bitacoras_refactory.py#L3608-L3665) | Permite inyectar IO y mockear respuestas en tests. |
| `gather_dataset_metadata()` | Selecciona archivo, hoja visible y carga DataFrame. | `io`, file pickers | `(df, archivo_entrada, hoja)` | [script_principal_bitacoras_refactory.py#L3672-L3745](script_principal_bitacoras_refactory.py#L3672-L3745) | Centraliza logging + manejo de errores de carga. |
| `normalize_and_validate_schema()` | Mantiene renombrados, `_run_schema_location_assistant()`, validaciones de columnas mínimas. | `df`, `config`, `cols_originales`, `io` | `df_normalizado` | [script_principal_bitacoras_refactory.py#L3746-L3950](script_principal_bitacoras_refactory.py#L3746-L3950) | Ya parcialmente modularizado; bastaría empaquetar la secuencia previa/post `_apply_qc_placeholders`. |
| `prompt_case_identity()` | Determina tipo de bitácora IMEI/TEL, alias corto y `primary`. | `df`, `io`, `clock` | `CaseIdentity` (`modo`, `principal_id`, `alias_short`) | [script_principal_bitacoras_refactory.py#L4035-L4135](script_principal_bitacoras_refactory.py#L4035-L4135) | Aísla la lógica condicional de `_limpiar_alias()` y `_pick_id()`. |
| `collect_top_overrides()` | Pregunta Top Antenas/Contactos y actualiza `CONFIG` / `OVERRIDE_TOPS`. | `io`, `config` | `TopOverrides` dict | [script_principal_bitacoras_refactory.py#L4186-L4218](script_principal_bitacoras_refactory.py#L4186-L4218) | Devuelve ints validados; el caller decide si persistir. |
| `suggest_case_name()` | Construye `base_auto` a partir de identidad, rango, filtros. | `CaseIdentity`, `df`, `filtros`, `timestamp_fn` | `nombre_sugerido`, `sufijo`, `metadata` | [script_principal_bitacoras_refactory.py#L3966-L4184](script_principal_bitacoras_refactory.py#L3966-L4184) | Reutilizable para wizard/GUI y fácil de testear con fixtures. |
| `prompt_output_routing()` | Pregunta nombre final y carpeta destino; decide estructura `kml/`. | `nombre_sugerido`, `io`, `selector_carpeta`, `config` | `OutputRouting` (paths completos) | [script_principal_bitacoras_refactory.py#L4219-L4309](script_principal_bitacoras_refactory.py#L4219-L4309) | Encapsula `sanear_nombre_archivo` y manejo de `separar_kml_kmz`. |
| `summarize_outputs()` | Lista archivos a generar, imprime resumen y actualiza logs. | `OutputRouting`, flags `solo_kmz` | None | [script_principal_bitacoras_refactory.py#L4172-L4285](script_principal_bitacoras_refactory.py#L4172-L4285) | Sólo side-effects → fácil stub en tests. |

## Contratos de Datos

Definir dataclasses (`ManualModeContext`, `CaseIdentity`, `TopOverrides`, `OutputRouting`) en `tz_core/manual_mode.py` o `tz_core/ui_utils.py` para mantener serializable el estado entre helpers y permitir pruebas independientes.

Ejemplo:

```python
@dataclass
class CaseIdentity:
    modo: str
    principal_id: str
    alias_short: str
    alias_full: str
```

## Camino de Extracción

1. **Fase 1 – aislamiento interno**
   - Crear helpers dentro del monolito pero fuera de `main()`, usando `WizardIO` o un nuevo `PromptIO` para reusar mocks (`tests/helpers/monkeypatch_flow`).
   - Añadir pruebas unitarias enfocadas en la lógica pura (nombres, casos, overrides) sin tocar `input()` directo.

2. **Fase 2 – mover a `tz_core`**
   - Una vez estabilizadas las firmas, mover helpers puros (`suggest_case_name`, `collect_top_overrides`) a `tz_core/ui_utils.py` o `tz_core/manual_mode.py`.
   - Mantener wrappers en el monolito que solo conecten IO y CONFIG.

3. **Fase 3 – integración GUI/CLI**
   - `run_tz_analysis()` y futuros frontends pueden pasar un IO programático para automatizar respuestas.
   - Documentar los nuevos contratos en `docs/FASE_2G_VALIDATION_EXPANSION.md`.

## Riesgos y Mitigación

- **Uso extensivo de globals (`CONFIG`, `nombre_salida`, `OVERRIDE_TOPS`)** → pasar referencias explícitas a los helpers y devolver copias. 
- **Dependencia de tiempo real (`datetime.now()`)** → inyectar `clock_fn` para pruebas deterministas.
- **Prompt chaining** → usar un objeto `ManualFlowIO` (similar a `WizardIO`) que derive en un solo lugar las llamadas a `input/print/log`.

Con este plan, podemos marcar “Plan manual flow split” como completado y proceder a implementar cada helper gradualmente sin romper el flujo heredado.
