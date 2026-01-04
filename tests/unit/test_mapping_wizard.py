"""Pruebas del Wizard QC con IO inyectable."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import tz_core.mapping_wizard as mapping_wizard_module

from tz_core.mapping_wizard import (
    MappingWizard,
    WizardIO,
    apply_quick_remap_selection,
    finalize_manual_mapping_dataframe,
    normalize_wizard_datetime_fields,
    perform_quick_remap_batch,
    collect_quick_remap_operations,
    collect_essential_mapping_assignments,
    collect_non_essential_mapping_assignments,
    collect_identity_overrides,
    execute_confirm_loop_flow,
    execute_wizard_lifecycle,
    format_columns_menu,
    build_mapping_intro_lines,
    build_remap_menu_order,
    apply_remap_single_selection,
    resolve_remap_single_flow,
    confirm_remap_selection,
    build_pending_warning_lines,
    build_preview_table,
    format_mapping_summary,
    resolve_confirm_loop_option,
    resolve_essential_column_selection,
    resolve_non_essential_selection,
    resolve_remap_target_selection,
    needs_identity_field_prompt,
    apply_wizard_assignments,
)


class _FakeIORecorder:
    """Fabrica de entradas/salidas deterministas para el wizard."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.outputs: list[str] = []

    def input(self, message: str) -> str:
        self.prompts.append(message)
        if self._responses:
            return self._responses.pop(0)
        return ""

    def output(self, message: str) -> None:
        self.outputs.append(message)


def test_wizard_io_handles_failing_callbacks():
    calls = {"write": 0}

    def bad_input(_message: str) -> str:  # pragma: no cover - se evalúa a través de WizardIO
        raise RuntimeError("boom")

    def bad_output(_message: str) -> None:  # pragma: no cover - se evalúa a través de WizardIO
        calls["write"] += 1
        raise RuntimeError("fail")

    io = WizardIO(input_fn=bad_input, output_fn=bad_output)

    assert io.prompt("msg") == ""
    io.write("hola")  # no debe propagar la excepción
    assert calls["write"] == 1


def test_mapping_wizard_uses_custom_io_flow():
    df = pd.DataFrame({
        "col_fecha": ["2025-01-01"],
        "duracion": [5],
    })

    recorder = _FakeIORecorder(["1", "", "", "", "S"])
    io = WizardIO(input_fn=recorder.input, output_fn=recorder.output)

    wizard = MappingWizard(df, esenciales=["fecha"], no_esenciales=[], io=io)
    mapped_df, asignadas = wizard.run()

    assert "fecha" in mapped_df.columns
    assert mapped_df.loc[0, "fecha"] == "2025-01-01"
    assert "duracion" in mapped_df.columns
    assert asignadas["fecha"] == ("col", "col_fecha")
    assert recorder.prompts == [
        "→ Elegí columna para fecha (número — '?' para ver menú / Enter=omitir): ",
        "→ Alias para toda la ejecución (Enter=omitir): ",
        "→ Nombre_usuario para toda la ejecución (Enter=omitir): ",
        "→ Abonado para toda la ejecución (Enter=omitir): ",
        "→ Opción (S/N/R): ",
    ]
    assert any("=== Resumen de mapeo ===" in msg for msg in recorder.outputs)


def test_apply_wizard_assignments_handles_numeric_and_fallbacks():
    df = pd.DataFrame({
        "LAT_RAW": ["-34.58", "foo"],
        "dur_col": ["10", "nope"],
        "siteid": ["AR-101", "AR-102"],
    })

    asignaciones = {
        "lat": ("col", "LAT_RAW"),
        "duracion": ("col", "dur_col"),
        "alias": ("fijo", "Alpha"),
    }

    messages: list[str] = []
    mapped = apply_wizard_assignments(
        df,
        asignaciones,
        numeric_fields={"lat", "duracion"},
        writer=messages.append,
    )

    assert "lat" in mapped.columns and "duracion" in mapped.columns
    assert mapped.loc[0, "alias"] == "Alpha"
    assert pd.isna(mapped.loc[1, "duracion"])  # coerción a NaN en valores inválidos
    assert pd.isna(mapped.loc[1, "lat"])  # "foo" se convierte en NaN
    assert "antena" in mapped.columns and list(mapped["antena"]) == ["AR-101", "AR-102"]
    assert messages == []


