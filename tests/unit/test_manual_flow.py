"""Tests for tz_core.manual_flow helpers."""

import pandas as pd
import pandas.testing as pdt

from tz_core.manual_flow import apply_time_filter_prompt, TimeFilterResult


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
