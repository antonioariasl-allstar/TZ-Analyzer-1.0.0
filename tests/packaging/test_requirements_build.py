"""requirements-build.txt: pin exacto de PyInstaller, sin dependencias runtime."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REQUIREMENTS_BUILD_PATH = REPO_ROOT / "requirements-build.txt"

_PIN_RE = re.compile(r"^pyinstaller==\d+\.\d+\.\d+$", re.IGNORECASE)


def _non_comment_lines() -> list[str]:
    text = REQUIREMENTS_BUILD_PATH.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def test_file_exists():
    assert REQUIREMENTS_BUILD_PATH.is_file()


def test_pins_exact_pyinstaller_version():
    lines = _non_comment_lines()
    assert any(_PIN_RE.match(line) for line in lines), lines


def test_pyinstaller_major_version_is_6():
    lines = _non_comment_lines()
    pin = next(line for line in lines if _PIN_RE.match(line))
    version = pin.split("==", 1)[1]
    assert version.split(".")[0] == "6"


def test_does_not_pin_runtime_dependencies():
    lines = {line.split("==", 1)[0].lower() for line in _non_comment_lines()}
    runtime_requirements = REPO_ROOT / "requirements.txt"
    runtime_names = {
        line.split("==", 1)[0].lower()
        for line in runtime_requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert lines.isdisjoint(runtime_names)


def test_does_not_pin_hooks_contrib():
    lines = _non_comment_lines()
    assert not any("pyinstaller-hooks-contrib" in line.lower() for line in lines)
