"""tz_core.folder_dialog.pick_folder — selector nativo en subprocess aislado
(MICROBLOQUE 6).

Nunca abre un diálogo real: ``run_subprocess`` se inyecta siempre como un
doble que simula el contrato de salida de ``tz_folder_dialog_helper.py``
(ver ese módulo para el contrato de códigos de salida), para poder probar
cada rama sin depender de un entorno gráfico.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from tz_core.folder_dialog import (
    DEFAULT_TIMEOUT_SECONDS,
    FolderDialogUnavailableError,
    pick_folder,
)


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_runner(returncode: int, stdout: str = "", stderr: str = ""):
    calls = []

    def _run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _FakeCompletedProcess(returncode, stdout, stderr)

    _run.calls = calls
    return _run


def _existing_script(tmp_path):
    script = tmp_path / "tz_folder_dialog_helper.py"
    script.write_text("# stub\n", encoding="utf-8")
    return script


def test_seleccion_exitosa_devuelve_ruta(tmp_path):
    runner = _fake_runner(0, stdout="C:\\Users\\alguien\\Documents\\Caso 1\n")
    resultado = pick_folder(
        helper_script=_existing_script(tmp_path),
        run_subprocess=runner,
        is_frozen_fn=lambda: False,
    )
    assert resultado == "C:\\Users\\alguien\\Documents\\Caso 1"


def test_cancelacion_devuelve_none_sin_lanzar(tmp_path):
    runner = _fake_runner(3)
    resultado = pick_folder(
        helper_script=_existing_script(tmp_path),
        run_subprocess=runner,
        is_frozen_fn=lambda: False,
    )
    assert resultado is None


def test_sin_gui_lanza_error_comprensible(tmp_path):
    runner = _fake_runner(4, stderr="Tkinter no está disponible en este intérprete")
    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=_existing_script(tmp_path),
            run_subprocess=runner,
            is_frozen_fn=lambda: False,
        )
    assert "interfaz gráfica" in str(excinfo.value)


def test_error_inesperado_del_subproceso_lanza_error(tmp_path):
    runner = _fake_runner(1, stderr="boom")
    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=_existing_script(tmp_path),
            run_subprocess=runner,
            is_frozen_fn=lambda: False,
        )
    assert "boom" in str(excinfo.value)


def test_timeout_lanza_error_comprensible_y_no_cuelga(tmp_path):
    def _run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=_existing_script(tmp_path),
            run_subprocess=_run,
            is_frozen_fn=lambda: False,
            timeout=5.0,
        )
    assert "plazo" in str(excinfo.value)


def test_fallo_al_arrancar_subproceso_lanza_error(tmp_path):
    def _run(cmd, **kwargs):
        raise OSError("no se pudo crear el proceso")

    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=_existing_script(tmp_path),
            run_subprocess=_run,
            is_frozen_fn=lambda: False,
        )
    assert "no se pudo crear el proceso" in str(excinfo.value)


def test_script_auxiliar_ausente_lanza_error_sin_invocar_subprocess(tmp_path):
    runner = _fake_runner(0, stdout="no debería usarse")
    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=tmp_path / "no_existe.py",
            run_subprocess=runner,
            is_frozen_fn=lambda: False,
        )
    assert "no se encontró" in str(excinfo.value).lower()
    assert runner.calls == []


def test_modo_frozen_no_invoca_subprocess_y_reporta_diferido(tmp_path):
    runner = _fake_runner(0, stdout="no debería usarse")
    with pytest.raises(FolderDialogUnavailableError) as excinfo:
        pick_folder(
            helper_script=_existing_script(tmp_path),
            run_subprocess=runner,
            is_frozen_fn=lambda: True,
        )
    assert "empaquetado" in str(excinfo.value).lower()
    assert runner.calls == []


def test_ruta_vacia_en_stdout_se_trata_como_cancelacion(tmp_path):
    runner = _fake_runner(0, stdout="   \n")
    resultado = pick_folder(
        helper_script=_existing_script(tmp_path),
        run_subprocess=runner,
        is_frozen_fn=lambda: False,
    )
    assert resultado is None


def test_invoca_con_sys_executable_y_carpeta_inicial_como_argumento(tmp_path):
    runner = _fake_runner(0, stdout=str(tmp_path))
    pick_folder(
        initial_dir=str(tmp_path),
        helper_script=_existing_script(tmp_path),
        run_subprocess=runner,
        is_frozen_fn=lambda: False,
    )
    cmd, kwargs = runner.calls[0]
    assert cmd[0] == sys.executable
    assert str(tmp_path) in cmd
    assert kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS
