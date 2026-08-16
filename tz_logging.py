#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tz_logging — configuración centralizada de logging técnico local.

Dependency-free y sin efectos secundarios de importación (mismo criterio que
``tz_version.py``): solo librería estándar, importable antes que Flask/
tz_core/tz_web y desde el contexto más temprano de ``tz_launcher.py``, para
poder capturar fallos de arranque incluso en un futuro build sin consola
(PyInstaller ``--noconsole``).

CONTRATO:
- Un único punto de configuración (``configure_logging()``), llamado una vez
  por el proceso; los demás módulos solo hacen ``logging.getLogger(__name__)``
  y dejan que sus mensajes se propaguen al logger raíz — ningún otro módulo
  debe crear su propio ``Handler``.
- Archivo persistente en ``%LOCALAPPDATA%\\TZ Analyzer\\Logs\\tz_analyzer.log``
  (rotación ~5 MiB x3 backups, UTF-8), más consola opcional (activa por
  defecto: sección 9 del encargo — no acoplar a PyInstaller todavía).
- Nunca debe impedir el arranque: si el directorio de logs no puede crearse
  o el archivo no puede abrirse, se continúa sin logging a archivo (consola/
  stderr si está disponible) en vez de lanzar una excepción.
- Solo eventos TÉCNICOS (arranque, servidor, etapas, resultado, excepciones)
  — nunca contenido investigativo (ver ``sanitize_log_text`` para el único
  caso en que un mensaje técnico podría arrastrar una ruta de caso).
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

APP_DIR_NAME = "TZ Analyzer"
LOG_SUBDIR_NAME = "Logs"
LOG_FILE_NAME = "tz_analyzer.log"

# ~5 MiB por archivo, 3 backups (tz_analyzer.log.1/.2/.3) — sección 3.
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

_MANAGED_ATTR = "_tz_analyzer_managed_handler"
_CONFIGURED = False
# Serializa toda la sección crítica de configure_logging() (comprobación +
# creación de handlers + addHandler + marcado) para que dos threads no
# puedan superar ambos el fast-path check antes de que el primero termine.
_LOCK = threading.Lock()
# Nivel del root logger justo antes de que configure_logging() lo tocara
# por primera vez; reset_logging_for_tests() lo usa para devolver el root
# a su estado previo real en vez de asumir un valor fijo (p. ej. NOTSET).
_PREVIOUS_ROOT_LEVEL: Optional[int] = None


def get_log_directory(localappdata: Optional[str] = None) -> Path:
    """Carpeta de logs (``%LOCALAPPDATA%\\TZ Analyzer\\Logs``).

    ``localappdata`` permite inyectar la ruta base en tests sin depender de
    la variable de entorno real (mismo patrón que
    ``tz_core.user_paths.get_user_config_dir``). Sin ``LOCALAPPDATA`` en el
    entorno (desarrollo/no-Windows), cae a ``~/AppData/Local`` — nunca cwd
    ni un usuario hardcodeado.
    """
    base = localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_DIR_NAME / LOG_SUBDIR_NAME


def configure_logging(
    *,
    log_dir: Optional[Union[str, Path]] = None,
    localappdata: Optional[str] = None,
    level: int = logging.INFO,
    console: Optional[bool] = None,
) -> logging.Logger:
    """Configura (una sola vez por proceso) el logger raíz.

    Idempotente: llamadas posteriores son no-op y devuelven el mismo logger
    raíz sin duplicar handlers. ``log_dir`` fija la carpeta de logs
    directamente (tests); en su ausencia se resuelve vía
    ``get_log_directory(localappdata)``. ``console`` por defecto agrega
    también un ``StreamHandler`` (sección 9: no quitar la consola en
    desarrollo); pásese ``False`` para archivo únicamente.
    """
    global _CONFIGURED, _PREVIOUS_ROOT_LEVEL
    root = logging.getLogger()
    if _CONFIGURED:
        return root

    with _LOCK:
        # Re-comprobar dentro del lock: otro thread pudo haber terminado de
        # configurar mientras este esperaba a adquirirlo (double-checked
        # locking) — evita duplicar handlers y evita bloquear llamadas
        # posteriores, ya idempotentes, detrás del lock innecesariamente.
        if _CONFIGURED:
            return root

        resolved_dir = Path(log_dir) if log_dir is not None else get_log_directory(localappdata)
        try:
            resolved_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(resolved_dir / LOG_FILE_NAME),
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            file_handler.setLevel(level)
            setattr(file_handler, _MANAGED_ATTR, True)
            root.addHandler(file_handler)
        except OSError:
            # Sección 15: el logging nunca puede impedir arrancar la app. Sin
            # archivo, se sigue únicamente con consola (si aplica, más abajo).
            pass

        if console is None:
            console = True
        if console and sys.stderr is not None:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            stream_handler.setLevel(level)
            setattr(stream_handler, _MANAGED_ATTR, True)
            root.addHandler(stream_handler)

        _PREVIOUS_ROOT_LEVEL = root.level
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)

        _CONFIGURED = True
        return root


def reset_logging_for_tests() -> None:
    """Solo para tests: retira los handlers gestionados por este módulo,
    restaura el nivel del root logger al que tenía antes de la primera
    ``configure_logging()`` y permite volver a llamar ``configure_logging()``
    desde cero."""
    global _CONFIGURED, _PREVIOUS_ROOT_LEVEL
    with _LOCK:
        root = logging.getLogger()
        for handler in list(root.handlers):
            if getattr(handler, _MANAGED_ATTR, False):
                root.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
        if _PREVIOUS_ROOT_LEVEL is not None:
            root.setLevel(_PREVIOUS_ROOT_LEVEL)
            _PREVIOUS_ROOT_LEVEL = None
        _CONFIGURED = False


# ---------------------------------------------------------------------------
# Sanitización mínima (sección 11) — no es DLP: solo cubre el caso descrito
# en el encargo (una excepción de E/S que arrastra una ruta de caso hacia un
# mensaje técnico). Las rutas suelen llegar entre comillas (repr de Python o
# el propio formato de OSError: "... 'C:\\CASOS\\...\\archivo.xlsx'"), así
# que el patrón corta en la comilla de cierre; sin comillas, se redacta hasta
# el final de la línea (mejor de más que dejar pasar una ruta).
# ---------------------------------------------------------------------------

_REDACTED = "<ruta_redactada>"
_UNC_PATH_RE = re.compile(r"\\\\[^\"'\r\n]*")
_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\"'\r\n]*")


def sanitize_log_text(text: str) -> str:
    """Redacta rutas absolutas de Windows/UNC en ``text``."""
    if not text:
        return text
    # Rutas con unidad primero: en un repr de Python ("C:\\\\CASOS\\\\...")
    # las barras dobles tras "C:" también calzarían con el patrón UNC de
    # abajo, dejando "C:" fuera de la redacción si se aplicara antes.
    text = _WINDOWS_PATH_RE.sub(_REDACTED, text)
    text = _UNC_PATH_RE.sub(_REDACTED, text)
    return text
