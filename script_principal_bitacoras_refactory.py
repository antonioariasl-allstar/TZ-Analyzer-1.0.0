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
import logging
import os
import re
import sys
import time
import traceback
import warnings
from datetime import datetime, time as _time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# === SECCIÓN: WIZARD DE MAPEO DE COLUMNAS (detección, mapeo manual, QC) ===
# Estos wrappers (_build_wizard_io, _prepare_manual_mapping, _run_manual_mapping,
# _persist_user_synonym) mantienen compatibilidad con el flujo original, pero
# delegan la lógica real a tz_core.mapping_wizard y tz_core.config_manager.
# No modificar comportamientos aquí sin coordinar con los módulos extraídos; si se
# refactoriza, moverlos a una capa de compatibilidad y deprecarlos de forma
# controlada.
from tz_core.bitacora_io import (
    seleccionar_archivo,
    seleccionar_carpeta_salida,
    ensure_dir,
    obtener_hojas_visibles,
    listar_todas_hojas,
    seleccionar_hoja_visible,
    seleccionar_hoja,
    cargar_excel_con_normalizacion,
)
from tz_core.mapping_wizard import WizardIO
from tz_core.manual_mapping_helpers import (
    prepare_manual_mapping as _prepare_manual_mapping,
    run_manual_mapping as _run_manual_mapping,
    build_wizard_io as _build_wizard_io_helper,
)
from tz_core.html_helpers import fmt_datetime as fmt_dt
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
    log_debug,
)
from tz_core.output_runner import run_outputs_flow
from tz_core.health_utils import (
    log_dataset_stats,
    run_health_checks,
)
from tz_core.synonym_utils import persist_user_synonym as _persist_user_synonym_helper
from tz_core.ui_utils import (
    collect_manual_mode_context,
    gather_dataset_metadata,
    prompt_case_identity,
    collect_top_overrides,
    prompt_output_routing,
    summarize_outputs,
    suggest_case_name,
)
from tz_core.output_flow import prepare_output_setup
from tz_core.manual_flow import (
    normalize_and_validate_schema,
    apply_time_filter_prompt,
    handle_manual_html_generation,
    write_minimal_filter_log_if_needed,
)
from tz_core.html_generator import (
    generate_html_header,
    generate_body_header,
    generate_metadata_section,
    generate_kpi_section,
    build_identification_rows,
    build_top_contacts_sections,
    build_top_antennas_section,
    build_antennas_by_hour_section,
    inject_technical_metadata,
    resolve_top_antennas_n,
)
from tz_core.time_filters import (
    _solicitar_filtros_tiempo,
    _aplicar_filtros_tiempo,
)

# =========================
# Generación de KML (usa CONFIG)
# =========================

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
    CONFIG = core_get_config()  # Usa la función centralizada (ya modular)
    
    # Importar cfg_build_rename_map desde el módulo (ya en imports globales)
    RENAME_MAP = cfg_build_rename_map(CONFIG)

# Flag para modo wizard de mapeo manual (QC)
MANUAL_QC_MAPPING = True
WIZARD_IO_LOGGING_ENABLED = os.getenv("TZ_WIZARD_LOGGING", "1").lower() not in {"0", "false", "off"}

ALIAS_VISIBLES = {
    "tel": "tel_analizado",
    "ubicacion": "direccion_antena",
}


def _build_wizard_io(log_to_system: Optional[bool] = None) -> WizardIO:
    """Wrapper que reusa build_wizard_io con logging opcional controlado por env."""

    return _build_wizard_io_helper(
        log_to_system,
        log_enabled_default=WIZARD_IO_LOGGING_ENABLED,
        log_debug=log_debug,
        log_info=log_info,
    )

