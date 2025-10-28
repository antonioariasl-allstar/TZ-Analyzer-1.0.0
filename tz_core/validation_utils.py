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
from typing import Any


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
# TODO: Deprecar en futuras versiones cuando se complete la modularización
def _tiene_valor(v: Any) -> bool:
    """Alias para compatibilidad hacia atrás."""
    return tiene_valor(v)

def _es_num(x: Any) -> bool:
    """Alias para compatibilidad hacia atrás."""
    return es_num(x)

def _a_float(v: Any) -> float | None:
    """Alias para compatibilidad hacia atrás."""
    return a_float(v)