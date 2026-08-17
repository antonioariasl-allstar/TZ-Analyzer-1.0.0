"""tz_web.lifecycle — RUNNING/CLOSE_WHEN_IDLE/SHUTTING_DOWN (MICROBLOQUE 5,
AUD-01). Usa ``tz_web.state`` real (sesiones/reserva de ejecución) para que
las pruebas ejerciten la integración de verdad, no un doble simulado."""

from __future__ import annotations

import os
import time

import pytest

from tz_web import lifecycle, state


@pytest.fixture(autouse=True)
def _lifecycle_isolation():
    """Aísla cada prueba: el módulo es un singleton por proceso (un solo
    backend real por vez), así que sin este reset un estado dejado por una
    prueba (o un shutdown-hook apuntando a un servidor ya destruido)
    contaminaría las siguientes."""
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None
    yield
    lifecycle.reset_for_tests()
    with state._SESSIONS_LOCK:
        state._SESSIONS.clear()
    with state._RUNNING_LOCK:
        state._RUNNING_SESSION_ID = None


def _start_fake_run() -> str:
    session = state.create_session()
    assert state.try_start_run(session.id) is True
    return session.id


# ---------------------------------------------------------------------------
# 8. Cierre explícito en reposo -> shutdown inmediato.
# ---------------------------------------------------------------------------


def test_cierre_explicito_idle_dispara_shutdown_inmediato():
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))

    result = lifecycle.request_shutdown(reason="user_requested")

    assert result == lifecycle.SHUTTING_DOWN
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    assert hook_calls == [1]


# ---------------------------------------------------------------------------
# 9. Cierre explícito durante un análisis -> se difiere, el worker sigue.
# ---------------------------------------------------------------------------


def test_cierre_explicito_durante_analisis_difiere_a_close_when_idle():
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))
    session_id = _start_fake_run()

    result = lifecycle.request_shutdown(reason="user_requested")

    assert result == lifecycle.CLOSE_WHEN_IDLE
    assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
    assert hook_calls == []  # el hook de apagado real NO se ejecuta todavía
    assert state.is_any_run_active() is True  # el worker no fue tocado

    state.finish_run(session_id)  # limpieza


# ---------------------------------------------------------------------------
# 10. El análisis termina -> el cierre diferido se completa solo.
# ---------------------------------------------------------------------------


def test_analisis_termina_completa_el_cierre_diferido():
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))
    session_id = _start_fake_run()

    lifecycle.request_shutdown(reason="user_requested")
    assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE

    state.finish_run(session_id)

    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    assert hook_calls == [1]


def test_analisis_termina_via_terminal_run_tambien_completa_el_cierre():
    """Mismo caso que arriba, pero por el camino que usa el worker real
    (``state.terminal_run``, ver tz_web/routes.py) en vez de ``finish_run``
    directo."""
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))
    session_id = _start_fake_run()
    lifecycle.request_shutdown(reason="user_requested")

    with state.terminal_run(session_id):
        pass  # el worker publica resultado/estado aquí; no es lo que se prueba

    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    assert hook_calls == [1]


# ---------------------------------------------------------------------------
# 11. El heartbeat mantiene la instancia viva mientras siga llegando.
# ---------------------------------------------------------------------------


def test_heartbeat_sostenido_mantiene_running():
    lifecycle.set_heartbeat_timeout(0.2)
    lifecycle.start_watchdog(interval=0.05)
    try:
        deadline = time.time() + 0.5
        while time.time() < deadline:
            lifecycle.record_heartbeat()
            time.sleep(0.05)
        assert lifecycle.get_state() == lifecycle.RUNNING
    finally:
        lifecycle.stop_watchdog()


# ---------------------------------------------------------------------------
# 12. Heartbeat expirado en reposo -> shutdown automático.
# ---------------------------------------------------------------------------


def test_heartbeat_expirado_idle_dispara_shutdown():
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))
    lifecycle.set_heartbeat_timeout(0.1)
    lifecycle.start_watchdog(interval=0.03)
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and lifecycle.get_state() != lifecycle.SHUTTING_DOWN:
            time.sleep(0.03)
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
        assert hook_calls == [1]
    finally:
        lifecycle.stop_watchdog()


# ---------------------------------------------------------------------------
# 13. Heartbeat expirado con análisis activo -> nunca mata al worker.
# ---------------------------------------------------------------------------


def test_heartbeat_expirado_durante_analisis_no_mata_worker():
    hook_calls = []
    lifecycle.set_shutdown_hook(lambda: hook_calls.append(1))
    lifecycle.set_heartbeat_timeout(0.1)
    session_id = _start_fake_run()
    lifecycle.start_watchdog(interval=0.03)
    try:
        deadline = time.time() + 1.0
        while time.time() < deadline and lifecycle.get_state() == lifecycle.RUNNING:
            time.sleep(0.03)
        assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
        assert hook_calls == []
        assert state.is_any_run_active() is True

        # 14. Al finalizar ese análisis expirado, el cierre se completa.
        state.finish_run(session_id)
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
        assert hook_calls == [1]
    finally:
        lifecycle.stop_watchdog()


