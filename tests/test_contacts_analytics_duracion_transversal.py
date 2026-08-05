"""Hito 2B FX-02 — Propagación transversal de DuracionEstado y del criterio
único de contacto válido a tz_core/html/contacts.py y tz_core/analytics.py.

Complementa (sin modificar) test_build_top_contacts_sections.py y
test_construir_seccion_todos_contactos.py, que ya cubren el contrato de
retorno y los bloques P0-B con "_sec" pre-resuelto.
"""
import re

import pandas as pd

from tz_core.bitacora_normalization import clasificar_confiabilidad_duracion
from tz_core.html.contacts import (
    build_top_contacts_sections,
    calcular_metricas_contactos,
    interpretar_contactos,
)
from tz_core.analytics import construir_seccion_todos_contactos
from tz_core.interacciones_builder import construir_seccion_interacciones


def _df_p0b(categorias, contactos_limpios, contactos_raw=None, durs=None):
    n = len(categorias)
    return pd.DataFrame({
        "contacto":                contactos_raw or [f"700{i:04d}" for i in range(n)],
        "contacto_categoria":      categorias,
        "contacto_limpio":         contactos_limpios,
        "contacto_motivo":         ["voz_longitud_valida"] * n,
        "tipo_evento_normalizado": ["VOZ"] * n,
        "duracion":                durs or [60] * n,
    })


# ── 2/3/4: contacts — duración segura por unidad ────────────────────────────

def test_contacts_duracion_segura_segundos_mantiene_metricas():
    df = pd.DataFrame({"contacto": ["70001234", "70001234"], "duracion_seg": [30, 90]})
    metricas = calcular_metricas_contactos(df, destino_col="contacto", duracion_col="duracion_seg")
    assert metricas["70001234"]["total_duracion_seg"] == 120.0
    assert metricas["70001234"]["duracion_confiable"] is True


def test_contacts_duracion_segura_minutos_convierte():
    df = pd.DataFrame({"contacto": ["70001234", "70001234"], "duracion": [5, 10]})
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="minutos")
    metricas = calcular_metricas_contactos(
        df, destino_col="contacto", duracion_col="duracion", duracion_estado=estado
    )
    assert metricas["70001234"]["total_duracion_seg"] == 900.0
    assert metricas["70001234"]["duracion_confiable"] is True


def test_contacts_duracion_segura_hhmmss_mantiene_metricas():
    df = pd.DataFrame({"contacto": ["70001234", "70001234"], "duracion": ["00:00:30", "00:01:30"]})
    metricas = calcular_metricas_contactos(df, destino_col="contacto", duracion_col="duracion")
    assert metricas["70001234"]["total_duracion_seg"] == 120.0
    assert metricas["70001234"]["duracion_confiable"] is True


# ── 5/6: contacts — ambigua conserva frecuencia, omite duración ─────────────

