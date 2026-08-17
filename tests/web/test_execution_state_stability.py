"""Microbloque 2: estabilidad de sesión, workers y concurrencia web."""
from __future__ import annotations

import copy
import hashlib
import io
import os
import threading
import time

import pytest

from tz_web import lifecycle
from tz_web import routes
from tz_web import state
from tz_web.services import CaseResult, FiltroTiempoSinRegistrosError
from tests.web.conftest import attach_csrf_header


def _attach_case(client, modo: str = state.MODO_1) -> state.Session:
    case = state.create_session()
    case.modo = modo
    with client.session_transaction() as browser_session:
        browser_session["case_id"] = case.id
    return case


def _mark_running(case: state.Session) -> None:
    assert state.try_start_run(case.id) is True
    case.status = state.STATUS_RUNNING
    case.task_started = True
    case.started_at = time.time()


def _seed_accepted_input(case: state.Session, tmp_path, content: bytes = b"xlsx-test") -> str:
    upload_dir = tmp_path / f"upload-{case.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / "input.xlsx"
    path.write_bytes(content)
    case.temp_path = str(path)
    case.original_filename = "input.xlsx"
    case.upload_dir = str(upload_dir)
    case.upload_sha256 = hashlib.sha256(content).hexdigest()
    return str(path)


def _contaminate(case: state.Session, tmp_path) -> None:
    upload_dir = os.path.join(state.UPLOAD_ROOT, case.id)
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = os.path.join(upload_dir, "anterior.xlsx")
    with open(temp_path, "wb") as uploaded:
        uploaded.write(b"contenido anterior")

    case.temp_path = temp_path
    case.original_filename = "anterior.xlsx"
    case.upload_dir = upload_dir
    case.upload_sha256 = hashlib.sha256(b"contenido anterior").hexdigest()
    case.available_sheets = ["Anterior"]
    case.sheet = "Anterior"
    case.columns = ["FECHA"]
    case.samples = {"FECHA": ["2025-01-01"]}
    case.mapping = {"fecha": ("col", "FECHA")}
    case.mapping_draft = {"fecha": ("fijo", "residuo")}
    case.identity_overrides = {"alias": "Caso anterior"}
    case.carpeta_salida = str(tmp_path / "salida-anterior")
    case.top_antenas = 99
    case.top_contactos = 88
    case.color_hex = "#123456"
    case.solo_kmz = False
    case.kml_opcional = True
    case.output_base_name = "resultado-anterior"
    case.tipo_bitacora = "T"
    case.filtro_tiempo = {"tipo": "dia", "dia": "2025-01-01"}
    case.modo3_tipo = "antena"
    case.modo3_registros = [{"id": "viejo", "nombre": "Registro anterior"}]
    case.result = CaseResult(success=True, output_dir=str(tmp_path), summary={"viejo": True})
    case.status = state.STATUS_SUCCESS
    case.task_started = True
    case.started_at = 1.0
    case.finished_at = 2.0


def _assert_clean(case: state.Session, modo: str) -> None:
    assert case.modo == modo
    assert case.temp_path is None
    assert case.original_filename is None
    assert case.upload_dir is None
    assert case.upload_sha256 is None
    assert case.input_snapshot_path is None
    assert case.input_snapshot_sha256 is None
    assert case.available_sheets == []
    assert case.sheet is None
    assert case.columns == []
    assert case.samples == {}
    assert case.mapping is None
    assert case.mapping_draft is None
    assert case.mapping_stage == "form"
    assert case.identity_overrides == {}
    assert case.capabilities_preview is None
    assert case.carpeta_salida is None
    assert case.top_antenas is None
    assert case.top_contactos is None
    assert case.color_hex is None
    assert case.solo_kmz is None
    assert case.kml_opcional is False
    assert case.output_base_name is None
    assert case.tipo_bitacora == ""
    assert case.filtro_tiempo is None
    assert case.date_order_decision == "1"
    assert case.duration_unit_decision == "desconocida"
    assert case.qc_bloqueante_decision == "S"
    assert case.modo3_tipo is None
    assert case.modo3_registros == []
    assert case.result is None
    assert case.status == state.STATUS_PENDING
    assert case.stage is None
    assert case.stage_message == ""
    assert case.sequence == 0
    assert case.percent == 0
    assert case.error_message is None
    assert case.error_code is None
    assert case.task_started is False
    assert case.started_at is None
    assert case.finished_at is None