# === SECCI�"N: WIZARD DE MAPEO DE COLUMNAS (detecci�n, mapeo manual, QC) ===
# � M�DULO EXTRA&#205;DO EN EPIC 15 - 27/12/2025
#
# La funci�n _wizard_qc_mapeo() (382 l�neas, marcada PELIGRO EXTREMO) fue
# exitosamente extra�da a tz_core/mapping_wizard.py con protocolo paranoico.
#
# MIGRACI�"N:
# - C�digo original: L183-565 (382 l�neas de l�gica cr�tica)
# - Nuevo m�dulo: tz_core/mapping_wizard.py (MappingWizard class)
# - Import: from tz_core.mapping_wizard import MappingWizard (uso directo vía helper)
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


def _persist_user_synonym(canonical: str, encabezado: str) -> None:
    """Actualiza CONFIG/RENAME_MAP cuando el asistente agrega sinónimos manuales."""

    global CONFIG, RENAME_MAP
    CONFIG, RENAME_MAP = _persist_user_synonym_helper(
        config=CONFIG,
        rename_map=RENAME_MAP,
        canonical=canonical,
        encabezado=encabezado,
        cfg_add_user_synonym=cfg_add_user_synonym,
        cfg_build_rename_map=cfg_build_rename_map,
        logger=log,
    )


# Wrappers de compatibilidad para logging

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
    """Wrapper de compatibilidad para función log."""
    _log_impl(msg)


def _apply_qc_placeholders(
    df: pd.DataFrame,
    missing_fields,
    cols_originales,
    target_alias,
    *,
    logger=log,
):
    """Rellena placeholders 'SinInf' y devuelve listas refrescadas para QC manual."""
    return apply_qc_placeholders(
        df=df,
        missing_fields=missing_fields,
        cols_originales=cols_originales,
        target_alias=target_alias,
        logger=logger,
    )


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

# =========================
# Configuración externa
# =========================
from tz_core.utils import sanear_nombre_archivo
from tz_core.config_loader import (
    get_config as core_get_config,
    cfg_build_rename_map,
    cfg_add_user_synonym,
    solicitar_color_tema,
)
from tz_core.bitacora_normalization import (
    validate_time_sample as _valida_formato_hora,
    validate_date_parsable as _valida_fecha_parsible,
    validate_latlon as _valida_latlon,
    sanitize_latlon,
    parse_duration_seconds,
)
from tz_core.schema_utils import (
    prep_meta_unicos,
    ensure_placeholder_columns,
    apply_qc_placeholders,
)
from tz_core.color_utils import color_mock
from tz_core.dataframe_utils import _pick_col
from tz_core.bitacora_utils import (
    coalesce_cols as _coalesce_cols,
    fmt_lista as _fmt_lista,
)
from tz_core.analytics import construir_seccion_todos_contactos, generar_historial_cambios_antena
from tz_core.file_utils import (
    escribe_hashes_txt,
    write_detailed_hashes_report,
    copiar_logo_a_salida,
    _copiar_logo_a_salida,
    relocate_kmz_file,
)
from tz_core.schema_guard import validate_schema_or_abort
from tz_core.output_pipeline import produce_case_outputs
from tz_core.html_toc import apply_toc
from tz_core.ingestion_pipeline import run_ingestion_pipeline

# === CONFIG & GLOBALS ===

# CONFIG inicializado al nivel de módulo (se carga una sola vez)
CONFIG = None
OVERRIDE_TOPS = None  # override temporal de Top N (se rellena en tiempo de ejecución)

HTML_SECCION_INTERACCIONES = ""

from tz_core.time_utils import to_datetime_silent, _to_datetime_series, _fmt_hms

