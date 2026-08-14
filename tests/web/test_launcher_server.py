"""tz_web.server — servidor WSGI de producción gestionado (MICROBLOQUE 5,
AUD-03). A diferencia del resto de tests/web, aquí sí se levanta un
Waitress real en 127.0.0.1:puerto-efímero, porque son precisamente el bind,
la disponibilidad real y el apagado desde otro hilo lo que hay que probar —
un ``test_client()`` de Flask no pasa por ningún socket real."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from tz_core.folder_dialog import FolderDialogInterruptedError
from tz_web import instance, lifecycle, routes, state
from tz_web.app import create_app
from tz_web.server import ManagedServer, ServerStartError

TOKEN = "token-servidor-real-abcdef"


def _session_cookie(server: ManagedServer, case_id: str) -> str:
    app = server._app
    serializer = app.session_interface.get_signing_serializer(app)
    assert serializer is not None
    value = serializer.dumps({"case_id": case_id})
    return f"{app.config['SESSION_COOKIE_NAME']}={value}"


def _request_json(
    server: ManagedServer,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    cookie: str | None = None,
    timeout: float = 3.0,
):
    headers = {}
    if token is not None:
        headers["X-TZ-Token"] = token
    if cookie is not None:
        headers["Cookie"] = cookie
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.port}{path}",
        data=b"" if method == "POST" else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            body = exc.read()
        finally:
            exc.close()
    return status, json.loads(body.decode("utf-8"))


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


def test_selector_retenido_no_bloquea_health_heartbeat_ni_shutdown_real(
    managed_server, monkeypatch, tmp_path
):
    """Un worker espera al picker; otros sirven lifecycle y cierran limpio."""
    assert managed_server.wait_until_ready(TOKEN, attempts=50, delay=0.01) is True

    case = state.create_session()
    case.modo = state.MODO_1
    anterior = tmp_path / "seleccion-anterior"
    anterior.mkdir()
    case.carpeta_salida = str(anterior)
    cookie = _session_cookie(managed_server, case.id)

    picker_entered = threading.Event()
    release_picker = threading.Event()
    cancellation_seen = threading.Event()
    selector_result = {}
    selector_errors = []

    def _blocking_pick(*, initial_dir, cancel_requested):
        assert initial_dir == str(anterior)
        assert callable(cancel_requested)
        assert cancel_requested() is False
        picker_entered.set()
        # Imita el polling corto del Popen real: lifecycle basta para
        # interrumpirlo; el hook no necesita tocar el mutex del selector.
        while not cancel_requested():
            if release_picker.wait(timeout=0.01):
                raise AssertionError("el test libero el picker antes del shutdown")
        cancellation_seen.set()
        raise FolderDialogInterruptedError("shutdown solicitado durante el selector")

    def _shutdown_hook():
        # Produccion conserva managed.stop como unico hook terminal.
        managed_server.stop()

    def _post_selector():
        try:
            selector_result["response"] = _request_json(
                managed_server,
                "/output-folder/select",
                method="POST",
                cookie=cookie,
                timeout=5,
            )
        except BaseException as exc:  # noqa: BLE001 - se propaga al hilo principal
            selector_errors.append(exc)

    monkeypatch.setattr(routes, "pick_folder", _blocking_pick)
    lifecycle.set_shutdown_hook(_shutdown_hook)
    selector_thread = threading.Thread(
        target=_post_selector,
        name="test-real-waitress-selector",
    )
    selector_thread.start()
    try:
        assert picker_entered.wait(timeout=3), "Waitress no despachó el selector"

        health_status, health = _request_json(
            managed_server,
            "/internal/health",
            token=TOKEN,
        )
        assert health_status == 200
        assert health["lifecycle_state"] == lifecycle.RUNNING

        heartbeat_status, heartbeat = _request_json(
            managed_server,
            "/internal/heartbeat",
            method="POST",
            token=TOKEN,
        )
        assert heartbeat_status == 200
        assert heartbeat["ok"] is True
        assert release_picker.is_set() is False

        shutdown_status, shutdown = _request_json(
            managed_server,
            "/internal/shutdown",
            method="POST",
            token=TOKEN,
            timeout=5,
        )
        assert shutdown_status == 200
        assert shutdown["lifecycle_state"] == lifecycle.SHUTTING_DOWN
    finally:
        selector_thread.join(timeout=5)
        # Red de seguridad del propio test si fallo antes de pedir shutdown.
        if selector_thread.is_alive():
            release_picker.set()
            selector_thread.join(timeout=5)

    assert selector_thread.is_alive() is False
    assert selector_errors == []
    assert cancellation_seen.is_set() is True
    assert selector_result["response"] == (
        409,
        {
            "status": "error",
            "message": state.MSG_SHUTDOWN_PENDING,
        },
    )
    assert case.carpeta_salida == str(anterior)

    # La salida Interrupted pasó por el finally de la ruta y dejó la puerta
    # disponible; no se fuerza ni se reemplaza el objeto lock del proceso.
    assert routes._OUTPUT_FOLDER_SELECTOR_LOCK.acquire(blocking=False) is True
    routes._OUTPUT_FOLDER_SELECTOR_LOCK.release()

    managed_server.wait_for_shutdown(timeout=5)
    assert managed_server.is_running() is False


def test_selector_y_analisis_activo_hacen_close_when_idle_por_http_real(
    managed_server, monkeypatch, tmp_path
):
    """El cierre diferido mantiene Waitress vivo hasta terminar el análisis."""
    assert managed_server.wait_until_ready(TOKEN, attempts=50, delay=0.01) is True

    selector_case = state.create_session()
    selector_case.modo = state.MODO_1
    anterior = tmp_path / "seleccion-anterior-close-when-idle"
    anterior.mkdir()
    selector_case.carpeta_salida = str(anterior)
    selector_cookie = _session_cookie(managed_server, selector_case.id)
    analysis = state.create_session()

    picker_entered = threading.Event()
    inspect_cancellation = threading.Event()
    selector_done = threading.Event()
    cancellation_seen = threading.Event()
    selector_result = {}
    selector_errors = []
    analysis_started = False

    def _blocking_pick(*, initial_dir, cancel_requested):
        assert initial_dir == str(anterior)
        assert callable(cancel_requested)
        assert cancel_requested() is False
        picker_entered.set()
        assert inspect_cancellation.wait(timeout=5), (
            "el test no permitió al picker observar CLOSE_WHEN_IDLE"
        )
        assert cancel_requested() is True
        cancellation_seen.set()
        raise FolderDialogInterruptedError("cierre diferido durante selector")

    def _post_selector():
        try:
            selector_result["response"] = _request_json(
                managed_server,
                "/output-folder/select",
                method="POST",
                cookie=selector_cookie,
                timeout=5,
            )
        except BaseException as exc:  # noqa: BLE001 - se propaga al hilo principal
            selector_errors.append(exc)
        finally:
            selector_done.set()

    monkeypatch.setattr(routes, "pick_folder", _blocking_pick)
    lifecycle.set_shutdown_hook(managed_server.stop)
    selector_thread = threading.Thread(
        target=_post_selector,
        name="test-real-waitress-selector-close-when-idle",
    )
    selector_thread.start()
    try:
        assert picker_entered.wait(timeout=3), "Waitress no despachó el selector"
        assert state.try_start_run(analysis.id) is True
        analysis_started = True

        shutdown_status, shutdown = _request_json(
            managed_server,
            "/internal/shutdown",
            method="POST",
            token=TOKEN,
        )
        assert shutdown_status == 200
        assert shutdown == {
            "ok": True,
            "lifecycle_state": lifecycle.CLOSE_WHEN_IDLE,
        }
        assert state.is_any_run_active() is True
        assert managed_server.is_running() is True

        # Ambos endpoints deben responder mientras el análisis y el picker
        # siguen retenidos; aún no se habilitó la salida del picker fake.
        health_status, health = _request_json(
            managed_server,
            "/internal/health",
            token=TOKEN,
        )
        assert health_status == 200
        assert health["lifecycle_state"] == lifecycle.CLOSE_WHEN_IDLE

        heartbeat_status, heartbeat = _request_json(
            managed_server,
            "/internal/heartbeat",
            method="POST",
            token=TOKEN,
        )
        assert heartbeat_status == 200
        assert heartbeat == {
            "ok": True,
            "lifecycle_state": lifecycle.CLOSE_WHEN_IDLE,
        }
        assert selector_done.is_set() is False

        inspect_cancellation.set()
        selector_thread.join(timeout=5)
        assert selector_thread.is_alive() is False
        assert selector_errors == []
        assert cancellation_seen.is_set() is True
        assert selector_result["response"] == (
            409,
            {
                "status": "error",
                "message": state.MSG_SHUTDOWN_PENDING,
            },
        )
        assert selector_case.carpeta_salida == str(anterior)
        assert state.is_any_run_active() is True
        assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
        assert managed_server.is_running() is True

        state.finish_run(analysis.id)
        analysis_started = False
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
        managed_server.wait_for_shutdown(timeout=5)
        assert managed_server.is_running() is False
    finally:
        inspect_cancellation.set()
        selector_thread.join(timeout=5)
        if analysis_started:
            state.finish_run(analysis.id)
        if managed_server.is_running() and lifecycle.get_state() != lifecycle.SHUTTING_DOWN:
            managed_server.stop()
        managed_server.wait_for_shutdown(timeout=5)


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
