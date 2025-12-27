# ======================================================================
#                 T Z   A N A L Y S I S  —  MAPA DE SECCIONES
# ======================================================================
# Este archivo implementa el motor principal del procesador forense TZ Analyzer.
# Incluye orquestación, normalización, generación de productos y utilidades clave.
#
# SECCIÓN 0 · IMPORTS & CONFIG
#     - Imports estándar y de terceros
#     - Carga/uso de CONFIG (sin lógica)
#
# SECCIÓN 1 · ENTRADA / I/O (Excel, hoja, prompts base)
#     - Selección de archivo y hoja visible
#     - Wizard de mapeo (SOLO esenciales)
#     - Elección de color (paleta/HEX)
#
# SECCIÓN 2 · NORMALIZACIÓN / LIMPIEZA
#     - Fecha/Hora: serial Excel, ISO y local → datetime (TZ: America/El_Salvador)
#     - Lat/Lon: floats válidos; descartar filas fuera de rango
#     - Azimut: permitir 0; normalizar [0..360)
#     - IMEI/TEL: como str, sin “.0”
#     - Omitir campos vacíos (no “SinInf”)
#
# SECCIÓN 3 · MOTOR / FILTROS / CÁLCULOS
#     - Filtro por día / rango de días / rango de horas
#     - Top N antenas y Top N contactos (después de filtros)
#     - Resúmenes y contadores (válidas/descartadas)
#
# SECCIÓN 4 · VISTAS HTML
#     - Metadatos (alias/nombre_usuario/abonado si existen)
#     - “Periodo analizado”: dd/mm/yyyy HH:MM — dd/mm/yyyy HH:MM
#     - Tablas (incluye “Antenas más activadas” con azimut sin decimales)
#
# SECCIÓN 5 · VISTAS KML/KMZ
#     - Puntos y líneas (azimut 0 también se dibuja)
#     - Burbujas: ocultar campos vacíos; IMEI/TEL sin “.0”
#
# SECCIÓN 6 · UTILIDADES
#     - Selección de carpeta/archivo (Tkinter + fallback consola)
#     - Logging y helpers varios
#
# SECCIÓN 7 · MENÚ / ORQUESTACIÓN
#     - Menú único (loop en modo manual)
#     - Flujo: menú → color → entrada → mapeo → preguntas finales (alias/nombre_usuario/abonado/top) → carpeta destino → generar
#
# NOTA: Este bloque solo documenta y ordena la lectura del archivo. No modifica funcionalidad.
# ======================================================================

#===============================================================================
# === SECCIÓN 0 · IMPORTS & CONFIG ===

# Estándar
import json
import math
import os
import re
import shutil
import sys
import unicodedata
import logging
import traceback
import io
import base64

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np

# Terceros
import pandas as pd  # <-- UNO solo, aquí arriba
from simplekml import Kml

# Módulos locales
from utilidades import seleccionar_archivo, seleccionar_carpeta
from validaciones import validar_datos, guardar_errores
# 🔧 MÓDULO EXTRAÍDO (Epic 14): KML puntos libres consolidado en tz_core
from tz_core.kml_generator import generar_kml_puntos_libres
# 🔧 MÓDULO EXTRAÍDO (Epic 15): Wizard QC mapeo completo
from tz_core.mapping_wizard import wizard_qc_mapeo as _wizard_qc_mapeo
# 🔧 MÓDULO EXTRAÍDO: HTML helpers para generar_informe_html
from tz_core.html_helpers import (
    fmt_datetime as fmt_dt, first_nonempty_in, 
    nunique_in, unique_values_in,
    fmt_imei_item, row_html, 
    luhn_check, is_valid_imei
)
# 🔧 MÓDULO EXTRAÍDO: Sistema de logging centralizado
from tz_core.logging_utils import (
    log as _log_impl,
    get_logs,
    get_log_placeholders,
    add_log_placeholder,
    has_log_placeholder,
    clear_logs,
    clear_log_placeholders,
    clear_all_logging_state,
    get_logs_count,
    get_recent_logs,
    log_info,
    log_warn,
    log_error,
    log_debug
)

# 🔧 MÓDULO EXTRAÍDO: Utilidades de interfaz de usuario
from tz_core.ui_utils import (
    solicitar_overrides_topn
)

# 🔧 MÓDULO EXTRAÍDO: Utilidades de procesamiento de texto
from tz_core.text_utils import (
    _fix_mojibake_text,
    _aplicar_reemplazos_regex
)
# 🔧 MÓDULO EXTRAÍDO: Utilidades de formato y configuración
from tz_core.format_utils import agregar_bloque, armar_descripcion_compacta
from tz_core.config_manager import cfg_build_rename_map, add_user_synonym, solicitar_color_tema
from tz_core.color_utils import hex_to_kml_color
from tz_core.html_generator import generate_html_header, generate_body_header, generate_metadata_section, generate_kpi_section
# --- Helpers de hora y carpetas/rangos (Preset A SV) ---
from datetime import time as _time

# =========================
# Generación de KML (usa CONFIG)
# =========================
# FUNCIÓN _crear_feature_kml MOVIDA A LÍNEA 1308 - ELIMINADA DUPLICACIÓN

# ...existing code...
#=================================================================================

def bootstrap_config() -> None:
    """
    🚨 FUNCIÓN ULTRA-CRÍTICA REFACTORIZADA: Inicializa configuración global y rename map.
    
    RESPONSABILIDADES:
    1. Muestra banner de la aplicación
    2. Inicializa variables globales CONFIG y RENAME_MAP
    3. Carga configuración desde archivo (tz_core.config_manager)
    4. Construye mapa de sinónimos de columnas (tz_core.config_manager)
    
    REFACTORIZACIÓN:
    - Banner: mantenido local (display)
    - CONFIG loading: usa cargar_config_modular() ✅ 
    - RENAME_MAP building: usa cfg_build_rename_map_modular() ✅
    - Variables globales: mantenidas locales por compatibilidad
    """
    # Banner (antes estaba al nivel superior)
    print("""
===============================================
           T  Z   A N A L Y Z E R
    Bitacoras -> KML/KMZ + Informe HTML
===============================================
""")
    
    # Configuración y mapa de sinónimos usando funciones modulares
    global CONFIG, RENAME_MAP
    CONFIG = get_config()  # Usa la función centralizada (ya modular)
    
    # Importar cfg_build_rename_map desde el módulo (ya en imports globales)
    RENAME_MAP = cfg_build_rename_map(CONFIG)

# Flag para modo wizard de mapeo manual (QC)
MANUAL_QC_MAPPING = True

# === SECCI�"N: WIZARD DE MAPEO DE COLUMNAS (detecci�n, mapeo manual, QC) ===
# � M�DULO EXTRA&#205;DO EN EPIC 15 - 27/12/2025
#
# La funci�n _wizard_qc_mapeo() (382 l�neas, marcada PELIGRO EXTREMO) fue
# exitosamente extra�da a tz_core/mapping_wizard.py con protocolo paranoico.
#
# MIGRACI�"N:
# - C�digo original: L183-565 (382 l�neas de l�gica cr�tica)
# - Nuevo m�dulo: tz_core/mapping_wizard.py (MappingWizard class)
# - Import: from tz_core.mapping_wizard import wizard_qc_mapeo as _wizard_qc_mapeo
# - Compatibilidad: 100% - firma id�ntica, comportamiento preservado
#
# ARQUITECTURA NUEVA:
# - MappingWizard: Clase profesional con separaci�n de responsabilidades
# - UI Layer: _menu_horizontal(), _ask_column_*(), _show_*()
# - Logic Layer: _map_essentials(), _map_non_essentials(), _apply_mapping()
# - Confirmation Layer: _confirm_loop() con recursi�n (opci�n N)
#
# VALIDACI�"N:
# - Sintaxis: py_compile OK
# - Imports: m�dulo carga correctamente
# - Tests: Pendiente validaci�n E2E con archivo real
#
# BENEFICIOS:
# - Reducci�n monolito: -382 l�neas (-6.4%)
# - Testeable: Clase permite mocking de inputs
# - Mantenible: Separaci�n clara de responsabilidades
# - Documentado: Docstrings completos + arquitectura clara
#
# COMMIT: Pendiente tras validaci�n paranoica completa
# =========================================================================


# --- LOGS: helper para registrar degrade/mapas/omisiones ---
from datetime import datetime
from datetime import datetime

# ===================================================================
# WRAPPERS DE COMPATIBILIDAD PARA LOGGING - FASE 9C
# ===================================================================
# EXTRAÍDO A: tz_core.logging_utils
# MIGRACIÓN: Variables globales LOGS y LOG_PLACEHOLDERS movidas a módulo
# COMPATIBILIDAD: Wrappers mantienen interfaz original del monolito

# Crear objetos que simulan las variables globales originales
class _LogsCompat:
    def __iter__(self):
        return iter(get_logs())
    def __len__(self):
        return get_logs_count()
    def __getitem__(self, key):
        return get_logs()[key]
    def append(self, item):
        # Para compatibilidad con código que hace LOGS.append()
        # Extraer el mensaje sin timestamp si ya lo tiene
        if item.startswith('[') and '] ' in item:
            parts = item.split('] ', 1)
            if len(parts) == 2:
                _log_impl(parts[1])
            else:
                _log_impl(item)
        else:
            _log_impl(item)

class _PlaceholdersCompat:
    def __iter__(self):
        return iter(get_log_placeholders())
    def __len__(self):
        return len(get_log_placeholders())
    def __contains__(self, item):
        return has_log_placeholder(item)
    def add(self, item):
        add_log_placeholder(item)

LOGS = _LogsCompat()
LOG_PLACEHOLDERS = _PlaceholdersCompat()

def log(msg: str):
    """
    Wrapper de compatibilidad para función log.
    IMPLEMENTACIÓN REAL: tz_core.logging_utils.log()
    """
    _log_impl(msg)


# === NORMALIZADOR-1 (inicio) ==============================================
# Todas las funciones de normalización de texto migradas a tz_core.text_utils
# Usar imports directos desde línea 765: normalizar_texto, normalizar_columnas_texto
# === NORMALIZADOR-1 (fin) ==================================================


# =========================
# Fallbacks de importación
# =========================
try:
    from validaciones import validar_datos, guardar_errores  # OK si existe
except Exception:
    # Fallback mínimo (no rompe el flujo)
    from datetime import datetime

    def validar_columnas(dataframe, columnas_esperadas):
        return [col for col in columnas_esperadas if col not in dataframe.columns]

    def validar_datos(df, columnas_esenciales):
        errores = []
        faltantes = validar_columnas(df, columnas_esenciales)
        if faltantes:
            errores.append(f"[FALLBACK] Faltan columnas esenciales: {', '.join(faltantes)}")

        # Garantizar fecha/hora como texto tolerante (sin convertir si no hay)
        if 'fecha' in df.columns:
            try:
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True)
                mask = df['fecha'].isna()
                df.loc[~mask, 'fecha'] = df.loc[~mask, 'fecha'].dt.strftime("%d/%m/%Y")
                df.loc[mask, 'fecha'] = "Sin Inf."
            except Exception:
                df['fecha'] = "Sin Inf."

        if 'hora' in df.columns:
            try:
                horas = pd.to_datetime(df['hora'].astype(str).str[:8], format="%H:%M:%S", errors="coerce")
                maskh = horas.isna()
                df.loc[~maskh, 'hora'] = horas.dt.strftime("%H:%M:%S")
                df.loc[maskh, 'hora'] = "Sin Inf."
            except Exception:
                df['hora'] = "Sin Inf."

        # Coordenadas tolerantes
        for c in ('lat', 'long'):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        if 'lat' in df.columns and 'long' in df.columns:
            maskc = df['lat'].isna() | df['long'].isna()
            if maskc.any():
                errores.append(f"[FALLBACK] {maskc.sum()} filas con coordenadas inválidas.")
                df[['lat', 'long']] = df[['lat', 'long']].astype(object)
                df.loc[maskc, ['lat', 'long']] = "Sin Inf."
        return df, errores

    def guardar_errores(errores, carpeta_salida, nombre_base):
        os.makedirs(carpeta_salida, exist_ok=True)
        # ahora: usar siempre el BASE unificado
        archivo_errores = os.path.join(carpeta_salida, "errores.txt")
        with open(archivo_errores, "w", encoding="utf-8") as f:
            if errores:
                f.write(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] Errores detectados:\n")
                for e in errores:
                    f.write(f"- {e}\n")
            else:
                f.write(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] No se detectaron errores.\n")
        return archivo_errores

try:
    from utilidades import seleccionar_archivo, seleccionar_carpeta
except Exception:
    # Fallback por consola (sin Tk)
    def seleccionar_archivo():
        ruta = input("Ruta del archivo Excel (.xlsx/.xls): ").strip('"').strip()
        return ruta if ruta else None

    def seleccionar_carpeta():
        ruta = input("Ruta de la carpeta de salida (Enter = actual): ").strip('"').strip()
        return ruta if ruta else os.getcwd()

# =========================
# Configuración externa
# =========================
# --- ANTI-COLISIONES DE COLUMNAS (fusiona duplicadas por primer valor no vacío) ---
# === IMPORTS MODULARES (gradual refactoring) ===
from tz_core.utils import sha256_de_archivo, compactar_ruta, sanear_nombre_archivo
from tz_core.config_manager import cargar_config as cargar_config_modular, DEFAULT_CONFIG as DEFAULT_CONFIG_MODULAR
from tz_core.geo_utils import grados_a_radianes, calcular_punto_final, generar_cono
from tz_core.text_utils import normalizar_texto, normalizar_columnas_texto, _fix_mojibake_text
from tz_core.color_utils import hex_to_kml_color, color_mock, _hex_to_kml_color, _color_mock
from tz_core.html_utils import row_html, fmt_imei_item, luhn_check
from tz_core.validation_utils import tiene_valor, es_num, a_float
from tz_core.time_utils import hhmmss_to_time_or_none, en_rango_tiempo, en_rango_minutos, clasificar_rango_sv, RANGOS_SV as RANGOS_SV_MODULAR
from tz_core.dataframe_utils import dedupe_columns
from tz_io.file_io import escribe_hashes_txt, copiar_logo_a_salida, _copiar_logo_a_salida

# Importar constantes desde tz_core para consistencia
RANGOS_SV = RANGOS_SV_MODULAR

# === HASHES + ENTORNO (helpers) — INICIO ====================================
def _copiar_logo_a_salida(logo_src: str, carpeta_salida: str) -> str | None:
    """Wrapper de compatibilidad - usa tz_core.file_utils.copiar_logo_a_salida"""
    return copiar_logo_a_salida(logo_src, carpeta_salida)


# Alias para compatibilidad - usar DEFAULT_CONFIG de tz_core.config_manager
DEFAULT_CONFIG = DEFAULT_CONFIG_MODULAR

# === SECCIÓN: CONFIGURACIÓN Y SINÓNIMOS (carga CONFIG, construye RENAME_MAP) ===
def cargar_config():
    """
    Wrapper para compatibilidad - usar cargar_config de tz_core.config_manager
    
    NOTA: Preserva comportamiento exacto incluyendo DEFAULT_CONFIG y merge logic.
    El sistema de sinónimos legacy se mantiene intacto para evitar breaking changes.
    """
    return cargar_config_modular()

# === SINONIMOS: MERGE + PERSISTENCIA (inicio) ==============================
import tempfile

def _normalize_key_for_synonyms(s: str) -> str:
    """
    Wrapper para compatibilidad - usar _normalize_key_for_synonyms de tz_core.config_manager
    """
    from tz_core.config_manager import _normalize_key_for_synonyms as _normalize_modular
    return _normalize_modular(s)

def cfg_build_rename_map(CONFIG: dict) -> dict:
    """
    Wrapper para compatibilidad - usar cfg_build_rename_map de tz_core.config_manager
    
    Nota: Sistema de sinónimos extraído al módulo config_manager.
    Este wrapper preserva el comportamiento exacto del mapeo de columnas legacy y dinámico.
    """
    from tz_core.config_manager import cfg_build_rename_map as cfg_build_modular
    return cfg_build_modular(CONFIG)

def cfg_add_user_synonym(CONFIG: dict, canonico: str, encabezado_crudo: str, ruta_cfg: str = None) -> dict:
    """
    🚨 WRAPPER DE COMPATIBILIDAD - usar add_user_synonym de tz_core.config_manager
    
    Nota: Función de gestión de sinónimos dinámicos extraída al módulo config_manager.
    Este wrapper preserva persistencia automática en config.json y memoria de mapeo manual.
    """
    return add_user_synonym(CONFIG, canonico, encabezado_crudo, ruta_cfg)
# === SINONIMOS: MERGE + PERSISTENCIA (fin) =================================

# CONFIG inicializado al nivel de módulo (se carga una sola vez)
CONFIG = None
OVERRIDE_TOPS = None  # override temporal de Top N (se rellena en tiempo de ejecución)

def get_config():
    """
    Lazy-load de CONFIG: retorna el diccionario global de configuración, inicializándolo si es necesario.
    Resuelve rutas absolutas para logo, compatible con PyInstaller.

    Uso:
        config = get_config()

    Returns:
        dict: Diccionario de configuración global.
    """
    import sys, os
    global CONFIG
    if CONFIG is None:
        # cargar_config() ya maneja la detección de ruta correctamente
        CONFIG = cargar_config()
        
        # Normaliza ruta de logo para PyInstaller si es necesario
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            logo_path = CONFIG.get("branding", {}).get("logo_path")
            if logo_path and not os.path.isabs(logo_path):
                CONFIG["branding"]["logo_path"] = os.path.join(base_path, logo_path)
    return CONFIG

def _solicitar_color_tema(CONFIG):
    """
    🚨 WRAPPER DE COMPATIBILIDAD - usar solicitar_color_tema de tz_core.config_manager
    
    Nota: Función interactiva extraída al módulo config_manager.
    Este wrapper preserva la paleta de 60 colores para diferenciación de bitácoras.
    """
    return solicitar_color_tema(CONFIG)

# =========================
# Geometría / KML helpers
# =========================
# --- Helpers de color KML (aabbggrr) desde #RRGGBB ---
def _hex_to_kml_color(hex_rgb: str, alpha: int = 255) -> str:
    """MIGRADA A tz_core.color_utils - usar import desde allí"""
    return hex_to_kml_color(hex_rgb, alpha)

# =========================
# Análisis de antenas (tolerante)
# =========================
def analizar_antenas(df: pd.DataFrame, archivo_salida: str):
    """Wrapper de compatibilidad - usa tz_core.analytics.analizar_antenas"""
    from tz_core.analytics import analizar_antenas as analizar_modular
    return analizar_modular(df, archivo_salida)

# =========================
# Burbuja condicional
# =========================
def generar_historial_cambios_antena(df: pd.DataFrame, max_saltos: int = 100):
    """Wrapper de compatibilidad - usa tz_core.analytics.generar_historial_cambios_antena"""
    from tz_core.analytics import generar_historial_cambios_antena as historial_modular
    return historial_modular(df, max_saltos)

HR_COMPACT = '<div style="border-top:1px solid #bbb; margin:1px 0; height:0;"></div>'

# =========================
# Funciones de formateo - usar imports directos desde tz_core.format_utils
# - armar_descripcion_compacta()
# - agregar_bloque()
# =========================
# Generación de KML (usa CONFIG)
# =========================
def _crear_feature_kml(container, nombre_punto, lon, lat, descripcion, azimut_float, CONFIG, azimuts_extra=None):
    # --- Sanitizar descripción: omitir campos vacíos o marcadores “sin valor” ---
    # Afecta todas las capas que llamen a _crear_feature_kml (por_rango_horario, top_3_*, etc.)
    try:

        # --- Compactación efectiva para el campo 'name' en KML/KMZ ---
        def compactar_nombre_antena_kml(nombre: str) -> str:
            """
            Compacta el nombre de antena para el campo 'name' en KML/KMZ.
            Reglas configurables via CONFIG.kml.name_compaction:
            - prefer_before_comma: número de secciones a tomar antes de la coma (ej. 2). Si 0/None, ignora.
            - max_words: si no hay comas o prefer_before_comma no aplica, toma primeras N palabras significativas.
            - max_chars: tope de caracteres; si excede, recorta y agrega '...'.
            - stopwords: lista de palabras a omitir.
            """
            try:
                nc = (CONFIG or {}).get("kml", {}).get("name_compaction", {})
            except Exception:
                nc = {}
            prefer_before = int(nc.get("prefer_before_comma", 2) or 0)
            max_words = int(nc.get("max_words", 5) or 5)
            max_chars = int(nc.get("max_chars", 40) or 40)
            stopwords = set(str(w).lower() for w in nc.get("stopwords", ["el","la","los","las","de","del","y","en","a","al","por","para","con","un","una"]))
            if not nombre:
                return ""
            nombre = str(nombre).strip()
            if "," in nombre and prefer_before > 0:
                secciones = [s.strip() for s in nombre.split(",")]
                if len(secciones) >= prefer_before:
                    parte = ", ".join(secciones[:prefer_before])
                else:
                    parte = ", ".join(secciones)
            else:
                palabras = [w for w in re.split(r'\s+', nombre) if w and w.lower() not in stopwords]
                parte = " ".join(palabras[:max_words])
            if len(parte) > max_chars:
                return parte[: max(0, max_chars-3) ] + "..."
            return parte

        # Usar nombre compacto SOLO para el campo 'name' del punto KML
        nombre_compacto = nombre_punto
        if nombre_punto:
            nombre_compacto = compactar_nombre_antena_kml(nombre_punto)

        # Si hay columna de dirección, no sobreescribir; si no, usar nombre completo como dirección
        # (esto se debe manejar en el flujo de mapeo, aquí solo se documenta)

        if descripcion:
            parts = re.split(r'<br\s*/?>', str(descripcion))

            # 1) Omitir líneas vacías / marcadores
            parts = [
                p for p in parts
                if p and p.strip() and not any(tok in p for tok in (
                    "> SinInf", "> Sin Inf.", "> None", "> nan", "> NaN"
                ))
            ]

            # 2) Normalizar IDs (TEL/IMEI): quitar .0 al final del número
            def _fix_id_line(s: str) -> str:
                if ("<b>IMEI" in s) or ("<b>Número" in s) or ("<b>Numero" in s):
                    return re.sub(r'(\d+)\.0\b', r'\1', s)
                return s

            parts = [_fix_id_line(p) for p in parts]
            descripcion = "<br>".join(parts)
    except Exception:
        pass

    # --- Normalizar y validar azimut (permitir 0°) ---
    try:
        az = float(azimut_float)
    except Exception:
        return  # no dibujar si no es numérico
    if isinstance(az, float) and math.isnan(az):
        return
    # Llevar a [0, 360)
    az = az % 360.0
    az_int = int(round(az)) % 360

    """
    Crea el punto + (opcional) línea y cono con estilos REUSABLES en un solo lugar.
    - Color/estilo se toma de CONFIG['style'] si existe; si no, usa defaults.
    - Reutiliza estilos (pin/linea/cono) para hacer el KML más liviano.
    """
    import simplekml as sk

    # Fallback eliminado - función migrada a tz_core.color_utils

    # Cache global de estilos reutilizables para evitar crear objetos Style duplicados
    # en cada llamada (mejora rendimiento del KML). Se inicializa una vez con los
    # parámetros de CONFIG y se comparte entre todas las features del documento.
    global _REUSABLE_STYLES
    if "_REUSABLE_STYLES" not in globals():
        _REUSABLE_STYLES = None

    if _REUSABLE_STYLES is None:
        style_cfg = {}
        try:
            style_cfg = CONFIG.get("style", {}) if isinstance(CONFIG, dict) else {}
        except Exception:
            style_cfg = {}
        theme_hex = style_cfg.get("theme_hex", "#ff00ff")
        pin_icon_url = style_cfg.get("pin_icon_url", "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png")
        pin_scale = float(style_cfg.get("pin_scale", 1.1))
        label_scale = float(style_cfg.get("label_scale", 1.2))
        line_width = float(style_cfg.get("line_width", 5))
        line_abgr = style_cfg.get("line_abgr", None)
        cone_opac = float(style_cfg.get("cone_opacity", 0.35))

        # Colores KML (AABBGGRR)
        pin_color  = _hex_to_kml_color(theme_hex, 255)
        # Si line_abgr está en config, úsalo directamente; si no, convierte theme_hex
        line_color = line_abgr if line_abgr else _hex_to_kml_color(theme_hex, 255)
        cone_color = _hex_to_kml_color(theme_hex, int(max(0, min(1.0, cone_opac)) * 255))

        # Estilo del PIN
        s_pin = sk.Style()
        s_pin.iconstyle.color = pin_color
        s_pin.iconstyle.scale = pin_scale
        s_pin.iconstyle.icon.href = pin_icon_url
        s_pin.labelstyle.color = pin_color
        s_pin.labelstyle.scale = label_scale

        # Estilo de la LÍNEA
        s_line = sk.Style()
        s_line.linestyle.color = line_color
        s_line.linestyle.width = line_width

        # Estilo del CONO (polígono)
        s_cone = sk.Style()
        s_cone.polystyle.color = cone_color
        s_cone.polystyle.fill = 1
        s_cone.polystyle.outline = 1

        _REUSABLE_STYLES = {
            "pin": s_pin,
            "line": s_line,
            "cone": s_cone,
        }

    # ---------- 2) Crear el punto ----------
    # Usar nombre compacto para la visualización en el mapa
    p = container.newpoint(name=nombre_compacto, coords=[(lon, lat)])
    if descripcion:
        p.description = f'<div style="line-height:1.10; font-size:14px">{descripcion}</div>'
    p.style = _REUSABLE_STYLES["pin"]

    # ---------- 3) Si hay azimut, dibujar LÍNEA y CONO con estilos ----------
    try:
        az = float(azimut_float) if azimut_float is not None else float("nan")
    except Exception:
        az = float("nan")

    if not (isinstance(az, float) and math.isnan(az)):
        # Distancia y ángulo del cono (defaults si CONFIG no trae)
        try:
            az_dist_km = CONFIG.get("kml", {}).get("azimuth_km", 1.5)
            # Priorizar kml.cone.half_degrees, luego style.cone_half_degrees
            cone_half  = CONFIG.get("kml", {}).get("cone", {}).get("half_degrees")
            if cone_half is None:
                cone_half = CONFIG.get("style", {}).get("cone_half_degrees", 35)
        except Exception:
            az_dist_km = 1.5
            cone_half = 35

        # Calcular punto final de la línea de azimut
        latf, lonf = calcular_punto_final(lat, lon, az, float(az_dist_km))

        # LÍNEA
        linea = container.newlinestring(
            name=f"Azimut {int(round(az))}°",
            coords=[(lon, lat), (lonf, latf)]
        )
        linea.style = _REUSABLE_STYLES["line"]

        # CONO (polígono)
        coords_cono = []
        paso = 5
        for ang in range(-int(cone_half), int(cone_half) + 1, paso):
            lat_p, lon_p = calcular_punto_final(lat, lon, az + ang, float(az_dist_km))
            coords_cono.append((lon_p, lat_p))
        coords_cono.append((lon, lat))
        pol = container.newpolygon(name=f"Cono Azimut {int(round(az))}°")
        pol.outerboundaryis = coords_cono
        pol.style = _REUSABLE_STYLES["cone"]
        
        # --- Azimuts secundarios (línea y cono; mismo pin) ---
        if azimuts_extra:
            for az_s in azimuts_extra:
                try:
                    az_s = float(az_s)
                except:
                    continue

                # Línea secundaria
                latf2, lonf2 = calcular_punto_final(lat, lon, az_s, float(az_dist_km))
                linea2 = container.newlinestring(
                    name=f"Azimut {int(round(az_s))}° (sec.)",
                    coords=[(lon, lat), (lonf2, latf2)]
                )
                linea2.style = _REUSABLE_STYLES["line"]  # si querés, luego la hacemos más tenue

                # Cono secundario
                coords_cono2 = []
                paso = 5
                for ang in range(-int(cone_half), int(cone_half) + 1, paso):
                    lat_p2, lon_p2 = calcular_punto_final(lat, lon, az_s + ang, float(az_dist_km))
                    coords_cono2.append((lon_p2, lat_p2))
                coords_cono2.append((lon, lat))

                pol2 = container.newpolygon(name=f"Cono Azimut {int(round(az_s))}° (sec.)")
                pol2.outerboundaryis = coords_cono2
                pol2.style = _REUSABLE_STYLES["cone"]  # luego bajamos opacidad si querés

# === SECCIÓN: GENERACIÓN KML/KMZ (placemarks, carpetas, top_n, estilos) ===
# ⚡ EPIC 13: Función migrada a tz_core.kml_generator (26/12/2025)
# Wrapper de compatibilidad - mantiene interfaz original del monolito
def generar_kml(df: pd.DataFrame, archivo_salida_kml: str, flat: bool=False) -> tuple[str, int]:
    """
    Wrapper de compatibilidad para tz_core.kml_generator.generar_kml()
    
    MIGRADA EN EPIC 13 (26/12/2025): ~350 líneas extraídas a módulo profesional
    IMPLEMENTACIÓN REAL: tz_core.kml_generator.generar_kml()
    """
    from tz_core.kml_generator import generar_kml as generar_kml_modular
    
    # Inyectar CONFIG global y OVERRIDE_TOPS si existen
    config_param = CONFIG if 'CONFIG' in globals() else {}
    override_param = OVERRIDE_TOPS if 'OVERRIDE_TOPS' in globals() else None
    
    return generar_kml_modular(
        df=df,
        archivo_salida_kml=archivo_salida_kml,
        config=config_param,
        flat=flat,
        override_tops=override_param
    )


