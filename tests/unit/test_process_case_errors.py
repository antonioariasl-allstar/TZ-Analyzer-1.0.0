"""FASE 1 WEB — contrato de errores, lock serial y productos parciales de
``tz_web.services.process_case()``.

Complementa ``tests/integration/test_process_case_e2e.py`` (camino feliz con
el fixture real) cubriendo:
- errores de dominio para precondiciones inválidas (archivo/hoja/mapeo/carpeta);
- rechazo controlado de una segunda ejecución simultánea (AnalysisInProgressError);
- que el Lock se libera incluso tras un fallo, permitiendo una ejecución
  posterior;
- degradación a producto parcial cuando un solo componente (KML) falla, sin
  abortar el análisis completo.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest

from tz_web.services import (
    AnalysisInProgressError,
    ArchivoNoProcesableError,
    CaseFileNotFoundError,
    CaseLoadError,
    CaseRequest,
    InvalidMappingError,
    OutputDirectoryError,
    SheetNotFoundError,
    _EXECUTION_LOCK,
    process_case,
)

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "bitacora_test.tsv.xlsx"
)

_MAPEO_MINIMO = {"fecha": ("col", "fecha_inicial")}

_MAPEO_COMPLETO = {
    "fecha": ("col", "fecha_inicial"),
    "hora": ("col", "hora_inicial"),
    "lat": ("col", "latitud_inicial"),
    "long": ("col", "longitud_inicial"),
    "azimut": ("col", "azimut_inicial"),
    "antena": ("col", "ubicacion_inicio"),
    "imei": ("col", "imei_origen"),
    "tel": ("col", "numero_origen"),
    "contacto": ("col", "numero_destino"),
    "interaccion": ("col", "tipo_llamada"),
    "duracion": ("col", "duracion_seg"),
}


def test_archivo_inexistente_lanza_case_file_not_found_error(tmp_path):
    with pytest.raises(CaseFileNotFoundError):
        process_case(
            CaseRequest(
                ruta_archivo=str(tmp_path / "no_existe.xlsx"),
                carpeta_salida=str(tmp_path / "out"),
                mapeo=_MAPEO_MINIMO,
            )
        )


def test_hoja_inexistente_lanza_sheet_not_found_error(tmp_path):
    with pytest.raises(SheetNotFoundError):
        process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                hoja="HojaQueNoExiste",
                carpeta_salida=str(tmp_path / "out"),
                mapeo=_MAPEO_MINIMO,
            )
        )


def test_mapeo_vacio_lanza_invalid_mapping_error(tmp_path):
    with pytest.raises(InvalidMappingError):
        process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida=str(tmp_path / "out"),
                mapeo={},
            )
        )


def test_mapeo_con_columna_inexistente_lanza_invalid_mapping_error(tmp_path):
    with pytest.raises(InvalidMappingError):
        process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida=str(tmp_path / "out"),
                mapeo={"fecha": ("col", "esta_columna_no_existe")},
            )
        )


def test_mapeo_todo_omitido_lanza_invalid_mapping_error(tmp_path):
    with pytest.raises(InvalidMappingError):
        process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida=str(tmp_path / "out"),
                mapeo={"fecha": ("omitido", None), "tel": ("omitido", None)},
            )
        )


def test_carpeta_salida_vacia_lanza_output_directory_error(tmp_path):
    with pytest.raises(OutputDirectoryError):
        process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida="",
                mapeo=_MAPEO_MINIMO,
            )
        )


def test_archivo_sin_datos_procesables_lanza_archivo_no_procesable_error(tmp_path):
    """Reutiliza el error de dominio ya existente en tz_core.exceptions (el
    mismo que lanza run_ingestion_pipeline) — no se define un tipo paralelo
    para la misma condición."""

    blank_path = tmp_path / "vacio.xlsx"
    pd.DataFrame({"col_a": ["", "", ""], "col_b": [None, None, None]}).to_excel(
        blank_path, index=False
    )

    with pytest.raises(ArchivoNoProcesableError):
        process_case(
            CaseRequest(
                ruta_archivo=str(blank_path),
                carpeta_salida=str(tmp_path / "out"),
                mapeo={"fecha": ("fijo", "")},
            )
        )


def test_lock_rechaza_segunda_ejecucion_simultanea(tmp_path):
    """Con el lock ya tomado externamente (simulando una ejecución en curso),
    una segunda llamada debe rechazarse de inmediato, sin bloquear."""

    acquired = _EXECUTION_LOCK.acquire(blocking=False)
    assert acquired, "Precondición del test: el lock debía estar libre al iniciar"

    try:
        with pytest.raises(AnalysisInProgressError):
            process_case(
                CaseRequest(
                    ruta_archivo=DATA_PATH,
                    carpeta_salida=str(tmp_path / "out"),
                    mapeo=_MAPEO_COMPLETO,
                )
            )
    finally:
        _EXECUTION_LOCK.release()


def test_lock_se_libera_tras_una_ejecucion_permitiendo_la_siguiente(tmp_path):
    """Una ejecución exitosa debe liberar el lock (vía finally), permitiendo
    una ejecución normal inmediatamente después."""

    req1 = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=str(tmp_path / "out1"),
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
    )
    resultado1 = process_case(req1)
    assert resultado1.success is True

    # Si el lock no se hubiera liberado, esta segunda llamada lanzaría
    # AnalysisInProgressError en vez de completarse.
    req2 = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=str(tmp_path / "out2"),
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
    )
    resultado2 = process_case(req2)
    assert resultado2.success is True


def test_lock_se_libera_incluso_si_process_case_lanza_una_excepcion(tmp_path):
    """El lock debe liberarse en el finally incluso ante un error de dominio,
    para no dejar el servicio inutilizable tras el primer fallo."""

    with pytest.raises(CaseFileNotFoundError):
        process_case(
            CaseRequest(
                ruta_archivo=str(tmp_path / "no_existe.xlsx"),
                carpeta_salida=str(tmp_path / "out"),
                mapeo=_MAPEO_MINIMO,
            )
        )

    # El lock debe estar libre: una ejecución real ahora debe poder completarse.
    req = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=str(tmp_path / "out_ok"),
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
    )
    resultado = process_case(req)
    assert resultado.success is True


def test_fallo_de_kml_degrada_a_producto_parcial_sin_abortar(tmp_path):
    """Si generar_kml() falla, el análisis debe completarse igual: HTML y
    hashes se generan, kmz_path queda en None y el motivo queda registrado
    en errors — el proceso no se aborta por completo."""

    def _boom(*_a, **_k):
        raise RuntimeError("kml roto (simulado)")

    with patch("tz_web.services.generar_kml", side_effect=_boom):
        resultado = process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida=str(tmp_path / "out"),
                mapeo=dict(_MAPEO_COMPLETO),
                duration_unit_decision="segundos",
            )
        )

    assert resultado.success is True
    assert resultado.kmz_path is None
    assert resultado.html_path and os.path.isfile(resultado.html_path)
    assert any("kml" in e.lower() for e in resultado.errors)


def test_fallo_de_html_degrada_a_producto_parcial_sin_abortar(tmp_path):
    """Simétrico al anterior: si la generación de HTML falla, el KMZ y los
    hashes igual deben producirse; el análisis no debe abortar."""

    def _boom(**_k):
        raise RuntimeError("html roto (simulado)")

    with patch("tz_web.services.generar_informe_html", side_effect=_boom):
        resultado = process_case(
            CaseRequest(
                ruta_archivo=DATA_PATH,
                carpeta_salida=str(tmp_path / "out"),
                mapeo=dict(_MAPEO_COMPLETO),
                duration_unit_decision="segundos",
            )
        )

    assert resultado.success is True
    assert resultado.html_path is None
    assert resultado.kmz_path and os.path.isfile(resultado.kmz_path)
    motivos = resultado.warnings + resultado.errors
    assert any("html" in motivo.lower() for motivo in motivos)
