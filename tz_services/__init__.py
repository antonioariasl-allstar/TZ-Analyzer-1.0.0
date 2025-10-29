"""
tz_services - Servicios de validación y generación de reportes

Este paquete contiene funciones puras extraídas del monolito TZ-Analyzer:
- validation.py: Funciones de validación de datos
- html_generation.py: Generación de contenido HTML

Sprint 1 - Fase 1.1: Extracción inicial de 18 funciones
Fecha: 29 octubre 2025
"""

# Imports públicos para facilitar el uso
from .validation import (
    validar_columnas,
    validar_datos,
    valid_latlon_vals,
    es_valida_latlon_row,
    first_valid_geo,
    valida_formato_hora,
    valida_fecha_parsible,
    valida_latlon,
    validate_schema_or_abort
)

from .html_generation import (
    build_logo_html,
    render_heatmap_html_for_day
)

__version__ = "1.0.0-sprint1"
__author__ = "TZ-Analyzer Refactoring Team"

# Funciones principales para API pública
__all__ = [
    # Validación
    'validar_columnas',
    'validar_datos', 
    'valid_latlon_vals',
    'es_valida_latlon_row',
    'validate_schema_or_abort',
    
    # HTML Generation
    'build_logo_html',
    'render_heatmap_html_for_day'
]