def _construir_seccion_interacciones(df, dias=3, columnas_config=None):

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

    # Normalizar coordenadas con helper central y marcar filas válidas
    has_latlon = pd.Series(False, index=df.index)
    if col_lat and col_long:
        try:
            df = sanitize_latlon(df, lat_col=col_lat, lon_col=col_long, bbox=_bbox_cfg)
            has_latlon = df[col_lat].notna() & df[col_long].notna()
        except Exception:
            pass

    def _es_valida_latlon_row(row):
        """Consulta la máscara de coordenadas válidas generada tras sanitize_latlon."""
        try:
            return bool(has_latlon.loc[row.name])
        except Exception:
            return False

    # Si no hay df razonable, retorna vacío (no rompe HTML)
    if df is None or df.empty:
        return ""

    # Construcción de datetime y fecha
    dt = _to_datetime_series(df)
    df_local = df.copy()
    df_local['_has_latlon'] = has_latlon.reindex(df_local.index, fill_value=False)
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
            df_local['_dur_sec'] = ser_dur.map(parse_duration_seconds)
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
            antenas_validas = df_d['_has_latlon'].any()

        fecha_h = pd.to_datetime(d).strftime("%d/%m/%Y")
        out.append(f'<div id="content-{pd.to_datetime(d).strftime("%Y-%m-%d")}" class="day-content" style="display:none;">')
        out.append(f'<h3>Se muestran las interacciones del día: {fecha_h}</h3>')

        # KPIs del día
        total_dia = int(len(df_d))
        dur_total_dia = _fmt_hms(df_d['_dur_sec'].sum() if '_dur_sec' in df_d.columns else 0)

        if total_dia > 0:
            if col_antena and (col_antena in df_d.columns):
                _valid_rows = df_d[df_d['_has_latlon']]
                antenas_unicas = int(_valid_rows[col_antena].dropna().astype(str).nunique()) if not _valid_rows.empty else 0
            else:
                antenas_unicas = 0
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                sin_antena_cnt = int((~df_d['_has_latlon']).sum())
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


