"""
Normalización y validación ligera para el flujo de bitácoras.

Helpers puros (sin I/O ni globals) para texto, hora, fecha y lat/lon.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
from decimal import Decimal

from tz_core.event_classification import classify_event_type


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
    parsed = parse_date_series(series, dayfirst=dayfirst)
    out = pd.Series(pd.NA, index=series.index, dtype="string")
    mask = parsed.notna()
    out[mask] = parsed[mask].dt.strftime("%d/%m/%Y")
    return out


def parse_date_series(series: pd.Series, *, dayfirst: bool = True) -> pd.Series:
    """Parse dates without reinterpreting ISO text as DD/MM or MM/DD."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    text = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    iso_mask = text.str.match(r"^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$", na=False)

    if iso_mask.any():
        parsed.loc[iso_mask] = pd.to_datetime(
            text.loc[iso_mask].str.slice(0, 10),
            format="%Y-%m-%d",
            errors="coerce",
        )

    other_mask = ~iso_mask & text.notna()
    if other_mask.any():
        parsed.loc[other_mask] = pd.to_datetime(
            text.loc[other_mask],
            errors="coerce",
            dayfirst=dayfirst,
        )

    return parsed


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


_VALORES_NO_SIGNIFICATIVOS = {
    "0", "-", "--", "nan", "none", "null", "n/a", "na",
    "sin inf", "sin inf.", "sin determinar", "s/i",
}


def es_valor_significativo(valor: Any) -> bool:
    """Indica si `valor` es un dato analíticamente utilizable (contacto, tipo, etc.).

    Criterio único, consolidado, reutilizado por interacciones_builder, contacts
    y analytics: placeholders como "SIN DETERMINAR", "N/A", "-" o vacío no
    cuentan, no agrupan y no pueden aparecer como sujeto de una alerta o KPI.
    """
    if valor is None:
        return False
    if isinstance(valor, float) and pd.isna(valor):
        return False
    try:
        if pd.isna(valor):
            return False
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if not texto:
        return False
    return texto.lower() not in _VALORES_NO_SIGNIFICATIVOS


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
    "parse_date_series",
    "validate_time_sample",
    "validate_date_parsable",
    "coalesce_cols",
    "es_valor_significativo",
    "validate_latlon",
    "sanitize_latlon",
    "parse_duration_seconds",
    "normalize_imei",
    "normalize_msisdn",
    "normalize_temporal_fields",
    "normalize_contact_fields",
    "normalize_event_fields",
    "DuracionEstado",
    "clasificar_confiabilidad_duracion",
    "requiere_pregunta_qc_duracion",
    "preguntar_unidad_duracion_qc",
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
            formatted = format(d, "f")
            if "." in formatted:
                formatted = formatted.rstrip("0").rstrip(".")
            return formatted or None
    except Exception:
        pass
    s = str(value).strip()
    if not s:
        return None
    try:
        d = Decimal(s)
        formatted = format(d, "f")
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted or None
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


def normalize_temporal_fields(
    df: pd.DataFrame,
    *,
    dayfirst: bool = True,
) -> pd.DataFrame:
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
        fecha_parsed = parse_date_series(df[fecha_col], dayfirst=dayfirst)
        if not pd.api.types.is_datetime64_any_dtype(fecha_parsed):
            fecha_parsed = fecha_parsed.astype("datetime64[ns]")
        hora_str = df[hora_col].astype(str).str.strip()
        combined_str = fecha_parsed.dt.strftime("%Y-%m-%d").fillna("1970-01-01") + " " + hora_str
        combined = pd.to_datetime(combined_str, errors="coerce", dayfirst=False)
        mask_valid = fecha_parsed.notna() & combined.notna()
        datetime_evento[mask_valid] = combined[mask_valid]

    # --- CASO C: solo fecha ---
    elif fecha_col:
        fecha_parsed = pd.to_datetime(
            df[fecha_col],
            errors="coerce",
            dayfirst=dayfirst,
        )
        if not pd.api.types.is_datetime64_any_dtype(fecha_parsed):
            fecha_parsed = fecha_parsed.astype("datetime64[ns]")
        datetime_evento = fecha_parsed.dt.normalize()

    # --- CASO D: solo hora o ninguna ---
    # datetime_evento queda NaT — no rompe flujo

    df["datetime_evento"] = datetime_evento
    return df


def _tiene_evidencia_formato_internacional(raw_str: str) -> bool:
    """Indica si ``raw_str`` trae evidencia explícita de formato internacional.

    Evidencia reconocida: prefijo "+" o prefijo de discado internacional "00".
    No implementa una base de códigos de país — solo detecta la marca de
    formato que el propio valor trae consigo (ver contrato §5, Tarea 2).
    """
    s = raw_str.strip()
    return s.startswith("+") or s.startswith("00")


