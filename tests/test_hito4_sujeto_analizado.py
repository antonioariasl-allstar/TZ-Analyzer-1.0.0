"""HITO 4 — Objeto analizado (teléfono/IMEI) en el filtro por fecha.

Cubre:
  16. El filtro por fecha muestra "Número analizado" cuando hay teléfono.
  17. Una bitácora por IMEI (sin teléfono) muestra "IMEI analizado".
  18. Sin teléfono ni IMEI, muestra "Identificador analizado: no disponible".
  19. Cada día muestra "Fecha seleccionada" y "Registros mostrados".
  20. El número/IMEI no se agrega como columna repetitiva en cada fila.
"""
from __future__ import annotations

import re

import pandas as pd

from tz_core.interacciones_builder import construir_seccion_interacciones


def _df(**cols) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    base = {
        "fecha": ["2026-08-01"] * n,
        "hora": [f"{8 + i:02d}:00:00" for i in range(n)],
        "contacto": [f"7001{i:04d}" for i in range(n)],
        "interaccion": ["LLAMADA"] * n,
    }
    base.update(cols)
    return pd.DataFrame(base)


def test_muestra_numero_analizado_cuando_hay_telefono():
    df = _df(tel=["68511697", "68511697"])
    html = construir_seccion_interacciones(df, config={})

    assert "Número analizado:</strong> 68511697" in html
    assert "Identificador analizado" not in html


def test_bitacora_imei_sin_telefono_muestra_imei_analizado():
    df = _df(imei=["865590080586567", "865590080586567"])
    html = construir_seccion_interacciones(df, config={})

    assert "IMEI analizado:</strong> 865590080586567" in html
    assert "Número analizado" not in html
    assert "Identificador analizado" not in html


def test_sin_telefono_ni_imei_muestra_identificador_no_disponible():
    df = _df(contacto=["70011111", "70022222"])
    html = construir_seccion_interacciones(df, config={})

    assert "Identificador analizado:</strong> no disponible" in html
    assert "Número analizado" not in html
    assert "IMEI analizado" not in html


def test_con_telefono_e_imei_prioriza_telefono_y_muestra_imei_secundario():
    df = _df(tel=["68511697", "68511697"], imei=["865590080586567", "865590080586567"])
    html = construir_seccion_interacciones(df, config={})

    assert "Número analizado:</strong> 68511697" in html
    assert "IMEI: 865590080586567" in html


def test_muestra_fecha_seleccionada_y_registros_mostrados():
    df = _df(tel=["68511697", "68511697", "68511697"])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"Fecha seleccionada:</strong>\s*01/08/2026", html)
    assert re.search(r"Registros mostrados:</strong>\s*3", html)


def test_telefono_e_imei_float_con_sufijo_punto_cero():
    """El IMEI leído como float de pandas (ej. 352971685312360.0) no debe
    mostrar el sufijo ".0" en la línea secundaria, igual que en Metadatos."""
    df = _df(tel=["68511697", "68511697"], imei=[352971685312360.0, 352971685312360.0])
    html = construir_seccion_interacciones(df, config={})

    assert "IMEI: 352971685312360</p>" in html
    assert "352971685312360.0" not in html


def test_solo_imei_float_con_sufijo_punto_cero():
    """Bitácora sin teléfono, con IMEI float .0: la línea principal no debe
    arrastrar el sufijo ".0"."""
    df = _df(imei=[352971685312360.0, 352971685312360.0])
    html = construir_seccion_interacciones(df, config={})

    assert "IMEI analizado:</strong> 352971685312360</p>" in html
    assert "352971685312360.0" not in html


def test_imei_string_limpio_no_se_altera():
    """Un IMEI que ya llega como string limpio se conserva igual."""
    df = _df(imei=["865590080586567", "865590080586567"])
    html = construir_seccion_interacciones(df, config={})

    assert "IMEI analizado:</strong> 865590080586567</p>" in html


def test_imei_ausente_no_muestra_sufijo_ni_columna():
    """Sin columna de IMEI significativa, se conserva el mensaje de identificador
    no disponible (no regresión)."""
    df = _df(contacto=["70011111", "70022222"])
    html = construir_seccion_interacciones(df, config={})

    assert "Identificador analizado:</strong> no disponible" in html
    assert "Número analizado" not in html
    assert "IMEI analizado" not in html


def test_sujeto_no_se_repite_como_columna_por_fila():
    """El número/IMEI analizado se muestra una sola vez a nivel de sección,
    no como una columna repetida en la tabla de detalle por fila."""
    df = _df(tel=["68511697", "68511697"])
    html = construir_seccion_interacciones(df, config={})

    thead_match = re.search(r"<thead>(.*?)</thead>", html, re.S)
    assert thead_match, "No se encontró el encabezado de la tabla de detalle."
    thead = thead_match.group(1)
    assert "tel" not in thead.lower()
    assert "número" not in thead.lower() and "numero" not in thead.lower()
