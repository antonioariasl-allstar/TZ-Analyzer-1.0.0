"""Contrato KML/KMZ congelado — P1-SIMPLEKML-GOLDEN.

Complementa (no sustituye) tests/golden/kml_normalized.txt. Estos tests
verifican el PRODUCTO FINAL (XML/KMZ real) usando tests/kml_assertions.py,
nunca objetos internos de simplekml, para que sobrevivan a la sustitución
del serializer.

Valores de contrato productivo (config.json["kml"]):
  azimuth_km = 1.5 km
  half_degrees = 35°
"""
from __future__ import annotations

import math
import os
import zipfile

import pandas as pd

from tz_core.color_utils import hex_to_kml_color
from tz_core.geo_utils import calcular_punto_final, resolve_azimuth_cone_geometry
from tz_core.kml_generator import generar_kml, generar_kml_puntos_libres

from tests.kml_assertions import (
    KML_NS,
    count_geometry,
    extract_kml_from_kmz,
    get_coord_tuples,
    get_screenoverlay_dict,
    parse_kml,
    resolve_style_element,
)

ABS_TOL_DEG = 1e-7

# Config de contrato productivo — ver config.json["kml"]. Los tests nuevos
# de este archivo congelan comportamiento productivo real, no overrides.
_CONFIG = {
    "kml": {"azimuth_km": 1.5, "cone": {"half_degrees": 35}},
    "style": {"theme_hex": "#ff00ff"},
    "salida": {"solo_kmz": True},
}

_LAT = 13.7
_LON = -89.2
_AZ = 90.0


def _reset_kml_globals():
    import tz_core.kml_generator as kml_mod

    kml_mod._REUSABLE_STYLES = None
    kml_mod._ICON_HREF = None


def _generar_kmz(df, tmp_path, config=None, flat=False):
    _reset_kml_globals()
    out = str(tmp_path / "contrato.kml")
    generar_kml(df, out, config or _CONFIG, flat=flat)
    kmz_path = os.path.splitext(out)[0] + ".kmz"
    return kmz_path


def _df_una_antena(azimut=_AZ):
    return pd.DataFrame({
        "fecha": ["10/01/2026"],
        "hora": ["09:00:00"],
        "lat": [_LAT],
        "long": [_LON],
        "antena": ["ANTENA-CONTRATO"],
        "azimut": [azimut],
    })


def _placemark_por_nombre(root, nombre_exacto=None, nombre_prefijo=None):
    for pm in root.findall(f".//{{{KML_NS}}}Placemark"):
        name_el = pm.find(f"{{{KML_NS}}}name")
        if name_el is None or not name_el.text:
            continue
        if nombre_exacto is not None and name_el.text == nombre_exacto:
            return pm
        if nombre_prefijo is not None and name_el.text.startswith(nombre_prefijo):
            return pm
    return None


# ── SCREENOVERLAY — P0 ───────────────────────────────────────────────────

def test_screenoverlay_contrato_p0(tmp_path):
    """ScreenOverlay permanente: name/href/overlayXY/screenXY/size exactos,
    y el asset referenciado existe físicamente dentro del ZIP."""
    kmz_path = _generar_kmz(_df_una_antena(), tmp_path)

    with zipfile.ZipFile(kmz_path, "r") as z:
        names = z.namelist()
    assert "files/kmz_aviso_orientativo.png" in names, (
        "El asset del ScreenOverlay no está físicamente dentro del KMZ"
    )

    root = parse_kml(extract_kml_from_kmz(kmz_path))
    overlay = get_screenoverlay_dict(root)

    assert overlay["name"] == "Representación orientativa"
    assert overlay["icon_href"] == "files/kmz_aviso_orientativo.png"

    assert overlay["overlayxy"] == {"x": 0.0, "y": 1.0, "xunits": "fraction", "yunits": "fraction"}
    assert overlay["screenxy"] == {"x": 0.01, "y": 0.96, "xunits": "fraction", "yunits": "fraction"}
    assert overlay["size"] == {"x": 360.0, "y": 60.0, "xunits": "pixels", "yunits": "pixels"}


