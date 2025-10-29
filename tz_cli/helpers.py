"""
tz_cli.helpers - HELPERS DE INPUT Y PROMPTS EXTRAÍDOS
====================================================

✅ ESTADO: SPRINT 3A - HELPERS IO EXTRAÍDOS DEL MONOLITO
🎯 PROPÓSITO: Centralizar helpers de input, validación y prompts
📍 DIFERENCIACIÓN: Funciones puras de input/output sin lógica negocio

RESPONSABILIDADES ESPECÍFICAS:
- input_str(), input_float(), input_int(): Helpers entrada datos manual
- bitacora_type_prompt(): Confirmación tipo IMEI/TEL
- output_name_prompt(): Prompt nombre archivos salida
- time_filters_prompt(): Solicitud filtros temporales
- Validación y sanitización entrada usuario

FUNCIONES EXTRAÍDAS:
- _input_str(), _input_float(), _input_int() de _modo_manual() L4743-L4780
- Prompts tipo bitácora L6479-L6487
- Prompts nombres salida L6665-L6677
- Filtros tiempo de _solicitar_filtros_tiempo() L6985-L7024

CARACTERÍSTICAS:
- Funciones puras sin side effects
- Validación robusta entrada usuario
- Mensajes error user-friendly
- Compatibilidad completa con monolito

FECHA EXTRACCIÓN: 29 octubre 2025 - Sprint 3A Fase 3A.3
"""

import re
import logging
from typing import Optional, Union, Dict, Any
from datetime import datetime

def log(message):
    """Helper logging compatible con monolito"""
    logging.info(message)

def input_str(msg: str, obligatorio: bool = False, maxlen: Optional[int] = None) -> str:
    """
    Helper entrada string con validación (extraído de _modo_manual)
    
    Args:
        msg: Mensaje prompt
        obligatorio: Si True, no permite string vacío
        maxlen: Longitud máxima (None = sin límite)
        
    Returns:
        str: String ingresado y validado
    """
    while True:
        resp = input(msg).strip()
        
        if not resp and obligatorio:
            print("  [QC] Este campo es obligatorio.")
            continue
            
        if maxlen and len(resp) > maxlen:
            print(f"  [QC] Máximo {maxlen} caracteres. Reingresa.")
            continue
            
        return resp

def input_float(msg: str, obligatorio: bool = False) -> Optional[float]:
    """
    Helper entrada float con validación (extraído de _modo_manual)
    
    Args:
        msg: Mensaje prompt
        obligatorio: Si True, no permite valor vacío
        
    Returns:
        float: Valor ingresado o None si vacío (y no obligatorio)
    """
    while True:
        resp = input(msg).strip()
        
        if not resp:
            if obligatorio:
                print("  [QC] Este campo es obligatorio.")
                continue
            return None
            
        try:
            return float(resp)
        except ValueError:
            print("  [QC] Debe ser un número válido (ej: 19.4326).")

def input_int(msg: str, obligatorio: bool = False, minv: Optional[int] = None, 
              maxv: Optional[int] = None) -> Optional[int]:
    """
    Helper entrada int con validación (extraído de _modo_manual)
    
    Args:
        msg: Mensaje prompt
        obligatorio: Si True, no permite valor vacío
        minv: Valor mínimo permitido
        maxv: Valor máximo permitido
        
    Returns:
        int: Valor ingresado o None si vacío (y no obligatorio)
    """
    while True:
        resp = input(msg).strip()
        
        if not resp:
            if obligatorio:
                print("  [QC] Este campo es obligatorio.")
                continue
            return None
            
        try:
            val = int(resp)
            
            if minv is not None and val < minv:
                print(f"  [QC] Valor mínimo: {minv}")
                continue
                
            if maxv is not None and val > maxv:
                print(f"  [QC] Valor máximo: {maxv}")
                continue
                
            return val
            
        except ValueError:
            print("  [QC] Debe ser un número entero.")

def bitacora_type_prompt() -> str:
    """
    Prompt tipo bitácora (extraído de L6479-L6487)
    
    Returns:
        str: "IMEI", "TEL", o "AUTO"
    """
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

def output_name_prompt(base_auto: str) -> str:
    """
    Prompt nombre base archivos (extraído de L6665-L6677)
    
    Args:
        base_auto: Nombre sugerido automáticamente
        
    Returns:
        str: Nombre base validado
    """
    print("Si desea cambiar el nombre base, escríbalo ahora (solo base, sin extensión).")
    resp = input(f"Nombre base del KML (Enter = {base_auto}): ").strip()
    nombre_salida = (resp or base_auto)

    # Validar que no sea color hex por error
    if re.fullmatch(r'#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?', resp or ''):
        print("Eso parece un color hex, no un nombre de archivo. Usaré el sugerido.")
        return base_auto

    # Sanitizar nombre si hay respuesta
    if resp:
        # Importar función sanitizadora del monolito
        try:
            import script_principal_bitacoras_refactory as script
            return script._sanear_nombre_archivo_local(resp)
        except:
            # Fallback sanitización básica
            return re.sub(r'[<>:"/\\|?*]', '_', resp)
    
    return base_auto

