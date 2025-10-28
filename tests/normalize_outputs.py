import os
import re
import zipfile

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
