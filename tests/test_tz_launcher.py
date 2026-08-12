"""tz_launcher — orquestación del arranque/cierre (MICROBLOQUE 5).

``tz_launcher.py`` vive en la raíz del repo (mismo nivel que ``run.py``,
que es el entrypoint del CLI y no tiene relación con este); ``pytest.ini``
fija ``pythonpath = .`` así que se importa igual que cualquier paquete.
"""

from __future__ import annotations

import threading
import time
import urllib.request

import pytest

import tz_launcher
from tz_web import instance, lifecycle, state


@pytest.fixture(autouse=True)
def _isolation():
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


def _metadata(**overrides) -> instance.InstanceMetadata:
    base = dict(
        schema_version=instance.INSTANCE_SCHEMA_VERSION,
        instance_id="inst-x",
        pid=1234,
        port=54000,
        token="tok",
        created_at=1.0,
        app_version="1.1",
        launcher_version=instance.LAUNCHER_VERSION,
    )
    base.update(overrides)
    return instance.InstanceMetadata(**base)


# ---------------------------------------------------------------------------
# _open_browser: un fallo nunca debe propagar (sección 20 del encargo).
# ---------------------------------------------------------------------------


def test_open_browser_exitoso(monkeypatch):
    monkeypatch.setattr(tz_launcher.webbrowser, "open", lambda url: True)
    assert tz_launcher._open_browser("http://127.0.0.1:1/") is True


def test_open_browser_fallo_no_propaga(monkeypatch):
    def _boom(url):
        raise RuntimeError("sin navegador disponible")

    monkeypatch.setattr(tz_launcher.webbrowser, "open", _boom)
    assert tz_launcher._open_browser("http://127.0.0.1:1/") is False


# ---------------------------------------------------------------------------
# Reutilizar instancia existente.
# ---------------------------------------------------------------------------


def test_run_existing_instance_abre_navegador_y_devuelve_0(monkeypatch):
    calls = []
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: calls.append(url) or True)
    rc = tz_launcher._run_existing_instance(_metadata(port=54321))
    assert rc == 0
    assert calls == ["http://127.0.0.1:54321/"]


def test_run_existing_instance_navegador_falla_devuelve_1(monkeypatch):
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: False)
    rc = tz_launcher._run_existing_instance(_metadata())
    assert rc == 1


# ---------------------------------------------------------------------------
# Arranque bloqueado (lock ocupado por algo que no valida como TZ Analyzer).
# ---------------------------------------------------------------------------


def test_run_blocked_devuelve_1():
    assert tz_launcher._run_blocked("stale_or_foreign") == 1


# ---------------------------------------------------------------------------
# main(): despacha según la acción del plan, sin duplicar la decisión.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action,expected_fn",
    [("reuse", "_run_existing_instance"), ("blocked", "_run_blocked"), ("start", "_run_new_instance")],
)
def test_main_despacha_segun_la_accion_del_plan(monkeypatch, action, expected_fn):
    calls = []
    monkeypatch.setattr(tz_launcher.instance, "get_run_dir", lambda: "run-dir-falso")
    monkeypatch.setattr(tz_launcher.instance, "InstanceLock", lambda run_dir: "lock-falso")

    meta = _metadata() if action != "start" else None
    plan = tz_launcher.instance.StartupPlan(action=action, metadata=meta, reason="motivo" if action == "blocked" else None)
    monkeypatch.setattr(tz_launcher.instance, "resolve_startup_plan", lambda lock: plan)

    for name in ("_run_existing_instance", "_run_blocked", "_run_new_instance"):
        monkeypatch.setattr(
            tz_launcher, name, lambda *a, __name=name, **kw: calls.append(__name) or 0
        )

    tz_launcher.main()
    assert calls == [expected_fn]


# ---------------------------------------------------------------------------
# 21. Fallo al iniciar el servidor WSGI limpia el lock (no deja la
# instancia "fantasma" bloqueada para el siguiente lanzamiento).
# ---------------------------------------------------------------------------


def test_run_new_instance_fallo_wsgi_libera_el_lock(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    class _BoomServer:
        def __init__(self, *_a, **_kw):
            pass

        def start(self):
            raise tz_launcher.ServerStartError("boom")

    monkeypatch.setattr(tz_launcher, "ManagedServer", _BoomServer)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kw: object())

    rc = tz_launcher._run_new_instance(lock)
    assert rc == 1

    # El lock quedó realmente libre: un lanzamiento nuevo puede tomarlo.
    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


