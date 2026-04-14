"""
tz_core.ui_utils - UTILIDADES DE INTERFAZ DE USUARIO
==================================================

✅ ESTADO: EXTRACCIÓN INCREMENTAL - HELPERS DE UI PUROS
🎯 PROPÓSITO: Funciones de interfaz de usuario e input del usuario
📍 DIFERENCIACIÓN: UI helpers sin lógica de negocio crítica

RESPONSABILIDADES ESPECÍFICAS:
- solicitar_overrides_topn(): Override temporal de configuración Top N
- Helpers de input y validación de usuario
- Funciones de interfaz sin side effects complejos

DEPENDENCIAS:
- Ninguna: Solo Python estándar (print, input, int, exception handling)

EXTRAÍDO DESDE: script_principal_bitacoras_refactory.py líneas 7322-7359
FECHA EXTRACCIÓN: 29 octubre 2025
"""

import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from tz_core.bitacora_normalization import normalize_imei, normalize_msisdn
from tz_core.types import (
    CaseIdentity,
    CaseNameSuggestion,
    DatasetMetadata,
    ManualModeContext,
    OutputRouting,
    TopSelection,
)


def collect_manual_mode_context(
    *,
    config: Optional[Dict[str, Any]],
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    color_picker: Callable[[Optional[Dict[str, Any]]], Dict[str, Any]],
    manual_mode_callback: Optional[Callable[[], None]] = None,
) -> ManualModeContext:
    """Muestra el menú principal y retorna la opción válida (1 o 2).

    Si el usuario elige la opción 3 (modo manual) se invoca el callback
    proporcionado y se vuelve a mostrar el menú. Cuando se elige 1/2 se
    ejecuta `color_picker` para actualizar la configuración y se devuelve
    un `ManualModeContext` con la opción elegida y la config resultante.
    """

    cfg = config or {}

    while True:
        output_fn("\nSeleccione el modo de procesamiento:\n")
        output_fn("[1] Procesar bitácora completa")
        output_fn("    → Genera informe HTML + mapa KML/KMZ con todos los registros")
        output_fn("    → Ideal para análisis forense completo de un caso\n")
        output_fn("[2] Procesar bitácora filtrada por tiempo")
        output_fn("    → Analiza período específico: día, rango de días o rango de horas")
        output_fn("    → Útil para enfocar en ventanas temporales de interés\n")
        output_fn("[3] Ingresar antenas manualmente (sin bitácora)")
        output_fn("    → Crea archivo KML desde coordenadas GPS directas")
        output_fn("    → Modo avanzado para ploteo rápido de ubicaciones\n")
        resp = (input_fn("Opción (1/2/3, Enter=1): ") or "").strip() or "1"

        if resp == "3":
            if manual_mode_callback:
                manual_mode_callback()
            continue

        if resp in ("1", "2"):
            try:
                cfg = color_picker(cfg) or cfg
            except Exception:
                pass
            return ManualModeContext(option=resp, config=cfg)

        output_fn("[QC] Opción inválida, intenta de nuevo.")


