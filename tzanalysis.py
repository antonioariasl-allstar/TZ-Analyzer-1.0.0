#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tzanalysis - ENTRY POINT CLI CLICK MODERNO
==========================================

✅ ESTADO: SPRINT 3B - CLI CLICK EXECUTABLE  
🎯 PROPÓSITO: Script ejecutable para tzanalysis CLI
📍 DIFERENCIACIÓN: Entrada CLI vs python run.py (menú interactivo)

COMANDO BASE: tzanalysis [COMMAND] [OPTIONS]

EJEMPLOS:
- tzanalysis run --input bitacora.xlsx --top-antenas 10
- tzanalysis validate --input data.tsv --verbose
- tzanalysis manual --coord-lat 40.4168 --coord-lon -3.7038
- tzanalysis info --dependencies

DIFERENCIACIÓN:
- tzanalysis: CLI argumentos (automation/programático)
- python run.py: Menú interactivo (wizard paso a paso)

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3B Fase 3B.1
"""

import sys
import os
from pathlib import Path

# Agregar directorio raíz al path para imports
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    from tz_cli_click.main import main
    main()