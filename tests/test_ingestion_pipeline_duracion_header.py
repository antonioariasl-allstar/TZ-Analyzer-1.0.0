"""FX-02 — Hito 1: preservación del encabezado original de duración.

Verifica que `run_ingestion_pipeline` ya no descarta la asignación
'duracion' devuelta por el wizard QC manual, sino que la expone en
`IngestionResult.duracion_encabezado_original` para la ejecución actual.
No se persiste en config.json ni se usa df.attrs como mecanismo principal.
"""
from unittest.mock import MagicMock, patch

import pandas as pd

from tz_core.ingestion_pipeline import run_ingestion_pipeline
from tz_core.manual_flow import TimeFilterResult


def _make_df() -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * 3,
        "hora": ["10:00:00"] * 3,
        "dur_llamada_bruta": [30, 5400, 120],
        "antena": ["ANT-01"] * 3,
        "lat": [13.7] * 3,
        "long": [-89.2] * 3,
    })


def _base_kwargs(df: pd.DataFrame, tmp_path, run_manual_mapping_fn=None) -> dict:
    return dict(
        df=df,
        config={},
        original_columns=list(df.columns),
        manual_qc_mapping=run_manual_mapping_fn is not None,
        alias_visibles=None,
        wizard_io_factory=MagicMock(),
        persist_synonym_fn=MagicMock(),
        validate_schema_fn=MagicMock(),
        validar_datos_fn=lambda d, _cols: (d, []),
        time_filter_option="ninguno",
        solicitar_filtros_fn=MagicMock(),
        aplicar_filtros_fn=MagicMock(),
        output_fn=lambda _msg: None,
        logger=lambda _msg: None,
        run_manual_mapping_fn=run_manual_mapping_fn,
        config_path=str(tmp_path / "config.json"),
        # dur_llamada_bruta/duracion son ambiguas; estas pruebas versan sobre
        # preservación de encabezado, no sobre la pregunta QC de unidad.
        preguntar_unidad_duracion_fn=lambda: "desconocida",
    )


def _patch_time_filter(df: pd.DataFrame):
    time_result = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)
    return patch(
        "tz_core.ingestion_pipeline.apply_time_filter_prompt",
        return_value=time_result,
    )


def test_preserva_encabezado_original_de_duracion_tras_wizard_manual(tmp_path):
    df = _make_df()

    def _fake_manual_mapping(df_in, *, wizard_io):
        renombrado = df_in.rename(columns={"dur_llamada_bruta": "duracion"})
        asignaciones = {"duracion": ("col", "dur_llamada_bruta")}
        return renombrado, asignaciones

    with _patch_time_filter(df.rename(columns={"dur_llamada_bruta": "duracion"})):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path, run_manual_mapping_fn=_fake_manual_mapping))

    assert result.duracion_encabezado_original == "dur_llamada_bruta"


def test_encabezado_original_es_none_si_duracion_fue_omitida(tmp_path):
    df = _make_df()

    def _fake_manual_mapping(df_in, *, wizard_io):
        asignaciones = {"duracion": ("omitido", None)}
        return df_in, asignaciones

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path, run_manual_mapping_fn=_fake_manual_mapping))

    assert result.duracion_encabezado_original is None


def test_encabezado_original_es_none_sin_mapeo_manual(tmp_path):
    df = _make_df().rename(columns={"dur_llamada_bruta": "duracion"})

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path, run_manual_mapping_fn=None))

    assert result.duracion_encabezado_original is None
