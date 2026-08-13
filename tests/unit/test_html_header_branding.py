"""tz_core.html.header.build_logo_html — identidad visual (Fase 2).

El informe HTML embebe el logo como base64. Estas pruebas verifican que,
tras el pulido de identidad visual, el informe usa el isotipo principal
aprobado (tz_core/assets/branding/) tanto en el candidato de respaldo sin
configuración como cuando la configuración lo indica explícitamente, y que
el legacy "Logo TZ.png" ya no es la fuente por defecto.
"""
from __future__ import annotations

import base64
import os

from tz_core.html.header import build_logo_html

BRANDING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tz_core", "assets", "branding",
)
ISOTIPO_PATH = os.path.join(BRANDING_DIR, "TZ_Analyzer_isotipo_principal.png")


def _b64_of(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def test_build_logo_html_sin_config_usa_isotipo_por_defecto():
    html = build_logo_html(None)
    assert _b64_of(ISOTIPO_PATH) in html
    assert 'alt="TZ Analyzer"' in html


def test_build_logo_html_respeta_ruta_configurada_en_brand_logo_path():
    config = {"brand": {"logo": {"path": "assets/branding/TZ_Analyzer_isotipo_principal.png", "width_px": 80}}}
    html = build_logo_html(config)
    assert _b64_of(ISOTIPO_PATH) in html
    assert "height:80px" in html
