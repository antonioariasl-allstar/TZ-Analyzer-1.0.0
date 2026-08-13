"""
Regresión visual KMZ — marcador de antena (PIN vs círculo).

Contexto: en MB4 (commit f25dfda) se reemplazó la dependencia remota
"http://maps.google.com/mapfiles/kml/paddle/wht-blank.png" por un ícono
local embebido (tz_core/assets/kml_point_icon.png), pero el PNG generado
en ese momento era un disco/círculo relleno en vez de un PIN — produciendo
en Google Earth un punto/círculo (tintado con el color de la bitácora)
donde antes se veía un PIN visible.

Estas pruebas fijan el contrato aprobado:
  - el ícono de punto sigue siendo un recurso local embebido (offline,
    AUD-08), nunca una URL remota;
  - el KMZ contiene físicamente el asset y el KML referencia la ruta
    empaquetada;
  - la forma del ícono es un PIN (no un círculo simétrico);
  - las geometrías de cobertura (círculo/sector/azimut), coordenadas y
    colores permanecen exactamente iguales — el fix es exclusivo del ícono.

Modo 1 y Modo 2 comparten el mismo pipeline (tz_web/services.py llama a
generar_kml() en modo carpetas); Modo 3 Antenas llama a
generar_kml(flat=True) (tz_web/services_modo3.py) y Modo 3 Puntos libres
llama a generar_kml_puntos_libres(). Los cuatro casos se ejercitan aquí
mediante esas mismas funciones de tz_core.kml_generator.
"""
import os
import zipfile

import pandas as pd
import pytest
from xml.etree import ElementTree as ET

from tz_core.color_utils import hex_to_kml_color

_KML_NS_URI = "http://www.opengis.net/kml/2.2"
_ICON_ASSET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tz_core", "assets", "kml_point_icon.png"
)

_CONFIG = {
    "kml": {"azimuth_km": 1.0, "cone": {"half_degrees": 60}},
    "style": {"theme_hex": "#00ffff"},  # turquesa: mismo tono reportado en la regresión
    "salida": {"solo_kmz": True},
}

_LAT = 13.712345
_LON = -89.212345

_DF_ANTENA_CON_AZ = pd.DataFrame({
    "fecha": ["10/01/2026"],
    "hora": ["09:00:00"],
    "lat": [_LAT],
    "long": [_LON],
    "antena": ["ANTENA-PIN-TEST"],
    "azimut": [45],
})

_DF_ANTENA_SIN_AZ = pd.DataFrame({
    "fecha": ["10/01/2026"],
    "hora": ["09:00:00"],
    "lat": [_LAT],
    "long": [_LON],
    "antena": ["ANTENA-SIN-AZIMUT"],
    "azimut": [None],
})

_DF_PUNTO_LIBRE = pd.DataFrame({
    "lat": [_LAT],
    "long": [_LON],
    "antena": ["PUNTO-LIBRE-TEST"],
    "detalle": ["Detalle"],
    "direccion": ["Direccion"],
})


def _reset_styles():
    import tz_core.kml_generator as kml_mod
    kml_mod._REUSABLE_STYLES = None


def _leer_kmz(kmz_path):
    assert os.path.exists(kmz_path), f"KMZ no generado: {kmz_path}"
    with zipfile.ZipFile(kmz_path, "r") as z:
        names = z.namelist()
        with z.open("doc.kml") as f:
            raw = f.read().decode("utf-8")
        icon_bytes = z.read("files/kml_point_icon.png") if "files/kml_point_icon.png" in names else None
    ET.fromstring(raw)  # H: KML sigue siendo XML válido
    return raw, names, icon_bytes


def _generar_modo1_2(df, tmp_path, config=None):
    """Modo 1/Modo 2: generar_kml() en modo carpetas (pipeline de tz_web/services.py)."""
    from tz_core.kml_generator import generar_kml
    _reset_styles()
    out = str(tmp_path / "modo12.kml")
    generar_kml(df, out, config or _CONFIG, flat=False)
    return _leer_kmz(str(tmp_path / "modo12.kmz"))


def _generar_modo3_antenas(df, tmp_path, config=None):
    """Modo 3 Antenas/Celdas: generar_kml(flat=True) (pipeline de tz_web/services_modo3.py)."""
    from tz_core.kml_generator import generar_kml
    _reset_styles()
    out = str(tmp_path / "modo3ant.kml")
    generar_kml(df, out, config or _CONFIG, flat=True)
    return _leer_kmz(str(tmp_path / "modo3ant.kmz"))


