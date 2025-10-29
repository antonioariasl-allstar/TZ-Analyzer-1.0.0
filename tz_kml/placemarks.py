"""
tz_kml.placemarks - Creación de Features KML

Funciones para crear puntos, líneas, conos y burbujas en archivos KML.
Extracción de _crear_feature_kml del monolito con dependencias adaptadas.

Sprint 2 Fase 2.2: Placemarks + burbujas
Compatibilidad 100% con output KML existente

Funciones:
- create_feature: Crea punto KML con línea azimut y cono opcional
- create_point: Crea solo punto KML sin azimut
- compact_antenna_name: Compacta nombres de antenas para KML

Fecha: 29 octubre 2025
"""

import math
import re
from typing import Dict, Any, Optional
import simplekml as sk


def compact_antenna_name(nombre_punto: str, max_chars: int = 45, max_words: int = 5, prefer_before: int = 3) -> str:
    """
    Compacta nombre de antena para visualización en KML.
    
    Extraído de compactar_nombre_antena_kml (L943-972) script_principal_bitacoras_refactory.py
    
    Args:
        nombre_punto: Nombre original de la antena
        max_chars: Máximo caracteres permitidos (default 45)
        max_words: Máximo palabras si no hay comas (default 5)
        prefer_before: Preferir elementos antes de coma (default 3)
        
    Returns:
        str: Nombre compactado para KML
        
    Estrategia:
    - Si hay comas: toma primeros elementos hasta prefer_before
    - Si no hay comas: toma primeras palabras hasta max_words
    - Trunca con "..." si excede max_chars
    """
    if not nombre_punto or not isinstance(nombre_punto, str):
        return ""
    
    nombre = nombre_punto.strip()
    if len(nombre) <= max_chars:
        return nombre
    
    # Stopwords para filtrar palabras irrelevantes
    stopwords = {"de", "del", "la", "el", "en", "y", "a", "con", "por", "para", "un", "una"}
    
    if ',' in nombre:
        secciones = [s.strip() for s in nombre.split(',') if s.strip()]
        if len(secciones) >= prefer_before:
            parte = ", ".join(secciones[:prefer_before])
        else:
            parte = ", ".join(secciones)
    else:
        palabras = [w for w in re.split(r'\\s+', nombre) if w and w.lower() not in stopwords]
        parte = " ".join(palabras[:max_words])
    
    if len(parte) > max_chars:
        return parte[:max(0, max_chars-3)] + "..."
    return parte


def _fix_id_line(s: str) -> str:
    """
    Normaliza líneas de ID (TEL/IMEI) quitando .0 al final de números.
    
    Extraído de _fix_id_line (L1011-1031) script_principal_bitacoras_refactory.py
    """
    if ("<b>IMEI" in s) or ("<b>Número" in s) or ("<b>Numero" in s):
        return re.sub(r'(\\d+)\\.0\\b', r'\\1', s)
    return s


def _create_reusable_styles(config: Dict[str, Any]) -> Dict[str, sk.Style]:
    """
    Crea estilos reutilizables para KML (optimización de tamaño).
    
    Args:
        config: Diccionario de configuración (CONFIG global)
        
    Returns:
        Dict con estilos {"pin": Style, "line": Style, "cone": Style}
    """
    # Importar funciones de color desde tz_core
    try:
        from tz_core.color_utils import hex_to_kml_color
    except ImportError:
        # Fallback si no está disponible
        def hex_to_kml_color(hex_rgb: str, alpha: int = 255) -> str:
            if not hex_rgb or not hex_rgb.startswith('#'):
                return "ff0000ff"  # rojo por defecto
            try:
                hex_clean = hex_rgb[1:]
                if len(hex_clean) == 6:
                    r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
                    alpha_hex = format(alpha, '02x')
                    return f"{alpha_hex}{b}{g}{r}"  # ABGR
                return "ff0000ff"
            except Exception:
                return "ff0000ff"
    
    style_cfg = config.get("style", {}) if isinstance(config, dict) else {}
    theme_hex = style_cfg.get("theme_hex", "#ff00ff")
    pin_icon_url = style_cfg.get("pin_icon_url", "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png")
    pin_scale = float(style_cfg.get("pin_scale", 1.1))
    label_scale = float(style_cfg.get("label_scale", 1.2))
    line_width = float(style_cfg.get("line_width", 5))
    line_abgr = style_cfg.get("line_abgr", None)
    cone_opac = float(style_cfg.get("cone_opacity", 0.35))

    # Colores KML (AABBGGRR)
    pin_color = hex_to_kml_color(theme_hex, 255)
    line_color = line_abgr if line_abgr else hex_to_kml_color(theme_hex, 255)
    cone_color = hex_to_kml_color(theme_hex, int(max(0, min(1.0, cone_opac)) * 255))

    # Estilo del PIN
    s_pin = sk.Style()
    s_pin.iconstyle.color = pin_color
    s_pin.iconstyle.scale = pin_scale
    s_pin.iconstyle.icon.href = pin_icon_url
    s_pin.labelstyle.color = pin_color
    s_pin.labelstyle.scale = label_scale

    # Estilo de la LÍNEA
    s_line = sk.Style()
    s_line.linestyle.color = line_color
    s_line.linestyle.width = line_width

    # Estilo del CONO (polígono)
    s_cone = sk.Style()
    s_cone.polystyle.color = cone_color
    s_cone.polystyle.fill = 1
    s_cone.polystyle.outline = 1

    return {"pin": s_pin, "line": s_line, "cone": s_cone}


