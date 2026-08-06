"""Tests para normalize_event_fields — QC-5."""
from __future__ import annotations

import pandas as pd
import pytest
from tz_core.bitacora_normalization import normalize_event_fields


def test_clasificacion_voz():
    df = pd.DataFrame({"interaccion": ["LLAMADA SALIENTE", "VOZ ENTRANTE", "CALL MO"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["VOZ", "VOZ", "VOZ"]


def test_clasificacion_sms():
    # Tarea 4 (P0-B) unificó el vocabulario de normalize_event_fields con el
    # de qc_type_classifier (fuente única tz_core.event_classification);
    # "MENSAJE" ya es un término reconocido de SMS en ambos módulos.
    df = pd.DataFrame({"interaccion": ["SMS ENVIADO", "SMS-MO", "MENSAJE"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["SMS", "SMS", "SMS"]


def test_clasificacion_datos():
    # Tarea 4 (P0-B): "GPRS" e "INTERNET" ya son términos reconocidos de
    # DATOS en el vocabulario unificado (antes solo lo era el literal "DATOS").
    df = pd.DataFrame({"interaccion": ["GPRS SESSION", "DATOS MOVILES", "INTERNET"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["DATOS", "DATOS", "DATOS"]


def test_clasificacion_desconocido():
    df = pd.DataFrame({"interaccion": ["CFU", "BLR", "DESVIO"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["DESCONOCIDO", "DESCONOCIDO", "DESCONOCIDO"]


def test_valor_mixto_datos_gana():
    """DATOS tiene prioridad sobre VOZ y SMS."""
    df = pd.DataFrame({"interaccion": ["VOZ/DATOS", "SMS DATOS", "DATOS CALL"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["DATOS", "DATOS", "DATOS"]


def test_columna_ausente():
    df = pd.DataFrame({"otra_col": ["algo"] * 3})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["DESCONOCIDO"] * 3
    assert list(result["evento_valido_analisis"]) == [False] * 3


def test_col_tipo_none():
    df = pd.DataFrame({"interaccion": ["LLAMADA"] * 3})
    result = normalize_event_fields(df, col_tipo=None)
    assert list(result["tipo_evento_normalizado"]) == ["DESCONOCIDO"] * 3


def test_valores_nan():
    df = pd.DataFrame({"interaccion": [None, float("nan"), "LLAMADA"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert result["tipo_evento_normalizado"].iloc[0] == "DESCONOCIDO"
    assert result["tipo_evento_normalizado"].iloc[1] == "DESCONOCIDO"
    assert result["tipo_evento_normalizado"].iloc[2] == "VOZ"


def test_evento_valido_analisis_voz_sms():
    df = pd.DataFrame({"interaccion": ["LLAMADA", "SMS", "DATOS", "DESCONOCIDO"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["evento_valido_analisis"]) == [True, True, False, False]


def test_no_modifica_columna_original():
    df = pd.DataFrame({"interaccion": ["llamada saliente"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert result["interaccion"].iloc[0] == "llamada saliente"


def test_case_insensitive():
    # Tarea 4 (P0-B): "gprs" ya es un término reconocido de DATOS.
    df = pd.DataFrame({"interaccion": ["llamada", "sms entrante", "gprs"]})
    result = normalize_event_fields(df, col_tipo="interaccion")
    assert list(result["tipo_evento_normalizado"]) == ["VOZ", "SMS", "DATOS"]
