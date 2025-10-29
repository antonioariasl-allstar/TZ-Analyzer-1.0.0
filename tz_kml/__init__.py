"""
tz_kml - Paquete de Generación KML/KMZ

Sprint 2: Extracción segura del KML/KMZ a tz_kml
Enfoque conservador, cero regresiones, compatibilidad 100%

Módulos:
- builder.py: Fachada pública principal (build_kml)
- styles.py: Paletas, iconos, tamaños, configuración visual  
- placemarks.py: Puntos, burbujas, nombres (Fase 2.2)
- folders.py: Carpetas global/por día/top/por rango (Fase 2.2)
- kmz.py: Empaquetado KMZ (Fase 2.3)

Fecha: 29 octubre 2025
"""

__version__ = "2.0.0"
__author__ = "Omar Arias (Tony Zero)"

# Exports principales (se irán agregando por fases)
from .builder import build_kml, generate_kml
from .styles import create_styles, hex_to_abgr
from .placemarks import create_feature, create_point, compact_antenna_name
from .folders import create_folder_hierarchy, create_root_folder, create_date_folders, create_range_folders, create_top_folders, get_date_folder, classify_time_range
from .kmz import save_kml_kmz, save_kml_only, save_kmz_only, save_flat_mode, save_folder_mode, get_kmz_path, is_solo_kmz_enabled, validate_kml_path, get_file_sizes

__all__ = [
    # Fase 2.1 - Fachada principal + estilos
    'build_kml',
    'generate_kml', 
    'create_styles',
    'hex_to_abgr',
    
    # Fase 2.2 - Placemarks completado
    'create_feature',
    'create_point', 
    'compact_antenna_name',
    
    # Fase 2.2 - Folders completado
    'create_folder_hierarchy',
    'create_root_folder',
    'create_date_folders', 
    'create_range_folders',
    'create_top_folders',
    'get_date_folder',
    'classify_time_range',
    
    # Fase 2.3 - KMZ Packaging completado
    'save_kml_kmz',
    'save_kml_only',
    'save_kmz_only', 
    'save_flat_mode',
    'save_folder_mode',
    'get_kmz_path',
    'is_solo_kmz_enabled',
    'validate_kml_path',
    'get_file_sizes'
]