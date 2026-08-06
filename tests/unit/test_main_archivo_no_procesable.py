"""FASE 0 WEB — main() debe traducir ArchivoNoProcesableError al sys.exit(0)
histórico que antes vivía dentro de run_ingestion_pipeline.

No se toca run_tz_analysis() (fuera de alcance): este test llama a main()
directamente, mockeando solo los puntos de entrada interactivos previos a
la ingesta (selección de modo/archivo/hoja/color) para llegar al punto
donde antes ocurría sys.exit(0) y comprobar que el comportamiento visible
del CLI (abortar limpio, código de salida 0, sin traceback) no cambió.
"""
from __future__ import annotations

import builtins

import pandas as pd
import pytest

import script_principal_bitacoras_refactory as app
from tz_core.exceptions import ArchivoNoProcesableError


def test_main_preserva_sys_exit_0_historico_ante_archivo_no_procesable(monkeypatch, tmp_path):
    app.bootstrap_config()
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    monkeypatch.setattr(app, "seleccionar_archivo", lambda: "dummy.xlsx")
    monkeypatch.setattr(app, "seleccionar_hoja_visible", lambda _archivo: None)
    monkeypatch.setattr(
        app,
        "cargar_excel_con_normalizacion",
        lambda _archivo, _hoja: (pd.DataFrame({"col_a": [1, 2, 3]}), "Hoja1"),
    )
    monkeypatch.setattr(app, "solicitar_color_tema", lambda cfg: cfg)

    def _raise_no_procesable(**_kwargs):
        raise ArchivoNoProcesableError("archivo sintético sin datos procesables (prueba)")

    monkeypatch.setattr(app, "run_ingestion_pipeline", _raise_no_procesable)

    with pytest.raises(SystemExit) as excinfo:
        app.main()

    assert excinfo.value.code == 0
