"""build_config.spec_config — fuente única de configuración de TZ_Analyzer.spec.

``TZ_Analyzer.spec`` no puede importarse ni ejecutarse sin PyInstaller
instalado: depende de globals que PyInstaller inyecta solo al exec-utarlo
(``Analysis``, ``PYZ``, ``EXE``, ``COLLECT``, ``SPECPATH``). Este módulo, en
cambio, es Python puro sin ninguna dependencia de PyInstaller, así que:

- el spec real importa desde aquí (no duplica rutas/flags);
- la suite de tests puede validar la configuración del build importando
  este módulo directamente, sin instalar PyInstaller.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ENTRYPOINT = REPO_ROOT / "tz_launcher.py"

PRODUCT_NAME = "TZ Analyzer"

ICON_PATH = REPO_ROOT / "tz_core" / "assets" / "branding" / "TZ_Analyzer.ico"
MANIFEST_PATH = REPO_ROOT / "build_config" / "TZ_Analyzer.manifest"
VERSION_INFO_PATH = REPO_ROOT / "build" / "pyinstaller" / "version_info.txt"

# (fuente, destino relativo dentro del bundle) — destino "." = raíz de
# sys._MEIPASS (ver tz_core/config_manager.py y tz_core/user_paths.py).
DATAS: tuple[tuple[Path, str], ...] = (
    (REPO_ROOT / "tz_web" / "templates", "tz_web/templates"),
    (REPO_ROOT / "tz_web" / "static", "tz_web/static"),
    (REPO_ROOT / "tz_core" / "assets", "tz_core/assets"),
    (REPO_ROOT / "config.json", "."),
)

# El primer build real decide estas listas a partir de fallos reproducibles
# (ver P1-BUILD-CONFIG, sección 24) — no se rellenan preventivamente aquí.
HIDDENIMPORTS: tuple[str, ...] = ()
EXCLUDES: tuple[str, ...] = ()

CONSOLE = False
UPX = False
STRIP = False
CONTENTS_DIRECTORY = "_internal"
