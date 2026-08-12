"""tz_folder_dialog_helper — script auxiliar del selector nativo de carpetas
(MICROBLOQUE 6), ejecutado como subproceso por ``tz_core.folder_dialog``.

Prueba ``main()`` directamente (import normal, sin subproceso real) con
Tkinter mockeado: nunca abre una ventana real, solo verifica que cada rama
del contrato de códigos de salida (ver el docstring del propio módulo)
se alcanza correctamente."""
from __future__ import annotations

import sys
import types

import pytest

import tz_folder_dialog_helper as helper


class _FakeRoot:
    def __init__(self):
        self.withdrawn = False
        self.destroyed = False
        self.attrs = {}

    def withdraw(self):
        self.withdrawn = True

    def attributes(self, name, value):
        self.attrs[name] = value

    def destroy(self):
        self.destroyed = True


def _install_fake_tkinter(monkeypatch, *, askdirectory_result=None, askdirectory_raises=None, tk_raises=None):
    fake_root = _FakeRoot()

    def _fake_tk():
        if tk_raises is not None:
            raise tk_raises
        return fake_root

    def _fake_askdirectory(**kwargs):
        if askdirectory_raises is not None:
            raise askdirectory_raises
        _fake_askdirectory.kwargs = kwargs
        return askdirectory_result

    fake_filedialog = types.SimpleNamespace(askdirectory=_fake_askdirectory)
    fake_tkinter_module = types.SimpleNamespace(
        Tk=_fake_tk, TclError=RuntimeError, filedialog=fake_filedialog
    )

    monkeypatch.setitem(sys.modules, "tkinter", fake_tkinter_module)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", fake_filedialog)
    return fake_root, _fake_askdirectory


def test_seleccion_exitosa_imprime_ruta_y_sale_0(monkeypatch, capsys):
    _install_fake_tkinter(monkeypatch, askdirectory_result="C:\\Casos\\Caso Ñ 1")
    codigo = helper.main(["tz_folder_dialog_helper.py"])
    assert codigo == helper.EXIT_OK
    assert capsys.readouterr().out.strip() == "C:\\Casos\\Caso Ñ 1"


def test_cancelacion_sin_salida_y_codigo_3(monkeypatch, capsys):
    _install_fake_tkinter(monkeypatch, askdirectory_result="")
    codigo = helper.main(["tz_folder_dialog_helper.py"])
    assert codigo == helper.EXIT_CANCELLED
    assert capsys.readouterr().out == ""


def test_tkinter_ausente_devuelve_codigo_4(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "tkinter", None)
    codigo = helper.main(["tz_folder_dialog_helper.py"])
    assert codigo == helper.EXIT_NO_GUI
    assert "Tkinter" in capsys.readouterr().err


def test_tclerror_al_abrir_devuelve_codigo_4(monkeypatch, capsys):
    _install_fake_tkinter(monkeypatch, tk_raises=RuntimeError("no display"))
    codigo = helper.main(["tz_folder_dialog_helper.py"])
    assert codigo == helper.EXIT_NO_GUI
    assert "selector gráfico" in capsys.readouterr().err


def test_error_inesperado_devuelve_codigo_1(monkeypatch, capsys):
    _install_fake_tkinter(monkeypatch, askdirectory_raises=ValueError("boom"))
    codigo = helper.main(["tz_folder_dialog_helper.py"])
    assert codigo == helper.EXIT_ERROR
    assert "boom" in capsys.readouterr().err


def test_root_siempre_se_destruye_incluso_si_askdirectory_falla(monkeypatch):
    fake_root, _ = _install_fake_tkinter(monkeypatch, askdirectory_raises=ValueError("boom"))
    helper.main(["tz_folder_dialog_helper.py"])
    assert fake_root.destroyed is True


def test_pasa_titulo_y_carpeta_inicial_al_dialogo(monkeypatch):
    _fake_root, fake_askdirectory = _install_fake_tkinter(monkeypatch, askdirectory_result="C:\\x")
    helper.main([
        "tz_folder_dialog_helper.py",
        "--title=Elegir carpeta del caso",
        "C:\\Users\\alguien\\Documents",
    ])
    assert fake_askdirectory.kwargs["title"] == "Elegir carpeta del caso"
    assert fake_askdirectory.kwargs["initialdir"] == "C:\\Users\\alguien\\Documents"
    assert fake_askdirectory.kwargs["mustexist"] is True


def test_sin_argumentos_usa_titulo_por_defecto(monkeypatch):
    _fake_root, fake_askdirectory = _install_fake_tkinter(monkeypatch, askdirectory_result="C:\\x")
    helper.main(["tz_folder_dialog_helper.py"])
    assert fake_askdirectory.kwargs["title"] == helper._DEFAULT_TITLE
    assert fake_askdirectory.kwargs["initialdir"] is None
