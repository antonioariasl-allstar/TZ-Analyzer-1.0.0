"""Equivalencia LEGACY (simplekml) vs WRITER (tz_core.kml_writer) — P1-SIMPLEKML-WRITER.

Ejecuta el MISMO código de negocio (tz_core.kml_generator, sin modificar) dos
veces sobre el mismo DataFrame/config: una vez con tz_core.kml_generator.Kml/sk
parchados (monkeypatch, solo dentro de este test) para apuntar al oracle
legacy simplekml, y otra vez sin parchar — productivo/NEW, que desde
P1-SIMPLEKML-SWITCH usa tz_core.kml_writer por defecto.

No recrea manualmente geometría/estilos/descripciones — solo compara los dos
productos finales por semántica XML (nunca objetos internos de simplekml),
usando tests/kml_assertions.py, para sobrevivir a la sustitución del
serializer.

Config de contrato productivo (igual que test_kml_golden_contract.py):
  azimuth_km = 1.5 km
  half_degrees = 35°
"""
from __future__ import annotations

import math
import os
import time
import zipfile

import pandas as pd
import simplekml

import tz_core.kml_generator as kml_mod
from tz_core.kml_generator import generar_kml, generar_kml_puntos_libres

from tests.kml_assertions import (
    KML_NS,
    count_geometry,
    extract_kml_from_kmz,
    get_coord_tuples,
    parse_kml,
    resolve_style_element,
)

ABS_TOL_DEG = 1e-7

_CONFIG = {
    "kml": {"azimuth_km": 1.5, "cone": {"half_degrees": 35}, "incluir_por_rango_horario": True},
    "style": {"theme_hex": "#ff00ff"},
    "salida": {"solo_kmz": True},
    "top_antenas": 2,
}


# ── INFRAESTRUCTURA DE EQUIVALENCIA ──────────────────────────────────────

def _reset_kml_globals():
    kml_mod._REUSABLE_STYLES = None
    kml_mod._ICON_HREF = None


def _use_legacy_backend(monkeypatch):
    """Parcha tz_core.kml_generator.Kml/sk para apuntar al oracle legacy simplekml.

    Únicamente dentro del test que lo invoca — se revierte con
    ``monkeypatch.undo()`` antes de generar el producto productivo/NEW (sin
    parche), o al finalizar el test. kml_generator.py permanece sin
    modificar: los únicos usos de Kml/sk. son los ya inventariados en
    P1-SIMPLEKML-WRITER (Style, OverlayXY, ScreenXY, Size, Units) — todos
    cubiertos también por simplekml.
    """
    monkeypatch.setattr(kml_mod, "Kml", simplekml.Kml)
    monkeypatch.setattr(kml_mod, "sk", simplekml)


def _generar_kmz(df, tmp_path, filename, config=None, flat=False, subdir="out"):
    """`filename` se mantiene idéntico entre legacy/writer (subdir distinto):
    el nombre de la carpeta raíz del KML se deriva del nombre de archivo
    (ver generar_kml), así que debe coincidir para que la comparación de
    equivalencia no confunda una diferencia de fixture con una del writer.
    """
    _reset_kml_globals()
    out_dir = tmp_path / subdir
    out_dir.mkdir(exist_ok=True)
    out = str(out_dir / filename)
    generar_kml(df, out, config or _CONFIG, flat=flat)
    return os.path.splitext(out)[0] + ".kmz"


def _generar_puntos_libres_kmz(df, tmp_path, filename, config=None, subdir="out"):
    _reset_kml_globals()
    out_dir = tmp_path / subdir
    out_dir.mkdir(exist_ok=True)
    out = str(out_dir / filename)
    kmz_path, descartadas = generar_kml_puntos_libres(df, out, config or _CONFIG)
    return kmz_path, descartadas


# ── COMPARACIÓN SEMÁNTICA (sin depender de IDs/whitespace/orden de Style) ─

def _children_elements(el):
    relevant = {f"{{{KML_NS}}}Folder", f"{{{KML_NS}}}Placemark", f"{{{KML_NS}}}ScreenOverlay"}
    return [c for c in el if c.tag in relevant]


def _text_or_none(el, tag):
    child = el.find(f"{{{KML_NS}}}{tag}")
    return child.text if child is not None else None


