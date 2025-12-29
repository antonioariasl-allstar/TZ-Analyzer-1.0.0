"""
Helper pequeño para centralizar la carga de config.json.
Delegamos en tz_core.config_manager para mantener una sola implementación
y añadimos un get_config con cache y ajuste PyInstaller.
"""
import os
import sys

from tz_core.config_manager import (
    cargar_config as _cargar_config,
    DEFAULT_CONFIG,
    _normalize_key_for_synonyms as _normalize_mod,
    cfg_build_rename_map as _cfg_build_mod,
    add_user_synonym as _add_user_synonym,
    solicitar_color_tema as _solicitar_color_tema,
)

_CONFIG_CACHE = None  # cache local para evitar relecturas


def load_config():
    """Carga config.json usando la implementación centralizada."""
    return _cargar_config()


def get_config():
    """
    Lazy-load con cache y ajuste de ruta de logo para PyInstaller.
    Devuelve siempre un dict (DEFAULT_CONFIG si algo falla).
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg = load_config() or {}
        try:
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS  # type: ignore[attr-defined]
                logo_path = cfg.get("branding", {}).get("logo_path")
                if logo_path and not os.path.isabs(logo_path):
                    cfg.setdefault("branding", {})["logo_path"] = os.path.join(base_path, logo_path)
        except Exception:
            pass
        _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


# ==== Wrappers ligeros para sinónimos y color (compatibilidad) ====

def normalize_key_for_synonyms(s: str) -> str:
    """Wrapper a _normalize_key_for_synonyms (compatibilidad)."""
    return _normalize_mod(s)


def cfg_build_rename_map(CONFIG: dict) -> dict:
    """Wrapper a cfg_build_rename_map (compatibilidad)."""
    return _cfg_build_mod(CONFIG)


def cfg_add_user_synonym(CONFIG: dict, canonico: str, encabezado_crudo: str, ruta_cfg: str | None = None) -> dict:
    """Wrapper a add_user_synonym con persistencia en config.json."""
    return _add_user_synonym(CONFIG, canonico, encabezado_crudo, ruta_cfg)


def solicitar_color_tema(CONFIG):
    """Wrapper interactivo para selección de color (compatibilidad)."""
    return _solicitar_color_tema(CONFIG)
