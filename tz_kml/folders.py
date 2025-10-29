"""
tz_kml.folders - Jerarquía de Carpetas KML

Funciones para crear la estructura de carpetas jerárquica en archivos KML.
Extracción de lógica de generar_kml del monolito con dependencias adaptadas.

Sprint 2 Fase 2.2: Folders + jerarquía
Compatibilidad 100% con estructura KML existente

Estructura típica:
- raiz (nombre archivo)
  ├── todas_las_antenas  
  │   ├── 001-2024-10-01 (por fecha)
  │   ├── 002-2024-10-02
  │   └── ...
  ├── por_rango_horario (opcional)
  │   ├── Mañana (06-12h)
  │   ├── Tarde (12-18h) 
  │   ├── Noche (18-24h)
  │   └── Madrugada (00-06h)
  ├── top_N_las_mas_activadas
  └── top_N_por_rango_horario
      ├── Mañana (06-12h)
      ├── Tarde (12-18h)
      ├── Noche (18-24h)
      └── Madrugada (00-06h)

Funciones:
- create_folder_hierarchy: Crea estructura completa de carpetas
- create_root_folder: Crea carpeta raíz con nombre del archivo
- create_date_folders: Crea carpetas por fecha en orden cronológico  
- create_range_folders: Crea carpetas por rango horario (opcional)
- create_top_folders: Crea carpetas top N global y por rango

Fecha: 29 octubre 2025
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Union
import simplekml as sk


# Configuración de rangos horarios (constante extraída del monolito)
RANGOS_SV = {
    "manana": ("Mañana (06-12h)", 6, 12),
    "tarde": ("Tarde (12-18h)", 12, 18), 
    "noche": ("Noche (18-24h)", 18, 24),
    "madrugada": ("Madrugada (00-06h)", 0, 6),
}


def create_root_folder(kml: sk.Kml, archivo_salida_kml: str) -> Any:
    """
    Crea carpeta raíz con nombre basado en el archivo de salida.
    
    Args:
        kml: Objeto KML donde crear la carpeta
        archivo_salida_kml: Ruta del archivo KML para extraer nombre
        
    Returns:
        Carpeta raíz creada (simplekml.Folder)
        
    Extracción de:
    - L1294: nombre_raiz = os.path.splitext(os.path.basename(archivo_salida_kml))[0]
    - L1295: raiz = kml.newfolder(name=nombre_raiz)
    """
    nombre_raiz = os.path.splitext(os.path.basename(archivo_salida_kml))[0]
    raiz = kml.newfolder(name=nombre_raiz)
    return raiz


def create_date_folders(f_todas: Any, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Crea carpetas por fecha en orden cronológico dentro de 'todas_las_antenas'.
    
    Args:
        f_todas: Carpeta padre 'todas_las_antenas'
        items: Lista de elementos con campo 'fecha'
        
    Returns:
        Dict[str, Any]: Mapeo fecha_str -> Folder
        
    Formato fecha: "001-2024-10-01" (día del año + fecha ISO)
    
    Extracción de:
    - L1299-1307: obtener_carpeta_fecha + folders_por_fecha
    - L1375-1378: fechas_unicas ordenadas cronológicamente
    """
    folders_por_fecha = {}
    
    def obtener_carpeta_fecha(fecha_dt: datetime) -> Any:
        """Helper interno para crear/obtener carpeta por fecha"""
        if isinstance(fecha_dt, str):
            try:
                fecha_dt = datetime.fromisoformat(fecha_dt)
            except Exception:
                try:
                    fecha_dt = datetime.strptime(fecha_dt, "%d/%m/%Y")
                except:
                    fecha_dt = datetime.strptime(fecha_dt, "%Y-%m-%d")
        
        fecha_str = f"{fecha_dt.timetuple().tm_yday:03d}-{fecha_dt.strftime('%Y-%m-%d')}"
        if fecha_str not in folders_por_fecha:
            folders_por_fecha[fecha_str] = f_todas.newfolder(name=fecha_str)
        return folders_por_fecha[fecha_str]
    
    # Crear carpetas en orden cronológico
    try:
        fechas_unicas = sorted({
            datetime.strptime(it["fecha"], "%Y-%m-%d") if "-" in it["fecha"] 
            else datetime.strptime(it["fecha"], "%d/%m/%Y") 
            for it in items
        })
        for fecha in fechas_unicas:
            obtener_carpeta_fecha(fecha)
    except Exception:
        # Fallback: crear según se encuentran
        for item in items:
            try:
                fecha = item.get("fecha", "")
                if fecha and fecha != "Sin Inf.":
                    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d") if "-" in fecha else datetime.strptime(fecha, "%d/%m/%Y")
                    obtener_carpeta_fecha(fecha_dt)
            except Exception:
                continue
    
    return folders_por_fecha


