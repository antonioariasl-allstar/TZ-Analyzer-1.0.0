"""Todas las fuentes que TZ_Analyzer.spec referencia existen en el filesystem.

No requiere PyInstaller: solo comprueba que las rutas declaradas en
build_config/spec_config.py apuntan a archivos/directorios reales.
"""
from __future__ import annotations

from build_config import spec_config as cfg


def test_entrypoint_exists():
    assert cfg.ENTRYPOINT.is_file()


def test_icon_exists():
    assert cfg.ICON_PATH.is_file()


def test_manifest_exists():
    assert cfg.MANIFEST_PATH.is_file()


def test_config_json_exists():
    config_json = cfg.REPO_ROOT / "config.json"
    assert config_json.is_file()


def test_templates_dir_exists():
    assert (cfg.REPO_ROOT / "tz_web" / "templates").is_dir()


def test_static_dir_exists():
    assert (cfg.REPO_ROOT / "tz_web" / "static").is_dir()


def test_tz_core_assets_dir_exists():
    assert (cfg.REPO_ROOT / "tz_core" / "assets").is_dir()


def test_all_datas_sources_exist():
    for src, _dest in cfg.DATAS:
        assert src.exists(), src
