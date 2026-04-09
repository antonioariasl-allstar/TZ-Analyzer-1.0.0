#!/usr/bin/env python3
"""
tz_core.validation_utils - Utilidades de validación para TZ Analyzer

Funciones puras para validación de datos y tipos.
Extraídas del script_principal_bitacoras_refactory.py para modularización.

Módulo de bajo riesgo - funciones sin estado y sin dependencias externas complejas.
"""

import math
import pandas as pd
import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple


def tiene_valor(v: Any) -> bool:
    """
    Verifica si un valor tiene contenido útil (no es None, NaN, vacío o texto sin información).
    
    Args:
        v: Valor a verificar
        
    Returns:
        True si el valor tiene contenido útil, False en caso contrario
    """
    if v is None:
        return False
    try:
        if isinstance(v, float) and math.isnan(v):
            return False
    except Exception:
        pass
    v_str = str(v).strip()
    if v_str == "" or v_str.lower() in {"sin inf.", "sin inf", "s/i", "sininf", "none", "null", "n/a", "na", "--", "—"}:
        return False
    return True


def es_num(x: Any) -> bool:
    """
    Verifica si un valor es numérico válido (int, float, numpy number) y no es NaN.
    
    Args:
        x: Valor a verificar
        
    Returns:
        True si es un número válido, False en caso contrario
    """
    try:
        return (isinstance(x, (int, float, np.number)) and not pd.isna(x))
    except Exception:
        return False


def a_float(v: Any) -> float | None:
    """
    Convierte un valor a float, reemplazando comas por puntos.
    Descarta valores infinitos.
    
    Args:
        v: Valor a convertir
        
    Returns:
        float si la conversión es exitosa, None en caso contrario o si el valor es infinito
    """
    try:
        s = str(v).replace(",", ".")
        f = float(s)
        return f if math.isfinite(f) else None  # descarta inf y -inf
    except Exception:
        return None


def es_vacio_o_nulo(v: Any) -> bool:
    """
    Verifica si un valor está vacío o es nulo.
    
    Args:
        v: Valor a verificar
        
    Returns:
        True si está vacío o es nulo, False en caso contrario
    """
    return not tiene_valor(v)


def normalizar_numero(v: Any, default: Any = None) -> float | None:
    """
    Normaliza un valor a número float, con valor por defecto.
    
    Args:
        v: Valor a normalizar
        default: Valor por defecto si no se puede convertir
        
    Returns:
        float normalizado o valor por defecto
    """
    resultado = a_float(v)
    return resultado if resultado is not None else default


def es_entero_valido(v: Any) -> bool:
    """
    Verifica si un valor puede ser interpretado como entero válido.
    
    Args:
        v: Valor a verificar
        
    Returns:
        True si puede ser entero, False en caso contrario
    """
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return False
        float_val = a_float(v)
        if float_val is None:
            return False
        return float_val == int(float_val)
    except Exception:
        return False


def limpiar_texto_validacion(texto: Any) -> str:
    """
    Limpia y normaliza texto para validación.
    
    Args:
        texto: Texto a limpiar
        
    Returns:
        Texto limpio como string
    """
    if texto is None:
        return ""
    return str(texto).strip()


# Funciones auxiliares para mantener compatibilidad con nombres originales
# Alias de compatibilidad con nombres internos anteriores a la modularización
_tiene_valor = tiene_valor
_es_num = es_num


# ==============================================================================
# VALIDACIÓN DE DATAFRAMES — Absorbido de validaciones.py (F10.1)
# ==============================================================================

