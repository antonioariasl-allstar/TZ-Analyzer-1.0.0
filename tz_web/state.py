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
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from tz_web.services import (
    AnalysisInProgressError,
    ArchivoNoProcesableError,
    CaseFileNotFoundError,
    CaseLoadError,
    CaseResult,
    FiltroTiempoSinRegistrosError,
    InvalidMappingError,
    OutputDirectoryError,
    SheetNotFoundError,
)
from tz_web.output_transaction import (
    InputIntegrityError,
    OutputCollisionError,
    OutputValidationError,
    TransactionError,
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
    # Modo 3 — mapeo manual (microbloque 2): etapas propias, más simples que
    # las 8 de bitácora (sin mapeo/QC/filtros); comparten el mismo mapeo fijo
    # etapa -> porcentaje y el mismo /status genérico, sin nombres en común
    # con las etapas de arriba.
    "preparando": 10,
    "generando_cartografia": 55,
    "generando_hashes": 80,
    "finalizando": 95,
    "completado": 100,
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
    "preparando": "Preparando registros y carpeta de salida",
    "generando_cartografia": "Generando cartografía (KMZ/KML)",
    "generando_hashes": "Calculando hashes de integridad",
    "finalizando": "Escribiendo log de ejecución",
    "completado": "Mapeo manual finalizado",
}

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

# ---------------------------------------------------------------------------
# Modo de análisis (sección 1 del microbloque Modo 2) — un único campo, no
# varios booleanos: "1" = bitácora completa, "2" = bitácora filtrada por
# tiempo, "3" = mapeo manual de antenas/ubicaciones (sin bitácora). El motor
# no conoce este campo; solo distingue qué pantallas recorre la capa web
# (ver tz_web.routes).
# ---------------------------------------------------------------------------

MODO_1 = "1"
MODO_2 = "2"
MODO_3 = "3"

# ---------------------------------------------------------------------------
# Carpetas de trabajo — nunca dentro del repositorio (sección 6/11/14).
# ---------------------------------------------------------------------------

UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "TZ_Analyzer_Web_Uploads")
_LOG_DIR = os.path.join(tempfile.gettempdir(), "TZ_Analyzer_Web_Logs")
ALLOWED_UPLOAD_EXTENSIONS: Tuple[str, ...] = (".xlsx",)
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
    InputIntegrityError,
    OutputCollisionError,
    OutputValidationError,
    TransactionError,
)

MSG_ANALYSIS_IN_PROGRESS = (
    "Hay un análisis en procesamiento. Espere a que finalice antes de iniciar "
    "o modificar otro análisis."
)

MSG_SHUTDOWN_PENDING = (
    "TZ Analyzer tiene un cierre pendiente y no puede iniciar un nuevo análisis."
)

# Motivos de rechazo de try_start_run_detailed() (sección 1 del MB5: mensaje
# de UI distinto segun la causa, sin que el llamador tenga que adivinarla
# comparando texto). "busy": ya hay otra sesión con un análisis activo.
# "shutdown_pending": tz_web.lifecycle está en CLOSE_WHEN_IDLE/SHUTTING_DOWN
# (ver set_run_start_guard más abajo) — no depende de is_any_run_active().
RUN_START_REJECTED_BUSY = "busy"
RUN_START_REJECTED_SHUTDOWN = "shutdown_pending"


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
# Código de error estructural (microajuste Modo 2) — pequeña señal separada
# del texto visible (``error_message``), para que la navegación de
# recuperación (p. ej. "Volver a revisar filtro temporal" en Resultados) no
# dependa de comparar contra un mensaje. No es un sistema general de
# excepciones: solo distingue los casos que la capa web necesita diferenciar
# hoy; una excepción de dominio sin código propio no obtiene ninguno (None).
# ---------------------------------------------------------------------------

ERROR_CODE_FILTRO_SIN_REGISTROS = "filtro_sin_registros"


def error_code_for(exc: BaseException) -> Optional[str]:
    """Código estructural pequeño asociado a ``exc``, o ``None`` si no
    corresponde a ninguno de los casos distinguidos."""
    if isinstance(exc, FiltroTiempoSinRegistrosError):
        return ERROR_CODE_FILTRO_SIN_REGISTROS
    return None


# ---------------------------------------------------------------------------
# Sesión de trabajo (sección 5) — un identificador aleatorio, estado en
# memoria, sin base de datos.
# ---------------------------------------------------------------------------


