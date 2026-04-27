from __future__ import annotations

import itertools

import pandas as pd

from tz_core.ui_utils import (
    CaseIdentity,
    collect_manual_mode_context,
    gather_dataset_metadata,
    prompt_case_identity,
    collect_top_overrides,
    prompt_output_routing,
    summarize_outputs,
    suggest_case_name,
)


def test_collect_manual_mode_context_returns_option_and_config():
    inputs = iter(["2"])
    outputs: list[str] = []

    def fake_input(_prompt: str = "") -> str:
        return next(inputs, "")

    def fake_output(message: str) -> None:
        outputs.append(message)

    def fake_color(cfg):
        colored = dict(cfg or {})
        colored["color"] = "blue"
        return colored

    ctx = collect_manual_mode_context(
        config={"foo": 1},
        input_fn=fake_input,
        output_fn=fake_output,
        color_picker=fake_color,
    )

    assert ctx.option == "2"
    assert ctx.config["color"] == "blue"
    assert any("Seleccione el modo de procesamiento" in line for line in outputs)


def test_collect_manual_mode_context_loops_through_manual_mode():
    inputs = iter(["3", "", "1"])
    manual_calls = itertools.count()

    def fake_input(_prompt: str = "") -> str:
        return next(inputs, "")

    def fake_output(_message: str) -> None:
        pass

    def fake_color(cfg):
        return cfg or {}

    def manual_cb() -> None:
        next(manual_calls)

    ctx = collect_manual_mode_context(
        config={},
        input_fn=fake_input,
        output_fn=fake_output,
        color_picker=fake_color,
        manual_mode_callback=manual_cb,
    )

    assert ctx.option == "1"
    assert next(manual_calls) == 1


def test_collect_manual_mode_context_rejects_invalid_options():
    inputs = iter(["9", "2"])
    messages: list[str] = []

    def fake_output(message: str) -> None:
        messages.append(message)

    ctx = collect_manual_mode_context(
        config=None,
        input_fn=lambda _prompt="": next(inputs, ""),
        output_fn=fake_output,
        color_picker=lambda cfg: cfg or {},
    )

    assert ctx.option == "2"
    assert any("Opción inválida" in msg for msg in messages)


def test_gather_dataset_metadata_returns_dataframe_and_metadata():
    logs: list[str] = []
    outputs: list[str] = []
    df = pd.DataFrame([[1, 2, 3]], columns=["Hora Evento", "Fecha", "Lat"])

    result = gather_dataset_metadata(
        log_fn=logs.append,
        select_file=lambda: "bitacora.xlsx",
        select_sheet=lambda _path: "Hoja 1",
        load_dataframe=lambda _path, _sheet: (df.copy(), "Hoja Normalizada"),
        output_fn=outputs.append,
    )

    assert result is not None
    assert result.archivo == "bitacora.xlsx"
    assert result.hoja == "Hoja 1"
    assert list(result.columnas) == ["hora_evento", "fecha", "lat"]
    assert "Columnas después de normalización" in logs[-1]
    assert not outputs


def test_gather_dataset_metadata_returns_none_if_no_file_selected():
    messages: list[str] = []

    result = gather_dataset_metadata(
        log_fn=lambda _msg: None,
        select_file=lambda: "",
        select_sheet=lambda _path: "Hoja 1",
        load_dataframe=lambda _path, _sheet: (pd.DataFrame(), "Hoja"),
        output_fn=messages.append,
    )

    assert result is None
    assert any("No se seleccionó un archivo" in msg for msg in messages)


def test_gather_dataset_metadata_handles_loader_errors():
    outputs: list[str] = []
    logs: list[str] = []

    def _loader(_path: str, _sheet: str):
        raise ValueError("boom")

    result = gather_dataset_metadata(
        log_fn=logs.append,
        select_file=lambda: "bitacora.xlsx",
        select_sheet=lambda _path: "Hoja 1",
        load_dataframe=_loader,
        output_fn=outputs.append,
    )

    assert result is None
    assert any("Error al leer el Excel" in msg for msg in outputs)
    assert any("ERROR CRÍTICO" in log for log in logs)


def test_prompt_case_identity_respects_user_choice():
    df = pd.DataFrame({"imei": ["12345"]})

    identity = prompt_case_identity(
        df=df,
        input_fn=lambda _prompt="": "I",
        output_fn=lambda _msg: None,
        now_fn=lambda: pd.Timestamp("2024-01-01 10:00"),
    )

    assert identity.mode == "IMEI"
    assert identity.primary_id == "12345"
    assert identity.base_name.startswith("IMEI_12345")


def test_prompt_case_identity_auto_detects_tel():
    df = pd.DataFrame({"tel": ["555", "555"]})
    outputs: list[str] = []

    identity = prompt_case_identity(
        df=df,
        input_fn=lambda _prompt="": "",
        output_fn=outputs.append,
        now_fn=lambda: pd.Timestamp("2024-02-02 09:30"),
    )

    assert identity.mode == "TEL"
    assert identity.primary_id == "555"
    assert any("Tipo de bitácora establecido" in msg for msg in outputs)


def test_prompt_case_identity_handles_missing_columns():
    df = pd.DataFrame({"otro": [1, 2]})

    identity = prompt_case_identity(
        df=df,
        input_fn=lambda _prompt="": "T",
        output_fn=lambda _msg: None,
        now_fn=lambda: pd.Timestamp("2024-03-03 08:15"),
    )

    assert identity.primary_id is None
    assert identity.mode == "TEL"
    assert identity.base_name.startswith("CASO")


