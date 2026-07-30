"""Pipeline de ingesta y normalización previo a la generación de reportes.

Extrae la orquestación que antes vivía en el monolito para dejar el DataFrame
listo tras mapeo de schema, normalización de fecha/hora y filtros de tiempo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from tz_core.manual_flow import (
    TimeFilterResult,
    apply_time_filter_prompt,
    normalize_and_validate_schema,
)
from tz_core.mapping_wizard import (
    finalize_manual_mapping_dataframe,
    normalize_wizard_datetime_fields,
)
from tz_core.bitacora_normalization import normalize_temporal_fields, normalize_contact_fields, normalize_event_fields
from tz_core.qc_engine import run_qc
from tz_core.ui_utils import safe_input, UserCancelledError


@dataclass
class IngestionResult:
    """Resultado del pipeline de ingesta."""

    dataframe: pd.DataFrame
    time_filters: TimeFilterResult
    errores: List[str]


def resolve_date_dayfirst(
    df: pd.DataFrame,
    *,
    config: Optional[Dict[str, Any]],
    prompt_fn: Callable[[str], str] = safe_input,
    output_fn: Optional[Callable[[str], None]] = None,
) -> bool:
    """Resuelve el orden de fechas antes de normalizarlas.

    ``excel.date_order`` admite ``DMY``, ``MDY`` o ``ASK``. En modo ``ASK``
    se decide automáticamente cuando una de las dos primeras posiciones es
    mayor que 12; si todas las muestras son ambiguas, se solicita confirmación.
    """
    out = output_fn or (lambda _msg: None)
    excel_cfg = ((config or {}).get("excel") or {})
    configured = str(excel_cfg.get("date_order", "DMY")).strip().upper()

    if configured == "DMY":
        return True
    if configured == "MDY":
        return False
    if configured not in {"ASK", "AUTO"}:
        raise ValueError(
            "excel.date_order debe ser DMY, MDY, ASK o AUTO; "
            f"se recibió {configured!r}"
        )

    if "fecha" not in df.columns:
        return True

    samples = df["fecha"].dropna().astype(str).str.strip()
    parts = samples.str.extract(r"^(\d{1,2})[/-](\d{1,2})[/-]\d{4}(?:\D|$)")
    parts = parts.dropna().astype(int)
    if parts.empty:
        return True

    first_over_12 = bool((parts[0] > 12).any())
    second_over_12 = bool((parts[1] > 12).any())
    if first_over_12 and second_over_12:
        raise ValueError(
            "La columna fecha mezcla formatos DD/MM y MM/DD; "
            "corrija el archivo antes de continuar."
        )
    if first_over_12:
        return True
    if second_over_12:
        return False

    out("\n[FECHAS] Todas las fechas muestreadas son ambiguas (día y mes <= 12).")
    out("  [1] DD/MM/AAAA  — día/mes/año")
    out("  [2] MM/DD/AAAA  — mes/día/año")
    while True:
        response = prompt_fn("  → Formato del archivo (1/2, C=cancelar): ").strip().upper()
        if response == "1":
            return True
        if response == "2":
            return False
        if response == "C":
            raise UserCancelledError("Importación cancelada al confirmar el formato de fecha.")
        out("  Opción inválida. Escriba 1, 2 o C.")


def run_ingestion_pipeline(
    *,
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]],
    original_columns: List[str],
    manual_qc_mapping: bool,
    alias_visibles: Optional[List[str]],
    wizard_io_factory: Callable[[], Any],
    persist_synonym_fn: Callable[..., None],
    validate_schema_fn: Callable[[pd.DataFrame], None],
    validar_datos_fn: Callable[[pd.DataFrame, List[str]], tuple[pd.DataFrame, List[str]]],
    time_filter_option: str,
    solicitar_filtros_fn: Callable[[], Any],
    aplicar_filtros_fn: Callable[[pd.DataFrame, Any], tuple[pd.DataFrame, str]],
    logger: Optional[Callable[[str], None]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    run_manual_mapping_fn: Optional[Callable[..., Any]] = None,
) -> IngestionResult:
    """Ejecuta normalización de schema, QC manual opcional y filtros de tiempo.

    Devuelve el DataFrame listo para downstream junto con los filtros aplicados
    y cualquier lista de errores de validación devuelta por el validador.
    """

    log = logger or (lambda _msg: None)
    out = output_fn or (lambda _msg: None)
    cfg = config or {}

    columnas_esenciales = (
        (cfg.get("entradas") or {}).get("columnas_esenciales") or ["antena", "lat", "long"]
    )
    if "long" in columnas_esenciales and "lon" not in columnas_esenciales:
        columnas_esenciales = list(dict.fromkeys(list(columnas_esenciales) + ["lon"]))

    df_norm = normalize_and_validate_schema(
        df=df,
        config=cfg,
        original_columns=original_columns,
        manual_qc_mapping=manual_qc_mapping,
        alias_visibles=alias_visibles,
        wizard_io_factory=wizard_io_factory,
        persist_synonym_fn=persist_synonym_fn,
        validate_schema_fn=validate_schema_fn,
        logger=log,
        output_fn=out,
    )

    if manual_qc_mapping and run_manual_mapping_fn:
        out("\n[QC] Iniciando wizard QC (mapeo manual).")
        wizard_io = wizard_io_factory()
        df_norm, _mapeo = run_manual_mapping_fn(df_norm, wizard_io=wizard_io)
        df_norm = finalize_manual_mapping_dataframe(df_norm)

    dayfirst = resolve_date_dayfirst(
        df_norm,
        config=cfg,
        prompt_fn=safe_input,
        output_fn=out,
    )
    df_norm = normalize_temporal_fields(df_norm, dayfirst=dayfirst)
    df_norm = normalize_contact_fields(df_norm)
    df_norm = normalize_event_fields(df_norm, col_tipo="interaccion")
    df_norm = normalize_wizard_datetime_fields(
        df_norm,
        warn_writer=lambda msg: out(msg),
        dayfirst=dayfirst,
    )

    df_norm, errores = validar_datos_fn(df_norm, columnas_esenciales)

    # --- QC Engine ---
    try:
        qc_result = run_qc(df_norm)
    except Exception as e:
        logging.error(f"[QC] run_qc falló inesperadamente: {type(e).__name__}: {e}")
        qc_result = None
    if qc_result is not None:
        out("")
        for linea in qc_result.resumen:
            out(f"  {linea}")
        out(f"\nCalidad del archivo: {qc_result.score}/100")
        if qc_result.bloqueante:
            out("\n⚠️  ADVERTENCIA: se detectaron problemas críticos en los datos.")
            respuesta = safe_input("¿Desea continuar de todas formas? (S/N, C=cancelar): ").upper()
            if respuesta != "S":
                import sys
                sys.exit(0)

    time_filters: TimeFilterResult = apply_time_filter_prompt(
        option=time_filter_option,
        df=df_norm,
        solicitar_fn=solicitar_filtros_fn,
        aplicar_fn=aplicar_filtros_fn,
        output_fn=out,
    )

    return IngestionResult(
        dataframe=time_filters.dataframe,
        time_filters=time_filters,
        errores=list(errores or []),
    )
