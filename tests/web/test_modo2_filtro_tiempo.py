"""FASE 2 WEB — Modo 2 (bitácora filtrada por tiempo), microbloque 1:
activación del modo real y pantalla de "Filtro temporal" entre la Revisión
del mapeo y la Identificación. No cubre todavía la aplicación real del
filtro al DataFrame (eso queda para un microbloque posterior)."""
from __future__ import annotations

import re

from tz_web import state as tz_web_state
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    advance_to_configure,
    upload_real_file,
)


def _mapeo_sin_hora():
    mapeo = dict(REAL_MAPPING_FORM)
    mapeo["tipo_hora"] = "omitido"
    mapeo.pop("col_hora", None)
    return mapeo


def _mapeo_sin_fecha():
    mapeo = dict(REAL_MAPPING_FORM)
    mapeo["tipo_fecha"] = "omitido"
    mapeo.pop("col_fecha", None)
    mapeo["tipo_hora"] = "omitido"
    mapeo.pop("col_hora", None)
    return mapeo


def enter_modo_2(client):
    return client.post("/modo/2", follow_redirects=True)


def advance_modo2_to_filtro_con_mapeo(client, mapeo_form):
    enter_modo_2(client)
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=mapeo_form, follow_redirects=True)
    return client.post("/mapping/confirm", follow_redirects=True)


def advance_modo2_to_filtro(client):
    return advance_modo2_to_filtro_con_mapeo(client, dict(REAL_MAPPING_FORM))


def current_case(client):
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    return tz_web_state.get_session(case_id)


# ---------------------------------------------------------------------------
# Modo 1 no debe verse afectado
# ---------------------------------------------------------------------------


def test_modo_1_sigue_entrando_directamente_al_flujo_existente(client):
    resp = advance_to_configure(client)
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data
    case = current_case(client)
    assert case.modo == tz_web_state.MODO_1


def test_modo_1_no_ve_pantalla_de_filtro(client):
    resp = advance_to_configure(client)
    html = resp.data.decode("utf-8")
    assert "Filtro temporal" not in html

    case = current_case(client)
    assert case.filtro_tiempo is None

    # Tampoco es alcanzable navegando directamente a la ruta.
    resp = client.get("/configure/filtro-tiempo", follow_redirects=True)
    assert "Identificación de la bitácora".encode("utf-8") in resp.data


# ---------------------------------------------------------------------------
# Entrada y flujo de Modo 2
# ---------------------------------------------------------------------------


def test_modo_2_entra_al_mismo_flujo_de_carga_y_mapeo(client):
    enter_modo_2(client)
    resp = client.get("/analizador")
    assert resp.status_code == 200
    assert b"Cargar archivo" in resp.data
    assert b'enctype="multipart/form-data"' in resp.data

    case = current_case(client)
    assert case.modo == tz_web_state.MODO_2


def test_despues_de_revision_modo_2_llega_a_filtro_temporal(client):
    resp = advance_modo2_to_filtro(client)
    assert resp.status_code == 200
    assert "Filtro temporal".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.modo == tz_web_state.MODO_2
    assert case.mapping is not None


# ---------------------------------------------------------------------------
# Capacidad (case.capabilities_preview -> filtros_temporales) -> opciones
# ---------------------------------------------------------------------------


def test_fecha_y_hora_habilitan_las_cuatro_opciones(client):
    advance_modo2_to_filtro(client)

    case = current_case(client)
    cap = case.capabilities_preview["capacidades"]["filtros_temporales"]
    assert cap["disponible"] is True
    assert cap["estado"] == "disponible"

    resp = client.get("/configure/filtro-tiempo")
    html = resp.data.decode("utf-8")
    assert "Día específico" in html
    assert "Rango de fechas" in html
    assert "Rango de horas" in html
    assert "Rango de horas en un día específico" in html
    assert "No disponible" not in html
    assert "disabled" not in html


def test_solo_fecha_habilita_unicamente_filtros_por_fecha(client):
    advance_modo2_to_filtro_con_mapeo(client, _mapeo_sin_hora())

    case = current_case(client)
    cap = case.capabilities_preview["capacidades"]["filtros_temporales"]
    assert cap["disponible"] is True
    assert cap["estado"] == "parcial"

    resp = client.get("/configure/filtro-tiempo")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    dia_input = re.search(r'<input type="radio" name="filtro_tipo" value="dia"[^>]*>', html)
    rango_dias_input = re.search(r'<input type="radio" name="filtro_tipo" value="rango_dias"[^>]*>', html)
    rango_horas_input = re.search(r'<input type="radio" name="filtro_tipo" value="rango_horas"[^>]*>', html)
    rango_horas_dia_input = re.search(r'<input type="radio" name="filtro_tipo" value="rango_horas_dia"[^>]*>', html)

    assert dia_input is not None and "disabled" not in dia_input.group(0)
    assert rango_dias_input is not None and "disabled" not in rango_dias_input.group(0)
    assert rango_horas_input is not None and "disabled" in rango_horas_input.group(0)
    assert rango_horas_dia_input is not None and "disabled" in rango_horas_dia_input.group(0)
    assert "No disponible" in html


