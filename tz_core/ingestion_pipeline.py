"""Pipeline de ingesta y normalización previo a la generación de reportes.

Extrae la orquestación que antes vivía en el monolito para dejar el DataFrame
listo tras mapeo de schema, normalización de fecha/hora y filtros de tiempo.
"""

from __future__ import annotations

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
from tz_core.bitacora_normalization import normalize_temporal_fields
from tz_core.qc_engine import run_qc


@dataclass
class IngestionResult:
    """Resultado del pipeline de ingesta."""

    dataframe: pd.DataFrame
    time_filters: TimeFilterResult
    errores: List[str]


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

    df_norm = normalize_temporal_fields(df_norm)
    df_norm = normalize_wizard_datetime_fields(df_norm, warn_writer=lambda msg: out(msg))

    df_norm, errores = validar_datos_fn(df_norm, columnas_esenciales)

    # --- QC Engine ---
    qc_result = run_qc(df_norm)
    out("")
    for linea in qc_result.resumen:
        out(f"  {linea}")
    out(f"\nCalidad del archivo: {qc_result.score}/100")
    if qc_result.bloqueante:
        out("\n⚠️  ADVERTENCIA: se detectaron problemas críticos en los datos.")
        respuesta = input("¿Desea continuar de todas formas? (S/N): ").strip().upper()
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
