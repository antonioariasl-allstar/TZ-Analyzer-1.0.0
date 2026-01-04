"""
I/O helpers para flujo de bitácoras.

Proveen selección de archivo/carpeta con fallback de consola cuando no
están disponibles los diálogos de `utilidades` (Tkinter).
"""

from __future__ import annotations

import os
from typing import Optional

try:  # pragma: no cover - depende del entorno (Tkinter)
    from utilidades import seleccionar_archivo as _sel_archivo  # type: ignore
    from utilidades import seleccionar_carpeta as _sel_carpeta  # type: ignore
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
    ruta = input("Ruta del archivo Excel (.xlsx/.xls): ").strip("\"").strip()
    return ruta if ruta else None


def seleccionar_carpeta(titulo: str = "Seleccionar carpeta de salida") -> Optional[str]:
    """Devuelve ruta de carpeta; Tkinter si existe, de lo contrario consola con cwd por defecto."""
    if _sel_carpeta:
        try:
            return _sel_carpeta(titulo=titulo)
        except TypeError:
            return _sel_carpeta()
        except Exception:
            pass
    ruta = input("Ruta de la carpeta de salida (Enter = actual): ").strip("\"").strip()
    return ruta if ruta else os.getcwd()


__all__ = ["seleccionar_archivo", "seleccionar_carpeta"]
