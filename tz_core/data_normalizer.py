"""
tz_core.data_normalizer - NORMALIZACIÓN DE DATOS ESPECIALIZADOS
===============================================================

✅ ESTADO: EXTRACCIÓN FASE 9A - FUNCIONES DE NORMALIZACIÓN FECHA/HORA
🎯 PROPÓSITO: Normalización especializada de campos temporales y datos estructurados
📍 DIFERENCIACIÓN: Manejo específico de formatos Excel, ISO, y locales de El Salvador

RESPONSABILIDADES ESPECÍFICAS:
- _normalizar_fecha(): Conversión robusta de fechas desde serial Excel e ISO
- _normalizar_hora(): Normalización de formatos horarios múltiples (HH:MM:SS)
- _pad_hhmmss(): Helper para formateo de cadenas de tiempo

DEPENDENCIAS:
- pandas: Operaciones sobre DataFrames y Series
- datetime: Manejo de objetos temporales
- re: Expresiones regulares para limpieza de formatos
- tz_core.validation_utils: Función es_num() para detección numérica

CARACTERÍSTICAS ESPECIALES:
- Manejo de fechas seriales de Excel (origin="1899-12-30")
- Formato dayfirst=True para región El Salvador (dd/mm/yyyy)
- Tolerancia a múltiples formatos de entrada
- Fallbacks robustos a "Sin Inf." para datos faltantes

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 5527-5580
FECHA MIGRACIÓN: 28 octubre 2025
FASE: 9A - Normalización (Riesgo Bajo)
"""

import re
import pandas as pd
from datetime import datetime
from typing import List
from tz_core.validation_utils import es_num


def _pad_hhmmss(s: str) -> str | None:
    """
    Convierte cadenas de tiempo a formato HH:MM:SS estándar.
    
    Acepta múltiples formatos de entrada y los normaliza:
    - "12:30" → "12:30:00"
    - "9.15.30" → "09:15:30" 
    - "14-20" → "14:20:00"
    - Maneja separadores: . - / :
    
    Args:
        s: Cadena de tiempo en formato variable
        
    Returns:
        Cadena normalizada "HH:MM:SS" o None si no es válida
        
    Examples:
        >>> _pad_hhmmss("12:30")
        "12:30:00"
        >>> _pad_hhmmss("9.15.30")
        "09:15:30"
        >>> _pad_hhmmss("invalid")
        None
    """
    if s is None:
        return None
        
    t = str(s).strip()
    if not t or t.lower() in {"sin inf.", "nan", "none"}:
        return None
        
    # Normalizar separadores: . - / → :
    t = re.sub(r"\s+", "", t).replace(".", ":").replace("-", ":").replace("/", ":")
    
    if ":" in t:
        p = t.split(":")
        h = (p[0] if p[0] else "00").zfill(2)
        m = (p[1] if len(p) > 1 else "00").zfill(2)
        s2 = (p[2] if len(p) > 2 else "00").zfill(2)
        cand = f"{h}:{m}:{s2}"
        
        try:
            # Validar que el tiempo sea válido
            datetime.strptime(cand, "%H:%M:%S")
            return cand
        except Exception:
            return None
    
    return None


