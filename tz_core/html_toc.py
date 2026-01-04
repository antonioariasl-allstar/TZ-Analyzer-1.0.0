"""Helpers para insertar TOC y asegurar anclas en reportes HTML."""

from __future__ import annotations

from typing import List


def _ensure_section_ids(html: str) -> str:
    """Garantiza IDs básicos en secciones conocidas para el TOC."""
    out = html.replace('<section class="meta">', '<section id="meta" class="meta">')
    out = out.replace('<section>\n    <h2>Top antenas</h2>', '<section id="top-antenas">\n    <h2>Top antenas</h2>')
    out = out.replace('<h2 id="interacciones">Interacciones y contactos</h2>', '<h2 id="interacciones">Contactos con más comunicación</h2>')
    out = out.replace('<h2>Contactos con más comunicación</h2>', '<h2 id="interacciones">Contactos con más comunicación</h2>')
    out = out.replace('<h2>Antenas por rango horario</h2>', '<h2 id="rangos">Antenas por rango horario</h2>')
    return out


def _collect_links(html: str) -> List[str]:
    """Construye la lista de enlaces del TOC según las secciones presentes."""
    links: List[str] = []
    if 'id="meta"' in html:
        links.append('<a href="#meta">Metadatos</a>')
    if 'id="resumen-antenas"' in html:
        links.append('<a href="#resumen-antenas">Antenas más activadas</a>')
    if 'id="interacciones"' in html:
        links.append('<a href="#interacciones">Contactos con más comunicación</a>')

    _id_rangos = None
    if 'id="antenas-rangos"' in html:
        _id_rangos = 'antenas-rangos'
    elif 'id="rangos"' in html:
        _id_rangos = 'rangos'
    if _id_rangos:
        links.append(f'<a href="#{_id_rangos}">Antenas por rango horario</a>')

    if 'id="historial-cambios"' in html:
        links.append('<a href="#historial-cambios">Historial de cambios de antena</a>')
    if 'id="interacciones-recientes"' in html:
        links.append('<a href="#interacciones-recientes">Interacciones recientes</a>')
    if 'id="top-antenas"' in html:
        links.append('<a href="#top-antenas">Todas las antenas</a>')
    if 'id="todos-contactos"' in html:
        links.append('<a href="#todos-contactos">Todos los contactos</a>')
    return links


def apply_toc(html: str) -> str:
    """Inserta TOC sticky y asegura anclas; retorna HTML modificado."""
    try:
        if not html:
            return html

        html_out = _ensure_section_ids(html)
        links = _collect_links(html_out)
        if not links:
            return html_out

        toc_html = '<nav id="toc" class="toc" style="z-index:999; background:#fff; border-bottom:1px solid #e5e7eb; box-shadow:0 2px 6px rgba(0,0,0,.06); padding:8px 12px;">' + ' ... '.join(links) + '</nav>'

        css_toc = """
.toc{position:sticky;top:0;background:#fff;padding:8px 0 10px;margin:6px 0 10px;border-bottom:1px solid #eee;z-index:999}
.toc a{margin-right:10px;text-decoration:none;color:var(--accent);font-size:13px}
.toc a:hover{text-decoration:underline}
@media (max-width: 768px) {
  .toc{position:relative;top:auto;}
}
"""
        if "</style>" in html_out:
            html_out = html_out.replace("</style>", css_toc + "</style>", 1)
        else:
            html_out = css_toc + html_out

        if "</header>" in html_out:
            html_out = html_out.replace("</header>", "</header>\n  " + toc_html, 1)
        else:
            html_out = toc_html + html_out

        return html_out
    except Exception:
        return html
