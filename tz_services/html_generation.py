"""
tz_services.html_generation - Generación de contenido HTML

Sprint 1 Fase 1.1: Estructura base 
Sprint 1 Fase 1.3: Migración de funciones HTML (pendiente)

Funciones a migrar:
- _build_logo_html (L3198) - 22 líneas - SAFE
- render_heatmap_html_for_day (L2193) - 157 líneas - COMPLEX

Fecha: 29 octubre 2025
"""

import base64
from typing import Dict, Any, Optional

def build_logo_html(logo_path: Optional[str] = None) -> str:
    """
    Placeholder para build_logo_html.
    
    Se implementará en Sprint 1 Fase 1.3
    
    Args:
        logo_path: Ruta opcional al logo
        
    Returns:
        HTML del logo
    """
    # TODO: Implementar en Fase 1.3
    return '<div class="logo-placeholder">Logo TZ-Analyzer</div>'


def render_heatmap_html_for_day(data: Dict[str, Any], config: Dict[str, Any]) -> str:
    """
    Placeholder para render_heatmap_html_for_day.
    
    Se implementará en Sprint 1 Fase 1.3
    
    Args:
        data: Datos del heatmap
        config: Configuración
        
    Returns:
        HTML del heatmap
    """
    # TODO: Implementar en Fase 1.3 (COMPLEX - 157 líneas)
    return '<div class="heatmap-placeholder">Heatmap para día</div>'