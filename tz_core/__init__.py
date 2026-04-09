"""
TZ Core - Módulo central de TZ Analyzer
Arquitectura modular para análisis forense de datos de telecomunicaciones

Módulos disponibles (ACTIVOS):
- utils: Utilidades comunes y helpers
- config_manager: Gestión de configuración y mapeo
- data_loader: Carga de datos Excel/TSV/CSV
- html_generator: Generación de reportes HTML (híbrido)
- time_utils: Utilidades de tiempo (funciones puras)
- validation_utils: Utilidades de validación (NUEVO - funciones puras)

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
    to_datetime_series,
    format_seconds_hms,
    RANGOS_SV,
)

# dataframe_utils
from .dataframe_utils import (
    dedupe_columns,
    pick_first_existing_column,
    coalesce_duplicates,
    apply_schema_renames,
    _pick_col,
)

# validation_utils - Funciones de validación extraídas para modularización
from .validation_utils import (
    tiene_valor,
    es_num,
    a_float,
    es_vacio_o_nulo,
    normalizar_numero,
    es_entero_valido,
    limpiar_texto_validacion,
)

# ui_utils - Funciones de interfaz de usuario extraídas para modularización
from .ui_utils import (
    solicitar_overrides_topn,
    # Aliases para compatibilidad hacia atrás
    _solicitar_overrides_topn
)

# text_utils - Funciones de procesamiento de texto extraídas para modularización  
from .text_utils import (
    _fix_mojibake_text,
    _aplicar_reemplazos_regex,
    normalizar_texto,
    normalizar_columnas_texto,
    normalize_header_key,
    _norm_head,
)

# schema_utils - Helpers de schema/sinónimos
from .schema_utils import (
    build_schema_synonym_map,
    has_location_coverage,
    collect_missing_required_fields,
    prep_meta_unicos,
    ensure_placeholder_columns,
    preview_column_mapping,
    confirm_column_mapping_with_preview,
    _muestras_columna,
    _es_numero,
    _en_bbox_sv,
    _es_columna_valida_para,
)

# time_filters - Helpers interactivos para filtros temporales
from .time_filters import (
    solicitar_filtros_tiempo,
    aplicar_filtros_tiempo,
)

# runtime_utils - Metadata del entorno de ejecucion
from .runtime_utils import collect_env_snapshot

# html_generator - Helpers de HTML
# html_generator - Compatibilidad legacy (implementación en tz_core.html.*)
from .html.antennas import (
    resolve_top_antennas_n,
    build_top_antennas_section,
    build_antennas_by_hour_section,
)
