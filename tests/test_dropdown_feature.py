"""
Script de prueba para verificar el dropdown de interacciones diarias.
Genera un HTML con la bitácora IMEI_20 de prueba.
"""
import sys
import os
sys.path.insert(0, r'c:\python_proyectos\TZ_Analysis_1.0.0_REPO')

import pandas as pd
from pathlib import Path

# Importar módulo principal
from script_principal_bitacoras_refactory import generar_informe_html

# CONFIG básico mínimo
CONFIG = {
    "salida": {
        "separar_kml_kmz": False,
        "solo_kmz": False
    },
    "columnas": {
        "fecha": "FECHA_INICIAL",
        "hora": "HORA_INICIAL",
        "contacto": "NUMERO_DESTINO",
        "duracion": "DURACION_SEG",
        "antena": "COD_CELDA_INICIAL",
        "lat": "LATITUD_INICIAL",
        "lon": "LONGITUD_INICIAL",
        "azimut": "AZIMUT_INICIAL"
    },
    "html": {
        "interacciones_ultimos_dias": 3,
        "top_antenas_n": 5,
        "enmascarar_contactos": False
    },
    "geografia": {
        "sv_bbox": {
            "lat_min": 12.9,
            "lat_max": 14.5,
            "lon_min": -90.3,
            "lon_max": -87.6
        }
    },
    "kml": {
        "incluir_por_rango_horario": True
    }
}

# Inyectar CONFIG en el módulo
import script_principal_bitacoras_refactory as script_mod
script_mod.CONFIG = CONFIG

bitacora_path = Path(r'c:\python_proyectos\TZ_Analysis_1.0.0_REPO\tests\data\bitacora_imei_20.tsv')
output_dir = Path(r'c:\python_proyectos\TZ_Analysis_1.0.0_REPO\tests')
output_dir.mkdir(exist_ok=True)

print(f"[TEST] Leyendo bitácora: {bitacora_path}")
df = pd.read_csv(bitacora_path, sep='\t')

# Renombrar columnas para que coincidan con los nombres esperados por la función
# (la función busca literalmente 'fecha', 'hora', etc. en minúsculas)
df = df.rename(columns={
    'FECHA_INICIAL': 'fecha',
    'HORA_INICIAL': 'hora',
    'NUMERO_DESTINO': 'contacto',
    'DURACION_SEG': 'duracion',
    'COD_CELDA_INICIAL': 'antena',
    'LATITUD_INICIAL': 'lat',
    'LONGITUD_INICIAL': 'long',
    'AZIMUT_INICIAL': 'azimut'
})

print(f"[TEST] Registros cargados: {len(df)}")
print(f"[TEST] Fechas únicas: {df['fecha'].unique().tolist()}")

# === PASO 1: Calcular sección de interacciones ANTES (como en flujo principal línea 7774) ===
print(f"\n[TEST] PASO 1: Calculando sección de interacciones...")
try:
    dias_cfg = CONFIG.get("html", {}).get("interacciones_ultimos_dias", 3)
    cols_cfg = CONFIG.get("columnas", {})

    # Debug: Ver estructura del DataFrame
    print(f"[DEBUG] Columnas disponibles: {df.columns.tolist()}")
    print(f"[DEBUG] Primeras filas de fecha:")
    print(df['fecha'].head())
    print(f"[DEBUG] Tipo de datos fecha: {df['fecha'].dtype}")
    print(f"[DEBUG] Shape del DataFrame: {df.shape}")
    
    # Calcular la sección y guardarla en la variable global del módulo
    seccion_html = script_mod._construir_seccion_interacciones(df, dias=dias_cfg, columnas_config=cols_cfg)
    script_mod.HTML_SECCION_INTERACCIONES = seccion_html
    
    print(f"[TEST] ✅ Sección de interacciones generada: {len(seccion_html)} caracteres")
    
    # Verificar que la sección tiene contenido del dropdown
    if 'id="dia-selector"' in seccion_html:
        print(f"[TEST] ✅ Dropdown encontrado en la sección")
    else:
        print(f"[TEST] ⚠️ Dropdown NO encontrado en la sección")
        
except Exception as e:
    print(f"[TEST] ❌ Error al calcular sección: {e}")
    import traceback
    traceback.print_exc()
    script_mod.HTML_SECCION_INTERACCIONES = ""

# === PASO 2: Generar informe HTML (que inyectará la sección global) ===
print(f"\n[TEST] PASO 2: Generando informe HTML completo...")
print(f"[TEST] Generando informe HTML...")
try:
    html_path = generar_informe_html(
        df=df,
        archivo_kml='test_dropdown.kml',
        carpeta_salida=str(output_dir),
        nombre_salida='test_dropdown_output',
        hoja=None,
        nombre_bitacora='IMEI_20_DROPDOWN_TEST'
    )
    print(f"[TEST] ✅ HTML generado exitosamente: {html_path}")
    
    # Verificar contenido HTML
    if html_path and os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Verificaciones
        checks = {
            'Dropdown selector': 'id="dia-selector"' in html_content,
            'Banner de rango': '📅 Rango:' in html_content,
            'Contenedor día 1': 'id="content-2020-01-01"' in html_content,
            'Contenedor día 2': 'id="content-2020-01-02"' in html_content,
            'JavaScript navegación': 'function showDay(dateStr)' in html_content,
            'Class day-content': 'class="day-content"' in html_content
        }
        
        print("\n[TEST] Verificaciones del HTML:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}: {result}")
        
        # Contar opciones del dropdown
        import re
        options = re.findall(r'<option value="(\d{4}-\d{2}-\d{2})">', html_content)
        print(f"\n[TEST] Opciones en dropdown: {len(options)} días")
        for opt in options:
            print(f"  - {opt}")
        
        print(f"\n[TEST] 🎉 Prueba completada. Abre el archivo para ver el resultado:")
        print(f"  {html_path}")
        
except Exception as e:
    print(f"[TEST] ❌ Error: {e}")
    import traceback
    traceback.print_exc()
