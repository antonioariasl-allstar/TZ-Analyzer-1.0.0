"""
tz_services.validation - Funciones de validación de datos

Sprint 1 Fase 1.1: Extracción de 8 funciones SAFE de validación
Origen: script_principal_bitacoras_refactory.py

Funciones migradas:
- validar_columnas (L666) - 3 líneas
- validar_datos (L671) - 25 líneas  
- _valid_latlon_vals (L1811) - 12 líneas
- _first_valid_geo (L3831) - 20 líneas
- _valida_formato_hora (L5568) - 6 líneas
- _valida_fecha_parsible (L5574) - 7 líneas
- _valida_latlon (L5581) - 15 líneas
- validate_schema_or_abort (L5596) - 25 líneas

Fecha: 29 octubre 2025
"""

import pandas as pd
import numpy as np
import sys
from typing import List, Any, Tuple, Optional

# Configuración bbox El Salvador (copiada del monolito)
_bbox_cfg = {
    "lat_min": 13.0,
    "lat_max": 14.5,
    "lon_min": -90.5,
    "lon_max": -87.0
}

def validar_columnas(dataframe: pd.DataFrame, columnas_esperadas: List[str]) -> List[str]:
    """
    Valida que las columnas esperadas existan en el dataframe.
    
    Args:
        dataframe: DataFrame a validar
        columnas_esperadas: Lista de nombres de columnas requeridas
        
    Returns:
        Lista de columnas faltantes (vacía si todas están presentes)
        
    Origen: L666 script_principal_bitacoras_refactory.py
    Tamaño: 3 líneas - SAFE
    """
    return [col for col in columnas_esperadas if col not in dataframe.columns]