HTML_SECCION_INTERACCIONES = ""
HTML_SECCION_ANTENAS = ""
# === HTML-INTERACCIONES-1 (inicio) ========================================
def _construir_seccion_interacciones(df, dias=3, columnas_config=None):
    """
    Construye una sección HTML con 'Interacciones de los últimos N días registrados en bitácora'.
    - Subsecciones por fecha (dd/mm/aaaa), orden: más reciente -> más antiguo.
    - Por cada fecha: tabla por contacto con #interacciones, duración acumulada, antena top y sus coords/azimut.
    - Si una fecha no tiene antenas válidas: muestra nota.
    """

    # Helpers
    def _pick_col(df, candidatos):
        for c in candidatos:
            if c and c in df.columns:  # Ignora None y strings vacíos
                return c
        return None

    def _to_datetime_series(df):
        # Intento 1: combinación fecha + hora
        if 'fecha' in df.columns and 'hora' in df.columns:
            try:
                return pd.to_datetime(df['fecha'].astype(str).str.strip() + ' ' + df['hora'].astype(str).str.strip(),
                                      dayfirst=True, errors='coerce')
            except Exception:
                pass
        # Intento 2: columnas comunes
        for c in ['datetime', 'fecha_hora', 'timestamp', 'fec_hor', 'fechaHora']:
            if c in df.columns:
                s = pd.to_datetime(df[c], dayfirst=True, errors='coerce')
                if s.notna().any():
                    return s
        # Intento 3: solo fecha
        if 'fecha' in df.columns:
            s = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
            return s
        return pd.Series(pd.NaT, index=df.index)

    def _fmt_hms(total_seconds):
        try:
            total_seconds = float(total_seconds)
        except Exception:
            return "00:00:00"
        if np.isnan(total_seconds):
            return "00:00:00"
        total_seconds = int(round(total_seconds))
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    # Column mapping - buscar primero por config, luego por nombres canónicos y fallbacks
    columnas_config = columnas_config or {}
    
    # Si viene mapeado desde config, usar ese nombre; si no, buscar por nombres estándar
    col_contacto = _pick_col(df, [
        columnas_config.get('contacto'),
        columnas_config.get('tel_contacto'),
        columnas_config.get('destino'),
        columnas_config.get('b_party'),
        'contacto', 'tel_contacto', 'destino', 'b_party', 'to', 'callee'
    ]) or 'tel_contacto'  # si no existe, más abajo se maneja

    col_duracion = _pick_col(df, [
        columnas_config.get('duracion'),
        'duracion', 'dur', 'duration', 'segundos', 'tiempo'
    ])
    col_antena = _pick_col(df, [
        columnas_config.get('antena'),
        'antena', 'nombre_antena', 'site_name', 'cell_name'
    ])
    col_lat = _pick_col(df, [
        columnas_config.get('lat'),
        'lat', 'latitud', 'latitude'
    ])
    col_long = _pick_col(df, [
        columnas_config.get('long'),
        columnas_config.get('lon'),
        'long', 'lon', 'longitud', 'lng', 'longitude'
    ])
    col_azimut = _pick_col(df, [
        columnas_config.get('azimut'),
        'azimut', 'azimuth', 'azi', 'angulo'
    ])

    # Columnas adicionales para la tabla detallada
    col_tipo = _pick_col(df, [
        columnas_config.get('tipo'),
        'tipo', 'interaccion', 'tipo_interaccion', 'interaction', 'tipo_llamada'
    ])
    col_celda = _pick_col(df, [
        columnas_config.get('celda'),
        'celda', 'cod_celda_inicial', 'cell_id', 'cgi'
    ])
    col_hora = _pick_col(df, [
        columnas_config.get('hora'),
        'hora', 'hora_inicial', 'time', 'timestamp'
    ])

    # === TOP-ANTENA-1A: bbox y validadores de coordenadas ===
    # Intentar leer bounding box (SV) desde config; si no, usar fallback
    try:
        _bbox_cfg = None
        if 'CONFIG' in globals() and isinstance(CONFIG, dict):
            _bbox_cfg = CONFIG.get("geografia", {}).get("sv_bbox", None)
    except Exception:
        _bbox_cfg = None

    if not (isinstance(_bbox_cfg, dict) and all(k in _bbox_cfg for k in ("lat_min","lat_max","lon_min","lon_max"))):
        # Aproximación para El Salvador
        _bbox_cfg = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

    def _valid_latlon_vals(lt, lg):
        """True si lat/lon son numéricas, no NaN, no (0,0) y dentro del bbox SV."""
        try:
            lt = float(lt); lg = float(lg)
            if np.isnan(lt) or np.isnan(lg):
                return False
            if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                return False
            return (_bbox_cfg["lat_min"] <= lt <= _bbox_cfg["lat_max"]) and (_bbox_cfg["lon_min"] <= lg <= _bbox_cfg["lon_max"])
        except Exception:
            return False

    def _es_valida_latlon_row(row):
        """Versión por fila: usa nombres de columnas detectados arriba."""
        if col_lat and col_long and (col_lat in row) and (col_long in row):
            return _valid_latlon_vals(row[col_lat], row[col_long])
        return False
    # === TOP-ANTENA-1A (fin) ===

    # Si no hay df razonable, retorna vacío (no rompe HTML)
    if df is None or df.empty:
        return ""

    # Construcción de datetime y fecha
    dt = _to_datetime_series(df)
    df_local = df.copy()
    df_local['_dt'] = dt
    df_local['_fecha'] = df_local['_dt'].dt.date
    df_local = df_local[df_local['_fecha'].notna()]
    if df_local.empty:
        return ""

    # TODOS los días con actividad (ordenados de más reciente a más antiguo)
    fechas_ord = sorted(df_local['_fecha'].dropna().unique().tolist(), reverse=True)
    if not fechas_ord:
        return ""
    # Ya no limitamos por 'dias', mostramos TODOS los días con actividad
    fechas_sel = fechas_ord

    # Si no hay columna de contacto, crea una genérica SIN DETERMINAR
    if col_contacto not in df_local.columns:
        df_local['_contacto'] = 'SIN DETERMINAR'
    else:
        df_local['_contacto'] = df_local[col_contacto].fillna('SIN DETERMINAR').astype(str).str.strip()
        df_local.loc[df_local['_contacto'] == '', '_contacto'] = 'SIN DETERMINAR'

    # Duración en segundos: si viene string tipo hh:mm:ss, conviértelo
    if col_duracion and col_duracion in df_local.columns:
        ser_dur = df_local[col_duracion]
        if pd.api.types.is_numeric_dtype(ser_dur):
            df_local['_dur_sec'] = pd.to_numeric(ser_dur, errors='coerce').fillna(0)
        else:
            # Parse formatos comunes
            def _parse_dur(x):
                x = str(x).strip()
                if not x or x.lower() in ('nan', 'none'):
                    return 0
                if x.isdigit():
                    return float(x)
                parts = x.split(':')
                try:
                    parts = [int(p) for p in parts]
                    if len(parts) == 3:
                        return parts[0]*3600 + parts[1]*60 + parts[2]
                    if len(parts) == 2:
                        return parts[0]*60 + parts[1]
                except Exception:
                    pass
                return 0
            df_local['_dur_sec'] = ser_dur.map(_parse_dur)
    else:
        df_local['_dur_sec'] = 0

    # HTML con dropdown y tabla por registro (con paginación 20 + ver más de 10)
    out = []
    out.append('<section id="interacciones-recientes">')
    out.append('<h2>Filtrar interacciones por fecha</h2>')
    out.append(f'<p>Nota: Se muestran <strong>{len(fechas_sel)}</strong> día(s) con actividad.</p>')

    # Banner de rango + dropdown (solo fechas)
    fmin = min(fechas_sel)
    fmax = max(fechas_sel)
    out.append(f"""
<div style="background:#e7f3ff;border-left:4px solid #2196F3;padding:12px;margin:12px 0;">
  <strong>📅 Rango:</strong> {pd.to_datetime(fmin).strftime('%d/%m/%Y')} — {pd.to_datetime(fmax).strftime('%d/%m/%Y')}
</div>
<div style="margin:12px 0 18px 0;">
  <label for="dia-selector" style="font-weight:600;margin-right:8px;">Seleccionar día:</label>
  <select id="dia-selector" style="padding:8px;font-size:1rem;border:1px solid #ccc;border-radius:4px;">
""")
    for d in fechas_sel:
        _dt = pd.to_datetime(d)
        label = _dt.strftime("%d/%m/%Y")
        out.append(f'<option value="{_dt.strftime("%Y-%m-%d")}">{label}</option>')
    out.append('</select></div>')

    # Recorre fechas seleccionadas
    for d in fechas_sel:
        df_d = df_local[df_local['_fecha'] == d].copy()
        # Orden cronológico por hora/_dt
        try:
            df_d = df_d.sort_values(by=['_dt'])
        except Exception:
            pass

        # ¿Fecha con alguna antena válida?
        antenas_validas = False
        if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
            antenas_validas = df_d[col_lat].notna().any() and df_d[col_long].notna().any()

        fecha_h = pd.to_datetime(d).strftime("%d/%m/%Y")
        out.append(f'<div id="content-{pd.to_datetime(d).strftime("%Y-%m-%d")}" class="day-content" style="display:none;">')
        out.append(f'<h3>Se muestran las interacciones del día: {fecha_h}</h3>')

        # KPIs del día
        total_dia = int(len(df_d))
        dur_total_dia = _fmt_hms(df_d['_dur_sec'].sum() if '_dur_sec' in df_d.columns else 0)

        # Validador de coordenadas con bbox El Salvador
        def _es_valida_latlon_row(row):
            try:
                lt = float(row[col_lat]) if (col_lat and col_lat in df_d.columns) else None
                lg = float(row[col_long]) if (col_long and col_long in df_d.columns) else None
                if lt is None or lg is None:
                    return False
                if np.isnan(lt) or np.isnan(lg):
                    return False
                if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                    return False
                # BBOX El Salvador
                try:
                    if 'CONFIG' in globals() and isinstance(CONFIG, dict):
                        bbox = CONFIG.get("geografia", {}).get("sv_bbox", None)
                        if bbox and isinstance(bbox, dict):
                            lat_min = bbox.get("lat_min", 12.9)
                            lat_max = bbox.get("lat_max", 14.5)
                            lon_min = bbox.get("lon_min", -90.3)
                            lon_max = bbox.get("lon_max", -87.6)
                        else:
                            lat_min, lat_max, lon_min, lon_max = 12.9, 14.5, -90.3, -87.6
                    else:
                        lat_min, lat_max, lon_min, lon_max = 12.9, 14.5, -90.3, -87.6
                    return (lat_min <= lt <= lat_max) and (lon_min <= lg <= lon_max)
                except Exception:
                    return True  # si falla el bbox, al menos validamos que no sea 0,0
            except Exception:
                return False

        if total_dia > 0:
            if col_antena and (col_antena in df_d.columns):
                _valid_rows = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
                antenas_unicas = int(_valid_rows[col_antena].dropna().astype(str).nunique()) if not _valid_rows.empty else 0
            else:
                antenas_unicas = 0
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                sin_antena_cnt = int((~df_d.apply(_es_valida_latlon_row, axis=1)).sum())
            else:
                sin_antena_cnt = total_dia
            pct_sin_antena = (sin_antena_cnt / total_dia) * 100.0
        else:
            antenas_unicas = 0
            pct_sin_antena = 0.0

        contactos_unicos = int(df_d['_contacto'].nunique()) if '_contacto' in df_d.columns else 0
        out.append(
            f'<p class="kpis-dia">'
            f'<span><strong>Interacciones:</strong> {total_dia}</span>'
            f' &nbsp;|&nbsp; <span><strong>Duración:</strong> {dur_total_dia}</span>'
            f' &nbsp;|&nbsp; <span><strong>Antenas únicas:</strong> {antenas_unicas}</span>'
            f' &nbsp;|&nbsp; <span><strong>Contactos únicos:</strong> {contactos_unicos}</span>'
            f' &nbsp;|&nbsp; <span><strong>Sin antena válida:</strong> {pct_sin_antena:.0f}%</span>'
            f'</p>'
        )

        if not antenas_validas:
            out.append('<p><em>Nota:</em> Esta fecha no registró antenas válidas en la bitácora.</p>')

        if df_d.empty:
            out.append('<p>Sin interacciones registradas.</p>')
            out.append('</div>')
            continue

        # Tabla detallada por registro
        include_celda = bool(col_celda) and (col_celda in df_d.columns)
        out.append('<div class="tabla-scroll">')
        out.append('<table class="tabla-compacta">')
        thead_cols = ["#","contacto","hora","tipo de interacción","duración","antena","lat","long","azimut"]
        if include_celda:
            thead_cols.append("celda")
        out.append('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in thead_cols) + '</tr></thead><tbody>')

        def _fmt_coord(val):
            try:
                if val is None:
                    return '—'
                val_f = float(val)
                if np.isnan(val_f):
                    return '—'
                return f"{val_f:.6f}"
            except Exception:
                return '—'

        def _fmt_az(v):
            if v is None:
                return '—'
            try:
                f = float(v)
                return f"{int(round(f))}"
            except Exception:
                s = str(v).strip()
                return s if s else '—'

        def _fmt_hora(row):
            try:
                if col_hora and (col_hora in row.index):
                    s = str(row[col_hora]).strip()
                    return s if s else '—'
                if pd.notna(row.get('_dt')):
                    return pd.to_datetime(row['_dt']).strftime('%H:%M:%S')
            except Exception:
                pass
            return '—'

        def _ant_fmt_link(ant, lt, lg):
            try:
                if ant and (lt is not None) and (lg is not None):
                    lt_f = float(lt); lg_f = float(lg)
                    if not (np.isnan(lt_f) or np.isnan(lg_f)):
                        url = f"https://www.google.com/maps?q={lt_f:.6f},{lg_f:.6f}"
                        return f'<a href="{url}" target="_blank" rel="noopener">{ant}</a>'
            except Exception:
                pass
            return (str(ant).strip() if str(ant).strip() else '—')

        # Render filas: 20 visibles, resto ocultas; botón "Ver más" muestra +10
        for idx, (_, r) in enumerate(df_d.iterrows(), start=1):
            contacto = str(r.get('_contacto', 'SIN DETERMINAR'))
            hora_val = _fmt_hora(r)
            tipo_val = (str(r.get(col_tipo, '')).strip() if col_tipo and (col_tipo in r.index) else '—')
            dur_hms = _fmt_hms(r.get('_dur_sec', 0))
            ant_val = _ant_fmt_link(r.get(col_antena, ''), r.get(col_lat, None), r.get(col_long, None)) if col_antena else '—'
            lat_val = _fmt_coord(r.get(col_lat, None))
            long_val = _fmt_coord(r.get(col_long, None))
            az_val = _fmt_az(r.get(col_azimut, None)) if col_azimut else '—'
            celda_val = (str(r.get(col_celda, '')).strip() if (include_celda and (col_celda in r.index)) else None)

            row_cls = '' if idx <= 20 else ' style="display:none" class="row-hidden"'
            tds = [
                f'<td class="mono">{idx}</td>',
                f'<td>{contacto}</td>',
                f'<td class="mono nowrap">{hora_val}</td>',
                f'<td>{tipo_val}</td>',
                f'<td class="mono nowrap">{dur_hms}</td>',
                f'<td>{ant_val}</td>',
                f'<td class="mono nowrap">{lat_val}</td>',
                    f'<td class="mono nowrap">{long_val}</td>',
                    f'<td class="mono">{az_val}°</td>'
                ]
            if include_celda:
                tds.append(f'<td class="mono">{(celda_val if celda_val else "—")}</td>')
            out.append('<tr data-day="' + pd.to_datetime(d).strftime('%Y-%m-%d') + '"' + row_cls + '>' + ''.join(tds) + '</tr>')

        out.append('</tbody></table></div>')

        # Botón Ver más (incrementa de 10 en 10) - solo si hay más de 20 registros
        if len(df_d) > 20:
            out.append(
                f"<div style='margin:10px 0;'>"
                f"<button class='ver-mas-btn' data-day='{pd.to_datetime(d).strftime('%Y-%m-%d')}' "
                f"style='padding:8px 12px;border:1px solid #ccc;border-radius:6px;background:#f8f8f8;cursor:pointer;'>Ver más registros</button>"
                f"</div>"
            )
        # === ALERTAS-2: avisos por fecha (concentración, movilidad, calidad) ===
        # Helper: distancia (km)
        def _haversine_km(lat1, lon1, lat2, lon2):
            from math import radians, sin, cos, sqrt, atan2
            R = 6371.0
            lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c

        # Helper: enmascarar contacto si está activado en CONFIG
        def _mask_contact(s):
            try:
                if 'CONFIG' in globals() and isinstance(CONFIG, dict):
                    cfg = CONFIG.get("html", {})
                    if cfg.get("enmascarar_contactos", False):
                        ult = int(cfg.get("enmascarar_ultimos", 4))
                        s = str(s)
                        return ("*" * max(0, len(s) - ult)) + s[-ult:]
            except Exception:
                pass
            return str(s)

        alertas = []

        # Agregación mínima por contacto para alertas de concentración
        try:
            if total_dia > 0:
                agg = (df_d.groupby('_contacto')
                              .agg(interacciones=('_contacto', 'size'),
                                   dur_total=('_dur_sec', 'sum'))
                              .reset_index())
            else:
                agg = pd.DataFrame()
        except Exception:
            agg = pd.DataFrame()

        # 1) Concentración por interacciones
        if total_dia > 0 and not agg.empty:
            agg_sorted = agg.sort_values(['interacciones', 'dur_total'], ascending=[False, False])
            top_row_inter = agg_sorted.iloc[0]
            prop_inter = top_row_inter['interacciones'] / total_dia
            if prop_inter >= 0.60:
                alertas.append(
                    f"Concentración (interacciones): {_mask_contact(top_row_inter['_contacto'])} acumula "
                    f"{prop_inter:.0%} del día ({int(top_row_inter['interacciones'])}/{total_dia})."
                )

        # 1b) Concentración por duración
        sum_dur = float(df_d['_dur_sec'].sum()) if '_dur_sec' in df_d.columns else 0.0
        if sum_dur > 0 and not agg.empty:
            agg_sorted_d = agg.sort_values(['dur_total', 'interacciones'], ascending=[False, False])
            top_row_dur = agg_sorted_d.iloc[0]
            prop_dur = float(top_row_dur['dur_total']) / sum_dur if sum_dur else 0.0
            if prop_dur >= 0.60:
                alertas.append(
                    f"Concentración (duración): {_mask_contact(top_row_dur['_contacto'])} acumula "
                    f"{prop_dur:.0%} del día ({_fmt_hms(top_row_dur['dur_total'])} de {_fmt_hms(sum_dur)})."
                )

        # 2) Movilidad: top 2 celdas válidas separadas > 2 km
        try:
            if col_antena and (col_lat in df_d.columns) and (col_long in df_d.columns):
                dfv = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
                if not dfv.empty:
                    top2 = (dfv.groupby(col_antena)
                            .agg(cnt=(col_antena, 'size'),
                                    lat=(col_lat, 'mean'),
                                    lon=(col_long, 'mean'))
                            .sort_values('cnt', ascending=False)
                            .head(2)
                            .reset_index())
                    if len(top2) >= 2:
                        a1, a2 = str(top2.loc[0, col_antena]), str(top2.loc[1, col_antena])
                        dist_km = _haversine_km(top2.loc[0, 'lat'], top2.loc[0, 'lon'],
                                                top2.loc[1, 'lat'], top2.loc[1, 'lon'])
                        if dist_km >= 2.0:
                            alertas.append(f"Movilidad: '{a1}' ↔ '{a2}' ≈ {dist_km:.1f} km (top 2 celdas del día).")
        except Exception:
            pass

        # 3) Calidad: % sin antena válida alto
        try:
            if total_dia > 0 and pct_sin_antena >= 30:
                alertas.append(f"Calidad: {pct_sin_antena:.0f}% de {total_dia} registros sin antena válida.")
        except Exception:
            pass

        # Render de alertas si hay al menos una
        if alertas:
            out.append('<div class="alertas-dia"><ul>')
            for a in alertas:
                out.append(f'<li class="alerta-item">{a}</li>')
            out.append('</ul></div>')
        # === ALERTAS-2 (fin) ===

        # === Mini-heatmap diario: genera un pequeño mapa por fecha ===
        # Se muestra DESPUÉS de las tablas y alertas
        try:
            # preparar filas válidas con lat/lon (usa el validador ya definido arriba con bbox)
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                df_points = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
            else:
                df_points = df_d.iloc[0:0]

            day_str = pd.to_datetime(d).strftime('%Y%m%d')

            def render_heatmap_html_for_day(df_day, day_id):
                """
                Genera un mapa que muestra TODAS las antenas únicas activadas en el día.
                Cada antena se muestra como un marcador con su nombre y conteo de activaciones.
                """
                antenas_dict = {}
                total_filas = 0
                if df_day is None or df_day.empty:
                    return f"<div class='map-notice'>Sin datos de ubicación para {pd.to_datetime(d).strftime('%d/%m/%Y')}</div>"
                
                # Recolectar y agrupar TODAS las antenas únicas del día
                for _, rr in df_day.iterrows():
                    total_filas += 1
                    try:
                        lat = float(rr[col_lat])
                        lon = float(rr[col_long])
                    except Exception:
                        continue
                    
                    # Agrupar por antena (usar lat/lon/nombre como clave única)
                    if col_antena and col_antena in df_day.columns:
                        name = str(rr.get(col_antena, ''))
                        if name and name != 'nan' and name != '':
                            # Usar coordenadas redondeadas para agrupar antenas muy cercanas
                            lat_round = round(lat, 5)  # ~1 metro de precisión
                            lon_round = round(lon, 5)
                            key = (lat_round, lon_round, name)
                            if key not in antenas_dict:
                                antenas_dict[key] = {'lat': lat, 'lon': lon, 'name': name, 'count': 0, 'azs': {}}
                            antenas_dict[key]['count'] += 1
                            # Registrar azimut si existe
                            if col_azimut and (col_azimut in df_day.columns):
                                try:
                                    azv = rr.get(col_azimut, None)
                                    if azv is not None and str(azv).strip() != '':
                                        azf = int(round(float(azv)))
                                        antenas_dict[key]['azs'][azf] = antenas_dict[key]['azs'].get(azf, 0) + 1
                                except Exception:
                                    pass

                if not antenas_dict:
                    return f"<div class='map-notice'>Sin antenas válidas para mapear en {pd.to_datetime(d).strftime('%d/%m/%Y')} (se procesaron {total_filas} registros con coordenadas)</div>"

                # Convertir TODAS las antenas a lista (sin limitar a top N)
                # Convertir a lista y calcular azimut principal por antena
                markers = []
                for item in antenas_dict.values():
                    azimut_principal = None
                    if item.get('azs'):
                        try:
                            azimut_principal = max(item['azs'].items(), key=lambda t: t[1])[0]
                        except Exception:
                            azimut_principal = None
                    markers.append({
                        'lat': item['lat'], 'lon': item['lon'], 'name': item['name'], 'count': item['count'], 'azimut': azimut_principal
                    })
                num_antenas = len(markers)
                
                # Log para debugging
                log(f"[DEBUG] Día {day_id}: {total_filas} registros procesados, {num_antenas} antenas únicas mapeadas")
                for m in markers:
                    log(f"  - {m['name']}: {m['count']} activaciones en ({m['lat']:.6f}, {m['lon']:.6f})")
                
                _markers_js = json.dumps(markers, ensure_ascii=False)
                div_id = f"heatmap-{day_id}"

                html = f'''<div style="margin:16px auto; max-width:95%; padding:0 20px;">
    <p style="font-size:12px; color:#666; margin:4px 0 8px;">
        Se muestran <strong>{num_antenas} antena(s)</strong> con coordenadas válidas de este día. 
        Haz clic en los marcadores para ver detalles de cada ubicación.
    </p>
    <div id="wrap-{div_id}" class="tz-map-wrap" style="position:relative;">
        <button class="tz-fs-btn" title="Pantalla completa" data-map-id="{div_id}" style="position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;">⛶</button>
        <div id="{div_id}" style="height:clamp(420px, 70vh, 720px); width:100%; margin-bottom:12px; border:1px solid #ddd; border-radius:6px;"></div>
    </div>
</div>
<script>
    (function(){{
        var markers = {_markers_js};
        if (!Array.isArray(markers) || markers.length === 0) return;
        try {{
            var map = L.map('{div_id}', {{ scrollWheelZoom: false }});
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OpenStreetMap' }}).addTo(map);
      
            // Crear bounds a partir de todos los marcadores
            var latlngs = markers.map(function(m){{ return [m.lat, m.lon]; }});
            var bounds = L.latLngBounds(latlngs);
            
            // Si solo hay 1 marcador, usar zoom 12; si hay varios, fitBounds con padding muy generoso
            if (markers.length === 1) {{
                map.setView([markers[0].lat, markers[0].lon], 12);
            }} else {{
                try {{ 
                    map.fitBounds(bounds, {{ padding: [80, 80] }}); 
                }} catch(e) {{ 
                    map.setView(latlngs[0], 10); 
                }}
            }}
      
            // Agregar TODOS los marcadores de antenas
            markers.forEach(function(m, idx) {{
                var mk = L.marker([m.lat, m.lon]).addTo(map);
        
                // Log para verificar que se agregó
                console.log('Marcador ' + (idx+1) + ': ' + m.name + ' en [' + m.lat + ', ' + m.lon + '] con ' + m.count + ' activaciones');
        
                var popupHtml = '' +
                    '<div style="font-family:sans-serif;min-width:180px;">' +
                    '<strong style="font-size:14px;">Antena #' + (idx+1) + '</strong><br>' +
                    '<strong style="font-size:13px;color:#333;">' + (m.name || '') + '</strong><br>' +
                    '<span style="font-size:12px;color:#666;">Activaciones: ' + (m.count || 0) + '</span><br>' +
                    '<span style="font-size:11px;color:#999;">Coordenadas: ' + (typeof m.lat==='number'? m.lat.toFixed(6): m.lat) + ', ' + (typeof m.lon==='number'? m.lon.toFixed(6): m.lon) + '</span>' +
                    ((m.azimut !== null && m.azimut !== undefined) ? "<br><span style=\'font-size:12px;color:#666;\'>Azimut principal: " + m.azimut + "°</span>" : '') +
                    '</div>';
                mk.bindPopup(popupHtml, {{ maxWidth: 250 }});
            }});

            // Registrar mapa y bounds para re-encuadre al cambiar de día
            try {{
                window.__tzDailyMaps = window.__tzDailyMaps || {{}};
                window.__tzDailyMaps['{div_id}'] = {{
                    map: map,
                    bounds: bounds,
                    markersCount: markers.length,
                    center: (latlngs && latlngs.length>0) ? latlngs[0] : null,
                    wrapperId: 'wrap-{div_id}'
                }};
            }} catch(e) {{}}
        }} catch(err) {{ console.error('heatmap-day error', err); }}
    }})();
</script>'''
                return html

            sec_day_heatmap = render_heatmap_html_for_day(df_points, day_str)
            out.append(sec_day_heatmap)
        except Exception as e:
            # no bloquear la generación por un fallo en el mapa
            log(f"[WARN] Error generando mini-heatmap para {day_str}: {e}")
            import traceback
            log(traceback.format_exc())

        # Cerrar contenedor del día
        out.append('</div>')  # cierra day-content

    # Estilos mínimos (reusa tu CSS si ya existe; acá defensivo)
    out.append("""
<style>
#interacciones-recientes .tabla-compacta { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
#interacciones-recientes .tabla-compacta th, 
#interacciones-recientes .tabla-compacta td { border: 1px solid #ddd; padding: 16px 32px; text-align: center; }
#interacciones-recientes .tabla-compacta th { background: #f2f2f2; }
#interacciones-recientes .tabla-scroll { overflow-x: auto; }
#interacciones-recientes tr.resalte { font-weight: 600; }
#interacciones-recientes .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
#interacciones-recientes .nowrap { white-space: nowrap; }
</style>
""")
    out.append("""
<style>
#interacciones-recientes .kpis-dia { margin: 4px 0 10px 0; font-size: 0.95rem; color: #333; }
#interacciones-recientes .kpis-dia span { display: inline-block; margin-right: 10px; }
</style>
""")
    out.append("""
<style>
#interacciones-recientes .alertas-dia { margin: 8px 0 18px 0; }
#interacciones-recientes .alertas-dia ul { margin: 0 0 0 18px; padding: 0; }
#interacciones-recientes .alerta-item { color: #b45309; }
</style>
""")
    # JS: mostrar/ocultar contenedores + ver más por día
    out.append("""
<script>
(function(){
    function showDay(dateStr){
        var all = document.querySelectorAll('#interacciones-recientes .day-content');
        all.forEach(function(el){ el.style.display = 'none'; });
        var el = document.getElementById('content-' + dateStr);
        if(el){
            el.style.display = 'block';
            // Reencuadrar el mapa del día mostrado (Leaflet necesita invalidateSize en contenedores que estaban ocultos)
            setTimeout(function(){
                try {
                    var key = 'heatmap-' + String(dateStr).replace(/-/g,'');
                    var reg = (window.__tzDailyMaps || {})[key];
                    if (reg && reg.map) {
                        reg.map.invalidateSize();
                        if (reg.markersCount === 1 && reg.center) {
                            reg.map.setView(reg.center, 12);
                        } else if (reg.bounds) {
                            reg.map.fitBounds(reg.bounds, { padding: [80, 80] });
                        }
                    }
                } catch(e) {}
            }, 0);
        }
    }
    var sel = document.getElementById('dia-selector');
    if(sel){ sel.addEventListener('change', function(){ showDay(this.value); });
             if(sel.options.length>0){ showDay(sel.options[0].value); } }

    // Ver más: revela 10 filas ocultas por click
    document.querySelectorAll('#interacciones-recientes .ver-mas-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
            var day = this.getAttribute('data-day');
            var rows = document.querySelectorAll('tr[data-day="' + day + '"].row-hidden');
            var reveal = 10;
            var count = 0;
            for(var i=0;i<rows.length && count<reveal;i++,count++){
                rows[i].style.display = 'table-row';
                rows[i].classList.remove('row-hidden');
            }
            if(document.querySelectorAll('tr[data-day="' + day + '"].row-hidden').length === 0){
                this.style.display = 'none';
            }
        });
    });

    // Delegación: botón de pantalla completa en mapas diarios
    document.addEventListener('click', function(ev){
        var btn = ev.target.closest('.tz-fs-btn');
        if(!btn) return;
        var mapId = btn.getAttribute('data-map-id');
        var reg = (window.__tzDailyMaps || {})[mapId];
        if(!reg || !reg.map) return;
        var wrap = document.getElementById('wrap-' + mapId);
        if(!wrap) return;
        var mapEl = document.getElementById(mapId);
        if(!mapEl) return;

        var fs = wrap.classList.toggle('tz-fs-active');
        if(fs){
            // Entrar a pseudo pantalla completa
            wrap.setAttribute('data-prev-scroll', String(window.scrollY||0));
            mapEl.setAttribute('data-prev-height', mapEl.style.height || '');
            // Estilos para overlay
            wrap.style.position = 'fixed';
            wrap.style.inset = '0';
            wrap.style.zIndex = '9999';
            mapEl.style.height = '100%';
            document.body.style.overflow = 'hidden';
        } else {
            // Salir
            var prevH = mapEl.getAttribute('data-prev-height') || '';
            mapEl.style.height = prevH;
            wrap.style.position = 'relative';
            wrap.style.inset = '';
            wrap.style.zIndex = '';
            document.body.style.overflow = '';
            var sy = parseInt(wrap.getAttribute('data-prev-scroll')||'0',10) || 0;
            window.scrollTo(0, sy);
        }
        // Recalcular mapa
        setTimeout(function(){
            try{
                reg.map.invalidateSize();
                if (reg.markersCount === 1 && reg.center) {
                    reg.map.setView(reg.center, fs ? 13 : 12);
                } else if (reg.bounds) {
                    reg.map.fitBounds(reg.bounds, { padding: fs ? [100,100] : [80,80] });
                }
            }catch(e){}
        }, 50);
    });
})();
</script>
""")

    out.append('</section>')
    return "".join(out)
def _construir_seccion_todos_contactos(df, columnas_config=None):
    """Wrapper de compatibilidad - usa tz_core.analytics.construir_seccion_todos_contactos"""
    from tz_core.analytics import construir_seccion_todos_contactos as contactos_modular
    return contactos_modular(df, columnas_config)


# === HTML-INTERACCIONES-1 (fin) ===========================================
# === RANGOS-UTILS (desde config, soporta cruces de medianoche) ===
from datetime import time as _time, datetime as _dt

def _parse_hhmmss_to_minutes(s: str | None) -> int | None:
    """Convierte 'HH:MM' o 'HH:MM:SS' a minutos desde 00:00. Devuelve None si no se puede."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        # ignorar segundos si vienen
        return hh * 60 + mm
    except Exception:
        return None

def _minutes_from_any(hora) -> int | None:
    """
    Acepta: datetime.time, datetime.datetime, pandas.Timestamp, str 'HH:MM(:SS)'.
    Devuelve minutos desde 00:00 o None.
    """
    try:
        # pandas.Timestamp o datetime
        if hasattr(hora, "hour") and hasattr(hora, "minute"):
            return int(hora.hour) * 60 + int(hora.minute)
        if isinstance(hora, _time):
            return hora.hour * 60 + hora.minute
        # string
        return _parse_hhmmss_to_minutes(str(hora))
    except Exception:
        return None

def _construir_rangos_cfg(rangos_cfg: list[dict]) -> list[tuple[str, int, int]]:
    """Wrapper de compatibilidad - usa tz_core.analytics.construir_rangos_cfg"""
    from tz_core.analytics import construir_rangos_cfg as rangos_modular
    return rangos_modular(rangos_cfg)

def _en_rango_minutos_local(minutos: int, ini: int, fin: int) -> bool:
    """
    True si 'minutos' cae dentro del rango [ini..fin] en minutos.
    Soporta cruce de medianoche: si ini > fin, el rango pasa por 00:00.
    """
    return en_rango_minutos(minutos, ini, fin)

def etiqueta_rango(hora, rangos_cfg: list[dict], default: str = "Sin rango") -> str:
    """Wrapper de compatibilidad - usa tz_core.analytics.etiqueta_rango"""
    from tz_core.analytics import etiqueta_rango as etiqueta_modular
    return etiqueta_modular(hora, rangos_cfg, default)
# === FIN RANGOS-UTILS ===


def generar_informe_html(df: pd.DataFrame, archivo_kml: str, carpeta_salida: str, nombre_salida: str, hoja: str | None = None, nombre_bitacora: str | None = None) -> str:
    """
    Genera un informe HTML sencillo (portada + KPIs + enlaces) en la misma carpeta del KML.
    Retorna la ruta del HTML generado.
    """
    # 🔧 MÓDULO EXTRAÍDO: HTML generator para generar_informe_html (ya en imports globales)
    
    # Validación defensiva de entrada
    if df is None:
        log("[ERROR] generar_informe_html: DataFrame es None, abortando")
        return ""
    if df.empty:
        log("[WARN] generar_informe_html: DataFrame vacío, generando reporte mínimo")
        # Continuar para crear archivo con mensaje de ausencia de datos
    
    from datetime import datetime
    
    # =============================================================
    # === Generación de salidas: HTML, KML, KMZ, TXT ===
    # Aquí se construyen los archivos de salida principales.
    # Los metadatos de alias/usuario/abonado se incluyen si existen.
    # =============================================================
    kml_name = os.path.basename(archivo_kml)  # nombre base, p.ej. "caso.kml"
    kmz_name = os.path.splitext(kml_name)[0] + ".kmz"

    # Integración de campos canónicos no esenciales en resultados
    df_html = df.copy()
    if "alias" in df.columns:
        df_html["Alias"] = df["alias"]
    if "usuario" in df.columns:
        df_html["Usuario"] = df["usuario"]
    if "abonado" in df.columns:
        df_html["Abonado"] = df["abonado"]

    # Asegurar que los campos se incluyan en la generación de KML/KMZ
    kml_data = {}
    if "alias" in df.columns:
        kml_data["Alias"] = df["alias"].tolist()
    if "usuario" in df.columns:
        kml_data["Usuario"] = df["usuario"].tolist()
    if "abonado" in df.columns:
        kml_data["Abonado"] = df["abonado"].tolist()

    if bool(CONFIG.get("salida", {}).get("separar_kml_kmz", False)):
        # El HTML se guarda en carpeta_salida (raíz). KML está en /kml y KMZ en /kmz
        kml_href = os.path.join("kml", kml_name) if os.path.basename(os.path.dirname(archivo_kml)).lower() == "kml" else kml_name
        kmz_rel  = os.path.join("kmz", kmz_name)
        kmz_abs  = os.path.join(carpeta_salida, kmz_rel)
        kmz_exists = os.path.exists(kmz_abs)
        kmz_link = f' | <a href="{kmz_rel}" download>Descargar KMZ</a>' if kmz_exists else ""
    else:
        kml_href = kml_name
        kmz_abs  = os.path.join(carpeta_salida, kmz_name)
        kmz_exists = os.path.exists(kmz_abs)
        kmz_link = f' | <a href="{kmz_name}" download>Descargar KMZ</a>' if kmz_exists else ""

    # --- Métricas rápidas ---
    total = int(len(df))
    # coords válidas
    lat_num = pd.to_numeric(df.get("lat", pd.Series(dtype=float)), errors="coerce")
    lon_num = pd.to_numeric(df.get("long", pd.Series(dtype=float)), errors="coerce")
    valid_coord = int((lat_num.notna() & lon_num.notna()).sum())
    coord_validas = int(valid_coord)
    coord_invalidas = int(total - coord_validas)

    # antenas únicas (mismo filtro que la tabla: sin nombres inválidos y con coords válidas)
    if "antena" in df.columns:
        s_ant = df["antena"].astype(str).str.strip()
        invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        m_name = ~s_ant.str.lower().isin(invalid_names)

        latn = pd.to_numeric(df.get("lat", pd.Series(dtype=float)), errors="coerce")
        lonn = pd.to_numeric(df.get("long", pd.Series(dtype=float)), errors="coerce")
        m_coord = (
            latn.notna() & lonn.notna() &
            ~((latn.fillna(0) == 0) & (lonn.fillna(0) == 0)) &
            latn.between(-90, 90) & lonn.between(-180, 180)
        )
        activaciones_total = len(df)
        coord_validas   = int(m_coord.sum())
        coord_invalidas = int(activaciones_total - coord_validas)


        ant_series_f = s_ant[m_name & m_coord]
        ant_uniq = int(ant_series_f.nunique()) if not ant_series_f.empty else 0

        if not ant_series_f.empty:
            vc = ant_series_f.value_counts()
            top_antena = vc.index[0]
            top_count = int(vc.iloc[0])
            top_pct = (top_count / len(ant_series_f) * 100.0)
        else:
            top_antena, top_count, top_pct = "—", 0, 0.0
    else:
        ant_uniq = 0
        top_antena, top_count, top_pct = "—", 0, 0.0
        print(f"Antenas únicas (KPI): {ant_uniq} — Top antena: {top_antena} ({top_count})")

    # celdas únicas (robusto: usa LAC+CID si ambos; si no, el que exista)
    cel_label = "Celdas (CID) únicas"
    cel_uniq = 0
    try:
        has_cid = any(c in df.columns for c in ["celda", "cid", "cellid", "cell_id"])
        has_lac = any(c in df.columns for c in ["lac", "lac_id", "lacid"])
        if has_cid and has_lac:
            ccol = next(c for c in ["celda", "cid", "cellid", "cell_id"] if c in df.columns)
            lcol = next(c for c in ["lac", "lac_id", "lacid"] if c in df.columns)
            s_c = df[ccol].dropna().astype(str).str.strip()
            s_l = df[lcol].dropna().astype(str).str.strip()
            m_c = s_c != ""
            m_l = s_l != ""
            if (m_c.any() and m_l.any()):
                cel_label = "Parejas LAC+CID únicas"
                cel_uniq = int(df.loc[m_c.index[m_c] & m_l.index[m_l], [lcol, ccol]].drop_duplicates().shape[0])
            elif m_c.any():
                cel_label = "Celdas (CID) únicas"
                cel_uniq = int(s_c[m_c].nunique())
            elif m_l.any():
                cel_label = "LAC únicas"
                cel_uniq = int(s_l[m_l].nunique())
        elif has_cid:
            ccol = next(c for c in ["celda", "cid", "cellid", "cell_id"] if c in df.columns)
            s_c = df[ccol].dropna().astype(str).str.strip()
            s_c = s_c[s_c != ""]
            cel_uniq = int(s_c.nunique()) if not s_c.empty else 0
        elif has_lac:
            lcol = next(c for c in ["lac", "lac_id", "lacid"] if c in df.columns)
            s_l = df[lcol].dropna().astype(str).str.strip()
            s_l = s_l[s_l != ""]
            cel_label = "LAC únicas"
            cel_uniq = int(s_l.nunique()) if not s_l.empty else 0
    except Exception as e:
        log(f"[WARN] generar_informe_html: Error calculando celdas únicas: {e}")

    # rango de fechas/horas (visual dd/mm/aaaa HH:MM — dd/mm/aaaa HH:MM)
    rango_str = "Sin datos"

    # 🔧 EXTRAÍDO: Usando fmt_dt del módulo html_helpers
    if "fecha" in df.columns:
        # Preferir combinar fecha+hora si existe 'hora'
        dt = None
        try:
            if "hora" in df.columns and df["hora"].notna().any():
                dt = pd.to_datetime(
                    df["fecha"].astype(str).str.strip() + " " + df["hora"].astype(str).str.strip(),
                    dayfirst=True, errors="coerce"
                ).dropna()
            else:
                # Solo fecha: tomar 00:00 para el inicio y 23:59 para el fin
                fechas = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce").dropna()
                if not fechas.empty:
                    fmin = fechas.min().normalize()                        # 00:00
                    fmax = (fechas.max().normalize() + pd.Timedelta(hours=23, minutes=59))
                    rango_str = f"{fmt_dt(fmin)} — {fmt_dt(fmax)}"
                else:
                    rango_str = "Sin datos"
        except Exception as e:
            log(f"[WARN] generar_informe_html: Error procesando rango de fechas: {e}")
            dt = None

        if dt is not None and not dt.empty:
            min_ts, max_ts = dt.min(), dt.max()
            rango_str = f"{fmt_dt(min_ts)} — {fmt_dt(max_ts)}"
        elif dt is None:
            # ya se resolvió arriba (solo fecha) o quedó Sin datos
            rango_str = rango_str if 'rango_str' in locals() else "Sin datos"
    else:
        rango_str = "Sin datos"


    # color tema para acentos (del CONFIG si está)
    try:
        theme_hex = CONFIG.get("style", {}).get("theme_hex", "#ff00ff")
    except Exception:
        theme_hex = "#ff00ff"

    # fecha/hora generación
    gen_dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # --- Identificación del número analizado (se omite lo que no exista) ---
    # 🔧 EXTRAÍDO: Usando first_nonempty_in del módulo html_helpers

    # 🔧 EXTRAÍDO: Usando nunique_in del módulo html_helpers
    
    # 🔧 EXTRAÍDO: Usando unique_values_in del módulo html_helpers

    # 🔧 EXTRAÍDO: Usando fmt_imei_item del módulo html_helpers

    # 🔧 EXTRAÍDO: Usando row_html del módulo html_helpers
        
    # 🔧 EXTRAÍDO: Usando luhn_check del módulo html_helpers

    # 🔧 EXTRAÍDO: Usando is_valid_imei del módulo html_helpers

    tel_cols    = ["tel","telefono","numero","msisdn","a_number","origen","from","callingnumber","num"]
    alias_cols  = ["alias","alias_usuario","apodo"]
    user_cols   = ["usuario","nombre_usuario","suscriptor","user_name"]
    abon_cols   = ["abonado","titular","owner","subscriber"]
    imei_cols   = ["imei","imei1","imei_1"]

    # [IMSI] columnas canónicas
    imsi_cols  = ["imsi","imsi1","imsi_1","imsi_origen"]

    tel_val     = first_nonempty_in(df, tel_cols)
    alias_val   = first_nonempty_in(df, alias_cols)
    user_val    = first_nonempty_in(df, user_cols)
    abon_val    = first_nonempty_in(df, abon_cols)
    imei_raw    = first_nonempty_in(df, imei_cols)

    # [IMSI] obtener valor único (similar a IMEI)
    imsi_raw = first_nonempty_in(df, imsi_cols)
    if imsi_raw is not None:
        try:
            f = float(str(imsi_raw))
            if f.is_integer():
                imsi_val = str(int(f))
            else:
                imsi_val = str(imsi_raw)
        except Exception:
            imsi_val = str(imsi_raw)
    else:
        imsi_val = None


    # Si faltan alias/usuario/abonado, pedir un valor único y aplicarlo a toda la hoja
    def _ask_if_missing(label_visible: str, current_value, col_name: str):
        try:
            val_actual = (str(current_value).strip() if current_value is not None else "")
        except Exception:
            val_actual = ""
        if val_actual:
            return current_value  # ya había algo
        try:
            entrada = ""
        except Exception:
            entrada = ""
        if entrada:
            # crear/llenar la columna para que figure en HTML/KML
            try:
                df[col_name] = entrada
            except Exception:
                pass
            return entrada
        return current_value

    alias_val = _ask_if_missing("alias", alias_val, "alias")
    user_val  = _ask_if_missing("nombre_usuario", user_val, "usuario")
    abon_val  = _ask_if_missing("abonado", abon_val, "abonado")

    # IMEI: quitar .0 si vino como float
    if imei_raw is not None:
        try:
            f = float(str(imei_raw))
            if f.is_integer():
                imei_val = str(int(f))
            else:
                imei_val = str(imei_raw)
        except Exception:
            imei_val = str(imei_raw)
    else:
        imei_val = None

    # Si hay múltiples valores en alguna columna, mostrar "múltiples (N)"
    tel_n  = nunique_in(df, tel_cols)
    ali_n  = nunique_in(df, alias_cols)
    usr_n  = nunique_in(df, user_cols)
    abo_n  = nunique_in(df, abon_cols)
    ime_n  = nunique_in(df, imei_cols)
    # [IMSI] conteo de valores únicos
    imsi_n  = nunique_in(df, imsi_cols)


    def _fmt_uni(val, n):
        if n > 1:   return f"múltiples ({n})"
        if val:     return val
        return None

    tel_disp   = _fmt_uni(tel_val,  tel_n)
    alias_disp = _fmt_uni(alias_val, ali_n)
    user_disp  = _fmt_uni(user_val, usr_n)
    abon_disp  = _fmt_uni(abon_val, abo_n)
    imei_disp  = _fmt_uni(imei_val,  ime_n)
    # [IMSI] display único
    imsi_disp = _fmt_uni(imsi_val, imsi_n)


    # Listas de valores (para cuando hay múltiples)
    tel_list,  tel_more  = unique_values_in(df, tel_cols,  max_items=8)
    ali_list,  ali_more  = unique_values_in(df, alias_cols, max_items=8)
    usr_list,  usr_more  = unique_values_in(df, user_cols, max_items=8)
    abo_list,  abo_more  = unique_values_in(df, abon_cols, max_items=8)
    imei_list, imei_more = unique_values_in(df, imei_cols, max_items=20)
    
    # limpiar “.0” y filtrar inválidos (0, null/none/nan, todos ceros, Luhn malo, etc.)
    imei_list = [fmt_imei_item(x) for x in imei_list]
    imei_list = [x for x in imei_list if is_valid_imei(x)]
    if not imei_list:
        imei_disp = None
        imei_more = 0
    
    # [IMSI] lista de valores (múltiples)
    imsi_list, imsi_more = unique_values_in(df, imsi_cols, max_items=20)

    # limpieza ligera
    _tmp = []
    for x in imsi_list:
        try:
            s = str(x).strip()
            try:
                f = float(s)
                if f.is_integer():
                    s = str(int(f))
            except Exception:
                pass
            s = re.sub(r"\D", "", s)
            if 14 <= len(s) <= 16:
                _tmp.append(s)
        except Exception:
            continue
    imsi_list = _tmp
    if not imsi_list:
        imsi_disp = None
        imsi_more = 0


    ident_rows = ""
    ident_rows = ""
    # 1) Número telefónico (antes decía "Número analizado")
    # Asociar IMSI a cada número telefónico si existen
    if tel_list and imsi_list:
        # Si hay varios números, asociar IMSI por número si posible
        tel_imsi = []
        for tel in tel_list:
            # Buscar IMSI asociados a ese número (si hay relación en el DataFrame)
            imsis = set()
            for idx, row in df.iterrows():
                if str(row.get('tel','')).strip() == str(tel):
                    imsi_val = row.get('imsi','')
                    if imsi_val:
                        imsis.add(str(imsi_val).strip())
            if imsis:
                tel_imsi.append(f"{tel} — IMSI: {', '.join(imsis)}")
            else:
                tel_imsi.append(str(tel))
        ident_rows += row_html("Número telefónico", None, len(tel_imsi), tel_imsi, 0, mono=True)
    else:
        ident_rows += row_html("Número telefónico", tel_disp,  tel_n,  tel_list,  tel_more,  mono=True)
    # 2) IMEI (subimos esta fila para que quede inmediatamente debajo del número)
    ident_rows += row_html("IMEI",             imei_disp,  ime_n,  imei_list, imei_more, mono=True)
    # 3) Alias
    ident_rows += row_html("Alias",            alias_disp, ali_n,  ali_list,  ali_more,  mono=False)
    # 4) Usuario
    ident_rows += row_html("Usuario",          user_disp,  usr_n,  usr_list,  usr_more,  mono=False)
    # 5) Abonado
    ident_rows += row_html("Abonado",          abon_disp,  abo_n,  abo_list,  abo_more,  mono=False)


    # --- Top contactos (por conteo y por duración) ---
    def _to_seconds_any(x) -> float:
        """Convierte '1128' o '00:18:48' a segundos. Tolerante."""
        try:
            s = str(x).strip()
            if not s or s.lower() in {"nan","none","null","sin inf.","sin inf","s/i"}:
                return 0.0
            if ":" in s:
                parts = s.split(":")
                if len(parts) == 3:
                    h,m,sec = parts
                    return float(int(h))*3600 + float(int(m))*60 + float(int(sec))
                if len(parts) == 2:
                    m,sec = parts
                    return float(int(m))*60 + float(int(sec))
            # num directo (segundos)
            return float(pd.to_numeric(s, errors="coerce") or 0.0)
        except Exception:
            return 0.0

    # detectar columna de contacto
    contact_cols = [
        "tel_contacto","contacto","destino","b_number","bnumber","numero_contacto",
        "callednumber","to","receptor","receptor_numero","numero_destino"
    ]
    dur_cols = ["duracion","duration","segundos","tiempo"]
    c_col = next((c for c in contact_cols if c in df.columns), None)
    d_col = next((c for c in dur_cols if c in df.columns), None)
    note_no_dur = "<p class='small' style='color:#666;background:#f7f7f7;border:1px solid #eee;padding:.5rem .75rem;border-radius:6px'>Se omite por no disponer de la columna <code>duracion</code>.</p>"
    note_zero_dur = "<p class='note muted'>No hay minutos acumulados &gt; 0 en el período; se omite la tabla.</p>"

    if not d_col:
        log("HTML: se omitió la subtabla 'Por minutos acumulados' por falta de 'duracion'.")


    top_contactos_cnt_html = "<p class='small'>No hay columna de contacto.</p>"
    top_contactos_dur_html = note_no_dur if not d_col else "<p class='small'>No hay columna de contacto.</p>"

    if c_col:
        # Top N de contactos según config
        try:
            if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('contactos') is not None:
                _topC = int(OVERRIDE_TOPS.get('contactos'))
            elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
                _topC = int(CONFIG.get("top_contactos", CONFIG.get("html", {}).get("top_contactos_n", 10)))
            else:
                _topC = 10
        except Exception:
            _topC = 10
        d = df.copy()
        d["_contacto"] = d[c_col].astype(str).str.strip()
        d = d[(d["_contacto"] != "") & d["_contacto"].notna()]

        if not d.empty:
            # segundos de duración
            if d_col:
                d["_sec"] = d[d_col].map(_to_seconds_any)
            else:
                d["_sec"] = 0.0

            # normalizar teléfono: dejar solo dígitos para agrupar (pero mostrar el original si querés luego)
            d["_c_norm"] = d["_contacto"].str.replace(r"\D+", "", regex=True)
            d.loc[d["_c_norm"] == "", "_c_norm"] = d["_contacto"]  # si quedó vacío, usa el texto crudo


            # por conteo (con % + barra + índice)
            g_cnt = (
                d.groupby("_c_norm", dropna=False)
                .size()
                .sort_values(ascending=False)
            )
            if int(_topC) > 0:
                g_cnt = g_cnt.head(int(_topC))
            total_cnt = int(len(d))
            rows = []
            for i, (k, n) in enumerate(g_cnt.items(), start=1):
                pct = (float(n) / total_cnt * 100.0) if total_cnt else 0.0
                rows.append(
                    f"<tr>"
                    f"<td class='right mono'>{i}</td>"
                    f"<td class='mono'>{k}</td>"
                    f"<td class='mono'>{int(n):,} <span class='small'>({pct:.1f}%)</span></td>"
                    f"</tr>"
                )
                rows.append(
                    f"<tr class='barrow'><td colspan='3'>"
                    f"<div class='bar'><div class='fill' style='width:{pct:.1f}%;'></div></div>"
                    f"</td></tr>"
                )
            if rows:
                top_contactos_cnt_html = (
                    "<table class='tbl'>"
                    "<thead><tr><th class='right'>#</th><th>Contacto</th><th>Interacciones</th></tr></thead>"
                    "<tbody>" + "".join(rows) + "</tbody></table>"
                )

            # por duración (con % + barra + índice)
            if d_col:
                g_dur = (
                    d.groupby("_c_norm", dropna=False)["_sec"]
                    .sum()
                    .sort_values(ascending=False)
                )
                if int(_topC) > 0:
                    g_dur = g_dur.head(int(_topC))
                def _fmt_hms(sec):
                    sec = int(round(sec))
                    h = sec // 3600; m = (sec % 3600) // 60; s = sec % 60
                    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

                # justo después de: total_sec = float(d["_sec"].sum())
                total_sec = float(pd.to_numeric(d["_sec"], errors="coerce").fillna(0).sum())

                if total_sec <= 0:
                    top_contactos_dur_html = note_zero_dur
                    log("HTML: se omitió 'Por minutos acumulados' porque la suma total de 'duracion' es 0.")
                else:
                    rows = []
                    for i, (k, tot) in enumerate(g_dur.items(), start=1):
                        pct = (float(tot) / total_sec * 100.0) if total_sec > 0 else 0.0
                        rows.append(
                            f"<tr>"
                            f"<td class='right mono'>{i}</td>"
                            f"<td class='mono'>{k}</td>"
                            f"<td class='mono'>{_fmt_hms(tot)} <span class='small'>({pct:.1f}%)</span></td>"
                            f"</tr>"
                        )
                        rows.append(
                            f"<tr class='barrow'><td colspan='3'>"
                            f"<div class='bar'><div class='fill' style='width:{pct:.1f}%;'></div></div>"
                            f"</td></tr>"
                        )
                    if rows:
                        top_contactos_dur_html = (
                            "<table class='tbl'>"
                            "<thead><tr><th class='right'>#</th><th>Contacto</th><th>Duración total</th></tr></thead>"
                            "<tbody>" + "\n".join(rows) + "</tbody></table>"
                        )

            # si no hay d_col o total_sec == 0, dejamos la nota en top_contactos_dur_html


    # HTML (sencillo, sin frameworks)
    html_path = os.path.join(carpeta_salida, f"{nombre_salida}_informe.html")
    # --- Top antenas (tabla) ---
    top_tab_html = "<p class='small'>No se encontraron antenas.</p>"
    if "antena" in df.columns:
        df_a = df.copy()
        df_a["antena"] = df_a.get("antena", "").astype(str).str.strip()
        _invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        df_a = df_a[~df_a["antena"].str.lower().isin(_invalid_names)]

        if not df_a.empty:
            # timestamp (fecha + hora si existe)
            if "fecha" in df_a.columns:
                hora_str = df_a.get("hora", "").astype(str).str[:8]
                ts = pd.to_datetime(
                    df_a["fecha"].astype(str).str.strip() + " " + hora_str,
                    errors="coerce", dayfirst=True
                )
                df_a["_ts"] = ts
            else:
                df_a["_ts"] = pd.NaT

            # azimut entero (para frecuencia)
            az = pd.to_numeric(df_a.get("azimut", pd.Series(dtype=float)), errors="coerce").round().astype("Int64")
            df_a["_az_i"] = az

            # coords numéricas
            df_a["_lat"] = pd.to_numeric(df_a.get("lat", pd.Series(dtype=float)), errors="coerce")
            df_a["_lon"] = pd.to_numeric(df_a.get("long", pd.Series(dtype=float)), errors="coerce")
            _mask_zerozero = df_a["_lat"].fillna(0).eq(0) & df_a["_lon"].fillna(0).eq(0)
            _mask_out = ~df_a["_lat"].between(-90, 90) | ~df_a["_lon"].between(-180, 180)
            df_a = df_a[~(_mask_zerozero | _mask_out)]


        # Construimos entradas y ordenamos por conteo (desc)
        entries = []
        for antenna, g in df_a.groupby("antena", dropna=False):
            cnt = int(len(g))
            lat_v = g["_lat"].dropna()
            lon_v = g["_lon"].dropna()
            lat_s = f"{lat_v.iloc[0]:.6f}" if not lat_v.empty else "—"
            lon_s = f"{lon_v.iloc[0]:.6f}" if not lon_v.empty else "—"
            azvc = g["_az_i"].dropna().value_counts().head(3)
            az_s = ", ".join([f"{int(k)}° ({int(v)})" for k, v in azvc.items()]) if not azvc.empty else "—"
            entries.append((cnt, antenna, lat_s, lon_s, az_s))

        entries.sort(key=lambda x: x[0], reverse=True)
        antenas_unicas = len(entries)

        rows = []
        for idx, (cnt, antenna, lat_s, lon_s, az_s) in enumerate(entries, start=1):
            # Si hay coordenadas válidas, convertir la antena en link a Google Maps
            if lat_s != "—" and lon_s != "—":
                ant_cell = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{antenna}</a>'
            else:
                ant_cell = antenna

            rows.append(
                f"<tr>"
                f"<td class='mono'>{idx}</td>"
                f"<td>{ant_cell}</td>"
                f"<td class='mono nowrap'>{lat_s}</td>"
                f"<td class='mono nowrap'>{lon_s}</td>"
                f"<td class='mono'>{cnt:,}</td>"
                f"<td>{az_s}</td>"
                f"</tr>"
            )


        if rows:
            top_tab_html = (
                "<table class='tbl'>"
                "<thead><tr>"
                "<th>#</th><th>Antena</th><th>Lat</th><th>Long</th><th>Conteo</th><th>Azimuts frecuentes</th>"
                "</tr></thead><tbody>"
                + "".join(rows) +
                "</tbody></table>"
            )


        # --- Contactos recientes (últimos 5 días del período) ---
        # Detectar columnas
        contacto_cols = [
            "tel_contacto","contacto","destino","b_number","bnumber",
            "numero_contacto","callednumber","to","receptor","receptor_numero","numero_destino"
        ]
        tipo_cols = ["interaccion","tipo_interaccion","interaction","tipo"]
        dur_cols  = ["duracion","duration","segundos","tiempo"]

        c_col = next((c for c in contacto_cols if c in df.columns), None)
        t_col = next((c for c in tipo_cols if c in df.columns), None)
        d_col = next((c for c in dur_cols  if c in df.columns), None)

        # Datetime robusto
        df_dt = df.copy()
        if "fecha" in df.columns and "hora" in df.columns:
            df_dt["_dt"] = pd.to_datetime(
                df["fecha"].astype(str).str.strip() + " " + df["hora"].astype(str).str[:8],
                dayfirst=True, errors="coerce"
            )
        elif "fecha" in df.columns:
            df_dt["_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
        elif "hora" in df.columns:
            today = pd.Timestamp.today().normalize()
            df_dt["_dt"] = pd.to_datetime(
                today.strftime("%Y-%m-%d") + " " + df["hora"].astype(str).str[:8],
                errors="coerce"
            )
        else:
            df_dt["_dt"] = pd.NaT

        max_dt = df_dt["_dt"].max()
        recent_html = ""
        if pd.notna(max_dt) and c_col:
            start = max_dt - pd.Timedelta(days=5)
            r = df_dt[df_dt["_dt"].between(start, max_dt)].copy()
            # Limpia contactos "vacíos"
            r[c_col] = r[c_col].astype(str).str.strip()
            r = r[(r[c_col] != "") & r[c_col].notna()]

            # Formateo
            r["_dt_str"] = r["_dt"].dt.strftime("%d/%m/%Y %H:%M:%S")
            def _fmt_sec(x):
                try:
                    s = str(x).strip()
                    if ":" in s:
                        return s  # ya viene HH:MM:SS
                    v = float(pd.to_numeric(s, errors="coerce") or 0.0)
                except Exception:
                    v = 0.0
                v = int(round(v))
                h = v // 3600; m = (v % 3600) // 60; s2 = v % 60
                return f"{h:02d}:{m:02d}:{s2:02d}" if h > 0 else f"{m:02d}:{s2:02d}"

            # Orden por fecha descendente y límite para no hacer pesado el HTML
            r = r.sort_values("_dt", ascending=False).head(200)

            filas = []
            for _, rr in r.iterrows():
                dt_s  = rr.get("_dt_str", "") or ""
                tipo  = rr.get(t_col, "") if t_col else ""
                cont  = rr.get(c_col, "")
                dur_s = _fmt_sec(rr.get(d_col, "")) if d_col else ""
                filas.append(
                    f"<tr>"
                    f"<td class='mono'>{dt_s}</td>"
                    f"<td>{tipo}</td>"
                    f"<td class='mono'>{cont}</td>"
                    f"<td class='mono'>{dur_s}</td>"
                    f"</tr>"
                )

            if filas:
                recent_html = ""


    # === TOPC (para títulos "Top N" en HTML) ===
    try:
        if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('contactos'):
            _topC = int(OVERRIDE_TOPS.get('contactos'))
        elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
            _topC = int(CONFIG.get("html", {}).get("top_contactos_n", 10))
        else:
            _topC = 10
    except Exception:
        _topC = 10

    # --- LOGO embebido: construir 'logo_html' SIEMPRE antes de interpolar el HTML ---
    try:
        import base64, mimetypes

        def _build_logo_html() -> str:
            """Devuelve el bloque <img> con logo embebido en base64 o un fallback SVG accesible.
            No depende de archivos externos: usa archivo si existe; si no, genera SVG inline.
            """
            # Config y atributos visibles
            _br_all = (CONFIG or {}) if 'CONFIG' in globals() else {}
            _brand  = _br_all.get('brand', {}) or {}
            _branding = _br_all.get('branding', {}) or {}

            # Alt y ancho deseado
            _alt = (
                str((_branding.get('logo_alt') or '')).strip()
                or str(((_brand.get('logo') or {}).get('alt') or '')).strip()
                or str(_brand.get('name') or 'TZ Analyzer').strip()
            )
            try:
                _w = int(((_brand.get('logo') or {}).get('width_px') or 120))
            except Exception:
                _w = 120

            # 1) Si en config viene un base64 directo, úsalo
            _b64_cfg = _branding.get('logo_base64') or (_brand.get('logo') or {}).get('base64')
            if isinstance(_b64_cfg, str) and _b64_cfg.strip():
                b64 = _b64_cfg.strip()
                if b64.startswith('data:'):
                    src = b64
                else:
                    # asumir PNG por defecto
                    src = f"data:image/png;base64,{b64}"
                return f'<img src="{src}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'

            # 2) Intentar archivo local si la ruta existe (robusto, nombres candidatos)
            _script_dir = os.path.dirname(__file__) if '__file__' in globals() else os.getcwd()
            _candidates = []
            # a) paths declarados en config
            for key_path in [(_branding.get('logo_path') or ''), (((_brand.get('logo') or {}).get('path')) or '')]:
                p = str(key_path or '').strip()
                if p:
                    _candidates.append(p)
            # b) candidatos comunes (soporta el caso "Logo TZ.png")
            _candidates.extend([
                'logo_tz.png', 'Logo TZ.png', 'Logo_TZ.png', 'logo.png', 'logo.svg', 'Logo.png', 'Logo.svg'
            ])

            for rel in _candidates:
                try:
                    p_abs = rel if os.path.isabs(rel) else os.path.join(_script_dir, rel)
                    if os.path.exists(p_abs) and os.path.isfile(p_abs):
                        mime, _ = mimetypes.guess_type(p_abs)
                        mime = mime or ('image/svg+xml' if p_abs.lower().endswith('.svg') else 'image/png')
                        with open(p_abs, 'rb') as fh:
                            data = fh.read()
                        b64 = base64.b64encode(data).decode('ascii')
                        return f'<img src="data:{mime};base64,{b64}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'
                except Exception:
                    continue

            # 3) Fallback: SVG inline accesible (sin archivos)
            _svg = (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='{_w}' height='{int(_w*0.38)}' viewBox='0 0 320 120' role='img' aria-label='{_alt}'>"
                "<rect width='320' height='120' fill='#0B57D0' rx='12'/>"
                "<text x='50%' y='53%' dominant-baseline='middle' text-anchor='middle' font-family='Segoe UI, Roboto, Arial, sans-serif' font-size='40' fill='white' font-weight='700'>TZ Analyzer</text>"
                "</svg>"
            )
            svg_uri = "data:image/svg+xml;utf8," + _svg.replace("\n", "")
            return f"<img src='{svg_uri}' alt='{_alt}' style='height:{_w}px;max-height:{_w}px'/>"

        logo_html = _build_logo_html()
    except Exception:
        # ante cualquier problema, evita romper: deja un placeholder textual
        logo_html = "<div style='font-weight:700;font-size:18px'>TZ Analyzer</div>"

    # 🔧 FASE 2.1: HTML Header extraído a módulo independiente  
    html_header = generate_html_header(theme_hex, nombre_salida)
    
    # 🔧 FASE 2.2: HTML Body Header extraído a módulo independiente
    body_header = generate_body_header(logo_html, nombre_salida, hoja, gen_dt, CONFIG)
    
    # 🔧 FASE 2.3: HTML Metadatos extraído a módulo independiente
    metadata_section = generate_metadata_section(nombre_bitacora, hoja, rango_str, ident_rows)
    
    # 🔧 FASE 2.4: HTML KPIs/Indicadores extraído a módulo independiente
    kpi_section = generate_kpi_section(total, coord_validas, coord_invalidas, ant_uniq, cel_uniq, cel_label, top_antena, top_count, top_pct)
    
    html = f"""{html_header}
{body_header}

{metadata_section}

{kpi_section}

    <section>
    <h2>Top antenas</h2>
    {top_tab_html}
  </section>
  
    <section>
    <h2>Contactos con más comunicación</h2>
    <p class="nota"><b>Nota:</b> en esta sección se muestran dos TOP LIST de los principales contactos con los que registra mayor interacciones tanto entrantes como salientes. el primer top list se construyo a partir del recuento de las interacciones tanto salietes como entrantes; el segundo se construyo a partir de los contactos con los que acumula más minutos tanto en interaciones entrantes como salientes. Le servirá para detectar patrones en la comunicación del número analizado.</p>
    <div class="two">
      <div>
        <h3 class="small">Top List por recuento de interacciones <span class="sub">(Top {_topC})</span></h3>
        {top_contactos_cnt_html}
      </div>
      <div>
        <h3 class="small">Top List por recuento de minutos acumulados <span class="sub">(Top {_topC})</span></h3>
        {top_contactos_dur_html}
      </div>
    </div>
  </section>

</body>
</html>
"""
    # --- TÍTULO H1 desde config.brand (name + version) ---
    try:
        _brand = CONFIG.get("brand", {}) if isinstance(CONFIG, dict) else {}
        _bname = str(_brand.get("name", "")).strip()
        _bver  = str(_brand.get("version", "")).strip()
        if _bname and _bver:
            _title = f"{_bname} — {_bver}"
        elif _bname:
            _title = _bname
        elif _bver:
            _title = _bver
        else:
            _title = ""
        _h1 = f'<h1 class="title">{_title}</h1>' if _title else ""
    except Exception:
        _h1 = ""

    # --- TÍTULO H1 desde config.brand (name + version) ---
    try:
        _brand = CONFIG.get("brand", {}) if isinstance(CONFIG, dict) else {}
        _bname = str(_brand.get("name", "")).strip()
        _bver  = str(_brand.get("version", "")).strip()
        if _bname and _bver:
            _title = f"{_bname} — {_bver}"
        elif _bname:
            _title = _bname
        elif _bver:
            _title = _bver
        else:
            _title = ""

        # ⬇️ Dejar SOLO este if, con pass adentro
        if _title:
            # Desactivado: no inyectar el H1 centrado
            pass

    except Exception:
        pass

        # === HTML-TOC-1: índice de navegación sticky (sin KML/KMZ) ===
    try:
        # 1) Asegurar IDs de secciones para poder enlazar
        html = html.replace('<section class="meta">', '<section id="meta" class="meta">')
        html = html.replace('<section>\n    <h2>Top antenas</h2>', '<section id="top-antenas">\n    <h2>Top antenas</h2>')
        html = html.replace('<h2 id="interacciones">Interacciones y contactos</h2>', '<h2 id="interacciones">Contactos con más comunicación</h2>')
        html = html.replace('<h2>Contactos con más comunicación</h2>', '<h2 id="interacciones">Contactos con más comunicación</h2>')
        html = html.replace('<h2>Antenas por rango horario</h2>', '<h2 id="rangos">Antenas por rango horario</h2>')
        # "Todos los contactos" ya sale con id="todos-contactos" cuando existe

        # 2) Construir links solo de las secciones presentes (orden deseado)
        _links = []
        if 'id="meta"' in html:
            _links.append('<a href="#meta">Metadatos</a>')
        if 'id="resumen-antenas"' in html:
            _links.append('<a href="#resumen-antenas">Antenas más activadas</a>')
        # Heatmap integrado visualmente en "Antenas más activadas"; no añadimos enlace separado al TOC.
        if 'id="interacciones"' in html:
            _links.append('<a href="#interacciones">Contactos con más comunicación</a>')
        # Aceptar dos posibles IDs para rangos horarios
        _id_rangos = None
        if 'id="antenas-rangos"' in html:
            _id_rangos = 'antenas-rangos'
        elif 'id="rangos"' in html:
            _id_rangos = 'rangos'
        if _id_rangos:
            _links.append(f'<a href="#{_id_rangos}">Antenas por rango horario</a>')
        # Incluir enlace a Historial de cambios si existe
        if 'id="historial-cambios"' in html:
            _links.append('<a href="#historial-cambios">Historial de cambios de antena</a>')
        if 'id="interacciones-recientes"' in html:
            _links.append('<a href="#interacciones-recientes">Interacciones recientes</a>')
        if 'id="top-antenas"' in html:
            _links.append('<a href="#top-antenas">Todas las antenas</a>')
        if 'id="todos-contactos"' in html:
            _links.append('<a href="#todos-contactos">Todos los contactos</a>')

        if _links:
            _toc_html = '<nav id="toc" class="toc" style="z-index:999; background:#fff; border-bottom:1px solid #e5e7eb; box-shadow:0 2px 6px rgba(0,0,0,.06); padding:8px 12px;">' + ' ... '.join(_links) + '</nav>'

            # 3) CSS para la barra sticky (desactivada en móvil)
            _css_toc = """
.toc{position:sticky;top:0;background:#fff;padding:8px 0 10px;margin:6px 0 10px;border-bottom:1px solid #eee;z-index:999}
.toc a{margin-right:10px;text-decoration:none;color:var(--accent);font-size:13px}
.toc a:hover{text-decoration:underline}
@media (max-width: 768px) {
  .toc{position:relative;top:auto;}
}
"""
            # Inyectar CSS dentro del <style>
            html = html.replace("</style>", _css_toc + "</style>", 1)
            # 4) Insertar el TOC inmediatamente después del </header>
            html = html.replace("</header>", "</header>\n  " + _toc_html, 1)
    except Exception:
        pass
    # === HTML-TOC-1 (fin) ===

    # === HTML-BRANDING-1: Marca de agua (usa config.branding) ===
    try:
        _br = (CONFIG or {}).get("branding", {}) if "CONFIG" in globals() else {}
        _mw_on   = bool(_br.get("mostrar_marca_agua", True))
        _mw_txt  = str(_br.get("marca_agua_texto", "CONFIDENCIAL"))
        _mw_opac = float(_br.get("marca_agua_opacidad", 0.08))
        _mw_print= bool(_br.get("marca_agua_en_impresion", True))

        if _mw_on and _mw_txt:
            _css_wm = f"""
.wm{{position:fixed;top:40%;left:50%;transform:translate(-50%,-50%) rotate(-28deg);color:#000;opacity:{_mw_opac};font-size:72px;font-weight:800;letter-spacing:.15em;white-space:nowrap;pointer-events:none;user-select:none;z-index:0}}
@media print{{ .wm{{display:{'block' if _mw_print else 'none'};position:fixed}} }}
"""
            # inyectar CSS en <style>
            html = html.replace("</style>", _css_wm + "</style>", 1)
            # insertar la marca de agua después del </header>
            html = html.replace("</header>", "</header>\n  " + f"<div class='wm'>{_mw_txt}</div>", 1)
    except Exception:
        pass
    # === HTML-BRANDING-1 (fin) ===

    # === HTML-TABLA-ESPACIADO-1: Ajustes de "Todos los contactos" (solo CSS) ===
    try:
        _css_tc = """
/* Tabla de 'Todos los contactos' con más respiración */
#todos-contactos table.tbl{
  border-collapse:separate !important;
  border-spacing:18px 8px !important;
  table-layout:fixed;
  width:100%;
}
#todos-contactos table.tbl th,
#todos-contactos table.tbl td{
  padding:12px 20px !important;
}

/* # (angosta, derecha) */
#todos-contactos table.tbl th:nth-child(1),
#todos-contactos table.tbl td:nth-child(1){
  width:56px !important;
  text-align:right !important;
}

/* Contacto (más ancha, con elipsis si se desborda) */
#todos-contactos table.tbl th:nth-child(2),
#todos-contactos table.tbl td:nth-child(2){
  width:300px !important;
  overflow:hidden !important;
  text-overflow:ellipsis !important;
  white-space:nowrap !important;
}

