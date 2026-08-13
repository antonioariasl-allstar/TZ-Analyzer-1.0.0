"""tz_web — identidad visual (Fase 2 pulido pre-Beta).

Cubre: assets de branding disponibles localmente, header/AYUDA usando el
nuevo icono/isotipo, ausencia de dependencias remotas nuevas y que el logo
legacy ("Logo TZ.png") deja de ser una dependencia activa de las rutas que
ya fueron migradas al nuevo branding.
"""
from __future__ import annotations

import os

from tz_web import routes as tz_web_routes

BRANDING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tz_core", "assets", "branding",
)


# ---------------------------------------------------------------------------
# A — assets de branding disponibles localmente.
# ---------------------------------------------------------------------------


def test_assets_de_branding_disponibles_localmente():
    for filename in (
        "TZ_Analyzer_icono_app.png",
        "TZ_Analyzer_isotipo_principal.png",
        "TZ_Analyzer_logo_horizontal.png",
    ):
        path = os.path.join(BRANDING_DIR, filename)
        assert os.path.isfile(path), f"falta asset de branding: {path}"
        assert os.path.getsize(path) > 0


# ---------------------------------------------------------------------------
# B — el header usa el nuevo icono (vía la ruta /assets/logo).
# ---------------------------------------------------------------------------


def test_header_usa_icono_nuevo(client):
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert 'src="/assets/logo"' in html

    logo_resp = client.get("/assets/logo")
    assert logo_resp.status_code == 200
    assert logo_resp.data == open(
        os.path.join(BRANDING_DIR, "TZ_Analyzer_icono_app.png"), "rb"
    ).read()


# ---------------------------------------------------------------------------
# C — AYUDA usa assets locales (icono en el header, isotipo en "Acerca de").
# ---------------------------------------------------------------------------


def test_ayuda_usa_assets_locales_icono_y_isotipo(client):
    html = client.get("/help").data.decode("utf-8")
    assert 'src="/assets/logo"' in html
    assert 'src="/assets/logo-isotipo"' in html

    isotipo_resp = client.get("/assets/logo-isotipo")
    assert isotipo_resp.status_code == 200
    assert isotipo_resp.data == open(
        os.path.join(BRANDING_DIR, "TZ_Analyzer_isotipo_principal.png"), "rb"
    ).read()


# ---------------------------------------------------------------------------
# D — sin dependencias remotas nuevas.
# ---------------------------------------------------------------------------


def test_branding_sin_dependencias_remotas(client):
    for endpoint in ("/", "/menu", "/help"):
        html = client.get(endpoint).data.decode("utf-8")
        assert "http://" not in html
        assert "https://" not in html
        assert "cdn." not in html.lower()


# ---------------------------------------------------------------------------
# E — el logo antiguo deja de ser dependencia activa donde se sustituyó.
# ---------------------------------------------------------------------------


def test_logo_legacy_ya_no_es_dependencia_activa_de_las_rutas_web():
    assert "branding" in tz_web_routes._LOGO_PATH
    assert "Logo TZ.png" not in tz_web_routes._LOGO_PATH
    assert "branding" in tz_web_routes._LOGO_ISOTIPO_PATH


def test_respuesta_de_logo_no_coincide_con_el_asset_legacy(client):
    legacy_path = os.path.join(
        os.path.dirname(BRANDING_DIR), "Logo TZ.png"
    )
    assert os.path.isfile(legacy_path), "el asset legacy debe conservarse en disco"
    legacy_bytes = open(legacy_path, "rb").read()

    resp = client.get("/assets/logo")
    assert resp.data != legacy_bytes


# ---------------------------------------------------------------------------
# F — no hay una ruta de favicon remota o rota (todavía no se sirve favicon
# dedicado en esta fase; ver contrato MB "Fase 2", sección 4).
# ---------------------------------------------------------------------------


def test_sin_referencia_a_favicon_remoto(client):
    html = client.get("/").data.decode("utf-8")
    assert 'rel="icon"' not in html or "http" not in html
