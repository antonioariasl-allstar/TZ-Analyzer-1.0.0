#!/usr/bin/env python3
"""
tz_core.time_utils - Utilidades de tiempo para TZ Analyzer

Funciones puras para manipulación, conversión y clasificación de tiempo.
Extraídas del script_principal_bitacoras_refactory.py para modularización.

Módulo de bajo riesgo - funciones sin estado y sin dependencias externas complejas.
"""

from datetime import time as _time, datetime as _datetime
import re
from typing import Optional, List, Dict, Tuple, Any

import pandas as pd
import numpy as np
import warnings

from tz_core.bitacora_normalization import parse_date_series

# Definición de rangos horarios para clasificación "SV" (usado en carpetas de KML)
# Formato: clave -> (nombre_carpeta, hora_inicio, hora_fin)
RANGOS_SV = {
    "madrugada": ("madrugada_0000-0559", _time(0, 0, 0),  _time(5, 59, 59)),  # 00:00–05:59
    "manana":    ("manana_0600-1159",    _time(6, 0, 0),  _time(11, 59, 59)), # 06:00–11:59
    "tarde":     ("tarde_1200-1759",     _time(12, 0, 0), _time(17, 59, 59)), # 12:00–17:59
    "noche":     ("noche_1800-2359",     _time(18, 0, 0), _time(23, 59, 59)), # 18:00–23:59
}


def hhmmss_to_time_or_none(hh: Any) -> Optional[_time]:
    """
    Convierte una cadena en formato HH:MM:SS a objeto datetime.time.
    
    Args:
        hh: Cadena con formato HH:MM:SS (se toman máx. 8 caracteres)
    
    Returns:
        datetime.time si la conversión es exitosa, None en caso de error
    """
    try:
        h, m, s = str(hh).strip()[:8].split(":")
        return _time(int(h), int(m), int(s))
    except Exception:
        return None


def normalize_hour_to_hhmmss(value: Any) -> Optional[str]:
    """
    Normaliza valores horarios con separadores variados a formato HH:MM:SS.

    Acepta entradas como "6.30", "14-20", "18/45", "2025-01-04 21:15:30" o
    objetos datetime/time. Devuelve None si no puede normalizar.
    """

    if value is None:
        return None

    try:
        if isinstance(value, float) and (np.isnan(value)):
            return None
    except Exception:
        pass

    s = str(value).strip()
    if not s:
        return None

    s_lower = s.lower()
    if s_lower in {"sin inf.", "sin inf", "s/i", "nan", "none"}:
        return None

    # 1) Intentar parsear timestamps completos o formatos estándar con pandas
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass

    # 2) Normalizar separadores variados (., -, /, espacios) a ":"
    t = re.sub(r"\s+", "", s)
    t = t.replace(".", ":").replace("-", ":").replace("/", ":")
    parts = t.split(":")
    if not parts:
        return None

    try:
        h = int(parts[0]) if parts[0] != "" else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
        sec = int(parts[2]) if len(parts) > 2 and parts[2] != "" else 0
        cand = f"{h:02d}:{m:02d}:{sec:02d}"
        # Validar rango usando datetime
        _datetime.strptime(cand, "%H:%M:%S")
        return cand
    except Exception:
        return None


def en_rango_tiempo(t: _time, ini: _time, fin: _time) -> bool:
    """
    Verifica si un tiempo t está dentro del rango [ini, fin].
    Soporta rangos que cruzan medianoche (ej: 22:00 a 02:00).
    
    Args:
        t: Tiempo a verificar
        ini: Tiempo de inicio del rango
        fin: Tiempo de fin del rango
    
    Returns:
        True si t está dentro del rango, False en caso contrario
    """
    if ini <= fin:
        return ini <= t <= fin
    return (t >= ini) or (t <= fin)


def clasificar_rango_sv(hhmmss: str) -> Optional[str]:
    """
    Clasifica una hora HH:MM:SS en uno de los rangos SV predefinidos
    (madrugada, manana, tarde, noche) según RANGOS_SV.
    
    Args:
        hhmmss: Cadena con formato HH:MM:SS
    
    Returns:
        Clave del rango ('madrugada', 'manana', 'tarde', 'noche') o None si no aplica
    """
    t = hhmmss_to_time_or_none(hhmmss)
    if t is None:
        return None
    for clave, (_, ini, fin) in RANGOS_SV.items():
        if en_rango_tiempo(t, ini, fin):
            return clave
    return None


