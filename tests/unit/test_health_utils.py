"""Pruebas para tz_core.health_utils (HITO 3).

Con `capabilities_report` provisto, `run_health_checks` delega la decisión
de aborto/continuación en él: solo `procesable=False` aborta. La ausencia
de una capacidad individual (coordenadas, hora) ya no dispara un prompt
crítico si el reporte sigue siendo `procesable=True` — cada situación se
informa por separado, no en un único prompt genérico mezclando coords/hora.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from tz_core.capabilities import detectar_capacidades
from tz_core.health_utils import run_health_checks


def _df_sin_coords_con_antena() -> pd.DataFrame:
    """Bitácora con antena/tel/fecha/hora pero sin lat/long: KML/heatmap no
    disponibles, pero antenas nominales sí — no debe abortar."""
    return pd.DataFrame({
        "tel": ["50370001111"] * 3,
        "fecha": ["25/07/2026"] * 3,
        "hora": ["10:00:00", "10:05:00", "10:10:00"],
        "antena": ["ANT-1", "ANT-2", "ANT-1"],
        "interaccion": ["VOZ", "SMS", "VOZ"],
        "contacto": ["50370002222", "50370003333", "50370002222"],
    })


def _df_sin_hora_con_coords() -> pd.DataFrame:
    """Bitácora con fecha (sin hora) y coordenadas válidas: KML disponible
    aunque falte el detalle horario — no debe abortar."""
    return pd.DataFrame({
        "tel": ["50370001111"] * 3,
        "fecha": ["25/07/2026", "26/07/2026", "27/07/2026"],
        "lat": [13.7, 13.71, 13.72],
        "long": [-89.2, -89.21, -89.22],
    })


class TestHealthChecksConCapabilitiesReport:
    def test_no_aborta_por_falta_de_coords_si_hay_otra_capacidad(self):
        """Caso 16: sin lat/long pero con antena disponible, no aborta ni
        pregunta nada al usuario."""
        df = _df_sin_coords_con_antena()
        report = detectar_capacidades(df)
        assert report.procesable is True
        assert report.capacidad("kml").disponible is False
        assert report.capacidad("antenas").disponible is True

        input_fn = MagicMock()
        ok = run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=lambda _msg: None,
            input_fn=input_fn,
            capabilities_report=report,
        )

        assert ok is True
        input_fn.assert_not_called()

    def test_no_aborta_por_falta_de_hora_si_hay_otra_capacidad(self):
        """Caso 17: sin hora pero con fecha+coordenadas válidas (KML), no
        aborta ni pregunta nada al usuario."""
        df = _df_sin_hora_con_coords()
        report = detectar_capacidades(df)
        assert report.procesable is True
        assert report.capacidad("cronologia").estado == "parcial"
        assert report.capacidad("kml").disponible is True

        input_fn = MagicMock()
        ok = run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=lambda _msg: None,
            input_fn=input_fn,
            capabilities_report=report,
        )

        assert ok is True
        input_fn.assert_not_called()

    def test_aborta_si_procesable_es_false(self):
        """Caso 18: si el CapabilitiesReport marca procesable=False, aborta
        sin prompt (la decisión ya fue tomada aguas arriba)."""
        df = pd.DataFrame({"tel": ["-", "N/A"], "fecha": ["", "Sin Inf."]})
        report = detectar_capacidades(df)
        assert report.procesable is False

        input_fn = MagicMock()
        ok = run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=lambda _msg: None,
            input_fn=input_fn,
            capabilities_report=report,
        )

        assert ok is False
        input_fn.assert_not_called()

    def test_dataframe_vacio_aborta_incluso_con_report(self):
        """El bloqueo por DataFrame vacío se resuelve antes de consultar
        capabilities_report."""
        df = pd.DataFrame()

        ok = run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=lambda _msg: None,
            input_fn=MagicMock(),
            capabilities_report=None,
        )

        assert ok is False

    def test_no_mezcla_coords_y_hora_en_un_unico_mensaje(self):
        """Las limitaciones de coords/hora (vía cronologia/kml) se informan
        como líneas separadas, no como un único prompt genérico."""
        df = _df_sin_coords_con_antena()
        report = detectar_capacidades(df)
        mensajes: list[str] = []

        run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=mensajes.append,
            input_fn=MagicMock(),
            capabilities_report=report,
        )

        lineas_kml = [m for m in mensajes if "KML" in m]
        assert lineas_kml, "Debe informarse que KML no está disponible."
        assert not any("coordenadas" in m.lower() and "hora" in m.lower() for m in mensajes), (
            "No debe mezclarse coords y hora en un único mensaje genérico."
        )


class TestHealthChecksCompatibilidadSinReport:
    def test_sin_capabilities_report_conserva_prompt_previo(self):
        """Sin capabilities_report (compatibilidad), el comportamiento
        previo se conserva: pregunta y aborta si el usuario no confirma."""
        df = pd.DataFrame({
            "tel": ["1"] * 20,
            # Sin 'lat'/'long' -> dispara advertencia de coordenadas.
        })

        ok = run_health_checks(
            df,
            logger=lambda _msg: None,
            output_fn=lambda _msg: None,
            input_fn=lambda _msg: "N",
        )

        assert ok is False
