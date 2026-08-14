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
  quedan protegidos por el token de instancia inyectado aquí.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from flask import Flask

from tz_version import VERSION as APP_VERSION
from tz_web import instance, state
from tz_web.internal_routes import bp as tz_web_internal_blueprint
from tz_web.routes import bp as tz_web_blueprint

HOST = "127.0.0.1"


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
    app.config["MAX_CONTENT_LENGTH"] = state.MAX_UPLOAD_BYTES

    app.config["TZ_INSTANCE_TOKEN"] = instance_token
    app.config["TZ_INSTANCE_ID"] = instance_id
    app.config["TZ_INSTANCE_PID"] = os.getpid()
    app.config["TZ_INSTANCE_PORT"] = None
    app.config["TZ_APP_VERSION"] = APP_VERSION
    app.config["TZ_LAUNCHER_VERSION"] = instance.LAUNCHER_VERSION
    app.config["TZ_INSTANCE_STARTED_AT"] = time.time()

    app.register_blueprint(tz_web_blueprint)
    app.register_blueprint(tz_web_internal_blueprint)

    @app.context_processor
    def _inject_instance_token() -> dict:
        # Único canal por el que el token llega a la interfaz (sección L:
        # nunca en la URL). Cadena vacía si no hay token configurado — la
        # UI simplemente no manda heartbeat ni ofrece "Cerrar TZ Analyzer".
        return {
            "tz_instance_token": app.config.get("TZ_INSTANCE_TOKEN") or "",
            "tz_app_version": app.config.get("TZ_APP_VERSION") or "",
        }

    state.cleanup_stale_uploads()

    return app