def parse_hhmmss_to_minutes(s: Optional[str]) -> Optional[int]:
    """
    Convierte 'HH:MM' o 'HH:MM:SS' a minutos desde 00:00. 
    
    Args:
        s: Cadena con formato HH:MM o HH:MM:SS
        
    Returns:
        Minutos desde 00:00 o None si no se puede convertir
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        # ignorar segundos si vienen
        return hh * 60 + mm
    except Exception:
        return None


def minutes_from_any(hora: Any) -> Optional[int]:
    """
    Acepta: datetime.time, datetime.datetime, pandas.Timestamp, str 'HH:MM(:SS)'.
    Devuelve minutos desde 00:00 o None.
    
    Args:
        hora: Objeto de tiempo en diversos formatos
        
    Returns:
        Minutos desde 00:00 o None si no se puede convertir
    """
    try:
        # pandas.Timestamp o datetime
        if hasattr(hora, "hour") and hasattr(hora, "minute"):
            return int(hora.hour) * 60 + int(hora.minute)
        if isinstance(hora, _time):
            return hora.hour * 60 + hora.minute
        # string
        return parse_hhmmss_to_minutes(str(hora))
    except Exception:
        return None


def to_datetime_silent(value: Any, **kwargs) -> pd.Series:
    """Wrapper de pd.to_datetime que silencia el warning de formato no inferido."""

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format*",
            category=UserWarning,
        )
        return pd.to_datetime(value, **kwargs)


def construir_rangos_cfg(rangos_cfg: List[Dict[str, Any]]) -> List[Tuple[str, int, int]]:
    """
    Convierte configuración de rangos a formato de minutos.
    
    Args:
        rangos_cfg: Lista de diccionarios con "nombre", "inicio", "fin"
        
    Returns:
        Lista de tuplas (nombre, minutos_inicio, minutos_fin)
    """
    res = []
    for r in rangos_cfg:
        n = str(r.get("nombre", "")).strip() or "Rango"
        mi = parse_hhmmss_to_minutes(r.get("inicio"))
        mf = parse_hhmmss_to_minutes(r.get("fin"))
        if mi is None or mf is None:
            continue
        res.append((n, mi, mf))
    return res


def en_rango_minutos(minutos: int, ini: int, fin: int) -> bool:
    """
    True si 'minutos' cae dentro del rango [ini..fin] en minutos.
    Soporta cruce de medianoche: si ini > fin, el rango pasa por 00:00.
    
    Args:
        minutos: Minutos desde 00:00 a verificar
        ini: Minutos de inicio del rango
        fin: Minutos de fin del rango
        
    Returns:
        True si está dentro del rango, False en caso contrario
    """
    if ini <= fin:
        return ini <= minutos <= fin
    # Cruce de medianoche: ejemplo 18:01–01:00 -> minutos >= ini O minutos <= fin
    return minutos >= ini or minutos <= fin


def etiqueta_rango(hora: Any, rangos_cfg: List[Dict[str, Any]], default: str = "Sin rango") -> str:
    """
    Devuelve el 'nombre' del rango del config que contiene 'hora'.
    'hora' puede ser time/datetime/Timestamp o str 'HH:MM(:SS)'.
    
    Args:
        hora: Objeto de tiempo en diversos formatos
        rangos_cfg: Lista de diccionarios con configuración de rangos
        default: Valor por defecto si no coincide ningún rango
        
    Returns:
        Nombre del rango que contiene la hora o valor por defecto
    """
    m = minutes_from_any(hora)
    if m is None:
        return default
    rangos = construir_rangos_cfg(rangos_cfg)
    for nombre, mi, mf in rangos:
        if en_rango_minutos(m, mi, mf):
            return nombre
    return default


# Funciones auxiliares para mantener compatibilidad con nombres originales
# Alias de compatibilidad con nombres internos anteriores a la modularización
_hhmmss_to_time_or_none = hhmmss_to_time_or_none
_en_rango = en_rango_tiempo
_clasificar_rango_sv = clasificar_rango_sv
_parse_hhmmss_to_minutes = parse_hhmmss_to_minutes
_minutes_from_any = minutes_from_any
_construir_rangos_cfg = construir_rangos_cfg
_en_rango_minutos = en_rango_minutos


def to_datetime_series(df: Any) -> pd.Series:
    """Construye la serie temporal canónica sin reinterpretar fechas ISO.

    Precedencia:
    1. ``datetime_evento``, creado durante la ingesta y considerado autoritativo.
    2. Combinación de ``fecha`` y ``hora`` para completar filas sin timestamp.
    3. Alias históricos de columnas datetime.
    4. ``fecha`` sola a medianoche.

    ``dayfirst`` solo se aplica a textos regionales. Los valores ISO
    ``YYYY-MM-DD`` se procesan mediante :func:`parse_date_series`, evitando que
    ``2026-05-01`` se convierta accidentalmente en 5 de enero.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df debe ser un pandas DataFrame")

    event_dt = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    if "datetime_evento" in df.columns:
        event_dt = pd.to_datetime(df["datetime_evento"], errors="coerce")

    if "fecha" in df.columns and "hora" in df.columns:
        try:
            fechas = parse_date_series(df["fecha"], dayfirst=True).dt.normalize()
            horas_norm = df["hora"].map(normalize_hour_to_hhmmss)
            horas = pd.to_timedelta(horas_norm, errors="coerce")
            combined = fechas + horas
            # Fila con fecha válida pero hora ausente/no parseable: usar la
            # fecha sola (medianoche, solo como ancla de orden) en vez de
            # NaT, para no perder la fila de las agrupaciones por fecha. La
            # hora ausente se preserva en la columna 'hora' original.
            combined = combined.where(combined.notna(), fechas)
            result = event_dt.combine_first(combined)
            if result.notna().any():
                return result
        except Exception:
            if event_dt.notna().any():
                return event_dt

    if event_dt.notna().any():
        return event_dt

    for column in ["datetime", "fecha_hora", "timestamp", "fec_hor", "fechaHora"]:
        if column in df.columns:
            series = to_datetime_silent(df[column], dayfirst=True, errors="coerce")
            if series.notna().any():
                return series

    if "fecha" in df.columns:
        return parse_date_series(df["fecha"], dayfirst=True)
    return pd.Series(pd.NaT, index=df.index)


def format_seconds_hms(total_seconds: Any) -> str:
    """Formatea segundos totales en HH:MM:SS con tolerancia a entradas inválidas."""
    try:
        total_seconds = float(total_seconds)
    except Exception:
        return "00:00:00"
    if np.isnan(total_seconds):
        return "00:00:00"
    total_seconds = int(round(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _to_datetime_series(df: Any) -> pd.Series:  # pragma: no cover
    return to_datetime_series(df)


def _fmt_hms(total_seconds: Any) -> str:  # pragma: no cover
    return format_seconds_hms(total_seconds)
