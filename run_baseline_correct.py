#!/usr/bin/env python3
"""
run_baseline_correct.py - TESTING AUTOMATION TOOL
===================================================

✅ ESTADO: HERRAMIENTA DE TESTING - USAR PARA AUTOMATIZACIÓN
🎯 PROPÓSITO: Captura automatizada de baseline dorado para testing
📍 DIFERENCIACIÓN: NO confundir con run.py (entry point principal)

RESPONSABILIDADES:
- Automatización de captura de baseline golden
- Validación de archivos de prueba
- Guía paso a paso para testing manual
- Preparación de datos para tests E2E

ARQUITECTURA HÍBRIDA:
- Este archivo es herramienta de TESTING/QA
- run.py es el LAUNCHER PRINCIPAL para usuarios
- Son complementarios, NO duplicados

Script automatizado para capturar baseline dorado con archivo de prueba específico
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🏆 BASELINE AUTOMATIZADO CON ARCHIVO CORRECTO")
    print("="*55)
    
    # Verificar archivo de datos de prueba
    test_data = "tests/data/bitacora_imei_20.tsv"
    if not os.path.exists(test_data):
        print(f"❌ ERROR: No se encuentra {test_data}")
        return False
    
    print(f"✅ Archivo de prueba: {test_data}")
    
    # Mostrar contenido del archivo para que veas qué columnas tiene
    print("\n📋 COLUMNAS DEL ARCHIVO DE PRUEBA:")
    try:
        with open(test_data, 'r', encoding='utf-8') as f:
            header = f.readline().strip()
            columns = header.split('\t')
            for i, col in enumerate(columns, 1):
                print(f"   {i:2d}. {col}")
        print(f"\n✅ Total: {len(columns)} columnas")
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False
    
    print(f"\n📁 Outputs se guardarán en: tests/golden/outputs/")
    
    print(f"\n📋 LO QUE VAS A HACER:")
    print(f"1. Se ejecutará el script principal")
    print(f"2. CUANDO PIDA ARCHIVO, escribe la ruta EXACTA:")
    print(f"   tests/data/bitacora_imei_20.tsv")
    print(f"3. Hoja: Enter (primera hoja)")
    print(f"4. Mapeo: Las columnas ya están bien nombradas")
    print(f"5. Carpeta destino: tests/golden/outputs")
    print(f"6. Resto: opciones por defecto")
    
    input(f"\n⏸️  Presiona Enter para ejecutar el script...")
    
    return True

if __name__ == "__main__":
    main()
    
    print(f"\n🚀 Ejecutando script principal...")
    print(f"="*50)
    
    # Ejecutar script directamente
    os.system("python script_principal_bitacoras_refactory.py")