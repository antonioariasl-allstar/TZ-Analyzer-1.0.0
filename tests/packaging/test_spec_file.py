"""TZ_Analyzer.spec: validación estructural de alto nivel, sin PyInstoller.

El .spec no puede ejecutarse aquí (depende de globals que PyInstaller
inyecta al exec-utarlo: Analysis, PYZ, EXE, COLLECT, SPECPATH). En su
lugar: ``ast.parse`` confirma que es Python sintácticamente válido, y
comprobaciones de texto (no un golden completo) confirman que delega en
build_config/spec_config en vez de hardcodear rutas o flags.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = REPO_ROOT / "TZ_Analyzer.spec"

_ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]")


def _spec_source() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def test_file_exists():
    assert SPEC_PATH.is_file()


def test_is_valid_python_syntax():
    ast.parse(_spec_source(), filename=str(SPEC_PATH))


def test_no_hardcoded_absolute_paths():
    matches = _ABS_PATH_RE.findall(_spec_source())
    assert not matches, matches


def test_no_this_machine_specific_paths():
    text = _spec_source()
    for forbidden in (str(REPO_ROOT), "Users", "TZ-Analyzer-Branding"):
        assert forbidden not in text


def test_imports_shared_spec_config():
    text = _spec_source()
    assert "from build_config import spec_config as cfg" in text


def test_root_derived_from_specpath():
    text = _spec_source()
    assert "SPECPATH" in text


def test_datas_wired_to_shared_config():
    text = _spec_source()
    assert "cfg.DATAS" in text


def test_icon_manifest_and_version_wired_to_shared_config():
    text = _spec_source()
    assert "cfg.ICON_PATH" in text
    assert "cfg.MANIFEST_PATH" in text
    assert "cfg.VERSION_INFO_PATH" in text


def test_entrypoint_wired_to_shared_config():
    text = _spec_source()
    assert "cfg.ENTRYPOINT" in text


def test_name_wired_to_product_name_not_hardcoded_exe():
    text = _spec_source()
    assert "cfg.PRODUCT_NAME" in text
    assert "TZ_Analyzer.exe" not in text
    assert '"TZ_Analyzer"' not in text


def test_console_upx_strip_contents_directory_wired_to_shared_config():
    text = _spec_source()
    assert "console=cfg.CONSOLE" in text
    assert "upx=cfg.UPX" in text
    assert "strip=cfg.STRIP" in text
    assert "contents_directory=cfg.CONTENTS_DIRECTORY" in text


def test_hiddenimports_and_excludes_wired_to_shared_config():
    text = _spec_source()
    assert "cfg.HIDDENIMPORTS" in text
    assert "cfg.EXCLUDES" in text


def test_manual_not_included_as_datas():
    text = _spec_source().lower()
    assert "manual" not in text


def test_no_tcl_tk_manual_overrides():
    text = _spec_source()
    for forbidden in ("tcl86t.dll", "tk86t.dll", "_tkinter.pyd", "tcl8.6", "tk8.6"):
        assert forbidden not in text
