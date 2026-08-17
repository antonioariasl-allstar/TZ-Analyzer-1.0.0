"""tz_web.app._guard_host — allowlist global de Host (MICROBLOQUE 7-B5-A1).

Defensa contra DNS rebinding: un navegador dirigido por DNS hacia
``127.0.0.1:<puerto>`` no debe poder alcanzar el backend con un Host
distinto al real de esta instancia. Cubre exclusivamente el guard de Host
— no CSRF, no Origin, no Fetch Metadata (fuera de alcance de este
microbloque, ver el encargo).
"""
from __future__ import annotations

import logging

import pytest

from tz_web import lifecycle, state
from tz_web.app import HOST, create_app
from tz_web.server import ManagedServer

TOKEN = "token-host-guard-1234567890"
PORT = 47654


@pytest.fixture()
def guard_app(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=TOKEN, instance_id="instancia-host-guard")
    application.config.update(TESTING=True)
    application.config["TZ_INSTANCE_PORT"] = PORT
    application.config["SERVER_NAME"] = f"{HOST}:{PORT}"
    # GET /internal/health también queda sujeto al guard de Origin/Fetch
    # (MB7-B5-B, ver tz_web.origin_guard): sin esto, las pruebas de este
    # archivo que lo ejercitan verían el 503 fail-closed de ese guard en
    # vez del comportamiento del guard de Host que quieren probar.
    application.config["TZ_INSTANCE_ORIGIN"] = f"http://{HOST}:{PORT}"
    yield application
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


@pytest.fixture()
def guard_client(guard_app):
    return guard_app.test_client()


