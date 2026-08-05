"""FX-02 — Hito 1.1, TAREA B/C/D: pregunta QC de duración conectada a
`run_ingestion_pipeline` y propagación de `DuracionEstado` en `IngestionResult`.

La función de pregunta es inyectable (`preguntar_unidad_duracion_fn`), por lo
que estas pruebas nunca llaman a `input()` real ni dependen de stdin.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tz_core.bitacora_normalization import DuracionEstado
from tz_core.ingestion_pipeline import run_ingestion_pipeline
from tz_core.manual_flow import TimeFilterResult


def _make_df(duracion_valores=None, duracion_col="duracion", incluir_duracion=True):
    data = {
        "fecha": ["2024-01-01"] * 3,
        "hora": ["10:00:00"] * 3,
        "interaccion": ["VOZ"] * 3,
        "contacto": ["70001234"] * 3,
        "tel": ["60001234"] * 3,
        "antena": ["ANT-01"] * 3,
        "lat": [13.7] * 3,
        "long": [-89.2] * 3,
    }
    if incluir_duracion:
        data[duracion_col] = duracion_valores if duracion_valores is not None else [30, 5400, 120]
    return pd.DataFrame(data)


def _base_kwargs(df: pd.DataFrame, tmp_path, preguntar_unidad_duracion_fn=None) -> dict:
    kwargs = dict(
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
        output_fn=lambda _msg: None,
        logger=lambda _msg: None,
        run_manual_mapping_fn=None,
        config_path=str(tmp_path / "config.json"),
    )
    if preguntar_unidad_duracion_fn is not None:
        kwargs["preguntar_unidad_duracion_fn"] = preguntar_unidad_duracion_fn
    return kwargs


def _patch_time_filter(df: pd.DataFrame):
    time_result = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)
    return patch(
        "tz_core.ingestion_pipeline.apply_time_filter_prompt",
        return_value=time_result,
    )


def _run(df, tmp_path, preguntar_unidad_duracion_fn=None):
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            return run_ingestion_pipeline(**_base_kwargs(df, tmp_path, preguntar_unidad_duracion_fn))


# 1. Genérica numérica -> pregunta exactamente una vez
def test_columna_generica_numerica_pregunta_una_vez(tmp_path):
    df = _make_df([30, 5400, 120])
    llamadas = []

    def _fake_pregunta():
        llamadas.append(1)
        return "desconocida"

    _run(df, tmp_path, preguntar_unidad_duracion_fn=_fake_pregunta)
    assert len(llamadas) == 1


# 2. Respuesta 1 (ya resuelta a "segundos") -> segura/segundos
def test_respuesta_segundos_resulta_en_segura_segundos(tmp_path):
    df = _make_df([30, 5400, 120])
    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=lambda: "segundos")
    assert result.duracion_estado.estado == "segura"
    assert result.duracion_estado.unidad == "segundos"


# 3. Respuesta 2 (ya resuelta a "minutos") -> segura/minutos
def test_respuesta_minutos_resulta_en_segura_minutos(tmp_path):
    df = _make_df([30, 5400, 120])
    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=lambda: "minutos")
    assert result.duracion_estado.estado == "segura"
    assert result.duracion_estado.unidad == "minutos"


# 4. Respuesta 3 ("desconocida") -> ambigua/desconocida
def test_respuesta_desconocida_resulta_en_ambigua(tmp_path):
    df = _make_df([30, 5400, 120])
    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=lambda: "desconocida")
    assert result.duracion_estado.estado == "ambigua"
    assert result.duracion_estado.unidad == "desconocida"


# 5. Enter (preguntar_unidad_duracion_qc real, prompt vacío) -> ambigua/desconocida
def test_enter_real_resulta_en_ambigua(tmp_path):
    from tz_core.bitacora_normalization import preguntar_unidad_duracion_qc

    df = _make_df([30, 5400, 120])
    result = _run(
        df, tmp_path,
        preguntar_unidad_duracion_fn=lambda: preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: ""),
    )
    assert result.duracion_estado.estado == "ambigua"
    assert result.duracion_estado.unidad == "desconocida"


# 6. HH:MM:SS -> no pregunta
def test_formato_hhmmss_no_pregunta(tmp_path):
    df = _make_df(["00:00:30", "01:30:00", "00:02:00"])

    def _no_deberia_llamarse():
        raise AssertionError("No debe preguntarse unidad para formato HH:MM:SS")

    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=_no_deberia_llamarse)
    assert result.duracion_estado.estado == "segura"
    assert result.duracion_estado.unidad == "hhmmss"


# 7. Encabezado duracion_seg -> no pregunta
def test_encabezado_duracion_seg_no_pregunta(tmp_path):
    df = _make_df([30, 5400, 120], duracion_col="duracion_seg")

    def _no_deberia_llamarse():
        raise AssertionError("No debe preguntarse unidad cuando el encabezado declara segundos")

    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=_no_deberia_llamarse)
    assert result.duracion_estado.estado == "segura"
    assert result.duracion_estado.unidad == "segundos"


# 8. Duración ausente -> no pregunta
def test_duracion_ausente_no_pregunta(tmp_path):
    df = _make_df(incluir_duracion=False)

    def _no_deberia_llamarse():
        raise AssertionError("No debe preguntarse unidad si la columna de duración está ausente")

    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=_no_deberia_llamarse)
    assert result.duracion_estado.estado == "ausente"


# 9. Duración vacía -> no pregunta
def test_duracion_vacia_no_pregunta(tmp_path):
    df = _make_df([None, None, None])

    def _no_deberia_llamarse():
        raise AssertionError("No debe preguntarse unidad si la columna de duración está vacía")

    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=_no_deberia_llamarse)
    assert result.duracion_estado.estado == "ausente"
    assert result.duracion_estado.motivo == "sin_valores"


# 10. IngestionResult conserva el DuracionEstado final (no None)
def test_ingestion_result_conserva_duracion_estado_final():
    from dataclasses import fields
    assert "duracion_estado" in {f.name for f in fields(__import__(
        "tz_core.ingestion_pipeline", fromlist=["IngestionResult"]
    ).IngestionResult)}


def test_ingestion_result_duracion_estado_es_instancia_valida(tmp_path):
    df = _make_df([30, 5400, 120])
    result = _run(df, tmp_path, preguntar_unidad_duracion_fn=lambda: "segundos")
    assert isinstance(result.duracion_estado, DuracionEstado)
    assert result.duracion_estado.confiable is True
