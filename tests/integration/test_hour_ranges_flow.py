import json
from pathlib import Path

import pandas as pd

from tz_core import html_generator, kml_generator


def _sample_df():
    return pd.DataFrame(
        [
            {"antena": "A1", "hora": "6.30", "lat": 13.7, "long": -89.2, "azimut": 10, "fecha": "2025-01-01"},
            {"antena": "A2", "hora": "14-20", "lat": 13.71, "long": -89.21, "azimut": 20, "fecha": "2025-01-01"},
            {"antena": "A3", "hora": "21/05", "lat": 13.8, "long": -89.25, "azimut": 30, "fecha": "2025-01-01"},
        ]
    )


def _kml_config():
    return {
        "kml": {
            "description": [
                [("Antena", "antena")],
                [("Hora", "hora")],
            ],
            "labels": {"direccion": "Direccion"},
            "name_compaction": {},
            "incluir_por_rango_horario": True,
        },
        "salida": {"solo_kmz": False},
        "style": {"theme_hex": "#ff0000"},
    }


def test_hour_ranges_flow_html_section_populates():
    df = _sample_df()
    html = html_generator.build_antennas_by_hour_section(df, {"html": {"top_antenas_n": 5}}, overrides=None)

    assert 'id="antenas-rangos"' in html
    assert "Mañana" in html and "Tarde" in html and "Noche" in html


def test_hour_ranges_flow_kml_populates(tmp_path: Path):
    df = _sample_df()
    out_path = tmp_path / "out.kml"
    cfg = _kml_config()

    ruta, descartadas = kml_generator.generar_kml(df.copy(), str(out_path), cfg, flat=False, override_tops=None)

    assert descartadas == 0
    assert Path(ruta).exists()

    text = Path(ruta).read_text(encoding="utf-8", errors="ignore")
    assert "manana_0600-1159" in text
    assert "tarde_1200-1759" in text
    assert "noche_1800-2359" in text
