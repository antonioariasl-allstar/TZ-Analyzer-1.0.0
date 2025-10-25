#!/usr/bin/env python3
"""
Test de regresión end-to-end simple para TZ Analyzer
Verifica que el baseline dorado esté funcionando
"""

import os
import sys
from pathlib import Path

def test_golden_baseline_exists():
    """Verificar que el golden baseline existe"""
    print("🧪 TEST: Verificando Golden Baseline...")
    
    golden_dir = Path("tests/golden")
    kml_golden = golden_dir / "kml_normalized.txt"
    html_golden = golden_dir / "html_normalized.txt"
    
    if not kml_golden.exists():
        print(f"❌ FAIL: No existe {kml_golden}")
        return False
    
    if not html_golden.exists():
        print(f"❌ FAIL: No existe {html_golden}")
        return False
    
    # Verificar contenido no vacío
    kml_content = kml_golden.read_text(encoding='utf-8').strip()
    html_content = html_golden.read_text(encoding='utf-8').strip()
    
    if not kml_content:
        print(f"❌ FAIL: {kml_golden} está vacío")
        return False
        
    if not html_content:
        print(f"❌ FAIL: {html_golden} está vacío")
        return False
    
    print(f"✅ PASS: Golden KML ({len(kml_content)} chars)")
    print(f"✅ PASS: Golden HTML ({len(html_content)} chars)")
    return True

def test_output_files_exist():
    """Verificar que se generaron archivos de output"""
    print("\n🧪 TEST: Verificando archivos de output...")
    
    output_dir = Path("tests/golden/outputs")
    if not output_dir.exists():
        print(f"❌ FAIL: No existe directorio {output_dir}")
        return False
    
    # Buscar archivos HTML y KMZ
    html_files = list(output_dir.glob("**/*.html"))
    kmz_files = list(output_dir.glob("**/*.kmz"))
    
    if not html_files:
        print(f"❌ FAIL: No se encontraron archivos HTML en {output_dir}")
        return False
        
    if not kmz_files:
        print(f"❌ FAIL: No se encontraron archivos KMZ en {output_dir}")
        return False
    
    print(f"✅ PASS: Encontrados {len(html_files)} HTML y {len(kmz_files)} KMZ")
    print(f"   HTML: {html_files[0].name}")
    print(f"   KMZ: {kmz_files[0].name}")
    return True

def main():
    """Ejecutar tests básicos"""
    print("🏆 GOLDEN BASELINE VALIDATION")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Golden baseline existe
    if test_golden_baseline_exists():
        tests_passed += 1
    
    # Test 2: Output files existen
    if test_output_files_exist():
        tests_passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 RESULTADOS: {tests_passed}/{total_tests} tests pasaron")
    
    if tests_passed == total_tests:
        print("🎯 ✅ TODOS LOS TESTS PASARON - Baseline dorado OK!")
        return True
    else:
        print("🚨 ❌ ALGUNOS TESTS FALLARON - Revisar baseline")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)