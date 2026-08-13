"""tz_web /help — Manual de Usuario (MICROBLOQUE 6-2).

Cubre: accesibilidad sin caso activo, no interferencia con Session/lifecycle,
presencia y posición de AYUDA en el encabezado, apertura en ventana/pestaña
nombrada estable, ausencia de CDN, y contenido aprobado del manual (índice,
Modos 1/2/3, advertencias, aclaración de IA, revisión por el analista, límite
de OSM offline, carpeta de salida explícita, Modo 3 (archivo de datos +
verificación) y placeholder de versión).
"""
from __future__ import annotations

import pytest

from tz_web import lifecycle, state
from tz_web.app import create_app
from tz_web.help_content import HELP_SECTIONS, HELP_VERSION_LABEL
from tests.web.conftest import REAL_MAPPING_FORM, SHEET_NAME, upload_real_file

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
    # Orden conceptual: Volver al menú | AYUDA | SALIR (aquí sin "volver al
    # menú" porque menu_screen usa show_nav=False; se valida el orden
    # AYUDA -> SALIR, que sí aplican ambos en esta pantalla).
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
# K/L — índice con las secciones aprobadas; Modos 1/2/3 documentados.
# ---------------------------------------------------------------------------


def test_indice_contiene_las_secciones_aprobadas(client):
    html = help_html(client)
    for anchor, label in HELP_SECTIONS:
        assert f'href="#{anchor}"' in html
        assert label in html


def test_modos_1_2_3_documentados(client):
    html = help_html(client)
    assert "Modo 1 — Procesar bitácora completa" in html
    assert "Modo 2 — Procesar bitácora filtrada por tiempo" in html
    assert "Modo 3 — Mapear antenas y ubicaciones manualmente" in html


# ---------------------------------------------------------------------------
# M — advertencia de carpeta ONEDIR presente.
# ---------------------------------------------------------------------------


def test_advertencia_onedir_carpeta_salida_presente(client):
    html = help_html(client)
    assert "PENDIENTE DE CONFIRMAR EN BETA" in html.upper() or "Pendiente de confirmar en Beta" in html
    assert "ONEDIR" in html


# ---------------------------------------------------------------------------
# N/O — aclaración de uso de IA en el desarrollo, y que TZ Analyzer no
# incorpora IA para sus análisis.
# ---------------------------------------------------------------------------


def test_aclaracion_uso_de_ia_en_desarrollo_presente(client):
    html = help_html(client)
    assert "herramientas de inteligencia artificial" in html


def test_aclaracion_no_incorpora_ia_presente(client):
    html = help_html(client)
    assert "TZ Analyzer no incorpora inteligencia artificial" in html


# ---------------------------------------------------------------------------
# P — consideración de revisión por el analista presente.
# ---------------------------------------------------------------------------


def test_consideracion_revision_por_analista_presente(client):
    html = help_html(client)
    assert "deben ser revisados por el analista antes de su utilización" in html


# ---------------------------------------------------------------------------
# Q — offline explica la limitación del mapa base OSM.
# ---------------------------------------------------------------------------


def test_offline_explica_limitacion_osm(client):
    html = help_html(client)
    assert "OpenStreetMap" in html
    assert "puede no visualizarse" in html


# ---------------------------------------------------------------------------
# R — carpeta de salida documentada como selección explícita (refleja MB6-1).
# ---------------------------------------------------------------------------


def test_carpeta_salida_refleja_seleccion_explicita(client):
    html = help_html(client)
    assert "Seleccionar carpeta…" in html
    assert "No existe una salida automática silenciosa" in html


# ---------------------------------------------------------------------------
# S — Modo 3 documenta archivo de datos + archivo de verificación.
# ---------------------------------------------------------------------------


def test_modo3_documenta_archivo_de_datos_y_verificacion(client):
    html = help_html(client)
    assert "Archivo de datos del análisis (Modo 3):" in html
    assert "Archivo de verificación:" in html


# ---------------------------------------------------------------------------
# T — placeholder de versión no inventa una versión final.
# ---------------------------------------------------------------------------


def test_placeholder_de_version_no_inventa_version_final(client):
    html = help_html(client)
    assert HELP_VERSION_LABEL in html
    assert "1.1 Beta" not in html
    assert "1.0.0-beta.1" not in html


