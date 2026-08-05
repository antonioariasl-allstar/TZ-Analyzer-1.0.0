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
    """HITO 2: contacto ausente ya no bloquea el motor de QC — la capacidad
    'contactos' queda no disponible (ver tz_core.capabilities), pero el resto
    del análisis (identificación, cronología, antenas, KML...) puede seguir.
    El peso de penalización también bajó de 30 a 15 para no exagerar el
    impacto en el score de una bitácora parcial pero válida."""
    df = df_base().drop(columns=["contacto"])
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["contacto"]["ausente"] is True
    assert result.flags["contacto"]["severidad"] == "ADVERTENCIA"
    assert result.score == 85

def test_contacto_vacio_supera_umbral():
    """HITO 2: contacto 100% vacío es una advertencia, no un bloqueo."""
    df = df_base()
    df["contacto"] = [None] * len(df)
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["contacto"]["pct_vacio"] == 100.0
    assert result.flags["contacto"]["severidad"] == "ADVERTENCIA"

def test_tipo_desconocido_supera_umbral():
    """HITO 2: tipo/interacción 100% DESCONOCIDO ya no bloquea — la capacidad
    'tipo_evento' queda no disponible, pero no detiene el pipeline."""
    df = df_base()
    df["interaccion"] = ["XXXXXX"] * len(df)
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["tipo"]["pct_desconocido"] == 100.0
    assert result.flags["tipo"]["severidad"] == "ADVERTENCIA"

def test_fecha_ausente():
    """HITO 2: fecha ausente sigue siendo una advertencia fuerte (severidad
    CRITICA en el flag, penalización completa del peso de fecha) pero ya no
    bloquea el motor — cronología/filtros_temporales quedan no disponibles
    vía CapabilitiesReport, el resto del análisis continúa."""
    df = df_base().drop(columns=["fecha"])
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["fecha"]["ausente"] is True
    assert result.flags["fecha"]["severidad"] == "CRITICA"

def test_contacto_parcialmente_vacio_no_bloquea():
    """HITO 2 TAREA 7 caso 2: contacto >30% vacío sigue siendo advertencia,
    nunca bloqueante — ya no existe el umbral CRITICA/bloqueante de antes."""
    df = df_base()
    df = pd.concat([df, df], ignore_index=True)  # 4 filas
    df.loc[[0, 1, 2], "contacto"] = None  # 75% vacío
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["contacto"]["pct_vacio"] == 75.0
    assert result.flags["contacto"]["severidad"] == "ADVERTENCIA"

def test_interaccion_ausente():
    """HITO 2 TAREA 7 caso 3: columna 'interaccion' ausente por completo ya
    no bloquea el motor — la capacidad 'tipo_evento' queda no disponible."""
    df = df_base().drop(columns=["interaccion"])
    result = run_qc(df)
    assert result.bloqueante is False
    assert result.flags["tipo"]["ausente"] is True
    assert result.flags["tipo"]["severidad"] == "ADVERTENCIA"

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
