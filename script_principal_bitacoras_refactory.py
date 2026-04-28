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

"""
TZ-Analyzer — Orquestador Principal

Punto de entrada y orquestador del flujo de análisis de bitácoras telefónicas.
Coordina la carga de configuración, validación de datos, y delega el procesamiento
a los módulos especializados en tz_core/ (normalización, generación HTML/KML,
análisis de interacciones, etc.).

No contiene lógica de procesamiento directa — toda la lógica reside en tz_core/.

Architecture: TZ-Analyzer v1.0.0
"""

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

warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    UserCancelledError,
)
from tz_core.output_flow import prepare_output_setup
from tz_core.manual_flow import (
    normalize_and_validate_schema,
    apply_time_filter_prompt,
    write_minimal_filter_log_if_needed,
)
from tz_core.html.assembler import generar_informe_html as generar_informe_html_core
from tz_core.html.contacts import build_top_contacts_sections
from tz_core.time_filters import (
    solicitar_filtros_tiempo,
    aplicar_filtros_tiempo,
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
     Desarrollado por Omar Arias (Tony Zero)
===============================================
""")
    
    # Configuración y mapa de sinónimos usando funciones modulares
    global CONFIG, RENAME_MAP
    CONFIG = core_get_config()  # Usa la función centralizada (ya modular)
    
    # Importar cfg_build_rename_map desde el módulo (ya en imports globales)
    RENAME_MAP = cfg_build_rename_map(CONFIG)

# Flag para modo wizard de mapeo manual (QC)
MANUAL_QC_MAPPING = True
WIZARD_IO_LOGGING_ENABLED = os.getenv("TZ_WIZARD_LOGGING", "0").lower() not in {"0", "false", "off"}

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

# === SECCIÓN: WIZARD DE MAPEO DE COLUMNAS ===
# Módulo extraído a tz_core/mapping_wizard.py (Epic 15, dic 2025)
# Import: from tz_core.mapping_wizard import MappingWizard


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
    """Wrapper de compatibilidad que emula una lista de logs para código legacy."""
    def __iter__(self):
        """Itera sobre los logs almacenados."""
        return iter(get_logs())
    def __len__(self):
        """Retorna el número de logs."""
        return get_logs_count()
    def __getitem__(self, key):
        """Accede a un log por índice."""
        return get_logs()[key]
    def append(self, item):
        """Agrega un log, extrayendo el mensaje sin timestamp si ya lo tiene."""
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
    """Wrapper de compatibilidad que emula un set de placeholders para código legacy."""
    def __iter__(self):
        """Itera sobre los placeholders de log."""
        return iter(get_log_placeholders())
    def __len__(self):
        """Retorna el número de placeholders."""
        return len(get_log_placeholders())
    def __contains__(self, item):
        """Verifica si un placeholder existe en el conjunto."""
        return has_log_placeholder(item)
    def add(self, item):
        """Agrega un placeholder al conjunto."""
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


from tz_core.validation_utils import validar_datos, guardar_errores

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
from tz_core.bitacora_utils import (
    coalesce_cols as _coalesce_cols,
    fmt_lista as _fmt_lista,
)
from tz_core.analytics import construir_seccion_todos_contactos
from tz_core.file_utils import (
    escribe_hashes_txt,
    write_detailed_hashes_report,
    copiar_logo_a_salida,
    _copiar_logo_a_salida,
    relocate_kmz_file,
)
from tz_core.schema_guard import validate_schema_or_abort
from tz_core.output_pipeline import produce_case_outputs
from tz_core.ingestion_pipeline import run_ingestion_pipeline
from tz_core.interacciones_builder import construir_seccion_interacciones

# === CONFIG & GLOBALS ===

# CONFIG inicializado al nivel de módulo (se carga una sola vez)
CONFIG = None


# --- Anti-hojas: ignorar ocultas y elegir visible ---

# =========================
# Flujo principal
# =========================

def _modo_manual():
    """Wrapper de compatibilidad - usa tz_core.manual_mode.modo_manual"""
    from tz_core.manual_mode import modo_manual
    return modo_manual(CONFIG)


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
    #   1) Top N: override_tops se pasa como variable local
    #   2) Solo KMZ: el script consulta CONFIG["salida"]["solo_kmz"]
    global CONFIG
    try:
        if "CONFIG" not in globals() or not isinstance(CONFIG, dict):
            CONFIG = {}
        CONFIG.setdefault("salida", {})
        CONFIG["salida"]["solo_kmz"] = bool(solo_kmz)
    except Exception:
        pass
    override_tops = {
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
            override_tops=override_tops,
            color_mock_fn=color_mock,
        )
        restore = mp_ctx.get("restore")
        out_root = mp_ctx.get("out_root")
        _snapshot = mp_ctx.get("snapshot")
    except Exception:
        def _snapshot(folder):
            """Toma snapshot de archivos en folder de forma recursiva, retorna set de paths."""
            try:
                return set(glob.glob(os.path.join(folder, "**/*"), recursive=True))
            except Exception:
                return set()

        def restore():
            """Función placeholder para restauración (no implementada)."""
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
        """Busca y retorna el archivo más reciente con extensión en exts desde archivos creados."""
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
        """Ejecuta el modo manual de antenas y registra el inicio y finalización."""
        log("Iniciando modo manual de antenas...")
        _modo_manual()
        log("Regresando del modo manual al menú principal")

    def _pick_color(cfg):
        """Solicita configuración de tema de colores al usuario y retorna el color seleccionado."""
        log("Solicitando configuración de tema de colores...")
        return solicitar_color_tema(cfg)

    context = collect_manual_mode_context(
        config=CONFIG,
        input_fn=input,
        output_fn=print,
        color_picker=lambda cfg: cfg,
        manual_mode_callback=_run_manual_mode,
    )
    opcion = context.option
    CONFIG = context.config
    log(f"Modo válido seleccionado: {opcion}")
    
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
    CONFIG = _pick_color(CONFIG) or CONFIG
    log("Configuración de colores completada")
    df = dataset.dataframe

    log_dataset_stats("carga_inicial", df, logger=log)

    # La carpeta se elegirá al final (previsualización)
    carpeta_salida = None

    # Snapshot de columnas originales (antes de cualquier mapeo/rename)
    cols_originales = list(dataset.columnas)


    # === VALIDACIÓN DE SCHEMA (aborto elegante) — INICIO =======================
    def validate_schema_or_abort_local(df):
        """Valida el esquema del DataFrame y aborta si hay errores críticos."""
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
        solicitar_filtros_fn=solicitar_filtros_tiempo,
        aplicar_filtros_fn=aplicar_filtros_tiempo,
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

    # Salidas (delegado a helper para modularidad)
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

    override_tops = {"antenas": int(top_antenas), "contactos": int(top_contactos)}

    nombre_salida = output_setup.nombre_salida
    carpeta_base = output_setup.carpeta_base
    carpeta_salida = output_setup.carpeta_salida
    archivo_kml = output_setup.archivo_kml
    archivo_kmz = output_setup.archivo_kmz
    carpeta_kml = output_setup.carpeta_kml

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
    archivo_kml, desc_coords = generar_kml(df, archivo_kml, config=CONFIG, flat=False, override_tops=override_tops)
    log(f"[salidas] KML listo: {archivo_kml}")

    # === BLOQUE HTML/SECCIONES (delegado) ===
    run_outputs_flow(
        df=df,
        config=CONFIG,
        override_tops=override_tops,
        nombre_salida=nombre_salida,
        archivo_kml=archivo_kml,
        carpeta_base=carpeta_base,
        carpeta_salida=carpeta_salida,
        archivo_entrada=archivo_entrada,
        hoja=hoja,
        archivo_errores=archivo_errores,
        desc_coords=desc_coords,
        build_interactions_section=construir_seccion_interacciones,
        build_contacts_section=construir_seccion_todos_contactos,
        generar_html_fn=generar_informe_html_core,
        relocate_kmz_fn=relocate_kmz_file,
        write_hashes_fn=escribe_hashes_txt,
        produce_fn=produce_case_outputs,
        summarize_fn=summarize_outputs,
        logger=log,
        output_fn=print,
        path_exists=os.path.exists,
        cwd_fn=os.getcwd,
        log_file_path=None,
        set_interactions_section=lambda _html: None,
        set_contacts_section=lambda _html: None,
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
    except UserCancelledError:
        print("\nProceso cancelado por el usuario.")
    except Exception as e:
        logging.error("Error no controlado: %s", e)
        traceback.print_exc()
        raise

