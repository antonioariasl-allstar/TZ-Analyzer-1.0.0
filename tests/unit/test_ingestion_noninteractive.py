"""FASE 0 WEB — endurecimiento no interactivo de run_ingestion_pipeline.

Cubre dos bloqueadores P0 identificados para una orquestación no interactiva:

1. DATE ORDER: ``run_ingestion_pipeline`` debe aceptar un ``date_order_prompt_fn``
   explícito que se propaga hasta ``resolve_date_dayfirst(..., prompt_fn=...)``,
   sin depender de ``safe_input``/``input()`` cuando se proporciona.
2. ERRORES DE DOMINIO: los ``sys.exit()`` que existían dentro de la ruta de
   ingesta (archivo no procesable / QC bloqueante no confirmado) ahora deben
   lanzar ``ArchivoNoProcesableError`` en vez de terminar el proceso.

Los canarios sobre ``builtins.input`` y ``tz_core.ingestion_pipeline.safe_input``
usan ``pytest.fail()`` en vez de solo ``Mock.assert_not_called()``: si alguno
de los dos símbolos quedara capturado como default en tiempo de importación,
un mock sin parchear en su punto de uso podría "no ser llamado" trivialmente
mientras el `input()`/`safe_input` real sí se invoca — lo que un canario que
falla ruidosamente si se ejecuta detecta y un `assert_not_called()` no.
"""
from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tz_core.exceptions import ArchivoNoProcesableError
from tz_core.ingestion_pipeline import run_ingestion_pipeline, safe_input
from tz_core.manual_flow import TimeFilterResult


def _make_df(rows: int = 3) -> pd.DataFrame:
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


def _make_ambiguous_date_df(rows: int = 3) -> pd.DataFrame:
    """fecha "03/04/2024": día y mes <= 12 -> ambigua bajo date_order=ASK."""
    df = _make_df(rows)
    df["fecha"] = ["03/04/2024"] * rows
    return df


def _base_kwargs(df: pd.DataFrame, tmp_path, **overrides) -> dict:
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
        preguntar_unidad_duracion_fn=lambda: "desconocida",
    )
    kwargs.update(overrides)
    return kwargs


def _patch_time_filter(df: pd.DataFrame):
    time_result = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)
    return patch(
        "tz_core.ingestion_pipeline.apply_time_filter_prompt",
        return_value=time_result,
    )


# ─────────────────────────────────────────────────────────────────────────
# 1. DATE ORDER
# ─────────────────────────────────────────────────────────────────────────

def test_run_ingestion_pipeline_propaga_date_order_prompt_fn_explicito(tmp_path):
    """El nuevo parámetro debe llegar intacto hasta resolve_date_dayfirst."""
    df = _make_ambiguous_date_df()
    custom_prompt = lambda _msg: "2"

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            with patch(
                "tz_core.ingestion_pipeline.resolve_date_dayfirst", return_value=True
            ) as mock_resolve:
                run_ingestion_pipeline(
                    **_base_kwargs(df, tmp_path, date_order_prompt_fn=custom_prompt)
                )

    _, kwargs = mock_resolve.call_args
    assert kwargs["prompt_fn"] is custom_prompt


def test_run_ingestion_pipeline_sin_date_order_prompt_fn_usa_safe_input_por_defecto(tmp_path):
    """Sin el parámetro nuevo, el comportamiento CLI histórico se preserva:
    resolve_date_dayfirst sigue recibiendo `safe_input` como antes."""
    df = _make_df()

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            with patch(
                "tz_core.ingestion_pipeline.resolve_date_dayfirst", return_value=True
            ) as mock_resolve:
                run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    _, kwargs = mock_resolve.call_args
    assert kwargs["prompt_fn"] is safe_input


def test_date_order_ambiguo_resuelto_por_parametro_sin_llamar_safe_input(tmp_path):
    """Ruta no interactiva: una fecha ambigua se resuelve vía
    date_order_prompt_fn sin invocar safe_input ni input() en ningún punto."""
    df = _make_ambiguous_date_df()
    df["config_date_order"] = "ASK"  # no-op column, solo documenta intención

    def _canario_safe_input(*_a, **_k):
        pytest.fail("safe_input no debe invocarse: date_order_prompt_fn fue provisto")

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            with patch("tz_core.ingestion_pipeline.safe_input", side_effect=_canario_safe_input):
                with patch("builtins.input", side_effect=_canario_safe_input):
                    result = run_ingestion_pipeline(
                        **_base_kwargs(
                            df,
                            tmp_path,
                            config={"excel": {"date_order": "ASK"}},
                            date_order_prompt_fn=lambda _msg: "1",
                        )
                    )

    assert result is not None