def test_solo_fecha_rechaza_envio_de_filtro_por_horas(client):
    """Defensa adicional en el servidor: aunque el HTML deshabilite la
    opción, un envío manipulado con un tipo no habilitado debe rechazarse."""
    advance_modo2_to_filtro_con_mapeo(client, _mapeo_sin_hora())

    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "siguiente", "filtro_tipo": "rango_horas",
        "filtro_hora_ini": "20:00", "filtro_hora_fin": "23:00",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "no está disponible para esta bitácora".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo is None


def test_sin_fecha_impide_continuar(client):
    advance_modo2_to_filtro_con_mapeo(client, _mapeo_sin_fecha())

    case = current_case(client)
    cap = case.capabilities_preview["capacidades"]["filtros_temporales"]
    assert cap["disponible"] is False
    assert cap["estado"] == "no_disponible"

    resp = client.get("/configure/filtro-tiempo")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "no dispone de una fecha reconocible" in html
    assert "Modo 1" in html
    assert 'name="filtro_tipo"' not in html
    assert "Volver al menú principal" in html

    # El envío directo también debe rechazarse (defensa en profundidad).
    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "siguiente", "filtro_tipo": "dia", "filtro_dia": "2024-01-01",
    }, follow_redirects=True)
    assert "no dispone de una fecha reconocible".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo is None


# ---------------------------------------------------------------------------
# Opciones visibles: sin "Sin filtro", sin combinación varios días + horas
# ---------------------------------------------------------------------------


def test_modo_2_no_ofrece_sin_filtro(client):
    advance_modo2_to_filtro(client)
    resp = client.get("/configure/filtro-tiempo")
    html = resp.data.decode("utf-8")
    assert "Sin filtro" not in html
    assert 'value="ninguno"' not in html


def test_no_existe_opcion_de_varios_dias_con_rango_horario(client):
    from tz_web.filter_catalog import FILTRO_TIEMPO_ORDER

    assert len(FILTRO_TIEMPO_ORDER) == 4
    assert set(FILTRO_TIEMPO_ORDER) == {"dia", "rango_dias", "rango_horas", "rango_horas_dia"}

    advance_modo2_to_filtro(client)
    resp = client.get("/configure/filtro-tiempo")
    html = resp.data.decode("utf-8")
    assert html.count('name="filtro_tipo"') == 4


# ---------------------------------------------------------------------------
# Persistencia y navegación
# ---------------------------------------------------------------------------


def test_seleccion_persiste_al_avanzar_y_volver(client):
    advance_modo2_to_filtro(client)

    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "siguiente", "filtro_tipo": "rango_horas_dia",
        "filtro_dia": "2024-01-05", "filtro_hora_ini": "20:00", "filtro_hora_fin": "23:30",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "rango_horas_dia", "dia": "2024-01-05", "desde": None, "hasta": None,
        "hora_ini": "20:00", "hora_fin": "23:30",
    }

    # Volver a la pantalla de filtro (navegación directa) repuebla la
    # selección guardada.
    resp = client.get("/configure/filtro-tiempo")
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    match = re.search(r'<input type="radio" name="filtro_tipo" value="rango_horas_dia"[^>]*checked', html)
    assert match is not None
    assert 'id="filtro_dia" name="filtro_dia" value="2024-01-05"' in html
    assert 'id="filtro_hora_ini" name="filtro_hora_ini" value="20:00"' in html
    assert 'id="filtro_hora_fin" name="filtro_hora_fin" value="23:30"' in html

    case = current_case(client)
    assert case.filtro_tiempo["tipo"] == "rango_horas_dia"


def test_anterior_guarda_estado_y_regresa_a_revision_del_mapeo(client):
    advance_modo2_to_filtro(client)

    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "anterior", "filtro_tipo": "dia", "filtro_dia": "2024-02-10",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "dia", "dia": "2024-02-10", "desde": None, "hasta": None,
        "hora_ini": None, "hora_fin": None,
    }
    assert case.mapping_draft == case.mapping
    assert case.mapping_stage == "review"


def test_confirmar_mapeo_de_nuevo_regresa_a_filtro_temporal(client):
    """Tras "Anterior" desde Filtro temporal, confirmar el mapeo otra vez
    debe volver a insertar la pantalla de Filtro temporal (sigue en Modo 2),
    sin perder la selección ya guardada."""
    advance_modo2_to_filtro(client)
    client.post("/configure/filtro-tiempo", data={
        "accion": "anterior", "filtro_tipo": "rango_dias",
        "filtro_desde": "2024-01-01", "filtro_hasta": "2024-01-31",
    }, follow_redirects=True)

    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert "Filtro temporal".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "rango_dias", "dia": None, "desde": "2024-01-01", "hasta": "2024-01-31",
        "hora_ini": None, "hora_fin": None,
    }