def _style_fields(style_el):
    def _t(path):
        el = style_el.find(path) if style_el is not None else None
        return el.text if el is not None else None

    return {
        "icon_color": _t(f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}color"),
        "icon_scale": _t(f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}scale"),
        "icon_href": _t(f"{{{KML_NS}}}IconStyle/{{{KML_NS}}}Icon/{{{KML_NS}}}href"),
        "label_color": _t(f"{{{KML_NS}}}LabelStyle/{{{KML_NS}}}color"),
        "label_scale": _t(f"{{{KML_NS}}}LabelStyle/{{{KML_NS}}}scale"),
        "line_color": _t(f"{{{KML_NS}}}LineStyle/{{{KML_NS}}}color"),
        "line_width": _t(f"{{{KML_NS}}}LineStyle/{{{KML_NS}}}width"),
        "poly_color": _t(f"{{{KML_NS}}}PolyStyle/{{{KML_NS}}}color"),
        "poly_fill": _t(f"{{{KML_NS}}}PolyStyle/{{{KML_NS}}}fill"),
        "poly_outline": _t(f"{{{KML_NS}}}PolyStyle/{{{KML_NS}}}outline"),
    }


def _assert_same_style(legacy_root, legacy_pm, writer_root, writer_pm, path):
    legacy_style = resolve_style_element(legacy_root, legacy_pm)
    writer_style = resolve_style_element(writer_root, writer_pm)
    if legacy_style is None and writer_style is None:
        return
    assert legacy_style is not None and writer_style is not None, (
        f"presencia de Style distinta en {path}"
    )
    lf = _style_fields(legacy_style)
    wf = _style_fields(writer_style)
    for key in lf:
        lv, wv = lf[key], wf[key]
        if lv is None or wv is None:
            assert lv == wv, f"{key} presencia distinta en {path}: legacy={lv!r} writer={wv!r}"
            continue
        try:
            assert math.isclose(float(lv), float(wv), rel_tol=1e-9, abs_tol=1e-9), (
                f"{key} distinto en {path}: legacy={lv!r} writer={wv!r}"
            )
        except ValueError:
            assert lv == wv, f"{key} distinto en {path}: legacy={lv!r} writer={wv!r}"


def _assert_same_geometry(legacy_pm, writer_pm, path):
    for geom_tag in ("Point", "LineString", "Polygon"):
        l_geom = legacy_pm.find(f"{{{KML_NS}}}{geom_tag}")
        w_geom = writer_pm.find(f"{{{KML_NS}}}{geom_tag}")
        assert (l_geom is None) == (w_geom is None), f"tipo de geometría distinto en {path} ({geom_tag})"
        if l_geom is None:
            continue
        l_coords = get_coord_tuples(l_geom)
        w_coords = get_coord_tuples(w_geom)
        assert len(l_coords) == len(w_coords), (
            f"cantidad de coordenadas distinta en {path}: legacy={len(l_coords)} writer={len(w_coords)}"
        )
        for i, ((llon, llat), (wlon, wlat)) in enumerate(zip(l_coords, w_coords)):
            assert math.isclose(llon, wlon, abs_tol=ABS_TOL_DEG), f"lon distinta en {path}[{i}]"
            assert math.isclose(llat, wlat, abs_tol=ABS_TOL_DEG), f"lat distinta en {path}[{i}]"


def _screenoverlay_fields(overlay_el):
    def _xy(tag):
        el = overlay_el.find(f"{{{KML_NS}}}{tag}")
        if el is None:
            return None
        return {"x": float(el.get("x")), "y": float(el.get("y")), "xunits": el.get("xunits"), "yunits": el.get("yunits")}

    icon_el = overlay_el.find(f"{{{KML_NS}}}Icon")
    href_el = icon_el.find(f"{{{KML_NS}}}href") if icon_el is not None else None

    return {
        "name": _text_or_none(overlay_el, "name"),
        "icon_href": href_el.text if href_el is not None else None,
        "overlayxy": _xy("overlayXY"),
        "screenxy": _xy("screenXY"),
        "size": _xy("size"),
    }


def _assert_same_structure(legacy_el, writer_el, legacy_root, writer_root, path):
    l_tag = legacy_el.tag.split("}")[-1]
    w_tag = writer_el.tag.split("}")[-1]
    assert l_tag == w_tag, f"tag distinto en {path}: legacy={l_tag} writer={w_tag}"

    assert _text_or_none(legacy_el, "name") == _text_or_none(writer_el, "name"), f"name distinto en {path}"
    assert _text_or_none(legacy_el, "open") == _text_or_none(writer_el, "open"), f"open distinto en {path}"
    assert _text_or_none(legacy_el, "description") == _text_or_none(writer_el, "description"), (
        f"description distinta en {path}"
    )

    if l_tag == "Placemark":
        _assert_same_geometry(legacy_el, writer_el, path)
        _assert_same_style(legacy_root, legacy_el, writer_root, writer_el, path)
    elif l_tag == "ScreenOverlay":
        assert _screenoverlay_fields(legacy_el) == _screenoverlay_fields(writer_el), (
            f"ScreenOverlay distinto en {path}"
        )
    elif l_tag == "Folder":
        lc = _children_elements(legacy_el)
        wc = _children_elements(writer_el)
        assert len(lc) == len(wc), f"cantidad de hijos distinta en {path}: legacy={len(lc)} writer={len(wc)}"
        for i, (lch, wch) in enumerate(zip(lc, wc)):
            _assert_same_structure(lch, wch, legacy_root, writer_root, f"{path}/{l_tag}[{i}]")