def _classify_contact_category(raw, limpio, tipo_norm: str, tel_limpio: Optional[str] = None) -> tuple:
    """Clasifica el contacto en (categoria, motivo) usando cascada raw+limpio+tipo.

    Categorías: telefonico_plausible | indeterminado | tecnico_no_personal

    ``tel_limpio`` (opcional): número investigado ya normalizado. Si
    ``limpio`` coincide con él (autocontacto — el número marcándose a sí
    mismo), se clasifica como técnico con motivo dedicado ``autocontacto``,
    fuera de ranking (ver contrato §6-C).
    """
    _EMPTY = ("tecnico_no_personal", "vacio_o_nulo")

    # 1. Vacío / nulo
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return _EMPTY
    raw_str = str(raw).strip()
    if not raw_str:
        return _EMPTY

    # 2. DATOS → siempre técnico independientemente del formato
    if tipo_norm == "DATOS":
        return ("tecnico_no_personal", "tipo_datos")

    # 3. IPv4 en valor original
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", raw_str):
        return ("tecnico_no_personal", "ipv4")

    # 4. Detectar notación científica válida antes de verificar alfanumérico
    _raw_nospace = raw_str.replace(" ", "")
    is_scientific = bool(re.match(r"^[+\-]?\d+\.?\d*[eE][+\-]?\d+$", _raw_nospace))

    # 5. Alfanumérico o formato incompatible (excluyendo notación científica)
    raw_phone_stripped = re.sub(r"[\s\+\-\(\)]", "", raw_str)
    # 5b. Decimal terminado en .0/.00... (representación Excel de un entero):
    # sanear ANTES del gate alfanumérico para no perder un identificador
    # numérico válido por el sufijo. Solo aplica a un único punto con
    # fracción exactamente cero — no reinterpreta IPv4 (ya resuelto en el
    # paso 3, que exige 4 octetos) ni decimales con fracción no nula
    # (ej. "70021111.5", que debe seguir cayendo en formato_alfanumerico).
    if re.match(r"^\d+\.0+$", raw_phone_stripped):
        raw_phone_stripped = raw_phone_stripped.split(".", 1)[0]
    if not is_scientific and not raw_phone_stripped.isdigit():
        return ("tecnico_no_personal", "formato_alfanumerico")

    # 6. Solo ceros
    if raw_phone_stripped and all(c == "0" for c in raw_phone_stripped):
        return ("tecnico_no_personal", "solo_ceros")

    # 7. Usar contacto_limpio como base analítica
    if limpio is None or (isinstance(limpio, float) and pd.isna(limpio)):
        return ("tecnico_no_personal", "sin_contacto_limpio")
    limpio_str = str(limpio).strip()
    if not limpio_str:
        return ("tecnico_no_personal", "sin_contacto_limpio")
    limpio_digits = limpio_str.lstrip("+")
    if not limpio_digits.isdigit():
        return ("tecnico_no_personal", "limpio_no_numerico")

    # 7b. Autocontacto: el contacto coincide con el número investigado.
    if tel_limpio is not None and not (isinstance(tel_limpio, float) and pd.isna(tel_limpio)):
        tel_limpio_digits = str(tel_limpio).strip().lstrip("+")
        if tel_limpio_digits and limpio_digits == tel_limpio_digits:
            return ("tecnico_no_personal", "autocontacto")

    # 8. Longitud 0–1 → técnico (no indeterminado)
    n = len(limpio_digits)
    if n <= 1:
        return ("tecnico_no_personal", "longitud_insuficiente")

    # 9. Matriz por tipo normalizado y longitud
    if tipo_norm == "VOZ":
        if n > 15:
            return ("indeterminado", "longitud_excesiva")
        if n == 15 and not _tiene_evidencia_formato_internacional(raw_str):
            return ("indeterminado", "identificador_15_digitos_no_confirmado")
        return (
            ("telefonico_plausible", "voz_longitud_valida") if n >= 8
            else ("indeterminado", "voz_longitud_corta")
        )
    if tipo_norm == "SMS":
        if n > 15:
            return ("indeterminado", "longitud_excesiva")
        if n == 15 and not _tiene_evidencia_formato_internacional(raw_str):
            return ("indeterminado", "identificador_15_digitos_no_confirmado")
        return (
            ("telefonico_plausible", "sms_longitud_valida") if n >= 8
            else ("indeterminado", "sms_longitud_ambigua")
        )
    if tipo_norm == "DESCONOCIDO":
        return (
            ("indeterminado", "desconocido_longitud_plausible") if n >= 5
            else ("indeterminado", "desconocido_longitud_corta")
        )

    return ("tecnico_no_personal", "sin_clasificacion")


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
            _tipo_col = df["tipo_evento_normalizado"] if "tipo_evento_normalizado" in df.columns else pd.Series(["DESCONOCIDO"] * len(df), index=df.index)
            _tel_limpio_col = df["tel_limpio"] if "tel_limpio" in df.columns else pd.Series([None] * len(df), index=df.index)
            _clasificaciones = [
                _classify_contact_category(r, l, t, tl)
                for r, l, t, tl in zip(df["contacto"], df["contacto_limpio"], _tipo_col, _tel_limpio_col)
            ]
            df["contacto_categoria"] = [c[0] for c in _clasificaciones]
            df["contacto_motivo"]    = [c[1] for c in _clasificaciones]
        else:
            df["contacto_limpio"] = None
            df["contacto_valido"] = False
            df["contacto_categoria"] = "tecnico_no_personal"
            df["contacto_motivo"]    = "sin_columna_contacto"

    except Exception as e:
        import warnings
        warnings.warn(f"normalize_contact_fields: error inesperado — {e}")
        if "tel_limpio" not in df.columns:
            df["tel_limpio"] = None
        if "contacto_limpio" not in df.columns:
            df["contacto_limpio"] = None
        if "contacto_valido" not in df.columns:
            df["contacto_valido"] = False
        if "contacto_categoria" not in df.columns:
            df["contacto_categoria"] = "tecnico_no_personal"
        if "contacto_motivo" not in df.columns:
            df["contacto_motivo"] = "sin_clasificacion_error"

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
        return classify_event_type(value)

    if col_tipo is None or col_tipo not in df.columns:
        df["tipo_evento_normalizado"] = "DESCONOCIDO"
    else:
        df["tipo_evento_normalizado"] = df[col_tipo].map(_classify)

    df["evento_valido_analisis"] = df["tipo_evento_normalizado"].isin({"VOZ", "SMS"})
    return df


