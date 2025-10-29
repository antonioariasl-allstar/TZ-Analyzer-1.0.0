"""
tz_cli_click.commands.info - COMANDO TZANALYSIS INFO  
====================================================

✅ ESTADO: SPRINT 3B - COMANDO INFO SISTEMA (CORREGIDO)
🎯 PROPÓSITO: Información sistema, versión, dependencias
📍 DIFERENCIACIÓN: Diagnóstico CLI vs funcionalidad core

COMANDO: tzanalysis info [OPTIONS]

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

import click
import sys
import platform

@click.command()
@click.option('--version', is_flag=True, help='Mostrar solo versión')
@click.option('--system', is_flag=True, help='Información sistema')
@click.option('--dependencies', is_flag=True, help='Estado dependencias')
@click.pass_context
def info_command(ctx, version: bool, system: bool, dependencies: bool):
    """
    Mostrar información del sistema TZ Analyzer.
    
    EJEMPLOS:
      tzanalysis info                    # Info completa
      tzanalysis info --version          # Solo versión
      tzanalysis info --dependencies     # Estado módulos
    """
    
    if version:
        click.echo("TZ Analyzer CLI v1.0.0")
        return
    
    # Info completa por default si no flags específicos
    if not (system or dependencies):
        system = dependencies = True
    
    click.echo("*** TZ ANALYZER - INFORMACION SISTEMA")
    click.echo("=" * 40)
    
    # Información versión
    click.echo(f"📋 Versión: TZ Analyzer CLI v1.0.0")
    click.echo(f"🐍 Python: {sys.version.split()[0]}")
    click.echo(f">> Sprint: 3B (CLI Click moderno)")
    
    if system:
        click.echo(f"\n*** SISTEMA:")
        click.echo(f"   OS: {platform.system()} {platform.release()}")
        click.echo(f"   Arquitectura: {platform.machine()}")
    
    if dependencies:
        click.echo(f"\n*** DEPENDENCIAS:")
        
        deps_status = []
        try:
            import click as click_module
            deps_status.append(f"   [OK] Click: {click_module.__version__}")
        except (ImportError, AttributeError):
            deps_status.append(f"   [ERR] Click: Error version")
            
        try:
            import pandas as pd
            deps_status.append(f"   [OK] Pandas: {pd.__version__}")
        except ImportError:
            deps_status.append(f"   [ERR] Pandas: No disponible")
            
        try:
            import openpyxl
            deps_status.append(f"   [OK] OpenPyXL: {openpyxl.__version__}")
        except ImportError:
            deps_status.append(f"   [ERR] OpenPyXL: No disponible")
            
        for status in deps_status:
            click.echo(status)
    
    # Módulos TZ internos
    click.echo(f"\n*** MODULOS TZ:")
    
    modules_status = []
    try:
        from script_principal_bitacoras_refactory import CONFIG
        modules_status.append("   [OK] Monolito principal: Disponible")
    except ImportError:
        modules_status.append("   [ERR] Monolito principal: Error import")
    
    try:
        from tz_cli.menu import main_menu
        modules_status.append("   [OK] tz_cli (menu interactivo): Disponible")
    except ImportError:
        modules_status.append("   [ERR] tz_cli: No disponible")
        
    for status in modules_status:
        click.echo(status)
    
    # Información del contexto (simplificada)
    try:
        tz_ctx = ctx.obj
        if tz_ctx and hasattr(tz_ctx, 'config') and len(tz_ctx.config) > 0:
            click.echo(f"\n*** CONFIGURACION:")
            click.echo(f"   Secciones cargadas: {len(tz_ctx.config)}")
        else:
            click.echo(f"\n!!! CONFIGURACION: No cargada")
    except Exception:
        click.echo(f"\n!!! CONFIGURACION: Error acceso contexto")