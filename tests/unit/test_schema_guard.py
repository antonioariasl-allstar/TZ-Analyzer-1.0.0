"""Pruebas para tz_core.schema_guard (HITO 3).

Política de producto verificada aquí: ningún campo analítico individual
(tel/imei, fecha/hora, contacto, interaccion, antena, lat/long, azimut) es
un bloqueante global. `validate_schema_or_abort` solo debe abortar
(`SystemExit`) cuando `detectar_capacidades` marca `procesable=False`
(DataFrame vacío, sin columnas o sin ningún valor analíticamente
significativo).
"""

from __future__ import annotations

import pandas as pd
import pytest

from tz_core.schema_guard import validate_schema_or_abort


def _validar(df: pd.DataFrame, config=None):
    mensajes: list[str] = []
    return (
        validate_schema_or_abort(
            df,
            config=config or {},
            logger=lambda _msg: None,
            output_fn=mensajes.append,
        ),
        mensajes,
    )


class TestNoAbortaPorCamposIndividualesAusentes:
    def test_no_aborta_sin_contacto_ni_interaccion(self):
        """Caso 1: bitácora de antenas sin contacto ni interaccion no aborta."""
        df = pd.DataFrame({
            "fecha": ["25/07/2026"] * 3,
            "hora": ["10:00:00"] * 3,
            "tel": ["50370001111"] * 3,
            "antena": ["ANT-1", "ANT-2", "ANT-1"],
            "lat": [13.7, 13.71, 13.7],
            "long": [-89.2, -89.21, -89.2],
        })

        ok, _ = _validar(df)

        assert ok is True

    def test_no_aborta_sin_fecha_hora_si_hay_kml_valido(self):
        """Caso 2: sin columnas fecha/hora, pero con lat/long válidos."""
        df = pd.DataFrame({
            "tel": ["50370001111"] * 3,
            "lat": [13.7, 13.71, 13.72],
            "long": [-89.2, -89.21, -89.22],
        })

        ok, _ = _validar(df)

        assert ok is True

    def test_no_aborta_sin_tel_ni_imei_si_hay_antenas_kml(self):
        """Caso 3: sin identificación (tel/imei), pero con antena y coordenadas."""
        df = pd.DataFrame({
            "fecha": ["25/07/2026"] * 2,
            "hora": ["10:00:00", "10:05:00"],
            "antena": ["ANT-1", "ANT-2"],
            "lat": [13.7, 13.71],
            "long": [-89.2, -89.21],
        })

        ok, _ = _validar(df)

        assert ok is True

    def test_no_aborta_antena_sin_coordenadas(self):
        """Caso 4: antena presente, sin columnas lat/long."""
        df = pd.DataFrame({
            "tel": ["50370001111"] * 2,
            "antena": ["ANT-1", "ANT-2"],
        })

        ok, _ = _validar(df)

        assert ok is True

    def test_no_aborta_coordenadas_sin_antena(self):
        """Caso 5: lat/long presentes, sin columna antena."""
        df = pd.DataFrame({
            "tel": ["50370001111"] * 2,
            "lat": [13.7, 13.71],
            "long": [-89.2, -89.21],
        })

        ok, _ = _validar(df)

        assert ok is True

    def test_no_aborta_sin_azimut(self):
        """Caso 6: antena y coordenadas presentes, sin columna azimut."""
        df = pd.DataFrame({
            "tel": ["50370001111"] * 2,
            "antena": ["ANT-1", "ANT-2"],
            "lat": [13.7, 13.71],
            "long": [-89.2, -89.21],
        })

        ok, _ = _validar(df)

        assert ok is True


class TestBloqueantesGlobalesReales:
    def test_aborta_dataframe_vacio(self):
        """Caso 7: DataFrame vacío sí aborta (bloqueante global real)."""
        df = pd.DataFrame()

        with pytest.raises(SystemExit):
            _validar(df)

    def test_aborta_sin_valores_significativos(self):
        """Caso 8: DataFrame con filas/columnas pero solo placeholders."""
        df = pd.DataFrame({
            "tel": ["-", "N/A"],
            "fecha": ["", "Sin Inf."],
            "antena": ["s/i", "0"],
        })

        with pytest.raises(SystemExit):
            _validar(df)
