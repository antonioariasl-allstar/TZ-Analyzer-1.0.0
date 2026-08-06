"""
tz_core.user_paths - Rutas de configuración de usuario y de salida
====================================================================

Helper único que centraliza la resolución de rutas sensibles al modo de
ejecución (normal vs. PyInstaller/frozen), para evitar:
- escrituras accidentales en sys._MEIPASS o config.json base;
- carpetas de salida inseguras (System32, HOME puro, CWD arbitrario,
  carpeta del ejecutable) cuando el usuario cancela el selector en modo
  frozen.

CONTRATO:
- Config base (solo lectura): raíz del repo en modo normal, sys._MEIPASS
  en modo frozen.
- Config de usuario (editable, solo en modo frozen):
  %LOCALAPPDATA%\\TZ Analyzer\\config.json — contiene únicamente claves
  modificables por el usuario (inicialmente: synonyms_user).
- Carpeta de salida por defecto: %USERPROFILE%\\Documents\\TZ Analyzer,
  con fallback a %TEMP%\\TZ Analyzer si Documents no puede crearse.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

APP_DIR_NAME = "TZ Analyzer"
CONFIG_FILENAME = "config.json"

# Claves del config base que el usuario puede sobrescribir/extender desde
# el archivo de usuario. Se mantiene deliberadamente corta (v1.1).
USER_EDITABLE_KEYS = ("synonyms_user",)


def is_frozen() -> bool:
    """Indica si el proceso corre empaquetado (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def get_repo_base_dir() -> Path:
    """Raíz del repositorio (padre de tz_core/), usada en modo normal."""
    return Path(__file__).resolve().parent.parent


def get_base_config_dir() -> Path:
    """Directorio de solo lectura donde vive el config.json base.

    Modo normal: raíz del repo. Modo frozen: bundle (sys._MEIPASS).
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return get_repo_base_dir()


def get_base_config_path() -> Path:
    """Ruta completa al config.json base (solo lectura)."""
    return get_base_config_dir() / CONFIG_FILENAME


def get_user_config_dir(localappdata: Optional[str] = None) -> Path:
    """Carpeta de configuración de usuario (%LOCALAPPDATA%\\TZ Analyzer).

    `localappdata` permite inyectar la ruta base en tests sin depender
    de variables de entorno reales.
    """
    base = localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_DIR_NAME


def get_user_config_path(localappdata: Optional[str] = None) -> Path:
    """Ruta completa al config.json de usuario (editable, modo frozen)."""
    return get_user_config_dir(localappdata) / CONFIG_FILENAME


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_user_config(
    *,
    localappdata: Optional[str] = None,
    warn: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Lee el archivo de configuración de usuario.

    Nunca lanza: archivo ausente -> {}; JSON corrupto o error de lectura ->
    {} + advertencia visible vía `warn`.
    """
    path = get_user_config_path(localappdata)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        warn(f"[WARN][config] No se pudo leer la configuración de usuario ({path}): {exc}")
        return {}


def merge_user_config(base_config: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
    """Combina la config base (solo lectura) con las claves editables del usuario.

    Solo se fusionan las claves declaradas en USER_EDITABLE_KEYS; el resto
    de la config base (kml, branding, schema, ...) queda intacta.
    """
    merged = dict(base_config or {})
    for key in USER_EDITABLE_KEYS:
        user_value = user_config.get(key) if isinstance(user_config, dict) else None
        if isinstance(user_value, dict):
            combined = dict(merged.get(key) or {})
            combined.update(user_value)
            merged[key] = combined
    return merged


def write_user_synonym(
    canonico: str,
    encabezado_crudo: str,
    *,
    localappdata: Optional[str] = None,
    warn: Callable[[str], None] = print,
) -> bool:
    """Persiste un sinónimo únicamente en el archivo de usuario.

    Debe usarse solo en modo frozen (el llamador decide, ver
    config_manager.add_user_synonym). Nunca escribe en config base ni en
    _MEIPASS. Devuelve True si se escribió correctamente; False si hubo
    error (ya notificado vía `warn`, sin lanzar excepción).
    """
    canonico = (canonico or "").strip()
    encabezado_crudo = (encabezado_crudo or "").strip()
    if not canonico or not encabezado_crudo:
        return False

    user_config = load_user_config(localappdata=localappdata, warn=warn)
    synonyms = dict(user_config.get("synonyms_user") or {})
    if synonyms.get(encabezado_crudo) == canonico:
        return True

    synonyms[encabezado_crudo] = canonico
    user_config["synonyms_user"] = synonyms

    try:
        user_dir = _ensure_dir(get_user_config_dir(localappdata))
        path = user_dir / CONFIG_FILENAME
        fd, tmp_path = tempfile.mkstemp(prefix="cfg_user_", suffix=".json", dir=str(user_dir))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(user_config, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(path))
        return True
    except Exception as exc:
        warn(f"[WARN][config] No se pudo guardar la configuración de usuario: {exc}")
        return False


def get_default_documents_dir(home: Optional[Path] = None) -> Path:
    """%USERPROFILE%\\Documents\\TZ Analyzer (o `home`/Documents/TZ Analyzer en tests)."""
    home_path = home if home is not None else Path.home()
    return home_path / "Documents" / APP_DIR_NAME


def get_fallback_temp_dir(temp_dir: Optional[str] = None) -> Path:
    """%TEMP%\\TZ Analyzer, fallback secundario si Documents no puede crearse."""
    base = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    return base / APP_DIR_NAME


def resolve_default_output_dir(
    *,
    home: Optional[Path] = None,
    temp_dir: Optional[str] = None,
    warn: Callable[[str], None] = print,
) -> str:
    """Resuelve y crea la carpeta de salida predeterminada.

    Preferencia: %USERPROFILE%\\Documents\\TZ Analyzer. Si no puede
    crearse, cae a %TEMP%\\TZ Analyzer con advertencia visible. Nunca
    devuelve cwd, HOME puro, _MEIPASS ni la carpeta del ejecutable.
    """
    documents_dir = get_default_documents_dir(home)
    try:
        _ensure_dir(documents_dir)
        return str(documents_dir)
    except Exception as exc:
        warn(
            f"[WARN][salida] No se pudo crear '{documents_dir}': {exc}. "
            f"Se usará una carpeta temporal."
        )

    fallback_dir = get_fallback_temp_dir(temp_dir)
    _ensure_dir(fallback_dir)
    return str(fallback_dir)


def default_output_cwd_fn(warn: Callable[[str], None] = print) -> str:
    """cwd_fn seguro para inyectar en flujos de salida.

    Modo normal: preserva el comportamiento actual (os.getcwd()). Modo
    frozen: nunca usa cwd; resuelve/crea Documents\\TZ Analyzer (con
    fallback a TEMP\\TZ Analyzer).
    """
    if is_frozen():
        return resolve_default_output_dir(warn=warn)
    return os.getcwd()
