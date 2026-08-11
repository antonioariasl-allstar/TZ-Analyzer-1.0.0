"""tz_web.app — servidor Flask local de TZ Analyzer (Fase 2 Web).

Uso:

    python -m tz_web.app

Requisitos (sección 7 del encargo):
- escucha exclusivamente en 127.0.0.1 (nunca 0.0.0.0 ni IP de red);
- puerto configurable (variable de entorno ``TZ_WEB_PORT``), con un rango
  pequeño de puertos alternativos si el preferido está ocupado;
- abre el navegador automáticamente una sola vez;
- sin reloader, sin modo debug;
- cierre limpio con Ctrl+C.
"""

from __future__ import annotations

import os
import socket
import threading
import webbrowser

from flask import Flask

from tz_web import state
from tz_web.routes import bp as tz_web_blueprint

DEFAULT_PORT = 5175
PORT_SCAN_ATTEMPTS = 5
HOST = "127.0.0.1"


def create_app() -> Flask:
    """Crea y configura la aplicación Flask (sin arrancar el servidor)."""
    app = Flask(__name__)
    # SECRET_KEY local por ejecución: solo firma la cookie de sesión que
    # guarda el identificador de caso (sección 5/6) — no se persiste entre
    # arranques, no hay nada sensible que proteja más allá de eso.
    app.config["SECRET_KEY"] = os.urandom(32)
    app.config["MAX_CONTENT_LENGTH"] = state.MAX_UPLOAD_BYTES
    app.register_blueprint(tz_web_blueprint)

    state.cleanup_stale_uploads()

    return app


def _find_open_port(host: str, start_port: int, attempts: int) -> int:
    for offset in range(attempts):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(
        f"No se encontró un puerto libre entre {start_port} y "
        f"{start_port + attempts - 1} en {host}. Cierre alguna aplicación que "
        "esté usando esos puertos e intente de nuevo."
    )


def main() -> None:
    start_port = int(os.environ.get("TZ_WEB_PORT", DEFAULT_PORT))

    try:
        port = _find_open_port(HOST, start_port, PORT_SCAN_ATTEMPTS)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return

    app = create_app()

    def _open_browser() -> None:
        webbrowser.open(f"http://{HOST}:{port}/")

    threading.Timer(1.0, _open_browser).start()

    print(f"TZ Analyzer — servidor local en http://{HOST}:{port}/ (Ctrl+C para detener)")
    try:
        app.run(host=HOST, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[INFO] Servidor detenido por el usuario.")


if __name__ == "__main__":
    main()
