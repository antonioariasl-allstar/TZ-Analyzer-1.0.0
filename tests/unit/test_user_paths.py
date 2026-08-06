"""Tests unitarios para tz_core.user_paths (gate pre-PyInstaller v1.1).

Cubre:
- Resolución de config base (repo vs _MEIPASS).
- Config de usuario en LOCALAPPDATA (lectura/escritura/merge).
- Fallback de carpeta de salida (Documents -> TEMP) sin usar cwd/HOME/_MEIPASS.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tz_core.user_paths import (
    is_frozen,
    get_base_config_dir,
    get_repo_base_dir,
    get_user_config_dir,
    get_user_config_path,
    load_user_config,
    merge_user_config,
    write_user_synonym,
    get_default_documents_dir,
    get_fallback_temp_dir,
    resolve_default_output_dir,
    default_output_cwd_fn,
)


# ---------------------------------------------------------------------------
# is_frozen / get_base_config_dir
# ---------------------------------------------------------------------------

def test_is_frozen_false_by_default():
    assert is_frozen() is False


def test_get_base_config_dir_normal_mode_is_repo_root():
    base_dir = get_base_config_dir()
    assert base_dir == get_repo_base_dir()
    assert (base_dir / "config.json").exists()


def test_get_base_config_dir_frozen_mode_is_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert is_frozen() is True
    assert get_base_config_dir() == tmp_path


# ---------------------------------------------------------------------------
# get_user_config_dir / get_user_config_path
# ---------------------------------------------------------------------------

def test_get_user_config_dir_uses_injected_localappdata(tmp_path):
    user_dir = get_user_config_dir(localappdata=str(tmp_path))
    assert user_dir == tmp_path / "TZ Analyzer"


def test_get_user_config_path_appends_config_json(tmp_path):
    path = get_user_config_path(localappdata=str(tmp_path))
    assert path == tmp_path / "TZ Analyzer" / "config.json"


# ---------------------------------------------------------------------------
# load_user_config
# ---------------------------------------------------------------------------

def test_load_user_config_missing_file_returns_empty_dict(tmp_path):
    result = load_user_config(localappdata=str(tmp_path))
    assert result == {}


def test_load_user_config_corrupt_json_warns_and_continues(tmp_path):
    user_dir = tmp_path / "TZ Analyzer"
    user_dir.mkdir(parents=True)
    (user_dir / "config.json").write_text("{not valid json", encoding="utf-8")

    warnings: list[str] = []
    result = load_user_config(localappdata=str(tmp_path), warn=warnings.append)

    assert result == {}
    assert len(warnings) == 1
    assert "config" in warnings[0].lower()


def test_load_user_config_reads_valid_synonyms(tmp_path):
    user_dir = tmp_path / "TZ Analyzer"
    user_dir.mkdir(parents=True)
    (user_dir / "config.json").write_text(
        json.dumps({"synonyms_user": {"numero": "tel"}}), encoding="utf-8"
    )

    result = load_user_config(localappdata=str(tmp_path))
    assert result == {"synonyms_user": {"numero": "tel"}}


# ---------------------------------------------------------------------------
# merge_user_config
# ---------------------------------------------------------------------------

def test_merge_user_config_preserves_base_sections():
    base = {
        "kml": {"azimuth_km": 1.5},
        "branding": {"logo_path": "logo.png"},
        "schema": {"fields": {"lat": {}}},
        "synonyms_user": {"_info": "no editar"},
    }
    user = {"synonyms_user": {"numero": "tel"}}

    merged = merge_user_config(base, user)

    assert merged["kml"] == {"azimuth_km": 1.5}
    assert merged["branding"] == {"logo_path": "logo.png"}
    assert merged["schema"] == {"fields": {"lat": {}}}
    assert merged["synonyms_user"] == {"_info": "no editar", "numero": "tel"}


def test_merge_user_config_empty_user_config_leaves_base_untouched():
    base = {"kml": {"azimuth_km": 1.5}, "synonyms_user": {"_info": "x"}}
    merged = merge_user_config(base, {})
    assert merged == base


# ---------------------------------------------------------------------------
# write_user_synonym
# ---------------------------------------------------------------------------

def test_write_user_synonym_creates_dir_and_file(tmp_path):
    user_dir = tmp_path / "TZ Analyzer"
    assert not user_dir.exists()

    ok = write_user_synonym("tel", "numero_telefono", localappdata=str(tmp_path))

    assert ok is True
    assert user_dir.exists()
    persisted = json.loads((user_dir / "config.json").read_text(encoding="utf-8"))
    assert persisted == {"synonyms_user": {"numero_telefono": "tel"}}


def test_write_user_synonym_second_load_recovers_synonym(tmp_path):
    write_user_synonym("tel", "numero_telefono", localappdata=str(tmp_path))

    # Segunda carga (simulando un nuevo arranque del proceso)
    reloaded = load_user_config(localappdata=str(tmp_path))
    assert reloaded["synonyms_user"]["numero_telefono"] == "tel"


def test_write_user_synonym_permission_error_warns_without_raising(tmp_path, monkeypatch):
    warnings: list[str] = []

    def _boom(*args, **kwargs):
        raise PermissionError("acceso denegado")

    monkeypatch.setattr("tz_core.user_paths.tempfile.mkstemp", _boom)

    ok = write_user_synonym(
        "tel", "numero_telefono", localappdata=str(tmp_path), warn=warnings.append
    )

    assert ok is False
    assert len(warnings) == 1
    assert "no se pudo guardar" in warnings[0].lower()


def test_write_user_synonym_does_not_touch_meipass(tmp_path, monkeypatch):
    meipass_dir = tmp_path / "bundle"
    meipass_dir.mkdir()
    base_config = meipass_dir / "config.json"
    base_config.write_text(json.dumps({"kml": {}}), encoding="utf-8")
    original_bytes = base_config.read_bytes()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    localappdata = tmp_path / "localappdata"
    write_user_synonym("tel", "numero", localappdata=str(localappdata))

    assert base_config.read_bytes() == original_bytes
    assert not (meipass_dir / "TZ Analyzer").exists()


# ---------------------------------------------------------------------------
# Carpeta de salida por defecto
# ---------------------------------------------------------------------------

def test_get_default_documents_dir_uses_injected_home(tmp_path):
    docs_dir = get_default_documents_dir(home=tmp_path)
    assert docs_dir == tmp_path / "Documents" / "TZ Analyzer"


def test_resolve_default_output_dir_creates_documents_folder(tmp_path):
    result = resolve_default_output_dir(home=tmp_path)
    expected = tmp_path / "Documents" / "TZ Analyzer"

    assert result == str(expected)
    assert expected.is_dir()


def test_resolve_default_output_dir_never_returns_cwd_home_or_meipass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = resolve_default_output_dir(home=tmp_path)

    assert result != os.getcwd()
    assert result != str(tmp_path)
    assert "_MEIPASS" not in result
    assert result.endswith(os.path.join("Documents", "TZ Analyzer"))


def test_resolve_default_output_dir_falls_back_to_temp_when_documents_fails(tmp_path, monkeypatch):
    def _boom(self, *args, **kwargs):
        if "Documents" in str(self):
            raise OSError("disco de solo lectura")
        return None

    monkeypatch.setattr(Path, "mkdir", _boom)

    warnings: list[str] = []
    result = resolve_default_output_dir(home=tmp_path, temp_dir=str(tmp_path / "tmp"), warn=warnings.append)

    assert result == str(tmp_path / "tmp" / "TZ Analyzer")
    assert len(warnings) == 1
    assert "no se pudo crear" in warnings[0].lower()


def test_default_output_cwd_fn_normal_mode_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_output_cwd_fn() == os.getcwd()


def test_default_output_cwd_fn_frozen_mode_uses_documents_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("tz_core.user_paths.Path.home", classmethod(lambda cls: tmp_path))

    result = default_output_cwd_fn()

    assert result == str(tmp_path / "Documents" / "TZ Analyzer")
    assert Path(result).is_dir()
