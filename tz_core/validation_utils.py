"""
Utilidades de validación y conversión de datos.

Este módulo contiene funciones puras para validar y convertir datos de manera segura,
sin dependencias de lógica de negocio específica.

Funciones:
- tiene_valor: Verifica si un valor no es nulo/vacío/inválido
- es_num: Detecta si un valor es numérico válido
- a_float: Convierte un valor a float de manera segura

Todas las funciones son helpers matemáticos puros extraídos del monolito principal
para mejorar reutilización y testing.
"""

import math
import pandas as pd
import numpy as np


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