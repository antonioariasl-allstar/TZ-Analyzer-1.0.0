"""Stress test dirigido a la carrera de cierre de Waitress en Windows
(``WinError 10038``) diagnosticada en este microbloque.

Causa raíz confirmada leyendo el código real de Waitress 3.0.2 (ver el
docstring de ``ManagedServer._drain_and_close`` en ``tz_web/server.py``):
un hilo worker del pool de tareas puede llamar ``server.pull_trigger()``
(al terminar de despachar una petición, o al escribir una respuesta grande)
exactamente cuando el hilo del bucle de aceptación está cerrando ese mismo
trigger — sin ninguna sincronización propia de Waitress entre ambos casos.
El escenario que más lo dispara: heartbeats y pedidos estáticos
concurrentes en el instante del cierre, que es justo lo que este test
reproduce deliberadamente y muchas veces seguidas.

Este test NO parchea ni modifica código de Waitress: solo ejercita el
servidor real (``tz_web.server.ManagedServer``) bajo carga concurrente real,
disparando el cierre por el mismo camino de producción
(``POST /internal/shutdown`` -> ``tz_web.lifecycle.request_shutdown`` ->
hook -> ``ManagedServer.stop``), y confirma tres cosas en cada repetición:
1. no queda ningún backend vivo tras el cierre;
2. no queda ninguna excepción no controlada en ningún hilo;
3. el logger ``"waitress"`` (donde antes del fix de este microbloque
   aparecía ``WinError 10038``, atrapado y logueado por Waitress mismo
   dentro de ``HTTPChannel.service()``) no registra ningún error.

Solo controla procesos/hilos creados por el propio test — nunca mata
procesos ni navegadores ajenos.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from typing import List

import pytest

from tz_web import instance, lifecycle, state
from tz_web.app import create_app
from tz_web.server import ManagedServer

TOKEN = "token-stress-cierre-0123456789abcdef"
REPETITIONS = 12
HAMMER_THREADS = 6
HAMMER_BURST_BEFORE_SECONDS = 0.3
HAMMER_BURST_AFTER_SECONDS = 0.3


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    yield
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


class _WaitressErrorCapture(logging.Handler):
    """Registra cualquier log >= WARNING del logger 'waitress' (el que usan
    HTTPChannel/ThreadedTaskDispatcher internamente) durante el test."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _hammer(base_url: str, stop_event: threading.Event) -> None:
    """Bombardea heartbeat (POST autenticado) y un recurso estático (GET)
    en bucle. Los errores de conexión son esperados en cuanto el servidor
    empieza a cerrar — el punto del test es que eso nunca deje una
    excepción no controlada en otro hilo ni un ``ERROR [waitress]``."""
    heartbeat_headers = {"X-TZ-Token": TOKEN}
    while not stop_event.is_set():
        try:
            req = urllib.request.Request(
                base_url + "/internal/heartbeat",
                data=b"",
                headers=heartbeat_headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1) as resp:
                resp.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        try:
            with urllib.request.urlopen(base_url + "/static/css/app.css", timeout=1) as resp:
                resp.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass


def test_cierre_bajo_carga_concurrente_no_deja_excepcion_ni_backend_vivo():
    waitress_logger = logging.getLogger("waitress")
    capture = _WaitressErrorCapture()
    waitress_logger.addHandler(capture)

    uncaught = []
    original_hook = threading.excepthook

    def _hook(args):
        uncaught.append(args)
        original_hook(args)

    threading.excepthook = _hook

    try:
        for i in range(REPETITIONS):
            app = create_app(instance_token=TOKEN, instance_id=f"stress-{i}")
            server = ManagedServer(app, host="127.0.0.1", port=0)
            server.start()
            assert server.wait_until_ready(TOKEN, attempts=50, delay=0.05) is True
            lifecycle.set_shutdown_hook(server.stop)

            base_url = f"http://127.0.0.1:{server.port}"
            stop_event = threading.Event()
            hammer_threads = [
                threading.Thread(target=_hammer, args=(base_url, stop_event), daemon=True)
                for _ in range(HAMMER_THREADS)
            ]
            for t in hammer_threads:
                t.start()

            time.sleep(HAMMER_BURST_BEFORE_SECONDS)

            # Mismo camino que produccion: el pedido HTTP real dispara el
            # cierre desde dentro de un hilo worker de Waitress.
            shutdown_req = urllib.request.Request(
                base_url + "/internal/shutdown",
                data=b"",
                headers={"X-TZ-Token": TOKEN},
                method="POST",
            )
            with urllib.request.urlopen(shutdown_req, timeout=2) as resp:
                assert resp.status == 200

            # Los hilos siguen martillando durante la ventana real de
            # drenado/cierre -- el momento que importa reproducir.
            time.sleep(HAMMER_BURST_AFTER_SECONDS)
            stop_event.set()
            for t in hammer_threads:
                t.join(timeout=2)

            server.wait_for_shutdown(timeout=5)
            assert not server.is_running(), f"repetición {i}: el servidor no confirmó su cierre"
            assert instance.check_health(server.port, TOKEN, timeout=0.3) is None, (
                f"repetición {i}: el backend sigue respondiendo tras el cierre"
            )
            lifecycle.reset_for_tests()
    finally:
        threading.excepthook = original_hook
        waitress_logger.removeHandler(capture)

    assert not uncaught, "quedó una excepción no controlada en un hilo durante el cierre bajo carga: " + "; ".join(
        f"{a.thread}: {a.exc_type}: {a.exc_value}" for a in uncaught
    )
    error_records = [r for r in capture.records if r.levelno >= logging.ERROR]
    assert not error_records, (
        "el logger 'waitress' registró un error durante el cierre bajo carga (posible "
        "WinError 10038 todavía reproducible): "
        + "; ".join(r.getMessage() for r in error_records)
    )
