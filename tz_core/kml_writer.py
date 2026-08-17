"""
MÓDULO: kml_writer.py
PROPÓSITO: Writer KML/KMZ stdlib-only, API parcialmente compatible con
           simplekml — implementa ÚNICAMENTE el subset de superficie que
           tz_core/kml_generator.py utiliza (ver inventario P1-SIMPLEKML-WRITER).

No es un framework KML general: son wrappers delgados alrededor de
xml.etree.ElementTree que reproducen el comportamiento observado
empíricamente en simplekml (formato de coordenadas, escaping semántico vía
ElementTree, estilos compartidos vía styleUrl, estructura de KMZ).

Toda la construcción del árbol es perezosa (diferida a save()/savekmz()):
los objetos (Style, IconStyle, ScreenOverlay, ...) se mutan progresivamente
después de crearse — igual que hace el código de negocio con simplekml — y
solo se serializan a XML una vez, al guardar, cuando todas las mutaciones ya
ocurrieron.
"""

from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"

ET.register_namespace("", KML_NS)


def _tag(name: str) -> str:
    return f"{{{KML_NS}}}{name}"


class Units:
    """Constantes de unidades para OverlayXY/ScreenXY/Size (no Enum)."""
    fraction = "fraction"
    pixels = "pixels"


class _Vector2:
    """Base de OverlayXY/ScreenXY/Size: par (x, y) + unidades."""

    def __init__(self, x=None, y=None, xunits=None, yunits=None):
        self.x = x
        self.y = y
        self.xunits = xunits
        self.yunits = yunits

    def _build_element(self, tag_name):
        el = ET.Element(_tag(tag_name))
        if self.x is not None:
            el.set("x", str(self.x))
        if self.y is not None:
            el.set("y", str(self.y))
        if self.xunits is not None:
            el.set("xunits", str(self.xunits))
        if self.yunits is not None:
            el.set("yunits", str(self.yunits))
        return el


class OverlayXY(_Vector2):
    pass


class ScreenXY(_Vector2):
    pass


class Size(_Vector2):
    pass


class Icon:
    """href de un IconStyle o de un ScreenOverlay."""

    def __init__(self, href=None):
        self.href = href

    def _build_element(self):
        el = ET.Element(_tag("Icon"))
        if self.href is not None:
            ET.SubElement(el, _tag("href")).text = str(self.href)
        return el


class IconStyle:
    def __init__(self):
        self.color = None
        self.scale = None
        self._icon = None

    @property
    def icon(self):
        if self._icon is None:
            self._icon = Icon()
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value

    def _build_element(self):
        el = ET.Element(_tag("IconStyle"))
        if self.color is not None:
            ET.SubElement(el, _tag("color")).text = str(self.color)
        if self.scale is not None:
            ET.SubElement(el, _tag("scale")).text = str(self.scale)
        if self._icon is not None:
            el.append(self._icon._build_element())
        return el


class LabelStyle:
    def __init__(self):
        self.color = None
        self.scale = None

    def _build_element(self):
        el = ET.Element(_tag("LabelStyle"))
        if self.color is not None:
            ET.SubElement(el, _tag("color")).text = str(self.color)
        if self.scale is not None:
            ET.SubElement(el, _tag("scale")).text = str(self.scale)
        return el


class LineStyle:
    def __init__(self):
        self.color = None
        self.width = None

    def _build_element(self):
        el = ET.Element(_tag("LineStyle"))
        if self.color is not None:
            ET.SubElement(el, _tag("color")).text = str(self.color)
        if self.width is not None:
            ET.SubElement(el, _tag("width")).text = str(self.width)
        return el


class PolyStyle:
    def __init__(self):
        self.color = None
        self.fill = None
        self.outline = None

    def _build_element(self):
        el = ET.Element(_tag("PolyStyle"))
        if self.color is not None:
            ET.SubElement(el, _tag("color")).text = str(self.color)
        if self.fill is not None:
            ET.SubElement(el, _tag("fill")).text = str(self.fill)
        if self.outline is not None:
            ET.SubElement(el, _tag("outline")).text = str(self.outline)
        return el


