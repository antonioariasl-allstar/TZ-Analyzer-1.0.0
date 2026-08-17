"""tz_web.app — fábrica de la aplicación Flask de TZ Analyzer (Fase 2 Web).

Entrypoint de ejecución real: ``tz_launcher.py`` en la raíz del repo (ver
docs/LAUNCHER_LIFECYCLE.md) — este módulo solo construye la aplicación
Flask; no decide instancia única, no levanta el servidor WSGI y no abre el
navegador (eso vive en ``tz_web.instance``, ``tz_web.server`` y
``tz_launcher`` respectivamente, MICROBLOQUE 5).

Requisitos que sí sigue cumpliendo esta fábrica (sección 7 del encargo
original, ahora sección E/L del MICROBLOQUE 5):
- pensada para escuchar exclusivamente en 127.0.0.1 (lo decide quien la
  sirve — ``tz_web.server.ManagedServer`` — no esta fábrica);
- sin reloader, sin modo debug (no aplica: no usa el servidor de Werkzeug);
- ``/internal/health``, ``/internal/heartbeat`` y ``/internal/shutdown``
  quedan protegidos por el token de instancia inyectado aquí;
- toda la app (blueprint principal e ``/internal/*`` por igual) exige que
  el ``Host`` de la request coincida exactamente con ``127.0.0.1:<puerto
  real>`` (MICROBLOQUE 7-B5-A1, defensa contra DNS rebinding — ver
  ``_guard_host`` más abajo);
- todos los POST del blueprint principal exigen un token CSRF propio,
  independiente de ``TZ_INSTANCE_TOKEN`` (MICROBLOQUE 7-B5-A2 — el guard
  vive en ``tz_web.routes``, no aquí: ver ``tz_web.routes._guard_csrf``);
- esos mismos POST, más ``/internal/heartbeat``, ``/internal/shutdown`` y
  ``GET /internal/health``, exigen además que ``Origin`` (si está
  presente) coincida exactamente con esta instancia y que
  ``Sec-Fetch-Site`` no indique un contexto cross-site (MICROBLOQUE 7-B5-B
  — el guard vive en ``tz_web.origin_guard``, invocado desde el
  ``before_request`` de cada blueprint).
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

from flask import Flask, Response, request

from tz_version import VERSION as APP_VERSION
from tz_web import instance, state
from tz_web.internal_routes import bp as tz_web_internal_blueprint
from tz_web.routes import bp as tz_web_blueprint

_LOGGER = logging.getLogger("tz_web.app")

HOST = "127.0.0.1"

# Mensajes deliberadamente genéricos (sección 14 del encargo MB7-B5-A1): no
# deben revelar el Host recibido, el Host/puerto esperado ni ningún otro
# estado interno — ver ``_guard_host`` más abajo.
_HOST_NOT_READY_BODY = "Servicio no disponible."
_HOST_REJECTED_BODY = "Solicitud no permitida."


def create_app(
    *,
    instance_token: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> Flask:
    """Crea y configura la aplicación Flask (sin arrancar el servidor).

    ``instance_token``/``instance_id`` los provee ``tz_launcher.py`` al
    arrancar de verdad; sin ellos (uso normal en pruebas), los endpoints
    ``/internal/*`` quedan protegidos igual — rechazan todo pedido, porque
    ``instance_token`` ausente nunca valida (ver ``tz_web.internal_routes``).
    """
    app = Flask(__name__)
    # SECRET_KEY local por ejecución: solo firma la cookie de sesión que
    # guarda el identificador de caso (sección 5/6) — no se persiste entre
    # arranques, no hay nada sensible que proteja más allá de eso.
    app.config["SECRET_KEY"] = os.urandom(32)

    app.config["TZ_INSTANCE_TOKEN"] = instance_token
    app.config["TZ_INSTANCE_ID"] = instance_id
    # Mismo valor, expuesto también fuera de app.config: el staging
    # transaccional (tz_web.output_transaction) corre en threads de trabajo
    # propios, sin app context, y no puede leer current_app.
    instance.set_current_instance_id(instance_id)
    app.config["TZ_INSTANCE_PID"] = os.getpid()
    app.config["TZ_INSTANCE_PORT"] = None
    # Fuente de verdad del Origin esperado (MB7-B5-B, ver
    # ``tz_web.origin_guard``): ``None`` hasta que ``ManagedServer.start()``
    # la calcule junto con TZ_INSTANCE_PORT — el guard falla cerrado (503)
    # mientras tanto, igual que ya hace el guard de Host con el puerto.
    app.config["TZ_INSTANCE_ORIGIN"] = None

    # Cookie de sesión (MB7-B5-B, sección 13 del encargo): configuración
    # explícita, sin depender del comportamiento implícito del navegador.
    # HttpOnly: la cookie solo guarda ``case_id``, JS nunca necesita leerla.
    # Secure=False: la app sirve HTTP puro sobre 127.0.0.1; Secure=True
    # rompería el envío normal de la cookie. SameSite=Strict: todo el flujo
    # legítimo de TZ Analyzer es local/same-origin.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["TZ_APP_VERSION"] = APP_VERSION
    app.config["TZ_LAUNCHER_VERSION"] = instance.LAUNCHER_VERSION
    app.config["TZ_INSTANCE_STARTED_AT"] = time.time()
    # Secreto CSRF independiente de TZ_INSTANCE_TOKEN (sección 3 del encargo
    # MB7-B5-A2): este token queda deliberadamente expuesto en HTML legítimo
    # (hidden fields, meta tag) para proteger los POST del blueprint
    # principal — TZ_INSTANCE_TOKEN protege heartbeat/shutdown y nunca debe
    # aparecer ahí. Solo en memoria, vive lo que dure el proceso; no se
    # deriva de puerto/pid/instance_id/case_id/SECRET_KEY/TZ_INSTANCE_TOKEN.
    app.config["TZ_CSRF_TOKEN"] = secrets.token_urlsafe(32)

    app.register_blueprint(tz_web_blueprint)
    app.register_blueprint(tz_web_internal_blueprint)

    def _expected_host() -> Optional[str]:
        # Nunca construido a partir de la request (sección 3 del encargo
        # MB7-B5-A1): siempre HOST + el puerto real, que
        # ``tz_web.server.ManagedServer.start()`` ya escribe en
        # TZ_INSTANCE_PORT antes de que el hilo de Waitress empiece a
        # aceptar conexiones.
        port = app.config.get("TZ_INSTANCE_PORT")
        if port is None:
            return None
        return f"{HOST}:{port}"

    @app.before_request
    def _guard_host() -> Optional[Response]:
        """Defensa contra DNS rebinding (MB7-B5-A1): capa central que
        protege toda la app (blueprint principal e ``/internal/*`` por
        igual) — Flask ejecuta los ``before_request`` globales (esta
        función) antes que los de blueprint, así que esto corre siempre
        antes que el guard de ``X-TZ-Token`` de ``tz_web.internal_routes``.
        """
        expected = _expected_host()
        if expected is None:
            _LOGGER.warning("request rechazada: host de instancia aún no configurado")
            return Response(_HOST_NOT_READY_BODY, status=503, mimetype="text/plain")
        if request.host != expected:
            _LOGGER.warning("request rechazada por Host no permitido")
            return Response(_HOST_REJECTED_BODY, status=403, mimetype="text/plain")
        return None

    @app.context_processor
    def _inject_instance_token() -> dict:
        # Único canal por el que el token llega a la interfaz (sección L:
        # nunca en la URL). Cadena vacía si no hay token configurado — la
        # UI simplemente no manda heartbeat ni ofrece "Cerrar TZ Analyzer".
        return {
            "tz_instance_token": app.config.get("TZ_INSTANCE_TOKEN") or "",
            "tz_app_version": app.config.get("TZ_APP_VERSION") or "",
            # Solo expone el token ya creado (sección 12 del encargo
            # MB7-B5-A2) — nunca lo genera aquí. Fallback vacío para no
            # romper el render si faltara: el POST posterior falla cerrado
            # (503) en tz_web.routes._guard_csrf.
            "csrf_token": app.config.get("TZ_CSRF_TOKEN") or "",
        }

    state.cleanup_stale_uploads()

    return app