def test_normalize_wizard_datetime_fields_formats_outputs():
    df = pd.DataFrame({
        "fecha": ["31/12/2025 13:05:00", "02/01/2026 08:30:00", None],
        "hora": ["1:5", "", ""],
    })

    result = normalize_wizard_datetime_fields(df.copy())

    assert result.loc[0, "fecha"] == "31/12/2025"
    assert result.loc[1, "fecha"] == "02/01/2026"
    assert pd.isna(result.loc[2, "fecha"])
    assert result.loc[0, "hora"] == "01:05:00"
    assert result.loc[1, "hora"] == "08:30:00"
    assert result.loc[2, "hora"] == "Sin Inf."


def test_normalize_wizard_datetime_fields_warns_and_coerces_on_failure(monkeypatch):
    df = pd.DataFrame({
        "fecha": ["2025-12-31"],
        "lat": ["10.0"],
        "long": ["-89.2"],
    })

    def boom(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(mapping_wizard_module.pd, "to_datetime", boom)

    warnings: list[str] = []
    normalize_wizard_datetime_fields(df, warn_writer=warnings.append)

    assert warnings and "[WARN] Normalización fecha/hora" in warnings[0]
    assert df.loc[0, "lat"] == 10.0
    assert df.loc[0, "long"] == -89.2


def test_finalize_manual_mapping_dataframe_syncs_lon_and_numeric():
    df = pd.DataFrame({
        "lon": ["-89.25", "foo"],
        "lat": ["13.50", "bar"],
        "azimut": ["45", "n/a"],
    })

    result = finalize_manual_mapping_dataframe(df.copy())

    assert "long" in result.columns
    assert result.loc[0, "long"] == -89.25
    assert pd.isna(result.loc[1, "long"])
    assert pd.isna(result.loc[1, "lat"])
    assert result.loc[0, "azimut"] == 45.0
    assert pd.isna(result.loc[1, "azimut"])


def test_finalize_manual_mapping_dataframe_supports_custom_fields():
    df = pd.DataFrame({
        "custom": ["10", "bad"],
    })

    result = finalize_manual_mapping_dataframe(df.copy(), numeric_fields=["custom"])

    assert pd.to_numeric(result["custom"], errors="coerce").isna().tolist() == [False, True]


def test_confirm_loop_reuses_same_io_on_restart():
    df = pd.DataFrame({"col_a": ["value"]})
    probe = MappingWizard(df)
    essentials = len(probe.esenciales)
    non_essentials = len(probe.no_esenciales)

    def _blank_run(confirm_value: str) -> list[str]:
        responses = [""] * essentials
        responses += [""] * non_essentials
        responses += [""] * 3  # alias/nombre_usuario/abonado
        responses.append("")  # quick remap duracion → 'no'
        responses.append(confirm_value)
        return responses

    responses = _blank_run("N") + _blank_run("S")
    recorder = _FakeIORecorder(responses)
    io = WizardIO(input_fn=recorder.input, output_fn=recorder.output)

    wizard = MappingWizard(df, io=io)
    mapped_df, asignadas = wizard.run()

    assert isinstance(mapped_df, pd.DataFrame)
    assert isinstance(asignadas, dict)
    assert recorder.prompts.count("→ Opción (S/N/R): ") == 2
    assert any("Reiniciando mapeo completo" in msg for msg in recorder.outputs)
    expected_prompts = 2 * (essentials + non_essentials + 5)
    assert len(recorder.prompts) == expected_prompts


def test_apply_quick_remap_selection_handles_fixed_and_column_modes():
    df = pd.DataFrame({"c1": ["10"], "c2": ["alias"]})
    menu = ["c1", "c2"]

    mapped = apply_quick_remap_selection(df.copy(), "duracion", "F 99", menu)
    assert list(mapped["duracion"]) == ["99"]

    mapped = apply_quick_remap_selection(mapped, "alias", "2", menu)
    assert "alias" in mapped.columns and "c2" not in mapped.columns

    untouched = apply_quick_remap_selection(mapped.copy(), "alias", "?", menu)
    assert list(untouched.columns) == list(mapped.columns)


def test_perform_quick_remap_batch_applies_operations_and_dedupes():
    df = pd.DataFrame({"c1": ["1"], "c2": ["2"], "alias": ["foo"]})
    menu = ["c1", "c2", "alias"]

    result = perform_quick_remap_batch(
        df,
        menu,
        [
            ("duracion", "1"),
            ("alias", "F fijo"),
            ("contacto", "2"),
        ],
    )

    assert list(result.columns).count("duracion") == 1
    assert list(result["duracion"]) == ["1"]
    assert list(result["alias"]) == ["fijo"]
    assert list(result["contacto"]) == ["2"]


def test_collect_quick_remap_operations_respects_menu_and_prompt_updates():
    responses = iter(["?", "2", "F fijo"])
    messages: list[str] = []

    def fake_prompt(_msg: str) -> str:
        return next(responses)

    operations = collect_quick_remap_operations(
        prompt_fn=fake_prompt,
        write_fn=messages.append,
        columns_menu=["c1", "c2"],
        canonicals=["duracion", "alias"],
    )

    assert operations == [("duracion", "2"), ("alias", "F fijo")]
    assert any("[1] c1" in msg for msg in messages)


def test_collect_essential_mapping_assignments_handles_menu_duplicates_and_pending():
    recorder = _FakeIORecorder(["?", "1", "1", "2", ""])

    assignments, used, pendientes = collect_essential_mapping_assignments(
        canonicals=["fecha", "tel", "hora"],
        columns_menu=["c1", "c2"],
        prompt_fn=recorder.input,
        write_fn=recorder.output,
        etiquetas={"fecha": "Fecha"},
    )

    assert assignments["fecha"] == ("col", "c1")
    assert assignments["tel"] == ("col", "c2")
    assert assignments["hora"] == ("omitido", None)
    assert used == {"c1", "c2"}
    assert pendientes == ["hora"]
    assert recorder.outputs[0].startswith("  [1] c1")
    assert any("Advertencia" in msg for msg in recorder.outputs)
    assert recorder.prompts.count("→ Elegí columna para **tel**: ") == 1


def test_collect_non_essential_mapping_assignments_supports_fixed_and_invalid_defaults():
    recorder = _FakeIORecorder(["?", "2", "F valor", "foo"])

    assignments = collect_non_essential_mapping_assignments(
        canonicals=["alias", "duracion", "custom"],
        columns_menu=["c1", "c2"],
        prompt_fn=recorder.input,
        write_fn=recorder.output,
        etiquetas={"alias": "Alias"},
        initial_assignments={"fecha": ("col", "c0")},
    )

    assert assignments["fecha"] == ("col", "c0")
    assert assignments["alias"] == ("col", "c2")
    assert assignments["duracion"] == ("fijo", "valor")
    assert assignments["custom"] == ("omitido", None)
    assert recorder.outputs[0].startswith("  [1] c1")


def test_format_columns_menu_wraps_after_per_line_items():
    cols = [f"c{i}" for i in range(1, 8)]
    menu = format_columns_menu(cols, per_line=3)

    lines = menu.splitlines()
    assert lines[0] == "  [1] c1  |  [2] c2  |  [3] c3"
    assert lines[1] == "  [4] c4  |  [5] c5  |  [6] c6"
    assert lines[2] == "  [7] c7"


def test_build_mapping_intro_lines_generates_section_text():
    lines = build_mapping_intro_lines(
        title="ESENCIALES",
        columns_menu=["c1"],
        instructions="extra",
        show_header_once=True,
    )

    assert lines[0].startswith("\n[QC] Columnas disponibles")
    assert "[1] c1" in lines[1]
    assert "=== Mapeo ESENCIALES ===" in lines[2]
    assert lines[3] == "extra"


def test_build_remap_menu_order_mixes_fixed_and_remaining():
    essentials = ["fecha", "tel"]
    non_essentials = ["alias", "duracion", "custom"]

    ordered = build_remap_menu_order(essentials, non_essentials)

    assert ordered[:3] == ["tel", "fecha", "alias"]  # tel/fecha vienen del fixed
    assert ordered[-1] == "custom"  # elemento fuera del fixed va al final


def test_format_mapping_summary_renders_all_assignment_types():
    assignments = {
        "tel": ("col", "c1"),
        "alias": ("fijo", "XYZ"),
        "abonado": ("omitido", None),
    }

    lines = format_mapping_summary(assignments)

    assert lines == [
        "  tel          <- columna 'c1'",
        "  alias        <- fijo 'XYZ'",
        "  abonado      <- omitido",
    ]


def test_build_pending_warning_lines_handles_empty_and_list():
    assert build_pending_warning_lines([]) == []

    warnings = build_pending_warning_lines(["tel", "lat"])
    assert warnings[0].startswith("\n[QC] Aviso: omitiste")
    assert "tel, lat" in warnings[0]
    assert "responsabilidad" in warnings[1]


def test_build_preview_table_respects_column_order():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    preview = build_preview_table(df, ["b", "a"], max_rows=1)
    assert preview is not None
    header = preview.splitlines()[0].strip().split()
    assert header == ["b", "a"]


def test_needs_identity_field_prompt_detects_missing_or_blank_columns():
    df = pd.DataFrame({"alias": ["   ", "  "]})

    assert needs_identity_field_prompt(df, "alias")
    assert needs_identity_field_prompt(df, "nombre_usuario")  # columna ausente

    df["alias"] = ["Ana", "Beto"]
    assert not needs_identity_field_prompt(df, "alias")


def test_collect_identity_overrides_prompts_only_missing_fields():
    df = pd.DataFrame({"alias": ["Ana"]})
    recorder = _FakeIORecorder(["", " VIP "])

    overrides = collect_identity_overrides(
        df,
        ["alias", "nombre_usuario", "abonado"],
        recorder.input,
    )

    assert overrides == {"abonado": "VIP"}
    assert recorder.prompts == [
        "→ Nombre_usuario para toda la ejecución (Enter=omitir): ",
        "→ Abonado para toda la ejecución (Enter=omitir): ",
    ]


def test_collect_identity_overrides_handles_prompt_exceptions_and_continues():
    df = pd.DataFrame()

    class _FlakyPrompt:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, message: str) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            return "Cliente"

    flaky = _FlakyPrompt()

    overrides = collect_identity_overrides(
        df,
        ["alias", "abonado"],
        flaky,
    )

    assert overrides == {"abonado": "Cliente"}
    assert flaky.calls == 2


