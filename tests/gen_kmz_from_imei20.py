import os
import sys
import pandas as pd

# Asegurar que el directorio raíz del repo esté en sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from script_principal_bitacoras_refactory import generar_kml, bootstrap_config

# Cargar TSV con separador tab
base = os.path.dirname(__file__)
fn = os.path.join(base, 'data', 'bitacora_imei_20.tsv')
df_raw = pd.read_csv(fn, sep='\t')

# Mapear columnas del TSV a canónicas mínimas
# fecha,hora,lat,long,azimut,antena,direccion,celda,lac,imei,tel,contacto,interaccion,duracion

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

# Inicializar config
basesalida = os.path.join(base, 'out')
os.makedirs(basesalida, exist_ok=True)
out_kml = os.path.join(basesalida, 'imei20.kml')
bootstrap_config()

# Generar KML/KMZ
_generado, descartadas = generar_kml(df, out_kml, flat=False)
print('Generado:', _generado, 'Descartadas:', descartadas)
print('KMZ:', os.path.splitext(_generado)[0] + '.kmz')
