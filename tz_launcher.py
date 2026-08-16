#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tz_launcher.py — LANZADOR de TZ Analyzer Web (MICROBLOQUE 5)

===============================================================
ESTADO: punto de entrada real de la aplicación web empaquetada.
===============================================================

Diferenciación con otros entrypoints del repo:
- ``run.py`` lanza el flujo CLI interactivo (``tz_core.app_runner.run``) —
  no toca este archivo ni tz_web.
- ``python -m tz_web.app`` ya NO levanta un servidor (ver su docstring):
  ``tz_web.app.create_app()`` es solo la fábrica de la aplicación Flask.
- Este archivo es el único que decide instancia única, levanta el servidor
  WSGI de producción (Waitress) y abre el navegador.

Responsabilidades (ver docs/LAUNCHER_LIFECYCLE.md para el diseño completo):
1. Adquirir el lock de instancia único por usuario (``tz_web.instance``).
   Si ya hay una instancia válida corriendo, abre el navegador apuntando a
   ella y termina sin levantar un segundo backend.
2. Si no hay ninguna, levantar Waitress en 127.0.0.1 con un puerto efímero
   asignado por el sistema operativo, escribir la metadata de instancia y
   abrir el navegador solo después de confirmar (health autenticado) que el
   servidor ya despacha pedidos reales.
3. Mantener vivo el ciclo de vida (``tz_web.lifecycle``): heartbeat del
   navegador, cierre explícito desde la interfaz, CLOSE_WHEN_IDLE mientras
   haya un análisis activo.
4. Al cerrar: nunca mientras un análisis siga activo (red de seguridad
   final antes de salir), liberar el lock y salir con código 0.