def test_perform_initial_mapping_flow_calls_sections_in_order(monkeypatch):
    df = pd.DataFrame({"a": [1]})
    noop_io = WizardIO(input_fn=lambda _msg: "", output_fn=lambda _msg: None)

    class _SpyWizard(MappingWizard):
        def __init__(self) -> None:
            super().__init__(df, esenciales=[], no_esenciales=[], io=noop_io)
            self.calls: list[str] = []

        def _map_essentials(self) -> None:
            self.calls.append("essentials")

        def _map_non_essentials(self) -> None:
            self.calls.append("non_essentials")

        def _show_summary(self) -> None:
            self.calls.append("summary")

        def _apply_mapping(self) -> pd.DataFrame:
            self.calls.append("apply")
            return pd.DataFrame({"stage": ["apply"]})

        def _handle_identity_fields(self, df: pd.DataFrame) -> pd.DataFrame:
            self.calls.append("identity")
            return pd.DataFrame({"stage": ["identity"]})

        def _show_preview(self, df: pd.DataFrame) -> None:
            self.calls.append("preview")

        def _quick_remap(self, df: pd.DataFrame) -> pd.DataFrame:
            self.calls.append("quick_remap")
            return pd.DataFrame({"stage": ["quick"]})

    wizard = _SpyWizard()
    final_df = wizard._perform_initial_mapping_flow()

    assert wizard.calls == [
        "essentials",
        "non_essentials",
        "summary",
        "apply",
        "identity",
        "preview",
        "quick_remap",
    ]
    assert list(final_df["stage"]) == ["quick"]


