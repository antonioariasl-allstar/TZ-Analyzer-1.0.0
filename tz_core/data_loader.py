"""
tz_core.data_loader - Carga de datos Excel/TSV/CSV
Manejo de diferentes formatos y hojas de Excel
"""

class DataLoader:
    """
    Cargador de datos para múltiples formatos
    
    Responsabilidades:
    - Lectura de Excel, TSV, CSV
    - Detección automática de formato
    - Selección de hojas en Excel
    - Validación de estructura básica
    """
    
    def __init__(self):
        """Inicializar cargador de datos"""
        pass
    
    def load_file(self, file_path, sheet_name=None):
        """Cargar archivo de datos"""
        pass
    
    def get_excel_sheets(self, file_path):
        """Obtener lista de hojas de Excel"""
        pass
    
    def detect_format(self, file_path):
        """Detectar formato de archivo"""
        pass
    
    def select_sheet_interactive(self, file_path):
        """Selección interactiva de hoja"""
        pass

# TODO: Extraer del script principal:
# - Funciones de lectura Excel/TSV/CSV
# - _obtener_hojas_visibles()
# - _seleccionar_hoja*()
# - _listar_todas_hojas()
# - Detección automática de formato