def generar_informe_html(df: pd.DataFrame, archivo_kml: str, carpeta_salida: str, nombre_salida: str, hoja: str | None = None, nombre_bitacora: str | None = None) -> str:
    """
    Genera un informe HTML sencillo (portada + KPIs + enlaces) en la misma carpeta del KML.
    Retorna la ruta del HTML generado.
    """
    # Validación defensiva de entrada
    if df is None:
        log("[ERROR] generar_informe_html: DataFrame es None, abortando")
        return ""
    if df.empty:
        log("[WARN] generar_informe_html: DataFrame vacío, generando reporte mínimo")
        # Continuar para crear archivo con mensaje de ausencia de datos
    
    from datetime import datetime
    
    kml_name = os.path.basename(archivo_kml)
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
    bbox_global = {"lat_min": -90.0, "lat_max": 90.0, "lon_min": -180.0, "lon_max": 180.0}
    df_coords = sanitize_latlon(df, bbox=bbox_global)
    lat_num = df_coords.get("lat", pd.Series(dtype=float))
    lon_num = df_coords.get("long", pd.Series(dtype=float))
    valid_coord = int((lat_num.notna() & lon_num.notna()).sum())
    coord_validas = int(valid_coord)
    coord_invalidas = int(total - coord_validas)

    # antenas únicas (mismo filtro que la tabla: sin nombres inválidos y con coords válidas)
    if "antena" in df.columns:
        s_ant = df["antena"].astype(str).str.strip()
        invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        m_name = ~s_ant.str.lower().isin(invalid_names)

        m_coord = lat_num.notna() & lon_num.notna()
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

    if "fecha" in df.columns:
        # Preferir combinar fecha+hora si existe 'hora'
        dt = None
        try:
            if "hora" in df.columns and df["hora"].notna().any():
                dt = to_datetime_silent(
                    df["fecha"].astype(str).str.strip() + " " + df["hora"].astype(str).str.strip(),
                    dayfirst=True, errors="coerce"
                ).dropna()
            else:
                # Solo fecha: tomar 00:00 para el inicio y 23:59 para el fin
                fechas = to_datetime_silent(df["fecha"], dayfirst=True, errors="coerce").dropna()
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

    # --- Identificación del número analizado (delegada a tz_core.html_generator) ---
    ident_rows = build_identification_rows(
        df,
        CONFIG if 'CONFIG' in globals() and isinstance(CONFIG, dict) else None,
    )


    # --- Top contactos (delegado a tz_core.html_generator) ---
    overrides_ctx = (
        OVERRIDE_TOPS
        if 'OVERRIDE_TOPS' in globals() and isinstance(OVERRIDE_TOPS, dict)
        else None
    )
    top_contactos_cnt_html, top_contactos_dur_html, _topC = build_top_contacts_sections(
        df,
        CONFIG if 'CONFIG' in globals() and isinstance(CONFIG, dict) else None,
        overrides_ctx,
    )


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
                ts = to_datetime_silent(
                    df_a["fecha"].astype(str).str.strip() + " " + hora_str,
                    errors="coerce", dayfirst=True
                )
                df_a["_ts"] = ts
            else:
                df_a["_ts"] = pd.NaT

            # azimut entero (para frecuencia)
            az = pd.to_numeric(df_a.get("azimut", pd.Series(dtype=float)), errors="coerce").round().astype("Int64")
            df_a["_az_i"] = az

            # coords numéricas validadas con helper central
            bbox_all = {"lat_min": -90.0, "lat_max": 90.0, "lon_min": -180.0, "lon_max": 180.0}
            try:
                df_a = sanitize_latlon(df_a, lat_col="lat", lon_col="long", bbox=bbox_all)
            except Exception:
                pass
            df_a["_lat"] = pd.to_numeric(df_a.get("lat", pd.Series(dtype=float)), errors="coerce")
            df_a["_lon"] = pd.to_numeric(df_a.get("long", pd.Series(dtype=float)), errors="coerce")
            df_a = df_a[df_a["_lat"].notna() & df_a["_lon"].notna()]


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

    html_header = generate_html_header(theme_hex, nombre_salida)
    body_header = generate_body_header(logo_html, nombre_salida, hoja, gen_dt, CONFIG)
    metadata_section = generate_metadata_section(nombre_bitacora, hoja, rango_str, ident_rows)
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

    # Índice de navegación: delegar en helper centralizado
    html = apply_toc(html)

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

    # === HTML-INTERACCIONES-1: sección Interacciones recientes (dropdown por día) ===
    try:
        # Preferir la sección ya generada por produce_case_outputs; si no existe, construirla aquí.
        sec_inter = (globals().get("HTML_SECCION_INTERACCIONES") or "").strip()

        if not sec_inter:
            cfg_html = CONFIG.get("html", {}) if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else {}
            cfg_cols = CONFIG.get("columnas", {}) if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else {}
            try:
                dias_cfg = int(cfg_html.get("interacciones_ultimos_dias", 3))
            except Exception:
                dias_cfg = 3
            sec_inter = _construir_seccion_interacciones(df, dias_cfg, cfg_cols)

        if sec_inter:
            anchor = "<h2>Indicadores</h2>"
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_inter + html[j+10:]
                else:
                    html += sec_inter
            else:
                html += sec_inter
    except Exception:
        pass

    # === HTML-CONTACTOS-ALL-1: sección Todos los contactos ===
    try:
        sec_todos = (globals().get("HTML_SECCION_TODOS_CONTACTOS") or "").strip()

        if not sec_todos:
            cfg_cols = CONFIG.get("columnas", {}) if ('CONFIG' in globals() and isinstance(CONFIG, dict)) else {}
            sec_todos = construir_seccion_todos_contactos(df, cfg_cols)

        if sec_todos:
            anchor = '<h2 id="interacciones">Contactos con más comunicación</h2>'
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_todos + html[j+10:]
                else:
                    html += sec_todos
            else:
                html += sec_todos
    except Exception:
        pass

    # === HTML-ANTENAS-SIMPLE-1: sección Top antenas (delegada al helper) ===
    try:
        sec_ant = build_top_antennas_section(
            df,
            globals().get("CONFIG"),
            globals().get("OVERRIDE_TOPS"),
        )

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
        # Columnas y validadores reutilizados por heatmap/rangos
        def _pick_col(_df, candidatos):
            for c in candidatos:
                if c in _df.columns:
                    return c
            return None

        col_ant = _pick_col(df, ["antena", "nombre_antena", "cell_name"])
        col_lat = _pick_col(df, ["lat", "latitud", "latitude"])
        col_lon = _pick_col(df, ["long", "lon", "longitud", "lng", "longitude"])
        col_az  = _pick_col(df, ["azimut", "azimuth", "azi", "angulo"])

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

        # === HTML-ANTENAS-RANGOS-1: Antenas por rango horario (debajo del Top antenas) ===
        # Además, prepararemos la nueva sección de "Mapa de calor de actividad" (heatmap)
        # para insertarla entre "Antenas más activadas" y "Contactos con más comunicación".
        sec_ant_rangos = ""
        sec_heatmap = ""
        sec_recientes = ""
        try:
            sec_ant_rangos = build_antennas_by_hour_section(
                df,
                globals().get("CONFIG"),
                globals().get("OVERRIDE_TOPS"),
            )
        except Exception:
            sec_ant_rangos = ""

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
                            # Obtener top_N del config (respeta overrides) con default 5
                            _topN_markers = resolve_top_antennas_n(
                                globals().get("CONFIG"),
                                globals().get("OVERRIDE_TOPS"),
                                default=5,
                            )
                            
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
                        insert_pos = fin_res + 10 if fin_res != -1 else -1

                        # Insertar heatmap primero (si existe)
                        if fin_res != -1 and sec_heatmap:
                            html = html[:fin_res+10] + "\n" + sec_heatmap + html[fin_res+10:]
                            idx_hm = html.find('id="heatmap-actividad"', fin_res)
                            if idx_hm != -1:
                                fin_hm = html.find("</section>", idx_hm)
                                if fin_hm != -1:
                                    insert_pos = fin_hm + 10

                        # Finalmente insertar el bloque de contactos (interacciones)
                        if insert_pos != -1:
                            html = html[:insert_pos] + "\n" + bloque_int + html[insert_pos:]

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
                            html = html[:j+10] + "\n" + sec_ant_rangos + html[j+10:]
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

    try:
        inject_technical_metadata(
            html_path,
            CONFIG if 'CONFIG' in globals() and isinstance(CONFIG, dict) else None,
        )
    except Exception:
        pass

    # --- HASHES de salida: HTML, KML y KMZ (si existen) ---
    try:
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
            write_detailed_hashes_report(txt_hash, archivos)
            try:
                log(f"[INFO] Hashes guardados en: {txt_hash}")
            except Exception:
                print(f"[INFO] Hashes guardados en: {txt_hash}")
    except Exception:
        # Nunca bloquear la generación por hashes
        pass


    return html_path



