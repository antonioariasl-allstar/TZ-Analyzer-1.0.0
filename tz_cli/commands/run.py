"""
tz_cli.commands.run - COMANDO RUN (EJECUCIÓN PROGRAMÁTICA)
=========================================================

✅ ESTADO: SPRINT 3 - DISEÑO CLI COMANDO PROGRAMÁTICO
🎯 PROPÓSITO: Interfaz CLI para run_tz_analysis() - ejecución directa sin prompts
📍 DIFERENCIACIÓN: API CLI para scripts/automatización sin interacción usuario

RESPONSABILIDADES ESPECÍFICAS:
- tzanalysis run: Ejecutar run_tz_analysis() con parámetros CLI
- Modo no-interactivo para integración en scripts/pipelines
- Validación exhaustiva de parámetros antes de ejecución
- Output estructurado para parsing programático

PARÁMETROS CLI:
- --input FILE (requerido): Archivo entrada
- --sheet NAME|NUMBER: Hoja Excel específica
- --top-antenas N: Top N antenas (default: 10)
- --top-contactos N: Top N contactos (default: 5) 
- --kmz-only: Solo generar KMZ (no HTML)
- --output-dir DIR: Directorio salida
- --output-name NAME: Nombre base archivos

FUNCIÓN ORIGEN: run_tz_analysis() en script_principal_bitacoras_refactory.py L5037
RETORNO: JSON con rutas archivos generados para integración programática
"""

import click
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from tz_cli import TZContext, pass_context

@click.command('run')
@click.option('--input', '-i', 'input_file', required=True,
              type=click.Path(exists=True, readable=True),
              help='Archivo Excel/TSV entrada (REQUERIDO)')
@click.option('--sheet', '-s',
              help='Hoja Excel específica (nombre o número, default: primera)')
@click.option('--top-antenas', '-ta', type=int, default=10,
              help='Top N antenas para análisis (default: 10)')
@click.option('--top-contactos', '-tc', type=int, default=5,
              help='Top N contactos para análisis (default: 5)')
@click.option('--kmz-only', is_flag=True,
              help='Solo generar KMZ, omitir HTML (modo rápido)')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida (default: directorio actual)')
@click.option('--output-name', '-n',
              help='Nombre base archivos salida (default: auto desde entrada)')
@click.option('--theme', '-t',
              type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              default='blue', help='Tema colores KML (default: blue)')
@click.option('--json-output', is_flag=True,
              help='Output resultado en formato JSON para parsing programático')
@click.option('--dry-run', is_flag=True,
              help='Validar parámetros sin ejecutar procesamiento')
