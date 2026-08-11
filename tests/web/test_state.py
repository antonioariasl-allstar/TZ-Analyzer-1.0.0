"""FASE 2 WEB — tz_web.state: contrato de progreso, sesiones y limpieza."""
from __future__ import annotations

import os
import time

import pytest

from tz_web import state as tz_web_state
from tz_web.services import (
    AnalysisInProgressError,
    ArchivoNoProcesableError,
    CaseFileNotFoundError,
    CaseLoadError,
    InvalidMappingError,
    OutputDirectoryError,
    SheetNotFoundError,
)


def test_stage_percent_cubre_las_8_etapas_reales_de_process_case():
    from tz_web.services import _PROGRESS_STAGES

    assert set(tz_web_state.STAGE_PERCENT.keys()) == set(_PROGRESS_STAGES)
    assert tz_web_state.STAGE_PERCENT["finalizado"] == 100
    # Estrictamente creciente: nunca retrocede ni repite valor entre etapas.
    valores = [tz_web_state.STAGE_PERCENT[e] for e in _PROGRESS_STAGES]
    assert valores == sorted(valores)
    assert len(set(valores)) == len(valores)


@pytest.mark.parametrize("exc_type,mensaje", [
    (CaseFileNotFoundError, "archivo de prueba no encontrado"),
    (SheetNotFoundError, "hoja de prueba no encontrada"),
    (CaseLoadError, "no se pudo cargar"),
    (InvalidMappingError, "mapeo inválido de prueba"),
    (OutputDirectoryError, "carpeta de prueba inválida"),
    (AnalysisInProgressError, "ya en ejecución de prueba"),
    (ArchivoNoProcesableError, "no procesable de prueba"),
])
def test_translate_error_usa_el_mensaje_curado_de_excepciones_de_dominio(exc_type, mensaje):
    assert tz_web_state.translate_error(exc_type(mensaje)) == mensaje


def test_translate_error_excepcion_desconocida_usa_mensaje_generico():
    mensaje = tz_web_state.translate_error(RuntimeError("detalle interno que no debe filtrarse"))
    assert "detalle interno" not in mensaje
    assert "inesperado" in mensaje


def test_create_get_touch_discard_session():
    session = tz_web_state.create_session()
    assert tz_web_state.get_session(session.id) is session

    before = session.updated_at
    time.sleep(0.01)
    tz_web_state.touch(session)
    assert session.updated_at > before

    tz_web_state.discard_session(session.id)
    assert tz_web_state.get_session(session.id) is None


def test_discard_session_borra_carpeta_de_subida(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    session = tz_web_state.create_session()
    upload_dir = os.path.join(str(tmp_path), session.id)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, "archivo.xlsx"), "w") as fh:
        fh.write("contenido")
    session.upload_dir = upload_dir

    tz_web_state.discard_session(session.id)
    assert not os.path.isdir(upload_dir)


def test_discard_session_nunca_borra_fuera_de_upload_root(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    carpeta_ajena = tmp_path / "no_tocar"
    carpeta_ajena.mkdir()
    (carpeta_ajena / "importante.txt").write_text("no borrar")

    session = tz_web_state.create_session()
    session.upload_dir = str(carpeta_ajena)
    tz_web_state.discard_session(session.id)

    assert carpeta_ajena.is_dir()
    assert (carpeta_ajena / "importante.txt").exists()


def test_try_start_run_es_exclusivo_entre_sesiones():
    assert tz_web_state.try_start_run("sesion-a") is True
    assert tz_web_state.try_start_run("sesion-b") is False
    assert tz_web_state.is_any_run_active() is True

    tz_web_state.finish_run("sesion-a")
    assert tz_web_state.is_any_run_active() is False
    assert tz_web_state.try_start_run("sesion-b") is True
    tz_web_state.finish_run("sesion-b")


def test_ensure_writable_dir_crea_y_confirma_escritura(tmp_path):
    destino = tmp_path / "nueva" / "carpeta"
    resultado = tz_web_state.ensure_writable_dir(str(destino))
    assert os.path.isdir(resultado)
    assert os.listdir(resultado) == []  # el archivo de prueba se borró


def test_ensure_writable_dir_falla_si_la_ruta_es_un_archivo(tmp_path):
    archivo = tmp_path / "no_es_carpeta.txt"
    archivo.write_text("contenido")
    with pytest.raises(OSError):
        tz_web_state.ensure_writable_dir(str(archivo))


def test_cleanup_stale_uploads_borra_solo_lo_antiguo(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))

    viejo = tmp_path / "viejo"
    viejo.mkdir()
    (viejo / "a.xlsx").write_text("x")
    nuevo = tmp_path / "nuevo"
    nuevo.mkdir()
    (nuevo / "b.xlsx").write_text("x")

    antiguo_ts = time.time() - 999999
    os.utime(viejo, (antiguo_ts, antiguo_ts))

    tz_web_state.cleanup_stale_uploads(max_age_seconds=3600)

    assert not viejo.exists()
    assert nuevo.exists()
