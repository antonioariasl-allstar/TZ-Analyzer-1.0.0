"""FASE 2 WEB — Recuperación desde un análisis fallido (microbloque
"COHERENCIA DE COLUMNAS UI -> PROCESS_CASE + RECUPERACIÓN DESDE ERROR").

Cubre la acción "Volver a revisar mapeo" en la pantalla de Resultados
cuando ``case.status == 'failed'``: debe llevar a "Revisión del mapeo" sin
perder archivo, hoja, mapeo ni Configuración 3A-3E, y debe permitir volver
a ejecutar el análisis tras corregir. También confirma que "Iniciar nuevo
análisis" sigue comportándose igual que antes."""
from __future__ import annotations

import os

from tz_web import routes as tz_web_routes
from tz_web import state as tz_web_state
from tz_web.services import ArchivoNoProcesableError
from tests.web.conftest import REAL_MAPPING_FORM, advance_to_configure, wait_for_terminal_status


def _submit_configure(client, tmp_path, **overrides):
    outdir = str(tmp_path / "salida")
    data = {
        "tipo_bitacora": "", "output_base_name": "",
        "identidad_alias": "", "identidad_nombre_usuario": "", "identidad_abonado": "",
        "top_antenas": "5", "top_contactos": "7", "color_hex": "#76ff03",
        "solo_kmz": "on",
        "filtro_tipo": "ninguno",
        "date_order_decision": "1", "duration_unit_decision": "segundos", "qc_bloqueante_decision": "S",
        "carpeta_salida": outdir,
    }
    data.update(overrides)
    return client.post("/configure/legacy", data=data, follow_redirects=True)


def _force_failure(client, tmp_path, monkeypatch, mensaje="No hay registros para procesar después de aplicar filtros."):
    def _raise(_req):
        raise ArchivoNoProcesableError(mensaje)

    monkeypatch.setattr(tz_web_routes, "process_case", _raise)
    advance_to_configure(client)
    _submit_configure(client, tmp_path, top_antenas="5", top_contactos="7", identidad_alias="Alias de prueba")
    return wait_for_terminal_status(client)


def _get_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


def test_fallo_controlado_muestra_boton_volver_a_revisar_mapeo(client, tmp_path, monkeypatch):
    status = _force_failure(client, tmp_path, monkeypatch)
    assert status["status"] == "failed"

    resp = client.get("/results")
    assert resp.status_code == 200
    assert "Volver a revisar mapeo".encode("utf-8") in resp.data
    assert "Iniciar nuevo análisis".encode("utf-8") in resp.data


def test_boton_lleva_a_revision_del_mapeo(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)

    resp = client.post("/results/back-to-mapping", follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data

    case = _get_case(client)
    assert case.mapping_draft == case.mapping


def test_mapping_hoja_y_archivo_siguen_presentes_tras_recuperacion(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)
    case_antes = _get_case(client)
    mapping_antes = dict(case_antes.mapping)
    sheet_antes = case_antes.sheet
    temp_path_antes = case_antes.temp_path

    client.post("/results/back-to-mapping", follow_redirects=True)

    case_despues = _get_case(client)
    assert case_despues.mapping == mapping_antes
    assert case_despues.sheet == sheet_antes
    assert case_despues.temp_path == temp_path_antes
    assert os.path.isfile(case_despues.temp_path)


def test_configuracion_3a_3e_se_conserva_tras_recuperacion(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)
    case_antes = _get_case(client)
    top_antenas_antes = case_antes.top_antenas
    top_contactos_antes = case_antes.top_contactos
    color_antes = case_antes.color_hex
    solo_kmz_antes = case_antes.solo_kmz
    identity_antes = dict(case_antes.identity_overrides)
    duration_unit_antes = case_antes.duration_unit_decision
    carpeta_antes = case_antes.carpeta_salida

    client.post("/results/back-to-mapping", follow_redirects=True)

    case_despues = _get_case(client)
    assert case_despues.top_antenas == top_antenas_antes
    assert case_despues.top_contactos == top_contactos_antes
    assert case_despues.color_hex == color_antes
    assert case_despues.solo_kmz == solo_kmz_antes
    assert case_despues.identity_overrides == identity_antes
    assert case_despues.duration_unit_decision == duration_unit_antes
    assert case_despues.carpeta_salida == carpeta_antes


def test_estado_terminal_obsoleto_se_limpia_al_recuperar(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)
    client.post("/results/back-to-mapping", follow_redirects=True)

    case = _get_case(client)
    assert case.error_message is None
    assert case.result is None
    assert case.finished_at is None
    assert case.status == tz_web_state.STATUS_PENDING
    assert case.task_started is False


def test_despues_de_corregir_y_confirmar_se_puede_ejecutar_de_nuevo(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)
    client.post("/results/back-to-mapping", follow_redirects=True)

    # "Corrección": el usuario vuelve a editar y reconfirma el mismo mapeo
    # válido (aquí basta con reconfirmar; el defecto ya no depende del
    # contenido del mapeo sino de que el flujo permita relanzar).
    client.post("/mapping/edit", follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)

    monkeypatch.undo()  # restaura tz_web_routes.process_case real
    resp = _submit_configure(client, tmp_path, carpeta_salida=str(tmp_path / "salida_reintento"))
    assert "Procesando análisis".encode("utf-8") in resp.data or resp.status_code == 200

    status = wait_for_terminal_status(client)
    assert status["status"] == "success"


def test_iniciar_nuevo_analisis_sigue_limpiando_la_sesion(client, tmp_path, monkeypatch):
    _force_failure(client, tmp_path, monkeypatch)
    case = _get_case(client)
    upload_dir = case.upload_dir
    assert os.path.isdir(upload_dir)

    resp = client.post("/new", follow_redirects=True)
    assert resp.status_code == 200
    assert "Procesar bitácora completa".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        assert "case_id" not in flask_sess or tz_web_state.get_session(flask_sess.get("case_id")) is None
    assert not os.path.isdir(upload_dir)


def test_volver_a_revisar_mapeo_sin_mapeo_confirmado_redirige(client):
    resp = client.post("/results/back-to-mapping", follow_redirects=True)
    assert resp.status_code == 200
    assert "Primero confirme el mapeo".encode("utf-8") in resp.data
