"""Health and dataset sanity helpers shared across pipelines."""

from typing import Callable, Optional

import pandas as pd


def log_dataset_stats(stage: str, df: pd.DataFrame, logger: Optional[Callable[[str], None]] = None) -> None:
    """Log basic dataset counters for a given stage."""

    logger = logger or (lambda msg: None)
    try:
        total = len(df)
        cols = len(df.columns)
        lat_ok = 0
        if "lat" in df.columns and ("long" in df.columns or "lon" in df.columns):
            lat_series = pd.to_numeric(df.get("lat"), errors="coerce")
            lon_series = pd.to_numeric(df.get("long", df.get("lon")), errors="coerce")
            lat_ok = int((lat_series.notna() & lon_series.notna()).sum())

        hora_missing = None
        if "hora" in df.columns:
            hora_missing = int(df["hora"].isna().sum())

        parts = [f"[{stage}] filas={total}", f"cols={cols}"]
        if lat_ok:
            parts.append(f"coord_validas={lat_ok}")
        if hora_missing is not None:
            parts.append(f"horas_sin_inf={hora_missing}")

        logger(" ".join(parts))
    except Exception:
        pass


def run_health_checks(
    df: pd.DataFrame,
    *,
    min_coord_ratio: float = 0.05,
    max_hora_missing_ratio: float = 0.25,
    logger: Optional[Callable[[str], None]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> bool:
    """Validate minimal signal before generating outputs; return True to proceed."""

    logger = logger or (lambda msg: None)
    output_fn = output_fn or (lambda msg: None)
    input_fn = input_fn or input

    try:
        total = len(df)
        if total == 0:
            msg = "[health] No hay registros para procesar después de filtros."
            try:
                logger(msg)
            except Exception:
                pass
            output_fn(msg)
            return False

        lat_ok = 0
        if "lat" in df.columns and ("long" in df.columns or "lon" in df.columns):
            lat_series = pd.to_numeric(df.get("lat"), errors="coerce")
            lon_series = pd.to_numeric(df.get("long", df.get("lon")), errors="coerce")
            lat_ok = int((lat_series.notna() & lon_series.notna()).sum())

        hora_missing = None
        if "hora" in df.columns:
            hora_missing = int(df["hora"].isna().sum())

        warnings_found = []

        if lat_ok == 0:
            warnings_found.append("[health] No hay coordenadas válidas (lat/long).")
        else:
            coord_ratio = lat_ok / total
            if coord_ratio < min_coord_ratio:
                warnings_found.append(
                    f"[health] Solo {lat_ok} de {total} filas tienen coordenadas ({coord_ratio:.1%})."
                )

        if hora_missing is not None and hora_missing > 0:
            hora_ratio = hora_missing / total
            if hora_ratio > max_hora_missing_ratio:
                warnings_found.append(
                    f"[health] {hora_missing} filas sin hora ({hora_ratio:.1%}); revisá la normalización."
                )

        if not warnings_found:
            try:
                logger("[health] OK: señales mínimas suficientes para continuar.")
            except Exception:
                pass
            return True

        for w in warnings_found:
            try:
                logger(w)
            except Exception:
                pass
            output_fn(w)

        try:
            resp = (input_fn("Continuar a salidas a pesar de las alertas? [s/N]: ") or "").strip().lower()
        except Exception:
            resp = ""

        if resp in {"s", "si", "y", "yes"}:
            try:
                logger("[health] Continuando bajo responsabilidad del usuario.")
            except Exception:
                pass
            return True

        try:
            logger("[health] Ejecución abortada por alertas de calidad.")
        except Exception:
            pass
        output_fn("Ejecución detenida por salud insuficiente. Ajustá los datos y reintenta.")
        return False
    except Exception:
        # If any unexpected error occurs, allow continuation to avoid blocking the flow.
        return True
