"""
tz_cli - INTERFAZ CLI MODULAR (SIN CLICK) 
=========================================

✅ ESTADO: SPRINT 3A - EXTRACCIÓN MENÚ INTERACTIVO COMPLETADA
🎯 PROPÓSITO: Modularización del CLI interactivo actual del monolito
📍 DIFERENCIACIÓN: NO CAMBIAR UX - solo modularizar código existente

RESPONSABILIDADES:
- menu.py: Menús interactivos [1/2/3] y [A/L/E/G/V]
- controllers.py: Bridge menú ↔ lógica core del monolito
- helpers.py: Helpers input, validación, prompts

INTEGRACIÓN:
- run_cli() en monolito → tz_cli.menu.main_menu()
- Zero cambios en UX o flujo usuario
- Variables globales preservadas
- Lógica negocio intacta en monolito

DIFERENCIA CON CLI CLICK:
- Este es menú interactivo actual (sin argumentos CLI)
- CLI Click será Sprint 3B (interfaz línea comandos moderna)
- Ambos son complementarios y valiosos

FECHA EXTRACCIÓN: 29 octubre 2025 - Sprint 3A
"""

# Entry points principales
from .menu import main_menu, manual_menu_loop
from .controllers import (
    handle_manual_mode, 
    handle_file_selection,
    handle_theme_selection,
    handle_output_setup
)
from .helpers import (
    input_str, 
    input_float, 
    input_int,
    bitacora_type_prompt,
    output_name_prompt,
    time_filters_prompt,
    confirm_yn
)

__version__ = "1.0.0"
__author__ = "TZ Analyzer Team" 
__description__ = "Interfaz CLI modular sin Click - Sprint 3A"

# Aliases principales para compatibilidad
show_main_menu = main_menu
run_interactive_menu = main_menu

# Re-exports para convenience
__all__ = [
    # Menu functions
    'main_menu',
    'manual_menu_loop', 
    'show_main_menu',
    'run_interactive_menu',
    
    # Controllers
    'handle_manual_mode',
    'handle_file_selection', 
    'handle_theme_selection',
    'handle_output_setup',
    
    # Helpers
    'input_str',
    'input_float',
    'input_int', 
    'bitacora_type_prompt',
    'output_name_prompt',
    'time_filters_prompt',
    'confirm_yn'
]