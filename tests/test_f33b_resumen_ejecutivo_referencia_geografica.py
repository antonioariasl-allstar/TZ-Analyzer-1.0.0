"""MICROBLOQUE F3.3B — Mejora narrativa del HTML: Resumen ejecutivo enriquecido
con datos de la antena/sitio top (coordenadas, activaciones, azimut dominante,
Dirección) y sustitución de la nota "Movilidad" por "Referencia geográfica" en
la sección de interacciones filtradas por fecha.

No modifica lógica analítica central: reutiliza `top_antena`/`top_count`
(fuente canónica en tz_core/html/kpi.py) y el mismo `col_antena` (prioriza
`antena_analitica`) que ya usa tz_core/interacciones_builder.py para el
cálculo de distancia entre las dos antenas/sitios con más activaciones.
"""
import pandas as pd

from tz_core.html import assembler as asm
from tz_core.interacciones_builder import construir_seccion_interacciones


# ───────────────────────────────────────────────────────────────────────────
# Resumen ejecutivo — antena/sitio top enriquecido
# ───────────────────────────────────────────────────────────────────────────

def test_resumen_antena_explicita_coords_activaciones_azimut_direccion():
    df = pd.DataFrame({
        "antena": ["VTRIUN", "VTRIUN", "VTRIUN"],
        "lat": [13.559339, 13.559339, 13.559339],
        "long": [-88.433997, -88.433997, -88.433997],
        "azimut": [40, 40, 90],
        "direccion": ["Colonia Escalón, San Salvador"] * 3,
    })
    html = asm._construir_resumen_ejecutivo(
        total=3, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=3,
    )
    assert (
        "La antena con mayor número de activaciones fue <strong>VTRIUN</strong>, "
        "ubicada en las coordenadas 13.559339, -88.433997, con 3 activaciones."
    ) in html
    assert (
        "El azimut con mayor frecuencia de activación fue <strong>40°</strong>, "
        "registrado en 2 ocasiones."
    ) in html
    assert (
        "La dirección asociada corresponde a "
        "<strong>Colonia Escalón, San Salvador</strong>."
    ) in html


def test_resumen_sitio_inferido_con_coordenadas():
    sitio = "SITIO_13.700000_-89.200000"
    df = pd.DataFrame({
        "antena_analitica": [sitio, sitio],
        "sitio_inferido": [True, True],
        "lat": [13.7, 13.7],
        "long": [-89.2, -89.2],
    })
    html = asm._construir_resumen_ejecutivo(
        total=2, orden=[], metricas={}, df=df,
        top_antena=sitio, _log=lambda m: None, top_count=2,
    )
    assert "El sitio inferido con mayor número de activaciones fue" in html
    assert f"<strong>{sitio}</strong>, ubicada en las coordenadas 13.700000, -89.200000" in html
    assert "con 2 activaciones" in html
    assert "La antena con mayor número de activaciones" not in html


def test_resumen_sin_azimut_no_muestra_placeholder():
    df = pd.DataFrame({
        "antena": ["VTRIUN", "VTRIUN"],
        "lat": [13.559339, 13.559339],
        "long": [-88.433997, -88.433997],
    })
    html = asm._construir_resumen_ejecutivo(
        total=2, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=2,
    )
    assert "con 2 activaciones" in html
    assert "azimut" not in html.lower()
    assert "no disponible" not in html.lower()
    assert "sin inf" not in html.lower()


def test_resumen_sin_direccion_no_muestra_placeholder():
    df = pd.DataFrame({
        "antena": ["VTRIUN", "VTRIUN"],
        "lat": [13.559339, 13.559339],
        "long": [-88.433997, -88.433997],
        "azimut": [40, 40],
    })
    html = asm._construir_resumen_ejecutivo(
        total=2, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=2,
    )
    assert "dirección" not in html.lower()
    assert "no disponible" not in html.lower()


def test_resumen_azimut_dominante_con_empate_usa_regla_deterministica():
    # Empate 2 vs 2 entre 90 y 40: la regla determinista (mayor conteo, luego
    # azimut menor) debe escoger 40°, no depender del orden de aparición.
    df = pd.DataFrame({
        "antena": ["VTRIUN"] * 4,
        "lat": [13.559339] * 4,
        "long": [-88.433997] * 4,
        "azimut": [90, 90, 40, 40],
    })
    html = asm._construir_resumen_ejecutivo(
        total=4, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=4,
    )
    assert "El azimut con mayor frecuencia de activación fue <strong>40°</strong>" in html