def solicitar_overrides_topn(config: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """
    Pide Top N de antenas y de contactos solo para esta ejecución (override temporal).
    
    EXTRAÍDO DE: script_principal_bitacoras_refactory.py líneas 7322-7359
    
    Args:
        config: Diccionario de configuración con estructura:
                config.get('html', {}).get('top_antenas_n', default)
                config.get('html', {}).get('top_contactos_n', default)
    
    Returns:
        Dict con overrides como {'antenas': int?, 'contactos': int?} 
        o None si no se cambia nada.
        
    Functionality:
        1. Extrae valores default de configuración
        2. Solicita input del usuario para override temporal
        3. Parsea valores con validación (> 0)
        4. Maneja caso especial "mismo" para contactos = antenas
        5. Retorna dict con overrides válidos
    """
    try:
        defA = int(config.get('html', {}).get('top_antenas_n', 3))
        defC = int(config.get('html', {}).get('top_contactos_n', 10))
    except Exception:
        defA, defC = 3, 10

    print("\n( Opcional ) Ajuste de Top N para esta ejecución:")
    sa = input(f"Top N de ANTENAS (Enter={defA}): ").strip()
    sc = input(f"Top N de CONTACTOS (Enter={defC}, escribe 'mismo' para usar el de antenas): ").strip()

    ovr = {}

    def _parse(x):
        """Parsea valor a int positivo, retorna None si falla o es no-positivo."""
        try:
            v = int(x)
            return v if v > 0 else None
        except Exception:
            return None

    if sa:
        va = _parse(sa)
        if va:
            ovr['antenas'] = va

    if sc:
        if sc.lower() == 'mismo' and 'antenas' in ovr:
            ovr['contactos'] = ovr['antenas']
        else:
            vc = _parse(sc)
            if vc:
                ovr['contactos'] = vc

    return ovr if ovr else None


def gather_dataset_metadata(
    *,
    log_fn: Callable[[str], None],
    select_file: Callable[[], Optional[str]],
    select_sheet: Callable[[str], Optional[str]],
    load_dataframe: Callable[[str, Optional[str]], Tuple[Any, Optional[str]]],
    output_fn: Callable[[str], None],
) -> Optional[DatasetMetadata]:
    """Orquesta la selección de archivo/hoja y la carga del DataFrame normalizado."""

    log_fn("Iniciando selección de archivo de entrada...")
    archivo = select_file()
    if not archivo:
        log_fn("ERROR: Usuario no seleccionó archivo, terminando ejecución")
        output_fn("No se seleccionó un archivo. Saliendo.")
        return None

    log_fn(f"Archivo seleccionado exitosamente: {archivo}")
    log_fn("Iniciando selección de hoja de Excel...")
    hoja = select_sheet(archivo)
    log_fn(f"Hoja seleccionada: {hoja}")

    log_fn(f"Iniciando carga de datos desde {archivo}...")
    try:
        df, hoja_usada = load_dataframe(archivo, hoja)
        log_fn(f"Excel cargado exitosamente: {len(df)} filas, hoja usada: {hoja_usada}")
    except Exception as exc:  # pragma: no cover - logging path
        log_fn(f"ERROR CRÍTICO al cargar Excel: {type(exc).__name__}: {exc}")
        output_fn(f"Error al leer el Excel: {exc}")
        return None

    log_fn("Aplicando normalización de columnas...")
    df.columns = (
        df.columns.astype(str)
        .str.normalize("NFD").str.encode("ascii", "ignore").str.decode("ascii")
        .str.lower()
        .str.replace(r"[\s\-\/\.]+", "_", regex=True)
        .str.replace(r"__+", "_", regex=True)
        .str.strip("_")
    )
    columnas = list(df.columns)
    log_fn(f"Columnas después de normalización: {columnas}")

    return DatasetMetadata(
        archivo=archivo,
        hoja=hoja,
        dataframe=df,
        columnas=columnas,
        hoja_usada=hoja_usada,
    )


def prompt_case_identity(
    *,
    df: Any,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    now_fn: Callable[[], Any],
) -> CaseIdentity:
    """Determina el modo de bitácora (IMEI/TEL/AUTO) y sugiere el nombre base."""

    output_fn("\n[QC] Confirmar si esta bitácora es por número de Teléfono o IMEI para nombrar archivos")
    output_fn("I = IMEI")
    output_fn("T = Número telefónico")
    output_fn("Enter = Que TZ Analyzer decida")
    tipo_bitacora = (input_fn("→ Opción (I/T/Enter): ") or "").strip().upper()

    def _normalize_id(column: str, value: Any) -> str:
        """Normaliza identificador según tipo de columna (tel/imei) o retorna string limpio."""
        if column == "tel":
            return normalize_msisdn(value) or str(value).strip()
        if column == "imei":
            return normalize_imei(value) or str(value).strip()
        return str(value).strip()

    def _safe_nunique(column: str) -> int:
        """Cuenta valores únicos normalizados en columna, retorna 0 si no existe."""
        if column not in getattr(df, "columns", []):
            return 0
        try:
            serie = df[column].dropna().map(lambda v: _normalize_id(column, v))
            valores = {v for v in serie if v}
            return len(valores)
        except Exception:
            return 0

    if tipo_bitacora == "I":
        modo_bitacora = "IMEI"
    elif tipo_bitacora == "T":
        modo_bitacora = "TEL"
    else:
        imeis_unicos = _safe_nunique("imei")
        tels_unicos = _safe_nunique("tel")
        if imeis_unicos == 1 and tels_unicos != 1:
            modo_bitacora = "IMEI"
        elif tels_unicos == 1 and imeis_unicos != 1:
            modo_bitacora = "TEL"
        else:
            modo_bitacora = "AUTO"

    output_fn(f"[QC] Tipo de bitácora establecido: {modo_bitacora}")

    def _limpiar_alias(valor: Optional[str]) -> str:
        """Limpia alias: reemplaza espacios con _, trunca a 12 caracteres, retorna vacío si None."""
        try:
            if valor is None:
                return ""
            s = str(valor).strip()
            if not s:
                return ""
            return s.replace(" ", "_")[:12]
        except Exception:
            return ""

    alias_val = None
    if "alias" in getattr(df, "columns", []):
        try:
            serie_alias = df["alias"].astype(str).str.strip()
            valores = [x for x in serie_alias.unique() if x]
            alias_val = valores[0] if valores else None
        except Exception:
            alias_val = None
    alias_short = _limpiar_alias(alias_val)

    def _first_sorted(column: str) -> Optional[str]:
        """Retorna el primer valor normalizado ordenado alfanuméricamente de la columna."""
        if column not in getattr(df, "columns", []):
            return None
        try:
            serie = df[column].dropna().map(lambda v: _normalize_id(column, v))
            valores = sorted({v for v in serie if v})
            return valores[0] if valores else None
        except Exception:
            return None

    primary = None
    prefix = "AUTO"
    if modo_bitacora == "IMEI":
        prefix = "IMEI"
        primary = _first_sorted("imei")
    elif modo_bitacora == "TEL":
        prefix = "TEL"
        primary = _first_sorted("tel")

    stamp = now_fn().strftime("%Y-%m-%d_%H-%M")
    if primary:
        base_auto = f"{prefix}_{primary}{('_' + alias_short) if alias_short else ''}_{stamp}"
    else:
        base_auto = f"CASO{('_' + alias_short) if alias_short else ''}_{stamp}"

    return CaseIdentity(
        mode=modo_bitacora,
        primary_id=primary,
        alias_short=alias_short,
        base_name=base_auto,
    )


def collect_top_overrides(
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    default_antennas: int = 10,
    default_contacts: int = 10,
) -> TopSelection:
    """Solicita los valores de Top N para antenas y contactos."""

    def _prompt(prompt: str) -> str:
        """Solicita input al usuario, retorna string limpio o vacío si falla."""
        try:
            return (input_fn(prompt) or "").strip()
        except Exception:
            return ""

    def _parse(raw: str, fallback: int) -> int:
        """Parsea string a int, retorna fallback si vacío o inválido, asegura no-negativo."""
        if raw == "":
            return fallback
        try:
            value = int(raw)
        except Exception:
            output_fn("[QC] Valor inválido, se utilizará el predeterminado.")
            return fallback
        return max(0, value)

    antennas_raw = _prompt(
        f"→ Top de antenas (Enter={default_antennas}; 0=sin límite): "
    )
    antennas = _parse(antennas_raw, default_antennas)

    contacts_raw = _prompt(
        f"→ Top de contactos (Enter={default_contacts}; 0=sin límite; 'mismo' para copiar el de antenas): "
    )
    if contacts_raw.lower() == "mismo":
        contacts = antennas
    else:
        contacts = _parse(contacts_raw, default_contacts)

    return TopSelection(antennas=antennas, contacts=contacts)


def prompt_output_routing(
    *,
    base_name: str,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    sanitize_fn: Callable[[str], str],
    select_folder: Callable[[], Optional[str]],
    cwd_fn: Callable[[], str],
    ensure_dir: Callable[[str], None],
    separate_kml: bool,
) -> OutputRouting:
    """Gestiona el rename opcional, carpeta destino y rutas finales de salida."""

    output_fn("[QC] Carpeta sugerida por TZ Analyzer:")
    output_fn(f"  📁 {base_name}\n")
    output_fn("[QC] Se generarán estos archivos:")
    output_fn(f"  - {base_name}_informe.html")
    output_fn(f"  - {base_name}_mapeo.kmz")
    output_fn(f"  - {base_name}_hashes.txt")
    output_fn(f"  - {base_name}_errores.txt\n")
    output_fn("Si desea cambiar el nombre base, escríbalo ahora (solo base, sin extensión).")

    _CHARS_PROHIBIDOS = r'\/:*?"<>|'
    while True:
        resp = (input_fn(f"Nombre base del KML (Enter = {base_name}): ") or "").strip()
        if not resp:
            resp = ""
            break
        if any(c in resp for c in _CHARS_PROHIBIDOS):
            output_fn(f'Nombre inválido. Evite caracteres: \\ / : * ? " < > |')
            continue
        if re.fullmatch(r"#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", resp):
            output_fn("Eso parece un color hex, no un nombre de archivo. Usaré el sugerido.")
            resp = ""
            break
        break

    nombre_salida = sanitize_fn(resp) if resp else base_name

    try:
        carpeta_base = select_folder() or ""
    except Exception:
        carpeta_base = ""
    if not carpeta_base:
        carpeta_base = cwd_fn()
    output_fn(f"[QC] Carpeta destino: {carpeta_base}")

    case_folder = nombre_salida
    carpeta_salida = os.path.join(carpeta_base, case_folder)
    ensure_dir(carpeta_salida)

    if separate_kml:
        carpeta_kml = os.path.join(carpeta_salida, "kml")
        ensure_dir(carpeta_kml)
        archivo_kml = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kml")
        archivo_kmz = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kmz")
    else:
        carpeta_kml = None
        archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
        archivo_kmz = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")

    return OutputRouting(
        base_name=nombre_salida,
        base_folder=carpeta_base,
        case_folder=case_folder,
        output_folder=carpeta_salida,
        kml_folder=carpeta_kml,
        kml_path=archivo_kml,
        kmz_path=archivo_kmz,
    )


def summarize_outputs(
    *,
    config: Optional[Dict[str, Any]],
    output_fn: Callable[[str], None],
    kml_path: Optional[str],
    error_report_path: Optional[str],
    discarded_coords: int,
    path_exists: Callable[[str], bool] = os.path.exists,
) -> Optional[str]:
    """Imprime los mensajes finales de archivos generados y retorna el KMZ esperado."""

    cfg = config or {}
    salida_cfg = cfg.get("salida", {}) if isinstance(cfg, dict) else {}
    solo_kmz = bool(salida_cfg.get("solo_kmz", False))
    separate_kmz = bool(salida_cfg.get("separar_kml_kmz", False))

    if kml_path and not solo_kmz:
        output_fn(f"KML generado en: {kml_path}")

    kmz_path = None
    if kml_path:
        if separate_kmz:
            kml_dir = os.path.dirname(kml_path)
            base_dir = os.path.dirname(kml_dir) if os.path.basename(kml_dir).lower() == "kml" else kml_dir
            kmz_dir = os.path.join(base_dir, "kmz")
            kmz_path = os.path.join(kmz_dir, os.path.splitext(os.path.basename(kml_path))[0] + ".kmz")
        else:
            kmz_path = os.path.splitext(kml_path)[0] + ".kmz"

    if kmz_path and path_exists(kmz_path):
        output_fn(f"KMZ generado en: {kmz_path}")

    output_fn(f"Filas descartadas por coordenadas inválidas: {discarded_coords}")
    if error_report_path:
        output_fn(f"Reporte de errores generado en: {error_report_path}")

    return kmz_path


def suggest_case_name(
    *,
    df: Any,
    identity: CaseIdentity,
    filters: Optional[Dict[str, Any]],
    timestamp_fn: Callable[[], Any],
    sanitize_fn: Callable[[str], str],
) -> CaseNameSuggestion:
    """Construye un nombre base sugerido considerando identidad y filtros."""

    columns = list(getattr(df, "columns", []))

    def _first_nonempty(column: str) -> Optional[str]:
        """Retorna el primer valor no-vacío de la columna, None si no existe o está vacía."""
        if column not in columns:
            return None
        try:
            serie = df[column].dropna().astype(str).str.strip()
            serie = serie[serie != ""]
            return serie.iloc[0] if not serie.empty else None
        except Exception:
            return None

    tel_candidates = [
        "tel",
        "telefono",
        "numero",
        "msisdn",
        "a_number",
        "origen",
        "from",
        "callingnumber",
        "num",
    ]
    alias_candidates = ["alias", "alias_usuario", "apodo"]

    tel_val = next((val for col in tel_candidates if (val := _first_nonempty(col))), None)
    alias_val = next((val for col in alias_candidates if (val := _first_nonempty(col))), None)

    tel_series = df.get("tel") if hasattr(df, "get") else None
    tel_multi = False
    if tel_series is not None:
        try:
            tel_multi = bool(tel_series.nunique(dropna=True) > 1)
        except Exception:
            tel_multi = False
    tel_part = tel_val or ("multi" if tel_multi else "sin_tel")
    alias_part = alias_val or "sin_alias"

    if "fecha" in columns:
        fechas_parsed = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
        fechas_valid = fechas_parsed.dropna()
        if not fechas_valid.empty:
            fmin = fechas_valid.min().strftime("%d-%m-%Y")
            fmax = fechas_valid.max().strftime("%d-%m-%Y")
            date_range = fmin if fmin == fmax else f"{fmin}__{fmax}"
        else:
            date_range = timestamp_fn().strftime("%d-%m-%Y")
    else:
        date_range = timestamp_fn().strftime("%d-%m-%Y")

    suffix = ""
    if filters:
        tipo = filters.get("tipo")
        try:
            if tipo == "dia":
                dia = pd.to_datetime(filters.get("dia"), dayfirst=True, errors="coerce")
                if pd.notna(dia):
                    suffix = f"__dia_{dia.strftime('%Y-%m-%d')}"
            elif tipo == "rango_dias":
                d1 = pd.to_datetime(filters.get("desde"), dayfirst=True, errors="coerce")
                d2 = pd.to_datetime(filters.get("hasta"), dayfirst=True, errors="coerce")
                if pd.notna(d1) and pd.notna(d2):
                    suffix = f"__rd_{d1.strftime('%Y-%m-%d')}__{d2.strftime('%Y-%m-%d')}"
            elif tipo == "rango_horas_dia":
                dia = pd.to_datetime(filters.get("dia"), dayfirst=True, errors="coerce")
                h1 = (filters.get("hora_ini") or "00:00")[:5].replace(":", "-")
                h2 = (filters.get("hora_fin") or "00:00")[:5].replace(":", "-")
                if pd.notna(dia) and h1 and h2:
                    suffix = f"__hrdia_{dia.strftime('%Y-%m-%d')}__{h1}__{h2}"
            elif tipo == "rango_horas":
                h1 = (filters.get("hora_ini") or "00:00")[:5].replace(":", "-")
                h2 = (filters.get("hora_fin") or "00:00")[:5].replace(":", "-")
                if h1 and h2:
                    suffix = f"__hr_{h1}__{h2}"
        except Exception:
            suffix = ""

    def _pick_id(column: str) -> str:
        """Selecciona identificador de columna: valor único, 'multiN' si hay varios, 'DESCONOCIDO' si falta."""
        if column not in columns:
            return "DESCONOCIDO"
        try:
            serie = df[column].astype(str).str.strip()
            serie = serie[~serie.isin(["", "0", "None", "none", "NULL", "null", "—", "--"])]
            if serie.empty:
                return "DESCONOCIDO"
            uniques = serie.unique()
            count = len(uniques)
            if count > 1:
                return f"multi{count}"
            return uniques[0]
        except Exception:
            return "DESCONOCIDO"

    mode_label = identity.mode or "AUTO"
    principal_col = "imei" if identity.mode == "IMEI" else "tel"
    principal_id = _pick_id(principal_col)
    alias_id = _pick_id("alias")
    if alias_id == "DESCONOCIDO" and alias_part != "sin_alias":
        alias_id = alias_part

    stamp = timestamp_fn().strftime("%Y-%m-%d_%H-%M")
    pieces = [mode_label or "AUTO", principal_id or "DESCONOCIDO"]
    if alias_id and alias_id != "DESCONOCIDO":
        pieces.append(alias_id)
    pieces.append(stamp)
    base_raw = "_".join(filter(None, pieces))
    base_name = sanitize_fn(base_raw)

    return CaseNameSuggestion(
        base_name=base_name,
        principal_id=principal_id,
        alias_id=alias_id,
        tel_part=tel_part,
        alias_part=alias_part,
        date_range_label=date_range,
        filter_suffix=suffix,
    )


# ==============================================================================
# SELECCIÓN DE ARCHIVOS/CARPETAS — Absorbido de utilidades.py (F10.2)
# ==============================================================================
"""
utilidades.py - UI HELPERS ESPECIALIZADOS EN INTERFAZ FORENSE
=============================================================

✅ ESTADO: CÓDIGO UI ACTIVO - ESPECIALIZADO EN INTERFAZ DE USUARIO
🎯 PROPÓSITO: Diálogos Tkinter y selección de archivos para workflow forense
📍 DIFERENCIACIÓN: NO confundir con tz_core/utils.py (funciones puras)

RESPONSABILIDADES ESPECÍFICAS:
- seleccionar_archivo(): Diálogos Tkinter para Excel + fallback consola
- seleccionar_carpeta(): Selección de directorios con memoria de sesión  
- _console_prompt(): Interfaz consola robusta para entornos sin GUI
- LAST_DIR: Memoria de sesión para UX optimizada

ARQUITECTURA HÍBRIDA:
- Este archivo maneja INTERFAZ DE USUARIO (UI layer)
- tz_core/utils.py maneja UTILIDADES PURAS (core functions)
- Son complementarios, NO duplicados

🎯 FILOSOFÍA DE DISEÑO: Especialización intencional en Excel para workflow forense real

CARACTERÍSTICAS ACTUALES:
- Especialización Excel (.xlsx/.xls) - 95% de casos de uso forenses
- UI robusta (Tkinter + fallback consola) - Funciona en cualquier entorno  
- Validación de archivos básica pero efectiva
- Memoria de sesión (LAST_DIR) - UX optimizada
- Código estable y confiable - 0 fallas conocidas

🚀 ROADMAP FUTURO (v2.0+):
Las siguientes mejoras están diferidas estratégicamente:
- Soporte CSV/TSV (cuando haya demanda real del usuario)
- Auto-detección de formato (cuando sea necesario)
- Manejo avanzado de encoding (UTF-8 actual es suficiente)
- Preview de datos (workflow actual no lo requiere)

📋 DECISIÓN ESTRATÉGICA (Oct 2025):
Sistema actual es PERFECTO para casos de uso reales. Las bitácoras forenses 
requieren análisis humano de estructura para mapeo correcto. "Lo perfecto 
es enemigo de lo bueno" - no optimizar lo que ya funciona excelentemente.

Ver docs/FILE_PROCESSOR_ESTADO_ACTUAL.md para análisis completo.

COMPORTAMIENTO TÉCNICO:
- Usa Tkinter para mostrar diálogos de selección.
- Si Tkinter no está disponible o el diálogo falla (TclError), cae a consola.
- Recuerda la última carpeta usada (variable global LAST_DIR) y la usa como initialdir.
- Devuelve rutas como str o None si el usuario cancela/ingresa inválido.
"""



# Última carpeta usada en este proceso (se mantiene en memoria)
LAST_DIR: Optional[str] = None

# Filtros de archivo para Excel
_EXCEL_FILETYPES = [("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]


def _console_prompt(msg: str, validator: Optional[Callable[[str], bool]] = None) -> Optional[str]:
    """
    Pide una ruta por consola. Devuelve la ruta válida o None si se cancela/ingresa inválida.
    """
    try:
        ruta = input(msg).strip()
    except Exception:
        return None
    if not ruta:
        return None
    if validator and not validator(ruta):
        print("[WARN] Ruta inválida. Operación cancelada.")
        return None
    return ruta


def _get_initialdir() -> str:
    """
    Determina la carpeta inicial para el diálogo: LAST_DIR o cwd.
    """
    return LAST_DIR or os.getcwd()


def seleccionar_archivo(titulo: str = "Seleccionar bitácora Excel") -> Optional[str]:
    """
    Abre un diálogo gráfico (Tkinter) para seleccionar un archivo Excel (.xlsx/.xls).
    Si Tkinter no está disponible o falla, solicita la ruta por consola.

    Args:
        titulo (str): Título del diálogo.
    Returns:
        Optional[str]: Ruta del archivo seleccionado o None si se cancela/ingresa inválido.
    """
    # Intento de GUI
    try:
        # Import diferido para no fallar en entornos sin Tk
        from tkinter import Tk, filedialog, TclError  # type: ignore
    except ImportError:
        # Fallback headless (sin GUI)
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta del archivo Excel (.xlsx/.xls) o presione Enter para cancelar: ",
            validator=lambda p: os.path.isfile(p) and os.path.splitext(p)[1].lower() in {".xlsx", ".xls"},
        )

    # GUI disponible
    try:
        global LAST_DIR
        initial = _get_initialdir()

        root = Tk()
        root.withdraw()
        filename = filedialog.askopenfilename(
            title=f"{titulo} (formatos .xlsx/.xls)",
            initialdir=initial,
            filetypes=_EXCEL_FILETYPES,
        )
        root.destroy()

        if not filename:
            return None  # cancelado

        # actualizar LAST_DIR
        try:
            LAST_DIR = os.path.dirname(filename) or LAST_DIR
        except Exception:
            pass

        return filename
    except TclError:
        # Fallback si el diálogo truena en tiempo de ejecución
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta del archivo Excel (.xlsx/.xls) o presione Enter para cancelar: ",
            validator=lambda p: os.path.isfile(p) and os.path.splitext(p)[1].lower() in {".xlsx", ".xls"},
        )


def seleccionar_carpeta(titulo: str = "Seleccionar carpeta destino") -> Optional[str]:
    """
    Abre un diálogo gráfico (Tkinter) para seleccionar una carpeta destino.
    Si Tkinter no está disponible o falla, solicita la ruta por consola.

    Args:
        titulo (str): Título del diálogo.
    Returns:
        Optional[str]: Ruta de la carpeta seleccionada o None si se cancela/ingresa inválida.
    """
    # Intento de GUI
    try:
        from tkinter import Tk, filedialog, TclError  # type: ignore
    except ImportError:
        # Fallback headless (sin GUI)
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta de la carpeta destino o presione Enter para cancelar: ",
            validator=lambda p: os.path.isdir(p),
        )

    # GUI disponible
    try:
        global LAST_DIR
        initial = _get_initialdir()

        root = Tk()
        root.withdraw()
        folder = filedialog.askdirectory(
            title=titulo,
            initialdir=initial,
        )
        root.destroy()

        if not folder:
            return None  # cancelado

        # actualizar LAST_DIR
        try:
            LAST_DIR = folder or LAST_DIR
        except Exception:
            pass

        return folder
    except TclError:
        # Fallback si el diálogo truena en tiempo de ejecución
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta de la carpeta destino o presione Enter para cancelar: ",
            validator=lambda p: os.path.isdir(p),
        )