def _get(client, path, host=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if host is not None:
        headers["Host"] = host
    return client.get(path, headers=headers, **kwargs)


# ---------------------------------------------------------------------------
# 1-5. Host correcto vs. variantes maliciosas/incorrectas (blueprint principal).
# ---------------------------------------------------------------------------


def test_host_correcto_permite_la_request(guard_client):
    resp = _get(guard_client, "/")
    assert resp.status_code == 200


def test_host_evil_example_es_rechazado(guard_client):
    resp = _get(guard_client, "/", host="evil.example")
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"


def test_host_evil_example_con_puerto_real_es_rechazado(guard_client):
    resp = _get(guard_client, "/", host=f"evil.example:{PORT}")
    assert resp.status_code == 403


def test_host_127_0_0_1_con_puerto_distinto_es_rechazado(guard_client):
    resp = _get(guard_client, "/", host=f"127.0.0.1:{PORT + 1}")
    assert resp.status_code == 403


def test_host_localhost_con_puerto_real_es_rechazado(guard_client):
    """Fuera del contrato de producción (sección 3 del encargo): solo
    ``127.0.0.1:<puerto>`` es válido, salvo evidencia nueva y concreta de
    que producción usa ``localhost`` legítimamente."""
    resp = _get(guard_client, "/", host=f"localhost:{PORT}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6-7. Guard global cubre rutas fuera del blueprint principal.
# ---------------------------------------------------------------------------


def test_help_con_host_valido_funciona(guard_client):
    resp = _get(guard_client, "/help")
    assert resp.status_code == 200


def test_assets_logo_con_host_valido_funciona(guard_client):
    resp = _get(guard_client, "/assets/logo")
    assert resp.status_code == 200


def test_assets_logo_con_host_invalido_es_rechazado(guard_client):
    resp = _get(guard_client, "/assets/logo", host="evil.example")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8-10. /internal/*: el guard de Host corre antes que el de X-TZ-Token.
# ---------------------------------------------------------------------------


def test_internal_health_host_valido_token_valido_conserva_comportamiento(guard_client):
    resp = guard_client.get("/internal/health", headers={"X-TZ-Token": TOKEN})
    assert resp.status_code == 200
    assert resp.get_json()["instance_id"] == "instancia-host-guard"


def test_internal_health_host_invalido_token_valido_rechaza_por_host(guard_client):
    """Un Host falsificado no debe llegar nunca al guard de X-TZ-Token: la
    respuesta debe ser el texto plano genérico del guard de Host, no el JSON
    ``{"error": "no_autorizado"}`` que produce ``tz_web.internal_routes``."""
    resp = _get(
        guard_client,
        "/internal/health",
        host="evil.example",
        headers={"X-TZ-Token": TOKEN},
    )
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"
    assert resp.get_data(as_text=True) != '{"error":"no_autorizado"}'
    assert resp.get_json(force=False) is None


def test_internal_health_host_valido_token_invalido_llega_al_guard_de_token(guard_client):
    """Confirma que, con el Host correcto, el guard de token sigue
    ejecutándose y produce su propio 403 JSON (comportamiento preexistente,
    sin cambios) — prueba indirecta de que el guard de Host no lo reemplaza."""
    resp = guard_client.get("/internal/health", headers={"X-TZ-Token": "incorrecto"})
    assert resp.status_code == 403
    assert resp.get_json() == {"error": "no_autorizado"}


# ---------------------------------------------------------------------------
# 12. Puerto efímero distinto entre instancias: allowlist dinámico.
# ---------------------------------------------------------------------------


def test_allowlist_es_dinamico_no_hardcodeado(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-dinamico"))
    lifecycle.reset_for_tests()
    other_port = PORT + 999
    application = create_app(instance_token=TOKEN, instance_id="otra-instancia")
    application.config.update(TESTING=True)
    application.config["TZ_INSTANCE_PORT"] = other_port
    application.config["SERVER_NAME"] = f"{HOST}:{other_port}"
    client = application.test_client()
    try:
        assert _get(client, "/").status_code == 200
        assert _get(client, "/", host=f"{HOST}:{PORT}").status_code == 403
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 13. Requests válidas consecutivas siguen funcionando.
# ---------------------------------------------------------------------------


def test_requests_validas_consecutivas_siguen_funcionando(guard_client):
    for _ in range(5):
        assert _get(guard_client, "/").status_code == 200
    assert _get(guard_client, "/", host="evil.example").status_code == 403
    assert _get(guard_client, "/").status_code == 200


# ---------------------------------------------------------------------------
# 14. Host permitido todavía no configurado -> 503, fail-closed.
# ---------------------------------------------------------------------------


def test_host_no_configurado_rechaza_con_503_sin_ejecutar_la_ruta(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-sin-puerto"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=TOKEN, instance_id="instancia-sin-puerto")
    application.config.update(TESTING=True)
    # Deliberadamente sin TZ_INSTANCE_PORT/SERVER_NAME: representa la
    # ventana (teórica, ver tz_web/server.py) entre create_app() y que
    # ManagedServer.start() conozca el puerto real.
    assert application.config["TZ_INSTANCE_PORT"] is None
    client = application.test_client()
    sessions_before = dict(state._SESSIONS)
    try:
        resp = client.get("/")
        assert resp.status_code == 503
        assert resp.mimetype == "text/plain"
        # La ruta real (que crearía sesión/estado) nunca se ejecutó.
        assert state._SESSIONS == sessions_before
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 15. La respuesta de rechazo no filtra información sensible.
# ---------------------------------------------------------------------------


def test_respuesta_de_host_invalido_no_filtra_informacion_sensible(guard_client):
    resp = _get(
        guard_client,
        "/internal/health",
        host="evil.example",
        headers={"X-TZ-Token": TOKEN},
    )
    body = resp.get_data(as_text=True)
    assert "evil.example" not in body
    assert HOST not in body
    assert str(PORT) not in body
    assert TOKEN not in body
    assert "instancia-host-guard" not in body
    assert "/internal" not in body


# ---------------------------------------------------------------------------
# 16. Logging: WARNING genérico, sin el Host malicioso ni el token.
# ---------------------------------------------------------------------------


def test_rechazo_por_host_genera_warning_sin_datos_sensibles(guard_client, caplog):
    with caplog.at_level(logging.WARNING, logger="tz_web.app"):
        _get(
            guard_client,
            "/internal/health",
            host="evil.example",
            headers={"X-TZ-Token": TOKEN},
        )
    warnings = [r for r in caplog.records if r.name == "tz_web.app" and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "evil.example" not in message
    assert TOKEN not in message
    assert str(PORT) not in message


def test_rechazo_por_host_no_configurado_genera_warning_generico(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-warning"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=TOKEN, instance_id="instancia-warning")
    application.config.update(TESTING=True)
    client = application.test_client()
    try:
        with caplog.at_level(logging.WARNING, logger="tz_web.app"):
            client.get("/")
        warnings = [r for r in caplog.records if r.name == "tz_web.app" and r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert TOKEN not in warnings[0].getMessage()
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 11/17. Probe contra ManagedServer real (socket real en 127.0.0.1, puerto
# efímero verdadero) — no un test_client() de Flask. Confirma también que el
# flujo de segunda instancia (check_health vía urllib, mismo Host que arma
# el propio urllib) sigue funcionando sin cambios.
# ---------------------------------------------------------------------------


def test_probe_managed_server_real_host_valido_e_invalido(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-managed"))
    lifecycle.reset_for_tests()
    app = create_app(instance_token=TOKEN, instance_id="instancia-managed-real")
    server = ManagedServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        assert server.wait_until_ready(TOKEN, attempts=50, delay=0.05) is True
        real_port = server.port

        import urllib.error
        import urllib.request

        def _status(host_header: str) -> int:
            request = urllib.request.Request(
                f"http://127.0.0.1:{real_port}/internal/health",
                headers={"X-TZ-Token": TOKEN, "Host": host_header},
            )
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    return response.status
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()
                return status

        # PROBE A: Host real -> respuesta normal.
        assert _status(f"127.0.0.1:{real_port}") == 200
        # PROBE B: mismo socket físico, Host falsificado -> rechazo.
        assert _status("evil.example") == 403
        # PROBE C: mismo socket físico, puerto equivocado en el Host -> rechazo.
        assert _status(f"127.0.0.1:{real_port + 1}") == 403

        # El socket sigue limitado a loopback (no se abrió ninguna interfaz
        # LAN al agregar el guard de Host).
        assert server._server.effective_host == "127.0.0.1"

        # Flujo de segunda instancia: check_health() real, sin exigir
        # Origin/Sec-Fetch-Site/CSRF (fuera de alcance de este microbloque).
        from tz_web import instance as tz_instance

        data = tz_instance.check_health(real_port, TOKEN)
        assert data is not None
        assert data["instance_id"] == "instancia-managed-real"
    finally:
        server.stop()
        server.wait_for_shutdown(timeout=5)
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None