def test_date_order_no_ambiguo_sigue_funcionando_sin_parametro_nuevo(tmp_path):
    """Fecha no ambigua (ISO) + comportamiento CLI histórico (sin el nuevo
    parámetro): no debe pedir nada, ni a safe_input ni a input() real."""
    df = _make_df()  # fecha ISO "2024-01-01", no ambigua

    def _canario(*_a, **_k):
        pytest.fail("No debía pedirse el orden de fechas: la muestra no es ambigua")

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            with patch("builtins.input", side_effect=_canario):
                result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    assert result is not None


# ─────────────────────────────────────────────────────────────────────────
# 2. ERRORES DE DOMINIO — ArchivoNoProcesableError en vez de sys.exit()
# ─────────────────────────────────────────────────────────────────────────

def test_archivo_no_procesable_lanza_archivo_no_procesable_error(tmp_path):
    """Antes: sys.exit(0). Ahora: ArchivoNoProcesableError con mensaje útil."""
    df = pd.DataFrame({
        "fecha": ["-", "N/A"],
        "contacto": ["", "Sin Inf."],
    })
    kwargs = _base_kwargs(
        df, tmp_path,
        original_columns=list(df.columns),
        wizard_io_factory=lambda: MagicMock(prompt=lambda _msg: "", write=lambda _msg: None),
    )

    def _canario(*_a, **_k):
        pytest.fail("No debía llamarse input() real en la ruta de archivo no procesable")

    with _patch_time_filter(df):
        with patch("builtins.input", side_effect=_canario):
            with pytest.raises(ArchivoNoProcesableError) as excinfo:
                run_ingestion_pipeline(**kwargs)

    assert str(excinfo.value)


def test_qc_bloqueante_respuesta_n_lanza_archivo_no_procesable_error_sin_safe_input(tmp_path):
    """Antes: sys.exit(0) tras preguntar por safe_input. Ahora: el nuevo
    qc_bloqueante_prompt_fn decide sin tocar safe_input, y el rechazo se
    traduce en ArchivoNoProcesableError."""
    df = _make_df()

    def _canario_safe_input(*_a, **_k):
        pytest.fail("safe_input no debe invocarse: qc_bloqueante_prompt_fn fue provisto")

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", side_effect=_canario_safe_input):
                with pytest.raises(ArchivoNoProcesableError):
                    run_ingestion_pipeline(
                        **_base_kwargs(df, tmp_path, qc_bloqueante_prompt_fn=lambda _msg: "N")
                    )


def test_qc_bloqueante_respuesta_s_continua_sin_safe_input(tmp_path):
    """Misma situación, pero la decisión inyectada es continuar ('S') — no
    debe abortar ni tocar safe_input."""
    df = _make_df()

    def _canario_safe_input(*_a, **_k):
        pytest.fail("safe_input no debe invocarse: qc_bloqueante_prompt_fn fue provisto")

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", side_effect=_canario_safe_input):
                result = run_ingestion_pipeline(
                    **_base_kwargs(df, tmp_path, qc_bloqueante_prompt_fn=lambda _msg: "S")
                )

    assert result is not None


def test_qc_bloqueante_sin_parametro_nuevo_usa_safe_input_por_defecto(tmp_path):
    """Comportamiento CLI histórico preservado: sin qc_bloqueante_prompt_fn,
    sigue usando safe_input (parcheable como antes) para decidir."""
    df = _make_df()

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", return_value="S") as mock_safe_input:
                result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    mock_safe_input.assert_called_once()
    assert result is not None


def test_run_ingestion_pipeline_completo_sin_ninguna_llamada_a_input(tmp_path):
    """Caso combinado del ítem 4: con parámetros explícitos, la ruta completa
    (wizard + QC + filtros) puede ejecutarse de punta a punta sin invocar
    input() real ni safe_input no inyectado — el requisito central de un
    futuro orquestador web no interactivo."""
    df = _make_df()

    def _canario(*_a, **_k):
        pytest.fail("Llamada no inyectada detectada durante ejecución no interactiva")

    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc", return_value=None):
            with patch("builtins.input", side_effect=_canario):
                with patch("tz_core.ingestion_pipeline.safe_input", side_effect=_canario):
                    result = run_ingestion_pipeline(
                        **_base_kwargs(
                            df,
                            tmp_path,
                            date_order_prompt_fn=lambda _msg: "1",
                            qc_bloqueante_prompt_fn=lambda _msg: "S",
                        )
                    )

    assert result is not None
    assert result.capabilities_report.procesable is True
