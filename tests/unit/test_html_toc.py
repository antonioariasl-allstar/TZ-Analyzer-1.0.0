from tz_core.html_toc import apply_toc


def test_apply_toc_injects_nav_and_ids():
    html = """
<html><head><style></style></head><body>
<header></header>
<section class="meta"><h2>Meta</h2></section>
<section>
    <h2>Top antenas</h2>
</section>
<section>
    <h2>Contactos con más comunicación</h2>
</section>
<section>
    <h2>Antenas por rango horario</h2>
</section>
</body></html>
"""

    out = apply_toc(html)

    assert 'id="toc"' in out
    assert out.count('id="meta"') == 1
    assert out.count('id="top-antenas"') == 1
    assert out.count('id="interacciones"') == 1
    assert out.count('id="rangos"') == 1
    assert '<a href="#meta">Metadatos</a>' in out
    assert '<a href="#top-antenas">Todas las antenas</a>' in out
    assert '<a href="#interacciones">Contactos con más comunicación</a>' in out
    assert '<a href="#rangos">Antenas por rango horario</a>' in out
    # TOC debe insertarse tras </header>
    assert out.index('<nav id="toc"') > out.index('</header>')
    # CSS del TOC debe estar presente
    assert '.toc{position:sticky' in out
