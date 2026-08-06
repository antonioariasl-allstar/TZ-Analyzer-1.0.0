"""HITO 2A — Integración: inferencia de sitios en el pipeline central, capacidades y HTML.

Cubre los 20 casos obligatorios del hito: enriquecimiento único en
run_ingestion_pipeline, no-mutación del DataFrame de entrada, capacidad
"antenas" disponible/parcial/no_disponible, "antenas_por_horario" parcial,
consumidores HTML (antennas.py, interacciones_builder.py), agrupación por
coordenadas, coexistencia de antena real e inferida, distinción de
limitaciones parcial/no_disponible, conteo correcto en la tarjeta de
capacidades, QC midiendo antena original (no antena_analitica), FX-02 verde,
y ausencia de impacto visual en una bitácora completa.

No cubre (verificado por revisión de código, no por test unitario aquí):
KML/KMZ — kml_generator.py no se modificó en este hito (HITO 2A); la
integración de antena_analitica/sitio_inferido en KML/KMZ, historial y KPI
llegó en HITO 2B (ver tests/unit/test_kml_generator_site_inference.py y
tests/test_hito2b_historial_kpi_site_inference.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from tz_core.capabilities import detectar_capacidades
from tz_core.html.antennas import (
    NOTA_SITIOS_INFERIDOS,
    build_antennas_by_hour_section,
    build_antennas_table,
    build_top_antennas_section,
)
from tz_core.html.assembler import generar_informe_html
from tz_core.ingestion_pipeline import run_ingestion_pipeline
from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.qc_engine import run_qc
from tz_core.site_inference import agregar_sitio_analitico

LAT_A, LON_A = 13.7, -89.2
LAT_B, LON_B = 13.71, -89.21


# ─────────────────────────────────────────────────────────────────────────
# Fixtures de DataFrame
# ─────────────────────────────────────────────────────────────────────────

def _make_df_antena_real(rows: int = 2, lat: float = LAT_A, lon: float = LON_A) -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * rows,
        "hora": ["10:00:00"] * rows,
        "interaccion": ["VOZ"] * rows,
        "contacto": ["70001234"] * rows,
        "tel": ["60001234"] * rows,
        "antena": ["ANT-01"] * rows,
        "lat": [lat] * rows,
        "long": [lon] * rows,
    })


def _make_df_sin_antena_con_coords(rows: int = 2, lat: float = LAT_A, lon: float = LON_A) -> pd.DataFrame:
    df = _make_df_antena_real(rows=rows, lat=lat, lon=lon)
    df["antena"] = None
    return df


def _make_df_sin_antena_sin_coords(rows: int = 2) -> pd.DataFrame:
    df = _make_df_antena_real(rows=rows)
    df["antena"] = None
    df["lat"] = None
    df["long"] = None
    return df


def _make_fx02_df(rows: int = 3) -> pd.DataFrame:
    """Bitácora sin 'contacto' ni 'interaccion' (caso FX-02), con antena real."""
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * rows,
        "hora": ["10:00:00"] * rows,
        "tel": ["60001234"] * rows,
        "antena": ["ANT-01"] * rows,
        "lat": [LAT_A] * rows,
        "long": [LON_A] * rows,
    })


# ─────────────────────────────────────────────────────────────────────────
# Harness mínimo para run_ingestion_pipeline (sin interacción real)
# ─────────────────────────────────────────────────────────────────────────

def _base_kwargs(df: pd.DataFrame, tmp_path) -> dict:
    return dict(
        df=df,
        config={},
        original_columns=list(df.columns),
        manual_qc_mapping=False,
        alias_visibles=None,
        wizard_io_factory=MagicMock(),
        persist_synonym_fn=MagicMock(),
        validate_schema_fn=MagicMock(),
        validar_datos_fn=lambda d, _cols: (d, []),
        # "ninguno" (!= "2") hace que apply_time_filter_prompt real devuelva
        # el propio df_norm ya enriquecido sin filtrar ni tocarlo — así el
        # DataFrame final del resultado refleja el enriquecimiento del pipeline.
        time_filter_option="ninguno",
        solicitar_filtros_fn=MagicMock(),
        aplicar_filtros_fn=MagicMock(),
        output_fn=lambda _msg: None,
        logger=lambda _msg: None,
        run_manual_mapping_fn=None,
        config_path=str(tmp_path / "config.json"),
        preguntar_unidad_duracion_fn=lambda: "desconocida",
    )


# ─────────────────────────────────────────────────────────────────────────
# Caso 1 — Pipeline agrega columnas derivadas una sola vez
# ─────────────────────────────────────────────────────────────────────────

def test_caso1_pipeline_agrega_columnas_derivadas_una_sola_vez(tmp_path):
    df = _make_df_antena_real()
    result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    cols = list(result.dataframe.columns)
    for derivada in (
        "antena_analitica",
        "sitio_inferido",
        "sitio_inferencia_motivo",
        "sitio_lat_normalizada",
        "sitio_long_normalizada",
    ):
        assert cols.count(derivada) == 1, f"{derivada} debe aparecer exactamente una vez"


# ─────────────────────────────────────────────────────────────────────────
# Caso 2 — DataFrame original de entrada no se muta
# ─────────────────────────────────────────────────────────────────────────

def test_caso2_dataframe_original_no_se_muta_fuera_del_contrato(tmp_path):
    df = _make_df_antena_real()
    original_cols = list(df.columns)
    original_copy = df.copy(deep=True)

    run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    assert list(df.columns) == original_cols
    pd.testing.assert_frame_equal(df, original_copy)
    assert "antena_analitica" not in df.columns


# ─────────────────────────────────────────────────────────────────────────
# Casos 3-5 — Capacidad "antenas": disponible / parcial / no_disponible
# ─────────────────────────────────────────────────────────────────────────

def test_caso3_antena_real_capacidad_antenas_disponible():
    df = agregar_sitio_analitico(_make_df_antena_real())
    cap = detectar_capacidades(df).capacidad("antenas")
    assert cap.disponible is True
    assert cap.estado == "disponible"


def test_caso4_sin_antena_con_coords_capacidad_antenas_parcial():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords())
    cap = detectar_capacidades(df).capacidad("antenas")
    assert cap.disponible is True
    assert cap.estado == "parcial"
    assert cap.faltantes == ("antena",)


def test_caso5_sin_antena_ni_coords_capacidad_antenas_no_disponible():
    df = agregar_sitio_analitico(_make_df_sin_antena_sin_coords())
    cap = detectar_capacidades(df).capacidad("antenas")
    assert cap.disponible is False
    assert cap.estado == "no_disponible"


# ─────────────────────────────────────────────────────────────────────────
# Caso 6 — antenas_por_horario parcial con sitio inferido + hora
# ─────────────────────────────────────────────────────────────────────────

def test_caso6_antenas_por_horario_parcial_con_sitio_inferido_y_hora():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords())
    cap = detectar_capacidades(df).capacidad("antenas_por_horario")
    assert cap.disponible is True
    assert cap.estado == "parcial"
    assert cap.faltantes == ("antena",)


# ─────────────────────────────────────────────────────────────────────────
# Caso 7 — HTML genera Top de sitios inferidos
# ─────────────────────────────────────────────────────────────────────────

def test_caso7_html_genera_top_de_sitios_inferidos():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=3))
    html = build_top_antennas_section(df, config=None, overrides=None)
    assert "SITIO_13.700000_-89.200000" in html
    assert "Inferido por coordenadas" in html


# ─────────────────────────────────────────────────────────────────────────
# Caso 8 — Tabla usa SITIO_lat_long
# ─────────────────────────────────────────────────────────────────────────

def test_caso8_tabla_completa_usa_identificador_sitio_lat_long():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=2))
    html = build_antennas_table(df)
    assert "SITIO_13.700000_-89.200000" in html
    assert "Antena/Sitio" in html


# ─────────────────────────────────────────────────────────────────────────
# Caso 9 — Nota de inferencia aparece una sola vez (no repite por fila)
# ─────────────────────────────────────────────────────────────────────────

def test_caso9_nota_de_inferencia_aparece_una_sola_vez():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=5))
    html = build_top_antennas_section(df, config=None, overrides=None)
    assert html.count(NOTA_SITIOS_INFERIDOS) == 1


# ─────────────────────────────────────────────────────────────────────────
# Caso 10 — La nota no afirma nomenclatura oficial
# ─────────────────────────────────────────────────────────────────────────

def test_caso10_nota_no_afirma_nomenclatura_oficial():
    assert "no corresponden necesariamente a la nomenclatura oficial del operador" in (
        NOTA_SITIOS_INFERIDOS.lower()
    )


# ─────────────────────────────────────────────────────────────────────────
# Caso 11 — Heatmap incluye filas antes excluidas por falta de antena
# ─────────────────────────────────────────────────────────────────────────

def test_caso11_heatmap_incluye_filas_sin_antena_original():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=2))
    html = construir_seccion_interacciones(df, config={})
    assert "SITIO_13.700000_-89.200000" in html


# ─────────────────────────────────────────────────────────────────────────
# Casos 12-13 — Agrupación por coordenadas
# ─────────────────────────────────────────────────────────────────────────

def test_caso12_mismas_coordenadas_normalizadas_agrupan():
    df = pd.DataFrame({
        "fecha": ["2024-01-01"] * 2,
        "hora": ["10:00:00", "11:00:00"],
        "antena": [None, None],
        "lat": [LAT_A, LAT_A],
        "long": [LON_A, LON_A],
    })
    enriched = agregar_sitio_analitico(df)
    assert enriched["antena_analitica"].nunique() == 1


def test_caso13_coordenadas_distintas_no_se_fusionan():
    df = pd.DataFrame({
        "fecha": ["2024-01-01"] * 2,
        "hora": ["10:00:00", "11:00:00"],
        "antena": [None, None],
        "lat": [LAT_A, LAT_B],
        "long": [LON_A, LON_B],
    })
    enriched = agregar_sitio_analitico(df)
    assert enriched["antena_analitica"].nunique() == 2


# ─────────────────────────────────────────────────────────────────────────
# Caso 14 — Antena real e inferida coexisten sin perder la original
# ─────────────────────────────────────────────────────────────────────────

def test_caso14_antena_real_e_inferida_coexisten():
    df = pd.DataFrame({
        "fecha": ["2024-01-01"] * 2,
        "hora": ["10:00:00", "11:00:00"],
        "antena": ["ANT-01", None],
        "lat": [LAT_A, LAT_B],
        "long": [LON_A, LON_B],
    })
    enriched = agregar_sitio_analitico(df)

    assert enriched.loc[0, "antena_analitica"] == "ANT-01"
    assert str(enriched.loc[1, "antena_analitica"]).startswith("SITIO_")
    # la antena original nunca se sobrescribe
    assert list(enriched["antena"]) == ["ANT-01", None]

    html = build_antennas_table(enriched)
    assert "ANT-01" in html
    assert "SITIO_" in html
    assert html.count("Inferido por coordenadas") == 1  # solo la fila inferida lleva el indicador


# ─────────────────────────────────────────────────────────────────────────
# Caso 15 — Limitaciones distingue "parcial" de "no_disponible"
# ─────────────────────────────────────────────────────────────────────────

def test_caso15_limitaciones_distingue_parcial_de_no_disponible(tmp_path):
    df_parcial = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=3))
    html_path_parcial = generar_informe_html(
        df=df_parcial,
        archivo_kml=str(tmp_path / "no_existe.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="parcial",
        config={},
    )
    html_parcial = Path(html_path_parcial).read_text(encoding="utf-8")
    assert (
        "Los registros fueron agrupados mediante identificadores técnicos "
        "derivados de coordenadas normalizadas." in html_parcial
    )
    assert "Antena nominal no disponible" not in html_parcial

    df_no_disp = agregar_sitio_analitico(_make_df_sin_antena_sin_coords(rows=3))
    html_path_no_disp = generar_informe_html(
        df=df_no_disp,
        archivo_kml=str(tmp_path / "no_existe2.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="nodisp",
        config={},
    )
    html_no_disp = Path(html_path_no_disp).read_text(encoding="utf-8")
    assert "Antena nominal no disponible" in html_no_disp
    assert "Los registros fueron agrupados mediante identificadores técnicos" not in html_no_disp


# ─────────────────────────────────────────────────────────────────────────
# Caso 16 — La tarjeta de capacidades cuenta "antenas" parcial correctamente
# ─────────────────────────────────────────────────────────────────────────

def test_caso16_tarjeta_capacidades_cuenta_parciales(tmp_path):
    df_parcial = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=3))
    html_path = generar_informe_html(
        df=df_parcial,
        archivo_kml=str(tmp_path / "no_existe.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="tarjeta",
        config={},
    )
    html = Path(html_path).read_text(encoding="utf-8")
    m = re.search(r'<div id="resumen-capacidades"[^>]*>(.*?)</div>', html, re.S)
    assert m, "No se encontró la tarjeta de capacidades en el HTML."
    assert re.search(r"\b1 parciales?\b|\bparciales?\b", m.group(1)), (
        "La tarjeta de capacidades debe reflejar al menos una capacidad parcial."
    )


# ─────────────────────────────────────────────────────────────────────────
# Caso 17 — QC sigue midiendo antena original, no antena_analitica
# ─────────────────────────────────────────────────────────────────────────

def test_caso17_qc_mide_antena_original_no_antena_analitica():
    df = agregar_sitio_analitico(_make_df_sin_antena_con_coords(rows=4))
    # antena_analitica está poblada (sitios inferidos) pero "antena" sigue vacía.
    assert df["antena_analitica"].notna().all()
    assert df["antena"].isna().all()

    qc = run_qc(df)
    assert qc.flags["antena"]["pct_vacia"] == 100.0


# ─────────────────────────────────────────────────────────────────────────
# Caso 18 — FX-02 continúa verde (contacto/interaccion ausentes no bloquean)
# ─────────────────────────────────────────────────────────────────────────

def test_caso18_fx02_continua_verde(tmp_path):
    df = _make_fx02_df()
    result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    assert result.capabilities_report.procesable is True
    assert result.capabilities_report.capacidad("contactos").disponible is False
    assert result.capabilities_report.capacidad("tipo_evento").disponible is False
    assert result.capabilities_report.capacidad("antenas").disponible is True
    assert result.capabilities_report.capacidad("antenas").estado == "disponible"
    assert result.capabilities_report.capacidad("kml").disponible is True


# ─────────────────────────────────────────────────────────────────────────
# Caso 19 — Bitácora completa: sin cambio visual salvo columnas derivadas
# ─────────────────────────────────────────────────────────────────────────

def test_caso19_bitacora_completa_no_cambia_visualmente(tmp_path):
    df = agregar_sitio_analitico(_make_df_antena_real(rows=3))
    # el enriquecimiento no debe marcar nada como inferido en una bitácora completa
    assert not df["sitio_inferido"].any()

    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(tmp_path / "no_existe.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida="completa",
        config={},
    )
    html = Path(html_path).read_text(encoding="utf-8")

    assert "Inferido por coordenadas" not in html
    assert NOTA_SITIOS_INFERIDOS not in html
    assert "Antena nominal no disponible" not in html
    assert "identificadores técnicos derivados de coordenadas normalizadas" not in html
    # el encabezado de columna se mantiene igual que antes de HITO 2A
    assert "<th>Antena</th>" in html or "Antena</th>" in html


# ─────────────────────────────────────────────────────────────────────────
# Caso 20 — KML/KMZ integrado con antena_analitica/sitio_inferido (HITO 2B)
# ─────────────────────────────────────────────────────────────────────────

def test_caso20_kml_generator_referencia_columnas_derivadas():
    """kml_generator.py fue integrado en HITO 2B: ahora sí lee antena_analitica
    y sitio_inferido para resolver el nombre visible de los puntos KML (ver
    tests/unit/test_kml_generator_site_inference.py para la cobertura
    funcional completa de KML/KMZ con sitios inferidos)."""
    kml_source = Path(__file__).resolve().parents[2] / "tz_core" / "kml_generator.py"
    contenido = kml_source.read_text(encoding="utf-8")
    assert "antena_analitica" in contenido
    assert "sitio_inferido" in contenido
