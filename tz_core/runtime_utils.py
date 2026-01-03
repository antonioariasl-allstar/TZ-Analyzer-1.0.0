"""Utilidades generales relacionadas con el entorno de ejecucion."""

from __future__ import annotations

import getpass
import platform
import sys
import time
from datetime import datetime
from typing import Any, Dict


def collect_env_snapshot(config: Dict[str, Any] | None = None) -> Dict[str, str]:
    """Devuelve metadatos basicos del entorno para trazabilidad de reportes.

    Args:
        config: Diccionario opcional de configuración global para enriquecer datos.

    Returns:
        Dict con datos como SO, version de Python, zona horaria y versiones declaradas.
    """

    cfg = config or {}
    brand = cfg.get("brand") or {}

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
        "tz_analysis": cfg.get("version") or brand.get("version") or "sin_version",
        "version_config": cfg.get("version_config") or "sin_version",
        "hostname": platform.node() or "",
        "usuario": usuario,
    }