# --- Anti-hojas: ignorar ocultas y elegir visible ---

# =========================
# Flujo principal
# =========================

def _modo_manual():
    """Wrapper de compatibilidad - usa tz_core.manual_mode.modo_manual"""
    from tz_core.manual_mode import modo_manual
    return modo_manual(CONFIG)


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
    try:
        from tests.helpers.monkeypatch_flow import apply_run_monkeypatch

        mp_ctx = apply_run_monkeypatch(
            globals_dict=globals(),
            ruta_entrada=ruta_entrada,
            hoja=hoja,
            carpeta_salida=carpeta_salida,
            override_tops=globals().get("OVERRIDE_TOPS"),
            color_mock_fn=color_mock,
        )
        restore = mp_ctx.get("restore")
        out_root = mp_ctx.get("out_root")
        _snapshot = mp_ctx.get("snapshot")
    except Exception:
        def _snapshot(folder):
            try:
                return set(glob.glob(os.path.join(folder, "**/*"), recursive=True))
            except Exception:
                return set()

        def restore():
            pass

        out_root = carpeta_salida or os.getcwd()

    # --- Capturar stdout/stderr como log en memoria ---
    buf = io.StringIO()
    html_path = kmz_path = hashes_path = log_path = None

    # --- Snapshot de archivos previos para detectar nuevos (HTML/KMZ/HASHES) ---
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
        restore()
    except Exception:
        pass

    return {
        "html": html_path,
        "kmz": kmz_path,
        "hashes": hashes_path,
        "log": log_path,
    }

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

    def _run_manual_mode() -> None:
        log("Iniciando modo manual de antenas...")
        _modo_manual()
        log("Regresando del modo manual al menú principal")

    def _pick_color(cfg):
        log("Solicitando configuración de tema de colores...")
        return solicitar_color_tema(cfg)

    context = collect_manual_mode_context(
        config=CONFIG,
        input_fn=input,
        output_fn=print,
        color_picker=_pick_color,
        manual_mode_callback=_run_manual_mode,
    )
    opcion = context.option
    CONFIG = context.config
    log(f"Modo válido seleccionado: {opcion}")
    log("Configuración de colores completada")
    
    dataset = gather_dataset_metadata(
        log_fn=log,
        select_file=seleccionar_archivo,
        select_sheet=seleccionar_hoja_visible,
        load_dataframe=cargar_excel_con_normalizacion,
        output_fn=print,
    )
    if not dataset:
        return

    archivo_entrada = dataset.archivo
    hoja = dataset.hoja
    df = dataset.dataframe

    log_dataset_stats("carga_inicial", df, logger=log)

    # La carpeta se elegirá al final (previsualización)
    carpeta_salida = None

    # Snapshot de columnas originales (antes de cualquier mapeo/rename)
    cols_originales = list(dataset.columnas)


    # === VALIDACIÓN DE SCHEMA (aborto elegante) — INICIO =======================
    def validate_schema_or_abort_local(df):
        return validate_schema_or_abort(
            df,
            config=CONFIG,
            logger=log,
            output_fn=print,
        )

    # Auto-mapeo de encabezados (desde CONFIG.schema.fields) con fuzzy
    # - Usa sinónimos del config
    # - Normaliza sinónimos igual que las columnas (lower, sin acentos, separadores -> _)
    # - Lógica fuzzy centralizada en tz_core.dataframe_utils.apply_schema_renames

    schema_fields = {}
    try:
        schema_fields = (CONFIG.get("schema") or {}).get("fields") or {}
    except Exception:
        schema_fields = {}

    ingestion = run_ingestion_pipeline(
        df=df,
        config=CONFIG,
        original_columns=cols_originales,
        manual_qc_mapping=MANUAL_QC_MAPPING,
        alias_visibles=ALIAS_VISIBLES,
        wizard_io_factory=_build_wizard_io,
        persist_synonym_fn=_persist_user_synonym,
        validate_schema_fn=validate_schema_or_abort_local,
        validar_datos_fn=validar_datos,
        time_filter_option=opcion,
        solicitar_filtros_fn=_solicitar_filtros_tiempo,
        aplicar_filtros_fn=_aplicar_filtros_tiempo,
        logger=log,
        output_fn=print,
        run_manual_mapping_fn=_run_manual_mapping,
    )

    df = ingestion.dataframe
    errores = ingestion.errores
    time_filters = ingestion.time_filters

    try:
        err_count = len(errores) if errores is not None else 0
        tf_summary = time_filters.summary if getattr(time_filters, "enabled", False) else "sin filtros de tiempo"
        log(f"[ingestion] errores={err_count} filtros={tf_summary}")
    except Exception:
        pass

    log_dataset_stats("post_ingestion", df, logger=log)

    if time_filters.enabled:
        if df.empty:
            print("No hay registros después de aplicar el filtro. Saliendo...")
            return
        if time_filters.summary:
            print(f"[INFO] Filtro aplicado: {time_filters.summary}")

    if not run_health_checks(df, logger=log, output_fn=print):
        return

    # Salidas (delegado a helper para reducir superficie del monolito)
    nombre_base = os.path.splitext(os.path.basename(archivo_entrada))[0]

    output_setup = prepare_output_setup(
        df=df,
        config=CONFIG,
        time_filters=time_filters,
        nombre_base=nombre_base,
        input_fn=input,
        output_fn=print,
        timestamp_fn=datetime.now,
        now_fn=datetime.now,
        sanitize_fn=sanear_nombre_archivo,
        prompt_case_identity=prompt_case_identity,
        suggest_case_name=suggest_case_name,
        collect_top_overrides=collect_top_overrides,
        prompt_output_routing=prompt_output_routing,
        select_folder=seleccionar_carpeta_salida,
        cwd_fn=os.getcwd,
        ensure_dir=ensure_dir,
    )

    identity = output_setup.identity
    suggestion = output_setup.suggestion
    base_auto = output_setup.base_auto
    modo_bitacora = identity.mode

    top_antenas = output_setup.top_antenas
    top_contactos = output_setup.top_contactos

    # Propagar overrides a nivel global para que las secciones HTML los lean
    try:
        globals()["OVERRIDE_TOPS"] = {"antenas": int(top_antenas), "contactos": int(top_contactos)}
    except Exception:
        pass

    nombre_salida = output_setup.nombre_salida
    carpeta_base = output_setup.carpeta_base
    carpeta_salida = output_setup.carpeta_salida
    archivo_kml = output_setup.archivo_kml
    archivo_kmz = output_setup.archivo_kmz
    carpeta_kml = output_setup.carpeta_kml

    informe_html = handle_manual_html_generation(
        config=CONFIG,
        df=df,
        archivo_kml=archivo_kml,
        carpeta_salida=carpeta_salida,
        nombre_salida=nombre_salida,
        hoja=hoja,
        carpeta_base=carpeta_base,
        logger=log,
        output_fn=print,
        generar_html_fn=generar_informe_html,
        relocate_kmz_fn=relocate_kmz_file,
    )

    write_minimal_filter_log_if_needed(
        result=time_filters,
        df=df,
        output_folder=carpeta_salida,
        logger=log,
    )

    log_dataset_stats("pre_kml_prep_meta", df, logger=log)

    # PRE-KML: asegurar alias/usuario/abonado sin prompt (usar 'SinInf' si faltan)
    df = prep_meta_unicos(
        df,
        [
            ("alias", "alias"),
            ("nombre_usuario", "nombre_usuario"),
            ("abonado", "abonado"),
        ],
        logger=log,
    )


    log("[salidas] Generando KML/KMZ…")
    from tz_core.kml_generator import generar_kml
    archivo_kml, desc_coords = generar_kml(df, archivo_kml, config=CONFIG, flat=False, override_tops=OVERRIDE_TOPS)
    log(f"[salidas] KML listo: {archivo_kml}")

    # === BLOQUE HTML/SECCIONES (delegado) ===
    def _store_interacciones(html):
        global HTML_SECCION_INTERACCIONES
        HTML_SECCION_INTERACCIONES = html or ""

    def _store_contactos(html):
        global HTML_SECCION_TODOS_CONTACTOS
        HTML_SECCION_TODOS_CONTACTOS = html or ""

    run_outputs_flow(
        df=df,
        config=CONFIG,
        nombre_salida=nombre_salida,
        archivo_kml=archivo_kml,
        carpeta_base=carpeta_base,
        carpeta_salida=carpeta_salida,
        archivo_entrada=archivo_entrada,
        hoja=hoja,
        archivo_errores=archivo_errores,
        desc_coords=desc_coords,
        build_interactions_section=_construir_seccion_interacciones,
        build_contacts_section=construir_seccion_todos_contactos,
        generar_html_fn=generar_informe_html,
        relocate_kmz_fn=relocate_kmz_file,
        write_hashes_fn=escribe_hashes_txt,
        produce_fn=produce_case_outputs,
        summarize_fn=summarize_outputs,
        logger=log,
        output_fn=print,
        path_exists=os.path.exists,
        cwd_fn=os.getcwd,
        log_file_path=globals().get("LOG_FILE"),
        set_interactions_section=_store_interacciones,
        set_contacts_section=_store_contactos,
    )
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
