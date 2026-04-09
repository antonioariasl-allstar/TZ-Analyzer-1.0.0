"""Test helper para ejecutar run_tz_analysis sin prompts.

Responsabilidad: parchear funciones interactivas del monolito para
rutas de entrada/salida deterministas y sin input de usuario.
"""
from __future__ import annotations

import builtins
import glob
import os
from typing import Any, Callable, Dict


def apply_run_monkeypatch(
    globals_dict: Dict[str, Any],
    ruta_entrada: str,
    hoja: Any,
    carpeta_salida: str | None,
    override_tops: Dict[str, Any] | None,
    color_mock_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Aplica monkeypatches para evitar prompts en run_tz_analysis.

    Devuelve un diccionario con:
    - restore: callable para restaurar globals e input
    - out_root: ruta de salida elegida (carpeta_salida o cwd)
    - snapshot: callable para tomar snapshot de archivos en carpeta
    """
    g = globals_dict
    _orig: Dict[str, Any] = {}

    def _keep(name: str, fallback: Any = None):
        if name in g:
            _orig[name] = g[name]
            return g[name]
        _orig[name] = fallback
        return fallback

    _keep("_menu_principal")
    _keep("seleccionar_archivo")
    _keep("seleccionar_carpeta")
    _keep("_input_str")
    _keep("_seleccionar_hoja_visible")
    _keep("solicitar_overrides_topn")
    _keep("_solicitar_color_tema")

    def _menu_principal_mock():
        return "1"

    def _sel_arch_mock():
        return ruta_entrada

    def _sel_carp_mock():
        return carpeta_salida or os.getcwd()

    def _input_str_mock(*_args, **_kwargs):
        return ""

    if hoja is not None:
        def _hoja_mock(_archivo):
            return hoja
        g["_seleccionar_hoja_visible"] = _hoja_mock

    def _ovr_mock(_cfg):
        return override_tops

    def _color_mock(cfg):
        return color_mock_fn(cfg)

    g["_menu_principal"] = _menu_principal_mock
    g["seleccionar_archivo"] = _sel_arch_mock
    g["seleccionar_carpeta"] = _sel_carp_mock
    g["_input_str"] = _input_str_mock
    g["solicitar_overrides_topn"] = _ovr_mock
    g["_solicitar_color_tema"] = _color_mock

    orig_input = getattr(builtins, "input", None)

    def _input_mock(*_args, **_kwargs):
        return ""

    try:
        builtins.input = _input_mock
    except Exception:
        pass

    def _snapshot(folder: str):
        try:
            return set(glob.glob(os.path.join(folder, "**/*"), recursive=True))
        except Exception:
            return set()

    def _restore():
        try:
            for name, fn in _orig.items():
                if fn is not None:
                    g[name] = fn
        except Exception:
            pass
        try:
            if orig_input is not None:
                builtins.input = orig_input
        except Exception:
            pass

    return {
        "restore": _restore,
        "out_root": _sel_carp_mock(),
        "snapshot": _snapshot,
    }
