#!/usr/bin/env python3
"""
Script para capturar baseline dorado de forma guiada
Ejecuta el script principal con datos de prueba y captura configuración
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🏆 CAPTURA DE BASELINE DORADO")
    print("="*50)
    
    # Verificar archivo de datos de prueba
    test_data = "tests/data/bitacora_imei_20.tsv"
    if not os.path.exists(test_data):
        print(f"❌ ERROR: No se encuentra {test_data}")
        return False
    
    print(f"✅ Datos de prueba encontrados: {test_data}")
    print(f"✅ Directorio de outputs: tests/golden/outputs/")
    
    print("\n📋 INSTRUCCIONES PARA TI:")
    print("1. Se va a ejecutar el script principal")
    print("2. Cuando pida archivo, selecciona: tests/data/bitacora_imei_20.tsv")
    print("3. Usa opciones por defecto en todo lo posible")
    print("4. En mapeo de columnas, mapea según coincidencias obvias")
    print("5. Para carpeta destino, usa: tests/golden/outputs/")
    print("6. Yo capturaré la configuración resultante")
    
    input("\n⏸️  Presiona Enter cuando estés listo para empezar...")
    
    print("\n🚀 Ejecutando script principal...")
    print("-" * 50)
    
    # Ejecutar script principal
    try:
        subprocess.run([sys.executable, "script_principal_bitacoras_refactory.py"], 
                      check=False, cwd=".")
    except KeyboardInterrupt:
        print("\n⚠️  Ejecución interrumpida por usuario")
    except Exception as e:
        print(f"❌ Error ejecutando script: {e}")
        return False
    
    print("\n✅ Ejecución completada")
    
    # Verificar outputs generados
    output_dir = Path("tests/golden/outputs")
    if output_dir.exists():
        files = list(output_dir.glob("*"))
        if files:
            print(f"📁 Archivos generados en {output_dir}:")
            for f in files:
                print(f"   - {f.name}")
        else:
            print("⚠️  No se encontraron archivos en el directorio de outputs")
    
    print("\n🎯 Siguiente paso: Normalizar outputs para golden baseline")
    print("   Ejecuta: python -m tests.update_golden")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)