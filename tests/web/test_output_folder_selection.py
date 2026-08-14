"""MICROBLOQUE 6 — selección explícita de carpeta de salida.

Cubre el contrato recuperado (ver diagnóstico MB6-1): el usuario debe elegir
explícitamente la carpeta base antes de poder generar un análisis, en los
tres modos, sin que TZ Analyzer sustituya en silencio esa ausencia por
Documents\\TZ Analyzer ni %TEMP%.

``pick_folder`` (el que abre el diálogo nativo de verdad, en un subproceso
aislado — ver ``tz_core.folder_dialog``) se monkeypatchea siempre en
``tz_web.routes.pick_folder``: ninguna prueba de este archivo abre una
ventana real. Las pruebas de ``pick_folder`` en sí (subprocess/timeout/
cancelación a nivel del propio módulo) viven en
``tests/unit/test_folder_dialog.py`` y ``tests/unit/test_folder_dialog_helper.py``.
"""
from __future__ import annotations

import os
import threading

import pytest

from tz_core.folder_dialog import (
    FolderDialogInterruptedError,
    FolderDialogTimeoutError,
    FolderDialogUnavailableError,
)
from tz_web import lifecycle
from tz_web import routes as tz_web_routes
from tz_web import state as tz_web_state
from tz_web.services import CaseRequest
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    select_output_folder,
    upload_real_file,
    wait_for_terminal_status,
)


def current_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


def _client_for_case(app, case_id):
    """Crea un cliente independiente que comparte solo el case_id firmado."""
    test_client = app.test_client()
    with test_client.session_transaction() as browser_session:
        browser_session["case_id"] = case_id
    return test_client


def mock_pick_folder(monkeypatch, *, return_value=None, side_effect=None):
    """Sustituye ``tz_web.routes.pick_folder`` (el nombre real que resuelve
    la vista al llamarlo) por un doble controlado. Devuelve la lista de
    kwargs con los que se invocó, para poder afirmar sobre ``initial_dir``
    cuando haga falta."""
    calls = []

    def _fake(**kwargs):
        calls.append(kwargs)
        if side_effect is not None:
            raise side_effect
        return return_value

    monkeypatch.setattr(tz_web_routes, "pick_folder", _fake)
    return calls


def click_seleccionar_carpeta(client, monkeypatch, *, return_value, side_effect=None):
    """Simula el clic en "Seleccionar carpeta…": mockea el diálogo nativo
    para que devuelva ``return_value`` (o lance ``side_effect``) y llama al
    endpoint real que el botón invoca vía fetch."""
    mock_pick_folder(monkeypatch, return_value=return_value, side_effect=side_effect)
    return client.post("/output-folder/select")


# ---------------------------------------------------------------------------
# Flujos completos por modo, hasta "Preparar análisis" (para Modo 1/2) o
# "Preparar salida" (Modo 3) — mismo patrón que usan test_configure.py /
# test_modo2_process_and_alcance.py / test_modo3_pipeline.py, sin
# reimportarlos (cada archivo de pruebas de tz_web es autocontenido).
# ---------------------------------------------------------------------------


def avanzar_modo1_hasta_preparar(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)
    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    return client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)


def avanzar_modo2_hasta_preparar(client):
    client.post("/modo/2", follow_redirects=True)
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)
    client.post("/configure/filtro-tiempo", data={
        "accion": "siguiente", "filtro_tipo": "dia", "filtro_dia": "2020-01-02",
    }, follow_redirects=True)
    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    return client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)


ANTENA_1 = {
    "nombre": "Sitio Norte 01", "lat": "10.5", "lon": "-66.9",
    "azimut": "22.5", "celda": "C1", "direccion": "Av. Principal", "detalle": "Torre alta",
}


