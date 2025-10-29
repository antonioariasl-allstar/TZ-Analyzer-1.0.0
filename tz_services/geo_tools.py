"""
tz_services.geo_tools - UTILIDADES GEOGRÁFICAS PURAS
==================================================

✅ ESTADO: MIGRACIÓN DESDE MONOLITO - FUNCIONES MATEMÁTICAS PURAS
🎯 PROPÓSITO: Cálculos geográficos y generación de geometrías KML
📍 DIFERENCIACIÓN: Matemáticas puras sin dependencias de UI o configuración

RESPONSABILIDADES ESPECÍFICAS:
- grados_a_radianes(): Conversión angular básica
- calcular_punto_final(): Navegación geodésica (gran círculo)
- generar_cono(): Generación de polígonos KML direccionales

DEPENDENCIAS:
- math: Cálculos trigonométricos
- simplekml: Generación de elementos KML

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 1113-1150
FECHA MIGRACIÓN: 27 octubre 2025
"""

import math
from typing import Tuple
try:
    from simplekml import Kml
except ImportError:
    # Para tests sin simplekml instalado
    Kml = None

def grados_a_radianes(grados: float) -> float:
    """Convierte grados a radianes.
    
    Args:
        grados: Ángulo en grados decimales
        
    Returns:
        float: Ángulo en radianes
    """
    return grados * math.pi / 180.0

def calcular_punto_final(lat: float, lon: float, azimut: float, distancia_km: float) -> Tuple[float, float]:
    """Calcula el punto final moviéndose una distancia desde coordenadas iniciales con rumbo específico.
    
    Utiliza fórmulas de navegación por gran círculo para cálculo geodésico preciso.
    
    Args:
        lat: Latitud inicial en grados decimales
        lon: Longitud inicial en grados decimales
        azimut: Rumbo en grados (0° = Norte, 90° = Este)
        distancia_km: Distancia a recorrer en kilómetros
        
    Returns:
        Tuple[float, float]: (latitud_final, longitud_final) en grados decimales
    """
    R = 6371.0  # Radio terrestre en km (WGS84 aproximado)
    
    lat_rad = grados_a_radianes(lat)
    lon_rad = grados_a_radianes(lon)
    azimut_rad = grados_a_radianes(azimut)

    lat_final = math.asin(
        math.sin(lat_rad) * math.cos(distancia_km / R)
        + math.cos(lat_rad) * math.sin(distancia_km / R) * math.cos(azimut_rad)
    )
    lon_final = lon_rad + math.atan2(
        math.sin(azimut_rad) * math.sin(distancia_km / R) * math.cos(lat_rad),
        math.cos(distancia_km / R) - math.sin(lat_rad) * math.sin(lat_final)
    )
    
    return math.degrees(lat_final), math.degrees(lon_final)

def generar_cono(kml, lat: float, lon: float, azimut: float, distancia_km: float, 
                angulo_lateral: int, color: str):
    """Genera un polígono tipo 'cono' direccional en KML.
    
    Crea un polígono triangular que representa la cobertura direccional de una antena,
    centrado en las coordenadas especificadas y abierto hacia el azimut dado.
    
    Args:
        kml: Objeto KML donde agregar el polígono
        lat: Latitud del vértice del cono en grados decimales
        lon: Longitud del vértice del cono en grados decimales
        azimut: Dirección central del cono en grados (0° = Norte)
        distancia_km: Alcance del cono en kilómetros
        angulo_lateral: Apertura lateral del cono en grados (±)
        color: Color del polígono en formato KML (AABBGGRR)
        
    Returns:
        None: Modifica el objeto KML directamente
        
    Raises:
        ImportError: Si simplekml no está disponible
    """
    if Kml is None:
        raise ImportError("simplekml requerido para generar_cono")
        
    poligono = kml.newpolygon(name=f"Cono Azimut {azimut}°")
    
    # Punto central (vértice del cono)
    coords = [(lon, lat)]
    
    # Calcular puntos del arco
    for i in range(-angulo_lateral, angulo_lateral + 1, 5):  # Cada 5 grados
        azimut_actual = azimut + i
        lat_punto, lon_punto = calcular_punto_final(lat, lon, azimut_actual, distancia_km)
        coords.append((lon_punto, lat_punto))
    
    # Cerrar el polígono volviendo al centro
    coords.append((lon, lat))
    
    poligono.outerboundaryis = coords
    poligono.style.polystyle.color = color
    poligono.style.polystyle.fill = 1
    poligono.style.polystyle.outline = 1
    poligono.style.linestyle.color = color
    poligono.style.linestyle.width = 2