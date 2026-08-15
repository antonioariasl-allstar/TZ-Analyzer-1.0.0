"""MICROBLOQUE F3.2 — flujo REAL (snapshot .execution-input-* -> HTML final)
preserva el nombre original de la bitácora en los productos visibles.

Reproduce de punta a punta, vía ``tz_web.services.process_case()`` (el mismo
servicio no interactivo que usan las rutas web) y el mismo mecanismo de
snapshot de entrada que ``tz_web.routes._start_task()`` usa antes de
arrancar el worker (``tz_web.output_transaction.create_input_snapshot``), el
escenario reportado: el archivo procesado internamente es un snapshot con
nombre técnico ``.execution-input-<uuid>.xlsx``, pero el HTML final debe
mostrar el nombre original cargado por el usuario y nunca el nombre técnico
interno.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tz_web.output_transaction import create_input_snapshot, sha256_file
from tz_web.services import CaseRequest, process_case


def _mapeo() -> dict:
    return {
        "fecha": ("col", "fecha"),
        "hora": ("col", "hora"),
        "lat": ("col", "lat"),
        "long": ("col", "long"),
        "azimut": ("col", "azimut"),
        "antena": ("col", "antena"),
        "tel": ("col", "tel"),
        "imei": ("col", "imei"),
        "contacto": ("col", "contacto"),
        "interaccion": ("col", "interaccion"),
    }


def _df_base() -> pd.DataFrame:
    return pd.DataFrame({
        "fecha": ["04/01/2026"],
        "hora": ["10:00:00"],
        "lat": [13.70],
        "long": [-89.21],
        "azimut": [45],
        "antena": ["Antena Centro"],
        "tel": ["70000001"],
        "imei": ["351111111111111"],
        "contacto": ["71000000"],
        "interaccion": ["Llamada"],
    })


@pytest.mark.integration
def test_flujo_real_preserva_nombre_original_bitacora_en_html(tmp_path):
    original_name = "TEL_PRUEBA_123.xlsx"
    uploaded_path = tmp_path / original_name
    _df_base().to_excel(uploaded_path, index=False)

    digest = sha256_file(str(uploaded_path))
    snapshot = create_input_snapshot(
        str(uploaded_path),
        str(tmp_path / ".execution-snapshots"),
        expected_sha256=digest,
        original_name=original_name,
    )

    # El archivo interno realmente procesado es el snapshot técnico, no el
    # archivo con el nombre que subió el usuario.
    assert os.path.basename(snapshot.path).startswith(".execution-input-")
    assert snapshot.original_name == original_name

    request = CaseRequest(
        ruta_archivo=snapshot.path,
        carpeta_salida=str(tmp_path / "salida"),
        mapeo=_mapeo(),
        input_sha256=snapshot.sha256,
        input_original_name=snapshot.original_name,
        duration_unit_decision="segundos",
    )
    result = process_case(request)
    assert result.success is True, result.errors

    with open(result.html_path, "r", encoding="utf-8", errors="ignore") as fh:
        html = fh.read()

    assert original_name in html
    assert ".execution-input-" not in html
