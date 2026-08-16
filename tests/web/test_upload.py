"""FASE 2 WEB — Pantalla 1: carga de archivo y listado de hojas."""
from __future__ import annotations

import hashlib
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
    with open(case.temp_path, "rb") as accepted:
        assert case.upload_sha256 == hashlib.sha256(accepted.read()).hexdigest()
    assert case.input_snapshot_path is None
    assert case.input_snapshot_sha256 is None


def test_upload_sin_archivo_muestra_error(client):
    client.post("/modo/1")
    resp = client.post("/upload", data={}, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Seleccione un archivo" in resp.data


def test_extension_invalida_es_rechazada(client):
    client.post("/modo/1")
    data = {"archivo": (io.BytesIO(b"contenido cualquiera"), "documento.txt")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "Formato no soportado".encode("utf-8") in resp.data
    with client.session_transaction() as flask_sess:
        case_id = flask_sess.get("case_id")
    case = tz_web_state.get_session(case_id)
    assert case.temp_path is None


def test_extension_xls_legacy_es_rechazada_y_la_ui_declara_solo_xlsx(client):
    client.post("/modo/1")
    data = {"archivo": (io.BytesIO(b"contenido BIFF simulado"), "bitacora.xls")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)

    assert resp.status_code == 200
    assert "Formato no soportado".encode("utf-8") in resp.data
    assert b'accept=".xlsx"' in resp.data
    assert b".xls," not in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess.get("case_id")
    case = tz_web_state.get_session(case_id)
    assert case.temp_path is None


# ---------------------------------------------------------------------------
# MB7-B2 — el límite fijo de 200 MB (protección provisional) fue eliminado.
# No se sustituye por otro número arbitrario: ver tz_web/state.py (ya no
# define MAX_UPLOAD_BYTES) y tz_web/app.py (ya no fija MAX_CONTENT_LENGTH).
# Estas pruebas demuestran la ausencia de la regla, sin crear archivos
# físicamente grandes: se simula el tamaño monkeypencheando os.path.getsize.
# ---------------------------------------------------------------------------


def test_pantalla_de_carga_no_menciona_200_mb(client):
    resp = client.post("/modo/1", follow_redirects=True)
    assert resp.status_code == 200
    assert b"200 MB" not in resp.data
    assert "Máximo 200".encode("utf-8") not in resp.data


def test_no_existe_constante_de_limite_fijo_de_tamano():
    assert not hasattr(tz_web_state, "MAX_UPLOAD_BYTES")


def test_app_no_configura_max_content_length(app):
    assert app.config["MAX_CONTENT_LENGTH"] is None


def test_archivo_grande_no_es_rechazado_por_una_regla_de_tamano(client, monkeypatch):
    """Con el tamaño reportado por el sistema de archivos simulado en más de
    200 MB (sin escribir ese contenido a disco), la subida de un .xlsx real
    y válido debe completarse igual: nada rechaza únicamente por tamaño."""
    from tz_web import routes as tz_web_routes

    client.post("/modo/1")
    original_getsize = os.path.getsize

    def _fake_getsize(path):
        if str(path).endswith(".xlsx"):
            return 500 * 1024 * 1024  # > 200 MB, tamaño simulado
        return original_getsize(path)

    monkeypatch.setattr(tz_web_routes.os.path, "getsize", _fake_getsize)

    resp = upload_real_file(client)
    assert resp.status_code == 200
    assert "supera el límite".encode("utf-8") not in resp.data
    assert "demasiado grande".encode("utf-8") not in resp.data
    # La subida llegó hasta el listado real de hojas — no fue interrumpida.
    assert SHEET_NAME.encode() in resp.data


def test_reemplazo_invalido_no_deja_ruta_digest_o_mapeo_obsoletos(client):
    upload_real_file(client)
    with client.session_transaction() as browser_session:
        case = tz_web_state.get_session(browser_session["case_id"])
    previous_path = case.temp_path
    case.mapping = {"fecha": ("col", "FECHA_INICIAL")}

    response = client.post(
        "/upload",
        data={"archivo": (io.BytesIO(b"no es un xlsx"), "reemplazo.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert not os.path.exists(previous_path)
    assert not os.path.isdir(os.path.dirname(previous_path))
    assert case.temp_path is None
    assert case.original_filename is None
    assert case.upload_dir is None
    assert case.upload_sha256 is None
    assert case.mapping is None


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
    client.post("/modo/1")
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