# ---------------------------------------------------------------------------
# Un hilo de Waitress que nunca confirma su propio cierre (p. ej. la carrera
# de Windows en su trigger interno, ver docs/LAUNCHER_LIFECYCLE.md) no debe
# colgar el launcher para siempre: hay un plazo acotado y luego se continúa.
# ---------------------------------------------------------------------------


def test_run_new_instance_no_cuelga_si_el_hilo_de_waitress_nunca_confirma(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setattr(tz_launcher, "_WAITRESS_JOIN_TIMEOUT_SECONDS", 0.3)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: True)

    class _WedgedServer:
        """Simula el hilo de Waitress atascado: arranca y responde
        readiness normalmente, pero nunca confirma su propio cierre."""

        def __init__(self, app, host, port=0):
            self._port = 0

        def start(self):
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                self._port = probe.getsockname()[1]

        @property
        def port(self):
            return self._port

        def wait_until_ready(self, token, **kwargs):
            return True

        def stop(self):
            pass  # a propósito: nunca hace nada

        def is_running(self):
            return True  # a propósito: nunca reporta haber terminado

        def wait_for_shutdown(self, timeout=None):
            time.sleep(timeout or 0)  # simula la espera acotada real

    monkeypatch.setattr(tz_launcher, "ManagedServer", _WedgedServer)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kw: object())

    # El plazo acotado solo debe aplicar una vez que un cierre YA fue
    # solicitado (ver el bug de autocierre corregido en este microbloque:
    # antes, el launcher se autoterminaba a los pocos segundos aunque nadie
    # pidiera cerrar nada — cubierto por otro test). Pedirlo de entrada es
    # seguro y determinista: lifecycle.request_shutdown() es idempotente,
    # así que no importa que se adelante al registro del hook dentro de
    # _run_new_instance (el hook, un no-op aquí, es irrelevante para lo que
    # este test verifica: el comportamiento del launcher una vez SHUTTING_
    # DOWN, no quién dispara el cierre).
    lifecycle.request_shutdown(reason="test_no_cuelga")

    start = time.time()
    rc = tz_launcher._run_new_instance(lock)
    elapsed = time.time() - start

    assert rc == 0
    assert elapsed < 3.0, "el launcher esperó mucho más que el plazo acotado configurado"

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True, "el lock debe liberarse igual, aunque el hilo quedara colgado"
    verifier.release()


# ---------------------------------------------------------------------------
# Regresión: sin ningún cierre pedido, el launcher NO debe autoterminarse.
#
# Bug encontrado en el smoke manual de este microbloque: _run_new_instance
# esperaba con un plazo acotado (_WAITRESS_JOIN_TIMEOUT_SECONDS) de forma
# INCONDICIONAL justo después de abrir el navegador, tratando ese plazo como
# si fuera el tiempo de vida del proceso en vez de una red de seguridad para
# DESPUÉS de que alguien pidiera cerrar. En producción esto hacía que el
# backend muriera solo, liberando el lock, a los pocos segundos de abrir —
# con el navegador del usuario todavía apuntando a un servidor ya muerto.
# ---------------------------------------------------------------------------


def test_run_new_instance_permanece_vivo_sin_cierre_pedido(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    # Deliberadamente muy corto: si el bug de autocierre siguiera presente,
    # el launcher ya habría terminado bastante antes del join de abajo.
    monkeypatch.setattr(tz_launcher, "_WAITRESS_JOIN_TIMEOUT_SECONDS", 0.2)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    opened_urls = []
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: opened_urls.append(url) or True)

    result = {}

    def _target():
        result["rc"] = tz_launcher._run_new_instance(lock)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    while time.time() < deadline and not opened_urls:
        time.sleep(0.05)
    assert opened_urls, "el servidor nunca quedó listo (el navegador nunca se abrió)"

    thread.join(timeout=1.5)
    assert thread.is_alive(), (
        "el launcher terminó solo sin que nadie pidiera cerrar nada "
        "(regresión del bug de autocierre a los pocos segundos de arrancar)"
    )
    assert lifecycle.get_state() == lifecycle.RUNNING
    assert state.is_any_run_active() is False

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is False, "el lock no debería quedar libre: el backend sigue activo"

    # Limpieza: pedir el cierre real para no dejar el hilo/servidor vivos
    # más allá de este test.
    lifecycle.request_shutdown(reason="test_cleanup")
    thread.join(timeout=5)
    assert not thread.is_alive(), "el launcher no terminó tras el cierre real"
    assert result["rc"] == 0

    verifier2 = instance.InstanceLock(run_dir)
    assert verifier2.try_acquire() is True, "el lock no quedó libre tras el cierre real"
    verifier2.release()