def _assert_equivalent_kml(legacy_root, writer_root):
    legacy_doc = legacy_root.find(f"{{{KML_NS}}}Document")
    writer_doc = writer_root.find(f"{{{KML_NS}}}Document")
    assert legacy_doc is not None and writer_doc is not None, "Falta <Document> en alguno de los dos productos"

    lc = _children_elements(legacy_doc)
    wc = _children_elements(writer_doc)
    assert len(lc) == len(wc), f"cantidad de nodos raíz distinta: legacy={len(lc)} writer={len(wc)}"
    for i, (lch, wch) in enumerate(zip(lc, wc)):
        _assert_same_structure(lch, wch, legacy_root, writer_root, f"root[{i}]")


def _assert_same_assets(legacy_kmz, writer_kmz):
    with zipfile.ZipFile(legacy_kmz, "r") as lz, zipfile.ZipFile(writer_kmz, "r") as wz:
        legacy_assets = sorted(n for n in lz.namelist() if n != "doc.kml")
        writer_assets = sorted(n for n in wz.namelist() if n != "doc.kml")
        assert legacy_assets == writer_assets, (
            f"assets distintos: legacy={legacy_assets} writer={writer_assets}"
        )
        for name in legacy_assets:
            assert lz.read(name) == wz.read(name), f"contenido de asset distinto: {name}"


# ── FIXTURES DE DATOS ─────────────────────────────────────────────────────

def _df_carpetas():
    return pd.DataFrame({
        "fecha": ["10/01/2026", "10/01/2026", "11/01/2026", "11/01/2026", "11/01/2026"],
        "hora": ["09:00:00", "14:30:00", "08:00:00", "20:15:00", "02:45:00"],
        "lat": [13.70, 13.71, 13.70, 13.72, 13.73],
        "long": [-89.20, -89.21, -89.20, -89.22, -89.23],
        "antena": ["ANTENA-A", "ANTENA-B", "ANTENA-A", "ANTENA-C", "ANTENA-B"],
        "azimut": [10, 90, 10, 200, 90],
        "tel": ["70000001", "70000002", "70000001", "70000003", "70000002"],
        "imei": ["111111111111111", "222222222222222", "111111111111111", "333333333333333", "222222222222222"],
    })


def _df_flat():
    return pd.DataFrame({
        "fecha": ["10/01/2026", "10/01/2026", "11/01/2026"],
        "hora": ["09:00:00", "10:00:00", "08:00:00"],
        "lat": [13.70, 13.71, 13.72],
        "long": [-89.20, -89.21, -89.22],
        "antena": ["FLAT-A", "FLAT-B", "FLAT-C"],
        "azimut": [10, 20, 30],
    })


def _df_puntos_libres():
    return pd.DataFrame({
        "lat": [13.7, 13.71, 13.72],
        "long": [-89.2, -89.21, -89.22],
        "antena": ["LIBRE-A", "LIBRE-B", "LIBRE-C"],
        "detalle": ["Detalle A", None, "Detalle C"],
        "direccion": [None, "Calle B", "Calle C"],
    })


def _df_escaping_adversarial():
    return pd.DataFrame({
        "fecha": ["10/01/2026"],
        "hora": ["09:00:00"],
        "lat": [13.70],
        "long": [-89.20],
        "antena": ['Antena <adversarial> & "quoted" \'single\''],
        "azimut": [45],
        "tel": ["70000001"],
        "abonado": ['Nombre & Cía <script>alert(1)</script>'],
    })


# ── CASO 1: CARPETAS (flat=False) ─────────────────────────────────────────

def test_equivalencia_modo_carpetas(tmp_path, monkeypatch):
    df = _df_carpetas()

    _use_legacy_backend(monkeypatch)
    legacy_kmz = _generar_kmz(df, tmp_path, "carpetas.kml", flat=False, subdir="legacy")
    legacy_root = parse_kml(extract_kml_from_kmz(legacy_kmz))

    monkeypatch.undo()
    writer_kmz = _generar_kmz(df, tmp_path, "carpetas.kml", flat=False, subdir="writer")
    writer_root = parse_kml(extract_kml_from_kmz(writer_kmz))

    _assert_equivalent_kml(legacy_root, writer_root)
    _assert_same_assets(legacy_kmz, writer_kmz)

    g_legacy = count_geometry(legacy_root)
    g_writer = count_geometry(writer_root)
    assert g_legacy == g_writer
    assert g_legacy["points"] > 0


# ── CASO 2: FLAT ────────────────────────────────────────────────────────

