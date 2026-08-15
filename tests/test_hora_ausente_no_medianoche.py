"""MICROBLOQUE F3.1 — Una hora ausente/no mapeada no debe convertirse en 00:00:00.

Caso real que originó el hallazgo: fecha mapeada, hora deliberadamente sin
mapear (contacto/tipo/duración también ausentes). La tabla HTML de
"Interacciones" mostraba "No disponible" para contacto/tipo/duración, pero
"hora" aparecía como "00:00:00" — un valor inventado a partir del ancla
interna de fecha (medianoche), no de la fuente original.

Causa raíz (dos puntos independientes, ambos corregidos aquí):

1. ``interacciones_builder._fmt_hora`` caía a formatear ``_dt``
   (derivado de ``datetime_evento``/fecha) como si fuera la hora observada
   cuando no había columna de hora mapeada. ``datetime_evento`` a
   medianoche es solo un ancla de orden por fecha (ver
   ``normalize_temporal_fields`` CASO C) — nunca una hora real.

2. ``normalize_temporal_fields`` (CASO B: fecha+hora como columnas
   separadas) y ``time_utils.to_datetime_series`` dejaban
   ``datetime_evento``/``_dt`` en NaT para cualquier fila cuya celda de
   hora estuviera vacía/NaN, aunque la fecha fuera válida — lo que hacía
   desaparecer esa fila entera de las agrupaciones por fecha (p.ej. la
   tabla de interacciones del día), en vez de conservarla con la hora
   marcada como ausente.
"""
from __future__ import annotations

import re

import pandas as pd

from tz_core.bitacora_normalization import normalize_temporal_fields
from tz_core.html.antennas import build_antennas_by_hour_section
from tz_core.interacciones_builder import construir_seccion_interacciones

TEXTO_HORA_NO_DISPONIBLE = (
    "Información de hora no disponible en esta bitácora. "
    "Análisis por rango horario no generado."
)


def _hora_td_por_contacto(html: str, contacto: str) -> str:
    """Extrae el contenido de la celda 'hora' de la fila cuyo contacto coincide."""
    m = re.search(
        r'<td class="mono">\d+</td><td>' + re.escape(contacto) +
        r'</td><td class="mono nowrap">([^<]*)</td>',
        html,
    )
    assert m, f"No se encontró fila de tabla para contacto {contacto!r} en el HTML"
    return m.group(1)


# ── 1. fecha válida + hora NO mapeada (columna 'hora' ausente) ─────────────

def test_hora_no_mapeada_muestra_no_disponible_no_medianoche():
    df = pd.DataFrame({
        "fecha": ["2026-08-01"],
        "contacto": ["70011111"],
    })
    html = construir_seccion_interacciones(df, config={})

    assert "00:00:00" not in html
    assert _hora_td_por_contacto(html, "70011111") == "No disponible"


# ── 2. hora real 00:00:00 se conserva y se muestra ──────────────────────────

def test_hora_real_medianoche_se_conserva():
    df = pd.DataFrame({
        "fecha": ["2026-08-01"],
        "hora": ["00:00:00"],
        "contacto": ["70011111"],
    })
    html = construir_seccion_interacciones(df, config={})

    assert _hora_td_por_contacto(html, "70011111") == "00:00:00"


# ── 3. columna 'hora' presente pero celda vacía/NaN en una fila ────────────

def test_columna_hora_presente_celda_vacia_no_disponible_y_fila_no_desaparece():
    df = pd.DataFrame({
        "fecha": ["2026-08-01"],
        "hora": [None],
        "contacto": ["70011111"],
    })
    html = construir_seccion_interacciones(df, config={})

    assert "00:00:00" not in html
    assert _hora_td_por_contacto(html, "70011111") == "No disponible"


# ── 4. mezcla: una fila con 00:00:00 real y otra sin hora ──────────────────

def test_mezcla_medianoche_real_y_hora_ausente_se_distinguen():
    df = pd.DataFrame({
        "fecha": ["2026-08-01", "2026-08-01"],
        "hora": ["00:00:00", None],
        "contacto": ["70011111", "70022222"],
    })
    html = construir_seccion_interacciones(df, config={})

    assert html.count("00:00:00") == 1
    assert _hora_td_por_contacto(html, "70011111") == "00:00:00"
    assert _hora_td_por_contacto(html, "70022222") == "No disponible"


# ── 5. no regresión: fecha+hora válidas mantienen comportamiento actual ────

def test_fecha_y_hora_validas_comportamiento_intacto():
    df = pd.DataFrame({
        "fecha": ["2026-08-01"],
        "hora": ["08:15:30"],
        "contacto": ["70011111"],
    })
    html = construir_seccion_interacciones(df, config={})

    assert _hora_td_por_contacto(html, "70011111") == "08:15:30"


# ── 6. normalize_temporal_fields (CASO B): hora vacía en una fila no borra
#      la fila de datetime_evento; se ancla a la fecha, no queda en NaT ────

def test_normalize_temporal_fields_hora_vacia_no_deja_datetime_evento_en_nat():
    df = pd.DataFrame({
        "fecha": ["01/08/2026", "01/08/2026"],
        "hora": ["09:00:00", ""],
    })
    result = normalize_temporal_fields(df)

    assert result["datetime_evento"].notna().all(), (
        "Una fila con fecha válida pero hora vacía debe conservar "
        "datetime_evento anclado a la fecha, no NaT — de lo contrario "
        "desaparece de las agrupaciones por fecha aguas abajo."
    )
    assert result["datetime_evento"].iloc[0].hour == 9
    assert result["datetime_evento"].iloc[1].hour == 0
    # La ausencia real de hora se conserva en la columna 'hora' original.
    assert result["hora"].iloc[1] == ""


# ── 7. análisis horario: datetime_evento a medianoche no se interpreta
#      como hora real ni se clasifica como "Madrugada" ─────────────────────

def test_antenas_por_rango_horario_ignora_datetime_evento_sintetico():
    df = pd.DataFrame({
        "antena": ["ANT-A", "ANT-B"],
        "fecha": ["01/08/2026", "02/08/2026"],
        "lat": [13.6929, 13.7100],
        "long": [-89.2182, -89.2300],
        "azimut": [45, 180],
    })
    df = normalize_temporal_fields(df)
    assert "hora" not in df.columns
    assert df["datetime_evento"].notna().all()

    html = build_antennas_by_hour_section(df, config=None, overrides=None)

    assert TEXTO_HORA_NO_DISPONIBLE in html
    assert "Madrugada (00:00" not in html
