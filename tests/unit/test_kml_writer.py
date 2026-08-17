"""Tests unitarios de tz_core/kml_writer.py — writer KML/KMZ stdlib-only.

Bloque P1-SIMPLEKML-WRITER. Verifica el writer AISLADO (sin negocio de
kml_generator.py): estructura XML, namespaces, estilos compartidos,
ScreenOverlay, addfile/save/savekmz y escaping semántico frente a simplekml
(oracle legacy, instalado en paralelo).
"""
from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET

import simplekml as sk

from tz_core.kml_writer import (
    Kml,
    Style,
    OverlayXY,
    ScreenXY,
    Size,
    Units,
)

from tests.kml_assertions import (
    KML_NS,
    count_geometry,
    extract_kml_from_kmz,
    get_coord_tuples,
    get_screenoverlay_dict,
    parse_kml,
    resolve_style_element,
)


# ── 1. ROOT / NAMESPACES ─────────────────────────────────────────────────

def test_root_namespace_kml_default(tmp_path):
    kml = Kml()
    kml.newpoint(name="P", coords=[(-89.2, 13.7)])
    out = str(tmp_path / "root.kml")
    kml.save(out)

    text = open(out, "r", encoding="utf-8").read()
    assert 'xmlns="http://www.opengis.net/kml/2.2"' in text

    root = parse_kml(text)
    assert root.tag == f"{{{KML_NS}}}kml"
    doc = root.find(f"{{{KML_NS}}}Document")
    assert doc is not None, "Falta <Document> como raíz de features"


# ── 2. FOLDER NESTING / OPEN / DESCRIPTION ───────────────────────────────

