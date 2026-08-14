#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tz_version — fuente canónica única de identidad y versión de TZ Analyzer.

Dependency-free y sin efectos secundarios: importable antes de Flask, desde
``tz_launcher.py``, y en contexto frozen (PyInstaller) sin arrastrar el resto
de la aplicación. No importa nada de ``tz_core`` ni de ``tz_web`` — son esos
paquetes los que derivan de este módulo, nunca al revés.
"""

from __future__ import annotations

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
    "Versión Beta destinada a evaluación y uso autorizado. "
    "No se autoriza su redistribución, modificación o publicación "
    "sin autorización del autor."
)

SUPPORT_NOTICE = (
    "Para soporte y sugerencias, contactar al autor por el medio "
    "proporcionado junto con la distribución."
)

# Metadata de Windows/PyInstaller (preparación anticipada, sin generar
# todavía version_info.txt ni recursos .spec — ver FASE 3, sección 8).
EXECUTABLE_NAME = "TZ Analyzer.exe"
FILE_DESCRIPTION = PRODUCT_DESCRIPTION
PRODUCT_VERSION = VERSION
FILE_VERSION = WINDOWS_FILE_VERSION_STRING
