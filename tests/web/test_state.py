"""FASE 2 WEB — tz_web.state: contrato de progreso, sesiones y limpieza."""
from __future__ import annotations

import logging
import os
import threading
import time
from unittest.mock import patch

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
from tz_web.output_transaction import InputIntegrityError, OutputValidationError


def test_stage_percent_cubre_las_8_etapas_reales_de_process_case():
    from tz_web.services import _PROGRESS_STAGES

    # STAGE_PERCENT/STAGE_LABELS son compartidos por /status para todos los
    # modos (sección 10 del microbloque 2 de Modo 3): deben cubrir las 8
    # etapas de bitácora, más las propias de Modo 3 (ver
    # test_stage_percent_cubre_las_etapas_de_modo3), sin pisarse entre sí.
    assert set(_PROGRESS_STAGES) <= set(tz_web_state.STAGE_PERCENT.keys())
    assert tz_web_state.STAGE_PERCENT["finalizado"] == 100
    # Estrictamente creciente: nunca retrocede ni repite valor entre etapas.
    valores = [tz_web_state.STAGE_PERCENT[e] for e in _PROGRESS_STAGES]
    assert valores == sorted(valores)
    assert len(set(valores)) == len(valores)


def test_stage_percent_cubre_las_etapas_de_modo3():
    etapas_modo3 = ("preparando", "generando_cartografia", "generando_hashes", "finalizando", "completado")
    assert set(etapas_modo3) <= set(tz_web_state.STAGE_PERCENT.keys())
    assert set(etapas_modo3) <= set(tz_web_state.STAGE_LABELS.keys())
    assert tz_web_state.STAGE_PERCENT["completado"] == 100
    valores = [tz_web_state.STAGE_PERCENT[e] for e in etapas_modo3]
    assert valores == sorted(valores)
    assert len(set(valores)) == len(valores)
    # Las etapas de Modo 3 no colisionan con las 8 de bitácora.
    from tz_web.services import _PROGRESS_STAGES

    assert set(etapas_modo3).isdisjoint(set(_PROGRESS_STAGES))


