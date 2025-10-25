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
from tz_core.utils import sha256_de_archivo, escribe_hashes_txt


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


def test_escribe_hashes_txt():
    """Test de escritura de archivo de hashes"""
    print("🧪 Testing escribe_hashes_txt...")
    
    # Crear archivos temporales de prueba
    test_files = []
    test_pares = []
    
    try:
        # Crear dos archivos con contenido conocido
        for i, content in enumerate([b"contenido archivo 1", b"contenido archivo 2"]):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_test{i}.txt") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                test_files.append(tmp_file.name)
                test_pares.append((tmp_file.name, f"test_file_{i}.txt"))
        
        # Crear archivo de hashes
        with tempfile.NamedTemporaryFile(delete=False, suffix="_hashes.txt") as hash_file:
            hash_file_path = hash_file.name
        
        # Ejecutar función
        escribe_hashes_txt(hash_file_path, test_pares)
        
        # Verificar contenido del archivo de hashes
        with open(hash_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificaciones
        assert "SHA256" in content, "Debe contener prefijo SHA256"
        assert "test_file_0.txt" in content, "Debe contener nombre relativo del primer archivo"
        assert "test_file_1.txt" in content, "Debe contener nombre relativo del segundo archivo"
        
        lines = content.strip().split('\n')
        assert len(lines) == 2, f"Debe tener 2 líneas, encontrado {len(lines)}"
        
        # Verificar formato de líneas
        for line in lines:
            parts = line.split()
            assert len(parts) == 3, f"Cada línea debe tener 3 partes: SHA256 <hash> <file>"
            assert parts[0] == "SHA256", f"Primera parte debe ser 'SHA256'"
            assert len(parts[1]) == 64, f"Hash debe tener 64 caracteres"
            assert parts[2].startswith("test_file_"), f"Archivo debe empezar con 'test_file_'"
        
        print(f"✅ PASS: Archivo de hashes generado correctamente")
        return True
        
    finally:
        # Limpiar archivos temporales
        for tmp_file in test_files:
            try:
                os.unlink(tmp_file)
            except:
                pass
        try:
            os.unlink(hash_file_path)
        except:
            pass


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.utils")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1
    if test_sha256_de_archivo():
        tests_passed += 1
    
    # Test 2
    if test_sha256_archivo_vacio():
        tests_passed += 1
    
    # Test 3 - NUEVO
    if test_escribe_hashes_txt():
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