def test_execute_confirm_loop_flow_confirms_without_callbacks():
    df_initial = pd.DataFrame({"stage": ["init"]})
    recorder = _FakeIORecorder([""])
    outputs: list[str] = []
    assignments = {"tel": ("col", "c1")}

    result_df, result_assignments = execute_confirm_loop_flow(
        initial_df=df_initial,
        prompt_fn=recorder.input,
        write_fn=outputs.append,
        perform_remap=lambda current: current.assign(stage="remapped"),
        perform_restart=lambda: (pd.DataFrame({"stage": ["restart"]}), {}),
        fetch_assignments=lambda: assignments,
    )

    assert result_df is df_initial
    assert result_assignments is assignments
    assert recorder.prompts == ["→ Opción (S/N/R): "]


def test_execute_confirm_loop_flow_handles_remap_then_confirm():
    df_initial = pd.DataFrame({"stage": ["init"]})
    recorder = _FakeIORecorder(["R", "s"])
    outputs: list[str] = []
    remap_calls: list[pd.DataFrame] = []

    def _remap(current: pd.DataFrame) -> pd.DataFrame:
        remap_calls.append(current)
        return pd.DataFrame({"stage": ["remapped"]})

    result_df, _ = execute_confirm_loop_flow(
        initial_df=df_initial,
        prompt_fn=recorder.input,
        write_fn=outputs.append,
        perform_remap=_remap,
        perform_restart=lambda: (pd.DataFrame({"stage": ["restart"]}), {}),
        fetch_assignments=lambda: {},
    )

    assert remap_calls and remap_calls[0] is df_initial
    assert list(result_df["stage"]) == ["remapped"]


