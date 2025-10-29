"""
tz_cli.commands.process - COMANDO PROCESS (INTERACTIVO PRINCIPAL)
================================================================

✅ ESTADO: SPRINT 3 - DISEÑO CLI COMANDO PRINCIPAL  
🎯 PROPÓSITO: Interfaz CLI para main() - menú interactivo principal
📍 DIFERENCIACIÓN: Wrapper CLI para flujo interactivo existente

RESPONSABILIDADES ESPECÍFICAS:
- tzanalysis process: Ejecutar main() con argumentos CLI
- tzanalysis process full: Forzar modo bitácora completa (opción 1)
- tzanalysis process time: Forzar modo temporal (opción 2) 
- tzanalysis process manual: Forzar modo manual (opción 3)
- Override de selección archivo/carpeta con argumentos CLI

PARÁMETROS CLI:
- --file FILE: Override seleccionar_archivo()
- --sheet NAME|NUMBER: Hoja Excel específica  
- --theme COLOR: Override _solicitar_color_tema()
- --output-dir DIR: Override seleccionar_carpeta()
- Sub-comandos: full, time, manual

FUNCIÓN ORIGEN: main() en script_principal_bitacoras_refactory.py L5232
DEPENDENCIAS: script_principal_bitacoras_refactory, utilidades, tz_core.ui_utils
"""

import click
import os
from pathlib import Path
from typing import Optional

from tz_cli import TZContext, pass_context

@click.group('process')
@pass_context  
def process_group(ctx: TZContext):
    """
    Procesar bitácoras con menú interactivo (modo principal)
    
    Ejecuta el flujo principal de TZ Analyzer con opciones de línea de comandos
    para override de selecciones interactivas (archivo, carpeta, tema, etc.)
    
    Disponible en tres modalidades:
    - full: Procesar bitácora completa (opción 1)
    - time: Procesar por tiempo (opción 2)  
    - manual: Entrada manual antenas (opción 3)
    """
    pass

@process_group.command('full')
@click.option('--file', '-f', 'input_file',
              type=click.Path(exists=True, readable=True),
              help='Archivo Excel/TSV entrada (override selección interactiva)')
@click.option('--sheet', '-s', 
              help='Hoja Excel específica (nombre o número)')
@click.option('--theme', '-t',
              type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              help='Tema de colores para KML/HTML')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida (override selección carpeta)')
@pass_context
def process_full(ctx: TZContext, input_file: Optional[str], sheet: Optional[str], 
                 theme: Optional[str], output_dir: Optional[str]):
    """
    Procesar bitácora completa (modo estándar)
    
    Ejecuta el procesamiento completo de una bitácora sin filtros temporales.
    Equivale a seleccionar opción [1] en el menú interactivo original.
    
    Ejemplos:
    
      # Interactivo con selecciones UI
      tzanalysis process full
      
      # Especificar archivo directamente
      tzanalysis process full --file bitacora.xlsx
      
      # Modo no interactivo completo
      tzanalysis process full -f bitacora.xlsx -t blue -o ./output
    """
    _execute_process_mode(ctx, mode="1", input_file=input_file, sheet=sheet,
                         theme=theme, output_dir=output_dir)

@process_group.command('time') 
@click.option('--file', '-f', 'input_file',
              type=click.Path(exists=True, readable=True),
              help='Archivo Excel/TSV entrada')
@click.option('--sheet', '-s',
              help='Hoja Excel específica (nombre o número)')
@click.option('--days', '-d', type=int,
              help='Número de días para filtro temporal')
@click.option('--date-range',
              help='Rango fechas (YYYY-MM-DD:YYYY-MM-DD)')
@click.option('--theme', '-t',
              type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              help='Tema de colores')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida')
@pass_context
def process_time(ctx: TZContext, input_file: Optional[str], sheet: Optional[str],
                 days: Optional[int], date_range: Optional[str], theme: Optional[str],
                 output_dir: Optional[str]):
    """
    Procesar por tiempo (día/rango días/horas)
    
    Procesa bitácora con filtros temporales. Equivale a seleccionar 
    opción [2] en el menú interactivo original.
    
    Ejemplos:
    
      # Interactivo con filtros tiempo
      tzanalysis process time
      
      # Últimos 3 días específicos
      tzanalysis process time --file bitacora.xlsx --days 3
      
      # Rango fechas específico  
      tzanalysis process time -f bitacora.xlsx --date-range 2024-10-01:2024-10-31
    """
    # TODO: Implementar filtros temporales en _execute_process_mode
    if days:
        ctx.config.setdefault('time_filters', {})['days'] = days
    if date_range:
        ctx.config.setdefault('time_filters', {})['date_range'] = date_range
        
    _execute_process_mode(ctx, mode="2", input_file=input_file, sheet=sheet,
                         theme=theme, output_dir=output_dir)

