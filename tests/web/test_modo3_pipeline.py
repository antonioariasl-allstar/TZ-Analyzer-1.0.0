"""FASE 2 WEB — Modo 3 (mapeo manual), microbloque 2: flujo de salida real
(Productos -> Color -> Preparar -> Resumen -> Procesamiento -> Resultados),
generando KMZ/KML opcional/hashes/log reales a partir de los registros
manuales — sin HTML. No repite las pruebas de ingreso/validación/CRUD del
microbloque 1 (ver tests/web/test_modo3_manual.py)."""
from __future__ import annotations

import os
import zipfile

from tz_web import state as tz_web_state
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    upload_real_file,
    wait_for_terminal_status,
)


def current_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


def enter_modo_3(client):
    return client.post("/modo/3", follow_redirects=True)


def elegir_tipo(client, tipo):
    return client.post("/modo3/tipo", data={"tipo": tipo}, follow_redirects=True)


ANTENA_1 = {
    "nombre": "Sitio Norte 01", "lat": "10.5", "lon": "-66.9",
    "azimut": "22.5", "celda": "C1", "direccion": "Av. Principal", "detalle": "Torre alta",
}
PUNTO_1 = {
    "nombre": "Domicilio A", "lat": "10.1", "lon": "-66.1",
    "direccion": "Calle 5", "detalle": "Casa esquinera",
}


def agregar_antena(client, **overrides):
    data = dict(ANTENA_1)
    data.update(overrides)
    return client.post("/modo3/registros", data=data, follow_redirects=True)


def agregar_punto(client, **overrides):
    data = dict(PUNTO_1)
    data.update(overrides)
    return client.post("/modo3/registros", data=data, follow_redirects=True)


