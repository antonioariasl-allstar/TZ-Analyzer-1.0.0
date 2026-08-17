# -*- mode: python ; coding: utf-8 -*-
"""TZ_Analyzer.spec — build PyInstaller ONEDIR de TZ Analyzer.

Toda ruta y flag no trivial vive en build_config/spec_config.py (fuente
única, importable sin PyInstaller instalado — ver su docstring). Este
archivo solo traduce esa configuración a las llamadas
Analysis/PYZ/EXE/COLLECT que PyInstaller 6.x espera encontrar en un .spec.

Reproducible: ninguna ruta está hardcodeada a esta máquina. La raíz del
repo se calcula desde SPECPATH (global que PyInstaller inyecta con el
directorio que contiene este .spec).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH)))  # noqa: F821 - inyectado por PyInstaller

from build_config import spec_config as cfg

a = Analysis(  # noqa: F821 - inyectado por PyInstaller
    [str(cfg.ENTRYPOINT)],
    pathex=[str(cfg.REPO_ROOT)],
    binaries=[],
    datas=[(str(src), dest) for src, dest in cfg.DATAS],
    hiddenimports=list(cfg.HIDDENIMPORTS),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(cfg.EXCLUDES),
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)  # noqa: F821 - inyectado por PyInstaller

exe = EXE(  # noqa: F821 - inyectado por PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=cfg.PRODUCT_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=cfg.STRIP,
    upx=cfg.UPX,
    console=cfg.CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(cfg.ICON_PATH),
    version=str(cfg.VERSION_INFO_PATH),
    manifest=str(cfg.MANIFEST_PATH),
)

coll = COLLECT(  # noqa: F821 - inyectado por PyInstaller
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=cfg.STRIP,
    upx=cfg.UPX,
    upx_exclude=[],
    name=cfg.PRODUCT_NAME,
    contents_directory=cfg.CONTENTS_DIRECTORY,
)
