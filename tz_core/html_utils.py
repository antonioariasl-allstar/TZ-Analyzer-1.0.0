"""
tz_core.html_utils - UTILIDADES MENORES PARA HTML
==================================================

✅ ESTADO: MIGRACIÓN ULTRA-CONSERVADORA - SOLO HELPERS SEGUROS
🎯 PROPÓSITO: Funciones auxiliares HTML pequeñas y matemáticamente puras
📍 DIFERENCIACIÓN: Helpers sin dependencias complejas, no toca motor principal

⚠️ NOTA CRÍTICA: 
El motor principal generar_informe_html() permanece en monolito por seguridad.
Otro agente intentó migración completa y causó problemas críticos.
Esta estrategia ultra-conservadora solo extrae helpers matemáticamente puros.

RESPONSABILIDADES ESPECÍFICAS:
- row_html(): Generador de filas HTML para tablas
- fmt_imei_item(): Formateo correcto de IMEI sin decimales  
- luhn_check(): Validación algoritmo Luhn para IMEI

DEPENDENCIAS:
- Ninguna: Solo Python estándar

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 3465, 3456, 3475
FECHA MIGRACIÓN: 27 octubre 2025
"""

from typing import List, Optional

from tz_core.bitacora_normalization import normalize_imei


def row_html(label: str, single: Optional[str], n: int, lst: List[str], 
             extra: int, mono: bool = False) -> str:
    """Genera una fila HTML para tabla con soporte para listas múltiples.
    
    Args:
        label: Etiqueta de la fila
        single: Valor único si n <= 1
        n: Número total de elementos
        lst: Lista de elementos a mostrar
        extra: Número de elementos adicionales no mostrados
        mono: Si usar fuente monoespaciada
        
    Returns:
        str: HTML de la fila (<tr>...</tr>) o cadena vacía si no hay datos
        
    Examples:
        >>> row_html("IMEI", "123456789012345", 1, [], 0)
        '<tr><td><b>IMEI:</b></td><td>123456789012345</td></tr>\\n'
        
        >>> row_html("Teléfonos", None, 3, ["555-1234", "555-5678"], 1)
        '<tr><td><b>Teléfonos:</b></td><td><ul class="list"><li>555-1234</li><li>555-5678</li><li>… y 1 más</li></ul></td></tr>\\n'
    """
    if n > 1 and lst:
        cls = 'list mono' if mono else 'list'
        items = "".join(f"<li>{v}</li>" for v in lst)
        more = f"<li>… y {extra} más</li>" if extra > 0 else ""
        return f"<tr><td><b>{label}:</b></td><td><ul class=\"{cls}\">{items}{more}</ul></td></tr>\n"
    elif single:
        return f"<tr><td><b>{label}:</b></td><td>{single}</td></tr>\n"
    else:
        return ""


def fmt_imei_item(x: str) -> str:
    """Formatea item IMEI eliminando decimales innecesarios (.0).
    
    Args:
        x: Valor a formatear (string representation)
        
    Returns:
        str: IMEI limpio sin decimales flotantes si era entero
        
    Examples:
        >>> fmt_imei_item("123456789012345.0")
        '123456789012345'
        >>> fmt_imei_item("abc123")
        'abc123'
    """
    normalized = normalize_imei(x)
    if normalized:
        return normalized
    try:
        f = float(str(x))
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return str(x)


def luhn_check(num: str) -> bool:
    """Valida IMEI de 15 dígitos usando algoritmo Luhn.
    
    Args:
        num: String numérico de 15 dígitos a validar
        
    Returns:
        bool: True si pasa validación Luhn, False en caso contrario
        
    Note:
        Algoritmo Luhn es estándar para validación de IMEI.
        Multiplica dígitos alternos por 2, suma todos, módulo 10 debe ser 0.
    """
    if not num or len(num) != 15 or not num.isdigit():
        return False
        
    s = 0
    parity = len(num) % 2
    for i, ch in enumerate(num):
        d = ord(ch) - 48  # int(ch) más rápido
        if (i % 2) == parity:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return (s % 10) == 0


# Aliases para compatibilidad con nombres originales del monolito
_row_html = row_html
_fmt_imei_item = fmt_imei_item
_luhn_check = luhn_check