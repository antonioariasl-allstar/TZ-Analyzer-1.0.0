"""
Normalización y validación ligera para el flujo de bitácoras.

Helpers puros (sin I/O ni globals) para texto, hora, fecha y lat/lon.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd
from decimal import Decimal


def normalize_time_strings(series: pd.Series) -> pd.Series:
    """Normaliza strings de hora a HH:MM:SS si cumplen patrón, conserva NaN en otros casos."""
    pat = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
    s = series.astype(str).str.strip()
    mask = s.apply(lambda v: bool(pat.match(v)))
    out = pd.Series(pd.NA, index=series.index, dtype="string")
    out[mask] = s[mask]
    return out


def normalize_dates(series: pd.Series, *, dayfirst: bool = True) -> pd.Series:
    """Parsea fechas tolerante; devuelve strings dd/mm/yyyy para válidos y NaN para inválidos."""
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)
    out = pd.Series(pd.NA, index=series.index, dtype="string")
    mask = parsed.notna()
    out[mask] = parsed[mask].dt.strftime("%d/%m/%Y")
    return out


def validate_time_sample(series: pd.Series) -> Tuple[bool, list[str]]:
    """Devuelve si las primeras muestras cumplen HH:MM:SS y las muestras evaluadas."""
    pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
    sample = series.astype(str).str.strip().str[:8].head(5)
    ok = sample.apply(lambda v: pat.match(v) is not None).all()
    return bool(ok), sample.tolist()


def validate_date_parsable(series: pd.Series, *, dayfirst: bool = True) -> Tuple[bool, list[str]]:
    """Intenta parsear fechas; devuelve si hay alguna válida y muestras."""
    try:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)
        return parsed.notna().any(), [str(v) for v in series.head(5).tolist()]
    except Exception:
        return False, [str(v) for v in series.head(5).tolist()]


def coalesce_cols(df: pd.DataFrame, *names: Optional[str]) -> Optional[str]:
    """Devuelve el primer nombre presente en el DataFrame (case-sensitive)."""
    for name in names:
        if name and name in df.columns:
            return name
    return None


def validate_latlon(
    df: pd.DataFrame,
    *,
    lat_col: str = "lat",
    lon_cols: Iterable[str] = ("long", "lon"),
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


def sanitize_latlon(
    df: pd.DataFrame,
    lat_col: str = "lat",
    lon_col: str = "long",
    *,
    zero_is_invalid: bool = True,
    bbox: Optional[dict] = None,
) -> pd.DataFrame:
    """Devuelve copia con lat/lon numéricas, NaN para valores fuera de rango o cero/0,0."""
    box = bbox or {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}
    out = df.copy()
    out[lat_col] = pd.to_numeric(out.get(lat_col, pd.Series(dtype=float)), errors="coerce")
    out[lon_col] = pd.to_numeric(out.get(lon_col, pd.Series(dtype=float)), errors="coerce")
    mask_zero = (out[lat_col].fillna(0) == 0) & (out[lon_col].fillna(0) == 0) if zero_is_invalid else pd.Series(False, index=out.index)
    mask_out = ~out[lat_col].between(box["lat_min"], box["lat_max"]) | ~out[lon_col].between(box["lon_min"], box["lon_max"])
    invalid = mask_zero | mask_out
    out.loc[invalid, [lat_col, lon_col]] = np.nan
    return out


__all__ = [
    "normalize_time_strings",
    "normalize_dates",
    "validate_time_sample",
    "validate_date_parsable",
    "coalesce_cols",
    "validate_latlon",
    "sanitize_latlon",
    "parse_duration_seconds",
    "normalize_imei",
    "normalize_msisdn",
    "normalize_temporal_fields",
    "normalize_contact_fields",
    "normalize_event_fields",
]


def parse_duration_seconds(value: object, *, default: float = 0.0) -> float:
    """Parsea una duración expresada en segundos o HH:MM[:SS] a segundos (float).

    - Strings vacíos/None retornan ``default``.
    - Si recibe ya un número, intenta convertirlo a float.
    - Tolerante a formatos "HH:MM" o "HH:MM:SS".
    """
    if value is None:
        return float(default)
    try:
        if isinstance(value, (int, float, np.number)) and not pd.isna(value):
            return float(value)
    except Exception:
        pass

    s = str(value).strip()
    if not s or s.lower() in {"nan", "none"}:
        return float(default)

    if s.isdigit():
        try:
            return float(s)
        except Exception:
            return float(default)

    parts = s.split(":")
    try:
        parts_int = [int(p) for p in parts]
        if len(parts_int) == 3:
            return float(parts_int[0] * 3600 + parts_int[1] * 60 + parts_int[2])
        if len(parts_int) == 2:
            return float(parts_int[0] * 60 + parts_int[1])
    except Exception:
        return float(default)

    return float(default)


def _normalize_decimal_string(value: object) -> Optional[str]:
    """Normaliza números pasados como float/Decimal/string evitando notación científica.

    Devuelve un string con dígitos solamente (sin signo) si se puede normalizar, de lo contrario None.
    """
    if value is None:
        return None
    try:
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        if isinstance(value, (float, np.floating, Decimal)):
            d = Decimal(str(value))
            return format(d, "f").rstrip("0").rstrip(".") or None
    except Exception:
        pass
    s = str(value).strip()
    if not s:
        return None
    try:
        d = Decimal(s)
        return format(d, "f").rstrip("0").rstrip(".") or None
    except Exception:
        return None


def normalize_imei(value: object) -> Optional[str]:
    """Devuelve IMEI como string de dígitos, sin sufijos ".0" ni notación científica.

    Retorna None si no puede sanearse a una cadena numérica.
    """
    cleaned = _normalize_decimal_string(value)
    if cleaned is None:
        return None
    cleaned = cleaned.replace(" ", "")
    if cleaned.isdigit():
        return cleaned
    return None


def normalize_msisdn(value: object, *, allow_plus: bool = True) -> Optional[str]:
    """Normaliza números telefónicos/MSISDN a string estable.

    - Elimina espacios, guiones, paréntesis y puntos.
    - Si viene como float, evita notación científica.
    - Permite prefijo "+" si ``allow_plus`` es True.
    Retorna None si no queda ningún dígito.
    """
    if value is None:
        return None

    # Si es numérico, primero normalizar evitando notación científica
    cleaned_num = _normalize_decimal_string(value)
    if cleaned_num is not None:
        base = cleaned_num
    else:
        base = str(value)

    s = base.strip()
    if not s:
        return None

    prefix_plus = s.startswith("+") and allow_plus
    # Eliminar separadores comunes
    s = s.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    if not s.isdigit():
        return None
    return ("+" + s) if prefix_plus else s


def normalize_temporal_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta y normaliza campos temporales en el DataFrame post-wizard.

    Casos manejados:
    A) 'fecha' contiene datetime combinado (YYYY-MM-DD HH:MM:SS o similar):
       - Parsea como datetime completo
       - Sobreescribe 'fecha' con componente date (dd/mm/yyyy)
       - Crea 'hora' con componente time (HH:MM:SS) si no existe o está vacía
       - Crea 'datetime_evento' como datetime64[ns]
    B) 'fecha' y 'hora' existen como columnas separadas:
       - Construye 'datetime_evento' combinando ambas
       - No altera 'fecha' ni 'hora'
    C) Solo existe 'fecha' (sin hora):
       - 'datetime_evento' = fecha a las 00:00:00
    D) Solo existe 'hora' o ninguna columna temporal:
       - 'datetime_evento' = NaT, no rompe flujo

    No modifica columnas no temporales. Tolerante a errores (coerce).
    'datetime_evento' es siempre datetime64[ns], nunca string.
    """
    df = df.copy()

    _DATETIME_PATTERN = re.compile(
        r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}"
    )

    def _is_combined_datetime(series: pd.Series) -> bool:
        """Devuelve True si la mayoría de valores no-nulos parecen datetime combinado."""
        sample = series.dropna().astype(str).str.strip().head(10)
        if sample.empty:
            return False
        matches = sample.apply(lambda v: bool(_DATETIME_PATTERN.match(v)))
        return matches.sum() >= max(1, len(sample) // 2)

    fecha_col = "fecha" if "fecha" in df.columns else None
    hora_col = "hora" if "hora" in df.columns else None

    datetime_evento = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

    # --- CASO A: fecha contiene datetime combinado ---
    if fecha_col and _is_combined_datetime(df[fecha_col]):
        parsed = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=False)
        datetime_evento = parsed
        df["fecha"] = parsed.dt.strftime("%d/%m/%Y").where(parsed.notna(), "SinInf")
        hora_vacia = (
            hora_col is None
            or df[hora_col].isna().all()
            or df[hora_col].astype(str).str.strip().isin(["", "Sin Inf.", "SinInf"]).all()
        )
        if hora_vacia:
            df["hora"] = parsed.dt.strftime("%H:%M:%S").where(parsed.notna(), "Sin Inf.")

    # --- CASO B: fecha y hora como columnas separadas ---
    elif fecha_col and hora_col:
        _sample = df[fecha_col].dropna().astype(str).str.strip().head(5)
        _dayfirst = not _sample.str.match(r"^\d{4}-\d{2}-\d{2}$").any()
        fecha_parsed = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=_dayfirst)
        hora_str = df[hora_col].astype(str).str.strip()
        combined_str = fecha_parsed.dt.strftime("%Y-%m-%d").fillna("1970-01-01") + " " + hora_str
        combined = pd.to_datetime(combined_str, errors="coerce", dayfirst=False)
        mask_valid = fecha_parsed.notna() & combined.notna()
        datetime_evento[mask_valid] = combined[mask_valid]

    # --- CASO C: solo fecha ---
    elif fecha_col:
        fecha_parsed = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=True)
        datetime_evento = fecha_parsed.dt.normalize()

    # --- CASO D: solo hora o ninguna ---
    # datetime_evento queda NaT — no rompe flujo

    df["datetime_evento"] = datetime_evento
    return df


