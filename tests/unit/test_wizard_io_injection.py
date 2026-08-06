"""FASE 0 WEB — endurecimiento no interactivo: cadena de WizardIO.

Verifica que ``input_fn``/``output_fn`` se propagan explícitamente por la
cadena ``_build_wizard_io`` -> ``build_wizard_io`` -> ``WizardIO``, y que
ninguno de los tres eslabones depende de una referencia a
``builtins.input``/``print`` capturada en tiempo de importación (lo que
antes impedía que un monkeypatch de ``builtins.input`` — o un futuro
orquestador no interactivo — tomara efecto sobre el default).
"""
from __future__ import annotations

import builtins

import pandas as pd
import pytest

import script_principal_bitacoras_refactory as app
from tz_core.manual_mapping_helpers import build_wizard_io, run_manual_mapping
from tz_core.mapping_wizard import MappingWizard, WizardIO


def test_wizard_io_usa_input_fn_output_fn_explicitos():
    """WizardIO(...) con input_fn/output_fn explícitos los usa tal cual."""
    entradas = iter(["col_a"])
    salidas = []

    io = WizardIO(input_fn=lambda _msg: next(entradas), output_fn=salidas.append)

    assert io.prompt("→ ") == "col_a"
    io.write("hola")
    assert salidas == ["hola"]


def test_wizard_io_default_resuelve_en_tiempo_de_instanciacion_no_de_import(monkeypatch):
    """WizardIO() creado DESPUÉS de parchear builtins.input/print debe usar
    la versión parcheada, no una referencia congelada al importar el módulo.

    Antes, ``input_fn: Callable = input`` como default de dataclass capturaba
    la referencia al builtin en el momento en que se importaba
    tz_core.mapping_wizard — mucho antes de que un test pudiera parchear
    builtins.input — y el monkeypatch quedaba sin efecto.
    """
    llamadas = []
    monkeypatch.setattr(builtins, "input", lambda _msg="": llamadas.append("input") or "respuesta")
    monkeypatch.setattr(builtins, "print", lambda *a, **k: llamadas.append("print"))

    io = WizardIO()
    assert io.prompt("→ ") == "respuesta"
    io.write("msg")

    assert llamadas == ["input", "print"]


def test_canario_builtins_input_falla_si_wizard_io_lo_invoca(monkeypatch):
    """Canario: si WizardIO recayera en `input()` real en vez del input_fn
    inyectado, este test debe fallar ruidosamente vía pytest.fail()."""

    def _canario(*_a, **_k):
        pytest.fail("WizardIO invocó builtins.input() en vez del input_fn inyectado")

    monkeypatch.setattr(builtins, "input", _canario)

    respuestas = iter(["1"])
    io = WizardIO(input_fn=lambda _msg: next(respuestas, ""), output_fn=lambda _msg: None)

    df = pd.DataFrame({"col_a": [1, 2, 3]})
    wizard = MappingWizard(df, esenciales=["tel"], no_esenciales=[], io=io)
    assert wizard._prompt("→ ") == "1"


def test_build_wizard_io_propaga_input_fn_output_fn_explicitos():
    """build_wizard_io(...) reenvía input_fn/output_fn explícitos a WizardIO."""
    entradas = iter(["respuesta"])
    salidas = []

    io = build_wizard_io(
        log_to_system=False,
        input_fn=lambda _msg: next(entradas),
        output_fn=salidas.append,
    )

    assert io.prompt("→ ") == "respuesta"
    io.write("mensaje")
    assert salidas == ["mensaje"]


def test_build_wizard_io_default_no_captura_input_en_import(monkeypatch):
    """build_wizard_io() sin input_fn/output_fn explícitos debe resolver
    contra builtins.input/print vigentes en el momento de la LLAMADA, no del
    import de tz_core.manual_mapping_helpers."""
    llamadas = []
    monkeypatch.setattr(builtins, "input", lambda _msg="": llamadas.append("input") or "x")
    monkeypatch.setattr(builtins, "print", lambda *a, **k: llamadas.append("print"))

    io = build_wizard_io(log_to_system=False)
    assert io.prompt("→ ") == "x"
    io.write("msg")

    assert llamadas == ["input", "print"]


def test_build_wizard_io_canario_builtins_input(monkeypatch):
    """Canario: build_wizard_io() sin input_fn no debe invocar builtins.input
    cuando se le inyecta un input_fn explícito."""

    def _canario(*_a, **_k):
        pytest.fail("build_wizard_io invocó builtins.input() pese a input_fn explícito")

    monkeypatch.setattr(builtins, "input", _canario)

    io = build_wizard_io(log_to_system=False, input_fn=lambda _msg: "ok", output_fn=lambda _msg: None)
    assert io.prompt("→ ") == "ok"


def test_script_build_wizard_io_propaga_input_fn_output_fn_explicitos():
    """_build_wizard_io (wrapper del orquestador CLI) también propaga
    input_fn/output_fn explícitos hasta WizardIO, sin depender de sus
    defaults `input`/`print`."""
    entradas = iter(["valor"])
    salidas = []

    io = app._build_wizard_io(
        log_to_system=False,
        input_fn=lambda _msg: next(entradas),
        output_fn=salidas.append,
    )

    assert io.prompt("→ ") == "valor"
    io.write("mensaje")
    assert salidas == ["mensaje"]


def test_run_manual_mapping_no_requiere_input_real_con_wizard_io_inyectado(monkeypatch):
    """La ruta reutilizable (run_manual_mapping) debe poder completarse sin
    ninguna llamada real a builtins.input, usando solo el WizardIO inyectado
    — esto es lo que necesita un futuro orquestador web no interactivo."""

    def _canario(*_a, **_k):
        pytest.fail("run_manual_mapping recayó en builtins.input() real")

    monkeypatch.setattr(builtins, "input", _canario)

    df = pd.DataFrame({"columna_fecha": ["01/01/2024"], "columna_tel": ["5000"]})
    io = WizardIO(input_fn=lambda _msg: "", output_fn=lambda _msg: None)

    df_out, asignaciones = run_manual_mapping(df, wizard_io=io)

    assert isinstance(df_out, pd.DataFrame)
    assert isinstance(asignaciones, dict)
