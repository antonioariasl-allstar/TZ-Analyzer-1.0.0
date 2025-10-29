"""
tz_cli_click.commands - COMANDOS CLI CLICK
==========================================

✅ ESTADO: SPRINT 3B - REGISTRY COMANDOS CLI
🎯 PROPÓSITO: Centralizar todos los comandos disponibles
📍 DIFERENCIACIÓN: Command pattern para extensibilidad

COMANDOS DISPONIBLES:
- run: Procesamiento programático directo
- process: Flujo interactivo simplificado  
- manual: Entrada manual antenas
- validate: Validación archivos
- config: Configuración sistema
- info: Información sistema

ESTRUCTURA:
- Cada comando en archivo separado
- Import centralizado desde main.py
- Context sharing entre comandos

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

# Commands registry para facilitar imports
__all__ = [
    'run_command',
    'process_command', 
    'manual_command',
    'validate_command',
    'config_command',
    'info_command'
]