"""Tests para helpers de metadatos HTML y snapshot de entorno."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from tz_core.html.metadata import (
    inject_technical_metadata,
    _build_meta_block,
    _inject_block,
)
from tz_core.html.antennas import (
    resolve_top_antennas_n,
    build_top_antennas_section,
    build_antennas_by_hour_section,
)
import pandas as pd
import tz_core.runtime_utils as runtime_utils
import tz_version


def test_inject_metadata_disabled_noop(tmp_path):
    path = tmp_path / "reporte.html"
    original = "<html><body><p>hola</p></body></html>"
    path.write_text(original, encoding="utf-8")

    config = {"html": {"metadatos_tecnicos": {"enabled": False}}}

    assert not inject_technical_metadata(str(path), config)
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

    monkeypatch.setattr("tz_core.html.metadata.collect_env_snapshot", lambda _: snapshot)

    assert inject_technical_metadata(str(path), config)
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

    block = _build_meta_block(snapshot, "ampliado", True)

    assert "Metadatos" in block
    assert "UnitOS" in block
    assert "cfg-A" in block
    assert "Hostname" in block
    assert "Usuario" in block


def test_build_meta_block_returns_empty_without_values():
    block = _build_meta_block({}, "minimo", False)
    assert block == ""


def test_inject_block_prefers_meta_sections():
    block = "<div>meta</div>"
    html = '<html><body><section class="meta-card"></section></body></html>'

    nuevo, injected = _inject_block(html, block)

    assert injected
    assert nuevo.count(block) == 1
    assert nuevo.index(block) < nuevo.index("</section>")


def test_inject_block_fallbacks_to_body_and_append():
    block = "<div>meta</div>"
    html_body = "<html><body><section></section></body></html>"
    html_plain = "<html><div>sin body</div></html>"

    in_body, injected_body = _inject_block(html_body, block)
    assert injected_body
    assert "<body" in in_body and block in in_body

    appended, injected_append = _inject_block(html_plain, block)
    assert injected_append
    assert appended.endswith(block)


def test_collect_env_snapshot_usa_tz_version_e_ignora_config(monkeypatch):
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

    # Valores deliberadamente distintos de tz_version.VERSION: prueban que
    # "tz_analysis" ya no puede leerse de config.json (fuente única:
    # tz_version). "version_config" sigue siendo config-driven a propósito
    # (identifica la versión del archivo de configuración, no del producto).
    config = {"version": "2.0.0", "version_config": "cfg-x", "brand": {"version": "0.1"}}

    snapshot = runtime_utils.collect_env_snapshot(config)

    assert snapshot["so"] == "UnitOS 11"
    assert snapshot["tz"] == "UnitTZ"
    assert snapshot["fecha_hora"] == "2026-01-03 12:00:00"
    assert snapshot["tz_analysis"] == tz_version.VERSION
    assert snapshot["version_config"] == "cfg-x"
    assert snapshot["hostname"] == "unit-host"
    assert snapshot["usuario"] == "ci-user"


def test_resolve_top_antennas_n_prefers_override_then_config():
    cfg = {"top_antenas": 7, "html": {"top_antenas_n": 9}}
    overrides = {"antenas": 5}

    assert resolve_top_antennas_n(cfg, overrides, default=3) == 5

    # Sin override usa config
    assert resolve_top_antennas_n(cfg, None, default=3) == 7

    # Sin top_antenas usa html.top_antenas_n
    cfg2 = {"html": {"top_antenas_n": 4}}
    assert resolve_top_antennas_n(cfg2, None, default=3) == 4

    # Fallback a default ante valores inválidos
    cfg_bad = {"top_antenas": "no-int"}
    assert resolve_top_antennas_n(cfg_bad, None, default=11) == 11


def test_build_top_antennas_section_respects_override_and_bbox():
    df = pd.DataFrame(
        [
            {"antena": "A1", "lat": 13.7, "long": -89.2, "azimut": 10},
            {"antena": "A1", "lat": 13.71, "long": -89.21, "azimut": 10},
            {"antena": "A2", "lat": 13.8, "long": -89.25, "azimut": 45},
            {"antena": "A3", "lat": 13.9, "long": -89.3, "azimut": 90},
        ]
    )

    cfg = {"top_antenas": 1}
    overrides = {"antenas": 2}

    html = build_top_antennas_section(df, cfg, overrides)

    assert "id=\"resumen-antenas\"" in html
    # Override 2 → debe contener A1 y A2, pero no A3
    assert "A1" in html and "A2" in html
    assert "A3" not in html
    # Link a maps presente
    assert "google.com/maps" in html


def test_build_antennas_by_hour_section_basic():
    df = pd.DataFrame(
        [
            {"antena": "A1", "hora": "06:30:00", "lat": 13.7, "long": -89.2, "azimut": 10},
            {"antena": "A2", "hora": "13:00:00", "lat": 13.71, "long": -89.21, "azimut": 20},
            {"antena": "A3", "hora": "02:00:00", "lat": 13.8, "long": -89.25, "azimut": 30},
        ]
    )

    html = build_antennas_by_hour_section(df, {"html": {"top_antenas_n": 2}}, overrides=None)

    assert 'id="antenas-rangos"' in html
    assert "Mañana" in html and "Tarde" in html and "Madrugada" in html
    assert "google.com/maps" in html


def test_build_antennas_by_hour_section_respects_override():
    df = pd.DataFrame(
        [
            {"antena": "A1", "hora": "10:00", "lat": 13.7, "long": -89.2},
            {"antena": "A2", "hora": "10:30", "lat": 13.71, "long": -89.21},
            {"antena": "A3", "hora": "10:45", "lat": 13.8, "long": -89.25},
        ]
    )

    html = build_antennas_by_hour_section(df, None, overrides={"antenas": 1})

    assert html.count("<tr><td class='mono'>") == 1


def test_build_antennas_by_hour_section_parses_nonstandard_hours():
    df = pd.DataFrame(
        [
            {"antena": "A1", "hora": "6.30", "lat": 13.7, "long": -89.2},
            {"antena": "A2", "hora": "14-20", "lat": 13.71, "long": -89.21},
            {"antena": "A3", "hora": "21/05", "lat": 13.8, "long": -89.25},
        ]
    )

    html = build_antennas_by_hour_section(df, {"html": {"top_antenas_n": 5}}, overrides=None)

    assert "Mañana" in html and "Tarde" in html and "Noche" in html


