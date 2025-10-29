"""
tz_kml.styles - Gestión de Estilos KML/KMZ

Funciones extraídas de kml_generador.py para manejo de estilos,
colores, iconos y configuración visual de archivos KML.

Sprint 2 Fase 2.1: Extracción segura con compatibilidad 100%

Funciones:
- create_styles: Creación de estilos reutilizables (pins, líneas, etc.)
- hex_to_abgr: Conversión colores HEX a formato ABGR (Google Earth)

Fecha: 29 octubre 2025
"""

from simplekml import Style
from typing import Dict, Any


def hex_to_abgr(hex_color: str) -> str:
    """
    Convierte color HEX a formato ABGR para Google Earth.
    
    Extraído de kml_generador.py (líneas 22-30)
    
    Args:
        hex_color: Color en formato HEX (#RRGGBB)
        
    Returns:
        str: Color en formato ABGR para KML
        
    Example:
        >>> hex_to_abgr("#ff0000")
        'ff0000ff'
    """
    if not hex_color or not hex_color.startswith('#'):
        return "ff0000ff"  # rojo por defecto
    try:
        # Eliminar # y convertir HEX → ABGR
        hex_clean = hex_color[1:]
        if len(hex_clean) == 6:
            r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
            return f"ff{b}{g}{r}"  # ABGR con alpha=ff
        return "ff0000ff"
    except Exception:
        return "ff0000ff"


def create_styles(config: Dict[str, Any]) -> Dict[str, Style]:
    """
    Crea estilos reutilizables para KML (pins, líneas, etc.).
    
    Extraído de _crear_estilos_reusables() kml_generador.py (líneas 437-455)
    
    Args:
        config: Diccionario de configuración con estilos
        
    Returns:
        Dict[str, Style]: Diccionario con estilos {"pin": Style, "line": Style}
        
    Configuración soportada:
        config["style"]["theme_hex"]: Color tema principal (ej: "#ff0000")
        config["style"]["pin_scale"]: Escala del pin (default 1.2)
        config["style"]["label_scale"]: Escala de etiqueta (default 1.2)  
        config["style"]["line_abgr"]: Color línea ABGR (default "ffff00ff")
        config["style"]["line_width"]: Ancho línea (default 2)
    """
    theme_hex = (config or {}).get("style", {}).get("theme_hex", "#ff0000")
    label_color = hex_to_abgr(theme_hex)

    # Estilo del pin: ícono blanco con label coloreado
    pin_style = Style()
    pin_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png"
    pin_style.iconstyle.scale = float((config or {}).get("style", {}).get("pin_scale", 1.2))
    pin_style.labelstyle.color = label_color
    pin_style.labelstyle.scale = float((config or {}).get("style", {}).get("label_scale", 1.2))

    # Estilo de línea para azimut
    line_style = Style()
    line_style.linestyle.color = (config or {}).get("style", {}).get("line_abgr", "ffff00ff")  # magenta por defecto
    try:
        line_style.linestyle.width = float((config or {}).get("style", {}).get("line_width", 2))
    except Exception:
        line_style.linestyle.width = 2

    return {"pin": pin_style, "line": line_style}