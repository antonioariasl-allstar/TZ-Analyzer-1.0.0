"""tools/build_third_party_notices.py: helper mecánico de avisos de terceros.

Corre el helper real (lee el manifiesto real, resuelve archivos reales) en
vez de mockearlo: es la única forma de verificar que THIRD-PARTY-NOTICES.txt
generado es determinista, cubre cada componente y no filtra rutas de la
máquina de build (ver P1-LICENSES, secciones 30-31).
"""
from __future__ import annotations

import pytest

import tools.build_third_party_notices as notices_module
from tools.build_third_party_notices import (
    NoticesError,
    generate_notices_text,
    load_manifest,
)

_FORBIDDEN_SUBSTRINGS = (
    "C:\\Users",
    "C:\\TZ-Analyzer",
    ".venv312",
    "AppData",
    "LOCALAPPDATA",
    "Temp\\",
)


@pytest.fixture(scope="module")
def components():
    return load_manifest()


@pytest.fixture(scope="module")
def rendered_text(components):
    return generate_notices_text(components)


def test_generation_is_deterministic(components):
    first = generate_notices_text(components)
    second = generate_notices_text(components)
    assert first == second


def test_contains_every_component_name(rendered_text, components):
    for component in components:
        assert component["name"] in rendered_text


def test_contains_every_component_version(rendered_text, components):
    for component in components:
        assert component["version"] in rendered_text


def test_does_not_contain_absolute_machine_paths(rendered_text):
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in rendered_text, forbidden


def test_header_present(rendered_text):
    assert "AVISOS DE TERCEROS" in rendered_text


def test_resolve_component_file_rejects_unknown_kind():
    with pytest.raises(NoticesError):
        notices_module.resolve_component_file({"kind": "unknown", "name": "x"}, "LICENSE")


def test_locate_pip_file_rejects_version_mismatch():
    with pytest.raises(NoticesError):
        notices_module._locate_pip_file("click", "0.0.0-does-not-exist", "LICENSE.txt")


def test_locate_pip_file_rejects_missing_package():
    with pytest.raises(NoticesError):
        notices_module._locate_pip_file("this-package-does-not-exist", "1.0", "LICENSE.txt")


def test_load_manifest_raises_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(notices_module, "MANIFEST_PATH", tmp_path / "missing.json")
    with pytest.raises(NoticesError):
        notices_module.load_manifest()


def test_validate_component_files_raises_on_declared_but_absent_file(tmp_path):
    component = {
        "name": "componente-de-prueba",
        "kind": "vendored",
        "vendored_dir": "no-existe",
        "license_files": ["LICENSE-que-no-existe.txt"],
        "notice_files": [],
        "bundled_license_files": [],
    }
    with pytest.raises(NoticesError):
        notices_module.validate_component_files(component)
