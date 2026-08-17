import os
import re
import zipfile
import xml.etree.ElementTree as ET

def _read_kml_from_kmz(kmz_path: str) -> str:
    with zipfile.ZipFile(kmz_path, 'r') as z:
        for n in z.namelist():
            if n.lower().endswith('.kml'):
                return z.read(n).decode('utf-8', errors='ignore')
    return ''

_WHITESPACE_RE = re.compile(r"\s+")
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})([ T]\d{2}:\d{2}:\d{2})?\b")
_LAT_LON_FLOAT_RE = re.compile(r"(-?\d{1,3}\.\d{5,})")  # redondear coords largas
_HTML_META_TIME_RE = re.compile(r"(Generado el|Fecha de generación|Generated on)[^\n<]*", re.IGNORECASE)
_HTML_TIMESTAMP_RE = re.compile(r"\b\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\b")  # formato dd/mm/yyyy HH:MM:SS
_DATE_PLACEHOLDER = "__TZ_ANALYZER_DATE__"

# id="N" que simplekml asigna a cada objeto Kmlable vía su contador global
# de terceros (simplekml.base.Kmlable._globalid), y su referencia en
# <styleUrl>#N</styleUrl>. Ambos patrones solo matchean atributos/elementos
# KML reales (nunca contenido de <description>, que va escapado como
# &quot;/&amp;quot; y no contiene la comilla literal `"`).
_ID_ATTR_RE = re.compile(r'id="(\d+)"')
_STYLEURL_REF_RE = re.compile(r'(<styleUrl>#)(\d+)(</styleUrl>)')


def renumber_simplekml_ids(kml: str) -> str:
    """Renumera de forma determinista los id="N" de simplekml.

    ``simplekml.base.Kmlable._globalid`` es un contador compartido por
    todo el proceso: su valor absoluto depende de cuántos objetos Kmlable
    se hayan creado *antes*, en tests previos dentro de la misma sesión de
    pytest, no del contenido semántico del KML generado. Comparar goldens
    contra ese valor absoluto hace que la prueba dependa del orden de
    ejecución de los tests.

    Esta función renumera los id según su orden de primera aparición en el
    documento (1, 2, 3, ...) y aplica el mismo mapeo a las referencias
    <styleUrl>#N</styleUrl>, preservando intacta la relación entre cada
    Placemark/Polygon/etc. y su Style — solo cambia el valor absoluto del
    identificador, nunca la semántica del documento.
    """
    mapping: dict[str, str] = {}
    for match in _ID_ATTR_RE.finditer(kml):
        old_id = match.group(1)
        if old_id not in mapping:
            mapping[old_id] = str(len(mapping) + 1)

    kml = _ID_ATTR_RE.sub(lambda m: f'id="{mapping.get(m.group(1), m.group(1))}"', kml)
    kml = _STYLEURL_REF_RE.sub(
        lambda m: f"{m.group(1)}{mapping.get(m.group(2), m.group(2))}{m.group(3)}",
        kml,
    )
    return kml


_COLOR_MODE_NORMAL = "normal"
_FOLDER_METADATA_ORDER = ("name", "description", "open")


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1]


def _referenced_style_ids(root: ET.Element) -> set:
    """IDs realmente referenciados por algún ``<styleUrl>#ID</styleUrl>``
    del documento — el único mecanismo de referencia cruzada por id que
    usa este dialecto KML (Placemark/Polygon/... -> Style)."""
    ids: set = set()
    for el in root.iter():
        if _local_tag(el.tag) != "styleUrl":
            continue
        text = (el.text or "").strip()
        if text.startswith("#"):
            ids.add(text[1:])
    return ids


