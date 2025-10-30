"""
tz_cli_click.commands.process - COMANDO TZANALYSIS PROCESS
=========================================================

✅ ESTADO: SPRINT 3B - COMANDO PROCESS INTERACTIVO
🎯 PROPÓSITO: Bridge hacia menú interactivo desde CLI
📍 DIFERENCIACIÓN: CLI -> menú wizard vs argumentos puros

COMANDO: tzanalysis process [OPTIONS]

FUNCIONALIDADES:
- Bridge hacia menú interactivo existente (Sprint 3A)
- Pre-configuración opcional via argumentos
- Flujo wizard guiado para usuarios CLI

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

import click
from typing import Optional

from ..main import pass_context, TZClickContext

@click.command()
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True, readable=True),
              help='Archivo a procesar (opcional - se puede seleccionar interactivamente)')
@click.option('--interactive', is_flag=True, default=True,
              help='Modo interactivo (default: activado)')
@click.pass_context
def process_command(ctx, input_file: Optional[str], interactive: bool):
    """
    Procesamiento con flujo interactivo guiado.
    
    Este comando es un bridge hacia el menú interactivo existente,
    permitiendo acceso desde CLI pero manteniendo el wizard paso a paso.
    
    EJEMPLOS:
      tzanalysis process                    # Menú interactivo completo
      tzanalysis process --input file.xlsx # Pre-seleccionar archivo
    
    DIFERENCIA vs 'run':
      - process: Wizard interactivo paso a paso 
      - run: Argumentos CLI directos, no interacción
    """
    
    # Acceder al contexto TZ específico
    tz_ctx: TZClickContext = ctx.obj
    
    if not tz_ctx.quiet:
        click.echo(f"🎯 TZ Analyzer - Modo proceso interactivo")
        
    if input_file and not tz_ctx.quiet:
        click.echo(f"📁 Archivo pre-seleccionado: {input_file}")
    
    try:
        # Delegación al menú interactivo existente
        from tz_cli.menu import main_menu
        
        if not tz_ctx.quiet:
            click.echo(f"🔄 Iniciando menú interactivo...")
            click.echo(f"   (Equivalente a: python run.py)")
            
        # TODO: Si input_file está especificado, pre-configurar el sistema
        # para usar ese archivo automáticamente
        
        result = main_menu()
        
        if not tz_ctx.quiet:
            click.echo(f"✅ Procesamiento interactivo completado")
            
        return result
        
    except ImportError:
        click.echo(f"❌ Error: Menú interactivo no disponible", err=True)
        click.echo(f"   Ejecute: python run.py", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Error durante procesamiento: {e}", err=True)
        if tz_ctx.verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()