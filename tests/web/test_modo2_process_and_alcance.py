"""FASE 2 WEB — Modo 2, microbloque 2: conecta la selección temporal ya
guardada en ``case.filtro_tiempo`` con ``process_case()`` real (sin
reimplementar filtrado en tz_web) y con la presentación de "Alcance" en
Resumen/Resultados. Usa el fixture real (bitácora_test.tsv.xlsx, hoja
CASO_860766049463800_PROCESADA), cuyos eventos van del 2020-01-01 al
2020-01-03 (50 filas)."""
from __future__ import annotations

from tz_web import state as tz_web_state
from tz_web.services import MSG_FILTRO_SIN_REGISTROS
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


def advance_modo2_to_filtro(client, mapeo_form=None):
    enter_modo_2(client)
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(mapeo_form or REAL_MAPPING_FORM), follow_redirects=True)
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


def advance_to_resumen_desde_filtro(client, *, nombre_modo="sugerido", output_base_name="", tipo_bitacora=""):
    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": nombre_modo,
        "output_base_name": output_base_name, "tipo_bitacora": tipo_bitacora,
    }, follow_redirects=True)
    select_output_folder(client)
    return client.get("/configure/resumen")


def run_modo2_analysis(client, filtro_form):
    """Desde "Filtro temporal" ya alcanzada (ver ``advance_modo2_to_filtro``),
    completa el resto de Configuración con valores por defecto, genera el
    análisis y espera el estado terminal. Devuelve el ``Session`` final."""
    submit_filtro(client, filtro_form)
    advance_to_resumen_desde_filtro(client)
    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    wait_for_terminal_status(client)
    return current_case(client)


# ---------------------------------------------------------------------------
# A. Día específico
# ---------------------------------------------------------------------------


def test_dia_especifico_llega_a_caserequest_y_process_case_filtra(client):
    advance_modo2_to_filtro(client)
    case = run_modo2_analysis(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})

    assert case.status == tz_web_state.STATUS_SUCCESS
    assert case.filtro_tiempo == {
        "tipo": "dia", "dia": "2020-01-02", "desde": None, "hasta": None,
        "hora_ini": None, "hora_fin": None,
    }
    assert 0 < case.result.summary["filas_totales"] <= 29
    assert case.result.summary["alcance"] == "Día 2 del mes 1 del año 2020"


# ---------------------------------------------------------------------------
# B. Rango de fechas
# ---------------------------------------------------------------------------


def test_rango_de_fechas_extremos_inclusivos_y_alcance(client):
    advance_modo2_to_filtro(client)
    case = run_modo2_analysis(client, {
        "filtro_tipo": "rango_dias", "filtro_desde": "2020-01-01", "filtro_hasta": "2020-01-02",
    })

    assert case.status == tz_web_state.STATUS_SUCCESS
    assert 0 < case.result.summary["filas_totales"] <= 41
    assert case.result.summary["alcance"] == "Del 01/01/2020 al 02/01/2020"


# ---------------------------------------------------------------------------
# C. Rango de horas (todos los días, cruce de medianoche)
# ---------------------------------------------------------------------------


def test_rango_de_horas_se_aplica_a_todos_los_dias_y_acepta_cruce_medianoche(client):
    advance_modo2_to_filtro(client)
    case = run_modo2_analysis(client, {
        "filtro_tipo": "rango_horas", "filtro_hora_ini": "20:00", "filtro_hora_fin": "00:00",
    })

    assert case.status == tz_web_state.STATUS_SUCCESS
    assert 0 < case.result.summary["filas_totales"] <= 6
    assert case.result.summary["alcance"] == "De 20:00 a 00:00, aplicado a todos los días de la bitácora"


# ---------------------------------------------------------------------------
# D. Rango de horas en un día específico
# ---------------------------------------------------------------------------


def test_rango_de_horas_en_dia_especifico_llega_correctamente_y_alcance(client):
    advance_modo2_to_filtro(client)
    case = run_modo2_analysis(client, {
        "filtro_tipo": "rango_horas_dia", "filtro_dia": "2020-01-02",
        "filtro_hora_ini": "20:00", "filtro_hora_fin": "21:30",
    })

    assert case.status == tz_web_state.STATUS_SUCCESS
    assert case.filtro_tiempo == {
        "tipo": "rango_horas_dia", "dia": "2020-01-02", "desde": None, "hasta": None,
        "hora_ini": "20:00", "hora_fin": "21:30",
    }
    assert 0 < case.result.summary["filas_totales"] <= 5
    assert case.result.summary["alcance"] == "02/01/2020, de 20:00 a 21:30"


# ---------------------------------------------------------------------------
# E. Modo 1 — sin filtro, alcance "Bitácora completa"
# ---------------------------------------------------------------------------


