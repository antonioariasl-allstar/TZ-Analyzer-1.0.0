"""Tests for tz_core.manual_flow helpers."""

import os

import pandas as pd
import pandas.testing as pdt

from tz_core.manual_flow import (
    apply_time_filter_prompt,
    TimeFilterResult,
    handle_manual_html_generation,
    write_minimal_filter_log_if_needed,
)


def _df(values):
    return pd.DataFrame({"fecha": values})


def test_apply_time_filter_prompt_skips_when_option_not_2():
    df = _df([1, 2, 3])

    def _should_not_run():
        raise AssertionError("No se deben solicitar filtros cuando la opción no es 2")

    result = apply_time_filter_prompt(
        option="1",
        df=df,
        solicitar_fn=_should_not_run,
        aplicar_fn=_should_not_run,
        output_fn=lambda _: None,
    )

    assert result.enabled is False
    assert result.summary is None
    assert result.filters is None
    pdt.assert_frame_equal(result.dataframe, df)


def test_apply_time_filter_prompt_applies_filters():
    df = _df([1, 2, 3])
    filtered = _df([2, 3])
    filtros = {"tipo": "dia"}

    def _fake_apply(ref_df, ref_filters):
        assert ref_df is df
        assert ref_filters is filtros
        return filtered, "Día específico"

    result = apply_time_filter_prompt(
        option="2",
        df=df,
        solicitar_fn=lambda: filtros,
        aplicar_fn=_fake_apply,
        output_fn=lambda _: None,
    )

    assert result.enabled is True
    assert result.summary == "Día específico"
    assert result.filters is filtros
    pdt.assert_frame_equal(result.dataframe, filtered)


def test_apply_time_filter_prompt_handles_errors():
    df = _df([1, 2, 3])
    mensajes = []

    def _fail_apply(*_, **__):
        raise RuntimeError("boom")

    result = apply_time_filter_prompt(
        option="2",
        df=df,
        solicitar_fn=lambda: {"tipo": "dia"},
        aplicar_fn=_fail_apply,
        output_fn=mensajes.append,
    )

    assert result.enabled is True
    assert result.summary is None
    assert result.filters is None
    pdt.assert_frame_equal(result.dataframe, df)
    assert any("boom" in msg for msg in mensajes)


def test_time_filter_result_empty_property():
    empty_df = pd.DataFrame(columns=["fecha"])
    result = TimeFilterResult(
        dataframe=empty_df,
        summary=None,
        filters=None,
        enabled=True,
    )

    assert result.empty is True


def test_handle_manual_html_generation_manual_mode_relocates_kmz():
    config = {"html": {"generar_en_modo_manual": True}}
    relocations = []
    mensajes = []

    resultado = handle_manual_html_generation(
        config=config,
        df=_df([1]),
        archivo_kml="archivo.kml",
        carpeta_salida="carpeta_salida",
        nombre_salida="CASO-123",
        hoja=None,
        carpeta_base="carpeta_base",
        logger=mensajes.append,
        output_fn=mensajes.append,
        generar_html_fn=lambda *args, **kwargs: "legacy.html",
        relocate_kmz_fn=lambda **kwargs: relocations.append(kwargs),
    )

    assert resultado is None
    assert relocations[0]["case_name"] == "CASO-123"
    assert relocations[0]["target_folder"] == "carpeta_salida"


def test_handle_manual_html_generation_legacy_path_is_returned():
    called = {"relocated": False}

    def _fail_relocate(**_):  # pragma: no cover - asegura que no se llama en modo legacy
        called["relocated"] = True
        raise AssertionError("No debe relocalizar en modo legacy")

    def _fake_generate(df, archivo_kml, carpeta_salida, nombre_salida, hoja, **kwargs):
        assert archivo_kml == "archivo.kml"
        assert carpeta_salida == "carpeta_salida"
        assert nombre_salida == "CASO-123"
        return os.path.join(carpeta_salida, f"{nombre_salida}.html")

    resultado = handle_manual_html_generation(
        config={"html": {"generar_en_modo_manual": False}},
        df=_df([1]),
        archivo_kml="archivo.kml",
        carpeta_salida="carpeta_salida",
        nombre_salida="CASO-123",
        hoja="Hoja1",
        carpeta_base="carpeta_base",
        logger=lambda *_: None,
        output_fn=lambda *_: None,
        generar_html_fn=_fake_generate,
        relocate_kmz_fn=_fail_relocate,
    )

    assert resultado.endswith("CASO-123.html")
    assert called["relocated"] is False


def test_write_minimal_filter_log_if_needed_generates_file(tmp_path):
    df = pd.DataFrame(
        {
            "lat": [13.7],
            "long": [-89.2],
            "antena": ["ANT-1"],
            "tel_contacto": ["503"],
        }
    )
    result = TimeFilterResult(
        dataframe=df,
        summary="Día específico",
        filters={"tipo": "dia"},
        enabled=True,
    )
    logs = []

    log_path = write_minimal_filter_log_if_needed(
        result=result,
        df=df,
        output_folder=str(tmp_path),
        logger=logs.append,
    )

    assert log_path is not None
    assert (tmp_path / "log_minimo.txt").exists()


def test_write_minimal_filter_log_if_needed_skips_when_disabled(tmp_path):
    df = _df([1])
    result = TimeFilterResult(
        dataframe=df,
        summary=None,
        filters=None,
        enabled=False,
    )

    log_path = write_minimal_filter_log_if_needed(
        result=result,
        df=df,
        output_folder=str(tmp_path),
        logger=lambda *_: None,
    )

    assert log_path is None
    assert not (tmp_path / "log_minimo.txt").exists()
