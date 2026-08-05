"""Hito 2C FX-02 — Coherencia de DuracionEstado en burbujas KML/KMZ.

Cubre:
  7. KML con duración segura muestra duración.
  8. KML con duración ambigua no muestra entero crudo ni HH:MM:SS.
  9. KML con duración ausente omite la línea.
  10. Consistencia transversal: misma entrada ambigua -> HTML completo sin
      duración confirmada y KML/KMZ sin duración confirmada.
  12. Compatibilidad: _formatear_valor_para_burbuja/armar_descripcion_compacta
      sin duracion_estado conservan el comportamiento histórico.

No usa snapshots completos: inspecciona directamente la burbuja HTML generada
por armar_descripcion_compacta / _formatear_valor_para_burbuja.
"""
import re
from pathlib import Path

import pandas as pd

from tz_core.bitacora_normalization import DuracionEstado, clasificar_confiabilidad_duracion
from tz_core.format_utils import _formatear_valor_para_burbuja, armar_descripcion_compacta


def _estado(estado: str, unidad=None, motivo="test") -> DuracionEstado:
    return DuracionEstado(
        estado=estado, unidad=unidad, columna="duracion",
        columna_original="duracion", motivo=motivo,
    )


# ── 7: duración segura ──────────────────────────────────────────────────

def test_formatear_burbuja_duracion_segura_segundos():
    estado = _estado("segura", unidad="segundos")
    out = _formatear_valor_para_burbuja("duracion", 65, duracion_estado=estado)
    assert out == "00:01:05"


def test_formatear_burbuja_duracion_segura_minutos_convierte():
    estado = _estado("segura", unidad="minutos")
    out = _formatear_valor_para_burbuja("duracion", 2, duracion_estado=estado)
    assert out == "00:02:00"


def test_formatear_burbuja_duracion_segura_hhmmss():
    estado = _estado("segura", unidad="hhmmss")
    out = _formatear_valor_para_burbuja("duracion", "01:02:03", duracion_estado=estado)
    assert out == "01:02:03"


def test_kml_burbuja_duracion_segura_muestra_duracion():
    estado = _estado("segura", unidad="segundos")
    campos = {"antena": "ANT-A", "duracion": 90}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "<b>Duración:</b> 00:01:30" in desc


# ── 8: duración ambigua ─────────────────────────────────────────────────

def test_formatear_burbuja_duracion_ambigua_no_es_entero_crudo():
    estado = _estado("ambigua", unidad="desconocida")
    out = _formatear_valor_para_burbuja("duracion", 5400, duracion_estado=estado)
    assert out == "unidad no confirmada"
    assert "5400" not in out
    assert not re.match(r"^\d{2}:\d{2}:\d{2}$", out)


def test_kml_burbuja_duracion_ambigua_no_muestra_entero_ni_hhmmss():
    estado = _estado("ambigua", unidad="desconocida")
    campos = {"antena": "ANT-A", "duracion": 5400}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "Duración" in desc
    assert "5400" not in desc
    assert not re.search(r"<b>Duraci[oó]n:</b>\s*\d{2}:\d{2}:\d{2}", desc)


# ── 9: duración ausente ─────────────────────────────────────────────────

def test_formatear_burbuja_duracion_ausente_es_none():
    estado = _estado("ausente", unidad=None)
    out = _formatear_valor_para_burbuja("duracion", 120, duracion_estado=estado)
    assert out is None


def test_kml_burbuja_duracion_ausente_omite_linea():
    estado = _estado("ausente", unidad=None)
    campos = {"antena": "ANT-A", "duracion": 120}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "Duración" not in desc


# ── 10: consistencia transversal HTML <-> KML para entrada ambigua ────────

def test_consistencia_transversal_duracion_ambigua_html_y_kml(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = pd.DataFrame(
        {
            "fecha": ["01/01/2026", "02/01/2026"],
            "hora": ["08:00:00", "09:00:00"],
            "antena": ["ANT-A", "ANT-B"],
            "lat": [13.6929, 13.7000],
            "long": [-89.2182, -89.2100],
            "contacto": ["70011111", "70022222"],
            "interaccion": ["LLAMADA ENTRANTE", "SMS SALIENTE"],
            "duracion": [30, 5400],
        }
    )
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "ambigua"

    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")
    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
        duracion_estado=estado,
    )
    html_contenido = Path(html_path).read_text(encoding="utf-8")

    # HTML completo: ninguna duración confirmada en formato HH:MM:SS
    assert not re.search(r"<strong>Duraci[oó]n:</strong>\s*\d{2}:\d{2}:\d{2}", html_contenido)
    assert "unidad de duración no confirmada" in html_contenido

    # KML/KMZ (burbuja): mismo criterio, ni entero crudo ni HH:MM:SS confirmado
    campos = {"antena": "ANT-A", "duracion": 5400}
    desc = armar_descripcion_compacta(campos, duracion_estado=estado)
    assert "5400" not in desc
    assert not re.search(r"<b>Duraci[oó]n:</b>\s*\d{2}:\d{2}:\d{2}", desc)


# ── 12: compatibilidad sin duracion_estado (comportamiento histórico) ─────

def test_formatear_burbuja_duracion_compatible_sin_estado():
    out = _formatear_valor_para_burbuja("duracion", 3661)
    assert out == "01:01:01"


def test_armar_descripcion_compacta_compatible_sin_estado():
    campos = {"antena": "ANT-A", "duracion": 90}
    desc = armar_descripcion_compacta(campos)
    assert "<b>Duración:</b> 00:01:30" in desc
