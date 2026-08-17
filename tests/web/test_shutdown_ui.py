"""Overlay terminal de cierre ("SALIR") — contrato de plantilla y JS.

Sin runner JS en el proyecto (mismo enfoque que
tests/web/test_form_keyboard_contract.py): estas pruebas verifican
estructura HTML y presencia/orden de la lógica en el código fuente de
tz_web/static/js/app.js. El comportamiento del endpoint real (cierre
inmediato, CLOSE_WHEN_IDLE, token, ausencia de fuga del token) ya está
cubierto por tests/web/test_internal_routes.py — no se duplica aquí. La
validación de comportamiento real en navegador es manual (fuera de pytest).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_HTML = (ROOT / "tz_web" / "templates" / "base.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "tz_web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
APP_CSS = (ROOT / "tz_web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
ROUTES_PY = (ROOT / "tz_web" / "routes.py").read_text(encoding="utf-8")
INTERNAL_ROUTES_PY = (ROOT / "tz_web" / "internal_routes.py").read_text(encoding="utf-8")


def _overlay_block() -> str:
    start = BASE_HTML.index('<div id="tz-shutdown-overlay"')
    end = BASE_HTML.index("{% endif %}", start)
    return BASE_HTML[start:end]


def _function_body(source: str, name: str) -> str:
    """Extrae el cuerpo de ``function name() { ... }`` contando llaves —
    suficiente para JS sin llaves dentro de strings/regex en este archivo."""
    marker = f"function {name}("
    start = source.index(marker)
    brace_start = source.index("{", start)
    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : index + 1]
    raise AssertionError(f"no se encontró el cierre de function {name}()")


# ---------------------------------------------------------------------------
# A. Estructura HTML: overlay pre-renderizado, oculto, dos estados, textos
# exactos, sin controles operativos dentro.
# ---------------------------------------------------------------------------


def test_overlay_existe_oculto_por_defecto():
    block = _overlay_block()
    assert 'id="tz-shutdown-overlay"' in block
    assert re.search(r'<div id="tz-shutdown-overlay"[^>]*\bhidden\b', block)


def test_overlay_tiene_los_dos_estados_ocultos_por_defecto():
    block = _overlay_block()
    assert re.search(r'<div id="tz-shutdown-closing"[^>]*class="tz-shutdown-state"[^>]*>', block)
    assert re.search(r'<div id="tz-shutdown-closed"[^>]*\bhidden\b', block)


def test_overlay_closing_tiene_mensaje_principal_y_detalle_condicional_oculto():
    block = _overlay_block()
    assert "Cerrando TZ Analyzer" in block
    detail_match = re.search(
        r'<p id="tz-shutdown-closing-detail"[^>]*>Cerrando al finalizar el análisis en curso',
        block,
    )
    assert detail_match
    assert "hidden" in block[detail_match.start() : detail_match.end() + 20]


def test_overlay_closed_tiene_el_texto_terminal_exacto():
    block = _overlay_block()
    assert "TZ Analyzer se ha cerrado." in block
    assert "Para realizar un nuevo análisis, ejecute nuevamente TZ Analyzer." in block
    assert "Puede cerrar esta pestaña." in block


def test_overlay_no_contiene_controles_operativos():
    block = _overlay_block()
    assert "<button" not in block
    assert "<a " not in block
    assert "<form" not in block
    assert "<input" not in block
    assert "onclick=" not in block


def test_overlay_solo_se_renderiza_cuando_hay_token_de_instancia():
    # El overlay depende del mismo guard que el botón SALIR: sin token de
    # instancia, no hay nada que solicitar cierre a /internal/*.
    start = BASE_HTML.index('id="tz-btn-exit"')
    overlay_start = BASE_HTML.index('id="tz-shutdown-overlay"')
    guard_before_button = BASE_HTML.rindex("{% if tz_instance_token %}", 0, start)
    guard_before_overlay = BASE_HTML.rindex("{% if tz_instance_token %}", 0, overlay_start)
    assert guard_before_button != -1
    assert guard_before_overlay != -1


def test_overlay_css_lo_cubre_completamente_y_por_encima_del_resto():
    assert ".tz-shutdown-overlay" in APP_CSS
    block = APP_CSS[APP_CSS.index(".tz-shutdown-overlay {") :]
    block = block[: block.index("}")]
    assert "position: fixed" in block
    assert "inset: 0" in block
    assert re.search(r"z-index:\s*\d+", block)


# ---------------------------------------------------------------------------
# 19/26. Sin nuevas rutas terminales; sin window.close().
# ---------------------------------------------------------------------------


def test_no_se_agregan_rutas_terminales_nuevas():
    for forbidden in ("/closed", "/shutdown-complete", "/goodbye"):
        assert forbidden not in ROUTES_PY
        assert forbidden not in INTERNAL_ROUTES_PY


def test_no_se_usa_window_close():
    assert "window.close(" not in APP_JS


def test_shutdown_endpoint_no_cambio_de_contrato():
    # El endpoint ya distinguía SHUTTING_DOWN de CLOSE_WHEN_IDLE en
    # lifecycle_state (ver tests/web/test_internal_routes.py); esta mejora
    # UX reutiliza ese campo sin tocar internal_routes.py.
    assert "def shutdown():" in INTERNAL_ROUTES_PY
    assert '"lifecycle_state": resulting_state' in INTERNAL_ROUTES_PY


# ---------------------------------------------------------------------------
# F/13. Doble click: el botón se deshabilita ANTES del fetch, dentro de la
# misma función síncrona (nunca tras la respuesta).
# ---------------------------------------------------------------------------


def test_boton_salir_se_deshabilita_antes_del_fetch():
    body = _function_body(APP_JS, "tzRequestShutdown")
    disable_index = body.index("btn.disabled = true")
    fetch_index = body.index('fetch("/internal/shutdown"')
    assert disable_index < fetch_index


# ---------------------------------------------------------------------------
# 12. El overlay CLOSING solo se muestra tras confirmar la aceptación del
# POST — nunca antes de la respuesta.
# ---------------------------------------------------------------------------


def test_overlay_closing_se_muestra_solo_tras_respuesta_exitosa():
    body = _function_body(APP_JS, "tzRequestShutdown")
    fetch_index = body.index('fetch("/internal/shutdown"')
    show_index = body.index('tzShowShutdownOverlay("closing"')
    assert fetch_index < show_index
    # tzShowShutdownOverlay debe quedar dentro del segundo .then() (tras
    # json()), no en el primer .then() ni fuera de la cadena.
    first_then_index = body.index(".then(function (resp)")
    second_then_index = body.index(".then(function (data)")
    assert first_then_index < second_then_index < show_index


# ---------------------------------------------------------------------------
# D/12. Fallo del POST: shutdown_requested no se activa, el botón se
# rehabilita, no se muestra overlay.
# ---------------------------------------------------------------------------


def test_fallo_del_post_rehabilita_boton_y_no_activa_shutdown_requested():
    body = _function_body(APP_JS, "tzRequestShutdown")
    catch_start = body.index(".catch(function ()")
    catch_body = body[catch_start:]
    assert "btn.disabled = false" in catch_body
    assert "tzShutdownRequested = true" not in catch_body
    assert "tzShowShutdownOverlay" not in catch_body


def test_shutdown_requested_solo_se_activa_en_la_rama_exitosa():
    body = _function_body(APP_JS, "tzRequestShutdown")
    then_data_start = body.index(".then(function (data)")
    catch_start = body.index(".catch(function ()")
    success_branch = body[then_data_start:catch_start]
    assert "tzShutdownRequested = true" in success_branch


# ---------------------------------------------------------------------------
# H/17. Heartbeat: se detiene una vez aceptado el cierre, no se reescribe
# el sistema completo (sigue existiendo tzStartHeartbeat con su intervalo).
# ---------------------------------------------------------------------------


def test_heartbeat_se_detiene_al_aceptar_el_cierre():
    body = _function_body(APP_JS, "tzRequestShutdown")
    then_data_start = body.index(".then(function (data)")
    catch_start = body.index(".catch(function ()")
    success_branch = body[then_data_start:catch_start]
    assert "tzStopHeartbeat()" in success_branch


def test_tz_stop_heartbeat_limpia_el_intervalo():
    body = _function_body(APP_JS, "tzStopHeartbeat")
    assert "window.clearInterval(tzHeartbeatIntervalId)" in body


def test_heartbeat_sigue_usando_un_solo_intervalo_no_reescrito():
    assert "TZ_HEARTBEAT_INTERVAL_MS = 60000" in APP_JS
    body = _function_body(APP_JS, "tzStartHeartbeat")
    assert "tzHeartbeatIntervalId = window.setInterval(beat, TZ_HEARTBEAT_INTERVAL_MS)" in body


# ---------------------------------------------------------------------------
# 9/G. Polling de /internal/health separado del heartbeat, a 1s, con token.
# ---------------------------------------------------------------------------


def test_polling_health_usa_un_segundo_y_ruta_propia():
    assert "TZ_HEALTH_POLL_INTERVAL_MS = 1000" in APP_JS
    body = _function_body(APP_JS, "tzPollShutdownHealth")
    assert '"/internal/health"' in body
    assert '"X-TZ-Token": token' in body


def test_polling_health_es_una_funcion_distinta_del_heartbeat():
    poll_body = _function_body(APP_JS, "tzPollShutdownHealth")
    assert "/internal/heartbeat" not in poll_body


# ---------------------------------------------------------------------------
# E/11. Falso positivo crítico: la detección de cierre solo puede disparar
# con shutdown_requested === true. Un fallo de health sin cierre pedido no
# debe poder marcar "cerrado".
# ---------------------------------------------------------------------------


def test_poll_health_exige_shutdown_requested_antes_de_marcar_cerrado():
    body = _function_body(APP_JS, "tzPollShutdownHealth")
    guard_index = body.index("if (!tzShutdownRequested")
    mark_index = body.index("tzMarkShutdownClosed()")
    assert guard_index < mark_index
    # El guard debe estar antes de cualquier llamada de red o de marcado.
    fetch_index = body.index('fetch("/internal/health"')
    assert guard_index < fetch_index


# ---------------------------------------------------------------------------
# I. Race worker/SALIR: el polling sigue vivo hasta que health deja de
# responder, sin condición adicional que lo detenga antes.
# ---------------------------------------------------------------------------


def test_stop_polling_solo_lo_dispara_marcar_cerrado_o_frenar_explicito():
    mark_body = _function_body(APP_JS, "tzMarkShutdownClosed")
    assert "tzStopShutdownHealthPolling()" in mark_body


# ---------------------------------------------------------------------------
# J/16. visibilitychange: con shutdown_requested true, al volver visible se
# fuerza un chequeo inmediato.
# ---------------------------------------------------------------------------


def test_visibilitychange_dispara_chequeo_inmediato_si_shutdown_requested():
    body = _function_body(APP_JS, "tzInstallShutdownWatchers")
    assert 'addEventListener("visibilitychange"' in body
    assert "tzShutdownRequested" in body
    assert "tzPollShutdownHealth()" in body


def test_shutdown_watchers_se_instalan_al_cargar_la_pagina():
    assert "tzInstallShutdownWatchers();" in BASE_HTML


# ---------------------------------------------------------------------------
# 15/L. Cleanup MB8-A: no se toca cleanup_session_uploads_on_shutdown; el
# hook de apagado real solo se dispara vía lifecycle, no desde el frontend.
# ---------------------------------------------------------------------------


def test_no_se_toca_cleanup_mb8a():
    assert "cleanup_session_uploads_on_shutdown" not in APP_JS
    assert "cleanup_session_uploads_on_shutdown" not in INTERNAL_ROUTES_PY
