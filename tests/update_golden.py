"""
Genera/actualiza los archivos golden normalizados para la prueba E2E.
Uso:
  python -m tests.update_golden
"""
from __future__ import annotations
import os
import tempfile
import pandas as pd

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
    fn = os.path.join(DATA, 'bitacora_test.tsv.xlsx')
    df_raw = pd.read_excel(fn)
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


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    df = _load_df_imei20()
    bootstrap_config()

    out_dir = tempfile.mkdtemp(prefix='tz_e2e_')
    kmz_base = os.path.join(out_dir, 'e2e.kml')

    generar_kml(df, kmz_base, flat=False)
    html_path = generar_informe_html(
        df=df,
        archivo_kml=kmz_base,
        carpeta_salida=out_dir,
        nombre_salida='e2e_informe',
        hoja=None,
        nombre_bitacora='E2E_REGRESION_TEST'
    )

    kmz_path = os.path.splitext(kmz_base)[0] + '.kmz'
    kml_norm = normalize_kml_from_kmz(kmz_path)
    html_norm = normalize_html(html_path)

    with open(GOLDEN_KML_NORM, 'w', encoding='utf-8') as fk:
        fk.write(kml_norm)
    with open(GOLDEN_HTML_NORM, 'w', encoding='utf-8') as fh:
        fh.write(html_norm)

    print('[update_golden] Golden actualizado:')
    print(' -', GOLDEN_KML_NORM)
    print(' -', GOLDEN_HTML_NORM)


if __name__ == '__main__':
    main()
