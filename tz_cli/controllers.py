"""
tz_cli.controllers - CONTROLADORES MENÚ ↔ LÓGICA CORE
====================================================

✅ ESTADO: SPRINT 3A - CONTROLLERS BRIDGE MENÚ/NEGOCIO
🎯 PROPÓSITO: Conectar menús extraídos con lógica core existente
📍 DIFERENCIACIÓN: Bridge layer sin cambiar lógica negocio original

RESPONSABILIDADES ESPECÍFICAS:
- handle_manual_mode(): Controller para _modo_manual() completo
- handle_file_selection(): Controller selección archivos/hojas
- handle_theme_selection(): Controller configuración colores  
- handle_output_setup(): Controller nombres/carpetas salida
- Preservar variables globales y contexto exacto

INTEGRACIÓN:
- Menús llaman controllers con parámetros simples
- Controllers llaman funciones originales del monolito
- Variables globales preservadas (CONFIG, df, etc.)
- Zero cambios en lógica de negocio core

FUNCIONES BRIDGEADAS:
- _modo_manual() → handle_manual_mode()
- seleccionar_archivo() → handle_file_selection()
- _solicitar_color_tema() → handle_theme_selection()
- Flujos selección carpeta/nombres → handle_output_setup()

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3A Fase 3A.3
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List

def log(message):
    """Helper logging compatible con monolito"""
    logging.info(message)

def handle_manual_mode() -> bool:
    """
    Controller para modo manual completo
    
    Ejecuta _modo_manual() del monolito preservando:
    - Flujo completo interactivo
    - Variables globales CONFIG
    - Generación KML/KMZ
    - Logging y contexto
    
    Returns:
        bool: True si completó exitosamente, False si canceló
    """
    try:
        # Import dinámico para evitar dependencias circulares
        import script_principal_bitacoras_refactory as script
        
        # Ejecutar función original del monolito
        script._modo_manual()
        
        # Si llegó aquí, fue exitoso (no canceló)
        return True
        
    except Exception as e:
        log(f"Error en modo manual: {e}")
        print(f"[ERROR] Error en modo manual: {e}")
        return False

def handle_file_selection() -> Optional[str]:
    """
    Controller para selección archivo entrada
    
    Delega a seleccionar_archivo() del monolito preservando:
    - Dialog nativo del SO
    - Validaciones archivo
    - Logging selección
    
    Returns:
        str: Path archivo seleccionado o None si canceló
    """
    try:
        from utilidades import seleccionar_archivo
        
        log("Iniciando selección de archivo de entrada...")
        archivo_entrada = seleccionar_archivo()
        
        if not archivo_entrada:
            log("ERROR: Usuario no seleccionó archivo, terminando ejecución")
            print("No se seleccionó un archivo. Saliendo.")
            return None
        
        log(f"Archivo seleccionado exitosamente: {archivo_entrada}")
        return archivo_entrada
        
    except Exception as e:
        log(f"Error seleccionando archivo: {e}")
        print(f"[ERROR] Error seleccionando archivo: {e}")
        return None

def handle_sheet_selection(archivo_entrada: str) -> Optional[str]:
    """
    Controller para selección hoja Excel
    
    Args:
        archivo_entrada: Path archivo Excel
        
    Returns:
        str/int: Hoja seleccionada o None si error
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        log("Iniciando selección de hoja de Excel...")
        hoja = script._seleccionar_hoja_visible(archivo_entrada)
        log(f"Hoja seleccionada: {hoja}")
        
        return hoja
        
    except Exception as e:
        log(f"Error seleccionando hoja: {e}")
        print(f"[ERROR] Error seleccionando hoja: {e}")
        return None