# ---------------------------------------------------------------------------
# Fase 2 — identidad visual + AYUDA (editorial).
# ---------------------------------------------------------------------------
# G — definición general usa "antenas y otros puntos de interés" (sin
# "celdas") en la descripción general de la sección "Acerca de".
# ---------------------------------------------------------------------------


def test_definicion_general_usa_antenas_y_otros_puntos_de_interes(client):
    html = help_html(client)
    assert "georreferenciación de antenas y otros puntos de interés" in html


# ---------------------------------------------------------------------------
# H — atribución de concepción/desarrollo/metodología a Omar Arias (Tony
# Zero), no presentado simplemente como "programador".
# ---------------------------------------------------------------------------


def test_ayuda_contiene_atribucion_del_desarrollo(client):
    html = help_html(client)
    assert "Concepción, desarrollo y metodología: Omar Arias (Tony Zero)." in html
    assert "programador" not in html.lower()


# ---------------------------------------------------------------------------
# I/J — distingue IA de desarrollo vs. IA en el análisis, con la fórmula
# aprobada "procedimientos técnicos y criterios metodológicos previamente
# definidos".
# ---------------------------------------------------------------------------


def test_ayuda_distingue_ia_de_desarrollo_de_ia_en_analisis(client):
    html = help_html(client)
    assert "asistencia técnica al proceso de desarrollo" in html
    assert "TZ Analyzer no incorpora inteligencia artificial" in html
    assert (
        "procedimientos técnicos y criterios metodológicos previamente definidos"
        in html
    )


# ---------------------------------------------------------------------------
# K — funcionamiento local descrito sin promesa falsa de aislamiento
# absoluto de Internet (fondo cartográfico OSM opcional).
# ---------------------------------------------------------------------------


def test_funcionamiento_local_sin_promesa_de_aislamiento_absoluto(client):
    html = help_html(client)
    assert (
        "no requiere conexión a Internet para procesar los archivos ni para "
        "realizar sus análisis" in html
    )
    assert "nunca se conecta a Internet" not in html
    assert "fondo cartográfico en línea, pueden estar" in html


# ---------------------------------------------------------------------------
# M — Soporte y sugerencias: sección presente, sin correo/teléfono/URL
# inventados.
# ---------------------------------------------------------------------------


def test_soporte_presente_sin_contacto_inventado(client):
    html = help_html(client)
    assert "Soporte y sugerencias" in html
    assert (
        "El medio de contacto para soporte y sugerencias será indicado en "
        "la versión de distribución." in html
    )
    assert "@" not in html.split('id="soporte"', 1)[1].split("</section>", 1)[0]
    assert "mailto:" not in html
    assert "tel:" not in html
    assert "Exportar diagnóstico Beta" in html
    assert "pendiente de implementación" in html


# ---------------------------------------------------------------------------
# N — Modo 3 descrito correctamente: no se inventa un producto HTML.
# ---------------------------------------------------------------------------


def test_modo3_no_incluye_informe_html_entre_sus_productos(client):
    html = help_html(client)
    modo3_block = html.split('id="modo-3"', 1)[1].split("</details>", 1)[0]
    assert "Informe HTML" not in modo3_block
    assert "KMZ (obligatorio)" in modo3_block
    assert "Archivo de datos del análisis (Modo 3):" in modo3_block
    assert "Archivo de verificación:" in modo3_block


# ---------------------------------------------------------------------------
# Fase 2C — limpieza editorial final de AYUDA: retiro de textos obsoletos de
# "pendiente" ya decididos (nombre del ejecutable, límite de 200 MB) y
# redacción operativa (no futura) de "Antes de comenzar".
# ---------------------------------------------------------------------------


def test_ayuda_no_menciona_limite_de_200_mb(client):
    html = help_html(client)
    assert "200 MB" not in html


def test_ayuda_no_contiene_pendiente_de_nombre_de_ejecutable(client):
    html = help_html(client)
    assert "Pendiente de confirmar en la distribución Beta" not in html
    assert "el nombre definitivo del archivo que iniciará TZ Analyzer" not in html
    assert "Nombre definitivo del archivo ejecutable." not in html


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


def test_antes_de_comenzar_sin_bullets_redundantes_sobre_archivos_internos(client):
    html = help_html(client)
    assert (
        "TZ Analyzer se inicia ejecutando únicamente el archivo principal "
        "indicado dentro de la carpeta de la aplicación." not in html
    )
    assert "No deben ejecutarse archivos internos para iniciar el programa." not in html
