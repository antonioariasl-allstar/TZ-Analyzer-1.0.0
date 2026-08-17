"""tools.build_third_party_notices — genera THIRD-PARTY-NOTICES.txt.

Herramienta MECANICA (P1-LICENSES): lee el manifiesto curado a mano
``build_config/third_party_components.json``, localiza los archivos de
licencia/aviso declarados para cada componente, valida que existan y
concatena su contenido textual íntegro con encabezados y separadores para
producir ``THIRD-PARTY-NOTICES.txt`` en la raíz del repo.

No infiere licencias, no consulta la red, no descarga nada, no decide
compatibilidad ni obligaciones jurídicas, no traduce ni altera los textos
legales. Toda esa curación vive en el manifiesto, escrito a mano por una
persona a partir de evidencia local (ver build_config/LGPL_ANALYSIS.md para
el caso especial de simplekml).

Resolución de archivos según ``kind`` de cada componente:

- ``pip``: localiza el archivo dentro del ``.dist-info`` del paquete
  instalado (vía ``importlib.metadata``), usando ``pip_name`` + ``version``
  como identificador reproducible (nunca una ruta absoluta guardada en el
  manifiesto). Si la versión instalada no coincide con la declarada, falla
  con un error explícito (detección de desincronización manifiesto/venv).
- ``vendored``: resuelve bajo
  ``build_config/third_party_licenses/<vendored_dir>/`` (copias locales
  versionadas de licencias cuyo origen real -instalación base de
  Python/Tcl/Tk- no es reproducible entre máquinas).
- ``repo_asset``: resuelve bajo ``<asset_dir>/`` dentro del propio
  repositorio (assets vendorizados que ya viven en tz_core).

Uso: ``python -m tools.build_third_party_notices``
"""
from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "build_config" / "third_party_components.json"
VENDORED_LICENSES_DIR = REPO_ROOT / "build_config" / "third_party_licenses"
OUTPUT_PATH = REPO_ROOT / "THIRD-PARTY-NOTICES.txt"

HEADER = """\
TZ Analyzer — AVISOS DE TERCEROS
=================================

TZ Analyzer incorpora componentes de terceros sujetos a sus respectivas
licencias. Los textos legales originales se conservan íntegros y sin
traducción sustitutiva a continuación, uno por componente.

Este archivo se genera de forma determinística a partir de
build_config/third_party_components.json mediante
tools/build_third_party_notices.py. No editar a mano: para corregir o
añadir un componente, editar el manifiesto y volver a generar.
"""

COMPONENT_SEPARATOR = "\n" + ("=" * 78) + "\n"
SECTION_SEPARATOR = "-" * 78


class NoticesError(RuntimeError):
    """Manifiesto inválido o archivo de licencia declarado ausente."""


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.is_file():
        raise NoticesError(f"No se encontró el manifiesto: {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    components = data.get("components")
    if not isinstance(components, list) or not components:
        raise NoticesError("El manifiesto no contiene una lista 'components' no vacía.")
    return components


def _locate_pip_file(pip_name: str, version: str, relative_path: str) -> Path:
    try:
        dist = metadata.distribution(pip_name)
    except metadata.PackageNotFoundError as exc:
        raise NoticesError(
            f"Paquete pip '{pip_name}' no está instalado en este entorno; "
            "no se puede generar THIRD-PARTY-NOTICES.txt sin él."
        ) from exc

    if dist.version != version:
        raise NoticesError(
            f"Desincronización de versión para '{pip_name}': manifiesto declara "
            f"{version!r}, entorno tiene {dist.version!r}. Actualizar el "
            "manifiesto (o el entorno) antes de generar notices."
        )

    wanted_parts = Path(relative_path).parts
    for package_path in dist.files or []:
        parts = package_path.parts
        for index, part in enumerate(parts):
            if part.endswith(".dist-info") and tuple(parts[index + 1 :]) == wanted_parts:
                located = Path(package_path.locate())
                if not located.is_file():
                    break
                return located
    raise NoticesError(
        f"No se encontró '{relative_path}' dentro del .dist-info de "
        f"'{pip_name}' {version} instalado."
    )


def _locate_vendored_file(vendored_dir: str, relative_path: str) -> Path:
    return VENDORED_LICENSES_DIR / vendored_dir / relative_path


def _locate_repo_asset_file(asset_dir: str, relative_path: str) -> Path:
    return REPO_ROOT / asset_dir / relative_path


def resolve_component_file(component: dict, relative_path: str) -> Path:
    kind = component.get("kind")
    if kind == "pip":
        return _locate_pip_file(component["pip_name"], component["version"], relative_path)
    if kind == "vendored":
        return _locate_vendored_file(component["vendored_dir"], relative_path)
    if kind == "repo_asset":
        return _locate_repo_asset_file(component["asset_dir"], relative_path)
    raise NoticesError(f"kind desconocido en manifiesto: {kind!r} (componente {component.get('name')!r})")


def validate_component_files(component: dict) -> list[Path]:
    """Resuelve y valida existencia de license_files + notice_files + bundled_license_files."""
    name = component.get("name", "<sin nombre>")
    declared = [
        *component.get("license_files", []),
        *component.get("notice_files", []),
        *component.get("bundled_license_files", []),
    ]
    resolved: list[Path] = []
    for relative_path in declared:
        path = resolve_component_file(component, relative_path)
        if not path.is_file():
            raise NoticesError(f"Archivo declarado ausente para '{name}': {path}")
        resolved.append(path)
    return resolved


def _format_component_header(component: dict) -> str:
    lines = [
        component.get("name", "<sin nombre>"),
        f"Versión: {component.get('version', '?')}",
        f"Licencia: {component.get('license', '?')}",
    ]
    copyright_holder = component.get("copyright_holder")
    if copyright_holder:
        lines.append(f"Copyright: {copyright_holder}")
    source_url = component.get("source_url")
    if source_url:
        lines.append(f"Origen: {source_url}")
    notes = component.get("notes")
    if notes:
        lines.append(f"Notas: {notes}")
    return "\n".join(lines)


def render_component(component: dict) -> str:
    header = _format_component_header(component)
    file_groups = (
        ("license_files", component.get("license_files", [])),
        ("notice_files", component.get("notice_files", [])),
        ("bundled_license_files", component.get("bundled_license_files", [])),
    )
    body_parts = []
    for _group_name, relative_paths in file_groups:
        for relative_path in relative_paths:
            path = resolve_component_file(component, relative_path)
            text = path.read_text(encoding="utf-8", errors="strict")
            body_parts.append(f"{SECTION_SEPARATOR}\n[{relative_path}]\n{SECTION_SEPARATOR}\n{text}")
    return header + "\n\n" + "\n\n".join(body_parts) if body_parts else header


def generate_notices_text(components: list[dict]) -> str:
    for component in components:
        validate_component_files(component)

    rendered_components = [render_component(component) for component in components]
    return HEADER + COMPONENT_SEPARATOR + COMPONENT_SEPARATOR.join(rendered_components) + "\n"


def write_notices(text: str) -> Path:
    OUTPUT_PATH.write_text(text, encoding="utf-8", newline="\n")
    return OUTPUT_PATH


def main() -> int:
    try:
        components = load_manifest()
        text = generate_notices_text(components)
        output_path = write_notices(text)
    except NoticesError as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(f"THIRD-PARTY-NOTICES.txt generado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
