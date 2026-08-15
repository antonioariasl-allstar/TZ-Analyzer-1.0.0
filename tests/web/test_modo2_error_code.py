"""FASE 2 WEB — Modo 2, microajuste estructural: la recuperación "Volver a
revisar filtro temporal" debe decidirse por ``case.error_code`` (una señal
estructural pequeña, ``ERROR_CODE_FILTRO_SIN_REGISTROS``), NUNCA comparando
``case.error_message`` contra un texto. Usa el mismo patrón de monkeypatch
de ``process_case`` que ``tests/web/test_recuperacion_desde_fallo.py`` para
aislar la decisión de navegación del motor real."""
from __future__ import annotations

from tz_web import routes as tz_web_routes
from tz_web import state as tz_web_state
from tz_web.services import ArchivoNoProcesableError, FiltroTiempoSinRegistrosError, MSG_FILTRO_SIN_REGISTROS
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    select_output_folder,
    upload_real_file,
    wait_for_terminal_status,
)


def enter_modo_2(client):
    return client.post("/modo/2", follow_redirects=True)


def current_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


def advance_modo2_to_filtro(client):
    enter_modo_2(client)
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    return client.post("/mapping/confirm", follow_redirects=True)


def submit_filtro(client, filtro_form, accion="siguiente"):
    """Completa las dos pantallas reales del Filtro temporal de Modo 2:
    Pantalla 1 (selección del tipo, ``filtro_tipo``) y Pantalla 2
    (parámetros exclusivos de ese tipo, el resto de ``filtro_form``)."""
    filtro_form = dict(filtro_form)
    tipo = filtro_form.pop("filtro_tipo")
    client.post(
        "/configure/filtro-tiempo",
        data={"accion": "siguiente", "filtro_tipo": tipo},
        follow_redirects=True,
    )
    data = {"accion": accion}
    data.update(filtro_form)
    return client.post("/configure/filtro-tiempo/parametros", data=data, follow_redirects=True)


def run_modo2_hasta_fallo(client, monkeypatch, exc):
    """Deja una sesión Modo 2 en estado FAILED con ``exc`` como causa,
    interceptando ``process_case`` (mismo patrón que
    ``test_recuperacion_desde_fallo.py::_force_failure``) — no depende de
    que el motor real produzca 0 filas."""

    def _raise(_req):
        raise exc

    monkeypatch.setattr(tz_web_routes, "process_case", _raise)

    advance_modo2_to_filtro(client)
    submit_filtro(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})
    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)
    select_output_folder(client)
    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    return wait_for_terminal_status(client)


# ---------------------------------------------------------------------------
# 1. Cambiar el texto visible no afecta la recuperación.
# ---------------------------------------------------------------------------


def test_cambio_de_texto_visible_no_afecta_la_recuperacion(client, monkeypatch):
    mensaje_distinto = "Un texto completamente distinto, sin relación con la constante estándar."
    status = run_modo2_hasta_fallo(client, monkeypatch, FiltroTiempoSinRegistrosError(mensaje_distinto))
    assert status["status"] == "failed"

    case = current_case(client)
    assert case.error_message == mensaje_distinto
    assert case.error_message != MSG_FILTRO_SIN_REGISTROS
    assert case.error_code == tz_web_state.ERROR_CODE_FILTRO_SIN_REGISTROS

    resp = client.get("/results")
    html = resp.data.decode("utf-8")
    assert mensaje_distinto in html
    assert "Volver a revisar filtro temporal" in html


# ---------------------------------------------------------------------------
# 2. error_code == filtro_sin_registros muestra el botón de filtro.
# ---------------------------------------------------------------------------


def test_error_code_filtro_sin_registros_muestra_boton_de_filtro(client, monkeypatch):
    status = run_modo2_hasta_fallo(
        client, monkeypatch, FiltroTiempoSinRegistrosError(MSG_FILTRO_SIN_REGISTROS)
    )
    assert status["status"] == "failed"

    case = current_case(client)
    assert case.error_code == tz_web_state.ERROR_CODE_FILTRO_SIN_REGISTROS

    resp = client.get("/results")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Volver a revisar filtro temporal" in html
    assert "Volver a revisar mapeo" in html


# ---------------------------------------------------------------------------
# 3. Otros errores no muestran ese botón, y "Volver a revisar mapeo" sigue.
# ---------------------------------------------------------------------------


def test_error_generico_con_mismo_texto_no_muestra_boton_de_filtro(client, monkeypatch):
    """Defensa directa contra volver a acoplar por texto: una
    ArchivoNoProcesableError genérica (NO la subclase) con el MISMO texto
    que la constante estándar no debe activar la recuperación de filtro."""
    status = run_modo2_hasta_fallo(
        client, monkeypatch, ArchivoNoProcesableError(MSG_FILTRO_SIN_REGISTROS)
    )
    assert status["status"] == "failed"

    case = current_case(client)
    assert case.error_message == MSG_FILTRO_SIN_REGISTROS
    assert case.error_code is None

    resp = client.get("/results")
    html = resp.data.decode("utf-8")
    assert "Volver a revisar filtro temporal" not in html
    assert "Volver a revisar mapeo" in html


def test_otro_tipo_de_error_no_muestra_boton_de_filtro(client, monkeypatch):
    status = run_modo2_hasta_fallo(
        client, monkeypatch, ArchivoNoProcesableError("Los chequeos de salud de datos impidieron continuar.")
    )
    assert status["status"] == "failed"

    case = current_case(client)
    assert case.error_code is None

    resp = client.get("/results")
    html = resp.data.decode("utf-8")
    assert "Volver a revisar filtro temporal" not in html
    assert "Volver a revisar mapeo" in html


# ---------------------------------------------------------------------------
# 4. Volver al filtro limpia el estado terminal y conserva el filtro previo.
# ---------------------------------------------------------------------------


def test_volver_al_filtro_limpia_estado_terminal_y_conserva_filtro(client, monkeypatch):
    run_modo2_hasta_fallo(client, monkeypatch, FiltroTiempoSinRegistrosError(MSG_FILTRO_SIN_REGISTROS))

    case_antes = current_case(client)
    filtro_previo = dict(case_antes.filtro_tiempo)
    archivo_antes, hoja_antes, mapping_antes = case_antes.temp_path, case_antes.sheet, dict(case_antes.mapping)
    top_antenas_antes, color_antes = case_antes.top_antenas, case_antes.color_hex

    resp = client.post("/results/back-to-filtro-tiempo", follow_redirects=True)
    assert resp.status_code == 200
    assert "Filtro temporal".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.status == tz_web_state.STATUS_PENDING
    assert case.error_message is None
    assert case.error_code is None
    assert case.result is None
    assert case.finished_at is None
    assert case.task_started is False

    # El filtro (incorrecto o no) sigue precargado para corregirlo.
    assert case.filtro_tiempo == filtro_previo
    assert case.temp_path == archivo_antes
    assert case.sheet == hoja_antes
    assert case.mapping == mapping_antes
    assert case.top_antenas == top_antenas_antes
    assert case.color_hex == color_antes