/* Conteo y Minutos (alineadas a la derecha, anchas) */
#todos-contactos table.tbl th:nth-child(3),
#todos-contactos table.tbl td:nth-child(3),
#todos-contactos table.tbl th:nth-child(4),
#todos-contactos table.tbl td:nth-child(4){
  width:200px !important;
  text-align:right !important;
}

/* Tarjetas visuales por fila (sombra sutil) */
#todos-contactos table.tbl tbody tr{
  background:#fff;
  box-shadow:0 1px 0 #eee;
}
#todos-contactos table.tbl thead tr{
  box-shadow:none;
}
"""
        html = html.replace("</style>", _css_tc + "</style>", 1)
        # === HTML-RESPONSIVE-1: Tablas en móvil (última columna se parte / scroll si hace falta) ===
        _css_resp = """
        <style>
        @media (max-width: 640px) {
            section table {
            width: 100%;
            border-collapse: collapse;
            }
            /* Forzar quiebre de línea en la ÚLTIMA columna (p. ej., Azimut) */
            section table td:last-child,
            section table th:last-child {
            white-space: normal !important;
            word-break: break-word !important;
            overflow-wrap: anywhere !important;
            max-width: 160px;
            }
            /* Tipografía un poco más compacta en celdas */
            section table td,
            section table th {
            font-size: 14px;
            line-height: 1.25;
            }
        }
        @media (max-width: 480px) {
            /* Si igual no cabe, permitir desplazamiento horizontal suave */
            section table {
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            }
            section table td,
            section table th {
            min-width: 80px;
            }
        }
        </style>
        """
        html = html.replace("</style>", _css_resp + "</style>", 1)
        # === HTML-RESPONSIVE-2: Mejoras de usabilidad táctil en móvil ===
        _css_mobile_touch = """
        <style>
        html{ scroll-behavior: smooth; }
        @media (max-width: 768px) {
            /* Selector de día: más grande y de ancho completo */
            #dia-selector{ display:block; width:100%; font-size:16px; padding:12px 14px; border-radius:8px; }
            /* Botón Ver más: área táctil mínima 44px */
            .ver-mas-btn{ padding:10px 14px !important; min-height:44px; font-size:15px; border-radius:8px; }
            /* Botón fullscreen del mini-mapa: un poco más grande */
            .tz-fs-btn{ padding:10px 12px !important; font-size:18px; }
            /* Controles de zoom de Leaflet: más grandes para dedo */
            .leaflet-control-zoom a{ width:44px; height:44px; line-height:44px; font-size:22px; }
            .leaflet-control-zoom{ box-shadow:0 1px 4px rgba(0,0,0,.15); }
            /* Links del menú TOC: más área clicable y separación vertical */
            .toc a{ display:inline-block; padding:10px 12px; margin:4px 8px 6px 0; border-radius:999px; }
            /* Tablas: más aire y legibilidad */
            table.tbl th, table.tbl td{ padding:10px 12px; font-size:14px; line-height:1.35; }
        }
        </style>
        """
        html = html.replace("</style>", _css_mobile_touch + "</style>", 1)
        

    except Exception:
        pass
    # === HTML-TABLA-ESPACIADO-1 (fin) ===



    # HTML-INTERACCIONES-1: inyectar sección (si fue calculada)
    try:
        _html_interacciones = globals().get("HTML_SECCION_INTERACCIONES", "")
        if isinstance(_html_interacciones, str) and _html_interacciones:
            if "</main>" in html:
                html = html.replace("</main>", _html_interacciones + "</main>")
            elif "</body>" in html:
                html = html.replace("</body>", _html_interacciones + "</body>")
            else:
                html += _html_interacciones
    except Exception:
        pass

        # TODOS-CONTACTOS-HTML: inyectar sección si fue calculada
    try:
        _html_all = globals().get("HTML_SECCION_TODOS_CONTACTOS", "")
        if isinstance(_html_all, str) and _html_all:
            if "</main>" in html:
                html = html.replace("</main>", _html_all + "</main>")
            elif "</body>" in html:
                html = html.replace("</body>", _html_all + "</body>")
            else:
                html += _html_all
    except Exception:
        pass


    # === HTML-ANTENAS-SIMPLE-1: sección Top antenas (computada aquí) ===
    try:
        # Top N configurable (override -> config -> 3)
        try:
            if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('antenas') is not None:
                _topN = int(OVERRIDE_TOPS.get('antenas'))
            elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
                _topN = int(CONFIG.get("top_antenas", CONFIG.get("html", {}).get("top_antenas_n", 3)))
            else:
                _topN = 3
        except Exception:
            _topN = 3


        # Helper para elegir columnas disponibles
        def _pick_col(_df, candidatos):
            for c in candidatos:
                if c in _df.columns:
                    return c
            return None

        col_ant = _pick_col(df, ["antena", "nombre_antena", "cell_name"])
        col_lat = _pick_col(df, ["lat", "latitud", "latitude"])
        col_lon = _pick_col(df, ["long", "lon", "longitud", "lng", "longitude"])
        col_az  = _pick_col(df, ["azimut", "azimuth", "azi", "angulo"])

        # BBOX El Salvador (o desde CONFIG si existe)
        try:
            _bbox = CONFIG.get("geografia", {}).get("sv_bbox", None) if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else None
        except Exception:
            _bbox = None
        if not (isinstance(_bbox, dict) and all(k in _bbox for k in ("lat_min","lat_max","lon_min","lon_max"))):
            _bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

        def _valid_latlon(lt, lg):
            try:
                lt = float(lt); lg = float(lg)
                if np.isnan(lt) or np.isnan(lg):
                    return False
                if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                    return False
                return (_bbox["lat_min"] <= lt <= _bbox["lat_max"]) and (_bbox["lon_min"] <= lg <= _bbox["lon_max"])
            except Exception:
                return False

        sec_ant = ""
        if col_ant:
            dfv = df.copy()
            dfv[col_ant] = dfv[col_ant].astype(str).str.strip()
            # quitar antena '0' o vacías
            dfv = dfv[dfv[col_ant].notna() & (dfv[col_ant] != "") & (dfv[col_ant] != "0")]
            # validar coords si existen
            if (col_lat in dfv.columns) and (col_lon in dfv.columns):
                dfv = dfv[dfv.apply(lambda r: _valid_latlon(r[col_lat], r[col_lon]), axis=1)]

            if not dfv.empty:
                top = (dfv.groupby(col_ant)
                        .size()
                        .reset_index(name="activaciones")
                        .sort_values("activaciones", ascending=False))
                if int(_topN) > 0:
                    top = top.head(int(_topN))

                filas = []
                for _, r0 in top.iterrows():
                    ant = str(r0[col_ant])
                    sub = dfv[dfv[col_ant] == ant]

                    # lat/lon promedio
                    lt = float(sub[col_lat].astype(float).mean()) if (col_lat in sub.columns) else None
                    lg = float(sub[col_lon].astype(float).mean()) if (col_lon in sub.columns) else None

                    # azimut dominante + desglose corto
                    az_dom, desg = "—", "—"
                    if col_az and (col_az in sub.columns):
                        vc = (sub[col_az].astype(str).str.strip()
                                        .replace({"": np.nan, "nan": np.nan})
                                        .dropna()
                                        .value_counts())
                        if not vc.empty:
                            az_dom = str(vc.index[0])
                            parts = [f"Azimut {int(float(k))}: {int(v)} {'vez' if int(v)==1 else 'veces'}"
                                     for k, v in vc.head(3).items()]
                            desg = "<br>".join(parts) + (" …" if len(vc) > 3 else "")

                    # mapa
                    if (lt is not None) and (lg is not None):
                        url = f"https://www.google.com/maps?q={lt:.6f},{lg:.6f}"
                        ant_fmt = f'<a href="{url}" target="_blank" rel="noopener">{ant}</a>'
                        lt_fmt, lg_fmt = f"{lt:.6f}", f"{lg:.6f}"
                    else:
                        ant_fmt, lt_fmt, lg_fmt = ant, "—", "—"

                    filas.append((ant_fmt, int(r0["activaciones"]), lt_fmt, lg_fmt, az_dom, desg))

                # Render simple
                out = []
                out.append('<section id="resumen-antenas">')
                out.append('<h2>Antenas más activadas (Top {n})</h2>'.format(n=_topN))
                out.append('<p class="nota"><b>Nota:</b> En esta sección se muestra un top list de las antenas más activadas en el periodo analizado; seguidamente se muestra la ubicación de esas antenas segun sus coordenadas.</p>')
                out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
                out.append('<thead><tr>'
                        '<th>#</th>'
                        '<th>Antena</th>'
                        '<th>Latitud</th>'
                        '<th>Longitud</th>'
                        '<th>Activaciones</th>'
                        '<th>Azimut</th>'
                        '</tr></thead><tbody>')
                for idx, (ant_fmt, act, lt_fmt, lg_fmt, az_dom, desg) in enumerate(filas, start=1):
                    out.append('<tr>'
                            f'<td>{idx}</td>'
                            f'<td>{ant_fmt}</td>'
                            f'<td>{lt_fmt}</td>'
                            f'<td>{lg_fmt}</td>'
                            f'<td>{act}</td>'
                            f'<td>{desg}</td>'
                            '</tr>')
                out.append('</tbody></table></div>')

                out.append("""
    <style>
    #resumen-antenas .tabla-compacta { border-collapse: collapse; width:100%; font-size:1rem; }
    #resumen-antenas .tabla-compacta th, #resumen-antenas .tabla-compacta td { border:1px solid #ddd; padding:6px 8px; text-align:left; }
    #resumen-antenas .tabla-compacta th { background:#f2f2f2; }
    #resumen-antenas .tabla-scroll { overflow-x:auto; }
    </style>
    """)
                out.append('</section>')
                sec_ant = "".join(out)

        if sec_ant:
            anchor = "<h2>Indicadores</h2>"
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_ant + html[j+10:]
                else:
                    html += sec_ant
            else:
                html += sec_ant


    except Exception:
        pass
    # === FIN HTML-ANTENAS-SIMPLE-1 ===

    # REORDENAR-SECCIONES-1: mover “Top antenas” al final y renombrar
    try:
        _hdr = "<h2>Top antenas</h2>"
        pos = html.find(_hdr)
        if pos != -1:
            ini = html.rfind("<section", 0, pos)
            fin = html.find("</section>", pos)
            if ini != -1 and fin != -1:
                bloque = html[ini:fin+10]
                # renombrar encabezado
                bloque = bloque.replace(
                    "<h2>Top antenas</h2>",
                    "<h2>Todas las antenas que ha activado en el período analizado</h2>"
                )
                # agregar nota explicativa después del h2
                bloque = bloque.replace(
                    "<h2>Todas las antenas que ha activado en el período analizado</h2>",
                    '<h2>Todas las antenas que ha activado en el período analizado</h2><div style="font-size:13px; color:#444; margin-bottom:8px;">Esta lista muestra todas las antenas que el usuario del número analizado ha activado durante el período analizado. Cada registro corresponde a una antena donde se ha detectado actividad, sin importar la frecuencia o duración de la conexión.</div><p class="nota"><b>Nota:</b> Si desea verificar la ubicación de una antena, puede hacer clic en el nombre para abrir su posición en Google Maps.</p>'
                )
                # quitar del lugar original
                html = html[:ini] + html[fin+10:]
                # insertar al final (antes de </body>)
                if "</body>" in html:
                    html = html.replace("</body>", bloque + "\n</body>")
                else:
                    html += bloque
    except Exception:
        pass

    # --- REORDENAR-SECCIONES-1: deja "Top antenas" después de "Indicadores"
    #     y manda "Todas las antenas..." hasta el final, ANTES de escribir el archivo.
    try:
        # === HTML-ANTENAS-RANGOS-1: Antenas por rango horario (debajo del Top antenas) ===
        # Además, prepararemos la nueva sección de "Mapa de calor de actividad" (heatmap)
        # para insertarla entre "Antenas más activadas" y "Contactos con más comunicación".
        sec_ant_rangos = ""
        sec_heatmap = ""
        try:
            # --- 1) Detección robusta de columnas ---
            cols_low = {c.lower(): c for c in df.columns}
            def pick(*names):
                for n in names:
                    c = cols_low.get(n)
                    if c: return c
                # búsqueda suavecita por contiene
                for c in df.columns:
                    lc = c.lower()
                    if any(n in lc for n in names):
                        return c
                return None

            col_ant = pick("antena", "antenanombre", "antena_nombre")
            col_lat = pick("lat", "latitud")
            col_lon = pick("lon", "long", "longitud")
            col_hora = pick("hora", "time")
            col_fecha_hora = pick("fecha y hora", "fechahora", "datetime", "timestamp")

            # Si no hay columna de antena, no armamos nada
            if col_ant:
                # --- 2) Obtener la hora (0..23) de forma robusta ---
                def _to_hour_series():
                    if col_hora is not None:
                        import warnings
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", message="Could not infer format*", category=UserWarning)
                            s = pd.to_datetime(df[col_hora], errors="coerce").dt.hour

                        if s.isna().mean() > 0.5:
                            def _hh(x):
                                try:
                                    x = str(x)
                                    hh = int(x.split(":")[0])
                                    return hh
                                except:
                                    return np.nan
                            s = df[col_hora].map(_hh)
                        return s
                    if col_fecha_hora is not None:
                        return pd.to_datetime(df[col_fecha_hora], errors="coerce").dt.hour
                    return None


                hours = _to_hour_series()

                                # Mañana 06–11:59, Tarde 12–17:59, Noche 18–23:59, Madrugada 00–05:59
                def _lab(h):
                    if h is None or np.isnan(h): return None
                    h = int(h)
                    if 6 <= h <= 11:        return "Mañana (06:00–11:59)"
                    if 12 <= h <= 17:       return "Tarde (12:00–17:59)"
                    if 18 <= h <= 23:       return "Noche (18:00–23:59)"
                    return "Madrugada (00:00–05:59)"

                labels_orden = [
                    "Madrugada (00:00–05:59)",
                    "Mañana (06:00–11:59)",
                    "Tarde (12:00–17:59)",
                    "Noche (18:00–23:59)",
                ]


                # --- 4) Utilidades de pretty/geo ---
                def _fmt(x):
                    try:
                        x = float(x)
                        return f"{x:.6f}"
                    except:
                        return "—"

                def _first_valid_geo(sub_ant):
                    if col_lat and col_lon:
                        tmp = sub_ant[[col_lat, col_lon]].dropna()
                        if not tmp.empty:
                            t2 = tmp[(tmp[col_lat]!=0) | (tmp[col_lon]!=0)]
                            if not t2.empty:
                                r = t2.iloc[0]
                                return float(r[col_lat]), float(r[col_lon])
                    return (None, None)

                # --- 5) Armar HTML ---
                out = []
                out.append('<section id="antenas-rangos">')
                out.append('<h2>Antenas por rango horario</h2>')
                out.append('<p class="nota"><b>Nota:</b> Si desea verificar la ubicación de una antena, puede hacer clic en el nombre para abrir su posición en Google Maps.</p>')
                out.append('<style>#antenas-rangos h3.sub{background:#f7f7f7;border:1px solid #e6e6e6;border-radius:6px;padding:.5rem .75rem;margin:1rem 0 .5rem}#antenas-rangos .mono{font-family:ui-monospace,Menlo,Consolas,monospace}#antenas-rangos .nowrap{white-space:nowrap}</style>')
                if hours is not None:
                    rangos = hours.map(_lab)
                    for lab in labels_orden:
                        mask = rangos == lab
                        total = int(mask.sum())
                        if total == 0:
                            continue
                        sub = df[mask]

                        # --- Filtrar antenas y coordenadas válidas antes del Top N ---
                        tmp = sub.copy()
                        # validar lat/lon si existen
                        tmp["_lat"] = pd.to_numeric(tmp.get(col_lat, pd.Series(dtype=float)), errors="coerce")
                        tmp["_lon"] = pd.to_numeric(tmp.get(col_lon, pd.Series(dtype=float)), errors="coerce")
                        valid_geo = (
                            tmp["_lat"].between(-90, 90) &
                            tmp["_lon"].between(-180, 180) &
                            ~((tmp["_lat"].abs() < 1e-9) & (tmp["_lon"].abs() < 1e-9))
                        )
                        # limpiar nombre de antena
                        ant_str = tmp[col_ant].astype(str).str.strip()
                        valid_ant = (ant_str != "") & (ant_str != "0") & (~ant_str.str.match(r"(?i)(sin\s*inf\.?|s/i)$"))

                        # dataframe ya depurado (sin .copy() innecesario - solo lectura después)
                        sub_valid = tmp[valid_geo & valid_ant]

                        # --- Top N (respeta override/config) ---
                        try:
                            if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('antenas'):
                                _topN = int(OVERRIDE_TOPS.get('antenas'))
                            elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
                                _topN = int(CONFIG.get("top_antenas", CONFIG.get("html", {}).get("top_antenas_n", 3)))
                            else:
                                _topN = 3
                        except Exception:
                            _topN = 3

                        conteo = sub_valid[col_ant].value_counts(dropna=False)
                        top_series = conteo
                        if int(_topN) > 0:
                            top_series = conteo.head(int(_topN))


                        out.append(f'<h3 class="sub">{lab} <span class="sub">({total} activaciones)</span></h3>')
                        out.append('<table class="tbl"><thead><tr><th>#</th><th>Antena</th><th>Latitud</th><th>Longitud</th><th>Conteo</th><th>Azimuts frecuentes</th></tr></thead><tbody>')

                        for i, (ant, cnt) in enumerate(top_series.items(), start=1):
                            sub_ant = sub_valid[sub_valid[col_ant] == ant]

                            # Geo (primera coord válida)
                            lat, lon = _first_valid_geo(sub_ant)
                            lat_s = _fmt(lat) if lat is not None else "—"
                            lon_s = _fmt(lon) if lon is not None else "—"

                            # Link a Maps si hay geo
                            if lat is not None and lon is not None:
                                ant_html = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{ant}</a>'
                            else:
                                ant_html = f"{ant}"

                            # Azimuts frecuentes (Top 3)
                            az_s = "—"
                            if "azimut" in sub_ant.columns:
                                try:
                                    azv = pd.to_numeric(sub_ant["azimut"], errors="coerce").round().dropna().astype(int)
                                    vc = azv.value_counts().head(3)
                                    if not vc.empty:
                                        parts = [f"Azimut {int(k)}: {int(v)} {'vez' if int(v)==1 else 'veces'}" for k, v in vc.items()]
                                        az_s = "<br>".join(parts)
                                except Exception:
                                    pass

                            out.append(
                                f"<tr><td class='mono'>{i}</td>"
                                f"<td>{ant_html}</td>"
                                f"<td class='mono nowrap'>{lat_s}</td>"
                                f"<td class='mono nowrap'>{lon_s}</td>"
                                f"<td class='mono'>{int(cnt):,}</td>"
                                f"<td>{az_s}</td></tr>"
    )

                        out.append("</tbody></table>")

                out.append("</section>")
                sec_ant_rangos = "\n".join(out)
                log(f"[DEBUG] Antenas por horario: {len(sec_ant_rangos)} chars")
        except Exception:
            sec_ant_rangos = ""
        # === FIN HTML-ANTENAS-RANGOS-1 ===

        # === HTML-HISTORIAL-CAMBIOS-1: Generar bloque de Historial de cambios de antena ===
        sec_historial = ""
        try:
            saltos = generar_historial_cambios_antena(df, max_saltos=100)
            if saltos:
                out = []
                out.append('<section id="historial-cambios">')
                out.append('<h2>Historial de cambios de antena</h2>')
                out.append('<p class="nota"><b>Nota:</b> Esta tabla muestra los cambios de antena detectados en orden cronológico. Cada fila representa un momento en que el dispositivo cambió de una antena a otra.</p>')
                out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
                out.append('<thead><tr>'
                          '<th>#</th>'
                          '<th>Fecha y Hora</th>'
                          '<th>Antena Origen</th>'
                          '<th>Antena Destino</th>'
                          '<th>Distancia (km)</th>'
                          '</tr></thead><tbody>')
                
                for idx, salto in enumerate(saltos, start=1):
                    ts_str = salto['timestamp'].strftime('%d/%m/%Y %H:%M:%S') if salto['timestamp'] else '—'
                    origen = salto['origen']
                    destino = salto['destino']
                    
                    # Formato distancia
                    if salto['distancia_km'] is not None:
                        dist_str = f"{salto['distancia_km']:.2f}"
                    else:
                        dist_str = '—'
                    
                    out.append('<tr>'
                              f'<td>{idx}</td>'
                              f'<td>{ts_str}</td>'
                              f'<td>{origen}</td>'
                              f'<td>{destino}</td>'
                              f'<td>{dist_str}</td>'
                              '</tr>')
                
                out.append('</tbody></table></div>')
                out.append("""
