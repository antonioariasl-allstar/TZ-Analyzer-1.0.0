"""MB3: snapshot manual y publicacion transaccional de Modo 3."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from tz_web import output_transaction, services_modo3
from tz_web.output_transaction import InputIntegrityError, RESULT_PARTIAL, RESULT_SUCCESS
from tz_web.services_modo3 import (
    MODO3_TIPO_ANTENA,
    Modo3Request,
    process_case_modo3,
    serializar_snapshot_modo3,
)


REGISTRO_ANTENA = {
    "id": "solo-ui-123",
    "nombre": "Antena Ñandú",
    "lat": 10.5,
    "lon": -66.9,
    "azimut": 22.5,
    "celda": "C1",
    "direccion": "Avenida Central",
    "detalle": "Torre principal",
}


def _procesar_modo3(tmp_path: Path, **overrides):
    values = {
        "tipo": MODO3_TIPO_ANTENA,
        "registros": [dict(REGISTRO_ANTENA)],
        "carpeta_salida": str(tmp_path / "salidas"),
        "color_hex": "#123456",
        "kml_opcional": True,
        "output_base_name": "caso_manual",
    }
    values.update(overrides)
    return process_case_modo3(Modo3Request(**values))


def _leer_manifiesto(path: str):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "TZ_ANALYZER_MANIFEST_V1"
    prefix, metadata_json = lines[1].split("\t", 1)
    assert prefix == "METADATA"
    metadata = json.loads(metadata_json)
    entries = []
    for line in lines[2:]:
        algorithm, digest, size, role, relative_path = line.split("\t", 4)
        assert algorithm == "SHA256"
        entries.append(
            {
                "sha256": digest,
                "size": int(size),
                "role": role,
                "relative_path": relative_path,
            }
        )
    return metadata, entries


def test_M_snapshot_modo3_es_utf8_determinista_y_coincide_con_lo_procesado(
    tmp_path, monkeypatch
):
    consumed = {}
    original_builder = services_modo3.construir_dataframe_modo3

    def _capture_builder(tipo, registros):
        consumed["tipo"] = tipo
        consumed["registros"] = copy.deepcopy(registros)
        return original_builder(tipo, registros)

    monkeypatch.setattr(services_modo3, "construir_dataframe_modo3", _capture_builder)
    result = _procesar_modo3(tmp_path)

    assert result.status == RESULT_SUCCESS
    snapshot_path = Path(result.summary["snapshot_path"])
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_bytes.decode("utf-8"))

    assert snapshot_path.parent == Path(result.output_dir)
    assert snapshot_bytes.endswith(b"\n")
    assert b"\r\n" not in snapshot_bytes
    assert "Antena Ñandú".encode("utf-8") in snapshot_bytes
    assert serializar_snapshot_modo3(snapshot) == snapshot_bytes
    assert snapshot["modo"] == "MODO_3"
    assert snapshot["tipo"] == "antena"
    assert snapshot["registros"] == [
        {
            "nombre": "Antena Ñandú",
            "lat": 10.5,
            "lon": -66.9,
            "azimut": 22.5,
            "celda": "C1",
            "direccion": "Avenida Central",
            "detalle": "Torre principal",
        }
    ]
    assert "id" not in snapshot["registros"][0]
    assert consumed == {
        "tipo": snapshot["tipo"],
        "registros": snapshot["registros"],
    }

    cartografia = snapshot["configuracion_cartografica"]
    assert cartografia["generador"] == "antenas_flat"
    assert cartografia["flat"] is True
    assert cartografia["kml_opcional"] is True
    assert cartografia["salida"] == {"solo_kmz": False}
    assert cartografia["style"]["theme_hex"] == "#123456"
    assert "azimuth_km" in cartografia["kml"]

    digest = hashlib.sha256(snapshot_bytes).hexdigest()
    assert result.summary["snapshot_sha256"] == digest
    metadata, entries = _leer_manifiesto(result.hashes_path)
    assert metadata["mode"] == "3"
    assert metadata["status"] == "SUCCESS"
    assert metadata["input"]["snapshot_sha256"] == digest
    assert any(entry["role"] == "snapshot_json" for entry in entries)


def test_A_modo3_mutacion_tardia_del_snapshot_impide_publicacion(
    tmp_path, monkeypatch
):
    real_finalize = output_transaction.finalize_output

    def _mutate_then_finalize(transaction, **kwargs):
        snapshot_spec = next(
            spec for spec in kwargs["artifacts"] if spec.role == "snapshot_json"
        )
        with open(snapshot_spec.path, "ab") as snapshot_file:
            snapshot_file.write(b" ")
        return real_finalize(transaction, **kwargs)

    monkeypatch.setattr(services_modo3, "finalize_output", _mutate_then_finalize)

    with pytest.raises(InputIntegrityError, match="cambi"):
        _procesar_modo3(tmp_path)

    output_base = tmp_path / "salidas"
    assert output_base.is_dir()
    assert list(output_base.iterdir()) == []


def test_H_kml_opcional_solicitado_ausente_publica_partial(
    tmp_path, monkeypatch
):
    def generar_solo_kmz(_df, archivo_kml, *, config, flat):
        assert config["salida"]["solo_kmz"] is False
        assert flat is True
        kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"
        with zipfile.ZipFile(kmz_path, "w") as archive:
            archive.writestr("doc.kml", "<kml xmlns='http://www.opengis.net/kml/2.2'/>")
        return archivo_kml, 0

    monkeypatch.setattr(
        "tz_web.services_modo3.generar_kml", generar_solo_kmz
    )

    result = _procesar_modo3(tmp_path, kml_opcional=True)

    assert result.success is False
    assert result.status == RESULT_PARTIAL
    assert result.summary["result_status"] == RESULT_PARTIAL
    assert result.kmz_path and os.path.isfile(result.kmz_path)
    assert result.kml_path is None
    assert result.hashes_path and os.path.isfile(result.hashes_path)
    assert result.summary["snapshot_path"]
    assert any("opcional solicitado: kml" in warning for warning in result.warnings)
    metadata, _entries = _leer_manifiesto(result.hashes_path)
    assert metadata["status"] == "PARTIAL"


def test_N_hashes_recomputados_coinciden_con_cada_archivo_listado(tmp_path):
    result = _procesar_modo3(tmp_path)
    _metadata, entries = _leer_manifiesto(result.hashes_path)

    assert entries
    for entry in entries:
        artifact = Path(result.output_dir, *Path(entry["relative_path"]).parts)
        content = artifact.read_bytes()
        assert len(content) == entry["size"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]


def test_O_manifiesto_no_se_autoincluye_y_log_aplica_politica_b(tmp_path):
    result = _procesar_modo3(tmp_path)
    metadata, entries = _leer_manifiesto(result.hashes_path)
    listed = {entry["relative_path"] for entry in entries}

    assert Path(result.hashes_path).name not in listed
    assert result.log_path and os.path.isfile(result.log_path)
    assert Path(result.log_path).name not in listed
    assert metadata["log_policy"] == "best-effort-excluded"


def test_P_archivos_listados_no_cambian_despues_de_registrar_digest(
    tmp_path, monkeypatch
):
    original_sha256 = output_transaction.sha256_file
    observations = {}

    def observing_sha256(path):
        digest = original_sha256(path)
        observations.setdefault(os.path.basename(path), []).append(digest)
        return digest

    monkeypatch.setattr(output_transaction, "sha256_file", observing_sha256)
    result = _procesar_modo3(tmp_path)
    _metadata, entries = _leer_manifiesto(result.hashes_path)

    for entry in entries:
        name = Path(entry["relative_path"]).name
        # Una lectura crea la entrada en staging y otra verifica los mismos
        # bytes ya publicados. Cualquier escritura intermedia rompe el par.
        assert len(observations[name]) >= 2
        assert observations[name][0] == observations[name][-1] == entry["sha256"]
        final_path = Path(result.output_dir, *Path(entry["relative_path"]).parts)
        assert original_sha256(str(final_path)) == entry["sha256"]
