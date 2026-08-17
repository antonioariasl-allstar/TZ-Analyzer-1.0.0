"""Helpers de test para inspeccionar KML/KMZ por XML final — agnósticos del
serializer de producción (hoy simplekml, mañana lo que sea).

Uso exclusivo de tests: nunca importar desde tz_core/tz_web. No es un
framework KML de producción — solo lectura/parseo mínimo para aserciones.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"
NS = {"kml": KML_NS, "gx": GX_NS}


def extract_kml_from_kmz(kmz_path) -> str:
    """Extrae el contenido de doc.kml de un KMZ como texto UTF-8.

    Exige que el KMZ contenga doc.kml en la raíz del ZIP (contrato actual —
    ver SPEC_OPERATIVA_KMZ), no cualquier archivo *.kml.
    """
    with zipfile.ZipFile(kmz_path, "r") as z:
        names = z.namelist()
        assert "doc.kml" in names, f"KMZ sin doc.kml en la raíz: {names}"
        with z.open("doc.kml") as f:
            return f.read().decode("utf-8")


def parse_kml(source):
    """Parsea KML y devuelve el elemento raíz <kml>.

    Acepta:
      - un Path/str a un archivo .kml existente;
      - un string con contenido XML (se detecta si, tras strip(), empieza
        con '<').
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    elif isinstance(source, str) and not source.lstrip().startswith("<"):
        with open(source, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = source
    return ET.fromstring(text)


def count_geometry(root) -> dict:
    """Cuenta geometrías reales (Point/LineString/Polygon) bajo `root`."""
    return {
        "points": len(root.findall(f".//{{{KML_NS}}}Point")),
        "linestrings": len(root.findall(f".//{{{KML_NS}}}LineString")),
        "polygons": len(root.findall(f".//{{{KML_NS}}}Polygon")),
    }


def get_coord_tuples(geom_el) -> list[tuple[float, float]]:
    """Devuelve [(lon, lat), ...] leídos del primer <coordinates> bajo
    `geom_el` (Point/LineString/Polygon o cualquier ancestro directo)."""
    coord_el = geom_el.find(f".//{{{KML_NS}}}coordinates")
    if coord_el is None or not coord_el.text:
        return []
    tuples = []
    for chunk in coord_el.text.split():
        parts = chunk.strip().split(",")
        if len(parts) >= 2:
            tuples.append((float(parts[0]), float(parts[1])))
    return tuples


def get_screenoverlay_dict(root) -> dict:
    """Extrae name/icon href/overlayXY/screenXY/size del primer
    ScreenOverlay del documento."""
    overlay = root.find(f".//{{{KML_NS}}}ScreenOverlay")
    assert overlay is not None, "No se encontró ScreenOverlay en el KML"

    def _xy(tag):
        el = overlay.find(f"{{{KML_NS}}}{tag}")
        if el is None:
            return None
        return {
            "x": float(el.get("x")),
            "y": float(el.get("y")),
            "xunits": el.get("xunits"),
            "yunits": el.get("yunits"),
        }

    name_el = overlay.find(f"{{{KML_NS}}}name")
    href_el = overlay.find(f"{{{KML_NS}}}Icon/{{{KML_NS}}}href")
    return {
        "name": name_el.text if name_el is not None else None,
        "icon_href": href_el.text if href_el is not None else None,
        "overlayxy": _xy("overlayXY"),
        "screenxy": _xy("screenXY"),
        "size": _xy("size"),
    }


def resolve_style_element(root, placemark_el):
    """Resuelve el <Style> real de un Placemark/feature: sigue su
    <styleUrl> si lo tiene (shared style), o devuelve su <Style> inline.

    Semántico a propósito (no depende de IDs simplekml): el futuro writer
    puede usar shared style o inline style indistintamente.
    """
    styleurl_el = placemark_el.find(f"{{{KML_NS}}}styleUrl")
    if styleurl_el is not None and styleurl_el.text:
        style_id = styleurl_el.text.lstrip("#")
        for style_el in root.findall(f".//{{{KML_NS}}}Style"):
            if style_el.get("id") == style_id:
                return style_el
        return None
    return placemark_el.find(f"{{{KML_NS}}}Style")