"""
validaciones.py - SISTEMA DE VALIDACIÓN FORENSE ACTIVO
======================================================

✅ ESTADO: CÓDIGO EN PRODUCCIÓN - SISTEMA COMPLETO DE VALIDACIÓN
🎯 PROPÓSITO: Normalización y validación defensiva de bitácoras forenses
📍 DIFERENCIACIÓN: NO confundir con tz_core/data_validator.py (esqueleto vacío)

FUNCIONES PRINCIPALES EN PRODUCCIÓN:
- validar_datos(): Pipeline completo de validación (función pública)
- guardar_errores(): Generación de reportes de errores
- _normalize_fecha_col(): Normalización de fechas (Excel serial, ISO, local)
- _normalize_hora_col(): Normalización de horas con timezone
- _to_float_safe(): Conversión segura de coordenadas
- _coerce_azimut(): Validación de azimut [0..360)

ARQUITECTURA HÍBRIDA:
- Este archivo contiene TODA la lógica de validación funcional
- tz_core/data_validator.py es esqueleto para migración futura
- Usado activamente por script_principal_bitacoras_refactory.py

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

import logging                                                           # ✚ logging
from typing import Iterable, Literal                                     # ✚ Literal (extra)


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
    errors: Literal["raise", "coerce", "ignore"] = "coerce"
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
        """Intenta parsear una celda individual a datetime manejando seriales de Excel."""
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
        """Limpia un valor eliminando espacios y reemplazando comas por puntos antes de conversión."""
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
        """Convierte un valor a float validando rango de azimut [0, 359] o devuelve NaN."""
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
    Normaliza y valida columnas esenciales en un DataFrame sin lanzar excepciones.

    Parámetros:
        df (pd.DataFrame): DataFrame de bitácora a validar/normalizar (se trabaja sobre referencia).
        columnas_esenciales (List[str]): Nombres canónicos esperados (p. ej. ['tel','lat','lon','fecha','hora','azimut']).

    Retorna:
        Tuple[pd.DataFrame, List[str]]: (df normalizado, lista de mensajes de error/warn/info).

    Notas:
        - No aborta ni filtra filas; la etapa HTML/KML decide.
        - Coloca 'Sin Inf.' donde no es posible normalizar.
        - Alias comunes de lat/lon se mapean a ('lat','lon') si existen.
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
            def _fmt_az(v: float) -> str:
                """Formatea valor de azimut para presentación, sin decimales si es entero."""
                if np.isnan(v):
                    return _SIN_INF
                return f"{int(v)}" if float(v).is_integer() else f"{v:.1f}"
            df["azimut"] = az_f.map(_fmt_az)
            if inv_az > 0:
                errores.append(f"[WARN] {inv_az}/{total} valores de 'azimut' inválidos → '{_SIN_INF}'.")

    # ===== Otros esenciales presentes pero no tratados arriba → si faltan, marca =====
    for col in columnas_esenciales:
        if col not in df.columns:
            df[col] = _SIN_INF
            errores.append(f"[CRIT] Columna esencial '{col}' ausente → marcada como '{_SIN_INF}'.")

    return df, errores


def guardar_errores(errores: List[str], carpeta_salida: str, nombre_base: str) -> Optional[str]:
    """
    Guarda un reporte de validación en un archivo .txt cuando hay mensajes.

    Parámetros:
        errores (List[str]): Mensajes a registrar.
        carpeta_salida (str): Carpeta destino (se crea si no existe).
        nombre_base (str): Prefijo del archivo (genera '<nombre_base>_errores.txt').

    Retorna:
        Optional[str]: Ruta del archivo generado, o None si no se creó.

    Notas:
        - Ante error al escribir, se debe registrar el aviso por logging y retornar None.
        - La configuración del logging corresponde al punto de entrada (run.py).
    """

    if not errores:
        return None

    try:
        os.makedirs(carpeta_salida, exist_ok=True)
    except Exception:
        pass

    ruta = os.path.join(carpeta_salida, f"{nombre_base}_errores.txt")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("=== Reporte de validación / normalización ===\n")
            for e in errores:
                f.write(f"{e}\n")
        return ruta
    except Exception as ex:
        logging.warning("No se pudo guardar el reporte de errores en '%s': %s", ruta, ex)
        return None