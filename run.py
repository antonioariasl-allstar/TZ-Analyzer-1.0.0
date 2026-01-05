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
import traceback
from tz_core.app_runner import run


if __name__ == "__main__":
    # Inicializar logging simple y visible en consola (se mantiene aquí)
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # Ejecutar flujo principal con manejo de errores
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n[INFO] Proceso cancelado por el usuario.")
    except Exception as e:
        logging.error("Error no controlado: %s", e)
        traceback.print_exc()
        raise
