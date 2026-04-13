"""Tests para qc_type_classifier — Fase QC-1."""

import pandas as pd
import pytest
from tz_core.qc_type_classifier import classify_single, classify_interaction_type, get_type_summary


class TestClassifySingle:
    """Tests para clasificación de valores individuales."""

    @pytest.mark.parametrize("value,expected", [
        # VOZ
        ("CALL", "VOZ"),
        ("Llamada entrante", "VOZ"),
        ("MOC", "VOZ"),
        ("MTC", "VOZ"),
        ("INCOMING", "VOZ"),
        ("OUTGOING", "VOZ"),
        ("voice call", "VOZ"),
        # SMS
        ("SMS", "SMS"),
        ("SMS-MO", "SMS"),
        ("MT-SMS", "SMS"),
        ("Mensaje de texto", "SMS"),
        ("SHORT MESSAGE", "SMS"),
        # DATOS
        ("GPRS", "DATOS"),
        ("DATA", "DATOS"),
        ("INTERNET", "DATOS"),
        ("Navegacion WAP", "DATOS"),
        ("PDP Context", "DATOS"),
        # DESCONOCIDO
        ("BLR", "DESCONOCIDO"),
        ("CFU", "DESCONOCIDO"),
        ("DESVIO", "DESCONOCIDO"),
        ("", "DESCONOCIDO"),
        (None, "DESCONOCIDO"),
        ("NaN", "DESCONOCIDO"),
        ("SIN INF.", "DESCONOCIDO"),
    ])
    def test_classify_single(self, value, expected):
        assert classify_single(value) == expected

    def test_case_insensitive(self):
        assert classify_single("gprs") == "DATOS"
        assert classify_single("sms") == "SMS"
        assert classify_single("call") == "VOZ"

    def test_datos_priority_over_voz(self):
        """Si un valor contiene keywords de DATOS y VOZ, DATOS gana."""
        assert classify_single("DATA CALL") == "DATOS"


class TestClassifyInteractionType:
    """Tests para clasificación de Serie completa."""

    def test_basic_series(self):
        s = pd.Series(["CALL", "SMS", "GPRS", "BLR", None])
        result = classify_interaction_type(s)
        assert list(result) == ["VOZ", "SMS", "DATOS", "DESCONOCIDO", "DESCONOCIDO"]

    def test_empty_series(self):
        s = pd.Series([], dtype=object)
        result = classify_interaction_type(s)
        assert len(result) == 0

    def test_preserves_index(self):
        s = pd.Series(["CALL", "SMS"], index=[10, 20])
        result = classify_interaction_type(s)
        assert list(result.index) == [10, 20]


class TestGetTypeSummary:
    """Tests para resumen de tipos."""

    def test_basic_summary(self):
        s = pd.Series(["VOZ", "VOZ", "SMS", "DATOS", "DESCONOCIDO"])
        result = get_type_summary(s)
        assert result["VOZ"]["count"] == 2
        assert result["VOZ"]["pct"] == 40.0
        assert result["SMS"]["count"] == 1
        assert result["DATOS"]["count"] == 1
        assert result["DESCONOCIDO"]["count"] == 1

    def test_empty_series(self):
        s = pd.Series([], dtype=object)
        result = get_type_summary(s)
        assert result == {}

    def test_all_same_type(self):
        s = pd.Series(["VOZ"] * 10)
        result = get_type_summary(s)
        assert result["VOZ"]["count"] == 10
        assert result["VOZ"]["pct"] == 100.0
        assert result["SMS"]["count"] == 0
