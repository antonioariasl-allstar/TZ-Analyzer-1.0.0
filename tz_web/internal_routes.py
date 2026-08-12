"""tz_web.internal_routes — endpoints internos de ciclo de vida (MB5).

Tres rutas, todas bajo ``/internal`` y todas protegidas por el mismo guard:
- ``GET /internal/health``: valida una instancia (usado por un segundo
  lanzamiento para decidir "reuse" vs "blocked", ver ``tz_web.instance``).
  Nunca expone datos de caso — solo identidad de la instancia y su estado
  de ciclo de vida.
- ``POST /internal/heartbeat``: el navegador la llama periodicamente
  mientras la pagina esta abierta (ver ``tz_web/static/js/app.js``).
- ``POST /internal/shutdown``: boton "Cerrar TZ Analyzer" de la interfaz.

Seguridad local basica (sección L del encargo, sin abordar CSRF/Origin
todavia): exige IP de loopback *y* el token secreto de esta instancia via
cabecera ``X-TZ-Token`` — nunca en la URL (evita que quede en logs de
acceso o en el historial del navegador). Sin token configurado en la app
(``TZ_INSTANCE_TOKEN`` ausente), todo pedido se rechaza — no hay modo
"abierto" por omision.
"""

from __future__ import annotations

import hmac
import time
from typing import Optional

from flask import Blueprint, current_app, jsonify, request

from tz_web import lifecycle

bp = Blueprint("tz_web_internal", __name__, url_prefix="/internal")

_LOCAL_ADDRESSES = {"127.0.0.1", "::1"}


def _configured_token() -> Optional[str]:
    token = current_app.config.get("TZ_INSTANCE_TOKEN")
    return token or None


def _request_token_valid() -> bool:
    expected = _configured_token()
    if not expected:
        return False
    provided = request.headers.get("X-TZ-Token", "")
    return hmac.compare_digest(provided, expected)


def _is_local_request() -> bool:
    return request.remote_addr in _LOCAL_ADDRESSES


@bp.before_request
def _guard_internal_requests():
    if not _is_local_request() or not _request_token_valid():
        return jsonify({"error": "no_autorizado"}), 403
    return None


@bp.route("/health", methods=["GET"])
def health():
    started_at = current_app.config.get("TZ_INSTANCE_STARTED_AT") or time.time()
    return jsonify(
        {
            "instance_id": current_app.config.get("TZ_INSTANCE_ID"),
            "pid": current_app.config.get("TZ_INSTANCE_PID"),
            "port": current_app.config.get("TZ_INSTANCE_PORT"),
            "app_version": current_app.config.get("TZ_APP_VERSION"),
            "launcher_version": current_app.config.get("TZ_LAUNCHER_VERSION"),
            "lifecycle_state": lifecycle.get_state(),
            "uptime_seconds": round(time.time() - started_at, 1),
        }
    )


@bp.route("/heartbeat", methods=["POST"])
def heartbeat():
    lifecycle.record_heartbeat()
    return jsonify({"ok": True, "lifecycle_state": lifecycle.get_state()})


@bp.route("/shutdown", methods=["POST"])
def shutdown():
    resulting_state = lifecycle.request_shutdown(reason="user_requested")
    return jsonify({"ok": True, "lifecycle_state": resulting_state})
