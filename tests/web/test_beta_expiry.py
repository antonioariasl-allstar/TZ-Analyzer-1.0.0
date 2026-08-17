"""P1-BETA-EXPIRY — enforcement real de la vigencia de la Beta en el único
punto de arranque de un análisis nuevo (``tz_web.state.try_start_run_detailed``,
compartido por Modo 1/2/legacy y Modo 3 — ver ``tz_web.routes._start_task`` /
``_start_task_modo3``).

Ninguna prueba de este archivo cambia el reloj real del sistema: todas
inyectan la vigencia monkeypatcheando ``tz_version.BETA_EXPIRES_ON`` (el
umbral, no "hoy"), dejando que la lógica real de ``tz_version.is_beta_expired``
decida — nunca se mockea directamente el resultado booleano.
"""
from __future__ import annotations

from datetime import date, timedelta

import tz_version
from tz_web import state as tz_web_state
from tz_web import routes as tz_web_routes
from tz_web import services_modo3 as tz_web_services_modo3
from tests.web.conftest import (
    advance_to_configure,
    select_output_folder,
    wait_for_terminal_status,
)
from tests.web.test_modo3_pipeline import (
    agregar_antena,
    avanzar_hasta_resumen,
    current_case,
    elegir_tipo,
    enter_modo_3,
)

_VIGENTE = date.today() + timedelta(days=365)
_VENCIDA = date.today() - timedelta(days=1)


def _advance_to_resumen_modo1(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    client.post(
        "/configure/opciones",
        data={"accion": "siguiente", "top_antenas": "", "top_contactos": ""},
        follow_redirects=True,
    )
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    client.post(
        "/configure/final",
        data={"accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": ""},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# M — Beta vigente: el guard no interfiere con un arranque normal.
# ---------------------------------------------------------------------------


def test_beta_vigente_permite_iniciar_analisis_modo1(client, monkeypatch):
    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VIGENTE)
    _advance_to_resumen_modo1(client)
    select_output_folder(client)

    resp = client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Procesando análisis".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.task_started is True
    assert case.status in (tz_web_state.STATUS_RUNNING, tz_web_state.STATUS_SUCCESS)
    wait_for_terminal_status(client)


# ---------------------------------------------------------------------------
# N — Beta vencida: rechazo real en el endpoint que arranca el análisis,
# llamado directamente (sin pasar por la UI/JS del navegador) — demuestra
# que ocultar el botón en el cliente no evita la expiración.
# ---------------------------------------------------------------------------


def test_beta_vencida_bloquea_configure_resumen_modo1(client, monkeypatch):
    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VENCIDA)
    _advance_to_resumen_modo1(client)
    select_output_folder(client)

    llamadas = []
    monkeypatch.setattr(
        tz_web_routes, "process_case",
        lambda *a, **k: llamadas.append((a, k)) or (_ for _ in ()).throw(
            AssertionError("process_case no debe ejecutarse con la Beta vencida")
        ),
    )

    resp = client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert tz_version.BETA_EXPIRED_NOTICE.encode("utf-8") in resp.data
    assert "Procesando análisis".encode("utf-8") not in resp.data

    case = current_case(client)
    assert case.task_started is False
    assert case.status == tz_web_state.STATUS_PENDING
    assert case.result is None
    assert llamadas == []


def test_beta_vencida_bloquea_configure_legacy_submit(client, monkeypatch):
    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VENCIDA)
    advance_to_configure(client)

    resp = client.post(
        "/configure/legacy",
        data={"carpeta_salida": select_output_folder(client), "accion": "siguiente"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert tz_version.BETA_EXPIRED_NOTICE.encode("utf-8") in resp.data

    case = current_case(client)
    assert case.task_started is False
    assert case.status == tz_web_state.STATUS_PENDING


def test_beta_vencida_bloquea_modo3_resumen(client, tmp_path, monkeypatch):
    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VENCIDA)
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path)

    llamadas = []
    monkeypatch.setattr(
        tz_web_routes, "process_case_modo3",
        lambda *a, **k: llamadas.append((a, k)) or (_ for _ in ()).throw(
            AssertionError("process_case_modo3 no debe ejecutarse con la Beta vencida")
        ),
    )

    resp = client.post("/modo3/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert tz_version.BETA_EXPIRED_NOTICE.encode("utf-8") in resp.data

    case = current_case(client)
    assert case.task_started is False
    assert case.status == tz_web_state.STATUS_PENDING
    assert llamadas == []


def test_beta_vencida_rechazo_expone_el_motivo_estructural(monkeypatch):
    """Ejercita el guard directamente (sin HTTP): el motivo de rechazo debe
    ser distinguible de "busy"/"shutdown_pending" para que la capa web nunca
    tenga que adivinar comparando texto (mismo contrato de
    ``try_start_run_detailed`` para los motivos ya existentes)."""
    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VENCIDA)
    session = tz_web_state.create_session()
    started, reason = tz_web_state.try_start_run_detailed(session.id)
    assert started is False
    assert reason == tz_web_state.RUN_START_REJECTED_BETA_EXPIRED
    assert tz_web_state.is_any_run_active() is False


# ---------------------------------------------------------------------------
# O — La aplicación puede quedar abierta desde antes del vencimiento: el
# guard consulta la fecha en CADA llamada, nunca solo al arrancar. Se
# demuestra llamando dos veces al mismo guard, cambiando entre medio la
# vigencia (equivalente a que el calendario haya avanzado con la instancia
# ya corriendo).
# ---------------------------------------------------------------------------


def test_arranque_no_queda_congelado_en_el_estado_de_inicio(monkeypatch):
    session = tz_web_state.create_session()

    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VIGENTE)
    started_antes, reason_antes = tz_web_state.try_start_run_detailed(session.id)
    assert started_antes is True
    assert reason_antes is None
    tz_web_state.finish_run(session.id)

    monkeypatch.setattr(tz_version, "BETA_EXPIRES_ON", _VENCIDA)
    started_despues, reason_despues = tz_web_state.try_start_run_detailed(session.id)
    assert started_despues is False
    assert reason_despues == tz_web_state.RUN_START_REJECTED_BETA_EXPIRED
