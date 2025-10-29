"""
tz_cli.commands.manual - COMANDO MANUAL (ENTRADA MANUAL ANTENAS)
===============================================================

✅ ESTADO: SPRINT 3 - DISEÑO CLI COMANDO MANUAL
🎯 PROPÓSITO: Interfaz CLI para _modo_manual() - entrada manual antenas/puntos
📍 DIFERENCIACIÓN: Wrapper CLI para entrada manual con opciones batch

RESPONSABILIDADES ESPECÍFICAS:
- tzanalysis manual: Ejecutar _modo_manual() interactivo
- Modo batch desde archivo JSON/CSV para automatización
- Validación registros antes de generar KML/KMZ
- Override de nombres y configuraciones salida

PARÁMETROS CLI:
- --name NAME: Nombre caso manual (override automático)
- --output-dir DIR: Directorio salida específico
- --interactive/--batch: Modo interactivo vs carga archivo
- --batch-file FILE: Archivo JSON/CSV con registros
- --template: Generar template vacío para batch

FUNCIÓN ORIGEN: _modo_manual() en script_principal_bitacoras_refactory.py L4732
FORMATOS BATCH: JSON con estructura [{antena, lat, lon, detalle, ...}]
"""

import click
import json
import csv
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from tz_cli import TZContext, pass_context

@click.command('manual')
@click.option('--name', '-n',
              help='Nombre caso manual (default: auto desde timestamp)')
@click.option('--output-dir', '-o',
              type=click.Path(file_okay=False, writable=True),
              help='Directorio salida (default: directorio actual)')
@click.option('--interactive/--batch', default=True,
              help='Modo interactivo vs carga desde archivo (default: interactivo)')
@click.option('--batch-file', '-b',
              type=click.Path(exists=True, readable=True),
              help='Archivo JSON/CSV con registros manuales')
@click.option('--template', is_flag=True,
              help='Generar archivo template para modo batch')
@click.option('--validate-only', is_flag=True,
              help='Solo validar archivo batch sin generar KML/KMZ')
@click.option('--theme', '-t',
              type=click.Choice(['blue', 'green', 'red', 'rainbow'], case_sensitive=False),
              default='blue', help='Tema colores KML (default: blue)')
@pass_context
def manual_command(ctx: TZContext, name: Optional[str], output_dir: Optional[str],
                   interactive: bool, batch_file: Optional[str], template: bool,
                   validate_only: bool, theme: str):
    """
    Entrada manual de antenas y puntos de interés
    
    Permite entrada interactiva paso a paso o carga batch desde archivo
    para crear KML/KMZ con registros manuales de antenas/puntos.
    
    Soporta dos modalidades:
    - Interactiva: Flujo guiado paso a paso (default)
    - Batch: Carga masiva desde archivo JSON/CSV
    
    Ejemplos:
    
      # Modo interactivo estándar
      tzanalysis manual
      
      # Caso manual con nombre específico
      tzanalysis manual --name "operativo_norte_2024"
      
      # Generar template para modo batch
      tzanalysis manual --template
      
      # Carga batch desde archivo
      tzanalysis manual --batch --batch-file registros.json
      
      # Solo validar archivo batch
      tzanalysis manual --batch-file registros.json --validate-only
    """
    
    # Generar template batch
    if template:
        _generate_batch_template(ctx, output_dir)
        return
    
    # Configurar directorio salida
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = os.getcwd()
        output_path = Path(output_dir)
    
    # Configurar tema en context
    ctx.config.setdefault('kml', {})['tema'] = theme
    
    # Modo batch
    if not interactive or batch_file:
        if not batch_file:
            click.echo("💥 Error: --batch-file requerido para modo batch", err=True)
            raise click.Abort()
        
        _execute_batch_mode(ctx, batch_file, name, output_path, validate_only)
        return
    
    # Modo interactivo
    _execute_interactive_mode(ctx, name, output_path)

