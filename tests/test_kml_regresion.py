import os
import sys
import zipfile
import tempfile
import pandas as pd
from datetime import datetime

# Agregar path padre para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar la función de generación real desde el script principal
# La función generar_kml está definida en script_principal_bitacoras_refactory.py
from script_principal_bitacoras_refactory import generar_kml, bootstrap_config


def test_kmz_estructura_basica(tmp_path=None):
    # 1) Preparar DF sintético con 3 puntos válidos y azimut
    df = pd.DataFrame([
        {"fecha": "23/12/2021", "hora": "10:43:09", "lat": 13.730, "long": -89.190, "antena": "Distrito Italia", "azimut": 45, "tel":"70871087", "imei":"352005090177850"},
        {"fecha": "23/12/2021", "hora": "10:59:53", "lat": 13.740, "long": -89.220, "antena": "Apopa II", "azimut": 120},
        {"fecha": "24/12/2021", "hora": "08:15:00", "lat": 13.750, "long": -89.200, "antena": "El Zope", "azimut": 200},
    ])

    # 2) Ruta de salida temporal
    if tmp_path is None:
        tmpdir = tempfile.TemporaryDirectory()
        base_dir = tmpdir.name
    else:
        base_dir = str(tmp_path)
    out_kml = os.path.join(base_dir, "test_sintetico.kml")

    # 3) Inicializar config (usa defaults si no hay archivo)
    bootstrap_config()

    # 4) Generar KML/KMZ
    generar_kml(df, out_kml)

    # 5) Abrir el KMZ y validar estructura mínima
    kmz_path = os.path.splitext(out_kml)[0] + ".kmz"
    assert os.path.exists(kmz_path), "No se generó el KMZ"

    with zipfile.ZipFile(kmz_path, 'r') as z:
        # Buscar el archivo KML dentro
        kml_names = [n for n in z.namelist() if n.lower().endswith('.kml')]
        assert kml_names, "El KMZ no contiene un archivo .kml"
        kml_data = z.read(kml_names[0]).decode('utf-8', errors='ignore')

    # Validaciones simples de estructura
    # - Carpeta raíz con nombre base (permitir atributos en la etiqueta)
    assert "<Folder" in kml_data, "No hay carpetas en KML"
    assert "todas_las_antenas" in kml_data, "Falta carpeta 'todas_las_antenas'"

    # - Al menos un LineString (azimut) y un Polygon (cono)
    assert ("<LineString" in kml_data) or ("Azimut " in kml_data), "Falta LineString (azimut)"
    assert ("<Polygon" in kml_data) or ("Cono Azimut" in kml_data), "Falta Polygon (cono)"

    # - Al menos 3 placemarks (nuestros 3 puntos)
    assert kml_data.count("<Placemark") >= 3, "Se esperaban al menos 3 placemarks"

    # - Que haya fechas distintas (carpetas por día)
    assert kml_data.count("<Folder") >= 3, "Se esperaban al menos 3 folders (raíz, todas_las_antenas y una fecha)"

    return True


if __name__ == "__main__":
    ok = test_kmz_estructura_basica()
    print("KMZ regresión básica:", "OK" if ok else "FALLÓ")
