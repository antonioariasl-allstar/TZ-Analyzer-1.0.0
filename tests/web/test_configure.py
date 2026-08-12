"""FASE 2 WEB — Pantalla 3: configuración e inicio de tarea (sección 9/10).

Cubre tanto la subpantalla 3A (Identificación de la bitácora, primera
subpantalla interna del Paso 3) como la Configuración completa "heredada"
(``/configure/legacy``), que por ahora solo se alcanza directamente en las
pruebas — la navegación real 3A -> 3B... todavía no llega hasta ella (ver
microbloque "cierre visual del mapeo + configuración 3A")."""
from __future__ import annotations

import os
import re

from tz_core.config_loader import get_config

from tz_web import state as tz_web_state
from tests.web.conftest import (
    REAL_MAPPING_FORM,
    SHEET_NAME,
    advance_to_configure,
    select_output_folder,
    upload_real_file,
    wait_for_terminal_status,
)


# ---------------------------------------------------------------------------
# Subpantalla 3A — Identificación de la bitácora
# ---------------------------------------------------------------------------


def test_configure_screen_sin_mapeo_confirmado_redirige_a_mapeo(client):
    resp = client.get("/configure", follow_redirects=True)
    assert resp.status_code == 200
    assert "Primero confirme el mapeo".encode("utf-8") in resp.data


def test_confirmar_mapeo_lleva_a_3a(client):
    resp = advance_to_configure(client)
    assert resp.status_code == 200
    assert "3. Configuración".encode("utf-8") in resp.data
    assert "Identificación de la bitácora".encode("utf-8") in resp.data
    assert "Paso 1 de 5".encode("utf-8") in resp.data


def test_3a_muestra_unicamente_alias_usuario_abonado(client):
    advance_to_configure(client)
    resp = client.get("/configure")
    html = resp.data.decode("utf-8")
    assert "Alias" in html
    assert "Nombre de usuario" in html
    assert "Abonado" in html
    # Nada de la Configuración antigua completa debe reaparecer aquí.
    for etiqueta in (
        "Tipo de bitácora", "Nombre de salida", "Top de antenas",
        "Top de contactos", "Color del tema", "Filtro temporal",
        "Orden de fecha", "Carpeta de salida", "Ejecutar análisis",
    ):
        assert etiqueta not in html


def test_volver_al_mapeo_regresa_a_revision_sin_perder_datos(client):
    advance_to_configure(client)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    mapping_confirmado = dict(case.mapping)
    unidad_duracion = case.duration_unit_decision
    hoja = case.sheet
    archivo = case.temp_path

    resp = client.post("/configure/back-to-mapping", follow_redirects=True)
    assert resp.status_code == 200
    assert "Revisión del mapeo".encode("utf-8") in resp.data
    assert "Volver a editar".encode("utf-8") in resp.data

    case = tz_web_state.get_session(case_id)
    assert case.mapping == mapping_confirmado
    assert case.mapping_draft == mapping_confirmado
    assert case.duration_unit_decision == unidad_duracion
    assert case.sheet == hoja
    assert case.temp_path == archivo


