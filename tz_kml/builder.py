"""
tz_kml.builder - Fachada Principal de Generación KML

Punto de entrada único para toda la funcionalidad KML/KMZ.
Mantiene compatibilidad 100% con API existente.

Sprint 2 Fase 2.1: Fachada mínima + delegación a implementación existente
Fase 2.2+: Migración gradual de lógica de generación

Funciones:
- build_kml: Fachada principal compatible con generar_kml()

Fecha: 29 octubre 2025
"""

import os
from typing import Tuple, Dict, Any
import pandas as pd


def build_kml(df: pd.DataFrame, config: Dict[str, Any], output_path: str, *, flat: bool = False) -> Tuple[str, int]:
    """
    Fachada principal para generación KML/KMZ.
    
    Mantiene compatibilidad 100% con generar_kml() del monolito.
    En Fase 2.1 delega a implementación existente.
    En fases futuras migrará lógica a tz_kml.
    
    Args:
        df: DataFrame con datos procesados
        config: Diccionario de configuración (CONFIG global)
        output_path: Ruta de archivo KML de salida
        flat: Si True, estructura plana sin carpetas
        
    Returns:
        Tuple[str, int]: (archivo_kml_path, puntos_descartados)
        
    Compatibilidad:
        - Misma firma que generar_kml()
        - Misma estructura de salida KML/KMZ
        - Mismos estilos y configuración
        - Mismo conteo de placemarks
    """
    # FASE 2.1: Delegación directa a implementación existente
    # En fases futuras esto será reemplazado por lógica modular
    
    # Importar función original (evitar circular imports)
    import sys
    import importlib.util
    
    # Estrategia segura: usar la función del monolito
    from script_principal_bitacoras_refactory import generar_kml as generar_kml_monolito
    
    # Delegación directa preservando API
    return generar_kml_monolito(df, output_path, flat)


# Alias para compatibilidad con naming conventions
def generate_kml(df: pd.DataFrame, config: Dict[str, Any], output_path: str, *, flat: bool = False) -> Tuple[str, int]:
    """Alias en inglés para build_kml()"""
    return build_kml(df, config, output_path, flat=flat)