def _current_case_id(client) -> str:
    with client.session_transaction() as browser_session:
        return browser_session["case_id"]


def test_A_new_durante_running_se_rechaza_y_conserva_caso(client, tmp_path):
    case = _attach_case(client)
    _contaminate(case, tmp_path)
    case.status = state.STATUS_PENDING
    case.task_started = False
    case.result = None
    _mark_running(case)
    original = copy.deepcopy(case.__dict__)

    try:
        response = client.post("/new", follow_redirects=True)
        assert response.status_code == 200
        assert state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") in response.data
        assert _current_case_id(client) == case.id
        assert state.get_session(case.id) is case
        assert os.path.isfile(case.temp_path)
        for field_name, value in original.items():
            if field_name != "updated_at":
                assert getattr(case, field_name) == value
    finally:
        state.finish_run(case.id)


@pytest.mark.parametrize("modo3", [False, True])
def test_resumen_con_cierre_pendiente_bloquea_y_muestra_mensaje_especifico(
    client, tmp_path, modo3
):
    """Extremo a extremo (sección 1 del MB5): con lifecycle en
    CLOSE_WHEN_IDLE/SHUTTING_DOWN, la pantalla de resumen no debe arrancar
    un análisis nuevo, y el mensaje mostrado debe ser el de cierre pendiente
    — no el genérico de "ya hay un análisis en curso" (MSG_ANALYSIS_IN_
    PROGRESS), que induciría a error sobre la causa real."""
    case = _attach_case(client, state.MODO_3 if modo3 else state.MODO_1)
    case.carpeta_salida = str(tmp_path / "salida")
    if modo3:
        case.modo3_tipo = "antena"
        case.modo3_registros = [{"id": "a", "nombre": "A"}]
        endpoint = "/modo3/resumen"
    else:
        _seed_accepted_input(case, tmp_path)
        case.mapping = {"fecha": ("col", "FECHA")}
        endpoint = "/configure/resumen"

    lifecycle.request_shutdown(reason="test_resumen_con_cierre_pendiente")
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN

    try:
        response = client.post(endpoint, follow_redirects=True)
        assert response.status_code == 200
        assert state.MSG_SHUTDOWN_PENDING.encode("utf-8") in response.data
        assert state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") not in response.data
        assert case.task_started is False
        assert state.is_any_run_active() is False
    finally:
        lifecycle.reset_for_tests()


