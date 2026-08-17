"""FASE 2 WEB — Pantallas 4/5: procesamiento, polling, resultados y apertura
segura de productos (secciones 6, 9, 10, 11)."""
from __future__ import annotations

import builtins
import os
import threading
import zipfile

import pytest

from tz_web import routes as tz_web_routes
from tz_web import state as tz_web_state
from tz_web.services import CaseRequest, CaseResult, ArchivoNoProcesableError
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    advance_to_configure,
    attach_csrf_header,
    upload_real_file,
    wait_for_terminal_status,
)


def _submit_configure(client, tmp_path, **overrides):
    outdir = str(tmp_path / "salida")
    data = {
        "tipo_bitacora": "", "output_base_name": "",
        "identidad_alias": "", "identidad_nombre_usuario": "", "identidad_abonado": "",
        "top_antenas": "", "top_contactos": "", "color_hex": "#76ff03",
        "solo_kmz": "on",
        "filtro_tipo": "ninguno",
        "date_order_decision": "1", "duration_unit_decision": "segundos", "qc_bloqueante_decision": "S",
        "carpeta_salida": outdir,
    }
    data.update(overrides)
    return client.post("/configure/legacy", data=data, follow_redirects=True)


def test_procesamiento_sin_tarea_iniciada_redirige_a_configuracion(client):
    advance_to_configure(client)
    resp = client.get("/processing", follow_redirects=True)
    assert resp.status_code == 200
    assert "Primero configure y confirme".encode("utf-8") in resp.data


def test_polling_de_estado_progresa_hasta_finalizado(client, tmp_path):
    advance_to_configure(client)
    _submit_configure(client, tmp_path)

    vistos = set()
    for _ in range(200):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        vistos.add(data["stage"])
        if data["status"] in ("success", "failed"):
            assert data["percent"] == 100
            break
        import time
        time.sleep(0.05)
    else:
        pytest.fail("El polling nunca llegó a un estado terminal")

    assert "validando_entrada" in vistos or "finalizado" in vistos


def test_status_sin_sesion_devuelve_404(client):
    resp = client.get("/status")
    assert resp.status_code == 404


def test_resultado_exitoso_con_fixture_real(client, tmp_path):
    advance_to_configure(client)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    resp = client.get("/results")
    assert resp.status_code == 200
    assert "Análisis finalizado correctamente".encode("utf-8") in resp.data
    assert b"Abrir HTML" in resp.data
    assert b"Abrir KMZ" in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.result.success is True
    assert case.result.html_path and os.path.isfile(case.result.html_path)
    assert case.result.kmz_path and os.path.isfile(case.result.kmz_path)


def test_eventos_de_procesamiento_no_registran_ruta_ni_nombre_de_archivo(client, tmp_path, caplog):
    """MICROBLOQUE 7-B3 (sección 12C): inicio/fin de process_case() se
    registran en el log técnico central sin el nombre del archivo subido ni
    la carpeta de salida elegida."""
    advance_to_configure(client)

    with caplog.at_level("INFO", logger="tz_web.routes"):
        _submit_configure(client, tmp_path)
        status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    mensajes = [record.getMessage() for record in caplog.records]
    assert any("Procesamiento de caso iniciado" in m for m in mensajes)
    assert any("Procesamiento de caso finalizado" in m for m in mensajes)
    assert not any("bitacora_test" in m for m in mensajes)
    assert not any(str(tmp_path) in m for m in mensajes)


def test_log_technical_error_real_redacta_ruta_y_conserva_tipo(client, monkeypatch, tmp_path, caplog):
    """Sin monkeypatchear ``log_technical_error``: verifica el comportamiento
    real migrado a ``tz_logging`` (secciones 10/11) — el tipo de excepción
    queda legible, pero una ruta de caso embebida en el mensaje se redacta."""
    advance_to_configure(client)
    ruta_sensible = "C:\\CASOS\\Investigacion_Juan_Perez\\bitacora.xlsx"

    def _raise(_req):
        raise RuntimeError(f"fallo simulado leyendo {ruta_sensible!r}")

    monkeypatch.setattr(tz_web_routes, "process_case", _raise)
    with caplog.at_level("ERROR", logger="tz_web.technical"):
        _submit_configure(client, tmp_path)
        status = wait_for_terminal_status(client)
        # ``case.status`` pasa a "failed" antes de que el worker llame a
        # log_technical_error() (ver _mark_run_failed): una espera acotada
        # evita la carrera con el polling de arriba.
        import time as _time
        deadline = _time.time() + 2.0
        while _time.time() < deadline and not caplog.records:
            _time.sleep(0.02)
    assert status["status"] == "failed"

    mensajes = "\n".join(record.getMessage() for record in caplog.records)
    assert "RuntimeError" in mensajes
    assert "<ruta_redactada>" in mensajes
    assert "Juan_Perez" not in mensajes
    assert ruta_sensible not in mensajes


