"""
tz_cli_click.main - CLI GROUP PRINCIPAL CON CLICK
=================================================

✅ ESTADO: SPRINT 3B - CLI CLICK FRAMEWORK CORE  
🎯 PROPÓSITO: Entry point principal para tzanalysis CLI
📍 DIFERENCIACIÓN: Orquestador CLI usando Click vs menú interactivo

ARQUITECTURA CLI:
- Click framework para parsing argumentos y help contextual
- Command pattern con registry para extensibilidad  
- Context object para inyección dependencias vs variables globales
- Handlers especializados para file I/O, config, output

COMANDO BASE: tzanalysis [COMMAND] [OPTIONS]
- Global options: --config, --output-dir, --quiet, --verbose
- Commands: run, process, manual, validate, config, info
- Context sharing entre comandos para estado consistente

INTEGRACIÓN:
- Bridge hacia script_principal_bitacoras_refactory para business logic
- Reutilización tz_core modules (KML, heatmap)
- Coexistencia con tz_cli menú interactivo

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

import click
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

class TZClickContext:
    """
    Context object para CLI Click - evita variables globales
    
    Centraliza estado aplicación para diferentes comandos:
    - config: Configuración cargada
    - output_dir: Directorio salida seleccionado  
    - quiet/verbose: Niveles output CLI
    - dry_run: Modo simulación sin ejecución
    """
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.output_dir: Optional[str] = None
        self.quiet: bool = False
        self.verbose: bool = False
        self.dry_run: bool = False
        self.theme: str = "default"
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """Carga configuración reutilizando bootstrap del monolito"""
        try:
            # Usar bootstrap existente del monolito
            from script_principal_bitacoras_refactory import bootstrap_config
            bootstrap_config()
            
            # Importar CONFIG del monolito
            import script_principal_bitacoras_refactory as script
            self.config = getattr(script, 'CONFIG', {})
            
            if not self.quiet:
                click.echo(f"✅ Configuración cargada: {len(self.config)} secciones")
        except Exception as e:
            if not self.quiet:
                click.echo(f"⚠️  Error cargando configuración: {e}", err=True)
                click.echo("Continuando con configuración por defecto...")
    
    def setup_logging(self, level: str = "INFO") -> None:
        """Configura logging para CLI con nivel especificado"""
        import logging
        
        # Mapeo niveles CLI a logging
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO, 
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR
        }
        
        log_level = level_map.get(level.upper(), logging.INFO)
        
        if self.quiet:
            log_level = logging.ERROR
        elif self.verbose:
            log_level = logging.DEBUG
            
        logging.basicConfig(
            level=log_level,
            format="%(levelname)s: %(message)s" if not self.verbose else "%(asctime)s [%(levelname)s] %(message)s"
        )

pass_context = click.make_pass_decorator(TZClickContext)

@click.group()
@click.option('--config', '-c', 'config_path', 
              help='Archivo config.json personalizado')
@click.option('--output-dir', '-o', 
              help='Directorio base para archivos de salida')
@click.option('--log-level', '-l', 
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False),
              default='INFO', help='Nivel de logging')
@click.option('--quiet', '-q', is_flag=True, 
              help='Suprimir output no esencial')
@click.option('--verbose', '-v', is_flag=True,
              help='Output detallado con timestamps')
@click.option('--dry-run', is_flag=True,
              help='Simular ejecución sin realizar cambios')
@click.version_option(version='1.0.0', prog_name='TZ Analyzer CLI')
@click.pass_context
def cli(ctx: click.Context, config_path: Optional[str], output_dir: Optional[str], 
        log_level: str, quiet: bool, verbose: bool, dry_run: bool):
    """
    TZ ANALYZER CLI - Herramienta línea comandos para análisis bitácoras telefónicas
    
    Procesamiento programático de datos antenas, geolocalización y reportes.
    Soporte archivos Excel/TSV con generación KML/KMZ y reportes HTML.
    
    EJEMPLOS DE USO:
    
      # Procesamiento directo programático
      tzanalysis run --input bitacora.xlsx --top-antenas 10
      
      # Validar archivo antes procesar
      tzanalysis validate --input bitacora.xlsx --verbose
      
      # Entrada manual coordenadas  
      tzanalysis manual --coord-lat 40.4168 --coord-lon -3.7038
      
      # Procesamiento con filtros temporales
      tzanalysis run --input data.xlsx --time-filter rango-dias \\
                     --date-start 2025-10-01 --date-end 2025-10-31
    
    DIFERENCIACIÓN:
      - CLI argumentos: Automation, batch processing, scripts
      - Menú interactivo: python run.py -> Wizard paso a paso
      - AMBOS COMPLEMENTARIOS para diferentes workflows
    """
    # Crear context object y configurar aplicación
    tz_ctx = TZClickContext()
    tz_ctx.output_dir = output_dir
    tz_ctx.quiet = quiet  
    tz_ctx.verbose = verbose
    tz_ctx.dry_run = dry_run
    
    # Configurar logging antes de cargar config
    tz_ctx.setup_logging(log_level)
    
    # Cargar configuración
    tz_ctx.load_config(config_path)
    
    # Guardar context para comandos
    ctx.obj = tz_ctx

# Importar y registrar comandos después de definir cli
def _register_commands():
    """Registra todos los comandos disponibles en el CLI"""
    # Import dinámico para evitar circular imports
    from .commands.run import run_command
    from .commands.process import process_command  
    from .commands.manual import manual_command
    from .commands.validate import validate_command
    from .commands.config import config_command
    from .commands.info import info_command
    
    # Registrar comandos en el group principal
    cli.add_command(run_command, name='run')
    cli.add_command(process_command, name='process')
    cli.add_command(manual_command, name='manual')
    cli.add_command(validate_command, name='validate')
    cli.add_command(config_command, name='config')
    cli.add_command(info_command, name='info')

def main():
    """Entry point principal para tz_cli_click - llamado desde setup.py"""
    # Registrar comandos antes de ejecutar CLI
    _register_commands()
    
    # Click ejecuta automáticamente con sys.argv
    cli()

if __name__ == '__main__':
    main()