<style>
#historial-cambios .tabla-compacta { border-collapse: collapse; width:100%; font-size:0.95rem; }
#historial-cambios .tabla-compacta th, #historial-cambios .tabla-compacta td { border:1px solid #ddd; padding:6px 8px; text-align:left; }
#historial-cambios .tabla-compacta th { background:#f2f2f2; font-weight:600; }
#historial-cambios .tabla-scroll { overflow-x:auto; }
</style>
""")
                out.append('</section>')
                sec_historial = "\n".join(out)
                log(f"[DEBUG] Historial de cambios: {len(saltos)} saltos detectados")
        except Exception as e:
            log(f"[WARNING] Error generando historial de cambios: {e}")
            sec_historial = ""
        # === FIN HTML-HISTORIAL-CAMBIOS-1 ===

        # === HTML-HEATMAP-1: Generar bloque de Mapa de Calor de actividad ===
        # Contrato de datos: puntos [lat, lon, weight] donde weight se normaliza (0..1) por
        # la frecuencia de activaciones (conteo por coordenada redondeada). Este bloque es
        # autónomo y se insertará entre el resumen de antenas y el bloque de contactos.
        # MEJORA: Incluye marcadores (pines) de las antenas Top N para hacerlo más comprensible.
        try:
            if col_lat and col_lon and (col_lat in df.columns) and (col_lon in df.columns):
                import json as _json
                _tmp = df.copy()
                _tmp["_lat"] = pd.to_numeric(_tmp.get(col_lat, pd.Series(dtype=float)), errors="coerce")
                _tmp["_lon"] = pd.to_numeric(_tmp.get(col_lon, pd.Series(dtype=float)), errors="coerce")
                _valid = (
                    _tmp["_lat"].between(-90, 90) &
                    _tmp["_lon"].between(-180, 180) &
                    ~((_tmp["_lat"].abs() < 1e-9) & (_tmp["_lon"].abs() < 1e-9))
                )
                _geo = _tmp.loc[_valid, ["_lat", "_lon"]]
                # Agrupar por coord redondeada para evitar duplicados excesivos
                if not _geo.empty:
                    _geo["_latr"] = _geo["_lat"].round(5)
                    _geo["_lonr"] = _geo["_lon"].round(5)
                    _grp = _geo.groupby(["_latr", "_lonr"]).size().reset_index(name="cnt").sort_values("cnt", ascending=False)
                    # Cap en cantidad de puntos para tamaño de HTML (ej. top 1500)
                    _grp = _grp.head(1500)
                    _max = float(_grp["cnt"].max()) if not _grp.empty else 0.0
                    heat_points = []
                    if _max > 0:
                        for _, rr in _grp.iterrows():
                            w = float(rr["cnt"]) / _max
                            heat_points.append([float(rr["_latr"]), float(rr["_lonr"]), round(w, 4)])
                    
                    # NUEVO: Preparar marcadores de antenas Top N (mismo criterio que sec_ant)
                    markers_data = []
                    if col_ant and (col_ant in df.columns):
                        try:
                            # Obtener top_N del config
                            _topN_markers = 5  # default
                            if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('antenas'):
                                _topN_markers = int(OVERRIDE_TOPS.get('antenas'))
                            elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
                                _topN_markers = int(CONFIG.get("top_antenas", CONFIG.get("html", {}).get("top_antenas_n", 5)))
                            
                            _dfv = df.copy()
                            _dfv[col_ant] = _dfv[col_ant].astype(str).str.strip()
                            _dfv = _dfv[_dfv[col_ant].notna() & (_dfv[col_ant] != "") & (_dfv[col_ant] != "0")]
                            if (col_lat in _dfv.columns) and (col_lon in _dfv.columns):
                                _dfv = _dfv[_dfv.apply(lambda r: _valid_latlon(r[col_lat], r[col_lon]), axis=1)]
                            
                            if not _dfv.empty:
                                _top = (_dfv.groupby(col_ant)
                                        .size()
                                        .reset_index(name="activaciones")
                                        .sort_values("activaciones", ascending=False))
                                if int(_topN_markers) > 0:
                                    _top = _top.head(int(_topN_markers))
                                
                                for _, _r in _top.iterrows():
                                    _ant = str(_r[col_ant])
                                    _sub = _dfv[_dfv[col_ant] == _ant]
                                    _lt = float(_sub[col_lat].astype(float).mean()) if (col_lat in _sub.columns) else None
                                    _lg = float(_sub[col_lon].astype(float).mean()) if (col_lon in _sub.columns) else None
                                    _act = int(_r["activaciones"])
                                    
                                    # Extraer azimuts únicos si existen
                                    _azimuts = []
                                    if col_az and (col_az in _sub.columns):
                                        try:
                                            _az_vals = (_sub[col_az].astype(str).str.strip()
                                                       .replace({"": np.nan, "nan": np.nan})
                                                       .dropna()
                                                       .apply(lambda x: int(float(x))))
                                            _az_counts = _az_vals.value_counts().sort_values(ascending=False)
                                            _azimuts = [{"deg": int(k), "n": int(v)} for k, v in _az_counts.items()]
                                        except Exception:
                                            pass
                                    
                                    if (_lt is not None) and (_lg is not None):
                                        markers_data.append({
                                            "lat": round(_lt, 6),
                                            "lon": round(_lg, 6),
                                            "name": _ant,
                                            "count": _act,
                                            "azimuts": _azimuts
                                        })
                        except Exception:
                            pass
                    
                    # Si no hay puntos suficientes, omitimos la sección
                    if heat_points:
                        _heat_js = _json.dumps(heat_points, ensure_ascii=False)
                        _markers_js = _json.dumps(markers_data, ensure_ascii=False)
                        # Sección integrada al bloque de "Antenas más activadas":
                        # sin H2 ni nota, para que el mapa se perciba como parte del resumen de antenas.
                        sec_heatmap = f"""
