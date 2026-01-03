"""Pruebas para el flujo de placeholders QC manual en el monolito."""

from __future__ import annotations

import pandas as pd

import script_principal_bitacoras_refactory as monolito


def test_apply_qc_placeholders_inyecta_fields():
    df = pd.DataFrame({"lat": [13.5]})
    cols_originales = ["lat"]
    missing = ["alias", "abonado"]

    cols, present = monolito._apply_qc_placeholders(df, missing, cols_originales, {})

    assert "alias" in df.columns
    assert "abonado" in df.columns
    assert (df["alias"] == "SinInf").all()
    assert (df["abonado"] == "SinInf").all()
    assert set(missing).issubset(present)
    assert cols[:1] == ["lat"]


def test_apply_qc_placeholders_respeta_aliases():
    df = pd.DataFrame({"dummy": [0]})
    cols_originales = ["dummy"]
    missing = ["abonado"]
    alias_map = {"abonado": "abonado_final"}

    cols, present = monolito._apply_qc_placeholders(df, missing, cols_originales, alias_map)

    assert "abonado_final" in df.columns
    assert (df["abonado_final"] == "SinInf").all()
    assert "abonado_final" in present
    assert "abonado_final" in cols
