"""Tests unitarios para tz_logging (MICROBLOQUE 7-B3 — logging técnico local).

Ninguna prueba de este archivo debe escribir en el LOCALAPPDATA real del
usuario: siempre se inyecta ``log_dir``/``localappdata`` apuntando a
``tmp_path``. El estado del logger raíz es global al proceso de pytest, así
que un fixture autouse lo resetea antes y después de cada prueba.
"""
from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

import tz_logging
from tz_version import VERSION


@pytest.fixture(autouse=True)
def _reset_tz_logging():
    tz_logging.reset_logging_for_tests()
    yield
    tz_logging.reset_logging_for_tests()


# ---------------------------------------------------------------------------
# get_log_directory — resolución de ruta (secciones 2/16).
# ---------------------------------------------------------------------------


def test_get_log_directory_usa_localappdata_inyectado(tmp_path):
    resultado = tz_logging.get_log_directory(localappdata=str(tmp_path))
    assert resultado == tmp_path / "TZ Analyzer" / "Logs"


def test_get_log_directory_sin_localappdata_cae_a_home_appdata_local(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(tz_logging.Path, "home", classmethod(lambda cls: tmp_path))
    resultado = tz_logging.get_log_directory()
    assert resultado == tmp_path / "AppData" / "Local" / "TZ Analyzer" / "Logs"


# ---------------------------------------------------------------------------
# configure_logging — carpeta, archivo, rotación, UTF-8 (secciones 2/3/17).
# ---------------------------------------------------------------------------


def test_configure_logging_crea_carpeta_tz_analyzer_logs(tmp_path):
    log_dir = tmp_path / "TZ Analyzer" / "Logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)
    assert log_dir.is_dir()


def test_configure_logging_crea_el_archivo_esperado(tmp_path):
    log_dir = tmp_path / "logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)
    logging.getLogger("tests.tz_logging").info("evento de prueba")
    assert (log_dir / tz_logging.LOG_FILE_NAME).is_file()


def test_configure_logging_usa_rotating_file_handler_con_limites_correctos(tmp_path):
    log_dir = tmp_path / "logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)

    handlers = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1
    handler = handlers[0]
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    assert handler.level == logging.INFO


def test_configure_logging_archivo_es_utf8(tmp_path):
    log_dir = tmp_path / "logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)
    logging.getLogger("tests.tz_logging").info("análisis de bitácora: canción, ñoño")

    contenido = (log_dir / tz_logging.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "canción, ñoño" in contenido


def test_configure_logging_registra_version_canonica(tmp_path):
    log_dir = tmp_path / "logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)
    logging.getLogger("tz_launcher").info("TZ Analyzer %s iniciado", VERSION)

    contenido = (log_dir / tz_logging.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert f"TZ Analyzer {VERSION} iniciado" in contenido


# ---------------------------------------------------------------------------
# Idempotencia (secciones 7/17.8/17.14).
# ---------------------------------------------------------------------------


def test_configure_logging_es_idempotente_no_duplica_handlers(tmp_path):
    log_dir_1 = tmp_path / "primero"
    log_dir_2 = tmp_path / "segundo"

    tz_logging.configure_logging(log_dir=log_dir_1, console=False)
    handlers_tras_primera_llamada = list(logging.getLogger().handlers)

    tz_logging.configure_logging(log_dir=log_dir_2, console=False)

    assert logging.getLogger().handlers == handlers_tras_primera_llamada
    assert not log_dir_2.exists()

    logging.getLogger("tests.tz_logging").info("mensaje unico")
    contenido = (log_dir_1 / tz_logging.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert contenido.count("mensaje unico") == 1


def test_reset_logging_for_tests_permite_reconfigurar(tmp_path):
    log_dir_1 = tmp_path / "primero"
    log_dir_2 = tmp_path / "segundo"

    tz_logging.configure_logging(log_dir=log_dir_1, console=False)
    tz_logging.reset_logging_for_tests()
    tz_logging.configure_logging(log_dir=log_dir_2, console=False)

    assert log_dir_2.is_dir()
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1
    assert Path(handlers[0].baseFilename).parent == log_dir_2


def test_reset_logging_for_tests_restaura_nivel_del_root_y_permite_una_sola_reconfiguracion(tmp_path):
    root = logging.getLogger()
    nivel_inicial = root.level

    tz_logging.configure_logging(log_dir=tmp_path / "primero", console=False, level=logging.DEBUG)
    assert root.level == logging.DEBUG

    tz_logging.reset_logging_for_tests()
    assert root.level == nivel_inicial
    assert not any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    tz_logging.configure_logging(log_dir=tmp_path / "segundo", console=False, level=logging.DEBUG)
    handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1
    assert Path(handlers[0].baseFilename).parent == tmp_path / "segundo"


# ---------------------------------------------------------------------------
# Concurrencia (MB7-B3B) — exclusión mutua en configure_logging().
# ---------------------------------------------------------------------------


def test_configure_logging_es_seguro_ante_llamadas_concurrentes(tmp_path):
    n_threads = 20
    log_dir = tmp_path / "logs"
    barrier = threading.Barrier(n_threads)
    marker = "TZ_CONCURRENCY_PROBE_UNIQUE"

    def worker():
        barrier.wait()
        tz_logging.configure_logging(log_dir=log_dir, console=True)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not any(t.is_alive() for t in threads), "un thread quedo bloqueado esperando el lock"

    root = logging.getLogger()
    # Solo handlers gestionados por tz_logging: pytest agrega sus propios
    # StreamHandler (captura de logs en vivo) al root, que no deben contarse
    # como duplicados de configure_logging().
    managed = [h for h in root.handlers if getattr(h, tz_logging._MANAGED_ATTR, False)]
    file_handlers = [h for h in managed if isinstance(h, RotatingFileHandler)]
    # RotatingFileHandler hereda de StreamHandler: los handlers de consola son
    # StreamHandler que NO son tambien FileHandler, para no contar dos veces
    # el mismo handler bajo dos clasificaciones distintas.
    console_handlers = [
        h for h in managed
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert len(file_handlers) == 1
    assert len(console_handlers) == 1

    logging.getLogger("tests.tz_logging.concurrencia").info(marker)
    for handler in file_handlers + console_handlers:
        handler.flush()

    contenido = (log_dir / tz_logging.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert contenido.count(marker) == 1


# ---------------------------------------------------------------------------
# Falla del propio logging — nunca debe impedir el arranque (sección 15).
# ---------------------------------------------------------------------------


def test_fallo_al_crear_directorio_de_logs_no_rompe_la_app(monkeypatch, tmp_path):
    def _boom(self, *args, **kwargs):
        raise OSError("disco de solo lectura (simulado)")

    monkeypatch.setattr(tz_logging.Path, "mkdir", _boom)

    logger = tz_logging.configure_logging(log_dir=tmp_path / "logs", console=False)

    assert isinstance(logger, logging.Logger)
    assert not any(
        isinstance(h, RotatingFileHandler) for h in logging.getLogger().handlers
    )
    # No debe lanzar tampoco al intentar loguear después del fallo.
    logging.getLogger("tests.tz_logging").info("no debe romper nada")


# ---------------------------------------------------------------------------
# logger.exception conserva tipo y traceback (sección 10).
# ---------------------------------------------------------------------------


def test_logger_exception_registra_tipo_y_traceback(tmp_path):
    log_dir = tmp_path / "logs"
    tz_logging.configure_logging(log_dir=log_dir, console=False)
    logger = logging.getLogger("tests.tz_logging")

    try:
        raise ValueError("fallo tecnico de prueba")
    except ValueError:
        logger.exception("contexto de prueba")

    contenido = (log_dir / tz_logging.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "ValueError" in contenido
    assert "fallo tecnico de prueba" in contenido
    assert "Traceback (most recent call last)" in contenido


# ---------------------------------------------------------------------------
# sanitize_log_text — redacción de rutas (sección 11).
# ---------------------------------------------------------------------------


def test_sanitize_log_text_redacta_ruta_windows_entre_comillas():
    texto = (
        "FileNotFoundError: [Errno 2] No such file or directory: "
        "'C:\\\\CASOS\\\\123\\\\BITACORA_PERSONA.xlsx'"
    )
    resultado = tz_logging.sanitize_log_text(texto)
    assert "BITACORA_PERSONA" not in resultado
    assert "<ruta_redactada>" in resultado
    assert "FileNotFoundError" in resultado


def test_sanitize_log_text_redacta_ruta_unc():
    texto = r"error leyendo \\SERVIDOR\Casos\BITACORA.xlsx"
    resultado = tz_logging.sanitize_log_text(texto)
    assert "BITACORA" not in resultado
    assert "<ruta_redactada>" in resultado


def test_sanitize_log_text_deja_texto_sin_rutas_intacto():
    texto = "Procesamiento de caso finalizado (resultado=success)"
    assert tz_logging.sanitize_log_text(texto) == texto


def test_sanitize_log_text_texto_vacio():
    assert tz_logging.sanitize_log_text("") == ""
