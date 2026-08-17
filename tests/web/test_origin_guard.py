"""tz_web.origin_guard — validación de Origin y Sec-Fetch-Site (MICROBLOQUE
7-B5-B), más la configuración explícita de la cookie de sesión.

Cubre exclusivamente esta capa — Host (MB7-B5-A1) y CSRF/X-TZ-Token
(MB7-B5-A2) siguen intactos y sin cambios; este archivo también confirma
el orden real: Host -> Origin/Fetch -> CSRF / X-TZ-Token.
"""
from __future__ import annotations

import logging

import pytest

from tz_web import lifecycle, routes, state
from tz_web.app import HOST, create_app
from tz_web.server import ManagedServer
from tests.web.conftest import configure_test_instance_host, csrf_token

INSTANCE_TOKEN = "token-origin-guard-1234567890"
PORT = 49876


@pytest.fixture()
def origin_app(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=INSTANCE_TOKEN, instance_id="instancia-origin")
    application.config.update(TESTING=True)
    configure_test_instance_host(application, port=PORT)
    yield application
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


@pytest.fixture()
def origin_client(origin_app):
    return origin_app.test_client()


def _token(app) -> str:
    return csrf_token(app)


ORIGIN_LOCAL = f"http://{HOST}:{PORT}"


def _post_modo(client, app, extra_headers=None):
    headers = {"X-TZ-CSRF-Token": _token(app)}
    if extra_headers:
        headers.update(extra_headers)
    return client.post("/modo/1", headers=headers)


# ---------------------------------------------------------------------------
# 1-10. Política Origin — blueprint principal.
# ---------------------------------------------------------------------------


def test_origin_local_exacto_permitido_con_csrf_valido(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app, {"Origin": ORIGIN_LOCAL})
    assert resp.status_code == 302


def test_origin_ausente_permitido_con_csrf_valido(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app)
    assert resp.status_code == 302


@pytest.mark.parametrize(
    "origin_value",
    [
        "https://evil.example",
        "http://evil.example",
        "null",
        "chrome-extension://abcdef",
        "moz-extension://abcdef",
        f"http://localhost:{PORT}",
        f"http://{HOST}:{PORT + 1}",
        f"https://{HOST}:{PORT}",
    ],
)
def test_origin_invalido_es_rechazado(origin_app, origin_client, origin_value):
    resp = _post_modo(origin_client, origin_app, {"Origin": origin_value})
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"


# ---------------------------------------------------------------------------
# 11-15. Fetch Metadata.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fetch_site", ["same-origin", "same-site", "none"])
def test_sec_fetch_site_permitido(origin_app, origin_client, fetch_site):
    resp = _post_modo(origin_client, origin_app, {"Sec-Fetch-Site": fetch_site})
    assert resp.status_code == 302


def test_sec_fetch_site_ausente_permitido(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app)
    assert resp.status_code == 302