# ---------------------------------------------------------------------------
# Ciclo completo real: arranca, confirma readiness, se cierra por
# /internal/shutdown y libera el lock — el equivalente automatizado del
# "Caso 1" de prueba manual (sección O del encargo).
# ---------------------------------------------------------------------------


def test_run_new_instance_ciclo_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    opened_urls = []
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: opened_urls.append(url) or True)

    result = {}

    def _target():
        result["rc"] = tz_launcher._run_new_instance(lock)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    while time.time() < deadline and not opened_urls:
        time.sleep(0.05)
    assert opened_urls, "el servidor nunca quedó listo (el navegador nunca se abrió)"

    metadata = instance.InstanceLock(run_dir).read_metadata()
    assert metadata is not None
    assert f"http://127.0.0.1:{metadata.port}/" == opened_urls[0]

    request = urllib.request.Request(
        f"http://127.0.0.1:{metadata.port}/internal/shutdown",
        data=b"",
        headers={"X-TZ-Token": metadata.token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        assert response.status == 200

    thread.join(timeout=5)
    assert not thread.is_alive(), "_run_new_instance no terminó tras el shutdown"
    assert result["rc"] == 0

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True, "el lock no quedó libre tras el cierre limpio"
    verifier.release()


# ---------------------------------------------------------------------------
# Token de instancia: 64 caracteres hex / 256 bits vía secrets.token_hex(32)
# (ver _generate_instance_token), no uuid.uuid4() como secreto.
# ---------------------------------------------------------------------------


def test_generate_instance_token_longitud_64_y_solo_hex():
    token = tz_launcher._generate_instance_token()
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)


def test_generate_instance_token_usa_secrets_token_hex_32():
    """No solo que "parezca" hex de 64: confirma la fuente real (256 bits,
    no los 244 efectivos de dos uuid4 concatenados)."""
    calls = []
    original = tz_launcher.secrets.token_hex

    def _spy(nbytes=None):
        calls.append(nbytes)
        return original(nbytes)

    tz_launcher.secrets.token_hex = _spy
    try:
        token = tz_launcher._generate_instance_token()
    finally:
        tz_launcher.secrets.token_hex = original

    assert calls == [32]
    assert len(token) == 64


def test_generate_instance_token_tokens_independientes_son_distintos():
    tokens = {tz_launcher._generate_instance_token() for _ in range(50)}
    assert len(tokens) == 50


def test_run_new_instance_nunca_registra_el_token_completo(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(state, "UPLOAD_ROOT", str(tmp_path / "uploads3"))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    monkeypatch.setattr(tz_launcher, "_open_browser", lambda url: True)

    result = {}

    def _target():
        with caplog.at_level("DEBUG"):
            result["rc"] = tz_launcher._run_new_instance(lock)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    metadata = None
    while time.time() < deadline and metadata is None:
        metadata = instance.InstanceLock(run_dir).read_metadata()
        if metadata is None:
            time.sleep(0.05)
    assert metadata is not None, "la instancia nunca escribió su metadata"
    token = metadata.token
    assert len(token) == 64

    request = urllib.request.Request(
        f"http://127.0.0.1:{metadata.port}/internal/shutdown",
        data=b"",
        headers={"X-TZ-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        assert response.status == 200

    thread.join(timeout=5)
    assert not thread.is_alive()
    assert result["rc"] == 0

    full_token_appearances = [
        record.getMessage() for record in caplog.records if token in record.getMessage()
    ]
    assert not full_token_appearances, (
        "el token completo apareció en un mensaje de log: " + repr(full_token_appearances)
    )

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()
