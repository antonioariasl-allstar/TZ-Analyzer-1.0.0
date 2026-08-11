"""tz_web.state — sesión de trabajo en memoria (Fase 2 Web).

La aplicación es local y de un solo usuario, así que el estado de cada
"caso" en curso (archivo subido, hoja, mapeo, opciones, progreso, resultado)
vive únicamente en memoria del proceso, indexado por un identificador
aleatorio de sesión (``Session.id``). No hay base de datos ni cookies con
datos sensibles: la cookie de Flask solo guarda ese identificador.

También centraliza:
- el mapeo etapa -> porcentaje fijo (sección 10 del encargo: nunca inventar
  precisión falsa, solo los 8 valores fijos correspondientes a las 8 etapas
  reales de ``process_case()``);
- la traducción de excepciones de dominio a mensajes comprensibles para el
  usuario (sección 11), con el traceback completo siempre registrado en un
  log técnico fuera del repositorio (nunca dentro de ``TZ-Analyzer-1.0.0``);
- la limpieza de archivos temporales de subida (al iniciar la app y al
  terminar/abandonar una sesión).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tz_web.services import (
    AnalysisInProgressError,
    ArchivoNoProcesableError,
    CaseFileNotFoundError,
    CaseLoadError,
    CaseResult,
    InvalidMappingError,
    OutputDirectoryError,
    SheetNotFoundError,
)

# ---------------------------------------------------------------------------
# Progreso — mapeo fijo y transparente de las 8 etapas reales de
# process_case() a un porcentaje aproximado (sección 10).
# ---------------------------------------------------------------------------

STAGE_PERCENT: Dict[str, int] = {
    "validando_entrada": 5,
    "cargando_archivo": 15,
    "aplicando_mapeo": 30,
    "normalizando_y_qc": 45,
    "aplicando_filtros": 60,
    "generando_productos": 80,
    "verificando_resultados": 95,
    "finalizado": 100,
}

STAGE_LABELS: Dict[str, str] = {
    "validando_entrada": "Validando archivo, hoja y carpeta de salida",
    "cargando_archivo": "Cargando archivo",
    "aplicando_mapeo": "Aplicando mapeo de columnas",
    "normalizando_y_qc": "Normalizando fecha/hora y ejecutando control de calidad",
    "aplicando_filtros": "Aplicando filtros temporales",
    "generando_productos": "Generando HTML, KMZ y hashes",
    "verificando_resultados": "Verificando resultados generados",
    "finalizado": "Análisis finalizado",
}

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# ---------------------------------------------------------------------------
# Carpetas de trabajo — nunca dentro del repositorio (sección 6/11/14).
# ---------------------------------------------------------------------------

UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "TZ_Analyzer_Web_Uploads")
_LOG_DIR = os.path.join(tempfile.gettempdir(), "TZ_Analyzer_Web_Logs")
ALLOWED_UPLOAD_EXTENSIONS: Tuple[str, ...] = (".xlsx", ".xls")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB (sección 4, límite inicial configurable)
_STALE_UPLOAD_MAX_AGE_SECONDS = 24 * 60 * 60  # 24h

_TECH_LOGGER = logging.getLogger("tz_web.technical")


def _ensure_technical_logger() -> logging.Logger:
    """Configura (una sola vez) el logger técnico fuera del repositorio."""
    if not _TECH_LOGGER.handlers:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = logging.FileHandler(
            os.path.join(_LOG_DIR, "tz_web_technical.log"), encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _TECH_LOGGER.addHandler(handler)
        _TECH_LOGGER.setLevel(logging.INFO)
    return _TECH_LOGGER


def log_technical_error(context: str, exc: BaseException) -> None:
    """Registra el traceback completo en el log técnico; nunca lo muestra al usuario."""
    logger = _ensure_technical_logger()
    detalle = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("%s: %s\n%s", context, exc, detalle)


# ---------------------------------------------------------------------------
# Traducción de errores de dominio (sección 11) — nunca traceback al usuario.
# ---------------------------------------------------------------------------

_KNOWN_DOMAIN_EXCEPTIONS: Tuple[type, ...] = (
    CaseFileNotFoundError,
    SheetNotFoundError,
    CaseLoadError,
    InvalidMappingError,
    OutputDirectoryError,
    AnalysisInProgressError,
    ArchivoNoProcesableError,
)

MSG_ANALYSIS_IN_PROGRESS = (
    "Ya hay un análisis en ejecución; espere a que finalice antes de iniciar otro."
)


def translate_error(exc: BaseException) -> str:
    """Traduce una excepción a un mensaje comprensible para el usuario.

    Las excepciones de dominio (``_KNOWN_DOMAIN_EXCEPTIONS``) ya se lanzan
    con un mensaje curado, sin detalles técnicos ni traceback (ver sus
    puntos de ``raise`` en ``tz_web.services``); se muestran tal cual.
    Cualquier excepción no reconocida cae en un mensaje genérico: nunca se
    expone el texto crudo de un error inesperado (podría filtrar detalles
    internos), y su traceback completo solo llega al log técnico
    (``log_technical_error``), nunca al usuario.
    """
    if isinstance(exc, _KNOWN_DOMAIN_EXCEPTIONS):
        return str(exc).strip() or "Ocurrió un problema conocido durante el análisis."
    return "Ocurrió un error inesperado durante el análisis. Revise el registro técnico para más detalle."


# ---------------------------------------------------------------------------
# Sesión de trabajo (sección 5) — un identificador aleatorio, estado en
# memoria, sin base de datos.
# ---------------------------------------------------------------------------


@dataclass
class Session:
    id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Pantalla 1 — archivo
    temp_path: Optional[str] = None
    original_filename: Optional[str] = None
    upload_dir: Optional[str] = None
    available_sheets: List[str] = field(default_factory=list)
    sheet: Optional[str] = None

    # Pantalla 2 — mapeo
    columns: List[str] = field(default_factory=list)
    samples: Dict[str, List[str]] = field(default_factory=dict)
    mapping: Optional[Dict[str, Tuple[str, Any]]] = None
    mapping_draft: Optional[Dict[str, Tuple[str, Any]]] = None
    # "form" -> pantalla de edición (grupos paginados); "review" -> tabla de
    # revisión horizontal. Independiente de si mapping_draft tiene datos: al
    # pulsar "Volver a editar" el borrador se conserva intacto y solo cambia
    # esta vista (ver mapping_edit en tz_web.routes).
    mapping_stage: str = "form"
    identity_overrides: Dict[str, str] = field(default_factory=dict)
    capabilities_preview: Optional[Dict[str, Any]] = None

    # Pantalla 3 — configuración
    carpeta_salida: Optional[str] = None
    top_antenas: Optional[int] = None
    top_contactos: Optional[int] = None
    color_hex: Optional[str] = None
    solo_kmz: Optional[bool] = None
    kml_opcional: bool = False
    output_base_name: Optional[str] = None
    tipo_bitacora: str = ""
    filtro_tiempo: Optional[Dict[str, Optional[str]]] = None
    date_order_decision: str = "1"
    duration_unit_decision: str = "desconocida"
    qc_bloqueante_decision: str = "S"

    # Pantalla 4/5 — progreso y resultado
    status: str = STATUS_PENDING
    stage: Optional[str] = None
    stage_message: str = ""
    sequence: int = 0
    percent: int = 0
    result: Optional[CaseResult] = None
    error_message: Optional[str] = None
    task_started: bool = False
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


_SESSIONS: Dict[str, Session] = {}
_SESSIONS_LOCK = threading.RLock()
_RUNNING_SESSION_ID: Optional[str] = None
_RUNNING_LOCK = threading.RLock()


def create_session() -> Session:
    session = Session(id=uuid.uuid4().hex)
    with _SESSIONS_LOCK:
        _SESSIONS[session.id] = session
    return session


def get_session(session_id: Optional[str]) -> Optional[Session]:
    if not session_id:
        return None
    with _SESSIONS_LOCK:
        return _SESSIONS.get(session_id)


def touch(session: Session) -> None:
    session.updated_at = time.time()


def try_start_run(session_id: str) -> bool:
    """Reserva el "turno" de ejecución para ``session_id``.

    Devuelve False si ya hay otra sesión con un análisis en curso —
    protección de doble envío / segunda tarea simultánea en la capa web,
    complementaria al ``threading.Lock`` propio de
    ``tz_web.services.process_case`` (sección 9).
    """
    global _RUNNING_SESSION_ID
    with _RUNNING_LOCK:
        if _RUNNING_SESSION_ID is not None:
            return False
        _RUNNING_SESSION_ID = session_id
        return True


def finish_run(session_id: str) -> None:
    global _RUNNING_SESSION_ID
    with _RUNNING_LOCK:
        if _RUNNING_SESSION_ID == session_id:
            _RUNNING_SESSION_ID = None


def is_any_run_active() -> bool:
    with _RUNNING_LOCK:
        return _RUNNING_SESSION_ID is not None


def discard_session(session_id: str) -> None:
    """Elimina la sesión y limpia su archivo temporal de subida, si existe."""
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(session_id, None)
    if session is not None:
        _cleanup_upload_dir(session.upload_dir)


def clear_uploaded_file(session: Session) -> None:
    """Elimina de forma segura el archivo temporal de ``session``, sin
    eliminar la sesión/case_id activa (a diferencia de ``discard_session``).

    Usado por la acción "Cambiar archivo" y por una nueva subida que
    reemplaza una anterior de la misma sesión.
    """
    _cleanup_upload_dir(session.upload_dir)


def _cleanup_upload_dir(upload_dir: Optional[str]) -> None:
    if not upload_dir:
        return
    try:
        if os.path.isdir(upload_dir) and os.path.commonpath(
            [os.path.abspath(upload_dir), os.path.abspath(UPLOAD_ROOT)]
        ) == os.path.abspath(UPLOAD_ROOT):
            shutil.rmtree(upload_dir, ignore_errors=True)
    except (OSError, ValueError):
        pass


def ensure_writable_dir(path: str) -> str:
    """Crea ``path`` si hace falta y confirma que es escribible.

    ``tz_core.bitacora_io.ensure_dir`` solo crea la carpeta; aquí se agrega
    una escritura de prueba (archivo temporal que se borra de inmediato)
    porque la carpeta puede existir pero no ser escribible (permisos), lo
    que ``ensure_dir`` por sí solo no detectaría (sección 8).
    """
    from tz_core.bitacora_io import ensure_dir

    abs_path = ensure_dir(path)
    probe = os.path.join(abs_path, f".tz_web_write_test_{uuid.uuid4().hex}")
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write("ok")
    os.remove(probe)
    return abs_path


def cleanup_stale_uploads(max_age_seconds: int = _STALE_UPLOAD_MAX_AGE_SECONDS) -> None:
    """Limpia temporales de subidas antiguas al iniciar la app (sección 5/14).

    Best-effort: cualquier error de E/O se ignora, nunca debe impedir el
    arranque de la aplicación.
    """
    if not os.path.isdir(UPLOAD_ROOT):
        return
    now = time.time()
    try:
        for name in os.listdir(UPLOAD_ROOT):
            path = os.path.join(UPLOAD_ROOT, name)
            try:
                age = now - os.path.getmtime(path)
                if age > max_age_seconds:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
            except OSError:
                continue
    except OSError:
        pass
