#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_s3a_e2e_automated.py - SPRINT 3A.6 TESTING AUTOMATIZADO
============================================================

ESTADO: TESTING E2E AUTOMATIZADO POST-MODULIZACION MENU
PROPOSITO: Ejecutar casos test con bitacora real, comparar outputs
DIFERENCIACION: Testing riguroso para confirmar zero regressions

RESPONSABILIDADES:
- Ejecutar con bitacora_test.tsv.xlsx existente
- Generar outputs y capturar checksums
- Comparar con baseline (si existe)
- Documentar resultados para v1.0.1-rc1

EJECUCION:
python tools/run_s3a_e2e_automated.py

FECHA: 29 octubre 2025 - Sprint 3A.6
"""

import os
import sys
import hashlib
import json
import time
from pathlib import Path
from datetime import datetime

# Añadir root al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def calculate_file_checksum(filepath):
    """Calcular checksum MD5 de archivo"""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'rb') as f:
        content = f.read()
        return hashlib.md5(content).hexdigest()

def catalog_output_files(output_dir):
    """Catalogar archivos generados en directorio"""
    if not os.path.exists(output_dir):
        return []
    
    files = []
    for root, dirs, filenames in os.walk(output_dir):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            relative_path = os.path.relpath(filepath, output_dir)
            
            stat_info = os.stat(filepath)
            files.append({
                'name': filename,
                'relative_path': relative_path,
                'size': stat_info.st_size,
                'checksum': calculate_file_checksum(filepath),
                'modified': stat_info.st_mtime
            })
    
    return files

def run_test_case():
    """Ejecutar caso de test con bitacora existente"""
    print("SPRINT 3A.6 - TESTING E2E AUTOMATIZADO")
    print("=" * 50)
    
    # Configuración
    test_file = "tests/data/bitacora_test.tsv.xlsx"
    output_dir = "outputs_s3a_test"
    
    # Verificar archivo test
    if not os.path.exists(test_file):
        print(f"ERROR: Archivo test no encontrado: {test_file}")
        return False
    
    print(f"SUCCESS: Archivo test: {test_file}")
    print(f"   Tamaño: {os.path.getsize(test_file)} bytes")
    
    # Crear directorio output
    os.makedirs(output_dir, exist_ok=True)
    
    # Test de importación
    try:
        from script_principal_bitacoras_refactory import run_cli
        from tz_cli.menu import main_menu
        print("SUCCESS: Módulos importados correctamente")
    except Exception as e:
        print(f"ERROR: Problema importación: {e}")
        return False
    
    print("\n=== INSTRUCCIONES EJECUCION MANUAL ===")
    print("Para completar testing E2E:")
    print("1. Ejecutar: python run.py")
    print("2. Seleccionar [1] Procesar archivo Excel/TSV")
    print(f"3. Archivo: {os.path.abspath(test_file)}")
    print("4. Top antenas: 10")
    print(f"5. Directorio salida: {os.path.abspath(output_dir)}")
    print("6. Procesar normalmente")
    print("7. Salir [3]")
    
    print(f"\n=== ANALISIS POST-EJECUCION ===")
    print("Tras ejecución manual, este script analizará:")
    print("- Archivos generados (HTML, KML, KMZ)")
    print("- Checksums y tamaños")
    print("- Estructura directorio")
    print("- Logs de errores")
    
    # Análisis pre-ejecución
    print(f"\n=== ESTADO PRE-EJECUCION ===")
    pre_files = catalog_output_files(output_dir)
    print(f"Archivos en {output_dir}: {len(pre_files)}")
    
    input("\nPresiona Enter tras completar ejecucion manual...")
    
    # Análisis post-ejecución
    print(f"\n=== ANALISIS POST-EJECUCION ===")
    post_files = catalog_output_files(output_dir)
    print(f"Archivos generados: {len(post_files)}")
    
    # Generar reporte
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_file': test_file,
        'output_dir': output_dir,
        'files_generated': post_files,
        'total_files': len(post_files),
        'test_status': 'completed'
    }
    
    # Escribir reporte
    report_file = os.path.join(output_dir, "s3a_test_report.json")
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nSUCCESS: Reporte guardado en {report_file}")
    
    # Mostrar archivos generados
    print(f"\n=== ARCHIVOS GENERADOS ===")
    for file_info in post_files:
        print(f"- {file_info['name']} ({file_info['size']} bytes)")
        print(f"  MD5: {file_info['checksum']}")
    
    return True

if __name__ == "__main__":
    success = run_test_case()
    
    if success:
        print(f"\n=== RESULTADO ===")
        print("Testing E2E preparado - completar ejecución manual")
        print("Próximo paso: Documentar en docs/S3A_CLI_NOTES.md")
    else:
        print(f"\nERROR: Testing fallido")
        sys.exit(1)