def _execute_interactive_mode(ctx: TZContext, name: Optional[str], output_path: Path):
    """Ejecuta modo manual interactivo estándar"""
    
    if not ctx.quiet:
        click.echo("🔧 Iniciando modo manual interactivo...")
        click.echo("📍 Podrás agregar antenas/puntos paso a paso")
        click.echo("💡 Usa Ctrl+C en cualquier momento para cancelar")
    
    try:
        # Preparar override de nombre si especificado
        if name:
            # TODO: Implementar override para _modo_manual() con nombre predefinido
            ctx.config.setdefault('manual', {})['nombre_caso'] = name
        
        # Preparar override de directorio salida
        # TODO: Implementar override para seleccionar_carpeta() en _modo_manual()
        ctx.output_dir = str(output_path)
        
        # Ejecutar función original
        from script_principal_bitacoras_refactory import _modo_manual
        _modo_manual()
        
        if not ctx.quiet:
            click.echo("✅ Modo manual completado exitosamente")
            
    except KeyboardInterrupt:
        click.echo("\n⏹️  Modo manual cancelado por usuario")
        raise click.Abort()
    except Exception as e:
        click.echo(f"💥 Error en modo manual: {e}", err=True)
        if ctx.verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()

def _execute_batch_mode(ctx: TZContext, batch_file: str, name: Optional[str], 
                        output_path: Path, validate_only: bool):
    """Ejecuta modo batch desde archivo JSON/CSV"""
    
    batch_path = Path(batch_file)
    
    if not ctx.quiet:
        click.echo(f"📂 Cargando registros batch desde: {batch_path.name}")
    
    # Cargar registros según formato
    try:
        if batch_path.suffix.lower() == '.json':
            registros = _load_json_batch(batch_path)
        elif batch_path.suffix.lower() in ['.csv', '.tsv']:
            registros = _load_csv_batch(batch_path)
        else:
            click.echo(f"💥 Error: Formato no soportado: {batch_path.suffix}", err=True)
            raise click.Abort()
            
    except Exception as e:
        click.echo(f"💥 Error cargando archivo batch: {e}", err=True)
        raise click.Abort()
    
    if not registros:
        click.echo("⚠️  Archivo batch vacío o sin registros válidos", err=True)
        raise click.Abort()
    
    if not ctx.quiet:
        click.echo(f"✅ Cargados {len(registros)} registros")
    
    # Validar registros
    errores = _validate_batch_records(registros)
    if errores:
        click.echo(f"💥 Errores de validación en registros:", err=True)
        for i, error in enumerate(errores[:5]):  # Mostrar máximo 5
            click.echo(f"   {i+1}. {error}", err=True)
        if len(errores) > 5:
            click.echo(f"   ... y {len(errores)-5} errores más", err=True)
        raise click.Abort()
    
    if not ctx.quiet:
        click.echo("✅ Validación de registros exitosa")
    
    # Solo validación
    if validate_only:
        click.echo("🔍 Validación completada - archivo batch correcto")
        return
    
    # Generar KML/KMZ desde registros batch
    try:
        _generate_from_batch(ctx, registros, name, output_path)
        
        if not ctx.quiet:
            click.echo("✅ KML/KMZ generado exitosamente desde batch")
            
    except Exception as e:
        click.echo(f"💥 Error generando desde batch: {e}", err=True)
        if ctx.verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()