@dataclass
class Session:
    id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Modo activo (sección 1 del microbloque Modo 2).
    modo: str = MODO_1

    # Pantalla 1 — archivo
    temp_path: Optional[str] = None
    original_filename: Optional[str] = None
    upload_dir: Optional[str] = None
    # SHA-256 calculado una sola vez cuando la subida ya fue aceptada como
    # XLSX legible. El worker no analiza ``temp_path``: antes de arrancar
    # crea su propia copia y conserva debajo su ruta/digest efectivos.
    upload_sha256: Optional[str] = None
    input_snapshot_path: Optional[str] = None
    input_snapshot_sha256: Optional[str] = None
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
    # Campos del mapeo que la última validación (tz_web.routes._parse_mapping_form)
    # marcó como conflictivos (columna duplicada o valor faltante). Se usa
    # únicamente para resaltar/enfocar esos campos al re-mostrar el
    # formulario tras un error; no participa en la validación en sí, que
    # sigue siendo server-side.
    mapping_conflicts: List[str] = field(default_factory=list)
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
    # Tipo elegido en la Pantalla 1 (selección) del Filtro temporal de Modo 2,
    # antes de que la Pantalla 2 (parámetros) valide y confirme el filtro
    # completo en ``filtro_tiempo``. Permite mostrar la Pantalla 2 correcta y
    # que la Pantalla 1 recuerde la última elección al regresar a ella.
    filtro_tiempo_tipo: Optional[str] = None
    date_order_decision: str = "1"
    duration_unit_decision: str = "desconocida"
    qc_bloqueante_decision: str = "S"

    # Modo 3 — mapeo manual de antenas/ubicaciones (sin bitácora). Una
    # sesión de Modo 3 trabaja con un único tipo elegido ("antena" o
    # "punto_libre", ver tz_web.routes.MODO3_TIPOS_VALIDOS); modo3_registros
    # es la única fuente de verdad de los registros cargados — no se
    # duplica en ninguna otra estructura, y persiste durante toda la sesión
    # de análisis (sobrevive navegación atrás/adelante y edición) hasta que
    # se inicia deliberadamente un nuevo análisis (ver discard_session).
    modo3_tipo: Optional[str] = None
    modo3_registros: List[Dict[str, Any]] = field(default_factory=list)

    # Pantalla 4/5 — progreso y resultado
    status: str = STATUS_PENDING
    stage: Optional[str] = None
    stage_message: str = ""
    sequence: int = 0
    percent: int = 0
    result: Optional[CaseResult] = None
    error_message: Optional[str] = None
    # Señal estructural separada de error_message (ver error_code_for más
    # arriba): None cuando el fallo no tiene un código distinguido.
    error_code: Optional[str] = None
    task_started: bool = False
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


_SESSIONS: Dict[str, Session] = {}
_SESSIONS_LOCK = threading.RLock()
_RUNNING_SESSION_ID: Optional[str] = None
_RUNNING_LOCK = threading.RLock()

# Callbacks invocados (bajo _RUNNING_LOCK, ya reentrante) justo despues de
# liberar la reserva de ejecucion activa. Usado por tz_web.lifecycle (MB5)
# para completar un cierre CLOSE_WHEN_IDLE en cuanto el analisis en curso
# termina, sin que ese modulo duplique este lock ni tz_web.state conozca a
# tz_web.lifecycle (import en un solo sentido).
_ON_RUN_RELEASED: List[Callable[[], None]] = []

# Chequeo adicional evaluado, bajo el mismo _RUNNING_LOCK que reserva una
# ejecucion, antes de conceder try_start_run(). Registrado por
# tz_web.lifecycle (mismo sentido de import de arriba: este modulo no sabe
# qué es "lifecycle", solo que alguien puede vetar un arranque y por qué).
# Debe devolver None si el arranque esta permitido, o uno de los
# RUN_START_REJECTED_* si debe rechazarse. Al evaluarse dentro del mismo
# lock que la reserva, no hay ventana entre "¿puedo iniciar?" y "reservar":
# cualquier transicion a CLOSE_WHEN_IDLE/SHUTTING_DOWN (tz_web.lifecycle.
# request_shutdown) tambien adquiere este lock antes de cambiar de estado,
# asi que las dos decisiones quedan serializadas entre si.
_RUN_START_GUARD: Optional[Callable[[], Optional[str]]] = None


