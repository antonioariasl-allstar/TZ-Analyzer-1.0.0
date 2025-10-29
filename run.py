#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run.py - ENTRY POINT PRINCIPAL del TZ Analyzer
===============================================

✅ ESTADO: PUNTO DE ENTRADA PRINCIPAL - SPRINT 3A INTEGRADO
🎯 PROPÓSITO: Launcher principal con logging y manejo de errores
📍 DIFERENCIACIÓN: USA NUEVO MENÚ MODULAR via run_cli()

RESPONSABILIDADES:
- Punto de entrada principal: python run.py
- Configuración de logging para debugging
- Delegación a tz_cli.menu.main_menu() via run_cli()
- Manejo robusto de errores y excepciones
- Bootstrap de configuración del sistema

SPRINT 3A INTEGRACIÓN:
- run.py → run_cli() → tz_cli.menu.main_menu()
- Zero cambios para usuario final
- Modularización transparente

Configura logging y ejecuta el flujo principal del analizador forense.
Uso: python run.py
"""

import logging
import traceback
from script_principal_bitacoras_refactory import run_cli, bootstrap_config


if __name__ == "__main__":
    # Inicializar configuración y banner
    bootstrap_config()

    # Configurar logging simple y visible en consola
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # Ejecutar flujo principal con menú modular tz_cli
    try:
        run_cli()  # SPRINT 3A: Delegación a menú modular
    except KeyboardInterrupt:
        print("\n\n[INFO] Proceso cancelado por el usuario.")
    except Exception as e:
        logging.error("Error no controlado: %s", e)
        traceback.print_exc()
        raise