class Style:
    """Contenedor de sub-estilos. Se registra por identidad (ver
    _BuildContext.register_style) para deduplicar Placemarks que comparten
    el mismo objeto Style — emitido una sola vez como <Style id=...>,
    referenciado por cada Placemark vía <styleUrl>."""

    def __init__(self):
        self._iconstyle = None
        self._labelstyle = None
        self._linestyle = None
        self._polystyle = None

    @property
    def iconstyle(self):
        if self._iconstyle is None:
            self._iconstyle = IconStyle()
        return self._iconstyle

    @iconstyle.setter
    def iconstyle(self, value):
        self._iconstyle = value

    @property
    def labelstyle(self):
        if self._labelstyle is None:
            self._labelstyle = LabelStyle()
        return self._labelstyle

    @labelstyle.setter
    def labelstyle(self, value):
        self._labelstyle = value

    @property
    def linestyle(self):
        if self._linestyle is None:
            self._linestyle = LineStyle()
        return self._linestyle

    @linestyle.setter
    def linestyle(self, value):
        self._linestyle = value

    @property
    def polystyle(self):
        if self._polystyle is None:
            self._polystyle = PolyStyle()
        return self._polystyle

    @polystyle.setter
    def polystyle(self, value):
        self._polystyle = value

    def _build_element(self, style_id):
        el = ET.Element(_tag("Style"), {"id": style_id})
        if self._iconstyle is not None:
            el.append(self._iconstyle._build_element())
        if self._labelstyle is not None:
            el.append(self._labelstyle._build_element())
        if self._linestyle is not None:
            el.append(self._linestyle._build_element())
        if self._polystyle is not None:
            el.append(self._polystyle._build_element())
        return el


def _coords_text(coords):
    """Serializa coordenadas exactamente como se reciben: "lon,lat,alt"
    separadas por espacio, altitud 0.0 si no se especifica (equivalencia
    empírica con simplekml.coordinates.Coordinates)."""
    parts = []
    for c in coords:
        lon = float(c[0])
        lat = float(c[1])
        alt = float(c[2]) if len(c) > 2 else 0.0
        parts.append(f"{lon},{lat},{alt}")
    return " ".join(parts)


class _BuildContext:
    """Acumula estilos compartidos vistos durante el recorrido del árbol,
    asignándoles IDs deterministas (style_0, style_1, ...) en orden de
    primera aparición en el documento."""

    def __init__(self):
        self._style_ids = {}
        self.style_elements = []
        self._counter = 0

    def register_style(self, style):
        key = id(style)
        style_id = self._style_ids.get(key)
        if style_id is not None:
            return style_id
        style_id = f"style_{self._counter}"
        self._counter += 1
        self._style_ids[key] = style_id
        self.style_elements.append(style._build_element(style_id))
        return style_id


class _FeatureBase:
    """Base común de Folder/Document/Point/LineString/Polygon/ScreenOverlay:
    name/description/open/style, igual que simplekml.featgeom.Feature."""

    def __init__(self, name=None, description=None):
        self.name = name
        self.description = description
        self.open = None
        self._style = None

    @property
    def style(self):
        if self._style is None:
            self._style = Style()
        return self._style

    @style.setter
    def style(self, value):
        self._style = value


def _apply_feature(el, feature, ctx):
    if feature.name is not None:
        ET.SubElement(el, _tag("name")).text = str(feature.name)
    if feature.description is not None:
        ET.SubElement(el, _tag("description")).text = str(feature.description)
    if feature.open is not None:
        ET.SubElement(el, _tag("open")).text = str(feature.open)
    if feature._style is not None:
        style_id = ctx.register_style(feature._style)
        ET.SubElement(el, _tag("styleUrl")).text = f"#{style_id}"


class Container(_FeatureBase):
    """Base de Folder/Document: contenedor con nesting arbitrario."""

    def __init__(self, name=None, description=None):
        super().__init__(name=name, description=description)
        self._children = []

    def newfolder(self, **kwargs):
        node = Folder(**kwargs)
        self._children.append(node)
        return node

    def newpoint(self, **kwargs):
        node = Point(**kwargs)
        self._children.append(node)
        return node

    def newpolygon(self, **kwargs):
        node = Polygon(**kwargs)
        self._children.append(node)
        return node

    def newlinestring(self, **kwargs):
        node = LineString(**kwargs)
        self._children.append(node)
        return node

    def newscreenoverlay(self, **kwargs):
        node = ScreenOverlay(**kwargs)
        self._children.append(node)
        return node


class Folder(Container):
    pass


class Document(Container):
    pass


class Point(_FeatureBase):
    def __init__(self, name=None, description=None, coords=()):
        super().__init__(name=name, description=description)
        self.coords = list(coords)


class LineString(_FeatureBase):
    def __init__(self, name=None, description=None, coords=()):
        super().__init__(name=name, description=description)
        self.coords = list(coords)