def test_equivalencia_modo_flat(tmp_path, monkeypatch):
    df = _df_flat()

    _use_legacy_backend(monkeypatch)
    legacy_kmz = _generar_kmz(df, tmp_path, "flat.kml", flat=True, subdir="legacy")
    legacy_root = parse_kml(extract_kml_from_kmz(legacy_kmz))

    monkeypatch.undo()
    writer_kmz = _generar_kmz(df, tmp_path, "flat.kml", flat=True, subdir="writer")
    writer_root = parse_kml(extract_kml_from_kmz(writer_kmz))

    assert legacy_root.findall(f".//{{{KML_NS}}}Folder") == []
    assert writer_root.findall(f".//{{{KML_NS}}}Folder") == []

    _assert_equivalent_kml(legacy_root, writer_root)
    _assert_same_assets(legacy_kmz, writer_kmz)


# ── CASO 3: PUNTOS LIBRES ──────────────────────────────────────────────

def test_equivalencia_puntos_libres(tmp_path, monkeypatch):
    df = _df_puntos_libres()

    _use_legacy_backend(monkeypatch)
    legacy_kmz, legacy_desc = _generar_puntos_libres_kmz(df, tmp_path, "libres.kml", subdir="legacy")
    legacy_root = parse_kml(extract_kml_from_kmz(legacy_kmz))

    monkeypatch.undo()
    writer_kmz, writer_desc = _generar_puntos_libres_kmz(df, tmp_path, "libres.kml", subdir="writer")
    writer_root = parse_kml(extract_kml_from_kmz(writer_kmz))

    assert legacy_desc == writer_desc == 0

    _assert_equivalent_kml(legacy_root, writer_root)
    _assert_same_assets(legacy_kmz, writer_kmz)

    g_legacy = count_geometry(legacy_root)
    assert g_legacy["points"] == 3
    assert g_legacy["polygons"] == 0
    assert g_legacy["linestrings"] == 0


# ── CASO 4: ESCAPING ADVERSARIAL ────────────────────────────────────────

def test_equivalencia_escaping_adversarial(tmp_path, monkeypatch):
    df = _df_escaping_adversarial()

    _use_legacy_backend(monkeypatch)
    legacy_kmz = _generar_kmz(df, tmp_path, "escaping.kml", flat=True, subdir="legacy")
    legacy_root = parse_kml(extract_kml_from_kmz(legacy_kmz))

    monkeypatch.undo()
    writer_kmz = _generar_kmz(df, tmp_path, "escaping.kml", flat=True, subdir="writer")
    writer_root = parse_kml(extract_kml_from_kmz(writer_kmz))

    _assert_equivalent_kml(legacy_root, writer_root)

    legacy_pm = legacy_root.find(f".//{{{KML_NS}}}Placemark")
    writer_pm = writer_root.find(f".//{{{KML_NS}}}Placemark")
    assert "adversarial" in (_text_or_none(legacy_pm, "name") or "")
    assert _text_or_none(legacy_pm, "name") == _text_or_none(writer_pm, "name")
    assert _text_or_none(legacy_pm, "description") == _text_or_none(writer_pm, "description")


# ── B6: PERFORMANCE SANITY (diagnóstico, no benchmark formal) ───────────

def test_performance_sanity_legacy_vs_writer(tmp_path, monkeypatch, capsys):
    filas = 150
    df = pd.DataFrame({
        "fecha": ["10/01/2026"] * filas,
        "hora": [f"{h % 24:02d}:00:00" for h in range(filas)],
        "lat": [13.70 + i * 0.001 for i in range(filas)],
        "long": [-89.20 - i * 0.001 for i in range(filas)],
        "antena": [f"ANTENA-{i % 10}" for i in range(filas)],
        "azimut": [(i * 7) % 360 for i in range(filas)],
    })

    _use_legacy_backend(monkeypatch)
    t0 = time.perf_counter()
    legacy_kmz = _generar_kmz(df, tmp_path, "perf.kml", flat=True, subdir="legacy")
    t_legacy = time.perf_counter() - t0
    assert os.path.exists(legacy_kmz)

    monkeypatch.undo()
    t0 = time.perf_counter()
    writer_kmz = _generar_kmz(df, tmp_path, "perf.kml", flat=True, subdir="writer")
    t_writer = time.perf_counter() - t0
    assert os.path.exists(writer_kmz)

    ratio = (t_writer / t_legacy) if t_legacy > 0 else float("inf")
    with capsys.disabled():
        print(
            f"\n[PERF] legacy={t_legacy:.4f}s writer={t_writer:.4f}s "
            f"ratio={ratio:.2f}x (filas={filas})"
        )

    if t_legacy >= 0.02:  # evitar ruido de medición en fixtures muy chicas
        assert ratio < 5.0, f"STOP: writer >=5x más lento que legacy (ratio={ratio:.2f}x)"
