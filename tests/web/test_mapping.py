"""FASE 2 WEB — Pantalla 2: mapeo de columnas."""
from __future__ import annotations

import json
import re

from tz_web import state as tz_web_state
from tests.web.conftest import REAL_MAPPING_FORM, SHEET_NAME, upload_real_file


def _reach_mapping_screen(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)


def test_mapping_screen_sin_hoja_redirige_a_inicio(client):
    client.post("/modo/1")
    resp = client.get("/mapping", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cargar archivo" in resp.data


def test_mapping_muestra_descripciones_field_context(client):
    _reach_mapping_screen(client)
    resp = client.get("/mapping")
    assert resp.status_code == 200
    assert "Fecha del evento telefónico".encode("utf-8") in resp.data
    assert "IMEI del dispositivo móvil investigado".encode("utf-8") in resp.data


def test_mapeo_valido_calcula_capacidades_previstas(client):
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data
    assert "Análisis que podrá generar el sistema".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft is not None
    assert case.mapping_draft["fecha"] == ("col", "FECHA_INICIAL")
    assert case.capabilities_preview is not None
    assert case.capabilities_preview["procesable"] is True
    assert case.capabilities_preview["capacidades"]["identificacion"]["disponible"] is True


def test_mapeo_duplicado_es_rechazado(client):
    """Corrección UX: la validación rechaza la columna duplicada, pero ya no
    descarta el resto del mapeo — el borrador y los campos no conflictivos
    se conservan para que el usuario solo corrija lo señalado (ver
    tz_web.routes._parse_mapping_form)."""
    _reach_mapping_screen(client)
    form = dict(REAL_MAPPING_FORM)
    # 'hora' apunta a la misma columna que 'fecha' -> asignación duplicada.
    form["tipo_hora"] = "col"
    form["col_hora"] = "FECHA_INICIAL"
    resp = client.post("/mapping", data=form, follow_redirects=True)
    assert resp.status_code == 200
    assert "no puede asignarse a más de un campo".encode("utf-8") in resp.data
    # No se retrocede a la Revisión: se vuelve a mostrar el formulario.
    assert "Revisión del mapeo".encode("utf-8") not in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft is not None
    assert case.mapping_stage == "form"
    # Los dos campos implicados en el conflicto quedan señalados...
    assert case.mapping_conflicts == ["fecha", "hora"]
    assert case.mapping_draft["fecha"] == ("col", "FECHA_INICIAL")
    assert case.mapping_draft["hora"] == ("col", "FECHA_INICIAL")
    # ...y el resto de las asignaciones ya hechas permanece intacto.
    assert case.mapping_draft["tel"] == ("col", "NUMERO_ORIGEN")
    assert case.mapping_draft["imei"] == ("col", "IMEI_ORIGEN")
    assert case.mapping_draft["duracion"] == ("col", "DURACION_SEG")


def test_mapeo_duplicado_repuebla_formulario_y_marca_campos_conflictivos(client):
    """La pantalla vuelta a mostrar debe traer los valores ya elegidos
    seleccionados en el HTML (no en blanco) y resaltar solo los campos
    conflictivos."""
    _reach_mapping_screen(client)
    form = dict(REAL_MAPPING_FORM)
    form["tipo_hora"] = "col"
    form["col_hora"] = "FECHA_INICIAL"
    resp = client.post("/mapping", data=form, follow_redirects=True)
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))

    # Asignaciones correctas ya elegidas (p. ej. tel) siguen preseleccionadas.
    assert re.search(r'<input type="radio" name="tipo_tel" value="col" id="tipo_col_tel"\s+checked', html)
    assert re.search(r'<option value="NUMERO_ORIGEN"\s+selected>NUMERO_ORIGEN</option>', html)

    # Los dos campos del conflicto están marcados como tal.
    assert 'class="tz-mapping-row tz-conflict" data-campo="fecha"' in html
    assert 'class="tz-mapping-row tz-conflict" data-campo="hora"' in html
    # Un campo no implicado no lleva la marca de conflicto.
    assert 'class="tz-mapping-row" data-campo="tel"' in html

    # El JS recibe la lista de campos a enfocar, en orden.
    match = re.search(r"tzMappingFocusConflict\((\[.*?\])\)", resp.data.decode("utf-8"))
    assert match is not None
    assert json.loads(match.group(1)) == ["fecha", "hora"]


