"""Utilidades generales relacionadas con el entorno de ejecucion."""

from __future__ import annotations

import getpass
import platform
import sys
import time
from datetime import datetime
from typing import Any, Dict

from tz_version import VERSION as TZ_VERSION


def collect_env_snapshot(config: Dict[str, Any] | None = None) -> Dict[str, str]:
    """Devuelve metadatos basicos del entorno para trazabilidad de reportes.

    Args:
        config: Diccionario opcional de configuración global para enriquecer datos.

    Returns:
        Dict con datos como SO, version de Python, zona horaria y versiones declaradas.
    """

    cfg = config or {}

    try:
        tzname = time.tzname[0]
    except Exception:
        tzname = "UTC"

    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = ""

    return {
        "so": f"{platform.system()} {platform.release()}".strip(),
        "python": sys.version.split()[0],
        "tz": tzname,
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # Versión de producto: siempre desde tz_version (fuente canónica
        # única), nunca desde config.json — evita divergencia con la app.
        "tz_analysis": TZ_VERSION,
        "version_config": cfg.get("version_config") or "sin_version",
        "hostname": platform.node() or "",
        "usuario": usuario,
    }
