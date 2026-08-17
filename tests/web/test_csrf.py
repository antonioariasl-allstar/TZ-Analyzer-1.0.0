"""tz_web.routes._guard_csrf — protección CSRF uniforme del blueprint
principal (MICROBLOQUE 7-B5-A2).

Cubre exclusivamente el guard CSRF de los POST del blueprint principal —
``/internal/*`` sigue su contrato propio de ``X-TZ-Token`` (MB5) sin
requerir este token; el Host allowlist (MB7-B5-A1) sigue vigente y sin
cambios, y este archivo también confirma que corre antes que el CSRF.
"""
from __future__ import annotations

import inspect
import logging

import pytest

from tz_web import lifecycle, routes, state
from tz_web.app import HOST, create_app
from tz_web.server import ManagedServer
from tests.web.conftest import configure_test_instance_host, csrf_token

INSTANCE_TOKEN = "token-csrf-instancia-1234567890"
PORT = 48765


@pytest.fixture()
def csrf_app(tmp_path, monkeypatch):
    """App SIN el header CSRF adjuntado automáticamente (a diferencia del
    fixture ``client`` de conftest.py): cada test controla explícitamente
    qué token manda, para poder ejercitar los casos adversariales."""
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=INSTANCE_TOKEN, instance_id="instancia-csrf")
    application.config.update(TESTING=True)
    configure_test_instance_host(application, port=PORT)
    yield application
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _token(app) -> str:
    return csrf_token(app)


# ---------------------------------------------------------------------------
# 1-3. Ausente / incorrecto / correcto.
# ---------------------------------------------------------------------------


def test_post_sensible_sin_token_es_rechazado(csrf_client):
    resp = csrf_client.post("/modo/1")
    assert resp.status_code == 403
    assert resp.mimetype == "text/plain"


def test_post_con_token_incorrecto_es_rechazado(csrf_client):
    resp = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": "token-equivocado"})
    assert resp.status_code == 403


def test_post_con_token_correcto_header_conserva_comportamiento_previo(csrf_app, csrf_client):
    resp = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/analizador")


def test_post_con_token_correcto_form_field_conserva_comportamiento_previo(csrf_app, csrf_client):
    resp = csrf_client.post("/modo/1", data={"csrf_token": _token(csrf_app)})
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# 4. TZ_CSRF_TOKEN ausente/no configurado -> 503, handler no se ejecuta.
# ---------------------------------------------------------------------------


def test_csrf_token_no_configurado_rechaza_con_503_sin_ejecutar_el_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-sin-csrf"))
    lifecycle.reset_for_tests()
    application = create_app()
    application.config.update(TESTING=True)
    configure_test_instance_host(application, port=PORT + 1)
    application.config["TZ_CSRF_TOKEN"] = None
    client = application.test_client()
    try:
        resp = client.post("/modo/1")
        assert resp.status_code == 503
        assert resp.mimetype == "text/plain"
        # El handler real (que crearía una sesión) nunca se ejecutó.
        assert state._SESSIONS == {}
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 5. Confirmación de código: comparación constant-time.
# ---------------------------------------------------------------------------


def test_guard_usa_hmac_compare_digest():
    source = inspect.getsource(routes._guard_csrf)
    assert "hmac.compare_digest" in source
    # La comparación insegura ("provided == expected") no debe existir en
    # absoluto en el guard: la única comparación de igualdad del token debe
    # pasar por hmac.compare_digest.
    assert "provided == expected" not in source
    assert "expected == provided" not in source


# ---------------------------------------------------------------------------
# 6/28. El token es por instancia: no es intercambiable, y una instancia u
# otro puerto genera un token independiente.
# ---------------------------------------------------------------------------


def test_token_de_una_instancia_no_funciona_en_otra(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-a"))
    lifecycle.reset_for_tests()
    app_a = create_app(instance_token="t-a", instance_id="instancia-a")
    app_a.config.update(TESTING=True)
    configure_test_instance_host(app_a, port=PORT + 2)

    app_b = create_app(instance_token="t-b", instance_id="instancia-b")
    app_b.config.update(TESTING=True)
    configure_test_instance_host(app_b, port=PORT + 3)

    assert _token(app_a) != _token(app_b)

    client_b = app_b.test_client()
    try:
        resp = client_b.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(app_a)})
        assert resp.status_code == 403
    finally:
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 7. Cambiar case_id no cambia TZ_CSRF_TOKEN.
# ---------------------------------------------------------------------------


def test_cambiar_case_id_no_cambia_el_token_csrf(csrf_app, csrf_client):
    token_before = _token(csrf_app)
    resp1 = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": token_before})
    assert resp1.status_code == 302
    resp2 = csrf_client.post("/modo/2", headers={"X-TZ-CSRF-Token": token_before})
    assert resp2.status_code == 302
    assert _token(csrf_app) == token_before


# ---------------------------------------------------------------------------
# 8. /modo/<modo> con token correcto ANTES de existir caso -> funciona.
# ---------------------------------------------------------------------------