def test_mapeo_corrige_conflicto_y_confirma(client):
    """Tras el error, el usuario corrige solo el campo conflictivo y puede
    completar el flujo normalmente."""
    _reach_mapping_screen(client)
    form = dict(REAL_MAPPING_FORM)
    form["tipo_hora"] = "col"
    form["col_hora"] = "FECHA_INICIAL"
    client.post("/mapping", data=form, follow_redirects=True)

    form["col_hora"] = "HORA_INICIAL"
    resp = client.post("/mapping", data=form, follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_conflicts == []
    assert case.mapping_draft["hora"] == ("col", "HORA_INICIAL")
    assert case.mapping_draft["fecha"] == ("col", "FECHA_INICIAL")


def test_mapeo_multiples_conflictos_marca_todos_los_campos(client):
    """Varias columnas duplicadas a la vez: todos los campos implicados
    quedan en mapping_conflicts, no solo el primero detectado."""
    _reach_mapping_screen(client)
    form = dict(REAL_MAPPING_FORM)
    form["col_hora"] = "FECHA_INICIAL"  # fecha/hora -> misma columna
    form["col_contacto"] = "NUMERO_ORIGEN"  # tel/contacto -> misma columna
    resp = client.post("/mapping", data=form, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert set(case.mapping_conflicts) == {"fecha", "hora", "tel", "contacto"}
    # Orden estable según CANONICAL_FIELDS, para que el foco vaya siempre
    # al primer campo del formulario (no al primero detectado).
    assert case.mapping_conflicts.index("fecha") < case.mapping_conflicts.index("tel")


def test_mapeo_vacio_es_rechazado(client):
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert "no asigna ningún campo".encode("utf-8") in resp.data


def test_confirmar_mapeo_sin_borrador_es_rechazado(client):
    _reach_mapping_screen(client)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "No hay un mapeo pendiente".encode("utf-8") in resp.data


def test_confirmar_mapeo_valido_avanza_a_configuracion(client):
    _reach_mapping_screen(client)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping is not None
    assert case.mapping_draft is None


def test_editar_mapeo_conserva_borrador_y_capacidades(client):
    """"Volver a editar" solo cambia la vista (de revisión a formulario):
    mapping_draft y capabilities_preview del análisis actual no se pierden,
    a diferencia del comportamiento previo que los descartaba por completo."""
    _reach_mapping_screen(client)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    draft_antes = dict(case.mapping_draft)
    capabilities_antes = case.capabilities_preview

    resp = client.post("/mapping/edit", follow_redirects=True)
    assert resp.status_code == 200

    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft == draft_antes
    assert case.capabilities_preview == capabilities_antes
    assert case.mapping_stage == "form"


def test_volver_a_editar_muestra_formulario_no_la_revision(client):
    _reach_mapping_screen(client)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/edit", follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "Revisión del mapeo" not in html
    assert "Grupo 1 de 7" in html


def test_volver_a_editar_repuebla_usar_columna_y_columna_elegida(client):
    _reach_mapping_screen(client)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    resp = client.post("/mapping/edit", follow_redirects=True)
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))

    assert re.search(r'<input type="radio" name="tipo_fecha" value="col" id="tipo_col_fecha"\s+checked', html)
    assert re.search(
        r'<option value="FECHA_INICIAL"\s+selected>FECHA_INICIAL</option>', html
    )


def test_volver_a_editar_repuebla_omitir_para_campos_no_mapeados(client):
    form = dict(REAL_MAPPING_FORM)
    del form["tipo_duracion"], form["col_duracion"]
    _reach_mapping_screen(client)
    client.post("/mapping", data=form, follow_redirects=True)
    resp = client.post("/mapping/edit", follow_redirects=True)
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))

    assert re.search(r'<input type="radio" name="tipo_duracion" value="omitido" id="tipo_omit_duracion"\s+checked', html)


