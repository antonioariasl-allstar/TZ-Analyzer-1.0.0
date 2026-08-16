#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run.py - ENTRY POINT PRINCIPAL del TZ Analyzer
===============================================

✅ ESTADO: PUNTO DE ENTRADA PRINCIPAL - USAR PARA EJECUCIÓN NORMAL
🎯 PROPÓSITO: Launcher principal con logging y manejo de errores
📍 DIFERENCIACIÓN: NO confundir con run_baseline_correct.py (testing automation)

RESPONSABILIDADES:
- Punto de entrada principal: python run.py
- Configuración de logging para debugging
- Manejo robusto de errores y excepciones
- Bootstrap de configuración del sistema

ARQUITECTURA HÍBRIDA:
- Este archivo es el LAUNCHER PRINCIPAL para usuarios
- run_baseline_correct.py es herramienta de TESTING/AUTOMATION
- Son complementarios, NO duplicados

Configura logging y ejecuta el flujo principal del analizador forense.
Uso: python run.py
"""

import logging

import tz_logging
from tz_core.app_runner import run


if __name__ == "__main__":
    # Logging centralizado (ver tz_logging.py): archivo persistente en
    # LOCALAPPDATA + consola, mismo destino que tz_launcher.py.
    tz_logging.configure_logging()
    _logger = logging.getLogger("run")

    # Ejecutar flujo principal con manejo de errores
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n[INFO] Proceso cancelado por el usuario.")
    except Exception:
        _logger.exception("Error no controlado")
        raise
