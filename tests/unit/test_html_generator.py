"""Tests para helpers de metadatos HTML y snapshot de entorno."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import tz_core.html_generator as html_generator
import tz_core.runtime_utils as runtime_utils


def test_inject_metadata_disabled_noop(tmp_path):
    path = tmp_path / "reporte.html"
    original = "<html><body><p>hola</p></body></html>"
    path.write_text(original, encoding="utf-8")

    config = {"html": {"metadatos_tecnicos": {"enabled": False}}}

    assert not html_generator.inject_technical_metadata(str(path), config)
    assert path.read_text(encoding="utf-8") == original


def test_inject_metadata_inserts_snapshot_block(tmp_path, monkeypatch):
    path = tmp_path / "reporte.html"
    template = '<html><body><section class="metainfo"></section></body></html>'
    path.write_text(template, encoding="utf-8")

    config = {
        "version": "1.2.3",
        "version_config": "cfg-9",
        "html": {
            "metadatos_tecnicos": {
                "enabled": True,
                "modo": "ampliado",
                "mostrar_versiones": True,
            }
        },
    }

    snapshot = {
        "so": "TestOS 1",
        "python": "3.12.8",
        "tz": "UTC",
        "fecha_hora": "2026-01-03 12:00:00",
        "tz_analysis": "1.2.3",
        "version_config": "cfg-9",
        "hostname": "unit-host",
        "usuario": "tester",
    }

    monkeypatch.setattr(html_generator, "collect_env_snapshot", lambda _: snapshot)

    assert html_generator.inject_technical_metadata(str(path), config)
    resultado = path.read_text(encoding="utf-8")

    assert "Metadatos técnicos (ampliado)" in resultado
    assert "TestOS 1" in resultado
    assert "cfg-9" in resultado
    assert resultado.count("meta-tecnica") == 1


def test_build_meta_block_handles_modes_and_versions():
    snapshot = {
        "so": "UnitOS",
        "python": "3.12.8",
        "tz_analysis": "2.1.0",
        "version_config": "cfg-A",
        "hostname": "unit-host",
        "usuario": "tester",
    }

    block = html_generator._build_meta_block(snapshot, "ampliado", True)

    assert "Metadatos" in block
    assert "UnitOS" in block
    assert "cfg-A" in block
    assert "Hostname" in block
    assert "Usuario" in block


def test_build_meta_block_returns_empty_without_values():
    block = html_generator._build_meta_block({}, "minimo", False)
    assert block == ""


def test_inject_block_prefers_meta_sections():
    block = "<div>meta</div>"
    html = '<html><body><section class="meta-card"></section></body></html>'

    nuevo, injected = html_generator._inject_block(html, block)

    assert injected
    assert nuevo.count(block) == 1
    assert nuevo.index(block) < nuevo.index("</section>")


def test_inject_block_fallbacks_to_body_and_append():
    block = "<div>meta</div>"
    html_body = "<html><body><section></section></body></html>"
    html_plain = "<html><div>sin body</div></html>"

    in_body, injected_body = html_generator._inject_block(html_body, block)
    assert injected_body
    assert "<body" in in_body and block in in_body

    appended, injected_append = html_generator._inject_block(html_plain, block)
    assert injected_append
    assert appended.endswith(block)


def test_collect_env_snapshot_prefers_config(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 1, 3, 12, 0, 0)

    monkeypatch.setattr(runtime_utils, "time", SimpleNamespace(tzname=("UnitTZ", "UnitTZ")))
    monkeypatch.setattr(runtime_utils, "datetime", FixedDatetime)
    monkeypatch.setattr(runtime_utils.platform, "system", lambda: "UnitOS")
    monkeypatch.setattr(runtime_utils.platform, "release", lambda: "11")
    monkeypatch.setattr(runtime_utils.platform, "node", lambda: "unit-host")
    monkeypatch.setattr(runtime_utils.getpass, "getuser", lambda: "ci-user")

    config = {"version": "2.0.0", "version_config": "cfg-x", "brand": {"version": "0.1"}}

    snapshot = runtime_utils.collect_env_snapshot(config)

    assert snapshot["so"] == "UnitOS 11"
    assert snapshot["tz"] == "UnitTZ"
    assert snapshot["fecha_hora"] == "2026-01-03 12:00:00"
    assert snapshot["tz_analysis"] == "2.0.0"
    assert snapshot["version_config"] == "cfg-x"
    assert snapshot["hostname"] == "unit-host"
    assert snapshot["usuario"] == "ci-user"