@pytest.mark.parametrize("exc_type,mensaje", [
    (CaseFileNotFoundError, "archivo de prueba no encontrado"),
    (SheetNotFoundError, "hoja de prueba no encontrada"),
    (CaseLoadError, "no se pudo cargar"),
    (InvalidMappingError, "mapeo inválido de prueba"),
    (OutputDirectoryError, "carpeta de prueba inválida"),
    (AnalysisInProgressError, "ya en ejecución de prueba"),
    (ArchivoNoProcesableError, "no procesable de prueba"),
    (InputIntegrityError, "integridad de entrada no verificable"),
    (OutputValidationError, "producto obligatorio invalido"),
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


def test_terminal_run_no_abre_ventana_entre_estado_terminal_y_liberacion():
    session = tz_web_state.create_session()
    assert tz_web_state.try_start_run(session.id) is True
    terminal_visible = threading.Event()
    allow_finish = threading.Event()
    mutation_attempted = threading.Event()
    mutation_entered = threading.Event()
    observed = []

    def _finish():
        with tz_web_state.terminal_run(session.id):
            session.status = tz_web_state.STATUS_PARTIAL
            terminal_visible.set()
            assert allow_finish.wait(timeout=5)

    def _mutate():
        mutation_attempted.set()
        with tz_web_state.mutation_guard() as allowed:
            observed.append(allowed)
            mutation_entered.set()

    finisher = threading.Thread(target=_finish)
    mutation = threading.Thread(target=_mutate)
    finisher.start()
    assert terminal_visible.wait(timeout=5)
    mutation.start()
    assert mutation_attempted.wait(timeout=5)
    assert mutation_entered.wait(timeout=0.1) is False

    allow_finish.set()
    finisher.join(timeout=5)
    mutation.join(timeout=5)

    assert mutation_entered.is_set()
    assert observed == [True]
    assert tz_web_state.is_any_run_active() is False


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


@pytest.fixture(autouse=True)
def _sessions_isolation():
    """Aísla ``_SESSIONS`` (registro global por proceso) entre pruebas, igual
    que ``tests/web/test_lifecycle.py``: sin esto, sesiones creadas por una
    prueba de limpieza contaminarían el conteo/iteración de las siguientes."""
    with tz_web_state._SESSIONS_LOCK:
        tz_web_state._SESSIONS.clear()
    yield
    with tz_web_state._SESSIONS_LOCK:
        tz_web_state._SESSIONS.clear()


# ---------------------------------------------------------------------------
# cleanup_session_uploads_on_shutdown — limpieza normal de temporales al
# cierre (SALIR / heartbeat_timeout en reposo). La integración con
# tz_web.lifecycle (cuándo se invoca) se prueba en tests/web/test_lifecycle.py;
# aquí se prueba la función en sí, aislada.
# ---------------------------------------------------------------------------


def _sesion_con_upload(tmp_path, con_snapshot: bool = False) -> tz_web_state.Session:
    session = tz_web_state.create_session()
    upload_dir = os.path.join(str(tmp_path), session.id)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, "archivo.xlsx"), "w") as fh:
        fh.write("contenido")
    if con_snapshot:
        snap_dir = os.path.join(upload_dir, ".execution-snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        with open(os.path.join(snap_dir, ".execution-input-abc.xlsx"), "w") as fh:
            fh.write("snapshot")
    session.upload_dir = upload_dir
    return session


def test_cleanup_shutdown_borra_upload_y_snapshot_de_la_sesion(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    session = _sesion_con_upload(tmp_path, con_snapshot=True)

    tz_web_state.cleanup_session_uploads_on_shutdown()

    assert not os.path.isdir(session.upload_dir)


def test_cleanup_shutdown_es_idempotente(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    _sesion_con_upload(tmp_path)

    tz_web_state.cleanup_session_uploads_on_shutdown()
    # Segunda llamada: el directorio ya no existe, no debe fallar.
    tz_web_state.cleanup_session_uploads_on_shutdown()


def test_cleanup_shutdown_tolera_sesion_sin_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    tz_web_state.create_session()  # sin upload_dir (None)

    tz_web_state.cleanup_session_uploads_on_shutdown()  # no debe lanzar


def test_cleanup_shutdown_limpia_todas_las_sesiones_propias(tmp_path, monkeypatch):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    session_a = _sesion_con_upload(tmp_path)
    session_b = _sesion_con_upload(tmp_path)

    tz_web_state.cleanup_session_uploads_on_shutdown()

    assert not os.path.isdir(session_a.upload_dir)
    assert not os.path.isdir(session_b.upload_dir)


def test_cleanup_shutdown_no_toca_carpeta_de_instancia_ajena(tmp_path, monkeypatch):
    """Un directorio dentro de UPLOAD_ROOT que esta sesión (este proceso) no
    creó — p. ej. de otra instancia — nunca aparece en ``_SESSIONS``, así que
    la limpieza no debe tocarlo."""
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    ajena = tmp_path / "caso-de-otra-instancia"
    ajena.mkdir()
    (ajena / "archivo.xlsx").write_text("no tocar")

    session = _sesion_con_upload(tmp_path)

    tz_web_state.cleanup_session_uploads_on_shutdown()

    assert not os.path.isdir(session.upload_dir)
    assert ajena.is_dir()
    assert (ajena / "archivo.xlsx").exists()


def test_cleanup_shutdown_no_toca_productos_finales_fuera_de_upload_root(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(upload_root))
    salida = tmp_path / "salida_usuario"
    salida.mkdir()
    (salida / "reporte.html").write_text("<html></html>")

    session = _sesion_con_upload(upload_root)

    tz_web_state.cleanup_session_uploads_on_shutdown()

    assert not os.path.isdir(session.upload_dir)
    assert (salida / "reporte.html").exists()


def test_cleanup_shutdown_permissionerror_loguea_warning_generico_y_continua(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path))
    session_a = _sesion_con_upload(tmp_path)
    session_b = _sesion_con_upload(tmp_path)

    with patch.object(tz_web_state.shutil, "rmtree", side_effect=PermissionError("bloqueado")):
        with caplog.at_level(logging.WARNING, logger="tz_web.state"):
            tz_web_state.cleanup_session_uploads_on_shutdown()  # no debe lanzar

    warnings = [r for r in caplog.records if r.name == "tz_web.state"]
    assert len(warnings) == 2  # una por sesión afectada, cierre continuó con ambas
    for record in warnings:
        message = record.getMessage()
        assert session_a.upload_dir not in message
        assert session_b.upload_dir not in message
        assert session_a.id not in message
        assert session_b.id not in message


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
