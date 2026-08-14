"""tz_core.html — versión de producto en el informe generado (MB-F3B).

El encabezado y el pie/byline del informe HTML mostraban "Versión 1.1"
leída de config.json, divergiendo de la versión canónica de la app
(tz_version.VERSION). Ambas superficies ahora derivan exclusivamente de
tz_version — config.json ya no puede afectar el texto de versión mostrado
en el informe (single source of truth).
"""
from __future__ import annotations

import pandas as pd

import tz_version
from tz_core.html.header import generate_body_header
from tz_core.html.assembler import generar_informe_html

EXPECTED_HEADER_VERSION_TEXT = f"TZ Analyzer — Versión {tz_version.VERSION}"
EXPECTED_BYLINE_TEXT = (
    f"Desarrollado por {tz_version.AUTHOR} — {tz_version.PRODUCT_NAME} "
    f"— Versión {tz_version.VERSION}"
)


def test_generate_body_header_usa_version_canonica():
    html = generate_body_header("<img/>", "caso_x", "Hoja1", "2026-08-13 10:00")
    assert EXPECTED_HEADER_VERSION_TEXT in html
    assert "Versión 1.1" not in html


def _df_minima() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": ["01/01/2026"],
            "hora": ["08:00:00"],
            "tel": ["70011111"],
            "antena": ["ANT-A"],
            "lat": [13.6929],
            "long": [-89.2182],
            "contacto": ["70022222"],
            "interaccion": ["LLAMADA ENTRANTE"],
            "duracion": ["00:01:00"],
        }
    )


def _generar(tmp_path, config) -> str:
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")
    return generar_informe_html(
        df=_df_minima(),
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="caso",
        hoja=None,
        nombre_bitacora=None,
        config=config,
    )


def test_informe_header_ignora_version_de_config(tmp_path):
    # config.json históricamente traía brand.version="Versión 1.1"; un valor
    # deliberadamente distinto aquí prueba que el header ya no lo lee en
    # absoluto (fuente única: tz_version).
    config = {"brand": {"name": "TZ Analyzer", "version": "Versión 9.9.9-residual"}}
    html_path = _generar(tmp_path, config)
    html = open(html_path, encoding="utf-8").read()

    assert EXPECTED_HEADER_VERSION_TEXT in html
    assert "9.9.9-residual" not in html


def test_informe_byline_ignora_config_y_usa_redaccion_natural(tmp_path):
    # branding.byline_texto históricamente traía "by: Omar Arias - TZ
    # Analyzer - Versión 1.1"; un valor deliberadamente distinto aquí prueba
    # que el byline ya no lo lee (fuente única: tz_version) y que el "by:"
    # fue reemplazado por una redacción natural en español.
    config = {
        "branding": {
            "mostrar_pie_legal": True,
            "pie_legal_texto": "Texto legal de prueba.",
            "byline_texto": "by: alguien - Otro Producto - Versión 0.0.1",
        }
    }
    html_path = _generar(tmp_path, config)
    html = open(html_path, encoding="utf-8").read()

    assert EXPECTED_BYLINE_TEXT in html
    assert "by:" not in html
    assert "Versión 0.0.1" not in html
    assert "Otro Producto" not in html


def test_informe_sin_residuo_version_1_1(tmp_path):
    html_path = _generar(tmp_path, config={})
    html = open(html_path, encoding="utf-8").read()
    assert "Versión 1.1" not in html
    assert "1.1 Beta" not in html
