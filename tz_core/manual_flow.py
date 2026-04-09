"""Helpers específicos para el flujo manual posterior al wizard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from tz_core.dataframe_utils import coalesce_duplicates, apply_schema_renames
from tz_core.bitacora_normalization import normalize_msisdn
from tz_core.schema_utils import build_schema_synonym_map, run_schema_location_assistant
from tz_core.logging_utils import write_minimal_filter_log
from tz_core.text_utils import normalizar_columnas_texto
from tz_core.time_filters import (
    FiltroTiempo,
    solicitar_filtros_tiempo,
    aplicar_filtros_tiempo,
)


def normalize_and_validate_schema(
    *,
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]],
    original_columns: List[str],
    manual_qc_mapping: bool,
    alias_visibles: Optional[List[str]],
    wizard_io_factory: Callable[[], Any],
    persist_synonym_fn: Callable[..., None],
    validate_schema_fn: Callable[[pd.DataFrame], None],
    logger: Callable[[str], None],
    output_fn: Callable[[str], None],
    config_path: str = "config.json",
) -> pd.DataFrame:
    """Normaliza encabezados, ejecuta asistentes y asegura columnas mínimas."""

    cfg = config or {}
    schema_fields = (cfg.get("schema") or {}).get("fields") or {}

    target_alias = {
        "lon": "long",
        "duracion_seg": "duracion",
    }
    syn2target = build_schema_synonym_map(schema_fields, target_alias=target_alias)

    df, rename_map = apply_schema_renames(
        df,
        syn2target,
        manual_qc_mapping=manual_qc_mapping,
        fuzzy_cutoff=0.84,
    )

    if manual_qc_mapping or not rename_map:
        output_fn("[QC] Sin renombrar encabezados ni coalesce (QC manual activo).")

    if not manual_qc_mapping:
        df = coalesce_duplicates(
            df,
            prefer=["hora", "fecha", "lat", "long", "lon", "azimut", "tel", "imei", "antena"],
            original_columns=original_columns,
        )
        wizard_io = wizard_io_factory()
        df = run_schema_location_assistant(
            df,
            original_columns=original_columns,
            config=cfg,
            alias_visibles=alias_visibles,
            input_fn=wizard_io.prompt,
            output_fn=wizard_io.write,
            persist_synonym_fn=persist_synonym_fn,
            validate_schema_fn=validate_schema_fn,
            logger=logger,
            config_path=config_path,
        )

    reglas = None
    try:
        reglas = ((cfg.get("normalizador", {}) or {}).get("reemplazos"))
    except Exception:
        reglas = None

    df = normalizar_columnas_texto(df, reglas=reglas)

    if "fecha" not in df.columns:
        if "fecha_inicial" in df.columns:
            df["fecha"] = df["fecha_inicial"]
        elif "fecha_final" in df.columns:
            df["fecha"] = df["fecha_final"]

    if "hora" not in df.columns:
        if "hora_inicial" in df.columns:
            df["hora"] = df["hora_inicial"]
        elif "hora_final" in df.columns:
            df["hora"] = df["hora_final"]

    if "lon" not in df.columns:
        if "longitud_inicial_objetivo" in df.columns:
            df["lon"] = df["longitud_inicial_objetivo"]
        elif "long" in df.columns:
            df["lon"] = df["long"]

    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if "tel" not in df.columns:
        for candidate in ("msisdn_origen", "msisdn", "telefono", "tel"):
            if candidate in df.columns:
                df["tel"] = df[candidate]
                output_fn(f"[QC] tel <- {candidate}")
                break

    if "tel" in df.columns:
        df["tel"] = df["tel"].map(lambda v: normalize_msisdn(v) or v)

    if not manual_qc_mapping and "interaccion" not in df.columns:
        for candidate in ("tipo", "tipo2", "contacto", "usuario"):
            if candidate in df.columns:
                df["interaccion"] = df[candidate]
                output_fn(f"[QC] interaccion <- {candidate}")
                break

    if not manual_qc_mapping and "antena" not in df.columns:
        for candidate in ("siteid", "cod_celda_inicial", "celda"):
            if candidate in df.columns:
                df["antena"] = df[candidate]
                output_fn(f"[QC] antena <- {candidate}")
                break

    output_fn(
        "[QC] mapeo: "
        + str({
            "tel": "tel" in df.columns,
            "interaccion": "interaccion" in df.columns,
            "antena": "antena" in df.columns,
        })
    )
    if all(col in df.columns for col in ("tel", "interaccion", "antena")):
        output_fn(
            "[QC] no-nulos: "
            + str({
                "tel": int(df["tel"].notna().sum()),
                "interaccion": int(df["interaccion"].notna().sum()),
                "antena": int(df["antena"].notna().sum()),
            })
        )

    for column in ("lat", "lon", "azimut"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


@dataclass
class TimeFilterResult:
    """Resultado del flujo interactivo de filtros de tiempo."""

    dataframe: pd.DataFrame
    summary: Optional[str]
    filters: FiltroTiempo
    enabled: bool

    @property
    def empty(self) -> bool:
        return self.dataframe.empty


def apply_time_filter_prompt(
    *,
    option: str,
    df: pd.DataFrame,
    solicitar_fn: Callable[[], FiltroTiempo] = solicitar_filtros_tiempo,
    aplicar_fn: Callable[[pd.DataFrame, FiltroTiempo], Tuple[pd.DataFrame, str]] = aplicar_filtros_tiempo,
    output_fn: Callable[[str], None] = print,
) -> TimeFilterResult:
    """Gestiona la obtención y aplicación de filtros temporales con manejo de errores."""

    enabled = str(option) == "2"
    if not enabled:
        return TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)

    filtros: FiltroTiempo = None
    resumen: Optional[str] = None

    try:
        filtros = solicitar_fn()
        filtered_df, resumen = aplicar_fn(df, filtros)
    except Exception as exc:  # pragma: no cover - flujo interactivo
        output_fn(f"[WARN] No se pudo aplicar el filtro temporal: {exc}")
        return TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=True)

    return TimeFilterResult(
        dataframe=filtered_df,
        summary=resumen,
        filters=filtros,
        enabled=True,
    )


def handle_manual_html_generation(
    *,
    config: Optional[Dict[str, Any]],
    df: pd.DataFrame,
    archivo_kml: str,
    carpeta_salida: str,
    nombre_salida: str,
    hoja: Optional[str],
    carpeta_base: str,
    logger: Callable[[str], None],
    output_fn: Callable[[str], None],
    generar_html_fn: Callable[[pd.DataFrame, str, str, str, Optional[str]], str],
    override_tops: Optional[Dict[str, Any]] = None,
    html_seccion_interacciones: Optional[str] = None,
    html_seccion_todos_contactos: Optional[str] = None,
    relocate_kmz_fn: Callable[..., None] = None,
) -> Optional[str]:
    """Gestiona la rama legacy/manual de HTML previo a `produce_case_outputs`."""

    cfg = config or {}
    html_cfg = (cfg.get("html") or {})
    manual_mode = bool(html_cfg.get("generar_en_modo_manual", False))
    informe_html: Optional[str] = None

    if manual_mode:
        output_fn("[INFO] Generación HTML modular no disponible. Usar generar_en_modo_manual=false en config.json")
        try:
            relocate_kmz_fn(
                case_name=nombre_salida,
                source_folder=carpeta_base,
                target_folder=carpeta_salida,
                logger=logger,
            )
        except Exception as exc:  # pragma: no cover - advertencia defensiva
            output_fn(f"[WARN] No se pudo reubicar KMZ: {exc}")
        return None

    try:
        informe_html = generar_html_fn(
            df=df,
            archivo_kml=archivo_kml,
            carpeta_salida=carpeta_salida,
            nombre_salida=nombre_salida,
            hoja=hoja,
            nombre_bitacora=None,
            config=config,
            override_tops=override_tops,
            html_seccion_interacciones=html_seccion_interacciones,
            html_seccion_todos_contactos=html_seccion_todos_contactos,
            logger=logger,
        )
        output_fn(f"Informe HTML generado (modo legacy): {informe_html}")
    except Exception as exc:  # pragma: no cover - mantiene compatibilidad legacy
        output_fn(f"[ERROR] No se pudo generar el HTML (modo legacy): {exc}")
        informe_html = None

    return informe_html


def write_minimal_filter_log_if_needed(
    *,
    result: TimeFilterResult,
    df: pd.DataFrame,
    output_folder: str,
    logger: Callable[[str], None],
) -> Optional[str]:
    """Genera log_minimo.txt cuando los filtros de tiempo estuvieron activos."""

    if not result.enabled or not result.summary:
        return None

    log_path = os.path.join(output_folder, "log_minimo.txt")

    try:
        write_minimal_filter_log(
            df,
            result.summary,
            log_path,
            logger=logger,
        )
        return log_path
    except Exception as exc:  # pragma: no cover - log defensivo
        try:
            logger(f"[WARN] No se pudo generar log_minimo: {exc}")
        except Exception:
            pass
        return None
