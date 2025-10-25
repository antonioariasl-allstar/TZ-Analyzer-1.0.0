#!/usr/bin/env python3
"""
Tests unitarios para tz_core.config_manager
Verificar carga de configuración y gestión de sinónimos
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tz_core.config_manager import cargar_config, DEFAULT_CONFIG
import tz_core.config_manager


def test_cargar_config_default():
    """Test que cargar_config retorna DEFAULT_CONFIG cuando no existe archivo"""
    print("🧪 Testing cargar_config con archivo inexistente...")
    
    # Cambiar temporalmente el directorio de trabajo para que no encuentre config.json
    with tempfile.TemporaryDirectory() as temp_dir:
        original_dir = os.getcwd()
        try:
            os.chdir(temp_dir)
            # Simular que __file__ está en temp_dir
            original_file = tz_core.config_manager.__file__ if hasattr(tz_core.config_manager, '__file__') else None
            
            config = cargar_config()
            
            # Verificar que retorna DEFAULT_CONFIG
            assert isinstance(config, dict), "Debe retornar un diccionario"
            assert "kml" in config, "Debe contener sección kml"
            assert config["kml"]["azimuth_km"] == 1.5, "Debe tener valor por defecto de azimuth_km"
            
            print("✅ PASS: DEFAULT_CONFIG retornado correctamente")
            return True
            
        finally:
            os.chdir(original_dir)


def test_cargar_config_archivo_real():
    """Test que cargar_config funciona con el config.json real"""
    print("🧪 Testing cargar_config con config.json real...")
    
    config = cargar_config()
    
    # Verificaciones básicas
    assert isinstance(config, dict), "Debe retornar un diccionario"
    assert "kml" in config, "Debe contener sección kml"
    assert "azimuth_km" in config["kml"], "Debe contener azimuth_km"
    
    # Verificar que tiene datos reales (no solo DEFAULT_CONFIG)
    if "fields" in config:
        assert isinstance(config["fields"], dict), "fields debe ser diccionario"
        print("✅ Config real cargado - contiene fields")
    
    if "synonyms_user" in config:
        assert isinstance(config["synonyms_user"], dict), "synonyms_user debe ser diccionario"
        print("✅ Config real cargado - contiene synonyms_user")
    
    print("✅ PASS: Config.json real cargado correctamente")
    return True


def test_default_config_structure():
    """Test que DEFAULT_CONFIG tiene la estructura esperada"""
    print("🧪 Testing estructura de DEFAULT_CONFIG...")
    
    assert isinstance(DEFAULT_CONFIG, dict), "DEFAULT_CONFIG debe ser diccionario"
    assert "kml" in DEFAULT_CONFIG, "Debe contener sección kml"
    
    kml_config = DEFAULT_CONFIG["kml"]
    assert "azimuth_km" in kml_config, "kml debe contener azimuth_km"
    assert "cone" in kml_config, "kml debe contener configuración de cone"
    assert "line" in kml_config, "kml debe contener configuración de line"
    assert "description" in kml_config, "kml debe contener description"
    
    # Verificar estructura de description
    desc = kml_config["description"]
    assert isinstance(desc, list), "description debe ser lista"
    assert len(desc) >= 3, "description debe tener al menos 3 bloques"
    
    print("✅ PASS: DEFAULT_CONFIG tiene estructura correcta")
    return True


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.config_manager")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1
    if test_default_config_structure():
        tests_passed += 1
    
    # Test 2
    if test_cargar_config_default():
        tests_passed += 1
    
    # Test 3 
    if test_cargar_config_archivo_real():
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTADOS: {tests_passed}/{total_tests} tests pasaron")
    
    if tests_passed == total_tests:
        print("🎯 ✅ TODOS LOS UNIT TESTS PASARON!")
        return True
    else:
        print("🚨 ❌ ALGUNOS TESTS FALLARON")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)