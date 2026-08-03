"""Tests implementación KMZ v1.1 — TZ Analyzer"""
import math
import zipfile
import pytest
import pandas as pd
from xml.etree import ElementTree as ET


# ── GEO_UTILS ──────────────────────────────────────────────────────────────

def test_circulo_count():
    from tz_core.geo_utils import generar_coordenadas_circulo
    coords = generar_coordenadas_circulo(13.7, -89.2, 1.0)
    assert len(coords) == 73  # 72 vértices + 1 cierre


def test_circulo_cerrado():
    from tz_core.geo_utils import generar_coordenadas_circulo
    coords = generar_coordenadas_circulo(13.7, -89.2, 1.0)
    assert coords[0] == coords[-1]


def test_circulo_radio_aproximado():
    """Todos los vértices deben estar a ≈ radio_km del centro."""
    from tz_core.geo_utils import generar_coordenadas_circulo
    radio = 1.0
    lat_c, lon_c = 13.7, -89.2
    for lon_p, lat_p in generar_coordenadas_circulo(lat_c, lon_c, radio)[:-1]:
        dlat = math.radians(lat_p - lat_c)
        dlon = math.radians(lon_p - lon_c)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat_c))
             * math.cos(math.radians(lat_p))
             * math.sin(dlon / 2) ** 2)
        dist = 6371.0 * 2 * math.asin(math.sqrt(a))
        assert abs(dist - radio) < 0.005, f"Vértice fuera de radio: {dist:.4f} km"


# ── ORDENAMIENTO CRONOLÓGICO ────────────────────────────────────────────────

_CONFIG_KMZ = {
    "kml": {"azimuth_km": 1.0},
    "style": {"theme_hex": "#ff0000"},
    "salida": {"solo_kmz": True},
}


def _generar_y_leer_kml(df, tmp_path, config=None):
    """Helper: genera KMZ y devuelve el contenido del doc.kml como string."""
    import tz_core.kml_generator as kml_mod
    from tz_core.kml_generator import generar_kml
    kml_mod._REUSABLE_STYLES = None
    out = str(tmp_path / "test.kml")
    generar_kml(df, out, config or _CONFIG_KMZ)
    kmz = str(tmp_path / "test.kmz")
    assert (tmp_path / "test.kmz").exists(), "KMZ no generado"
    with zipfile.ZipFile(kmz, "r") as z:
        with z.open("doc.kml") as f:
            return f.read().decode("utf-8")


