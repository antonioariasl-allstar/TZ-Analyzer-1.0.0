"""tz_web.server — servidor WSGI de producción gestionado (MICROBLOQUE 5,
AUD-03). A diferencia del resto de tests/web, aquí sí se levanta un
Waitress real en 127.0.0.1:puerto-efímero, porque son precisamente el bind,
la disponibilidad real y el apagado desde otro hilo lo que hay que probar —
un ``test_client()`` de Flask no pasa por ningún socket real."""

from __future__ import annotations

import socket

import pytest

from tz_web import instance, lifecycle, state
from tz_web.app import create_app
from tz_web.server import ManagedServer, ServerStartError

TOKEN = "token-servidor-real-abcdef"


@pytest.fixture()
def managed_server(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    app = create_app(instance_token=TOKEN, instance_id="instancia-servidor")
    server = ManagedServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        yield server
    finally:
        server.stop()
        server.wait_for_shutdown(timeout=5)
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 17. Bind únicamente en 127.0.0.1.
# ---------------------------------------------------------------------------


def test_bind_unicamente_en_127_0_0_1(managed_server):
    assert managed_server._server.effective_host == "127.0.0.1"
    assert managed_server.port > 0


# ---------------------------------------------------------------------------
# 18. Servidor de producción real, no el servidor de desarrollo de Werkzeug
# (que sí tiene reloader/debug propios): el objeto interno viene del
# paquete ``waitress`` y no expone ``use_reloader``.
# ---------------------------------------------------------------------------


def test_servidor_de_produccion_no_es_werkzeug_dev_server(managed_server):
    assert type(managed_server._server).__module__.startswith("waitress")
    assert not hasattr(managed_server._server, "use_reloader")


# ---------------------------------------------------------------------------
# 19. El navegador solo debe abrir tras confirmar disponibilidad real.
# ---------------------------------------------------------------------------


def test_wait_until_ready_confirma_disponibilidad_real(managed_server):
    assert managed_server.wait_until_ready(TOKEN, attempts=50, delay=0.05) is True
    data = instance.check_health(managed_server.port, TOKEN)
    assert data is not None
    assert data["instance_id"] == "instancia-servidor"


def test_wait_until_ready_falla_con_token_incorrecto(managed_server):
    assert managed_server.wait_until_ready("token-incorrecto", attempts=5, delay=0.02) is False


# ---------------------------------------------------------------------------
# 20. Un fallo al abrir el navegador (aquí, un token/URL inválidos desde el
# punto de vista del *cliente* de health) no debe tumbar el servidor: sigue
# respondiendo correctamente después.
# ---------------------------------------------------------------------------


def test_fallo_de_readiness_no_tumba_el_servidor(managed_server):
    assert instance.check_health(managed_server.port, "token-malo") is None
    # El servidor real sigue en pie y responde con el token correcto.
    assert instance.check_health(managed_server.port, TOKEN) is not None


# ---------------------------------------------------------------------------
# Shutdown real: cerrar detiene el servidor de verdad (deja de responder).
# ---------------------------------------------------------------------------


def test_stop_detiene_el_servidor_de_verdad(managed_server):
    assert managed_server.wait_until_ready(TOKEN) is True
    managed_server.stop()
    managed_server.wait_for_shutdown(timeout=5)
    assert instance.check_health(managed_server.port, TOKEN, timeout=0.5) is None


# ---------------------------------------------------------------------------
# 21. Fallo de arranque del WSGI (puerto ya ocupado) se reporta como error
# claro y no deja hilos ni servidor a medio construir.
# ---------------------------------------------------------------------------


def test_fallo_de_arranque_por_puerto_ocupado_limpia_estado(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads2"))
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    occupied_port = blocker.getsockname()[1]
    try:
        app = create_app(instance_token="t", instance_id="i")
        server = ManagedServer(app, host="127.0.0.1", port=occupied_port)
        with pytest.raises(ServerStartError):
            server.start()
        # No quedó ningún hilo de servidor corriendo tras el fallo.
        assert server._thread is None
    finally:
        blocker.close()