def create_feature(container, nombre_punto: str, lon: float, lat: float, 
                  descripcion: Optional[str], azimut_float: Optional[float], 
                  config: Dict[str, Any], azimuts_extra: Optional[list] = None) -> None:
    """
    Crea feature KML completo: punto + línea azimut + cono.
    
    Extraído de _crear_feature_kml (L943-1100) script_principal_bitacoras_refactory.py
    
    Args:
        container: Contenedor KML donde agregar el feature (Folder o Kml)
        nombre_punto: Nombre de la antena
        lon: Longitud
        lat: Latitud  
        descripcion: HTML para burbuja popup
        azimut_float: Azimut en grados (puede ser None)
        config: Diccionario de configuración (CONFIG global)
        azimuts_extra: Lista de azimuts adicionales (no implementado)
        
    Funcionalidades:
    - Crea punto con icono y etiqueta coloreada
    - Si hay azimut: dibuja línea y cono direccional
    - Normaliza descripción (quita líneas vacías, corrige IDs)
    - Usa estilos reutilizables para optimizar KML
    """
    # Cache global de estilos para optimización
    if not hasattr(create_feature, '_reusable_styles'):
        create_feature._reusable_styles = _create_reusable_styles(config)
    
    styles = create_feature._reusable_styles
    
    # Usar nombre compacto para visualización en mapa
    nombre_compacto = compact_antenna_name(nombre_punto) if nombre_punto else ""
    
    # Normalizar descripción
    if descripcion:
        try:
            parts = re.split(r'<br\\s*/?>', str(descripcion))
            
            # 1) Omitir líneas vacías / marcadores
            parts = [
                p for p in parts
                if p and p.strip() and not any(tok in p for tok in (
                    "> SinInf", "> Sin Inf.", "> None", "> nan", "> NaN"
                ))
            ]
            
            # 2) Normalizar IDs (TEL/IMEI): quitar .0 al final del número
            parts = [_fix_id_line(p) for p in parts]
            descripcion = "<br>".join(parts)
        except Exception:
            pass
    
    # Validar azimut
    try:
        az = float(azimut_float) if azimut_float is not None else float("nan")
    except Exception:
        az = float("nan")
    
    if not (isinstance(az, float) and math.isnan(az)):
        # Normalizar azimut a [0, 360)
        az = az % 360.0
    
    # ---------- 1) Crear el punto ----------
    p = container.newpoint(name=nombre_compacto, coords=[(lon, lat)])
    if descripcion:
        p.description = f'<div style="line-height:1.10; font-size:14px">{descripcion}</div>'
    p.style = styles["pin"]
    
    # ---------- 2) Si hay azimut válido, dibujar LÍNEA y CONO ----------
    if not (isinstance(az, float) and math.isnan(az)):
        # Importar función de cálculo geográfico
        try:
            from tz_core.geo_utils import calcular_punto_final
        except ImportError:
            try:
                from kml_generador import calcular_punto_final
            except ImportError:
                # Fallback básico de cálculo geográfico
                def calcular_punto_final(lat: float, lon: float, azimut: float, distancia_km: float):
                    """Cálculo básico de punto final dados azimut y distancia"""
                    import math
                    R = 6371.0  # Radio de la Tierra en km
                    lat_rad = math.radians(lat)
                    lon_rad = math.radians(lon)
                    az_rad = math.radians(azimut)
                    
                    lat_final_rad = math.asin(
                        math.sin(lat_rad) * math.cos(distancia_km / R) +
                        math.cos(lat_rad) * math.sin(distancia_km / R) * math.cos(az_rad)
                    )
                    
                    lon_final_rad = lon_rad + math.atan2(
                        math.sin(az_rad) * math.sin(distancia_km / R) * math.cos(lat_rad),
                        math.cos(distancia_km / R) - math.sin(lat_rad) * math.sin(lat_final_rad)
                    )
                    
                    return math.degrees(lat_final_rad), math.degrees(lon_final_rad)
        
        # Distancia y ángulo del cono (defaults si CONFIG no especifica)
        try:
            az_dist_km = config.get("kml", {}).get("azimuth_km", 1.5)
            cone_half = config.get("kml", {}).get("cone", {}).get("half_degrees")
            if cone_half is None:
                cone_half = config.get("style", {}).get("cone_half_degrees", 35)
        except Exception:
            az_dist_km = 1.5
            cone_half = 35
        
        # Calcular punto final de la línea de azimut
        latf, lonf = calcular_punto_final(lat, lon, az, float(az_dist_km))
        
        # LÍNEA
        linea = container.newlinestring(
            name=f"Azimut {int(round(az))}°",
            coords=[(lon, lat), (lonf, latf)]
        )
        linea.style = styles["line"]
        
        # CONO (polígono)
        coords_cono = []
        paso = 5
        for ang in range(-int(cone_half), int(cone_half) + 1, paso):
            lat_p, lon_p = calcular_punto_final(lat, lon, az + ang, float(az_dist_km))
            coords_cono.append((lon_p, lat_p))
        coords_cono.append((lon, lat))
        pol = container.newpolygon(name=f"Cono Azimut {int(round(az))}°")
        pol.outerboundaryis = coords_cono
        pol.style = styles["cone"]


def create_point(container, nombre_punto: str, lon: float, lat: float, 
                descripcion: Optional[str], config: Dict[str, Any]) -> None:
    """
    Crea solo un punto KML sin azimut (versión simplificada).
    
    Args:
        container: Contenedor KML donde agregar el punto
        nombre_punto: Nombre de la antena
        lon: Longitud
        lat: Latitud
        descripcion: HTML para burbuja popup
        config: Diccionario de configuración
    """
    create_feature(container, nombre_punto, lon, lat, descripcion, None, config)