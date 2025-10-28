"""
TZ Core - Módulo central de TZ Analyzer
Arquitectura modular para análisis forense de datos de telecomunicaciones

Módulos disponibles (ACTIVOS):
- utils: Utilidades comunes y helpers
- config_manager: Gestión de configuración y mapeo
- data_loader: Carga de datos Excel/TSV/CSV
- html_generator: Generación de reportes HTML (híbrido)
- time_utils: Utilidades de tiempo (NUEVO - funciones puras)

NOTA: Esqueletos removidos para claridad (data_validator, data_processor, 
kml_generator, ui_helpers). Funcionalidad activa en archivos raíz.
"""

__version__ = "2.0.0"
__author__ = "Omar Arias (Tony Zero)"

# Imports principales (se irán agregando según se extraigan módulos)
# from .utils import *
# from .config_manager import ConfigManager
# from .data_loader import DataLoader
# from .data_validator import DataValidator
# from .data_processor import AnalysisEngine
# from .kml_generator import KMLGenerator
# from .html_generator import HTMLReportGenerator
# from .ui_helpers import UIWizards

# time_utils - Funciones de tiempo extraídas para modularización
from .time_utils import (
    hhmmss_to_time_or_none,
    en_rango_tiempo,
    clasificar_rango_sv,
    parse_hhmmss_to_minutes,
    minutes_from_any,
    etiqueta_rango,
    RANGOS_SV,
    # Aliases para compatibilidad hacia atrás
    _hhmmss_to_time_or_none,
    _en_rango,
    _clasificar_rango_sv,
    _parse_hhmmss_to_minutes,
    _minutes_from_any,
    _construir_rangos_cfg,
    _en_rango_minutos
)