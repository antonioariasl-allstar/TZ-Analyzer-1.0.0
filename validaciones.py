"""
validaciones.py
----------------
Normalización y validación defensiva de bitácoras antes de generar HTML/KML/KMZ.

Objetivos:
- Aceptar variedad de formatos de fecha/hora (serial Excel, strings, datetime).
- Blindar coordenadas (lat/lon) y azimut con conversiones tolerantes.
- No romper en presencia de tipos mixtos (evitar FutureWarnings asignando a object).
- Reportar un resumen de errores/warnings y, si corresponde, guardar un .txt.

Contratos públicos (compatibles con el código existente):
- validar_datos(df, columnas_esenciales) -> (df_validado, errores:list[str])
- guardar_errores(errores, carpeta_salida, nombre_base) -> Optional[str]
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any, Iterable
import os
import math

import pandas as pd
import numpy as np

__all__ = ["validar_datos", "guardar_errores"]


# ==========================
# Utilitarios internos
# ==========================

_SIN_INF = "Sin Inf."

# Algunas bitácoras usan 'long' para longitud; normalizamos a 'lon'
_LONG_ALIASES = {"long", "lng", "longitud", "longitud_inicial", "long_inicial"}
_LAT_ALIASES = {"latitud", "lat", "latitud_inicial", "lat_inicial"}


def _to_object(df: pd.DataFrame, cols: Iterable[str]) -> None:
    """Fuerza dtype=object en columnas antes de asignar strings como 'Sin Inf.'."""
    for c in cols:
        if c in df.columns and df[c].dtype != "O":
            df[c] = df[c].astype("O")


def _is_excel_serial(x: Any) -> bool:
    """True si parece serial de fecha de Excel (número positivo finito)."""
    try:
        # Excel en Windows arranca en 1899-12-30; validamos rango razonable
        # pero no lo limitamos demasiado para no cortar datos históricos.
        f = float(x)
        return math.isfinite(f) and f > 0
    except Exception:
        return False


def _excel_serial_to_timestamp(x: Any) -> Optional[pd.Timestamp]:
    """
    Convierte un serial de Excel a Timestamp (origin=1899-12-30).
    Devuelve None si no puede convertir.
    """
    try:
        return pd.to_datetime(float(x), unit="D", origin="1899-12-30", utc=False)
    except Exception:
        return None


def _safe_to_datetime(
    series: pd.Series,
    dayfirst: bool = True,
    errors: str = "coerce"
) -> pd.Series:
    """
    Convierte a datetime de forma tolerante:
    - Si hay números → intenta como serial Excel.
    - Si hay strings/datetimes → pd.to_datetime() con dayfirst=True (por defecto).
    Devuelve serie dtype datetime64[ns] con NaT donde no se pudo.
    """
    # Fast path: si todo es número y parece serial
    if series.map(_is_excel_serial).all():
        return pd.to_datetime(series.astype(float), unit="D", origin="1899-12-30", utc=False)

    # Mezcla: intentamos elemento a elemento (para evitar advertencias)
    def _parse_cell(v: Any) -> Any:
        if _is_excel_serial(v):
            ts = _excel_serial_to_timestamp(v)
            return ts if ts is not None else pd.NaT
        try:
            return pd.to_datetime(v, dayfirst=dayfirst, errors=errors)
        except Exception:
            return pd.NaT

    return series.map(_parse_cell)


def _normalize_fecha_col(df: pd.DataFrame, col: str) -> Tuple[pd.Series, int]:
    """
    Normaliza columna 'fecha' a str 'YYYY-MM-DD HH:MM:SS' o 'Sin Inf.' si no se puede.
    Devuelve (serie_normalizada, cantidad_invalidos).
    """
    if col not in df.columns:
        # Creamos columna vacía y marcamos todo como inválido
        s = pd.Series([pd.NaT] * len(df), index=df.index)
        invalid = len(df)
    else:
        s = _safe_to_datetime(df[col], dayfirst=True, errors="coerce")
        invalid = int(s.isna().sum())

    # Formato string consistente; NaT -> Sin Inf.
    out = s.dt.strftime("%Y-%m-%d %H:%M:%S")
    out = out.where(~s.isna(), _SIN_INF)
    return out, invalid


def _normalize_hora_col(df: pd.DataFrame, col: str) -> Tuple[pd.Series, int]:
    """
    Normaliza columna 'hora' a str 'HH:MM:SS' o 'Sin Inf.' si no se puede.
    Acepta:
      - strings 'HH:MM', 'HH:MM:SS'
      - datetime (toma solo tiempo)
      - serial Excel (interpreta como fecha y toma hora)
    Devuelve (serie_normalizada, cantidad_invalidos).
    """
    if col not in df.columns:
        s = pd.Series([pd.NaT] * len(df), index=df.index)
        invalid = len(df)
    else:
        raw = df[col]

        # Intento 1: si todo parece número → serial Excel
        if raw.map(_is_excel_serial).all():
            s = pd.to_datetime(raw.astype(float), unit="D", origin="1899-12-30", utc=False)
        else:
            # Intento 2: to_datetime tolerante (strings mixtos / datetime)
            s = pd.to_datetime(raw, errors="coerce", dayfirst=True)

        invalid = int(s.isna().sum())

    # Extraer solo la hora como string HH:MM:SS
    out = s.dt.strftime("%H:%M:%S")
    out = out.where(~s.isna(), _SIN_INF)
    return out, invalid


def _to_float_safe(series: pd.Series) -> Tuple[pd.Series, int]:
    """
    Convierte a float de forma tolerante:
    - Reemplaza coma decimal por punto.
    - Quita espacios/char raros.
    - Devuelve NaN donde no se puede.
    Retorna (serie_float, cantidad_invalidos).
    """
    def _clean(v: Any) -> Any:
        if v is None:
            return np.nan
        try:
            if isinstance(v, str):
                v = v.strip().replace(",", ".")
            return float(v)
        except Exception:
            return np.nan

    out = series.map(_clean).astype(float)
    invalid = int(np.isnan(out).sum())
    return out, invalid


def _coerce_azimut(series: pd.Series) -> Tuple[pd.Series, int]:
    """
    Azimut válido: [0, 359] (0 es válido).
    Cualquier cosa que no sea numérico en ese rango → NaN.
    Retorna (serie_float, cantidad_invalidos).
    """
    def _conv(v: Any) -> Any:
        try:
            f = float(str(v).strip().replace(",", "."))
            if 0 <= f < 360:
                return f
            return np.nan
        except Exception:
            return np.nan

    out = series.map(_conv).astype(float)
    invalid = int(np.isnan(out).sum())
    return out, invalid


def _ensure_lon_name(df: pd.DataFrame) -> None:
    """
    Si existe alguna variante de 'longitud' común, la mapea a 'lon' (sin pisar 'lon' si ya existe).
    """
    if "lon" in df.columns:
        return
    for alias in _LONG_ALIASES:
        if alias in df.columns:
            df.rename(columns={alias: "lon"}, inplace=True)
            return


def _ensure_lat_name(df: pd.DataFrame) -> None:
    """Alias de latitud → 'lat' si aún no existe."""
    if "lat" in df.columns:
        return
    for alias in _LAT_ALIASES:
        if alias in df.columns:
            df.rename(columns={alias: "lat"}, inplace=True)
            return


# ==========================
# API pública
# ==========================

def validar_datos(df: pd.DataFrame, columnas_esenciales: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Normaliza y valida columnas esenciales en df.
    - NO lanza excepciones; devuelve lista de mensajes (errores/warnings).
    - Devuelve un nuevo df (o una vista) con columnas normalizadas.

    columnas_esenciales típicas: ['tel','lat','lon','fecha','hora','azimut', ...]
    """
    errores: List[str] = []
    total = len(df)

    # Asegurar nombres canónicos lat/lon
    _ensure_lat_name(df)
    _ensure_lon_name(df)

    # Convertir a object antes de colocar 'Sin Inf.' (evitar FutureWarning de pandas)
    _to_object(df, ["fecha", "hora", "lat", "lon", "azimut"])

    # ===== Fecha =====
    if "fecha" in columnas_esenciales:
        fecha_norm, inv_f = _normalize_fecha_col(df, "fecha")
        df["fecha"] = fecha_norm
        if inv_f > 0:
            errores.append(f"[WARN] {inv_f}/{total} valores de 'fecha' no válidos → marcados como '{_SIN_INF}'.")

    # ===== Hora =====
    if "hora" in columnas_esenciales:
        hora_norm, inv_h = _normalize_hora_col(df, "hora")
        df["hora"] = hora_norm
        if inv_h > 0:
            errores.append(f"[WARN] {inv_h}/{total} valores de 'hora' no válidos → marcados como '{_SIN_INF}'.")

    # ===== Latitud =====
    if "lat" in columnas_esenciales:
        if "lat" not in df.columns:
            df["lat"] = _SIN_INF
            errores.append(f"[CRIT] Columna 'lat' ausente → marcada como '{_SIN_INF}'.")
            inv_lat = total
        else:
            lat_f, inv_lat = _to_float_safe(df["lat"])
            # Guardamos como string para no romper cuando se imprimen/usan en HTML
            df["lat"] = lat_f.map(lambda v: _SIN_INF if np.isnan(v) else f"{v:.6f}")
            if inv_lat > 0:
                errores.append(f"[WARN] {inv_lat}/{total} valores de 'lat' inválidos → '{_SIN_INF}'.")

    # ===== Longitud =====
    if "lon" in columnas_esenciales:
        if "lon" not in df.columns:
            df["lon"] = _SIN_INF
            errores.append(f"[CRIT] Columna 'lon' ausente → marcada como '{_SIN_INF}'.")
            inv_lon = total
        else:
            lon_f, inv_lon = _to_float_safe(df["lon"])
            df["lon"] = lon_f.map(lambda v: _SIN_INF if np.isnan(v) else f"{v:.6f}")
            if inv_lon > 0:
                errores.append(f"[WARN] {inv_lon}/{total} valores de 'lon' inválidos → '{_SIN_INF}'.")

    # ===== Azimut (si está en esenciales, lo tratamos; si no, lo dejamos pasar) =====
    if "azimut" in columnas_esenciales:
        if "azimut" not in df.columns:
            df["azimut"] = _SIN_INF
            errores.append(f"[INFO] Columna 'azimut' ausente → se omite (colocada como '{_SIN_INF}').")
        else:
            az_f, inv_az = _coerce_azimut(df["azimut"])
            # preservar 0 como válido y formatear sin decimales si es entero
            def _fmt_az(v: float) -> str:
                if np.isnan(v):
                    return _SIN_INF
                # 0–359 pueden traer coma; mostramos sin decimales si es entero
                return f"{int(v)}" if float(v).is_integer() else f"{v:.1f}"
            df["azimut"] = az_f.map(_fmt_az)
            if inv_az > 0:
                errores.append(f"[WARN] {inv_az}/{total} valores de 'azimut' inválidos → '{_SIN_INF}'.")

    # ===== Otros esenciales presentes pero no tratados arriba → si faltan, marca =====
    for col in columnas_esenciales:
        if col not in df.columns:
            df[col] = _SIN_INF
            errores.append(f"[CRIT] Columna esencial '{col}' ausente → marcada como '{_SIN_INF}'.")

    # Nota: aquí NO filtramos filas ni abortamos; dejamos a la etapa HTML/KML decidir.

    return df, errores


def guardar_errores(errores: List[str], carpeta_salida: str, nombre_base: str) -> Optional[str]:
    """
    Guarda un TXT con los errores si hay algo que reportar.
    Retorna la ruta del archivo generado o None si no se generó nada.
    """
    if not errores:
        return None

    try:
        os.makedirs(carpeta_salida, exist_ok=True)
    except Exception:
        # si no se puede crear, evitamos tronar (mejor que falle en open con mensaje claro)
        pass

    ruta = os.path.join(carpeta_salida, f"{nombre_base}_errores.txt")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("=== Reporte de validación / normalización ===\n")
            for e in errores:
                f.write(f"{e}\n")
        return ruta
    except Exception as ex:
        # No impedimos el flujo por problemas al escribir el log.
        print(f"[WARN] No se pudo guardar el reporte de errores en '{ruta}': {ex}")
        return None
