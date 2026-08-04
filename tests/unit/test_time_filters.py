"""
Tests para tz_core.time_filters

Cubre el parseo robusto de fechas en aplicar_filtros_tiempo (S2):
fechas ISO (YYYY-MM-DD[ HH:MM:SS]) deben interpretarse año-mes-día,
fechas DD/MM/YYYY deben seguir interpretándose con dayfirst=True,
y datetime_evento debe usarse como fuente canónica cuando exista.
"""

import pandas as pd

from tz_core.time_filters import aplicar_filtros_tiempo


def _df_iso():
    return pd.DataFrame(
        [
            {"fecha": "2026-07-25 00:00:00", "hora": "10:00:00", "antena": "A1"},
            {"fecha": "2026-07-24 00:00:00", "hora": "10:00:00", "antena": "A2"},
        ]
    )


def _df_ddmmyyyy():
    return pd.DataFrame(
        [
            {"fecha": "25/07/2026", "hora": "10:00:00", "antena": "A1"},
            {"fecha": "24/07/2026", "hora": "10:00:00", "antena": "A2"},
        ]
    )


class TestDiaEspecifico:
    """Caso 1 y 2: filtro de día específico con fecha ISO y con fecha DD/MM/YYYY."""

    def test_dia_especifico_conserva_fila_con_fecha_iso(self):
        df = _df_iso()
        filtros = {
            "tipo": "dia",
            "dia": "25/07/2026",
            "desde": None,
            "hasta": None,
            "hora_ini": None,
            "hora_fin": None,
        }

        resultado, _resumen = aplicar_filtros_tiempo(df, filtros)

        assert len(resultado) == 1
        assert resultado.iloc[0]["antena"] == "A1"

    def test_dia_especifico_conserva_fila_con_fecha_ddmmyyyy(self):
        df = _df_ddmmyyyy()
        filtros = {
            "tipo": "dia",
            "dia": "25/07/2026",
            "desde": None,
            "hasta": None,
            "hora_ini": None,
            "hora_fin": None,
        }

        resultado, _resumen = aplicar_filtros_tiempo(df, filtros)

        assert len(resultado) == 1
        assert resultado.iloc[0]["antena"] == "A1"


class TestRangoDeDias:
    """Caso 3: rango de días que incluye 25/07/2026, con fechas ISO."""

    def test_rango_de_dias_incluye_25_07_2026(self):
        df = pd.DataFrame(
            [
                {"fecha": "2026-07-20 00:00:00", "hora": "10:00:00", "antena": "antes"},
                {"fecha": "2026-07-25 00:00:00", "hora": "10:00:00", "antena": "dentro"},
                {"fecha": "2026-08-05 00:00:00", "hora": "10:00:00", "antena": "despues"},
            ]
        )
        filtros = {
            "tipo": "rango_dias",
            "dia": None,
            "desde": "22/07/2026",
            "hasta": "28/07/2026",
            "hora_ini": None,
            "hora_fin": None,
        }

        resultado, _resumen = aplicar_filtros_tiempo(df, filtros)

        assert list(resultado["antena"]) == ["dentro"]


class TestRangoDeHorasEnDia:
    """Caso 4: rango de horas en un día específico, fecha ISO dentro del rango horario."""

    def test_rango_horas_en_dia_conserva_fila_dentro_del_rango(self):
        df = pd.DataFrame(
            [
                {"fecha": "2026-07-25 00:00:00", "hora": "10:00:00", "antena": "dentro_hora"},
                {"fecha": "2026-07-25 00:00:00", "hora": "23:00:00", "antena": "fuera_hora"},
                {"fecha": "2026-07-24 00:00:00", "hora": "10:00:00", "antena": "otro_dia"},
            ]
        )
        filtros = {
            "tipo": "rango_horas_dia",
            "dia": "25/07/2026",
            "desde": None,
            "hasta": None,
            "hora_ini": "08:00:00",
            "hora_fin": "12:00:00",
        }

        resultado, _resumen = aplicar_filtros_tiempo(df, filtros)

        assert list(resultado["antena"]) == ["dentro_hora"]


class TestRangoDeHorasGlobal:
    """Caso 5: rango de horas aplicado a todos los días — sin regresión, no usa 'fecha'."""

    def test_rango_horas_global_no_usa_fecha(self):
        df = pd.DataFrame(
            [
                {"fecha": "2026-07-25 00:00:00", "hora": "10:00:00", "antena": "dentro"},
                {"fecha": "2000-01-01 00:00:00", "hora": "10:00:00", "antena": "otra_fecha_misma_hora"},
                {"fecha": "2026-07-25 00:00:00", "hora": "23:00:00", "antena": "fuera_hora"},
            ]
        )
        filtros = {
            "tipo": "rango_horas",
            "dia": None,
            "desde": None,
            "hasta": None,
            "hora_ini": "08:00:00",
            "hora_fin": "12:00:00",
        }

        resultado, _resumen = aplicar_filtros_tiempo(df, filtros)

        assert set(resultado["antena"]) == {"dentro", "otra_fecha_misma_hora"}


class TestFechaIsoNoSeInvierte:
    """Caso 6: 2026-07-01 debe seguir siendo 1 de julio, no 7 de enero (causa raíz S2)."""

    def test_fecha_iso_dia_menor_a_12_no_se_invierte(self):
        df = pd.DataFrame(
            [
                {"fecha": "2026-07-01 00:00:00", "hora": "10:00:00", "antena": "primero_julio"},
            ]
        )

        filtro_julio = {
            "tipo": "dia",
            "dia": "01/07/2026",
            "desde": None,
            "hasta": None,
            "hora_ini": None,
            "hora_fin": None,
        }
        resultado_julio, _ = aplicar_filtros_tiempo(df, filtro_julio)
        assert len(resultado_julio) == 1

        filtro_enero = {
            "tipo": "dia",
            "dia": "07/01/2026",
            "desde": None,
            "hasta": None,
            "hora_ini": None,
            "hora_fin": None,
        }
        resultado_enero, _ = aplicar_filtros_tiempo(df, filtro_enero)
        assert len(resultado_enero) == 0