def test_modo_con_token_correcto_antes_de_existir_caso_funciona(csrf_app, csrf_client):
    with csrf_client.session_transaction() as browser_session:
        assert "case_id" not in browser_session
    resp = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})
    assert resp.status_code == 302
    with csrf_client.session_transaction() as browser_session:
        assert "case_id" in browser_session


# ---------------------------------------------------------------------------
# 9. /upload multipart: hidden token aceptado, archivo llega intacto.
# ---------------------------------------------------------------------------


def test_upload_multipart_acepta_csrf_y_conserva_el_archivo(csrf_app, csrf_client, monkeypatch):
    import io
    import os

    # Evita depender del parser real de Excel: el foco de esta prueba es que
    # el guard CSRF conviva con multipart/form-data sin alterar el archivo,
    # no la lectura de hojas en sí (ya cubierta en tests/web/conftest.py).
    monkeypatch.setattr(routes, "_list_sheets", lambda path: ["Hoja1"])

    token = _token(csrf_app)
    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": token})

    contenido = b"contenido-de-prueba-no-alterado"
    data = {
        "csrf_token": token,
        "archivo": (io.BytesIO(contenido), "archivo_prueba.xlsx"),
    }
    resp = csrf_client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200

    with csrf_client.session_transaction() as browser_session:
        case_id = browser_session["case_id"]
    case = state.get_session(case_id)
    assert case.original_filename == "archivo_prueba.xlsx"
    assert case.available_sheets == ["Hoja1"]
    saved = os.path.join(case.upload_dir, "archivo_prueba.xlsx")
    with open(saved, "rb") as fh:
        assert fh.read() == contenido


def test_upload_sin_csrf_es_rechazado_sin_tocar_el_archivo(csrf_app, csrf_client):
    import io

    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})
    data = {"archivo": (io.BytesIO(b"x"), "no_deberia_guardarse.xlsx")}
    resp = csrf_client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 403
    with csrf_client.session_transaction() as browser_session:
        case_id = browser_session["case_id"]
    case = state.get_session(case_id)
    assert case.original_filename is None
    assert case.upload_dir is None


# ---------------------------------------------------------------------------
# 10-12. /output-folder/select.
# ---------------------------------------------------------------------------


def test_output_folder_select_sin_token_rechaza_y_no_abre_dialogo(csrf_app, csrf_client, monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "pick_folder", lambda **kwargs: calls.append(kwargs))
    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})

    resp = csrf_client.post("/output-folder/select")
    assert resp.status_code == 403
    assert calls == []


def test_output_folder_select_token_correcto_conserva_contrato_previo(csrf_app, csrf_client, monkeypatch, tmp_path):
    token = _token(csrf_app)
    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": token})
    elegido = str(tmp_path / "salida-elegida")
    import os

    os.makedirs(elegido, exist_ok=True)
    monkeypatch.setattr(routes, "pick_folder", lambda **kwargs: elegido)

    resp = csrf_client.post("/output-folder/select", headers={"X-TZ-CSRF-Token": token})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert os.path.abspath(body["carpeta_salida"]) == os.path.abspath(elegido)


def test_output_folder_select_cancelado_sigue_funcionando(csrf_app, csrf_client, monkeypatch):
    token = _token(csrf_app)
    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": token})
    monkeypatch.setattr(routes, "pick_folder", lambda **kwargs: None)

    resp = csrf_client.post("/output-folder/select", headers={"X-TZ-CSRF-Token": token})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 13-14. /open/<kind>: efecto local real (os.startfile) cubierto por CSRF.
# ---------------------------------------------------------------------------


def test_open_kind_sin_token_rechaza_y_no_ejecuta_startfile(csrf_app, csrf_client, monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "_open_with_default_app", lambda path: calls.append(path))
    csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})

    resp = csrf_client.post("/open/kml")
    assert resp.status_code == 403
    assert calls == []


def test_open_kind_token_correcto_conserva_contrato_previo(csrf_app, csrf_client, monkeypatch):
    """Con token válido, el guard CSRF deja pasar la request y el handler se
    ejecuta con su comportamiento preexistente (sin caso -> 404, nunca 403
    por CSRF): la prueba de que efectivamente abre el archivo con un caso
    real completo ya vive en test_processing_and_results.py, sin cambios,
    y sigue en verde con el guard activo."""
    resp = csrf_client.post("/open/kml", headers={"X-TZ-CSRF-Token": _token(csrf_app)})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 15-16. /configure/final/preview-name.
# ---------------------------------------------------------------------------


def test_preview_name_sin_token_es_rechazado(csrf_client):
    resp = csrf_client.post("/configure/final/preview-name", data={"tipo_bitacora": ""})
    assert resp.status_code == 403


def test_preview_name_con_token_header_funciona(csrf_app, csrf_client):
    resp = csrf_client.post(
        "/configure/final/preview-name",
        data={"tipo_bitacora": ""},
        headers={"X-TZ-CSRF-Token": _token(csrf_app)},
    )
    # Sin caso/mapeo todavía: 400 propio del handler, nunca 403 de CSRF —
    # confirma que el guard dejó pasar la request.
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 17-18. Inventario: 100% de los <form method="post"> tienen csrf_token.
# ---------------------------------------------------------------------------