def avanzar_modo3_hasta_preparar(client):
    client.post("/modo/3", follow_redirects=True)
    client.post("/modo3/tipo", data={"tipo": "antena"}, follow_redirects=True)
    client.post("/modo3/registros", data=dict(ANTENA_1), follow_redirects=True)
    client.post("/modo3/productos", data={"accion": "siguiente"}, follow_redirects=True)
    return client.post("/modo3/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)


# ---------------------------------------------------------------------------
# Contrato HTTP directo del selector: sesión obligatoria e initial_dir.
# ---------------------------------------------------------------------------


def test_post_sin_sesion_activa_no_abre_dialogo(client, monkeypatch):
    calls = mock_pick_folder(monkeypatch, return_value="C:\\no_deberia_usarse")

    resp = client.post("/output-folder/select")

    assert resp.status_code == 400
    assert resp.get_json() == {
        "status": "error",
        "message": "No hay una sesión activa.",
    }
    assert calls == []


def test_selector_usa_seleccion_previa_como_initial_dir(client, monkeypatch, tmp_path):
    client.post("/modo/1", follow_redirects=True)
    anterior = tmp_path / "salida anterior"
    anterior.mkdir()
    select_output_folder(client, str(anterior))
    calls = mock_pick_folder(monkeypatch, return_value=None)

    resp = client.post("/output-folder/select")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "cancelled",
        "carpeta_salida": str(anterior),
    }
    assert len(calls) == 1
    assert calls[0]["initial_dir"] == str(anterior)
    assert callable(calls[0]["cancel_requested"])
    assert calls[0]["cancel_requested"]() is False


def test_selector_usa_fallback_como_initial_dir_sin_seleccion_previa(
    client, monkeypatch, tmp_path
):
    client.post("/modo/1", follow_redirects=True)
    fallback = str(tmp_path / "fallback sugerido")
    resolver_calls = []

    def _resolve_default(*, warn):
        resolver_calls.append(warn)
        return fallback

    monkeypatch.setattr(tz_web_routes, "resolve_default_output_dir", _resolve_default)
    calls = mock_pick_folder(monkeypatch, return_value=None)

    resp = client.post("/output-folder/select")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "cancelled",
        "carpeta_salida": None,
    }
    assert len(resolver_calls) == 1
    assert callable(resolver_calls[0])
    assert len(calls) == 1
    assert calls[0]["initial_dir"] == fallback
    assert callable(calls[0]["cancel_requested"])
    assert calls[0]["cancel_requested"]() is False


# ---------------------------------------------------------------------------
# 1/2/3 — Selección válida de punta a punta por modo: el botón persiste la
# ruta, Resumen la conserva, y los productos terminan físicamente bajo la
# carpeta elegida (nunca Documents\TZ Analyzer ni %TEMP%).
# ---------------------------------------------------------------------------


def _assert_publicado_bajo(tmp_path, output_dir: str):
    assert output_dir.startswith(str(tmp_path))
    base = os.path.dirname(output_dir)
    # Sin residuos de la reserva transaccional de MB3 (".{name}.tzp") en la
    # carpeta elegida: la publicación atómica debe haber renombrado todo.
    assert not any(entry.startswith(".") for entry in os.listdir(base))


def test_seleccion_valida_modo1_produce_bajo_la_carpeta_elegida(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    elegida = str(tmp_path / "Salida Modo 1")
    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "carpeta_salida": elegida}
    assert current_case(client).carpeta_salida == elegida

    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    assert case.result.output_dir is not None
    _assert_publicado_bajo(tmp_path, case.result.output_dir)
    assert os.path.isfile(case.result.html_path)
    assert os.path.isfile(case.result.kmz_path)
    assert os.path.isfile(case.result.hashes_path)


def test_seleccion_valida_modo2_produce_bajo_la_carpeta_elegida(client, monkeypatch, tmp_path):
    avanzar_modo2_hasta_preparar(client)
    elegida = str(tmp_path / "Salida Modo 2")
    click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)
    assert current_case(client).carpeta_salida == elegida

    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    _assert_publicado_bajo(tmp_path, case.result.output_dir)
    assert case.filtro_tiempo is not None


def test_seleccion_valida_modo3_produce_bajo_la_carpeta_elegida(client, monkeypatch, tmp_path):
    avanzar_modo3_hasta_preparar(client)
    elegida = str(tmp_path / "Salida Modo 3")
    click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)
    assert current_case(client).carpeta_salida == elegida

    client.post("/modo3/preparar", data={"accion": "siguiente", "nombre_modo": "sugerido"}, follow_redirects=True)
    client.post("/modo3/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    _assert_publicado_bajo(tmp_path, case.result.output_dir)
    assert os.path.isfile(case.result.kmz_path)


# ---------------------------------------------------------------------------
# 4/5 — Cancelar el diálogo nunca modifica la selección existente (haya o
# no una selección previa).
# ---------------------------------------------------------------------------


def test_cancelar_sin_seleccion_previa_deja_carpeta_en_none(client, monkeypatch):
    avanzar_modo1_hasta_preparar(client)
    assert current_case(client).carpeta_salida is None

    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=None)
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "cancelled", "carpeta_salida": None}
    assert current_case(client).carpeta_salida is None


