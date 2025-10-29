"""
tz_services.html_generation - Generación de contenido HTML

Sprint 1 Fase 1.1: Estructura base 
Sprint 1 Fase 1.3: Migración de funciones HTML

Funciones migradas:
- build_logo_html (extraída de _build_logo_html L3119) - COMPLETADA
- render_heatmap_html_for_day (L2193) - PENDIENTE

Fecha: 29 octubre 2025
"""

import base64
import os
import mimetypes
from typing import Dict, Any, Optional


def build_logo_html(config: Optional[Dict[str, Any]] = None, script_dir: Optional[str] = None) -> str:
    """
    Genera HTML para logo embebido en base64 o SVG fallback.
    
    Extraído de _build_logo_html (L3119-L3183) script_principal_bitacoras_refactory.py
    
    Args:
        config: Diccionario de configuración (equivalente a CONFIG global)
        script_dir: Directorio base del script (equivalente a __file__)
        
    Returns:
        str: HTML del logo como <img> tag con base64 o SVG inline
        
    Funcionalidades:
    - Intenta usar base64 desde config primero
    - Busca archivos logo comunes (logo_tz.png, Logo TZ.png, etc.)
    - Fallback a SVG inline accesible si no encuentra archivos
    """
    # Config y atributos visibles
    _br_all = config or {}
    _brand = _br_all.get('brand', {}) or {}
    _branding = _br_all.get('branding', {}) or {}

    # Alt y ancho deseado
    _alt = (
        str((_branding.get('logo_alt') or '')).strip()
        or str(((_brand.get('logo') or {}).get('alt') or '')).strip()
        or str(_brand.get('name') or 'TZ Analyzer').strip()
    )
    try:
        _w = int(((_brand.get('logo') or {}).get('width_px') or 120))
    except Exception:
        _w = 120

    # 1) Si en config viene un base64 directo, úsalo
    _b64_cfg = _branding.get('logo_base64') or (_brand.get('logo') or {}).get('base64')
    if isinstance(_b64_cfg, str) and _b64_cfg.strip():
        b64 = _b64_cfg.strip()
        if b64.startswith('data:'):
            src = b64
        else:
            # asumir PNG por defecto
            src = f"data:image/png;base64,{b64}"
        return f'<img src="{src}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'

    # 2) Intentar archivo local si la ruta existe (robusto, nombres candidatos)
    _script_dir = script_dir or os.getcwd()
    _candidates = []
    # a) paths declarados en config
    for key_path in [(_branding.get('logo_path') or ''), (((_brand.get('logo') or {}).get('path')) or '')]:
        p = str(key_path or '').strip()
        if p:
            _candidates.append(p)
    # b) candidatos comunes (soporta el caso "Logo TZ.png")
    _candidates.extend([
        'logo_tz.png', 'Logo TZ.png', 'Logo_TZ.png', 'logo.png', 'logo.svg', 'Logo.png', 'Logo.svg'
    ])

    for rel in _candidates:
        try:
            p_abs = rel if os.path.isabs(rel) else os.path.join(_script_dir, rel)
            if os.path.exists(p_abs) and os.path.isfile(p_abs):
                mime, _ = mimetypes.guess_type(p_abs)
                mime = mime or ('image/svg+xml' if p_abs.lower().endswith('.svg') else 'image/png')
                with open(p_abs, 'rb') as fh:
                    data = fh.read()
                b64 = base64.b64encode(data).decode('ascii')
                return f'<img src="data:{mime};base64,{b64}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'
        except Exception:
            continue

    # 3) Fallback: SVG inline accesible (sin archivos)
    _svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{_w}' height='{int(_w*0.38)}' viewBox='0 0 320 120' role='img' aria-label='{_alt}'>"
        "<rect width='320' height='120' fill='#0B57D0' rx='12'/>"
        "<text x='50%' y='53%' dominant-baseline='middle' text-anchor='middle' font-family='Segoe UI, Roboto, Arial, sans-serif' font-size='40' fill='white' font-weight='700'>TZ Analyzer</text>"
        "</svg>"
    )
    svg_uri = "data:image/svg+xml;utf8," + _svg.replace("\n", "")
    return f"<img src='{svg_uri}' alt='{_alt}' style='height:{_w}px;max-height:{_w}px'/>"


def render_heatmap_html_for_day(data: Dict[str, Any], config: Dict[str, Any]) -> str:
    """
    Genera HTML de heatmap para un día específico.
    
    MIGRADO A: tz_services.heatmap.build_heatmap_html()
    
    Args:
        data: Datos del heatmap con DataFrame
        config: Configuración de columnas y parámetros
        
    Returns:
        HTML del heatmap con mapas Leaflet.js
        
    Migración Sprint 2B Fase 2B.2:
    - Extracción completa de render_heatmap_html_for_day
    - Fachada temporal build_heatmap_html()
    - Template HTML modularizado
    """
    from tz_services.heatmap import build_heatmap_html
    
    df_day = data.get("dataframe")
    day_id = data.get("day_id", "unknown")
    
    return build_heatmap_html(df_day, day_id, config)