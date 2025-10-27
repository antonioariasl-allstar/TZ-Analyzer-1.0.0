"""
tz_core.validation_utils - UTILIDADES DE VALIDACIÓN EXPANDIDAS
============================================================

✅ MÓDULO: #8 del framework tz_core/ - EXPANDIDO EN FASE 2G
🎯 PROPÓSITO: Utilities de validación de datos (básicas + avanzadas)
🚀 EXPANSIÓN: FASE 2G - Validation Utils avanzadas migradas desde validaciones.py

FUNCIONES BÁSICAS (ya existentes):
- tiene_valor: Verifica si un valor no es nulo/vacío/inválido
- es_num: Detecta si un valor es numérico válido  
- a_float: Convierte un valor a float de manera segura

FUNCIONES AVANZADAS (FASE 2G):
- to_object: Conversión segura de tipos a object para evitar FutureWarnings
- is_excel_serial: Detección de números seriales de Excel para fechas
- excel_serial_to_timestamp: Conversión de seriales Excel a timestamps
- to_float_safe: Conversión tolerante a float con limpieza de datos
- coerce_azimut: Validación de azimut en rango [0..360)

ESTRATEGIA ULTRA-CONSERVADORA:
- Migrate helpers only: ✅ Solo funciones utility puras
- Preserve business logic: ✅ Lógica principal permanece en validaciones.py
- Comprehensive testing: ✅ Tests exhaustivos para edge cases
- Zero regressions: ✅ Backward compatibility garantizada

Todas las funciones son helpers matemáticos puros extraídos del monolito principal
para mejorar reutilización y testing.
"""

import math
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Any, Iterable


