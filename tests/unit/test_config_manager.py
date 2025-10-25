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

from tz_core.config_manager import (
    cargar_config, 
    DEFAULT_CONFIG,
    _normalize_key_for_synonyms,
    cfg_build_rename_map,
    log
)
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


def test_normalize_key_for_synonyms():
    """Test normalización de claves para sinónimos"""
    print("🧪 Testing _normalize_key_for_synonyms...")
    
    # Casos de prueba
    test_cases = [
        ("LATITUD", "latitud"),
        ("Número de Teléfono", "numero de telefono"),
        ("  IMEI  ", "imei"),
        ("", ""),
        (None, ""),
        ("Azimút", "azimut"),  # Acentos
    ]
    
    for input_val, expected in test_cases:
        result = _normalize_key_for_synonyms(input_val)
        assert result == expected, f"_normalize_key_for_synonyms({input_val!r}) = {result!r}, esperado {expected!r}"
    
    print("✅ PASS: Normalización de claves funciona correctamente")
    return True


def test_cfg_build_rename_map():
    """Test construcción de mapa de sinónimos"""
    print("🧪 Testing cfg_build_rename_map...")
    
    # Config de prueba con sinónimos
    test_config = {
        "schema": {
            "fields": {
                "lat": {
                    "synonyms": ["latitud", "latitude", "LAT"]
                },
                "tel": {
                    "synonyms": ["telefono", "phone", "numero"]
                }
            }
        },
        "synonyms_user": {
            "mi_campo": "lat",
            "_internal": "ignored"  # Se ignora por empezar con _
        }
    }
    
    rename_map = cfg_build_rename_map(test_config)
    
    assert isinstance(rename_map, dict), "rename_map debe ser dict"
    assert "lat" in rename_map, "rename_map debe contener 'lat'"
    assert "tel" in rename_map, "rename_map debe contener 'tel'"
    
    # Verificar que los sinónimos se normalizan
    lat_synonyms = rename_map["lat"]
    assert isinstance(lat_synonyms, set), "Sinónimos deben ser set"
    assert "latitud" in lat_synonyms, "lat debe incluir sinónimo 'latitud'"
    assert "lat" in lat_synonyms, "lat debe incluirse a sí mismo"
    
    # DEBUG: Ver qué contiene lat_synonyms
    print(f"🔍 lat_synonyms contiene: {lat_synonyms}")
    
    # Verificar synonyms_user - la lógica del código agrega al campo normalizado del mapped value
    # mi_campo -> lat significa que 'mi_campo' se agrega como sinónimo de 'lat'
    assert "mi_campo" in lat_synonyms, "lat debe incluir 'mi_campo' del synonyms_user"
    
    print("✅ PASS: cfg_build_rename_map funciona correctamente")
    return True


def test_log_function():
    """Test función de logging"""
    print("🧪 Testing función log...")
    
    # Solo verificamos que no falla
    try:
        log("Test message desde unit test")
        print("✅ PASS: Función log ejecuta sin errores")
        return True
    except Exception as e:
        print(f"❌ FAIL: log() falló: {e}")
        return False


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.config_manager")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: Estructura DEFAULT_CONFIG
    if test_default_config_structure():
        tests_passed += 1
    
    # Test 2: Config archivo inexistente
    if test_cargar_config_default():
        tests_passed += 1
    
    # Test 3: Config real
    if test_cargar_config_archivo_real():
        tests_passed += 1
    
    # Test 4: Normalización de claves
    if test_normalize_key_for_synonyms():
        tests_passed += 1
    
    # Test 5: Construcción de rename map
    if test_cfg_build_rename_map():
        tests_passed += 1
    
    # Test 6: Función log
    if test_log_function():
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