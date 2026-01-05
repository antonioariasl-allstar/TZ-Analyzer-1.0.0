from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

import script_principal_bitacoras_refactory as app
from tz_core.mapping_wizard import WizardIO


def _fake_wizard_io() -> WizardIO:
    """WizardIO determinista que no requiere entrada del usuario."""

    prompts: list[str] = []
    outputs: list[str] = []

    def _prompt(message: str) -> str:
        prompts.append(message)
        return ""

    def _write(message: str) -> None:
        outputs.append(message)

    return WizardIO(input_fn=_prompt, output_fn=_write)


@pytest.mark.integration
def test_option1_manual_flow_generates_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app.bootstrap_config()

    df = pd.DataFrame(
        [
            {
                "fecha": "2025-12-31",
                "hora": "10:00:00",
                "lat": 13.70,
                "long": -89.21,
                "antena": "Antena Centro",
                "direccion": "Calle 1",
                "tel": "70000001",
                "imei": "351111111111111",
                "contacto": "71234567",
                "interaccion": "Llamada",
                "duracion": 120,
            },
            {
                "fecha": "2026-01-01",
                "hora": "08:15:00",
                "lat": 13.71,
                "long": -89.20,
                "antena": "Antena Norte",
                "direccion": "Av. Norte",
                "tel": "70000001",
                "imei": "351111111111111",
                "contacto": "79876543",
                "interaccion": "SMS",
                "duracion": 45,
            },
        ]
    )

    excel_path = tmp_path / "manual_flow.xlsx"
    df.to_excel(excel_path, index=False)

    monkeypatch.setattr(app, "_build_wizard_io", lambda: _fake_wizard_io())
    monkeypatch.setattr(app, "MANUAL_QC_MAPPING", False)
    monkeypatch.setattr(app, "seleccionar_carpeta_salida", lambda: str(tmp_path))

    result = app.run_tz_analysis(
        ruta_entrada=str(excel_path),
        hoja=0,
        top_antenas=5,
        top_contactos=5,
        solo_kmz=False,
        carpeta_salida=str(tmp_path),
    )

    html_path = result.get("html")
    kmz_path = result.get("kmz")
    log_path = result.get("log")

    assert html_path and os.path.exists(html_path), "No se generó el HTML en el flujo manual"
    assert kmz_path and os.path.exists(kmz_path), "No se generó el KMZ en el flujo manual"
    assert log_path and os.path.exists(log_path), "No se generó el log de ejecución"