def test_resumen_direccion_con_valores_vacios_no_filtra_placeholder():
    df = pd.DataFrame({
        "antena": ["VTRIUN", "VTRIUN", "VTRIUN"],
        "lat": [13.559339] * 3,
        "long": [-88.433997] * 3,
        "azimut": [40, 40, 40],
        "direccion": [None, "Sin Inf.", "Colonia Escalón, San Salvador"],
    })
    html = asm._construir_resumen_ejecutivo(
        total=3, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=3,
    )
    assert "NaN" not in html
    assert "None" not in html
    assert "Sin Inf" not in html
    assert (
        "La dirección asociada corresponde a "
        "<strong>Colonia Escalón, San Salvador</strong>."
    ) in html


def test_resumen_direccion_igual_a_antena_se_omite_por_redundancia():
    df = pd.DataFrame({
        "antena": ["VTRIUN", "VTRIUN"],
        "lat": [13.559339, 13.559339],
        "long": [-88.433997, -88.433997],
        "direccion": ["VTRIUN", "VTRIUN"],
    })
    html = asm._construir_resumen_ejecutivo(
        total=2, orden=[], metricas={}, df=df,
        top_antena="VTRIUN", _log=lambda m: None, top_count=2,
    )
    assert "dirección asociada" not in html.lower()


# ───────────────────────────────────────────────────────────────────────────
# Referencia geográfica (antes "Movilidad") — filtrado por fecha
# ───────────────────────────────────────────────────────────────────────────

def _df_dos_antenas(nombre_col_antena="antena", extra=None):
    base = {
        "fecha": ["01/03/2024"] * 4,
        "hora": ["08:00:00", "08:05:00", "08:10:00", "08:15:00"],
        "contacto": ["70011111", "70022222", "70033333", "70044444"],
        "duracion": [10, 20, 30, 40],
        nombre_col_antena: ["VTRIUN", "VTRIUN", "PANAM3", "PANAM3"],
        "lat": [13.559339, 13.559339, 13.700000, 13.700000],
        "long": [-88.433997, -88.433997, -88.300000, -88.300000],
    }
    if extra:
        base.update(extra)
    return pd.DataFrame(base)


def test_referencia_geografica_dos_antenas_explicitas():
    df = _df_dos_antenas()
    html = construir_seccion_interacciones(df, config={})

    assert "Referencia geográfica:" in html
    assert "las dos antenas con mayor número de activaciones del día fueron" in html
    assert "VTRIUN" in html and "PANAM3" in html
    assert "entre sí." in html

    # Redacción anterior eliminada por completo.
    assert "Movilidad" not in html
    assert "top 2 celdas del día" not in html
    assert "↔" not in html


def test_referencia_geografica_dos_sitios_inferidos():
    sitio_a = "SITIO_13.559339_-88.433997"
    sitio_b = "SITIO_13.700000_-88.300000"
    df = pd.DataFrame({
        "fecha": ["01/03/2024"] * 4,
        "hora": ["08:00:00", "08:05:00", "08:10:00", "08:15:00"],
        "contacto": ["70011111", "70022222", "70033333", "70044444"],
        "duracion": [10, 20, 30, 40],
        "antena_analitica": [sitio_a, sitio_a, sitio_b, sitio_b],
        "sitio_inferido": [True, True, True, True],
        "lat": [13.559339, 13.559339, 13.700000, 13.700000],
        "long": [-88.433997, -88.433997, -88.300000, -88.300000],
    })
    html = construir_seccion_interacciones(df, config={})

    assert "Referencia geográfica:" in html
    assert sitio_a in html and sitio_b in html
    assert "Movilidad" not in html


def test_referencia_geografica_una_sola_antena_no_fabrica_comparacion():
    df = _df_dos_antenas()
    df["antena"] = "VTRIUN"  # una sola antena en todo el día
    html = construir_seccion_interacciones(df, config={})

    assert "Referencia geográfica:" not in html
    assert "Movilidad" not in html


def test_referencia_geografica_distancia_aproximada_se_calcula():
    df = _df_dos_antenas()
    html = construir_seccion_interacciones(df, config={})

    import re
    m = re.search(r"distancia aproximada de ([\d.]+) km entre sí", html)
    assert m, "No se encontró la distancia aproximada en la Referencia geográfica"
    dist_km = float(m.group(1))
    assert dist_km > 2.0  # supera el umbral mínimo para mostrarse
