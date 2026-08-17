"""MB8-B1: identidad técnica de máquina para el marker de ownership."""
from __future__ import annotations

import uuid

from tz_core.user_paths import get_user_config_dir
from tz_web import machine_id as mid


def test_primera_lectura_crea_identidad_valida(tmp_path):
    localappdata = str(tmp_path)
    created = mid.get_or_create_machine_id(localappdata)
    assert created is not None
    uuid.UUID(created)  # no lanza -> formato válido

    path = get_user_config_dir(localappdata) / "machine_id"
    assert path.is_file()


def test_segunda_lectura_devuelve_la_misma_identidad(tmp_path):
    localappdata = str(tmp_path)
    first = mid.get_or_create_machine_id(localappdata)
    second = mid.get_or_create_machine_id(localappdata)
    assert first == second


def test_no_deriva_de_hostname_ni_mac(tmp_path):
    import socket
    import uuid as uuid_module

    localappdata = str(tmp_path)
    created = mid.get_or_create_machine_id(localappdata)
    assert socket.gethostname() not in created
    assert str(uuid_module.getnode()) not in created


def test_vive_bajo_localappdata_helper_canonico(tmp_path):
    localappdata = str(tmp_path)
    mid.get_or_create_machine_id(localappdata)
    expected_dir = get_user_config_dir(localappdata)
    assert (expected_dir / "machine_id").exists()


def test_archivo_corrupto_no_se_sobrescribe(tmp_path):
    localappdata = str(tmp_path)
    path = get_user_config_dir(localappdata) / "machine_id"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("no-es-un-uuid", encoding="utf-8")

    result = mid.get_or_create_machine_id(localappdata)
    assert result is None
    assert path.read_text(encoding="utf-8") == "no-es-un-uuid"


def test_env_localappdata_real_no_se_toca_por_defecto(monkeypatch, tmp_path):
    # El autouse de tests/conftest.py ya redirige LOCALAPPDATA; esta prueba
    # confirma explícitamente que get_or_create_machine_id() respeta esa
    # redirección cuando se llama sin argumento.
    redirected = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(redirected))
    mid.get_or_create_machine_id()
    assert (redirected / "TZ Analyzer" / "machine_id").exists()
