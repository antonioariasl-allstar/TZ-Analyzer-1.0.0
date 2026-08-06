"""HITO 1 — Inferencia de identidad analítica de sitio.

Cubre las reglas de tz_core/site_inference.py: prioridad antena real >
sitio inferido por coordenadas > nulo; normalización a 6 decimales;
agrupación/separación por coordenada; y el enriquecimiento puro de
DataFrame vía agregar_sitio_analitico().
"""
from __future__ import annotations

import pandas as pd

from tz_core.site_inference import (
    MOTIVO_ANTENA_ORIGINAL,
    MOTIVO_SIN_DATOS,
    MOTIVO_SITIO_INFERIDO,
    agregar_sitio_analitico,
    construir_identificador_sitio,
    normalizar_coordenada_sitio,
    resolver_sitio_analitico,
)

LAT_SV = 13.559339
LON_SV = -88.433997


# --- 1. antena real gana sobre coordenadas -----------------------------------

def test_antena_real_gana_sobre_coordenadas():
    r = resolver_sitio_analitico("Antena Real 01", LAT_SV, LON_SV)
    assert r.valor == "Antena Real 01"
    assert r.inferido is False
    assert r.motivo == MOTIVO_ANTENA_ORIGINAL


# --- 2. antena vacía + coords válidas genera SITIO_lat_long ------------------

def test_antena_vacia_con_coords_validas_genera_sitio():
    r = resolver_sitio_analitico("", LAT_SV, LON_SV)
    assert r.valor == "SITIO_13.559339_-88.433997"
    assert r.inferido is True
    assert r.motivo == MOTIVO_SITIO_INFERIDO


# --- 3. antena placeholder + coords válidas genera sitio ---------------------

def test_antena_placeholder_con_coords_validas_genera_sitio():
    for placeholder in ("SIN DETERMINAR", "N/A", "-", "s/i"):
        r = resolver_sitio_analitico(placeholder, LAT_SV, LON_SV)
        assert r.inferido is True, placeholder
        assert r.valor == "SITIO_13.559339_-88.433997"


# --- 4. columna antena ausente + coords válidas genera sitio -----------------

def test_columna_antena_ausente_con_coords_validas_genera_sitio():
    df = pd.DataFrame({"lat": [LAT_SV], "long": [LON_SV]})
    out = agregar_sitio_analitico(df)
    assert out.loc[0, "antena_analitica"] == "SITIO_13.559339_-88.433997"
    assert out.loc[0, "sitio_inferido"] is True or bool(out.loc[0, "sitio_inferido"]) is True
    assert out.loc[0, "sitio_inferencia_motivo"] == MOTIVO_SITIO_INFERIDO


# --- 5. misma pareja genera mismo identificador -------------------------------

def test_misma_pareja_coordenadas_genera_mismo_identificador():
    r1 = resolver_sitio_analitico(None, LAT_SV, LON_SV)
    r2 = resolver_sitio_analitico(None, LAT_SV, LON_SV)
    assert r1.valor == r2.valor


# --- 6. redondeo a seis decimales ---------------------------------------------

def test_redondeo_a_seis_decimales():
    assert normalizar_coordenada_sitio(13.55933949) == "13.559339"
    assert normalizar_coordenada_sitio(13.5593395) == "13.559340"  # ROUND_HALF_UP


# --- 7. valores que difieren después del sexto decimal agrupan ---------------

def test_diferencia_despues_del_sexto_decimal_agrupa():
    r1 = resolver_sitio_analitico(None, 13.5593391, -88.4339971)
    r2 = resolver_sitio_analitico(None, 13.5593394, -88.4339974)
    assert r1.valor == r2.valor == "SITIO_13.559339_-88.433997"


# --- 8. valores que difieren dentro de los primeros seis decimales separan ---

def test_diferencia_dentro_de_seis_decimales_separa():
    r1 = resolver_sitio_analitico(None, 13.559339, LON_SV)
    r2 = resolver_sitio_analitico(None, 13.559340, LON_SV)
    assert r1.valor != r2.valor


# --- 9. longitud negativa se conserva -----------------------------------------

def test_longitud_negativa_se_conserva():
    assert normalizar_coordenada_sitio(-88.433997) == "-88.433997"
    ident = construir_identificador_sitio(LAT_SV, -88.433997)
    assert ident == "SITIO_13.559339_-88.433997"


# --- 10. no genera "-0.000000" ------------------------------------------------

def test_no_genera_menos_cero():
    assert normalizar_coordenada_sitio(-0.0000001) == "0.000000"
    assert normalizar_coordenada_sitio(-0.0) == "0.000000"


# --- 11. coordenadas inválidas no generan sitio -------------------------------

def test_coordenadas_invalidas_no_generan_sitio():
    r = resolver_sitio_analitico(None, None, None)
    assert r.valor is None
    assert r.motivo == MOTIVO_SIN_DATOS

    r2 = resolver_sitio_analitico(None, "no-es-numero", LON_SV)
    assert r2.valor is None
    assert r2.motivo == MOTIVO_SIN_DATOS


# --- 12. fuera del bbox de El Salvador no genera sitio ------------------------

def test_fuera_de_bbox_el_salvador_no_genera_sitio():
    r = resolver_sitio_analitico(None, 40.4168, -3.7038)  # Madrid
    assert r.valor is None
    assert r.inferido is False
    assert r.motivo == MOTIVO_SIN_DATOS


# --- 13. sin antena ni coords devuelve nulo -----------------------------------