def test_datos_de_3a_se_conservan_al_navegar_atras_y_adelante(client):
    advance_to_configure(client)
    client.post("/configure", data={
        "accion": "siguiente",
        "identidad_alias": "Investigador Uno",
        "identidad_nombre_usuario": "juan.perez",
        "identidad_abonado": "3001234567",
    }, follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.identity_overrides == {
        "alias": "Investigador Uno",
        "nombre_usuario": "juan.perez",
        "abonado": "3001234567",
    }

    # Volver al mapeo y confirmar de nuevo no debe perder los datos escritos.
    client.post("/configure/back-to-mapping", follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)

    resp = client.get("/configure")
    html = resp.data.decode("utf-8")
    assert "Investigador Uno" in html
    assert "juan.perez" in html
    assert "3001234567" in html

    case = tz_web_state.get_session(case_id)
    assert case.identity_overrides == {
        "alias": "Investigador Uno",
        "nombre_usuario": "juan.perez",
        "abonado": "3001234567",
    }


def test_omitir_deja_los_tres_valores_vacios(client):
    advance_to_configure(client)
    resp = client.post("/configure", data={
        "accion": "omitir",
        "identidad_alias": "no debería guardarse",
        "identidad_nombre_usuario": "tampoco",
        "identidad_abonado": "ni esto",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.identity_overrides == {}


def test_omitir_y_siguiente_avanzan_a_3b_sin_configuracion_antigua(client):
    advance_to_configure(client)
    resp = client.post("/configure", data={"accion": "omitir"}, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Paso 2 de 5".encode("utf-8") in resp.data
    assert "Opciones del análisis" in html
    for etiqueta in ("Tipo de bitácora", "Carpeta de salida", "Ejecutar análisis", "Color del tema"):
        assert etiqueta not in html


# ---------------------------------------------------------------------------
# Indicador superior — "3. Configuración" activo en todas las subpantallas
# ---------------------------------------------------------------------------


def test_indicador_marca_configuracion_activo_en_todas_las_subpantallas(client):
    import re

    advance_to_configure(client)
    for path in (
        "/configure", "/configure/opciones", "/configure/productos", "/configure/color",
        "/configure/final", "/configure/resumen", "/configure/legacy",
    ):
        resp = client.get(path)
        html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
        assert '<li class="active"> 3. Configuración </li>' in html
        assert '<li class="active"> 1. Archivo </li>' not in html


# ---------------------------------------------------------------------------
# Subpantalla 3B — Opciones del análisis
# ---------------------------------------------------------------------------


def test_3b_muestra_opciones_del_analisis(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    resp = client.get("/configure/opciones")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Paso 2 de 5" in html
    assert "Top de antenas" in html
    assert "Top de contactos" in html


def test_3b_anterior_regresa_a_3a(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    resp = client.post("/configure/opciones", data={
        "accion": "anterior", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 1 de 5".encode("utf-8") in resp.data


def test_3b_siguiente_avanza_a_3c(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    resp = client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "7", "top_contactos": "3",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 3 de 5".encode("utf-8") in resp.data


def test_3b_valida_top_antenas_no_numerico(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    resp = client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "no-es-un-numero", "top_contactos": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "debe ser un número entero".encode("utf-8") in resp.data


def test_3b_persiste_valores_al_navegar_atras_y_adelante(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "7", "top_contactos": "3",
    }, follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.top_antenas == 7
    assert case.top_contactos == 3

    client.post("/configure/productos", data={"accion": "anterior"}, follow_redirects=True)
    resp = client.get("/configure/opciones")
    html = resp.data.decode("utf-8")
    assert 'value="7"' in html
    assert 'value="3"' in html


# ---------------------------------------------------------------------------
# Subpantalla 3C — Productos de salida
# ---------------------------------------------------------------------------


def _advance_to_3c(client):
    advance_to_configure(client)
    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    return client.post("/configure/opciones", data={
        "accion": "siguiente", "top_antenas": "", "top_contactos": "",
    }, follow_redirects=True)


def test_3c_muestra_html_kmz_hashes_como_incluidos(client):
    _advance_to_3c(client)
    resp = client.get("/configure/productos")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Informe HTML" in html
    assert "Mapa KMZ" in html
    assert "Hashes SHA-256" in html
    assert html.count("INCLUIDO") == 3
    # No deben aparecer como checkboxes desmarcables.
    assert 'name="html"' not in html
    assert 'name="kmz"' not in html
    assert 'name="hashes"' not in html


def test_3c_kml_desactivado_por_defecto(client):
    _advance_to_3c(client)
    resp = client.get("/configure/productos")
    html = resp.data.decode("utf-8")
    assert 'id="kml_opcional"' in html
    assert 'id="kml_opcional" name="kml_opcional" checked' not in html


def test_3c_activar_kml_produce_solo_kmz_false(client):
    _advance_to_3c(client)
    resp = client.post("/configure/productos", data={
        "accion": "siguiente", "kml_opcional": "on",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.kml_opcional is True
    assert case.solo_kmz is False


def test_3c_desactivar_kml_produce_solo_kmz_true(client):
    _advance_to_3c(client)
    resp = client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.kml_opcional is False
    assert case.solo_kmz is True


def test_3c_anterior_regresa_a_3b(client):
    _advance_to_3c(client)
    resp = client.post("/configure/productos", data={"accion": "anterior"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 2 de 5".encode("utf-8") in resp.data


# ---------------------------------------------------------------------------
# Subpantalla 3D — Color de la bitácora
# ---------------------------------------------------------------------------


def _advance_to_3d(client):
    _advance_to_3c(client)
    return client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)


def test_3d_muestra_paleta_real_y_color_por_defecto_seleccionado(client):
    _advance_to_3d(client)
    resp = client.get("/configure/color")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Paso 4 de 5" in html
    assert "Color de la bitácora" in html
    # La paleta real (config.json -> style.palette) debe estar presente,
    # incluido el nombre del color por defecto (theme_hex = #76ff03).
    assert "Verde neón" in html
    assert "#76ff03" in html
    assert "Magenta (alto contraste)" in html
    match = re.search(
        r'<input type="radio" name="color_hex" value="#76ff03"\s+checked',
        re.sub(r"\s+", " ", html),
    )
    assert match is not None


def test_3d_elegir_otro_color_lo_persiste(client):
    _advance_to_3d(client)
    resp = client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#ff00ff",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.color_hex == "#ff00ff"

    resp = client.get("/configure/color")
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    assert 'value="#ff00ff" checked' in html


def test_3d_color_fuera_de_paleta_es_rechazado(client):
    _advance_to_3d(client)
    resp = client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#123456",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Elija uno de los colores disponibles".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.color_hex is None


def test_3d_persiste_al_navegar_atras_y_adelante(client):
    _advance_to_3d(client)
    client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#00ffff",
    }, follow_redirects=True)

    client.post("/configure/productos", data={"accion": "anterior"}, follow_redirects=True)
    resp = client.get("/configure/color")
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    assert 'value="#00ffff" checked' in html


def test_3d_swatch_seleccionado_no_depende_del_texto_visible(client):
    """El estado funcional de la tarjeta seleccionada se expresa con el
    atributo ``checked`` del radio nativo (accesible) y la clase CSS
    ``selected`` de la tarjeta; el texto "Seleccionado" (si está presente en
    el DOM) es solo un refuerzo accesible, no la fuente de verdad visual."""
    _advance_to_3d(client)
    resp = client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#ff00ff",
    }, follow_redirects=True)
    assert resp.status_code == 200

    resp = client.get("/configure/color")
    html = re.sub(r"\s+", " ", resp.data.decode("utf-8"))
    assert 'value="#ff00ff" checked' in html
    assert 'class="tz-color-check"' in html


def test_3d_anterior_regresa_a_3c(client):
    _advance_to_3d(client)
    resp = client.post("/configure/color", data={"accion": "anterior"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 3 de 5".encode("utf-8") in resp.data


def test_3d_siguiente_conduce_a_3e(client):
    _advance_to_3d(client)
    resp = client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#76ff03",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 5 de 5".encode("utf-8") in resp.data
    assert "Preparar análisis".encode("utf-8") in resp.data


# ---------------------------------------------------------------------------
# Subpantalla 3E — Preparar análisis
# ---------------------------------------------------------------------------


def _advance_to_3e(client):
    _advance_to_3d(client)
    return client.post("/configure/color", data={
        "accion": "siguiente", "color_hex": "#76ff03",
    }, follow_redirects=True)


def test_3e_muestra_nombre_sugerido(client):
    _advance_to_3e(client)
    resp = client.get("/configure/final")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Nombre de salida" in html
    assert "CAMBIAR NOMBRE" in html
    assert "identificador de ejecución" in html


def test_3e_cambiar_nombre_persiste(client):
    _advance_to_3e(client)
    resp = client.post("/configure/final", data={
        "accion": "anterior", "nombre_modo": "manual", "output_base_name": "Mi Caso Especial",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.output_base_name == "Mi Caso Especial"

    resp = client.get("/configure/final")
    assert "Mi Caso Especial" in resp.data.decode("utf-8")


def test_3e_puede_volver_al_nombre_sugerido(client):
    _advance_to_3e(client)
    client.post("/configure/final", data={
        "accion": "anterior", "nombre_modo": "manual", "output_base_name": "Nombre Manual",
    }, follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.output_base_name == "Nombre Manual"

    client.post("/configure/final", data={"accion": "anterior", "nombre_modo": "sugerido"}, follow_redirects=True)
    case = tz_web_state.get_session(case_id)
    assert case.output_base_name is None


def test_3e_ubicacion_es_carpeta_segura_sin_input_libre(client):
    _advance_to_3e(client)
    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    assert "Ubicación de salida" in html
    assert "TZ Analyzer" in html
    assert 'name="carpeta_salida"' not in html
    assert 'type="text" id="carpeta_salida"' not in html


def test_3e_no_contiene_alcance_ni_filtro(client):
    """"Preparar análisis" ya no muestra Alcance/filtro temporal (movido al
    Resumen, sección 2 del microbloque de separación Preparar/Resumen)."""
    _advance_to_3e(client)
    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    assert "Bitácora completa" not in html
    assert "filtro_tipo" not in html
    assert "Filtro temporal" not in html


def test_3e_no_contiene_opciones_avanzadas_ni_orden_fecha_ni_qc(client):
    """"Preparar análisis" ya no tiene sección "Opciones avanzadas": tipo de
    bitácora pasa a control de primer nivel, y Orden de fecha / QC
    bloqueante se eliminan de esta pantalla (sección 1/A1 del microbloque)."""
    _advance_to_3e(client)
    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    assert "Opciones avanzadas" not in html
    assert "<details" not in html
    assert "date_order_decision" not in html
    assert "qc_bloqueante_decision" not in html
    assert "Orden de fecha" not in html
    assert "Ante un problema excepcional" not in html
    match = re.search(
        r'<option value=""\s+selected>Automático</option>',
        re.sub(r"\s+", " ", html),
    )
    assert match is not None


def test_3e_no_contiene_resumen_completo(client):
    """"Preparar análisis" ya no incluye el resumen completo (Identificación,
    Análisis, Productos, Color) ni el botón "Generar análisis": eso vive
    ahora en la subpantalla de Resumen (sección A1/A2 del microbloque)."""
    _advance_to_3e(client)
    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    assert "Resumen del análisis" not in html
    for etiqueta in ("Identificación", "Productos", "Color de la bitácora"):
        assert etiqueta not in html
    assert "Generar análisis" not in html
    assert "Continuar al resumen" in html


def test_3e_anterior_regresa_a_3d_conservando_estado(client):
    _advance_to_3e(client)
    resp = client.post("/configure/final", data={"accion": "anterior"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 4 de 5".encode("utf-8") in resp.data


def test_3e_siguiente_no_inicia_tarea_y_lleva_a_resumen(client):
    """Pulsar "Continuar al resumen" únicamente guarda tipo de bitácora y
    nombre de salida; no arranca el análisis (sección 3 de PRUEBAS)."""
    _advance_to_3e(client)
    resp = client.post("/configure/final", data={
        "accion": "siguiente",
        "nombre_modo": "sugerido",
        "tipo_bitacora": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Resumen del análisis".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.task_started is False
    assert case.status == tz_web_state.STATUS_PENDING


# ---------------------------------------------------------------------------
# Subpantalla final — Resumen del análisis
# ---------------------------------------------------------------------------


def _advance_to_resumen(client, **final_overrides):
    _advance_to_3e(client)
    data = {"accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": ""}
    data.update(final_overrides)
    return client.post("/configure/final", data=data, follow_redirects=True)


def test_resumen_existe_como_pantalla_separada(client):
    _advance_to_resumen(client)
    resp = client.get("/configure/resumen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Resumen del análisis" in html
    assert "Identificación" in html
    assert "Análisis" in html
    assert "Productos" in html
    assert "Color" in html
    assert "Salida" in html
    assert "Generar análisis" in html


def test_resumen_sin_identificacion_muestra_no_especificado(client):
    _advance_to_resumen(client)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert html.count("No especificado") == 3


def test_resumen_con_identificacion(client):
    advance_to_configure(client)
    client.post("/configure", data={
        "accion": "siguiente",
        "identidad_alias": "Investigador Uno",
        "identidad_nombre_usuario": "juan.perez",
        "identidad_abonado": "3001234567",
    }, follow_redirects=True)
    client.post("/configure/opciones", data={"accion": "siguiente", "top_antenas": "", "top_contactos": ""}, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente", "kml_opcional": "on"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#ff00ff"}, follow_redirects=True)
    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)

    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert "Investigador Uno" in html
    assert "juan.perez" in html
    assert "3001234567" in html
    assert "Magenta (alto contraste)" in html
    assert html.count("Incluido") == 3  # HTML, KMZ, Hashes
    assert "Solicitado" in html


def test_resumen_kml_no_solicitado_si_no_se_selecciono_en_3c(client):
    _advance_to_resumen(client)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert "No solicitado" in html


def test_resumen_anterior_regresa_a_preparar_analisis(client):
    _advance_to_resumen(client)
    resp = client.post("/configure/resumen", data={"accion": "anterior"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Paso 5 de 5".encode("utf-8") in resp.data
    assert "Preparar análisis".encode("utf-8") in resp.data


def test_navegar_resumen_anterior_preparar_resumen_conserva_valores(client):
    _advance_to_resumen(client, nombre_modo="manual", output_base_name="Mi Caso Especial", tipo_bitacora="I")

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.output_base_name == "Mi Caso Especial"
    assert case.tipo_bitacora == "I"

    client.post("/configure/resumen", data={"accion": "anterior"}, follow_redirects=True)
    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    assert "Mi Caso Especial" in html
    match = re.search(
        r'<option value="I"\s+selected>',
        re.sub(r"\s+", " ", html),
    )
    assert match is not None

    client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "manual",
        "output_base_name": "Mi Caso Especial", "tipo_bitacora": "I",
    }, follow_redirects=True)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")
    assert "Mi Caso Especial" in html

    case = tz_web_state.get_session(case_id)
    assert case.output_base_name == "Mi Caso Especial"
    assert case.tipo_bitacora == "I"


def _advance_to_resumen_con_mapeo(client, mapeo_form, **opciones_overrides):
    """Como ``_advance_to_resumen``, pero permite un mapeo de columnas
    personalizado (p. ej. omitiendo ``contacto``) en vez del mapeo real
    completo que usa ``advance_to_configure``."""
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=mapeo_form, follow_redirects=True)
    client.post("/mapping/confirm", follow_redirects=True)

    client.post("/configure", data={"accion": "siguiente"}, follow_redirects=True)
    opciones = {"accion": "siguiente", "top_antenas": "", "top_contactos": ""}
    opciones.update(opciones_overrides)
    client.post("/configure/opciones", data=opciones, follow_redirects=True)
    client.post("/configure/productos", data={"accion": "siguiente"}, follow_redirects=True)
    client.post("/configure/color", data={"accion": "siguiente", "color_hex": "#76ff03"}, follow_redirects=True)
    return client.post("/configure/final", data={
        "accion": "siguiente", "nombre_modo": "sugerido", "tipo_bitacora": "",
    }, follow_redirects=True)


def test_resumen_top_contactos_usa_valor_real_de_configuracion(client):
    """El texto "(valor por defecto)" del Resumen debe reflejar el valor
    real de config.json (top_contactos_n), no un "10" fijo en la plantilla
    — evita que Resumen y Resultados muestren números distintos para el
    mismo caso sin ninguna decisión del usuario de por medio."""
    _advance_to_resumen(client)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")

    default_top_contactos = int(get_config().get("html", {}).get("top_contactos_n", 10))
    default_top_antenas = int(get_config().get("html", {}).get("top_antenas_n", 10))
    assert f"{default_top_contactos} (valor por defecto)" in html
    assert f"{default_top_antenas} (valor por defecto)" in html


def test_resumen_contacto_omitido_muestra_no_disponible(client):
    """Si la bitácora no tiene el campo `contacto` mapeado, el Resumen no
    debe insinuar un Top de contactos numérico que nunca se usará."""
    mapeo_sin_contacto = dict(REAL_MAPPING_FORM)
    mapeo_sin_contacto["tipo_contacto"] = "omitido"
    mapeo_sin_contacto.pop("col_contacto", None)

    _advance_to_resumen_con_mapeo(client, mapeo_sin_contacto)
    resp = client.get("/configure/resumen")
    html = resp.data.decode("utf-8")

    assert "No disponible para esta bitácora" in html
    match = re.search(
        r"<dt>Top de contactos</dt>\s*<dd>(.*?)</dd>",
        re.sub(r"\s+", " ", html),
        re.DOTALL,
    )
    assert match is not None
    assert "valor por defecto" not in match.group(1)


def test_tipo_bitacora_persiste_en_preparar_analisis(client):
    _advance_to_3e(client)
    client.post("/configure/final", data={
        "accion": "anterior", "nombre_modo": "sugerido", "tipo_bitacora": "T",
    }, follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.tipo_bitacora == "T"

    resp = client.get("/configure/final")
    html = resp.data.decode("utf-8")
    match = re.search(
        r'<option value="T"\s+selected>',
        re.sub(r"\s+", " ", html),
    )
    assert match is not None


def test_preview_name_refleja_tipo_bitacora_sin_guardarlo_en_sesion(client):
    """El endpoint ligero de 3E reutiliza preview_suggested_case_name() (no
    duplica su lógica en JS) y no persiste el tipo_bitacora recibido — solo
    lo hace el envío real del formulario (configure_final_submit)."""
    _advance_to_3e(client)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    tipo_antes = tz_web_state.get_session(case_id).tipo_bitacora

    resp_auto = client.post("/configure/final/preview-name", data={"tipo_bitacora": ""})
    assert resp_auto.status_code == 200
    nombre_auto = resp_auto.get_json()["suggested_name"]
    # "Automático" deja que el motor decida IMEI/TEL/AUTO según los datos
    # (ver tz_core.ui_utils.prompt_case_identity); solo se descarta aquí que
    # sea el prefijo forzado por "Por teléfono" (comparado más abajo).
    assert nombre_auto is not None

    resp_tel = client.post("/configure/final/preview-name", data={"tipo_bitacora": "T"})
    assert resp_tel.status_code == 200
    nombre_tel = resp_tel.get_json()["suggested_name"]
    assert nombre_tel is not None
    assert nombre_tel.startswith("TEL_")
    assert nombre_tel != nombre_auto

    # No efecto secundario sobre la sesión: tipo_bitacora sigue como estaba.
    case = tz_web_state.get_session(case_id)
    assert case.tipo_bitacora == tipo_antes


def test_preview_name_sin_mapeo_confirmado_responde_400(client):
    resp = client.post("/configure/final/preview-name", data={"tipo_bitacora": "T"})
    assert resp.status_code == 400


def test_cambiar_tipo_no_sobrescribe_nombre_personalizado_al_confirmar(client):
    """Requisito 3 del OBJETIVO 2: una vez que el usuario personalizó el
    nombre (nombre_modo=manual), reenviar la subpantalla con un tipo de
    bitácora distinto no debe recuperar el nombre automático."""
    _advance_to_3e(client)
    client.post("/configure/final", data={
        "accion": "anterior", "nombre_modo": "manual",
        "output_base_name": "Nombre Personalizado", "tipo_bitacora": "",
    }, follow_redirects=True)

    resp = client.post("/configure/final", data={
        "accion": "anterior", "nombre_modo": "manual",
        "output_base_name": "Nombre Personalizado", "tipo_bitacora": "T",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.output_base_name == "Nombre Personalizado"
    assert case.tipo_bitacora == "T"


def test_generar_analisis_inicia_tarea_y_redirige_a_procesamiento(client):
    _advance_to_resumen(client)
    select_output_folder(client)
    resp = client.post("/configure/resumen", data={"accion": "siguiente"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Procesando análisis".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.task_started is True
    assert case.filtro_tiempo is None
    assert case.status in (tz_web_state.STATUS_RUNNING, tz_web_state.STATUS_SUCCESS)

    status = wait_for_terminal_status(client)
    assert status["status"] == "success"


# ---------------------------------------------------------------------------
# Configuración heredada completa (/configure/legacy) — inicio de tarea
# ---------------------------------------------------------------------------


def test_configure_legacy_screen_muestra_carpeta_por_defecto(client):
    advance_to_configure(client)
    resp = client.get("/configure/legacy")
    assert resp.status_code == 200
    assert b"TZ Analyzer" in resp.data  # ruta sugerida contiene el nombre de la carpeta por defecto


def test_configuracion_valida_inicia_tarea_y_redirige_a_procesamiento(client, tmp_path):
    advance_to_configure(client)
    outdir = str(tmp_path / "salida_valida")
    resp = client.post("/configure/legacy", data={
        "tipo_bitacora": "", "output_base_name": "",
        "identidad_alias": "", "identidad_nombre_usuario": "", "identidad_abonado": "",
        "top_antenas": "", "top_contactos": "", "color_hex": "#76ff03",
        "solo_kmz": "on",
        "filtro_tipo": "ninguno",
        "date_order_decision": "1", "duration_unit_decision": "segundos", "qc_bloqueante_decision": "S",
        "carpeta_salida": outdir,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Procesando análisis".encode("utf-8") in resp.data

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = tz_web_state.get_session(case_id)
    assert case.task_started is True
    assert case.status in (tz_web_state.STATUS_RUNNING, tz_web_state.STATUS_SUCCESS)

    status = wait_for_terminal_status(client)
    assert status["status"] == "success"


def test_carpeta_salida_vacia_es_rechazada(client):
    advance_to_configure(client)
    resp = client.post("/configure/legacy", data={"carpeta_salida": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Indique una carpeta de salida".encode("utf-8") in resp.data


def test_top_antenas_no_numerico_es_rechazado(client, tmp_path):
    advance_to_configure(client)
    resp = client.post("/configure/legacy", data={
        "carpeta_salida": str(tmp_path / "out"),
        "top_antenas": "no-es-un-numero",
        "filtro_tipo": "ninguno",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "debe ser un número entero".encode("utf-8") in resp.data


def test_color_invalido_es_rechazado(client, tmp_path):
    advance_to_configure(client)
    resp = client.post("/configure/legacy", data={
        "carpeta_salida": str(tmp_path / "out"),
        "color_hex": "no-es-un-color",
        "filtro_tipo": "ninguno",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "formato #RRGGBB".encode("utf-8") in resp.data


def test_carpeta_salida_no_escribible_es_rechazada(client, tmp_path, monkeypatch):
    advance_to_configure(client)

    def _boom(_path):
        raise OSError("permiso denegado (simulado)")

    monkeypatch.setattr(tz_web_state, "ensure_writable_dir", _boom)
    resp = client.post("/configure/legacy", data={
        "carpeta_salida": str(tmp_path / "sin_permiso"),
        "filtro_tipo": "ninguno",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "No se pudo usar la carpeta de salida".encode("utf-8") in resp.data