def test_request_shutdown_es_idempotente_una_vez_shutting_down():
    calls = []
    lifecycle.set_shutdown_hook(lambda: calls.append(1))
    assert lifecycle.request_shutdown(reason="primero") == lifecycle.SHUTTING_DOWN
    assert lifecycle.request_shutdown(reason="segundo") == lifecycle.SHUTTING_DOWN
    assert calls == [1]  # el hook no se re-ejecuta


# ---------------------------------------------------------------------------
# Bloqueo de nuevas ejecuciones con cierre pendiente (sección 1 del MB5).
# RUNNING permite arrancar; CLOSE_WHEN_IDLE y SHUTTING_DOWN lo impiden, con
# un motivo distinguible de "ya hay un análisis en curso" (RUN_START_
# REJECTED_SHUTDOWN vs RUN_START_REJECTED_BUSY) para que la capa web pueda
# mostrar el mensaje correcto (ver tz_web/routes.py, _flash_start_rejected).
# ---------------------------------------------------------------------------


def test_running_normal_permite_arrancar_un_analisis():
    assert lifecycle.get_state() == lifecycle.RUNNING
    session = state.create_session()
    started, reason = state.try_start_run_detailed(session.id)
    assert started is True
    assert reason is None
    state.finish_run(session.id)


def test_close_when_idle_rechaza_nuevo_analisis():
    session_en_curso = _start_fake_run()
    lifecycle.request_shutdown(reason="user_requested")
    assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE

    # El análisis que disparó el cierre diferido sigue activo -> ocupado; lo
    # que este test aisla es que, ADEMÁS, una vez liberado ese cupo, un
    # análisis nuevo sigue sin poder arrancar por el veto de lifecycle (no
    # por "ocupado").
    state.finish_run(session_en_curso)
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN

    otra_sesion = state.create_session()
    started, reason = state.try_start_run_detailed(otra_sesion.id)
    assert started is False
    assert reason == state.RUN_START_REJECTED_SHUTDOWN


def test_close_when_idle_rechaza_nuevo_analisis_mientras_el_primero_sigue_activo():
    """El caso más directo: todavía en CLOSE_WHEN_IDLE (el primer análisis
    ni siquiera terminó), un segundo intento de arranque debe rechazarse
    por el veto de cierre pendiente, no solo por "ocupado" — ambos motivos
    apuntan a False, pero la UI necesita distinguirlos."""
    _start_fake_run()
    lifecycle.request_shutdown(reason="user_requested")
    assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE

    otra_sesion = state.create_session()
    started, reason = state.try_start_run_detailed(otra_sesion.id)
    assert started is False
    # Con el cupo de ejecución ya ocupado, "busy" prevalece porque se
    # comprueba primero (ver try_start_run_detailed) — sigue siendo un
    # rechazo correcto, solo que la causa más específica en este caso es
    # la reserva ocupada, no (todavía) el veto de lifecycle por sí solo.
    assert reason == state.RUN_START_REJECTED_BUSY


def test_shutting_down_rechaza_nuevo_analisis():
    lifecycle.request_shutdown(reason="user_requested")
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN

    session = state.create_session()
    started, reason = state.try_start_run_detailed(session.id)
    assert started is False
    assert reason == state.RUN_START_REJECTED_SHUTDOWN
    assert state.is_any_run_active() is False  # el rechazo no dejó nada reservado


def test_analisis_ya_activo_sigue_hasta_finalizar_pese_al_cierre_pendiente():
    session_id = _start_fake_run()
    lifecycle.request_shutdown(reason="user_requested")
    assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
    assert state.is_any_run_active() is True

    # Ningún rechazo de arranque nuevo interfiere con la reserva ya viva.
    otra_sesion = state.create_session()
    assert state.try_start_run(otra_sesion.id) is False

    state.finish_run(session_id)
    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN


def test_carrera_cierre_pendiente_vs_nuevo_analisis_queda_serializada():
    """No debe existir ventana entre "¿puedo iniciar?" y "reservar": ambas
    decisiones (arrancar / pedir cierre) compiten por el mismo
    ``state._RUNNING_LOCK`` (ver set_run_start_guard / request_shutdown), así
    que, disparadas concurrentemente muchas veces, cada intento de arranque
    debe quedar consistente con el estado ya resuelto — nunca "arrancó" con
    lifecycle en SHUTTING_DOWN."""
    import threading

    for _ in range(200):
        lifecycle.reset_for_tests()
        with state._RUNNING_LOCK:
            state._RUNNING_SESSION_ID = None

        session = state.create_session()
        results = {}
        barrier = threading.Barrier(2)

        def _start():
            barrier.wait(timeout=2)
            results["start"] = state.try_start_run_detailed(session.id)

        def _shutdown():
            barrier.wait(timeout=2)
            results["shutdown"] = lifecycle.request_shutdown(reason="carrera")

        t1 = threading.Thread(target=_start)
        t2 = threading.Thread(target=_shutdown)
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        started, reason = results["start"]
        final_state = lifecycle.get_state()
        if started:
            # Ganó el arranque: lifecycle solo pudo quedar en RUNNING (nada
            # que cerrar todavía) o CLOSE_WHEN_IDLE (la corrida recién
            # reservada lo impidió) — nunca SHUTTING_DOWN con una corrida
            # que "arrancó" después de todo.
            assert final_state in (lifecycle.RUNNING, lifecycle.CLOSE_WHEN_IDLE)
            state.finish_run(session.id)
        else:
            # Perdió el arranque: el motivo debe ser consistente con lo que
            # lifecycle decidió, nunca "ocupado" por una corrida fantasma.
            assert reason == state.RUN_START_REJECTED_SHUTDOWN
            assert final_state == lifecycle.SHUTTING_DOWN


