"""Pruebas para el flujo de placeholders QC manual en el monolito."""

from __future__ import annotations

import pandas as pd

import script_principal_bitacoras_refactory as monolito
from tz_core.schema_utils import run_schema_location_assistant


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


def test_run_schema_location_assistant_maps_columns_and_creates_antena():
    df = pd.DataFrame({
        "col_lat": [13.5, 13.6],
        "col_lon": [-89.2, -89.25],
    })

    inputs = iter(["1", "1", "2", ""])

    config = {
        "schema": {
            "fields": {},
            "location_alternatives": [["lat", "lon"]],
            "subject_default_mode": "tel",
        },
        "entradas": {"columnas_esenciales": ["lat", "long"]},
    }

    result = run_schema_location_assistant(
        df.copy(),
        original_columns=list(df.columns),
        config=config,
        alias_visibles=monolito.ALIAS_VISIBLES,
        input_fn=lambda _prompt="": next(inputs, ""),
        output_fn=lambda _msg: None,
        config_path=None,
    )

    assert "lat" in result.columns
    assert "long" in result.columns
    assert "antena" in result.columns
    assert result.loc[0, "lat"] == 13.5
    assert result.loc[0, "long"] == -89.2
    assert result["antena"].str.startswith("Antena").all()


def test_run_schema_location_assistant_respects_existing_location_columns():
    df = pd.DataFrame({
        "lat": [13.5],
        "long": [-89.2],
        "antena": ["Antena 1"],
    })

    inputs = iter(["", "", "", ""])

    config = {
        "schema": {
            "fields": {},
            "location_alternatives": [["lat", "lon"]],
            "subject_default_mode": "tel",
        },
        "entradas": {"columnas_esenciales": ["lat", "long", "antena"]},
    }

    result = run_schema_location_assistant(
        df.copy(),
        original_columns=list(df.columns),
        config=config,
        alias_visibles=monolito.ALIAS_VISIBLES,
        input_fn=lambda _prompt="": next(inputs, ""),
        output_fn=lambda _msg: None,
        config_path=None,
    )

    assert list(result.columns) == ["lat", "long", "antena"]
    assert result.equals(df)


def test_prepare_manual_mapping_sets_defaults_and_orig_cols():
    df = pd.DataFrame({"a": [1], "b": [2]})

    df_ready, esenciales, no_esenciales = monolito._prepare_manual_mapping(df.copy())

    assert hasattr(df_ready, "_orig_cols")
    assert df_ready._orig_cols == ["a", "b"]
    assert esenciales == [
        "fecha",
        "hora",
        "tel",
        "imei",
        "interaccion",
        "contacto",
        "lat",
        "long",
        "azimut",
        "antena",
    ]
    assert no_esenciales == ["celda", "direccion", "imsi", "duracion"]


def test_run_manual_mapping_instantiates_mappingwizard(monkeypatch):
    df = pd.DataFrame({"foo": ["value"]})
    sentinel_io = object()
    captured = {}

    class _DummyWizard:
        def __init__(self, df_arg, esenciales, no_esenciales, io):
            captured["df"] = df_arg
            captured["esenciales"] = esenciales
            captured["no_esenciales"] = no_esenciales
            captured["io"] = io
            self._df = df_arg

        def run(self):
            result = self._df.copy()
            result["mapped"] = True
            return result, {"tel": ("col", "foo")}

    monkeypatch.setattr(monolito, "MappingWizard", _DummyWizard)

    mapped, assignments = monolito._run_manual_mapping(df.copy(), wizard_io=sentinel_io)

    assert assignments == {"tel": ("col", "foo")}
    assert "mapped" in mapped.columns
    assert captured["df"]._orig_cols == ["foo"]
    assert captured["esenciales"][0] == "fecha"
    assert captured["no_esenciales"] == ["celda", "direccion", "imsi", "duracion"]
    assert captured["io"] is sentinel_io