def test_contacts_ambigua_conserva_top_por_frecuencia():
    df = _df_p0b(
        categorias=["telefonico_plausible"] * 3,
        contactos_limpios=["70001234", "70001234", "70005678"],
        durs=[30, 5400, 45],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "70001234" in cnt_html
    assert "2 <span" in cnt_html


def test_contacts_ambigua_omite_top_por_duracion():
    df = _df_p0b(
        categorias=["telefonico_plausible"] * 2,
        contactos_limpios=["70001234", "70001234"],
        durs=[30, 5400],
    )
    _, dur_html, _ = build_top_contacts_sections(df)
    assert "no pudo confirmarse" in dur_html
    assert "<table" not in dur_html


# ── 7: contacts — narrativa no usa duración ambigua ─────────────────────────

def test_interpretar_contactos_no_narra_duracion_no_confiable():
    metricas = {
        "70001234": {
            "total_interacciones": 5,
            "total_duracion_seg": 0.0,
            "promedio_duracion_seg": 0.0,
            "dias_activos": 2,
            "primer_contacto": "2026-01-01",
            "ultimo_contacto": "2026-01-02",
            "duracion_confiable": False,
        }
    }
    resultado = interpretar_contactos(metricas, total_interacciones=5, total_duracion=0.0)
    narrativa = resultado["70001234"]["narrativa"]
    assert re.search(r"\(\d+s\)", narrativa) is None, (
        "No debe narrarse una duración en segundos cuando la unidad no es confiable."
    )
    assert "no pudo confirmarse" in narrativa


# ── 8/9: analytics — ambigua omite minutos, segura los mantiene ────────────

def test_analytics_ambigua_no_muestra_minutos_acumulados():
    df = pd.DataFrame({
        "contacto":                ["70001234"],
        "contacto_categoria":      ["telefonico_plausible"],
        "contacto_limpio":         ["70001234"],
        "contacto_motivo":         ["voz_longitud_valida"],
        "tipo_evento_normalizado": ["VOZ"],
        "duracion":                [5400],
    })
    result = construir_seccion_todos_contactos(df)
    assert "N/D" in result
    assert "no pudo confirmarse" in result


def test_analytics_segura_mantiene_metricas():
    df = pd.DataFrame({
        "contacto":                ["70001234", "70001234"],
        "contacto_categoria":      ["telefonico_plausible"] * 2,
        "contacto_limpio":         ["70001234"] * 2,
        "contacto_motivo":         ["voz_longitud_valida"] * 2,
        "tipo_evento_normalizado": ["VOZ"] * 2,
        "duracion":                ["00:01:00", "00:01:00"],
    })
    result = construir_seccion_todos_contactos(df)
    assert ">2<" in result  # 120s / 60 = 2 minutos


# ── 10: placeholder no cuenta como contacto en contacts/analytics ──────────

def test_contacts_placeholder_no_cuenta_como_contacto():
    df = pd.DataFrame({"contacto": ["SIN DETERMINAR", "-", ""], "duracion": [10, 20, 30]})
    metricas = calcular_metricas_contactos(df, destino_col="contacto", duracion_col="duracion")
    assert metricas == {}


def test_analytics_placeholder_no_aparece_en_bloque_de_telefonicos():
    df = pd.DataFrame({
        "contacto":                ["SIN DETERMINAR"],
        "contacto_categoria":      ["tecnico_no_personal"],
        "contacto_limpio":         [None],
        "contacto_motivo":         ["vacio_o_nulo"],
        "tipo_evento_normalizado": ["DESCONOCIDO"],
        "_sec":                    [0],
    })
    result = construir_seccion_todos_contactos(df)
    assert "No se registraron números con formato telefónico" in result


# ── 11: consistencia transversal ────────────────────────────────────────────

def test_consistencia_transversal_duracion_ambigua():
    """La misma entrada ambigua no debe presentarse como duración confirmada
    en interacciones_builder, contacts ni analytics."""
    df = pd.DataFrame({
        "fecha":                   ["2026-08-01", "2026-08-01"],
        "hora":                    ["08:00:00", "09:00:00"],
        "contacto":                ["70001234", "70001234"],
        "duracion":                [30, 5400],
        "contacto_categoria":      ["telefonico_plausible"] * 2,
        "contacto_limpio":         ["70001234"] * 2,
        "contacto_motivo":         ["voz_longitud_valida"] * 2,
        "tipo_evento_normalizado": ["VOZ"] * 2,
    })

    html_interacciones = construir_seccion_interacciones(df, config={})
    _, dur_html, _ = build_top_contacts_sections(df)
    html_analytics = construir_seccion_todos_contactos(df)

    assert not re.search(r"<strong>Duraci[oó]n:</strong>\s*\d{2}:\d{2}:\d{2}", html_interacciones)
    assert "<table" not in dur_html
    assert "N/D" in html_analytics

    for html in (html_interacciones, dur_html, html_analytics):
        assert "no pudo confirmarse" in html


def test_kpi_no_presenta_duracion_evidencia():
    """Diagnóstico Tarea 4: kpi.py no calcula ni presenta duración, por lo
    que no requiere DuracionEstado ni modificación en este hito."""
    from tz_core.html.kpi import generate_kpi_section

    html = generate_kpi_section(10, 8, 2, 3, 3, "Celdas (CID) únicas", "ANT1", 5, 50.0)
    assert "duraci" not in html.lower()
