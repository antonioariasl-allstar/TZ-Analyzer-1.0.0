#!/usr/bin/env python3
"""
Tests unitarios para tz_core.utils
"""

import os
import sys
import tempfile
import hashlib
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Importar módulo a testear
from tz_core.utils import sha256_de_archivo


def test_sha256_de_archivo():
    """Test básico de SHA256 con archivo temporal"""
    print("🧪 Testing sha256_de_archivo...")
    
    # Crear archivo temporal con contenido conocido
    test_content = b"TZ Analyzer test content 123"
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(test_content)
        tmp_file.flush()
        tmp_file_path = tmp_file.name
        
    try:
        # Calcular hash con nuestra función
        result_hash = sha256_de_archivo(tmp_file_path)
        
        # Calcular hash esperado
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        # Verificar
        assert result_hash == expected_hash, f"Hash mismatch: {result_hash} != {expected_hash}"
        assert len(result_hash) == 64, f"Hash length should be 64, got {len(result_hash)}"
        assert all(c in '0123456789abcdef' for c in result_hash), "Hash should be hex"
        
        print(f"✅ PASS: Hash correcto {result_hash[:16]}...")
        return True
        
    finally:
        # Limpiar archivo temporal
        try:
            os.unlink(tmp_file_path)
        except:
            pass  # Ignorar errores de limpieza en Windows


def test_sha256_archivo_vacio():
    """Test con archivo vacío"""
    print("🧪 Testing SHA256 archivo vacío...")
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        # Archivo vacío
        tmp_file.flush()
        tmp_file_path = tmp_file.name
        
    try:
        result_hash = sha256_de_archivo(tmp_file_path)
        # Hash SHA256 de archivo vacío es conocido
        expected_empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        assert result_hash == expected_empty_hash, f"Empty file hash incorrect"
        print(f"✅ PASS: Archivo vacío hash OK")
        return True
        
    finally:
        try:
            os.unlink(tmp_file_path)
        except:
            pass  # Ignorar errores de limpieza en Windows


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.utils")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1
    if test_sha256_de_archivo():
        tests_passed += 1
    
    # Test 2
    if test_sha256_archivo_vacio():
        tests_passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 RESULTADOS: {tests_passed}/{total_tests} tests pasaron")
    
    if tests_passed == total_tests:
        print("🎯 ✅ TODOS LOS UNIT TESTS PASARON!")
        return True
    else:
        print("🚨 ❌ ALGUNOS TESTS FALLARON")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)