@process_group.command('manual')
@click.option('--name', '-n',
              help='Nombre caso manual (override automático)')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida')
@click.option('--interactive/--batch', default=True,
              help='Modo interactivo vs batch desde archivo')
@click.option('--batch-file',
              type=click.Path(exists=True, readable=True),
              help='Archivo JSON/CSV con registros manuales')
@pass_context
def process_manual(ctx: TZContext, name: Optional[str], output_dir: Optional[str],
                   interactive: bool, batch_file: Optional[str]):
    """
    Entrada manual de antenas/puntos
    
    Permite entrada interactiva o batch de registros de antenas.
    Equivale a seleccionar opción [3] en el menú interactivo original.
    
    Ejemplos:
    
      # Modo interactivo estándar
      tzanalysis process manual
      
      # Caso manual con nombre específico
      tzanalysis process manual --name "operativo_especial"
      
      # Carga batch desde archivo
      tzanalysis process manual --batch --batch-file registros.json
    """
    _execute_process_mode(ctx, mode="3", output_dir=output_dir,
                         manual_name=name, batch_file=batch_file)

# Comando process sin sub-comando (interactivo completo)
@click.command('process')
@click.option('--file', '-f', 'input_file',
              type=click.Path(exists=True, readable=True),
              help='Archivo Excel/TSV entrada')
@click.option('--sheet', '-s',
              help='Hoja Excel específica (nombre o número)')  
@click.option('--theme', '-t',
              type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              help='Tema de colores')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida')
@pass_context
def process_command(ctx: TZContext, input_file: Optional[str], sheet: Optional[str],
                    theme: Optional[str], output_dir: Optional[str]):
    """
    Procesar bitácora con menú interactivo principal
    
    Ejecuta el flujo completo de TZ Analyzer mostrando el menú principal
    para seleccionar modo de procesamiento (completo/tiempo/manual).
    
    Es el comando principal equivalente a ejecutar directamente el script original.
    
    Ejemplos:
    
      # Flujo interactivo completo (equivale a python run.py)
      tzanalysis process
      
      # Pre-cargar archivo pero mantener menú
      tzanalysis process --file bitacora.xlsx
      
      # Setup inicial con tema y directorio
      tzanalysis process -t blue -o ./outputs
    """
    _execute_process_mode(ctx, mode=None, input_file=input_file, sheet=sheet,
                         theme=theme, output_dir=output_dir)

def _execute_process_mode(ctx: TZContext, mode: Optional[str] = None,
                         input_file: Optional[str] = None, sheet: Optional[str] = None,
                         theme: Optional[str] = None, output_dir: Optional[str] = None,
                         manual_name: Optional[str] = None, batch_file: Optional[str] = None):
    """
    Ejecutor común para todos los modos de process
    
    Prepara variables globales, ejecuta main() con overrides de CLI,
    y maneja el flujo según el modo especificado.
    """
    import script_principal_bitacoras_refactory as script
    
    # Setup variables globales según argumentos CLI
    if input_file:
        # TODO: Override seleccionar_archivo() con mock o inyección
        pass
    
    if output_dir:
        ctx.output_dir = output_dir
        # TODO: Override seleccionar_carpeta() 
        
    if theme:
        # TODO: Override _solicitar_color_tema()
        ctx.config.setdefault('kml', {})['tema'] = theme
        
    if sheet:
        # TODO: Override selección hoja Excel
        ctx.config.setdefault('excel', {})['hoja_preferida'] = sheet
    
    # Ejecutar según modo
    try:
        if mode == "3":  # Manual
            if not ctx.quiet:
                click.echo("🔧 Iniciando modo manual de antenas...")
            # TODO: Implementar override para _modo_manual() con batch_file
            script._modo_manual()
        else:
            # Modos 1, 2 o interactivo (None)
            if not ctx.quiet:
                if mode == "1":
                    click.echo("📊 Ejecutando procesamiento completo...")
                elif mode == "2":
                    click.echo("⏰ Ejecutando procesamiento temporal...")
                else:
                    click.echo("🎛️  Iniciando menú interactivo principal...")
            
            # TODO: Implementar overrides para main() con mode forzado
            script.main()
            
    except KeyboardInterrupt:
        click.echo("\n⏹️  Procesamiento cancelado por usuario")
        raise click.Abort()
    except Exception as e:
        click.echo(f"💥 Error durante procesamiento: {e}", err=True)
        if ctx.verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()
        
    if not ctx.quiet:
        click.echo("✅ Procesamiento completado exitosamente")