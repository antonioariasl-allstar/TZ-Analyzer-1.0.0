"""Tests de integracion QC-3 y QC-HITO2 (capacidades)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from tz_core.capabilities import CapabilitiesReport
from tz_core.exceptions import ArchivoNoProcesableError
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


def _base_kwargs(df: pd.DataFrame, tmp_path, output_fn=None) -> dict:
    """Kwargs base para `run_ingestion_pipeline`.

    `config_path` siempre apunta a un archivo temporal: `run_schema_location_assistant`
    persiste un snapshot del config recibido de forma incondicional (ver
    `_persist_config_snapshot` en schema_utils.py), y sin este aislamiento el
    valor por defecto ("config.json", ruta relativa) sobrescribiría el
    config.json real de la raíz del repo cuando el proceso corre desde ahí.
    """
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
        config_path=str(tmp_path / "config.json"),
        # La columna 'duracion' de _make_df() es numérica ambigua; estas pruebas
        # no versan sobre duración, así que se inyecta una respuesta fija para
        # no bloquear en input() real ni depender de stdin bajo pytest.
        preguntar_unidad_duracion_fn=lambda: "desconocida",
    )


def _patch_time_filter(df: pd.DataFrame):
    time_result = TimeFilterResult(dataframe=df, summary=None, filters=None, enabled=False)
    return patch(
        "tz_core.ingestion_pipeline.apply_time_filter_prompt",
        return_value=time_result,
    )


def test_run_qc_es_llamado(tmp_path):
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=90, bloqueante=False, resumen=["OK: sin problemas detectados"]
            )
            run_ingestion_pipeline(**_base_kwargs(df, tmp_path))
            mock_qc.assert_called_once()
            args, _ = mock_qc.call_args
            assert isinstance(args[0], pd.DataFrame)


def test_score_y_resumen_impresos(tmp_path):
    df = _make_df()
    mensajes = []
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=75, bloqueante=False, resumen=["ADVERTENCIA: contacto vacio en 5%"]
            )
            run_ingestion_pipeline(**_base_kwargs(df, tmp_path, output_fn=mensajes.append))
    texto = "\n".join(mensajes)
    assert "75/100" in texto
    assert "ADVERTENCIA" in texto


def test_bloqueante_respuesta_n_aborta(tmp_path):
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", return_value="N"):
                with pytest.raises(ArchivoNoProcesableError):
                    run_ingestion_pipeline(**_base_kwargs(df, tmp_path))


def test_bloqueante_respuesta_s_continua(tmp_path):
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=20, bloqueante=True, resumen=["CRITICO: columna contacto ausente"]
            )
            with patch("tz_core.ingestion_pipeline.safe_input", return_value="S"):
                result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))
                assert result is not None


def test_no_bloqueante_no_interrumpe(tmp_path):
    df = _make_df()
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=95, bloqueante=False, resumen=["OK: sin problemas detectados"]
            )
            with patch("builtins.input") as mock_input:
                result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))
                mock_input.assert_not_called()
                assert result is not None


def test_config_path_real_no_se_modifica(tmp_path):
    """TAREA A: correr el flujo con manual_qc_mapping=False no debe tocar el
    config.json real del repo — la escritura de snapshot debe ir a tmp_path."""
    import hashlib
    import os

    real_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    before = hashlib.sha256(open(real_config, "rb").read()).hexdigest()

    df = _make_df()
    tmp_config = tmp_path / "config.json"
    with _patch_time_filter(df):
        with patch("tz_core.ingestion_pipeline.run_qc") as mock_qc:
            mock_qc.return_value = MagicMock(
                score=90, bloqueante=False, resumen=["OK: sin problemas detectados"]
            )
            run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    after = hashlib.sha256(open(real_config, "rb").read()).hexdigest()
    assert before == after, "config.json real fue modificado por el test — aislamiento roto."
    assert tmp_config.exists(), "El snapshot de config debía escribirse en tmp_path."


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


# ─────────────────────────────────────────────────────────────────────────
# HITO 2 — integración CapabilitiesReport / QC
# ─────────────────────────────────────────────────────────────────────────

def _make_fx02_df(rows: int = 5) -> pd.DataFrame:
    """Bitácora sin 'contacto' ni 'interaccion' (caso FX-02)."""
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * rows,
        "hora": ["10:00:00"] * rows,
        "tel": ["60001234"] * rows,
        "antena": ["ANT-01"] * rows,
        "lat": [13.7] * rows,
        "long": [-89.2] * rows,
    })


class _SkippingWizardIO:
    """Wizard IO que responde "Enter" (vacío) a cualquier prompt.

    Necesario para fixtures que omiten campos "esenciales" (contacto,
    interaccion): ``run_schema_location_assistant`` (schema_utils.py, fuera
    de alcance de este hito) pide interactivamente una columna sustituta
    para cada campo faltante. El ``MagicMock()`` por defecto de
    ``_base_kwargs`` responde ahí con otro MagicMock, y
    ``int(MagicMock())`` devuelve 1 en vez de fallar — el asistente lo
    interpreta como "elegí la primera columna del menú" y renombra una
    columna real (p.ej. 'fecha') al campo faltante, corrompiendo el
    DataFrame. Responder con "" reproduce el comportamiento real de un
    usuario que pulsa Enter para omitir, dejando el campo genuinamente
    ausente — que es lo que estos tests de capacidades necesitan probar.
    """

    def prompt(self, _message: str) -> str:
        return ""

    def write(self, _message: str) -> None:
        pass


def test_capabilities_report_se_agrega_a_ingestion_result(tmp_path):
    """TAREA 7 caso 12: IngestionResult conserva el CapabilitiesReport calculado."""
    df = _make_df()
    with _patch_time_filter(df):
        result = run_ingestion_pipeline(**_base_kwargs(df, tmp_path))

    assert isinstance(result.capabilities_report, CapabilitiesReport)
    assert result.capabilities_report.procesable is True
    assert result.capabilities_report.capacidad("identificacion").disponible is True
    assert result.capabilities_report.capacidad("antenas").disponible is True
    assert result.capabilities_report.capacidad("kml").disponible is True


def test_fx02_sin_contacto_ni_interaccion_no_aparece_prompt_critico(tmp_path):
    """TAREA 7 caso 9: FX-02 no debe disparar el prompt '¿Desea continuar?' ni
    abortar — contacto/interaccion ausentes ya no son bloqueantes."""
    df = _make_fx02_df()
    kwargs = _base_kwargs(df, tmp_path)
    kwargs["wizard_io_factory"] = lambda: _SkippingWizardIO()
    with _patch_time_filter(df):
        with patch("builtins.input") as mock_input:
            result = run_ingestion_pipeline(**kwargs)
            mock_input.assert_not_called()

    assert result.capabilities_report.procesable is True
    assert result.capabilities_report.capacidad("contactos").disponible is False
    assert result.capabilities_report.capacidad("tipo_evento").disponible is False
    assert result.capabilities_report.capacidad("antenas").disponible is True
    assert result.capabilities_report.capacidad("kml").disponible is True
    assert result.capabilities_report.capacidad("cronologia").disponible is True


def test_resumen_cli_capacidades_muestra_estados_correctos(tmp_path):
    """TAREA 7 caso 13: el resumen CLI usa las etiquetas [OK]/[NO DISPONIBLE]
    esperadas, con el motivo legible para las capacidades no disponibles."""
    df = _make_fx02_df()
    mensajes = []
    kwargs = _base_kwargs(df, tmp_path, output_fn=mensajes.append)
    kwargs["wizard_io_factory"] = lambda: _SkippingWizardIO()
    with _patch_time_filter(df):
        with patch("builtins.input"):
            run_ingestion_pipeline(**kwargs)

    texto = "\n".join(mensajes)
    assert "Capacidades detectadas:" in texto
    assert "[OK] Cronología" in texto
    assert "[OK] Antenas" in texto
    assert "[OK] KML" in texto
    assert "[NO DISPONIBLE] Contactos — falta contacto válido" in texto
    assert "[NO DISPONIBLE] Tipo de evento — falta interacción" in texto


def test_score_usa_etiqueta_completitud_para_analisis_integral(tmp_path):
    """TAREA 7 caso 14: la etiqueta del score ya no dice 'Calidad del
    archivo', sino 'Completitud del archivo para análisis integral'."""
    df = _make_df()
    mensajes = []
    with _patch_time_filter(df):
        run_ingestion_pipeline(**_base_kwargs(df, tmp_path, output_fn=mensajes.append))

    texto = "\n".join(mensajes)
    assert "Completitud del archivo para análisis integral:" in texto
    assert "Calidad del archivo" not in texto


