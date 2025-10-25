"""
tz_core.config_manager - Gestión de configuración del sistema
Manejo de archivos de configuración, sinónimos y mapeo de columnas
"""

import json
import os
import sys
from typing import Dict, Any


# Configuración por defecto del sistema
DEFAULT_CONFIG = {
    "kml": {
        "azimuth_km": 1.5,
        "cone": {"half_degrees": 35, "fill_color": "7fffffff"},
        "line": {"color": "ffff00ff", "width": 5},
        "description": [
            # Bloque 2: Tel + identidad (incluye Alias; etiqueta Usuario)
            [["Tel","tel"], ["IMEI","imei"], ["Alias","alias"], ["Nombre de Usuario","nombre_usuario"], ["Abonado","abonado"]],
            # Bloque 3: datos de antena/posiciones
            [["Antena","antena"], ["Detalle","detalle"], ["Lat","lat"], ["Long","long"], ["Azimut","azimut"], ["Celda","celda"], ["LAC","lac"]],
            # Bloque 4: interacción + duración
            [["Interacción","interaccion"], ["Duración","duracion"]]
        ]
    }
}


def cargar_config() -> Dict[str, Any]:
    """
    Carga la configuración global desde config.json.
    
    NOTA TÉCNICA: Esta función maneja un sistema híbrido de sinónimos:
    - 'synonyms': Legacy del mapeo automático (posiblemente excesivos)
    - 'synonyms_user': Memoria de mapeos manuales (crece automáticamente)
    
    CONSIDERACIÓN FUTURA: La memoria automática (synonyms_user) podría 
    desactivarse ya que el mapeo actual es completamente manual.
    
    Compatible con PyInstaller (detecta sys.frozen y usa sys._MEIPASS).

    Returns:
        dict: Diccionario de configuración global con merge de defaults
        
    Raises:
        None: Siempre retorna DEFAULT_CONFIG en caso de error
    """
    # Detecta base_path según modo de ejecución (normal vs PyInstaller)
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        # Ajustar ruta para tz_core (subir un nivel)
        base = os.path.dirname(base)
    
    ruta_cfg = os.path.join(base, "config.json")
    
    try:
        with open(ruta_cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Merge superficial con defaults
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data or {})
        
        # Merge profundo de sección kml
        if "kml" in data:
            cfg["kml"].update(data["kml"])
        
        # Blindaje: asegurar que 'Alias' aparezca en el bloque 2 de la descripción
        try:
            desc = cfg["kml"]["description"]
            if isinstance(desc, list) and len(desc) >= 2:
                bloque2 = desc[1]  # Tel/IMEI/…
                if isinstance(bloque2, list):
                    etiquetas = [etq for etq, _ in bloque2 if isinstance(etq, str)]
                    if "Alias" not in etiquetas:
                        # Insertar después de IMEI (posición 2)
                        bloque2.insert(2, ["Alias", "alias"])
        except Exception:
            # Fallo en blindaje no es crítico
            pass
        
        return cfg
        
    except Exception:
        # En caso de cualquier error, retornar configuración por defecto
        return DEFAULT_CONFIG


# =====================================
# TODO: Extraer más funciones de configuración aquí:
# - cfg_build_rename_map()
# - cfg_add_user_synonym() 
# - get_config()
# ====================================
    
    def add_user_synonym(self, key, synonym):
        """Agregar sinónimo definido por usuario"""
        pass


# === FUNCIONES DE BOOTSTRAP Y SINÓNIMOS ===

def log(msg: str):
    """
    Función de logging simple y visible en consola.
    
    NOTA: Esta es una función auxiliar extraída para las funciones de configuración.
    En el futuro podría moverse a un módulo de logging dedicado.
    """
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = f"[{ts}] {msg}"
    print(s)
    # Nota: LOGS list no se mantiene en el módulo para evitar dependencias