def avanzar_hasta_resumen(client, tmp_path, kml_opcional=False, output_dir_name="salida"):
    """Recorre Productos -> Color -> Preparar fijando la carpeta de salida
    dentro de tmp_path (nunca la carpeta real por defecto del sistema) y
    deja la sesión lista para "Generar análisis" en Resumen."""
    data_productos = {"accion": "siguiente"}
    if kml_opcional:
        data_productos["kml_opcional"] = "on"
    client.post("/modo3/productos", data=data_productos, follow_redirects=True)
    client.post("/modo3/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)

    case = current_case(client)
    case.carpeta_salida = str(tmp_path / output_dir_name)

    client.post("/modo3/preparar", data={"accion": "siguiente", "nombre_modo": "sugerido"}, follow_redirects=True)
    return client.get("/modo3/resumen")


def generar(client):
    """Pulsa "Generar análisis" y espera a que el hilo en segundo plano
    termine, vía el mismo /status genérico de Modo 1/2."""
    client.post("/modo3/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    return wait_for_terminal_status(client)


def _leer_kml_de_kmz(kmz_path: str) -> str:
    with zipfile.ZipFile(kmz_path) as zf:
        return zf.read(zf.namelist()[0]).decode("utf-8")


# ---------------------------------------------------------------------------
# A/B/C — Antenas: círculo siempre, sector solo con azimut, varias antenas
# ---------------------------------------------------------------------------


def test_A_antena_sin_azimut_genera_kmz_con_circulo_sin_sector(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, azimut="")
    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    result = case.result
    assert result.kmz_path and os.path.isfile(result.kmz_path)
    kml_text = _leer_kml_de_kmz(result.kmz_path)
    assert "Radio de referencia" in kml_text
    assert "Cono Azimut" not in kml_text


def test_B_antena_con_azimut_decimal_genera_sector_y_preserva_valor(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, azimut="22.5")
    case = current_case(client)
    assert case.modo3_registros[0]["azimut"] == 22.5

    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    result = case.result
    kml_text = _leer_kml_de_kmz(result.kmz_path)
    assert "Radio de referencia" in kml_text
    assert "Cono Azimut" in kml_text
    # El valor decimal se preservó en el estado de la sesión (no se truncó a
    # entero antes de llegar al generador).
    assert case.modo3_registros[0]["azimut"] == 22.5


def test_C_varias_antenas_todas_aparecen(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, nombre="Antena Uno")
    agregar_antena(client, nombre="Antena Dos", lat="10.7", lon="-66.7")
    case = current_case(client)
    assert len(case.modo3_registros) == 2

    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    kml_text = _leer_kml_de_kmz(case.result.kmz_path)
    assert "Antena Uno" in kml_text
    assert "Antena Dos" in kml_text


# ---------------------------------------------------------------------------
# D/E — Puntos libres: pin únicamente, sin círculo/sector
# ---------------------------------------------------------------------------


def test_D_punto_libre_genera_pin_sin_circulo_ni_sector(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "punto_libre")
    agregar_punto(client)
    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    result = case.result
    assert result.kmz_path and os.path.isfile(result.kmz_path)
    assert result.kml_path is None  # generar_kml_puntos_libres solo produce KMZ

    kml_text = _leer_kml_de_kmz(result.kmz_path)
    assert "Domicilio A" in kml_text
    assert "Radio de referencia" not in kml_text
    assert "Cono Azimut" not in kml_text


def test_E_varios_puntos_libres_todos_aparecen(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "punto_libre")
    agregar_punto(client, nombre="Punto Uno")
    agregar_punto(client, nombre="Punto Dos", lat="10.3", lon="-66.3")

    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    kml_text = _leer_kml_de_kmz(case.result.kmz_path)
    assert "Punto Uno" in kml_text
    assert "Punto Dos" in kml_text


# ---------------------------------------------------------------------------
# F/G — KML opcional
# ---------------------------------------------------------------------------


def test_F_kml_opcional_activado_genera_kml_y_kmz(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path, kml_opcional=True)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    assert case.result.kml_path and os.path.isfile(case.result.kml_path)
    assert case.result.kmz_path and os.path.isfile(case.result.kmz_path)


def test_G_kml_opcional_desactivado_solo_kmz(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path, kml_opcional=False)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    assert case.result.kmz_path and os.path.isfile(case.result.kmz_path)
    assert case.result.kml_path is None


def test_kml_opcional_no_aplica_a_puntos_libres(client, tmp_path):
    """El checkbox de KML opcional se ignora (se fuerza False) para Puntos
    libres: generar_kml_puntos_libres() solo produce KMZ sin importar
    solo_kmz, así que no tiene sentido prometer un KML suelto ahí."""
    enter_modo_3(client)
    elegir_tipo(client, "punto_libre")
    agregar_punto(client)
    avanzar_hasta_resumen(client, tmp_path, kml_opcional=True)

    case = current_case(client)
    assert case.kml_opcional is False

    status = generar(client)
    assert status["status"] == "success"
    case = current_case(client)
    assert case.result.kml_path is None


# ---------------------------------------------------------------------------
# H — Hashes
# ---------------------------------------------------------------------------


def test_H_hashes_incluye_productos_reales_y_no_se_autoincluye(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path, kml_opcional=True)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    result = case.result
    assert result.hashes_path and os.path.isfile(result.hashes_path)
    contenido = open(result.hashes_path, encoding="utf-8").read()
    assert "SHA256" in contenido
    assert os.path.basename(result.kmz_path) in contenido
    assert os.path.basename(result.kml_path) in contenido
    assert os.path.basename(result.hashes_path) not in contenido


# ---------------------------------------------------------------------------
# I — Log
# ---------------------------------------------------------------------------


def test_I_log_contiene_modo_tipo_y_cantidad(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, nombre="Antena A")
    agregar_antena(client, nombre="Antena B", lat="10.7", lon="-66.7")
    avanzar_hasta_resumen(client, tmp_path)
    status = generar(client)
    assert status["status"] == "success"

    case = current_case(client)
    result = case.result
    assert result.log_path and os.path.isfile(result.log_path)
    contenido = open(result.log_path, encoding="utf-8").read()
    assert "Modo manual (Modo 3)" in contenido
    assert "antena" in contenido
    assert "Registros procesados: 2" in contenido


# ---------------------------------------------------------------------------
# J — Resultados
# ---------------------------------------------------------------------------


def test_J_results_muestra_productos_y_oculta_html(client, tmp_path):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path, kml_opcional=True)
    generar(client)

    resp = client.get("/results")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Análisis finalizado correctamente" in body
    assert "Abrir HTML" not in body
    assert "Abrir KMZ" in body
    assert "Abrir KML" in body
    assert "Abrir hashes" in body
    assert "Abrir log" in body


# ---------------------------------------------------------------------------
# K — Sin registros no permite continuar
# ---------------------------------------------------------------------------


def test_K_sin_registros_no_permite_continuar(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    for ruta in ("/modo3/productos", "/modo3/color", "/modo3/preparar", "/modo3/resumen"):
        resp = client.get(ruta, follow_redirects=True)
        assert resp.request.path == "/modo3/registros"


# ---------------------------------------------------------------------------
# L — Error de generación conserva los registros
# ---------------------------------------------------------------------------


def test_L_error_de_generacion_preserva_registros_y_permite_volver(client, tmp_path, monkeypatch):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    avanzar_hasta_resumen(client, tmp_path)

    from tz_web import routes as tz_web_routes

    def _falla(_req):
        raise RuntimeError("fallo simulado de generación")

    monkeypatch.setattr(tz_web_routes, "process_case_modo3", _falla)

    status = generar(client)
    assert status["status"] == "failed"

    case = current_case(client)
    assert len(case.modo3_registros) == 1
    assert case.modo3_registros[0]["nombre"] == "Sitio Norte 01"

    resp = client.get("/results")
    body = resp.get_data(as_text=True)
    assert "no pudo completarse" in body
    assert "Volver a preparar salida" in body

    resp2 = client.post("/modo3/results/back", follow_redirects=True)
    assert resp2.request.path == "/modo3/preparar"

    case = current_case(client)
    assert len(case.modo3_registros) == 1
    assert case.status == tz_web_state.STATUS_PENDING


# ---------------------------------------------------------------------------
# M — Modo 1 y Modo 2 siguen funcionando
# ---------------------------------------------------------------------------


def test_M_modo_1_sigue_funcionando(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_1
    assert resp.request.path == "/configure"


def test_M_modo_2_sigue_funcionando(client):
    client.post("/modo/2", follow_redirects=True)
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_2
    assert resp.request.path == "/configure/filtro-tiempo"
