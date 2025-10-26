"""
tz_core.ui_helpers - Interfaz de usuario y wizards
Manejo de interacciones con el usuario y menús
"""

class UIWizards:
    """
    Manejador de interfaz de usuario y wizards
    
    Responsabilidades:
    - Menús principales de selección
    - Wizards de configuración
    - Selección de archivos
    - Validación de entrada de usuario
    - Mensajes y confirmaciones
    """
    
    def __init__(self):
        """Inicializar manejador de UI"""
        pass
    
    def show_main_menu(self):
        """Mostrar menú principal"""
        pass
    
    def select_file_dialog(self, title="Seleccionar archivo"):
        """Diálogo de selección de archivo"""
        pass
    
    def color_selection_wizard(self):
        """Wizard de selección de color"""
        pass
    
    def confirm_action(self, message):
        """Confirmación de acción"""
        pass
    
    def show_progress(self, message, progress=None):
        """Mostrar progreso de operación"""
        pass

# TODO: Extraer del script principal:
# - Wizards y menús
# - Funciones de input
# - Selección de archivos
# - Validación de entrada usuario
# - Mensajes de confirmación