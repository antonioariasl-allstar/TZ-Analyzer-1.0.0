"""FASE 2 WEB — Modo 3 (mapeo manual de antenas/ubicaciones), microbloque 1:
activación del modo real, selección de tipo de registro y gestión manual de
registros (alta/listado/edición/eliminación) con persistencia de sesión.
No cubre generación de KMZ/KML/hashes/log (queda para el siguiente
microbloque)."""
from __future__ import annotations

from tz_web import state as tz_web_state
from tests.web.conftest import REAL_MAPPING_FORM, SHEET_NAME, upload_real_file


def current_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


def enter_modo_3(client):
    return client.post("/modo/3", follow_redirects=True)


def elegir_tipo(client, tipo):
    return client.post("/modo3/tipo", data={"tipo": tipo}, follow_redirects=True)


ANTENA_VALIDA = {
    "nombre": "Sitio Norte 01",
    "lat": "10.5",
    "lon": "-66.9",
    "azimut": "22.5",
    "celda": "C1",
    "direccion": "Av. Principal",
    "detalle": "Torre alta",
}

PUNTO_VALIDO = {
    "nombre": "Domicilio sospechoso",
    "lat": "10.1",
    "lon": "-66.1",
    "direccion": "Calle 5",
    "detalle": "Casa esquinera",
}


def agregar_antena(client, **overrides):
    data = dict(ANTENA_VALIDA)
    data.update(overrides)
    return client.post("/modo3/registros", data=data, follow_redirects=True)


def agregar_punto(client, **overrides):
    data = dict(PUNTO_VALIDO)
    data.update(overrides)
    return client.post("/modo3/registros", data=data, follow_redirects=True)


# ---------------------------------------------------------------------------
# 1-3: Menú, entrada y no entrar al flujo de bitácora
# ---------------------------------------------------------------------------


def test_modo_3_ya_no_esta_pendiente(client):
    resp = client.get("/menu")
    body = resp.get_data(as_text=True)
    assert "Modo pendiente" not in body
    assert "Mapear antenas y ubicaciones manualmente" in body


def test_entrada_desde_menu_marca_modo_3(client):
    enter_modo_3(client)
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_3


def test_modo_3_no_pasa_por_carga_de_archivo(client):
    resp = enter_modo_3(client)
    assert resp.request.path == "/modo3/tipo"
    body = resp.get_data(as_text=True)
    assert "¿Qué tipo de registros desea agregar?" in body


# ---------------------------------------------------------------------------
# 4-5: Submenú de tipo y persistencia de la selección
# ---------------------------------------------------------------------------


def test_submenu_muestra_antenas_y_puntos_libres(client):
    enter_modo_3(client)
    resp = client.get("/modo3/tipo")
    body = resp.get_data(as_text=True)
    assert "Antenas/Celdas" in body
    assert "Puntos libres" in body