def test_folder_nesting_open_description(tmp_path):
    kml = Kml()
    raiz = kml.newfolder(name="raiz")
    raiz.open = 0
    hijo = raiz.newfolder(name="hijo")
    hijo.open = 1
    hijo.description = "desc hijo"

    out = str(tmp_path / "folders.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    folders = root.findall(f".//{{{KML_NS}}}Folder")
    assert len(folders) == 2

    raiz_el = folders[0]
    assert raiz_el.find(f"{{{KML_NS}}}name").text == "raiz"
    assert raiz_el.find(f"{{{KML_NS}}}open").text == "0"

    hijo_el = raiz_el.find(f"{{{KML_NS}}}Folder")
    assert hijo_el is not None, "El folder hijo debe anidarse dentro del padre"
    assert hijo_el.find(f"{{{KML_NS}}}name").text == "hijo"
    assert hijo_el.find(f"{{{KML_NS}}}open").text == "1"
    assert hijo_el.find(f"{{{KML_NS}}}description").text == "desc hijo"


# ── 3. POINT ──────────────────────────────────────────────────────────────

def test_point_coords_y_name(tmp_path):
    kml = Kml()
    p = kml.newpoint(name="Antena", coords=[(-89.2, 13.7)])
    p.description = "burbuja"

    out = str(tmp_path / "point.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    g = count_geometry(root)
    assert g["points"] == 1

    pm = root.find(f".//{{{KML_NS}}}Placemark")
    assert pm.find(f"{{{KML_NS}}}name").text == "Antena"
    assert pm.find(f"{{{KML_NS}}}description").text == "burbuja"

    point_el = pm.find(f"{{{KML_NS}}}Point")
    coords = get_coord_tuples(point_el)
    assert coords == [(-89.2, 13.7)]


# ── 4. POLYGON ────────────────────────────────────────────────────────────

def test_polygon_outerboundaryis(tmp_path):
    kml = Kml()
    pol = kml.newpolygon(name="Cono")
    pol.outerboundaryis = [(-89.2, 13.7), (-89.21, 13.71), (-89.22, 13.72)]

    out = str(tmp_path / "polygon.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    g = count_geometry(root)
    assert g["polygons"] == 1

    pol_el = root.find(f".//{{{KML_NS}}}Polygon")
    coords = get_coord_tuples(pol_el)
    assert coords == [(-89.2, 13.7), (-89.21, 13.71), (-89.22, 13.72)]

    # El writer no cierra el polígono ni normaliza — refleja exactamente lo recibido
    assert coords[0] != coords[-1]


# ── 5. LINESTRING ─────────────────────────────────────────────────────────

def test_linestring_dos_puntos(tmp_path):
    kml = Kml()
    ls = kml.newlinestring(name="Azimut", coords=[(-89.2, 13.7), (-89.19, 13.71)])

    out = str(tmp_path / "line.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    g = count_geometry(root)
    assert g["linestrings"] == 1

    ls_el = root.find(f".//{{{KML_NS}}}LineString")
    coords = get_coord_tuples(ls_el)
    assert coords == [(-89.2, 13.7), (-89.19, 13.71)]


# ── 6. SHARED STYLE / STYLEURL ───────────────────────────────────────────

def test_shared_style_una_sola_vez_y_styleurl_en_cada_placemark(tmp_path):
    kml = Kml()
    estilo = Style()
    estilo.iconstyle.color = "ff00ffff"
    estilo.iconstyle.scale = 1.1
    estilo.iconstyle.icon.href = "files/pin.png"
    estilo.labelstyle.color = "ff00ffff"
    estilo.labelstyle.scale = 1.2

    f1 = kml.newfolder(name="F1")
    p1 = f1.newpoint(name="P1", coords=[(-89.2, 13.7)])
    p1.style = estilo

    f2 = f1.newfolder(name="F2")
    p2 = f2.newpoint(name="P2", coords=[(-89.21, 13.71)])
    p2.style = estilo  # mismo objeto -> debe deduplicarse

    out = str(tmp_path / "shared_style.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    style_els = root.findall(f".//{{{KML_NS}}}Style")
    assert len(style_els) == 1, "El Style compartido debe emitirse una sola vez"

    placemarks = root.findall(f".//{{{KML_NS}}}Placemark")
    assert len(placemarks) == 2
    for pm in placemarks:
        estilo_resuelto = resolve_style_element(root, pm)
        assert estilo_resuelto is not None
        assert estilo_resuelto.find(f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}color").text == "ff00ffff"
        assert estilo_resuelto.find(f"{{{KML_NS}}}LabelStyle/{{{KML_NS}}}scale").text == "1.2"


def test_style_individual_por_placemark_no_se_comparte(tmp_path):
    kml = Kml()
    p1 = kml.newpoint(name="P1", coords=[(-89.2, 13.7)])
    p1.style.iconstyle.icon.href = "files/a.png"
    p1.style.iconstyle.scale = 1.2

    p2 = kml.newpoint(name="P2", coords=[(-89.21, 13.71)])
    p2.style.iconstyle.icon.href = "files/b.png"

    out = str(tmp_path / "individual_style.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    style_els = root.findall(f".//{{{KML_NS}}}Style")
    assert len(style_els) == 2, "Estilos auto-creados por placemark distinto no deben compartirse"

    placemarks = root.findall(f".//{{{KML_NS}}}Placemark")
    href_p1 = resolve_style_element(root, placemarks[0]).find(
        f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}Icon/{{{KML_NS}}}href"
    ).text
    href_p2 = resolve_style_element(root, placemarks[1]).find(
        f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}Icon/{{{KML_NS}}}href"
    ).text
    assert href_p1 == "files/a.png"
    assert href_p2 == "files/b.png"


# ── 7. SCREENOVERLAY ──────────────────────────────────────────────────────

def test_screenoverlay_atributos_exactos(tmp_path):
    kml = Kml()
    overlay = kml.newscreenoverlay(name="Representación orientativa")
    overlay.icon.href = "files/kmz_aviso_orientativo.png"
    overlay.overlayxy = OverlayXY(x=0, y=1, xunits=Units.fraction, yunits=Units.fraction)
    overlay.screenxy = ScreenXY(x=0.01, y=0.96, xunits=Units.fraction, yunits=Units.fraction)
    overlay.size = Size(x=360, y=60, xunits=Units.pixels, yunits=Units.pixels)

    out = str(tmp_path / "overlay.kml")
    kml.save(out)
    root = parse_kml(open(out, encoding="utf-8").read())

    overlay_dict = get_screenoverlay_dict(root)
    assert overlay_dict["name"] == "Representación orientativa"
    assert overlay_dict["icon_href"] == "files/kmz_aviso_orientativo.png"
    assert overlay_dict["overlayxy"] == {"x": 0.0, "y": 1.0, "xunits": "fraction", "yunits": "fraction"}
    assert overlay_dict["screenxy"] == {"x": 0.01, "y": 0.96, "xunits": "fraction", "yunits": "fraction"}
    assert overlay_dict["size"] == {"x": 360.0, "y": 60.0, "xunits": "pixels", "yunits": "pixels"}


# ── 8. ADDFILE ────────────────────────────────────────────────────────────

def test_addfile_devuelve_ruta_files_basename(tmp_path):
    kml = Kml()
    fake_asset = tmp_path / "algun_icono.png"
    fake_asset.write_bytes(b"\x89PNG\r\n")

    href = kml.addfile(str(fake_asset))
    assert href == "files/algun_icono.png"
    assert kml._files == [(str(fake_asset), "files/algun_icono.png")]


# ── 9. SAVEKMZ ────────────────────────────────────────────────────────────

def test_savekmz_doc_kml_y_assets_zip_deflated(tmp_path):
    kml = Kml()
    asset_path = tmp_path / "icono.png"
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    href = kml.addfile(str(asset_path))

    pnt = kml.newpoint(name="P", coords=[(-89.2, 13.7)])
    pnt.style.iconstyle.icon.href = href

    kmz_path = str(tmp_path / "salida.kmz")
    kml.savekmz(kmz_path)

    with zipfile.ZipFile(kmz_path, "r") as zf:
        names = zf.namelist()
        assert names[0] == "doc.kml", "doc.kml debe ser el primer entry del ZIP"
        assert "files/icono.png" in names
        info = zf.getinfo("doc.kml")
        assert info.compress_type == zipfile.ZIP_DEFLATED

    root = parse_kml(extract_kml_from_kmz(kmz_path))
    g = count_geometry(root)
    assert g["points"] == 1


# ── 10. SAVE PLANO ────────────────────────────────────────────────────────

def test_save_plano_no_genera_zip(tmp_path):
    kml = Kml()
    kml.newpoint(name="P", coords=[(-89.2, 13.7)])

    out = str(tmp_path / "plano.kml")
    kml.save(out)

    assert os.path.exists(out)
    assert not zipfile.is_zipfile(out), "save() debe escribir XML plano, nunca un ZIP"
    with open(out, "rb") as f:
        head = f.read(5)
    assert head == b"<?xml"


# ── 11. ESCAPING SEMÁNTICO (writer vs legacy) ─────────────────────────────

_ADVERSARIAL = 'Nombre <adversarial> & "quoted" \'single\' texto'
_ADVERSARIAL_DESC = 'desc & < > " \' <b>markup real</b>'


def _legacy_xml(name, description):
    kml = sk.Kml()
    p = kml.newpoint(name=name, coords=[(-89.2, 13.7)])
    p.description = description
    return kml.kml()


def _writer_xml(tmp_path, filename, name, description):
    kml = Kml()
    p = kml.newpoint(name=name, coords=[(-89.2, 13.7)])
    p.description = description
    out = str(tmp_path / filename)
    kml.save(out)
    return open(out, encoding="utf-8").read()


def test_escaping_semantico_coincide_con_legacy(tmp_path):
    legacy_root = parse_kml(_legacy_xml(_ADVERSARIAL, _ADVERSARIAL_DESC))
    writer_root = parse_kml(_writer_xml(tmp_path, "esc.kml", _ADVERSARIAL, _ADVERSARIAL_DESC))

    legacy_pm = legacy_root.find(f".//{{{KML_NS}}}Placemark")
    writer_pm = writer_root.find(f".//{{{KML_NS}}}Placemark")

    legacy_name = legacy_pm.find(f"{{{KML_NS}}}name").text
    writer_name = writer_pm.find(f"{{{KML_NS}}}name").text
    assert writer_name == legacy_name == _ADVERSARIAL

    legacy_desc = legacy_pm.find(f"{{{KML_NS}}}description").text
    writer_desc = writer_pm.find(f"{{{KML_NS}}}description").text
    assert writer_desc == legacy_desc == _ADVERSARIAL_DESC


def test_escaping_sin_doble_escape_observable(tmp_path):
    # Un valor ya escapado por security_escaping.esc_kml_value (html.escape)
    # antes de llegar al writer no debe volver a escaparse.
    ya_escapado = "Juan &amp; Maria"
    text = _writer_xml(tmp_path, "no_doble_escape.kml", "N", ya_escapado)

    # En el XML crudo, el '&' de "&amp;" debe escaparse una sola vez (a
    # &amp;amp;) — igual que simplekml — y el texto parseado debe reproducir
    # exactamente el string original (una sola capa de escape residual).
    root = parse_kml(text)
    desc = root.find(f".//{{{KML_NS}}}description").text
    assert desc == ya_escapado