<section id=\"heatmap-actividad\">
    <!-- Nota informativa: este mapa forma parte de "Antenas más activadas" -->
    <p class=\"nota\">Nota: Recomendación: para mejorar la visualización del mapa desde un celular, hágalo con la pantalla horizontal; al hacer clic en un punto de la antena se desplegará la información y se habilitará el azimut.</p>
    <div id=\"wrap-heatmap\" class=\"tz-map-wrap\" style=\"position:relative; margin:0 40px;\">
            <button class=\"tz-fs-btn\" title=\"Pantalla completa\" data-map-id=\"heatmap\" style=\"position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;\">⛶</button>\n        <div id=\"heatmap\" style=\"height:560px; border:1px solid #ddd; border-radius:8px; overflow:hidden;\"></div>
    </div>

  <script>
    (function() {{
      const heatData = { _heat_js };
      const markers = { _markers_js };
      if (!Array.isArray(heatData) || heatData.length === 0) return;
      
      const map = L.map('heatmap', {{ scrollWheelZoom: false }});
      const tiles = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap'
      }}).addTo(map);
      
                    // === Utilidades para dibujar la orientación (azimut principal) ===
                    const AZ_COLOR = '#e74c3c';
                    const AZ_LINE_LEN_M = 1500;      // longitud de la flecha
                    const AZ_LINE_WEIGHT = 5;         // grosor de la línea del azimut
                    const AZ_CONE_HALF_DEG = 30;      // medio ángulo del cono (±30°)
                    const AZ_CONE_STEPS = 24;         // discretización del arco
            // Convertir grados a radianes
            const toRad = d => d * Math.PI / 180;
            // Convertir radianes a grados
            const toDeg = r => r * 180 / Math.PI;
            // Calcula un punto destino a partir de lat, lon, rumbo (grados) y distancia (m)
            function destinationPoint(lat, lon, bearingDeg, distanceM) {{
                const R = 6371000; // radio medio de la Tierra, en metros
                const δ = distanceM / R;
                const θ = toRad(bearingDeg);
                const φ1 = toRad(lat);
                const λ1 = toRad(lon);
                const sinφ1 = Math.sin(φ1), cosφ1 = Math.cos(φ1);
                const sinδ = Math.sin(δ), cosδ = Math.cos(δ);
                const sinφ2 = sinφ1 * cosδ + cosφ1 * sinδ * Math.cos(θ);
                const φ2 = Math.asin(sinφ2);
                const y = Math.sin(θ) * sinδ * cosφ1;
                const x = cosδ - sinφ1 * sinφ2;
                const λ2 = λ1 + Math.atan2(y, x);
                return [toDeg(φ2), ((toDeg(λ2) + 540) % 360) - 180]; // normaliza longitud a [-180,180]
            }}
            // Selecciona el azimut principal: mayor 'n'; si empata, el menor grado
            function principalAzimut(azimuts) {{
                if (!Array.isArray(azimuts) || azimuts.length === 0) return null;
                let best = null;
                azimuts.forEach(a => {{
                    const n = (a && typeof a.n === 'number') ? a.n : 0;
                    const d = (a && typeof a.deg === 'number') ? a.deg : null;
                    if (d === null) return;
                    if (!best || n > best.n || (n === best.n && d < best.deg)) best = {{ deg: d, n }};
                }});
                return best ? best.deg : null;
            }}
                    // Construye un polígono en forma de cono desde el punto de origen
                    function buildCone(lat, lon, bearingDeg, halfDeg, radiusM, steps) {{
                        const pts = [];
                        pts.push([lat, lon]);
                        const start = bearingDeg - halfDeg;
                        const end = bearingDeg + halfDeg;
                        const cnt = Math.max(3, steps|0);
                        for (let i = 0; i <= cnt; i++) {{
                            const b = start + (i * (end - start) / cnt);
                            pts.push(destinationPoint(lat, lon, b, radiusM));
                        }}
                        pts.push([lat, lon]);
                        return pts;
                    }}
                    let currentAzLine = null; // polyline activo del último popup
                    let currentAzCone = null; // polígono del cono activo

      // Agregar capa de calor
      const latlngs = heatData.map(p => [p[0], p[1]]);
      const bounds = L.latLngBounds(latlngs);
      try {{ map.fitBounds(bounds.pad(0.15)); }} catch(e) {{ map.setView(latlngs[0], 12); }}
      L.heatLayer(heatData, {{ radius: 22, blur: 18, maxZoom: 16, minOpacity: 0.3 }}).addTo(map);
      
      // Agregar marcadores de antenas Top N
      if (Array.isArray(markers) && markers.length > 0) {{
        markers.forEach((m, idx) => {{
          const marker = L.marker([m.lat, m.lon], {{
            title: m.name
          }}).addTo(map);
          
          // Construir popup con información completa
          let popupContent = `<div style="font-family:sans-serif; font-size:13px;">`;
          popupContent += `<strong style="font-size:14px;">${{m.name}}</strong><br>`;
          popupContent += `<span style="color:#666;">Activaciones: ${{m.count.toLocaleString()}}</span><br>`;
                    popupContent += `<span style="color:#666;">Coordenadas: ${{m.lat.toFixed(6)}}, ${{m.lon.toFixed(6)}}</span>`;
          
          // Agregar azimuts si existen
                                if (m.azimuts && m.azimuts.length > 0) {{
                                    m.azimuts.forEach(a => {{
                                        popupContent += `<br><span style=\"color:#666;\">Azimut ${{a.deg}}°</span>`;
                                    }});
                                }}
          
          popupContent += `</div>`;
          marker.bindPopup(popupContent);

                                // Dibuja la flecha y el cono del azimut principal al abrir el popup; limpia al cerrar
                    marker.on('popupopen', () => {{
                                    if (currentAzLine) {{ try {{ map.removeLayer(currentAzLine); }} catch(e) {{}} currentAzLine = null; }}
                                    if (currentAzCone) {{ try {{ map.removeLayer(currentAzCone); }} catch(e) {{}} currentAzCone = null; }}
                        const bearing = principalAzimut(m.azimuts);
                        if (typeof bearing === 'number' && isFinite(bearing)) {{
                            const p1 = [m.lat, m.lon];
                                        const p2 = destinationPoint(m.lat, m.lon, bearing, AZ_LINE_LEN_M);
                                        currentAzLine = L.polyline([p1, p2], {{ color: AZ_COLOR, weight: AZ_LINE_WEIGHT, opacity: 1.0 }}).addTo(map);
                                        const conePts = buildCone(m.lat, m.lon, bearing, AZ_CONE_HALF_DEG, AZ_LINE_LEN_M, AZ_CONE_STEPS);
                                        currentAzCone = L.polygon(conePts, {{ color: AZ_COLOR, weight: 1, opacity: 0.9, fillColor: AZ_COLOR, fillOpacity: 0.18 }}).addTo(map);
                        }}
                    }});
                    marker.on('popupclose', () => {{
                                    if (currentAzLine) {{ try {{ map.removeLayer(currentAzLine); }} catch(e) {{}} currentAzLine = null; }}
                                    if (currentAzCone) {{ try {{ map.removeLayer(currentAzCone); }} catch(e) {{}} currentAzCone = null; }}
                    }});
        }});
      }}
      // Registrar mapa global para fullscreen
      try {{
        window.__tzDailyMaps = window.__tzDailyMaps || {{}};
        window.__tzDailyMaps['heatmap'] = {{
          map: map,
          bounds: bounds,
          markersCount: (Array.isArray(markers) && markers.length>0) ? markers.length : latlngs.length,
          center: bounds.getCenter(),
          wrapperId: 'wrap-heatmap'
        }};
      }} catch(e) {{}}
    }})();
  </script>
</section>
"""
                        log(f"[DEBUG] Heatmap: {len(sec_heatmap)} chars, puntos={len(heat_points)}")
        except Exception:
            sec_heatmap = ""
        # === FIN HTML-HEATMAP-1 ===

        # 1) Mover "Top antenas" inmediatamente después de "Indicadores" (si aún no lo está)
        idx_ind = html.find("<h2>Indicadores</h2>")
        idx_top = html.find("<h2>Top antenas</h2>")
        if idx_ind != -1 and idx_top != -1 and idx_top < idx_ind:
            fin_top = html.find("</section>", idx_top)
            bloque_top = html[idx_top: fin_top + 10]  # incluye </section>
            # quita el bloque de donde estaba
            html = html[:idx_top] + html[fin_top + 10:]
            # inserta justo después de la sección "Indicadores"
            fin_ind = html.find("</section>", idx_ind)
            html = html[:fin_ind + 10] + "\n  " + bloque_top + "\n  " + html[fin_ind + 10:]

                # REORDENAR-SECCIONES-2: mover "<h2>Contactos con más comunicación" debajo de "Antenas más activadas"
        try:
            # 2A) Insertar primero el HEATMAP (si existe) y luego mover
            #     el bloque "Contactos con más comunicación" inmediatamente
            #     después del heatmap. Si no hay heatmap, va debajo del resumen.
            hdr_resumen = "<h2>Antenas más activadas"
            idx_res = html.find(hdr_resumen)
            if idx_res != -1:
                # localizar bloque de "<h2>Contactos con más comunicación"
                # primero busca con id, si no, por el H2 plano
                idx_int = html.find('id="interacciones"')
                if idx_int == -1:
                    idx_int = html.find("<h2>Contactos con más comunicación")
                if idx_int != -1:
                    ini_int = html.rfind("<section", 0, idx_int)
                    fin_int = html.find("</section>", idx_int)
                    if ini_int != -1 and fin_int != -1:
                        bloque_int = html[ini_int:fin_int+10]
                        # quitar del lugar original
                        html = html[:ini_int] + html[fin_int+10:]
                        # 2A.1) Insertar HEATMAP justo después del resumen (si lo tenemos)
                        fin_res = html.find("</section>", idx_res)
                        if fin_res != -1 and sec_heatmap:
                            html = html[:fin_res+10] + "\n" + sec_heatmap + html[fin_res+10:]
                            # recalcular punto de inserción para contactos: después del heatmap
                            idx_hm = html.find('id="heatmap-actividad"', fin_res)
                            if idx_hm != -1:
                                fin_hm = html.find("</section>", idx_hm)
                                if fin_hm != -1:
                                    html = html[:fin_hm+10] + "\n" + bloque_int + html[fin_hm+10:]
                                else:
                                    # fallback: si no encontramos cierre, insertar tras resumen
                                    html = html[:fin_res+10] + "\n" + bloque_int + html[fin_res+10:]
                            else:
                                # fallback por si no quedó el id (no debería ocurrir)
                                html = html[:fin_res+10] + "\n" + bloque_int + html[fin_res+10:]
                        else:
                            # si no hay heatmap, insertar interacciones debajo del resumen
                            if fin_res != -1:
                                html = html[:fin_res+10] + "\n" + bloque_int + html[fin_res+10:]

            # 2B) Insertar "Antenas por rango horario" debajo de "Interacciones" (si existe); si no, debajo del resumen
            if sec_ant_rangos:
                # intentar ponerlo después del bloque de interacciones recién reubicado
                i_int = html.find('id="interacciones"')
                if i_int == -1:
                    i_int = html.find("<h2>Contactos con más comunicación")
                if i_int != -1:
                    j_int = html.find("</section>", i_int)
                    if j_int != -1:
                        html = html[:j_int+10] + "\n" + sec_ant_rangos + html[j_int+10:]
                else:
                    # fallback: debajo de "Antenas más activadas"
                    i = html.find(hdr_resumen)
                    if i != -1:
                        j = html.find("</section>", i)
                        if j != -1:
                            html = html[:j+10] + "\n" + sec_ant_rangos + html[j_int+10:]
                    else:
                        # si no hay ninguna de las dos, mándalo al final
                        if "</body>" in html:
                            html = html.replace("</body>", sec_ant_rangos + "\n</body>")
                        else:
                            html += sec_ant_rangos

            # 2C) Insertar "Historial de cambios de antena" debajo de "Antenas por rango horario" (si existe)
            if sec_historial:
                # intentar ponerlo después del bloque de antenas por rango
                i_rangos = html.find('id="antenas-rangos"')
                if i_rangos != -1:
                    j_rangos = html.find("</section>", i_rangos)
                    if j_rangos != -1:
                        html = html[:j_rangos+10] + "\n" + sec_historial + html[j_rangos+10:]
                else:
                    # fallback: después de interacciones
                    i_int = html.find('id="interacciones"')
                    if i_int == -1:
                        i_int = html.find("<h2>Contactos con más comunicación")
                    if i_int != -1:
                        j_int = html.find("</section>", i_int)
                        if j_int != -1:
                            html = html[:j_int+10] + "\n" + sec_historial + html[j_int+10:]
                    else:
                        # último fallback: al final
                        if "</body>" in html:
                            html = html.replace("</body>", sec_historial + "\n</body>")
                        else:
                            html += sec_historial
        except Exception:
            pass

        # REORDENAR-SECCIONES-3: enviar "Todos los contactos" al final del documento
        try:
            idx_tc = html.find('id="todos-contactos"')
            if idx_tc != -1:
                ini_tc = html.rfind("<section", 0, idx_tc)
                fin_tc = html.find("</section>", idx_tc)
                if ini_tc != -1 and fin_tc != -1:
                    bloque_tc = html[ini_tc:fin_tc+10]
                    # quitar del lugar original
                    html = html[:ini_tc] + html[fin_tc+10:]
                    # insertarlo ANTES de </body> (última sección)
                    if "</body>" in html:
                        html = html.replace("</body>", bloque_tc + "\n</body>", 1)
                        # === JS: Auto-agregar correlativo (#) a tablas que NO lo tengan ===
                        _js_autonum = """
                        <script>
                        (function() {
                        try {
                            var tables = document.querySelectorAll('section table');
                            tables.forEach(function(t) {
                            // ¿Ya está marcado con índice? (o ya tiene '#' primero)
                            var thFirst = t.querySelector('thead tr th:first-child') || t.querySelector('tr:first-child th:first-child');
                            var hasHash = thFirst && thFirst.textContent && thFirst.textContent.trim() === '#';
                            if (t.classList.contains('has-index') || hasHash) {
                                // ya tienen índice (p.ej., Top antenas), solo asegurar clase para el CSS
                                if (!t.classList.contains('has-index')) t.classList.add('has-index');
                                return;
                            }

                            // 1) Insertar TH '#' al inicio del encabezado (crea THEAD si no hay)
                            var thead = t.querySelector('thead');
                            if (!thead) {
                                thead = document.createElement('thead');
                                var firstRow = t.querySelector('tr');
                                if (firstRow) {
                                var trHead = document.createElement('tr');
                                // Crear celdas de encabezado según número de columnas
                                var thAuto = document.createElement('th');
                                thAuto.textContent = '#';
                                trHead.appendChild(thAuto);
                                // Duplicar estructura de la primera fila como encabezado (vacío)
                                var cells = firstRow.children;
                                for (var i = 0; i < cells.length; i++) {
                                    var th = document.createElement('th');
                                    // si la primera fila ya es header, se respetará después
                                    trHead.appendChild(th);
                                }
                                thead.appendChild(trHead);
                                t.insertBefore(thead, t.firstChild);
                                }
                            } else {
                                // Hay thead: insertamos '#' como primera celda de la primera fila de encabezado
                                var tr0 = thead.querySelector('tr');
                                if (tr0) {
                                var thHash = document.createElement('th');
                                thHash.textContent = '#';
                                tr0.insertBefore(thHash, tr0.firstChild);
                                }
                            }

                            // 2) Numerar cuerpo: insertar TD (1..n) como primera celda en cada fila del tbody
                            var rows = t.querySelectorAll('tbody tr');
                            if (rows.length === 0) { rows = t.querySelectorAll('tr'); } // fallback si no hay tbody
                            var n = 1;
                            rows.forEach(function(r) {
                                var td = document.createElement('td');
                                td.textContent = String(n++);
                                // estilos mínimos para que no rompa
                                td.style.textAlign = 'center';
                                r.insertBefore(td, r.firstChild);
                            });

                            // 3) Marcar la tabla para que reciba el CSS de columna angosta
                            t.classList.add('has-index');
                            });
                        } catch(e) { /* silencioso */ }
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_autonum + "</body>", 1)
                        # === JS: ajustar offset según altura del header y hacer scroll con margen ===
                        _js_anchor = """
                        <script>
                        (function(){
                        try{
                            // 1) Medir header y setear --anchor-offset (con pequeño colchón)
                            var hdr = document.querySelector('header');
                            var offset = 96; // default
                            if (hdr){
                            var rect = hdr.getBoundingClientRect();
                            offset = Math.round(rect.height + 12); // colchón extra
                            }
                            document.documentElement.style.setProperty('--anchor-offset', offset + 'px');

                            // 2) Interceptar clics del TOC para asegurar scroll con offset (cross-browser)
                            var links = document.querySelectorAll('.toc a[href^="#"]');
                            links.forEach(function(a){
                            a.addEventListener('click', function(e){
                                e.preventDefault();
                                var id = this.getAttribute('href').slice(1);
                                var el = document.getElementById(id);
                                if (!el) return;

                                // Calcular posición considerando el offset
                                var y = el.getBoundingClientRect().top + window.pageYOffset - offset;

                                // Scroll suave; si no soporta, cae en instantáneo
                                window.scrollTo({ top: y, behavior: 'smooth' });

                                // Actualizar hash sin saltos “raros”
                                history.replaceState(null, '', '#' + id);
                            });
                            });

                            // 3) Si el usuario llega con hash en la URL, re-posicionar con offset
                            if (location.hash && document.getElementById(location.hash.slice(1))){
                            var target = document.getElementById(location.hash.slice(1));
                            var y = target.getBoundingClientRect().top + window.pageYOffset - offset;
                            window.scrollTo(0, y);
                            }
                        }catch(e){}
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_anchor + "</body>", 1)

                        # === JS: detectar pastillas claras y aplicar .need-contrast ===
                        _js_contrast = """
                        <script>
                        (function(){
                        try{
                            // Seleccionamos elementos "chip/pastilla" más comunes en el header/subtítulos
                            var sels = [
                            'header .badge','header .chip','header .pill','header .tag',
                            'header span','header a.badge','header a.chip','header a.pill','header a.tag'
                            ];
                            var nodes = document.querySelectorAll(sels.join(','));
                            var THRESH = 0.85; // luminancia: >0.85 lo consideramos "claro"

                            function parseRGB(s){
                            // soporta "rgb(r,g,b)" o "rgba(r,g,b,a)"
                            var m = s.match(/rgba?\\((\\d+),(\\d+),(\\d+)/i);
                            if(!m) return null;
                            return {r:+m[1], g:+m[2], b:+m[3]};
                            }
                            function relLum(c){
                            // WCAG relative luminance
                            function n(x){ x/=255; return (x<=0.03928)? x/12.92 : Math.pow((x+0.055)/1.055,2.4); }
                            var R=n(c.r), G=n(c.g), B=n(c.b);
                            return 0.2126*R + 0.7152*G + 0.0722*B;
                            }

                            nodes.forEach(function(el){
                            var cs = getComputedStyle(el);
                            // ignorar elementos sin color de fondo
                            var bg = cs.backgroundColor;
                            if(!bg || bg === 'transparent') return;
                            var rgb = parseRGB(bg);
                            if(!rgb) return;
                            var L = relLum(rgb);
                            if(L > THRESH){
                                el.classList.add('need-contrast'); // activa borde y texto oscuro
                            }
                            });
                        }catch(e){}
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_contrast + "</body>", 1)

                        # === CSS: columna de correlativo (#) SOLO en tablas con .has-index — AJUSTE FINO (28px móvil) ===
                        _css_idx = """
                        <style>
                        /* Desktop / tablet: compacto (44px) */
                        .has-index th:first-child,
                        .has-index td:first-child {
                            text-align: center !important;
                            width: 44px;
                            min-width: 44px;
                            max-width: 44px;
                            padding-left: 4px;
                            padding-right: 4px;
                        }
                        /* Móvil vertical: ultra compacto (28px) */
                        @media (max-width: 640px) {
                            .has-index th:first-child,
                            .has-index td:first-child {
                            width: 28px;
                            min-width: 28px;
                            max-width: 28px;
                            font-size: 12px;
                            padding-left: 2px;
                            padding-right: 2px;
                            }
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_idx + "</style>", 1)
                        # === CSS OVERRIDE (header + menú) para contraste seguro ===
                        _css_hdr = """
                        <style>
                        /* Texto del header en gris oscuro (legible sobre fondo blanco) */
                        header, header * { color: #444 !important; }

                        /* Enlaces del menú (TOC) dentro del header: gris oscuro y con hover subrayado */
                        header nav a,
                        .toc a {
                            color: #444 !important;
                            text-decoration: none;
                        }
                        header nav a:hover,
                        .toc a:hover { text-decoration: underline; }

                        /* Pastillas/etiquetas del header: texto oscuro + contorno suave */
                        header .badge,
                        header .chip,
                        header .pill,
                        header .tag,
                        header span.badge,
                        header span.pill {
                            color: #111 !important;
                            box-shadow: inset 0 0 0 1px rgba(0,0,0,.28);
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_hdr + "</style>", 1)
                        # === CSS: TOC como botones azules con alto contraste ===
                        _css_tocbtn = """
                        <style>
                        /* Contenedor del TOC: filas envolventes y espacio entre botones */
                        .toc{
                            display: flex;
                            flex-wrap: wrap;
                            gap: 8px;
                            margin: 6px 0 10px;
                        }
                        /* Cada enlace del TOC luce como botón “pill” azul */
                        .toc a{
                            display: inline-block;
                            background: #0B57D0;             /* azul accesible */
                            color: #fff !important;           /* texto blanco, alto contraste */
                            padding: 6px 12px;
                            border-radius: 9999px;            /* pastilla */
                            border: 1px solid rgba(0,0,0,.15);
                            text-decoration: none !important;
                            font-weight: 500;
                            line-height: 1.1;
                            box-shadow: 0 1px 0 rgba(0,0,0,.06);
                            transition: filter .12s ease, transform .06s ease;
                        }
                        .toc a:hover{ filter: brightness(.92); }
                        .toc a:active{ transform: translateY(1px); }
                        .toc a:focus{
                            outline: 2px solid #003C99;       /* foco visible */
                            outline-offset: 2px;
                        }

                        /* Móvil: botones un poco más compactos */
                        @media (max-width: 640px){
                            .toc{ gap: 6px; }
                            .toc a{ padding: 5px 10px; font-size: 14px; }
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_tocbtn + "</style>", 1)
                        # === CSS: líneas/bordes para la tabla de "Todos los contactos" ===
                        _css_tc_lines = """
                        <style>
                        /* Solo afecta la sección con id="todos-contactos" */
                        #todos-contactos table{
                            width: 100%;
                            border-collapse: collapse;
                        }
                        #todos-contactos thead th{
                            background: #f7f7f7;
                            border-top: 1px solid #e6e6e6;
                            border-bottom: 1px solid #e6e6e6;
                        }
                        #todos-contactos tbody td{
                            border-bottom: 1px solid #eaeaea;
                        }
                        /* (Opcional) líneas verticales suaves como en otras tablas */
                        #todos-contactos th:not(:last-child),
                        #todos-contactos td:not(:last-child){
                            border-right: 1px solid #f0f0f0;
                        }
                        /* Hover sutil para lectura */
                        #todos-contactos tbody tr:hover{
                            background: #fafafa;
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_tc_lines + "</style>", 1)

                        # === CSS: margen para anclas y scroll suave ===
                        _css_anchor = """
                        <style>
                        :root { --anchor-offset: 96px; } /* valor seguro; JS lo ajusta a la altura real */
                        /* Cualquier sección con id (#meta, #antenas, #todos-contactos, etc.) dejará colchón arriba */
                        section[id] { scroll-margin-top: var(--anchor-offset); }

                        /* Scroll suave nativo (fallback con JS abajo) */
                        html { scroll-behavior: smooth; }
                        </style>
                        """
                        html = html.replace("</style>", _css_anchor + "</style>", 1)


                        # === CSS: contraste para pastillas claras ===
                        _css_contrast = """
                        <style>
                        .need-contrast{
                            /* contorno discreto para que destaque en fondo blanco */
                            box-shadow: inset 0 0 0 1px rgba(0,0,0,.28);
                            color: #111 !important;            /* texto oscuro para legibilidad */
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_contrast + "</style>", 1)


                    else:
                        html += bloque_tc
        except Exception:
            pass


        # REORDENAR-SECCIONES-3: asegurar "Todos los contactos" quede como última sección (antes del pie)
        try:
            idx_tc = html.find('<section id="todos-contactos">')
            if idx_tc != -1:
                ini_tc = html.rfind("<section", 0, idx_tc)
                fin_tc = html.find("</section>", idx_tc)
                if ini_tc != -1 and fin_tc != -1:
                    bloque_tc = html[ini_tc:fin_tc+10]
                    # quitar del lugar original
                    html = html.replace(bloque_tc, "")
                    # reinsertar al final del <body> (antes del pie legal)
                    html = html.replace("</body>", bloque_tc + "\n</body>")
        except Exception:
            pass

    except Exception:
        # si algo falla, no bloquees la generación del HTML
        pass

        # STICKY-HEADER-1: CSS adicional para que el encabezado de las tablas quede fijo al hacer scroll
    css_sticky = """
<style>
/* Encabezados fijos para tablas largas (más contraste) */
.tbl thead th,
.tabla-compacta thead th{
  position: sticky;
  top: 0;
  z-index: 2;
  background: #e9ecef !important;   /* gris más oscuro */
  color:#111;
  box-shadow: 0 1px 0 rgba(0,0,0,.16);
  background-clip: padding-box;
}
</style>