def normalize_contact_fields(df: pd.DataFrame) -> pd.DataFrame:
    """QC-4: Normalización estructural conservadora de campos telefónicos.

    Crea columnas derivadas sin modificar los originales:
      - tel_limpio: tel normalizado estructuralmente
      - contacto_limpio: contacto normalizado estructuralmente
      - contacto_valido: bool — True si contacto_limpio es un número usable

    Reglas de validación (global, no dependiente de país):
      - Solo dígitos con posible '+' inicial
      - Longitud entre 7 y 15 caracteres
      - No puede ser secuencia de solo ceros
    """
    def _is_valid(value) -> bool:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return False
        s = str(value)
        digits = s.lstrip("+")
        if not digits.isdigit():
            return False
        if len(digits) == 0:
            return False
        if len(digits) < 7 or len(digits) > 15:
            return False
        if all(c == "0" for c in digits):
            return False
        return True

    try:
        if "tel" in df.columns:
            df["tel_limpio"] = df["tel"].apply(
                lambda v: normalize_msisdn(v) if not (isinstance(v, float) and pd.isna(v)) else None
            )
        else:
            df["tel_limpio"] = None

        if "contacto" in df.columns:
            df["contacto_limpio"] = df["contacto"].apply(
                lambda v: normalize_msisdn(v) if not (isinstance(v, float) and pd.isna(v)) else None
            )
            df["contacto_valido"] = df["contacto_limpio"].apply(_is_valid)
        else:
            df["contacto_limpio"] = None
            df["contacto_valido"] = False

    except Exception as e:
        import warnings
        warnings.warn(f"normalize_contact_fields: error inesperado — {e}")
        if "tel_limpio" not in df.columns:
            df["tel_limpio"] = None
        if "contacto_limpio" not in df.columns:
            df["contacto_limpio"] = None
        if "contacto_valido" not in df.columns:
            df["contacto_valido"] = False

    return df


