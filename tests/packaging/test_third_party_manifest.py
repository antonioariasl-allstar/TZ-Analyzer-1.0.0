"""build_config/third_party_components.json: manifiesto curado de licencias.

Valida forma y que los archivos que cada componente declara (license_files,
notice_files, bundled_license_files) existan realmente, según su 'kind'
(pip / vendored / repo_asset / compliance). No compara textos legales
completos contra goldens: solo existencia y metadatos básicos (ver
P1-LICENSES, sección 30; kind 'compliance' agregado en P1-LICENSES-B1 para
los binarios nativos OpenSSL/zlib/SQLite).
"""
from __future__ import annotations

import json
import re

import pytest

from tools.build_third_party_notices import MANIFEST_PATH, load_manifest, resolve_component_file

_REQUIRED_STRING_FIELDS = ("name", "version", "kind", "license")
_VALID_KINDS = {"pip", "vendored", "repo_asset", "compliance"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def test_file_exists():
    assert MANIFEST_PATH.is_file()


def test_is_valid_json():
    json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_load_manifest_returns_nonempty_list():
    components = load_manifest()
    assert isinstance(components, list)
    assert len(components) > 0


def test_each_component_has_required_fields():
    for component in load_manifest():
        for field in _REQUIRED_STRING_FIELDS:
            value = component.get(field)
            assert isinstance(value, str) and value.strip(), (component.get("name"), field)


def test_each_component_has_valid_kind():
    for component in load_manifest():
        assert component["kind"] in _VALID_KINDS, component["name"]


def test_kind_specific_identifier_present():
    for component in load_manifest():
        kind = component["kind"]
        if kind == "pip":
            assert component.get("pip_name"), component["name"]
        elif kind == "vendored":
            assert component.get("vendored_dir"), component["name"]
        elif kind == "repo_asset":
            assert component.get("asset_dir"), component["name"]
        elif kind == "compliance":
            assert component.get("compliance_dir"), component["name"]


def test_no_component_declares_absolute_paths():
    for component in load_manifest():
        for field in ("license_files", "notice_files", "bundled_license_files"):
            for relative_path in component.get(field, []):
                assert ":" not in relative_path and not relative_path.startswith("/"), (
                    component["name"],
                    relative_path,
                )


def test_component_names_are_unique():
    names = [component["name"] for component in load_manifest()]
    assert len(names) == len(set(names)), names


@pytest.mark.parametrize("component", load_manifest(), ids=lambda c: c["name"])
def test_license_files_exist(component):
    for relative_path in component.get("license_files", []):
        path = resolve_component_file(component, relative_path)
        assert path.is_file(), (component["name"], relative_path, path)


@pytest.mark.parametrize("component", load_manifest(), ids=lambda c: c["name"])
def test_notice_files_exist(component):
    for relative_path in component.get("notice_files", []):
        path = resolve_component_file(component, relative_path)
        assert path.is_file(), (component["name"], relative_path, path)


@pytest.mark.parametrize("component", load_manifest(), ids=lambda c: c["name"])
def test_bundled_license_files_exist(component):
    for relative_path in component.get("bundled_license_files", []):
        path = resolve_component_file(component, relative_path)
        assert path.is_file(), (component["name"], relative_path, path)


@pytest.mark.parametrize("component", load_manifest(), ids=lambda c: c["name"])
def test_component_declares_at_least_one_evidence_file(component):
    declared = (
        component.get("license_files", [])
        + component.get("notice_files", [])
        + component.get("bundled_license_files", [])
    )
    assert declared, component["name"]


def test_simplekml_is_flagged_as_lgpl_special_case():
    components = {component["name"]: component for component in load_manifest()}
    simplekml = components["simplekml"]
    assert "LGPL" in simplekml["license"]
    assert "B" in simplekml["notes"] or "clasificacion" in simplekml["notes"].lower()


@pytest.mark.parametrize("component", load_manifest(), ids=lambda c: c["name"])
def test_binary_files_have_valid_sha256(component):
    binary_files = component.get("binary_files", [])
    sha256_map = component.get("sha256", {})
    if not binary_files:
        return
    assert set(binary_files) == set(sha256_map), component["name"]
    for filename, digest in sha256_map.items():
        assert _SHA256_RE.match(digest), (component["name"], filename, digest)
        assert "\\" not in filename and "/" not in filename, (component["name"], filename)


@pytest.mark.parametrize("name", ["OpenSSL", "zlib", "SQLite"])
def test_native_binary_components_present(name):
    components = {component["name"]: component for component in load_manifest()}
    assert name in components


def test_openssl_covers_both_dlls_in_single_entry():
    components = {component["name"]: component for component in load_manifest()}
    openssl = components["OpenSSL"]
    assert set(openssl.get("binary_files", [])) == {"libssl-3.dll", "libcrypto-3.dll"}


def test_sqlite_license_is_public_domain():
    components = {component["name"]: component for component in load_manifest()}
    assert components["SQLite"]["license"] == "Public Domain"