Uso: ``python tz_launcher.py`` (o el ejecutable empaquetado que lo invoque).
"""

from __future__ import annotations

import sys

import tz_logging
from tz_folder_dialog_ipc import (
    EXIT_ERROR,
    INTERNAL_MODE_ARGUMENT,
    cleanup_stale_dialog_ipc,
)


def _dispatch_internal_folder_dialog(argv: list[str]) -> int | None:
    """Despacha el hijo Tk antes de importar el backend normal."""
    if argv[1:2] != [INTERNAL_MODE_ARGUMENT]:
        return None
    if len(argv) != 3:
        return EXIT_ERROR

    from tz_folder_dialog_helper import run_internal_folder_dialog

    return run_internal_folder_dialog(argv[2])


if __name__ == "__main__":
    _internal_exit_code = _dispatch_internal_folder_dialog(sys.argv)
    if _internal_exit_code is not None:
        raise SystemExit(_internal_exit_code)


import logging
import os
import secrets
import time
import uuid
import webbrowser

from tz_web import instance, lifecycle, state
from tz_web.app import APP_VERSION, HOST, create_app
from tz_web.server import ManagedServer, ServerStartError
from tz_core.folder_dialog import shutdown_dialog_children

_LOGGER = logging.getLogger("tz_launcher")

_SHUTDOWN_WAIT_SAFETY_POLL_SECONDS = 0.5

# Espera acotada a que el hilo de Waitress confirme su propio cierre. Un
# hilo daemon sin estado de aplicación no debe poder colgar el proceso para
# siempre; ver el comentario junto a wait_for_shutdown() más abajo.
_WAITRESS_JOIN_TIMEOUT_SECONDS = 8.0


def _configure_logging() -> None:
    tz_logging.configure_logging()
    _LOGGER.info("TZ Analyzer %s iniciado", APP_VERSION)


def _open_browser(url: str) -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:
        _LOGGER.exception("no se pudo abrir el navegador (%s)", url)
        return False


def _run_existing_instance(metadata: instance.InstanceMetadata) -> int:
    url = f"http://{HOST}:{metadata.port}/"
    _LOGGER.info(
        "instancia existente reutilizada: instance_id=%s… pid=%s port=%s",
        metadata.instance_id[:8],
        metadata.pid,
        metadata.port,
    )
    if not _open_browser(url):
        print(f"[ERROR] TZ Analyzer ya está en ejecución en {url}, pero no se pudo abrir el navegador.")
        return 1
    return 0


def _run_blocked(reason: str) -> int:
    _LOGGER.error("arranque bloqueado (motivo=%s)", reason)
    print(
        "[ERROR] TZ Analyzer parece estar en ejecución, pero no respondió correctamente "
        f"(motivo interno: {reason}). Cierre cualquier proceso previo de TZ Analyzer e "
        "intente de nuevo. No se inició un nuevo servidor para evitar dos instancias a la vez."
    )
    return 1


def _generate_instance_token() -> str:
    """Token secreto de instancia (cabecera ``X-TZ-Token``, ver
    ``tz_web.internal_routes``): 32 bytes de ``os.urandom`` vía
    ``secrets.token_hex`` -> 64 caracteres hex, 256 bits de entropía real.

    Deliberadamente no ``uuid.uuid4()``: un UUID4 fija 6 bits (versión +
    variante, RFC 4122) por diseño, así que dos concatenados (lo que este
    módulo usaba antes) dan igual 64 caracteres hex pero solo 244 bits de
    entropía real, no 256 — y "generar un identificador único" no es la
    misma garantía que necesita un secreto de autenticación, aunque ambos
    usen ``os.urandom()`` por debajo. ``secrets`` es, además, el módulo que
    la propia documentación de Python señala para este uso exacto.
    """
    return secrets.token_hex(32)


def _run_new_instance(lock: instance.InstanceLock) -> int:
    managed = None
    server_started = False
    normal_shutdown = False
    controlled_failure = False
    try:
        # Solo la instancia nueva barre residuos IPC propios >24 h. El cleanup
        # es best-effort y no se ejecuta en create_app ni en el proceso Tk.
        try:
            cleanup_stale_dialog_ipc()
        except Exception:  # noqa: BLE001 - housekeeping nunca impide arrancar
            pass

        token = _generate_instance_token()
        # instance_id no es secreto, solo necesita ser distinto entre
        # instancias: uuid4 sigue siendo la herramienta correcta para eso.
        instance_id = uuid.uuid4().hex

        app = create_app(instance_token=token, instance_id=instance_id)
        managed = ManagedServer(app, host=HOST, port=0)

        try:
            managed.start()
        except ServerStartError as exc:
            controlled_failure = True
            _LOGGER.error("fallo al iniciar el servidor WSGI: %s", exc)
            print(f"[ERROR] No se pudo iniciar el servidor local: {exc}")
            return 1
        server_started = True

        metadata = instance.InstanceMetadata(
            schema_version=instance.INSTANCE_SCHEMA_VERSION,
            instance_id=instance_id,
            pid=os.getpid(),
            port=managed.port,
            token=token,
            created_at=time.time(),
            app_version=APP_VERSION,
            launcher_version=instance.LAUNCHER_VERSION,
        )
        lock.write_metadata(metadata)
        _LOGGER.info(
            "instancia iniciada: pid=%s port=%s instance_id=%s… app_version=%s",
            metadata.pid,
            metadata.port,
            metadata.instance_id[:8],
            metadata.app_version,
        )

        lifecycle.set_shutdown_hook(managed.stop)
        lifecycle.start_watchdog()

        url = f"http://{HOST}:{managed.port}/"
        if managed.wait_until_ready(token):
            if not _open_browser(url):
                _LOGGER.warning("el servidor está listo pero el navegador no pudo abrirse (%s)", url)
                print(f"[AVISO] TZ Analyzer sigue activo en {url}; ábralo manualmente si hace falta.")
            else:
                print(f"TZ Analyzer — servidor local en {url}")
        else:
            _LOGGER.warning("no se pudo confirmar que el servidor respondiera a tiempo; se intenta abrir igual")
            _open_browser(url)

        # El proceso debe permanecer vivo indefinidamente mientras no se
        # haya pedido ningún cierre real (RUNNING normal) NI mientras haya
        # un cierre diferido por un análisis todavía activo (CLOSE_WHEN_
        # IDLE: matar el proceso ahí mataría ese análisis, justo lo que la
        # sección M prohíbe). El timeout acotado de abajo NUNCA debe ser lo
        # que decide cuánto vive el proceso en operación normal — antes lo
        # era, por error: este bucle esperaba con timeout incondicionalmente
        # justo después de abrir el navegador, así que el launcher se
        # autoterminaba a los pocos segundos de arrancar sin que nadie
        # pidiera cerrar nada (bug encontrado en el smoke manual de este
        # microbloque). Solo una vez que lifecycle confirma SHUTTING_DOWN
        # (lo que implica que el hook de apagado, ``managed.stop``, ya se
        # ejecutó — ``lifecycle._do_shutdown_locked`` lo llama sin soltar su
        # lock antes) tiene sentido acotar la espera: a partir de ahí sí es
        # una carrera conocida de Windows en el trigger interno de Waitress
        # lo que se está esperando, no la vida normal del proceso.
        while managed.is_running() and lifecycle.get_state() != lifecycle.SHUTTING_DOWN:
            managed.wait_for_shutdown(timeout=_SHUTDOWN_WAIT_SAFETY_POLL_SECONDS)
        if lifecycle.get_state() != lifecycle.SHUTTING_DOWN:
            controlled_failure = True
            _LOGGER.error(
                "el servidor WSGI termino sin una solicitud de cierre de lifecycle"
            )
            return 1
        normal_shutdown = True
        return 0
    finally:
        body_exception_active = sys.exc_info()[0] is not None
        server_wait_error = None
        try:
            # El selector no forma parte del análisis. Su cleanup es
            # best-effort: un fallo aquí nunca puede saltarse la espera de la
            # corrida activa ni el resto de la liberación de recursos.
            try:
                shutdown_dialog_children()
            except Exception:  # noqa: BLE001 - frontera de cleanup final
                _LOGGER.exception("fallo al terminar hijos del selector de carpetas")

            # Red de seguridad final (sección M): nunca detener el servidor y
            # matar así un worker daemon mientras su análisis siga activo.
            while state.is_any_run_active():
                time.sleep(_SHUTDOWN_WAIT_SAFETY_POLL_SECONDS)
        finally:
            try:
                lifecycle.stop_watchdog()
            except Exception:  # noqa: BLE001 - no impedir otros cleanups
                _LOGGER.exception("fallo al detener el watchdog de lifecycle")

            if managed is not None:
                try:
                    managed.stop()
                except Exception:  # noqa: BLE001 - continuar hasta liberar lock
                    _LOGGER.exception("fallo al solicitar el cierre del servidor WSGI")
                try:
                    managed.wait_for_shutdown(timeout=_WAITRESS_JOIN_TIMEOUT_SECONDS)
                    if managed.is_running():
                        # Un hilo daemon sin estado propio no debe colgar el
                        # proceso indefinidamente tras el plazo de seguridad.
                        _LOGGER.warning(
                            "el hilo del servidor no confirmó su cierre en %ss; "
                            "se continúa de todas formas",
                            _WAITRESS_JOIN_TIMEOUT_SECONDS,
                        )
                except Exception as exc:  # noqa: BLE001 - liberar lock primero
                    _LOGGER.exception("fallo al esperar el cierre del servidor WSGI")
                    # Conserva la semantica previa: un fallo de la espera
                    # terminal se propaga si no hay ya una excepcion mas
                    # temprana (readiness/metadata/etc.) que deba preservarse.
                    if (
                        not body_exception_active
                        and server_started
                        and not controlled_failure
                    ):
                        server_wait_error = exc

            try:
                lock.release()
            except Exception:  # noqa: BLE001 - conservar la excepción original
                _LOGGER.exception("fallo al liberar el lock de instancia")

        if server_wait_error is not None:
            raise server_wait_error
        if normal_shutdown:
            _LOGGER.info(
                "apagado limpio completo (motivo=%s)",
                lifecycle.get_shutdown_reason(),
            )


def main() -> int:
    _configure_logging()

    run_dir = instance.get_run_dir()
    lock = instance.InstanceLock(run_dir)
    plan = instance.resolve_startup_plan(lock)

    if plan.action == "reuse":
        assert plan.metadata is not None
        return _run_existing_instance(plan.metadata)
    if plan.action == "blocked":
        return _run_blocked(plan.reason or "desconocido")
    return _run_new_instance(lock)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        # Red de seguridad final de logging (sección 10): un fallo no
        # controlado en main() debe quedar en el log técnico con su
        # traceback, incluso en un futuro build sin consola visible.
        _LOGGER.exception("fallo no controlado durante el arranque/ejecución")
        raise