def time_filters_prompt() -> Dict[str, Any]:
    """
    Prompt filtros temporales (extraído de _solicitar_filtros_tiempo)
    
    Returns:
        Dict: Configuración filtros temporales
    """
    filtros = {}
    
    print("\n[QC] === FILTROS TEMPORALES ===")
    print("Configurar filtros para procesar solo datos de ciertos períodos:")
    print()
    
    # Tipo de filtro
    print("Tipos de filtro disponibles:")
    print("[1] Por día específico")
    print("[2] Por rango de días")
    print("[3] Por rango de horas en día específico")
    print("[4] Sin filtros (procesar todo)")
    
    tipo = input("→ Tipo de filtro (1/2/3/4, Enter=4): ").strip() or "4"
    
    if tipo == "1":
        # Día específico
        fecha_str = input("→ Fecha (YYYY-MM-DD o DD/MM/YYYY): ").strip()
        if fecha_str:
            filtros['tipo'] = 'dia_especifico'
            filtros['fecha'] = fecha_str
            
    elif tipo == "2":
        # Rango días
        fecha_inicio = input("→ Fecha inicio (YYYY-MM-DD): ").strip()
        fecha_fin = input("→ Fecha fin (YYYY-MM-DD): ").strip()
        if fecha_inicio and fecha_fin:
            filtros['tipo'] = 'rango_dias'
            filtros['fecha_inicio'] = fecha_inicio
            filtros['fecha_fin'] = fecha_fin
            
    elif tipo == "3":
        # Rango horas en día
        fecha_str = input("→ Fecha (YYYY-MM-DD): ").strip()
        hora_inicio = input("→ Hora inicio (HH:MM): ").strip()
        hora_fin = input("→ Hora fin (HH:MM): ").strip()
        if fecha_str and hora_inicio and hora_fin:
            filtros['tipo'] = 'rango_horas'
            filtros['fecha'] = fecha_str
            filtros['hora_inicio'] = hora_inicio
            filtros['hora_fin'] = hora_fin
    else:
        # Sin filtros
        filtros['tipo'] = 'sin_filtros'
    
    return filtros

def confirm_yn(mensaje: str, default_si: bool = False) -> bool:
    """
    Helper confirmación S/N
    
    Args:
        mensaje: Mensaje de confirmación
        default_si: Si True, Enter = Sí; si False, Enter = No
        
    Returns:
        bool: True si confirmó, False si canceló
    """
    sufijo = " (S/n)" if default_si else " (s/N)"
    resp = input(f"{mensaje}{sufijo}: ").strip().lower()
    
    if not resp:
        return default_si
    
    return resp in ('s', 'si', 'sí', 'y', 'yes')

def sanitize_filename(filename: str) -> str:
    """
    Sanitización básica nombres archivo
    
    Args:
        filename: Nombre archivo original
        
    Returns:
        str: Nombre sanitizado
    """
    # Remover caracteres problemáticos para nombres archivo
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Limitar longitud
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    # Remover espacios inicio/fin y múltiples espacios
    sanitized = re.sub(r'\s+', ' ', sanitized.strip())
    
    return sanitized

def validate_date_input(date_str: str) -> Optional[datetime]:
    """
    Validación entrada fechas con formatos múltiples
    
    Args:
        date_str: String fecha ingresado
        
    Returns:
        datetime: Fecha parseada o None si inválida
    """
    if not date_str:
        return None
    
    # Formatos soportados
    formatos = [
        "%Y-%m-%d",      # 2024-10-29
        "%d/%m/%Y",      # 29/10/2024
        "%d-%m-%Y",      # 29-10-2024
        "%Y/%m/%d",      # 2024/10/29
    ]
    
    for formato in formatos:
        try:
            return datetime.strptime(date_str, formato)
        except ValueError:
            continue
    
    return None

def validate_time_input(time_str: str) -> bool:
    """
    Validación entrada horas HH:MM
    
    Args:
        time_str: String hora formato HH:MM
        
    Returns:
        bool: True si válida, False si inválida
    """
    if not time_str:
        return False
    
    try:
        # Validar formato HH:MM
        parts = time_str.split(':')
        if len(parts) != 2:
            return False
        
        horas, minutos = int(parts[0]), int(parts[1])
        return 0 <= horas <= 23 and 0 <= minutos <= 59
        
    except (ValueError, IndexError):
        return False

def format_file_list_preview(base_name: str) -> str:
    """
    Formatea lista archivos que se generarán
    
    Args:
        base_name: Nombre base archivos
        
    Returns:
        str: Lista formateada para mostrar al usuario
    """
    files = [
        f"{base_name}_informe.html",
        f"{base_name}_mapeo.kmz", 
        f"{base_name}_hashes.txt",
        f"{base_name}_errores.txt"
    ]
    
    lines = ["Se generarán estos archivos:"]
    for file in files:
        lines.append(f"  - {file}")
    
    return "\n".join(lines)

def show_processing_summary(opcion: str, archivo: str, hoja: str, 
                           carpeta: str, nombre: str):
    """
    Muestra resumen configuración antes de procesar
    
    Args:
        opcion: Modo seleccionado ("1", "2", "3")
        archivo: Archivo entrada
        hoja: Hoja Excel
        carpeta: Carpeta destino
        nombre: Nombre base archivos
    """
    modo_nombres = {
        "1": "Bitácora completa",
        "2": "Por tiempo (filtrado)",
        "3": "Manual"
    }
    
    print("\n" + "="*50)
    print("RESUMEN DE CONFIGURACIÓN")
    print("="*50)
    print(f"Modo: {modo_nombres.get(opcion, opcion)}")
    print(f"Archivo: {archivo}")
    if hoja:
        print(f"Hoja: {hoja}")
    print(f"Carpeta destino: {carpeta}")
    print(f"Nombre base: {nombre}")
    print("="*50)

# Aliases para compatibilidad con monolito
_input_str = input_str
_input_float = input_float  
_input_int = input_int