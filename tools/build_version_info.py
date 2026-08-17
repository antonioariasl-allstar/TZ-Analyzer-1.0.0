"""tools.build_version_info — genera el recurso de versión de Windows para PyInstaller.

Fuente canónica única: ``tz_version.py``. Este helper no inventa ni duplica
metadata: solo la traduce al formato de texto que PyInstoller espera en
``EXE(..., version=...)`` (una llamada ``VSVersionInfo(...)`` evaluable por
``PyInstaller.utils.win32.versioninfo``). stdlib-only: no requiere
PyInstaller instalado para ejecutarse.

Uso:

    python -m tools.build_version_info
    python tools/build_version_info.py [--output PATH]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import tz_version

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = REPO_ROOT / "build" / "pyinstaller" / "version_info.txt"

# Convención fijada por el encargo (sección 12): English-US + Unicode.
_LANG_ID = 0x0409
_CODEPAGE_ID = 1200
_STRING_TABLE_KEY = "040904B0"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def render_version_info() -> str:
    """Genera el texto del version-info. Determinista: mismas entradas de
    tz_version.py -> mismo texto (sin timestamps ni rutas absolutas)."""
    filevers = tuple(tz_version.WINDOWS_FILE_VERSION)
    prodvers = tuple(tz_version.WINDOWS_FILE_VERSION)

    fields = (
        ("CompanyName", tz_version.COMPANY_NAME),
        ("FileDescription", tz_version.FILE_DESCRIPTION),
        ("FileVersion", tz_version.FILE_VERSION),
        ("InternalName", tz_version.PRODUCT_NAME),
        ("LegalCopyright", tz_version.COPYRIGHT),
        ("OriginalFilename", tz_version.EXECUTABLE_NAME),
        ("ProductName", tz_version.PRODUCT_NAME),
        ("ProductVersion", tz_version.PRODUCT_VERSION),
    )
    string_structs = ",\n        ".join(
        f"StringStruct(u'{name}', u'{_escape(value)}')" for name, value in fields
    )

    return (
        "# UTF-8\n"
        "#\n"
        "# Generado por tools/build_version_info.py a partir de tz_version.py.\n"
        "# No editar a mano: se regenera en cada build.\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={filevers!r},\n"
        f"    prodvers={prodvers!r},\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "    ),\n"
        "  kids=[\n"
        "    StringFileInfo(\n"
        "      [\n"
        "      StringTable(\n"
        f"        u'{_STRING_TABLE_KEY}',\n"
        f"        [{string_structs}])\n"
        "      ]),\n"
        f"    VarFileInfo([VarStruct(u'Translation', [{_LANG_ID}, {_CODEPAGE_ID}])])\n"
        "  ]\n"
        ")\n"
    )


def generate(output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Escribe el version-info en ``output_path`` (creando el directorio
    destino si falta) y devuelve la ruta escrita."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_version_info(), encoding="utf-8", newline="\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        type=Path,
        help="Ruta de salida del version-info (por defecto build/pyinstaller/version_info.txt).",
    )
    args = parser.parse_args()
    output_path = generate(args.output)
    print(output_path)


if __name__ == "__main__":
    main()
