"""tz_launcher — orquestación del arranque/cierre (MICROBLOQUE 5).

``tz_launcher.py`` vive en la raíz del repo (mismo nivel que ``run.py``,
que es el entrypoint del CLI y no tiene relación con este); ``pytest.ini``
fija ``pythonpath = .`` así que se importa igual que cualquier paquete.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
import time
import urllib.request
from pathlib import Path

import pytest

import tz_launcher
from tz_folder_dialog_ipc import (
    EXIT_CANCELLED,
    EXIT_ERROR,
    EXIT_NO_GUI,
    EXIT_OK,
    INTERNAL_MODE_ARGUMENT,
)
from tz_web import instance, lifecycle, state


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    # Ninguna prueba de orquestacion debe barrer el LocalAppData real ni
    # terminar hijos que no haya creado. Las pruebas dirigidas de abajo
    # reemplazan estos no-op por spies propios.
    monkeypatch.setattr(tz_launcher, "cleanup_stale_dialog_ipc", lambda: None)
    monkeypatch.setattr(tz_launcher, "shutdown_dialog_children", lambda: None)
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


_VALID_INTERNAL_DIALOG_REQUEST_ID = "ab" * 32


def _run_launcher_internal_mode_isolated(
    *,
    launcher_args: list[str],
    expected_exit_code: int,
    helper_exit_code: int | None,
) -> subprocess.CompletedProcess[str]:
    """Ejecuta ``tz_launcher.py`` como ``__main__`` en un proceso limpio.

    El archivo de pruebas importa el launcher normal durante collection; por
    eso un ``runpy`` en este mismo proceso no podria demostrar que el modo
    interno se despacha antes de cargar ``tz_web``. El hijo instala un helper
    falso y prohibe expresamente esos imports antes de ejecutar el entrypoint.
    """
    launcher_path = Path(tz_launcher.__file__).resolve()
    child_code = textwrap.dedent(
        f"""
        import builtins
        import runpy
        import sys
        import types

        launcher_path = {str(launcher_path)!r}
        launcher_args = {launcher_args!r}
        expected_exit_code = {expected_exit_code!r}
        expected_request_id = {_VALID_INTERNAL_DIALOG_REQUEST_ID!r}
        helper_must_run = {helper_exit_code is not None!r}
        helper_exit_code = {(helper_exit_code if helper_exit_code is not None else 99)!r}
        helper_calls = []
        cleanup_calls = []

        fake_ipc = types.ModuleType("tz_folder_dialog_ipc")
        fake_ipc.EXIT_ERROR = {EXIT_ERROR!r}
        fake_ipc.INTERNAL_MODE_ARGUMENT = {INTERNAL_MODE_ARGUMENT!r}

        def cleanup_stale_dialog_ipc():
            cleanup_calls.append(1)
            raise AssertionError("el hijo interno intento barrer IPC obsoleto")

        fake_ipc.cleanup_stale_dialog_ipc = cleanup_stale_dialog_ipc
        sys.modules["tz_folder_dialog_ipc"] = fake_ipc

        fake_helper = types.ModuleType("tz_folder_dialog_helper")

        def run_internal_folder_dialog(request_id):
            helper_calls.append(request_id)
            if request_id != expected_request_id:
                raise AssertionError(
                    f"ID interno inesperado: {{request_id!r}}"
                )
            return helper_exit_code

        fake_helper.run_internal_folder_dialog = run_internal_folder_dialog
        sys.modules["tz_folder_dialog_helper"] = fake_helper

        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "tz_web" or name.startswith("tz_web."):
                raise AssertionError(f"el modo interno intento importar {{name}}")
            if name == "flask" or name.startswith("flask."):
                raise AssertionError(f"el modo interno intento importar {{name}}")
            if name == "waitress" or name.startswith("waitress."):
                raise AssertionError(f"el modo interno intento importar {{name}}")
            if name == "tz_core.folder_dialog":
                raise AssertionError("el modo interno intento importar el controlador de hijos")
            if not helper_must_run and name == "tz_folder_dialog_helper":
                raise AssertionError("argumentos invalidos intentaron importar el helper")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = guarded_import
        sys.argv = [launcher_path, *launcher_args]
        try:
            try:
                runpy.run_path(launcher_path, run_name="__main__")
            except SystemExit as exc:
                if exc.code != expected_exit_code:
                    raise AssertionError(
                        f"codigo de salida inesperado: {{exc.code!r}}"
                    ) from exc
            else:
                raise AssertionError("el modo interno no termino mediante SystemExit")
        finally:
            builtins.__import__ = real_import

        expected_calls = [expected_request_id] if helper_must_run else []
        if helper_calls != expected_calls:
            raise AssertionError(
                f"llamadas al helper inesperadas: {{helper_calls!r}}"
            )
        if cleanup_calls:
            raise AssertionError(
                f"cleanup IPC inesperado en modo interno: {{cleanup_calls!r}}"
            )
        """
    )
    return subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=str(launcher_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.parametrize(
    "helper_exit_code",
    [EXIT_OK, EXIT_ERROR, EXIT_CANCELLED, EXIT_NO_GUI],
    ids=["ok", "error", "cancelled", "no_gui"],
)
def test_modo_interno_despacha_helper_antes_del_backend(helper_exit_code):
    completed = _run_launcher_internal_mode_isolated(
        launcher_args=[INTERNAL_MODE_ARGUMENT, _VALID_INTERNAL_DIALOG_REQUEST_ID],
        expected_exit_code=helper_exit_code,
        helper_exit_code=helper_exit_code,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "launcher_args",
    [
        [INTERNAL_MODE_ARGUMENT],
        [INTERNAL_MODE_ARGUMENT, _VALID_INTERNAL_DIALOG_REQUEST_ID, "extra"],
    ],
    ids=["sin_id", "argumento_extra"],
)
def test_modo_interno_rechaza_forma_incompleta_o_extra_sin_cargar_backend(launcher_args):
    completed = _run_launcher_internal_mode_isolated(
        launcher_args=launcher_args,
        expected_exit_code=EXIT_ERROR,
        helper_exit_code=None,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


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
# A2: la instancia normal barre IPC antes de construir Flask y siempre
# termina los hijos de dialogo desde su cierre final. El modo interno queda
# cubierto arriba: sale antes de ejecutar cualquiera de estas dos acciones.
# ---------------------------------------------------------------------------


def test_run_new_instance_limpia_ipc_antes_de_create_app_y_hijos_al_cerrar(
    tmp_path, monkeypatch
):
    events = []
    run_dir = tmp_path / "run-a2"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    monkeypatch.setattr(
        tz_launcher,
        "cleanup_stale_dialog_ipc",
        lambda: events.append("cleanup_stale_dialog_ipc"),
    )

    def _create_app(**_kwargs):
        events.append("create_app")
        assert events[0] == "cleanup_stale_dialog_ipc"
        return object()

    monkeypatch.setattr(tz_launcher, "create_app", _create_app)
    monkeypatch.setattr(
        tz_launcher,
        "shutdown_dialog_children",
        lambda: events.append("shutdown_dialog_children"),
    )
    monkeypatch.setattr(
        tz_launcher,
        "_open_browser",
        lambda _url: events.append("open_browser") or True,
    )

    class _ServerQueCierraEnReadiness:
        def __init__(self, _app, host, port=0):
            assert host == tz_launcher.HOST
            assert port == 0
            self._running = True
            self._port = 43123

        @property
        def port(self):
            return self._port

        def start(self):
            events.append("server_start")

        def wait_until_ready(self, _token):
            events.append("server_ready")
            assert lifecycle.request_shutdown(reason="test_a2_cleanup") == lifecycle.SHUTTING_DOWN
            return True

        def stop(self):
            events.append("server_stop")
            self._running = False

        def is_running(self):
            return self._running

        def wait_for_shutdown(self, timeout=None):
            events.append(("wait_for_shutdown", timeout))

    monkeypatch.setattr(tz_launcher, "ManagedServer", _ServerQueCierraEnReadiness)

    assert tz_launcher._run_new_instance(lock) == 0
    assert events.count("cleanup_stale_dialog_ipc") == 1
    assert events.count("shutdown_dialog_children") == 1
    assert events.index("cleanup_stale_dialog_ipc") < events.index("create_app")
    assert events.index("server_stop") < events.index("shutdown_dialog_children")

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


def test_run_new_instance_finally_termina_hijos_aunque_falle_la_espera(
    tmp_path, monkeypatch
):
    run_dir = tmp_path / "run-a2-finally"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True
    shutdown_calls = []

    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kwargs: object())
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda _url: True)
    monkeypatch.setattr(
        tz_launcher,
        "shutdown_dialog_children",
        lambda: shutdown_calls.append(1),
    )

    class _ServerConEsperaRota:
        def __init__(self, _app, host, port=0):
            self._running = True
            self._port = 43124

        @property
        def port(self):
            return self._port

        def start(self):
            pass

        def wait_until_ready(self, _token):
            assert lifecycle.request_shutdown(reason="test_a2_finally") == lifecycle.SHUTTING_DOWN
            return True

        def stop(self):
            self._running = False

        def is_running(self):
            return self._running

        def wait_for_shutdown(self, timeout=None):
            raise RuntimeError("espera rota simulada")

    monkeypatch.setattr(tz_launcher, "ManagedServer", _ServerConEsperaRota)

    with pytest.raises(RuntimeError, match="espera rota simulada"):
        tz_launcher._run_new_instance(lock)

    assert shutdown_calls == [1]
    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


def test_run_new_instance_excepcion_tras_start_antes_del_bucle_limpia_todo(
    tmp_path, monkeypatch
):
    events = []
    run_dir = tmp_path / "run-a2-pre-loop"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    monkeypatch.setattr(
        tz_launcher,
        "create_app",
        lambda **_kwargs: events.append("create_app") or object(),
    )
    monkeypatch.setattr(
        tz_launcher,
        "shutdown_dialog_children",
        lambda: events.append("shutdown_dialog_children"),
    )
    monkeypatch.setattr(
        tz_launcher.lifecycle,
        "start_watchdog",
        lambda: events.append("start_watchdog"),
    )
    monkeypatch.setattr(
        tz_launcher.lifecycle,
        "stop_watchdog",
        lambda: events.append("stop_watchdog"),
    )

    class _ServerReadinessRota:
        def __init__(self, _app, host, port=0):
            self._port = 43125
            self._running = False

        @property
        def port(self):
            return self._port

        def start(self):
            events.append("server_start")
            self._running = True

        def wait_until_ready(self, _token):
            events.append("readiness")
            raise RuntimeError("readiness rota simulada")

        def stop(self):
            events.append("server_stop")
            self._running = False

        def wait_for_shutdown(self, timeout=None):
            events.append(("server_wait", timeout))

        def is_running(self):
            return self._running

    monkeypatch.setattr(tz_launcher, "ManagedServer", _ServerReadinessRota)

    with pytest.raises(RuntimeError, match="readiness rota simulada"):
        tz_launcher._run_new_instance(lock)

    assert events.index("server_start") < events.index("readiness")
    assert events.index("readiness") < events.index("shutdown_dialog_children")
    assert events.index("shutdown_dialog_children") < events.index("stop_watchdog")
    assert events.index("stop_watchdog") < events.index("server_stop")
    assert ("server_wait", tz_launcher._WAITRESS_JOIN_TIMEOUT_SECONDS) in events

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


def test_cleanup_hijos_fallido_no_salta_espera_de_analisis_ni_limpieza_final(
    tmp_path, monkeypatch
):
    events = []
    run_started = threading.Event()
    child_cleanup_attempted = threading.Event()
    run_id = "run-activo-durante-finally-a2"
    run_dir = tmp_path / "run-a2-child-cleanup-error"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    monkeypatch.setattr(tz_launcher, "_SHUTDOWN_WAIT_SAFETY_POLL_SECONDS", 0.01)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kwargs: object())
    monkeypatch.setattr(
        tz_launcher.lifecycle,
        "start_watchdog",
        lambda: events.append("start_watchdog"),
    )
    monkeypatch.setattr(
        tz_launcher.lifecycle,
        "stop_watchdog",
        lambda: events.append("stop_watchdog"),
    )

    def _broken_child_cleanup():
        events.append("shutdown_dialog_children")
        child_cleanup_attempted.set()
        raise RuntimeError("cleanup de hijo roto simulado")

    monkeypatch.setattr(
        tz_launcher,
        "shutdown_dialog_children",
        _broken_child_cleanup,
    )

    class _ServerConRunActivo:
        def __init__(self, _app, host, port=0):
            self._port = 43126
            self._running = False

        @property
        def port(self):
            return self._port

        def start(self):
            events.append("server_start")
            self._running = True

        def wait_until_ready(self, _token):
            assert state.try_start_run(run_id) is True
            run_started.set()
            raise RuntimeError("fallo pre-loop con run activo")

        def stop(self):
            events.append("server_stop")
            self._running = False

        def wait_for_shutdown(self, timeout=None):
            events.append(("server_wait", timeout))

        def is_running(self):
            return self._running

    monkeypatch.setattr(tz_launcher, "ManagedServer", _ServerConRunActivo)

    outcome = {}

    def _target():
        try:
            tz_launcher._run_new_instance(lock)
        except BaseException as exc:  # noqa: BLE001 - se afirma abajo
            outcome["exception"] = exc

    thread = threading.Thread(target=_target, name="test-a2-finally-active-run")
    thread.start()
    try:
        assert run_started.wait(timeout=2)
        assert child_cleanup_attempted.wait(timeout=2)
        assert thread.is_alive() is True
        assert state.is_any_run_active() is True
        assert "stop_watchdog" not in events
        assert "server_stop" not in events

        verifier_during_run = instance.InstanceLock(run_dir)
        assert verifier_during_run.try_acquire() is False

        state.finish_run(run_id)
        thread.join(timeout=3)
    finally:
        if state.is_any_run_active():
            state.finish_run(run_id)
        thread.join(timeout=3)

    assert thread.is_alive() is False
    assert isinstance(outcome.get("exception"), RuntimeError)
    assert str(outcome["exception"]) == "fallo pre-loop con run activo"
    assert events.index("shutdown_dialog_children") < events.index("stop_watchdog")
    assert events.index("stop_watchdog") < events.index("server_stop")
    assert ("server_wait", tz_launcher._WAITRESS_JOIN_TIMEOUT_SECONDS) in events

    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


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

        def stop(self):
            pass

        def wait_for_shutdown(self, timeout=None):
            pass

        def is_running(self):
            return False

    monkeypatch.setattr(tz_launcher, "ManagedServer", _BoomServer)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kw: object())

    rc = tz_launcher._run_new_instance(lock)
    assert rc == 1

    # El lock quedó realmente libre: un lanzamiento nuevo puede tomarlo.
    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


def test_run_new_instance_start_parcial_inesperado_intenta_cleanup_y_preserva_error(
    tmp_path, monkeypatch
):
    events = []
    run_dir = tmp_path / "run-start-parcial"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    class _PartialStartServer:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            events.append("start")
            raise RuntimeError("fallo inesperado tras inicio parcial")

        def stop(self):
            events.append("stop")

        def wait_for_shutdown(self, timeout=None):
            events.append(("wait", timeout))

        def is_running(self):
            return False

    monkeypatch.setattr(tz_launcher, "ManagedServer", _PartialStartServer)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kw: object())

    with pytest.raises(RuntimeError, match="inicio parcial"):
        tz_launcher._run_new_instance(lock)

    assert events == [
        "start",
        "stop",
        ("wait", tz_launcher._WAITRESS_JOIN_TIMEOUT_SECONDS),
    ]
    verifier = instance.InstanceLock(run_dir)
    assert verifier.try_acquire() is True
    verifier.release()


def test_run_new_instance_muerte_inesperada_del_servidor_retorna_error(
    tmp_path, monkeypatch
):
    events = []
    run_dir = tmp_path / "run-server-dead"
    run_dir.mkdir()
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True

    class _DeadServer:
        def __init__(self, *_args, **_kwargs):
            self._port = 43127

        @property
        def port(self):
            return self._port

        def start(self):
            events.append("start")

        def wait_until_ready(self, _token):
            return True

        def stop(self):
            events.append("stop")

        def wait_for_shutdown(self, timeout=None):
            events.append(("wait", timeout))

        def is_running(self):
            return False

    monkeypatch.setattr(tz_launcher, "ManagedServer", _DeadServer)
    monkeypatch.setattr(tz_launcher, "create_app", lambda **_kw: object())
    monkeypatch.setattr(tz_launcher, "_open_browser", lambda _url: True)

    assert tz_launcher._run_new_instance(lock) == 1
    assert lifecycle.get_state() == lifecycle.RUNNING
    assert events == [
        "start",
        "stop",
        ("wait", tz_launcher._WAITRESS_JOIN_TIMEOUT_SECONDS),
    ]
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
