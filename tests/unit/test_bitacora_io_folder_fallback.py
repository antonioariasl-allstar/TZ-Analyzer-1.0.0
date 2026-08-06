"""tz_core.bitacora_io.seleccionar_carpeta_salida es el `select_folder` real
usado por el flujo principal (script_principal_bitacoras_refactory.main()).

Antes del gate v1.1, su fallback interno (`or os.getcwd()`) resolvía la
cancelación ANTES de que tz_core.ui_utils.prompt_output_routing pudiera
aplicar cualquier cwd_fn inyectado — por lo que el fallback frozen-aware
debe vivir aquí para que el flujo real quede protegido.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import tz_core.bitacora_io as bitacora_io_module
from tz_core.bitacora_io import seleccionar_carpeta_salida


def test_gui_cancel_normal_mode_preserves_cwd_behavior(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bitacora_io_module, "_sel_carpeta", lambda titulo="": None)

    resultado = seleccionar_carpeta_salida()

    assert resultado == str(tmp_path)
    captured = capsys.readouterr()
    assert "No se seleccionó carpeta. Se utilizará:" in captured.out


def test_gui_cancel_frozen_mode_never_uses_cwd(tmp_path, monkeypatch, capsys):
    cwd_marker = tmp_path / "cwd_no_deberia_usarse"
    cwd_marker.mkdir()
    monkeypatch.chdir(cwd_marker)

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("tz_core.user_paths.Path.home", classmethod(lambda cls: home_dir))
    monkeypatch.setattr(bitacora_io_module, "_sel_carpeta", lambda titulo="": None)

    resultado = seleccionar_carpeta_salida()

    expected_dir = home_dir / "Documents" / "TZ Analyzer"
    assert resultado == str(expected_dir)
    assert resultado != str(cwd_marker)
    assert Path(resultado).is_dir()

    captured = capsys.readouterr()
    assert f"No se seleccionó carpeta. Se utilizará: {expected_dir}" in captured.out


def test_gui_folder_chosen_skips_fallback_entirely(tmp_path, monkeypatch, capsys):
    chosen = tmp_path / "elegida_por_usuario"
    monkeypatch.setattr(bitacora_io_module, "_sel_carpeta", lambda titulo="": str(chosen))

    resultado = seleccionar_carpeta_salida()

    assert resultado == str(chosen.resolve()) or resultado == os.path.abspath(str(chosen))
    captured = capsys.readouterr()
    assert "No se seleccionó carpeta" not in captured.out