# ─────────────────────────────────────────────────────────────────────────
# FX-02 — Infraestructura de confiabilidad de duración
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DuracionEstado:
    """Resultado de clasificar la confiabilidad de una columna de duración.

    Estados posibles: "segura", "ambigua", "ausente".
    Unidades canónicas: "milisegundos", "segundos", "minutos", "hhmmss",
    "desconocida" o None.
    """

    estado: str
    unidad: Optional[str]
    columna: Optional[str]
    columna_original: Optional[str]
    motivo: str

    @property
    def confiable(self) -> bool:
        return self.estado == "segura"


_DURATION_GENERIC_NAMES = ("duracion", "duración", "duration", "dur")

_DURATION_EXPLICIT_SECONDS_NAMES = (
    "duracion_seg",
    "duración_seg",
    "segundos",
    "duration_seconds",
    "duracion_segundos",
    "duración_segundos",
    "duration_sec",
    "dur_seg",
)

_DURATION_CANDIDATE_NAMES = _DURATION_EXPLICIT_SECONDS_NAMES + _DURATION_GENERIC_NAMES

_DURATION_EXPLICIT_SECONDS_SET = set(_DURATION_EXPLICIT_SECONDS_NAMES)

_HHMMSS_PATTERN = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

_DURATION_EMPTY_TOKENS = {"", "nan", "none", "nat", "sin inf", "sin inf."}


def _normalize_duration_header_key(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _find_duration_column(
    df: pd.DataFrame,
    columnas_config: Dict[str, Any],
) -> Optional[str]:
    """Localiza la columna de duración en `df` sin modificarlo."""
    configured = columnas_config.get("duracion")
    if configured and configured in df.columns:
        return configured

    normalized_map = {_normalize_duration_header_key(c): c for c in df.columns}
    for candidate in _DURATION_CANDIDATE_NAMES:
        if candidate in normalized_map:
            return normalized_map[candidate]
    return None


def clasificar_confiabilidad_duracion(
    df: pd.DataFrame,
    *,
    columnas_config: Optional[Dict[str, Any]] = None,
    encabezado_original: Optional[str] = None,
    unidad_declarada: Optional[str] = None,
) -> DuracionEstado:
    """Clasifica la confiabilidad de la unidad de duración de `df`.

    Función pura: no modifica `df`, no convierte valores y no llama input().
    No infiere unidad por magnitud — solo reconoce formatos autodescriptivos
    (HH:MM:SS / MM:SS), encabezados que declaran explícitamente segundos, o
    una unidad ya resuelta por selección del usuario (`unidad_declarada`).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame a inspeccionar (solo lectura).
    columnas_config : dict | None
        Config opcional con `{"duracion": "<nombre_columna>"}` para forzar
        la columna a inspeccionar.
    encabezado_original : str | None
        Nombre de encabezado original (previo a renombrar a canónico) si el
        wizard/normalización lo preservó para esta ejecución.
    unidad_declarada : str | None
        Resultado ya resuelto de una selección del usuario:
        "milisegundos", "segundos", "minutos", "desconocida" o None.
    """
    columnas_config = columnas_config or {}

    columna = _find_duration_column(df, columnas_config)
    if columna is None:
        return DuracionEstado(
            estado="ausente",
            unidad=None,
            columna=None,
            columna_original=encabezado_original,
            motivo="sin_columna",
        )

    header_ref = encabezado_original or columna

    serie = df[columna]
    texto = serie.astype(str).str.strip()
    vacio_mask = serie.isna() | texto.str.lower().isin(_DURATION_EMPTY_TOKENS)
    no_vacios = texto[~vacio_mask]

    if no_vacios.empty:
        return DuracionEstado(
            estado="ausente",
            unidad=None,
            columna=columna,
            columna_original=header_ref,
            motivo="sin_valores",
        )

    if no_vacios.apply(lambda v: bool(_HHMMSS_PATTERN.match(v))).all():
        return DuracionEstado(
            estado="segura",
            unidad="hhmmss",
            columna=columna,
            columna_original=header_ref,
            motivo="formato_autodescriptivo",
        )

    if _normalize_duration_header_key(header_ref) in _DURATION_EXPLICIT_SECONDS_SET:
        return DuracionEstado(
            estado="segura",
            unidad="segundos",
            columna=columna,
            columna_original=header_ref,
            motivo="encabezado_declara_segundos",
        )

    if unidad_declarada == "milisegundos":
        return DuracionEstado(
            estado="segura",
            unidad="milisegundos",
            columna=columna,
            columna_original=header_ref,
            motivo="seleccion_usuario_milisegundos",
        )
    if unidad_declarada == "segundos":
        return DuracionEstado(
            estado="segura",
            unidad="segundos",
            columna=columna,
            columna_original=header_ref,
            motivo="seleccion_usuario_segundos",
        )
    if unidad_declarada == "minutos":
        return DuracionEstado(
            estado="segura",
            unidad="minutos",
            columna=columna,
            columna_original=header_ref,
            motivo="seleccion_usuario_minutos",
        )
    if unidad_declarada == "desconocida":
        return DuracionEstado(
            estado="ambigua",
            unidad="desconocida",
            columna=columna,
            columna_original=header_ref,
            motivo="seleccion_usuario_desconocida",
        )

    return DuracionEstado(
        estado="ambigua",
        unidad="desconocida",
        columna=columna,
        columna_original=header_ref,
        motivo="columna_generica_numerica_sin_unidad",
    )


def requiere_pregunta_qc_duracion(estado: DuracionEstado) -> bool:
    """Indica si corresponde preguntar la unidad al usuario (PASO 4).

    Solo aplica cuando la columna existe, es numérica genérica sin unidad
    determinada (no HH:MM:SS/MM:SS, sin encabezado explícito de segundos y
    sin resolución previa por selección del usuario).
    """
    return estado.motivo == "columna_generica_numerica_sin_unidad"


def preguntar_unidad_duracion_qc(
    prompt_fn: Callable[[str], str] = input,
) -> str:
    """[QC] Solicita al usuario la unidad de una duración numérica ambigua.

    Devuelve "milisegundos", "segundos", "minutos" o "desconocida". Enter
    (o cualquier respuesta distinta de "1"/"2"/"3") equivale a "desconocida".
    No persiste la respuesta — aplica solo a la ejecución actual.
    """
    mensaje = (
        "[QC] La columna de duración contiene valores numéricos,\n"
        "pero el archivo no indica claramente la unidad de medida.\n\n"
        "Seleccione la unidad en la que están expresados estos valores:\n\n"
        "[1] Milisegundos\n"
        "[2] Segundos\n"
        "[3] Minutos\n"
        "[4] Unidad desconocida — no calcular duración\n\n"
        "Opción (1/2/3/4, Enter=4): "
    )
    respuesta = prompt_fn(mensaje).strip()
    if respuesta == "1":
        return "milisegundos"
    if respuesta == "2":
        return "segundos"
    if respuesta == "3":
        return "minutos"
    return "desconocida"
