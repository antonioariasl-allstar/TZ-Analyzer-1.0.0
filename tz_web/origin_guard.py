"""tz_web.origin_guard — validación de Origin y Sec-Fetch-Site (MICROBLOQUE 7-B5-B).

Defensa en profundidad complementaria al Host guard (MB7-B5-A1, ver
``tz_web.app._guard_host``) y al CSRF guard (MB7-B5-A2, ver
``tz_web.routes._guard_csrf``): un Host correcto solo prueba que el
navegador fue dirigido al socket correcto, y CSRF exige un secreto que ya
vive en el HTML servido — ninguno de los dos, por sí solo, impide que un
navegador con una pestaña abierta en un sitio externo dispare una request
hacia esta instancia arrastrando la cookie de sesión. ``Origin`` y
``Sec-Fetch-Site`` son cabeceras que pone el navegador — nunca la página
que dispara la request — y por eso sirven como defensa adicional aquí.

Aplicado uniformemente por ``tz_web.routes`` (todos los POST del
blueprint principal) y ``tz_web.internal_routes`` (``GET /internal/health``,
``POST /internal/heartbeat``, ``POST /internal/shutdown``) — ver el
``before_request`` de cada blueprint, ambos registrados para correr antes
que su guard específico (CSRF / ``X-TZ-Token`` respectivamente). El guard
de Host global (``tz_web.app._guard_host``) ya corrió antes que cualquiera
de los dos, porque Flask ejecuta los ``before_request`` de aplicación
antes que los de blueprint.

Fuente de verdad del origen esperado: ``app.config["TZ_INSTANCE_ORIGIN"]``,
calculada una única vez por ``tz_web.server.ManagedServer.start()`` en el
mismo momento en que fija ``TZ_INSTANCE_PORT`` — nunca reconstruida aquí a
partir de la propia request (``request.host``, el ``Origin`` recibido, el
``Referer``, etc.).
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Response, current_app, request

_LOGGER = logging.getLogger("tz_web.origin_guard")

# Mensajes deliberadamente genéricos e idénticos a los de los otros guards
# (Host/CSRF): no deben revelar el Origin recibido, el esperado, el
# Sec-Fetch-Site recibido ni ningún otro estado interno — ni tampoco dar
# pistas de qué capa exactamente rechazó la request.
_NOT_READY_BODY = "Servicio no disponible."
_REJECTED_BODY = "Solicitud no permitida."

# Valores de Sec-Fetch-Site que esta política deja pasar. "cross-site" es el
# valor estándar que la especificación de Fetch Metadata reserva para un
# navegante externo y se rechaza explícitamente; cualquier otro valor no
# reconocido (fuera de estos tres más "cross-site") se trata también como
# rechazo — conservador por diseño, sin introducir un parser adicional.
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "same-site", "none"})


def guard_request() -> Optional[Response]:
    """Valida Origin (si está presente) y Sec-Fetch-Site (si está presente)
    contra la política de esta instancia.

    Devuelve una ``Response`` de rechazo (503 fail-closed si el origen de
    instancia aún no está configurado; 403 si Origin o Sec-Fetch-Site no
    son válidos) o ``None`` si la request puede continuar hacia el
    siguiente guard (CSRF / X-TZ-Token, según el blueprint).
    """
    expected_origin = current_app.config.get("TZ_INSTANCE_ORIGIN")
    if not expected_origin:
        _LOGGER.warning("request rechazada: origen de instancia aún no configurado")
        return Response(_NOT_READY_BODY, status=503, mimetype="text/plain")

    origin = request.headers.get("Origin")
    if origin is not None and origin != expected_origin:
        _LOGGER.warning("request rechazada por Origin no permitido")
        return Response(_REJECTED_BODY, status=403, mimetype="text/plain")

    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None and fetch_site not in _ALLOWED_FETCH_SITES:
        _LOGGER.warning("request rechazada por contexto cross-site")
        return Response(_REJECTED_BODY, status=403, mimetype="text/plain")

    return None
