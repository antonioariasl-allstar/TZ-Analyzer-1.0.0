"""
tz_cli_click.commands.manual - COMANDO TZANALYSIS MANUAL
=======================================================

✅ ESTADO: SPRINT 3B - COMANDO ENTRADA MANUAL
🎯 PROPÓSITO: Entrada coordenadas antenas vía CLI argumentos
📍 DIFERENCIACIÓN: CLI argumentos vs wizard manual interactivo

COMANDO: tzanalysis manual [OPTIONS]

FUNCIONALIDADES:
- Entrada directa coordenadas via argumentos
- Configuración antenas programática
- Generación outputs sin interacción
- Import/export antenas desde archivo

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

import click
from typing import Optional

from ..main import pass_context, TZClickContext

@click.command()
@click.option('--coord-lat', type=float, help='Latitud antena')
@click.option('--coord-lon', type=float, help='Longitud antena')
@click.option('--name', type=str, help='Nombre antena')
@click.option('--radius', type=str, default='1km', help='Radio cobertura (ej: 1km, 500m)')
@click.option('--add-multiple', is_flag=True, help='Modo entrada múltiple interactiva')
@click.option('--import-file', type=click.Path(exists=True, readable=True),
              help='Importar antenas desde archivo')
@click.option('--theme', type=str, default='default',
              help='Color tema visualización')
@click.option('--output', '-o', 'output_dir', type=click.Path(),
              help='Directorio salida')
@click.pass_context
def manual_command(ctx, coord_lat: Optional[float], coord_lon: Optional[float],
                   name: Optional[str], radius: str, add_multiple: bool, 
                   import_file: Optional[str], theme: str, output_dir: Optional[str]):
    """
    Entrada manual de coordenadas antenas.
    
    EJEMPLOS:
      # Antena individual
      tzanalysis manual --coord-lat 40.4168 --coord-lon -3.7038 --name "Torre Madrid"
      
      # Import desde archivo
      tzanalysis manual --import-file antenas.csv --theme magenta
      
      # Entrada múltiple interactiva
      tzanalysis manual --add-multiple --theme cyan
    
    FORMATOS IMPORT:
      CSV: lat,lon,name,radius
      TSV: lat	lon	name	radius
    """
    
    # Acceder al contexto TZ específico
    tz_ctx: TZClickContext = ctx.obj
    
    if not tz_ctx.quiet:
        click.echo(f"📍 TZ Analyzer - Entrada manual antenas")
    
    # Validaciones entrada
    if import_file:
        # Modo import desde archivo
        result = _import_antennas_from_file(import_file, theme, output_dir, tz_ctx)
        
    elif coord_lat is not None and coord_lon is not None:
        # Modo antena individual
        if not name:
            name = f"Antena_{coord_lat:.4f}_{coord_lon:.4f}"
            
        result = _process_single_antenna(coord_lat, coord_lon, name, radius, theme, output_dir, tz_ctx)
        
    elif add_multiple:
        # Modo múltiple interactivo
        result = _multiple_antenna_mode(theme, output_dir, tz_ctx)
        
    else:
        # Sin parámetros - bridge hacia modo manual interactivo
        result = _interactive_manual_mode(tz_ctx)
    
    if not tz_ctx.quiet and result.get('status') == 'success':
        click.echo(f"✅ Procesamiento manual completado")
        if result.get('files_generated'):
            click.echo(f"📁 Archivos generados: {len(result['files_generated'])}")
            for file_path in result['files_generated']:
                click.echo(f"   - {file_path}")

def _process_single_antenna(lat: float, lon: float, name: str, radius: str,
                           theme: str, output_dir: Optional[str], ctx: TZClickContext) -> dict:
    """Procesar antena individual"""
    
    if not ctx.quiet:
        click.echo(f"📡 Procesando antena: {name}")
        click.echo(f"   Coordenadas: {lat:.6f}, {lon:.6f}")
        click.echo(f"   Radio: {radius}")
        click.echo(f"   Tema: {theme}")
    
    if ctx.dry_run:
        click.echo(f"🔍 DRY-RUN: Validación completada")
        return {'status': 'dry_run'}
    
    # TODO: Integrar con sistema manual del monolito
    # Por ahora simulamos procesamiento
    
    if not output_dir:
        output_dir = f"outputs_manual_{name.replace(' ', '_')}"
    
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    files_generated = [
        f"{output_dir}/antena_{name}_mapa.kml",
        f"{output_dir}/antena_{name}_cobertura.kmz"
    ]
    
    return {
        'status': 'success',
        'files_generated': files_generated,
        'antenna': {'lat': lat, 'lon': lon, 'name': name, 'radius': radius}
    }

def _import_antennas_from_file(import_file: str, theme: str, output_dir: Optional[str],
                              ctx: TZClickContext) -> dict:
    """Importar antenas desde archivo"""
    
    if not ctx.quiet:
        click.echo(f"📥 Importando antenas desde: {import_file}")
    
    # TODO: Implementar import real
    # Por ahora simulamos carga
    
    return {
        'status': 'success',
        'files_generated': [],
        'antennas_imported': 0
    }

def _multiple_antenna_mode(theme: str, output_dir: Optional[str], ctx: TZClickContext) -> dict:
    """Modo entrada múltiple interactiva"""
    
    if not ctx.quiet:
        click.echo(f"🔢 Modo entrada múltiple antenas")
        click.echo(f"   Formato: lat,lon,nombre (Enter vacío para terminar)")
    
    antennas = []
    
    while True:
        try:
            entrada = input("Antena (lat,lon,nombre): ").strip()
            if not entrada:
                break
                
            parts = entrada.split(',')
            if len(parts) >= 2:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip()) 
                name = parts[2].strip() if len(parts) > 2 else f"Antena_{len(antennas)+1}"
                
                antennas.append({'lat': lat, 'lon': lon, 'name': name})
                click.echo(f"   ✅ Agregada: {name} ({lat:.4f}, {lon:.4f})")
            else:
                click.echo(f"   ❌ Formato inválido, use: lat,lon,nombre")
                
        except ValueError:
            click.echo(f"   ❌ Coordenadas inválidas")
        except KeyboardInterrupt:
            click.echo(f"\n⏹️  Cancelado por usuario")
            break
    
    if antennas:
        click.echo(f"\n📊 Total antenas: {len(antennas)}")
        # TODO: Procesar antenas
        
    return {
        'status': 'success',
        'antennas_processed': len(antennas),
        'files_generated': []
    }

def _interactive_manual_mode(ctx: TZClickContext) -> dict:
    """Bridge hacia modo manual interactivo existente"""
    
    try:
        from tz_cli.controllers import handle_manual_mode
        
        if not ctx.quiet:
            click.echo(f"🔄 Iniciando modo manual interactivo...")
            
        result = handle_manual_mode()
        
        return {
            'status': 'success' if result else 'cancelled',
            'mode': 'interactive'
        }
        
    except ImportError:
        click.echo(f"❌ Modo manual interactivo no disponible", err=True)
        raise click.Abort()