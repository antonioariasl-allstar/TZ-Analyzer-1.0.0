"""
Helpers reutilizables del flujo de bitácoras.

Incluye utilidades puras para validación rápida de schema y formato.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

import pandas as pd


def coalesce_cols(df: pd.DataFrame, *names: Optional[str]) -> Optional[str]:
    """Devuelve el primer nombre presente en el DataFrame (case-sensitive)."""
    for name in names:
        if name and name in df.columns:
            return name
    return None


def fmt_lista(values: Iterable[object]) -> str:
    """Une iterables amigables para mensajes de error."""
    return ", ".join(str(v) for v in values) if values else "(ninguna)"


def valida_formato_hora(serie: pd.Series) -> tuple[bool, list[str]]:
    """Valida que los primeros valores tengan formato HH:MM:SS."""
    pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
    sample = serie.astype(str).str.strip().str[:8].head(5)
    ok = sample.apply(lambda v: pat.match(v) is not None).all()
    return bool(ok), sample.tolist()


def valida_fecha_parsible(serie: pd.Series) -> tuple[bool, list[str]]:
    """Intenta parsear fechas; devuelve si hay alguna válida y muestras."""
    try:
        parsed = pd.to_datetime(serie, errors="coerce", dayfirst=True)
        return parsed.notna().any(), [str(v) for v in serie.head(5).tolist()]
    except Exception:
        return False, [str(v) for v in serie.head(5).tolist()]


def valida_latlon(
    df: pd.DataFrame,
    *,
    lat_col: str = "lat",
    lon_cols: tuple[str, ...] = ("long", "lon"),
    bbox: Optional[dict] = None,
) -> bool:
    """Verifica al menos una fila con lat/lon numéricas razonables dentro de bbox.

    bbox espera llaves lat_min, lat_max, lon_min, lon_max. Si no viene, usa un
    fallback básico para El Salvador.
    """
    box = bbox or {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}
    try:
        if lat_col not in df.columns:
            return False
        lon_col = coalesce_cols(df, *lon_cols)
        if not lon_col:
            return False

        lt = pd.to_numeric(df[lat_col], errors="coerce")
        lg = pd.to_numeric(df[lon_col], errors="coerce")
        mask = (
            (~lt.isna())
            & (~lg.isna())
            & (lt != 0)
            & (lg != 0)
            & lt.between(box["lat_min"], box["lat_max"])
            & lg.between(box["lon_min"], box["lon_max"])
        )
        return bool(mask.any())
    except Exception:
        return False