def test_modo_1_sigue_enviando_filtro_none_y_alcance_bitacora_completa(client):
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
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)

    case = current_case(client)
    assert case.filtro_tiempo is None
    assert case.modo == tz_web_state.MODO_1

    select_output_folder(client)
    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    wait_for_terminal_status(client)

    case = current_case(client)
    assert case.status == tz_web_state.STATUS_SUCCESS
    assert case.result.summary["alcance"] == "Bitácora completa"
    assert case.result.summary["filas_totales"] == 50


# ---------------------------------------------------------------------------
# F. Persistencia atrás/adelante a través de toda la Configuración
# ---------------------------------------------------------------------------


def test_filtro_persiste_navegando_toda_la_configuracion_atras_y_adelante(client):
    advance_modo2_to_filtro(client)
    submit_filtro(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})

    esperado = {
        "tipo": "dia", "dia": "2020-01-02", "desde": None, "hasta": None,
        "hora_ini": None, "hora_fin": None,
    }
    case = current_case(client)
    assert case.filtro_tiempo == esperado

    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    # "Anterior" desde 3E hasta 3D y de vuelta no debe perder el filtro.
    client.post("/configure/final", data={"accion": "anterior"}, follow_redirects=True)
    assert current_case(client).filtro_tiempo == esperado

    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)
    assert current_case(client).filtro_tiempo == esperado

    resp = client.get("/configure/resumen")
    assert resp.status_code == 200
    assert "Día 2 del mes 1 del año 2020".encode("utf-8") in resp.data
    assert current_case(client).filtro_tiempo == esperado

    # Anterior desde Resumen -> Preparar y de vuelta -> Resumen: sigue intacto.
    client.post("/configure/resumen", data={"accion": "anterior"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)
    assert current_case(client).filtro_tiempo == esperado


# ---------------------------------------------------------------------------
# G. 0 registros — error claro y recuperación al filtro temporal
# ---------------------------------------------------------------------------


def test_cero_registros_da_error_claro_y_permite_volver_al_filtro(client):
    advance_modo2_to_filtro(client)
    case = run_modo2_analysis(client, {"filtro_tipo": "dia", "filtro_dia": "2020-06-15"})

    assert case.status == tz_web_state.STATUS_FAILED
    assert case.error_message == MSG_FILTRO_SIN_REGISTROS

    resp = client.get("/results")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert MSG_FILTRO_SIN_REGISTROS in html
    assert "Volver a revisar filtro temporal" in html

    # La recuperación no debe pedir repetir archivo/mapeo/configuración.
    archivo_antes, hoja_antes, mapping_antes = case.temp_path, case.sheet, dict(case.mapping)
    top_antenas_antes, color_antes = case.top_antenas, case.color_hex

    resp = client.post("/results/back-to-filtro-tiempo", follow_redirects=True)
    assert resp.status_code == 200
    assert "Filtro temporal".encode("utf-8") in resp.data
    # La selección incorrecta anterior sigue precargada para corregirla.
    assert 'value="2020-06-15"' in resp.data.decode("utf-8")

    case = current_case(client)
    assert case.status == tz_web_state.STATUS_PENDING
    assert case.error_message is None
    assert case.result is None
    assert case.temp_path == archivo_antes
    assert case.sheet == hoja_antes
    assert case.mapping == mapping_antes
    assert case.top_antenas == top_antenas_antes
    assert case.color_hex == color_antes

    # Corrige la selección y puede volver a ejecutar sin repetir nada más.
    submit_filtro(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})
    client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    status = wait_for_terminal_status(client)
    assert status["status"] == "success"


def test_volver_a_revisar_filtro_temporal_requiere_modo_2(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)

    resp = client.post("/results/back-to-filtro-tiempo", follow_redirects=True)
    assert resp.status_code == 200
    # No hay resultados FAILED aún y no es Modo 2: cae al mensaje genérico de guard.
    assert "Primero confirme el mapeo".encode("utf-8") in resp.data


# ---------------------------------------------------------------------------
# H. Nombre sugerido refleja el filtro (Modo 2); nombre manual no se pisa
# ---------------------------------------------------------------------------


def test_nombre_sugerido_refleja_filtro_en_modo_2(client):
    advance_modo2_to_filtro(client)
    submit_filtro(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})

    resp = client.post("/configure/final/preview-name", data={"tipo_bitacora": ""})
    assert resp.status_code == 200
    nombre = resp.get_json()["suggested_name"]
    assert nombre is not None
    assert "dia_2020-01-02" in nombre


def test_nombre_manual_no_se_sobrescribe_en_modo_2(client):
    advance_modo2_to_filtro(client)
    submit_filtro(client, {"filtro_tipo": "dia", "filtro_dia": "2020-01-02"})

    client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "manual",
        "output_base_name": "Mi Caso Filtrado", "tipo_bitacora": "",
    }, follow_redirects=True)

    case = current_case(client)
    assert case.output_base_name == "Mi Caso Filtrado"

    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert "Mi Caso Filtrado" in html
