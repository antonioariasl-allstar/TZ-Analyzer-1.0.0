"""Antenas sin columna 'hora' — corrección de AttributeError en build_antennas_table.

Bug: cuando el DataFrame tiene columna 'antena' y 'fecha' pero carece por
completo de la columna 'hora', build_antennas_table (tz_core/html/antennas.py)
llamaba a `df_a.get("hora", "").astype(str)`. `DataFrame.get` con clave
ausente devuelve el valor por defecto literal (`""`, un str de Python, no una
Series), y `str` no tiene `.astype`, produciendo:

    AttributeError: 'str' object has no attribute 'astype'

El pipeline normal nunca expone este defecto porque etapas previas
(mapping_wizard.py, manual_mode.py, kml_generator.py) siempre garantizan que
la columna 'hora' exista (aunque sea rellena con el placeholder "Sin Inf.")
antes de que el DataFrame llegue a tz_core/html/antennas.py. El defecto solo
se manifiesta en llamadas directas a build_antennas_table/generar_informe_html
que se salten esa normalización previa.

build_antennas_by_hour_section ya manejaba correctamente la ausencia total
de 'hora' (devuelve el mensaje declarativo "Información de hora no disponible
en esta bitácora. Análisis por rango horario no generado."); estos casos
verifican que ese comportamiento se mantenga intacto y que la tabla general/
Top de antenas ya no aborten.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tz_core.html.antennas import (
    build_antennas_by_hour_section,
    build_antennas_table,
    build_top_antennas_section,
)
from tz_core.html.assembler import generar_informe_html

TEXTO_HORA_NO_DISPONIBLE = (
    "Información de hora no disponible en esta bitácora. "
    "Análisis por rango horario no generado."
)


def _df_antena_sin_hora() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "antena": ["ANT-A", "ANT-A", "ANT-B"],
            "fecha": ["2026-08-01", "2026-08-01", "2026-08-02"],
            "lat": [13.6929, 13.6929, 13.7100],
            "long": [-89.2182, -89.2182, -89.2300],
            "azimut": [45, 50, 180],
        }
    )


# ── 1. antena presente + hora ausente ───────────────────────────────────────

def test_antena_sin_hora_no_lanza_excepcion_y_tabla_existe():
    df = _df_antena_sin_hora()
    html = build_antennas_table(df)
    assert "ANT-A" in html and "ANT-B" in html


def test_antena_sin_hora_top_antenas_existe():
    df = _df_antena_sin_hora()
    html = build_top_antennas_section(df, config=None, overrides=None)
    assert "ANT-A" in html
    assert "Antenas con mayor número de activaciones" in html


def test_antena_sin_hora_rango_horario_declara_ausencia():
    df = _df_antena_sin_hora()
    html = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert TEXTO_HORA_NO_DISPONIBLE in html


# ── 2. antena presente + hora vacía (columna presente, sin valores útiles) ──

def test_antena_con_hora_vacia_no_lanza_excepcion():
    df = _df_antena_sin_hora()
    df["hora"] = ["", "", None]
    html = build_antennas_table(df)
    assert "ANT-A" in html and "ANT-B" in html

    top = build_top_antennas_section(df, config=None, overrides=None)
    assert "ANT-A" in top

    # No debe lanzar excepción ni fabricar rangos horarios inexistentes: o
    # declara ausencia explícitamente, o el desglose por rango se omite
    # (ninguna franja horaria con conteo > 0), pero nunca se inserta un
    # marcador tipo "Sin Inf." como si fuera una hora válida.
    rango = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert "Sin Inf." not in rango
    assert "Madrugada (00:00" not in rango
    assert "Mañana (06:00" not in rango
    assert "Tarde (12:00" not in rango
    assert "Noche (18:00" not in rango


# ── 3. antena presente + hora válida: comportamiento intacto ───────────────

def test_antena_con_hora_valida_comportamiento_intacto():
    df = _df_antena_sin_hora()
    df["hora"] = ["08:15:00", "09:40:00", "18:05:00"]

    html = build_antennas_table(df)
    assert "ANT-A" in html and "ANT-B" in html

    rango = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert TEXTO_HORA_NO_DISPONIBLE not in rango
    assert "ANT-A" in rango and "ANT-B" in rango
    assert "Mañana (06:00" in rango
    assert "Noche (18:00" in rango


# ── 4. antena ausente + hora ausente ────────────────────────────────────────

def test_sin_antena_sin_hora_declara_antena_no_disponible():
    df = pd.DataFrame(
        {
            "fecha": ["2026-08-01", "2026-08-02"],
            "lat": [13.6929, 13.71],
            "long": [-89.2182, -89.23],
        }
    )
    html = build_antennas_table(df)
    assert "Campo de antena no disponible en esta bitácora." in html

    top = build_top_antennas_section(df, config=None, overrides=None)
    assert "no mapeado" in top

    rango = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert "no mapeado" in rango


# ── 5. sitio inferido + hora ausente ────────────────────────────────────────

def test_sitio_inferido_sin_hora_tabla_visible_y_rango_no_disponible():
    from tz_core.site_inference import agregar_sitio_analitico

    df = pd.DataFrame(
        {
            "fecha": ["2026-08-01", "2026-08-01", "2026-08-02"],
            "antena": [None, None, None],
            "lat": [13.559339, 13.559339, 13.7],
            "long": [-88.433997, -88.433997, -89.2],
            "azimut": [10, 15, 200],
        }
    )
    df = agregar_sitio_analitico(df)
    assert "hora" not in df.columns

    tabla = build_antennas_table(df)
    assert "SITIO_" in tabla
    assert "Antena/Sitio" in tabla

    rango = build_antennas_by_hour_section(df, config=None, overrides=None)
    assert TEXTO_HORA_NO_DISPONIBLE in rango


# ── 6. llamada directa a generar_informe_html no falla ─────────────────────

def test_generar_informe_html_directo_sin_hora_no_falla(tmp_path: Path):
    df = _df_antena_sin_hora()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="antenas_sin_hora",
        hoja=None,
        nombre_bitacora=None,
        config={},
    )
    assert html_path
    contenido = Path(html_path).read_text(encoding="utf-8")
    assert "ANT-A" in contenido
    assert TEXTO_HORA_NO_DISPONIBLE in contenido


# ── 8. el texto declarativo aparece una sola vez ────────────────────────────

def test_texto_declarativo_hora_no_disponible_una_sola_vez(tmp_path: Path):
    df = _df_antena_sin_hora()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="antenas_sin_hora_unica",
        hoja=None,
        nombre_bitacora=None,
        config={},
    )
    contenido = Path(html_path).read_text(encoding="utf-8")
    assert contenido.count(TEXTO_HORA_NO_DISPONIBLE) == 1