def test_ordenamiento_carpetas_cronologico(tmp_path):
    """
    '02/12/2026' < '10/01/2026' alfabéticamente.
    Cronológicamente: 10/01/2026 < 02/12/2026.
    La carpeta '001 — 2026-01-10' debe aparecer antes que '002 — 2026-12-02'.
    """
    df = pd.DataFrame({
        "fecha":  ["02/12/2026", "10/01/2026"],
        "hora":   ["10:00:00",   "09:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["A",          "B"],
        "azimut": [90,           180],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_jan = kml_content.find("2026-01-10")
    pos_dec = kml_content.find("2026-12-02")
    assert pos_jan != -1, "No se encontró fecha 2026-01-10 en el KMZ"
    assert pos_dec != -1, "No se encontró fecha 2026-12-02 en el KMZ"
    assert pos_jan < pos_dec, "Orden incorrecto: dic-2026 aparece antes que ene-2026"


def test_ordenamiento_mismo_timestamp_respeta_fila_original(tmp_path):
    """Dos registros con idéntica fecha y hora → orden por fila original."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "10/01/2026"],
        "hora":   ["09:00:00",   "09:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["PRIMERO",    "SEGUNDO"],
        "azimut": [90,           180],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_a = kml_content.find("PRIMERO")
    pos_b = kml_content.find("SEGUNDO")
    assert pos_a != -1 and pos_b != -1
    assert pos_a < pos_b, "Orden de fila original no respetado en timestamps iguales"


def test_ordenamiento_fecha_valida_sin_hora_al_final_de_su_dia(tmp_path):
    """Registro con fecha válida pero sin hora → al final de ese día, no de la bitácora."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "10/01/2026", "11/01/2026"],
        "hora":   ["09:00:00",   "Sin Inf.",    "08:00:00"],
        "lat":    [13.7,         13.8,           13.9],
        "long":   [-89.2,        -89.3,          -89.4],
        "antena": ["CON_HORA",   "SIN_HORA",     "DIA2"],
        "azimut": [90,           90,              90],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_con = kml_content.find("CON_HORA")
    pos_sin = kml_content.find("SIN_HORA")
    pos_d2  = kml_content.find("DIA2")
    assert pos_con < pos_sin, "Registro sin hora debe aparecer después del registro con hora"
    assert pos_sin < pos_d2,  "Registro sin hora del día 1 debe aparecer antes que cualquier activación del día 2"


# ── _CREAR_FEATURE_KML ──────────────────────────────────────────────────────

_CFG = {
    "kml": {"azimuth_km": 1.0, "cone": {"half_degrees": 60}},
    "style": {"theme_hex": "#ff0000", "cone_opacity": 0.4},
}


def _reset_and_import():
    import tz_core.kml_generator as kml_mod
    kml_mod._REUSABLE_STYLES = None
    from tz_core.kml_generator import _crear_feature_kml
    return _crear_feature_kml


def _contar_geometrias(kml_obj):
    """Cuenta geometrías reales serializando el objeto simplekml a XML."""
    root = ET.fromstring(kml_obj.kml())
    return {
        "points":      len(root.findall(".//{*}Point")),
        "polygons":    len(root.findall(".//{*}Polygon")),
        "linestrings": len(root.findall(".//{*}LineString")),
    }


def test_sin_azimut_solo_pin_y_circulo():
    """azimut=None: exactamente 1 pin + 1 polígono (círculo). Sin líneas."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, None, _CFG)
    g = _contar_geometrias(kml_obj)
    assert g["points"]      == 1, "Esperado 1 pin"
    assert g["linestrings"] == 0, "Sin líneas (no hay azimut)"
    assert g["polygons"]    == 1, "Esperado 1 polígono (círculo)"


def test_azimut_nan_solo_pin_y_circulo():
    """azimut=float('nan'): mismo comportamiento que None."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, float("nan"), _CFG)
    g = _contar_geometrias(kml_obj)
    assert g["points"]      == 1, "Esperado 1 pin"
    assert g["linestrings"] == 0, "Sin líneas (azimut NaN)"
    assert g["polygons"]    == 1, "Esperado 1 polígono (círculo)"


def test_con_azimut_genera_todo():
    """Con azimut válido: 1 pin + 2 polígonos (círculo + cono) + 1 línea."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, 90.0, _CFG)
    g = _contar_geometrias(kml_obj)
    assert g["points"]      == 1, "Esperado 1 pin"
    assert g["linestrings"] == 1, "Esperado 1 línea de azimut"
    assert g["polygons"]    == 2, "Esperado 2 polígonos (círculo + cono)"


def test_registro_sin_fecha_aparece_en_kmz(tmp_path):
    """Registro con fecha 'Sin Inf.' no debe perderse — debe aparecer en el KMZ."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "Sin Inf."],
        "hora":   ["09:00:00",   "10:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["CON_FECHA",  "SIN_FECHA"],
        "azimut": [90,           90],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    assert "SIN_FECHA" in kml_content, "Registro sin fecha desapareció del KMZ"
    assert "Sin fecha determinada" in kml_content, "Carpeta 'Sin fecha determinada' no creada"


# ── PADDING ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("total_dias,total_act,esperado_dia,esperado_act", [
    (1,     1,     "001",   "0001"),    # mínimos
    (999,   9999,  "999",   "9999"),    # justo en los límites de los mínimos
    (1000,  10000, "1000",  "10000"),   # superan mínimos → padding crece
])
def test_padding_dinamico(total_dias, total_act, esperado_dia, esperado_act):
    pad_dias = max(3, len(str(total_dias)))
    pad_act  = max(4, len(str(total_act)))
    assert str(total_dias).zfill(pad_dias) == esperado_dia
    assert str(total_act).zfill(pad_act)   == esperado_act