def test_dataframe_vacio_tras_validacion_aborta_por_capacidades(tmp_path):
    """TAREA 7 caso 10: si el df queda vacío (0 filas), CapabilitiesReport lo
    marca procesable=False y el pipeline aborta sin ofrecer continuar."""
    df = _make_df()
    kwargs = _base_kwargs(df, tmp_path)
    kwargs["validar_datos_fn"] = lambda d, _cols: (d.iloc[0:0], [])

    with _patch_time_filter(df):
        with patch("builtins.input") as mock_input:
            with pytest.raises(ArchivoNoProcesableError):
                run_ingestion_pipeline(**kwargs)
            mock_input.assert_not_called()


def test_sin_datos_significativos_aborta_por_capacidades(tmp_path):
    """TAREA 7 caso 11: un DataFrame con filas pero sin ningún valor
    analíticamente significativo (solo placeholders) también se marca
    procesable=False y aborta."""
    df = pd.DataFrame({
        "fecha": ["-", "N/A"],
        "contacto": ["", "Sin Inf."],
    })
    kwargs = _base_kwargs(df, tmp_path)
    kwargs["original_columns"] = list(df.columns)
    kwargs["wizard_io_factory"] = lambda: _SkippingWizardIO()

    with _patch_time_filter(df):
        with pytest.raises(ArchivoNoProcesableError):
            run_ingestion_pipeline(**kwargs)
