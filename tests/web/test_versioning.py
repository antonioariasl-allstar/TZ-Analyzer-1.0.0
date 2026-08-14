"""tz_web — versión de producto mostrada en la interfaz (FASE 3).

Cubre: header y portada muestran la versión canónica (tz_version.VERSION,
"1.0.0-beta.1"), ya no queda "Versión 1.1" activa en esas superficies, y
``/internal/health`` sigue reportando app_version/launcher_version con la
misma forma que antes (solo cambia el valor de app_version).
"""
from __future__ import annotations

import tz_version


def test_portada_muestra_version_canonica(client):
    html = client.get("/").data.decode("utf-8")
    assert f"Versión {tz_version.VERSION}" in html
    assert "Versión 1.1" not in html


def test_header_menu_muestra_version_canonica(client):
    html = client.get("/menu").data.decode("utf-8")
    assert f"Versión {tz_version.VERSION}" in html
    assert "Versión 1.1" not in html


def test_internal_health_reporta_app_version_canonica(client):
    app = client.application
    token = "test-token"
    app.config["TZ_INSTANCE_TOKEN"] = token
    resp = client.get("/internal/health", headers={"X-TZ-Token": token})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["app_version"] == tz_version.VERSION
    # launcher_version es el protocolo de instancia única — no forma parte
    # de esta migración (ver tz_web.instance.LAUNCHER_VERSION).
    assert body["launcher_version"] == "1.0"