def test_volver_a_editar_no_afecta_hoja_ni_archivo_ni_mapeo_confirmado(client):
    """El único estado que se limpia al editar es el terminal de una corrida
    fallida (no aplicable aquí); archivo, hoja y mapeo confirmado no se
    tocan (solo cambia mapping_stage)."""
    _reach_mapping_screen(client)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    archivo_antes, hoja_antes = case.temp_path, case.sheet

    client.post("/mapping/edit", follow_redirects=True)
    case = tz_web_state.get_session(case_id)
    assert case.temp_path == archivo_antes
    assert case.sheet == hoja_antes
    assert case.mapping is None  # aún no confirmado, sin cambios


def test_plantilla_de_mapeo_no_ofrece_valor_fijo(client):
    _reach_mapping_screen(client)
    resp = client.get("/mapping")
    assert resp.status_code == 200
    assert "Valor fijo".encode("utf-8") not in resp.data
    assert "Usar columna".encode("utf-8") in resp.data
    assert "Omitir".encode("utf-8") in resp.data


def test_backend_sigue_aceptando_asignacion_fija_por_compatibilidad_interna(client):
    """La UI ya no ofrece 'Valor fijo', pero _parse_mapping_form debe seguir
    aceptando tipo_<campo>=fijo (contrato interno Dict[str, Tuple[str, Any]]
    que _apply_mapeo/_validate_mapeo siguen soportando)."""
    _reach_mapping_screen(client)
    form = dict(REAL_MAPPING_FORM)
    del form["tipo_interaccion"], form["col_interaccion"]
    form["tipo_interaccion"] = "fijo"
    form["fijo_interaccion"] = "LLAMADA"

    resp = client.post("/mapping", data=form, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft is not None
    assert case.mapping_draft["interaccion"] == ("fijo", "LLAMADA")


def test_mapping_screen_muestra_selector_de_unidad_de_duracion(client):
    """El selector de unidad vive dentro de col_wrap_duracion (el mismo
    bloque que JS oculta/muestra según Usar columna/Omitir)."""
    _reach_mapping_screen(client)
    resp = client.get("/mapping")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'id="col_wrap_duracion"' in html
    assert 'id="duration_unit_decision"' in html
    assert "Seleccione la unidad utilizada por los valores de esta columna." in html
    idx_row = html.index('data-campo="duracion"')
    idx_next_row = html.index('data-campo="interaccion"')
    idx_wrap = html.index('id="col_wrap_duracion"')
    idx_unidad = html.index('id="duration_unit_decision"')
    assert idx_row < idx_wrap < idx_unidad < idx_next_row


def test_mapeo_guarda_unidad_de_duracion_antes_de_capabilities_preview(client):
    form = dict(REAL_MAPPING_FORM)
    form["duration_unit_decision"] = "segundos"
    _reach_mapping_screen(client)
    client.post("/mapping", data=form, follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.duration_unit_decision == "segundos"
    assert case.mapping_draft["duracion"] == ("col", "DURACION_SEG")


def _celda_duracion(html: str) -> str:
    """Celda de estado de 'duracion' en la tabla horizontal de capacidades
    (identificada por data-capacidad="duracion", no por posición de fila)."""
    marker = '<td data-capacidad="duracion">'
    idx = html.index(marker)
    return html[idx: html.index("</td>", idx)]


def test_revision_muestra_disponible_cuando_hay_unidad_valida(client):
    form = dict(REAL_MAPPING_FORM)
    form["duration_unit_decision"] = "segundos"
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=form, follow_redirects=True)
    html = resp.data.decode("utf-8")

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    cap = case.capabilities_preview["capacidades"]["duracion"]
    celda = _celda_duracion(html)
    if not cap["disponible"]:
        assert "No disponible" not in celda
        assert "Pendiente de configuración" not in celda
        assert "Disponible" in celda


def test_revision_muestra_pendiente_cuando_falta_unidad(client):
    """Sin duration_unit_decision explícita, la revisión no debe decir 'No
    disponible' por ausencia de unidad: debe pedir la decisión."""
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    html = resp.data.decode("utf-8")
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    cap = case.capabilities_preview["capacidades"]["duracion"]
    if not cap["disponible"]:
        assert "Pendiente de configuración" in _celda_duracion(html)


def test_revision_muestra_omitida_cuando_duracion_no_se_mapea(client):
    form = dict(REAL_MAPPING_FORM)
    del form["tipo_duracion"], form["col_duracion"]
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=form, follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "Omitida" in html

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft["duracion"] == ("omitido", None)


def test_unidad_de_duracion_persiste_al_volver_a_editar(client):
    form = dict(REAL_MAPPING_FORM)
    form["duration_unit_decision"] = "milisegundos"
    _reach_mapping_screen(client)
    client.post("/mapping", data=form, follow_redirects=True)
    client.post("/mapping/edit", follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.duration_unit_decision == "milisegundos"

    resp = client.get("/mapping")
    html = resp.data.decode("utf-8")
    assert '<option value="milisegundos" selected>' in html


def test_confirmar_mapeo_con_unidad_de_duracion_sigue_llevando_a_configuracion(client):
    form = dict(REAL_MAPPING_FORM)
    form["duration_unit_decision"] = "segundos"
    _reach_mapping_screen(client)
    client.post("/mapping", data=form, follow_redirects=True)
    resp = client.post("/mapping/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "Identificación de la bitácora".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping is not None
    assert case.duration_unit_decision == "segundos"


def test_revision_presenta_azimut_entero_sin_decimal_y_conserva_fraccion_real(client):
    """Sección 1 del microbloque: solo presentación de la fila 'Muestra' en
    la revisión horizontal del mapeo — no toca case.samples ni el DataFrame."""
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    valor_original = list(case.samples["AZIMUT_INICIAL"])
    case.samples["AZIMUT_INICIAL"] = ["20.0", "22.5", "160.0"]

    resp = client.get("/mapping")
    html = resp.data.decode("utf-8")
    idx = html.index('data-campo="azimut"', html.index("Muestra"))
    celda = html[idx: html.index("</td>", idx)]
    assert celda.strip().endswith(">20")
    assert "20.0" not in celda

    # No se modificó el DataFrame ni el valor original guardado en el estado.
    assert case.samples["AZIMUT_INICIAL"] == ["20.0", "22.5", "160.0"]
    case.samples["AZIMUT_INICIAL"] = valor_original


def test_mapping_form_usa_etiquetas_del_catalogo_central(client):
    """El formulario de mapeo muestra las etiquetas del catálogo central
    (``tz_web.field_catalog``), no las claves internas crudas."""
    _reach_mapping_screen(client)
    resp = client.get("/mapping")
    html = resp.data.decode("utf-8")
    assert "<h3>Fecha</h3>" in html
    assert "<h3>Número analizado</h3>" in html
    assert "<h3>Tipo de interacción</h3>" in html


def test_revision_horizontal_usa_etiquetas_del_catalogo_central(client):
    """La tabla de revisión horizontal muestra las etiquetas del catálogo
    central en sus encabezados de columna, no las claves internas crudas."""
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "<th>Fecha</th>" in html
    assert "<th>Número analizado</th>" in html
    assert "<th>IMEI</th>" in html


def test_mapeo_y_revision_siguen_usando_claves_internas_originales(client):
    """Las claves internas del mapeo (``case.mapping_draft``) no cambian por
    la introducción del catálogo de presentación: siguen siendo 'fecha',
    'tel', 'imei', etc., exactamente como las espera process_case()."""
    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.mapping_draft["fecha"] == ("col", "FECHA_INICIAL")
    assert case.mapping_draft["tel"] == ("col", "NUMERO_ORIGEN")
    assert case.mapping_draft["imei"] == ("col", "IMEI_ORIGEN")
    assert set(case.mapping_draft.keys()) == {
        "fecha", "hora", "duracion", "interaccion", "tel", "contacto",
        "imei", "imsi", "lat", "long", "azimut", "antena", "celda", "direccion",
    }


def test_mapeo_no_ejecuta_mapping_wizard_run(client, monkeypatch):
    """El wizard interactivo nunca debe instanciarse/ejecutarse desde la web."""
    from tz_core.mapping_wizard import MappingWizard

    def _fail_run(self):
        raise AssertionError("MappingWizard.run() no debía invocarse desde tz_web")

    monkeypatch.setattr(MappingWizard, "run", _fail_run)

    _reach_mapping_screen(client)
    resp = client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    assert resp.status_code == 200
    client.post("/mapping/confirm", follow_redirects=True)