# ── SECTOR — P0 ──────────────────────────────────────────────────────────

def test_sector_16_coordenadas_coinciden_con_geometria_productiva(tmp_path):
    """Sector (cono): 16 coordenadas totales — 15 puntos de arco (±35° cada
    5°) + centro de antena al final, sin repetir el primer punto del arco.

    Las coordenadas esperadas se calculan con las MISMAS funciones
    geográficas productivas (calcular_punto_final / resolve_azimuth_cone_geometry),
    nunca duplicando la matemática geodésica en el test.
    """
    kmz_path = _generar_kmz(_df_una_antena(azimut=_AZ), tmp_path)
    root = parse_kml(extract_kml_from_kmz(kmz_path))

    sector_pm = _placemark_por_nombre(root, nombre_prefijo="Cono Azimut")
    assert sector_pm is not None, "No se encontró el Placemark del sector (Cono Azimut)"
    polygon_el = sector_pm.find(f"{{{KML_NS}}}Polygon")
    assert polygon_el is not None, "El Placemark del sector no contiene un Polygon"

    coords = get_coord_tuples(polygon_el)
    assert len(coords) == 16, f"Esperadas 16 coordenadas en el sector, se obtuvieron {len(coords)}"

    az_dist_km, cone_half = resolve_azimuth_cone_geometry(_CONFIG)
    assert (az_dist_km, cone_half) == (1.5, 35), "Precondición de contrato: 1.5 km / 35°"

    esperado_arco = [
        calcular_punto_final(_LAT, _LON, _AZ + ang, az_dist_km)
        for ang in range(-cone_half, cone_half + 1, 5)
    ]
    assert len(esperado_arco) == 15

    for i, (lat_esp, lon_esp) in enumerate(esperado_arco):
        lon_obs, lat_obs = coords[i]
        assert math.isclose(lon_obs, lon_esp, abs_tol=ABS_TOL_DEG), f"Arco[{i}] lon difiere"
        assert math.isclose(lat_obs, lat_esp, abs_tol=ABS_TOL_DEG), f"Arco[{i}] lat difiere"

    lon_centro, lat_centro = coords[-1]
    assert math.isclose(lon_centro, _LON, abs_tol=ABS_TOL_DEG), "Último punto no es el centro (lon)"
    assert math.isclose(lat_centro, _LAT, abs_tol=ABS_TOL_DEG), "Último punto no es el centro (lat)"

    assert coords[-1] != coords[0], (
        "El último punto no debe repetir el primer punto del arco "
        "(el sector no se cierra como el círculo — comportamiento actual, no 'corregir')"
    )


# ── LÍNEA DE AZIMUT — geometría real ─────────────────────────────────────

def test_linea_azimut_2_puntos_coherente_con_1_5km(tmp_path):
    """La LineString de azimut tiene exactamente 2 puntos: origen (antena) y
    punto final calculado con calcular_punto_final() a 1.5 km / azimut."""
    kmz_path = _generar_kmz(_df_una_antena(azimut=_AZ), tmp_path)
    root = parse_kml(extract_kml_from_kmz(kmz_path))

    linea_pm = _placemark_por_nombre(root, nombre_prefijo="Azimut")
    assert linea_pm is not None, "No se encontró el Placemark de la línea de azimut"
    line_el = linea_pm.find(f"{{{KML_NS}}}LineString")
    assert line_el is not None, "El Placemark de azimut no contiene un LineString"

    coords = get_coord_tuples(line_el)
    assert len(coords) == 2, f"Esperados 2 puntos en la línea de azimut, se obtuvieron {len(coords)}"

    az_dist_km, _ = resolve_azimuth_cone_geometry(_CONFIG)
    assert az_dist_km == 1.5

    lat_final_esp, lon_final_esp = calcular_punto_final(_LAT, _LON, _AZ, az_dist_km)

    lon_origen, lat_origen = coords[0]
    assert math.isclose(lon_origen, _LON, abs_tol=ABS_TOL_DEG)
    assert math.isclose(lat_origen, _LAT, abs_tol=ABS_TOL_DEG)

    lon_final, lat_final = coords[1]
    assert math.isclose(lon_final, lon_final_esp, abs_tol=ABS_TOL_DEG)
    assert math.isclose(lat_final, lat_final_esp, abs_tol=ABS_TOL_DEG)


