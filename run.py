#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run.py
------
Punto de entrada principal para TZ-Analysis-1.0.0

Configura logging y ejecuta el flujo principal del analizador forense.
Uso: python run.py
"""

import logging
import traceback
from script_principal_bitacoras_refactory import main, bootstrap_config


if __name__ == "__main__":
    # Inicializar configuración y banner
    bootstrap_config()

    # Configurar logging simple y visible en consola
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # Ejecutar flujo principal con manejo de errores
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Proceso cancelado por el usuario.")
    except Exception as e:
        logging.error("Error no controlado: %s", e)
        traceback.print_exc()
        raise