class Polygon(_FeatureBase):
    def __init__(self, name=None, description=None, outerboundaryis=()):
        super().__init__(name=name, description=description)
        self.outerboundaryis = list(outerboundaryis)


class ScreenOverlay(_FeatureBase):
    def __init__(self, name=None, description=None):
        super().__init__(name=name, description=description)
        self._icon = None
        self.overlayxy = None
        self.screenxy = None
        self.size = None

    @property
    def icon(self):
        if self._icon is None:
            self._icon = Icon()
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value


def _build_container_children(el, container, ctx):
    for child in container._children:
        el.append(_build_node(child, ctx))


def _build_node(node, ctx):
    if isinstance(node, Folder):
        el = ET.Element(_tag("Folder"))
        _apply_feature(el, node, ctx)
        _build_container_children(el, node, ctx)
        return el

    if isinstance(node, Point):
        el = ET.Element(_tag("Placemark"))
        _apply_feature(el, node, ctx)
        point_el = ET.SubElement(el, _tag("Point"))
        ET.SubElement(point_el, _tag("coordinates")).text = _coords_text(node.coords)
        return el

    if isinstance(node, LineString):
        el = ET.Element(_tag("Placemark"))
        _apply_feature(el, node, ctx)
        ls_el = ET.SubElement(el, _tag("LineString"))
        ET.SubElement(ls_el, _tag("coordinates")).text = _coords_text(node.coords)
        return el

    if isinstance(node, Polygon):
        el = ET.Element(_tag("Placemark"))
        _apply_feature(el, node, ctx)
        pol_el = ET.SubElement(el, _tag("Polygon"))
        outer_el = ET.SubElement(pol_el, _tag("outerBoundaryIs"))
        ring_el = ET.SubElement(outer_el, _tag("LinearRing"))
        ET.SubElement(ring_el, _tag("coordinates")).text = _coords_text(node.outerboundaryis)
        return el

    if isinstance(node, ScreenOverlay):
        el = ET.Element(_tag("ScreenOverlay"))
        _apply_feature(el, node, ctx)
        if node._icon is not None:
            el.append(node._icon._build_element())
        if node.overlayxy is not None:
            el.append(node.overlayxy._build_element("overlayXY"))
        if node.screenxy is not None:
            el.append(node.screenxy._build_element("screenXY"))
        if node.size is not None:
            el.append(node.size._build_element("size"))
        return el

    raise TypeError(f"tz_core.kml_writer: tipo de nodo no soportado: {type(node)!r}")


class Kml:
    """Documento KML raíz. Equivalente reducido de simplekml.Kml: envuelve
    un Document único (kml.document) y delega newX()/addfile/save/savekmz."""

    def __init__(self):
        self.document = Document()
        self._files = []

    def addfile(self, path):
        """Registra un asset a incluir en el KMZ y devuelve su ruta interna
        (files/<basename>). No deduplica ni valida existencia — igual que
        simplekml.Kml.addfile."""
        arcname = "files/" + os.path.basename(path)
        self._files.append((path, arcname))
        return arcname

    def newfolder(self, **kwargs):
        return self.document.newfolder(**kwargs)

    def newpoint(self, **kwargs):
        return self.document.newpoint(**kwargs)

    def newpolygon(self, **kwargs):
        return self.document.newpolygon(**kwargs)

    def newlinestring(self, **kwargs):
        return self.document.newlinestring(**kwargs)

    def newscreenoverlay(self, **kwargs):
        return self.document.newscreenoverlay(**kwargs)

    def _build_xml_bytes(self):
        ctx = _BuildContext()
        doc_el = ET.Element(_tag("Document"))
        _apply_feature(doc_el, self.document, ctx)
        _build_container_children(doc_el, self.document, ctx)
        for i, style_el in enumerate(ctx.style_elements):
            doc_el.insert(i, style_el)

        root = ET.Element(_tag("kml"))
        root.append(doc_el)
        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        return ET.tostring(root, encoding="UTF-8", xml_declaration=True)

    def save(self, path):
        """Escribe el .kml plano (sin comprimir) en UTF-8."""
        with open(path, "wb") as f:
            f.write(self._build_xml_bytes())

    def savekmz(self, path):
        """Escribe el .kmz: doc.kml en la raíz del ZIP seguido de los
        assets registrados vía addfile(), en orden de registro."""
        xml_bytes = self._build_xml_bytes()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", xml_bytes)
            for source_path, arcname in self._files:
                zf.write(source_path, arcname)