# ── COLORES — LineStyle de la línea de azimut (hueco no cubierto por
#    test_kmz_pin_marker_regresion.py::test_k, que verifica pin/circulo/cono
#    pero no la línea de azimut) ─────────────────────────────────────────

def test_linea_azimut_color_coincide_con_theme(tmp_path):
    kmz_path = _generar_kmz(_df_una_antena(azimut=_AZ), tmp_path)
    root = parse_kml(extract_kml_from_kmz(kmz_path))

    linea_pm = _placemark_por_nombre(root, nombre_prefijo="Azimut")
    assert linea_pm is not None
    estilo = resolve_style_element(root, linea_pm)
    assert estilo is not None, "No se pudo resolver el Style de la línea de azimut"

    color_el = estilo.find(f"{{{KML_NS}}}LineStyle/{{{KML_NS}}}color")
    assert color_el is not None and color_el.text
    esperado = hex_to_kml_color(_CONFIG["style"]["theme_hex"], 255)
    assert color_el.text.lower() == esperado


# ── FLAT MODE — diferencia estructural propia (sin carpetas) ────────────

def test_flat_mode_sin_carpetas_puntos_en_raiz(tmp_path):
    """flat=True: todos los puntos en raíz, CERO <Folder>. Complementa la
    cobertura de geometría/colores/pin ya existente en
    test_kmz_pin_marker_regresion.py (que cubre un único registro) probando
    la diferencia estructural definitoria de flat=True con varios registros."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "10/01/2026", "11/01/2026"],
        "hora":   ["09:00:00",   "10:00:00",   "08:00:00"],
        "lat":    [13.70,        13.71,        13.72],
        "long":   [-89.20,       -89.21,       -89.22],
        "antena": ["FLAT-A",     "FLAT-B",     "FLAT-C"],
        "azimut": [10,           20,           30],
    })
    kmz_path = _generar_kmz(df, tmp_path, flat=True)
    root = parse_kml(extract_kml_from_kmz(kmz_path))

    folders = root.findall(f".//{{{KML_NS}}}Folder")
    assert folders == [], f"flat=True no debe generar carpetas, se encontraron {len(folders)}"

    g = count_geometry(root)
    assert g["points"] == 3, "Un Point por registro en modo flat"


# ── PUNTOS LIBRES — estructura propia ────────────────────────────────────

def test_puntos_libres_estructura_kmz(tmp_path):
    """generar_kml_puntos_libres(): KMZ válido, un Point por registro válido,
    sin círculo ni sector (solo pines), asset de pin correcto.

    Complementa test_kml_implementation.py (contenido de burbuja) y
    test_kmz_pin_marker_regresion.py::test_d (asset del pin) con el conteo
    estructural de geometrías que ninguno de los dos verifica.
    """
    df = pd.DataFrame({
        "lat": [13.7, 13.71],
        "long": [-89.2, -89.21],
        "antena": ["LIBRE-A", "LIBRE-B"],
        "detalle": ["Detalle A", None],
        "direccion": [None, "Calle B"],
    })
    out = str(tmp_path / "libres.kml")
    kmz_path, descartadas = generar_kml_puntos_libres(df, out, _CONFIG)
    assert descartadas == 0
    assert kmz_path and os.path.exists(kmz_path)

    with zipfile.ZipFile(kmz_path, "r") as z:
        names = z.namelist()
    assert "doc.kml" in names
    assert "files/kml_point_icon.png" in names, "Asset de pin ausente en el KMZ de puntos libres"

    root = parse_kml(extract_kml_from_kmz(kmz_path))
    g = count_geometry(root)
    assert g["points"] == 2, "Un Point por registro válido"
    assert g["polygons"] == 0, "Puntos libres no debe generar círculo/sector"
    assert g["linestrings"] == 0, "Puntos libres no debe generar línea de azimut"
