"""MB8-B1: marker técnico de ownership sibling al staging transaccional."""
from __future__ import annotations

import json
import logging
import os
import socket
import uuid
import zipfile

import pytest

from tz_version import PRODUCT_NAME, PRODUCT_VERSION
from tz_web import instance as tz_instance
from tz_web import machine_id as mid
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


def _read_marker(marker_path: str):
    with open(marker_path, "r", encoding="utf-8") as source:
        return json.load(source)


# ---------------------------------------------------------------------------
# A. Creación
# ---------------------------------------------------------------------------


def test_A_reserve_crea_staging_y_marker_sibling(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    assert os.path.isdir(tx.work_dir)
    assert tx.marker_path == tx.reservation_dir + ".marker"
    assert os.path.isfile(tx.marker_path)
    # Sibling, no dentro del staging.
    assert os.path.dirname(tx.marker_path) == os.path.dirname(tx.reservation_dir)
    tx.abort()


# ---------------------------------------------------------------------------
# B. Contenido JSON
# ---------------------------------------------------------------------------


def test_B_marker_es_json_utf8_con_schema_esperado(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_instance, "_current_instance_id", "instancia-test")
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    try:
        payload = _read_marker(tx.marker_path)
        assert payload["schema"] == 1
        assert payload["product"] == PRODUCT_NAME
        assert payload["product_version"] == PRODUCT_VERSION
        assert payload["transaction_id"] == tx.transaction_id
        uuid.UUID(payload["transaction_id"])
        assert payload["created_at_utc"].endswith("+00:00") or "Z" in payload["created_at_utc"]
        assert payload["instance_id"] == "instancia-test"
        assert payload["machine_id"] is not None
        uuid.UUID(payload["machine_id"])
    finally:
        tx.abort()


# ---------------------------------------------------------------------------
# C. Privacidad
# ---------------------------------------------------------------------------


def test_C_marker_no_contiene_datos_del_caso_ni_del_equipo(tmp_path):
    candidato = "555-1234-caso-secreto-juan-perez"
    tx = ot.OutputTransaction.reserve(str(tmp_path), candidato)
    try:
        raw = open(tx.marker_path, "r", encoding="utf-8").read()
        assert candidato not in raw
        assert str(tmp_path) not in raw
        assert tx.final_dir not in raw
        assert os.environ.get("USERNAME", "___no_username___") not in raw
        assert socket.gethostname() not in raw
        payload = _read_marker(tx.marker_path)
        assert set(payload.keys()) == {
            "schema",
            "product",
            "product_version",
            "transaction_id",
            "created_at_utc",
            "instance_id",
            "machine_id",
        }
    finally:
        tx.abort()


# ---------------------------------------------------------------------------
# E. Fallo al escribir el marker: la transacción continúa
# ---------------------------------------------------------------------------


def test_E_fallo_al_escribir_marker_no_impide_reservar(tmp_path, monkeypatch, caplog):
    def _bogus_marker_path(reservation_dir):
        return os.path.join(str(tmp_path), "carpeta_inexistente", "x.marker")

    monkeypatch.setattr(ot, "_marker_path_for", _bogus_marker_path)
    with caplog.at_level(logging.WARNING, logger="tz_web.output_transaction"):
        tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    try:
        assert os.path.isdir(tx.work_dir)
        assert not os.path.exists(tx.marker_path)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "se esperaba un WARNING genérico"
        for record in warnings:
            message = record.getMessage()
            assert str(tmp_path) not in message
            assert "caso" not in message
            assert tx.transaction_id not in message
    finally:
        tx.abort()


# ---------------------------------------------------------------------------
# F. Publish exitoso
# ---------------------------------------------------------------------------


def test_F_publish_exitoso_elimina_marker_y_no_deja_metadata_en_final(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    result = ot.finalize_output(
        tx,
        artifacts=(
            ot.ArtifactSpec("html", html, required=True),
            ot.ArtifactSpec("kmz", kmz, required=True),
        ),
        mode="1",
        manifest_name="caso_hashes.txt",
    )
    assert os.path.isdir(result.final_dir)
    assert not os.path.exists(tx.marker_path)
    for _root, _dirs, files in os.walk(result.final_dir):
        for filename in files:
            assert not filename.endswith(".marker")


# ---------------------------------------------------------------------------
# G. Publish exitoso + fallo al eliminar el marker
# ---------------------------------------------------------------------------


def test_G_fallo_eliminando_marker_tras_publish_no_invalida_output(tmp_path, monkeypatch, caplog):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    html, kmz = _base_artifacts(tx)
    marker_path = tx.marker_path
    real_remove = ot.os.remove

    def _deny_remove(path):
        if os.path.abspath(path) == os.path.abspath(marker_path):
            raise OSError("fallo inyectado eliminando marker")
        return real_remove(path)

    monkeypatch.setattr(ot.os, "remove", _deny_remove)
    with caplog.at_level(logging.WARNING, logger="tz_web.output_transaction"):
        result = ot.finalize_output(
            tx,
            artifacts=(
                ot.ArtifactSpec("html", html, required=True),
                ot.ArtifactSpec("kmz", kmz, required=True),
            ),
            mode="1",
            manifest_name="caso_hashes.txt",
        )
    assert os.path.isdir(result.final_dir)
    assert result.status == ot.RESULT_SUCCESS
    assert os.path.isfile(marker_path)  # quedó huérfano, aceptable (MB8-B2)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# H. Fallo de publish: el marker no desaparece prematuramente
# ---------------------------------------------------------------------------


def test_H_fallo_de_rename_no_elimina_el_marker(tmp_path, monkeypatch):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    marker_path = tx.marker_path
    assert os.path.isfile(marker_path)

    def _boom_rename(*_args, **_kwargs):
        raise OSError("fallo de rename inyectado")

    monkeypatch.setattr(ot.os, "rename", _boom_rename)
    with pytest.raises(OSError, match="inyectado"):
        tx.publish()
    assert os.path.isfile(marker_path)
    tx.abort()


# ---------------------------------------------------------------------------
# I. Abort limpia staging y marker
# ---------------------------------------------------------------------------


def test_I_abort_limpia_staging_y_marker(tmp_path):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    marker_path = tx.marker_path
    assert os.path.isfile(marker_path)
    tx.abort()
    assert not os.path.exists(tx.staging_root)
    assert not os.path.exists(marker_path)


# ---------------------------------------------------------------------------
# J. Abort + fallo eliminando marker: no sustituye la excepción original
# ---------------------------------------------------------------------------


def test_J_fallo_eliminando_marker_durante_abort_no_agrega_excepcion(
    tmp_path, monkeypatch, caplog
):
    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    marker_path = tx.marker_path
    real_remove = ot.os.remove

    def _deny_remove(path):
        if os.path.abspath(path) == os.path.abspath(marker_path):
            raise OSError("fallo inyectado eliminando marker en abort")
        return real_remove(path)

    monkeypatch.setattr(ot.os, "remove", _deny_remove)
    with caplog.at_level(logging.WARNING, logger="tz_web.output_transaction"):
        tx.abort()  # no debe lanzar
    assert not os.path.exists(tx.staging_root)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# K. Dos transacciones: markers independientes
# ---------------------------------------------------------------------------


def test_K_dos_transacciones_tienen_transaction_id_y_marker_distintos(tmp_path):
    tx1 = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    tx2 = ot.OutputTransaction.reserve(str(tmp_path), "caso")
    try:
        assert tx1.name != tx2.name
        assert tx1.transaction_id != tx2.transaction_id
        assert tx1.marker_path != tx2.marker_path
        assert os.path.isfile(tx1.marker_path)
        assert os.path.isfile(tx2.marker_path)
        payload1 = _read_marker(tx1.marker_path)
        payload2 = _read_marker(tx2.marker_path)
        assert payload1["transaction_id"] != payload2["transaction_id"]
    finally:
        tx1.abort()
        tx2.abort()


# ---------------------------------------------------------------------------
# L. No housekeeping: B1 no toca stagings preexistentes sin marker
# ---------------------------------------------------------------------------


def test_L_reserve_no_toca_stagings_previos_sin_marker(tmp_path):
    huerfano = os.path.join(str(tmp_path), ".otro_caso.tzp")
    os.mkdir(huerfano)
    _write(os.path.join(huerfano, "resto.txt"), b"contenido de una staging vieja")

    tx = ot.OutputTransaction.reserve(str(tmp_path), "caso_nuevo")
    try:
        assert os.path.isdir(huerfano)
        assert os.path.isfile(os.path.join(huerfano, "resto.txt"))
        assert not os.path.exists(huerfano + ".marker")
    finally:
        tx.abort()
    # abort() de la transacción nueva tampoco debe haber tocado la vieja.
    assert os.path.isdir(huerfano)


def test_L_no_expone_ninguna_funcion_de_housekeeping():
    forbidden_prefixes = ("scan", "list_stagings", "cleanup", "purge", "housekeep")
    public_names = [name for name in dir(ot) if not name.startswith("_")]
    for name in public_names:
        lowered = name.lower()
        assert not any(lowered.startswith(prefix) for prefix in forbidden_prefixes), name
