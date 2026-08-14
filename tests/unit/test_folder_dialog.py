"""Contrato padre/hijo y control de procesos del selector MB7-A1/A2."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tz_web import lifecycle
from tz_core.folder_dialog import (
    DEFAULT_TIMEOUT_SECONDS,
    DialogChildRegistry,
    FolderDialogBusyError,
    FolderDialogInterruptedError,
    FolderDialogTimeoutError,
    FolderDialogUnavailableError,
    pick_folder,
)
from tz_folder_dialog_ipc import (
    INTERNAL_MODE_ARGUMENT,
    PROTOCOL_SCHEMA,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_UNAVAILABLE,
    read_request,
    request_path,
    result_path,
    write_request,
    write_result,
)

REQUEST_ID = "ab" * 32


class _FinishedProcess:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.calls: list[object] = []

    def poll(self):
        self.calls.append("poll")
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append(("wait", timeout))
        return self.returncode

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")


class _BlockingProcess:
    def __init__(
        self,
        *,
        ignore_terminate: bool = False,
        ignore_kill: bool = False,
    ):
        self.returncode = None
        self.ignore_terminate = ignore_terminate
        self.ignore_kill = ignore_kill
        self.calls: list[object] = []
        self.wait_entered = threading.Event()
        self.finished = threading.Event()

    def poll(self):
        self.calls.append("poll")
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append(("wait", timeout))
        self.wait_entered.set()
        if self.finished.wait(timeout=timeout):
            return int(self.returncode)
        raise subprocess.TimeoutExpired(cmd="dialog-child", timeout=timeout)

    def terminate(self):
        self.calls.append("terminate")
        if not self.ignore_terminate:
            self.returncode = -15
            self.finished.set()

    def kill(self):
        self.calls.append("kill")
        if not self.ignore_kill:
            self.returncode = -9
            self.finished.set()

    def finish_naturally(self, returncode: int = 0):
        self.returncode = returncode
        self.finished.set()


class _UnpollableProcess(_BlockingProcess):
    def poll(self):
        self.calls.append("poll-error")
        raise OSError("estado del proceso no disponible")


def _existing_launcher(tmp_path: Path) -> Path:
    script = tmp_path / "tz_launcher.py"
    script.write_text("# stub\n", encoding="utf-8")
    return script


def _publishing_popen(
    dialog_dir: Path,
    *,
    status: str,
    selected_path: str | None = None,
    error_code: str | None = None,
    returncode: int = 0,
):
    calls = []

    def _popen(cmd, **kwargs):
        current_id = cmd[-1]
        calls.append((cmd, kwargs, read_request(current_id, dialog_dir=dialog_dir)))
        write_result(
            current_id,
            status=status,
            path=selected_path,
            error_code=error_code,
            dialog_dir=dialog_dir,
        )
        return _FinishedProcess(returncode)

    _popen.calls = calls
    return _popen


def _pick_kwargs(tmp_path: Path, **overrides):
    values = {
        "launcher_script": _existing_launcher(tmp_path),
        "dialog_dir": tmp_path / "ipc",
        "is_frozen_fn": lambda: False,
        "request_id_factory": lambda: REQUEST_ID,
        "child_registry": DialogChildRegistry(terminate_grace=0.01, kill_grace=0.01),
    }
    values.update(overrides)
    return values


def test_desarrollo_reinvoca_launcher_y_transporta_unicode_solo_por_json(tmp_path):
    dialog_dir = tmp_path / "ipc"
    launcher = _existing_launcher(tmp_path)
    selected = tmp_path / "Caso con espacios - Pe\u00f1a - \u6f22\u5b57 - \U0001f680"
    selected.mkdir()
    factory = _publishing_popen(
        dialog_dir,
        status=STATUS_SUCCESS,
        selected_path=str(selected),
    )

    result = pick_folder(
        initial_dir="C:\\Inicial con espacios\\Ni\u00f1ez \u6f22\u5b57",
        title="Elegir carpeta de Jos\u00e9 \U0001f680",
        launcher_script=launcher,
        dialog_dir=dialog_dir,
        popen_factory=factory,
        is_frozen_fn=lambda: False,
        request_id_factory=lambda: REQUEST_ID,
        child_registry=DialogChildRegistry(),
    )

    assert result == str(selected)
    cmd, kwargs, request = factory.calls[0]
    assert cmd == [sys.executable, str(launcher), INTERNAL_MODE_ARGUMENT, REQUEST_ID]
    assert request["initial_dir"] == "C:\\Inicial con espacios\\Ni\u00f1ez \u6f22\u5b57"
    assert request["title"] == "Elegir carpeta de Jos\u00e9 \U0001f680"
    assert request["initial_dir"] not in cmd
    assert request["title"] not in cmd
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["shell"] is False


def test_modo_frozen_reinvoca_mismo_exe_sin_archivo_py(tmp_path):
    dialog_dir = tmp_path / "ipc"
    selected = tmp_path / "Salida frozen"
    selected.mkdir()
    factory = _publishing_popen(
        dialog_dir,
        status=STATUS_SUCCESS,
        selected_path=str(selected),
    )

    result = pick_folder(
        launcher_script=tmp_path / "no-debe-usarse.py",
        dialog_dir=dialog_dir,
        popen_factory=factory,
        is_frozen_fn=lambda: True,
        request_id_factory=lambda: REQUEST_ID,
        child_registry=DialogChildRegistry(),
    )

    assert result == str(selected)
    assert factory.calls[0][0] == [sys.executable, INTERNAL_MODE_ARGUMENT, REQUEST_ID]
    assert not any(str(arg).lower().endswith(".py") for arg in factory.calls[0][0][1:])


def test_cancelacion_estructurada_devuelve_none(tmp_path):
    dialog_dir = tmp_path / "ipc"
    factory = _publishing_popen(dialog_dir, status=STATUS_CANCELLED, returncode=3)
    assert pick_folder(**_pick_kwargs(tmp_path, popen_factory=factory)) is None


@pytest.mark.parametrize(
    ("status", "error_code", "returncode", "message"),
    [
        (STATUS_UNAVAILABLE, "TK_UNAVAILABLE", 4, "entorno grafico"),
        (STATUS_ERROR, "UNEXPECTED_DIALOG_ERROR", 1, "error tecnico"),
    ],
)
def test_estados_tecnicos_producen_error_controlado(
    tmp_path, status, error_code, returncode, message
):
    factory = _publishing_popen(
        tmp_path / "ipc",
        status=status,
        error_code=error_code,
        returncode=returncode,
    )
    with pytest.raises(FolderDialogUnavailableError, match=message):
        pick_folder(**_pick_kwargs(tmp_path, popen_factory=factory))


def test_json_valido_tiene_prioridad_sobre_exit_code_secundario(tmp_path):
    selected = tmp_path / "Seleccion valida"
    selected.mkdir()
    factory = _publishing_popen(
        tmp_path / "ipc",
        status=STATUS_SUCCESS,
        selected_path=str(selected),
        returncode=1,
    )
    assert pick_folder(**_pick_kwargs(tmp_path, popen_factory=factory)) == str(selected)


def test_resultado_malformado_es_rechazado_y_eliminado(tmp_path):
    dialog_dir = tmp_path / "ipc"

    def _popen(cmd, **_kwargs):
        result_path(cmd[-1], dialog_dir=dialog_dir).write_text(
            '{"status":"SUCCESS","path":42}', encoding="utf-8"
        )
        return _FinishedProcess(0)

    with pytest.raises(FolderDialogUnavailableError, match="estructurado valido"):
        pick_folder(**_pick_kwargs(tmp_path, popen_factory=_popen))
    assert not request_path(REQUEST_ID, dialog_dir=dialog_dir).exists()
    assert not result_path(REQUEST_ID, dialog_dir=dialog_dir).exists()


def test_resultado_con_request_id_distinto_es_rechazado(tmp_path):
    dialog_dir = tmp_path / "ipc"

    def _popen(cmd, **_kwargs):
        result_path(cmd[-1], dialog_dir=dialog_dir).write_text(
            json.dumps(
                {
                    "schema": PROTOCOL_SCHEMA,
                    "request_id": "cd" * 32,
                    "status": STATUS_CANCELLED,
                    "path": None,
                    "error_code": None,
                }
            ),
            encoding="utf-8",
        )
        return _FinishedProcess(3)

    with pytest.raises(FolderDialogUnavailableError, match="estructurado valido"):
        pick_folder(**_pick_kwargs(tmp_path, popen_factory=_popen))


def test_ruta_publicada_debe_existir_y_ser_directorio(tmp_path):
    factory = _publishing_popen(
        tmp_path / "ipc",
        status=STATUS_SUCCESS,
        selected_path=str(tmp_path / "ya-no-existe"),
    )
    with pytest.raises(FolderDialogUnavailableError, match="ya no existe"):
        pick_folder(**_pick_kwargs(tmp_path, popen_factory=factory))


def test_intercambio_y_registry_se_limpian_despues_de_consumir(tmp_path):
    selected = tmp_path / "salida"
    selected.mkdir()
    registry = DialogChildRegistry()
    factory = _publishing_popen(
        tmp_path / "ipc", status=STATUS_SUCCESS, selected_path=str(selected)
    )
    pick_folder(**_pick_kwargs(tmp_path, popen_factory=factory, child_registry=registry))
    assert registry.snapshot() == ()
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()
    assert not result_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()


def test_timeout_escala_terminate_wait_kill_wait_y_no_deja_hijo(tmp_path):
    process = _BlockingProcess(ignore_terminate=True)
    registry = DialogChildRegistry(terminate_grace=0.01, kill_grace=0.01)
    clock = iter([0.0, DEFAULT_TIMEOUT_SECONDS + 1.0])

    with pytest.raises(FolderDialogTimeoutError, match="600 segundos"):
        pick_folder(
            **_pick_kwargs(
                tmp_path,
                popen_factory=lambda _cmd, **_kwargs: process,
                child_registry=registry,
                monotonic_fn=lambda: next(clock),
            )
        )

    significant = [call for call in process.calls if call != "poll"]
    assert significant == [
        "terminate",
        ("wait", 0.01),
        "kill",
        ("wait", 0.01),
    ]
    assert process.poll() is not None
    assert registry.snapshot() == ()
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()


def test_shutdown_durante_selector_termina_hijo_registry_e_ipc(tmp_path):
    process = _BlockingProcess()
    registry = DialogChildRegistry(terminate_grace=0.1, kill_grace=0.1)
    outcome: dict[str, object] = {}
    lifecycle.reset_for_tests()

    def _target():
        try:
            pick_folder(
                **_pick_kwargs(
                    tmp_path,
                    popen_factory=lambda _cmd, **_kwargs: process,
                    child_registry=registry,
                    cancel_requested=lambda: (
                        lifecycle.get_state() != lifecycle.RUNNING
                    ),
                    poll_interval=0.01,
                )
            )
        except Exception as exc:  # noqa: BLE001 - se afirma abajo
            outcome["exception"] = exc

    thread = threading.Thread(target=_target)
    thread.start()
    try:
        assert process.wait_entered.wait(timeout=1)
        assert registry.has_live_child() is True
        assert lifecycle.request_shutdown(reason="test-selector-open") == (
            lifecycle.SHUTTING_DOWN
        )
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(outcome.get("exception"), FolderDialogInterruptedError)
        assert "terminate" in process.calls
        assert registry.snapshot() == ()
        assert not request_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()
        assert not result_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()
    finally:
        lifecycle.reset_for_tests()


def test_hijo_ya_terminado_no_se_termina_ni_mata(tmp_path):
    registry = DialogChildRegistry()
    process = _FinishedProcess(0)
    handle = registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )
    assert registry.terminate(handle) is True
    assert "terminate" not in process.calls
    assert "kill" not in process.calls
    assert registry.snapshot() == ()


def test_shutdown_registry_termina_hijo_limpia_ipc_y_cierra_spawn_gate(tmp_path):
    registry = DialogChildRegistry(terminate_grace=0.01, kill_grace=0.01)
    process = _BlockingProcess()
    write_request(
        REQUEST_ID,
        title=None,
        initial_dir=None,
        dialog_dir=tmp_path,
    )
    handle = registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )

    registry.terminate_all()

    assert process.poll() is not None
    assert registry.snapshot() == ()
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path).exists()
    popen_calls = []
    with pytest.raises(RuntimeError, match="cerrando"):
        registry.spawn(
            lambda *_args, **_kwargs: popen_calls.append(1),
            ["fake"],
            request_id=REQUEST_ID,
            dialog_dir=tmp_path,
            popen_kwargs={},
        )
    assert popen_calls == []
    assert handle not in registry.snapshot()


def test_shutdown_registry_con_hijo_ya_muerto_solo_limpia(tmp_path):
    registry = DialogChildRegistry()
    process = _FinishedProcess(0)
    write_request(
        REQUEST_ID,
        title=None,
        initial_dir=None,
        dialog_dir=tmp_path,
    )
    registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )

    registry.terminate_all()

    assert "terminate" not in process.calls
    assert "kill" not in process.calls
    assert registry.snapshot() == ()
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path).exists()


def test_kill_no_confirmado_conserva_registry_ipc_y_rechaza_otro_hijo(tmp_path):
    registry = DialogChildRegistry(terminate_grace=0.001, kill_grace=0.001)
    process = _BlockingProcess(ignore_terminate=True, ignore_kill=True)
    write_request(
        REQUEST_ID,
        title=None,
        initial_dir=None,
        dialog_dir=tmp_path,
    )
    handle = registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )

    assert registry.terminate_all() == (handle,)
    assert registry.snapshot() == (handle,)
    assert request_path(REQUEST_ID, dialog_dir=tmp_path).exists()
    assert process.poll() is None
    with pytest.raises(RuntimeError, match="cerrando"):
        registry.spawn(
            lambda *_args, **_kwargs: pytest.fail("no debe crear otro hijo"),
            ["fake-2"],
            request_id="cd" * 32,
            dialog_dir=tmp_path,
            popen_kwargs={},
        )

    process.finish_naturally(0)
    assert registry.terminate(handle) is True
    assert registry.snapshot() == ()


def test_picker_rechaza_registry_ocupado_sin_spawn_y_limpia_su_ipc(tmp_path):
    registry = DialogChildRegistry()
    process = _BlockingProcess(ignore_terminate=True, ignore_kill=True)
    first_id = "cd" * 32
    registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=first_id,
        dialog_dir=tmp_path / "ipc",
        popen_kwargs={},
    )
    popen_calls = []

    with pytest.raises(FolderDialogBusyError, match="Ya existe"):
        pick_folder(
            **_pick_kwargs(
                tmp_path,
                child_registry=registry,
                popen_factory=lambda *_args, **_kwargs: popen_calls.append(1),
            )
        )

    assert popen_calls == []
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()
    assert registry.has_live_child() is True
    process.finish_naturally(0)
    assert registry.terminate(registry.snapshot()[0]) is True


def test_poll_fallido_es_muerte_no_confirmada_y_shutdown_no_propaga(tmp_path):
    registry = DialogChildRegistry(terminate_grace=0.001, kill_grace=0.001)
    process = _UnpollableProcess(ignore_terminate=True, ignore_kill=True)
    write_request(
        REQUEST_ID,
        title=None,
        initial_dir=None,
        dialog_dir=tmp_path,
    )
    handle = registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )

    assert registry.has_live_child() is True
    assert registry.terminate_all() == (handle,)
    assert registry.snapshot() == (handle,)
    assert request_path(REQUEST_ID, dialog_dir=tmp_path).exists()

    # Al poder esperar finalmente al hijo, el registro vuelve a limpiarse
    # aunque poll siga sin estar disponible.
    process.finish_naturally(0)
    assert registry.terminate(handle) is True
    assert registry.snapshot() == ()


def test_carrera_fin_natural_vs_shutdown_no_deja_registry(tmp_path):
    registry = DialogChildRegistry(terminate_grace=0.1, kill_grace=0.1)
    process = _BlockingProcess()
    handle = registry.spawn(
        lambda _cmd, **_kwargs: process,
        ["fake"],
        request_id=REQUEST_ID,
        dialog_dir=tmp_path,
        popen_kwargs={},
    )
    results: dict[str, object] = {}

    def _natural_wait():
        results["wait"] = registry.wait(handle, timeout=1.0)

    def _shutdown():
        results["shutdown"] = registry.terminate(handle)

    waiter = threading.Thread(target=_natural_wait)
    terminator = threading.Thread(target=_shutdown)
    waiter.start()
    assert process.wait_entered.wait(timeout=1)
    terminator.start()
    process.finish_naturally(0)
    waiter.join(timeout=2)
    terminator.join(timeout=2)

    assert not waiter.is_alive() and not terminator.is_alive()
    assert results == {"wait": 0, "shutdown": True}
    assert "terminate" not in process.calls
    assert "kill" not in process.calls
    assert registry.snapshot() == ()


def test_fallo_al_crear_popen_es_controlado_y_limpia(tmp_path):
    def _popen(_cmd, **_kwargs):
        raise OSError("ruta privada que no debe escapar")

    with pytest.raises(FolderDialogUnavailableError, match="No se pudo iniciar") as excinfo:
        pick_folder(**_pick_kwargs(tmp_path, popen_factory=_popen))
    assert "ruta privada" not in str(excinfo.value)
    assert not request_path(REQUEST_ID, dialog_dir=tmp_path / "ipc").exists()


def test_launcher_dev_ausente_no_invoca_popen(tmp_path):
    calls = []

    def _popen(*args, **kwargs):
        calls.append((args, kwargs))
        return _FinishedProcess()

    with pytest.raises(FolderDialogUnavailableError, match="entrypoint"):
        pick_folder(
            **_pick_kwargs(
                tmp_path,
                launcher_script=tmp_path / "ausente.py",
                popen_factory=_popen,
            )
        )
    assert calls == []


def test_request_id_con_traversal_es_rechazado_sin_popen(tmp_path):
    calls = []

    def _popen(*args, **kwargs):
        calls.append((args, kwargs))
        return _FinishedProcess()

    with pytest.raises(FolderDialogUnavailableError, match="intercambio tecnico"):
        pick_folder(
            **_pick_kwargs(
                tmp_path,
                is_frozen_fn=lambda: True,
                request_id_factory=lambda: "../resultado",
                popen_factory=_popen,
            )
        )
    assert calls == []
