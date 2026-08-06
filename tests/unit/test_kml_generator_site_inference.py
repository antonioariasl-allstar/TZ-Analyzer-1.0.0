"""HITO 2B — Integración de antena_analitica/sitio_inferido en KML/KMZ.

Cubre los casos 1-8, 17 y 20 de la lista obligatoria del hito: resolución del
nombre visible por prioridad (antena_analitica > antena > identificador
neutral), ausencia del literal genérico "Antena", no fusión de sitios
inferidos distintos, agrupación del mismo sitio inferido, conservación de
sectores por azimut, prioridad de la antena real, indicador de sitio
inferido en la burbuja, nota general única, y ausencia de cambio visual en
una bitácora completa (sin sitios inferidos).
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from script_principal_bitacoras_refactory import bootstrap_config
from tz_core.kml_generator import GUIA_SITIOS_INFERIDOS_KML, generar_kml
from tz_core.site_inference import agregar_sitio_analitico

LAT_SV = 13.559339
LON_SV = -88.433997
SITIO_SV = "SITIO_13.559339_-88.433997"

LAT_SV_2 = 13.7
LON_SV_2 = -89.2
SITIO_SV_2 = "SITIO_13.700000_-89.200000"


@pytest.fixture(autouse=True, scope="module")
def _config():
    bootstrap_config()


def _extract_kml_from_kmz(kmz_path: str) -> str:
    with zipfile.ZipFile(kmz_path, "r") as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".kml"))
        return archive.read(name).decode("utf-8", errors="ignore")


def _generar_y_extraer(df: pd.DataFrame, tmp_dir: str, nombre: str = "test") -> str:
    out_kml = str(Path(tmp_dir) / f"{nombre}.kml")
    generar_kml(df, out_kml, config={}, flat=False)
    kmz_path = str(Path(out_kml).with_suffix(".kmz"))
    return _extract_kml_from_kmz(kmz_path)


def _df_sin_antena(coords: list[tuple[float, float]], *, azimut=None, celda=None, fecha=None, hora=None) -> pd.DataFrame:
    n = len(coords)
    data = {
        "fecha": fecha if fecha is not None else [f"0{(i % 9) + 1}/01/2025" for i in range(n)],
        "hora": hora if hora is not None else [f"{8 + i:02d}:00:00" for i in range(n)],
        "antena": [None] * n,
        "lat": [c[0] for c in coords],
        "long": [c[1] for c in coords],
    }
    if azimut is not None:
        data["azimut"] = azimut
    if celda is not None:
        data["celda"] = celda
    df = pd.DataFrame(data)
    return agregar_sitio_analitico(df)


# --- 1. KML usa antena_analitica (identificador de sitio inferido) ----------

def test_kml_usa_antena_analitica_para_sitio_inferido():
    df = _df_sin_antena([(LAT_SV, LON_SV)])
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert f"<name>{SITIO_SV}</name>" in kml_data


# --- 2. No usa el literal genérico "Antena" cuando hay sitio inferible ------

def test_kml_no_usa_literal_generico_antena():
    df = _df_sin_antena([(LAT_SV, LON_SV)])
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert "<name>Antena</name>" not in kml_data


# --- 3. Sitios inferidos distintos no se fusionan ---------------------------

def test_kml_sitios_inferidos_distintos_no_se_fusionan():
    df = _df_sin_antena([(LAT_SV, LON_SV), (LAT_SV_2, LON_SV_2)])
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert f"<name>{SITIO_SV}</name>" in kml_data
    assert f"<name>{SITIO_SV_2}</name>" in kml_data
    assert SITIO_SV != SITIO_SV_2
    # No debe existir un identificador híbrido que mezcle las coordenadas de ambos sitios.
    assert "SITIO_13.559339_-89.2" not in kml_data


# --- 4. Mismo sitio inferido se agrupa (Top N deduplicado) ------------------

def test_kml_mismo_sitio_inferido_se_agrupa_en_top():
    df = _df_sin_antena([(LAT_SV, LON_SV)] * 3)
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    # En el Top Global deduplicado debe existir una única carpeta "1_SITIO_..."
    assert f"<name>1_{SITIO_SV}</name>" in kml_data
    assert "Total de activaciones:&lt;/b&gt; 3" in kml_data


# --- 5. Mismo sitio con azimuts distintos conserva sectores separados -------

def test_kml_mismo_sitio_azimuts_distintos_conserva_sectores():
    df = _df_sin_antena(
        [(LAT_SV, LON_SV), (LAT_SV, LON_SV)],
        azimut=[45, 200],
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert "Cono Azimut 45°" in kml_data
    assert "Cono Azimut 200°" in kml_data or "Cono Azimut 200° (sec.)" in kml_data
    assert "Azimuts secundarios:</b> Ninguno" not in kml_data


# --- 6. Nombre real conserva prioridad sobre coordenadas --------------------

def test_kml_antena_real_conserva_prioridad():
    df = pd.DataFrame({
        "fecha": ["01/01/2025"],
        "hora": ["10:00:00"],
        "antena": ["Distrito Italia"],
        "lat": [LAT_SV],
        "long": [LON_SV],
    })
    df = agregar_sitio_analitico(df)
    assert df.loc[0, "antena_analitica"] == "Distrito Italia"
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert "<name>Distrito Italia</name>" in kml_data
    assert SITIO_SV not in kml_data


# --- 7. Burbuja indica sitio inferido ---------------------------------------

def test_kml_burbuja_indica_sitio_inferido():
    df = _df_sin_antena([(LAT_SV, LON_SV)])
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert "Sitio inferido por coordenadas normalizadas." in kml_data


# --- 8. La nota general del KMZ aparece una sola vez ------------------------

def test_kml_nota_general_aparece_una_sola_vez():
    df = _df_sin_antena([(LAT_SV, LON_SV), (LAT_SV, LON_SV), (LAT_SV_2, LON_SV_2)])
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert kml_data.count(GUIA_SITIOS_INFERIDOS_KML) == 1


# --- Extra: la nota general no aparece si no hay sitios inferidos ----------

def test_kml_nota_general_ausente_sin_sitios_inferidos():
    df = pd.DataFrame({
        "fecha": ["01/01/2025", "01/01/2025"],
        "hora": ["10:00:00", "11:00:00"],
        "antena": ["Distrito Italia", "Apopa II"],
        "lat": [LAT_SV, LAT_SV_2],
        "long": [LON_SV, LON_SV_2],
        "azimut": [45, 120],
    })
    df = agregar_sitio_analitico(df)
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert GUIA_SITIOS_INFERIDOS_KML not in kml_data
    assert "Sitio inferido por coordenadas normalizadas." not in kml_data


# --- 17. Bitácora completa (antena real en todas las filas): sin cambio visual

def test_kml_bitacora_completa_no_cambia_visualmente():
    df = pd.DataFrame([
        {"fecha": "23/12/2021", "hora": "10:43:09", "lat": 13.730, "long": -89.190,
         "antena": "Distrito Italia", "azimut": 45, "tel": "70871087", "imei": "352005090177850"},
        {"fecha": "23/12/2021", "hora": "10:59:53", "lat": 13.740, "long": -89.220,
         "antena": "Apopa II", "azimut": 120},
        {"fecha": "24/12/2021", "hora": "08:15:00", "lat": 13.750, "long": -89.200,
         "antena": "El Zope", "azimut": 200},
    ])
    df = agregar_sitio_analitico(df)
    assert not df["sitio_inferido"].any()

    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)

    assert "<Folder" in kml_data
    assert "todas_las_antenas" in kml_data
    assert ("<LineString" in kml_data) or ("Azimut " in kml_data)
    assert ("<Polygon" in kml_data) or ("Cono Azimut" in kml_data)
    assert kml_data.count("<Placemark") >= 3
    assert "SITIO_" not in kml_data
    assert "Sitio inferido por coordenadas normalizadas." not in kml_data
    assert GUIA_SITIOS_INFERIDOS_KML not in kml_data


# --- 20. Mismo sitio con celdas distintas conserva atributos por activación

def test_kml_mismo_sitio_celdas_distintas_conserva_atributos_por_activacion():
    df = _df_sin_antena(
        [(LAT_SV, LON_SV), (LAT_SV, LON_SV)],
        celda=["1001", "2002"],
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert "1001" in kml_data
    assert "2002" in kml_data


# --- Fallback: sin columna antena_analitica (llamador legado) --------------

def test_kml_fallback_sin_columna_antena_analitica_no_usa_literal_antena():
    """Si el DataFrame no pasó por agregar_sitio_analitico (llamador legado,
    p.ej. un script que arma el KML directamente), el generador debe seguir
    resolviendo un identificador neutral por coordenadas en vez del literal
    genérico "Antena" para dos puntos sin antena en coordenadas distintas."""
    df = pd.DataFrame({
        "fecha": ["01/01/2025", "01/01/2025"],
        "hora": ["10:00:00", "11:00:00"],
        "antena": [None, None],
        "lat": [LAT_SV, LAT_SV_2],
        "long": [LON_SV, LON_SV_2],
    })
    with tempfile.TemporaryDirectory() as tmp_dir:
        kml_data = _generar_y_extraer(df, tmp_dir)
    assert f"<name>{SITIO_SV}</name>" in kml_data
    assert f"<name>{SITIO_SV_2}</name>" in kml_data
    assert "<name>Antena</name>" not in kml_data