def _canonicalize_ids_and_styleurls(root: ET.Element) -> None:
    """Preserva el grafo Placemark→styleUrl→Style; elimina IDs incidentales.

    ``simplekml.base.Kmlable`` asigna un ``id="N"`` (contador global de
    terceros) a *todo* objeto que crea — Document, Folder, Placemark,
    Point, Polygon, LinearRing, LineString, ScreenOverlay, Icon,
    sub-estilos... — pero en KML el único elemento cuyo id tiene
    significado semántico es el ``<Style id="...">`` referenciado por un
    ``<styleUrl>#...</styleUrl>``. tz_core.kml_writer solo asigna id a
    Style (formato ``style_N``); el resto de sus nodos no llevan id.

    Esta función mantiene ambos backends comparables sin perder la
    relación Placemark→Style: solo los id efectivamente targeteados por un
    styleUrl se conservan, renumerados de forma determinista en orden de
    primera aparición en el documento. El resto se elimina por completo
    (nunca están referenciados por nada — ver docstring de
    ``_referenced_style_ids``). El mapeo es por VALOR ORIGINAL DE ID, nunca
    por contenido del Style: dos id distintos jamás colapsan al mismo
    canónico, así que estilos compartidos y estilos distintos preservan su
    relación exacta.
    """
    referenced = _referenced_style_ids(root)
    elements_with_id = [el for el in root.iter() if el.get("id") is not None]

    mapping: dict = {}
    for el in elements_with_id:
        id_val = el.get("id")
        if id_val in referenced:
            if id_val not in mapping:
                mapping[id_val] = f"style_canon_{len(mapping)}"
            el.set("id", mapping[id_val])
        else:
            del el.attrib["id"]

    styleurl_elements = [el for el in root.iter() if _local_tag(el.tag) == "styleUrl"]
    for el in styleurl_elements:
        text = (el.text or "").strip()
        if text.startswith("#"):
            old_id = text[1:]
            el.text = f"#{mapping.get(old_id, old_id)}"


def _strip_default_colormode(root: ET.Element) -> None:
    """Elimina ``<colorMode>normal</colorMode>``: "normal" es el valor por
    defecto de KML cuando el elemento está ausente (IconStyle/LabelStyle/
    LineStyle/PolyStyle), así que declararlo explícitamente no cambia el
    significado. Cualquier otro valor (p.ej. ``random``) nunca se toca."""
    parents = {child: parent for parent in root.iter() for child in parent}
    to_remove = [
        el for el in root.iter()
        if _local_tag(el.tag) == "colorMode" and (el.text or "").strip() == _COLOR_MODE_NORMAL
    ]
    for el in to_remove:
        parent = parents.get(el)
        if parent is not None:
            parent.remove(el)


def _reorder_folder_metadata(root: ET.Element) -> None:
    """Normaliza el orden relativo de name/description/open únicamente
    como hijos directos de ``<Folder>`` (legacy los serializa en orden de
    asignación de atributos en Python; el writer usa un orden fijo). Nunca
    reordena Folder/Placemark/geometrías entre sí ni toca ningún otro tipo
    de hijo — esos órdenes pueden ser semánticos/cronológicos."""
    folders = [el for el in root.iter() if _local_tag(el.tag) == "Folder"]
    for folder in folders:
        children = list(folder)
        meta: dict = {}
        rest = []
        for child in children:
            local = _local_tag(child.tag)
            if local in _FOLDER_METADATA_ORDER and local not in meta:
                meta[local] = child
            else:
                rest.append(child)
        if not meta:
            continue
        for child in children:
            folder.remove(child)
        for key in _FOLDER_METADATA_ORDER:
            if key in meta:
                folder.append(meta[key])
        for child in rest:
            folder.append(child)


def _document_element(root: ET.Element) -> ET.Element:
    if _local_tag(root.tag) == "Document":
        return root
    for el in root.iter():
        if _local_tag(el.tag) == "Document":
            return el
    return root


def _hoist_shared_styles_to_document(root: ET.Element) -> None:
    """Canonicaliza la posición de cada ``<Style>`` a hijo directo de
    ``<Document>``, preservando su orden relativo de primera aparición,
    contenido e ID intactos.

    legacy (simplekml) inserta cada Style compartido como hijo del primer
    Folder que lo usa, en el momento en que el código de negocio hace
    ``feature.style = ...``; el writer los agrupa como hijos directos de
    Document. La posición de un ``<Style>`` en el árbol no tiene
    significado KML — ``styleUrl`` resuelve por id en todo el documento,
    sin importar dónde esté declarado el Style — así que solo se
    canonicaliza la posición, nunca el contenido ni el ID (ya
    canonicalizados por ``_canonicalize_ids_and_styleurls``).
    """
    doc = _document_element(root)
    parents = {child: parent for parent in root.iter() for child in parent}
    styles = [el for el in root.iter() if _local_tag(el.tag) == "Style"]
    for insert_at, style_el in enumerate(styles):
        parent = parents.get(style_el)
        if parent is not None:
            parent.remove(style_el)
        doc.insert(insert_at, style_el)


