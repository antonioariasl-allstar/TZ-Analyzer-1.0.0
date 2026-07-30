"""Tests de integracion QC-3."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from tz_core.ingestion_pipeline import resolve_date_dayfirst, run_ingestion_pipeline
from tz_core.manual_flow import TimeFilterResult


def _make_df(rows: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * rows,
        "hora": ["10:00:00"] * rows,
        "interaccion": ["VOZ"] * rows,
        "contacto": ["70001234"] * rows,
        "tel": ["60001234"] * rows,
        "duracion": [60] * rows,
        "antena": ["ANT-01"] * rows,
        "lat": [13.7] * rows,
        "long": [-89.2] * rows,
    })


def _base_kwargs(df: pd.DataFrame, output_fn=None) -> dict:
    return dict(
        df=df,
        config={},
        original_columns=list(df.columns),
        manual_qc_mapping=False,
        alias_visibles=None,
        wizard_io_factory=MagicMock(),
        persist_synonym_fn=MagicMock(),
        validate_schema_fn=MagicMock(),
        validar_datos_fn=lambda d, _cols: (d, []),
        time_filter_option="ninguno",
        solicitar_filtros_fn=MagicMock(),
        aplicar_filtros_fn=MagicMock(),
        output_fn=output_fn or (lambda _: None),
        logger=lambda _: None,
        run_manual_mapping_fn=None,
    )


def _patch_time_filter(df: pd.DataFrame):
    time_result = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)
    return patch(
        "tz_core.ingestion_pipeline.apply_time_filter_prompt",
        return_value=time_result,
    )


def test_run_qc_es_llamado():
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=90, bloqueante=False, resumen=["OK: sin problemas detectados"]
            )
            run_ingestion_pipeline(**_base_kwargs(df))
            mock_qc.assert_called_once()
            args, _ = mock_qc.call_args
            assert isinstance(args[0], pd.DataFrame)


def test_score_y_resumen_impresos():
    df = _make_df()
    mensajes = []
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=75, bloqueante=False, resumen=["ADVERTENCIA: contacto vacio en 5%"]
            )
            run_ingestion_pipeline(**_base_kwargs(df, output_fn=mensajes.append))
    texto = "\n".join(mensajes)
    assert "75/100" in texto
    assert "ADVERTENCIA" in texto


def test_bloqueante_respuesta_n_aborta():
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", return_value="N"):
                with pytest.raises(SystemExit):
                    run_ingestion_pipeline(**_base_kwargs(df))


def test_bloqueante_respuesta_s_continua():
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", return_value="S"):
                result = run_ingestion_pipeline(**_base_kwargs(df))
                assert result is not None


def test_no_bloqueante_no_interrumpe():
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=95, bloqueante=False, resumen=["OK: sin problemas detectados"]
            )
            with patch("builtins.input") as mock_input:
                result = run_ingestion_pipeline(**_base_kwargs(df))
                mock_input.assert_not_called()
                assert result is not None


def test_resolve_date_dayfirst_pregunta_si_todas_son_ambiguas():
    df = pd.DataFrame({"fecha": ["05/01/2026", "06/12/2026"]})
    assert resolve_date_dayfirst(
        df,
        config={"excel": {"date_order": "ASK"}},
        prompt_fn=lambda _prompt: "2",
    ) is False


def test_resolve_date_dayfirst_detecta_mdy_con_dia_mayor_que_12():
    df = pd.DataFrame({"fecha": ["05/13/2026"]})
    assert resolve_date_dayfirst(
        df,
        config={"excel": {"date_order": "ASK"}},
        prompt_fn=lambda _prompt: pytest.fail("no debe preguntar"),
    ) is False
