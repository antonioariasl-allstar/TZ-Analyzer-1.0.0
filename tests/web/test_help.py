"""tz_web /help — Manual de Usuario (FASE 4B: reestructuración y reescritura
integral, sobre la base de MICROBLOQUE 6-2).

Cubre: accesibilidad sin caso activo, no interferencia con Session/lifecycle,
presencia y posición de AYUDA en el encabezado, apertura en ventana/pestaña
nombrada estable, ausencia de CDN, y contratos semánticos del contenido
aprobado (índice de 14 secciones, Preparación de la bitácora, Modos 1/2/3
reflejando el flujo real, los 14 campos canónicos, geometría de cobertura
1.5 km / 70° (±35°) coherente con F3.6, distinción inferencia vs. hecho
observado, complementariedad, carpeta de salida con sufijo _02/_03, versión
Beta visible, autoría, uso de IA, y ausencia de la sección de soporte).

Deliberadamente NO se comparan bloques de texto completos byte a byte: las
aserciones son contratos semánticos (presencia/ausencia de fragmentos y de
términos prohibidos) para no volver la prueba frágil ante mejoras de
redacción futuras.
"""
from __future__ import annotations

import pytest

from tz_web import lifecycle, state
from tz_web.app import create_app
from tz_web.field_catalog import CANONICAL_FIELDS, FIELD_LABELS
from tz_web.help_content import HELP_SECTIONS
from tz_version import AUTHOR, BETA_USAGE_NOTICE, VERSION
from tests.web.conftest import REAL_MAPPING_FORM, SHEET_NAME, configure_test_instance_host, upload_real_file

TOKEN = "token-ayuda-prueba-1234567890"


def help_html(client) -> str:
    """Cuerpo de /help con espacios en blanco colapsados: el template envuelve
    líneas dentro de párrafos (indentación/saltos de línea propios del HTML
    fuente) sin que eso cambie el texto que un lector ve — las aserciones de
    contenido no deben depender de en qué columna se cortó una línea."""
    html = client.get("/help").data.decode("utf-8")
    return " ".join(html.split())


@pytest.fixture()
def token_app(tmp_path, monkeypatch):
    """App con ``instance_token`` configurado (como en una ejecución real vía
    el launcher), para poder observar SALIR junto a AYUDA en el encabezado —
    el fixture ``app``/``client`` de conftest.py crea la app SIN token, lo
    que oculta SALIR por diseño (ver tz_web/app.py)."""
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    lifecycle.reset_for_tests()
    application = create_app(instance_token=TOKEN, instance_id="instancia-ayuda")
    application.config.update(TESTING=True)
    configure_test_instance_host(application)
    yield application
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


@pytest.fixture()
def token_client(token_app):
    return token_app.test_client()


# ---------------------------------------------------------------------------
# A/B — accesible sin caso activo, y no toca Session.
# ---------------------------------------------------------------------------


def test_help_accesible_sin_caso_activo(client):
    resp = client.get("/help")
    assert resp.status_code == 200
    assert "Manual de Usuario".encode("utf-8") in resp.data


def test_help_no_modifica_session(client):
    with client.session_transaction() as before:
        assert "case_id" not in before

    client.get("/help")

    with client.session_transaction() as after:
        assert "case_id" not in after


def test_help_no_crea_ni_toca_sesion_de_caso_existente(client):
    """Con un caso ya en curso, visitar /help no debe alterar su estado
    (``updated_at`` no debe avanzar, a diferencia de lo que hace
    ``_current_session`` con ``state.touch``)."""
    client.post("/modo/1")
    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case_before = state.get_session(case_id)
    updated_before = case_before.updated_at

    client.get("/help")

    case_after = state.get_session(case_id)
    assert case_after.updated_at == updated_before


# ---------------------------------------------------------------------------
# C/D/E/F/U — AYUDA presente en portada, menú y pantalla operativa, junto a
# SALIR y sin regresión del resto del encabezado.
# ---------------------------------------------------------------------------


