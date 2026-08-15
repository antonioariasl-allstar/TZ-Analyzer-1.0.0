"""FASE 2 WEB — Modo 2 (bitácora filtrada por tiempo): pantalla de "Filtro
temporal" entre la Revisión del mapeo y la Identificación, dividida en dos
pantallas reales (MICROBLOQUE F3.4):

- Pantalla 1 (``/configure/filtro-tiempo``): solo la selección del tipo de
  filtro.
- Pantalla 2 (``/configure/filtro-tiempo/parametros``): solo los parámetros
  del tipo ya elegido.

No cubre todavía la aplicación real del filtro al DataFrame (eso queda para
un microbloque posterior, cubierto en ``test_modo2_process_and_alcance.py``)."""
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


def seleccionar_tipo(client, tipo, accion="siguiente"):
    """Envía la Pantalla 1 (selección) y devuelve la respuesta (por defecto,
    sigue el redirect hasta la Pantalla 2)."""
    return client.post(
        "/configure/filtro-tiempo",
        data={"accion": accion, "filtro_tipo": tipo},
        follow_redirects=True,
    )


def enviar_parametros(client, parametros, accion="siguiente"):
    data = {"accion": accion}
    data.update(parametros)
    return client.post("/configure/filtro-tiempo/parametros", data=data, follow_redirects=True)


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

    # Tampoco es alcanzable navegando directamente a ninguna de las dos
    # pantallas.
    resp = client.get("/configure/filtro-tiempo", follow_redirects=True)
    assert "Identificación de la bitácora".encode("utf-8") in resp.data
    resp = client.get("/configure/filtro-tiempo/parametros", follow_redirects=True)
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
# Pantalla 1 — las cuatro opciones (checklist punto 1)
# ---------------------------------------------------------------------------


def test_pantalla_1_muestra_las_cuatro_opciones_y_ningun_campo_de_parametros(client):
    advance_modo2_to_filtro(client)
    resp = client.get("/configure/filtro-tiempo")
    html = resp.data.decode("utf-8")

    assert html.count('name="filtro_tipo"') == 4
    assert "Día específico" in html
    assert "Rango de fechas" in html
    assert "Rango de horas" in html
    assert "Rango de horas en un día específico" in html

    # La Pantalla 1 no debe mostrar todavía ningún campo de parámetros.
    assert 'name="filtro_dia"' not in html
    assert 'name="filtro_desde"' not in html
    assert 'name="filtro_hasta"' not in html
    assert 'name="filtro_hora_ini"' not in html
    assert 'name="filtro_hora_fin"' not in html


