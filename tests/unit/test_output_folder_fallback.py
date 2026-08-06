"""Tests de integración para el fallback de carpeta de salida (gate v1.1).

Ejercita el mismo camino de código que usa script_principal_bitacoras_
refactory.py: tz_core.output_flow.prepare_output_setup con las funciones
reales de tz_core.ui_utils y tz_core.user_paths.default_output_cwd_fn como
cwd_fn, simulando cancelación del selector de carpeta.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from tz_core.output_flow import prepare_output_setup
from tz_core.ui_utils import (
    prompt_case_identity,
    suggest_case_name,
    collect_top_overrides,
    prompt_output_routing,
)
from tz_core.utils import sanear_nombre_archivo
from tz_core.user_paths import default_output_cwd_fn
from tz_core.manual_flow import TimeFilterResult


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tel": ["50370000000"],
            "imei": ["123456789012345"],
            "fecha": ["01/01/2026"],
        }
    )


def _run_prepare_output_setup(*, select_folder, cwd_fn, output_sink):
    df = _sample_df()
    time_filters = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)

    return prepare_output_setup(
        df,
        {},
        time_filters,
        "nombre_base",
        input_fn=lambda _prompt="": "",
        output_fn=output_sink.append,
        timestamp_fn=datetime.now,
        now_fn=datetime.now,
        sanitize_fn=sanear_nombre_archivo,
        prompt_case_identity=prompt_case_identity,
        suggest_case_name=suggest_case_name,
        collect_top_overrides=collect_top_overrides,
        prompt_output_routing=prompt_output_routing,
        select_folder=select_folder,
        cwd_fn=cwd_fn,
        ensure_dir=lambda path: os.makedirs(path, exist_ok=True),
    )


def test_cancel_folder_normal_mode_keeps_cwd_behavior(tmp_path, monkeypatch):
    """Modo normal: cancelar el selector conserva el comportamiento histórico
    (cwd_fn=default_output_cwd_fn se comporta como os.getcwd)."""
    monkeypatch.chdir(tmp_path)
    outputs: list[str] = []

    setup = _run_prepare_output_setup(
        select_folder=lambda: None,
        cwd_fn=default_output_cwd_fn,
        output_sink=outputs,
    )

    assert setup.carpeta_base == str(tmp_path)


def test_cancel_folder_frozen_mode_uses_documents_not_cwd(tmp_path, monkeypatch):
    """Modo frozen: cancelar el selector NO debe usar os.getcwd(); debe
    resolver y crear Documents\\TZ Analyzer, y avisar con la ruta."""
    cwd_marker = tmp_path / "cwd_no_deberia_usarse"
    cwd_marker.mkdir()
    monkeypatch.chdir(cwd_marker)

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("tz_core.user_paths.Path.home", classmethod(lambda cls: home_dir))

    outputs: list[str] = []
    setup = _run_prepare_output_setup(
        select_folder=lambda: None,
        cwd_fn=default_output_cwd_fn,
        output_sink=outputs,
    )

    expected_dir = home_dir / "Documents" / "TZ Analyzer"

    assert setup.carpeta_base == str(expected_dir)
    assert setup.carpeta_base != str(cwd_marker)
    assert Path(setup.carpeta_base).is_dir()
    assert any("No se seleccionó carpeta" in m and str(expected_dir) in m for m in outputs)


def test_cancel_folder_frozen_mode_never_returns_meipass_or_bare_home(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    meipass_dir = tmp_path / "bundle"
    meipass_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)
    monkeypatch.setattr("tz_core.user_paths.Path.home", classmethod(lambda cls: home_dir))

    outputs: list[str] = []
    setup = _run_prepare_output_setup(
        select_folder=lambda: None,
        cwd_fn=default_output_cwd_fn,
        output_sink=outputs,
    )

    assert setup.carpeta_base != str(home_dir)  # no HOME puro
    assert setup.carpeta_base != str(meipass_dir)  # no _MEIPASS
    assert "bundle" not in setup.carpeta_base


def test_folder_selected_normally_skips_fallback(tmp_path):
    """Cuando sí hay carpeta seleccionada, no se invoca el fallback (misma
    lógica en modo normal y frozen)."""
    chosen = tmp_path / "elegida_por_usuario"
    chosen.mkdir()
    outputs: list[str] = []

    setup = _run_prepare_output_setup(
        select_folder=lambda: str(chosen),
        cwd_fn=default_output_cwd_fn,
        output_sink=outputs,
    )

    assert setup.carpeta_base == str(chosen)
    assert not any("No se seleccionó carpeta" in m for m in outputs)