def test_execute_confirm_loop_flow_handles_restart_path():
    df_initial = pd.DataFrame({"stage": ["init"]})
    recorder = _FakeIORecorder(["n"])
    outputs: list[str] = []
    restart_result = (pd.DataFrame({"stage": ["restart"]}), {"alias": ("fijo", "X")})

    returned_df, returned_assignments = execute_confirm_loop_flow(
        initial_df=df_initial,
        prompt_fn=recorder.input,
        write_fn=outputs.append,
        perform_remap=lambda current: current,
        perform_restart=lambda: restart_result,
        fetch_assignments=lambda: {},
    )

    assert returned_df is restart_result[0]
    assert returned_assignments is restart_result[1]


def test_execute_confirm_loop_flow_reports_invalid_options():
    df_initial = pd.DataFrame({"stage": ["init"]})
    recorder = _FakeIORecorder(["x", "s"])
    outputs: list[str] = []

    execute_confirm_loop_flow(
        initial_df=df_initial,
        prompt_fn=recorder.input,
        write_fn=outputs.append,
        perform_remap=lambda current: current,
        perform_restart=lambda: (df_initial, {}),
        fetch_assignments=lambda: {},
    )

    assert any("Opción inválida" in msg for msg in outputs)


def test_execute_wizard_lifecycle_chains_initial_and_confirm():
    calls: list[str] = []

    def _initial_flow() -> pd.DataFrame:
        calls.append("initial")
        return pd.DataFrame({"stage": ["initial"]})

    def _confirm_flow(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
        calls.append(f"confirm:{list(df['stage'])[0]}")
        return df.assign(stage="final"), {"alias": ("omitido", None)}

    final_df, assignments = execute_wizard_lifecycle(_initial_flow, _confirm_flow)

    assert list(final_df["stage"])[0] == "final"
    assert assignments == {"alias": ("omitido", None)}
    assert calls == ["initial", "confirm:initial"]


def test_wizard_qc_mapeo_instantiates_mapping_wizard(monkeypatch):
    created: dict[str, Any] = {}

    class _StubWizard:
        def __init__(self, df: pd.DataFrame, esenciales, no_esenciales, io=None):
            created["df"] = df
            created["esenciales"] = esenciales
            created["no_esenciales"] = no_esenciales
            created["io"] = io

        def run(self) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
            return pd.DataFrame({"mapped": [True]}), {"tel": ("col", "col_tel")}

    monkeypatch.setattr(mapping_wizard_module, "MappingWizard", _StubWizard)

    df = pd.DataFrame({"col_tel": ["1"]})
    custom_io = WizardIO(input_fn=lambda msg: "", output_fn=lambda msg: None)
    mapped, asignadas = mapping_wizard_module.wizard_qc_mapeo(
        df,
        esenciales=["tel"],
        no_esenciales=["alias"],
        io=custom_io,
    )

    assert created["df"] is df
    assert created["esenciales"] == ["tel"]
    assert created["no_esenciales"] == ["alias"]
    assert created["io"] is custom_io
    assert isinstance(mapped, pd.DataFrame)
    assert asignadas == {"tel": ("col", "col_tel")}


def test_wizard_qc_mapeo_allows_default_arguments(monkeypatch):
    captured: dict[str, Any] = {}

    class _StubWizard:
        def __init__(self, df, esenciales=None, no_esenciales=None, io=None):
            captured.update({
                "df": df,
                "esenciales": esenciales,
                "no_esenciales": no_esenciales,
                "io": io,
            })

        def run(self):
            return captured["df"], {"alias": ("omitido", None)}

    monkeypatch.setattr(mapping_wizard_module, "MappingWizard", _StubWizard)

    df = pd.DataFrame({"alias": ["foo"]})
    mapped, asignadas = mapping_wizard_module.wizard_qc_mapeo(df)

    assert mapped is df
    assert asignadas == {"alias": ("omitido", None)}
    assert captured["esenciales"] is None
    assert captured["no_esenciales"] is None
    assert captured["io"] is None


def test_resolve_remap_target_selection_accepts_number_and_name():
    todos = ["tel", "lat", "lon"]

    resolved = resolve_remap_target_selection(todos, "2")
    assert resolved.canonical == "lat"
    assert resolved.display_index == 2
    assert resolved.error is None

    resolved = resolve_remap_target_selection(todos, "LoN")
    assert resolved.canonical == "lon"
    assert resolved.display_index == 3
    assert resolved.error is None


def test_resolve_remap_target_selection_reports_errors():
    todos = ["tel", "lat"]

    resolved = resolve_remap_target_selection(todos, "9")
    assert resolved.canonical is None
    assert resolved.error == "[QC] Número fuera de rango."

    resolved = resolve_remap_target_selection(todos, "alias")
    assert resolved.canonical is None
    assert resolved.error == "[QC] Canónico inválido. Usá número o nombre de la lista."


def test_resolve_essential_column_selection_handles_menu_and_assign():
    used = set()
    menu = ["c1", "c2"]

    decision = resolve_essential_column_selection("?", menu, used)
    assert decision.action == "show_menu"

    decision = resolve_essential_column_selection("2", menu, used)
    assert decision.action == "assign"
    assert decision.column == "c2"


def test_resolve_essential_column_selection_flags_errors_and_duplicates():
    used = {"c1"}
    menu = ["c1", "c2"]

    decision = resolve_essential_column_selection("", menu, used)
    assert decision.action == "omit"

    decision = resolve_essential_column_selection("9", menu, used)
    assert decision.action == "invalid"

    decision = resolve_essential_column_selection("1", menu, used)
    assert decision.action == "duplicate"
    assert decision.column == "c1"


def test_resolve_non_essential_selection_supports_menu_fixed_and_columns():
    menu = ["c1", "c2", "c3"]

    decision = resolve_non_essential_selection("?", menu)
    assert decision.action == "show_menu"

    decision = resolve_non_essential_selection("", menu)
    assert decision.action == "omit"

    decision = resolve_non_essential_selection("F valor", menu)
    assert decision.action == "fixed"
    assert decision.fixed_value == "valor"

    decision = resolve_non_essential_selection("2", menu)
    assert decision.action == "assign"
    assert decision.column == "c2"


def test_resolve_non_essential_selection_defaults_to_omit_on_invalid():
    menu = ["c1"]

    decision = resolve_non_essential_selection("99", menu)
    assert decision.action == "omit"

    decision = resolve_non_essential_selection("foo", menu)
    assert decision.action == "omit"


def test_resolve_confirm_loop_option_maps_primary_actions():
    decision = resolve_confirm_loop_option("")
    assert decision.action == "confirm"

    decision = resolve_confirm_loop_option("n")
    assert decision.action == "restart"

    decision = resolve_confirm_loop_option("R")
    assert decision.action == "remap"


def test_resolve_confirm_loop_option_flags_invalid_values():
    decision = resolve_confirm_loop_option("x")
    assert decision.action == "invalid"
    assert decision.message == "[QC] Opción inválida. Escribí S, N o R."


def test_apply_remap_single_selection_handles_menu_and_duplicates():
    assignments = {"tel": ("col", "c1"), "lat": ("col", "c2")}
    used = {"c1", "c2"}
    menu = ["c1", "c2", "c3"]

    result = apply_remap_single_selection("tel", "?", menu, True, assignments, used)
    assert result.show_menu and not result.applied

    result = apply_remap_single_selection("lat", "1", menu, True, assignments, used)
    assert result.duplicate_column == "c1"
    assert assignments["lat"] == ("col", "c2")
    assert used == {"c1", "c2"}


def test_apply_remap_single_selection_updates_used_columns_and_modes():
    assignments = {"tel": ("col", "c1")}
    used = {"c1"}
    menu = ["c1", "c2"]

    result = apply_remap_single_selection("tel", "2", menu, True, assignments, used)
    assert result.applied
    assert assignments["tel"] == ("col", "c2")
    assert used == {"c2"}

    result = apply_remap_single_selection("alias", "F valor fijo", menu, False, assignments, used)
    assert result.applied
    assert assignments["alias"] == ("fijo", "valor fijo")

    result = apply_remap_single_selection("alias", "", menu, False, assignments, used)
    assert assignments["alias"] == ("omitido", None)


def test_resolve_remap_single_flow_reports_menu_and_duplicates():
    assignments = {"tel": ("col", "c1"), "lat": ("col", "c2")}
    used = {"c1", "c2"}
    menu = ["c1", "c2", "c3"]

    flow = resolve_remap_single_flow("tel", "?", menu, True, assignments, used)
    assert flow.show_menu and "?" in flow.prompt_message

    flow = resolve_remap_single_flow("lat", "1", menu, True, assignments, used)
    assert flow.duplicate_column == "c1"

    flow = resolve_remap_single_flow("alias", "F fijo", menu, False, assignments, used)
    assert not flow.show_menu and flow.duplicate_column is None


def test_confirm_remap_selection_accepts_only_s():
    prompts = iter(["S", "n"])

    def fake_prompt(message: str) -> str:
        _ = message
        return next(prompts)

    assert confirm_remap_selection(fake_prompt, "tel", 1)
    assert not confirm_remap_selection(fake_prompt, "tel", 1)


def test_quick_remap_flow_maps_missing_recommended_field():
    df = pd.DataFrame({"dur_col": ["15"]})
    responses = ["", "", "", "s", "?", "1", "S"]
    recorder = _FakeIORecorder(responses)
    io = WizardIO(input_fn=recorder.input, output_fn=recorder.output)

    wizard = MappingWizard(df, esenciales=[], no_esenciales=[], io=io)
    mapped_df, _ = wizard.run()

    assert "duracion" in mapped_df.columns
    assert mapped_df.loc[0, "duracion"] == "15"
