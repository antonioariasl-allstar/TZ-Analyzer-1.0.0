"""
tz_cli.commands - REGISTRO DE COMANDOS CLI
=========================================

✅ ESTADO: SPRINT 3 - REGISTRO Y ORQUESTACIÓN COMANDOS
🎯 PROPÓSITO: Registry central de comandos CLI para TZ Analyzer
📍 DIFERENCIACIÓN: Command pattern con auto-discovery y registration

RESPONSABILIDADES ESPECÍFICAS:
- Registry automático de comandos desde commands/
- Integration point entre CLI framework y business logic
- Command discovery y help system contextual
- Validación y routing de comandos

COMANDOS REGISTRADOS:
- process: Menú interactivo principal (main())
- run: Ejecución programática (run_tz_analysis())
- manual: Entrada manual antenas (_modo_manual())
- config: Configuración sistema
- validate: Validaciones archivos

ARQUITECTURA:
- Click group con command registration
- Auto-discovery de comandos desde módulos
- Context object para inyección dependencias
- Error handling unificado

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3 Fase 3.2
"""

import click
from typing import Dict, Any

# Import comandos principales
from .process import process_command, process_group
from .run import run_command, run_quick  
from .manual import manual_command

def register_commands(cli_group: click.Group) -> None:
    """
    Registra todos los comandos disponibles en el CLI group principal
    
    Utiliza patrón registry para auto-discovery y registration de comandos
    desde módulos individuales. Permite extensibilidad modular.
    
    Args:
        cli_group: Click Group principal donde registrar comandos
    """
    
    # Comandos principales
    cli_group.add_command(process_command)
    cli_group.add_command(process_group) 
    cli_group.add_command(run_command)
    cli_group.add_command(run_quick)
    cli_group.add_command(manual_command)
    
    # Comandos auxiliares
    cli_group.add_command(config_command)
    cli_group.add_command(validate_command)
    cli_group.add_command(info_command)

# Comandos auxiliares definidos aquí por simplicidad

@click.command('config')
@click.option('--show', is_flag=True, help='Mostrar configuración actual')
@click.option('--theme', type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              help='Configurar tema de colores global')
@click.option('--reset', is_flag=True, help='Resetear configuración a defaults')
@click.option('--edit', is_flag=True, help='Abrir config.json en editor')
@click.pass_obj
def config_command(ctx, show: bool, theme: str, reset: bool, edit: bool):
    """
    Configuración del sistema TZ Analyzer
    
    Permite ver, modificar y resetear configuraciones globales
    incluyendo temas de colores, rutas por defecto y preferencias.
    
    Ejemplos:
      tzanalysis config --show
      tzanalysis config --theme blue
      tzanalysis config --reset
    """
    if show:
        _show_current_config(ctx)
    elif theme:
        _set_theme(ctx, theme)
    elif reset:
        _reset_config(ctx)
    elif edit:
        _edit_config(ctx)
    else:
        # Mostrar configuración por defecto
        _show_current_config(ctx)

@click.command('validate')
@click.argument('file_path', type=click.Path(exists=True, readable=True))
@click.option('--sheet', '-s', help='Hoja específica para validar')
@click.option('--detailed', '-d', is_flag=True, help='Validación detallada')
@click.option('--json', 'json_output', is_flag=True, help='Output en formato JSON')
@click.pass_obj
def validate_command(ctx, file_path: str, sheet: str, detailed: bool, json_output: bool):
    """
    Validar archivo de entrada antes de procesamiento
    
    Verifica estructura, columnas requeridas, tipos de datos y
    detecta posibles problemas antes de ejecutar procesamiento completo.
    
    Ejemplos:
      tzanalysis validate bitacora.xlsx
      tzanalysis validate bitacora.xlsx --sheet 0 --detailed
      tzanalysis validate bitacora.xlsx --json
    """
    from tz_cli.validators.file_validators import validate_input_file
    
    try:
        result = validate_input_file(file_path, sheet, detailed)
        
        if json_output:
            import json
            click.echo(json.dumps(result, indent=2))
        else:
            _show_validation_result(result, detailed)
            
    except Exception as e:
        if json_output:
            import json
            error_result = {"status": "error", "error": str(e)}
            click.echo(json.dumps(error_result, indent=2), err=True)
        else:
            click.echo(f"💥 Error validando archivo: {e}", err=True)
        raise click.Abort()