@pass_context
def run_command(ctx: TZContext, input_file: str, sheet: Optional[str],
                top_antenas: int, top_contactos: int, kmz_only: bool,
                output_dir: Optional[str], output_name: Optional[str],
                theme: str, json_output: bool, dry_run: bool):
    """
    Ejecución programática directa sin prompts interactivos
    
    Ejecuta run_tz_analysis() con parámetros especificados, ideal para
    automatización, scripts y pipelines de datos. No requiere interacción
    del usuario y retorna rutas de archivos generados.
    
    Ejemplos:
    
      # Ejecución básica mínima
      tzanalysis run --input bitacora.xlsx
      
      # Configuración completa
      tzanalysis run -i bitacora.xlsx -ta 15 -tc 8 -o ./outputs -n caso_especial
      
      # Solo KMZ para procesamiento rápido
      tzanalysis run -i bitacora.xlsx --kmz-only
      
      # Output JSON para scripts
      tzanalysis run -i bitacora.xlsx --json-output
      
      # Validación sin ejecutar
      tzanalysis run -i bitacora.xlsx --dry-run
    """
    
    # Validar archivo entrada
    input_path = Path(input_file)
    if not input_path.exists():
        click.echo(f"💥 Error: Archivo no encontrado: {input_file}", err=True)
        raise click.Abort()
    
    if not input_path.suffix.lower() in ['.xlsx', '.xls', '.tsv', '.csv']:
        click.echo(f"⚠️  Advertencia: Extensión no estándar: {input_path.suffix}", err=True)
    
    # Configurar directorio salida
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = os.getcwd()
        output_path = Path(output_dir)
    
    # Validar parámetros numéricos
    if top_antenas < 1 or top_antenas > 100:
        click.echo(f"💥 Error: top-antenas debe estar entre 1-100, recibido: {top_antenas}", err=True)
        raise click.Abort()
        
    if top_contactos < 1 or top_contactos > 100:
        click.echo(f"💥 Error: top-contactos debe estar entre 1-100, recibido: {top_contactos}", err=True)
        raise click.Abort()
    
    # Configurar nombre salida
    if not output_name:
        output_name = input_path.stem  # Usar nombre archivo sin extensión
    
    # Configurar tema en context
    ctx.config.setdefault('kml', {})['tema'] = theme
    
    # Mostrar configuración si no es quiet
    if not ctx.quiet:
        click.echo("🚀 Configuración ejecución programática:")
        click.echo(f"   📁 Entrada: {input_file}")
        if sheet:
            click.echo(f"   📊 Hoja: {sheet}")
        click.echo(f"   📈 Top antenas: {top_antenas}")
        click.echo(f"   📞 Top contactos: {top_contactos}")
        click.echo(f"   🎨 Tema: {theme}")
        click.echo(f"   📂 Salida: {output_dir}")
        click.echo(f"   📝 Nombre: {output_name}")
        if kmz_only:
            click.echo(f"   ⚡ Modo: Solo KMZ (rápido)")
    
    # Modo dry-run: validar sin ejecutar
    if dry_run:
        if not ctx.quiet:
            click.echo("✅ Validación completada - parámetros correctos")
            if json_output:
                result = {
                    "status": "validated", 
                    "input": str(input_path.absolute()),
                    "output_dir": str(output_path.absolute()),
                    "config": {
                        "top_antenas": top_antenas,
                        "top_contactos": top_contactos,
                        "kmz_only": kmz_only,
                        "theme": theme
                    }
                }
                click.echo(json.dumps(result, indent=2))
        return
    
    # Ejecutar run_tz_analysis
    try:
        if not ctx.quiet:
            click.echo("⚙️  Iniciando procesamiento...")
        
        # Preparar parámetros para run_tz_analysis
        # TODO: Implementar conversión hoja str→int si es numérica
        sheet_param = sheet
        if sheet and sheet.isdigit():
            sheet_param = int(sheet)
        
        # Importar y ejecutar función programática
        from script_principal_bitacoras_refactory import run_tz_analysis
        
        resultado = run_tz_analysis(
            ruta_entrada=str(input_path.absolute()),
            hoja=sheet_param,
            top_antenas=top_antenas,
            top_contactos=top_contactos,
            solo_kmz=kmz_only,
            carpeta_salida=str(output_path.absolute())
        )
        
        # Procesar resultado
        if isinstance(resultado, dict):
            # Resultado exitoso con rutas archivos
            if not ctx.quiet:
                click.echo("✅ Procesamiento completado exitosamente")
                if resultado.get('html'):
                    click.echo(f"   📄 HTML: {resultado['html']}")
                if resultado.get('kmz'):
                    click.echo(f"   🗺️  KMZ: {resultado['kmz']}")
                if resultado.get('hashes'):
                    click.echo(f"   🔒 Hashes: {resultado['hashes']}")
                if resultado.get('log'):
                    click.echo(f"   📋 Log: {resultado['log']}")
            
            # Output JSON si solicitado
            if json_output:
                click.echo(json.dumps(resultado, indent=2))
                
        else:
            # Resultado inesperado
            if not ctx.quiet:
                click.echo("⚠️  Procesamiento completado con resultado inesperado")
            if json_output:
                click.echo(json.dumps({"status": "completed", "result": str(resultado)}, indent=2))
        
    except KeyboardInterrupt:
        click.echo("\n⏹️  Procesamiento cancelado por usuario")
        raise click.Abort()
        
    except Exception as e:
        error_msg = f"💥 Error durante procesamiento: {e}"
        click.echo(error_msg, err=True)
        
        if ctx.verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        
        if json_output:
            error_result = {
                "status": "error",
                "error": str(e),
                "input": str(input_path.absolute())
            }
            click.echo(json.dumps(error_result, indent=2), err=True)
            
        raise click.Abort()

# Comando alternativo más corto para uso frecuente
@click.command('r')  
@click.option('--input', '-i', required=True, type=click.Path(exists=True, readable=True))
@click.option('--output-dir', '-o', type=click.Path(file_okay=False, writable=True))
@click.option('--json', 'json_output', is_flag=True, help='Output JSON')
@pass_context
def run_quick(ctx: TZContext, input: str, output_dir: Optional[str], json_output: bool):
    """
    Ejecución rápida con parámetros default (alias de 'run')
    
    Versión corta del comando run con configuración por defecto.
    Ideal para uso frecuente en terminal.
    
    Ejemplos:
      tzanalysis r -i bitacora.xlsx
      tzanalysis r -i bitacora.xlsx -o ./out --json
    """
    # Delegar a run_command con parámetros default
    from click.testing import CliRunner
    
    ctx.invoke(run_command, 
               input_file=input,
               sheet=None,
               top_antenas=10,
               top_contactos=5,
               kmz_only=False,
               output_dir=output_dir,
               output_name=None,
               theme='blue',
               json_output=json_output,
               dry_run=False)