def test_sin_antena_ni_coords_devuelve_nulo():
    r = resolver_sitio_analitico(None, None, None)
    assert r.valor is None
    assert r.inferido is False
    assert r.latitud_normalizada is None
    assert r.longitud_normalizada is None
    assert r.motivo == MOTIVO_SIN_DATOS


# --- 14. DataFrame original no se modifica ------------------------------------

def test_dataframe_original_no_se_modifica():
    df = pd.DataFrame({
        "antena": ["Real1", None],
        "lat": [LAT_SV, LAT_SV],
        "long": [LON_SV, LON_SV],
    })
    original_cols = list(df.columns)
    original_copy = df.copy(deep=True)

    out = agregar_sitio_analitico(df)

    assert list(df.columns) == original_cols
    pd.testing.assert_frame_equal(df, original_copy)
    assert "antena_analitica" not in df.columns
    assert "antena_analitica" in out.columns
    assert out is not df


# --- 15. columnas derivadas tienen longitud correcta --------------------------

def test_columnas_derivadas_tienen_longitud_correcta():
    df = pd.DataFrame({
        "antena": ["Real1", None, None],
        "lat": [LAT_SV, LAT_SV, None],
        "long": [LON_SV, LON_SV, None],
    })
    out = agregar_sitio_analitico(df)

    for col in (
        "antena_analitica",
        "sitio_inferido",
        "sitio_inferencia_motivo",
        "sitio_lat_normalizada",
        "sitio_long_normalizada",
    ):
        assert col in out.columns
        assert len(out[col]) == len(df)


# --- 16. mezcla de antenas reales e inferidas ---------------------------------

def test_mezcla_de_antenas_reales_e_inferidas():
    df = pd.DataFrame({
        "antena": ["Real1", None, "SIN DETERMINAR"],
        "lat": [LAT_SV, LAT_SV, 40.0],
        "long": [LON_SV, LON_SV, -3.0],
    })
    out = agregar_sitio_analitico(df)

    assert out.loc[0, "antena_analitica"] == "Real1"
    assert bool(out.loc[0, "sitio_inferido"]) is False
    assert out.loc[0, "sitio_inferencia_motivo"] == MOTIVO_ANTENA_ORIGINAL

    assert out.loc[1, "antena_analitica"] == "SITIO_13.559339_-88.433997"
    assert bool(out.loc[1, "sitio_inferido"]) is True
    assert out.loc[1, "sitio_inferencia_motivo"] == MOTIVO_SITIO_INFERIDO

    assert pd.isna(out.loc[2, "antena_analitica"])
    assert bool(out.loc[2, "sitio_inferido"]) is False
    assert out.loc[2, "sitio_inferencia_motivo"] == MOTIVO_SIN_DATOS

    # La columna antena original nunca se sobrescribe.
    assert list(out["antena"]) == ["Real1", None, "SIN DETERMINAR"]


# --- 17. placeholders no cuentan como antena real -----------------------------

def test_placeholders_no_cuentan_como_antena_real():
    for placeholder in ("0", "-", "--", "nan", "none", "null", "n/a", "na", "sin inf", "sin determinar", "s/i"):
        r = resolver_sitio_analitico(placeholder, LAT_SV, LON_SV)
        assert r.motivo != MOTIVO_ANTENA_ORIGINAL, placeholder
        assert r.inferido is True, placeholder


# --- 18. resultado determinista ------------------------------------------------

def test_resultado_determinista():
    resultados = {resolver_sitio_analitico(None, LAT_SV, LON_SV).valor for _ in range(20)}
    assert len(resultados) == 1


# --- 19. strings numéricos funcionan -------------------------------------------

def test_strings_numericos_funcionan():
    r = resolver_sitio_analitico(None, "13.559339", "-88.433997")
    assert r.valor == "SITIO_13.559339_-88.433997"
    assert r.inferido is True

    df = pd.DataFrame({"lat": ["13.559339"], "long": ["-88.433997"]})
    out = agregar_sitio_analitico(df)
    assert out.loc[0, "antena_analitica"] == "SITIO_13.559339_-88.433997"


# --- 20. motivo correcto por fila ----------------------------------------------

def test_motivo_correcto_por_fila():
    df = pd.DataFrame({
        "antena": ["Real1", None, None],
        "lat": [LAT_SV, LAT_SV, None],
        "long": [LON_SV, LON_SV, None],
    })
    out = agregar_sitio_analitico(df)
    motivos = list(out["sitio_inferencia_motivo"])
    assert motivos == [MOTIVO_ANTENA_ORIGINAL, MOTIVO_SITIO_INFERIDO, MOTIVO_SIN_DATOS]


# --- Extra: antena real + coordenadas inválidas conserva la antena -----------

def test_antena_real_con_coords_invalidas_conserva_antena():
    r = resolver_sitio_analitico("Antena Real 01", None, None)
    assert r.valor == "Antena Real 01"
    assert r.inferido is False
    assert r.motivo == MOTIVO_ANTENA_ORIGINAL


# --- Extra: NaN/None explícitos en antena y coordenadas -----------------------

def test_nan_none_no_generan_sitio_ni_fallan():
    import math
    r = resolver_sitio_analitico(float("nan"), math.nan, None)
    assert r.valor is None
    assert r.motivo == MOTIVO_SIN_DATOS


# --- Extra: la antena original nunca se sobrescribe en el DataFrame -----------

def test_antena_analitica_no_sobrescribe_columna_antena_original():
    df = pd.DataFrame({"antena": [None], "lat": [LAT_SV], "long": [LON_SV]})
    out = agregar_sitio_analitico(df)
    assert pd.isna(out.loc[0, "antena"])
    assert out.loc[0, "antena_analitica"] == "SITIO_13.559339_-88.433997"