def _generar_modo3_puntos_libres(df, tmp_path, config=None):
    """Modo 3 Puntos libres: generar_kml_puntos_libres()."""
    from tz_core.kml_generator import generar_kml_puntos_libres
    out = str(tmp_path / "modo3pl.kml")
    kmz_path, _desc = generar_kml_puntos_libres(df, out, config or _CONFIG)
    return _leer_kmz(kmz_path)


def _icon_hrefs(raw):
    root = ET.fromstring(raw)
    hrefs = [el.text for el in root.iter(f"{{{_KML_NS_URI}}}href")]
    # Excluye el href del ScreenOverlay (kmz_aviso_orientativo.png), que no es el pin.
    return [h for h in hrefs if h and "kml_point_icon" in h]


# ── A/B/C/D — cada modo usa el pin local embebido ───────────────────────────

@pytest.mark.parametrize("modo", ["modo1", "modo2"])
def test_a_b_modo1_modo2_antena_usa_pin_local(tmp_path, modo):
    """A/B: antena en Modo 1 y Modo 2 usa el ícono local (comparten el mismo pipeline)."""
    raw, names, icon_bytes = _generar_modo1_2(_DF_ANTENA_CON_AZ, tmp_path)
    hrefs = _icon_hrefs(raw)
    assert hrefs, f"{modo}: no se encontró href de ícono de punto en el KML"
    assert all(h == "files/kml_point_icon.png" for h in hrefs)
    assert icon_bytes, f"{modo}: el KMZ no contiene físicamente el asset del pin"


def test_c_modo3_antenas_usa_pin_local(tmp_path):
    """C: Modo 3 Antenas usa el ícono local."""
    raw, names, icon_bytes = _generar_modo3_antenas(_DF_ANTENA_CON_AZ, tmp_path)
    hrefs = _icon_hrefs(raw)
    assert hrefs, "Modo 3 Antenas: no se encontró href de ícono de punto en el KML"
    assert all(h == "files/kml_point_icon.png" for h in hrefs)
    assert icon_bytes, "Modo 3 Antenas: el KMZ no contiene físicamente el asset del pin"


def test_d_modo3_puntos_libres_conserva_icono_esperado(tmp_path):
    """D: Modo 3 Puntos libres conserva su ícono esperado (mismo asset local que antenas,
    igual que el comportamiento histórico pre-MB4 donde ambos usaban la misma paddle URL)."""
    raw, names, icon_bytes = _generar_modo3_puntos_libres(_DF_PUNTO_LIBRE, tmp_path)
    hrefs = _icon_hrefs(raw)
    assert hrefs, "Modo 3 Puntos libres: no se encontró href de ícono de punto en el KML"
    assert all(h == "files/kml_point_icon.png" for h in hrefs)
    assert icon_bytes, "Modo 3 Puntos libres: el KMZ no contiene físicamente el asset del pin"


# ── E — ningún ícono depende de maps.google.com ─────────────────────────────

def test_e_ningun_modo_referencia_maps_google_para_icono(tmp_path):
    raw12, _, _ = _generar_modo1_2(_DF_ANTENA_CON_AZ, tmp_path)
    raw3a, _, _ = _generar_modo3_antenas(_DF_ANTENA_CON_AZ, tmp_path)
    raw3p, _, _ = _generar_modo3_puntos_libres(_DF_PUNTO_LIBRE, tmp_path)
    for raw in (raw12, raw3a, raw3p):
        assert "maps.google.com" not in raw


# ── F/G — KMZ contiene el asset y el href apunta al recurso empaquetado ─────

def test_f_g_kmz_contiene_asset_y_href_apunta_al_empaquetado(tmp_path):
    raw, names, icon_bytes = _generar_modo1_2(_DF_ANTENA_CON_AZ, tmp_path)
    # F: el asset está físicamente en el KMZ.
    assert "files/kml_point_icon.png" in names
    with open(_ICON_ASSET_PATH, "rb") as f:
        asset_en_disco = f.read()
    assert icon_bytes == asset_en_disco, (
        "El PNG embebido en el KMZ no coincide byte a byte con el asset fuente"
    )
    # G: el href interno del KML apunta exactamente a ese recurso empaquetado.
    hrefs = _icon_hrefs(raw)
    assert hrefs and all(h == "files/kml_point_icon.png" for h in hrefs)


# ── H — KML/KMZ sigue siendo XML/ZIP válido ─────────────────────────────────
# Cubierto implícitamente por _leer_kmz() (ET.fromstring + zipfile.ZipFile) en
# todos los tests de este archivo; se deja explícito aquí por completitud.

