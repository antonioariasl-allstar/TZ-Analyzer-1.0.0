"""
tz_cli_click - CLI MODERNO CON CLICK FRAMEWORK
==============================================

✅ ESTADO: SPRINT 3B - IMPLEMENTACIÓN CLI ARGUMENTOS
🎯 PROPÓSITO: Interfaz línea comandos moderna complementaria al menú interactivo  
📍 DIFERENCIACIÓN: CLI programático vs menú wizard interactivo

RESPONSABILIDADES:
- Entry point principal: tzanalysis [comando] [opciones]
- Click framework para parsing argumentos y help contextual
- Command pattern con registry para extensibilidad
- Context object para manejo estado sin variables globales

COMANDOS DISPONIBLES:
- tzanalysis run: Procesamiento programático directo
- tzanalysis process: Flujo interactivo simplificado  
- tzanalysis manual: Entrada manual antenas
- tzanalysis validate: Validación archivos entrada
- tzanalysis config: Configuración sistema
- tzanalysis info: Información sistema

DIFERENCIACIÓN vs tz_cli (Sprint 3A):
- tz_cli: Menú interactivo [1/2/3] wizard paso a paso
- tz_cli_click: CLI argumentos 'tzanalysis run --input file.xlsx'
- AMBOS COMPLEMENTARIOS para diferentes workflows

INTEGRACIÓN:
- Reutiliza tz_core (KML, heatmap) y script_principal (business logic)
- Coexiste con menú interactivo sin conflictos
- Entry points separados en setup.py

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

# Entry points principales
from .main import cli

__version__ = "1.0.0"
__author__ = "TZ Analyzer Team" 
__description__ = "CLI moderno con Click framework - Sprint 3B"

# Re-exports principales
__all__ = [
    'cli'
]