"""HITO 2B — Integración de antena_analitica/sitio_inferido en historial de
cambios y KPI/resumen ejecutivo, y consistencia transversal del identificador
de sitio inferido entre HTML, KML, historial y KPI.

Cubre los casos 9-16 de la lista obligatoria del hito.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from tz_core.analytics import generar_historial_cambios_antena
from tz_core.html.antennas import build_antennas_table
from tz_core.html.assembler import generar_informe_html
from tz_core.html.kpi import generate_kpi_section, prepare_report_metrics
from tz_core.site_inference import agregar_sitio_analitico, construir_identificador_sitio

LAT_A, LON_A = 13.559339, -88.433997
LAT_B, LON_B = 13.7, -89.2
SITIO_A = construir_identificador_sitio(LAT_A, LON_A)
SITIO_B = construir_identificador_sitio(LAT_B, LON_B)


def _bitacora_sin_antena_con_saltos() -> pd.DataFrame:
    """Fixture realista sin columna 'antena' útil: coordenadas repetidas
    (permanencia), coordenadas distintas (cambio de sitio), azimuts
    distintos y varias fechas/horas."""
    df = pd.DataFrame({
        "fecha_hora": [
            "2025-01-01 08:00:00",
            "2025-01-01 09:00:00",
            "2025-01-01 10:00:00",
            "2025-01-02 08:00:00",
            "2025-01-02 09:00:00",
        ],
        "antena": [None, None, None, None, None],
        "lat": [LAT_A, LAT_A, LAT_B, LAT_B, LAT_A],
        "long": [LON_A, LON_A, LON_B, LON_B, LON_A],
        "azimut": [10, 15, 200, 205, 12],
    })
    return agregar_sitio_analitico(df)


# --- 9. Historial usa antena_analitica --------------------------------------

def test_historial_usa_antena_analitica():
    df = _bitacora_sin_antena_con_saltos()
    saltos = generar_historial_cambios_antena(df, max_saltos=100)
    assert saltos, "antena vacía + coordenadas debe producir historial vía antena_analitica"
    for salto in saltos:
        assert salto["origen"] in (SITIO_A, SITIO_B)
        assert salto["destino"] in (SITIO_A, SITIO_B)


# --- 10. Historial reconoce permanencia en el mismo sitio -------------------

def test_historial_reconoce_permanencia_mismo_sitio():
    df = _bitacora_sin_antena_con_saltos()
    saltos = generar_historial_cambios_antena(df, max_saltos=100)
    # 5 filas -> 4 transiciones; solo 2 son cambio real de sitio (A->B, B->A).
    # Las transiciones dentro del mismo sitio (fila 1->2 y 3->4) son
    # permanencia y no deben generar una entrada de salto.
    assert len(saltos) == 2


# --- 11. Historial reconoce cambio entre sitios distintos -------------------

def test_historial_reconoce_cambio_entre_sitios_distintos():
    df = _bitacora_sin_antena_con_saltos()
    saltos = generar_historial_cambios_antena(df, max_saltos=100)
    assert saltos[0]["origen"] == SITIO_A
    assert saltos[0]["destino"] == SITIO_B
    assert saltos[0]["origen_inferido"] is True
    assert saltos[0]["destino_inferido"] is True

    assert saltos[1]["origen"] == SITIO_B
    assert saltos[1]["destino"] == SITIO_A


# --- 12. Cálculo Haversine sigue correcto ------------------------------------

def test_historial_distancia_haversine_sigue_correcta():
    df = _bitacora_sin_antena_con_saltos()
    saltos = generar_historial_cambios_antena(df, max_saltos=100)

    lon1, lat1, lon2, lat2 = map(math.radians, [LON_A, LAT_A, LON_B, LAT_B])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    esperado_km = 6371 * (2 * math.asin(math.sqrt(a)))

    assert saltos[0]["distancia_km"] == pytest.approx(esperado_km, abs=0.01)


# --- Extra: no afirma torres distintas cuando comparten coordenadas --------

def test_historial_no_afirma_torres_distintas_en_mismas_coordenadas():
    """Una fila con antena real y otra sin antena, en las MISMAS coordenadas,
    producen identificadores de texto distintos (antena real vs. SITIO_...)
    pero deben reflejar distancia ~0, nunca una distancia positiva que
    sugiera torres físicamente distintas."""
    df = pd.DataFrame({
        "fecha_hora": ["2025-03-01 08:00:00", "2025-03-01 09:00:00"],
        "antena": ["Torre Real", None],
        "lat": [LAT_A, LAT_A],
        "long": [LON_A, LON_A],
    })
    df = agregar_sitio_analitico(df)
    assert df.loc[0, "antena_analitica"] == "Torre Real"
    assert df.loc[1, "antena_analitica"] == SITIO_A

    saltos = generar_historial_cambios_antena(df, max_saltos=100)
    assert len(saltos) == 1
    assert saltos[0]["origen"] != saltos[0]["destino"]
    assert saltos[0]["distancia_km"] is not None
    assert saltos[0]["distancia_km"] == pytest.approx(0.0, abs=1e-6)


# --- Título del historial cambia solo cuando hay sitios inferidos ----------

def test_historial_titulo_cambia_solo_con_sitios_inferidos(tmp_path):
    df_inferido = _bitacora_sin_antena_con_saltos()
    html_path = generar_informe_html(
        df=df_inferido,
        archivo_kml=str(tmp_path / "no_existe.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="hist_inferido",
        config={},
    )
    html = Path(html_path).read_text(encoding="utf-8")
    assert "<h2>Historial de cambios de antena/sitio</h2>" in html
    assert "Inferido por coordenadas" in html

    df_real = pd.DataFrame({
        "fecha_hora": ["2025-01-01 08:00:00", "2025-01-01 09:00:00"],
        "antena": ["Distrito Italia", "Apopa II"],
        "lat": [LAT_A, LAT_B],
        "long": [LON_A, LON_B],
    })
    df_real = agregar_sitio_analitico(df_real)
    assert not df_real["sitio_inferido"].any()
    html_path_real = generar_informe_html(
        df=df_real,
        archivo_kml=str(tmp_path / "no_existe2.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="hist_real",
        config={},
    )
    html_real = Path(html_path_real).read_text(encoding="utf-8")
    assert "<h2>Historial de cambios de antena</h2>" in html_real
    assert "<h2>Historial de cambios de antena/sitio</h2>" not in html_real


# --- 13/14/15. KPI cuenta sitios inferidos, no placeholders, etiqueta condicional

def test_kpi_cuenta_sitios_inferidos_como_unicos(tmp_path):
    df = _bitacora_sin_antena_con_saltos()  # 2 sitios inferidos distintos (A, B)
    metrics = prepare_report_metrics(df, str(tmp_path / "no_existe.kml"), str(tmp_path))
    assert metrics["ant_uniq"] == 2
    assert metrics["hay_sitio_inferido"] is True


def test_kpi_no_cuenta_placeholders(tmp_path):
    df = pd.DataFrame({
        "fecha_hora": ["2025-01-01 08:00:00"] * 3,
        "antena": ["SIN DETERMINAR", "-", None],
        "lat": [LAT_A, LAT_A, LAT_A],
        "long": [LON_A, LON_A, LON_A],
    })
    df = agregar_sitio_analitico(df)
    # Los tres placeholders/ausencias colapsan al mismo sitio inferido por coordenadas.
    metrics = prepare_report_metrics(df, str(tmp_path / "no_existe.kml"), str(tmp_path))
    assert metrics["ant_uniq"] == 1
    assert metrics["top_antena"] == SITIO_A


def test_kpi_etiqueta_antenas_sitios_solo_cuando_aplica():
    html_con_sitio = generate_kpi_section(10, 8, 2, 2, 3, "Celdas", "X", 5, 50.0, hay_sitio_inferido=True)
    assert "Antenas/Sitios únicos" in html_con_sitio
    assert "<div class=\"label\">Antenas únicas</div>" not in html_con_sitio

    html_sin_sitio = generate_kpi_section(10, 8, 2, 2, 3, "Celdas", "X", 5, 50.0, hay_sitio_inferido=False)
    assert "<div class=\"label\">Antenas únicas</div>" in html_sin_sitio
    assert "Antenas/Sitios únicos" not in html_sin_sitio


# --- 16. Identificador coincide en HTML/KML/historial/KPI -------------------

def test_identificador_coincide_en_html_kml_historial_kpi(tmp_path):
    from tz_core.kml_generator import generar_kml
    import tempfile
    import zipfile

    df = _bitacora_sin_antena_con_saltos()

    # HTML (tabla de antenas)
    html_tabla = build_antennas_table(df)
    assert SITIO_A in html_tabla
    assert SITIO_B in html_tabla

    # KML/KMZ
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_kml = str(Path(tmp_dir) / "consist.kml")
        generar_kml(df, out_kml, config={}, flat=False)
        kmz_path = str(Path(out_kml).with_suffix(".kmz"))
        with zipfile.ZipFile(kmz_path, "r") as archive:
            name = next(n for n in archive.namelist() if n.lower().endswith(".kml"))
            kml_data = archive.read(name).decode("utf-8", errors="ignore")
    assert f"<name>{SITIO_A}</name>" in kml_data
    assert f"<name>{SITIO_B}</name>" in kml_data

    # Historial
    saltos = generar_historial_cambios_antena(df, max_saltos=100)
    identificadores_historial = {salto["origen"] for salto in saltos} | {salto["destino"] for salto in saltos}
    assert identificadores_historial == {SITIO_A, SITIO_B}

    # KPI
    metrics = prepare_report_metrics(df, str(tmp_path / "no_existe.kml"), str(tmp_path))
    assert metrics["ant_uniq"] == 2