def test_suggest_case_name_builds_base_from_identity_and_filters():
    df = pd.DataFrame(
        {
            "tel": ["111", "222"],
            "alias": ["Alias", "Alias"],
            "fecha": ["01-01-2024", "02-01-2024"],
        }
    )
    identity = CaseIdentity(mode="TEL", primary_id=None, alias_short="AL", base_name="")

    suggestion = suggest_case_name(
        df=df,
        identity=identity,
        filters={"tipo": "dia", "dia": "03-01-2024"},
        timestamp_fn=lambda: pd.Timestamp("2024-01-05 10:00"),
        sanitize_fn=lambda value: value,
    )

    assert suggestion.base_name.startswith("TEL_multi2_Alias_20240105_1000")
    assert suggestion.tel_part == "111"
    assert "dia_2024-01-03" in suggestion.filter_suffix


def test_suggest_case_name_falls_back_to_alias_part_when_missing_column():
    df = pd.DataFrame(
        {
            "tel": ["999"],
            "alias_usuario": ["Apodo"],
            "fecha": ["05-01-2024"],
        }
    )
    identity = CaseIdentity(mode="IMEI", primary_id=None, alias_short="", base_name="")

    suggestion = suggest_case_name(
        df=df,
        identity=identity,
        filters=None,
        timestamp_fn=lambda: pd.Timestamp("2024-01-06 12:30"),
        sanitize_fn=lambda value: value.lower(),
    )

    assert suggestion.alias_part == "Apodo"
    assert suggestion.alias_id == "Apodo"
    assert suggestion.base_name.startswith("imei_desconocido_apodo_20240106_1230")


def test_collect_top_overrides_uses_defaults_and_parses_values():
    inputs = iter(["15", ""])

    def fake_input(_prompt: str = "") -> str:
        return next(inputs, "")

    selection = collect_top_overrides(
        input_fn=fake_input,
        output_fn=lambda _msg: None,
        default_antennas=7,
        default_contacts=9,
    )

    assert selection.antennas == 15
    assert selection.contacts == 9  # default applied


def test_collect_top_overrides_guard_against_invalid_numbers():
    outputs: list[str] = []
    inputs = iter(["abc", "-5"])

    selection = collect_top_overrides(
        input_fn=lambda _prompt="": next(inputs, ""),
        output_fn=outputs.append,
    )

    assert selection.antennas == 10  # fallback
    assert selection.contacts == 0   # max(0, -5)
    assert any("Valor inválido" in msg for msg in outputs)


def test_collect_top_overrides_accepts_mismo_keyword():
    inputs = iter(["12", "mismo"])

    selection = collect_top_overrides(
        input_fn=lambda _prompt="": next(inputs, ""),
        output_fn=lambda _msg: None,
        default_antennas=8,
        default_contacts=5,
    )

    assert selection.antennas == 12
    assert selection.contacts == 12


def test_prompt_output_routing_creates_paths_and_respects_rename():
    created_dirs: list[str] = []

    routing = prompt_output_routing(
        base_name="CASO_AUTO",
        input_fn=lambda _prompt="": "Caso Final",
        output_fn=lambda _msg: None,
        sanitize_fn=lambda value: value.replace(" ", "_").upper(),
        select_folder=lambda: "/tmp",
        cwd_fn=lambda: "/cwd",
        ensure_dir=created_dirs.append,
        separate_kml=True,
    )

    assert routing.base_name == "CASO_FINAL"
    assert routing.base_folder == "/tmp"
    assert routing.kml_path.endswith("CASO_FINAL_mapeo.kml")
    assert len(created_dirs) == 2  # carpeta del caso + subcarpeta kml


def test_prompt_output_routing_handles_hex_and_folder_fallback():
    outputs: list[str] = []

    def select_folder() -> str:
        raise RuntimeError("no ui")

    routing = prompt_output_routing(
        base_name="CASO_AUTO",
        input_fn=lambda _prompt="": "#fff",
        output_fn=outputs.append,
        sanitize_fn=lambda value: value or "CASO_AUTO",
        select_folder=select_folder,
        cwd_fn=lambda: "/home/user",
        ensure_dir=lambda _path: None,
        separate_kml=False,
    )

    assert routing.base_folder == "/home/user"
    assert routing.kml_path.endswith("CASO_AUTO_mapeo.kml")
    assert any("color hex" in msg.lower() for msg in outputs)


def test_summarize_outputs_prints_kml_and_kmz():
    messages: list[str] = []

    summarize_outputs(
        config={"salida": {"solo_kmz": False, "separar_kml_kmz": False}},
        output_fn=messages.append,
        kml_path="/tmp/CASO/kml/CASO_mapeo.kml",
        error_report_path="/tmp/CASO/errores.txt",
        discarded_coords=4,
        path_exists=lambda path: True,
    )

    assert any("KML generado" in msg for msg in messages)
    assert any("KMZ generado" in msg for msg in messages)
    assert any("Filas descartadas" in msg for msg in messages)
    assert any("errores" in msg.lower() for msg in messages)


def test_summarize_outputs_handles_separate_dirs_and_solo_kmz():
    messages: list[str] = []

    kmz_path = summarize_outputs(
        config={"salida": {"solo_kmz": True, "separar_kml_kmz": True}},
        output_fn=messages.append,
        kml_path="/cases/out/kml/CASO_mapeo.kml",
        error_report_path=None,
        discarded_coords=0,
        path_exists=lambda path: False,
    )

    assert kmz_path.replace("\\", "/") == "/cases/out/kmz/CASO_mapeo.kmz"
    assert not any("KML generado" in msg for msg in messages)
    assert any("Filas descartadas" in msg for msg in messages)
