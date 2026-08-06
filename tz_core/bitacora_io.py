"""
I/O helpers para flujo de bitácoras.

Proveen selección de archivo/carpeta con fallback de consola cuando no
están disponibles los diálogos de `utilidades` (Tkinter).
"""

from __future__ import annotations

import os
from typing import Optional

from tz_core.ui_utils import safe_input, UserCancelledError
from tz_core.user_paths import default_output_cwd_fn

try:  # pragma: no cover - depende del entorno (Tkinter)
    from .ui_utils import seleccionar_archivo as _sel_archivo
    from .ui_utils import seleccionar_carpeta as _sel_carpeta
except Exception:  # pragma: no cover - fallback de consola
    _sel_archivo = None
    _sel_carpeta = None


def seleccionar_archivo(titulo: str = "Seleccionar bitácora Excel") -> Optional[str]:
    """Devuelve ruta de archivo Excel; usa Tkinter si está disponible, sino consola."""
    if _sel_archivo:
        try:
            return _sel_archivo(titulo=titulo)
        except TypeError:
            return _sel_archivo()
        except Exception:
            pass
    ruta = safe_input("Ruta del archivo Excel (.xlsx/.xls) (C=cancelar): ").strip('"')
    return ruta if ruta else None


def seleccionar_carpeta(titulo: str = "Seleccionar carpeta de salida") -> Optional[str]:
    """Devuelve ruta de carpeta; Tkinter si existe, de lo contrario consola con
    fallback seguro por defecto (ver tz_core.user_paths.default_output_cwd_fn:
    cwd en modo normal, Documents\\TZ Analyzer en modo frozen — nunca cwd)."""
    if _sel_carpeta:
        try:
            return _sel_carpeta(titulo=titulo)
        except TypeError:
            return _sel_carpeta()
        except Exception:
            pass
    ruta = safe_input("Ruta de la carpeta de salida (Enter=actual, C=cancelar): ").strip('"')
    return ruta if ruta else default_output_cwd_fn()


def ensure_dir(path: str) -> str:
    """Crea la carpeta si no existe y devuelve la ruta absoluta."""
    if not path:
        raise ValueError("Ruta vacía para ensure_dir")
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def seleccionar_carpeta_salida(titulo: str = "Seleccionar carpeta de salida") -> str:
    """Selecciona carpeta de salida y garantiza que exista.

    Si el usuario cancela la selección (diálogo Tkinter), cae a la carpeta
    de salida predeterminada: modo normal preserva el comportamiento
    histórico (cwd); modo frozen nunca usa cwd, resuelve/crea
    Documents\\TZ Analyzer (ver tz_core.user_paths.default_output_cwd_fn).
    """
    carpeta = seleccionar_carpeta(titulo=titulo)
    if not carpeta:
        carpeta = default_output_cwd_fn()
        print(f"No se seleccionó carpeta. Se utilizará: {carpeta}")
    return ensure_dir(carpeta)


def resolver_rutas_salida(base_name: str, carpeta_base: str, separar_kml: bool = False) -> dict[str, str]:
    """Construye rutas de salida coherentes (raíz, kml, kmz)."""
    base_folder = ensure_dir(carpeta_base)
    output_folder = base_folder
    kml_folder = base_folder if not separar_kml else ensure_dir(os.path.join(base_folder, "kml"))
    kmz_folder = base_folder if not separar_kml else ensure_dir(os.path.join(base_folder, "kmz"))

    kml_path = os.path.join(kml_folder, f"{base_name}.kml")
    kmz_path = os.path.join(kmz_folder, f"{base_name}.kmz")

    return {
        "base_folder": base_folder,
        "output_folder": output_folder,
        "kml_folder": kml_folder,
        "kml_path": kml_path,
        "kmz_path": kmz_path,
    }


# Re-exportar utilidades de hojas/Excel desde data_loader para centralizar I/O
from tz_core.data_loader import (  # noqa: E402
    obtener_hojas_visibles,
    listar_todas_hojas,
    seleccionar_hoja_visible,
    seleccionar_hoja,
    cargar_excel_con_normalizacion,
)


__all__ = [
    "seleccionar_archivo",
    "seleccionar_carpeta",
    "seleccionar_carpeta_salida",
    "ensure_dir",
    "resolver_rutas_salida",
    "obtener_hojas_visibles",
    "listar_todas_hojas",
    "seleccionar_hoja_visible",
    "seleccionar_hoja",
    "cargar_excel_con_normalizacion",
]