def _normalize_key_for_synonyms(s: str) -> str:
    """
    Normaliza una cadena para comparación de sinónimos.
    
    Aplica:
    - Normalización Unicode NFKD
    - Eliminación de acentos/diacríticos
    - Conversión a minúsculas
    - Normalización de espacios en blanco
    
    Args:
        s: Cadena a normalizar
        
    Returns:
        str: Cadena normalizada para comparación
    """
    import unicodedata
    import re
    
    s = "" if s is None else str(s)
    s = unicodedata.normalize('NFKD', s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def cfg_build_rename_map(CONFIG: dict) -> dict:
    """
    Construye el mapa de sinónimos de columnas a partir de CONFIG.
    
    SISTEMA HÍBRIDO DE SINÓNIMOS:
    1. 'schema.fields.*.synonyms': Sinónimos legacy del mapeo automático
    2. 'synonyms_user': Memoria dinámica de mapeos manuales
    
    NOTA TÉCNICA: El sistema actual usa mapeo 100% manual, por lo que
    la memoria automática (synonyms_user) podría ser obsoleta.
    
    Args:
        CONFIG: Diccionario de configuración global
        
    Returns:
        dict: Mapa de sinónimos {columna_canonica: {set_de_variantes}}
    """
    rename_map = {}
    schema = (CONFIG or {}).get('schema', {})
    fields = schema.get('fields', {}) if isinstance(schema, dict) else {}
    
    # Procesar sinónimos legacy del schema
    for canonico, spec in (fields or {}).items():
        sinos = set()
        if isinstance(spec, dict):
            for raw in spec.get('synonyms', []) or []:
                sinos.add(_normalize_key_for_synonyms(raw))
            sinos.add(_normalize_key_for_synonyms(canonico))
        rename_map[canonico] = sinos
    
    # Procesar sinónimos de memoria dinámica
    user_syn = (CONFIG or {}).get('synonyms_user', {}) or {}
    for raw, mapped in user_syn.items():
        if raw.startswith('_'):
            continue
        c_norm = _normalize_key_for_synonyms(mapped)
        r_norm = _normalize_key_for_synonyms(raw)
        if c_norm not in rename_map:
            rename_map[c_norm] = set()
        rename_map[c_norm].add(r_norm)
    
    try: 
        log(f"[synonyms] Construido rename_map: {sum(len(v) for v in rename_map.values())} entradas totales.")
    except Exception: 
        pass
    return rename_map


# TODO: Extraer del script principal:
# - _solicitar_color_tema()
# - _atomic_write_json() 
# - cfg_add_user_synonym()


def solicitar_color_tema(CONFIG, input_mock=None):
    """
    🚨 FUNCIÓN INTERACTIVA CRÍTICA: Interfaz para elegir color de tema visual del informe/KML.
    
    FUNCIONALIDAD:
    - Muestra paleta de 60 colores configurables (diferenciación de bitácoras)
    - Permite selección por número, HEX manual o usar predeterminado
    - Actualiza CONFIG["style"]["theme_hex"] con la elección
    - Aplicación global: el color elegido se aplica a todo el KML/KMZ
    
    SISTEMA DE PALETA:
    - Si existe paleta en config.json → muestra menú numerado
    - Soporte para HEX manual: #RRGGBB, RRGGBB, #RGB, RGB
    - Validación robusta con fallback a color predeterminado
    
    Args:
        CONFIG (dict): Diccionario de configuración global
        input_mock (callable, optional): Mock para testing (reemplaza input())
        
    Returns:
        dict: CONFIG actualizado con el color elegido
        
    NOTA TÉCNICA: La función usa input() - requiere mocking para tests automatizados.
    """
    import re
    
    # Función de input configurable para testing
    input_func = input_mock if input_mock else input
    
    style = CONFIG.get("style", {}) if isinstance(CONFIG, dict) else {}
    default_hex = style.get("theme_hex", "#ff00ff")
    palette = style.get("palette") or []   # lista de [nombre, "#hex"]

    # Construir el prompt
    print("")  # pequeña separación visual
    if palette:
        print("Colores sugeridos (visibles en Google Earth):")
        for i, item in enumerate(palette, start=1):
            try:
                nombre, hexv = item[0], item[1]
            except Exception:
                # por si el ítem no tiene la forma esperada
                continue
            print(f"  [{i}] {nombre}  {hexv}")
        print(f"  [0] Usar el predeterminado ({default_hex})")

        resp = input_func("Elegí número o pegá un HEX (Enter = predeterminado): ").strip()
    else:
        # Sin paleta configurada, conservamos el comportamiento clásico
        resp = input_func(f"Ingresá color tema en hex (Enter = {default_hex}): ").strip()

    # Normalizar elección
    if resp == "":
        elegido = default_hex
    else:
        # ¿opción numérica?
        if resp.isdigit():
            idx = int(resp)
            if idx == 0 and palette:
                elegido = default_hex
            elif 1 <= idx <= len(palette):
                elegido = str(palette[idx - 1][1]).strip()
            else:
                print("Opción fuera de rango; usaré el color predeterminado.")
                elegido = default_hex
        else:
            # ¿HEX manual?
            if re.fullmatch(r"#?[0-9a-fA-F]{6}", resp):
                elegido = resp if resp.startswith("#") else f"#{resp}"
            else:
                print("Formato de color no válido; usaré el color predeterminado.")
                elegido = default_hex

    # Actualizar CONFIG y confirmar
    style["theme_hex"] = elegido
    CONFIG["style"] = style
    print(f"Color tema: {elegido}")
    return CONFIG