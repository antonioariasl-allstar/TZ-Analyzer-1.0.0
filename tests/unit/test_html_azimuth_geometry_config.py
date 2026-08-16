"""
F3.6 — Coherencia geométrica entre HTML y KML/KMZ.

El mapa "heatmap-actividad" del informe HTML (único lugar que dibuja el
cono de azimut en HTML, ver tz_core/html/assembler.py) debe reflejar la
misma configuración canónica que usa tz_core/kml_generator.py:
config["kml"]["azimuth_km"] (radio/longitud de línea, en metros para JS) y
config["kml"]["cone"]["half_degrees"] (semiancho del cono).

Estas pruebas ejecutan el pipeline real de generar_informe_html() (no solo
búsqueda textual sobre una plantilla) y verifican las constantes JS
efectivamente embebidas en el HTML producido.
"""
import re

import pandas as pd

from tz_core.html.assembler import generar_informe_html


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


def _az_line_len_m(html: str) -> int:
    m = re.search(r"AZ_LINE_LEN_M\s*=\s*(\d+)", html)
    assert m, "No se encontró AZ_LINE_LEN_M en el HTML generado"
    return int(m.group(1))


def _az_cone_half_deg(html: str) -> int:
    m = re.search(r"AZ_CONE_HALF_DEG\s*=\s*(\d+)", html)
    assert m, "No se encontró AZ_CONE_HALF_DEG en el HTML generado"
    return int(m.group(1))


def test_config_productivo_azimuth_km_llega_al_html_como_metros(tmp_path):
    df = _df_con_antena()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    config = {"kml": {"azimuth_km": 1.5, "cone": {"half_degrees": 35}}}
    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="caso_prod",
        hoja=None,
        config=config,
    )
    html = open(html_path, encoding="utf-8").read()

    assert _az_line_len_m(html) == 1500
    assert _az_cone_half_deg(html) == 35


def test_cambiar_config_cambia_geometria_html_sin_constantes_fijas(tmp_path):
    """Prueba que el HTML no depende de constantes hardcodeadas: cambiar
    azimuth_km/half_degrees en config debe reflejarse 1:1 en el HTML."""
    df = _df_con_antena()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    config = {"kml": {"azimuth_km": 2.0, "cone": {"half_degrees": 25}}}
    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="caso_alt",
        hoja=None,
        config=config,
    )
    html = open(html_path, encoding="utf-8").read()

    assert _az_line_len_m(html) == 2000
    assert _az_cone_half_deg(html) == 25
    # Ni el valor productivo (1500/35) ni el antiguo hardcodeado (1500/30)
    # deben aparecer como constantes de geometría del azimut.
    assert _az_line_len_m(html) != 1500
    assert _az_cone_half_deg(html) not in (30, 35)


def test_config_ausente_usa_default_del_sistema_no_hardcode_antiguo(tmp_path):
    """Sin config, el HTML debe usar el mismo default que kml_generator
    (1.0 km / 60°), no el antiguo hardcode del template (1.5 km / 30°)."""
    df = _df_con_antena()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="caso_sin_config",
        hoja=None,
        config=None,
    )
    html = open(html_path, encoding="utf-8").read()

    assert _az_line_len_m(html) == 1000
    assert _az_cone_half_deg(html) == 60