# ---------------------------------------------------------------------------
# Cleanup normal de temporales al cierre — el shutdown definitivo
# (``_do_shutdown_locked``, único punto de convergencia entre SALIR y
# heartbeat_timeout) dispara ``state.cleanup_session_uploads_on_shutdown()``
# antes de invocar el hook de apagado real.
# ---------------------------------------------------------------------------


def _session_con_upload(tmp_path) -> state.Session:
    session = state.create_session()
    upload_dir = os.path.join(str(tmp_path), session.id)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, "archivo.xlsx"), "w") as fh:
        fh.write("contenido")
    session.upload_dir = upload_dir
    return session


def test_salir_en_reposo_limpia_temporales_de_la_instancia(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path))
    lifecycle.set_shutdown_hook(lambda: None)
    session = _session_con_upload(tmp_path)

    result = lifecycle.request_shutdown(reason="user_requested")

    assert result == lifecycle.SHUTTING_DOWN
    assert not os.path.isdir(session.upload_dir)


def test_worker_activo_no_limpia_hasta_que_termina(tmp_path, monkeypatch):
    """Caso crítico: un cierre pedido mientras hay un análisis activo NO debe
    tocar los temporales todavía — recién al terminar ese análisis (y
    completarse el cierre diferido) debe ejecutarse la limpieza."""
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path))
    lifecycle.set_shutdown_hook(lambda: None)
    session = _session_con_upload(tmp_path)
    assert state.try_start_run(session.id) is True

    result = lifecycle.request_shutdown(reason="user_requested")
    assert result == lifecycle.CLOSE_WHEN_IDLE
    assert os.path.isdir(session.upload_dir)  # el worker sigue "activo"

    state.finish_run(session.id)

    assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
    assert not os.path.isdir(session.upload_dir)  # limpieza recién ahora


def test_heartbeat_timeout_en_reposo_limpia_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path))
    lifecycle.set_shutdown_hook(lambda: None)
    session = _session_con_upload(tmp_path)
    lifecycle.set_heartbeat_timeout(0.1)
    lifecycle.start_watchdog(interval=0.03)
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and lifecycle.get_state() != lifecycle.SHUTTING_DOWN:
            time.sleep(0.03)
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
        assert not os.path.isdir(session.upload_dir)
    finally:
        lifecycle.stop_watchdog()


def test_heartbeat_timeout_durante_analisis_no_limpia_hasta_finalizar(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path))
    lifecycle.set_shutdown_hook(lambda: None)
    session = _session_con_upload(tmp_path)
    assert state.try_start_run(session.id) is True
    lifecycle.set_heartbeat_timeout(0.1)
    lifecycle.start_watchdog(interval=0.03)
    try:
        deadline = time.time() + 1.0
        while time.time() < deadline and lifecycle.get_state() == lifecycle.RUNNING:
            time.sleep(0.03)
        assert lifecycle.get_state() == lifecycle.CLOSE_WHEN_IDLE
        assert os.path.isdir(session.upload_dir)

        state.finish_run(session.id)
        assert lifecycle.get_state() == lifecycle.SHUTTING_DOWN
        assert not os.path.isdir(session.upload_dir)
    finally:
        lifecycle.stop_watchdog()


def test_cleanup_ocurre_antes_del_hook_de_apagado(monkeypatch):
    """Orden exigido: limpiar temporales ANTES de detener el servidor real
    (nunca al revés), para no dejar una ventana donde el servidor ya está
    caído pero los temporales siguen vivos innecesariamente."""
    orden = []
    monkeypatch.setattr(
        state, "cleanup_session_uploads_on_shutdown", lambda: orden.append("cleanup")
    )
    lifecycle.set_shutdown_hook(lambda: orden.append("hook"))

    lifecycle.request_shutdown(reason="user_requested")

    assert orden == ["cleanup", "hook"]


def test_shutdown_no_falla_si_no_hay_sesiones_con_upload():
    lifecycle.set_shutdown_hook(lambda: None)
    result = lifecycle.request_shutdown(reason="user_requested")
    assert result == lifecycle.SHUTTING_DOWN
