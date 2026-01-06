import pytest

from tz_core.types import (
    CaseIdentity,
    CaseNameSuggestion,
    DatasetMetadata,
    ManualModeContext,
    OutputRouting,
    TopSelection,
)


def test_manual_mode_context_fields():
    ctx = ManualModeContext(option="1", config={"foo": "bar"})
    assert ctx.option == "1"
    assert ctx.config == {"foo": "bar"}


def test_dataset_metadata_defaults():
    meta = DatasetMetadata(
        archivo="file.xlsx",
        hoja=None,
        dataframe=[[1, 2]],
        columnas=["a", "b"],
    )
    assert meta.archivo == "file.xlsx"
    assert meta.hoja is None
    assert meta.hoja_usada is None
    assert meta.columnas == ["a", "b"]


def test_case_identity_fields():
    ident = CaseIdentity(mode="TEL", primary_id="123", alias_short="abc", base_name="TEL_123")
    assert ident.mode == "TEL"
    assert ident.primary_id == "123"
    assert ident.alias_short == "abc"
    assert ident.base_name == "TEL_123"


def test_top_selection_fields():
    top = TopSelection(antennas=5, contacts=10)
    assert top.antennas == 5
    assert top.contacts == 10


def test_output_routing_fields():
    routing = OutputRouting(
        base_name="case",
        base_folder="/tmp/base",
        case_folder="case",
        output_folder="/tmp/base/case",
        kml_folder=None,
        kml_path="/tmp/base/case/case_mapeo.kml",
        kmz_path="/tmp/base/case/case_mapeo.kmz",
    )
    assert routing.kml_folder is None
    assert routing.kml_path.endswith("case_mapeo.kml")
    assert routing.kmz_path.endswith("case_mapeo.kmz")


def test_case_name_suggestion_fields():
    suggestion = CaseNameSuggestion(
        base_name="BASE",
        principal_id="P1",
        alias_id="AL",
        tel_part="T",
        alias_part="A",
        date_range_label="2026",
        filter_suffix="filt",
    )
    assert suggestion.base_name == "BASE"
    assert suggestion.principal_id == "P1"
    assert suggestion.filter_suffix == "filt"
