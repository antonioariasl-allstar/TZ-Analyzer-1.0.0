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


def canonicalize_normalized_kml(kml: str) -> str:
    """Canonicaliza KML normalizado para compararlo por semántica XML.

    El golden histórico contiene ``<DATE>`` como marcador textual. Antes de
    parsearlo se convierte a texto plano para que el XML vuelva a ser válido.
    C14N 2.0 elimina diferencias léxicas equivalentes, por ejemplo ``&quot;``
    frente a una comilla literal dentro del texto de ``description``.
    """
    parseable_kml = kml.replace("<DATE>", _DATE_PLACEHOLDER)
    return ET.canonicalize(xml_data=parseable_kml)


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