# ---------------------------------------------------------------------------
# Capacidad (case.capabilities_preview -> filtros_temporales) -> opciones
# (checklist punto 2)
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
    opción, un envío manipulado con un tipo no habilitado debe rechazarse
    ya en la Pantalla 1, sin llegar nunca a la Pantalla 2."""
    advance_modo2_to_filtro_con_mapeo(client, _mapeo_sin_hora())

    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "siguiente", "filtro_tipo": "rango_horas",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "no está disponible para esta bitácora".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo is None
    assert case.filtro_tiempo_tipo is None


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
        "accion": "siguiente", "filtro_tipo": "dia",
    }, follow_redirects=True)
    assert "no dispone de una fecha reconocible".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo is None

    # Tampoco es alcanzable la Pantalla 2 directamente.
    resp = client.get("/configure/filtro-tiempo/parametros", follow_redirects=True)
    assert "no dispone de una fecha reconocible".encode("utf-8") in resp.data


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
# Pantalla 2 — solo los campos del tipo elegido (checklist puntos 3-6)
# ---------------------------------------------------------------------------


def test_dia_especifico_pantalla_2_solo_muestra_fecha(client):
    advance_modo2_to_filtro(client)
    resp = seleccionar_tipo(client, "dia")
    assert resp.status_code == 200
    assert resp.request.path == "/configure/filtro-tiempo/parametros"
    html = resp.data.decode("utf-8")

    assert 'name="filtro_dia"' in html
    assert 'name="filtro_desde"' not in html
    assert 'name="filtro_hasta"' not in html
    assert 'name="filtro_hora_ini"' not in html
    assert 'name="filtro_hora_fin"' not in html


def test_rango_de_fechas_pantalla_2_solo_muestra_fecha_inicial_y_final(client):
    advance_modo2_to_filtro(client)
    resp = seleccionar_tipo(client, "rango_dias")
    html = resp.data.decode("utf-8")

    assert 'name="filtro_desde"' in html
    assert 'name="filtro_hasta"' in html
    assert 'name="filtro_dia"' not in html
    assert 'name="filtro_hora_ini"' not in html
    assert 'name="filtro_hora_fin"' not in html


def test_rango_de_horas_pantalla_2_solo_muestra_hora_inicial_y_final(client):
    advance_modo2_to_filtro(client)
    resp = seleccionar_tipo(client, "rango_horas")
    html = resp.data.decode("utf-8")

    assert 'name="filtro_hora_ini"' in html
    assert 'name="filtro_hora_fin"' in html
    assert 'name="filtro_dia"' not in html
    assert 'name="filtro_desde"' not in html
    assert 'name="filtro_hasta"' not in html


def test_rango_de_horas_en_dia_especifico_pantalla_2_muestra_fecha_y_dos_horas(client):
    advance_modo2_to_filtro(client)
    resp = seleccionar_tipo(client, "rango_horas_dia")
    html = resp.data.decode("utf-8")

    assert 'name="filtro_dia"' in html
    assert 'name="filtro_hora_ini"' in html
    assert 'name="filtro_hora_fin"' in html
    assert 'name="filtro_desde"' not in html
    assert 'name="filtro_hasta"' not in html


# ---------------------------------------------------------------------------
# Persistencia y navegación entre las dos pantallas (checklist puntos 7-8)
# ---------------------------------------------------------------------------


def test_seleccion_persiste_al_avanzar_y_volver(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_horas_dia")

    resp = enviar_parametros(client, {
        "filtro_dia": "2024-01-05", "filtro_hora_ini": "20:00", "filtro_hora_fin": "23:30",
    })
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "rango_horas_dia", "dia": "2024-01-05", "desde": None, "hasta": None,
        "hora_ini": "20:00", "hora_fin": "23:30",
    }

    # Volver a la Pantalla 1 (navegación directa) mantiene el tipo marcado.
    resp = client.get("/configure/filtro-tiempo")
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    match = re.search(r'<input type="radio" name="filtro_tipo" value="rango_horas_dia"[^>]*checked', html)
    assert match is not None

    # Y volver a la Pantalla 2 repuebla los parámetros ya guardados.
    resp = client.get("/configure/filtro-tiempo/parametros")
    html = resp.data.decode("utf-8")
    assert 'id="filtro_dia" name="filtro_dia" value="2024-01-05"' in html
    assert 'id="filtro_hora_ini" name="filtro_hora_ini" value="20:00"' in html
    assert 'id="filtro_hora_fin" name="filtro_hora_fin" value="23:30"' in html

    case = current_case(client)
    assert case.filtro_tiempo["tipo"] == "rango_horas_dia"


def test_anterior_en_pantalla_1_regresa_a_revision_del_mapeo(client):
    advance_modo2_to_filtro(client)

    resp = client.post("/configure/filtro-tiempo", data={
        "accion": "anterior", "filtro_tipo": "dia",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.mapping_draft == case.mapping
    assert case.mapping_stage == "review"
    # "Anterior" en la Pantalla 1 es navegación pura: no guarda ninguna
    # selección todavía (solo "Continuar" guarda el tipo elegido).
    assert case.filtro_tiempo_tipo is None
    assert case.filtro_tiempo is None


def test_anterior_en_pantalla_2_regresa_a_pantalla_1_conservando_el_tipo(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_dias")

    resp = enviar_parametros(client, {
        "filtro_desde": "2024-01-01", "filtro_hasta": "2024-01-31",
    }, accion="anterior")
    assert resp.status_code == 200
    assert resp.request.path == "/configure/filtro-tiempo"
    assert "Filtro temporal".encode("utf-8") in resp.data

    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    match = re.search(r'<input type="radio" name="filtro_tipo" value="rango_dias"[^>]*checked', html)
    assert match is not None

    # "Anterior" en la Pantalla 2 no confirma un filtro: los parámetros
    # recién tecleados (aún no validados) no se guardan como filtro final.
    case = current_case(client)
    assert case.filtro_tiempo_tipo == "rango_dias"
    assert case.filtro_tiempo is None


def test_confirmar_mapeo_de_nuevo_regresa_a_filtro_temporal_sin_perder_la_seleccion(client):
    """Tras completar el Filtro temporal (ambas pantallas) y volver a
    confirmar el mapeo, la pantalla de selección debe volver a insertarse
    (sigue en Modo 2) con el tipo ya elegido precargado."""
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_dias")
    enviar_parametros(client, {"filtro_desde": "2024-01-01", "filtro_hasta": "2024-01-31"})

    client.post("/configure/back-to-mapping", follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert "Filtro temporal".encode("utf-8") in resp.data

    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    match = re.search(r'<input type="radio" name="filtro_tipo" value="rango_dias"[^>]*checked', html)
    assert match is not None

    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "rango_dias", "dia": None, "desde": "2024-01-01", "hasta": "2024-01-31",
        "hora_ini": None, "hora_fin": None,
    }


def test_cambio_de_tipo_no_aplica_parametros_incompatibles_del_tipo_anterior(client):
    """Si el usuario ya había completado "Rango de fechas" y cambia a "Día
    específico" en la Pantalla 1, la Pantalla 2 del nuevo tipo debe partir
    en blanco: no debe precargar ni aplicar en silencio ``desde``/``hasta``
    del tipo anterior."""
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_dias")
    enviar_parametros(client, {"filtro_desde": "2024-01-01", "filtro_hasta": "2024-01-31"})

    case = current_case(client)
    assert case.filtro_tiempo["tipo"] == "rango_dias"

    # Cambia de tipo en la Pantalla 1.
    resp = seleccionar_tipo(client, "dia")
    html = resp.data.decode("utf-8")
    assert 'name="filtro_dia"' in html
    assert 'value="2024-01-01"' not in html
    assert 'value="2024-01-31"' not in html

    # Si completa y confirma el nuevo tipo, el filtro final no conserva
    # ningún rastro del tipo anterior.
    enviar_parametros(client, {"filtro_dia": "2024-02-10"})
    case = current_case(client)
    assert case.filtro_tiempo == {
        "tipo": "dia", "dia": "2024-02-10", "desde": None, "hasta": None,
        "hora_ini": None, "hora_fin": None,
    }


# ---------------------------------------------------------------------------
# Validaciones (checklist punto 9) — se conservan en la Pantalla 2
# ---------------------------------------------------------------------------


def test_dia_especifico_sin_fecha_es_rechazado(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "dia")

    resp = enviar_parametros(client, {"filtro_dia": ""})
    assert "Indique el día para el filtro.".encode("utf-8") in resp.data

    case = current_case(client)
    assert case.filtro_tiempo is None


def test_rango_de_fechas_incompleto_es_rechazado(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_dias")

    resp = enviar_parametros(client, {"filtro_desde": "2024-01-10", "filtro_hasta": ""})
    assert "Indique el rango de fechas completo".encode("utf-8") in resp.data
    assert current_case(client).filtro_tiempo is None


def test_rango_de_fechas_invertido_es_rechazado(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_dias")

    resp = enviar_parametros(client, {"filtro_desde": "2024-02-01", "filtro_hasta": "2024-01-01"})
    assert "anterior o igual a la fecha final".encode("utf-8") in resp.data
    assert current_case(client).filtro_tiempo is None


def test_rango_de_horas_incompleto_es_rechazado(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_horas")

    resp = enviar_parametros(client, {"filtro_hora_ini": "20:00", "filtro_hora_fin": ""})
    assert "Indique el rango de horas completo".encode("utf-8") in resp.data
    assert current_case(client).filtro_tiempo is None


def test_rango_de_horas_en_dia_especifico_incompleto_es_rechazado(client):
    advance_modo2_to_filtro(client)
    seleccionar_tipo(client, "rango_horas_dia")

    resp = enviar_parametros(client, {"filtro_dia": "2024-01-05", "filtro_hora_ini": "", "filtro_hora_fin": "23:00"})
    assert "Indique el día y el rango de horas completo".encode("utf-8") in resp.data
    assert current_case(client).filtro_tiempo is None


def test_parametros_no_accesible_sin_elegir_tipo_primero(client):
    """Defensa en profundidad: navegar directo a la Pantalla 2 sin haber
    pasado por la Pantalla 1 debe devolver a la selección, no romper."""
    advance_modo2_to_filtro(client)

    resp = client.get("/configure/filtro-tiempo/parametros", follow_redirects=True)
    assert resp.status_code == 200
    assert resp.request.path == "/configure/filtro-tiempo"
    assert "Seleccione primero el tipo de filtro temporal".encode("utf-8") in resp.data
