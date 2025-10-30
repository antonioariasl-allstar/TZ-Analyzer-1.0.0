"""
tz_cli.__main__ - Entry point para python -m tz_cli.menu
=========================================================

Elimina warnings de sys.modules al ejecutar como módulo.
"""

from .menu import main_menu
import sys

if len(sys.argv) > 1 and sys.argv[1] == "--help":
    print("TZ CLI Menu - Interfaz interactivo")
    print("Uso: python -m tz_cli.menu")
    sys.exit(0)

main_menu()