def test_todos_los_forms_post_tienen_csrf_token_oculto():
    import re
    from pathlib import Path

    templates_dir = Path(__file__).resolve().parents[2] / "tz_web" / "templates"
    form_re = re.compile(r'<form\b[^>]*\bmethod=["\']?post["\']?[^>]*>', re.IGNORECASE)
    total = 0
    missing = []
    for path in templates_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        for m in form_re.finditer(text):
            total += 1
            tail = text[m.end():m.end() + 400]
            before_close = tail.split("</form>")[0]
            if 'name="csrf_token"' not in before_close:
                missing.append((path.name, m.group(0)))
    assert total == 39
    assert missing == []


# ---------------------------------------------------------------------------
# 19. El token no aparece en URL/query/logs de rechazo/error response.
# ---------------------------------------------------------------------------


def test_token_no_aparece_en_respuesta_de_rechazo(csrf_app, csrf_client):
    real_token = _token(csrf_app)
    resp = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": "token-malicioso-enviado"})
    body = resp.get_data(as_text=True)
    assert real_token not in body
    assert "token-malicioso-enviado" not in body


def test_token_no_aparece_en_logs_de_rechazo(csrf_app, csrf_client, caplog):
    real_token = _token(csrf_app)
    with caplog.at_level(logging.WARNING, logger="tz_web.routes"):
        csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": "token-malicioso-en-log"})
    warnings = [r for r in caplog.records if r.name == "tz_web.routes" and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert real_token not in message
    assert "token-malicioso-en-log" not in message


def test_url_de_los_endpoints_post_nunca_lleva_el_token(csrf_app, csrf_client):
    resp = csrf_client.post("/modo/1", headers={"X-TZ-CSRF-Token": _token(csrf_app)})
    assert "csrf" not in resp.request.path.lower()
    assert _token(csrf_app) not in resp.request.path


# ---------------------------------------------------------------------------
# 20. Host inválido + CSRF válido -> gana el guard de Host (corre primero).
# ---------------------------------------------------------------------------


def test_host_invalido_con_csrf_valido_rechaza_por_host_primero(csrf_app, csrf_client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = csrf_client.post(
            "/modo/1",
            headers={"Host": "evil.example", "X-TZ-CSRF-Token": _token(csrf_app)},
        )
    assert resp.status_code == 403
    host_warnings = [r for r in caplog.records if r.name == "tz_web.app"]
    csrf_warnings = [r for r in caplog.records if r.name == "tz_web.routes"]
    assert len(host_warnings) == 1
    assert csrf_warnings == []


# ---------------------------------------------------------------------------
# 21-23. /internal/* sigue exento de CSRF, con su contrato X-TZ-Token intacto.
# ---------------------------------------------------------------------------


def test_internal_health_no_requiere_csrf_token(csrf_client):
    resp = csrf_client.get("/internal/health", headers={"X-TZ-Token": INSTANCE_TOKEN})
    assert resp.status_code == 200


def test_internal_heartbeat_sigue_usando_solo_x_tz_token(csrf_client):
    resp = csrf_client.post("/internal/heartbeat", headers={"X-TZ-Token": INSTANCE_TOKEN})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_internal_shutdown_sigue_usando_solo_x_tz_token(csrf_client):
    resp = csrf_client.post("/internal/shutdown", headers={"X-TZ-Token": INSTANCE_TOKEN})
    assert resp.status_code == 200
    assert resp.get_json()["lifecycle_state"] == lifecycle.SHUTTING_DOWN


# ---------------------------------------------------------------------------
# 26. Segunda instancia / check_health real sigue funcionando sin CSRF.
# ---------------------------------------------------------------------------


def test_segunda_instancia_check_health_real_no_requiere_csrf(tmp_path, monkeypatch):
    from tz_web import instance as tz_instance

    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads-managed"))
    lifecycle.reset_for_tests()
    app = create_app(instance_token=INSTANCE_TOKEN, instance_id="instancia-managed-csrf")
    server = ManagedServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        assert server.wait_until_ready(INSTANCE_TOKEN, attempts=50, delay=0.05) is True
        data = tz_instance.check_health(server.port, INSTANCE_TOKEN)
        assert data is not None
        assert data["instance_id"] == "instancia-managed-csrf"
    finally:
        server.stop()
        server.wait_for_shutdown(timeout=5)
        lifecycle.reset_for_tests()
        with state._SESSIONS_LOCK:
            state._SESSIONS.clear()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None


# ---------------------------------------------------------------------------
# 27. Requests POST válidos consecutivos siguen funcionando.
# ---------------------------------------------------------------------------


def test_requests_post_validos_consecutivos_siguen_funcionando(csrf_app, csrf_client):
    token = _token(csrf_app)
    for modo in ("1", "2", "1", "2", "1"):
        resp = csrf_client.post(f"/modo/{modo}", headers={"X-TZ-CSRF-Token": token})
        assert resp.status_code == 302
