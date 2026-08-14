#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Selector Tk callable para el modo interno de TZ Analyzer.

No importa Flask, Waitress, ``tz_web`` ni ``tz_core``. El launcher lo llama
unicamente cuando fue reinvocado con ``--tz-internal-folder-dialog``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from tz_folder_dialog_ipc import (
    EXIT_CANCELLED,
    EXIT_ERROR,
    EXIT_NO_GUI,
    EXIT_OK,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_UNAVAILABLE,
    DialogProtocolError,
    read_request,
    validate_request_id,
    write_result,
)

_DEFAULT_TITLE = "Seleccionar carpeta de salida"


@dataclass(frozen=True)
class DialogOutcome:
    status: str
    path: Optional[str] = None
    error_code: Optional[str] = None


def select_folder(*, title: Optional[str] = None, initial_dir: Optional[str] = None) -> DialogOutcome:
    """Muestra un unico ``Tk()`` y devuelve un resultado estructurado."""
    try:
        from tkinter import TclError, Tk, filedialog
    except ImportError:
        return DialogOutcome(STATUS_UNAVAILABLE, error_code="TKINTER_UNAVAILABLE")

    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            folder = filedialog.askdirectory(
                title=title or _DEFAULT_TITLE,
                initialdir=initial_dir or None,
                mustexist=True,
            )
        finally:
            root.destroy()
    except TclError:
        return DialogOutcome(STATUS_UNAVAILABLE, error_code="TK_UNAVAILABLE")
    except Exception:  # noqa: BLE001 - frontera tecnica del proceso hijo
        return DialogOutcome(STATUS_ERROR, error_code="UNEXPECTED_DIALOG_ERROR")

    if not folder:
        return DialogOutcome(STATUS_CANCELLED)
    return DialogOutcome(STATUS_SUCCESS, path=str(folder))


def run_internal_folder_dialog(
    request_id: object,
    *,
    dialog_dir: Optional[Path] = None,
    select_folder_fn: Callable[..., DialogOutcome] = select_folder,
) -> int:
    """Consume la solicitud derivada del ID y publica el resultado atomico."""
    try:
        validated_id = validate_request_id(request_id)
    except DialogProtocolError:
        return EXIT_ERROR

    try:
        request = read_request(validated_id, dialog_dir=dialog_dir)
    except DialogProtocolError:
        try:
            write_result(
                validated_id,
                status=STATUS_ERROR,
                error_code="INVALID_REQUEST",
                dialog_dir=dialog_dir,
            )
        except (DialogProtocolError, OSError):
            pass
        return EXIT_ERROR

    try:
        outcome = select_folder_fn(
            title=request["title"],
            initial_dir=request["initial_dir"],
        )
    except Exception:  # noqa: BLE001 - el hijo siempre debe cerrar con estado tecnico
        outcome = DialogOutcome(STATUS_ERROR, error_code="UNEXPECTED_DIALOG_ERROR")

    try:
        write_result(
            validated_id,
            status=outcome.status,
            path=outcome.path,
            error_code=outcome.error_code,
            dialog_dir=dialog_dir,
        )
    except (DialogProtocolError, OSError):
        return EXIT_ERROR

    return {
        STATUS_SUCCESS: EXIT_OK,
        STATUS_CANCELLED: EXIT_CANCELLED,
        STATUS_UNAVAILABLE: EXIT_NO_GUI,
        STATUS_ERROR: EXIT_ERROR,
    }.get(outcome.status, EXIT_ERROR)