def test_h_kml_kmz_valido(tmp_path):
    raw, names, _ = _generar_modo1_2(_DF_ANTENA_CON_AZ, tmp_path)
    ET.fromstring(raw)  # no debe lanzar
    assert "doc.kml" in names


# ── I — círculo/sector/azimut siguen existiendo sin cambios ─────────────────

def _contar_geometrias(raw):
    root = ET.fromstring(raw)
    return {
        "points": len(root.findall(f".//{{{_KML_NS_URI}}}Point")),
        "polygons": len(root.findall(f".//{{{_KML_NS_URI}}}Polygon")),
        "linestrings": len(root.findall(f".//{{{_KML_NS_URI}}}LineString")),
    }


def test_i_geometrias_cobertura_intactas_con_azimut(tmp_path):
    raw, _, _ = _generar_modo3_antenas(_DF_ANTENA_CON_AZ, tmp_path)
    g = _contar_geometrias(raw)
    assert g["points"] == 1
    assert g["linestrings"] == 1, "Línea de azimut ausente"
    assert g["polygons"] == 2, "Se esperaban círculo + cono"


def test_i_geometrias_cobertura_intactas_sin_azimut(tmp_path):
    raw, _, _ = _generar_modo3_antenas(_DF_ANTENA_SIN_AZ, tmp_path)
    g = _contar_geometrias(raw)
    assert g["points"] == 1
    assert g["linestrings"] == 0, "No debe haber línea de azimut sin azimut válido"
    assert g["polygons"] == 1, "Solo debe existir el círculo de referencia"


# ── J — coordenadas no cambian ──────────────────────────────────────────────

def test_j_coordenadas_del_pin_no_cambian(tmp_path):
    raw, _, _ = _generar_modo3_antenas(_DF_ANTENA_CON_AZ, tmp_path)
    root = ET.fromstring(raw)
    coords_text = root.find(f".//{{{_KML_NS_URI}}}Point/{{{_KML_NS_URI}}}coordinates").text.strip()
    lon_str, lat_str, *_ = coords_text.split(",")
    assert abs(float(lon_str) - _LON) < 1e-9
    assert abs(float(lat_str) - _LAT) < 1e-9


# ── K — colores no cambian ───────────────────────────────────────────────────

def test_k_colores_pin_circulo_cono_no_cambian(tmp_path):
    raw, _, _ = _generar_modo3_antenas(_DF_ANTENA_CON_AZ, tmp_path)
    root = ET.fromstring(raw)
    theme_hex = _CONFIG["style"]["theme_hex"]

    icon_color = root.find(f".//{{{_KML_NS_URI}}}IconStyle/{{{_KML_NS_URI}}}color").text.lower()
    assert icon_color == hex_to_kml_color(theme_hex, 255)

    label_color = root.find(f".//{{{_KML_NS_URI}}}LabelStyle/{{{_KML_NS_URI}}}color").text.lower()
    assert label_color == hex_to_kml_color(theme_hex, 255)

    # Círculo: contorno visible, sin relleno (fill=0), color de línea con alpha 200.
    poligonos = root.findall(f".//{{{_KML_NS_URI}}}Polygon/..")
    circulo = next(pm for pm in poligonos if pm.find(f"{{{_KML_NS_URI}}}name").text == "Radio de referencia")
    style_id = circulo.find(f"{{{_KML_NS_URI}}}styleUrl").text.lstrip("#")
    estilo_circulo = next(s for s in root.findall(f".//{{{_KML_NS_URI}}}Style") if s.get("id") == style_id)
    assert estilo_circulo.find(f"{{{_KML_NS_URI}}}PolyStyle/{{{_KML_NS_URI}}}fill").text == "0"
    line_color = estilo_circulo.find(f"{{{_KML_NS_URI}}}LineStyle/{{{_KML_NS_URI}}}color").text.lower()
    assert line_color == hex_to_kml_color(theme_hex, 200)

    # Cono: relleno activo con la opacidad configurada (default 0.35).
    cono = next(pm for pm in poligonos if pm.find(f"{{{_KML_NS_URI}}}name").text.startswith("Cono Azimut"))
    style_id_cono = cono.find(f"{{{_KML_NS_URI}}}styleUrl").text.lstrip("#")
    estilo_cono = next(s for s in root.findall(f".//{{{_KML_NS_URI}}}Style") if s.get("id") == style_id_cono)
    cono_color = estilo_cono.find(f"{{{_KML_NS_URI}}}PolyStyle/{{{_KML_NS_URI}}}color").text.lower()
    assert cono_color == hex_to_kml_color(theme_hex, int(0.35 * 255))


