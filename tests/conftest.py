"""Fixtures compartidos por toda la suite (no solo tests/web)."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _localappdata_aislado(tmp_path, monkeypatch):
    """Ninguna prueba debe leer ni escribir la config/identidad de usuario
    (p. ej. machine_id, ver tz_web.machine_id) del equipo real que ejecuta la
    suite. Cada prueba recibe su propio %LOCALAPPDATA% temporal; las pruebas
    que ya inyectan `localappdata=` explícito no se ven afectadas."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
