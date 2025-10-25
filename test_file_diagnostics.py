#!/usr/bin/env python3
"""
Script de diagnóstico para ver dónde falla el proceso
"""

import sys
import pandas as pd
import traceback

def test_file_loading():
    """Test específico de carga del archivo"""
    try:
        print("🔍 DIAGNÓSTICO DE ARCHIVO TSV")
        print("="*40)
        
        file_path = "tests/data/bitacora_imei_20.tsv"
        
        # Test 1: Lectura básica
        print("1. Leyendo archivo...")
        df = pd.read_csv(file_path, sep='\t')
        print(f"   ✅ {len(df)} filas, {len(df.columns)} columnas")
        
        # Test 2: Verificar columnas
        print("\n2. Columnas encontradas:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        
        # Test 3: Verificar datos
        print(f"\n3. Primeras filas:")
        print(df.head(2).to_string())
        
        # Test 4: Verificar tipos de datos problemáticos
        print(f"\n4. Verificación de fechas:")
        print(f"   FECHA_INICIAL: {df['FECHA_INICIAL'].dtype}")
        print(f"   Ejemplo: {df['FECHA_INICIAL'].iloc[0]}")
        
        # Test 5: Verificar coordenadas
        print(f"\n5. Verificación de coordenadas:")
        print(f"   LATITUD_INICIAL: {df['LATITUD_INICIAL'].dtype}")
        print(f"   LONGITUD_INICIAL: {df['LONGITUD_INICIAL'].dtype}")
        print(f"   Ejemplo LAT: {df['LATITUD_INICIAL'].iloc[0]}")
        print(f"   Ejemplo LON: {df['LONGITUD_INICIAL'].iloc[0]}")
        
        print(f"\n✅ ARCHIVO PARECE ESTAR BIEN")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_file_loading()