"""
Prueba E2E con baseline dorado. Ejecuta el pipeline mínimo para generar
KMZ + HTML con el dataset de ejemplo y compara contra golden normalizado.

Modo de uso inicial para crear golden:
  python -m tests.update_golden
Luego:
  python tests/test_e2e_regresion.py
"""
from __future__ import annotations
import os
import tempfile
import zipfile
import pandas as pd
try:
    import pytest  # Opcional para decoradores avanzados
except ImportError:
    pytest = None

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


if pytest:
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
else:
    def test_e2e_outputs_golden_match():
        """Versión simplificada sin pytest para compatibilidad"""
        print("TEST E2E: Requiere pytest para ejecución completa")


def test_kmz_estructura_basica_sintetica():
    """
    Test de estructura KMZ usando datos sintéticos para validar elementos específicos.
    Consolidado desde test_kml_regresion.py para mantener validaciones de estructura.
    """
    # Preparar DF sintético con 3 puntos válidos y azimut
    df = pd.DataFrame([
        {"fecha": "23/12/2021", "hora": "10:43:09", "lat": 13.730, "long": -89.190, 
         "antena": "Distrito Italia", "azimut": 45, "tel": "70871087", "imei": "352005090177850"},
        {"fecha": "23/12/2021", "hora": "10:59:53", "lat": 13.740, "long": -89.220, 
         "antena": "Apopa II", "azimut": 120},
        {"fecha": "24/12/2021", "hora": "08:15:00", "lat": 13.750, "long": -89.200, 
         "antena": "El Zope", "azimut": 200},
    ])

    # Ruta de salida temporal
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_kml = os.path.join(tmp_dir, "test_sintetico.kml")
        
        # Inicializar config y generar KML/KMZ
        bootstrap_config()
        generar_kml(df, out_kml, flat=False)
        
        # Validar que se generó el KMZ
        kmz_path = os.path.splitext(out_kml)[0] + ".kmz"
        assert os.path.exists(kmz_path), "No se generó el KMZ"

        # Abrir KMZ y validar estructura interna
        with zipfile.ZipFile(kmz_path, 'r') as z:
            kml_names = [n for n in z.namelist() if n.lower().endswith('.kml')]
            assert kml_names, "El KMZ no contiene un archivo .kml"
            kml_data = z.read(kml_names[0]).decode('utf-8', errors='ignore')

        # Validaciones específicas de estructura KML
        assert "<Folder" in kml_data, "No hay carpetas en KML"
        assert "todas_las_antenas" in kml_data, "Falta carpeta 'todas_las_antenas'"
        
        # Validar elementos geométricos (azimut y conos)
        assert ("<LineString" in kml_data) or ("Azimut " in kml_data), "Falta LineString (azimut)"
        assert ("<Polygon" in kml_data) or ("Cono Azimut" in kml_data), "Falta Polygon (cono)"
        
        # Validar cantidad esperada de elementos
        assert kml_data.count("<Placemark") >= 3, "Se esperaban al menos 3 placemarks"
        assert kml_data.count("<Folder") >= 3, "Se esperaban al menos 3 folders (raíz, todas_las_antenas y una fecha)"