def _normalizar_fecha(df: pd.DataFrame) -> List[str]:
    """
    Normaliza la columna 'fecha' del DataFrame manejando múltiples formatos.
    
    Soporta conversión desde:
    - Fechas seriales de Excel (números como 44197.0)
    - Cadenas ISO (2020-12-31, 2020/12/31)
    - Formatos locales (31/12/2020, 31-12-2020)
    - dayfirst=True para región El Salvador
    
    Modifica el DataFrame in-place convirtiendo a formato "dd/mm/yyyy".
    
    Args:
        df: DataFrame con columna 'fecha' a normalizar
        
    Returns:
        Lista de avisos/warnings sobre el proceso
        
    Side Effects:
        Modifica df["fecha"] in-place con formato "dd/mm/yyyy" o "Sin Inf."
        
    Examples:
        >>> df = pd.DataFrame({"fecha": [44197.0, "2020-12-31", "31/12/2020"]})
        >>> avisos = _normalizar_fecha(df)
        >>> df["fecha"].tolist()
        ["31/12/2020", "31/12/2020", "31/12/2020"]
    """
    avisos = []
    
    if "fecha" not in df.columns:
        avisos.append("Pre-flight: no existe columna 'fecha'.")
        return avisos
    
    s = df["fecha"]
    res = pd.Series([pd.NaT] * len(df), index=s.index, dtype="datetime64[ns]")
    
    # 1. Procesar fechas numéricas (seriales de Excel)
    mask_num = s.apply(es_num)
    if mask_num.any():
        res.loc[mask_num] = pd.to_datetime(
            s[mask_num], 
            unit="D", 
            origin="1899-12-30",  # Origen Excel
            errors="coerce"
        )
    
    # 2. Procesar fechas como cadenas (ISO y locales)
    mask_str = ~mask_num
    if mask_str.any():
        res.loc[mask_str] = pd.to_datetime(
            s[mask_str], 
            errors="coerce", 
            dayfirst=True  # Formato dd/mm/yyyy para El Salvador
        )
    
    # 3. Convertir a formato estándar dd/mm/yyyy
    df["fecha"] = res.dt.strftime("%d/%m/%Y").fillna("Sin Inf.")
    
    return avisos


def _normalizar_hora(df: pd.DataFrame) -> List[str]:
    """
    Normaliza la columna 'hora' del DataFrame a formato HH:MM:SS.
    
    Maneja múltiples formatos de entrada:
    - Objetos datetime (extrae solo la hora)
    - Cadenas de tiempo ("12:30", "9.15.30")
    - Formatos con separadores diversos
    
    Modifica el DataFrame in-place convirtiendo a formato "HH:MM:SS".
    
    Args:
        df: DataFrame con columna 'hora' a normalizar
        
    Returns:
        Lista de avisos/warnings sobre el proceso
        
    Side Effects:
        Modifica df["hora"] in-place con formato "HH:MM:SS" o "Sin Inf."
        
    Examples:
        >>> df = pd.DataFrame({"hora": ["12:30", "9.15.30", "14-20"]})
        >>> avisos = _normalizar_hora(df)
        >>> df["hora"].tolist()
        ["12:30:00", "09:15:30", "14:20:00"]
    """
    avisos = []
    
    if "hora" not in df.columns:
        avisos.append("Pre-flight: no existe columna 'hora'.")
        return avisos
    
    col = df["hora"]
    res = pd.Series([None] * len(col), index=col.index, dtype="object")
    
    # 1. Intentar conversión directa a datetime (para objetos time/datetime)
    dt = pd.to_datetime(col, errors="coerce")
    mask_ok = dt.notna()
    if mask_ok.any():
        res.loc[mask_ok] = dt.loc[mask_ok].dt.strftime("%H:%M:%S")
    
    # 2. Para el resto, usar helper de formateo manual
    mask_rest = ~mask_ok
    if mask_rest.any():
        res.loc[mask_rest] = col.loc[mask_rest].apply(_pad_hhmmss)
    
    # 3. Aplicar resultado con fallback a "Sin Inf."
    df["hora"] = res.where(res.notna(), "Sin Inf.")
    
    return avisos


# Funciones auxiliares para debugging y testing
def validar_formato_fecha(fecha_str: str) -> bool:
    """
    Valida que una cadena esté en formato dd/mm/yyyy.
    
    Args:
        fecha_str: Cadena a validar
        
    Returns:
        True si está en formato correcto, False en caso contrario
    """
    if not isinstance(fecha_str, str):
        return False
    
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False


def validar_formato_hora(hora_str: str) -> bool:
    """
    Valida que una cadena esté en formato HH:MM:SS.
    
    Args:
        hora_str: Cadena a validar
        
    Returns:
        True si está en formato correcto, False en caso contrario
    """
    if not isinstance(hora_str, str):
        return False
    
    try:
        datetime.strptime(hora_str, "%H:%M:%S")
        return True
    except ValueError:
        return False