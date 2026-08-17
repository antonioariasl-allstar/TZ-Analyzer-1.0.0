"""Tests unitarios del normalizador de comparación golden — P1-SIMPLEKML-SWITCH-NORM.

Valida que ``canonicalize_normalized_kml`` ignora ÚNICAMENTE ruido
incidental de serializador (IDs no referenciados por ningún styleUrl,
colorMode=normal implícito, orden relativo de name/description/open dentro
de Folder) sin enmascarar ningún cambio semántico real: grafo Style
compartido, Styles distintos, colorMode=random, y orden de Folder/Placemark.
"""
from tests.normalize_outputs import canonicalize_normalized_kml

KML_NS = 'xmlns="http://www.opengis.net/kml/2.2"'


def _wrap(body: str) -> str:
    return f'<kml {KML_NS}><Document>{body}</Document></kml>'


# ── CASO 1 — IDs distintos, misma relación ──────────────────────────────

def test_ids_distintos_misma_relacion_son_equivalentes():
    doc_a = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


# ── CASO 2 — shared style preservado ────────────────────────────────────

def test_shared_style_preservado_entre_backends():
    doc_a = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#9</styleUrl></Placemark>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#style_0</styleUrl></Placemark>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


# ── CASO 3 — relación distinta NO se oculta ─────────────────────────────

def test_relacion_distinta_no_se_enmascara():
    """Documento A: dos Placemarks comparten el mismo Style. Documento B:
    cada Placemark referencia un Style DISTINTO. El normalizador no debe
    fusionar estilos ni ocultar esta diferencia de grafo real."""
    doc_a = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#9</styleUrl></Placemark>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Style id="style_1"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#style_1</styleUrl></Placemark>'
    )
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


# ── CASO 4 — Styles distintos siguen distintos ──────────────────────────

def test_styles_con_propiedades_distintas_no_se_deduplican():
    doc_a = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Style id="10"><LineStyle><color>ff00ff00</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#10</styleUrl></Placemark>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Style id="style_1"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
        '<Placemark><name>P2</name><styleUrl>#style_1</styleUrl></Placemark>'
    )
    # doc_a tiene dos Styles con colores distintos; doc_b tiene dos Styles
    # con el MISMO color pero IDs distintos. No deben canonicalizar igual:
    # el normalizador no compara/deduplica por contenido de Style.
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


def test_ids_no_referenciados_se_eliminan_sin_afectar_comparacion():
    """IDs incidentales en Document/Placemark/Point (nunca targeteados por
    un styleUrl) deben desaparecer y no producir diferencias espurias."""
    doc_a = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark id="55"><name>P1</name><styleUrl>#9</styleUrl>'
        '<Point id="56"><coordinates>-89.2,13.7,0</coordinates></Point></Placemark>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl>'
        '<Point><coordinates>-89.2,13.7,0</coordinates></Point></Placemark>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


# ── CASO 5 — colorMode ───────────────────────────────────────────────────

def test_colormode_normal_ausente_vs_explicito_son_equivalentes():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><colorMode>normal</colorMode>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap('<Style id="9"><IconStyle><color>ff0000ff</color></IconStyle></Style>')
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


def test_colormode_random_no_se_normaliza():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><colorMode>random</colorMode>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap('<Style id="9"><IconStyle><color>ff0000ff</color></IconStyle></Style>')
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


def test_colormode_random_distinto_de_normal_explicito():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><colorMode>random</colorMode>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><colorMode>normal</colorMode>'
        '</IconStyle></Style>'
    )
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


# ── CASO 6 — metadata Folder ─────────────────────────────────────────────

