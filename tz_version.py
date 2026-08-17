#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tz_version — fuente canónica única de identidad y versión de TZ Analyzer.

Dependency-free y sin efectos secundarios: importable antes de Flask, desde
``tz_launcher.py``, y en contexto frozen (PyInstaller) sin arrastrar el resto
de la aplicación. No importa nada de ``tz_core`` ni de ``tz_web`` — son esos
paquetes los que derivan de este módulo, nunca al revés.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

PRODUCT_NAME = "TZ Analyzer"

PRODUCT_DESCRIPTION = "Análisis de bitácoras telefónicas y georreferenciación"

# Versión pública (display/producto).
VERSION = "1.0.0-beta.1"

# Representación PEP 440 (para empaquetado/distribución cuando se necesite).
PEP440_VERSION = "1.0.0b1"

# FileVersion numérica de Windows (4 componentes).
WINDOWS_FILE_VERSION = (1, 0, 0, 1)
WINDOWS_FILE_VERSION_STRING = "1.0.0.1"

AUTHOR = "Omar Arias (Tony Zero)"
COMPANY_NAME = ""

COPYRIGHT = "© 2026 Omar Arias (Tony Zero). Todos los derechos reservados."

BETA_USAGE_NOTICE = (
    "Versión Beta gratuita destinada a evaluación operativa y recopilación "
    "de experiencia de uso, con el fin de identificar incidencias y "
    "orientar mejoras futuras. Esta versión permanecerá vigente hasta el "
    "31 de diciembre de 2027. No se autoriza su redistribución, "
    "modificación o publicación sin autorización del autor."
)

SUPPORT_NOTICE = (
    "Para soporte y sugerencias, contactar al autor por el medio "
    "proporcionado junto con la distribución."
)

# ---------------------------------------------------------------------------
# Vigencia de la Beta — fuente única de verdad (fecha, estado, mensajes).
#
# ``BETA_EXPIRES_ON`` es la última fecha calendario (hora local, no UTC: la
# vigencia se comunica como fecha de calendario, no como instante global) en
# que sigue permitido iniciar nuevos análisis. El 31/12/2027 completo sigue
# vigente; recién el 01/01/2028 se considera vencida (comparación estricta
# ">", nunca ">="). No es un mecanismo antifraude: no intenta detectar un
# reloj del sistema manipulado ni requiere activación en línea — es
# simplemente el aviso de fin del período de evaluación de esta Beta.
# ---------------------------------------------------------------------------

BETA_EXPIRES_ON = date(2027, 12, 31)

# A partir de cuántos días restantes se muestra un aviso discreto de
# proximidad del vencimiento (sección F del encargo: un solo umbral, sin
# escalonar 60/30/15/7).
BETA_WARNING_THRESHOLD_DAYS = 30

BETA_EXPIRED_NOTICE = (
    "El período de evaluación de esta versión Beta de TZ Analyzer ha "
    "finalizado. Para realizar nuevos análisis, instale una versión "
    "vigente de TZ Analyzer. Los resultados generados previamente no se "
    "verán afectados."
)


def is_beta_expired(on_date: Optional[date] = None) -> bool:
    """``True`` si ``on_date`` (por defecto la fecha local de hoy) es
    posterior a ``BETA_EXPIRES_ON``. El propio día del vencimiento
    (31/12/2027) todavía cuenta como vigente."""
    current = on_date if on_date is not None else date.today()
    return current > BETA_EXPIRES_ON


def beta_days_remaining(on_date: Optional[date] = None) -> int:
    """Días entre ``on_date`` (por defecto hoy) y ``BETA_EXPIRES_ON``. Puede
    ser negativo una vez vencida la Beta."""
    current = on_date if on_date is not None else date.today()
    return (BETA_EXPIRES_ON - current).days


@dataclass(frozen=True)
class BetaStatus:
    expires_on: date
    expired: bool
    days_remaining: int
    show_warning: bool
    notice: Optional[str]


def _beta_warning_notice(days_remaining: int) -> str:
    if days_remaining <= 0:
        return "Esta versión Beta de TZ Analyzer finaliza su período de evaluación hoy."
    dia_o_dias = "día" if days_remaining == 1 else "días"
    return (
        "Esta versión Beta permanecerá vigente hasta el 31 de diciembre de "
        f"2027. Faltan {days_remaining} {dia_o_dias} para finalizar su "
        "período de evaluación."
    )


def get_beta_status(on_date: Optional[date] = None) -> BetaStatus:
    """Estado completo de vigencia para ``on_date`` (por defecto hoy):
    vencida/vigente, días restantes y el mensaje a mostrar, si corresponde
    (``None`` cuando no hay nada que comunicar todavía, es decir, vigente y
    a más de ``BETA_WARNING_THRESHOLD_DAYS`` del vencimiento)."""
    current = on_date if on_date is not None else date.today()
    expired = is_beta_expired(current)
    days_remaining = beta_days_remaining(current)
    show_warning = not expired and days_remaining <= BETA_WARNING_THRESHOLD_DAYS
    if expired:
        notice = BETA_EXPIRED_NOTICE
    elif show_warning:
        notice = _beta_warning_notice(days_remaining)
    else:
        notice = None
    return BetaStatus(
        expires_on=BETA_EXPIRES_ON,
        expired=expired,
        days_remaining=days_remaining,
        show_warning=show_warning,
        notice=notice,
    )

# Metadata de Windows/PyInstaller (preparación anticipada, sin generar
# todavía version_info.txt ni recursos .spec — ver FASE 3, sección 8).
EXECUTABLE_NAME = "TZ Analyzer.exe"
FILE_DESCRIPTION = PRODUCT_DESCRIPTION
PRODUCT_VERSION = VERSION
FILE_VERSION = WINDOWS_FILE_VERSION_STRING
