"""tools.generate_user_manual — Manual de Usuario externo autocontenido
(FASE 4C).

Cubre: generación del archivo esperado, validez razonable del HTML,
contenido esencial (versión, 14 campos, geometría 1.5 km / 70° (±35°),
autoría, aviso Beta), independencia de Flask/localhost/rutas absolutas del
repositorio, CSS y branding incrustados (sin dependencias externas),
determinismo entre generaciones, y paridad semántica con el AYUDA interno
servido en /help (misma fuente de contenido — no se compara byte a byte
porque las envolturas HTML son distintas).
"""
from __future__ import annotations

import base64
import html.parser
import re

import pytest

from tools.generate_user_manual import (
    OUTPUT_FILENAME,
    REPO_ROOT,
    build_context,
    generate,
    render_manual_html,
)
from tz_web.field_catalog import CANONICAL_FIELDS, FIELD_LABELS
from tz_version import AUTHOR, BETA_USAGE_NOTICE, VERSION


class _BalancedTagChecker(html.parser.HTMLParser):
    """Validador liviano: verifica que las etiquetas abren y cierran de
    forma balanceada. No pretende ser un validador W3C completo — solo
    suficiente para detectar HTML roto por un error de plantilla."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self._VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self._VOID_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"cierre inesperado de </{tag}>, pila={self.stack}")
            return
        self.stack.pop()


@pytest.fixture(scope="module")
def manual_html() -> str:
    return render_manual_html()


@pytest.fixture()
def help_html_interno(client) -> str:
    return " ".join(client.get("/help").data.decode("utf-8").split())


# ---------------------------------------------------------------------------
# 1/2 — se genera el archivo esperado, y es HTML razonablemente válido.
# ---------------------------------------------------------------------------


def test_generate_produce_el_archivo_esperado(tmp_path):
    output_path = generate(str(tmp_path))
    assert output_path == str(tmp_path / OUTPUT_FILENAME)
    assert output_path.endswith(OUTPUT_FILENAME)
    with open(output_path, "r", encoding="utf-8") as fh:
        contenido = fh.read()
    assert contenido.strip().startswith("<!DOCTYPE html>")


def test_manual_es_html_razonablemente_valido(manual_html):
    parser = _BalancedTagChecker()
    parser.feed(manual_html)
    assert parser.errors == []
    assert parser.stack == [], f"etiquetas sin cerrar: {parser.stack}"


# ---------------------------------------------------------------------------
# 3-7 — contenido esencial: versión, 14 campos, geometría, autoría, Beta.
# ---------------------------------------------------------------------------


def test_manual_contiene_version(manual_html):
    assert VERSION == "1.0.0-beta.1"
    assert VERSION in manual_html


def test_manual_contiene_los_14_campos(manual_html):
    assert len(CANONICAL_FIELDS) == 14
    for campo in CANONICAL_FIELDS:
        assert FIELD_LABELS[campo] in manual_html


def test_manual_contiene_1_5_km(manual_html):
    assert "1.5 km" in manual_html


def test_manual_contiene_70_grados_35(manual_html):
    assert "70°" in manual_html
    assert "±35°" in manual_html


def test_manual_contiene_autoria_y_aviso_beta(manual_html):
    assert f"Concepción, desarrollo y metodología: {AUTHOR}." in manual_html
    assert BETA_USAGE_NOTICE in manual_html


# ---------------------------------------------------------------------------
# 8-12 — independencia de Flask/localhost/rutas absolutas/CDN.
# ---------------------------------------------------------------------------


def test_manual_no_contiene_localhost(manual_html):
    assert "localhost" not in manual_html.lower()


def test_manual_no_contiene_127_0_0_1(manual_html):
    assert "127.0.0.1" not in manual_html


def test_manual_no_contiene_rutas_absolutas_del_repo(manual_html):
    assert REPO_ROOT not in manual_html
    assert "C:\\" not in manual_html
    assert "c:\\" not in manual_html.lower()


def test_manual_no_depende_de_static(manual_html):
    assert "/static/" not in manual_html
    assert "url_for" not in manual_html


def test_manual_sin_enlaces_externos_requeridos(manual_html):
    assert "http://" not in manual_html
    assert "https://" not in manual_html
    assert "cdn." not in manual_html.lower()


# ---------------------------------------------------------------------------
# 13/14 — CSS esencial y branding incrustados, disponibles sin servidor.
# ---------------------------------------------------------------------------


def test_manual_incrusta_css_esencial(manual_html):
    assert "<style>" in manual_html
    # --tz-navy vive en app.css (:root); .tz-help-section vive en help.css.
    # Confirma que ambas hojas quedaron incrustadas, no solo una.
    assert "--tz-navy" in manual_html
    assert ".tz-help-section" in manual_html


def test_manual_incrusta_branding_como_data_uri(manual_html):
    ocurrencias = manual_html.count("data:image/png;base64,")
    assert ocurrencias >= 2  # logo (header) + isotipo (sección "¿Qué es TZ Analyzer?")


def test_manual_data_uri_decodifica_a_png_valido():
    context = build_context()
    for clave in ("logo_src", "logo_isotipo_src"):
        data_uri = context[clave]
        assert data_uri.startswith("data:image/png;base64,")
        payload = data_uri.split(",", 1)[1]
        crudo = base64.b64decode(payload)
        assert crudo[:8] == b"\x89PNG\r\n\x1a\n"  # firma PNG


# ---------------------------------------------------------------------------
# 15 — determinismo: dos generaciones sin cambios producen el mismo HTML.
# ---------------------------------------------------------------------------


def test_dos_generaciones_son_deterministas(tmp_path):
    primero = render_manual_html()
    segundo = render_manual_html()
    assert primero == segundo

    ruta_a = generate(str(tmp_path / "gen_a"))
    ruta_b = generate(str(tmp_path / "gen_b"))
    with open(ruta_a, "r", encoding="utf-8") as fh:
        contenido_a = fh.read()
    with open(ruta_b, "r", encoding="utf-8") as fh:
        contenido_b = fh.read()
    assert contenido_a == contenido_b


def test_manual_no_contiene_marcadores_no_deterministas(manual_html):
    # Ninguna marca de tiempo, UUID, ni usuario/host de la máquina que
    # generó el archivo.
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", manual_html)
    assert not re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        manual_html,
    )
    import getpass
    assert getpass.getuser() not in manual_html


# ---------------------------------------------------------------------------
# 16 — paridad semántica con el AYUDA interno (misma fuente de contenido).
# ---------------------------------------------------------------------------


def test_contenido_esencial_coincide_semanticamente_con_ayuda_interna(
    manual_html, help_html_interno
):
    manual_compacto = " ".join(manual_html.split())
    fragmentos_compartidos = (
        VERSION,
        "¿Qué es TZ Analyzer?",
        "Preparación de la bitácora",
        "Modo 1 — Análisis completo",
        "Modo 2 — Análisis con filtro temporal",
        "Modo 3 — Mapeo manual",
        "1.5 km",
        "70°",
        "±35°",
        "no representan la ubicación exacta del dispositivo",
        "distancia entre dos antenas no demuestra",
        "i2 Analyst's Notebook",
        f"Concepción, desarrollo y metodología: {AUTHOR}.",
        BETA_USAGE_NOTICE,
    )
    for fragmento in fragmentos_compartidos:
        assert fragmento in manual_compacto, f"falta en manual externo: {fragmento!r}"
        assert fragmento in help_html_interno, f"falta en AYUDA interno: {fragmento!r}"


def test_manual_no_contiene_seccion_soporte(manual_html):
    """El manual externo hereda la misma limpieza editorial de FASE 4B:
    sin sección de soporte ni placeholders de pendientes."""
    assert "Soporte y sugerencias" not in manual_html
    assert "pendiente de confirmación" not in manual_html.lower()