# ── L — el asset del ícono tiene forma de PIN, no de círculo simétrico ──────
# (guarda de regresión a nivel de píxeles: evita que se vuelva a introducir
# un ícono de disco/círculo relleno como el de la regresión original)

def test_l_icono_es_pin_no_circulo_simetrico():
    """Guarda de forma a nivel de píxeles.

    Un círculo relleno (la regresión original) tiene una caja delimitadora
    cuadrada (alto == ancho, relación 1.0) porque es simétrico en ambos
    ejes. Un PIN con cola/punta es más alto que ancho (la cola se extiende
    más allá del diámetro de la cabeza). Verificado contra el asset previo
    al fix (git HEAD~ de esta corrección): disco → relación 1.0 exacta;
    PIN nuevo → relación ≈1.31. Un umbral de 1.15 separa ambos casos con
    margen.
    """
    pil = pytest.importorskip("PIL.Image", reason="Pillow no instalado; guarda de forma opcional")
    img = pil.open(_ICON_ASSET_PATH).convert("RGBA")
    w, h = img.size

    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if img.getpixel((x, y))[3] > 40:
                xs.append(x)
                ys.append(y)
    assert xs and ys, "El ícono no tiene píxeles visibles"
    bbox_w = max(xs) - min(xs) + 1
    bbox_h = max(ys) - min(ys) + 1

    assert bbox_h / bbox_w > 1.15, (
        f"La caja delimitadora del ícono (h={bbox_h}, w={bbox_w}, "
        f"relación={bbox_h / bbox_w:.2f}) es demasiado cuadrada/simétrica: "
        "parece un círculo relleno en vez de un PIN con punta — "
        "esto es exactamente la regresión reportada"
    )

    # Las esquinas deben ser transparentes (el ícono no ocupa el lienzo
    # completo, a diferencia de un ícono rectangular sin forma).
    assert img.getpixel((0, 0))[3] == 0
    assert img.getpixel((w - 1, 0))[3] == 0


# ── M — la fila de mayor ancho está en la cabeza, no en el centro vertical ──
# (segunda guarda de forma, independiente de la relación alto/ancho de L:
# un círculo relleno es simétrico respecto a su eje horizontal, así que su
# fila más ancha cae siempre en el centro vertical del bounding box
# (~50%). Un PIN tiene la cabeza circular concentrada arriba y una cola
# que se angosta hacia una punta abajo, así que su fila más ancha queda
# muy por encima del centro. Esta prueba detectaría, por ejemplo, un óvalo
# vertical alargado que pasara la prueba de relación de L pero siguiera
# siendo simétrico arriba/abajo — no un PIN real.)

def test_m_fila_mas_ancha_esta_en_la_cabeza_no_en_el_centro():
    pil = pytest.importorskip("PIL.Image", reason="Pillow no instalado; guarda de forma opcional")
    img = pil.open(_ICON_ASSET_PATH).convert("RGBA")
    w, h = img.size

    anchos_por_fila = {}
    for y in range(h):
        ancho = sum(1 for x in range(w) if img.getpixel((x, y))[3] > 40)
        if ancho:
            anchos_por_fila[y] = ancho

    assert anchos_por_fila, "El ícono no tiene píxeles visibles"
    min_y, max_y = min(anchos_por_fila), max(anchos_por_fila)
    bbox_h = max_y - min_y + 1

    fila_mas_ancha = max(anchos_por_fila, key=anchos_por_fila.get)
    posicion_relativa = (fila_mas_ancha - min_y) / bbox_h

    assert posicion_relativa < 0.35, (
        f"La fila más ancha del ícono está al {posicion_relativa:.0%} de su "
        "altura — demasiado cerca del centro vertical (50%), propio de un "
        "círculo/óvalo simétrico y no de un PIN con cabeza arriba y cola "
        "angostándose hacia una punta abajo."
    )

    # La punta inferior debe quedar claramente definida (angosta), no un
    # borde ancho como el de un disco cortado.
    ancho_punta = anchos_por_fila[max_y]
    ancho_cabeza = anchos_por_fila[fila_mas_ancha]
    assert ancho_punta < ancho_cabeza * 0.35, (
        f"La última fila visible tiene un ancho de {ancho_punta}px frente a "
        f"{ancho_cabeza}px en la cabeza: la punta inferior no está "
        "claramente definida."
    )