def test_B_upload_y_cambios_durante_running_no_mutan_input(client, tmp_path):
    case = _attach_case(client)
    _contaminate(case, tmp_path)
    case.status = state.STATUS_PENDING
    case.task_started = False
    case.result = None
    _mark_running(case)
    original = copy.deepcopy(case.__dict__)

    try:
        responses = [
            client.post(
                "/upload",
                data={"archivo": (io.BytesIO(b"reemplazo"), "reemplazo.xlsx")},
                content_type="multipart/form-data",
                follow_redirects=True,
            ),
            client.post("/file/change", follow_redirects=True),
            client.post("/sheet", data={"hoja": "Otra"}, follow_redirects=True),
            client.post("/sheet/change", follow_redirects=True),
        ]
        assert all(state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") in r.data for r in responses)
        for field_name, value in original.items():
            if field_name != "updated_at":
                assert getattr(case, field_name) == value
        assert os.path.isfile(case.temp_path)
    finally:
        state.finish_run(case.id)


@pytest.mark.parametrize("modo", [state.MODO_1, state.MODO_2, state.MODO_3])
def test_C_seleccion_de_cualquier_modo_durante_running_es_rechazada(client, modo):
    case = _attach_case(client, state.MODO_3)
    case.modo3_tipo = "antena"
    case.modo3_registros = [{"id": "persistente", "nombre": "Antena"}]
    _mark_running(case)

    try:
        response = client.post(f"/modo/{modo}", follow_redirects=True)
        assert state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") in response.data
        assert _current_case_id(client) == case.id
        assert case.modo == state.MODO_3
        assert case.modo3_registros == [{"id": "persistente", "nombre": "Antena"}]
    finally:
        state.finish_run(case.id)


def test_D_transicion_2_a_1_crea_un_caso_limpio(client, tmp_path):
    previous = _attach_case(client, state.MODO_2)
    _contaminate(previous, tmp_path)
    old_id = previous.id
    old_upload_dir = previous.upload_dir

    response = client.post("/modo/1", follow_redirects=True)

    assert response.status_code == 200
    current = state.get_session(_current_case_id(client))
    assert current.id != old_id
    assert state.get_session(old_id) is None
    assert not os.path.exists(old_upload_dir)
    _assert_clean(current, state.MODO_1)


def test_E_transicion_3_a_1_borra_registros_y_crea_caso_limpio(client, tmp_path):
    previous = _attach_case(client, state.MODO_3)
    _contaminate(previous, tmp_path)
    assert previous.modo3_registros

    client.post("/modo/1", follow_redirects=True)

    current = state.get_session(_current_case_id(client))
    assert current is not previous
    _assert_clean(current, state.MODO_1)


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (state.MODO_1, state.MODO_2),
        (state.MODO_2, state.MODO_3),
        (state.MODO_3, state.MODO_2),
    ],
)
def test_F_transiciones_entre_modos_no_conservan_contaminacion(client, tmp_path, origen, destino):
    previous = _attach_case(client, origen)
    _contaminate(previous, tmp_path)

    client.post(f"/modo/{destino}", follow_redirects=True)

    current = state.get_session(_current_case_id(client))
    assert current.id != previous.id
    _assert_clean(current, destino)


class _InlineThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


@pytest.mark.parametrize("modo3", [False, True])
def test_G_fallo_del_logger_no_impide_estado_failed(monkeypatch, tmp_path, modo3):
    case = state.create_session()
    case.carpeta_salida = str(tmp_path)
    if modo3:
        case.modo = state.MODO_3
        case.modo3_tipo = "antena"
        case.modo3_registros = [{"id": "a", "nombre": "A"}]
        process_name = "process_case_modo3"
        starter = routes._start_task_modo3
    else:
        _seed_accepted_input(case, tmp_path)
        case.mapping = {"fecha": ("col", "FECHA")}
        process_name = "process_case"
        starter = routes._start_task

    observed_at_log = {}

    def _process_fails(_request):
        raise FiltroTiempoSinRegistrosError("fallo controlado del motor")

    def _logger_fails(_context, _exc):
        observed_at_log.update(
            status=case.status,
            error_code=case.error_code,
            error_message=case.error_message,
            finished_at=case.finished_at,
            reservation_active=state.is_any_run_active(),
        )
        raise OSError("disco de log no disponible")

    monkeypatch.setattr(routes.threading, "Thread", _InlineThread)
    monkeypatch.setattr(routes, process_name, _process_fails)
    monkeypatch.setattr(state, "log_technical_error", _logger_fails)

    assert starter(case) == (True, None)
    assert case.status == state.STATUS_FAILED
    assert case.error_message
    assert case.error_code == state.ERROR_CODE_FILTRO_SIN_REGISTROS
    assert case.finished_at is not None
    assert state.is_any_run_active() is False
    assert observed_at_log == {
        "status": state.STATUS_FAILED,
        "error_code": state.ERROR_CODE_FILTRO_SIN_REGISTROS,
        "error_message": "fallo controlado del motor",
        "finished_at": case.finished_at,
        "reservation_active": False,
    }


