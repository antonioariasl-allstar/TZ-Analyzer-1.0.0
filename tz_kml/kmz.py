"""
tz_kml.kmz - Empaquetado y Guardado KML/KMZ

Funciones para guardar archivos KML y empaquetar como KMZ con configuración flexible.
Extracción de lógica de guardado desde generar_kml del monolito.

Sprint 2 Fase 2.3: KMZ Packaging  
Compatibilidad 100% con comportamiento de guardado existente

Funcionalidades:
- Guardado KML opcional (controlado por solo_kmz)
- Empaquetado KMZ siempre junto al archivo base
- Manejo robusto de errores con logging
- Soporte para rutas absolutas y relativas
- Preservación de estructura de carpetas

Configuración típica:
- CONFIG["salida"]["solo_kmz"] = True: Solo genera KMZ, omite KML
- CONFIG["salida"]["solo_kmz"] = False: Genera tanto KML como KMZ

Funciones:
- save_kml_kmz: Guardado principal con configuración automática
- save_kml_only: Guarda solo archivo KML
- save_kmz_only: Guarda solo archivo KMZ  
- get_kmz_path: Calcula ruta KMZ desde ruta KML
- is_solo_kmz_enabled: Verifica configuración solo_kmz

Fecha: 29 octubre 2025
"""

import os
import logging
from typing import Dict, Any, Tuple, Optional
import simplekml as sk


def get_kmz_path(archivo_kml: str) -> str:
    """
    Calcula ruta del archivo KMZ basado en la ruta KML.
    
    Args:
        archivo_kml: Ruta del archivo KML (ej: "salida/datos.kml")
        
    Returns:
        str: Ruta del archivo KMZ (ej: "salida/datos.kmz")
        
    Preserva directorio y nombre base, solo cambia extensión.
    
    Extracción de:
    - L1283: kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
    - L1653: kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
    """
    return os.path.splitext(archivo_kml)[0] + ".kmz"


def is_solo_kmz_enabled(config: Dict[str, Any]) -> bool:
    """
    Verifica si está habilitado el modo "solo KMZ" en configuración.
    
    Args:
        config: Diccionario de configuración (CONFIG global)
        
    Returns:
        bool: True si solo se debe generar KMZ, False si también KML
        
    Lee: config["salida"]["solo_kmz"] con fallback a False
    
    Extracción de:
    - L1272: solo_kmz = bool(CONFIG.get("salida", {}).get("solo_kmz", False))
    - L1647: solo_kmz = bool(CONFIG.get("salida", {}).get("solo_kmz", False))
    """
    try:
        return bool(config.get("salida", {}).get("solo_kmz", False))
    except Exception:
        return False


def save_kml_only(kml: sk.Kml, archivo_kml: str, silent_errors: bool = False) -> bool:
    """
    Guarda solo el archivo KML con manejo robusto de errores.
    
    Args:
        kml: Objeto KML a guardar
        archivo_kml: Ruta donde guardar el archivo KML
        silent_errors: Si True, no imprime errores (para save_kmz_only)
        
    Returns:
        bool: True si guardado exitoso, False si error
        
    Funcionalidad:
    - Crea directorios padre si no existen
    - Logging de errores con traceback
    - Manejo robusto de excepciones
    
    Extracción de:
    - L1276-1281: try/except con logging.error y traceback
    - L1649-1653: try/except silencioso
    """
    try:
        # Crear directorio padre si no existe
        dir_padre = os.path.dirname(archivo_kml)
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)
        
        # Guardar archivo KML
        kml.save(archivo_kml)
        return True
        
    except Exception as e:
        if not silent_errors:
            logging.error(f"Error al guardar KML '{archivo_kml}': {e}")
            import traceback
            traceback.print_exc()
        return False


def save_kmz_only(kml: sk.Kml, archivo_kmz: str, silent_errors: bool = False) -> bool:
    """
    Guarda solo el archivo KMZ con manejo robusto de errores.
    
    Args:
        kml: Objeto KML a empaquetar como KMZ
        archivo_kmz: Ruta donde guardar el archivo KMZ
        silent_errors: Si True, no imprime errores (modo silencioso)
        
    Returns:
        bool: True si guardado exitoso, False si error
        
    Funcionalidad:
    - Crea directorios padre si no existen
    - Empaquetado automático con simplekml.savekmz()
    - Logging de errores con traceback
    - Soporte para modo silencioso
    
    Extracción de:
    - L1283-1288: try/except con logging.error y traceback
    - L1655-1657: try/except silencioso
    """
    try:
        # Crear directorio padre si no existe
        dir_padre = os.path.dirname(archivo_kmz)
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)
        
        # Guardar archivo KMZ
        kml.savekmz(archivo_kmz)
        return True
        
    except Exception as e:
        if not silent_errors:
            logging.error(f"Error al guardar KMZ '{archivo_kmz}': {e}")
            import traceback
            traceback.print_exc()
        return False