def test_cancelar_conservando_seleccion_anterior(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    anterior = str(tmp_path / "ya_elegida")
    click_seleccionar_carpeta(client, monkeypatch, return_value=anterior)
    assert current_case(client).carpeta_salida == anterior

    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=None)
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "cancelled", "carpeta_salida": anterior}
    assert current_case(client).carpeta_salida == anterior


# ---------------------------------------------------------------------------
# 6 — Carpeta elegida pero no escribible: error comprensible, selección
# anterior no se pisa, y se puede reintentar.
# ---------------------------------------------------------------------------


def test_carpeta_no_escribible_es_rechazada_y_permite_reintentar(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    anterior = tmp_path / "seleccion_anterior"
    anterior.mkdir()
    select_output_folder(client, str(anterior))
    original_ensure_writable_dir = tz_web_state.ensure_writable_dir

    def _boom(_path):
        raise OSError("permiso denegado (simulado)")

    monkeypatch.setattr(tz_web_state, "ensure_writable_dir", _boom)
    no_escribible = str(tmp_path / "sin_permiso")
    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=no_escribible)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "error"
    assert "No se pudo usar la carpeta seleccionada" in data["message"]
    assert current_case(client).carpeta_salida == str(anterior)

    # Reintento con la carpeta ya escribible (mismo click, sin el mock roto).
    monkeypatch.setattr(
        tz_web_state, "ensure_writable_dir", original_ensure_writable_dir
    )
    elegida = str(tmp_path / "esta_si_sirve")
    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)
    assert resp.status_code == 200
    assert current_case(client).carpeta_salida == elegida


def test_dialogo_no_disponible_produce_mensaje_comprensible(client, monkeypatch):
    avanzar_modo1_hasta_preparar(client)
    resp = click_seleccionar_carpeta(
        client, monkeypatch, return_value=None,
        side_effect=FolderDialogUnavailableError("Tkinter no está disponible en este intérprete."),
    )
    assert resp.status_code == 502
    data = resp.get_json()
    assert data["status"] == "error"
    assert "Tkinter" in data["message"]
    assert current_case(client).carpeta_salida is None


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    [
        pytest.param("success", 200, id="SUCCESS"),
        pytest.param("cancelled", 200, id="CANCELLED"),
        pytest.param("error", 502, id="ERROR"),
        pytest.param("interrupted", 409, id="Interrupted"),
        pytest.param("timeout", 502, id="timeout"),
        pytest.param("spawn_error", 502, id="spawn-error"),
    ],
)
def test_puerta_del_selector_se_libera_en_todas_las_salidas(
    app, monkeypatch, tmp_path, outcome, expected_status
):
    """Cada retorno o excepción controlada permite un POST posterior."""
    case = tz_web_state.create_session()
    case.modo = tz_web_state.MODO_1
    anterior = tmp_path / "seleccion-anterior"
    anterior.mkdir()
    case.carpeta_salida = str(anterior)
    client = _client_for_case(app, case.id)
    primera = str(tmp_path / f"primera-{outcome}")

    exceptions = {
        "error": FolderDialogUnavailableError("error tecnico controlado"),
        "interrupted": FolderDialogInterruptedError("cierre solicitado"),
        "timeout": FolderDialogTimeoutError("selector agotado"),
        "spawn_error": FolderDialogUnavailableError("no se pudo iniciar el selector"),
    }

    def _first_pick(*, initial_dir, cancel_requested):
        assert initial_dir == str(anterior)
        assert callable(cancel_requested)
        assert cancel_requested() is False
        if outcome == "success":
            return primera
        if outcome == "cancelled":
            return None
        raise exceptions[outcome]

    monkeypatch.setattr(tz_web_routes, "pick_folder", _first_pick)
    first_response = client.post("/output-folder/select")

    assert first_response.status_code == expected_status
    if outcome == "success":
        assert first_response.get_json()["status"] == "ok"
        assert case.carpeta_salida == primera
    elif outcome == "cancelled":
        assert first_response.get_json() == {
            "status": "cancelled",
            "carpeta_salida": str(anterior),
        }
        assert case.carpeta_salida == str(anterior)
    elif outcome == "interrupted":
        assert first_response.get_json() == {
            "status": "error",
            "message": tz_web_state.MSG_SHUTDOWN_PENDING,
        }
        assert case.carpeta_salida == str(anterior)
    else:
        assert first_response.get_json()["status"] == "error"
        assert case.carpeta_salida == str(anterior)

    segunda = str(tmp_path / f"segunda-{outcome}")

    def _second_pick(*, initial_dir, cancel_requested):
        assert initial_dir == case.carpeta_salida
        assert callable(cancel_requested)
        assert cancel_requested() is False
        return segunda

    monkeypatch.setattr(tz_web_routes, "pick_folder", _second_pick)
    second_response = client.post("/output-folder/select")

    assert second_response.status_code == 200
    assert second_response.get_json() == {
        "status": "ok",
        "carpeta_salida": segunda,
    }
    assert case.carpeta_salida == segunda