def tiene_valor(v) -> bool:
    """
    Verifica si un valor no es nulo, vacío o inválido.
    
    Considera inválidos: None, NaN, strings vacíos, y varios indicadores
    comunes de valores faltantes.
    
    Args:
        v: Valor a verificar (cualquier tipo)
    
    Returns:
        bool: True si el valor es válido, False si es nulo/vacío/inválido
    
    Examples:
        >>> tiene_valor(42)
        True
        >>> tiene_valor(None)
        False
        >>> tiene_valor("")
        False
        >>> tiene_valor("sin inf")
        False
        >>> tiene_valor(float('nan'))
        False
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


def es_num(x) -> bool:
    """
    Detecta si un valor es numérico válido.
    
    Verifica que sea int, float, o numpy number, y que no sea NaN.
    
    Args:
        x: Valor a verificar
    
    Returns:
        bool: True si es numérico válido, False en caso contrario
    
    Examples:
        >>> es_num(42)
        True
        >>> es_num(3.14)
        True
        >>> es_num("hello")
        False
        >>> es_num(float('nan'))
        False
    """
    try:
        return (isinstance(x, (int, float, np.number)) and not pd.isna(x))
    except Exception:
        return False


def a_float(v):
    """
    Convierte un valor a float de manera segura.
    
    Maneja conversión de strings con comas como separador decimal,
    y descarta valores infinitos.
    
    Args:
        v: Valor a convertir (cualquier tipo)
    
    Returns:
        float | None: Valor convertido a float, o None si la conversión falla
                     o el resultado es infinito
    
    Examples:
        >>> a_float("3,14")
        3.14
        >>> a_float("42")
        42.0
        >>> a_float("invalid")
        None
        >>> a_float(float('inf'))
        None
    """
    try:
        s = str(v).replace(",", ".")
        f = float(s)
        return f if math.isfinite(f) else None  # descarta inf y -inf
    except Exception:
        return None


# Aliases para compatibilidad con código existente
_tiene_valor = tiene_valor
_es_num = es_num
_a_float = a_float


# ========================================
# FUNCIONES AVANZADAS - FASE 2G EXPANSION
# ========================================

def to_object(df: pd.DataFrame, cols: Iterable[str]) -> None:
    """
    Fuerza dtype=object en columnas antes de asignar strings como 'Sin Inf.'.
    
    Previene FutureWarnings cuando pandas intenta asignar strings mixtos.
    Modifica el DataFrame in-place para evitar copias innecesarias.
    
    Args:
        df: DataFrame a modificar
        cols: Nombres de columnas a convertir a object
        
    Ejemplo:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'nums': [1, 2, 3], 'texto': ['a', 'b', 'c']})
        >>> to_object(df, ['nums'])  # Evita warning al asignar strings después
    """
    for c in cols:
        if c in df.columns and df[c].dtype != "O":
            df[c] = df[c].astype("O")


def is_excel_serial(x: Any) -> bool:
    """
    Determina si un valor parece un serial de fecha de Excel.
    
    Excel almacena fechas como números donde 1 = 1900-01-01.
    Validamos que sea un número positivo finito en rango razonable.
    
    Args:
        x: Valor a evaluar (cualquier tipo)
        
    Returns:
        True si parece un serial de Excel válido
        
    Ejemplo:
        >>> is_excel_serial(44927)  # True - Feb 2023
        >>> is_excel_serial("texto")  # False
        >>> is_excel_serial(-1)  # False - fuera de rango
    """
    try:
        # Excel en Windows arranca en 1899-12-30; validamos rango razonable
        # pero no lo limitamos demasiado para no cortar datos históricos.
        f = float(x)
        return math.isfinite(f) and f > 0
    except Exception:
        return False


def excel_serial_to_timestamp(x: Any) -> Optional[pd.Timestamp]:
    """
    Convierte un serial de Excel a pandas Timestamp.
    
    Utiliza origin=1899-12-30 que es el estándar de Excel en Windows.
    Retorna None si la conversión falla por cualquier motivo.
    
    Args:
        x: Valor que debería ser un serial de Excel
        
    Returns:
        Timestamp convertido o None si falla
        
    Ejemplo:
        >>> excel_serial_to_timestamp(44927)
        Timestamp('2023-02-15 00:00:00')
        >>> excel_serial_to_timestamp("invalid")
        None
    """
    try:
        return pd.to_datetime(float(x), unit="D", origin="1899-12-30", utc=False)
    except Exception:
        return None


def to_float_safe(series: pd.Series) -> Tuple[pd.Series, int]:
    """
    Convierte pandas Series a float de forma tolerante con limpieza.
    
    Maneja casos comunes de datos sucios:
    - Comas decimales → puntos decimales
    - Espacios en blanco → eliminados
    - Strings no numéricos → NaN
    - Valores None/null → NaN
    
    Args:
        series: Serie de pandas a convertir
        
    Returns:
        Tupla de (serie_convertida, cantidad_valores_invalidos)
        
    Ejemplo:
        >>> s = pd.Series(["3,14", " 2.71 ", "texto", None])
        >>> clean_s, invalid_count = to_float_safe(s)
        >>> print(clean_s.tolist())  # [3.14, 2.71, NaN, NaN]
        >>> print(invalid_count)  # 2
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


def coerce_azimut(series: pd.Series) -> Tuple[pd.Series, int]:
    """
    Valida y convierte valores de azimut al rango [0, 360).
    
    Azimut debe ser un número en el rango [0, 359] donde:
    - 0° = Norte
    - 90° = Este  
    - 180° = Sur
    - 270° = Oeste
    
    Cualquier valor fuera del rango o no numérico se convierte a NaN.
    
    Args:
        series: Serie con valores de azimut a validar
        
    Returns:
        Tupla de (serie_validada, cantidad_valores_invalidos)
        
    Ejemplo:
        >>> s = pd.Series([0, 90, 180, 270, 360, -10, "N"])
        >>> clean_s, invalid = coerce_azimut(s)
        >>> print(clean_s.tolist())  # [0.0, 90.0, 180.0, 270.0, NaN, NaN, NaN]
        >>> print(invalid)  # 3
    """
    def _conv(v: Any) -> Any:
        try:
            f = float(v)
            # Azimut válido: [0, 359] (incluye 0, excluye 360)
            if math.isfinite(f) and 0 <= f < 360:
                return f
            return np.nan
        except Exception:
            return np.nan

    out = series.map(_conv).astype(float)
    invalid = int(np.isnan(out).sum())
    return out, invalid


# Aliases de compatibilidad para funciones migradas
_to_object = to_object
_is_excel_serial = is_excel_serial
_excel_serial_to_timestamp = excel_serial_to_timestamp
_to_float_safe = to_float_safe
_coerce_azimut = coerce_azimut