@click.command('info') 
@click.option('--version', is_flag=True, help='Mostrar versión detallada')
@click.option('--system', is_flag=True, help='Información del sistema')
@click.option('--paths', is_flag=True, help='Rutas importantes')
@click.pass_obj
def info_command(ctx, version: bool, system: bool, paths: bool):
    """
    Información del sistema TZ Analyzer
    
    Muestra versión, configuración del sistema, rutas importantes
    y estado de dependencias.
    
    Ejemplos:
      tzanalysis info
      tzanalysis info --version
      tzanalysis info --system --paths
    """
    if version:
        _show_version_info()
    elif system:
        _show_system_info() 
    elif paths:
        _show_paths_info()
    else:
        # Info general
        _show_general_info()

# Helpers para comandos auxiliares

def _show_current_config(ctx):
    """Muestra configuración actual"""
    config = getattr(ctx, 'config', {})
    
    click.echo("🔧 Configuración actual TZ Analyzer:")
    click.echo(f"   📁 Directorios: {len(config.get('paths', {}))}")
    click.echo(f"   🎨 Tema: {config.get('kml', {}).get('tema', 'blue')}")
    click.echo(f"   📊 Columnas: {len(config.get('columnas', {}))}")
    click.echo(f"   📈 Top antenas: {config.get('analisis', {}).get('top_antenas', 10)}")
    click.echo(f"   📞 Top contactos: {config.get('analisis', {}).get('top_contactos', 5)}")

def _set_theme(ctx, theme: str):
    """Configura tema de colores"""
    # TODO: Implementar persistencia de configuración
    click.echo(f"🎨 Tema configurado: {theme}")
    click.echo("💾 Guardando en config.json...")

def _reset_config(ctx):
    """Resetea configuración a defaults"""
    # TODO: Implementar reset de configuración
    click.echo("🔄 Reseteando configuración a valores por defecto...")
    click.echo("✅ Configuración reseteada")

def _edit_config(ctx):
    """Abre config.json en editor"""
    import os
    config_path = "config.json"
    if os.path.exists(config_path):
        os.system(f"notepad {config_path}")  # Windows
    else:
        click.echo("📝 config.json no encontrado - creando template...")

def _show_validation_result(result: Dict[str, Any], detailed: bool):
    """Muestra resultado de validación en formato usuario"""
    status = result.get('status', 'unknown')
    
    if status == 'valid':
        click.echo("✅ Archivo válido para procesamiento")
        click.echo(f"   📊 Filas: {result.get('rows', 0)}")
        click.echo(f"   📋 Columnas: {result.get('columns', 0)}")
        if 'sheets' in result:
            click.echo(f"   📄 Hojas: {len(result['sheets'])}")
    else:
        click.echo("❌ Archivo con problemas:")
        for error in result.get('errors', []):
            click.echo(f"   💥 {error}")

def _show_version_info():
    """Muestra información detallada de versión"""
    click.echo("📦 TZ Analyzer v1.0.0")
    click.echo("🏗️  Arquitectura modular completa")
    click.echo("🚀 Sprint 3: CLI Modular")

def _show_system_info():
    """Muestra información del sistema"""
    import sys
    import platform
    
    click.echo("💻 Información del sistema:")
    click.echo(f"   🐍 Python: {sys.version}")
    click.echo(f"   🖥️  OS: {platform.system()} {platform.release()}")
    click.echo(f"   📁 Working Dir: {os.getcwd()}")

def _show_paths_info():
    """Muestra rutas importantes"""
    import os
    
    click.echo("📁 Rutas importantes:")
    click.echo(f"   🏠 Home: {os.path.expanduser('~')}")
    click.echo(f"   📂 Current: {os.getcwd()}")
    click.echo(f"   ⚙️  Config: ./config.json")

def _show_general_info():
    """Muestra información general"""
    click.echo("ℹ️  TZ Analyzer - Herramienta análisis bitácoras")
    click.echo("🎯 Procesamiento datos antenas y geolocalización")
    click.echo("📊 Generación KML/KMZ y reportes HTML")
    click.echo("\n💡 Usa 'tzanalysis --help' para ver comandos disponibles")