def test_seleccion_de_tipo_persiste(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    case = current_case(client)
    assert case.modo3_tipo == "antena"

    # otra petición (simula navegación) conserva la selección
    client.get("/modo3/registros")
    case = current_case(client)
    assert case.modo3_tipo == "antena"


# ---------------------------------------------------------------------------
# 6-7: Alta válida de antena y de punto libre
# ---------------------------------------------------------------------------


def test_alta_valida_de_antena(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    resp = agregar_antena(client)
    case = current_case(client)
    assert len(case.modo3_registros) == 1
    registro = case.modo3_registros[0]
    assert registro["nombre"] == "Sitio Norte 01"
    assert registro["lat"] == 10.5
    assert registro["lon"] == -66.9
    assert registro["celda"] == "C1"
    body = resp.get_data(as_text=True)
    assert "Sitio Norte 01" in body


def test_alta_valida_de_punto_libre(client):
    enter_modo_3(client)
    elegir_tipo(client, "punto_libre")
    agregar_punto(client)
    case = current_case(client)
    assert len(case.modo3_registros) == 1
    registro = case.modo3_registros[0]
    assert registro["nombre"] == "Domicilio sospechoso"
    assert registro["lat"] == 10.1
    assert registro["lon"] == -66.1
    assert "azimut" not in registro


# ---------------------------------------------------------------------------
# 8-10: Validaciones de coordenadas
# ---------------------------------------------------------------------------


def test_latitud_fuera_de_rango_rechazada(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, lat="95")
    case = current_case(client)
    assert case.modo3_registros == []


def test_longitud_fuera_de_rango_rechazada(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, lon="-200")
    case = current_case(client)
    assert case.modo3_registros == []


def test_cero_cero_rechazada_para_antena(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, lat="0", lon="0")
    case = current_case(client)
    assert case.modo3_registros == []


def test_cero_cero_aceptada_para_punto_libre():
    """generar_kml_puntos_libres no descarta (0, 0): solo valida el rango,
    a diferencia de generar_kml (antenas). Ver tz_core/kml_generator.py."""
    from tz_web import manual_validators as mv

    lat, lon, error = mv.parse_lat_lon("0", "0", permitir_cero_cero=True)
    assert error is None
    assert lat == 0.0 and lon == 0.0


def test_cero_cero_aceptada_para_punto_libre_via_web(client):
    enter_modo_3(client)
    elegir_tipo(client, "punto_libre")
    agregar_punto(client, lat="0", lon="0")
    case = current_case(client)
    assert len(case.modo3_registros) == 1
    assert case.modo3_registros[0]["lat"] == 0.0
    assert case.modo3_registros[0]["lon"] == 0.0


# ---------------------------------------------------------------------------
# 11-12: Validaciones de azimut
# ---------------------------------------------------------------------------


def test_azimut_invalido_rechazado(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, azimut="360")
    case = current_case(client)
    assert case.modo3_registros == []


def test_azimut_decimal_preservado(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, azimut="22.5")
    case = current_case(client)
    assert case.modo3_registros[0]["azimut"] == 22.5


# ---------------------------------------------------------------------------
# 13-14: Editar y eliminar
# ---------------------------------------------------------------------------


def test_editar_conserva_identidad_y_no_duplica(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    case = current_case(client)
    registro_id = case.modo3_registros[0]["id"]

    data = dict(ANTENA_VALIDA)
    data["nombre"] = "Sitio Norte 01 (editado)"
    data["registro_id"] = registro_id
    client.post("/modo3/registros", data=data, follow_redirects=True)

    case = current_case(client)
    assert len(case.modo3_registros) == 1
    assert case.modo3_registros[0]["id"] == registro_id
    assert case.modo3_registros[0]["nombre"] == "Sitio Norte 01 (editado)"


def test_eliminar_solo_quita_el_registro_indicado(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client, nombre="Antena A")
    agregar_antena(client, nombre="Antena B")
    case = current_case(client)
    assert len(case.modo3_registros) == 2
    id_a = next(r["id"] for r in case.modo3_registros if r["nombre"] == "Antena A")

    client.post(f"/modo3/registros/{id_a}/eliminar", follow_redirects=True)
    case = current_case(client)
    assert len(case.modo3_registros) == 1
    assert case.modo3_registros[0]["nombre"] == "Antena B"


# ---------------------------------------------------------------------------
# 15: Navegación atrás/adelante conserva registros
# ---------------------------------------------------------------------------


def test_navegar_atras_adelante_conserva_registros(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)

    client.get("/modo3/tipo")  # "atrás"
    client.get("/modo3/registros")  # "adelante"

    case = current_case(client)
    assert len(case.modo3_registros) == 1


# ---------------------------------------------------------------------------
# 16: No permite cambiar tipo silenciosamente con registros existentes
# ---------------------------------------------------------------------------


def test_no_permite_cambiar_tipo_con_registros_existentes(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)

    resp = elegir_tipo(client, "punto_libre")
    case = current_case(client)
    assert case.modo3_tipo == "antena"
    assert len(case.modo3_registros) == 1
    body = resp.get_data(as_text=True)
    assert "Elimínelos" in body or "eliminar" in body.lower()


def test_permite_cambiar_tipo_tras_eliminar_registros(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    case = current_case(client)
    registro_id = case.modo3_registros[0]["id"]
    client.post(f"/modo3/registros/{registro_id}/eliminar", follow_redirects=True)

    elegir_tipo(client, "punto_libre")
    case = current_case(client)
    assert case.modo3_tipo == "punto_libre"


# ---------------------------------------------------------------------------
# 17: Modo 1 y Modo 2 no se ven afectados
# ---------------------------------------------------------------------------


def test_modo_1_sigue_funcionando(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_1
    assert resp.request.path == "/configure"


def test_modo_2_sigue_funcionando(client):
    client.post("/modo/2", follow_redirects=True)
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_2

    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert resp.request.path == "/configure/filtro-tiempo"


# ---------------------------------------------------------------------------
# Extra: "Continuar" exige al menos un registro (microbloque 2: ahora lleva
# a la pantalla real de Productos, ver tests/web/test_modo3_pipeline.py para
# el resto del flujo Productos -> Color -> Preparar -> Resumen -> Resultados)
# ---------------------------------------------------------------------------


def test_continuar_exige_al_menos_un_registro(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    resp = client.get("/modo3/productos", follow_redirects=True)
    assert resp.request.path == "/modo3/registros"


def test_continuar_con_registros_muestra_pantalla_de_productos(client):
    enter_modo_3(client)
    elegir_tipo(client, "antena")
    agregar_antena(client)
    resp = client.get("/modo3/productos")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Productos de salida" in body
