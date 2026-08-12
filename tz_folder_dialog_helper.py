#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tz_folder_dialog_helper.py — proceso auxiliar aislado del selector nativo
de carpetas (MICROBLOQUE 6).

No es un entrypoint de la aplicación: ``tz_core.folder_dialog.pick_folder``
lo invoca como subproceso independiente (``sys.executable
tz_folder_dialog_helper.py [--title=...] [carpeta_inicial]``) para que el
diálogo modal de Tkinter nunca comparta hilo ni proceso con el servidor
Waitress (ver el docstring de ``tz_core.folder_dialog`` para el porqué).

Este script deliberadamente no importa nada de ``tz_web``/``tz_core`` más
allá de la biblioteca estándar: debe arrancar rápido y no arrastrar Flask,
pandas ni el resto de dependencias pesadas de la aplicación solo para
mostrar un diálogo.

Contrato de salida (única fuente de verdad; ``tz_core.folder_dialog`` lo
replica como constantes para interpretarlo):
- exit 0, ruta elegida en stdout: selección exitosa.
- exit 3, sin salida: el usuario canceló el diálogo.
- exit 4, mensaje en stderr: sin interfaz gráfica disponible (Tkinter
  ausente o el diálogo no pudo abrirse).
- exit 1, mensaje en stderr: cualquier otro error inesperado.
"""

from __future__ import annotations

import sys

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CANCELLED = 3
EXIT_NO_GUI = 4

_DEFAULT_TITLE = "Seleccionar carpeta de salida"


def _parse_args(argv):
    title = _DEFAULT_TITLE
    initial_dir = None
    for arg in argv[1:]:
        if arg.startswith("--title="):
            title = arg[len("--title="):] or _DEFAULT_TITLE
        elif initial_dir is None:
            initial_dir = arg
    return title, initial_dir


def main(argv) -> int:
    title, initial_dir = _parse_args(argv)

    try:
        from tkinter import Tk, TclError, filedialog
    except ImportError as exc:
        print(f"Tkinter no está disponible en este intérprete: {exc}", file=sys.stderr)
        return EXIT_NO_GUI

    try:
        root = Tk()
        root.withdraw()
        # -topmost: sin esto, en algunos entornos Windows el diálogo puede
        # abrirse detrás de la ventana del navegador que disparó la
        # petición, dando la falsa impresión de que "no pasó nada".
        root.attributes("-topmost", True)
        try:
            folder = filedialog.askdirectory(
                title=title,
                initialdir=initial_dir or None,
                mustexist=True,
            )
        finally:
            root.destroy()
    except TclError as exc:
        print(f"No se pudo abrir el selector gráfico: {exc}", file=sys.stderr)
        return EXIT_NO_GUI
    except Exception as exc:  # noqa: BLE001 - cualquier fallo inesperado del diálogo
        print(f"Error inesperado en el selector de carpetas: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not folder:
        return EXIT_CANCELLED

    print(folder)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
