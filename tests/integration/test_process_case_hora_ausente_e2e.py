"""MICROBLOQUE F3.1C — flujo REAL (mapeo web -> HTML final) con hora omitida.

Reproduce de punta a punta, vía ``tz_web.services.process_case()`` (el mismo
servicio no interactivo que usan las rutas web), el escenario reportado
manualmente: fecha mapeada, hora deliberadamente NO mapeada.

Causa raíz confirmada: ``tz_core.mapping_wizard.normalize_wizard_datetime_fields``
—llamada incondicionalmente por ``run_ingestion_pipeline`` tras aplicar el
mapeo, exista o no columna 'hora' en el DataFrame— sintetizaba, cuando 'hora'
no existía en absoluto, una columna 'hora' rellena con
``fecha.dt.strftime("%H:%M:%S")``. Para una fecha sin componente horario
("04/01/2026") eso produce "00:00:00" en TODAS las filas: una medianoche
fabricada, indistinguible aguas abajo (``es_valor_significativo``) de una
hora real observada. Tanto Metadatos (``kpi._calcular_rango_temporal``) como
"Filtrar por fecha" (``interacciones_builder._fmt_hora``) ya habían sido
corregidos en F3.1/F3.1B para no inventar hora — pero ambos confían en el
contenido real de la columna 'hora' que el mapeo les entrega, y el mapeo
mismo era quien fabricaba el dato antes de que llegara.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pytest

from tz_web.services import CaseRequest, CaseResult, process_case


def _mapeo(*, con_hora: bool) -> dict:
    mapeo = {
        "fecha": ("col", "fecha"),
        "lat": ("col", "lat"),
        "long": ("col", "long"),
        "azimut": ("col", "azimut"),
        "antena": ("col", "antena"),
        "tel": ("col", "tel"),
        "imei": ("col", "imei"),
        "contacto": ("col", "contacto"),
        "interaccion": ("col", "interaccion"),
    }
    mapeo["hora"] = ("col", "hora") if con_hora else ("omitido", None)
    return mapeo


def _df_base(fechas: list[str], horas: list[str] | None = None) -> pd.DataFrame:
    n = len(fechas)
    data = {
        "fecha": fechas,
        "lat": [13.70] * n,
        "long": [-89.21] * n,
        "azimut": [45] * n,
        "antena": ["Antena Centro"] * n,
        "tel": ["70000001"] * n,
        "imei": ["351111111111111"] * n,
        "contacto": [f"7100000{i}" for i in range(n)],
        "interaccion": ["Llamada"] * n,
    }
    if horas is not None:
        data["hora"] = horas
    return pd.DataFrame(data)


def _run(tmp_path, df: pd.DataFrame, *, con_hora: bool) -> CaseResult:
    excel_path = tmp_path / "bitacora.xlsx"
    df.to_excel(excel_path, index=False)
    request = CaseRequest(
        ruta_archivo=str(excel_path),
        carpeta_salida=str(tmp_path / "salida"),
        mapeo=_mapeo(con_hora=con_hora),
        duration_unit_decision="segundos",
    )
    result = process_case(request)
    assert result.success is True, result.errors
    return result


def _html(result: CaseResult) -> str:
    with open(result.html_path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _periodo_analizado(html: str) -> str:
    m = re.search(
        r"Periodo analizado:.*?<td class=\"mono\">([^<]*)</td>",
        html,
        re.DOTALL,
    )
    assert m, "No se encontró la fila 'Periodo analizado' en Metadatos"
    return m.group(1)


def _hora_td_por_contacto(html: str, contacto: str) -> str:
    m = re.search(
        r'<td class="mono">\d+</td><td>' + re.escape(contacto) +
        r'</td><td class="mono nowrap">([^<]*)</td>',
        html,
    )
    assert m, f"No se encontró fila de tabla para contacto {contacto!r} en el HTML"
    return m.group(1)


@pytest.mark.integration
def test_flujo_real_fecha_mapeada_hora_omitida_no_muestra_medianoche_sintetica(tmp_path):
    df = _df_base(["04/01/2026", "05/01/2026"])
    result = _run(tmp_path, df, con_hora=False)
    html = _html(result)

    periodo = _periodo_analizado(html)
    # A. Metadatos degrada a solo fecha.
    assert periodo == "04/01/2026 — 05/01/2026"
    # B. Metadatos NO fabrica hora.
    assert "00:00" not in periodo

    # C. "Filtrar por fecha" (tabla de interacciones) muestra "No disponible".
    assert _hora_td_por_contacto(html, "7100000" + "0") == "No disponible"
    assert _hora_td_por_contacto(html, "7100000" + "1") == "No disponible"

    # D. Ningún 00:00/00:00:00 sintético se filtró al HTML final.
    assert "00:00:00" not in html
    assert "00:00 — " not in html


@pytest.mark.integration
def test_flujo_real_hora_fuente_medianoche_real_se_conserva(tmp_path):
    df = _df_base(["04/01/2026"], horas=["00:00:00"])
    result = _run(tmp_path, df, con_hora=True)
    html = _html(result)

    # Medianoche REAL observada en la fuente: debe conservarse tal cual,
    # tanto en Metadatos como en "Filtrar por fecha".
    periodo = _periodo_analizado(html)
    assert periodo == "04/01/2026 00:00 — 04/01/2026 00:00"
    assert _hora_td_por_contacto(html, "7100000" + "0") == "00:00:00"
