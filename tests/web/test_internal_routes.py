"""tz_web.internal_routes — /internal/health, /internal/heartbeat,
/internal/shutdown (MICROBLOQUE 5). Seguridad local básica (sección L): sin
token correcto y sin IP de loopback, todo pedido se rechaza; ningún pedido
expone datos de caso."""

from __future__ import annotations

import pytest

from tz_web import lifecycle, state
from tz_web.app import create_app
from tests.web.conftest import configure_test_instance_host

TOKEN = "token-de-prueba-1234567890"


@pytest.fixture()
def internal_app(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=TOKEN, instance_id="instancia-prueba")
    application.config.update(TESTING=True)
    configure_test_instance_host(application)
    yield application
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


@pytest.fixture()
def internal_client(internal_app):
    return internal_app.test_client()


# ---------------------------------------------------------------------------
# 22/23. Sin token -> rechazado, en las tres rutas.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [("get", "/internal/health"), ("post", "/internal/heartbeat"), ("post", "/internal/shutdown")],
)
def test_rutas_internas_sin_token_son_rechazadas(internal_client, method, path):
    resp = getattr(internal_client, method)(path)
    assert resp.status_code == 403
    assert resp.get_json() == {"error": "no_autorizado"}


@pytest.mark.parametrize(
    "method,path",
    [("get", "/internal/health"), ("post", "/internal/heartbeat"), ("post", "/internal/shutdown")],
)
def test_rutas_internas_con_token_incorrecto_son_rechazadas(internal_client, method, path):
    resp = getattr(internal_client, method)(path, headers={"X-TZ-Token": "token-equivocado"})
    assert resp.status_code == 403


def test_health_sin_app_sin_token_configurado_rechaza_igual(tmp_path, monkeypatch):
    """Sin instance_token en create_app() (p. ej. una app de pruebas normal
    de tests/web/conftest.py), /internal/* nunca queda abierto por omisión."""
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    app = create_app()  # sin instance_token
    configure_test_instance_host(app)
    client = app.test_client()
    resp = client.get("/internal/health", headers={"X-TZ-Token": ""})
    assert resp.status_code == 403


def test_rutas_internas_rechazan_ip_no_local(internal_client):
    resp = internal_client.get(
        "/internal/health",
        headers={"X-TZ-Token": TOKEN},
        environ_overrides={"REMOTE_ADDR": "203.0.113.5"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Health: identidad de instancia, sin datos de caso.
# ---------------------------------------------------------------------------


def test_health_con_token_correcto_devuelve_identidad_minima(internal_client):
    resp = internal_client.get("/internal/health", headers={"X-TZ-Token": TOKEN})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["instance_id"] == "instancia-prueba"
    assert data["lifecycle_state"] == lifecycle.RUNNING
    assert set(data.keys()) == {
        "instance_id",
        "pid",
        "port",
        "app_version",
        "launcher_version",
        "lifecycle_state",
        "uptime_seconds",
    }


def test_health_nunca_expone_datos_de_sesion(internal_client):
    # Crea una sesión con datos como lo haría un flujo real.
    session = state.create_session()
    session.original_filename = "bitacora_confidencial.xlsx"
    session.carpeta_salida = r"C:\Users\alguien\Documents\caso_confidencial"

    resp = internal_client.get("/internal/health", headers={"X-TZ-Token": TOKEN})
    body = resp.get_data(as_text=True)
    assert session.original_filename not in body
    assert session.carpeta_salida not in body
    assert session.id not in body


# ---------------------------------------------------------------------------
# Heartbeat.
# ---------------------------------------------------------------------------


def test_heartbeat_con_token_actualiza_lifecycle(internal_client):
    before = lifecycle.get_last_heartbeat()
    resp = internal_client.post("/internal/heartbeat", headers={"X-TZ-Token": TOKEN})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert lifecycle.get_last_heartbeat() >= before


# ---------------------------------------------------------------------------
# Shutdown.
# ---------------------------------------------------------------------------


def test_shutdown_idle_con_token_cierra_de_inmediato(internal_client):
    resp = internal_client.post("/internal/shutdown", headers={"X-TZ-Token": TOKEN})
    assert resp.status_code == 200
    assert resp.get_json()["lifecycle_state"] == lifecycle.SHUTTING_DOWN
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN


def test_shutdown_durante_analisis_activo_difiere(internal_client):
    session = state.create_session()
    assert state.try_start_run(session.id) is True
    try:
        resp = internal_client.post("/internal/shutdown", headers={"X-TZ-Token": TOKEN})
        assert resp.get_json()["lifecycle_state"] == lifecycle.CLOSE_WHEN_IDLE
        assert state.is_any_run_active() is True
    finally:
        state.finish_run(session.id)


# ---------------------------------------------------------------------------
# 24. El token nunca aparece en un log — solo se verifica en el propio
# formato "seguro para log" que usa tz_web.instance (ver test_instance.py);
# aquí se confirma que la app no filtra el token por ningún otro canal de
# respuesta HTTP salvo el que ella misma configuró.
# ---------------------------------------------------------------------------


def test_respuestas_internas_no_incluyen_el_token(internal_client):
    resp = internal_client.get("/internal/health", headers={"X-TZ-Token": TOKEN})
    assert TOKEN not in resp.get_data(as_text=True)


def test_pagina_html_incluye_el_token_solo_en_el_meta_tag(internal_client):
    resp = internal_client.get("/")
    body = resp.get_data(as_text=True)
    assert f'<meta name="tz-token" content="{TOKEN}">' in body
    assert body.count(TOKEN) == 1
