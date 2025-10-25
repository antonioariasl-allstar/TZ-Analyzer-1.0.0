"""
tz_core.config_manager - Gestión de configuración del sistema
Manejo de archivos de configuración, sinónimos y mapeo de columnas
"""

import json
import os
import sys
from typing import Dict, Any


# Configuración por defecto del sistema
DEFAULT_CONFIG = {
    "kml": {
        "azimuth_km": 1.5,
        "cone": {"half_degrees": 35, "fill_color": "7fffffff"},
        "line": {"color": "ffff00ff", "width": 5},
        "description": [
            # Bloque 2: Tel + identidad (incluye Alias; etiqueta Usuario)
            [["Tel","tel"], ["IMEI","imei"], ["Alias","alias"], ["Nombre de Usuario","nombre_usuario"], ["Abonado","abonado"]],
            # Bloque 3: datos de antena/posiciones
            [["Antena","antena"], ["Detalle","detalle"], ["Lat","lat"], ["Long","long"], ["Azimut","azimut"], ["Celda","celda"], ["LAC","lac"]],
            # Bloque 4: interacción + duración
            [["Interacción","interaccion"], ["Duración","duracion"]]
        ]
    }
}


def cargar_config() -> Dict[str, Any]:
    """
    Carga la configuración global desde config.json.
    
    NOTA TÉCNICA: Esta función maneja un sistema híbrido de sinónimos:
    - 'synonyms': Legacy del mapeo automático (posiblemente excesivos)
    - 'synonyms_user': Memoria de mapeos manuales (crece automáticamente)
    
    CONSIDERACIÓN FUTURA: La memoria automática (synonyms_user) podría 
    desactivarse ya que el mapeo actual es completamente manual.
    
    Compatible con PyInstaller (detecta sys.frozen y usa sys._MEIPASS).

    Returns:
        dict: Diccionario de configuración global con merge de defaults
        
    Raises:
        None: Siempre retorna DEFAULT_CONFIG en caso de error
    """
    # Detecta base_path según modo de ejecución (normal vs PyInstaller)
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        # Ajustar ruta para tz_core (subir un nivel)
        base = os.path.dirname(base)
    
    ruta_cfg = os.path.join(base, "config.json")
    
    try:
        with open(ruta_cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Merge superficial con defaults
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data or {})
        
        # Merge profundo de sección kml
        if "kml" in data:
            cfg["kml"].update(data["kml"])
        
        # Blindaje: asegurar que 'Alias' aparezca en el bloque 2 de la descripción
        try:
            desc = cfg["kml"]["description"]
            if isinstance(desc, list) and len(desc) >= 2:
                bloque2 = desc[1]  # Tel/IMEI/…
                if isinstance(bloque2, list):
                    etiquetas = [etq for etq, _ in bloque2 if isinstance(etq, str)]
                    if "Alias" not in etiquetas:
                        # Insertar después de IMEI (posición 2)
                        bloque2.insert(2, ["Alias", "alias"])
        except Exception:
            # Fallo en blindaje no es crítico
            pass
        
        return cfg
        
    except Exception:
        # En caso de cualquier error, retornar configuración por defecto
        return DEFAULT_CONFIG


# =====================================
# TODO: Extraer más funciones de configuración aquí:
# - cfg_build_rename_map()
# - cfg_add_user_synonym() 
# - get_config()
# ====================================
    
    def add_user_synonym(self, key, synonym):
        """Agregar sinónimo definido por usuario"""
        pass

# TODO: Extraer del script principal:
# - bootstrap_config()
# - cargar_config()
# - cfg_build_rename_map()
# - cfg_add_user_synonym()
# - _normalize_key_for_synonyms()
# - _atomic_write_json()