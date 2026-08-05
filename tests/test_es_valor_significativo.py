"""Hito 2B FX-02 — Pruebas del predicado único `es_valor_significativo()`
consolidado en tz_core/bitacora_normalization.py.

Cubre el contrato exacto de centinelas no significativos y confirma que
valores reales (contactos, tipos de evento, etc.) siguen contando.
"""
import numpy as np
import pandas as pd
import pytest

from tz_core.bitacora_normalization import es_valor_significativo


SENTINELAS = [
    "0", "-", "--", "nan", "none", "null", "n/a", "na",
    "sin inf", "sin inf.", "sin determinar", "s/i",
]


@pytest.mark.parametrize("valor", SENTINELAS)
def test_centinelas_exactos_no_son_significativos(valor):
    assert es_valor_significativo(valor) is False


@pytest.mark.parametrize("valor", SENTINELAS)
def test_centinelas_case_insensitive_y_con_espacios(valor):
    assert es_valor_significativo(f"  {valor.upper()}  ") is False


def test_none_no_es_significativo():
    assert es_valor_significativo(None) is False


def test_nan_float_no_es_significativo():
    assert es_valor_significativo(float("nan")) is False
    assert es_valor_significativo(np.nan) is False


def test_pandas_na_no_es_significativo():
    assert es_valor_significativo(pd.NA) is False


def test_vacio_no_es_significativo():
    assert es_valor_significativo("") is False
    assert es_valor_significativo("   ") is False


@pytest.mark.parametrize("valor", ["70011234", "LLAMADA ENTRANTE", "ANT-01", "1", "0.0"])
def test_valores_reales_son_significativos(valor):
    assert es_valor_significativo(valor) is True


def test_numero_entero_valido_es_significativo():
    assert es_valor_significativo(70011234) is True