def test_resultado_parcial_muestra_advertencias_y_errores(client, monkeypatch, tmp_path):
    """KML solicitado ausente es PARTIAL con los obligatorios disponibles."""
    advance_to_configure(client)

    output_dir = tmp_path / "salida_parcial"
    output_dir.mkdir()
    html_path = output_dir / "informe.html"
    html_path.write_text("<html>resultado disponible</html>", encoding="utf-8")
    kmz_path = output_dir / "mapa.kmz"
    with zipfile.ZipFile(kmz_path, "w") as kmz:
        kmz.writestr("doc.kml", "<?xml version='1.0'?><kml/>")
    hashes_path = output_dir / "caso_hashes.txt"
    hashes_path.write_text("TZ_ANALYZER_MANIFEST_V1\n", encoding="utf-8")

    resultado_parcial = CaseResult(
        success=True,
        output_dir=str(output_dir),
        html_path=str(html_path),
        kmz_path=str(kmz_path),
        hashes_path=str(hashes_path),
        log_path=None,
        warnings=["No se generó el producto opcional solicitado: kml."],
        errors=[],
        summary={"filas_totales": 10},
        status="partial",
    )
    assert resultado_parcial.success is False

    monkeypatch.setattr(tz_web_routes, "process_case", lambda _req: resultado_parcial)
    _submit_configure(client, tmp_path, carpeta_salida=resultado_parcial.output_dir)
    status = wait_for_terminal_status(client)
    assert status["status"] == "partial"

    resp = client.get("/results")
    assert resp.status_code == 200
    assert b"finalizado parcialmente" in resp.data
    assert b"finalizado correctamente" not in resp.data
    assert b"Volver a configurar productos" in resp.data

    with client.session_transaction() as flask_sess:
        case = tz_web_state.get_session(flask_sess["case_id"])
    snapshot_path = case.input_snapshot_path
    snapshot_sha256 = case.input_snapshot_sha256

    back = client.post("/results/back-to-products", follow_redirects=True)
    assert back.request.path == "/configure/productos"
    assert case.status == tz_web_state.STATUS_PENDING
    assert case.input_snapshot_path == snapshot_path
    assert case.input_snapshot_sha256 == snapshot_sha256
    assert "No se generó el producto opcional solicitado: kml".encode("utf-8") in resp.data


def _advance_to_configure_sin_contacto(client):
    """Como ``advance_to_configure``, pero omitiendo el mapeo de la columna
    `contacto` — reproduce una bitácora que no trae ese campo."""
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    mapeo_sin_contacto = dict(REAL_MAPPING_FORM)
    mapeo_sin_contacto["tipo_contacto"] = "omitido"
    mapeo_sin_contacto.pop("col_contacto", None)
    client.post("/mapping", data=mapeo_sin_contacto, follow_redirects=True)
    return client.post("/mapping/confirm", follow_redirects=True)


def test_resultado_top_contactos_disponible_refleja_configuracion(client, tmp_path):
    """Con `contacto` mapeado, Resultados debe mostrar el Top N configurado,
    coherente con lo pedido en Configuración."""
    advance_to_configure(client)
    _submit_configure(client, tmp_path, top_contactos="8")
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    resp = client.get("/results")
    html = resp.data.decode("utf-8")
    assert "Alcance" in html
    assert "Bitácora completa" in html
    assert "Filtro temporal" not in html
    assert "Sin filtro de tiempo" not in html

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.result.summary["contactos_disponible"] is True
    assert case.result.summary["top_contactos"] == 8
    assert "Top contactos" in html
    assert "No disponible" not in html


def test_resultado_contacto_omitido_no_muestra_top_numerico(client, tmp_path):
    """Sin `contacto` mapeado, la capacidad "contactos" no está disponible:
    Resultados no debe mostrar ningún número como si fuera un Top de
    contactos real."""
    _advance_to_configure_sin_contacto(client)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.result.summary["contactos_disponible"] is False

    resp = client.get("/results")
    html = resp.data.decode("utf-8")
    assert "No disponible" in html


def test_error_controlado_no_muestra_traceback(client, monkeypatch, tmp_path):
    advance_to_configure(client)

    def _raise(_req):
        raise ArchivoNoProcesableError("No hay registros para procesar después de aplicar filtros.")

    monkeypatch.setattr(tz_web_routes, "process_case", _raise)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)
    assert status["status"] == "failed"

    resp = client.get("/results")
    assert resp.status_code == 200
    assert "No hay registros para procesar".encode("utf-8") in resp.data
    assert b"Traceback" not in resp.data
    assert b".py\", line" not in resp.data


