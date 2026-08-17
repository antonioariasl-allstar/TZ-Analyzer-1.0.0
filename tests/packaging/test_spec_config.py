"""build_config/spec_config.py: constantes que TZ_Analyzer.spec consume.

Importable sin PyInstaller instalado (ver docstring del módulo). El .spec
en sí no se ejecuta aquí: PyInstaller inyecta globals (Analysis, PYZ, EXE,
COLLECT, SPECPATH) que no existen fuera de una build real.
"""
from __future__ import annotations

from build_config import spec_config as cfg


def test_entrypoint_is_tz_launcher():
    assert cfg.ENTRYPOINT.name == "tz_launcher.py"
    assert cfg.ENTRYPOINT.parent == cfg.REPO_ROOT


def test_product_name():
    assert cfg.PRODUCT_NAME == "TZ Analyzer"


def test_icon_points_to_canonical_branding_ico():
    assert cfg.ICON_PATH == cfg.REPO_ROOT / "tz_core" / "assets" / "branding" / "TZ_Analyzer.ico"


def test_manifest_path():
    assert cfg.MANIFEST_PATH == cfg.REPO_ROOT / "build_config" / "TZ_Analyzer.manifest"


def test_version_info_path_is_generated_artifact_location():
    assert cfg.VERSION_INFO_PATH == cfg.REPO_ROOT / "build" / "pyinstaller" / "version_info.txt"


def test_datas_cover_flask_and_assets_and_config():
    destinations = {dest for _src, dest in cfg.DATAS}
    assert destinations == {"tz_web/templates", "tz_web/static", "tz_core/assets", "."}


def test_datas_sources_match_repo_layout():
    sources = {src for src, _dest in cfg.DATAS}
    expected = {
        cfg.REPO_ROOT / "tz_web" / "templates",
        cfg.REPO_ROOT / "tz_web" / "static",
        cfg.REPO_ROOT / "tz_core" / "assets",
        cfg.REPO_ROOT / "config.json",
    }
    assert sources == expected


def test_no_manual_datas_entry():
    for _src, dest in cfg.DATAS:
        assert "manual" not in dest.lower()


def test_hiddenimports_and_excludes_start_empty():
    assert cfg.HIDDENIMPORTS == ()
    assert cfg.EXCLUDES == ()


def test_first_build_flags():
    assert cfg.CONSOLE is True
    assert cfg.UPX is False
    assert cfg.STRIP is False
    assert cfg.CONTENTS_DIRECTORY == "_internal"