def register_on_run_released(callback: Callable[[], None]) -> None:
    """Registra ``callback`` para ejecutarse cada vez que se libera la
    reserva de ejecucion activa (exito, fallo o cancelacion del arranque)."""
    _ON_RUN_RELEASED.append(callback)


def set_run_start_guard(guard: Optional[Callable[[], Optional[str]]]) -> None:
    """Registra (o quita, con ``None``) el chequeo adicional de
    ``try_start_run_detailed``. Ver el comentario junto a ``_RUN_START_GUARD``."""
    global _RUN_START_GUARD
    with _RUNNING_LOCK:
        _RUN_START_GUARD = guard


def _notify_run_released() -> None:
    for callback in _ON_RUN_RELEASED:
        try:
            callback()
        except Exception:  # noqa: BLE001 - un callback no debe tumbar al worker
            pass


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

    Devuelve False si ya hay otra sesión con un análisis en curso, o si el
    chequeo adicional registrado vía ``set_run_start_guard`` rechaza el
    arranque (p. ej. cierre pendiente) — ver ``try_start_run_detailed`` para
    distinguir ambos motivos.
    """
    started, _reason = try_start_run_detailed(session_id)
    return started


def try_start_run_detailed(session_id: str) -> Tuple[bool, Optional[str]]:
    """Igual que ``try_start_run``, pero además informa el motivo del rechazo
    (uno de ``RUN_START_REJECTED_*``) para que la capa web pueda mostrar un
    mensaje preciso en vez de asumir siempre "análisis en curso".

    Protección de doble envío / segunda tarea simultánea en la capa web,
    complementaria al ``threading.Lock`` propio de
    ``tz_web.services.process_case`` (sección 9), más el veto de
    ``_RUN_START_GUARD`` — ambos chequeos y la reserva ocurren en una sola
    adquisición de ``_RUNNING_LOCK``, así que no hay ventana entre decidir y
    reservar.
    """
    global _RUNNING_SESSION_ID
    with _RUNNING_LOCK:
        if _RUNNING_SESSION_ID is not None:
            return False, RUN_START_REJECTED_BUSY
        if _RUN_START_GUARD is not None:
            rejection = _RUN_START_GUARD()
            if rejection is not None:
                return False, rejection
        _RUNNING_SESSION_ID = session_id
        return True, None


def finish_run(session_id: str) -> None:
    global _RUNNING_SESSION_ID
    with _RUNNING_LOCK:
        if _RUNNING_SESSION_ID == session_id:
            _RUNNING_SESSION_ID = None
            _notify_run_released()


@contextmanager
def terminal_run(session_id: str) -> Iterator[None]:
    """Hace atomica la transicion terminal respecto de mutaciones web.

    El worker completa resultado/error/estado dentro del mismo ``RLock`` que
    usa ``mutation_guard``. Si el polling observa el estado terminal antes de
    salir del bloque, cualquier POST de recuperacion espera hasta que la
    reserva global haya sido liberada en ``finally``.
    """
    global _RUNNING_SESSION_ID
    with _RUNNING_LOCK:
        try:
            yield
        finally:
            if _RUNNING_SESSION_ID == session_id:
                _RUNNING_SESSION_ID = None
                _notify_run_released()


def is_any_run_active() -> bool:
    with _RUNNING_LOCK:
        return _RUNNING_SESSION_ID is not None


@contextmanager
def run_lock() -> Iterator[None]:
    """Expone el lock de reserva de ejecucion para coordinar decisiones
    atomicas con ``is_any_run_active()`` desde otros modulos (p. ej.
    ``tz_web.lifecycle`` al decidir si un cierre solicitado debe aplicarse
    de inmediato o diferirse), sin duplicar el lock ni el estado que ya
    mantiene ``try_start_run``/``terminal_run``.
    """
    with _RUNNING_LOCK:
        yield


@contextmanager
def mutation_guard() -> Iterator[bool]:
    """Serializa una mutación destructiva contra el inicio de una corrida.

    El lock se conserva durante toda la mutación. Así, comprobar que no hay
    una ejecución activa y modificar/descartar el caso forman una sola
    operación respecto de ``try_start_run``; no queda una ventana entre un
    ``is_any_run_active()`` y el cambio de estado.

    El valor producido es ``False`` cuando ya existe una reserva activa. En
    ese caso el llamador debe salir sin tocar sesión, input ni configuración.
    """
    with _RUNNING_LOCK:
        yield _RUNNING_SESSION_ID is None


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
