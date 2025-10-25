"""
tz_core.config_manager - Gestión de configuración y mapeo
Manejo de config.json, mapeo de columnas y sinónimos
"""

class ConfigManager:
    """
    Gestor de configuración para TZ Analyzer
    
    Responsabilidades:
    - Carga y validación de config.json
    - Gestión de sinónimos de columnas
    - Mapeo de campos por ISP
    - Persistencia de configuraciones
    """
    
    def __init__(self):
        """Inicializar gestor de configuración"""
        pass
    
    def load_config(self, config_path="config.json"):
        """Cargar configuración desde archivo"""
        pass
    
    def save_config(self, config_path="config.json"):
        """Guardar configuración a archivo"""
        pass
    
    def build_rename_map(self):
        """Construir mapa de renombrado de columnas"""
        pass
    
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