# ---------------------------------------------------------------------------
# 7 — Sin selección, no se puede generar (en ningún modo), y nunca cae en
# Documents\TZ Analyzer ni %TEMP% en su lugar.
# ---------------------------------------------------------------------------


def test_generar_sin_seleccion_modo1_2_es_rechazado(client):
    avanzar_modo1_hasta_preparar(client)
    resp = client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Seleccione una carpeta de salida".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.task_started is False
    assert case.carpeta_salida is None


def test_generar_sin_seleccion_modo3_es_rechazado(client):
    avanzar_modo3_hasta_preparar(client)
    client.post("/modo3/preparar", data={"accion": "siguiente", "nombre_modo": "sugerido"}, follow_redirects=True)
    resp = client.post("/modo3/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Seleccione una carpeta de salida".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.task_started is False
    assert case.carpeta_salida is None


def test_resumen_sin_seleccion_deshabilita_boton_generar(client):
    avanzar_modo1_hasta_preparar(client)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert "Ninguna carpeta seleccionada" in html
    assert "disabled" in html


# ---------------------------------------------------------------------------
# 8 — Persistencia Preparar -> Resumen -> worker: exactamente la carpeta
# elegida llega a CaseRequest.carpeta_salida.
# ---------------------------------------------------------------------------


def test_persistencia_preparar_resumen_worker(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    elegida = str(tmp_path / "persistente")
    click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)

    resp = client.get("/configure/resumen")
    assert elegida in resp.data.decode("utf-8")

    captured = {}
    original = tz_web_routes.process_case

    def _capture(request_obj: CaseRequest):
        captured["carpeta_salida"] = request_obj.carpeta_salida
        return original(request_obj)

    monkeypatch.setattr(tz_web_routes, "process_case", _capture)
    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    wait_for_terminal_status(client)

    assert captured["carpeta_salida"] == elegida


# ---------------------------------------------------------------------------
# 9 — Cambiar de carpeta antes de ejecutar: la última elección gana.
# ---------------------------------------------------------------------------


def test_cambio_de_carpeta_antes_de_generar_usa_la_ultima(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    primera = str(tmp_path / "primera")
    segunda = str(tmp_path / "segunda")

    click_seleccionar_carpeta(client, monkeypatch, return_value=primera)
    assert current_case(client).carpeta_salida == primera

    click_seleccionar_carpeta(client, monkeypatch, return_value=segunda)
    assert current_case(client).carpeta_salida == segunda

    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    assert case.result.output_dir.startswith(segunda)
    assert not case.result.output_dir.startswith(primera)


# ---------------------------------------------------------------------------
# 10/11 — Rechazo durante análisis activo / cierre pendiente: el diálogo
# nunca se abre (falla rápido, sin invocar pick_folder), y el backend nunca
# queda bloqueado esperando al usuario.
# ---------------------------------------------------------------------------


def test_rechazo_durante_analisis_activo_no_invoca_el_dialogo(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    calls = mock_pick_folder(monkeypatch, return_value=str(tmp_path / "no_deberia_usarse"))

    assert tz_web_state.try_start_run("otra-sesion-activa") is True
    try:
        resp = client.post("/output-folder/select")
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["status"] == "error"
        assert data["message"] == tz_web_state.MSG_ANALYSIS_IN_PROGRESS
        assert calls == []  # el diálogo nunca se abrió
        assert current_case(client).carpeta_salida is None
    finally:
        tz_web_state.finish_run("otra-sesion-activa")


def test_rechazo_durante_cierre_pendiente_no_invoca_el_dialogo(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    calls = mock_pick_folder(monkeypatch, return_value=str(tmp_path / "no_deberia_usarse"))

    lifecycle.request_shutdown(reason="test_rechazo_carpeta_cierre_pendiente")
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    try:
        resp = client.post("/output-folder/select")
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["status"] == "error"
        assert data["message"] == tz_web_state.MSG_SHUTDOWN_PENDING
        assert calls == []
        assert current_case(client).carpeta_salida is None
    finally:
        lifecycle.reset_for_tests()


def test_rechazo_si_analisis_comienza_mientras_dialogo_esta_abierto(
    client, monkeypatch, tmp_path
):
    avanzar_modo1_hasta_preparar(client)
    anterior = tmp_path / "seleccion_anterior"
    anterior.mkdir()
    select_output_folder(client, str(anterior))
    elegida = str(tmp_path / "no_debe_persistirse")
    run_id = "iniciado-mientras-dialogo-abierto"

    def _fake_pick_folder(**_kwargs):
        assert tz_web_state.try_start_run(run_id) is True
        return elegida

    def _ensure_no_debe_invocarse(_path):
        pytest.fail("No debe validar/escribir después de detectar el análisis activo")

    monkeypatch.setattr(tz_web_routes, "pick_folder", _fake_pick_folder)
    monkeypatch.setattr(
        tz_web_state, "ensure_writable_dir", _ensure_no_debe_invocarse
    )
    try:
        resp = client.post("/output-folder/select")

        assert resp.status_code == 409
        assert resp.get_json() == {
            "status": "error",
            "message": tz_web_state.MSG_ANALYSIS_IN_PROGRESS,
        }
        assert current_case(client).carpeta_salida == str(anterior)
    finally:
        tz_web_state.finish_run(run_id)


def test_rechazo_si_shutdown_comienza_mientras_dialogo_esta_abierto(
    client, monkeypatch, tmp_path
):
    avanzar_modo1_hasta_preparar(client)
    anterior = tmp_path / "seleccion_anterior"
    anterior.mkdir()
    select_output_folder(client, str(anterior))
    elegida = str(tmp_path / "no_debe_persistirse")

    def _fake_pick_folder(**_kwargs):
        lifecycle.request_shutdown(reason="test_shutdown_mientras_dialogo_abierto")
        return elegida

    def _ensure_no_debe_invocarse(_path):
        pytest.fail("No debe validar/escribir después de detectar el cierre pendiente")

    monkeypatch.setattr(tz_web_routes, "pick_folder", _fake_pick_folder)
    monkeypatch.setattr(
        tz_web_state, "ensure_writable_dir", _ensure_no_debe_invocarse
    )
    try:
        resp = client.post("/output-folder/select")

        assert resp.status_code == 409
        assert resp.get_json() == {
            "status": "error",
            "message": tz_web_state.MSG_SHUTDOWN_PENDING,
        }
        assert current_case(client).carpeta_salida == str(anterior)
    finally:
        lifecycle.reset_for_tests()


def test_segundo_post_de_otra_sesion_recibe_409_mientras_el_primero_sigue_abierto(
    app, monkeypatch, tmp_path
):
    case = tz_web_state.create_session()
    case.modo = tz_web_state.MODO_1
    competing_case = tz_web_state.create_session()
    competing_case.modo = tz_web_state.MODO_3
    first_client = _client_for_case(app, case.id)
    second_client = _client_for_case(app, competing_case.id)
    selected = str(tmp_path / "seleccion-del-primer-post")

    picker_entered = threading.Event()
    release_picker = threading.Event()
    first_done = threading.Event()
    picker_calls = []
    first_result = {}
    first_errors = []

    def _blocking_pick(**kwargs):
        picker_calls.append(kwargs)
        assert callable(kwargs["cancel_requested"])
        assert kwargs["cancel_requested"]() is False
        picker_entered.set()
        assert release_picker.wait(timeout=3), "el test no liberó el selector retenido"
        return selected

    def _post_first():
        try:
            first_result["response"] = first_client.post("/output-folder/select")
        except BaseException as exc:  # noqa: BLE001 - se propaga al hilo principal
            first_errors.append(exc)
        finally:
            first_done.set()

    monkeypatch.setattr(tz_web_routes, "pick_folder", _blocking_pick)
    first_thread = threading.Thread(target=_post_first, name="test-selector-owner")
    first_thread.start()
    try:
        assert picker_entered.wait(timeout=3), "el primer POST no entró al picker"

        second_response = second_client.post("/output-folder/select")

        assert second_response.status_code == 409
        assert second_response.get_json() == {
            "status": "error",
            "message": tz_web_routes._OUTPUT_FOLDER_SELECTOR_BUSY_MESSAGE,
        }
        # Prueba causal de no bloqueo: el segundo ya terminó aunque el evento
        # que permite terminar al primer picker sigue sin activarse.
        assert release_picker.is_set() is False
        assert first_done.is_set() is False
        assert len(picker_calls) == 1
    finally:
        release_picker.set()
        first_thread.join(timeout=3)

    assert first_thread.is_alive() is False
    assert first_errors == []
    assert first_result["response"].status_code == 200
    assert first_result["response"].get_json() == {
        "status": "ok",
        "carpeta_salida": selected,
    }
    assert case.carpeta_salida == selected
    assert competing_case.carpeta_salida is None


def test_rafaga_de_cinco_posts_invoca_un_solo_picker_y_rechaza_los_otros(
    app, monkeypatch, tmp_path
):
    case = tz_web_state.create_session()
    case.modo = tz_web_state.MODO_1
    clients = [_client_for_case(app, case.id) for _ in range(5)]
    selected = str(tmp_path / "seleccion-del-owner")

    picker_entered = threading.Event()
    release_picker = threading.Event()
    owner_done = threading.Event()
    picker_calls = []
    picker_calls_lock = threading.Lock()
    owner_result = {}
    owner_errors = []

    def _blocking_pick(**kwargs):
        with picker_calls_lock:
            picker_calls.append(kwargs)
            ordinal = len(picker_calls)
        if ordinal != 1:
            raise AssertionError("más de un POST alcanzó el picker")
        assert callable(kwargs["cancel_requested"])
        assert kwargs["cancel_requested"]() is False
        picker_entered.set()
        assert release_picker.wait(timeout=3), "el test no liberó el picker owner"
        return selected

    def _post_owner():
        try:
            owner_result["response"] = clients[0].post("/output-folder/select")
        except BaseException as exc:  # noqa: BLE001 - se propaga al hilo principal
            owner_errors.append(exc)
        finally:
            owner_done.set()

    monkeypatch.setattr(tz_web_routes, "pick_folder", _blocking_pick)
    owner_thread = threading.Thread(target=_post_owner, name="test-selector-burst-owner")
    owner_thread.start()

    duplicate_barrier = threading.Barrier(5)
    duplicate_responses = [None] * 4
    duplicate_errors = []

    def _post_duplicate(index):
        try:
            duplicate_barrier.wait(timeout=3)
            duplicate_responses[index] = clients[index + 1].post(
                "/output-folder/select"
            )
        except BaseException as exc:  # noqa: BLE001 - se propaga al hilo principal
            duplicate_errors.append(exc)

    duplicate_threads = [
        threading.Thread(
            target=_post_duplicate,
            args=(index,),
            name=f"test-selector-burst-{index}",
        )
        for index in range(4)
    ]

    try:
        assert picker_entered.wait(timeout=3), "el owner no entró al picker"
        for thread in duplicate_threads:
            thread.start()
        duplicate_barrier.wait(timeout=3)
        for thread in duplicate_threads:
            thread.join(timeout=3)

        assert all(thread.is_alive() is False for thread in duplicate_threads)
        assert duplicate_errors == []
        assert owner_done.is_set() is False
        assert release_picker.is_set() is False
        assert len(picker_calls) == 1
        for response in duplicate_responses:
            assert response is not None
            assert response.status_code == 409
            assert response.get_json() == {
                "status": "error",
                "message": tz_web_routes._OUTPUT_FOLDER_SELECTOR_BUSY_MESSAGE,
            }
    finally:
        release_picker.set()
        owner_thread.join(timeout=3)
        for thread in duplicate_threads:
            if thread.ident is not None:
                thread.join(timeout=3)

    assert owner_thread.is_alive() is False
    assert owner_errors == []
    assert owner_result["response"].status_code == 200
    assert len(picker_calls) == 1
    assert case.carpeta_salida == selected


# ---------------------------------------------------------------------------
# 12 — Ruta con espacios y caracteres Unicode: se persiste y se usa tal
# cual, sin normalizarla ni rechazarla.
# ---------------------------------------------------------------------------


def test_close_when_idle_interrumpe_selector_sin_matar_analisis(
    app, monkeypatch, tmp_path
):
    case = tz_web_state.create_session()
    case.modo = tz_web_state.MODO_1
    anterior = tmp_path / "seleccion-anterior-close-when-idle"
    anterior.mkdir()
    case.carpeta_salida = str(anterior)
    selector_client = _client_for_case(app, case.id)
    analysis = tz_web_state.create_session()
    picker_entered = threading.Event()
    inspect_cancellation = threading.Event()
    response_holder = {}
    errors = []

    def _blocking_pick(*, initial_dir, cancel_requested):
        assert initial_dir == str(anterior)
        picker_entered.set()
        assert inspect_cancellation.wait(timeout=3)
        assert cancel_requested() is True
        raise FolderDialogInterruptedError("cierre diferido solicitado")

    def _post_selector():
        try:
            response_holder["response"] = selector_client.post(
                "/output-folder/select"
            )
        except BaseException as exc:  # noqa: BLE001 - se afirma abajo
            errors.append(exc)

    monkeypatch.setattr(tz_web_routes, "pick_folder", _blocking_pick)
    thread = threading.Thread(target=_post_selector, name="test-selector-close-idle")
    thread.start()
    try:
        assert picker_entered.wait(timeout=3)
        assert tz_web_state.try_start_run(analysis.id) is True
        assert lifecycle.request_shutdown(reason="test_close_when_idle_selector") == (
            lifecycle.CLOSE_WHEN_IDLE
        )
        assert tz_web_state.is_any_run_active() is True
        inspect_cancellation.set()
        thread.join(timeout=3)

        assert not thread.is_alive()
        assert errors == []
        response = response_holder["response"]
        assert response.status_code == 409
        assert response.get_json() == {
            "status": "error",
            "message": tz_web_state.MSG_SHUTDOWN_PENDING,
        }
        assert case.carpeta_salida == str(anterior)
        assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
        assert tz_web_state.is_any_run_active() is True

        tz_web_state.finish_run(analysis.id)
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    finally:
        inspect_cancellation.set()
        thread.join(timeout=3)
        if tz_web_state.is_any_run_active():
            tz_web_state.finish_run(analysis.id)
        lifecycle.reset_for_tests()


def test_ruta_con_espacios_y_unicode_se_persiste_y_produce_alli(client, monkeypatch, tmp_path):
    avanzar_modo1_hasta_preparar(client)
    elegida = str(tmp_path / "Casos 2026 - Investigación Ñoño (José)")
    resp = click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)
    assert resp.status_code == 200
    assert resp.get_json()["carpeta_salida"] == elegida
    assert current_case(client).carpeta_salida == elegida

    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    assert case.result.output_dir.startswith(elegida)
    assert os.path.isfile(case.result.html_path)
    assert "Ñoño" in case.result.output_dir


# ---------------------------------------------------------------------------
# 13/14 — No hay regresión de la publicación transaccional de MB3: hashes
# recomputados coinciden, el manifiesto no se autoincluye, y no queda
# ninguna carpeta de reserva (".{nombre}.tzp") en la carpeta elegida.
# ---------------------------------------------------------------------------


def test_staging_y_publicacion_mb3_sin_regresion_con_carpeta_elegida(client, monkeypatch, tmp_path):
    import hashlib
    from pathlib import Path

    avanzar_modo1_hasta_preparar(client)
    elegida = str(tmp_path / "salida_mb3")
    click_seleccionar_carpeta(client, monkeypatch, return_value=elegida)

    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    case = current_case(client)
    output_dir = case.result.output_dir
    assert output_dir.startswith(elegida)

    # Sin residuos de reserva (".<nombre>.tzp") en la carpeta elegida.
    assert not any(entry.startswith(".") for entry in os.listdir(elegida))

    hashes_path = case.result.hashes_path
    assert os.path.isfile(hashes_path)
    lines = Path(hashes_path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "TZ_ANALYZER_MANIFEST_V1"
    listed_relative = set()
    for line in lines[2:]:
        _algorithm, digest, size, _role, relative_path = line.split("\t", 4)
        artifact = Path(output_dir, *Path(relative_path).parts)
        content = artifact.read_bytes()
        assert len(content) == int(size)
        assert hashlib.sha256(content).hexdigest() == digest
        listed_relative.add(relative_path)

    # El propio manifiesto nunca se autoincluye.
    assert os.path.basename(hashes_path) not in listed_relative
