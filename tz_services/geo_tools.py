"""
tz_services.geo_tools - Wrapper de compatibilidad
=================================================

✅ CANÓNICO: tz_core.geo_utils
🎯 PROPÓSITO: Reexportar funciones geográficas manteniendo compatibilidad

Este módulo solo delega en tz_core.geo_utils y conserva las mismas firmas
públicas para llamados existentes en tz_services.
"""

from tz_core.geo_utils import calcular_punto_final, generar_cono, grados_a_radianes

__all__ = [
    "grados_a_radianes",
    "calcular_punto_final",
    "generar_cono",
]