"""
utilidades.py
--------------
Utilidades de selección de archivo/carpeta con Tkinter y fallback a consola.

Comportamiento clave:
- Usa Tkinter para mostrar diálogos de selección.
- Si Tkinter no está disponible o el diálogo falla (TclError), cae a consola.
- Recuerda la última carpeta usada (variable global LAST_DIR) y la usa como initialdir.
- Devuelve rutas como str o None si el usuario cancela/ingresa inválido.
"""

from __future__ import annotations

from typing import Optional, Callable
import os

# Última carpeta usada en este proceso (se mantiene en memoria)
LAST_DIR: Optional[str] = None

# Filtros de archivo para Excel
_EXCEL_FILETYPES = [("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]


def _console_prompt(msg: str, validator: Optional[Callable[[str], bool]] = None) -> Optional[str]:
    """
    Pide una ruta por consola. Devuelve la ruta válida o None si se cancela/ingresa inválida.
    """
    try:
        ruta = input(msg).strip()
    except Exception:
        return None
    if not ruta:
        return None
    if validator and not validator(ruta):
        print("[WARN] Ruta inválida. Operación cancelada.")
        return None
    return ruta


def _get_initialdir() -> str:
    """
    Determina la carpeta inicial para el diálogo: LAST_DIR o cwd.
    """
    return LAST_DIR or os.getcwd()


def seleccionar_archivo(titulo: str = "Seleccionar bitácora Excel") -> Optional[str]:
    """
    Abre un diálogo gráfico (Tkinter) para seleccionar un archivo Excel (.xlsx/.xls).
    Si Tkinter no está disponible o falla, solicita la ruta por consola.

    Args:
        titulo (str): Título del diálogo.
    Returns:
        Optional[str]: Ruta del archivo seleccionado o None si se cancela/ingresa inválido.
    """
    # Intento de GUI
    try:
        # Import diferido para no fallar en entornos sin Tk
        from tkinter import Tk, filedialog, TclError  # type: ignore
    except ImportError:
        # Fallback headless (sin GUI)
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta del archivo Excel (.xlsx/.xls) o presione Enter para cancelar: ",
            validator=lambda p: os.path.isfile(p) and os.path.splitext(p)[1].lower() in {".xlsx", ".xls"},
        )

    # GUI disponible
    try:
        global LAST_DIR
        initial = _get_initialdir()

        root = Tk()
        root.withdraw()
        filename = filedialog.askopenfilename(
            title=f"{titulo} (formatos .xlsx/.xls)",
            initialdir=initial,
            filetypes=_EXCEL_FILETYPES,
        )
        root.destroy()

        if not filename:
            return None  # cancelado

        # actualizar LAST_DIR
        try:
            LAST_DIR = os.path.dirname(filename) or LAST_DIR
        except Exception:
            pass

        return filename
    except TclError:
        # Fallback si el diálogo truena en tiempo de ejecución
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta del archivo Excel (.xlsx/.xls) o presione Enter para cancelar: ",
            validator=lambda p: os.path.isfile(p) and os.path.splitext(p)[1].lower() in {".xlsx", ".xls"},
        )


def seleccionar_carpeta(titulo: str = "Seleccionar carpeta destino") -> Optional[str]:
    """
    Abre un diálogo gráfico (Tkinter) para seleccionar una carpeta destino.
    Si Tkinter no está disponible o falla, solicita la ruta por consola.

    Args:
        titulo (str): Título del diálogo.
    Returns:
        Optional[str]: Ruta de la carpeta seleccionada o None si se cancela/ingresa inválida.
    """
    # Intento de GUI
    try:
        from tkinter import Tk, filedialog, TclError  # type: ignore
    except ImportError:
        # Fallback headless (sin GUI)
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta de la carpeta destino o presione Enter para cancelar: ",
            validator=lambda p: os.path.isdir(p),
        )

    # GUI disponible
    try:
        global LAST_DIR
        initial = _get_initialdir()

        root = Tk()
        root.withdraw()
        folder = filedialog.askdirectory(
            title=titulo,
            initialdir=initial,
        )
        root.destroy()

        if not folder:
            return None  # cancelado

        # actualizar LAST_DIR
        try:
            LAST_DIR = folder or LAST_DIR
        except Exception:
            pass

        return folder
    except TclError:
        # Fallback si el diálogo truena en tiempo de ejecución
        return _console_prompt(
            "No se pudo abrir el selector gráfico.\n"
            "Ingrese la ruta de la carpeta destino o presione Enter para cancelar: ",
            validator=lambda p: os.path.isdir(p),
        )
