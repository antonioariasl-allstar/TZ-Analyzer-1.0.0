"""
F3.6 — Coherencia geométrica entre HTML y KML/KMZ.

Genera KMZ + HTML a partir del mismo DataFrame y la misma config, y
verifica que ambas representaciones expresan el mismo radio/longitud de
línea y el mismo semiancho/apertura del cono de azimut. Antes de esta
corrección, el HTML usaba constantes JS hardcodeadas (1500 m / ±30°)
independientes de config, mientras KML/KMZ sí respetaba
config["kml"]["azimuth_km"] / config["kml"]["cone"]["half_degrees"].
"""
import os
import re

import pandas as pd

from tz_core.html.assembler import generar_informe_html
from tz_core.kml_generator import generar_kml
from tests.normalize_outputs import _read_kml_from_kmz


def _df_con_antena():
    return pd.DataFrame(
        {
            "fecha": ["01/01/2020", "02/01/2020"],
            "hora": ["10:00:00", "11:00:00"],
            "antena": ["Antena A", "Antena A"],
            "lat": [13.7, 13.701],
            "long": [-88.9, -88.901],
            "azimut": [45, 45],
            "tel": ["70000000", "70000000"],
            "imei": ["350000000000000", "350000000000000"],
        }
    )


def _generar_par_kml_html(tmp_path, config):
    df = _df_con_antena()
    kml_base = os.path.join(str(tmp_path), "caso.kml")

    generar_kml(df, kml_base, config=config, flat=False)
    kmz_path = os.path.splitext(kml_base)[0] + ".kmz"
    kml_content = _read_kml_from_kmz(kmz_path)

    html_path = generar_informe_html(
        df=df,
        archivo_kml=kml_base,
        carpeta_salida=str(tmp_path),
        nombre_salida="caso",
        hoja=None,
        config=config,
    )
    html_content = open(html_path, encoding="utf-8").read()
    return kml_content, html_content


def _kml_radio_km(kml: str) -> float:
    # El <description> del KML contiene HTML embebido, que a su vez queda
    # escapado como entidades XML (&lt;b&gt;...&lt;/b&gt;) al serializarse.
    m = re.search(r"Radio gr.fico:&lt;/b&gt; ([\d.]+) km", kml)
    assert m, "No se encontró 'Radio gráfico' en el KML generado"
    return float(m.group(1))


def _kml_apertura_half_deg(kml: str) -> int:
    m = re.search(r"Apertura del sector:&lt;/b&gt; \d+. \(.(\d+).\)", kml)
    assert m, "No se encontró 'Apertura del sector' en el KML generado"
    return int(m.group(1))


def _html_az_line_len_m(html: str) -> int:
    m = re.search(r"AZ_LINE_LEN_M\s*=\s*(\d+)", html)
    assert m, "No se encontró AZ_LINE_LEN_M en el HTML generado"
    return int(m.group(1))


def _html_az_cone_half_deg(html: str) -> int:
    m = re.search(r"AZ_CONE_HALF_DEG\s*=\s*(\d+)", html)
    assert m, "No se encontró AZ_CONE_HALF_DEG en el HTML generado"
    return int(m.group(1))


def test_html_y_kml_coinciden_con_config_productiva(tmp_path):
    config = {"kml": {"azimuth_km": 1.5, "cone": {"half_degrees": 35}}}
    kml, html = _generar_par_kml_html(tmp_path, config)

    assert _kml_radio_km(kml) == 1.5
    assert _kml_apertura_half_deg(kml) == 35
    assert _html_az_line_len_m(html) == 1500
    assert _html_az_cone_half_deg(html) == 35

    # Coherencia cruzada: el radio del KML (km) expresado en metros debe
    # coincidir exactamente con la longitud de línea usada en el HTML, y el
    # semiancho debe ser idéntico en ambas representaciones.
    assert _html_az_line_len_m(html) == round(_kml_radio_km(kml) * 1000)
    assert _html_az_cone_half_deg(html) == _kml_apertura_half_deg(kml)


def test_html_y_kml_coinciden_con_config_alternativa(tmp_path):
    config = {"kml": {"azimuth_km": 2.0, "cone": {"half_degrees": 25}}}
    kml, html = _generar_par_kml_html(tmp_path, config)

    assert _html_az_line_len_m(html) == round(_kml_radio_km(kml) * 1000) == 2000
    assert _html_az_cone_half_deg(html) == _kml_apertura_half_deg(kml) == 25