def _load_json_batch(batch_path: Path) -> List[Dict[str, Any]]:
    """Carga registros desde archivo JSON"""
    with open(batch_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'registros' in data:
        return data['registros']
    else:
        raise ValueError("Formato JSON inválido - esperado lista o {registros: [...]}")

def _load_csv_batch(batch_path: Path) -> List[Dict[str, Any]]:
    """Carga registros desde archivo CSV/TSV"""
    delimiter = '\t' if batch_path.suffix.lower() == '.tsv' else ','
    
    registros = []
    with open(batch_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            # Convertir campos numéricos
            if 'lat' in row:
                row['lat'] = float(row['lat'])
            if 'lon' in row or 'long' in row:
                lon_key = 'lon' if 'lon' in row else 'long'
                row['lon'] = float(row[lon_key])
            
            registros.append(row)
    
    return registros

def _validate_batch_records(registros: List[Dict[str, Any]]) -> List[str]:
    """Valida registros batch y retorna lista de errores"""
    errores = []
    
    for i, registro in enumerate(registros):
        # Campos requeridos
        if 'antena' not in registro or not registro['antena']:
            errores.append(f"Registro {i+1}: Campo 'antena' requerido")
        
        if 'lat' not in registro:
            errores.append(f"Registro {i+1}: Campo 'lat' requerido")
        else:
            try:
                lat = float(registro['lat'])
                if not (-90 <= lat <= 90):
                    errores.append(f"Registro {i+1}: Latitud fuera de rango [-90, 90]: {lat}")
            except (ValueError, TypeError):
                errores.append(f"Registro {i+1}: Latitud inválida: {registro['lat']}")
        
        lon_key = 'lon' if 'lon' in registro else 'long'
        if lon_key not in registro:
            errores.append(f"Registro {i+1}: Campo 'lon' o 'long' requerido")
        else:
            try:
                lon = float(registro[lon_key])
                if not (-180 <= lon <= 180):
                    errores.append(f"Registro {i+1}: Longitud fuera de rango [-180, 180]: {lon}")
            except (ValueError, TypeError):
                errores.append(f"Registro {i+1}: Longitud inválida: {registro[lon_key]}")
    
    return errores

def _generate_from_batch(ctx: TZContext, registros: List[Dict[str, Any]], 
                        name: Optional[str], output_path: Path):
    """Genera KML/KMZ desde registros batch validados"""
    
    # TODO: Implementar generación KML/KMZ desde registros estructurados
    # usando funciones modulares de tz_kml package
    
    if not ctx.quiet:
        click.echo("🚧 Generación desde batch en desarrollo - usando modo manual estándar")
    
    # Por ahora, delegar a modo manual interactivo
    # En Sprint 3.3 se implementará generación directa
    _execute_interactive_mode(ctx, name, output_path)

def _generate_batch_template(ctx: TZContext, output_dir: Optional[str]):
    """Genera archivo template para modo batch"""
    
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path.cwd()
    
    # Template JSON
    template_json = {
        "registros": [
            {
                "antena": "Antena_Ejemplo_1",
                "lat": 19.4326,
                "lon": -99.1332,
                "detalle": "Descripción detallada de la antena",
                "alias": "Alias opcional",
                "usuario": "Nombre usuario",
                "abonado": "Número abonado",
                "celda": "Celda técnica",
                "lac": "LAC código",
                "interaccion": "Tipo interacción",
                "tel_contacto": "Teléfono contacto",
                "duracion": 120
            },
            {
                "antena": "Antena_Ejemplo_2", 
                "lat": 19.4330,
                "lon": -99.1340,
                "detalle": "Segunda antena de ejemplo"
            }
        ]
    }
    
    # Template CSV  
    template_csv = [
        ["antena", "lat", "lon", "detalle", "alias", "usuario"],
        ["Antena_Ejemplo_1", "19.4326", "-99.1332", "Descripción detallada", "Alias1", "Usuario1"],
        ["Antena_Ejemplo_2", "19.4330", "-99.1340", "Segunda antena", "Alias2", "Usuario2"]
    ]
    
    # Escribir templates
    json_path = output_path / "template_manual.json"
    csv_path = output_path / "template_manual.csv"
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(template_json, f, indent=2, ensure_ascii=False)
    
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(template_csv)
    
    if not ctx.quiet:
        click.echo("📝 Templates generados:")
        click.echo(f"   📄 JSON: {json_path}")
        click.echo(f"   📊 CSV: {csv_path}")
        click.echo("\n💡 Edita los templates con tus datos y usa:")
        click.echo(f"   tzanalysis manual --batch --batch-file {json_path.name}")
        click.echo(f"   tzanalysis manual --batch --batch-file {csv_path.name}")