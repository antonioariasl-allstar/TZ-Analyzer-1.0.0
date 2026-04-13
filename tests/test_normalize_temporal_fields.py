"""Tests para normalize_temporal_fields — detección y separación de datetime combinado."""
from __future__ import annotations
import pandas as pd
import pytest
from tz_core.bitacora_normalization import normalize_temporal_fields


def test_caso_a_datetime_combinado_crea_tres_campos():
    df = pd.DataFrame({"fecha": ["2020-01-15 08:30:00"] * 5})
    result = normalize_temporal_fields(df)
    assert "datetime_evento" in result.columns
    assert "hora" in result.columns
    assert result["fecha"].iloc[0] == "15/01/2020"
    assert result["hora"].iloc[0] == "08:30:00"
    assert pd.api.types.is_datetime64_any_dtype(result["datetime_evento"])


def test_caso_a_no_sobreescribe_hora_si_existe():
    df = pd.DataFrame({
        "fecha": ["2020-01-15 08:30:00"] * 3,
        "hora": ["10:00:00"] * 3,
    })
    result = normalize_temporal_fields(df)
    assert result["hora"].iloc[0] == "10:00:00"


def test_caso_b_fecha_hora_separadas_construye_datetime_evento():
    df = pd.DataFrame({
        "fecha": ["15/01/2020"] * 3,
        "hora": ["08:30:00"] * 3,
    })
    result = normalize_temporal_fields(df)
    assert "datetime_evento" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["datetime_evento"])
    assert result["datetime_evento"].iloc[0].hour == 8


def test_caso_c_solo_fecha_datetime_evento_a_medianoche():
    df = pd.DataFrame({"fecha": ["2020-03-10"] * 3})
    result = normalize_temporal_fields(df)
    assert "datetime_evento" in result.columns
    assert result["datetime_evento"].iloc[0].hour == 0


def test_caso_d_sin_campos_temporales_no_rompe():
    df = pd.DataFrame({"antena": ["ANT-01"] * 3, "lat": [13.7] * 3})
    result = normalize_temporal_fields(df)
    assert "datetime_evento" in result.columns
    assert result["datetime_evento"].isna().all()


def test_valores_nulos_tolerados():
    df = pd.DataFrame({"fecha": ["2020-01-15 08:30:00", None, "2020-01-16 09:00:00"]})
    result = normalize_temporal_fields(df)
    assert result["datetime_evento"].notna().sum() == 2