def _strip_zero_heading(root: ET.Element) -> None:
    """Elimina ``<heading>0</heading>``/``<heading>0.0</heading>``:
    ``heading`` con valor 0.0 es el default KML de IconStyle cuando el
    elemento está ausente, así que declararlo explícitamente no cambia el
    significado. Cualquier valor numérico distinto de cero se conserva sin
    tocar."""
    parents = {child: parent for parent in root.iter() for child in parent}
    to_remove = []
    for el in root.iter():
        if _local_tag(el.tag) != "heading":
            continue
        text = (el.text or "").strip()
        try:
            is_zero = float(text) == 0.0
        except ValueError:
            continue
        if is_zero:
            to_remove.append(el)
    for el in to_remove:
        parent = parents.get(el)
        if parent is not None:
            parent.remove(el)


def canonicalize_normalized_kml(kml: str) -> str:
    """Canonicaliza KML normalizado para compararlo por semántica XML,
    ignorando ruido incidental de serializador — IDs no referenciados por
    ningún styleUrl, ``colorMode=normal`` implícito, ``heading=0`` implícito,
    posición de ``<Style>`` en el árbol, y el orden relativo de
    name/description/open dentro de Folder — sin tocar coordenadas,
    colores, textos, jerarquía, hrefs, ScreenOverlay ni assets.

    El golden histórico contiene ``<DATE>`` como marcador textual. Antes de
    parsearlo se convierte a texto plano para que el XML vuelva a ser válido.
    C14N 2.0 elimina además diferencias léxicas equivalentes, por ejemplo
    ``&quot;`` frente a una comilla literal dentro del texto de
    ``description``.
    """
    parseable_kml = kml.replace("<DATE>", _DATE_PLACEHOLDER)
    root = ET.fromstring(parseable_kml)
    _canonicalize_ids_and_styleurls(root)
    _strip_default_colormode(root)
    _strip_zero_heading(root)
    _reorder_folder_metadata(root)
    _hoist_shared_styles_to_document(root)
    return ET.canonicalize(xml_data=ET.tostring(root, encoding="unicode"))


def normalize_kml_from_kmz(kmz_path: str) -> str:
    """Devuelve el contenido KML normalizado para diffs estables.
    - colapsa espacios
    - elimina/normaliza timestamps ISO
    - redondea floats largos para evitar jitter de precisión
    """
    kml = _read_kml_from_kmz(kmz_path)
    if not kml:
        return ''
    # Normalizar saltos de línea y espacios
    kml = kml.replace('\r\n', '\n').replace('\r', '\n')
    # Normalizar timestamps ISO
    kml = _ISO_DATE_RE.sub("<DATE>", kml)
    # Redondeo de coordenadas muy largas para evitar ruido en diffs
    kml = _LAT_LON_FLOAT_RE.sub(lambda m: f"{float(m.group(1)):.6f}", kml)
    # Renumerar id="N"/styleUrl#N internos de simplekml (contador global de
    # terceros, independiente del contenido semántico — ver docstring)
    kml = renumber_simplekml_ids(kml)
    # Colapsar espacios múltiples
    kml = _WHITESPACE_RE.sub(' ', kml)
    return kml.strip()


def normalize_html(html_path: str) -> str:
    """Devuelve HTML normalizado para diffs estables.
    - elimina metadatos de fecha/hora
    - colapsa espacios
    - normaliza timestamps ISO
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        return ''
    html = html.replace('\r\n', '\n').replace('\r', '\n')
    html = _HTML_META_TIME_RE.sub('<META-TIME>', html)
    html = _HTML_TIMESTAMP_RE.sub('<TIMESTAMP>', html)  # normalizar timestamps dd/mm/yyyy HH:MM:SS
    html = _ISO_DATE_RE.sub('<DATE>', html)
    html = _WHITESPACE_RE.sub(' ', html)
    return html.strip()
