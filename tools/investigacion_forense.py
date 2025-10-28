#!/usr/bin/env python3
"""
Script de investigación forense - Detectar negligencia en normalización
"""

import pandas as pd
import sys
import os

print("🔍 INVESTIGACIÓN FORENSE - DETECTAR NEGLIGENCIA")
print("="*60)

# Agregar directorio actual al path para imports
sys.path.insert(0, os.getcwd())

def test_paso_1_pandas_directo():
    """Paso 1: Cargar archivo directamente con pandas"""
    print("\n📂 PASO 1: Pandas directo")
    try:
        df = pd.read_excel('tests/data/bitacora_test.tsv.xlsx')
        print(f"   ✅ Cargado: {len(df)} registros")
        print(f"   📋 Columnas originales: {list(df.columns)[:5]}...")
        
        # Verificar datos críticos
        lat_cols = [col for col in df.columns if 'lat' in col.lower()]
        lon_cols = [col for col in df.columns if 'lon' in col.lower()]
        print(f"   🎯 Columnas LAT encontradas: {lat_cols}")
        print(f"   🎯 Columnas LON encontradas: {lon_cols}")
        
        if lat_cols and lon_cols:
            lat_col, lon_col = lat_cols[0], lon_cols[0]
            coords_validas = ((df[lat_col].notna()) & (df[lon_col].notna())).sum()
            print(f"   ✅ Coordenadas válidas: {coords_validas}/{len(df)}")
        return True
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_paso_2_config_manager():
    """Paso 2: Probar config manager y rename_map"""
    print("\n⚙️ PASO 2: Config manager")
    try:
        from tz_core.config_manager import cargar_config, cfg_build_rename_map
        config = cargar_config()
        print(f"   ✅ CONFIG: {len(config)} secciones")
        
        rename_map = cfg_build_rename_map(config)
        print(f"   ✅ Rename map: {len(rename_map)} entradas")
        
        # Buscar entradas relevantes
        relevant = {k: v for k, v in rename_map.items() 
                   if any(word in k.lower() for word in ['lat', 'lon', 'antena', 'celda'])}
        print(f"   🎯 Mapeos relevantes: {relevant}")
        return True, rename_map
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False, {}

def test_paso_3_normalizacion_manual():
    """Paso 3: Aplicar normalización manual"""
    print("\n🔄 PASO 3: Normalización manual")
    try:
        # Cargar datos
        df_original = pd.read_excel('tests/data/bitacora_test.tsv.xlsx')
        
        # Obtener rename_map
        from tz_core.config_manager import cargar_config, cfg_build_rename_map
        config = cargar_config()
        rename_map = cfg_build_rename_map(config)
        
        # Aplicar normalización
        df_normalized = df_original.rename(columns=rename_map)
        print(f"   ✅ Normalización aplicada")
        print(f"   📋 Columnas después: {list(df_normalized.columns)[:5]}...")
        
        # Verificar columnas críticas
        critical = ['lat', 'long', 'antena', 'celda']
        found = [col for col in critical if col in df_normalized.columns]
        missing = [col for col in critical if col not in df_normalized.columns]
        print(f"   ✅ Encontradas: {found}")
        print(f"   ❌ Faltantes: {missing}")
        
        return len(found) > 0, df_normalized
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False, None

def test_paso_4_data_loader():
    """Paso 4: Probar data loader modular"""
    print("\n📦 PASO 4: Data loader modular")
    try:
        from tz_core.data_loader import cargar_excel_con_normalizacion
        df, hoja = cargar_excel_con_normalizacion('tests/data/bitacora_test.tsv.xlsx')
        print(f"   ✅ Data loader: {len(df)} registros, hoja: {hoja}")
        print(f"   📋 Columnas: {list(df.columns)[:5]}...")
        
        # Verificar normalización
        critical = ['lat', 'long', 'antena', 'celda']
        found = [col for col in critical if col in df.columns]
        print(f"   🎯 Resultado: {found}")
        
        return len(found) > 0, df
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False, None

if __name__ == "__main__":
    print(f"🎯 Archivo objetivo: tests/data/bitacora_test.tsv.xlsx")
    
    # Ejecutar tests paso a paso
    paso1_ok = test_paso_1_pandas_directo()
    paso2_ok, rename_map = test_paso_2_config_manager() 
    paso3_ok, df_manual = test_paso_3_normalizacion_manual()
    paso4_ok, df_loader = test_paso_4_data_loader()
    
    print("\n" + "="*60)
    print("📊 RESUMEN DE INVESTIGACIÓN FORENSE:")
    print(f"   Paso 1 (Pandas directo): {'✅ OK' if paso1_ok else '❌ FAIL'}")
    print(f"   Paso 2 (Config manager): {'✅ OK' if paso2_ok else '❌ FAIL'}")
    print(f"   Paso 3 (Normalización manual): {'✅ OK' if paso3_ok else '❌ FAIL'}")
    print(f"   Paso 4 (Data loader modular): {'✅ OK' if paso4_ok else '❌ FAIL'}")
    
    if not paso4_ok and paso3_ok:
        print("\n🚨 NEGLIGENCIA DETECTADA: Data loader modular NO aplica normalización")
        print("   ➡️ El problema está en tz_core.data_loader")
    elif not paso3_ok and paso2_ok:
        print("\n🚨 NEGLIGENCIA DETECTADA: Rename map no funciona correctamente")
        print("   ➡️ El problema está en el mapeo de columnas")
    elif not paso2_ok:
        print("\n🚨 NEGLIGENCIA DETECTADA: Config manager defectuoso")
        print("   ➡️ El problema está en la configuración")
    else:
        print("\n✅ Sistema funcionando - Verificar flujo completo")