def normalize_event_fields(
    df: pd.DataFrame,
    col_tipo: Optional[str] = None,
) -> pd.DataFrame:
    """QC-5: Clasifica eventos y genera flag analítico.

    Crea dos columnas derivadas sin modificar las originales:
      - tipo_evento_normalizado: VOZ, SMS, DATOS o DESCONOCIDO
      - evento_valido_analisis: True para VOZ y SMS, False para el resto

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame post-wizard.
    col_tipo : str | None
        Nombre de la columna que contiene el tipo de evento (ej. "interaccion").
        Si es None o no existe en df, todo queda DESCONOCIDO.
    """
    def _classify(value) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "DESCONOCIDO"
        text = str(value).strip().upper()
        if not text:
            return "DESCONOCIDO"
        if "DATOS" in text:
            return "DATOS"
        if "SMS" in text:
            return "SMS"
        if "VOZ" in text or "CALL" in text or "LLAMADA" in text:
            return "VOZ"
        return "DESCONOCIDO"

    if col_tipo is None or col_tipo not in df.columns:
        df["tipo_evento_normalizado"] = "DESCONOCIDO"
    else:
        df["tipo_evento_normalizado"] = df[col_tipo].map(_classify)

    df["evento_valido_analisis"] = df["tipo_evento_normalizado"].isin({"VOZ", "SMS"})
    return df