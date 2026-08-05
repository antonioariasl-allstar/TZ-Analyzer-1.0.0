"""
Tests para tz_core.capabilities (HITO 1 — modelo puro de capacidades).

Cubre las 20 reglas aprobadas: bloqueo global, disponibilidad parcial/total
por capacidad, y las invariantes de pureza (no modifica df, es determinista).
"""

from __future__ import annotations

import pandas as pd
import pytest

from tz_core.bitacora_normalization import DuracionEstado
from tz_core.capabilities import Capacidad, CapabilitiesReport, detectar_capacidades


def _bitacora_completa() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tel": "50370001111",
                "imei": "356938035643809",
                "imsi": "334020000000001",
                "fecha": "25/07/2026",
                "hora": "10:00:00",
                "contacto": "50370002222",
                "interaccion": "VOZ",
                "duracion": "00:05:30",
                "antena": "ANT-1",
                "lat": 13.7,
                "long": -89.2,
                "azimut": 120,
            },
            {
                "tel": "50370001111",
                "imei": "356938035643809",
                "imsi": "334020000000001",
                "fecha": "25/07/2026",
                "hora": "10:05:00",
                "contacto": "50370003333",
                "interaccion": "SMS",
                "duracion": "00:00:15",
                "antena": "ANT-2",
                "lat": 13.71,
                "long": -89.21,
                "azimut": 200,
            },
        ]
    )


class TestBloqueoGlobal:
    def test_dataframe_vacio_bloquea_globalmente(self):
        df = pd.DataFrame()

        report = detectar_capacidades(df)

        assert report.procesable is False
        assert report.bloqueos_globales == ("dataframe_vacio",)
        assert len(report.capacidades) > 0
        for capacidad in report.capacidades.values():
            assert capacidad.disponible is False
            assert capacidad.estado == "bloqueada"

    def test_dataframe_solo_placeholders_bloquea_por_sin_datos_procesables(self):
        df = pd.DataFrame({"tel": ["-", "N/A"], "fecha": ["", "Sin Inf."]})

        report = detectar_capacidades(df)

        assert report.procesable is False
        assert report.bloqueos_globales == ("sin_datos_procesables",)


class TestBitacoraCompleta:
    def test_todas_las_capacidades_esperadas_disponibles(self):
        df = _bitacora_completa()

        report = detectar_capacidades(df)

        assert report.procesable is True
        assert report.bloqueos_globales == ()
        esperadas = (
            "identificacion",
            "cronologia",
            "filtros_temporales",
            "antenas",
            "antenas_por_horario",
            "kml",
            "heatmap",
            "contactos",
            "tipo_evento",
            "duracion",
            "orientacion",
            "metadatos",
            "hashes",
        )
        for nombre in esperadas:
            capacidad = report.capacidad(nombre)
            assert capacidad.disponible is True, f"{nombre} debería estar disponible"
            assert capacidad.estado == "disponible", f"{nombre} debería ser 'disponible' (no parcial)"


class TestFX02SinContactoNiInteraccion:
    def test_antenas_kml_cronologia_disponibles_contactos_tipo_evento_no(self):
        df = _bitacora_completa().drop(columns=["contacto", "interaccion"])

        report = detectar_capacidades(df)

        assert report.capacidad("contactos").disponible is False
        assert report.capacidad("tipo_evento").disponible is False
        assert report.capacidad("antenas").disponible is True
        assert report.capacidad("kml").disponible is True
        assert report.capacidad("cronologia").disponible is True


class TestSinFecha:
    def test_cronologia_y_filtros_no_disponibles_kml_si(self):
        df = _bitacora_completa().drop(columns=["fecha"])

        report = detectar_capacidades(df)

        assert report.capacidad("cronologia").disponible is False
        assert report.capacidad("cronologia").faltantes == ("fecha",)
        assert report.capacidad("filtros_temporales").disponible is False
        assert report.capacidad("kml").disponible is True


class TestSinHora:
    def test_cronologia_parcial_antenas_por_horario_no_disponible(self):
        df = _bitacora_completa().drop(columns=["hora"])

        report = detectar_capacidades(df)

        cronologia = report.capacidad("cronologia")
        assert cronologia.disponible is True
        assert cronologia.estado == "parcial"
        assert cronologia.faltantes == ("hora",)

        assert report.capacidad("antenas_por_horario").disponible is False
        assert report.bloqueos_globales == ()


class TestSinContacto:
    def test_contactos_no_disponible_resto_intacto(self):
        df = _bitacora_completa().drop(columns=["contacto"])

        report = detectar_capacidades(df)

        assert report.capacidad("contactos").disponible is False
        assert report.capacidad("antenas").disponible is True
        assert report.capacidad("cronologia").disponible is True
        assert report.capacidad("kml").disponible is True
        assert report.capacidad("identificacion").disponible is True


class TestSinInteraccion:
    def test_tipo_evento_no_disponible(self):
        df = _bitacora_completa().drop(columns=["interaccion"])

        report = detectar_capacidades(df)

        assert report.capacidad("tipo_evento").disponible is False
        assert report.capacidad("tipo_evento").faltantes == ("interaccion",)


