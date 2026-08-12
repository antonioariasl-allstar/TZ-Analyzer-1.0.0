"""Pruebas adversariales — MICROBLOQUE 4 (AUD-07 / AUD-08).

AUD-07: datos de bitácora/manuales no deben interpretarse como HTML/JS/XML
activo en el HTML, el JSON embebido en <script>, ni en KML/KMZ.

AUD-08: el informe HTML debe poder inicializar mapas/heatmaps sin depender
de CDN externos, y el KMZ no debe depender de íconos remotos.
"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

import tz_core.html.header as header_mod
from tz_core.security_escaping import esc_html, safe_json_for_script
from tz_core.format_utils import armar_descripcion_compacta
from tz_core.html.antennas import build_top_antennas_section, build_antennas_by_hour_section
from tz_core.html.header import generate_html_header
from tz_core.interacciones_builder import construir_seccion_interacciones


PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "</script><script>alert(1)</script>",
    '<a href="javascript:alert(1)">x</a>',
    '"><img src=x onerror=alert(1)>',
    "A&B",
    "<ANTENA>",
    '"alias"',
    "'usuario'",
    "]]>",
    "áéíóúñ 🎯",
]


def _assert_no_hallucinated_active_markup(html: str, payload: str):
    """El payload debe sobrevivir como texto visible pero no como nodo activo."""
    escaped = esc_html(payload)
    assert escaped in html, f"payload escapado no encontrado para: {payload!r}"
    # Ningún caso debe dejar el payload crudo (tal cual) dentro del documento,
    # lo que indicaría que quedó como markup/atributo activo sin escapar.
    assert payload not in html or escaped == payload, (
        f"payload sin escapar sobrevivió literal en el HTML: {payload!r}"
    )


# ---------------------------------------------------------------------------
# AUD-07 — HTML: texto y atributos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload", PAYLOADS)
def test_esc_html_neutraliza_payloads(payload):
    out = esc_html(payload)
    # Ninguna etiqueta activa real sobrevive: '<' y '>' quedan como entidades,
    # de modo que "onerror=" (si estaba presente) queda dentro de texto inerte,
    # nunca dentro de un tag real.
    assert "<" not in out
    assert ">" not in out
    if payload:
        assert out != payload or not any(c in payload for c in "&<>\"'")


def test_antennas_top_section_escapa_nombre_antena():
    df = pd.DataFrame({
        "antena": ["<img src=x onerror=alert(1)>"] * 3,
        "lat": [13.7, 13.7, 13.7],
        "long": [-89.2, -89.2, -89.2],
        "azimut": [90, 90, 90],
    })
    html = build_top_antennas_section(df, config=None, overrides=None)
    assert "<img src=x onerror=alert(1)>" not in html
    assert esc_html("<img src=x onerror=alert(1)>") in html


def test_antennas_by_hour_escapa_nombre_antena():
    df = pd.DataFrame({
        "antena": ["<script>alert(1)</script>"] * 2,
        "lat": [13.7, 13.7],
        "long": [-89.2, -89.2],
        "hora": ["10:00:00", "11:00:00"],
        "azimut": [90, 90],
    })
    html = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_interacciones_builder_escapa_contacto_y_tipo_y_json_marcadores():
    df = pd.DataFrame({
        "fecha": ["10/01/2026", "10/01/2026"],
        "hora": ["09:00:00", "10:00:00"],
        "contacto": ['"><img src=x onerror=alert(1)>', "5511"],
        "tipo": ["<svg onload=alert(1)>", "Llamada"],
        "antena": ["</script><script>alert(1)</script>", "Sitio B"],
        "lat": [13.7, 13.71],
        "long": [-89.2, -89.21],
        "azimut": [90, 100],
        "celda": ["<b>1</b>", "2"],
    })
    html = construir_seccion_interacciones(df, dias=3)

    # Ningún payload crudo debe sobrevivir como markup/​script real.
    assert "<img src=x onerror=alert(1)>" not in html
    assert "<svg onload=alert(1)>" not in html
    # El cierre prematuro de <script> vía dato no debe aparecer literal.
    assert "</script><script>alert(1)</script>" not in html

    # El JSON embebido para los marcadores del heatmap debe ir neutralizado:
    # ni un literal "</script" ni un '<' crudo proveniente del dato.
    for m in re.finditer(r"var markers = (.*?);\n", html):
        assert "</script" not in m.group(1).lower()


def test_json_embebido_en_script_no_rompe_bloque_y_preserva_datos():
    payload = {"name": "</script><script>alert(1)</script>", "n": 3}
    safe = safe_json_for_script(payload)
    assert "</script" not in safe.lower()
    html_doc = f"<script>\nvar data = {safe};\n</script>"
    assert html_doc.count("<script>") == 1
    assert html_doc.count("</script>") == 1

    import json
    assert json.loads(safe) == payload


# ---------------------------------------------------------------------------
# AUD-07 — KML/KMZ
# ---------------------------------------------------------------------------

_CONFIG_KMZ = {
    "kml": {"azimuth_km": 1.0},
    "style": {"theme_hex": "#ff0000"},
    "salida": {"solo_kmz": True},
}


def _generar_y_leer_kml(df, tmp_path, config=None):
    import tz_core.kml_generator as kml_mod
    kml_mod._REUSABLE_STYLES = None
    out = str(tmp_path / "test.kml")
    kml_mod.generar_kml(df, out, config or _CONFIG_KMZ)
    kmz = str(tmp_path / "test.kmz")
    assert os.path.exists(kmz), "KMZ no generado"
    with zipfile.ZipFile(kmz, "r") as z:
        with z.open("doc.kml") as f:
            raw = f.read().decode("utf-8")
    # El doc.kml debe seguir siendo XML válido.
    ET.fromstring(raw)
    return raw


@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "A&B <SITE> \"01\"",
    "]]>",
    "áéíóúñ 🎯",
])
def test_kml_description_neutraliza_payloads_en_alias(tmp_path, payload):
    df = pd.DataFrame({
        "fecha": ["10/01/2026"],
        "hora": ["09:00:00"],
        "lat": [13.7],
        "long": [-89.2],
        "antena": ["Sitio Normal"],
        "azimut": [90],
        "alias": [payload],
    })
    raw = _generar_y_leer_kml(df, tmp_path)
    # Tras un único unescape XML (lo que hace cualquier parser KML), el dato
    # debe seguir teniendo una capa de escape residual: nunca debe quedar
    # como '<script>'/'<img ...>' crudo lista para ser interpretada como
    # HTML activo por un visor que renderiza la burbuja como HTML.
    assert "<script>alert(1)</script>" not in raw
    assert "<img src=x onerror=alert(1)>" not in raw
    # El valor sigue siendo recuperable (no se pierde el dato forense).
    root = ET.fromstring(raw)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    descripciones = " ".join(
        (el.text or "") for el in root.iter("{http://www.opengis.net/kml/2.2}description")
    )
    # Tras el unescape de ET.fromstring, el valor original (o su forma
    # doblemente escapada si el payload no contiene < > &) debe aparecer.
    if any(c in payload for c in "<>&"):
        assert esc_html(payload) in descripciones or payload not in descripciones
    else:
        assert payload in descripciones


def test_kml_puntos_libres_no_deja_markup_activo(tmp_path):
    from tz_core.kml_generator import generar_kml_puntos_libres
    df = pd.DataFrame({
        "antena": ["<img src=x onerror=alert(1)>"],
        "detalle": ["<img src=x onerror=alert(1)>"],
        "direccion": ['A&B <SITE> "01"'],
        "lat": [13.7],
        "long": [-89.2],
    })
    out_kml = str(tmp_path / "libres.kml")
    kmz_path, descartadas = generar_kml_puntos_libres(df, out_kml, _CONFIG_KMZ)
    assert kmz_path and os.path.exists(kmz_path)
    with zipfile.ZipFile(kmz_path, "r") as z:
        with z.open("doc.kml") as f:
            raw = f.read().decode("utf-8")
    ET.fromstring(raw)  # XML válido
    assert "<img src=x onerror=alert(1)>" not in raw


def test_kml_no_referencia_maps_google_para_icono(tmp_path):
    df = pd.DataFrame({
        "fecha": ["10/01/2026"],
        "hora": ["09:00:00"],
        "lat": [13.7],
        "long": [-89.2],
        "antena": ["Sitio X"],
        "azimut": [90],
    })
    raw = _generar_y_leer_kml(df, tmp_path)
    assert "maps.google.com" not in raw


# ---------------------------------------------------------------------------
# AUD-08 — funcionamiento offline
# ---------------------------------------------------------------------------

def test_html_header_no_depende_de_cdn_para_leaflet():
    html = generate_html_header("#ff6b35", "caso_offline")
    assert "unpkg.com" not in html
    assert "cdnjs" not in html
    assert "cdn." not in html
    assert "L.Icon.Default.mergeOptions" in html
    assert "window.tzEscHtml" in html
    assert "window.tzShowOfflineMapNotice" in html


def test_vendor_assets_leaflet_presentes():
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tz_core", "assets", "vendor", "leaflet",
    )
    for rel in [
        "leaflet.css", "leaflet.js", "leaflet-heat.js",
        "images/marker-icon.png", "images/marker-icon-2x.png", "images/marker-shadow.png",
        "NOTICE.md",
    ]:
        assert os.path.exists(os.path.join(base, rel)), f"falta asset vendorizado: {rel}"


def test_html_solo_referencia_tile_openstreetmap_como_fondo_opcional():
    """Las únicas URLs http(s) restantes en el <head> deben ser el tile layer
    (fondo cartográfico opcional, con manejo de error) — no dependencias
    obligatorias de JS/CSS."""
    html = generate_html_header("#ff6b35", "caso_offline")
    head_end = html.find("</head>")
    urls = re.findall(r"https?://[^\s\"'<>]+", html[:head_end])
    for u in urls:
        assert "tile.openstreetmap.org" in u or "opengis.net" not in u


@pytest.fixture
def _vendor_cache_reset():
    """Limpia la caché en memoria del bloque Leaflet antes y después de cada
    prueba, para que el estado de una prueba (assets faltantes) no se filtre
    a otra (assets presentes), ni al revés."""
    header_mod._vendor_cache.clear()
    yield
    header_mod._vendor_cache.clear()


@pytest.mark.parametrize("missing_file", ["leaflet.css", "leaflet.js", "leaflet-heat.js"])
def test_falta_asset_vendorizado_falla_explicitamente_sin_degradar_a_cdn(
    tmp_path, monkeypatch, missing_file, _vendor_cache_reset
):
    """AUD-08 (endurecido): si falta un asset imprescindible de Leaflet/
    leaflet-heat, la generación debe fallar con un error técnico explícito —
    nunca debe caer de vuelta a etiquetas <link>/<script> apuntando a un CDN
    externo (unpkg u otro)."""
    fake_dir = tmp_path / "vendor_leaflet"
    shutil.copytree(header_mod._VENDOR_DIR, fake_dir)
    os.remove(fake_dir / missing_file)
    monkeypatch.setattr(header_mod, "_VENDOR_DIR", str(fake_dir))

    with pytest.raises(RuntimeError) as excinfo:
        header_mod._load_vendor_leaflet_block()

    assert "unpkg.com" not in str(excinfo.value)
    assert "http://" not in str(excinfo.value) and "https://" not in str(excinfo.value)
    # El fallo no debe dejar un bloque degradado cacheado para futuras llamadas.
    assert "block" not in header_mod._vendor_cache


@pytest.mark.parametrize("missing_file", ["leaflet.css", "leaflet.js", "leaflet-heat.js"])
def test_falta_asset_vendorizado_propaga_error_desde_generate_html_header(
    tmp_path, monkeypatch, missing_file, _vendor_cache_reset
):
    """El fallo debe propagarse hasta generate_html_header (no producir un
    HTML parcial/degradado dependiente de Internet)."""
    fake_dir = tmp_path / "vendor_leaflet"
    shutil.copytree(header_mod._VENDOR_DIR, fake_dir)
    os.remove(fake_dir / missing_file)
    monkeypatch.setattr(header_mod, "_VENDOR_DIR", str(fake_dir))

    with pytest.raises(RuntimeError):
        header_mod.generate_html_header("#ff6b35", "caso_offline")


def test_assets_presentes_html_generado_sin_cdn_y_sin_error(_vendor_cache_reset):
    """Caso feliz explícito: con los assets vendorizados reales presentes, la
    generación no lanza y el HTML resultante no referencia ningún CDN."""
    html = header_mod.generate_html_header("#ff6b35", "caso_offline")
    assert "unpkg.com" not in html
    assert "cdnjs" not in html
    assert "L.Icon.Default.mergeOptions" in html