def validar_datos(df: pd.DataFrame, columnas_esenciales: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validación básica de datos del dataframe.
    
    Args:
        df: DataFrame a validar
        columnas_esenciales: Columnas que deben estar presentes
        
    Returns:
        Tupla (df_procesado, lista_errores)
        
    Origen: L671 script_principal_bitacoras_refactory.py  
    Tamaño: 25 líneas - SAFE
    NOTA: Implementación completa preservando signature original
    """
    errores = []
    faltantes = validar_columnas(df, columnas_esenciales)
    if faltantes:
        errores.append(f"[FALLBACK] Faltan columnas esenciales: {', '.join(faltantes)}")

    # Copia para no mutar el original
    df_result = df.copy()

    # Garantizar fecha/hora como texto tolerante (sin convertir si no hay)
    if 'fecha' in df_result.columns:
        try:
            df_result['fecha'] = pd.to_datetime(df_result['fecha'], errors='coerce', dayfirst=True)
            mask = df_result['fecha'].isna()
            df_result.loc[~mask, 'fecha'] = df_result.loc[~mask, 'fecha'].dt.strftime("%d/%m/%Y")
            df_result.loc[mask, 'fecha'] = "Sin Inf."
        except Exception:
            df_result['fecha'] = "Sin Inf."
    
    if 'hora' in df_result.columns:
        try:
            horas = pd.to_datetime(df_result['hora'].astype(str).str[:8], format="%H:%M:%S", errors="coerce")
            maskh = horas.isna()
            df_result.loc[~maskh, 'hora'] = horas.dt.strftime("%H:%M:%S")
            df_result.loc[maskh, 'hora'] = "Sin Inf."
        except Exception:
            df_result['hora'] = "Sin Inf."

    # Coordenadas tolerantes
    for c in ('lat', 'long'):
        if c in df_result.columns:
            df_result[c] = pd.to_numeric(df_result[c], errors='coerce')
            
    if 'lat' in df_result.columns and 'long' in df_result.columns:
        maskc = df_result['lat'].isna() | df_result['long'].isna()
        if maskc.any():
            errores.append(f"[FALLBACK] {maskc.sum()} filas con coordenadas inválidas.")
            df_result[['lat', 'long']] = df_result[['lat', 'long']].astype(object)
            df_result.loc[maskc, ['lat', 'long']] = "Sin Inf."
    
    return df_result, errores


def valid_latlon_vals(lt: float, lg: float) -> bool:
    """
    Valida que lat/lon sean numéricas, no NaN, no (0,0) y dentro del bbox SV.
    
    Args:
        lt: Latitud
        lg: Longitud
        
    Returns:
        True si las coordenadas son válidas
        
    Origen: L1811 script_principal_bitacoras_refactory.py
    Tamaño: 12 líneas - SAFE
    """
    try:
        lt = float(lt)
        lg = float(lg)
        if np.isnan(lt) or np.isnan(lg):
            return False
        if abs(lt) < 1e-9 and abs(lg) < 1e-9:
            return False
        return (_bbox_cfg["lat_min"] <= lt <= _bbox_cfg["lat_max"]) and (_bbox_cfg["lon_min"] <= lg <= _bbox_cfg["lon_max"])
    except Exception:
        return False


def first_valid_geo(df: pd.DataFrame, col_lat: str = 'latitud', col_long: str = 'longitud') -> Optional[Tuple[float, float]]:
    """
    Encuentra la primera coordenada válida en el dataframe.
    
    Args:
        df: DataFrame con datos geográficos
        col_lat: Nombre de la columna de latitud
        col_long: Nombre de la columna de longitud
        
    Returns:
        Tupla (lat, lon) de la primera coordenada válida, o None
        
    Origen: L3831 script_principal_bitacoras_refactory.py
    Tamaño: 20 líneas - SAFE
    """
    if col_lat not in df.columns or col_long not in df.columns:
        return None
        
    for _, row in df.iterrows():
        try:
            lat = float(row[col_lat])
            lon = float(row[col_long])
            if valid_latlon_vals(lat, lon):
                return (lat, lon)
        except (ValueError, TypeError):
            continue
    
    return None


def valida_formato_hora(hora_str: str) -> bool:
    """
    Valida que el string tenga formato de hora válido (HH:MM:SS).
    
    Args:
        hora_str: String a validar
        
    Returns:
        True si el formato es válido
        
    Origen: L5568 script_principal_bitacoras_refactory.py
    Tamaño: 6 líneas - SAFE
    """
    try:
        pd.to_datetime(hora_str, format='%H:%M:%S', errors='raise')
        return True
    except Exception:
        return False


def valida_fecha_parsible(fecha_str: str) -> bool:
    """
    Valida que el string sea una fecha parseable.
    
    Args:
        fecha_str: String a validar
        
    Returns:
        True si la fecha es parseable
        
    Origen: L5574 script_principal_bitacoras_refactory.py
    Tamaño: 7 líneas - SAFE
    """
    try:
        pd.to_datetime(fecha_str, dayfirst=True, errors='raise')
        return True
    except Exception:
        return False


def valida_latlon(lat: Any, lon: Any) -> bool:
    """
    Alias de valid_latlon_vals para compatibilidad.
    
    Args:
        lat: Latitud (cualquier tipo)
        lon: Longitud (cualquier tipo)
        
    Returns:
        True si las coordenadas son válidas
        
    Origen: L5581 script_principal_bitacoras_refactory.py
    Tamaño: 15 líneas - SAFE (alias simplificado)
    """
    return valid_latlon_vals(lat, lon)


def validate_schema_or_abort(df: pd.DataFrame, required_cols: List[str], context: str = "dataset") -> None:
    """
    Valida esquema de datos o aborta ejecución.
    
    Args:
        df: DataFrame a validar
        required_cols: Columnas requeridas
        context: Contexto para el mensaje de error
        
    Raises:
        SystemExit: Si la validación falla
        
    Origen: L5596 script_principal_bitacoras_refactory.py
    Tamaño: 25 líneas - SAFE
    """
    missing = validar_columnas(df, required_cols)
    if missing:
        print(f"ERROR: {context} no tiene las columnas requeridas: {', '.join(missing)}")
        print(f"Columnas disponibles: {', '.join(df.columns.tolist())}")
        sys.exit(1)
    
    if df.empty:
        print(f"ERROR: {context} está vacío")
        sys.exit(1)
    
    print(f"✓ {context} validado: {len(df)} filas, {len(df.columns)} columnas")


def es_valida_latlon_row(row, col_lat: str = 'latitud', col_long: str = 'longitud') -> bool:
    """
    Valida coordenadas por fila usando nombres de columnas.
    
    Args:
        row: Fila del DataFrame
        col_lat: Nombre de la columna de latitud
        col_long: Nombre de la columna de longitud
        
    Returns:
        True si las coordenadas de la fila son válidas
        
    Origen: L1823 script_principal_bitacoras_refactory.py
    Tamaño: 27 líneas - SAFE
    """
    if col_lat and col_long and (col_lat in row) and (col_long in row):
        return valid_latlon_vals(row[col_lat], row[col_long])
    return False


def fmt_azimuth(v: Any) -> str:
    """
    Formatea azimuth a string limpio (consolidado de 3 implementaciones).
    
    Args:
        v: Valor azimuth (float, int, string, o None)
        
    Returns:
        String formateado del azimuth
        
    Origen: L1978 script_principal_bitacoras_refactory.py (mejor implementación)
    Consolidación: L1448, L1566, L1978 → versión unificada
    """
    if v is None:
        return '—'
    try:
        f = float(v)
        return f"{int(round(f))}"
    except Exception:
        s = str(v).strip()
        return s if s else '—'


def fmt_coordinate(val: Any) -> str:
    """
    Formatea coordenada a string con 6 decimales (consolidado de 2 implementaciones).
    
    Args:
        val: Valor coordenada (float, int, string, o None)
        
    Returns:
        String formateado de la coordenada con 6 decimales
        
    Origen: L1936 script_principal_bitacoras_refactory.py (mejor implementación)
    Consolidación: L1936, L6342 → versión unificada  
    """
    try:
        if val is None:
            return '—'
        val_f = float(val)
        if np.isnan(val_f):
            return '—'
        return f"{val_f:.6f}"
    except Exception:
        return '—'


def es_columna_valida_para(df: pd.DataFrame, col_name: str, validation_type: str = "numeric") -> bool:
    """
    Valida si una columna es válida para un tipo específico de validación.
    
    Args:
        df: DataFrame
        col_name: Nombre de la columna
        validation_type: Tipo de validación ("numeric", "datetime", "string")
        
    Returns:
        True si la columna es válida para el tipo especificado
        
    Origen: L6011 script_principal_bitacoras_refactory.py
    Tamaño: 10 líneas - SAFE
    """
    if col_name not in df.columns:
        return False
        
    try:
        if validation_type == "numeric":
            pd.to_numeric(df[col_name], errors='raise')
        elif validation_type == "datetime":
            pd.to_datetime(df[col_name], errors='raise')
        # string validation always passes if column exists
        return True
    except Exception:
        return False