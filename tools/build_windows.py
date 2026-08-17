"""tools.build_windows — orquestación mínima del build PyInstaller ONEDIR.

Responsabilidades exactas: verificar Python/PyInstaller, limpiar solo los
artefactos de packaging (build/pyinstaller y dist/"TZ Analyzer"), generar
version_info.txt, el manual y THIRD-PARTY-NOTICES.txt, invocar
``python -m PyInstaller --clean TZ_Analyzer.spec``, copiar el manual y los
avisos de terceros al bundle y verificar que el .exe, el manual y los
avisos quedaron en dist/. No corre tests, no toca git, no genera íconos, no
edita el .spec, no firma, no toca el registro ni instala dependencias.

Uso: ``python -m tools.build_windows``
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "TZ_Analyzer.spec"
BUILD_PYINSTALLER_DIR = REPO_ROOT / "build" / "pyinstaller"
DIST_DIR = REPO_ROOT / "dist" / "TZ Analyzer"
MANUAL_FILENAME = "Manual de usuario - TZ Analyzer.html"
NOTICES_FILENAME = "THIRD-PARTY-NOTICES.txt"


class BuildError(RuntimeError):
    """Preflight o paso de build fallido."""


def check_python() -> None:
    if sys.version_info < (3, 12):
        raise BuildError(f"Se requiere Python 3.12+; se detectó {sys.version}")


def check_pyinstaller_installed() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        raise BuildError(
            "PyInstaller no está instalado. Instalar con: "
            "pip install -r requirements-build.txt"
        )


def clean_packaging_artifacts() -> None:
    shutil.rmtree(BUILD_PYINSTALLER_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)


def generate_version_info() -> Path:
    from tools.build_version_info import generate as generate_version_resource

    return generate_version_resource()


def generate_manual() -> Path:
    from tools.generate_user_manual import generate as generate_manual_html

    return Path(generate_manual_html())


def generate_third_party_notices() -> Path:
    from tools.build_third_party_notices import generate_notices_text, load_manifest, write_notices

    text = generate_notices_text(load_manifest())
    return write_notices(text)


def run_pyinstaller() -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", str(SPEC_PATH)],
        cwd=str(REPO_ROOT),
        check=True,
    )


def copy_manual_to_dist(manual_path: Path) -> Path:
    destination = DIST_DIR / MANUAL_FILENAME
    shutil.copyfile(manual_path, destination)
    return destination


def copy_notices_to_dist(notices_path: Path) -> Path:
    destination = DIST_DIR / NOTICES_FILENAME
    shutil.copyfile(notices_path, destination)
    return destination


def verify_dist() -> None:
    exe_path = DIST_DIR / f"{spec_config_product_name()}.exe"
    manual_path = DIST_DIR / MANUAL_FILENAME
    notices_path = DIST_DIR / NOTICES_FILENAME
    if not exe_path.exists():
        raise BuildError(f"No se generó el ejecutable esperado: {exe_path}")
    if not manual_path.exists():
        raise BuildError(f"No se copió el manual esperado: {manual_path}")
    if not notices_path.exists():
        raise BuildError(f"No se copiaron los avisos de terceros esperados: {notices_path}")


def spec_config_product_name() -> str:
    from build_config.spec_config import PRODUCT_NAME

    return PRODUCT_NAME


def main() -> int:
    from tools.build_third_party_notices import NoticesError

    try:
        check_python()
        check_pyinstaller_installed()
        clean_packaging_artifacts()
        generate_version_info()
        manual_path = generate_manual()
        notices_path = generate_third_party_notices()
        run_pyinstaller()
        copy_manual_to_dist(manual_path)
        copy_notices_to_dist(notices_path)
        verify_dist()
    except (BuildError, NoticesError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(f"Build completo: {DIST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
