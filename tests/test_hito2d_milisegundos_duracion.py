"""Hito 2D FX-02 — Milisegundos como unidad canónica transversal de duración.

Cubre la conversión ms -> segundos (/1000) en todos los consumidores ya
integrados con DuracionEstado: interacciones_builder, html/contacts,
analytics y las burbujas KML/KMZ (format_utils). Complementa, sin sustituir,
las pruebas de segundos/minutos/hhmmss/ambigua/ausente de los Hitos 2A-2C.

Decisión de formato: el formateador HH:MM:SS histórico no admite fracciones
de segundo. 760905 ms = 760.905 s se redondea al segundo más cercano (mismo
criterio ya usado para segundos/minutos), resultando en 00:12:41. No se
amplía el formato para admitir milisegundos decimales.
"""
import re
from pathlib import Path

import pandas as pd

from tz_core.bitacora_normalization import DuracionEstado, clasificar_confiabilidad_duracion
from tz_core.format_utils import _formatear_valor_para_burbuja, armar_descripcion_compacta
from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.html.contacts import calcular_metricas_contactos
from tz_core.analytics import construir_seccion_todos_contactos


def _estado(estado: str, unidad=None, motivo="test") -> DuracionEstado:
    return DuracionEstado(
        estado=estado, unidad=unidad, columna="duracion",
        columna_original="duracion", motivo=motivo,
    )


# ── Clasificador ─────────────────────────────────────────────────────────

def test_unidad_declarada_milisegundos_es_segura():
    df = pd.DataFrame({"duracion": [760905, 239095]})
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    assert estado.estado == "segura"
    assert estado.unidad == "milisegundos"
    assert estado.motivo == "seleccion_usuario_milisegundos"


# ── format_utils: burbujas KML/HTML ─────────────────────────────────────

def test_formatear_burbuja_duracion_segura_milisegundos_convierte():
    estado = _estado("segura", unidad="milisegundos")
    out = _formatear_valor_para_burbuja("duracion", 760905, duracion_estado=estado)
    assert out == "00:12:41"
    assert "760905" not in out


def test_formatear_burbuja_milisegundos_no_se_confunde_con_segundos():
    """760905 interpretado como milisegundos (~12min) difiere radicalmente
    de 760905 interpretado como segundos (~211h): el consumidor no debe
    ignorar la unidad confirmada."""
    ms = _formatear_valor_para_burbuja(
        "duracion", 760905, duracion_estado=_estado("segura", unidad="milisegundos")
    )
    seg = _formatear_valor_para_burbuja(
        "duracion", 760905, duracion_estado=_estado("segura", unidad="segundos")
    )
    assert ms != seg
    assert ms == "00:12:41"


def test_kml_burbuja_duracion_segura_milisegundos_muestra_duracion():
    estado = _estado("segura", unidad="milisegundos")
    campos = {"antena": "ANT-A", "duracion": 760905}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "<b>Duración:</b> 00:12:41" in desc
    assert "760905" not in desc


# ── interacciones_builder ────────────────────────────────────────────────

def test_duracion_segura_milisegundos_convierte_correctamente():
    df = pd.DataFrame({
        "fecha": ["2026-08-01"],
        "hora": ["08:00:00"],
        "duracion": [760905],
    })
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    assert estado.estado == "segura" and estado.unidad == "milisegundos"

    html = construir_seccion_interacciones(df, config={}, duracion_estado=estado)

    assert re.search(r"<strong>Duración:</strong>\s*00:12:41", html), (
        "760905 ms == 760.905s -> redondeado a 761s == 00:12:41."
    )
    assert "760905" not in html


# ── contacts: acumulados usan /1000 ─────────────────────────────────────

def test_contacts_duracion_segura_milisegundos_convierte():
    df = pd.DataFrame({"contacto": ["70001234", "70001234"], "duracion": [760905, 239095]})
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    metricas = calcular_metricas_contactos(
        df, destino_col="contacto", duracion_col="duracion", duracion_estado=estado
    )
    assert metricas["70001234"]["total_duracion_seg"] == 1000.0
    assert metricas["70001234"]["duracion_confiable"] is True


# ── analytics: minutos acumulados parten de segundos normalizados ───────

def test_analytics_segura_milisegundos_convierte_minutos():
    df = pd.DataFrame({
        "contacto":                ["70001234", "70001234"],
        "contacto_categoria":      ["telefonico_plausible"] * 2,
        "contacto_limpio":         ["70001234"] * 2,
        "contacto_motivo":         ["voz_longitud_valida"] * 2,
        "tipo_evento_normalizado": ["VOZ"] * 2,
        "duracion":                [60000, 60000],
    })
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    result = construir_seccion_todos_contactos(df, duracion_estado=estado)
    assert ">2<" in result  # (60000+60000)ms / 1000 = 120s = 2 minutos


# ── Consistencia transversal HTML <-> KML ───────────────────────────────

def test_consistencia_transversal_duracion_milisegundos_html_y_kml(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = pd.DataFrame({
        "fecha": ["01/01/2026"],
        "hora": ["08:00:00"],
        "antena": ["ANT-A"],
        "lat": [13.6929],
        "long": [-89.2182],
        "contacto": ["70011111"],
        "interaccion": ["LLAMADA ENTRANTE"],
        "duracion": [760905],
    })
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    assert estado.estado == "segura" and estado.unidad == "milisegundos"

    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")
    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
        duracion_estado=estado,
    )
    html_contenido = Path(html_path).read_text(encoding="utf-8")

    assert "760905" not in html_contenido
    assert re.search(r"00:12:41", html_contenido)

    campos = {"antena": "ANT-A", "duracion": 760905}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "<b>Duración:</b> 00:12:41" in desc
    assert "760905" not in desc