def test_sec_fetch_site_cross_site_es_rechazado(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app, {"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"


# ---------------------------------------------------------------------------
# 16-18. Orden de guards.
# ---------------------------------------------------------------------------


def test_host_invalido_con_origin_y_csrf_validos_rechaza_por_host_primero(origin_app, origin_client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = origin_client.post(
            "/modo/1",
            headers={
                "Host": "evil.example",
                "Origin": ORIGIN_LOCAL,
                "X-TZ-CSRF-Token": _token(origin_app),
            },
        )
    assert resp.status_code == 403
    host_warnings = [r for r in caplog.records if r.name == "tz_web.app"]
    origin_warnings = [r for r in caplog.records if r.name == "tz_web.origin_guard"]
    csrf_warnings = [r for r in caplog.records if r.name == "tz_web.routes"]
    assert len(host_warnings) == 1
    assert origin_warnings == []
    assert csrf_warnings == []


def test_origin_externo_con_csrf_valido_rechaza_por_origin_antes_que_csrf(origin_app, origin_client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = origin_client.post(
            "/modo/1",
            headers={"Origin": "https://evil.example", "X-TZ-CSRF-Token": _token(origin_app)},
        )
    assert resp.status_code == 403
    origin_warnings = [r for r in caplog.records if r.name == "tz_web.origin_guard"]
    csrf_warnings = [r for r in caplog.records if r.name == "tz_web.routes"]
    assert len(origin_warnings) == 1
    assert csrf_warnings == []


def test_cross_site_con_csrf_valido_rechaza_por_fetch_antes_que_csrf(origin_app, origin_client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = origin_client.post(
            "/modo/1",
            headers={"Sec-Fetch-Site": "cross-site", "X-TZ-CSRF-Token": _token(origin_app)},
        )
    assert resp.status_code == 403
    origin_warnings = [r for r in caplog.records if r.name == "tz_web.origin_guard"]
    csrf_warnings = [r for r in caplog.records if r.name == "tz_web.routes"]
    assert len(origin_warnings) == 1
    assert csrf_warnings == []


# ---------------------------------------------------------------------------
# 19. Fail-closed: TZ_INSTANCE_ORIGIN ausente -> 503, handler no se ejecuta.
# ---------------------------------------------------------------------------


def test_instance_origin_no_configurado_rechaza_con_503_sin_ejecutar_el_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-sin-origin"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=INSTANCE_TOKEN, instance_id="instancia-sin-origin")
    application.config.update(TESTING=True)
    configure_test_instance_host(application, port=PORT + 1)
    application.config["TZ_INSTANCE_ORIGIN"] = None
    client = application.test_client()
    try:
        resp = client.post("/modo/1", headers={"X-TZ-CSRF-Token": csrf_token(application)})
        assert resp.status_code == 503
        assert resp.mimetype == "text/plain"
        assert state._SESSIONS == {}
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 20-24. /internal/*.
# ---------------------------------------------------------------------------


def test_internal_health_sin_origin_fetch_token_valido_funciona(origin_client):
    resp = origin_client.get("/internal/health", headers={"X-TZ-Token": INSTANCE_TOKEN})
    assert resp.status_code == 200


def test_internal_health_origin_local_token_valido_funciona(origin_client):
    resp = origin_client.get(
        "/internal/health", headers={"Origin": ORIGIN_LOCAL, "X-TZ-Token": INSTANCE_TOKEN}
    )
    assert resp.status_code == 200


def test_internal_health_origin_externo_rechaza_antes_del_token_guard(origin_client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = origin_client.get(
            "/internal/health",
            headers={"Origin": "https://evil.example", "X-TZ-Token": INSTANCE_TOKEN},
        )
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"
    # No es el 403 JSON que produce tz_web.internal_routes._guard_internal_requests.
    assert resp.get_json(force=False) is None


def test_internal_heartbeat_origin_local_same_origin_token_valido_funciona(origin_client):
    resp = origin_client.post(
        "/internal/heartbeat",
        headers={
            "Origin": ORIGIN_LOCAL,
            "Sec-Fetch-Site": "same-origin",
            "X-TZ-Token": INSTANCE_TOKEN,
        },
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_internal_shutdown_origin_local_same_origin_token_valido_funciona(origin_client):
    resp = origin_client.post(
        "/internal/shutdown",
        headers={
            "Origin": ORIGIN_LOCAL,
            "Sec-Fetch-Site": "same-origin",
            "X-TZ-Token": INSTANCE_TOKEN,
        },
    )
    assert resp.status_code == 200
    assert resp.get_json()["lifecycle_state"] == lifecycle.SHUTTING_DOWN


# ---------------------------------------------------------------------------
# 25/33. Probe real contra ManagedServer: segunda instancia sin Origin/Fetch,
# y recálculo correcto de TZ_INSTANCE_ORIGIN con un puerto efímero distinto.
# ---------------------------------------------------------------------------


def test_segunda_instancia_check_health_real_no_requiere_origin_fetch(tmp_path, monkeypatch):
    from tz_web import instance as tz_instance

    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-managed-origin"))
    lifecycle.reset_for_tests()
    app = create_app(instance_token=INSTANCE_TOKEN, instance_id="instancia-managed-origin")
    server = ManagedServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        assert server.wait_until_ready(INSTANCE_TOKEN, attempts=50, delay=0.05) is True
        assert app.config["TZ_INSTANCE_ORIGIN"] == f"http://127.0.0.1:{server.port}"
        data = tz_instance.check_health(server.port, INSTANCE_TOKEN)
        assert data is not None
        assert data["instance_id"] == "instancia-managed-origin"
    finally:
        server.stop()
        server.wait_for_shutdown(timeout=5)
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


def test_puerto_efimero_distinto_recalcula_origin_correctamente(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-managed-origin-2"))
    lifecycle.reset_for_tests()
    app_a = create_app(instance_token="t-a", instance_id="instancia-a")
    server_a = ManagedServer(app_a, host="127.0.0.1", port=0)
    app_b = create_app(instance_token="t-b", instance_id="instancia-b")
    server_b = ManagedServer(app_b, host="127.0.0.1", port=0)
    server_a.start()
    server_b.start()
    try:
        assert server_a.wait_until_ready("t-a", attempts=50, delay=0.05) is True
        assert server_b.wait_until_ready("t-b", attempts=50, delay=0.05) is True
        assert server_a.port != server_b.port
        assert app_a.config["TZ_INSTANCE_ORIGIN"] == f"http://127.0.0.1:{server_a.port}"
        assert app_b.config["TZ_INSTANCE_ORIGIN"] == f"http://127.0.0.1:{server_b.port}"
        assert app_a.config["TZ_INSTANCE_ORIGIN"] != app_b.config["TZ_INSTANCE_ORIGIN"]
    finally:
        server_a.stop()
        server_b.stop()
        server_a.wait_for_shutdown(timeout=5)
        server_b.wait_for_shutdown(timeout=5)
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 26-28. Cookie Flask.
# ---------------------------------------------------------------------------


def _set_cookie_headers(resp) -> list:
    return resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else resp.headers.getlist("Set-Cookie")


def test_set_cookie_contiene_httponly(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app)
    cookies = _set_cookie_headers(resp)
    assert any("session=" in c for c in cookies)
    assert any("HttpOnly" in c for c in cookies)


def test_set_cookie_contiene_samesite_strict(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app)
    cookies = _set_cookie_headers(resp)
    assert any("SameSite=Strict" in c for c in cookies)


def test_set_cookie_no_contiene_secure(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app)
    cookies = _set_cookie_headers(resp)
    session_cookies = [c for c in cookies if "session=" in c]
    assert session_cookies
    for cookie in session_cookies:
        assert "Secure" not in cookie.split(";")


# ---------------------------------------------------------------------------
# 29-30. Sin CORS, sin dependencia de Referer.
# ---------------------------------------------------------------------------


def test_no_existe_access_control_allow_origin(origin_app, origin_client):
    resp = _post_modo(origin_client, origin_app, {"Origin": ORIGIN_LOCAL})
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_no_existe_dependencia_logica_de_referer():
    """El módulo puede mencionar 'Referer' en prosa (explicando por qué no
    se usa, ver el docstring del módulo) pero no debe leer esa cabecera en
    ningún punto de la lógica real."""
    import inspect

    from tz_web import origin_guard as og

    source = inspect.getsource(og.guard_request)
    assert "referer" not in source.lower()
    assert "request.referrer" not in inspect.getsource(og)


# ---------------------------------------------------------------------------
# 31-32. Regresión: wizard normal y requests consecutivos siguen funcionando.
# ---------------------------------------------------------------------------


def test_wizard_post_normal_sigue_funcionando(origin_app, origin_client, monkeypatch):
    monkeypatch.setattr(routes, "_list_sheets", lambda path: ["Hoja1"])
    token = _token(origin_app)
    resp = origin_client.post("/modo/1", headers={"X-TZ-CSRF-Token": token})
    assert resp.status_code == 302

    import io

    data = {
        "csrf_token": token,
        "archivo": (io.BytesIO(b"contenido"), "archivo.xlsx"),
    }
    resp = origin_client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert resp.status_code == 200


def test_requests_post_validos_consecutivos_con_origin_local_siguen_funcionando(origin_app, origin_client):
    token = _token(origin_app)
    for modo in ("1", "2", "1", "2", "1"):
        resp = origin_client.post(
            f"/modo/{modo}", headers={"X-TZ-CSRF-Token": token, "Origin": ORIGIN_LOCAL}
        )
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# 34. Los logs de rechazo no filtran el Origin recibido ni otros datos.
# ---------------------------------------------------------------------------


def test_logs_de_rechazo_no_contienen_origin_recibido(origin_app, origin_client, caplog):
    with caplog.at_level(logging.WARNING, logger="tz_web.origin_guard"):
        _post_modo(origin_client, origin_app, {"Origin": "https://evil.example"})
    warnings = [r for r in caplog.records if r.name == "tz_web.origin_guard"]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "evil.example" not in message
    assert ORIGIN_LOCAL not in message
    assert INSTANCE_TOKEN not in message


def test_logs_de_rechazo_cross_site_no_contienen_datos_sensibles(origin_app, origin_client, caplog):
    """El mensaje genérico puede nombrar la categoría "cross-site" (es
    literalmente el ejemplo de la sección 12 del encargo) — lo que no debe
    aparecer es el valor de Sec-Fetch-Site tal como llegó si fuera un valor
    no estándar, ni ningún otro dato de la request."""
    with caplog.at_level(logging.WARNING, logger="tz_web.origin_guard"):
        _post_modo(origin_client, origin_app, {"Sec-Fetch-Site": "cross-site"})
    warnings = [r for r in caplog.records if r.name == "tz_web.origin_guard"]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert INSTANCE_TOKEN not in message
    assert ORIGIN_LOCAL not in message
