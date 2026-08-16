"""tools.generate_user_manual — genera el Manual de Usuario externo,
autocontenido, de TZ Analyzer (FASE 4C).

Produce un único archivo HTML pensado para abrirse con doble clic, sin
ejecutar TZ Analyzer, sin servidor Flask y sin conexión a Internet:

    Manual de usuario - TZ Analyzer.html

No existe una segunda redacción del manual: este generador renderiza el
mismo fragmento de contenido (``tz_web/templates/help_manual.html``) que
sirve el AYUDA interno en ``/help`` (ver ``tz_web.routes.help_screen``),
usando un ``jinja2.Environment`` propio — sin depender de una app Flask en
ejecución ni de un contexto de request — y las mismas fuentes canónicas
(``tz_version``, ``tz_web.field_catalog``, ``tz_core.geo_utils``). Una
edición futura del contenido del manual, hecha una sola vez en el
fragmento compartido, se refleja automáticamente en ambos productos.

El HTML/CSS/branding se incrustan en el propio archivo (CSS inline,
imágenes como data URI) para que el resultado sea autónomo: sin
``<link>``/``<img src="/...">`` que dependan de un servidor.

Uso:

    python -m tools.generate_user_manual
    python tools/generate_user_manual.py [--output-dir RUTA]
"""

from __future__ import annotations

import argparse
import base64
import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "tz_web", "templates")
STATIC_CSS_DIR = os.path.join(REPO_ROOT, "tz_web", "static", "css")
BRANDING_DIR = os.path.join(REPO_ROOT, "tz_core", "assets", "branding")

# Ubicación de build por defecto (FASE 4C, sección 4): no asume todavía la
# estructura final de distribución ONEDIR — ya está ignorada por git
# (ver .gitignore: build/).
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "build", "manual")

OUTPUT_FILENAME = "Manual de usuario - TZ Analyzer.html"

_STANDALONE_TEMPLATE = "help_manual_standalone.html"

_CSS_FILES = ("app.css", "help.css")

_BRANDING_FILES = {
    "logo_src": "TZ_Analyzer_icono_app.png",
    "logo_isotipo_src": "TZ_Analyzer_isotipo_principal.png",
}


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_css_comments(css: str) -> str:
    """Quita los comentarios /* ... */ del CSS fuente antes de incrustarlo:
    son notas de desarrollo (nombres de fases, justificaciones internas)
    que no aportan nada al documento distribuido, y de paso evitan que
    texto interno (p. ej. una nota explicando que no se usa CDN) termine
    filtrándose de forma engañosa al HTML final."""
    return _CSS_COMMENT_RE.sub("", css)


def _inline_css() -> str:
    """Concatena las mismas hojas de estilo que enlaza el AYUDA interno
    (app.css + help.css), en el mismo orden, para paridad visual exacta."""
    partes = [
        _strip_css_comments(_read_text(os.path.join(STATIC_CSS_DIR, nombre)))
        for nombre in _CSS_FILES
    ]
    return "\n\n".join(partes)


def _data_uri_png(path: str) -> str:
    with open(path, "rb") as fh:
        contenido = fh.read()
    codificado = base64.b64encode(contenido).decode("ascii")
    return f"data:image/png;base64,{codificado}"


def _branding_data_uris() -> dict:
    return {
        variable: _data_uri_png(os.path.join(BRANDING_DIR, nombre_archivo))
        for variable, nombre_archivo in _BRANDING_FILES.items()
    }


def _jinja_environment() -> Environment:
    """Entorno Jinja propio, independiente de Flask: reutiliza las mismas
    plantillas de tz_web/templates/ sin necesitar una app en ejecución, un
    contexto de request ni ``url_for`` (FASE 4C, sección 11)."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(("html",)),
    )


def build_context() -> dict:
    """Reúne únicamente valores de fuentes canónicas ya existentes — sin
    hardcodear versión, autoría, catálogo de campos ni geometría de
    cobertura (FASE 4C, sección 9)."""
    from tz_core.config_manager import DEFAULT_CONFIG
    from tz_core.geo_utils import resolve_azimuth_cone_geometry
    from tz_version import AUTHOR, BETA_USAGE_NOTICE, COPYRIGHT, VERSION
    from tz_web.field_catalog import FIELD_DESCRIPTIONS, FIELD_GROUPS, FIELD_LABELS
    from tz_web.help_content import HELP_SECTIONS

    az_km, az_half_deg = resolve_azimuth_cone_geometry(DEFAULT_CONFIG)

    context = {
        "help_sections": HELP_SECTIONS,
        "version": VERSION,
        "author": AUTHOR,
        "copyright_notice": COPYRIGHT,
        "beta_notice": BETA_USAGE_NOTICE,
        "field_groups": FIELD_GROUPS,
        "field_labels": FIELD_LABELS,
        "field_descriptions": FIELD_DESCRIPTIONS,
        "az_km": az_km,
        "az_half_deg": az_half_deg,
        "az_total_deg": az_half_deg * 2,
        "inline_css": _inline_css(),
    }
    context.update(_branding_data_uris())
    return context


def render_manual_html() -> str:
    """Renderiza el HTML completo del manual externo. Determinista: no
    incorpora timestamp, ruta local, hostname, usuario ni UUID (FASE 4C,
    sección 12) — dos llamadas con las mismas fuentes producen el mismo
    resultado."""
    env = _jinja_environment()
    template = env.get_template(_STANDALONE_TEMPLATE)
    return template.render(**build_context())


def generate(output_dir: str = DEFAULT_OUTPUT_DIR) -> str:
    """Genera el archivo y devuelve su ruta absoluta."""
    html = render_manual_html()
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, OUTPUT_FILENAME)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta donde escribir el manual (por defecto build/manual/).",
    )
    args = parser.parse_args()
    output_path = generate(args.output_dir)
    print(output_path)


if __name__ == "__main__":
    main()
