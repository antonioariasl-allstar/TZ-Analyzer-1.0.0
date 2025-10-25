"""
Prueba E2E con baseline dorado. Ejecuta el pipeline mínimo para generar
KMZ + HTML con el dataset de ejemplo y compara contra golden normalizado.

Modo de uso inicial para crear golden:
  python -m tests.update_golden
Luego:
  pytest -q tests/test_e2e_regresion.py
"""
from __future__ import annotations
import os
import tempfile
import pandas as pd
import pytest

from script_principal_bitacoras_refactory import (
    generar_kml,
    generar_informe_html,
    bootstrap_config,
)
from tests.normalize_outputs import normalize_kml_from_kmz, normalize_html

ROOT = os.path.dirname(os.path.dirname(__file__))
TESTS = os.path.join(ROOT, 'tests')
DATA = os.path.join(TESTS, 'data')
GOLDEN_DIR = os.path.join(TESTS, 'golden')
GOLDEN_KML_NORM = os.path.join(GOLDEN_DIR, 'kml_normalized.txt')
GOLDEN_HTML_NORM = os.path.join(GOLDEN_DIR, 'html_normalized.txt')


def _load_df_imei20() -> pd.DataFrame:
    fn = os.path.join(DATA, 'bitacora_imei_20.tsv')
    df_raw = pd.read_csv(fn, sep='\t')
    df = pd.DataFrame({
        'fecha': df_raw['FECHA_INICIAL'].astype(str),
        'hora': df_raw['HORA_INICIAL'].astype(str).str[:8],
        'lat': df_raw['LATITUD_INICIAL'],
        'long': df_raw['LONGITUD_INICIAL'],
        'azimut': df_raw['AZIMUT_INICIAL'],
        'antena': df_raw['UBICACION_INICIO'],
        'direccion': df_raw['UBICACION_INICIO'],
        'celda': df_raw['COD_CELDA_INICIAL'],
        'lac': '',
        'imei': df_raw['IMEI_ORIGEN'].astype(str),
        'tel': df_raw['NUMERO_ORIGEN'].astype(str),
        'contacto': df_raw['NUMERO_DESTINO'].astype(str),
        'interaccion': df_raw['TIPO_LLAMADA'],
        'duracion': df_raw['DURACION_SEG'],
    })
    return df


@pytest.mark.skipif(not os.path.exists(GOLDEN_DIR), reason="Golden no inicializado. Ejecuta: python -m tests.update_golden")
def test_e2e_outputs_golden_match(tmp_path):
    # Arrange
    df = _load_df_imei20()
    bootstrap_config()

    out_dir = tmp_path if tmp_path else tempfile.mkdtemp()
    out_dir = str(out_dir)
    kmz_base = os.path.join(out_dir, 'e2e.kml')

    # Act
    generar_kml(df, kmz_base, flat=False)
    html_path = generar_informe_html(
        df=df,
        archivo_kml=kmz_base,
        carpeta_salida=out_dir,
        nombre_salida='e2e_informe',
        hoja=None,
        nombre_bitacora='E2E_REGRESION_TEST'
    )

    # Normalize actual outputs
    kmz_path = os.path.splitext(kmz_base)[0] + '.kmz'
    actual_kml = normalize_kml_from_kmz(kmz_path)
    actual_html = normalize_html(html_path)

    # Load golden
    assert os.path.exists(GOLDEN_KML_NORM), "Falta golden KML normalizado. Ejecuta: python -m tests.update_golden"
    assert os.path.exists(GOLDEN_HTML_NORM), "Falta golden HTML normalizado. Ejecuta: python -m tests.update_golden"
    with open(GOLDEN_KML_NORM, 'r', encoding='utf-8') as fk:
        golden_kml = fk.read().strip()
    with open(GOLDEN_HTML_NORM, 'r', encoding='utf-8') as fh:
        golden_html = fh.read().strip()

    # Assert
    assert actual_kml == golden_kml, "El KML actual no coincide con el golden normalizado"
    assert actual_html == golden_html, "El HTML actual no coincide con el golden normalizado"