class _BrokenStartThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        raise OSError("no se pudo crear el hilo")


@pytest.mark.parametrize("modo3", [False, True])
def test_H_thread_start_fallido_hace_rollback_y_expone_resultado(
    client, monkeypatch, tmp_path, modo3
):
    case = _attach_case(client, state.MODO_3 if modo3 else state.MODO_1)
    case.carpeta_salida = str(tmp_path)
    if modo3:
        case.modo3_tipo = "antena"
        case.modo3_registros = [{"id": "a", "nombre": "A"}]
        starter = routes._start_task_modo3
    else:
        _seed_accepted_input(case, tmp_path)
        case.mapping = {"fecha": ("col", "FECHA")}
        starter = routes._start_task

    monkeypatch.setattr(routes.threading, "Thread", _BrokenStartThread)

    assert starter(case) == (True, None)
    assert case.status == state.STATUS_FAILED
    assert case.task_started is False
    assert case.finished_at is not None
    assert "No se pudo iniciar el procesamiento" in case.error_message
    assert state.is_any_run_active() is False
    assert state.try_start_run("otra-sesion") is True
    state.finish_run("otra-sesion")

    response = client.get("/processing", follow_redirects=True)
    assert response.request.path == "/results"
    assert "No se pudo iniciar el procesamiento".encode("utf-8") in response.data


@pytest.mark.parametrize("modo3", [False, True])
def test_I_dos_pestanas_misma_sesion_crean_un_solo_worker(
    client, monkeypatch, tmp_path, modo3
):
    case = _attach_case(client, state.MODO_3 if modo3 else state.MODO_1)
    case.carpeta_salida = str(tmp_path / "salida")
    gate = threading.Event()
    worker_started = threading.Event()
    calls = []

    def _slow_process(_request):
        calls.append("worker")
        worker_started.set()
        gate.wait(timeout=10)
        return CaseResult(success=True, output_dir=case.carpeta_salida, summary={})

    if modo3:
        case.modo3_tipo = "antena"
        case.modo3_registros = [{"id": "a", "nombre": "A"}]
        endpoint = "/modo3/resumen"
        monkeypatch.setattr(routes, "process_case_modo3", _slow_process)
    else:
        _seed_accepted_input(case, tmp_path)
        case.mapping = {"fecha": ("col", "FECHA")}
        endpoint = "/configure/resumen"
        monkeypatch.setattr(routes, "process_case", _slow_process)

    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    # Dominio explícito: el fixture ``app`` de conftest.py fija SERVER_NAME a
    # 127.0.0.1:<puerto> (MB7-B5-A1, ver configure_test_instance_host) — ya
    # no es el "localhost" que Werkzeug usaría por defecto sin esa config.
    session_cookie = client.get_cookie(cookie_name, domain="127.0.0.1")
    assert session_cookie is not None
    second_tab = client.application.test_client()
    second_tab.set_cookie(cookie_name, session_cookie.value, domain="127.0.0.1")
    attach_csrf_header(second_tab, client.application)

    try:
        first = client.post(endpoint, data={"accion": "siguiente"})
        assert worker_started.wait(timeout=5)
        second = second_tab.post(endpoint, data={"accion": "siguiente"})
        assert first.status_code == 302
        assert second.status_code == 302
        assert first.headers["Location"].endswith("/processing")
        assert second.headers["Location"].endswith("/processing")
        assert calls == ["worker"]
    finally:
        gate.set()
        deadline = time.time() + 5
        while case.status == state.STATUS_RUNNING and time.time() < deadline:
            time.sleep(0.01)

    assert case.status == state.STATUS_SUCCESS
    assert state.is_any_run_active() is False


