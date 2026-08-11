"""FASE 2 WEB — Pantalla 1: carga de archivo y listado de hojas."""
from __future__ import annotations

import io
import os

from tz_web import state as tz_web_state
from tests.web.conftest import DATA_PATH, SHEET_NAME, upload_real_file


def test_upload_valido_lista_hojas_reales(client):
    resp = upload_real_file(client)
    assert resp.status_code == 200
    assert SHEET_NAME.encode() in resp.data
    assert b"segunda" in resp.data


def test_upload_guarda_archivo_con_nombre_seguro_fuera_del_original(client):
    upload_real_file(client, filename="../../evil name??.xlsx")
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.temp_path is not None
    assert os.path.isfile(case.temp_path)
    # secure_filename despoja separadores de ruta y caracteres peligrosos.
    assert ".." not in os.path.basename(case.temp_path)
    assert "/" not in os.path.basename(case.temp_path) and "\\" not in os.path.basename(case.temp_path)
    # El nombre original se conserva solo como metadato visible.
    assert case.original_filename == "../../evil name??.xlsx"


def test_upload_sin_archivo_muestra_error(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Seleccione un archivo" in resp.data


def test_extension_invalida_es_rechazada(client):
    data = {"archivo": (io.BytesIO(b"contenido cualquiera"), "documento.txt")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "Formato no soportado".encode("utf-8") in resp.data
    with client.session_transaction() as flask_sess:
        case_id = flask_sess.get("case_id")
    case = tz_web_state.get_session(case_id)
    assert case.temp_path is None


def test_archivo_demasiado_grande_es_rechazado(app, client, monkeypatch):
    monkeypatch.setattr(tz_web_state, "MAX_UPLOAD_BYTES", 100)
    app.config["MAX_CONTENT_LENGTH"] = 100
    data = {"archivo": (io.BytesIO(b"x" * 1000), "grande.xlsx")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "supera el límite permitido".encode("utf-8") in resp.data


def test_listado_de_hojas_via_seleccion_carga_columnas_y_muestras(client):
    upload_real_file(client)
    resp = client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"FECHA_INICIAL" in resp.data
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.sheet == SHEET_NAME
    assert "FECHA_INICIAL" in case.columns
    assert len(case.samples["FECHA_INICIAL"]) == 3


def test_hoja_no_disponible_es_rechazada(client):
    upload_real_file(client)
    resp = client.post("/sheet", data={"hoja": "hoja_que_no_existe"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Seleccione una hoja válida".encode("utf-8") in resp.data


def test_seleccionar_hoja_sin_archivo_previo_redirige_a_inicio(client):
    resp = client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cargar archivo" in resp.data


def test_tras_cargar_no_aparecen_simultaneamente_carga_y_seleccion_de_hoja(client):
    resp = upload_real_file(client)
    assert resp.status_code == 200
    # El formulario de subida (con su enctype multipart) ya no debe aparecer
    # una vez que el archivo fue cargado; solo la selección de hoja.
    assert b'enctype="multipart/form-data"' not in resp.data
    assert b'name="hoja"' in resp.data


def test_cambiar_archivo_limpia_estado_y_elimina_temporal(client):
    upload_real_file(client)
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    temp_path = case.temp_path
    assert os.path.isfile(temp_path)

    resp = client.post("/file/change", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cargar archivo" in resp.data

    # El temporal fue eliminado de forma segura.
    assert not os.path.isfile(temp_path)

    # La sesión (case_id) sigue activa; solo se limpió el estado de archivo/hoja/mapeo.
    with client.session_transaction() as flask_sess:
        assert flask_sess["case_id"] == case_id
    case = tz_web_state.get_session(case_id)
    assert case is not None
    assert case.temp_path is None
    assert case.original_filename is None
    assert case.available_sheets == []
    assert case.sheet is None
    assert case.columns == []
    assert case.samples == {}
    assert case.mapping is None
    assert case.mapping_draft is None
    assert case.mapping_stage == "form"
    assert case.mapping_draft is None
    assert case.capabilities_preview is None


def test_cambiar_hoja_conserva_archivo_y_permite_elegir_otra(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    temp_path = case.temp_path
    assert case.sheet == SHEET_NAME

    resp = client.post("/sheet/change", follow_redirects=True)
    assert resp.status_code == 200
    assert b'name="hoja"' in resp.data

    case = tz_web_state.get_session(case_id)
    # El archivo se conserva intacto.
    assert case.temp_path == temp_path
    assert os.path.isfile(temp_path)
    assert case.available_sheets
    # La hoja/columnas/mapeo quedan disponibles para elegir de nuevo.
    assert case.sheet is None
    assert case.columns == []
    assert case.mapping is None


def test_vista_previa_muestra_filas_coherentes_entre_columnas(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    resp = client.get("/preview")
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    # Las muestras de todas las columnas provienen de las mismas filas
    # (misma cantidad de valores por columna, en el mismo orden posicional).
    longitudes = {len(v) for v in case.samples.values()}
    assert longitudes == {3}


def test_valores_nulos_se_muestran_como_guion_largo(client, monkeypatch):
    import pandas as pd

    from tz_web import routes as tz_web_routes

    df = pd.DataFrame({
        "A": [1, None, 3],
        "B": ["x", "y", None],
    })
    samples = tz_web_routes._build_samples(df, limit=3)
    assert samples["A"][1] == "—"
    assert samples["B"][2] == "—"
    assert samples["B"][0] == "x"
