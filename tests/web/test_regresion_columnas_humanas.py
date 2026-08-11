"""FASE 2 WEB — Regresión: coherencia de nombres de columna entre la UI de
mapeo y process_case() cuando el Excel trae encabezados "humanos" (no
normalizados: mayúsculas, espacios, guiones, acentos).

Reproduce y blinda el defecto descrito en el diagnóstico "MAPPING CORRECTO
EN UI PERO FALLA EN PROCESS_CASE": la UI (tz_web.routes, vía
cargar_excel_con_normalizacion) conservaba encabezados como
"NUMERO DE ORIGEN" y los guardaba tal cual en el mapeo, pero
process_case() volvía a cargar el archivo con gather_dataset_metadata(),
que renombra encabezados a minúsculas_con_guion_bajo — rompiendo la
correspondencia y produciendo InvalidMappingError pese a un mapeo correcto.

No sustituye tests/data/bitacora_test.tsv.xlsx ni sus pruebas existentes
(ver test_mapping.py / test_processing_and_results.py, que ya cubren el
fixture snake_case/mayúsculas-sin-espacios "REAL_MAPPING_FORM"): agrega una
cobertura específica para encabezados no normalizados.
"""
from __future__ import annotations

import os

from tz_web import state as tz_web_state
from tz_web.services import CaseRequest
from tests.web.conftest import (
    HUMAN_MAPPING_FORM,
    HUMAN_SHEET_NAME,
    upload_file_from_path,
    wait_for_terminal_status,
)


def _reach_mapping_screen_humano(client, human_headers_file):
    upload_file_from_path(client, human_headers_file, "bitacora_encabezados_humanos.xlsx")
    return client.post("/sheet", data={"hoja": HUMAN_SHEET_NAME}, follow_redirects=True)


def _submit_configure(client, tmp_path, **overrides):
    outdir = str(tmp_path / "salida_humana")
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


def test_pantalla_de_hoja_ofrece_encabezados_sin_normalizar(client, human_headers_file):
    resp = _reach_mapping_screen_humano(client, human_headers_file)
    assert resp.status_code == 200
    assert "NUMERO DE ORIGEN".encode("utf-8") in resp.data
    assert "IMEI-ORIGEN".encode("utf-8") in resp.data
    assert "NÚMERO DESTINO".encode("utf-8") in resp.data


def test_mapeo_conserva_encabezado_humano_exacto_hasta_confirmar(client, human_headers_file):
    _reach_mapping_screen_humano(client, human_headers_file)
    client.post("/mapping", data=dict(HUMAN_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    # El valor guardado debe seguir siendo EXACTAMENTE el encabezado humano
    # que la UI mostró — nada lo reescribe a snake_case en el camino.
    assert case.mapping["tel"] == ("col", "NUMERO DE ORIGEN")
    assert case.mapping["imei"] == ("col", "IMEI-ORIGEN")
    assert case.mapping["contacto"] == ("col", "NÚMERO DESTINO")


def test_caserequest_mapeo_llega_intacto_a_process_case(client, human_headers_file, tmp_path, monkeypatch):
    """Traza tel -> ... -> CaseRequest.mapeo (sección 1 del diagnóstico):
    debe llegar EXACTAMENTE "NUMERO DE ORIGEN" al servicio no interactivo."""
    from tz_web import routes as tz_web_routes

    capturado = {}
    original_process_case = tz_web_routes.process_case

    def _capture(req: CaseRequest):
        capturado["req"] = req
        return original_process_case(req)

    monkeypatch.setattr(tz_web_routes, "process_case", _capture)

    _reach_mapping_screen_humano(client, human_headers_file)
    client.post("/mapping", data=dict(HUMAN_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)
    _submit_configure(client, tmp_path)
    wait_for_terminal_status(client)

    req = capturado["req"]
    assert isinstance(req, CaseRequest)
    assert req.mapeo["tel"] == ("col", "NUMERO DE ORIGEN")


def test_recorrido_completo_con_encabezados_humanos_procesa_sin_error(client, human_headers_file, tmp_path):
    """Reproduce exactamente el recorrido reportado como roto: upload ->
    selección de hoja -> mapping_submit -> mapping_confirm -> configuración
    -> CaseRequest -> process_case. Antes de la corrección, esto terminaba
    en status == 'failed' con InvalidMappingError ("La columna 'NUMERO DE
    ORIGEN' asignada a 'tel' no existe en el archivo de entrada")."""
    _reach_mapping_screen_humano(client, human_headers_file)
    resp = client.post("/mapping", data=dict(HUMAN_MAPPING_FORM), follow_redirects=True)
    assert "Revisión del mapeo".encode("utf-8") in resp.data

    client.post("/mapping/confirm", follow_redirects=True)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)

    assert status["status"] == "success", status

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.error_message is None
    assert case.result is not None
    assert case.result.success is True
    assert case.result.html_path and os.path.isfile(case.result.html_path)


def test_process_case_no_usa_gather_dataset_metadata(monkeypatch):
    """Blindaje estructural (sección 5 del microbloque): si en el futuro se
    reintroduce gather_dataset_metadata() como ruta de carga de
    process_case(), esta prueba debe fallar de inmediato en vez de esperar
    a que un usuario reporte un mapeo "fantasma" roto."""
    import tz_web.services as services_mod

    assert "gather_dataset_metadata" not in dir(services_mod)


def test_columnas_de_ui_coinciden_con_las_que_valida_process_case(client, human_headers_file, tmp_path, monkeypatch):
    """Regla de consistencia (sección 3 del microbloque): las columnas que
    la pantalla de mapeo mostró/guardó deben ser EXACTAMENTE las mismas que
    ve process_case() al validar request.mapeo, para el mismo archivo/hoja.
    """
    import tz_web.services as services_mod

    columnas_vistas_por_process_case = {}
    original_loader = services_mod.cargar_excel_con_normalizacion

    def _spy(ruta, hoja):
        df, hoja_real = original_loader(ruta, hoja)
        columnas_vistas_por_process_case["columnas"] = [str(c) for c in df.columns]
        return df, hoja_real

    monkeypatch.setattr(services_mod, "cargar_excel_con_normalizacion", _spy)

    _reach_mapping_screen_humano(client, human_headers_file)
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    columnas_vistas_por_ui = list(tz_web_state.get_session(case_id).columns)

    client.post("/mapping", data=dict(HUMAN_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)

    assert status["status"] == "success", status
    assert columnas_vistas_por_process_case["columnas"] == columnas_vistas_por_ui


def test_otro_campo_con_guion_y_acento_tambien_procesa(client, human_headers_file, tmp_path):
    """No es un defecto exclusivo de 'tel': imei (guion) y contacto (acento)
    deben resolverse igual de bien (sección 5 del diagnóstico)."""
    _reach_mapping_screen_humano(client, human_headers_file)
    client.post("/mapping", data=dict(HUMAN_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)
    _submit_configure(client, tmp_path)
    status = wait_for_terminal_status(client)

    assert status["status"] == "success", status
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping["imei"] == ("col", "IMEI-ORIGEN")
    assert case.mapping["contacto"] == ("col", "NÚMERO DESTINO")
