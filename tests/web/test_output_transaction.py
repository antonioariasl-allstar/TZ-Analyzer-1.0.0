"""MB3: fallos inyectados del contrato transaccional compartido."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import zipfile

import pytest

from tz_web import output_transaction as ot


def _write(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as target:
        target.write(data)
    return path


def _valid_kmz(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("doc.kml", "<?xml version='1.0'?><kml><Document/></kml>")
    return path


def _base_artifacts(tx: ot.OutputTransaction):
    html = _write(os.path.join(tx.work_dir, "informe.html"), b"<!doctype html><html>ok</html>")
    kmz = _valid_kmz(os.path.join(tx.work_dir, "mapa.kmz"))
    return html, kmz


def _manifest_metadata(path: str):
    with open(path, "r", encoding="utf-8") as source:
        lines = source.read().splitlines()
    assert lines[0] == ot.MANIFEST_SCHEMA
    return json.loads(lines[1].split("\t", 1)[1]), lines[2:]


def test_A_input_modificado_tras_snapshot_es_detectado(tmp_path):
    source = _write(str(tmp_path / "aceptado.xlsx"), b"bytes aceptados")
    expected = ot.sha256_file(source)
    snapshot = ot.create_input_snapshot(
        source,
        str(tmp_path / "session"),
        expected_sha256=expected,
        original_name="caso.xlsx",
    )
    assert snapshot.sha256 == expected

    _write(snapshot.path, b"bytes alterados")
    with pytest.raises(ot.InputIntegrityError, match="cambió"):
        ot.verify_input_snapshot(snapshot.path, expected)


def test_A_rehash_inmediatamente_antes_de_publish_detecta_cambio_tardio(
    tmp_path, monkeypatch
):
    source = _write(str(tmp_path / "aceptado.xlsx"), b"bytes aceptados")
    expected = ot.sha256_file(source)
    snapshot = ot.create_input_snapshot(
        source, str(tmp_path / "session"), expected_sha256=expected
    )
    tx = ot.OutputTransaction.reserve(str(tmp_path / "out"), "caso")
    html, kmz = _base_artifacts(tx)
    write_manifest_real = ot._write_manifest

    def _write_then_mutate(*args, **kwargs):
        write_manifest_real(*args, **kwargs)
        _write(snapshot.path, b"cambio posterior al manifiesto")

    monkeypatch.setattr(ot, "_write_manifest", _write_then_mutate)
    with pytest.raises(ot.InputIntegrityError, match="cambió"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
            pre_publish_check=lambda: ot.verify_input_snapshot(snapshot.path, expected),
        )
    assert not os.path.exists(tx.final_dir)


def test_F_fallo_escribiendo_manifiesto_no_publica_y_limpia_staging(tmp_path, monkeypatch):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    staging_root = tx.staging_root

    def _boom(*_args, **_kwargs):
        raise OSError("fallo de manifiesto inyectado")

    monkeypatch.setattr(ot, "_write_manifest", _boom)
    with pytest.raises(OSError, match="inyectado"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )

    assert not os.path.exists(tx.final_dir)
    assert not os.path.exists(staging_root)
    assert not os.path.exists(tx.reservation_dir)


def test_G_producto_obligatorio_ausente_es_failed_sin_publicacion(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html = _write(os.path.join(tx.work_dir, "informe.html"), b"<html>ok</html>")
    with pytest.raises(ot.OutputValidationError, match="kmz"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", None, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert not os.path.exists(tx.final_dir)


def test_I_output_final_previo_no_se_sobrescribe(tmp_path):
    previous = tmp_path / "caso"
    previous.mkdir()
    marker = previous / "anterior.txt"
    marker.write_text("intacto", encoding="utf-8")

    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    assert tx.name == "caso_02"
    html, kmz = _base_artifacts(tx)
    result = ot.finalize_output(
        tx,
        artifacts=(
            ot.ArtifactSpec("html", html, required=True),
            ot.ArtifactSpec("kmz", kmz, required=True),
        ),
        mode="1",
        manifest_name=f"{tx.name}_hashes.txt",
    )

    assert result.final_dir.endswith("caso_02")
    assert marker.read_text(encoding="utf-8") == "intacto"


def test_J_dos_reservas_simultaneas_reciben_variantes_seguras(tmp_path):
    barrier = threading.Barrier(3)
    transactions = []
    errors = []

    def _reserve():
        try:
            barrier.wait(timeout=5)
            transactions.append(ot.OutputTransaction.reserve(str(tmp_path), "caso"))
        except Exception as exc:  # pragma: no cover - se reporta abajo
            errors.append(exc)

    threads = [threading.Thread(target=_reserve) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)

    try:
        assert errors == []
        assert sorted(tx.name for tx in transactions) == ["caso", "caso_02"]
        assert len({tx.final_dir for tx in transactions}) == 2
    finally:
        for tx in transactions:
            tx.abort()


def test_K_kmz_corrupto_impide_publicacion_success(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html = _write(os.path.join(tx.work_dir, "informe.html"), b"<html>ok</html>")
    kmz = _write(os.path.join(tx.work_dir, "mapa.kmz"), b"no es zip")

    with pytest.raises(ot.OutputValidationError, match="KMZ|kmz"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert not os.path.exists(tx.final_dir)


@pytest.mark.parametrize(
    "embedded_kml",
    [b"<kml><roto>", b"<?xml version='1.0'?><foo/>"]
)
def test_K_kmz_con_xml_interno_no_kml_tambien_es_rechazado(tmp_path, embedded_kml):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html = _write(os.path.join(tx.work_dir, "informe.html"), b"<html>ok</html>")
    kmz = os.path.join(tx.work_dir, "mapa.kmz")
    with zipfile.ZipFile(kmz, "w") as archive:
        archive.writestr("doc.kml", embedded_kml)

    with pytest.raises(ot.OutputValidationError, match="KML|kml"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert not os.path.exists(tx.final_dir)


@pytest.mark.parametrize("invalid_kml", [b"<kml><roto>", b"<?xml version='1.0'?><foo/>"])
def test_L_kml_invalido_solicitado_es_partial_y_no_se_publica(tmp_path, invalid_kml):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    kml = _write(os.path.join(tx.work_dir, "mapa.kml"), invalid_kml)

    result = ot.finalize_output(
        tx,
        artifacts=(
            ot.ArtifactSpec("html", html, required=True),
            ot.ArtifactSpec("kmz", kmz, required=True),
            ot.ArtifactSpec("kml", kml, required=False, requested=True),
        ),
        mode="1",
        manifest_name="caso_hashes.txt",
    )

    assert result.status == ot.RESULT_PARTIAL
    assert "kml" not in result.artifacts
    assert not os.path.exists(os.path.join(result.final_dir, "mapa.kml"))
    assert all(entry.role != "kml" for entry in result.entries)


def test_L_si_no_puede_retirarse_opcional_invalido_se_aborta(tmp_path, monkeypatch):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    kml = _write(os.path.join(tx.work_dir, "mapa.kml"), b"<foo/>")
    real_remove = ot.os.remove

    def _deny_remove(path):
        if os.path.abspath(path) == os.path.abspath(kml):
            raise OSError("archivo bloqueado")
        return real_remove(path)

    monkeypatch.setattr(ot.os, "remove", _deny_remove)
    with pytest.raises(ot.OutputValidationError, match="retirar"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
                ot.ArtifactSpec("kml", kml, required=False, requested=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert not os.path.exists(tx.final_dir)


def test_N_O_P_manifiesto_coincide_no_se_autoincluye_y_nada_cambia(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    support = _write(os.path.join(tx.work_dir, "aux", "detalle.txt"), b"soporte")
    log_path = _write(os.path.join(tx.work_dir, "caso_ejecucion_log.txt"), b"log cerrado")

    result = ot.finalize_output(
        tx,
        artifacts=(
            ot.ArtifactSpec("html", html, required=True),
            ot.ArtifactSpec("kmz", kmz, required=True),
        ),
        mode="2",
        manifest_name="caso_hashes.txt",
        input_metadata={"original_name": "entrada.xlsx", "snapshot_sha256": "a" * 64},
        executed_at="2026-08-11T00:00:00+00:00",
        excluded_paths=(log_path,),
    )

    metadata, file_lines = _manifest_metadata(result.manifest_path)
    assert metadata["status"] == "SUCCESS"
    assert metadata["unhashed_files"] == ["caso_ejecucion_log.txt"]
    assert all("caso_hashes.txt" not in line for line in file_lines)
    assert all("ejecucion_log" not in line for line in file_lines)
    assert any(entry.role == "support" and entry.relative_path == "aux/detalle.txt" for entry in result.entries)

    recorded = {}
    for entry in result.entries:
        final_path = os.path.join(result.final_dir, *entry.relative_path.split("/"))
        digest = hashlib.sha256(open(final_path, "rb").read()).hexdigest()
        assert digest == entry.sha256
        recorded[entry.relative_path] = (digest, os.path.getsize(final_path))

    # Leer/verificar después de publicar no reescribe ningún listado.
    for relative, expected in recorded.items():
        final_path = os.path.join(result.final_dir, *relative.split("/"))
        assert (ot.sha256_file(final_path), os.path.getsize(final_path)) == expected
    assert os.path.isfile(os.path.join(result.final_dir, "caso_ejecucion_log.txt"))
    assert os.path.isfile(os.path.join(result.final_dir, os.path.relpath(support, tx.work_dir)))


def test_P_mutacion_real_tras_digest_revierte_la_publicacion(tmp_path, monkeypatch):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    publish_real = tx.publish

    def _mutate_then_publish():
        with open(html, "ab") as target:
            target.write(b"alterado tras digest")
        return publish_real()

    monkeypatch.setattr(tx, "publish", _mutate_then_publish)
    with pytest.raises(ot.OutputValidationError, match="integridad cambió"):
        ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert not os.path.exists(tx.final_dir)
