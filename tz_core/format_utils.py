"""
tz_core.format_utils - UTILIDADES DE FORMATEO DE VALORES
========================================================

✅ ESTADO: MIGRACIÓN DESDE MONOLITO - FUNCIONES DE FORMATEO
🎯 PROPÓSITO: Formateo específico de valores para diferentes contextos (KML, HTML, etc.)
📍 DIFERENCIACIÓN: Formateo especializado sin dependencias de UI o I/O

RESPONSABILIDADES ESPECÍFICAS:
- _formatear_valor_para_burbuja(): Formateo específico para burbujas KML/HTML
- Reglas por tipo de columna: lat/long (decimales), azimut/lac (enteros), etc.
- Manejo de casos especiales: IMEI (sin notación científica), duración (HH:MM:SS)

DEPENDENCIAS:
- re: Expresiones regulares para validación y formateo
- tz_core.validation_utils: Para función _a_float()

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 1311-1375  
FECHA MIGRACIÓN: 27 octubre 2025
"""

import re
from decimal import Decimal
from typing import Any, Optional

# Import de validation_utils para _a_float
try:
    from .validation_utils import _a_float
except ImportError:
    # Fallback si validation_utils no está disponible
    def _a_float(val) -> Optional[float]:
        """Fallback básico para convertir a float"""
        try:
            return float(val)
        except (ValueError, TypeError):
            return None


def _formatear_valor_para_burbuja(col: str, val: Any) -> str:
    """
    Formatear valores según reglas específicas para burbujas KML/HTML.
    
    Reglas por tipo de columna:
    - lat/long: 6 decimales de precisión
    - azimut/lac: enteros (sin .0) si son numéricos; texto si no
    - celda: entero si es numérica; texto si es alfanumérica (ej: "C102")
    - imei: limpieza de .0 y notación científica
    - duracion: conversión segundos -> HH:MM:SS; preserva formato existente
    - demás: string tal cual
    
    Args:
        col: Nombre de la columna (usado para determinar reglas)
        val: Valor a formatear
        
    Returns:
        str: Valor formateado según las reglas específicas
        
    Examples:
        >>> _formatear_valor_para_burbuja("lat", 13.123456789)
        '13.123457'
        >>> _formatear_valor_para_burbuja("azimut", 45.0)
        '45'
        >>> _formatear_valor_para_burbuja("celda", "C102")
        'C102'
        >>> _formatear_valor_para_burbuja("duracion", 3661)
        '01:01:01'
    """
    col = (col or "").strip().lower()
    s = str(val).strip()

    # lat/long -> 6 decimales
    if col in {"lat", "long"}:
        f = _a_float(val)
        return None if f is None else f"{f:.6f}"

    # azimut / lac -> enteros si son numéricos; si no, se deja el texto
    if col in {"azimut", "lac"}:
        f = _a_float(val)
        return s if f is None else str(int(round(f)))

    # celda -> entero si es numérico; si no, se deja el texto (p.ej., "C102")
    if col == "celda":
        f = _a_float(val)
        return s if f is None else str(int(round(f)))

    # imei -> cadena limpia sin .0 ni notación científica
    if col == "imei":
        s_clean = str(val).strip()
        try:
            # caso 123456789012345.0 -> 123456789012345
            m = re.fullmatch(r'(\d+)\.0+', s_clean)
            if m:
                return m.group(1)
            # caso notación científica: 3.579E14 -> 357900000000000
            if re.fullmatch(r'\d+(?:\.\d+)?[eE][+-]?\d+', s_clean):
                d = Decimal(s_clean)
                s_clean = format(d, 'f').rstrip('0').rstrip('.')
                return s_clean
            # si ya son solo dígitos, devolver tal cual
            if re.fullmatch(r'\d+', s_clean):
                return s_clean
        except Exception:
            # ante cualquier cosa rara, devuelve lo que venga
            return s_clean
        return s_clean

    # duracion -> si es numérica (segundos) => HH:MM:SS; si ya trae "HH:MM[:SS]" se deja
    if col == "duracion":
        if ":" in s:
            return s
        f = _a_float(val)
        if f is None:
            return s
        f = int(round(f))
        h = f // 3600
        m = (f % 3600) // 60
        sec = f % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    # default: como string
    return s


# Backwards compatibility alias
formatear_valor_para_burbuja = _formatear_valor_para_burbuja