def save_kml_kmz(kml: sk.Kml, archivo_kml: str, config: Dict[str, Any], 
                 silent_errors: bool = False) -> Tuple[bool, bool]:
    """
    Guarda KML y/o KMZ según configuración con manejo completo de errores.
    
    Args:
        kml: Objeto KML a guardar
        archivo_kml: Ruta del archivo KML base
        config: Diccionario de configuración (CONFIG global)
        silent_errors: Si True, usa modo silencioso para errores
        
    Returns:
        Tuple[bool, bool]: (kml_guardado, kmz_guardado)
        
    Comportamiento:
    - Si solo_kmz=True: Solo guarda KMZ, omite KML
    - Si solo_kmz=False: Guarda tanto KML como KMZ
    - KMZ siempre se guarda junto al archivo base
    - Manejo independiente de errores para cada archivo
    
    Funcionalidad completa:
    - Determina automáticamente ruta KMZ desde ruta KML
    - Respeta configuración solo_kmz
    - Crea directorios padre según necesidad
    - Logging detallado de operaciones y errores
    - Retorna estado de guardado para cada formato
    
    Extracción de:
    - L1272-1289: Lógica completa modo flat
    - L1647-1657: Lógica completa modo carpetas
    """
    solo_kmz = is_solo_kmz_enabled(config)
    kmz_path = get_kmz_path(archivo_kml)
    
    kml_guardado = False
    kmz_guardado = False
    
    # 1. Guardar KML solo si NO está activado solo_kmz
    if not solo_kmz:
        kml_guardado = save_kml_only(kml, archivo_kml, silent_errors)
    else:
        kml_guardado = True  # No se requiere, marcamos como exitoso
    
    # 2. Guardar KMZ siempre (junto al archivo base)
    kmz_guardado = save_kmz_only(kml, kmz_path, silent_errors)
    
    return kml_guardado, kmz_guardado


def save_flat_mode(kml: sk.Kml, archivo_kml: str, config: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Guardado específico para modo flat (sin subcarpetas).
    
    Args:
        kml: Objeto KML en modo plano
        archivo_kml: Ruta del archivo KML base
        config: Diccionario de configuración
        
    Returns:
        Tuple[bool, bool]: (kml_guardado, kmz_guardado)
        
    Modo flat características:
    - KMZ siempre junto al archivo base, sin subcarpetas
    - Comentario en código: "KMZ en misma carpeta; KML opcional"
    - Logging de errores habilitado
    
    Extracción directa de:
    - L1271-1289: === GUARDAR SALIDAS (KMZ en misma carpeta; KML opcional) ===
    """
    return save_kml_kmz(kml, archivo_kml, config, silent_errors=False)


def save_folder_mode(kml: sk.Kml, archivo_kml: str, config: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Guardado específico para modo carpetas (estructura jerárquica).
    
    Args:
        kml: Objeto KML con estructura de carpetas
        archivo_kml: Ruta del archivo KML base
        config: Diccionario de configuración
        
    Returns:
        Tuple[bool, bool]: (kml_guardado, kmz_guardado)
        
    Modo carpetas características:
    - Preserva estructura de directorios
    - Errores silenciosos (try/except pass en original)
    - KMZ junto al archivo base
    
    Extracción directa de:
    - L1647-1657: Guardado al final de estructura por carpetas
    """
    return save_kml_kmz(kml, archivo_kml, config, silent_errors=True)


def validate_kml_path(archivo_kml: str) -> str:
    """
    Valida y normaliza ruta de archivo KML.
    
    Args:
        archivo_kml: Ruta del archivo KML a validar
        
    Returns:
        str: Ruta normalizada y validada
        
    Raises:
        ValueError: Si la ruta es inválida o no tiene extensión .kml
        
    Validaciones:
    - Ruta no vacía
    - Extensión .kml
    - Directorio padre accesible
    """
    if not archivo_kml or not isinstance(archivo_kml, str):
        raise ValueError("Ruta de archivo KML es requerida y debe ser string")
    
    archivo_kml = archivo_kml.strip()
    if not archivo_kml:
        raise ValueError("Ruta de archivo KML no puede estar vacía")
    
    # Verificar extensión
    if not archivo_kml.lower().endswith('.kml'):
        raise ValueError(f"Archivo debe tener extensión .kml: {archivo_kml}")
    
    # Normalizar ruta
    archivo_kml = os.path.normpath(archivo_kml)
    
    # Verificar que el directorio padre sea válido
    dir_padre = os.path.dirname(archivo_kml)
    if dir_padre:
        try:
            os.makedirs(dir_padre, exist_ok=True)
        except Exception as e:
            raise ValueError(f"No se puede crear directorio padre '{dir_padre}': {e}")
    
    return archivo_kml


def get_file_sizes(archivo_kml: str) -> Dict[str, Optional[int]]:
    """
    Obtiene tamaños de archivos KML y KMZ generados.
    
    Args:
        archivo_kml: Ruta del archivo KML base
        
    Returns:
        Dict con tamaños en bytes: {"kml": int|None, "kmz": int|None}
        
    Útil para:
    - Validación post-guardado
    - Logging de estadísticas
    - Verificación de generación exitosa
    """
    kmz_path = get_kmz_path(archivo_kml)
    
    def safe_getsize(path: str) -> Optional[int]:
        try:
            if os.path.exists(path):
                return os.path.getsize(path)
        except Exception:
            pass
        return None
    
    return {
        "kml": safe_getsize(archivo_kml),
        "kmz": safe_getsize(kmz_path)
    }