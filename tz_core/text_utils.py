"""
tz_core.text_utils - UTILIDADES DE PROCESAMIENTO DE TEXTO
=========================================================

✅ ESTADO: MIGRACIÓN DESDE MONOLITO - FUNCIONES DE NORMALIZACIÓN
🎯 PROPÓSITO: Limpieza, normalización y corrección de textos
📍 DIFERENCIACIÓN: Procesamiento puro sin dependencias de UI o I/O

RESPONSABILIDADES ESPECÍFICAS:
- _fix_mojibake_text(): Corrección de encoding UTF-8/latin-1 mal decodificado
- normalizar_texto(): Normalización completa con reglas configurables
- normalizar_columnas_texto(): Aplicación masiva a DataFrames pandas

DEPENDENCIAS:
- unicodedata: Normalización de caracteres Unicode (NFKC)
- re: Expresiones regulares para reemplazos y limpieza
- pandas: Operaciones sobre DataFrames (typing opcional)

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 775-850  
FECHA MIGRACIÓN: 27 octubre 2025
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional
try:
    import pandas as pd
except ImportError:
    # Para tests sin pandas instalado
    pd = None


# Tokens comunes de mojibake UTF-8 mal decodificado como latin-1
_MOJIBAKE_TOKENS = ('Ã', 'Â', '�')

# Abreviaturas comunes (case-insensitive)
_DEFAULT_REEMPLAZOS_REGEX = [
    (re.compile(r'\bNvo\.?\b', flags=re.IGNORECASE), 'Nuevo'),
    (re.compile(r'\bNva\.?\b', flags=re.IGNORECASE), 'Nueva'),
    (re.compile(r'\bSta\.?\b', flags=re.IGNORECASE), 'Santa'),
    (re.compile(r'\bSto\.?\b', flags=re.IGNORECASE), 'Santo'),
    (re.compile(r'\bSn\.?\b',  flags=re.IGNORECASE), 'San'),
    # Toponimia frecuente:
    (re.compile(r'\bV(?:alle)?\s+Nvo\.?\b', flags=re.IGNORECASE), 'Valle Nuevo'),
]


def _fix_mojibake_text(s: Any) -> Any:
    """Corrige mojibake típico (UTF-8 mal decodificado como latin-1) y limpia espacios.
    
    Args:
        s: Texto a corregir (puede ser cualquier tipo)
        
    Returns:
        str: Texto corregido si era string, valor original si no
        
    Proceso:
        1. Detección de tokens mojibake comunes (Ã, Â, �)
        2. Intento de recodificación latin1 → utf-8
        3. Fallback a reemplazos de emergencia específicos
        4. Normalización Unicode NFKC
        5. Compactación de espacios en blanco
    """
    if not isinstance(s, str) or not s:
        return s
    if any(t in s for t in _MOJIBAKE_TOKENS):
        # Intento 1: recodificar latin1 -> utf-8
        try:
            s_try = s.encode('latin1', errors='strict').decode('utf-8', errors='strict')
            s = s_try
        except Exception:
            # Intento 2: reemplazos comunes de emergencia
            s = (s.replace('Ã¡', 'á').replace('Ã©', 'é').replace('Ãí', 'í')
                  .replace('Ã³', 'ó').replace('Ãº', 'ú').replace('Ã±', 'ñ')
                  .replace('Â', '')
                  .replace('ÃÁ', 'Á').replace('Ã‰', 'É').replace('ÃÍ', 'Í')
                  .replace('Ã"', 'Ó').replace('Ãš', 'Ú').replace('\u00c3\u0091', 'Ñ')
                  .replace('EstaciÃ³n', 'Estación').replace('MetapÃ¡n', 'Metapán'))
    # Normaliza Unicode y espacios
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _aplicar_reemplazos_regex(s: str, reglas_regex: Optional[List] = None) -> str:
    """Aplica reemplazos usando expresiones regulares compiladas.
    
    Args:
        s: Texto a procesar
        reglas_regex: Lista de tuplas (patrón_compilado, reemplazo)
        
    Returns:
        str: Texto con reemplazos aplicados
    """
    if not isinstance(s, str) or not s:
        return s
    seq = reglas_regex or _DEFAULT_REEMPLAZOS_REGEX
    for pat, repl in seq:
        s = pat.sub(repl, s)
    return s


def normalizar_texto(s: Any, reglas: Optional[Dict[str, str]] = None) -> Any:
    """Arregla mojibake, normaliza Unicode y aplica abreviaturas/reglas (regex o literales).
    
    Args:
        s: Texto a normalizar (puede ser cualquier tipo)
        reglas: Diccionario de patrones → reemplazos desde config.json
        
    Returns:
        str: Texto normalizado si era string, valor original si no
        
    Proceso:
        1. Corrección de mojibake via _fix_mojibake_text()
        2. Aplicación de reglas personalizadas (regex o literal)
        3. Aplicación de abreviaturas estándar via regex
    """
    if not isinstance(s, str):
        return s
    s = _fix_mojibake_text(s)
    # Reglas de config.json (si existen): claves pueden ser regex
    if reglas and isinstance(reglas, dict):
        for k, v in reglas.items():
            try:
                s = re.sub(k, v, s, flags=re.IGNORECASE)
            except re.error:
                s = s.replace(k, v)
    # Reglas por defecto
    s = _aplicar_reemplazos_regex(s)
    return s


def normalizar_columnas_texto(df, columnas: Optional[List[str]] = None, 
                             reglas: Optional[Dict[str, str]] = None):
    """Aplica normalización a columnas de texto (por defecto, todas las 'object').
    
    Respeta NaN/None sin convertirlos a 'None'.
    
    Args:
        df: DataFrame de pandas a procesar
        columnas: Lista específica de columnas, o None para auto-detectar 'object'
        reglas: Diccionario de reglas de normalización
        
    Returns:
        DataFrame: Copia con columnas normalizadas
        
    Raises:
        ImportError: Si pandas no está disponible
    """
    if pd is None:
        raise ImportError("pandas requerido para normalizar_columnas_texto")
        
    if df is None:
        return df
    try:
        cols = columnas or [c for c in df.columns if df[c].dtype == 'object']
        if not cols:
            return df
        return df.assign(**{c: df[c].map(lambda x: normalizar_texto(x, reglas)) for c in cols})
    except Exception:
        return df