class TestDuracion:
    def test_sin_duracion_no_disponible(self):
        df = _bitacora_completa().drop(columns=["duracion"])

        report = detectar_capacidades(df)

        duracion = report.capacidad("duracion")
        assert duracion.disponible is False
        assert duracion.motivo.startswith("duracion_ausente:")

    def test_duracion_ambigua_no_disponible_con_motivo_unidad(self):
        df = _bitacora_completa().copy()
        df["duracion"] = [300, 45]

        report = detectar_capacidades(df)

        duracion = report.capacidad("duracion")
        assert duracion.disponible is False
        assert "unidad_no_confirmada" in duracion.motivo

    def test_duracion_segura_en_milisegundos_disponible(self):
        df = _bitacora_completa().copy()
        df["duracion"] = [5300, 1500]
        estado_ms = DuracionEstado(
            estado="segura",
            unidad="milisegundos",
            columna="duracion",
            columna_original="duracion",
            motivo="seleccion_usuario_milisegundos",
        )

        report = detectar_capacidades(df, duracion_estado=estado_ms)

        duracion = report.capacidad("duracion")
        assert duracion.disponible is True
        assert duracion.estado == "disponible"


class TestAntenaSinCoordenadas:
    def test_antenas_disponible_kml_heatmap_no(self):
        df = _bitacora_completa().drop(columns=["lat", "long"])

        report = detectar_capacidades(df)

        assert report.capacidad("antenas").disponible is True
        assert report.capacidad("kml").disponible is False
        assert report.capacidad("heatmap").disponible is False


class TestCoordenadasSinAntena:
    def test_kml_heatmap_disponibles_antenas_no(self):
        df = _bitacora_completa().drop(columns=["antena"])

        report = detectar_capacidades(df)

        assert report.capacidad("kml").disponible is True
        assert report.capacidad("heatmap").disponible is True
        assert report.capacidad("antenas").disponible is False


class TestSinAzimut:
    def test_kml_disponible_orientacion_no(self):
        df = _bitacora_completa().drop(columns=["azimut"])

        report = detectar_capacidades(df)

        assert report.capacidad("kml").disponible is True
        assert report.capacidad("orientacion").disponible is False
        assert report.capacidad("orientacion").faltantes == ("azimut",)


class TestIdentificacion:
    def test_solo_imei_e_imsi_identificacion_disponible(self):
        df = _bitacora_completa().drop(columns=["tel"])

        report = detectar_capacidades(df)

        assert report.capacidad("identificacion").disponible is True

    def test_sin_tel_ni_imei_pero_con_antenas_y_coords_procesable_identificacion_no(self):
        df = _bitacora_completa().drop(columns=["tel", "imei", "imsi"])

        report = detectar_capacidades(df)

        assert report.procesable is True
        assert report.capacidad("identificacion").disponible is False
        assert report.capacidad("identificacion").faltantes == ("tel", "imei")

    def test_coordenadas_presentes_pero_invalidas_kml_no_disponible(self):
        df = _bitacora_completa().copy()
        df["lat"] = [0.0, 0.0]
        df["long"] = [0.0, 0.0]

        report = detectar_capacidades(df)

        assert report.capacidad("kml").disponible is False
        assert report.capacidad("kml").motivo == "coordenadas_presentes_pero_invalidas"


class TestCombinacionDeAusencias:
    def test_reporte_coherente_con_solo_antena_disponible(self):
        df = pd.DataFrame({"antena": ["ANT-9", "ANT-9"]})

        report = detectar_capacidades(df)

        assert report.procesable is True
        assert report.capacidad("antenas").disponible is True
        assert report.capacidad("identificacion").disponible is False
        assert report.capacidad("cronologia").disponible is False
        assert report.capacidad("filtros_temporales").disponible is False
        assert report.capacidad("kml").disponible is False
        assert report.capacidad("heatmap").disponible is False
        assert report.capacidad("contactos").disponible is False
        assert report.capacidad("tipo_evento").disponible is False
        assert report.capacidad("duracion").disponible is False
        assert report.capacidad("antenas_por_horario").disponible is False
        assert report.capacidad("metadatos").disponible is True
        assert report.capacidad("hashes").disponible is True


class TestPureza:
    def test_detector_no_modifica_el_dataframe(self):
        df = _bitacora_completa()
        copia_original = df.copy(deep=True)

        detectar_capacidades(df)

        assert list(df.columns) == list(copia_original.columns)
        assert df.equals(copia_original)

    def test_resultado_determinista_en_llamadas_repetidas(self):
        df = _bitacora_completa()

        report_1 = detectar_capacidades(df)
        report_2 = detectar_capacidades(df)

        assert report_1 == report_2


class TestHashesSiempreDisponible:
    def test_hashes_disponible_aunque_falten_campos_analiticos(self):
        df = pd.DataFrame({"columna_irrelevante": ["algo", "otro valor"]})

        report = detectar_capacidades(df)

        assert report.procesable is True
        assert report.capacidad("hashes").disponible is True
        assert report.capacidad("hashes").estado == "disponible"
        assert report.capacidad("metadatos").disponible is True