def test_orden_metadata_folder_name_open_description_equivalente():
    doc_a = _wrap(
        '<Folder><name>F1</name><open>0</open><description>Desc</description>'
        '<Placemark><name>P1</name></Placemark></Folder>'
    )
    doc_b = _wrap(
        '<Folder><name>F1</name><description>Desc</description><open>0</open>'
        '<Placemark><name>P1</name></Placemark></Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


# ── CASO 7 — orden de Folders/Placemarks NO se toca ─────────────────────

def test_orden_de_folders_hermanos_no_se_altera():
    """B3 solo reordena metadata DIRECTA de cada Folder — nunca el orden
    relativo entre Folders/Placemarks hermanos (puede ser cronológico)."""
    doc_a = _wrap(
        '<Folder><name>A</name></Folder>'
        '<Folder><name>B</name></Folder>'
    )
    doc_b = _wrap(
        '<Folder><name>B</name></Folder>'
        '<Folder><name>A</name></Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


def test_orden_de_placemarks_dentro_de_folder_no_se_altera():
    doc_a = _wrap(
        '<Folder><name>F1</name>'
        '<Placemark><name>P1</name></Placemark>'
        '<Placemark><name>P2</name></Placemark>'
        '</Folder>'
    )
    doc_b = _wrap(
        '<Folder><name>F1</name>'
        '<Placemark><name>P2</name></Placemark>'
        '<Placemark><name>P1</name></Placemark>'
        '</Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


# ── CASO 8 — posición de <Style> en el árbol ────────────────────────────

def test_style_dentro_de_folder_vs_en_document_son_equivalentes():
    """legacy declara el Style inline en el primer Folder que lo usa; el
    writer lo agrupa como hijo directo de Document. La posición no tiene
    significado KML — styleUrl resuelve por id en todo el documento."""
    doc_a = _wrap(
        '<Folder><name>F1</name>'
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '</Folder>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Folder><name>F1</name>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
        '</Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


def test_style_con_propiedades_diferentes_no_equivalente_pese_a_posicion():
    """Aunque ambos Styles estén en la misma posición relativa (dentro del
    Folder), propiedades de color distintas deben seguir siendo detectadas
    — la canonicalización de posición no debe enmascarar cambios reales."""
    doc_a = _wrap(
        '<Folder><name>F1</name>'
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '</Folder>'
    )
    doc_b = _wrap(
        '<Folder><name>F1</name>'
        '<Style id="9"><LineStyle><color>ff00ff00</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '</Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


def test_shared_style_graph_preservado_tras_hoist_de_posicion():
    """Dos Placemarks en Folders distintos comparten un Style declarado
    inline en el primero de ellos (patrón legacy real): el hoist a
    Document no debe romper la relación compartida."""
    doc_a = _wrap(
        '<Folder><name>F1</name>'
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Placemark><name>P1</name><styleUrl>#9</styleUrl></Placemark>'
        '</Folder>'
        '<Folder><name>F2</name>'
        '<Placemark><name>P2</name><styleUrl>#9</styleUrl></Placemark>'
        '</Folder>'
    )
    doc_b = _wrap(
        '<Style id="style_0"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
        '<Folder><name>F1</name>'
        '<Placemark><name>P1</name><styleUrl>#style_0</styleUrl></Placemark>'
        '</Folder>'
        '<Folder><name>F2</name>'
        '<Placemark><name>P2</name><styleUrl>#style_0</styleUrl></Placemark>'
        '</Folder>'
    )
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


# ── CASO 9 — heading default ─────────────────────────────────────────────

def test_heading_ausente_vs_cero_son_equivalentes():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><heading>0</heading>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap('<Style id="9"><IconStyle><color>ff0000ff</color></IconStyle></Style>')
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


def test_heading_ausente_vs_cero_punto_cero_son_equivalentes():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><heading>0.0</heading>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap('<Style id="9"><IconStyle><color>ff0000ff</color></IconStyle></Style>')
    assert canonicalize_normalized_kml(doc_a) == canonicalize_normalized_kml(doc_b)


def test_heading_ausente_vs_45_no_son_equivalentes():
    doc_a = _wrap(
        '<Style id="9"><IconStyle><color>ff0000ff</color><heading>45</heading>'
        '</IconStyle></Style>'
    )
    doc_b = _wrap('<Style id="9"><IconStyle><color>ff0000ff</color></IconStyle></Style>')
    assert canonicalize_normalized_kml(doc_a) != canonicalize_normalized_kml(doc_b)


# ── B4 — restricción de alcance: nada más cambia ────────────────────────

def test_coordenadas_colores_y_jerarquia_no_normalizados():
    """Cambios reales de coordenadas/colores/nombres/jerarquía deben seguir
    detectándose — la normalización no debe volverse "ciega" a ellos."""
    base = _wrap(
        '<Folder><name>F1</name>'
        '<Placemark><name>P1</name>'
        '<Point><coordinates>-89.200000,13.700000,0</coordinates></Point>'
        '</Placemark></Folder>'
    )
    coords_distintas = base.replace("-89.200000", "-88.200000")
    assert canonicalize_normalized_kml(base) != canonicalize_normalized_kml(coords_distintas)

    color_distinto = _wrap(
        '<Style id="9"><LineStyle><color>ff0000ff</color></LineStyle></Style>'
    )
    color_otro = _wrap(
        '<Style id="9"><LineStyle><color>ff00ff00</color></LineStyle></Style>'
    )
    assert canonicalize_normalized_kml(color_distinto) != canonicalize_normalized_kml(color_otro)

    jerarquia_a = _wrap('<Folder><name>F1</name><Folder><name>F2</name></Folder></Folder>')
    jerarquia_b = _wrap('<Folder><name>F1</name></Folder><Folder><name>F2</name></Folder>')
    assert canonicalize_normalized_kml(jerarquia_a) != canonicalize_normalized_kml(jerarquia_b)


def test_screenoverlay_href_overlayxy_no_normalizados():
    base = _wrap(
        '<ScreenOverlay><name>Aviso</name><Icon><href>files/a.png</href></Icon>'
        '<overlayXY x="0" y="1" xunits="fraction" yunits="fraction"/>'
        '</ScreenOverlay>'
    )
    href_distinto = base.replace("files/a.png", "files/b.png")
    assert canonicalize_normalized_kml(base) != canonicalize_normalized_kml(href_distinto)

    overlay_distinto = base.replace('x="0" y="1"', 'x="0.5" y="1"')
    assert canonicalize_normalized_kml(base) != canonicalize_normalized_kml(overlay_distinto)
