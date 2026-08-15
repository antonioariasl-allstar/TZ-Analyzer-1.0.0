"""MICROBLOQUE F3.3 — Integración: pines del mapa del Top de antenas cuando
el sitio es inferido por coordenadas.

Reproduce el defecto reportado: con la columna antena NO mapeada pero con
lat/lon válidas, TZ Analyzer genera el identificador SITIO_<lat>_<long> y la
tabla "Antenas con mayor número de activaciones" lo muestra correctamente,
pero el mapa embebido en esa misma sección (id="heatmap-actividad") no
recibía marcador alguno: el bloque que arma `markers_data` en
tz_core/html/assembler.py resolvía `col_ant` solo contra las columnas
"antena"/"nombre_antena"/"cell_name" (sin considerar `antena_analitica`), a
diferencia de la tabla (`build_top_antennas_section`, en
tz_core/html/antennas.py), que ya usaba el helper canónico
`_resolver_columna_antena` con esa misma prioridad. Con `col_ant` en None,
el bloque de armado de `markers_data` (guardado tras `if col_ant and ...`)
se saltaba por completo, dejando el mapa del Top sin pines aunque el
heatmap (que no depende de `col_ant`) sí se generaba.

Caso B (objetivo del fix): antena NO mapeada + lat/lon válidas -> tabla,
heatmap, pin, popup y azimut deben funcionar igual que con antena real.

Caso A (control, sin regresión): antena mapeada + lat/lon válidas -> mismo
comportamiento que antes del fix.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from tz_core.html.assembler import generar_informe_html
from tz_core.site_inference import agregar_sitio_analitico

LAT, LON = 13.7, -89.2
SITIO_ID = f"SITIO_{LAT:.6f}_{LON:.6f}"

_MARKERS_RE = re.compile(r"const markers = (\[.*?\]);", re.DOTALL)


def _df_base(rows: int = 4, antena=None) -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": ["2024-01-01"] * rows,
        "hora": ["10:00:00", "10:05:00", "10:10:00", "10:15:00"][:rows],
        "interaccion": ["VOZ"] * rows,
        "contacto": ["70001234"] * rows,
        "tel": ["60001234"] * rows,
        "antena": [antena] * rows,
        "lat": [LAT] * rows,
        "long": [LON] * rows,
        "azimut": [45, 45, 90, 45][:rows],
    })


def _extract_markers(html: str) -> list[dict]:
    m = _MARKERS_RE.search(html)
    assert m, "No se encontró 'const markers = [...]' en el HTML (mapa del Top)"
    return json.loads(m.group(1))


def _generar_html(df: pd.DataFrame, tmp_path: Path, nombre: str) -> str:
    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(tmp_path / "no_existe.kml"),
        carpeta_salida=str(tmp_path),
        nombre_salida=nombre,
        config={},
    )
    return Path(html_path).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────
# Caso B — sitio inferido por coordenadas (antena NO mapeada)
# ─────────────────────────────────────────────────────────────────────────

def test_sitio_inferido_genera_pin_popup_y_azimut_en_mapa_del_top(tmp_path):
    df = agregar_sitio_analitico(_df_base(rows=4, antena=None))
    html = _generar_html(df, tmp_path, "sitio_inferido")

    # A. aparece SITIO_lat_lon (tabla "Antenas con mayor número de activaciones")
    assert SITIO_ID in html
    assert 'id="resumen-antenas"' in html

    # B. existe el marcador/pin correspondiente en el mapa del Top
    markers = _extract_markers(html)
    assert markers, "El mapa del Top no recibió ningún marcador"
    sitio_markers = [m for m in markers if m.get("name") == SITIO_ID]
    assert len(sitio_markers) == 1
    marker = sitio_markers[0]
    assert marker["lat"] == pytest.approx(LAT, abs=1e-4)
    assert marker["lon"] == pytest.approx(LON, abs=1e-4)
    assert marker["count"] == 4

    # C. existe popup asociado (mecanismo genérico de construcción de popup,
    # alimentado por el mismo objeto `m` del marcador ya verificado arriba)
    assert "marker.bindPopup(popupContent)" in html
    assert "window.tzEscHtml(m.name)" in html

    # D. azimut permanece disponible: en el marcador (para el cono/flecha del
    # popup) y en la tabla del Top
    assert marker["azimuts"], "El marcador no trae azimuts"
    az_degs = {a["deg"] for a in marker["azimuts"]}
    assert az_degs == {45, 90}
    assert "Azimut 45: 3 veces" in html

    # E. heatmap sigue presente
    assert 'id="heatmap-actividad"' in html
    assert "L.heatLayer(heatData" in html
    heat_match = re.search(r"const heatData = (\[.*?\]);", html, re.DOTALL)
    assert heat_match and json.loads(heat_match.group(1))

    # badge de sitio inferido visible en la sección del Top
    assert "Inferido por coordenadas" in html


# ─────────────────────────────────────────────────────────────────────────
# Caso A — control: antena explícita, sin regresión
# ─────────────────────────────────────────────────────────────────────────

def test_antena_explicita_sigue_generando_pin_sin_regresion(tmp_path):
    df = agregar_sitio_analitico(_df_base(rows=4, antena="ANT-01"))
    html = _generar_html(df, tmp_path, "antena_real")

    assert "ANT-01" in html
    assert SITIO_ID not in html
    assert "Inferido por coordenadas" not in html

    markers = _extract_markers(html)
    ant_markers = [m for m in markers if m.get("name") == "ANT-01"]
    assert len(ant_markers) == 1
    marker = ant_markers[0]
    assert marker["count"] == 4
    az_degs = {a["deg"] for a in marker["azimuts"]}
    assert az_degs == {45, 90}

    assert 'id="heatmap-actividad"' in html
    assert "L.heatLayer(heatData" in html
