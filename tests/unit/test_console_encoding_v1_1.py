"""Ítem 3 del gate v1.1: compatibilidad de consola Windows (cp1252).

Verifica puntualmente los tres símbolos identificados (uno en ui_utils.py,
dos en manual_mode.py) sin exigir limpieza general de emojis en el resto
del código (fuera de alcance del gate).
"""
from __future__ import annotations

import inspect

import tz_core.manual_mode as manual_mode_module
import tz_core.ui_utils as ui_utils_module

FOLDER_EMOJI = "\U0001F4C1"  # 📁
CHECK_MARK = "✓"  # ✓


def test_ui_utils_source_has_no_folder_emoji():
    source = inspect.getsource(ui_utils_module)
    assert FOLDER_EMOJI not in source


def test_manual_mode_source_has_no_check_mark():
    source = inspect.getsource(manual_mode_module)
    assert CHECK_MARK not in source


def test_ui_utils_replacement_marker_present_and_cp1252_safe():
    source = inspect.getsource(ui_utils_module)
    assert "[CARPETA]" in source
    "[CARPETA]".encode("cp1252")


def test_manual_mode_replacement_markers_present_and_cp1252_safe():
    source = inspect.getsource(manual_mode_module)
    assert source.count("[OK]") >= 2
    "[OK] Punto agregado.".encode("cp1252")
    "[OK] Registro agregado.".encode("cp1252")
