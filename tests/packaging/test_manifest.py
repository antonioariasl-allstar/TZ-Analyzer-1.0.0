"""build_config/TZ_Analyzer.manifest: XML real, no grep textual."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = REPO_ROOT / "build_config" / "TZ_Analyzer.manifest"

_ASM_V3 = "urn:schemas-microsoft-com:asm.v3"
_LONGPATH_NS = "http://schemas.microsoft.com/SMI/2016/WindowsSettings"


def test_file_exists():
    assert MANIFEST_PATH.is_file()


def test_is_valid_xml():
    ET.parse(MANIFEST_PATH)  # lanza ParseError si no es XML válido


def test_requested_execution_level_as_invoker_no_ui_access():
    root = ET.parse(MANIFEST_PATH).getroot()
    level_el = root.find(f".//{{{_ASM_V3}}}requestedExecutionLevel")
    assert level_el is not None
    assert level_el.get("level") == "asInvoker"
    assert level_el.get("uiAccess") == "false"


def test_long_path_aware_true():
    root = ET.parse(MANIFEST_PATH).getroot()
    longpath_el = root.find(f".//{{{_LONGPATH_NS}}}longPathAware")
    assert longpath_el is not None
    assert (longpath_el.text or "").strip().lower() == "true"


def test_does_not_request_elevation():
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    for forbidden in ("requireAdministrator", "highestAvailable", "autoElevate"):
        assert forbidden not in text
