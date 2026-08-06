"""Tests del modo manual (tz_core.manual_mode.modo_manual) para el gate v1.1:

- En modo frozen, cancelar el selector de carpeta ya NO aborta la operación:
  cae a Documents\\TZ Analyzer (nunca os.getcwd()), la crea y avisa.
- En modo normal se conserva el contrato histórico (cancelar aborta).
- Se generan productos mínimos (KMZ) en la carpeta resuelta.
- Los textos visibles ya no contienen el símbolo '✓' (encoding cp1252).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import tz_core.manual_mode as manual_mode_module
import tz_core.ui_utils as ui_utils_module
from tz_core.manual_mode import modo_manual


def _scripted_input(monkeypatch, responses):
    it = iter(responses)

    def _fake_input(_prompt: str = "") -> str:
        return next(it, "")

    monkeypatch.setattr("builtins.input", _fake_input)


# Secuencia para: puntos libres -> agregar 1 punto -> graficar (Enter = nombre auto)
_PUNTO_LIBRE_RESPONSES = [
    "2",        # tipo de registro: puntos libres
    "A",        # agregar registro
    "TestPoint",  # nombre del lugar
    "",         # direccion (opcional)
    "13.7",     # lat
    "-89.2",    # lon
    "",         # comentarios (opcional)
    "G",        # graficar
    "",         # nombre base (Enter = auto)
]


def test_manual_mode_frozen_cancel_uses_documents_fallback_and_generates_kmz(tmp_path, monkeypatch, capsys):
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("tz_core.user_paths.Path.home", classmethod(lambda cls: home_dir))
    monkeypatch.setattr(ui_utils_module, "seleccionar_carpeta", lambda *a, **k: None)

    _scripted_input(monkeypatch, _PUNTO_LIBRE_RESPONSES)

    modo_manual(config={})

    expected_dir = home_dir / "Documents" / "TZ Analyzer"
    captured = capsys.readouterr()

    assert "No se seleccionó carpeta. Se utilizará:" in captured.out
    assert str(expected_dir) in captured.out
    assert expected_dir.is_dir()

    # Producto mínimo (KMZ) generado dentro de la ruta resuelta
    kmz_files = list(expected_dir.rglob("*.kmz"))
    assert kmz_files, "Debe generarse al menos un .kmz dentro de Documents\\TZ Analyzer"


def test_manual_mode_normal_mode_cancel_still_aborts(tmp_path, monkeypatch, capsys):
    """Modo normal: se conserva el contrato histórico (cancelar aborta,
    sin generar productos)."""
    assert getattr(sys, "frozen", False) is False

    monkeypatch.setattr(ui_utils_module, "seleccionar_carpeta", lambda *a, **k: None)
    _scripted_input(monkeypatch, _PUNTO_LIBRE_RESPONSES)

    modo_manual(config={})

    captured = capsys.readouterr()
    assert "[QC] Selección de carpeta cancelada. Operación abortada." in captured.out
    assert "No se seleccionó carpeta. Se utilizará:" not in captured.out


def test_manual_mode_visible_texts_have_no_check_mark_and_are_cp1252_safe(tmp_path, monkeypatch, capsys):
    chosen_dir = tmp_path / "elegida"
    chosen_dir.mkdir()

    monkeypatch.setattr(ui_utils_module, "seleccionar_carpeta", lambda *a, **k: str(chosen_dir))
    _scripted_input(monkeypatch, _PUNTO_LIBRE_RESPONSES)

    modo_manual(config={})

    captured = capsys.readouterr()
    assert "✓" not in captured.out  # ✓
    assert "[OK] Punto agregado." in captured.out
    # Solo el texto puntualmente corregido debe ser cp1252-safe (no se hizo
    # limpieza general de emojis en el resto del módulo, fuera de alcance).
    "[OK] Punto agregado.".encode("cp1252")  # no debe lanzar UnicodeEncodeError
