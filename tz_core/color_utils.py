"""
tz_core.color_utils - UTILIDADES DE MANEJO DE COLORES
======================================================

✅ ESTADO: MIGRACIÓN DESDE MONOLITO - FUNCIONES DE COLOR PURAS
🎯 PROPÓSITO: Conversión y manipulación de colores para KML y HTML
📍 DIFERENCIACIÓN: Funciones matemáticas puras sin dependencias de UI

RESPONSABILIDADES ESPECÍFICAS:
- hex_to_kml_color(): Conversión HEX → KML AABBGGRR format
- color_mock(): Mock function para testing sin interacción
- Soporte para formatos cortos (#RGB → #RRGGBB)

DEPENDENCIAS:
- Ninguna: Solo Python estándar

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 1074-1095, 6386, 1674-1685
FECHA MIGRACIÓN: 27 octubre 2025
"""

from typing import Dict, Any


def hex_to_kml_color(hex_rgb: str, alpha: int = 255) -> str:
    """Convierte '#RRGGBB' o 'RRGGBB' a 'aabbggrr' (formato KML).
    
    Args:
        hex_rgb: Color en formato hexadecimal (#RRGGBB, RRGGBB, o #RGB)
        alpha: Transparencia 0-255 (0=transparente, 255=opaco)
        
    Returns:
        str: Color en formato KML 'aabbggrr' (8 caracteres hex lowercase)
        
    Examples:
        >>> hex_to_kml_color("#ff0000")  # rojo
        'ffff0000'
        >>> hex_to_kml_color("#00ff00", alpha=128)  # verde semi-transparente  
        '8000ff00'
        >>> hex_to_kml_color("#abc")  # formato corto
        'ffccbbaa'
    """
    s = (hex_rgb or "").strip().lstrip("#")
    
    # Soporta formato corto #RGB → #RRGGBB
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    
    if len(s) != 6:
        # Fallback seguro (blanco opaco)
        return "ffffffff"
    
    try:
        a = max(0, min(255, int(alpha)))
    except Exception:
        a = 255
    
    rr, gg, bb = s[0:2], s[2:4], s[4:6]
    # KML format = AABBGGRR (nota: orden BGR)
    return f"{a:02x}{bb}{gg}{rr}".lower()


def color_mock(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Mock function para testing que bypassa selección interactiva de color.
    
    Args:
        cfg: Configuración a retornar sin modificaciones
        
    Returns:
        Dict: La misma configuración recibida (passthrough)
        
    Note:
        Usado en tests automatizados para evitar prompts interactivos.
        Preserva la configuración existente sin solicitar color al usuario.
    """
    return cfg


# Alias para compatibilidad con nombre original del monolito
_hex_to_kml_color = hex_to_kml_color
_color_mock = color_mock