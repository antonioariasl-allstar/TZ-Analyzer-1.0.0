"""tz_web.lifecycle — ciclo de vida del backend local (MICROBLOQUE 5).

Resuelve AUD-01 (lifecycle/shutdown): un pequeño estado thread-safe con tres
valores (``RUNNING`` / ``CLOSE_WHEN_IDLE`` / ``SHUTTING_DOWN``), un
heartbeat del navegador con timeout configurable, y un "hook" de apagado que
el launcher (``tz_launcher.py``) conecta al servidor WSGI real. Este modulo
no sabe nada de Waitress ni de Flask: solo decide *cuándo* debe cerrarse el
proceso, nunca *cómo*.

Invariante central (sección M del encargo): un cierre nunca debe matar un
analisis activo. Por eso toda decision que involucra "¿hay un analisis
activo?" se toma bajo ``tz_web.state.run_lock()`` — el mismo lock que ya
serializa el inicio/fin de una corrida — en vez de duplicar esa señal aquí.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from tz_web import state

RUNNING = "RUNNING"
CLOSE_WHEN_IDLE = "CLOSE_WHEN_IDLE"
SHUTTING_DOWN = "SHUTTING_DOWN"

# Centralizado aquí (sección H del encargo: nada de magic numbers dispersos).
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 15 * 60
DEFAULT_WATCHDOG_INTERVAL_SECONDS = 30.0

_LOGGER = logging.getLogger("tz_web.lifecycle")

_LOCK = threading.RLock()
_STATE = RUNNING
_LAST_HEARTBEAT: float = time.time()
_SHUTDOWN_REASON: Optional[str] = None
_SHUTDOWN_HOOK: Optional[Callable[[], None]] = None
_HEARTBEAT_TIMEOUT_SECONDS = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS

_WATCHDOG_STOP: Optional[threading.Event] = None
_WATCHDOG_THREAD: Optional[threading.Thread] = None


def get_state() -> str:
    with _LOCK:
        return _STATE


def get_shutdown_reason() -> Optional[str]:
    with _LOCK:
        return _SHUTDOWN_REASON


def set_shutdown_hook(hook: Optional[Callable[[], None]]) -> None:
    """Conecta la accion real de apagado (p. ej. ``ManagedServer.stop``).

    Sin hook registrado, una transicion a SHUTTING_DOWN solo cambia el
    estado — util en pruebas que no levantan un servidor real.
    """
    global _SHUTDOWN_HOOK
    with _LOCK:
        _SHUTDOWN_HOOK = hook


def set_heartbeat_timeout(seconds: float) -> None:
    global _HEARTBEAT_TIMEOUT_SECONDS
    with _LOCK:
        _HEARTBEAT_TIMEOUT_SECONDS = seconds


def get_heartbeat_timeout() -> float:
    with _LOCK:
        return _HEARTBEAT_TIMEOUT_SECONDS


def get_last_heartbeat() -> float:
    with _LOCK:
        return _LAST_HEARTBEAT


def record_heartbeat() -> None:
    global _LAST_HEARTBEAT
    with _LOCK:
        _LAST_HEARTBEAT = time.time()


def reset_for_tests() -> None:
    """Reinicia todo el estado del modulo. Solo para aislar pruebas: el
    modulo es deliberadamente un singleton (un solo backend por proceso)."""
    stop_watchdog()
    global _STATE, _LAST_HEARTBEAT, _SHUTDOWN_REASON, _SHUTDOWN_HOOK, _HEARTBEAT_TIMEOUT_SECONDS
    with _LOCK:
        _STATE = RUNNING
        _LAST_HEARTBEAT = time.time()
        _SHUTDOWN_REASON = None
        _SHUTDOWN_HOOK = None
        _HEARTBEAT_TIMEOUT_SECONDS = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS


def _do_shutdown_locked(reason: str) -> None:
    """Ejecuta la transicion terminal. El llamador debe sostener ``_LOCK``.

    En este punto ya no queda ningun analisis activo (todo llamador lo
    confirma bajo ``state.run_lock()`` antes de llegar aqui — ver
    ``request_shutdown``, ``on_run_finished`` y ``_watchdog_loop``), asi que
    es el momento seguro y unico de convergencia para la limpieza sincrona
    de temporales de esta instancia, antes de detener el servidor.
    """
    global _STATE, _SHUTDOWN_REASON
    if _STATE == SHUTTING_DOWN:
        return
    _STATE = SHUTTING_DOWN
    _SHUTDOWN_REASON = reason
    _LOGGER.info("shutdown iniciado (motivo=%s)", reason)
    try:
        state.cleanup_session_uploads_on_shutdown()
    except Exception:
        _LOGGER.exception("fallo inesperado durante la limpieza de temporales al apagar")
    hook = _SHUTDOWN_HOOK
    if hook is not None:
        try:
            hook()
        except Exception:
            _LOGGER.exception("fallo al ejecutar el hook de apagado")


def request_shutdown(reason: str) -> str:
    """Solicita el cierre del backend. Devuelve el estado resultante.

    Con un analisis activo, difiere a CLOSE_WHEN_IDLE (se completa solo via
    ``on_run_finished`` cuando ese analisis termine). Sin analisis activo,
    cierra de inmediato. La comprobacion de "analisis activo" y el cambio de
    estado ocurren bajo el mismo lock de reserva de ``tz_web.state`` para
    que no quede una ventana entre comprobar y decidir (evita la carrera con
    un nuevo analisis arrancando justo en ese instante).
    """
    with state.run_lock():
        with _LOCK:
            if _STATE == SHUTTING_DOWN:
                return _STATE
            if state.is_any_run_active():
                _set_close_when_idle_locked(reason)
                return _STATE
            _do_shutdown_locked(reason)
            return _STATE


def _set_close_when_idle_locked(reason: str) -> None:
    global _STATE, _SHUTDOWN_REASON
    if _STATE == RUNNING:
        _LOGGER.info("cierre diferido a CLOSE_WHEN_IDLE (motivo=%s)", reason)
    _STATE = CLOSE_WHEN_IDLE
    _SHUTDOWN_REASON = reason


def _run_start_guard() -> Optional[str]:
    """Veta ``state.try_start_run_detailed`` fuera de RUNNING.

    Registrado vía ``state.set_run_start_guard`` y evaluado por ese módulo
    dentro de la misma adquisición de ``_RUNNING_LOCK`` que la reserva de
    ejecución (ver el comentario en ``tz_web/state.py``) — por eso este
    chequeo solo necesita leer ``_STATE`` bajo el lock local de este módulo,
    sin volver a tomar ``state.run_lock()``: quien nos llamó ya lo sostiene,
    y ``request_shutdown``/el watchdog, que sí escriben ``_STATE``, también
    lo adquieren antes de tocarlo, así que no queda ventana entre "¿puedo
    iniciar?" y una transición a CLOSE_WHEN_IDLE/SHUTTING_DOWN concurrente.
    """
    with _LOCK:
        if _STATE == RUNNING:
            return None
        return state.RUN_START_REJECTED_SHUTDOWN


def on_run_finished() -> None:
    """Registrado en ``tz_web.state.register_on_run_released`` (ver
    ``tz_web/app.py``). Si habia un cierre diferido y ya no queda ningun
    analisis activo, completa el cierre. Se invoca ya bajo
    ``state.run_lock()`` (el propio ``terminal_run``/``finish_run``), asi
    que aqui solo hace falta el lock de este modulo.
    """
    with _LOCK:
        if _STATE == CLOSE_WHEN_IDLE and not state.is_any_run_active():
            _do_shutdown_locked(_SHUTDOWN_REASON or "analysis_finished")


def _watchdog_loop(stop_event: threading.Event, interval: float) -> None:
    while not stop_event.wait(interval):
        with state.run_lock():
            with _LOCK:
                if _STATE == SHUTTING_DOWN:
                    return
                idle_for = time.time() - _LAST_HEARTBEAT
                if idle_for < _HEARTBEAT_TIMEOUT_SECONDS:
                    continue
                if state.is_any_run_active():
                    # Nunca cerrar por timeout con un analisis activo
                    # (sección M): se completa via on_run_finished() al
                    # terminar, igual que un cierre explicito pedido a
                    # mitad de un analisis.
                    if _STATE != CLOSE_WHEN_IDLE:
                        _set_close_when_idle_locked("heartbeat_timeout")
                    continue
                _do_shutdown_locked("heartbeat_timeout")
                return


def start_watchdog(interval: float = DEFAULT_WATCHDOG_INTERVAL_SECONDS) -> None:
    """Arranca el hilo que vigila el heartbeat del navegador. Idempotente:
    si ya hay un watchdog vivo, no arranca uno segundo."""
    global _WATCHDOG_STOP, _WATCHDOG_THREAD
    with _LOCK:
        if _WATCHDOG_THREAD is not None and _WATCHDOG_THREAD.is_alive():
            return
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_watchdog_loop,
            args=(stop_event, interval),
            daemon=True,
            name="tz-lifecycle-watchdog",
        )
        _WATCHDOG_STOP = stop_event
        _WATCHDOG_THREAD = thread
    thread.start()


def stop_watchdog() -> None:
    global _WATCHDOG_STOP, _WATCHDOG_THREAD
    with _LOCK:
        stop_event = _WATCHDOG_STOP
        thread = _WATCHDOG_THREAD
        _WATCHDOG_STOP = None
        _WATCHDOG_THREAD = None
    if stop_event is not None:
        stop_event.set()
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=2.0)


# Un solo registro por proceso: el modulo se importa una sola vez (cache de
# import de Python), asi que esto no duplica el callback aunque create_app()
# se llame muchas veces (como hacen las pruebas).
state.register_on_run_released(on_run_finished)
state.set_run_start_guard(_run_start_guard)
