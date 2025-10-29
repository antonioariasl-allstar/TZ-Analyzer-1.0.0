"""
tz_cli.main - ENTRY POINT PRINCIPAL CLI TZ ANALYZER
==================================================

✅ ESTADO: SPRINT 3 - ORQUESTADOR CLI PRINCIPAL
🎯 PROPÓSITO: Entry point unificado para interfaz línea de comandos
📍 DIFERENCIACIÓN: Punto de entrada único con command registry automático

RESPONSABILIDADES ESPECÍFICAS:
- Entry point principal desde setup.py o run.py
- Integración commands con CLI group principal
- Exception handling global y user experience
- Context setup y dependency injection

ARQUITECTURA:
- Click framework como base CLI
- Command registry pattern para extensibilidad
- Context object para variables globales
- Error handling unificado para UX

COMANDOS DISPONIBLES:
- tzanalysis process: Flujo interactivo principal
- tzanalysis run: Ejecución programática directa
- tzanalysis manual: Entrada manual antenas
- tzanalysis config: Configuración sistema
- tzanalysis validate: Validación archivos
- tzanalysis info: Información sistema

INTEGRACIÓN:
- Importa tz_cli.__init__.cli como base
- Registra comandos desde tz_cli.commands
- Setup logging y configuración global
- Bridge hacia script_principal_bitacoras_refactory

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3 Fase 3.2
"""

import sys
import os
from pathlib import Path

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """
    Entry point principal para TZ Analyzer CLI
    
    Configura entorno, registra comandos y ejecuta CLI con manejo
    robusto de errores y experiencia de usuario optimizada.
    
    Punto de entrada desde:
    - setup.py console_scripts
    - python -m tz_cli
    - run.py con argumento --cli
    """
    
    try:
        # Import dinámico para manejar dependencias faltantes
        try:
            import click
        except ImportError:
            print("💥 Error: Click no está instalado")
            print("📦 Instala con: pip install click")
            sys.exit(1)
        
        # Import CLI base y comandos
        try:
            from tz_cli import cli as base_cli
            from tz_cli.commands import register_commands
        except ImportError as e:
            print(f"💥 Error importando módulos CLI: {e}")
            print("🔧 Verifica estructura del proyecto")
            sys.exit(1)
        
        # Registrar comandos en CLI base
        register_commands(base_cli)
        
        # Ejecutar CLI
        base_cli()
        
    except KeyboardInterrupt:
        print("\n⏹️  Operación cancelada por usuario")
        sys.exit(1)
        
    except click.ClickException as e:
        # Errores CLI específicos (argumentos inválidos, etc.)
        e.show()
        sys.exit(e.exit_code)
        
    except Exception as e:
        # Errores no controlados
        print(f"💥 Error no controlado: {e}")
        print("🐛 Reporte este error si persiste")
        
        # Mostrar traceback en modo debug
        if os.environ.get('TZ_DEBUG'):
            import traceback
            traceback.print_exc()
            
        sys.exit(1)

def cli_entry_point():
    """
    Entry point alternativo para console_scripts
    
    Wrapper de main() para compatibility con setuptools
    console_scripts entry points.
    """
    main()

if __name__ == '__main__':
    main()