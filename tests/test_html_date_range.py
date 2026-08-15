"""MICROBLOQUE F3.1B — "Periodo analizado" no debe fabricar horas.

``prepare_report_metrics`` (tz_core/html/kpi.py) construye ``rango_str`` con
precisión HH:MM únicamente cuando TODAS las filas con fecha válida tienen una
hora real (columna 'hora', criterio ``es_valor_significativo``) y parseable.
En cualquier otro caso (sin columna 'hora', hora ausente/vacía en alguna
fila, o mezcla de filas con/sin hora) se degrada a precisión de fecha
solamente — sin inventar 00:00 ni 23:59.

``datetime_evento`` sigue usándose para ubicar la fecha (ordenar/agrupar) de
las filas relevantes, pero nunca para decidir si existe precisión horaria.
"""
import re

import pandas as pd

from tz_core.bitacora_normalization import normalize_temporal_fields
from tz_core.html import assembler as asm
from tz_core.html.kpi import prepare_report_metrics
from tz_core.html.metadata import generate_metadata_section


# ── CASO A: fecha + hora real en todas las filas ────────────────────────────

def test_html_range_prefers_datetime_evento_and_preserves_may_to_july(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2026-05-01 00:00:00", "2026-07-28 00:00:00"],
        "hora": ["09:00:14", "17:16:31"],
        "datetime_evento": pd.to_datetime([
            "2026-05-01 09:00:14",
            "2026-07-28 17:16:31",
        ]),
        "lat": [13.67560667, 13.663242],
        "long": [-89.27647667, -89.248115],
        "antena": ["INCATE", "CTMSEL"],
    })

    metrics = prepare_report_metrics(
        df,
        archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path),
        config={},
    )

    assert metrics["rango_str"] == (
        "01/05/2026 09:00 — 28/07/2026 17:16"
    )


# ── CASO B: fecha válida sin columna 'hora' en absoluto ─────────────────────

def test_rango_fecha_sin_columna_hora_muestra_solo_fecha(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "antena": ["ANT-A", "ANT-B"],
        "lat": [13.69, 13.71],
        "long": [-89.21, -89.23],
    })
    df = normalize_temporal_fields(df)
    assert "hora" not in df.columns

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )

    assert metrics["rango_str"] == "01/08/2026 — 02/08/2026"


# ── CASO C: mezcla — una fila con hora real, otra sin hora ─────────────────

def test_rango_mezcla_hora_real_y_ausente_degrada_a_solo_fecha(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "hora": ["23:50:00", None],
        "antena": ["ANT-A", "ANT-B"],
        "lat": [13.69, 13.71],
        "long": [-89.21, -89.23],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )

    assert metrics["rango_str"] == "01/08/2026 — 02/08/2026"
    assert "23:50" not in metrics["rango_str"]


# ── CASO D: medianoche REAL en todas las filas relevantes ──────────────────

def test_rango_medianoche_real_en_todas_las_filas_se_conserva(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "hora": ["00:00:00", "00:00:00"],
        "antena": ["ANT-A", "ANT-B"],
        "lat": [13.69, 13.71],
        "long": [-89.21, -89.23],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )

    assert metrics["rango_str"] == "01/08/2026 00:00 — 02/08/2026 00:00"


# ── CASO E: columna 'hora' presente pero con NaN en una fila ───────────────

def test_rango_columna_hora_con_nan_en_una_fila_degrada_a_solo_fecha(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "hora": ["08:00:00", None],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )

    assert metrics["rango_str"] == "01/08/2026 — 02/08/2026"


# ── No debe fabricarse ninguna hora cuando la hora está ausente ────────────

def test_rango_sin_hora_no_inventa_00_00_ni_23_59(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "05/08/2026"],
        "antena": ["ANT-A", "ANT-B"],
        "lat": [13.69, 13.71],
        "long": [-89.21, -89.23],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )

    assert "00:00" not in metrics["rango_str"]
    assert "23:59" not in metrics["rango_str"]


# ── Resumen ejecutivo: sin regresión con rango de solo fecha ───────────────

def test_resumen_ejecutivo_sin_regresion_con_rango_solo_fecha():
    html = asm._construir_resumen_ejecutivo(
        total=25, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None,
        rango_str="01/08/2026 — 05/08/2026",
        tel_val="70011111",
    )
    assert "número 70011111" in html
    assert "del 01/08/2026 al 05/08/2026" in html
    assert "<strong>25</strong> interacciones" in html
    assert "00:00" not in html


# ── Metadata: "Periodo analizado" recibe el rango correcto ─────────────────

def test_metadata_periodo_analizado_sin_hora_no_muestra_medianoche(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "antena": ["ANT-A", "ANT-B"],
        "lat": [13.69, 13.71],
        "long": [-89.21, -89.23],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )
    html = generate_metadata_section(
        "bitacora.xlsx", "Hoja1", metrics["rango_str"], ""
    )

    assert "00:00" not in html
    assert re.search(
        r"Periodo analizado:</b></td><td class=\"mono\">01/08/2026 — 02/08/2026",
        html,
    )


def test_metadata_periodo_analizado_con_hora_real_conserva_hh_mm(tmp_path):
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "02/08/2026"],
        "hora": ["08:15:00", "17:42:00"],
    })
    df = normalize_temporal_fields(df)

    metrics = prepare_report_metrics(
        df, archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path), config={},
    )
    html = generate_metadata_section(
        "bitacora.xlsx", "Hoja1", metrics["rango_str"], ""
    )

    assert "08:15" in html
    assert "17:42" in html
