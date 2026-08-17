"""tz_web.server — envoltorio del servidor WSGI de producción (MB5).

Resuelve AUD-03 (servidor de producción / launcher): Waitress en vez del
servidor de desarrollo de Werkzeug, atado exclusivamente a 127.0.0.1, sin
reloader ni modo debug, con una forma explícita de saber cuándo ya está
escuchando de verdad (para no abrir el navegador antes de tiempo) y de
detenerlo desde otro hilo (para que ``tz_web.lifecycle`` pueda cerrarlo sin
conocer los detalles de Waitress).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from flask import Flask
from waitress import create_server, wasyncore

from tz_web import instance

_LOGGER = logging.getLogger("tz_web.server")

DEFAULT_READY_ATTEMPTS = 50
DEFAULT_READY_DELAY_SECONDS = 0.1

# Plazo para que el pool de hilos de tareas de Waitress termine de despachar
# lo que ya tenía en curso al pedirse el cierre (ver ManagedServer.stop()).
# Mismo valor por defecto que trae ThreadedTaskDispatcher.shutdown() en la
# propia librería (waitress/task.py) — no es un número inventado aquí, solo
# se hace explícito para no depender del default implícito de un tercero.
_TASK_DRAIN_TIMEOUT_SECONDS = 5.0


class ServerStartError(RuntimeError):
    """El servidor WSGI no pudo iniciar (p. ej. puerto/host inválido)."""


class ManagedServer:
    """Arranca Waitress en un hilo propio y expone start/ready/stop.

    No decide *cuándo* detenerse (eso es responsabilidad de
    ``tz_web.lifecycle``, vía ``lifecycle.set_shutdown_hook(managed.stop)``)
    — solo sabe cómo hacerlo de forma limpia una vez que se lo piden.
    """

    def __init__(self, app: Flask, host: str, port: int = 0):
        self._app = app
        self._host = host
        self._port = port
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._stop_lock = threading.Lock()
        self._stopped = False
        # Mapa de sockets propio (``waitress.create_server(map=...)`` es un
        # parámetro público, no un detalle interno) en vez de confiar en el
        # atributo ``_server._map``: lo necesitamos en ``_close_all_sockets``
        # para cerrar también los canales ya aceptados que
        # ``BaseWSGIServer.close()`` deja abiertos (ver esa función).
        self._map: dict = {}

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("El servidor todavía no se inició.")
        # waitress expone effective_port como resultado de
        # socket.getnameinfo(..., NI_NUMERICSERV), que siempre es str.
        return int(self._server.effective_port)

    def start(self) -> None:
        """Crea y enlaza el socket (sección E: debug=False, reloader=False —
        Waitress no tiene ninguno de los dos) y arranca el bucle de
        aceptación en un hilo daemon. Al regresar, el socket ya está
        enlazado y escuchando: ``self.port`` es válido de inmediato: la
        confirmación de que la *aplicación* ya responde de verdad la da
        ``wait_until_ready``, no este método.
        """
        try:
            self._server = create_server(
                self._app, map=self._map, host=self._host, port=self._port, threads=4
            )
        except OSError as exc:
            raise ServerStartError(str(exc)) from exc

        self._app.config["TZ_INSTANCE_PORT"] = int(self._server.effective_port)
        # Fuente de verdad única del origen esperado (MB7-B5-B, ver
        # ``tz_web.origin_guard``): calculado aquí, en el mismo momento
        # lógico en que queda fijado TZ_INSTANCE_PORT — nunca reconstruido
        # por request a partir de ``request.host``/``Origin`` recibido.
        self._app.config["TZ_INSTANCE_ORIGIN"] = (
            f"http://{self._host}:{self._app.config['TZ_INSTANCE_PORT']}"
        )
        self._thread = threading.Thread(
            target=self._server.run, daemon=True, name="tz-waitress"
        )
        self._thread.start()

    def wait_until_ready(
        self,
        token: str,
        attempts: int = DEFAULT_READY_ATTEMPTS,
        delay: float = DEFAULT_READY_DELAY_SECONDS,
    ) -> bool:
        """Confirma, con el mismo health autenticado que valida una segunda
        instancia, que el servidor ya despacha pedidos reales — no solo que
        el socket está enlazado. Solo después de esto es seguro abrir el
        navegador (sección F)."""
        for _ in range(attempts):
            if instance.check_health(self.port, token) is not None:
                return True
            time.sleep(delay)
        return False

    def stop(self) -> None:
        """Detiene el bucle de aceptación (deja de aceptar conexiones
        nuevas; las conexiones en curso —incluida la que disparó este mismo
        cierre— terminan de despacharse).

        Seguro de llamar desde cualquier hilo — y más de una vez, p. ej.
        una vez desde el hook de apagado y otra desde la limpieza de quien
        levantó el servidor — pero con dos precauciones, ambas
        confirmadas necesarias durante el diagnóstico de este microbloque
        del `WinError 10038` en Windows (ver docs/LAUNCHER_LIFECYCLE.md
        para el análisis completo, y ``_drain_and_close`` más abajo):

        1. No cierra el socket directamente desde aquí: en Windows, cerrar
           un socket que el hilo de ``server.run()`` tiene en ese instante
           dentro de un ``select()`` es una carrera de Winsock. En vez de
           eso se usa ``trigger.pull_trigger()`` — el mecanismo que el
           propio Waitress expone para encolar un callback que se ejecuta
           *dentro* del hilo del bucle de aceptación, despertando su
           ``select()`` de forma segura.
        2. No lo hace de inmediato ni desde este hilo: primero drena el
           pool de hilos de tareas de Waitress (``_drain_and_close``, en un
           hilo propio) para garantizar que ningún hilo worker siga vivo
           para "jalar" ese mismo trigger al mismo tiempo que lo cerramos
           — la causa real de la carrera, no una casualidad de temporización
           (ver ``_drain_and_close``).
        """
        if self._server is None:
            return
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
        drain_thread = threading.Thread(
            target=self._drain_and_close, daemon=True, name="tz-waitress-shutdown"
        )
        drain_thread.start()

    def _drain_and_close(self) -> None:
        """Ejecuta, en su propio hilo (nunca en un hilo worker de Waitress
        ni en el hilo del bucle de aceptación), la secuencia que evita la
        carrera de cierre diagnosticada en este microbloque.

        Causa raíz confirmada leyendo el código real de Waitress 3.0.2
        (``waitress/channel.py``/``waitress/trigger.py``/``waitress/task.py``
        de la instalación en ``.venv312``), no asumida: cada hilo worker del
        pool de tareas (``ThreadedTaskDispatcher``) llama
        ``server.pull_trigger()`` sin ninguna sincronización propia — al
        terminar de despachar una petición (``HTTPChannel.service()``) y al
        escribir la respuesta si se supera el umbral de buffer
        (``HTTPChannel.write_soon``/``_flush_outbufs_below_high_watermark``).
        ``trigger.pull_trigger()`` internamente hace ``self.trigger.send(...)``
        sobre el socket interno del trigger, sin lock. Nuestro cierre
        (``server.trigger.close()``, disparado vía ``pull_trigger(thunk=
        self._close_all_sockets)`` para que corra en el hilo del bucle de
        aceptación, nunca aquí) cierra ese mismo socket. Si un hilo worker
        todavía vivo
        —p. ej. sirviendo un heartbeat o un recurso estático concurrente—
        alcanza su propio ``pull_trigger()`` mientras el trigger ya se cerró
        (o se está cerrando), ``send()`` sobre un socket cerrado produce
        exactamente ``OSError: [WinError 10038]`` en Windows. Es una carrera
        real dentro de Waitress (``trigger.py`` no protege ``close()`` contra
        ``pull_trigger()`` concurrente de otro hilo) — no un uso incorrecto
        nuestro de la API, no un doble cierre nuestro (``_stop_lock``/
        ``_stopped`` ya impiden eso arriba) y sí evitable desde nuestro lado
        sin parchear Waitress: basta con no dejar ningún hilo worker vivo
        antes de cerrar el trigger.

        ``ThreadedTaskDispatcher.shutdown()`` es el método público que la
        propia Waitress usa para eso — lo llama ``MultiSocketServer.close()``
        internamente — pero ``BaseWSGIServer.close()`` (la ruta que toma
        nuestro caso de un único socket) no lo invoca. Llamarlo aquí, antes
        del trigger, no es un parche a Waitress: es completar, desde nuestro
        lado, la secuencia de apagado con la misma API pública que la
        librería ya expone y usa para su otra ruta de cierre.
        ``shutdown()`` bloquea hasta que cada hilo activo termine su tarea
        en curso (nunca cancela una petición a medias) o hasta
        ``_TASK_DRAIN_TIMEOUT_SECONDS``; solo entonces es seguro pedir el
        cierre real. Por eso esto debe correr en un hilo dedicado: si
        corriera en el propio hilo worker que atendió ``/internal/shutdown``,
        ``shutdown()`` esperaría a que ese mismo hilo termine su tarea
        actual — la que lo está llamando — y se autobloquearía hasta agotar
        el timeout en cada cierre.

        Efecto secundario observado del propio ``shutdown()`` (no es un bug
        nuestro): con ``cancel_pending=True`` (su valor por defecto) cancela
        las tareas que ya estaban en cola pero nunca llegaron a arrancar —
        p. ej. un heartbeat/estático que un hilo worker recién había
        aceptado. Cancelar la *tarea* no cierra el *canal* que la esperaba:
        ese canal queda con una petición pendiente que nadie va a servir,
        conectado para siempre. Confirmado con diagnóstico dirigido (varios
        canales así sobreviven en ``self._map`` tras cerrar, y
        ``wasyncore.loop()`` — el bucle del hilo de aceptación, condicionado
        a ``while map: ...`` en ``waitress/wasyncore.py`` — nunca termina
        mientras el mapa no quede vacío, por más que el socket de escucha
        y el trigger ya se hayan cerrado). Por eso ``_close_all_sockets``
        (no ``server.close`` a secas) es el thunk que se programa abajo.
        """
        if self._server is None:
            return
        try:
            self._server.task_dispatcher.shutdown(timeout=_TASK_DRAIN_TIMEOUT_SECONDS)
        except Exception:
            _LOGGER.exception(
                "fallo al drenar el pool de tareas de Waitress antes de cerrar"
            )
        self._pull_close_trigger()

    def _close_all_sockets(self) -> None:
        """Cierra listening socket, trigger y cualquier canal ya aceptado
        que haya quedado en ``self._map`` (ver el comentario sobre tareas
        canceladas en ``_drain_and_close``).

        Es exactamente lo que hace ``waitress.server.MultiSocketServer.
        close()`` internamente (``self.task_dispatcher.shutdown(); wasyncore.
        close_all(self.map)``) — la ruta de cierre completo que sí existe en
        Waitress, pero que ``BaseWSGIServer.close()`` (la clase real que usa
        nuestro caso de un único socket, devuelta por ``create_server()``)
        no ofrece por sí sola. No es un parche a Waitress: es la misma
        función pública (``waitress.wasyncore.close_all``) que la librería
        ya usa para esto, aplicada aquí a nuestro propio ``self._map``
        (pasado nosotros mismos a ``create_server(map=self._map, ...)`` en
        ``start()``) en vez de al que Waitress guarda internamente.
        ``ignore_all=True`` porque, a esta altura, cualquier error al cerrar
        un canal individual (p. ej. el par ya se desconectó) no debe impedir
        cerrar el resto.
        """
        if self._server is None:
            return
        wasyncore.close_all(self._map, ignore_all=True)

    def _pull_close_trigger(self) -> None:
        if self._server is not None:
            self._server.trigger.pull_trigger(self._close_all_sockets)

    def is_running(self) -> bool:
        """``True`` mientras el hilo del bucle de aceptación siga vivo."""
        return self._thread is not None and self._thread.is_alive()

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> None:
        """Bloquea hasta que el bucle de ``server.run()`` termine (es decir,
        hasta que ``stop()`` haya drenado todas las conexiones)."""
        if self._thread is not None:
            self._thread.join(timeout)