def create_range_folders(raiz: Any, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Crea carpetas por rango horario si está habilitado en configuración.
    
    Args:
        raiz: Carpeta raíz donde crear 'por_rango_horario'
        config: Diccionario de configuración (CONFIG global)
        
    Returns:
        Dict[str, Any] o None: Mapeo rango -> Folder si está habilitado
        
    Controlado por: config["kml"]["incluir_por_rango_horario"]
    
    Extracción de:
    - L1309-1321: incluir_rango + f_rangos + rango_folders
    """
    try:
        incluir_rango = bool(config.get("kml", {}).get("incluir_por_rango_horario", False))
    except Exception:
        incluir_rango = False
    
    if not incluir_rango:
        return None
    
    f_rangos = raiz.newfolder(name="por_rango_horario")
    rango_folders = {
        "manana":    f_rangos.newfolder(name=RANGOS_SV["manana"][0]),
        "tarde":     f_rangos.newfolder(name=RANGOS_SV["tarde"][0]),
        "noche":     f_rangos.newfolder(name=RANGOS_SV["noche"][0]),
        "madrugada": f_rangos.newfolder(name=RANGOS_SV["madrugada"][0]),
    }
    return rango_folders


def create_top_folders(raiz: Any, config: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    """
    Crea carpetas para top N antenas: global y por rango horario.
    
    Args:
        raiz: Carpeta raíz donde crear las carpetas top
        config: Diccionario de configuración (CONFIG global)
        
    Returns:
        Tuple[Any, Dict[str, Any]]: (f_top_global, top_rango_folders)
        
    Top N dinámico:
    - Si existe OVERRIDE_TOPS['antenas']: usa ese valor
    - Sino: config["top_antenas"] o config["html"]["top_antenas_n"] 
    - Default: 3
    - 0 o None = sin límite ("top_las_mas_activadas")
    
    Extracción de:
    - L1323-1341: Top N dinámico con OVERRIDE_TOPS
    - L1342-1351: f_top_global + f_top_por_rango + top_rango_folders
    """
    # Top N dinámico (coincide con HTML)
    try:
        # Verificar si existe OVERRIDE_TOPS global
        import sys
        module = sys.modules.get('__main__')
        override_tops = getattr(module, 'OVERRIDE_TOPS', None) if module else None
        
        if override_tops and isinstance(override_tops, dict) and (override_tops.get('antenas') is not None):
            antenas_val = override_tops.get('antenas')
            topN_ant = int(antenas_val) if antenas_val is not None else 3
        else:
            topN_ant = int(config.get("top_antenas", config.get("html", {}).get("top_antenas_n", 3)))
    except Exception:
        topN_ant = 3
    
    # Nombres de carpetas según límite
    name_top_global = ("top_las_mas_activadas" if (topN_ant is None or topN_ant <= 0) 
                      else f"top_{topN_ant}_las_mas_activadas")
    name_top_por_rango = ("top_por_rango_horario" if (topN_ant is None or topN_ant <= 0)
                         else f"top_{topN_ant}_por_rango_horario")
    
    # Crear carpetas
    f_top_global = raiz.newfolder(name=name_top_global)
    f_top_por_rango = raiz.newfolder(name=name_top_por_rango)
    
    top_rango_folders = {
        "manana":    f_top_por_rango.newfolder(name=RANGOS_SV["manana"][0]),
        "tarde":     f_top_por_rango.newfolder(name=RANGOS_SV["tarde"][0]),
        "noche":     f_top_por_rango.newfolder(name=RANGOS_SV["noche"][0]),
        "madrugada": f_top_por_rango.newfolder(name=RANGOS_SV["madrugada"][0]),
    }
    
    return f_top_global, top_rango_folders


def create_folder_hierarchy(kml: sk.Kml, archivo_salida_kml: str, items: List[Dict[str, Any]], 
                           config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea la jerarquía completa de carpetas KML según configuración.
    
    Args:
        kml: Objeto KML donde crear la estructura
        archivo_salida_kml: Ruta del archivo KML (para nombre raíz)
        items: Lista de elementos a procesar (para fechas)
        config: Diccionario de configuración (CONFIG global)
        
    Returns:
        Dict con todas las carpetas creadas:
        {
            "raiz": sk.Folder,
            "todas": sk.Folder, 
            "por_fecha": Dict[str, sk.Folder],
            "por_rango": Dict[str, sk.Folder] | None,
            "top_global": sk.Folder,
            "top_rango": Dict[str, sk.Folder]
        }
        
    Funcionalidad completa:
    - Carpeta raíz con nombre del archivo
    - Subcarpeta 'todas_las_antenas' con carpetas por fecha
    - Subcarpeta 'por_rango_horario' (opcional según config)
    - Subcarpetas top N global y por rango horario
    
    Extracción de toda la lógica de carpetas de generar_kml (L1294-1351)
    """
    # 1. Carpeta raíz
    raiz = create_root_folder(kml, archivo_salida_kml)
    
    # 2. Carpeta 'todas_las_antenas' con subcarpetas por fecha
    f_todas = raiz.newfolder(name="todas_las_antenas") 
    folders_por_fecha = create_date_folders(f_todas, items)
    
    # 3. Carpetas por rango horario (opcional)
    rango_folders = create_range_folders(raiz, config)
    
    # 4. Carpetas top N global y por rango
    f_top_global, top_rango_folders = create_top_folders(raiz, config)
    
    return {
        "raiz": raiz,
        "todas": f_todas,
        "por_fecha": folders_por_fecha,
        "por_rango": rango_folders,
        "top_global": f_top_global, 
        "top_rango": top_rango_folders
    }


def get_date_folder(folders_por_fecha: Dict[str, Any], fecha_str: str) -> Optional[Any]:
    """
    Obtiene carpeta por fecha desde el mapeo creado.
    
    Args:
        folders_por_fecha: Mapeo fecha_str -> Folder
        fecha_str: Fecha en formato "DD/MM/YYYY" o "YYYY-MM-DD"
        
    Returns:
        Folder o None: Carpeta correspondiente a la fecha
        
    Helper para acceder a carpetas por fecha desde items individuales.
    """
    try:
        # Convertir fecha a formato estándar para búsqueda
        if "-" in fecha_str:
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        else:
            fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
        
        fecha_key = f"{fecha_dt.timetuple().tm_yday:03d}-{fecha_dt.strftime('%Y-%m-%d')}"
        return folders_por_fecha.get(fecha_key)
    except Exception:
        return None


def classify_time_range(hora_str: Optional[str]) -> str:
    """
    Clasifica hora en rango horario para distribución en carpetas.
    
    Args:
        hora_str: Hora en formato "HH:MM:SS" o similar
        
    Returns:
        str: Clave de rango ("manana", "tarde", "noche", "madrugada")
        
    Rangos:
    - Madrugada: 00:00-05:59  
    - Mañana: 06:00-11:59
    - Tarde: 12:00-17:59
    - Noche: 18:00-23:59
    
    Extracción de _clasificar_rango_sv del monolito
    """
    if not hora_str or hora_str in ("Sin Inf.", "S/I", None, ""):
        return "manana"  # default
    
    try:
        hora_clean = str(hora_str).strip()[:8]  # "HH:MM:SS"
        if ":" in hora_clean:
            hora_int = int(hora_clean.split(":")[0])
        else:
            hora_int = int(hora_clean[:2])  # "HHMMSS"
        
        if 0 <= hora_int < 6:
            return "madrugada"
        elif 6 <= hora_int < 12:
            return "manana"
        elif 12 <= hora_int < 18:
            return "tarde"
        else:  # 18-23
            return "noche"
    except Exception:
        return "manana"  # default