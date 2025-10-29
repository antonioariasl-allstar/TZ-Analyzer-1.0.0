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

__all__ = [
    # Fase 2.1 - Fachada principal + estilos
    'build_kml',
    'generate_kml', 
    'create_styles',
    'hex_to_abgr',
    
    # Fase 2.2 (pendiente)
    # 'create_placemarks',
    # 'create_folders',
    
    # Fase 2.3 (pendiente)  
    # 'create_kmz'
]