def test_error_no_controlado_muestra_mensaje_generico_y_registra_tecnico(client, monkeypatch, tmp_path):
    advance_to_configure(client)

    registrado = {}

    def _raise(_req):
        raise RuntimeError("detalle interno sensible que no debe llegar al navegador")

    def _fake_log(context, exc):
        registrado["context"] = context
        registrado["exc"] = exc

    monkeypatch.setattr(tz_web_routes, "process_case", _raise)
    monkeypatch.setattr(tz_web_state, "log_technical_error", _fake_log)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)
    assert status["status"] == "failed"

    resp = client.get("/results")
    assert b"detalle interno sensible" not in resp.data
    assert "error inesperado".encode("utf-8") in resp.data
    assert registrado.get("context") == "process_case"
    assert "detalle interno sensible" in str(registrado.get("exc"))


def test_kml_path_se_expone_cuando_solo_kmz_es_false(client, tmp_path):
    """Con solo_kmz=False (KML opcional activado en 3C), CaseResult.kml_path
    debe apuntar a un archivo real dentro de output_dir y results.html debe
    ofrecer "Abrir KML"."""
    advance_to_configure(client)
    _submit_configure(client, tmp_path, solo_kmz="")
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.result.kml_path is not None
    assert os.path.isfile(case.result.kml_path)
    assert os.path.commonpath(
        [os.path.abspath(case.result.kml_path), os.path.abspath(case.result.output_dir)]
    ) == os.path.abspath(case.result.output_dir)

    resp = client.get("/results")
    assert b"Abrir KML" in resp.data


def test_kml_path_ausente_cuando_solo_kmz_es_true(client, tmp_path):
    """Comportamiento por defecto (solo_kmz=True): no debe exponerse
    kml_path ni el botón "Abrir KML" en Resultados."""
    advance_to_configure(client)
    _submit_configure(client, tmp_path, solo_kmz="on")
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.result.kml_path is None

    resp = client.get("/results")
    assert b"Abrir KML" not in resp.data


def test_open_kml_usa_las_mismas_validaciones_de_seguridad(client, monkeypatch, tmp_path):
    advance_to_configure(client)
    _submit_configure(client, tmp_path, solo_kmz="")
    wait_for_terminal_status(client)

    llamadas = []
    monkeypatch.setattr(tz_web_routes, "_open_with_default_app", lambda path: llamadas.append(path))

    resp = client.post("/open/kml", follow_redirects=True)
    assert resp.status_code == 200
    assert len(llamadas) == 1

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert llamadas[0] == os.path.abspath(case.result.kml_path)

    # Una ruta manipulada fuera de output_dir nunca debe abrirse.
    llamadas.clear()
    fuera_de_carpeta = str(tmp_path / "otro_lugar_kml" / "archivo.kml")
    os.makedirs(os.path.dirname(fuera_de_carpeta), exist_ok=True)
    with open(fuera_de_carpeta, "w") as fh:
        fh.write("contenido")
    case.result.kml_path = fuera_de_carpeta

    resp = client.post("/open/kml", follow_redirects=True)
    assert resp.status_code == 200
    assert "no está disponible".encode("utf-8") in resp.data
    assert llamadas == []


def test_bloqueo_de_segunda_tarea_simultanea(app, tmp_path):
    """Dos sesiones distintas: la segunda no puede iniciar mientras la
    primera sigue en ejecución (sección 9)."""
    client_a = app.test_client()
    attach_csrf_header(client_a, app)
    client_b = app.test_client()
    attach_csrf_header(client_b, app)

    gate = threading.Event()

    def _slow_process(_req):
        gate.wait(timeout=10)
        return CaseResult(success=True, output_dir=str(tmp_path / "a"), summary={})

    import tz_web.routes as routes_mod
    original = routes_mod.process_case
    routes_mod.process_case = _slow_process
    try:
        advance_to_configure(client_a)
        # La segunda sesión se configura antes de reservar la ejecución. Una
        # vez activa la primera, incluso sus POST de configuración quedan
        # sujetos a la guarda central y no pueden iniciar otro worker.
        advance_to_configure(client_b)
        os.makedirs(tmp_path / "a", exist_ok=True)
        resp_a = _submit_configure(client_a, tmp_path, carpeta_salida=str(tmp_path / "a"))
        assert "Procesando análisis".encode("utf-8") in resp_a.data

        resp_b = _submit_configure(client_b, tmp_path, carpeta_salida=str(tmp_path / "b"))
        assert tz_web_state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") in resp_b.data
        assert "Carpeta de salida".encode("utf-8") in resp_b.data  # se quedó en /configure/legacy

        with client_b.session_transaction() as flask_sess:
            case_id_b = flask_sess["case_id"]
        case_b = tz_web_state.get_session(case_id_b)
        assert case_b.task_started is False
    finally:
        gate.set()
        routes_mod.process_case = original
        wait_for_terminal_status(client_a)