def handle_theme_selection(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Controller para configuración tema colores
    
    Args:
        config: CONFIG global actual
        
    Returns:
        Dict: CONFIG actualizado con tema seleccionado
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        log("Solicitando configuración de tema de colores...")
        updated_config = script._solicitar_color_tema(config)
        log("Configuración de colores completada")
        
        return updated_config
        
    except Exception as e:
        log(f"Error configurando tema: {e}")
        print(f"[ERROR] Error configurando tema: {e}")
        return config

def handle_output_setup() -> Tuple[Optional[str], Optional[str]]:
    """
    Controller para selección carpeta y configuración salida
    
    Returns:
        tuple: (carpeta_base, carpeta_salida) o (None, None) si error
    """
    try:
        from utilidades import seleccionar_carpeta
        
        log("Iniciando selección de carpeta de salida...")
        
        # Selección carpeta base
        try:
            carpeta_base = seleccionar_carpeta()
        except Exception:
            carpeta_base = None
            
        if not carpeta_base:
            carpeta_base = os.getcwd()
            
        log(f"Carpeta destino seleccionada: {carpeta_base}")
        print(f"[QC] Carpeta destino: {carpeta_base}")
        
        return (carpeta_base, carpeta_base)
        
    except Exception as e:
        log(f"Error configurando salida: {e}")
        print(f"[ERROR] Error configurando salida: {e}")
        return (None, None)

def handle_bitacora_type_prompt() -> str:
    """
    Controller para confirmación tipo bitácora (IMEI/TEL)
    
    Returns:
        str: "IMEI", "TEL", o "AUTO"
    """
    try:
        print("\n[QC] Confirmar si esta bitácora es por número de Teléfono o IMEI para nombrar archivos")
        print("I = IMEI")
        print("T = Número telefónico")
        print("Enter = Que TZ Analyzer decida")
        tipo_bitacora = input("→ Opción (I/T/Enter): ").strip().upper() or ""
        
        if tipo_bitacora == "I":
            return "IMEI"
        elif tipo_bitacora == "T":
            return "TEL"
        else:
            return "AUTO"
            
    except Exception as e:
        log(f"Error en prompt tipo bitácora: {e}")
        return "AUTO"

def handle_output_name_prompt(base_auto: str) -> str:
    """
    Controller para prompt nombre base archivos salida
    
    Args:
        base_auto: Nombre sugerido automáticamente
        
    Returns:
        str: Nombre base final para archivos
    """
    try:
        import re
        import script_principal_bitacoras_refactory as script
        
        print("Si desea cambiar el nombre base, escríbalo ahora (solo base, sin extensión).")
        resp = input(f"Nombre base del KML (Enter = {base_auto}): ").strip()
        nombre_salida = (resp or base_auto)

        if re.fullmatch(r'#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?', resp or ''):
            print("Eso parece un color hex, no un nombre de archivo. Usaré el sugerido.")
            resp = ""

        nombre_salida = script._sanear_nombre_archivo_local(resp) if resp else base_auto
        return nombre_salida
        
    except Exception as e:
        log(f"Error en prompt nombre: {e}")
        return base_auto

def handle_load_excel_with_normalization(archivo_entrada: str, hoja) -> Tuple[Any, str]:
    """
    Controller para carga Excel con normalización
    
    Args:
        archivo_entrada: Path archivo Excel
        hoja: Hoja seleccionada
        
    Returns:
        tuple: (dataframe, hoja_usada) o raises Exception
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        log(f"Iniciando carga de datos desde {archivo_entrada}...")
        df, hoja_usada = script._cargar_excel_con_normalizacion(archivo_entrada, hoja)
        log(f"Excel cargado exitosamente: {len(df)} filas, hoja usada: {hoja_usada}")
        
        return (df, hoja_usada)
        
    except Exception as e:
        log(f"ERROR CRÍTICO al cargar Excel: {type(e).__name__}: {e}")
        print(f"Error al leer el Excel: {e}")
        raise

def handle_time_filters() -> Dict[str, Any]:
    """
    Controller para solicitar filtros temporales (modo 2)
    
    Returns:
        Dict: Filtros temporales configurados
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        log("Solicitando filtros temporales...")
        filtros = script._solicitar_filtros_tiempo()
        log(f"Filtros temporales configurados: {filtros}")
        
        return filtros
        
    except Exception as e:
        log(f"Error configurando filtros tiempo: {e}")
        print(f"[ERROR] Error configurando filtros tiempo: {e}")
        return {}

def handle_apply_time_filters(df, filtros: Dict[str, Any]):
    """
    Controller para aplicar filtros temporales al DataFrame
    
    Args:
        df: DataFrame original
        filtros: Filtros temporales a aplicar
        
    Returns:
        DataFrame: DataFrame filtrado
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        log("Aplicando filtros temporales...")
        df_filtrado = script._aplicar_filtros_tiempo(df, filtros)
        log(f"Filtros aplicados: {len(df_filtrado)} filas resultantes")
        
        return df_filtrado
        
    except Exception as e:
        log(f"Error aplicando filtros tiempo: {e}")
        print(f"[ERROR] Error aplicando filtros tiempo: {e}")
        return df

def get_global_context():
    """
    Helper para acceder variables globales del monolito
    
    Returns:
        Dict: Variables globales relevantes (CONFIG, etc.)
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        context = {}
        
        # CONFIG global
        if hasattr(script, 'CONFIG'):
            context['CONFIG'] = script.CONFIG
        
        # Variables de sesión si existen
        for var_name in ['nombre_salida', 'hoja', 'archivo_errores']:
            if hasattr(script, var_name):
                context[var_name] = getattr(script, var_name)
                
        return context
        
    except Exception as e:
        log(f"Error accediendo contexto global: {e}")
        return {}

def set_global_context(context: Dict[str, Any]):
    """
    Helper para actualizar variables globales del monolito
    
    Args:
        context: Dict con variables a actualizar
    """
    try:
        import script_principal_bitacoras_refactory as script
        
        # Actualizar CONFIG
        if 'CONFIG' in context:
            script.CONFIG = context['CONFIG']
        
        # Actualizar variables de sesión
        for var_name, value in context.items():
            if var_name != 'CONFIG' and hasattr(script, var_name):
                setattr(script, var_name, value)
                
    except Exception as e:
        log(f"Error actualizando contexto global: {e}")

# Aliases para compatibilidad
manual_mode_controller = handle_manual_mode
file_selection_controller = handle_file_selection
theme_selection_controller = handle_theme_selection