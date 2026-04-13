import pandas as pd
import pytest
from tz_core.qc_engine import run_qc, QCResult

def df_base():
    return pd.DataFrame({
        "fecha": ["2024-01-01", "2024-01-02"],
        "hora": ["10:00", "11:00"],
        "tel": ["70001234", "70001235"],
        "contacto": ["80001234", "80001235"],
        "interaccion": ["LLAMADA SALIENTE", "SMS ENTRANTE"],
        "lat": ["13.6929", "13.6930"],
        "long": ["-89.2182", "-89.2183"],
        "antena": ["ANT-001", "ANT-002"],
        "duracion": [60, 30],
        "imei": ["123456789012345", "123456789012346"],
    })

def test_score_perfecto():
    result = run_qc(df_base())
    assert isinstance(result, QCResult)
    assert result.score == 100
    assert result.bloqueante is False

def test_dataframe_vacio():
    result = run_qc(pd.DataFrame())
    assert result.score == 0
    assert result.bloqueante is True

def test_contacto_ausente():
    df = df_base().drop(columns=["contacto"])
    result = run_qc(df)
    assert result.bloqueante is True
    assert result.flags["contacto"]["ausente"] is True
    assert result.score <= 70

def test_contacto_vacio_supera_umbral():
    df = df_base()
    df["contacto"] = [None] * len(df)
    result = run_qc(df)
    assert result.bloqueante is True
    assert result.flags["contacto"]["pct_vacio"] == 100.0

def test_tipo_desconocido_supera_umbral():
    df = df_base()
    df["interaccion"] = ["XXXXXX"] * len(df)
    result = run_qc(df)
    assert result.bloqueante is True
    assert result.flags["tipo"]["pct_desconocido"] == 100.0

def test_fecha_ausente():
    df = df_base().drop(columns=["fecha"])
    result = run_qc(df)
    assert result.bloqueante is True
    assert result.flags["fecha"]["ausente"] is True

def test_coords_ausentes():
    df = df_base().drop(columns=["lat", "long"])
    result = run_qc(df)
    assert result.flags["coords"]["ausente"] is True
    assert result.bloqueante is False

def test_antena_ausente():
    df = df_base().drop(columns=["antena"])
    result = run_qc(df)
    assert result.flags["antena"]["ausente"] is True
    assert result.bloqueante is False

def test_duracion_opcional_no_penaliza_si_ausente():
    df = df_base().drop(columns=["duracion"])
    result = run_qc(df)
    assert "duracion" not in result.flags

def test_resumen_es_lista_strings():
    result = run_qc(df_base())
    assert isinstance(result.resumen, list)
    assert all(isinstance(s, str) for s in result.resumen)

def test_score_entre_0_y_100():
    df = df_base()
    df["contacto"] = [None] * len(df)
    df["interaccion"] = ["???"] * len(df)
    result = run_qc(df)
    assert 0 <= result.score <= 100