def test_ayuda_presente_en_portada(client):
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert "AYUDA" in html
    assert 'tzAbrirAyuda()' in html


def test_ayuda_presente_en_menu(client):
    resp = client.get("/menu")
    html = resp.data.decode("utf-8")
    assert "AYUDA" in html
    assert "Volver al menú principal" not in html  # menu_screen usa show_nav=False


def test_ayuda_presente_en_pantalla_operativa(client):
    resp = client.post("/modo/1", follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "AYUDA" in html
    assert "Volver al menú principal" in html


def test_ayuda_junto_a_salir_con_instance_token(token_client):
    resp = token_client.get("/menu")
    html = resp.data.decode("utf-8")
    assert "AYUDA" in html
    assert "SALIR" in html
    assert html.index("AYUDA") < html.index("SALIR")


def test_header_y_salir_sin_regresion(token_client):
    resp = token_client.post("/modo/1", follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert html.index("Volver al menú principal") < html.index("AYUDA") < html.index("SALIR")
    assert "tzRequestShutdown()" in html


def test_salir_ausente_sin_instance_token(client):
    """Sin token configurado (app de pruebas normal), SALIR sigue oculto por
    diseño — AYUDA no depende de esa condición y sigue presente."""
    resp = client.get("/menu")
    html = resp.data.decode("utf-8")
    assert "AYUDA" in html
    assert "SALIR" not in html


# ---------------------------------------------------------------------------
# G/H — abre ventana/pestaña independiente con nombre estable reutilizable.
# ---------------------------------------------------------------------------


def test_ayuda_abre_ventana_nombrada_estable(client):
    resp = client.get("/static/js/app.js")
    js = resp.data.decode("utf-8")
    assert 'function tzAbrirAyuda' in js
    assert 'window.open("/help", "tz_analyzer_help")' in js


# ---------------------------------------------------------------------------
# I — el manual no depende de CDN ni de recursos externos.
# ---------------------------------------------------------------------------


def test_manual_no_depende_de_cdn(client):
    html = help_html(client)
    assert "http://" not in html
    assert "https://" not in html
    assert "cdn." not in html.lower()


# ---------------------------------------------------------------------------
# J — el manual no refleja datos de caso ni de sesión.
# ---------------------------------------------------------------------------


def test_manual_no_contiene_datos_de_caso(client):
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)

    with client.session_transaction() as flask_sess:
        case_id = flask_sess["case_id"]
    case = state.get_session(case_id)

    html = help_html(client)
    assert case.original_filename not in html
    assert case_id not in html
    assert SHEET_NAME not in html


# ---------------------------------------------------------------------------
# Índice — 14 secciones aprobadas en FASE 4B, en el orden fijado por
# HELP_SECTIONS (única fuente de verdad para índice + anclas).
# ---------------------------------------------------------------------------


def test_indice_contiene_las_secciones_aprobadas(client):
    html = help_html(client)
    for anchor, label in HELP_SECTIONS:
        assert f'href="#{anchor}"' in html
        assert label in html


def test_indice_tiene_las_14_secciones_esperadas():
    assert len(HELP_SECTIONS) == 14
    anchors = [anchor for anchor, _ in HELP_SECTIONS]
    assert len(anchors) == len(set(anchors)), "anclas del índice no deben repetirse"


# ---------------------------------------------------------------------------
# Modos 1/2/3 — reflejan el flujo real (mapeo, revisión, confirmación,
# configuración; dos pantallas de filtro; solo lo que Modo 3 genera hoy).
# ---------------------------------------------------------------------------


def test_modos_1_2_3_documentados(client):
    html = help_html(client)
    assert "Modo 1 — Análisis completo" in html
    assert "Modo 2 — Análisis con filtro temporal" in html
    assert "Modo 3 — Mapeo manual" in html


def test_modo1_documenta_revision_del_mapeo_y_confirmacion(client):
    modo1_block = help_html(client).split('id="modo-1"', 1)[1].split("</section>", 1)[0]
    assert "Revisión del mapeo" in modo1_block
    assert "Confirmación" in modo1_block
    assert "Configuración" in modo1_block
    assert "Procesamiento" in modo1_block
    assert "Resultados" in modo1_block


def test_modo2_refleja_dos_pantallas_de_filtro(client):
    modo2_block = help_html(client).split('id="modo-2"', 1)[1].split("</section>", 1)[0]
    assert "dos pantallas" in modo2_block
    assert "Día específico" in modo2_block
    assert "Rango de fechas" in modo2_block
    assert "Rango de horas" in modo2_block
    assert "Rango de horas en un día específico" in modo2_block


def test_modo2_no_indica_que_enter_avanza(client):
    html = help_html(client)
    assert "Enter" not in html


def test_modo3_no_incluye_informe_html_entre_sus_productos(client):
    modo3_block = help_html(client).split('id="modo-3"', 1)[1].split("</section>", 1)[0]
    assert "Informe HTML" not in modo3_block
    assert "KMZ" in modo3_block


def test_modo3_no_describe_funciones_futuras(client):
    """Solo lo que Modo 3 ofrece hoy: nada de importar Excel, exportar tabla
    estructurada, reabrir análisis, acumular revisiones ni sincronización."""
    modo3_block = help_html(client).split('id="modo-3"', 1)[1].split("</section>", 1)[0].lower()
    for termino_futuro in (
        "importar excel",
        "exportar tabla",
        "reabrir análisis",
        "sincroniz",
    ):
        assert termino_futuro not in modo3_block


# ---------------------------------------------------------------------------
# Preparación de la bitácora — nueva sección (P2), y campos canónicos (P2).
# ---------------------------------------------------------------------------


def test_existe_preparacion_de_la_bitacora(client):
    html = help_html(client)
    assert "Preparación de la bitácora" in html
    assert "Número analizado" in html
    assert "consolidad" in html.lower()


def test_aparecen_los_14_campos_canonicos(client):
    html = help_html(client)
    assert len(CANONICAL_FIELDS) == 14
    campos_block = html.split('id="campos"', 1)[1].split("</section>", 1)[0]
    for campo in CANONICAL_FIELDS:
        assert FIELD_LABELS[campo] in campos_block


# ---------------------------------------------------------------------------
# Interpretación de antenas, cobertura y azimut — geometría F3.6 (P0/P2) y
# distinción inferencia vs. hecho observado (P0).
# ---------------------------------------------------------------------------


def test_explica_radio_grafico_1_5_km(client):
    html = help_html(client)
    assert "1.5 km" in html


def test_explica_apertura_70_grados_35(client):
    html = help_html(client)
    assert "70°" in html
    assert "±35°" in html


def test_distingue_ubicacion_exacta_del_dispositivo(client):
    html = help_html(client)
    assert "no representan la ubicación exacta del dispositivo" in html


def test_distingue_distancia_entre_antenas_de_desplazamiento_demostrado(client):
    html = help_html(client)
    assert (
        "distancia entre dos antenas no demuestra" in html
        and "desplazamiento físico del dispositivo" in html
    )


def test_explica_sitio_inferido(client):
    html = help_html(client)
    cobertura_block = html.split('id="cobertura"', 1)[1].split("</section>", 1)[0]
    assert "sitio inferido" in cobertura_block.lower()


# ---------------------------------------------------------------------------
# Carpeta de salida y productos generados — selección explícita y sufijo
# _02/_03 (P1/P2), sin lenguaje de "en desarrollo".
# ---------------------------------------------------------------------------


def test_carpeta_salida_refleja_seleccion_explicita(client):
    html = help_html(client)
    assert "Seleccionar carpeta…" in html


def test_carpeta_salida_documenta_sufijo(client):
    html = help_html(client)
    assert "_02" in html
    assert "_03" in html


def test_carpeta_salida_no_dice_que_esta_en_desarrollo(client):
    html = help_html(client)
    assert "en desarrollo" not in html.lower()
    assert "ONEDIR" not in html


# ---------------------------------------------------------------------------
# Complementariedad con otras herramientas (P2).
# ---------------------------------------------------------------------------


def test_complementariedad_menciona_i2_excel_google_earth(client):
    html = help_html(client)
    complementariedad_block = html.split('id="complementariedad"', 1)[1].split(
        "</section>", 1
    )[0]
    assert "i2 Analyst's Notebook" in complementariedad_block
    assert "Excel" in complementariedad_block
    assert "Google Earth" in complementariedad_block
    assert "sustituye" not in complementariedad_block.lower()


# ---------------------------------------------------------------------------
# Uso local / privacidad — sin promesa falsa de aislamiento absoluto.
# ---------------------------------------------------------------------------


def test_funcionamiento_local_sin_promesa_de_aislamiento_absoluto(client):
    html = help_html(client)
    assert "TZ Analyzer se ejecuta localmente" in html
    assert "El análisis puede ejecutarse sin conexión a Internet" in html
    assert "nunca se conecta a Internet" not in html


# ---------------------------------------------------------------------------
# Versión Beta, autoría y uso de IA (P1/P3) — sin lenguaje que debilite el
# producto, y sin sección de soporte (P1).
# ---------------------------------------------------------------------------


def test_version_visible_es_1_0_0_beta_1(client):
    html = help_html(client)
    assert VERSION == "1.0.0-beta.1"
    assert VERSION in html


def test_no_aparece_pendiente_de_confirmacion(client):
    html = help_html(client)
    assert "pendiente de confirmación" not in html.lower()
    assert "experimental" not in html.lower()
    assert "puede presentar errores" not in html.lower()


def test_no_existe_seccion_soporte_y_sugerencias(client):
    html = help_html(client)
    assert "Soporte y sugerencias" not in html
    assert "será indicado en la versión de distribución" not in html
    assert "Exportar diagnóstico Beta" not in html


def test_ayuda_contiene_atribucion_del_desarrollo(client):
    html = help_html(client)
    assert f"Concepción, desarrollo y metodología: {AUTHOR}." in html
    assert "programador" not in html.lower()


def test_ayuda_distingue_ia_de_desarrollo_de_ia_en_analisis(client):
    html = help_html(client)
    assert "asistencia técnica al proceso de desarrollo" in html
    assert "TZ Analyzer no incorpora inteligencia artificial" in html
    assert (
        "procedimientos técnicos y criterios metodológicos previamente definidos"
        in html
    )


def test_ayuda_no_menciona_marcas_de_ia_concretas(client):
    html = help_html(client)
    for marca in ("ChatGPT", "Claude", "Codex"):
        assert marca not in html


def test_ayuda_incluye_aviso_beta_canonico(client):
    html = help_html(client)
    assert BETA_USAGE_NOTICE in html


# ---------------------------------------------------------------------------
# Limpieza editorial ya decidida en fases previas: no debe reaparecer.
# ---------------------------------------------------------------------------


def test_ayuda_no_menciona_limite_de_200_mb(client):
    html = help_html(client)
    assert "200 MB" not in html


def test_ayuda_declara_el_ejecutable_definitivo(client):
    html = help_html(client)
    assert '"TZ Analyzer.exe"' in html
    assert "tz_launcher.exe" not in html.lower()
    assert "tzanalyzer.exe" not in html.lower()


def test_antes_de_comenzar_no_habla_en_futuro_del_empaquetado(client):
    html = help_html(client)
    assert "cuando tz analyzer se distribuya" not in html.lower()
    assert (
        '<strong>Para iniciar TZ Analyzer:</strong> ejecute únicamente '
        '"TZ Analyzer.exe" desde la carpeta de la aplicación.' in html
    )


# ---------------------------------------------------------------------------
# Tono — vocabulario interno prohibido fuera del manual para usuarios.
# ---------------------------------------------------------------------------


def test_ayuda_sin_terminos_internos_prohibidos(client):
    html = help_html(client).lower()
    for termino in (
        "no garantiza",
        "podría fallar",
        "runtime",
        "snapshot",
        "fallback",
        "frozen",
        "pipeline",
        "backend",
        "frontend",
    ):
        assert termino not in html