class _DeferredThread:
    targets = []

    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon
        self.__class__.targets.append(target)

    def start(self):
        return None


def test_J_requests_son_snapshots_independientes_de_session(monkeypatch, tmp_path):
    _DeferredThread.targets = []
    captured = {}
    monkeypatch.setattr(routes.threading, "Thread", _DeferredThread)

    case = state.create_session()
    _seed_accepted_input(case, tmp_path, b"original")
    case.carpeta_salida = str(tmp_path / "salida-1")
    case.mapping = {"fecha": ("col", "FECHA_ORIGINAL")}
    case.filtro_tiempo = {"tipo": "dia", "dia": "2025-01-01"}
    case.identity_overrides = {"alias": "Original"}

    def _capture_case(request_obj):
        captured["case"] = request_obj
        return CaseResult(success=True, output_dir=request_obj.carpeta_salida, summary={})

    monkeypatch.setattr(routes, "process_case", _capture_case)
    assert routes._start_task(case) == (True, None)
    case.mapping["fecha"] = ("col", "FECHA_MUTADA")
    case.filtro_tiempo["dia"] = "2030-12-31"
    case.identity_overrides["alias"] = "Mutado"
    _DeferredThread.targets.pop(0)()

    case_request = captured["case"]
    assert case_request.mapeo == {"fecha": ("col", "FECHA_ORIGINAL")}
    assert case_request.filtro_tiempo == {"tipo": "dia", "dia": "2025-01-01"}
    assert case_request.identity_overrides == {"alias": "Original"}

    modo3 = state.create_session()
    modo3.modo = state.MODO_3
    modo3.modo3_tipo = "antena"
    modo3.modo3_registros = [
        {"id": "a", "nombre": "Original", "meta": {"etiquetas": ["uno"]}}
    ]
    modo3.carpeta_salida = str(tmp_path / "salida-3")

    def _capture_modo3(request_obj):
        captured["modo3"] = request_obj
        return CaseResult(success=True, output_dir=request_obj.carpeta_salida, summary={})

    monkeypatch.setattr(routes, "process_case_modo3", _capture_modo3)
    assert routes._start_task_modo3(modo3) == (True, None)
    modo3.modo3_registros[0]["nombre"] = "Mutado"
    modo3.modo3_registros[0]["meta"]["etiquetas"].append("dos")
    _DeferredThread.targets.pop(0)()

    modo3_request = captured["modo3"]
    assert modo3_request.registros == [
        {"id": "a", "nombre": "Original", "meta": {"etiquetas": ["uno"]}}
    ]


def test_menu_usa_la_misma_entrada_post_para_los_tres_modos(client):
    response = client.get("/menu")
    html = response.data.decode("utf-8")
    for modo in (state.MODO_1, state.MODO_2, state.MODO_3):
        assert f'action="/modo/{modo}" method="post"' in html


def test_sin_seleccion_explicita_analizador_y_upload_no_crean_modo_1(client):
    response = client.get("/analizador", follow_redirects=True)
    assert response.request.path == "/menu"

    upload_response = client.post(
        "/upload",
        data={"archivo": (io.BytesIO(b"xlsx simulado"), "entrada.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload_response.request.path == "/menu"

    with client.session_transaction() as browser_session:
        assert browser_session.get("case_id") is None


def test_navegar_a_menu_o_analizador_no_descarta_el_caso(client, tmp_path):
    case = _attach_case(client, state.MODO_2)
    _contaminate(case, tmp_path)
    original = copy.deepcopy(case.__dict__)

    assert client.get("/menu").status_code == 200
    assert client.get("/analizador").status_code == 200

    assert _current_case_id(client) == case.id
    assert state.get_session(case.id) is case
    for field_name, value in original.items():
        if field_name != "updated_at":
            assert getattr(case, field_name) == value