"""
    # Inyectar el CSS extra justo antes de cerrar el <body>
    html = html.replace("</body>", css_sticky + "\n</body>")

    # --- ESCRIBIR ARCHIVO ---

    # === HTML-BRANDING-2: Pie legal + byline (al FINAL del <body>) ===
    try:
        br = (CONFIG or {}).get("branding", {}) if 'CONFIG' in globals() else {}
        _pl_on   = bool(br.get("mostrar_pie_legal", True))
        _pl_txt  = str(br.get("pie_legal_texto", ""))
        _by_txt  = str(br.get("byline_texto", ""))
        _pl_prnt = bool(br.get("pie_legal_en_impresion", True))

        if _pl_on and (_pl_txt or _by_txt):
            # 1) CSS del pie (lo metemos en <head>)
            _disp = "block" if _pl_prnt else "none"
            _css_pl = f"""
            <style>
                .legal {{
                    margin-top:30px;
                    padding:10px 0;
                    border-top:1px solid #eee;
                    color:#666;
                    font-size:12px;
                    line-height:1.35;
                    text-align:center !important;
                }}
                .legal .legal-text {{
                    display:block;
                    text-align:center !important;
                }}
                .legal .by {{
                    float:none;
                    display:block;
                    margin-top:6px;
                    color:#444;
                    text-align:center !important;
                }}
                @media print {{
                    .legal {{ display:{_disp} }}
                }}
            </style>
            """



            html = html.replace("</style>", "</style>" + _css_pl, 1)

            # --- FOOTER legal + byline desde config.branding (robusto) ---
            try:
                _branding = CONFIG.get("branding", {}) if isinstance(CONFIG, dict) else {}
                _legal   = str(_branding.get("pie_legal_texto", "")).strip()
                _byline  = str(_branding.get("byline_texto", "")).strip()

                # Construir footer solo si hay algo que mostrar
                _footer_html = ""
                if _legal or _byline:
                    _by  = f'<span class="by" style="display:block;text-align:center">{_byline}</span>' if _byline else ""
                    # Eliminar cualquier mención de fecha o versión al final del pie legal
                    _legal_sin_fecha = re.sub(r'Generado.*?\d{2}/\d{2}/\d{4}.*?Versi[óo]n.*', '', _legal, flags=re.I)
                    _txt = f'<span class="legal-text">{_legal_sin_fecha.strip()}</span>' if _legal_sin_fecha.strip() else ""
                    _footer_html = (
                        f'<footer class="legal" style="text-align:center">'
                        f'<span class="legal-text" style="display:block;text-align:center">{_txt}</span>'
                        f'{_by}'
                        f'</footer>'
                    )


                    # 0) Eliminar cualquier footer previo (ambas comillas)
                    html = html.replace("<footer class='legal'>", "<footer class=\"legal\">")
                    html = html.replace('<footer class="legal">', "")

                    # 1) Insertar ANTES del cierre de </body> (posición segura)
                    _tag = "</body>"
                    _pos = html.rfind(_tag)
                    if _pos != -1:
                        html = html[:_pos] + _footer_html + _tag + html[_pos+len(_tag):]
                    else:
                        # 2) Si por alguna razón no hay </body>, lo agregamos al final
                        html += _footer_html
            except Exception:
                pass

    except Exception:
        pass
    # === HTML-BRANDING-2 (fin) ===

    # FORZAR-ULTIMO: mover "Todos los contactos" al final del documento (antes del footer si existe)
    try:
        idx_tc = html.find('id="todos-contactos"')
        if idx_tc != -1:
            ini_tc = html.rfind("<section", 0, idx_tc)
            fin_tc = html.find("</section>", idx_tc)
            if ini_tc != -1 and fin_tc != -1:
                bloque_tc = html[ini_tc:fin_tc+10]
                # quitar del lugar original
                html = html[:ini_tc] + html[fin_tc+10:]

                # Buscar CUALQUIER footer class="legal" con o sin atributos extra
                m = re.search(r"<footer\s+class=['\"]legal['\"][^>]*>", html, flags=re.I)
                foot_i = m.start() if m else -1


                if foot_i != -1:
                    # Insertar ANTES del footer (queda como última sección visible)
                    html = html[:foot_i] + bloque_tc + html[foot_i:]
                elif "</body>" in html:
                    # Fallback: justo antes de </body>
                    html = html.replace("</body>", bloque_tc + "\n</body>", 1)
                else:
                    # Último fallback: al final del documento
                    html += bloque_tc
    except Exception:
        pass


        # TOC-REFRESH: reconstruir índice final (orden objetivo) y reemplazar el anterior
    try:
        def _has(id_): 
            return f'id="{id_}"' in html

        _links = []
        if _has("meta"):
            _links.append('<a href="#meta">Metadatos</a>')
        if _has("resumen-antenas"):
            _links.append('<a href="#resumen-antenas">Antenas más activadas</a>')
        # Heatmap integrado en el resumen de antenas: no incluir enlace específico en el TOC.
        if _has("interacciones"):
            _links.append('<a href="#interacciones">Contactos con más comunicación</a>')
        # Rangos: aceptar cualquiera de los dos IDs posibles
        if _has("antenas-rangos") or _has("rangos"):
            _id_rangos = "antenas-rangos" if _has("antenas-rangos") else "rangos"
            _links.append(f'<a href="#{_id_rangos}">Antenas por rango horario</a>')
        if _has("historial-cambios"):
            _links.append('<a href="#historial-cambios">Historial de cambios de antena</a>')
        if _has("interacciones-recientes"):
            _links.append('<a href="#interacciones-recientes">Interacciones recientes</a>')
        if _has("top-antenas"):
            _links.append('<a href="#top-antenas">Todas las antenas</a>')
        if _has("todos-contactos"):
            _links.append('<a href="#todos-contactos">Todos los contactos</a>')

        if _links:
            _toc_html = '<nav id="toc" class="toc" style="z-index:999; background:#fff; border-bottom:1px solid #e5e7eb; box-shadow:0 2px 6px rgba(0,0,0,.06); padding:8px 12px;">' + ' ... '.join(_links) + '</nav>'
            # Si ya existe un TOC, reemplazarlo; si no, insertarlo después del </header>
            i = html.find('<nav id="toc"')
            if i != -1:
                j = html.find("</nav>", i)
                if j != -1:
                    html = html[:i] + _toc_html + html[j+6:]
            else:
                html = html.replace("</header>", "</header>\n  " + _toc_html, 1)
    except Exception:
        pass


    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # --- HASHES de salida: HTML, KML y KMZ (si existen) ---
    try:
        import hashlib

        def _file_hashes(path: str) -> tuple[str, str, int]:
            md5 = hashlib.md5()
            sha = hashlib.sha256()
            size = 0
            with open(path, 'rb') as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    md5.update(chunk)
                    sha.update(chunk)
            return md5.hexdigest(), sha.hexdigest(), size

        archivos = []
        # HTML recién generado
        if os.path.exists(html_path):
            archivos.append(("HTML", html_path))
        # KML (ruta absoluta recibida por parámetro)
        if archivo_kml and os.path.exists(archivo_kml):
            archivos.append(("KML", archivo_kml))
        # KMZ (si existe, en la ruta resuelta más arriba)
        try:
            if 'kmz_abs' in locals() and kmz_abs and os.path.exists(kmz_abs):
                archivos.append(("KMZ", kmz_abs))
        except Exception:
            pass

        if archivos:
            txt_hash = os.path.join(carpeta_salida, f"{nombre_salida}_hashes.txt")
            lines = []
            lines.append(f"Hashes generados: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for etiqueta, path in archivos:
                try:
                    md5, sha, size = _file_hashes(path)
                    lines.append(f"[{etiqueta}] {os.path.basename(path)}")
                    lines.append(f"  Ruta: {path}")
                    lines.append(f"  Tamaño: {size} bytes")
                    lines.append(f"  MD5: {md5}")
                    lines.append(f"  SHA256: {sha}\n")
                except Exception as _e:
                    lines.append(f"[{etiqueta}] {path} — error al calcular hashes: {_e}\n")
            with open(txt_hash, 'w', encoding='utf-8') as fh:
                fh.write("\n".join(lines).strip() + "\n")
            try:
                log(f"[INFO] Hashes guardados en: {txt_hash}")
            except Exception:
                print(f"[INFO] Hashes guardados en: {txt_hash}")
    except Exception:
        # Nunca bloquear la generación por hashes
        pass


    return html_path



# --- Anti-hojas: ignorar ocultas y elegir visible ---
# 🔄 WRAPPER: Funciones extraídas a tz_core.data_loader
from tz_core.data_loader import obtener_hojas_visibles, listar_todas_hojas, seleccionar_hoja_visible, seleccionar_hoja, cargar_excel_con_normalizacion

def _seleccionar_hoja_visible(ruta_excel):
    """Wrapper de compatibilidad para tz_core.data_loader.seleccionar_hoja_visible"""
    return seleccionar_hoja_visible(ruta_excel)

def _cargar_excel_con_normalizacion(ruta_excel, hoja_elegida=None):
    """
    Wrapper de compatibilidad para tz_core.data_loader.cargar_excel_con_normalizacion
    
    🚨 FASE 5.3a - SISTEMA DUAL DE COLUMNAS EXTRAÍDO 🚨
    
    Esta función implementa el sistema dual de columnas descubierto durante 
    la refactorización campo minado:
    
    1. df.attrs["orig_cols"] - Columnas originales del archivo (para UI)
    2. df.columns normalizadas - Columnas procesadas (para algoritmo)
    
    CRÍTICO: Ambas versiones son necesarias y NO deben ser "optimizadas".
    La UI muestra nombres reales, el algoritmo usa nombres limpiados.
    
    Preserva comportamiento exacto de líneas originales 6543-6557.
    """
    return cargar_excel_con_normalizacion(ruta_excel, hoja_elegida)

# --- Fallback: listar TODAS las hojas con pandas y seleccionar una ---
# 🔄 WRAPPER: Funciones extraídas a tz_core.data_loader (wrappers ya definidos arriba)

# --- Normalizadores robustos y pre-flight de esenciales ---

ESENCIALES_IN = ["fecha", "hora", "tel", "imei", "interaccion", "contacto", "lat", "long", "azimut", "antena"]

def _es_num(x):
    """Wrapper de compatibilidad - usa tz_core.validation_utils.es_num"""
    return es_num(x)

def _pad_hhmmss(s: str) -> str | None:
    """Wrapper de compatibilidad - usa tz_core.data_normalizer._pad_hhmmss"""
    from tz_core.data_normalizer import _pad_hhmmss as _pad_modular
    return _pad_modular(s)

def _normalizar_fecha(df: pd.DataFrame) -> list:
    """Wrapper de compatibilidad - usa tz_core.data_normalizer._normalizar_fecha"""
    from tz_core.data_normalizer import _normalizar_fecha as _normalizar_fecha_modular
    return _normalizar_fecha_modular(df)

def _normalizar_hora(df: pd.DataFrame) -> list:
    """Wrapper de compatibilidad - usa tz_core.data_normalizer._normalizar_hora"""
    from tz_core.data_normalizer import _normalizar_hora as _normalizar_hora_modular
    return _normalizar_hora_modular(df)

# --- Helpers de hora y carpetas/rangos (Preset A SV) ---
# (Ahora importados desde tz_core.time_utils)

# =========================
# Flujo principal
# =========================

def _modo_manual():
    """
    Entrada manual de puntos/antenas con validación básica.
    Genera un KML/KMZ usando los mismos estilos reusables.
    """
    global CONFIG
    from collections import Counter

    log("=== INICIANDO MODO MANUAL ===")
    log("Configurando funciones auxiliares para entrada de datos...")

    # Helpers locales
    def _input_str(msg, obligatorio=False, maxlen=None):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            if s == "" and obligatorio:
                print("Este campo es obligatorio.")
                continue
            if maxlen and len(s) > maxlen:
                print(f"Máximo {maxlen} caracteres.")
                continue
            return s

    def _input_float(msg, obligatorio=False):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            try:
                return float(s.replace(",", "."))
            except Exception:
                print("Valor numérico inválido. Ej: 13.71234")

    def _input_int(msg, obligatorio=False, minv=None, maxv=None):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            try:
                val = int(s)
                if minv is not None and val < minv:
                    print(f"Debe ser ≥ {minv}."); continue
                if maxv is not None and val > maxv:
                    print(f"Debe ser ≤ {maxv}."); continue
                return val
            except Exception:
                print("Ingrese un entero válido.")

    def _listar(items):
        if not items:
            print("No hay registros cargados.")
            return
        print("\n# | Antena (corta) | Lat, Long | Azimut")
        for i, it in enumerate(items, 1):
            a = it.get("antena") or "(sin nombre)"
            a = (a[:38] + "…") if len(a) > 40 else a
            lat = it.get("lat")
            lon = it.get("long")
            az  = it.get("azimut")
            print(f"{i:>2} | {a:<40} | {lat},{lon} | {az if az is not None else '-'}")
        print()

    def _armar_df(items):
        # Convertimos a DF con los nombres que ya espera tu pipeline
        df = pd.DataFrame(items)
        # Tipos
        for c in ("lat", "long"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "azimut" in df.columns:
            df["azimut"] = pd.to_numeric(df["azimut"], errors="coerce")
        # Fecha/Hora si faltan
        if "fecha" not in df.columns: df["fecha"] = None
        if "hora"  not in df.columns: df["hora"]  = None
        return df
        
    def _sanear_nombre_archivo(s):
        """
        Wrapper para compatibilidad - usar sanear_nombre_archivo de tz_core.utils
        
        CRÍTICO: Preserva fallback original "antenas_manual" para mantener
        comportamiento idéntico en casos límite (None, "", "...", "___")
        
        Función original extraída con cero breaking changes garantizado.
        """
        return sanear_nombre_archivo(s, "antenas_manual")

    def _nombre_auto_desde_items(items):
        # toma el primer tel y el primer alias no vacios
        tel = next((it.get("tel") for it in items if it.get("tel")), None)
        alias = next((it.get("alias") for it in items if it.get("alias")), None)
        partes = []
        if tel:   partes.append(str(tel))
        if alias: partes.append(str(alias))
        base = "_".join(partes) if partes else "antenas_manual"
        return _sanear_nombre_archivo(base)

    # --------- flujo interactivo ---------
    items = []
    log("Iniciando flujo interactivo de entrada manual")
    print("\nModo MANUAL. Ingresará uno o más puntos/antenas.")
    
    # Preguntar tipo de registro UNA SOLA VEZ al inicio
    log("Solicitando tipo de registro al usuario...")
    print("\n¿Qué tipo de registros desea agregar?")
    print("[1] Antenas/Celdas")
    print("[2] Puntos libres (lugares, domicilios, escenas, etc.)")
    tipo_modo = (input("Tipo (1/2, Enter=1): ").strip() or "1")
    es_punto_libre = (tipo_modo == "2")
    log(f"Usuario seleccionó tipo: {'Puntos libres' if es_punto_libre else 'Antenas/Celdas'}")
    
    if es_punto_libre:
        print("\n→ Modo: Puntos libres (sin azimut, campos simplificados)")
    else:
        print("\n→ Modo: Antenas/Celdas (con azimut y campos completos)")

    log("Iniciando bucle principal de entrada de datos...")
    while True:
        print("\nMenú:")
        print("[A] Agregar registro")
        print("[L] Listar registros")
        print("[E] Eliminar registro (#)")
        print("[G] Graficar (generar KML/KMZ)")
        print("[V] Volver (cancelar)")
        op = input("Opción: ").strip().upper() or "A"
        log(f"Usuario seleccionó opción del menú: '{op}'")

        if op == "V":
            log("Usuario canceló modo manual, regresando sin generar archivos")
            print("Volviendo sin generar…")
            return

        if op == "L":
            log(f"Listando {len(items)} registros existentes")
            _listar(items)
            continue

        if op == "E":
            if not items:
                log("Intento de eliminar registro sin datos existentes")
                print("No hay registros para eliminar.")
                continue
            _listar(items)
            s = input("Número de registro a eliminar: ").strip()
            log(f"Usuario ingresó índice para eliminar: '{s}'")
            if s.isdigit():
                idx = int(s) - 1
                if 0 <= idx < len(items):
                    borr = items.pop(idx)
                    nombre_borrado = borr.get('antena','(sin nombre)')
                    log(f"Registro eliminado exitosamente: {nombre_borrado}")
                    print(f"Eliminado: {nombre_borrado}")
                else:
                    log(f"Índice fuera de rango: {idx}, total items: {len(items)}")
                    print("Índice fuera de rango.")
            else:
                log(f"Entrada inválida para eliminar: '{s}' (no es número)")
                print("Ingrese un número válido.")
            continue

        if op == "A":
            log("Iniciando entrada de nuevo registro...")
            print("\n— Nuevo registro —")

            if es_punto_libre:
                # Punto libre (sin azimut ni campos de antena)
                nombre = _input_str("Nombre/identificador del lugar: ", True, 160)
                direccion = _input_str("Dirección del lugar (opcional): ", False, 500)
                lat  = _input_float("Latitud (obligatoria): ", True)
                lon  = _input_float("Longitud (obligatoria): ", True)
                comentarios = _input_str("Comentarios (opcional): ", False, 800)

                # Mapear a las columnas soportadas por el generador KML
                # Usamos 'antena' como nombre del punto; 'direccion' se muestra en su bloque
                # y 'detalle' lo reutilizamos para comentarios.
                items.append({
                    "tipo": "punto",
                    "antena": nombre,
                    "detalle": comentarios,
                    "direccion": direccion,
                    "lat": lat,
                    "long": lon,
                    "azimut": None,  # sin orientación
                })
                print("✓ Punto agregado.")
            else:
                # Antena/Celda
                antena = _input_str("Nombre de la antena (recomendado corto): ", True, 120)
                detalle = _input_str("Detalle/dirección (opcional): ", False, 500)
                lat  = _input_float("Latitud (obligatoria): ", True)
                lon  = _input_float("Longitud (obligatoria): ", True)
                az   = _input_int("Azimut 0–359 (opcional): ", False, 0, 359)

                # Identidad (opcionales)
                tel     = _input_str("Tel (opcional): ", False, 50)
                imei    = _input_str("IMEI (opcional): ", False, 50)
                alias   = _input_str("Alias (opcional): ", False, 120)
                usuario = _input_str("Nombre del Usuario (opcional): ", False, 200)
                abonado = _input_str("Abonado (opcional): ", False, 200)

                # Técnica (opcionales)
                celda = _input_str("Celda (opcional): ", False, 50)
                lac   = _input_str("LAC (opcional): ", False, 50)

                # Interacción (opcionales)
                interaccion  = _input_str("Interacción (opcional): ", False, 80)
                tel_contacto = _input_str("Tel contacto (opcional): ", False, 50)
                duracion     = _input_int("Duración en segundos (opcional): ", False, 0)

                items.append({
                    "tipo": "antena",
                    "antena": antena, "detalle": detalle,
                    "lat": lat, "long": lon, "azimut": az,
                    "tel": tel, "imei": imei, "alias": alias,
                    "usuario": usuario, "abonado": abonado,
                    "celda": celda, "lac": lac,
                    "interaccion": interaccion,
                    "tel_contacto": tel_contacto,
                    "duracion": duracion
                })
                print("✓ Registro agregado.")
            continue

        if op == "G":
            if not items:
                print("No hay registros para graficar.")
                continue

            # Carpeta y nombre de salida
            # [MOVIDO] La selección de carpeta se hará al final del flujo.
            base_auto = _nombre_auto_desde_items(items)
            nombre_sugerido = _input_str(
                f"Nombre base del archivo (Enter = {base_auto}): ", False, 120
            ) or base_auto
            # (No crear carpeta aquí)

            # Normalizar nombre base y preparar carpeta de salida (manual)
            nombre_salida = (nombre_sugerido or base_auto)
            # === Color tema (modo manual, antes de seleccionar carpeta) ===
            CONFIG = _solicitar_color_tema(CONFIG)

            try:
                carpeta_base = seleccionar_carpeta()
            except Exception:
                carpeta_base = None

            if not carpeta_base:
                print("[QC] Selección de carpeta cancelada. Operación abortada.")
                return

            print(f"[QC] Carpeta destino: {carpeta_base}")

            carpeta_salida = os.path.join(carpeta_base, nombre_salida)
            os.makedirs(carpeta_salida, exist_ok=True)

            # DF y KML
            df = _armar_df(items)
            # --- RUTAS FINALES KML/KMZ (modo manual) ---
            if es_punto_libre:
                archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
                archivo_kml, desc_coords = generar_kml_puntos_libres(df, archivo_kml, CONFIG)
                print(f"KML generado en: {archivo_kml}")
                kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"
                if os.path.exists(kmz_path):
                    print(f"KMZ generado en: {kmz_path}")
                print(f"Filas descartadas por coordenadas inválidas: {desc_coords}")
                print(f"Reporte de errores generado en: {archivo_errores}")
                return
            # Requiere que ya existan: carpeta_salida y nombre_salida
            if CONFIG.get("salida", {}).get("separar_kml_kmz", False):
                carpeta_kml = os.path.join(carpeta_salida, "kml")
                os.makedirs(carpeta_kml, exist_ok=True)
                archivo_kml = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kml")
                archivo_kmz = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kmz")
            else:
                archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
                archivo_kmz = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")

            # Generar el KML/KMZ en modo plano (sin subcarpetas del KML)
            archivo_kml, desc_coords = generar_kml(df, archivo_kml, flat=True)
            print(f"KML generado en: {archivo_kml}")


            # KMZ (si se pudo generar)
            if bool(CONFIG.get("salida", {}).get("separar_kml_kmz", False)):
                kml_dir = os.path.dirname(archivo_kml)
                base_dir = os.path.dirname(kml_dir) if os.path.basename(kml_dir).lower() == "kml" else kml_dir
                kmz_dir = os.path.join(base_dir, "kmz")
                kmz_path = os.path.join(kmz_dir, os.path.splitext(os.path.basename(archivo_kml))[0] + ".kmz")
            else:
                kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"

            if os.path.exists(kmz_path):
                print(f"KMZ generado en: {kmz_path}")

            print(f"Filas descartadas por coordenadas inválidas: {desc_coords}")
            print(f"Reporte de errores generado en: {archivo_errores}")
            return


        print("Opción no reconocida.")

# === RUN_TZ_ANALYSIS (INICIO) ================================================
# Puente público para GUI: recibe parámetros, evita prompts y retorna rutas.
# Pegar ESTE bloque ENCIMA de `def main():` (sangría cero).
def run_tz_analysis(
    ruta_entrada: str,
    hoja,                          # int o str o None
    top_antenas: int,
    top_contactos: int,
    solo_kmz: bool,
    carpeta_salida: str | None = None,
) -> dict:
    """
    Retorna diccionario con rutas y log:
      {"html": path|None, "kmz": path|None, "hashes": path|None, "log": path|None}
    No imprime a consola; captura el log.
    """
    import io, os, sys, time, glob, contextlib
    from datetime import datetime

    # --- Sanitizar entradas mínimas ---
    ruta_entrada = (ruta_entrada or "").strip().strip('"')
    if not ruta_entrada or not os.path.isfile(ruta_entrada):
        return {"html": None, "kmz": None, "hashes": None, "log": None}

    if carpeta_salida:
        carpeta_salida = carpeta_salida.strip().strip('"')
        if not carpeta_salida:
            carpeta_salida = None

    # --- Preparar overrides (Top N, Solo KMZ) ---
    #   1) Top N: el script ya contempla OVERRIDE_TOPS si existe en globals()
    #   2) Solo KMZ: el script consulta CONFIG["salida"]["solo_kmz"]
    global CONFIG
    try:
        if "CONFIG" not in globals() or not isinstance(CONFIG, dict):
            CONFIG = {}
        CONFIG.setdefault("salida", {})
        CONFIG["salida"]["solo_kmz"] = bool(solo_kmz)
    except Exception:
        pass
    globals()["OVERRIDE_TOPS"] = {
        "antenas": int(top_antenas) if str(top_antenas).isdigit() else 5,
        "contactos": int(top_contactos) if str(top_contactos).isdigit() else 5,
    }

    # --- Monkey-patch de funciones interactivas para evitar prompts ---
    # Guardamos originales para restaurar luego
    g = globals()
    _orig = {}
    def _keep(name, fallback=None):
        if name in g:
            _orig[name] = g[name]
            return g[name]
        _orig[name] = fallback
        return fallback

    _keep("_menu_principal")
    _keep("seleccionar_archivo")
    _keep("seleccionar_carpeta")
    _keep("_input_str")
    _keep("_seleccionar_hoja_visible")
    _keep("_solicitar_overrides_topn")
    _keep("_solicitar_color_tema")

    # 1) Modo directo: "1" (bitácora Excel)
    def _menu_principal_mock():
        return "1"
    g["_menu_principal"] = _menu_principal_mock

    # 2) Archivo de entrada (sin diálogo)
    def _sel_arch_mock():
        return ruta_entrada
    g["seleccionar_archivo"] = _sel_arch_mock

    # 3) Carpeta de salida (sin diálogo)
    def _sel_carp_mock():
        return carpeta_salida or os.getcwd()
    g["seleccionar_carpeta"] = _sel_carp_mock

    # 4) Nombre sugerido / otros input_str: devolver vacío = aceptar por defecto
    def _input_str_mock(msg, *args, **kwargs):
        return ""
    g["_input_str"] = _input_str_mock

    # 5) Selección de hoja visible (si el script lo usa)
    if hoja is not None:
        def _hoja_mock(_archivo):
            return hoja
        g["_seleccionar_hoja_visible"] = _hoja_mock

    # 6) Overrides TopN si el flujo intenta pedirlos
    def _ovr_mock(_cfg):
        return globals().get("OVERRIDE_TOPS", None)
    g["_solicitar_overrides_topn"] = _ovr_mock

    # 7) Color tema: no preguntar; dejar CONFIG tal cual
    def _color_mock(cfg):
        """MIGRADA A tz_core.color_utils - usar import desde allí"""
        return color_mock(cfg)
    g["_solicitar_color_tema"] = _color_mock

    # --- Silenciar input() durante la ejecución ---
    import builtins
    _orig_input_builtin = getattr(builtins, "input", None)

    def _input_mock(*args, **kwargs):
        # Simula presionar Enter en cualquier prompt
        return ""

    try:
        builtins.input = _input_mock
    except Exception:
        pass

    # --- Capturar stdout/stderr como log en memoria ---
    buf = io.StringIO()
    html_path = kmz_path = hashes_path = log_path = None

    # --- Snapshot de archivos previos para detectar nuevos (HTML/KMZ/HASHES) ---
    def _snapshot(folder):
        try:
            pat = "**/*"
            return set(glob.glob(os.path.join(folder, pat), recursive=True))
        except Exception:
            return set()

    out_root = _sel_carp_mock()
    before = _snapshot(out_root)

    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            # Ejecutar flujo normal
            main()
    except SystemExit:
        # Algunos abortos elegantes usan SystemExit; igual seguimos capturando
        pass
    except Exception as e:
        print(f"[ERROR] run_tz_analysis: {e}", file=sys.stderr)

    # --- Detectar nuevos archivos generados ---
    time.sleep(0.05)  # pequeño respiro para flush del FS
    after = _snapshot(out_root)
    created = [p for p in (after - before) if os.path.isfile(p)]

    # Heurística simple: tomar los más recientes por extensión
    def _pick(exts):
        cands = [p for p in created if os.path.splitext(p)[1].lower() in exts]
        if not cands:
            # buscar también en subcarpetas nuevas
            cands = [p for p in after if os.path.splitext(p)[1].lower() in exts]
        if not cands:
            return None
        cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return cands[0]

    html_path   = _pick({".html", ".htm"})
    kmz_path    = _pick({".kmz"})
    hashes_path = _pick({".txt"})  # HASHES.txt esperado como .txt

    # --- Persistir el log a archivo junto a salidas ---
    try:
        base_dir = os.path.dirname(html_path or kmz_path or out_root)
        os.makedirs(base_dir, exist_ok=True)
        log_path = os.path.join(base_dir, "ejecucion_log.txt")
        with open(log_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(buf.getvalue())
    except Exception:
        log_path = None

    # --- Restaurar originales ---
    try:
        for name, fn in _orig.items():
            if fn is not None:
                g[name] = fn
    except Exception:
        pass

        # Restaurar input() original
    try:
        if _orig_input_builtin is not None:
            builtins.input = _orig_input_builtin
    except Exception:
        pass

    return {
        "html": html_path,
        "kmz": kmz_path,
        "hashes": hashes_path,
        "log": log_path,
    }
# === RUN_TZ_ANALYSIS (FIN) ====================================================

# === SECCIÓN: MENÚ PRINCIPAL / ENTRYPOINT (opciones 1/2/3) ===
def main():
    """Muestra el menú principal y orquesta el flujo de opciones (1: completo, 2: por tiempo, 3: manual)."""
    global CONFIG
    global nombre_salida, hoja, archivo_errores
    nombre_salida = ""
    hoja = None
    archivo_errores = ""

    log("=== INICIO APLICACIÓN TZ ANALYZER ===")
    log("Inicializando variables globales...")

    # ===== Menú de modos (único) =====
    log("Mostrando menú principal de opciones...")
    while True:
        print("\nSeleccione el modo de trabajo:")
        print("[1] Procesar bitácora completa")
        print("[2] Procesar por tiempo (día / rango de días / rango de horas)")
        print("[3] Ingresar antenas manualmente")
        resp = input("Opción (1/2/3, Enter=1): ").strip() or "1"
        log(f"Usuario seleccionó opción: '{resp}'")

        if resp == "3":
            log("Iniciando modo manual de antenas...")
            _modo_manual()        # Al terminar manual, volvemos a mostrar el menú
            log("Regresando del modo manual al menú principal")
            continue

        if resp in ("1", "2"):
            opcion = resp
            log(f"Modo válido seleccionado: {opcion}")
            # Preguntar color SIEMPRE para modos 1/2
            log("Solicitando configuración de tema de colores...")
            CONFIG = _solicitar_color_tema(CONFIG)
            log("Configuración de colores completada")
            break

        log(f"Opción inválida recibida: '{resp}', mostrando menú nuevamente")
        print("[QC] Opción inválida, intenta de nuevo.")
    
    # ===== Modo Excel (bitácora) =====
    log("Iniciando selección de archivo de entrada...")
    archivo_entrada = seleccionar_archivo()
    if not archivo_entrada:
        log("ERROR: Usuario no seleccionó archivo, terminando ejecución")
        print("No se seleccionó un archivo. Saliendo.")
        return
    
    log(f"Archivo seleccionado exitosamente: {archivo_entrada}")

    # La carpeta se elegirá al final (previsualización)
    carpeta_salida = None

    # Selección de hoja visible (si hay varias)
    log("Iniciando selección de hoja de Excel...")
    hoja = _seleccionar_hoja_visible(archivo_entrada)
    log(f"Hoja seleccionada: {hoja}")

    # Carga del Excel con sistema dual de columnas (FASE 5.3a modular)
    log(f"Iniciando carga de datos desde {archivo_entrada}...")
    try:
        df, hoja_usada = _cargar_excel_con_normalizacion(archivo_entrada, hoja)
        log(f"Excel cargado exitosamente: {len(df)} filas, hoja usada: {hoja_usada}")
    except Exception as e:
        log(f"ERROR CRÍTICO al cargar Excel: {type(e).__name__}: {e}")
        print(f"Error al leer el Excel: {e}")
        return

    # Normalización adicional de encabezados (heredada del sistema dual)
    log("Aplicando normalización de columnas...")
    df.columns = (
        df.columns.astype(str)
          .str.normalize('NFD').str.encode('ascii', 'ignore').str.decode('ascii')
          .str.lower()
          .str.replace(r'[\s\-\/\.]+', '_', regex=True)   # espacios, guiones, diagonales y puntos -> _
          .str.replace(r'__+', '_', regex=True)           # colapsar múltiples _
          .str.strip('_')                                 # quitar _ al inicio/fin
    )

    # Snapshot de columnas originales (antes de cualquier mapeo/rename)
    cols_originales = list(df.columns)
    log(f"Columnas después de normalización: {cols_originales}")


    # === VALIDACIÓN DE SCHEMA (aborto elegante) — INICIO =======================
    def _coalesce_cols(df, *nombres):
        """Devuelve el primer nombre de columna que exista en df (case-sensitive actual)."""
        for n in nombres:
            if n in df.columns:
                return n
        return None

    def _fmt_lista(xs): 
        return ", ".join(xs) if xs else "(ninguna)"

    def _valida_formato_hora(serie):
        pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
        sample = serie.astype(str).str.strip().str[:8].head(5)
        ok = sample.apply(lambda v: pat.match(v) is not None).all()
        return ok, sample.tolist()

    def _valida_fecha_parsible(serie):
        try:
            s = pd.to_datetime(serie, errors="coerce", dayfirst=True)
            return s.notna().any(), [str(v) for v in serie.head(5).tolist()]
        except Exception:
            return False, [str(v) for v in serie.head(5).tolist()]

    def _valida_latlon(df):
        """Al menos una fila con lat/long numéricas razonables (no 0,0; dentro de bbox SV)."""
        bbox = (CONFIG or {}).get("geografia", {}).get("sv_bbox", None)
        if not (isinstance(bbox, dict) and all(k in bbox for k in ("lat_min","lat_max","lon_min","lon_max"))):
            bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}  # fallback SV
        try:
            lt = pd.to_numeric(df["lat"], errors="coerce")
            lg = pd.to_numeric(df[_coalesce_cols(df, "long", "lon")], errors="coerce")
            mask = (~lt.isna()) & (~lg.isna()) & (lt != 0) & (lg != 0) \
                & (lt.between(bbox["lat_min"], bbox["lat_max"])) \
                & (lg.between(bbox["lon_min"], bbox["lon_max"]))
            return bool(mask.any())
        except Exception:
            return False

    def validate_schema_or_abort(df):
        """
        Verifica:
        1) Presencia de esenciales (de config.entradas.columnas_esenciales) con tolerancia lon/long.
        2) Alternativas de localización (schema.location_alternatives): p.ej., (lat+long) o (antena).
        3) Tipos mínimos: hora HH:MM:SS, fecha parseable, al menos una fila con lat/long válidas.
        Si falla: imprime guía, loguea y aborta ejecución (SystemExit).
        """
        esenciales_cfg = (CONFIG or {}).get("entradas", {}).get("columnas_esenciales", []) or []
        # Tolerancia: si piden "long", aceptar "lon" también
        esenciales = set(esenciales_cfg)
        if "long" in esenciales and "lon" not in esenciales:
            esenciales.add("lon")

        headers = list(df.columns)
        faltan = [c for c in esenciales if c not in headers]
        # Permitir que si falta long pero hay lon (o viceversa), no cuente como faltante
        if "long" in faltan and "lon" in headers:
            faltan.remove("long")
        if "lon" in faltan and "long" in headers:
            faltan.remove("lon")

        # Alternativas de localización
        alts = (CONFIG or {}).get("schema", {}).get("location_alternatives", []) or []
        # Normalizar posibles 'lon' a 'long' internamente
        def _alt_ok(alt_group):
            # Un grupo es válido si TODAS sus columnas existen (tratando lon/long como equivalentes)
            cols_needed = []
            for c in alt_group:
                if c == "lon":  # tu schema trae 'lon' como canónico, pero el pipeline usa 'long'
                    cols_needed.append(_coalesce_cols(df, "long", "lon"))
                else:
                    cols_needed.append(c if c in df.columns else None)
            return all(col is not None for col in cols_needed)

        hay_alt_loc = any(_alt_ok(g) for g in alts) if alts else True

        problemas = []
        if faltan:
            problemas.append(f"- Faltan columnas esenciales: {_fmt_lista(faltan)}")
        if not hay_alt_loc:
            problemas.append("- No se cumple ninguna alternativa de localización (p. ej., (lat+long) o (antena)).")

        # Chequeos de tipo mínimos
        # hora
        if _coalesce_cols(df, "hora"):
            ok_hora, smp_h = _valida_formato_hora(df["hora"].astype(str))
            if not ok_hora:
                problemas.append(f"- 'hora' debería verse como HH:MM:SS; muestras: {_fmt_lista(smp_h)}")

        # fecha
        if _coalesce_cols(df, "fecha"):
            ok_fecha, smp_f = _valida_fecha_parsible(df["fecha"])
            if not ok_fecha:
                problemas.append(f"- 'fecha' no es parseable en algunas filas; muestras: {_fmt_lista(smp_f)}")

        # lat/long
        if _coalesce_cols(df, "lat") and _coalesce_cols(df, "long", "lon"):
            if not _valida_latlon(df):
                problemas.append("- 'lat/long' no tienen registros válidos (no 0,0; dentro de SV).")

        if problemas:
            guia = []
            guia.append("\n[SCHEMA] No se puede continuar. Ajustá los encabezados o agrega sinónimos:\n")
            guia.extend(p + "\n" for p in problemas)
            guia.append("\nSugerencias:\n")
            guia.append("• Revisá 'entradas.columnas_esenciales' en config.json.\n")
            guia.append("• Usá el wizard para mapear encabezados raros (se persisten en synonyms_user).\n")
            guia.append("• Para 'long' también se acepta 'lon' (sinónimo en schema.fields).\n")
            msg = "".join(guia)
            try:
                log(f"[FATAL][schema] {msg}")
            except Exception:
                pass
            print(msg)
            raise SystemExit(2)
        else:
            try:
                log("[schema] Validación OK: esenciales presentes y tipos mínimos razonables.")
            except Exception:
                pass
            return True
    # === VALIDACIÓN DE SCHEMA — FIN ============================================


    # Auto-mapeo de encabezados (desde CONFIG.schema.fields) con fuzzy
    # - Usa sinónimos del config
    # - Normaliza sinónimos igual que las columnas (lower, sin acentos, separadores -> _)
    # - Fuzzy (difflib) para casos no exactos
    import difflib, re, unicodedata

    def _norm_head(x: str) -> str:
        x = str(x or "").strip()
        x = unicodedata.normalize("NFD", x).encode("ascii", "ignore").decode("ascii")
        x = x.lower()
        x = re.sub(r"[\s\-\/\.]+", "_", x)   # igual que arriba
        x = re.sub(r"__+", "_", x).strip("_")
        return x

    schema_fields = {}
    try:
        schema_fields = (CONFIG.get("schema") or {}).get("fields") or {}
    except Exception:
        schema_fields = {}

    # Canonicos que el script realmente usa internamente (target)
    # Nota: el script usa "long" (no "lon") y "duracion" (no "duracion_seg")
    _target_alias = {
        "lon": "long",
        "duracion_seg": "duracion",
    }
    # --- Alias VISIBLES para etiquetas del wizard (no cambian claves internas) ---
    ALIAS_VISIBLES = {
        "tel": "tel_analizado",
        "ubicacion": "direccion_antena",
    }


    # Construir tabla de sinónimos normalizados -> nombre_canonico_target
    syn2target = {}
    for canon, meta in schema_fields.items():
        target = _target_alias.get(canon, canon)
        # incluir el propio nombre canonico como sinonimo
        for s in [canon] + list(meta.get("synonyms", [])):
            ns = _norm_head(s)
            if ns:
                syn2target[ns] = target

    # Mapeo exacto primero
    rename_map = {}
    for col in list(df.columns):
        ncol = _norm_head(col)  # ya están normalizadas, pero por si acaso
        if ncol in syn2target:
            rename_map[col] = syn2target[ncol]

    # Fuzzy para columnas no mapeadas aún
    remaining = [c for c in df.columns if c not in rename_map]
    candidate_keys = list(syn2target.keys())
    for col in remaining:
        ncol = _norm_head(col)
        if not ncol:
            continue
        # mejores coincidencias (umbral conservador 0.84)
        matches = difflib.get_close_matches(ncol, candidate_keys, n=1, cutoff=0.84)
        if matches:
            best = matches[0]
            rename_map[col] = syn2target[best]

    # Aplicar (solo si NO estamos en QC manual)
    if not MANUAL_QC_MAPPING and rename_map:
        df = df.rename(columns=rename_map)

        # === DEDUP/COALESCE DE COLUMNAS DUPLICADAS (post-rename) =====================
        def _coalesce_duplicates(df: pd.DataFrame, prefer: list[str] | None = None) -> pd.DataFrame:
            """
            Si quedaron columnas duplicadas tras el rename (p.ej. 2 columnas 'hora'),
            coalescea fila por fila tomando el primer valor "no vacío" y elimina duplicadas.
            'prefer' permite dar un orden de preferencia por nombre exacto de columna original.
            """
            import numpy as np

            prefer = prefer or []
            cols = list(df.columns)
            seen = set()
            for col in cols:
                if col in seen:
                    continue
                # ¿Cuántas veces aparece este nombre?
                idxs = [i for i, c in enumerate(cols) if c == col]
                if len(idxs) <= 1:
                    seen.add(col)
                    continue

                # Armar lista de nombres "con sufijo posición" para poder ordenarlos por preferencia
                dup_names = [df.columns[i] for i in idxs]  # todos se llaman igual, pero usamos posiciones
                # Orden: primero los que estén en 'prefer' (si alguno matchea exactamente), luego el resto
                def _rank(n):
                    try:
                        return prefer.index(n)
                    except ValueError:
                        return len(prefer)
                # Nota: aunque todos se llamen igual, pandas conserva el orden original; usamos ese orden más 'prefer'
                sub = [df.iloc[:, i] for i in idxs]
                # Coalesce fila por fila: primer valor que no sea vacío/"Sin Inf."/NaN
                def _clean_series(s: pd.Series) -> pd.Series:
                    s2 = s.astype(object).copy()
                    # normalizamos "vacío"
                    inv = {"", "sin inf", "sin inf.", "nan", "none", "null", "s/i"}
                    s2 = s2.where(~s2.astype(str).str.strip().str.lower().isin(inv), None)
                    return s2

                base = None
                for ser in sub:
                    s = _clean_series(ser)
                    if base is None:
                        base = s
                    else:
                        mask = (base.isna()) | (base.astype(str).str.strip() == "")
                        base = base.where(~mask, s)

                # Asignamos columna coalescida y eliminamos duplicadas extras
                df[col] = base
                # eliminar las otras instancias (dejamos la primera posición)
                drop_pos = idxs[1:]
                df = df.drop(columns=[cols[i] for i in drop_pos])
                # recomputar lista de columnas tras drop (unión: originales + actuales)
                cols = list(dict.fromkeys(cols_originales + list(df.columns)))

                seen.add(col)

            return df

        # Si en tu archivo original había una llamada inmediata a _coalesce_duplicates(...),
        # cortala de donde estaba y pegala aquí debajo, indentada dentro del 'if'.
        # Ejemplo (mantén tus parámetros tal cual):
        # df = _coalesce_duplicates(df, prefer=[...])

    else:
        print("[QC] Sin renombrar encabezados ni coalesce (QC manual activo).")

        
        # Ejecutar dedup/coalesce con preferencia ligera (por si te interesa priorizar algún origen)
        if not MANUAL_QC_MAPPING:
            df = _coalesce_duplicates(df, prefer=["hora", "fecha", "lat", "long", "lon", "azimut", "tel", "imei", "antena"])
        # === FIN DEDUP/COALESCE =======================================================


             # WIZARD (esenciales + selector de UBICACIÓN) y persistencia de sinónimos (modo estricto)
    try:
        import json, unicodedata, re, difflib, sys

        def _norm_head_local(x):
            x = unicodedata.normalize("NFD", str(x)).encode("ascii","ignore").decode("ascii")
            x = x.lower()
            x = re.sub(r"[\s\-\/\.]+","_", x)
            x = re.sub(r"__+","_", x).strip("_")
            return x

        # 1) Schema y alias
        SCHEMA = (CONFIG.get("schema") or {})
        fields_meta = SCHEMA.get("fields", {}) or {}
        location_alts = SCHEMA.get("location_alternatives", [["lat","lon"],["antena"]])
        subject_mode = (SCHEMA.get("subject_default_mode") or "tel").lower()
        _target_alias = {"lon": "long", "duracion_seg": "duracion"}

        # 2) Estado actual
        # lista completa para el wizard (unión: originales + actuales)
        cols = list(dict.fromkeys(cols_originales + list(df.columns)))

        present = set(cols)

        def _has_location_ok():
            return any(all((_target_alias.get(a, a)) in present for a in alt) for alt in location_alts)

        def _need_fields():
            req = set()
            # sujeto
            req.add("imei" if subject_mode == "imei" else "tel")
            # tiempo
            if "timestamp" in present:
                req.add("timestamp")
            else:
                req.update(["fecha","hora"])
            # contacto/interaccion
            req.update(["contacto","interaccion"])
            # ubicación (si no está completa, pediremos luego)
            # respetar required/required_mode del schema
            for k, meta in fields_meta.items():
                tgt = _target_alias.get(k, k)
                if meta.get("required") is True:
                    req.add(tgt)
                if str(meta.get("required_mode","")).lower() == subject_mode:
                    req.add(tgt)
            # faltantes fuera de ubicación
            faltan = [f for f in req if f not in present]
            return faltan

        # 3) Si falta ubicación completa, NO preguntar (modo QC manual)
        if not _has_location_ok():
            if MANUAL_QC_MAPPING:
                print("\n[WIZARD] Falta UBICACIÓN → modo asistido desactivado. Usando 'lat + long' automáticamente (QC).")
                choice = None  # QC manual: se mapea lat/lon dentro del wizard QC, no aquí
            else:
                print("\n[WIZARD] Falta UBICACIÓN. Elegí alternativa:")
                for i, alt in enumerate(location_alts, 1):
                    alt_view = " + ".join([_target_alias.get(x, x) for x in alt])
                    print(f"  [{i}] {alt_view}")
                sel = input("→ Opción (#, Enter=1): ").strip()
                try:
                    k = int(sel) if sel else 1
                except Exception:
                    k = 1
                k = max(1, min(k, len(location_alts)))
                choice = location_alts[k-1]
                # (si no es QC manual, aquí sí pide columnas…)


            # Pedir columnas para la alternativa elegida
            for tgt in choice:
                t_tgt = _target_alias.get(tgt, tgt)
                if t_tgt in present:
                    continue
                tgt_label = ALIAS_VISIBLES.get(tgt, tgt)
                print(f"\n[WIZARD] Elegí la columna para '{tgt_label}':")
                for i, c in enumerate(cols, 1):
                    print(f"  [{i}] {c}")
                sel2 = input(f"→ Columna para '{tgt_label}' (# o Enter=omitir): ").strip()

                if not sel2:
                    continue
                try:
                    k2 = int(sel2)
                    if 1 <= k2 <= len(cols):
                        src = cols[k2-1]
                        if src != t_tgt:
                            if src in df.columns:
                                # caso normal: el nombre elegido todavía existe en df
                                df = df.rename(columns={src: t_tgt})
                            else:
                                # caso tolerante: quizá ya fue renombrada antes; buscamos por nombre normalizado
                                for c in list(df.columns):
                                    if _norm_head(c) == _norm_head(src):
                                        df = df.rename(columns={c: t_tgt})
                                        break
                            present.add(t_tgt)

                except Exception:
                    pass

       # 4) Resolver otros esenciales faltantes (no-ubicación)
        missing = _need_fields()
        if missing:
            if MANUAL_QC_MAPPING:
                print("\n[WIZARD] QC activo: faltan canónicos esenciales (no se pedirá aquí):", ", ".join(missing))
                # No abortamos ni preguntamos; dejamos marcadores para que el pipeline no truene.
                for k in missing:
                    real_tgt = _target_alias.get(k, k)
                    if real_tgt not in df.columns:
                        df[real_tgt] = "SinInf"
                # refrescar listas internas
                cols = list(dict.fromkeys(cols_originales + list(df.columns)))
                present = set(cols)
            else:
                print("\n[WIZARD] Faltan campos esenciales:", ", ".join(missing))
                print("Elegí la columna correspondiente (número). Enter = saltar.\nColumnas disponibles:")
                for i, c in enumerate(cols, 1):
                    print(f"  [{i}] {c}")
                for tgt in missing:
                    tgt_label = ALIAS_VISIBLES.get(tgt, tgt)
                    sel = input(f"→ ¿Cuál columna corresponde a '{tgt_label}'? (# o Enter): ").strip()
                    if not sel:
                        continue
                    try:
                        k = int(sel)
                        if 1 <= k <= len(cols):
                            src = cols[k-1]
                            real_tgt = _target_alias.get(tgt, tgt)
                            if src != real_tgt:
                                if src in df.columns:
                                    df = df.rename(columns={src: real_tgt})
                                else:
                                    for c in list(df.columns):
                                        if _norm_head(c) == _norm_head(src):
                                            df = df.rename(columns={c: real_tgt})
                                            break
                            present.add(real_tgt)
                    except Exception:
                        pass


        # 6) Persistir sinónimos aprendidos (solo si renombramos algo)
        # Nota: para simplificar, guardamos únicamente cuando exista CONFIG y schema
        try:
            to_dump = CONFIG if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else None
            if to_dump is not None:
                # reconstruir fields_meta desde CONFIG (por si cambió)
                schema_now = to_dump.setdefault("schema", {})
                fields_now = schema_now.setdefault("fields", {})
                # agregar cualquier nombre original que haya quedado como columna y sea sinónimo útil
                # (no hacemos here mapeo inverso avanzado para mantenerlo estable)
                # Guardado sencillo: no tocamos nada si no hay cambios explícitos
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(to_dump, f, ensure_ascii=False, indent=2)
                print("[WIZARD] Validación completada. Config guardada (sin cambios de sinónimos).")
                df = dedupe_columns(df)
                
                # === WIZARD: HELPERS DE VALIDACIÓN (inicio) ================================
                def _muestras_columna(serie, n=5):
                    try:
                        vals = [str(v) for v in serie.dropna().astype(str).head(n).tolist()]
                        if not vals:
                            vals = ["(sin datos visibles)"]
                        return vals
                    except Exception:
                        return ["(error al leer muestras)"]

                def _es_numero(x):
                    try:
                        float(str(x).replace(",", "."))
                        return True
                    except Exception:
                        return False

                def _en_bbox_sv(lat, lon):
                    try:
                        bbox = (CONFIG or {}).get("geografia", {}).get("sv_bbox", None)
                        if not (isinstance(bbox, dict) and all(k in bbox for k in ("lat_min","lat_max","lon_min","lon_max"))):
                            bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}
                        lat = float(lat); lon = float(lon)
                        if abs(lat) < 1e-9 and abs(lon) < 1e-9:
                            return False
                        return (bbox["lat_min"] <= lat <= bbox["lat_max"]) and (bbox["lon_min"] <= lon <= bbox["lon_max"])
                    except Exception:
                        return False

                def _es_columna_valida_para(canonico: str, serie) -> tuple[bool, str]:
                    """
                    Reglas mínimas por tipo canónico. Devuelve (ok, motivo_si_falla).
                    """
                    name = (canonico or "").strip().lower()
                    smps = _muestras_columna(serie, n=5)

                    if name in {"lat", "long"}:
                        # pedimos 5/5 numéricos; si ambos existen, validamos bbox con pares lat/long si están en el df
                        nums = sum(1 for v in smps if _es_numero(v))
                        if nums < max(1, len(smps)):  # al menos todo lo que se ve debe ser numérico
                            return False, f"La columna para '{canonico}' debería ser numérica; muestras: {', '.join(smps)}"
                        return True, ""

                    if name == "hora":
                        pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
                        ok = sum(1 for v in smps if pat.match(str(v).strip()[:8]) is not None)
                        if ok < max(1, len(smps)):
                            return False, f"Se espera formato HH:MM:SS; muestras: {', '.join(smps)}"
                        return True, ""

                    if name == "fecha":
                        conv = pd.to_datetime(pd.Series(smps), errors="coerce", dayfirst=True)
                        if conv.isna().any():
                            return False, f"Algunas muestras no parecen fechas; muestras: {', '.join(smps)}"
                        return True, ""

                    if name in {"tel", "contacto", "tel_contacto"}:
                        # números, +, espacios y guiones tolerados, pero que haya dígitos suficientes
                        ok = sum(1 for v in smps if re.search(r"\d{7,}", v) is not None)
                        if ok < max(1, len(smps)):
                            return False, f"Se esperan números telefónicos; muestras: {', '.join(smps)}"
                        return True, ""

                    if name in {"azimut", "lac", "celda"}:
                        nums = sum(1 for v in smps if _es_numero(v))
                        if nums < max(1, len(smps)):
                            return False, f"Se esperan valores numéricos; muestras: {', '.join(smps)}"
                        return True, ""

                    # Por defecto, no bloqueamos
                    return True, ""

                def _smoke_schema_postmap(df):
                    """
                    Chequeo express después de mapear:
                    - Revisa esenciales definidos en config.entradas.columnas_esenciales.
                    - Valida lat/long si están presentes (numéricos y no (0,0) en bbox).
                    """
                    esenciales = (CONFIG or {}).get("entradas", {}).get("columnas_esenciales", []) or []
                    faltan = [c for c in esenciales if c not in df.columns]
                    if faltan:
                        return False, f"Faltan columnas esenciales tras el mapeo: {', '.join(faltan)}"

                    if "lat" in df.columns and "long" in df.columns:
                        import numpy as np
                        try:
                            lt = pd.to_numeric(df["lat"], errors="coerce")
                            lg = pd.to_numeric(df["long"], errors="coerce")
                            # al menos una fila válida
                            mask_valid = (~lt.isna()) & (~lg.isna()) & (lt != 0) & (lg != 0)
                            if not mask_valid.any():
                                return False, "No quedaron coordenadas válidas (lat/long) tras el mapeo."
                        except Exception:
                            return False, "Coordenadas inválidas tras el mapeo."
                    return True, ""
                
                # === WIZARD: HELPERS DE VALIDACIÓN (fin) ===================================

                # WIZARD UBICACIÓN POR CAMPO + VALIDACIÓN DURA (lat, long, antena)
                try:
                    def _ask_map_col(_df, colname: str):
                        # si ya existe, no preguntar
                        if colname in _df.columns:
                            return _df
                        print(f"\n[WIZARD] Falta columna esencial de ubicación: '{colname}'. Elegí la columna correspondiente (número). Enter=omitir.")
                        cols_list = list(_df.columns)
                        for i, c in enumerate(cols_list, 1):
                            print(f"  [{i}] {c}")
                        sel = input(f"→ ¿Cuál columna corresponde a '{colname}'? (# o Enter): ").strip()
                        if not sel:
                            return _df
                        try:
                            k = int(sel)
                            if 1 <= k <= len(cols_list):
                                src = cols_list[k-1]
                                # === WIZARD: MAPEO ROBUSTO CON PREVIEW + CHECKS (inicio) ===================
                                if src != colname and src in _df.columns:
                                    # 1) Vista previa de muestras y validación por tipo
                                    smps = _muestras_columna(_df[src], n=5)
                                    print(f"\n[WIZARD] Previsualización de '{src}' para mapear a '{colname}':")
                                    for i, v in enumerate(smps, 1):
                                        print(f"   {i}. {v}")
                                    ok_tipo, motivo = _es_columna_valida_para(colname, _df[src])
                                    if not ok_tipo:
                                        print(f"[WIZARD] Esta columna no parece ser '{colname}': {motivo}")
                                        print("Volvé a elegir otra columna para este canónico.")
                                        return None  # aborta esta selección, se vuelve al menú

                                    # 2) Doble confirmación anti-error de dedo
                                    resp = input(f"[CONFIRMAR] ¿Seguro que '{src}' → '{colname}'? (S/N): ").strip().lower()
                                    if resp not in ("s", "si", "sí"):
                                        print("Cancelado. Elegí otra columna.")
                                        return None

                                    # 3) Conflictos con synonyms_user (si ya apuntaba a otro canónico)
                                    user_syn = (CONFIG or {}).get("synonyms_user", {}) or {}
                                    if src in user_syn and str(user_syn[src]).strip().lower() != str(colname).strip().lower():
                                        print(f"[WIZARD] Conflicto: '{src}' ya está registrado como sinónimo de '{user_syn[src]}'.")
                                        resp2 = input("¿Deseás SOBREESCRIBIR ese registro? (S/N): ").strip().lower()
                                        if resp2 not in ("s", "si", "sí"):
                                            print("No se aplicó el mapeo por conflicto. Volvé a elegir.")
                                            return None

                                    # 4) Renombrar (aplicar) y smoke test
                                    _df_backup = _df.copy()
                                    _df = _df.rename(columns={src: colname})

                                    ok_schema, motivo_schema = _smoke_schema_postmap(_df)
                                    if not ok_schema:
                                        print(f"[WIZARD] Se revirtió el mapeo por inconsistencia: {motivo_schema}")
                                        _df = _df_backup  # rollback
                                        return None

                                    # 5) Persistir sinónimo y reconstruir mapa efectivo (solo si todo fue ok)
                                    try:
                                        CONFIG = cfg_add_user_synonym(CONFIG, colname, src)     # guarda en config.json
                                        RENAME_MAP = cfg_build_rename_map(CONFIG)                # vuelve a construir mapa en memoria
                                    except Exception as e:
                                        log(f"[WARN][synonyms] No se pudo persistir el sinónimo: {e}")

                                    log(f"WIZARD: la columna '{src}' fue mapeada a '{colname}'.")
                                # === WIZARD: MAPEO ROBUSTO — FIN ===========================================
                                validate_schema_or_abort(_df)

                                # === VALIDACIÓN DE SCHEMA (aborto elegante) — INICIO =======================
                                def _coalesce_cols(df, *nombres):
                                    for n in nombres:
                                        if n in df.columns:
                                            return n
                                    return None

                                def _fmt_lista(xs):
                                    return ", ".join(xs) if xs else "(ninguna)"

                                def _valida_formato_hora(serie):
                                    pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
                                    sample = serie.astype(str).str.strip().str[:8].head(5)
                                    ok = sample.apply(lambda v: pat.match(v) is not None).all()
                                    return ok, sample.tolist()

                                def _valida_fecha_parsible(serie):
                                    try:
                                        s = pd.to_datetime(serie, errors="coerce", dayfirst=True)
                                        return s.notna().any(), [str(v) for v in serie.head(5).tolist()]
                                    except Exception:
                                        return False, [str(v) for v in serie.head(5).tolist()]

                                def _valida_latlon(df):
                                    bbox = (CONFIG or {}).get("geografia", {}).get("sv_bbox", None)
                                    if not (isinstance(bbox, dict) and all(k in bbox for k in ("lat_min","lat_max","lon_min","lon_max"))):
                                        bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}
                                    try:
                                        lt = pd.to_numeric(df["lat"], errors="coerce")
                                        lg = pd.to_numeric(df[_coalesce_cols(df, "long", "lon")], errors="coerce")
                                        mask = (~lt.isna()) & (~lg.isna()) & (lt != 0) & (lg != 0) \
                                            & (lt.between(bbox["lat_min"], bbox["lat_max"])) \
                                            & (lg.between(bbox["lon_min"], bbox["lon_max"]))
                                        return bool(mask.any())
                                    except Exception:
                                        return False

                                def validate_schema_or_abort(df):
                                    esenciales_cfg = (CONFIG or {}).get("entradas", {}).get("columnas_esenciales", []) or []
                                    esenciales = set(esenciales_cfg)
                                    if "long" in esenciales and "lon" not in esenciales:
                                        esenciales.add("lon")

                                    headers = list(df.columns)
                                    faltan = [c for c in esenciales if c not in headers]
                                    if "long" in faltan and "lon" in headers:
                                        faltan.remove("long")
                                    if "lon" in faltan and "long" in headers:
                                        faltan.remove("lon")

                                    alts = (CONFIG or {}).get("schema", {}).get("location_alternatives", []) or []
                                    def _alt_ok(alt_group):
                                        cols_needed = []
                                        for c in alt_group:
                                            if c == "lon":
                                                cols_needed.append(_coalesce_cols(df, "long", "lon"))
                                            else:
                                                cols_needed.append(c if c in df.columns else None)
                                        return all(col is not None for col in cols_needed)
                                    hay_alt_loc = any(_alt_ok(g) for g in alts) if alts else True

                                    problemas = []
                                    if faltan:
                                        problemas.append(f"- Faltan columnas esenciales: {_fmt_lista(faltan)}")
                                    if not hay_alt_loc:
                                        problemas.append("- No se cumple ninguna alternativa de localización (p. ej., (lat+long) o (antena)).")

                                    # hora
                                    if _coalesce_cols(df, "hora"):
                                        ok_hora, smp_h = _valida_formato_hora(df["hora"].astype(str))
                                        if not ok_hora:
                                            problemas.append(f"- 'hora' debería verse como HH:MM:SS; muestras: {_fmt_lista(smp_h)}")
                                    # fecha
                                    if _coalesce_cols(df, "fecha"):
                                        ok_fecha, smp_f = _valida_fecha_parsible(df["fecha"])
                                        if not ok_fecha:
                                            problemas.append(f"- 'fecha' no es parseable en algunas filas; muestras: {_fmt_lista(smp_f)}")
                                    # lat/long
                                    if _coalesce_cols(df, "lat") and _coalesce_cols(df, "long", "lon"):
                                        if not _valida_latlon(df):
                                            problemas.append("- 'lat/long' no tienen registros válidos (no 0,0; dentro de SV).")

                                    if problemas:
                                        guia = []
                                        guia.append("\n[SCHEMA] No se puede continuar. Ajustá encabezados o agregá sinónimos:\n")
                                        guia.extend(p + "\n" for p in problemas)
                                        guia.append("\nSugerencias:\n")
                                        guia.append("• Revisá 'entradas.columnas_esenciales' en config.json.\n")
                                        guia.append("• Usá el wizard para mapear encabezados raros (se persisten en synonyms_user).\n")
                                        guia.append("• Para 'long' también se acepta 'lon'.\n")
                                        msg = "".join(guia)
                                        try:
                                            log(f"[FATAL][schema] {msg}")
                                        except Exception:
                                            pass
                                        print(msg)
                                        raise SystemExit(2)
                                    else:
                                        try:
                                            log("[schema] Validación OK: esenciales presentes y tipos mínimos razonables.")
                                        except Exception:
                                            pass
                                        return True
                                # === VALIDACIÓN DE SCHEMA — FIN ============================================

                                    import platform, sys, datetime, time
                                    try:
                                        tzname = time.tzname[0]
                                    except Exception:
                                        tzname = "UTC?"
                                    return {
                                        "so": f"{platform.system()} {platform.release()}",
                                        "python": sys.version.split()[0],
                                        "tz": tzname,
                                        "fecha_hora": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "tz_analysis": (CONFIG or {}).get("version", "¿sin_version?"),
                                        "version_config": (CONFIG or {}).get("version_config", "¿sin_version?")
                                    }
                                
                                # === METADATOS TÉCNICOS (controlado por config) — INICIO =====================
                                def _post_inyectar_metadatos(informe_html_path: str):
                                    """
                                    Si html.metadatos_tecnicos.enabled == true, inserta un bloque mínimo o ampliado.
                                    Si está en false (por defecto), NO toca el HTML.
                                    """
                                    try:
                                        if not isinstance(informe_html_path, str) or not os.path.exists(informe_html_path):
                                            return

                                        meta_cfg = (CONFIG or {}).get("html", {}).get("metadatos_tecnicos", {}) or {}
                                        if not bool(meta_cfg.get("enabled", False)):
                                            return  # HTML limpio

                                        modo = (meta_cfg.get("modo") or "minimo").lower()
                                        mostrar_ver = bool(meta_cfg.get("mostrar_versiones", False))

                                        # Datos disponibles
                                        import platform, sys, datetime, time
                                        try:
                                            tzname = time.tzname[0]
                                        except Exception:
                                            tzname = "UTC?"

                                        # Bloques
                                        partes = []
                                        bloque = '<div class="metainfo" style="margin:8px 0 12px 0;">' + "".join(partes) + '</div>'

                                        # Insertar tras <body> si no hay sección “meta”
                                        with open(informe_html_path, "r", encoding="utf-8") as fr:
                                            html = fr.read()

                                        i = html.lower().find("<section")
                                        inyectado = False
                                        if i != -1 and "meta" in html[i:i+200].lower():
                                            j = html.find(">", i)
                                            if j != -1:
                                                html = html[:j+1] + bloque + html[j+1:]
                                                inyectado = True

                                        if not inyectado:
                                            b = html.lower().find("<body")
                                            if b != -1:
                                                bj = html.find(">", b)
                                                if bj != -1:
                                                    html = html[:bj+1] + bloque + html[bj+1:]

                                        with open(informe_html_path, "w", encoding="utf-8") as fw:
                                            fw.write(html)

                                        try: log("[meta] Metadatos técnicos inyectados (según config).")
                                        except Exception: pass

                                    except Exception as _e:
                                        try: log(f"[WARN][meta] No se pudo inyectar metadatos técnicos: {_e}")
                                        except Exception: pass
                                # === METADATOS TÉCNICOS — FIN ===============================================

                                # === COPIAR LOGO A CARPETA DE SALIDA (INICIO) ================================
                                def _copiar_logo_a_salida(logo_path: str, dest_dir: str, dest_name: str = "logo_tz.png"):
                                    """
                                    Copia el logo a la carpeta de salida con nombre 'logo_tz.png'.
                                    Si no existe o falla, no rompe nada.
                                    """
                                    try:
                                        if not logo_path or not dest_dir:
                                            return
                                        # Aceptamos rutas con / o con \\ (Windows)
                                        if not os.path.exists(logo_path):
                                            return
                                        os.makedirs(dest_dir, exist_ok=True)
                                        shutil.copyfile(logo_path, os.path.join(dest_dir, dest_name))
                                    except Exception:
                                        pass
                                # === COPIAR LOGO A CARPETA DE SALIDA (FIN) ===================================
                                
                                    # === RENOMBRADOR DE HEADERS (opcional, si no tenés uno) ====================
                                    def aplicar_rename_map(df, rename_map: dict) -> pd.DataFrame:
                                        """
                                        Intenta mapear nombres crudos del DataFrame a canónicos usando RENAME_MAP.
                                        - Compara por clave normalizada (minúsculas, sin tildes, sin dobles espacios).
                                        - Si dos canónicos reclaman el mismo header, prioriza el primero encontrado.
                                        """
                                        if df is None or df.empty or not rename_map:
                                            return df

                                        # Construir índice invertido: raw_norm -> canonico
                                        inv = {}
                                        for canonico, sinonimos in rename_map.items():
                                            for raw_norm in (sinonimos or []):
                                                if raw_norm not in inv:
                                                    inv[raw_norm] = canonico

                                        # Generar renames
                                        ren = {}
                                        for c in list(df.columns):
                                            raw_norm = _normalize_key_for_synonyms(c)
                                            if raw_norm in inv:
                                                ren[c] = inv[raw_norm]

                                        if ren:
                                            df = df.rename(columns=ren)
                                        return df
                                    # ==========================================================================

                                    # (y en tu flujo, luego de leer el DataFrame):
                                    # df = aplicar_rename_map(df, RENAME_MAP)

                        except Exception:
                            pass
                        return _df

                    # Preguntar individualmente por cada campo de ubicación
                    for need in ("lat", "long", "antena"):
                        df = _ask_map_col(df, need)

                    # Quitar duplicadas si quedaron tras renombrar
                    df = dedupe_columns(df)

                    # Validación dura: sin lat/lon → en QC no abortamos, intentamos coalesce y seguimos
                    faltan_ub = [x for x in ("lat", "lon") if x not in df.columns]  # OJO: usamos 'lon' como canónica
                    if faltan_ub:
                        if MANUAL_QC_MAPPING:
                            print("\n[WIZARD] QC activo: faltan columnas de ubicación -> " + ", ".join(faltan_ub))

                            # Intento de coalesce automático (hoja PROCESADA y variantes)
                            if "lat" not in df.columns and "latitud_inicial_objetivo" in df.columns:
                                df["lat"] = df["latitud_inicial_objetivo"]
                            # Aceptamos 'long' o 'longitud_inicial_objetivo' como fuente de 'lon'
                            if "lon" not in df.columns:
                                if "longitud_inicial_objetivo" in df.columns:
                                    df["lon"] = df["longitud_inicial_objetivo"]
                                elif "long" in df.columns:
                                    df["lon"] = df["long"]

                            # Si aún faltan, no abortamos: ponemos placeholder para que el wizard QC lo resuelva
                            for c in ("lat", "lon"):
                                if c not in df.columns:
                                    df[c] = None
                            print("[WIZARD] Continuamos; el mapeo manual definirá 'lat'/'lon'.")
                        else:
                            print("\n[ERROR] No se puede continuar: faltan columnas esenciales de ubicación -> " + ", ".join(faltan_ub))
                            print("Revise los encabezados de la hoja o use el wizard para mapearlos correctamente.")
                            sys.exit(2)

                    # ANTENA FALLBACK — autogenerar nombres si hay lat/long pero falta 'antena'
                    try:
                        if ("lat" in df.columns) and ("long" in df.columns) and ("antena" not in df.columns):
                            def _fmt_coord(x):
                                try:
                                    return f"{float(x):.6f}"
                                except Exception:
                                    return ""

                            lat_key = df["lat"].map(_fmt_coord)
                            lon_key = df["long"].map(_fmt_coord)

                            # válidas: ambas coords presentes (no blanco)
                            mask = (lat_key != "") & (lon_key != "")

                            # pares (lat,long) en el orden de aparición
                            pairs = pd.Series(list(zip(lat_key, lon_key)), index=df.index)
                            uniq_pairs = pd.unique(pairs[mask])

                            # mapa estable: primer par visto = Antena 1, siguiente = Antena 2, etc.
                            mapdict = {p: f"Antena {i}" for i, p in enumerate(uniq_pairs, start=1)}
                            log(f"Antena fallback: se crearon {len(mapdict)} grupos por par (lat,long).")

                            df["antena"] = np.where(
                                mask,
                                pairs.map(mapdict),
                                "Antena —"
                            )

                            # por si quedó alguna duplicación posterior
                            df = dedupe_columns(df)

                    except Exception:
                        pass


                    # Nota: si no hay 'antena' pero sí lat/long, seguimos (Step 3 creará nombres 'Antena N').
                except Exception:
                    pass

        except Exception:
            print("[WIZARD] Aviso: no se pudo escribir config.json; se continúa sin persistir.")

    except Exception:
        pass


    # NORMALIZADOR-1: aplicar correcciones de codificación y abreviaturas en columnas de texto
    try:
        _reglas_norm = None
        if 'CONFIG' in globals() and isinstance(CONFIG, dict):
            _reglas_norm = (CONFIG.get("normalizador", {}) or {}).get("reemplazos", None)
    except Exception:
        _reglas_norm = None

    df = normalizar_columnas_texto(df, reglas=_reglas_norm)

    # Validación
    columnas_esenciales = ["antena", "lat", "long"]
    # --- QC: coalesce de fecha/hora y limpieza de duplicados antes de validar ---
    # 1) Normalizar 'fecha' tomando inicio si existe
    if "fecha" not in df.columns:
        if "fecha_inicial" in df.columns:
            df["fecha"] = df["fecha_inicial"]
        elif "fecha_final" in df.columns:
            df["fecha"] = df["fecha_final"]

    # 2) Normalizar 'hora' tomando inicio si existe
    if "hora" not in df.columns:
        if "hora_inicial" in df.columns:
            df["hora"] = df["hora_inicial"]
        elif "hora_final" in df.columns:
            df["hora"] = df["hora_final"]

    # 3) Asegurar canónica 'lon' si vino como 'long' o similares
    if "lon" not in df.columns:
        if "longitud_inicial_objetivo" in df.columns:
            df["lon"] = df["longitud_inicial_objetivo"]
        elif "long" in df.columns:
            df["lon"] = df["long"]

    # 4) Eliminar columnas duplicadas por nombre (pandas permite duplicados)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # --- PROCESADA: completar canónicos mínimos antes de validar ---
    # tel
    if "tel" not in df.columns:
        for c in ("msisdn_origen","msisdn","telefono","tel"):
            if c in df.columns:
                df["tel"] = df[c]
                print("[QC] tel <-", c)
                break

    # interaccion (solo si NO estamos en mapeo manual)
    if not MANUAL_QC_MAPPING and "interaccion" not in df.columns:
        for c in ("tipo","tipo2","contacto","usuario"):
            if c in df.columns:
                df["interaccion"] = df[c]
                print("[QC] interaccion <-", c)
                break

    # antena (solo si NO estamos en mapeo manual)
    if not MANUAL_QC_MAPPING and "antena" not in df.columns:
        for c in ("siteid","cod_celda_inicial","celda"):
            if c in df.columns:
                df["antena"] = df[c]
                print("[QC] antena <-", c)
                break


    # --- QC: verificación rápida y tipado numérico ---
    print("[QC] mapeo:", {
        "tel": "tel" in df.columns,
        "interaccion": "interaccion" in df.columns,
        "antena": "antena" in df.columns
    })
    if "tel" in df.columns and "interaccion" in df.columns and "antena" in df.columns:
        print("[QC] no-nulos:", {
            "tel": int(df["tel"].notna().sum()),
            "interaccion": int(df["interaccion"].notna().sum()),
            "antena": int(df["antena"].notna().sum())
        })

    # Asegurar que lat/lon/azimut sean numéricos (evita KPI=0 por NaN)
    for c in ("lat", "lon", "azimut"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # --- WIZARD QC MANUAL ---
    if MANUAL_QC_MAPPING:
        print("\n[QC] Iniciando wizard QC (mapeo manual).")
        esenciales_qc = ["fecha", "hora", "tel", "imei", "interaccion", "contacto", "lat", "long", "azimut", "antena"]
        no_esenciales_qc = ["celda", "direccion", "imsi", "duracion"]
        
        # ⚡ LÍNEA CRÍTICA: Segunda componente del sistema dual
        # Esta línea preserva las columnas DESPUÉS de la normalización inicial
        # pero ANTES del wizard. Es parte del sistema dual de columnas.
        # Ver docs/SISTEMA_DUAL_COLUMNAS.md y docs/WIZARD_QC_PELIGRO_EXTREMO.md
        df._orig_cols = list(df.columns)
        
        # 🚨 FUNCIÓN DE RIESGO EXTREMO - Ver warning arriba en línea 353
        df, _mapeo = _wizard_qc_mapeo(df, esenciales=esenciales_qc, no_esenciales=no_esenciales_qc)
        # --- Compatibilidad lon/long para KPIs/HTML ---
        if "lon" in df.columns and "long" not in df.columns:
            df["long"] = df["lon"]
        elif "long" in df.columns and "lon" not in df.columns:
            df["lon"] = df["long"]

    # --- Normalización estricta de fecha y hora (solo formato, sin cambiar mapeo) ---
    try:
        # 1) Parsear FECHA a datetime y dejarla como dd/mm/YYYY (solo fecha)
        _f_dt = None
        if "fecha" in df.columns:
            _f_dt = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
            df["fecha"] = _f_dt.dt.strftime("%d/%m/%Y")  # siempre string solo fecha

        # 2) Construir HORA robusta (HH:MM:SS)
        if "hora" in df.columns:
            # intentar parsear 'hora' como datetime (muchas vienen 'fecha+hora' camufladas)
            _h_dt = pd.to_datetime(df["hora"], errors="coerce", dayfirst=True)
            _h_out = pd.Series("", index=df.index, dtype=object)

            # 2a) Para las que sí parsearon como datetime: tomar solo la hora
            mask_h_ok = _h_dt.notna()
            if mask_h_ok.any():
                _h_out.loc[mask_h_ok] = _h_dt.loc[mask_h_ok].dt.strftime("%H:%M:%S")

            # 2b) Para las que NO parsearon, intentar con prefijo fecha dummy (texto tipo "2:2" o "02:02")
            mask_h_bad = ~mask_h_ok & df["hora"].astype(str).str.strip().ne("")
            if mask_h_bad.any():
                _h_try2 = pd.to_datetime(
                    "1970-01-01 " + df.loc[mask_h_bad, "hora"].astype(str).str.strip(),
                    errors="coerce", dayfirst=True
                )
                mask_h2_ok = _h_try2.notna()
                if mask_h2_ok.any():
                    _h_out.loc[mask_h_bad[mask_h_bad].index[mask_h2_ok]] = _h_try2.loc[mask_h2_ok].dt.strftime("%H:%M:%S")

            # 2c) Para las que siguen vacías: si 'fecha' traía hora embebida, derivarla desde 'fecha'
            if _f_dt is not None:
                mask_empty = _h_out.eq("")
                if mask_empty.any():
                    _h_from_f = _f_dt.dt.strftime("%H:%M:%S")
                    _h_out.loc[mask_empty & _f_dt.notna()] = _h_from_f.loc[mask_empty & _f_dt.notna()]

            # 2d) Si aún quedó vacío, dejar "Sin Inf."
            _h_out = _h_out.replace("", "Sin Inf.")
            df["hora"] = _h_out

        else:
            # No existe columna 'hora': si 'fecha' tenía hora embebida, crearla; si no, "Sin Inf."
            if _f_dt is not None:
                df["hora"] = _f_dt.dt.strftime("%H:%M:%S").where(_f_dt.notna(), "Sin Inf.")
            else:
                df["hora"] = "Sin Inf."

    except Exception as __e:
        print(f"[WARN] Normalización fecha/hora: {__e}")



        # Asegurar numéricos
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce") if "lat" in df.columns else None
        if "long" in df.columns:
            df["long"] = pd.to_numeric(df["long"], errors="coerce")

        # Post–mapeo: si faltan alias/usuario/abonado, ofrecer cargarlos como valor único (solo en QC manual)


    # === Overrides Top N (Modos 1 y 2) ===
    if opcion in ("1", "2") and not MANUAL_QC_MAPPING:
        try:
            ovr = _solicitar_overrides_topn(CONFIG)
            if ovr:
                globals()["OVERRIDE_TOPS"] = ovr
                print(f"[INFO] Top N override aplicado: {ovr}")
        except Exception:
            pass

    df, errores = validar_datos(df, columnas_esenciales)

    # Salidas
    nombre_base = os.path.splitext(os.path.basename(archivo_entrada))[0]

    # --- Nombre sugerido para salida (Excel): TEL + ALIAS + RANGO ISO + EXCEL + TIMESTAMP ---
    def _sanear_nombre_archivo_local(s: str) -> str:
        """
        Wrapper para compatibilidad - usar sanear_nombre_archivo de tz_core.utils
        
        CRÍTICO: Preserva fallback dinámico (nombre_base) para mantener
        comportamiento idéntico en generación de nombres Excel.
        
        CONTEXTO: Esta función se usa en:
        - Línea 7899: generación automática de nombres Excel  
        - Línea 8098: validación entrada usuario para nombres Excel
        
        El fallback nombre_base es crucial para nombres consistentes.
        """
        return sanear_nombre_archivo(s, nombre_base)

    def _first_nonempty(colname):
        if not colname or colname not in df.columns:
            return None
        serie = df[colname].dropna().astype(str).str.strip()
        serie = serie[serie != ""]
        return serie.iloc[0] if not serie.empty else None

    # Tel / Alias
    tel_col   = next((c for c in ["tel","telefono","numero","msisdn","a_number","origen","from","callingnumber","num"] if c in df.columns), None)
    alias_col = next((c for c in ["alias","alias_usuario","apodo"] if c in df.columns), None)
    tel_val   = _first_nonempty(tel_col)
    alias_val = _first_nonempty(alias_col)

    tel_part   = tel_val if tel_val else "multi" if df.get("tel", pd.Series()).nunique(dropna=True) > 1 else "sin_tel"
    alias_part = alias_val if alias_val else "sin_alias"

    # Rango de fechas (ISO yyyyMMdd)
    from datetime import datetime
    if "fecha" in df.columns:
        fechas_parsed = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
        fechas_valid = fechas_parsed.dropna()
        if not fechas_valid.empty:
            fmin = fechas_valid.min().strftime("%d-%m-%Y")
            fmax = fechas_valid.max().strftime("%d-%m-%Y")
            rango = fmin if fmin == fmax else f"{fmin}__{fmax}"
        else:
            rango = datetime.now().strftime("%d-%m-%Y")
    else:
        rango = datetime.now().strftime("%d-%m-%Y")


    # Timestamp de generación
    # Etiqueta de filtro para el nombre de salida (solo Modo 2)
    suf = ""
    if opcion == "2":
        try:
            t = filtros.get("tipo") if 'filtros' in locals() else None
            if t == "dia":
                d = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce")
                if pd.notna(d):
                    suf = f"__dia_{d.strftime('%Y-%m-%d')}"
            elif t == "rango_dias":
                d1 = pd.to_datetime(filtros.get("desde"), dayfirst=True, errors="coerce")
                d2 = pd.to_datetime(filtros.get("hasta"), dayfirst=True, errors="coerce")
                if pd.notna(d1) and pd.notna(d2):
                    suf = f"__rd_{d1.strftime('%Y-%m-%d')}__{d2.strftime('%Y-%m-%d')}"
            elif t == "rango_horas_dia":
                d = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce")
                h1 = (filtros.get("hora_ini") or "00:00")[:5].replace(":", "-")
                h2 = (filtros.get("hora_fin") or "00:00")[:5].replace(":", "-")
                if pd.notna(d) and h1 and h2:
                    suf = f"__hrdia_{d.strftime('%Y-%m-%d')}__{h1}__{h2}"
            elif t == "rango_horas":
                h1 = (filtros.get("hora_ini") or "00:00")[:5].replace(":", "-")
                h2 = (filtros.get("hora_fin") or "00:00")[:5].replace(":", "-")
                if h1 and h2:
                    suf = f"__hr_{h1}__{h2}"
        except Exception:
            pass

    stamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
    base_auto = _sanear_nombre_archivo_local(f"{tel_part}_{alias_part}_{rango}{suf}_EXCEL_{stamp}")

    # Evitar que el usuario ponga un color hex por error como nombre
    # [QC] Confirmar tipo de bitácora (afecta solo nombres de archivos y carpetas)
    print("\n[QC] Confirmar si esta bitácora es por número de Teléfono o IMEI para nombrar archivos")
    print("I = IMEI")
    print("T = Número telefónico")
    print("Enter = Que TZ Analyzer decida")
    tipo_bitacora = input("→ Opción (I/T/Enter): ").strip().upper() or ""

    # Definir modo según respuesta del usuario o detección automática
    modo_bitacora = "AUTO"
    if tipo_bitacora == "I":
        modo_bitacora = "IMEI"
    elif tipo_bitacora == "T":
        modo_bitacora = "TEL"
    else:
        # Detección automática basada en unicidad de columnas
        imeis_unicos = df["imei"].nunique() if "imei" in df.columns else 0
        tels_unicos = df["tel"].nunique() if "tel" in df.columns else 0
        if imeis_unicos == 1 and tels_unicos != 1:
            modo_bitacora = "IMEI"
        elif tels_unicos == 1 and imeis_unicos != 1:
            modo_bitacora = "TEL"
        else:
            modo_bitacora = "AUTO"

    print(f"[QC] Tipo de bitácora establecido: {modo_bitacora}")

    # [BASE-NAME v1] Sugerido según modo_bitacora (solo nombres; sin período ni "EXCEL")
    def _limpiar_alias(s):
        try:
            s = str(s).strip()
            if not s:
                return ""
            s = s.replace(" ", "_")
            return s[:12]
        except Exception:
            return ""

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # alias corto (si existe)
    alias_val = None
    if "alias" in df.columns:
        try:
            _a = [x for x in df["alias"].astype(str).str.strip().unique() if x]
            alias_val = _a[0] if _a else None
        except Exception:
            alias_val = None
    alias_short = _limpiar_alias(alias_val)

    # principal según elección
    primary = None
    prefix = "AUTO"

    if "modo_bitacora" in locals():
        if modo_bitacora == "IMEI":
            prefix = "IMEI"
            if "imei" in df.columns:
                try:
                    vals = [str(x).strip() for x in df["imei"].dropna().astype(str) if str(x).strip()]
                    vals = sorted(set(vals))
                    if vals:
                        primary = vals[0]
                except Exception:
                    pass
        elif modo_bitacora == "TEL":
            prefix = "TEL"
            if "tel" in df.columns:
                try:
                    vals = [str(x).strip() for x in df["tel"].dropna().astype(str) if str(x).strip()]
                    vals = sorted(set(vals))
                    if vals:
                        primary = vals[0]
                except Exception:
                    pass

    # construir base_auto final (este valor es el que verá el input)
    if primary:
        base_auto = f"{prefix}_{primary}{('_' + alias_short) if alias_short else ''}_{stamp}"
    else:
        base_auto = f"CASO{('_' + alias_short) if alias_short else ''}_{stamp}"

    # --- PREVISUALIZACIÓN (antes de nombrar) ---
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")

    kml_habilitado = not CONFIG.get("salida", {}).get("solo_kmz", False)

    def _pick_id(df, col):
        if col not in df.columns:
            return "DESCONOCIDO"
        serie = df[col].astype(str).str.strip()
        # Quitar vacíos, “0”, “None”, “null”, “—”
        serie = serie[~serie.isin(["", "0", "None", "none", "NULL", "null", "—", "--"])]
        if serie.empty:
            return "DESCONOCIDO"
        # Más frecuente (modo) como identificador estable
        try:
            return serie.mode().iat[0]
        except Exception:
            return serie.iloc[0]

    # Elegir identificador principal según tipo de bitácora
    # === principal_id con soporte multiN (IMEI/TEL) ===
    if modo_bitacora == "IMEI":
        col = "imei"
    else:
        col = "tel"

    try:
        if col in df.columns:
            serie = df[col].astype(str).str.strip()
            serie = serie[~serie.isin(["", "0", "None", "none", "NULL", "null", "—", "--"])]
            uniques = serie.unique()  # evitar pd.unique() para no depender de 'pd' local
            n = len(uniques)
            if n > 1:
                principal_id = f"multi{n}"
            elif n == 1:
                principal_id = uniques[0]
            else:
                principal_id = "DESCONOCIDO"
        else:
            principal_id = "DESCONOCIDO"
    except Exception:
        # Fallback seguro si algo raro pasa
        principal_id = _pick_id(df, col)

    # Alias (si no existe, usar 'SinAlias')
    alias_id = _pick_id(df, "alias")
    if alias_id == "DESCONOCIDO":
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")

        alias_id = (alias_val or "").strip()

        # timestamp local para el BASE (comparto formato con el resto)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")

    if alias_id:
        base_auto = f"{modo_bitacora}_{principal_id}_{alias_id}_{ts}"
    else:
        base_auto = f"{modo_bitacora}_{principal_id}_{ts}"

    # --- Submenú Filtro de tiempo (post-mapeo, antes de nombres) ---
    sel = locals().get('resp') or locals().get('opcion') or ""
    if str(sel) == "2":
        try:
            filtros = _solicitar_filtros_tiempo()
            df, _resumen_filtro = _aplicar_filtros_tiempo(df, filtros)
            if df.empty:
                print("No hay registros después de aplicar el filtro. Saliendo...")
                return
            print(f"[INFO] Filtro aplicado: {_resumen_filtro}")
        except Exception as __e:
            print(f"[WARN] No se pudo aplicar el filtro temporal: {__e}")

    # [QC] Alias / Usuario / Abonado (post-mapeo; opcional)

    # [QC] Preguntas de TOPs (antenas/contactos) — antes de la previsualización
    try:
        _raw_top_ant = input("→ Top de antenas (Enter=10; 0=sin límite): ").strip()
        top_antenas = 10 if _raw_top_ant == "" else max(0, int(_raw_top_ant))
    except Exception:
        top_antenas = 10

    try:
        _raw_top_cto = input("→ Top de contactos (Enter=10; 0=sin límite): ").strip()
        top_contactos = 10 if _raw_top_cto == "" else max(0, int(_raw_top_cto))
    except Exception:
        top_contactos = 10

    # Propagar a CONFIG si existe (para que HTML/KMZ usen estos valores)
    if "CONFIG" in globals() and isinstance(CONFIG, dict):
        CONFIG["top_antenas"] = top_antenas
        CONFIG["top_contactos"] = top_contactos

    # Además, propagar overrides a nivel global para que las secciones HTML los lean
    try:
        globals()["OVERRIDE_TOPS"] = {"antenas": int(top_antenas), "contactos": int(top_contactos)}
    except Exception:
        pass

    print("[QC] Carpeta sugerida por TZ Analyzer:")
    print(f"  📁 {base_auto}\n")

    print("[QC] Se generarán estos archivos:")
    print(f"  - {base_auto}_informe.html")
    print(f"  - {base_auto}_mapeo.kmz")
    print(f"  - {base_auto}_hashes.txt")
    print(f"  - {base_auto}_errores.txt\n")

    print("Si desea cambiar el nombre base, escríbalo ahora (solo base, sin extensión).")
    resp = input(f"Nombre base del KML (Enter = {base_auto}): ").strip()
    nombre_salida = (resp or base_auto)

    if re.fullmatch(r'#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?', resp or ''):
        print("Eso parece un color hex, no un nombre de archivo. Usaré el sugerido.")
        resp = ""

    nombre_salida = _sanear_nombre_archivo_local(resp) if resp else base_auto

    # --- Selección de carpeta al final (estilo i2) ---
    try:
        carpeta_base = seleccionar_carpeta()
    except Exception:
        carpeta_base = None
    if not carpeta_base:
        carpeta_base = os.getcwd()
    print(f"[QC] Carpeta destino: {carpeta_base}")


    # Subcarpeta del caso = nombre_salida (sin acortador)
    nombre_carpeta = nombre_salida
    carpeta_salida = os.path.join(carpeta_base, nombre_carpeta)
    os.makedirs(carpeta_salida, exist_ok=True)
    # --- FIN selección de carpeta ---

    # --- RUTAS FINALES KML/KMZ (ya existe carpeta_salida) ---
    if CONFIG.get("salida", {}).get("separar_kml_kmz", False):
        carpeta_kml = os.path.join(carpeta_salida, "kml")
        os.makedirs(carpeta_kml, exist_ok=True)
        archivo_kml = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kml")
        archivo_kmz = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kmz")
    else:
        archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
        archivo_kmz = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")
    # --- FIN rutas KML/KMZ ---

    # HTML opcional (solo si lo activás en config.json con html.generar_en_modo_manual = true)
    if bool(CONFIG.get("html", {}).get("generar_en_modo_manual", False)):
        try:
            # 🚨 DESHABILITADO: Framework HTML modular no implementado completamente
            # TODO: Implementar tz_core.html_generator cuando sea necesario
            # from tz_core.html_generator import HTMLReportGenerator
            # html_gen = HTMLReportGenerator()
            # html_gen._copiar_logo_a_salida(CONFIG.get("branding", {}).get("logo_path"), carpeta_salida)
            # informe_html = html_gen.generar_informe_html(
            #     df, archivo_kml, carpeta_salida, nombre_salida, hoja
            # )
            # print(f"Informe HTML generado en: {informe_html}")
            
            print("[INFO] Generación HTML modular no disponible. Usar generar_en_modo_manual=false en config.json")
            # --- Normalizar ubicación del KMZ (por si quedó fuera de BASE) ---
            try:
                kmz_esperado = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")
                kmz_fuera    = os.path.join(carpeta_base,  f"{nombre_salida}_mapeo.kmz")
                if os.path.isfile(kmz_fuera):
                    if os.path.isfile(kmz_esperado):
                        try:
                            os.remove(kmz_esperado)
                        except Exception:
                            pass
                    os.replace(kmz_fuera, kmz_esperado)
                    log(f"[DEBUG] KMZ reubicado a: {kmz_esperado}")
            except Exception as _e:
                print(f"[WARN] No se pudo reubicar KMZ: {_e}")
            # --- FIN normalización KMZ ---

        except Exception as e:
            print(f"[ERROR] No se pudo generar el HTML: {e}")
            informe_html = None
    else:
        # 🔧 FIX: Usar función original cuando modo manual está deshabilitado
        try:
            informe_html = generar_informe_html(df, archivo_kml, carpeta_salida, nombre_salida, hoja)
            print(f"Informe HTML generado (modo legacy): {informe_html}")
        except Exception as e:
            print(f"[ERROR] No se pudo generar el HTML (modo legacy): {e}")
            informe_html = None

    # Log mínimo para Modo 2
    if opcion == "2":
        try:
            log_min = os.path.join(carpeta_salida, "log_minimo.txt")

            # Conteos básicos
            total_post_filtro = len(df)

            # Antenas válidas (con coordenadas válidas)
            latn = pd.to_numeric(df.get("lat", pd.Series(dtype=float)), errors="coerce")
            lonn = pd.to_numeric(df.get("long", pd.Series(dtype=float)), errors="coerce")
            m_coord = (
                latn.notna() & lonn.notna() &
                ~((latn.fillna(0) == 0) & (lonn.fillna(0) == 0)) &
                latn.between(-90, 90) & lonn.between(-180, 180)
            )

            ant_unicas = 0
            if "antena" in df.columns:
                s_ant = df.loc[m_coord, "antena"].astype(str).str.strip()
                invalid = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
                s_ant = s_ant[~s_ant.str.lower().isin(invalid)]
                ant_unicas = int(s_ant.nunique())

            contactos_unicos = 0
            if "tel_contacto" in df.columns:
                s_ct = df["tel_contacto"].astype(str).str.strip()
                s_ct = s_ct.replace({"": None})
                contactos_unicos = int(s_ct.nunique(dropna=True))

            with open(log_min, "w", encoding="utf-8") as f:
                f.write(f"Filtro aplicado: {_resumen_filtro}\n")
                f.write(f"Registros tras filtro: {total_post_filtro}\n")
                f.write(f"Antenas únicas (válidas): {ant_unicas}\n")
                f.write(f"Contactos únicos: {contactos_unicos}\n")
        except Exception:
            # No detiene el flujo si hay algún problema con el log
            pass

    # PRE-KML: asegurar alias/usuario/abonado sin prompt (usar 'SinInf' si faltan)
    def _prep_meta_unicos(_df, campos):

        for etiqueta, col in campos:
            serie = _df[col] if col in _df.columns else None

            vacio = True
            if serie is not None:
                try:
                    vacio = bool(serie.isna().all() or (serie.astype(str).str.strip() == '').all())
                except Exception:
                    vacio = True

            if (col not in _df.columns) or vacio:
                _df[col] = ""  # dejar vacío (sin placeholder)
                log(f"[QC] {col} no presente/vacío; se deja vacío (no se imprime en salida).")

        return _df

    # Rellena solo si faltan; si ya existen no pregunta
    df = _prep_meta_unicos(df, [
        ("alias", "alias"),
        ("nombre_usuario", "nombre_usuario"),  # 🔧 FIX: volver a "nombre_usuario" que es como se guarda realmente
        ("abonado", "abonado"),
    ])


    archivo_kml, desc_coords = generar_kml(df, archivo_kml, flat=False)
    
    # === BLOQUE HTML/SECCIONES (repuesto) ===
    try:
        # 1) Parámetros para "Interacciones de los últimos días"
        try:
            _dias_cfg = 3
            if 'CONFIG' in globals() and isinstance(CONFIG, dict):
                _dias_cfg = int(CONFIG.get("html", {}).get("interacciones_ultimos_dias", 3))
        except Exception:
            _dias_cfg = 3

        try:
            _cols_cfg = CONFIG.get("columnas", {}) if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else {}
        except Exception:
            _cols_cfg = {}

        # 2) Construir sección de interacciones (se inyecta en el HTML)
        try:
            global HTML_SECCION_INTERACCIONES
            HTML_SECCION_INTERACCIONES = _construir_seccion_interacciones(
                df, dias=_dias_cfg, columnas_config=_cols_cfg
            )
            log(f"[DEBUG] Interacciones: {len(HTML_SECCION_INTERACCIONES)} chars")
        except Exception as e:
            log(f"[ERROR] Interacciones falló: {e}")
            HTML_SECCION_INTERACCIONES = ""

        # 2b) Construir sección "Todos los contactos"
        try:
            global HTML_SECCION_TODOS_CONTACTOS
            HTML_SECCION_TODOS_CONTACTOS = _construir_seccion_todos_contactos(
                df, columnas_config=_cols_cfg
            )
        except Exception:
            HTML_SECCION_TODOS_CONTACTOS = ""


        # 3) (Opcional) Sección Top N antenas para la portada del HTML
        try:
            global HTML_SECCION_ANTENAS

            # Leer Top N antenas (override -> config -> 3)
            try:
                if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict) and OVERRIDE_TOPS.get('antenas'):
                    _topN = int(OVERRIDE_TOPS.get('antenas'))
                elif 'CONFIG' in globals() and isinstance(CONFIG, dict):
                    _topN = int(CONFIG.get("html", {}).get("top_antenas_n", 3))
                else:
                    _topN = 3
            except Exception:
                _topN = 3


            # Buscar la función si existe (con o sin guion bajo)
            _func = globals().get("_construir_seccion_antenas") or globals().get("construir_seccion_antenas")
            if callable(_func):
                HTML_SECCION_ANTENAS = _func(df, top_n=_topN, columnas_config=_cols_cfg)
            else:
                # Si no existe la función, no pasa nada: el HTML ya arma su sección de antenas.
                HTML_SECCION_ANTENAS = ""
        except Exception:
            HTML_SECCION_ANTENAS = ""

            # Si no existe la función o algo falla, la sección queda vacía (no bloquea el HTML)
            # print(f"[DEBUG] Antenas HTML error: {e}")
            HTML_SECCION_ANTENAS = ""

        # 4) Generar el HTML
        print("[DEBUG] Llamando a generar_informe_html(...)")
        # � FIX: Usar función original (no existe html_generator modular funcional)
        try:
            informe_html = generar_informe_html(
                df, archivo_kml, carpeta_salida, nombre_salida, hoja,
                os.path.basename(archivo_entrada)
            )
            print(f"Informe HTML generado en: {informe_html}")
        except Exception as e:
            print(f"[ERROR] No se pudo generar el HTML: {e}")
            informe_html = None
        # --- Normalizar ubicación del KMZ (por si quedó fuera de BASE) ---
        try:
            kmz_esperado = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")
            kmz_fuera    = os.path.join(carpeta_base,  f"{nombre_salida}_mapeo.kmz")
            if os.path.isfile(kmz_fuera):
                if os.path.isfile(kmz_esperado):
                    try:
                        os.remove(kmz_esperado)
                    except Exception:
                        pass
                os.replace(kmz_fuera, kmz_esperado)
        except Exception as _e:
            print(f"[WARN] No se pudo reubicar KMZ: {_e}")
        # --- FIN normalización KMZ ---


        # === HASHES.txt (entrada/salidas/config/log) — INICIO =======================
        try:
            pares = []

            # 1) Entrada (usa la primera variable que exista)
            for _cand in ("ruta_archivo_entrada", "archivo_entrada"):
                _v = locals().get(_cand) or globals().get(_cand)
                if isinstance(_v, str) and os.path.exists(_v):
                    pares.append((os.path.abspath(_v), os.path.basename(_v)))
                    break

            # 2) HTML recién generado
            if isinstance(informe_html, str) and os.path.exists(informe_html):
                pares.append((os.path.abspath(informe_html), os.path.basename(informe_html)))

            # 3) KMZ (derivado del path base del KML)
            _kmz_added = False; _k_ref = None
            for _cand_k in ("archivo_salida_kml", "archivo_kml"):
                _k = locals().get(_cand_k) or globals().get(_cand_k)
                if _k:
                    _k_ref = _k
                    _kmz = os.path.splitext(_k)[0] + ".kmz"
                    if os.path.exists(_kmz):
                        pares.append((os.path.abspath(_kmz), os.path.basename(_kmz)))
                        _kmz_added = True
                    break


            # 5) Log actual (si existe)
            _log_file = globals().get("LOG_FILE")
            if _log_file and os.path.exists(_log_file):
                pares.append((os.path.abspath(_log_file), os.path.basename(_log_file)))

            # 6) Carpeta destino (prefiero la del HTML; si no, la del KML/KMZ; si no, cwd)
            _dest_dir = None
            if isinstance(informe_html, str) and informe_html:
                _dest_dir = os.path.dirname(informe_html)
            elif _kmz_added and _k_ref:
                _dest_dir = os.path.dirname(_k_ref)
            if not _dest_dir:
                _dest_dir = os.getcwd()

            _hashes_path = os.path.join(_dest_dir, f"{nombre_salida}_hashes.txt")
            escribe_hashes_txt(_hashes_path, pares)
            try: log(f"[hashes] Generado {os.path.basename(_hashes_path)}")
            except Exception: pass
        except Exception as e:
            try: log(f"[WARN][hashes] No se pudo generar HASHES.txt: {e}")
            except Exception: pass
        # === HASHES.txt — FIN ========================================================


        # 5) Mensajes finales (KML/KMZ/errores)
        print(f"KML generado en: {archivo_kml}")
        if bool(CONFIG.get("salida", {}).get("separar_kml_kmz", False)):
            kml_dir = os.path.dirname(archivo_kml)
            base_dir = os.path.dirname(kml_dir) if os.path.basename(kml_dir).lower() == "kml" else kml_dir
            kmz_dir = os.path.join(base_dir, "kmz")
            kmz_path = os.path.join(kmz_dir, os.path.splitext(os.path.basename(archivo_kml))[0] + ".kmz")
        else:
            kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"

        if os.path.exists(kmz_path):
            print(f"KMZ generado en: {kmz_path}")
        print(f"Filas descartadas por coordenadas inválidas: {desc_coords}")
        print(f"Reporte de errores generado en: {archivo_errores}")

    except Exception as e:
        print(f"[ERROR] Bloque HTML/KML falló: {e}")
def _solicitar_filtros_tiempo():
    """
    Devuelve un dict con claves:
      {"tipo": "dia"|"rango_dias"|"rango_horas_dia"|"rango_horas",
       "dia": "dd/mm/yyyy" | None,
       "desde": "dd/mm/yyyy" | None,
       "hasta": "dd/mm/yyyy" | None,
       "hora_ini": "HH:MM:SS" | None,
       "hora_fin": "HH:MM:SS" | None}
    Si el usuario pulsa Enter en todo, retorna None (sin filtros).
    """
    print("\nSeleccione el filtro de tiempo:")
    print("[1] Día específico")
    print("[2] Rango de días")
    print("[3] Rango de horas en un día específico")
    print("[4] Rango de horas (aplicado a todos los días)")
    resp = input("Opción (1/2/3/4, Enter=sin filtro): ").strip()
    if resp not in ("1","2","3","4"):
        return None
    if resp == "1":
        d = input("Ingrese el día (dd/mm/yyyy): ").strip()
        return {"tipo":"dia","dia":d, "desde":None,"hasta":None,"hora_ini":None,"hora_fin":None}
    if resp == "2":
        d1 = input("Desde (dd/mm/yyyy): ").strip()
        d2 = input("Hasta (dd/mm/yyyy): ").strip()
        return {"tipo":"rango_dias","dia":None,"desde":d1,"hasta":d2,"hora_ini":None,"hora_fin":None}
    if resp == "3":
        d = input("Día (dd/mm/yyyy): ").strip()
        h1 = input("Hora inicio (HH:MM, Enter=usar presets SV): ").strip()
        h2 = input("Hora fin (HH:MM, Enter=usar presets SV): ").strip()
        h1 = (h1 + ":00") if (h1 and len(h1)==5) else (h1 if h1 else None)
        h2 = (h2 + ":00") if (h2 and len(h2)==5) else (h2 if h2 else None)
        return {"tipo":"rango_horas_dia","dia":d,"desde":None,"hasta":None,"hora_ini":h1,"hora_fin":h2}
    if resp == "4":
        h1 = input("Hora inicio (HH:MM, Enter=usar presets SV): ").strip()
        h2 = input("Hora fin (HH:MM, Enter=usar presets SV): ").strip()
        h1 = (h1 + ":00") if (h1 and len(h1)==5) else (h1 if h1 else None)
        h2 = (h2 + ":00") if (h2 and len(h2)==5) else (h2 if h2 else None)
        return {"tipo":"rango_horas","dia":None,"desde":None,"hasta":None,"hora_ini":h1,"hora_fin":h2}

def _aplicar_filtros_tiempo(df, filtros):
    """
    Aplica los filtros al DataFrame según el dict de _solicitar_filtros_tiempo().
    Devuelve: (df_filtrado, resumen_texto).
    """
    if not filtros:
        return df, "Sin filtro de tiempo"

    tipo = filtros.get("tipo")
    resumen = ""

    # Normalizar fecha (f) y hora (h)
    f = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce") if "fecha" in df.columns else None
    h = pd.to_timedelta(df["hora"].astype(str), errors="coerce") if "hora" in df.columns else None

    # Máscara base
    mask = pd.Series([True]*len(df), index=df.index)

    if tipo == "dia" and f is not None:
        try:
            d = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce").normalize()
            mask &= (f.dt.normalize() == d)
            resumen = f"Día: {filtros.get('dia')}"
        except Exception:
            pass

    elif tipo == "rango_dias" and f is not None:
        d1 = pd.to_datetime(filtros.get("desde"), dayfirst=True, errors="coerce")
        d2 = pd.to_datetime(filtros.get("hasta"), dayfirst=True, errors="coerce")
        if pd.notna(d1): d1 = d1.normalize()
        if pd.notna(d2): d2 = d2.normalize()
        if pd.notna(d1): mask &= (f.dt.normalize() >= d1)
        if pd.notna(d2): mask &= (f.dt.normalize() <= d2)
        resumen = f"Rango de días: {filtros.get('desde')} → {filtros.get('hasta')}"

    elif tipo == "rango_horas_dia" and (f is not None) and (h is not None):
        # Día específico + rango de horas (maneja cruce de medianoche)
        d = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce")
        h1 = filtros.get("hora_ini")
        h2 = filtros.get("hora_fin")
        if pd.notna(d) and h1 and h2:
            try:
                d = d.normalize()
                t1 = pd.to_timedelta(h1)
                t2 = pd.to_timedelta(h2)
                mask &= (f.dt.normalize() == d)
                if t1 <= t2:
                    mask &= (h >= t1) & (h <= t2)
                else:
                    mask &= (h >= t1) | (h <= t2)
                resumen = f"Rango de horas en día {filtros.get('dia')}: {h1} → {h2}"
            except Exception:
                resumen = "Rango de horas en día (entrada inválida, sin filtrar)"

    elif tipo == "rango_horas" and h is not None:
        # Rango de horas aplicado a todos los días (maneja cruce de medianoche)
        h1 = filtros.get("hora_ini")
        h2 = filtros.get("hora_fin")
        if h1 and h2:
            try:
                t1 = pd.to_timedelta(h1)
                t2 = pd.to_timedelta(h2)
                if t1 <= t2:
                    mask &= (h >= t1) & (h <= t2)
                else:
                    mask &= (h >= t1) | (h <= t2)
                resumen = f"Rango de horas: {h1} → {h2}"
            except Exception:
                resumen = "Rango de horas (entrada inválida, sin filtrar)"
        else:
            resumen = "Rango de horas (usando presets SV)"

    df2 = df.loc[mask].copy()
    return df2, resumen

def _solicitar_overrides_topn(config):
    """Wrapper de compatibilidad - usa tz_core.ui_utils.solicitar_overrides_topn"""
    return solicitar_overrides_topn(config)

if __name__ == "__main__":
    bootstrap_config()

    # Logging simple y visible en consola para toda la app
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    try:
        main()
    except Exception as e:
        logging.error("Error no controlado: %s", e)
        traceback.print_exc()
        raise