def test_apertura_segura_de_producto(client, monkeypatch, tmp_path):
    advance_to_configure(client)
    _submit_configure(client, tmp_path)
    wait_for_terminal_status(client)

    llamadas = []
    monkeypatch.setattr(tz_web_routes, "_open_with_default_app", lambda path: llamadas.append(path))

    resp = client.post("/open/html", follow_redirects=True)
    assert resp.status_code == 200
    assert len(llamadas) == 1

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert llamadas[0] == os.path.abspath(case.result.html_path)


def test_rechazo_de_ruta_manipulada(client, monkeypatch, tmp_path):
    """kind desconocido, o un CaseResult apuntando fuera de output_dir,
    nunca deben resultar en una apertura."""
    advance_to_configure(client)
    _submit_configure(client, tmp_path)
    wait_for_terminal_status(client)

    llamadas = []
    monkeypatch.setattr(tz_web_routes, "_open_with_default_app", lambda path: llamadas.append(path))

    resp = client.post("/open/no_es_un_kind_valido", follow_redirects=True)
    assert resp.status_code == 200
    assert "no está disponible".encode("utf-8") in resp.data
    assert llamadas == []

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    fuera_de_carpeta = str(tmp_path / "otro_lugar" / "archivo.html")
    os.makedirs(os.path.dirname(fuera_de_carpeta), exist_ok=True)
    with open(fuera_de_carpeta, "w") as fh:
        fh.write("contenido")
    case.result.html_path = fuera_de_carpeta

    resp = client.post("/open/html", follow_redirects=True)
    assert resp.status_code == 200
    assert "no está disponible".encode("utf-8") in resp.data
    assert llamadas == []


def test_open_sin_resultado_devuelve_404(client):
    resp = client.post("/open/html")
    assert resp.status_code == 404


def test_nuevo_analisis_limpia_temporales_y_sesion(client, tmp_path):
    advance_to_configure(client)
    _submit_configure(client, tmp_path)
    wait_for_terminal_status(client)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    upload_dir = case.upload_dir
    assert os.path.isdir(upload_dir)

    resp = client.post("/new", follow_redirects=True)
    assert resp.status_code == 200
    assert "Procesar bitácora completa".encode("utf-8") in resp.data

    assert tz_web_state.get_session(case_id) is None
    assert not os.path.isdir(upload_dir)


def test_process_case_recibe_caserequest_correcto(client, monkeypatch, tmp_path):
    advance_to_configure(client)

    capturado = {}

    def _capture(req: CaseRequest):
        capturado["req"] = req
        return CaseResult(success=True, output_dir=str(tmp_path / "cap"), summary={})

    os.makedirs(tmp_path / "cap", exist_ok=True)
    monkeypatch.setattr(tz_web_routes, "process_case", _capture)
    _submit_configure(
        client, tmp_path,
        carpeta_salida=str(tmp_path / "cap"),
        top_antenas="7", top_contactos="3",
        duration_unit_decision="segundos",
        identidad_alias="Alias de prueba",
    )
    wait_for_terminal_status(client)

    req = capturado["req"]
    assert isinstance(req, CaseRequest)
    assert req.mapeo["fecha"] == ("col", "FECHA_INICIAL")
    assert req.carpeta_salida == str(tmp_path / "cap")
    assert req.top_antenas == 7
    assert req.top_contactos == 3
    assert req.duration_unit_decision == "segundos"
    assert req.identity_overrides == {"alias": "Alias de prueba"}
    assert callable(req.on_progress)


def test_ejecucion_web_no_invoca_input_ni_safe_input_ni_tkinter(client, monkeypatch, tmp_path):
    def _canary_input(*_a, **_k):
        pytest.fail("La ejecución vía web invocó builtins.input()")

    def _canary_safe_input(*_a, **_k):
        pytest.fail("La ejecución vía web invocó tz_core.ingestion_pipeline.safe_input()")

    def _canary_tk(*_a, **_k):
        pytest.fail("La ejecución vía web intentó abrir Tkinter")

    monkeypatch.setattr(builtins, "input", _canary_input)
    monkeypatch.setattr("tz_core.ingestion_pipeline.safe_input", _canary_safe_input)
    monkeypatch.setattr("tkinter.Tk", _canary_tk, raising=False)

    advance_to_configure(client)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"
