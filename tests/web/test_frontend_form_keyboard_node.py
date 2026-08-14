"""Integra el contrato JS de teclado en las suites canónicas de pytest."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js no está disponible para validar app.js")
def test_frontend_form_keyboard_contract_with_node() -> None:
    result = subprocess.run(
        [NODE, "--test", "tests/web/frontend_form_keyboard.test.js"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
