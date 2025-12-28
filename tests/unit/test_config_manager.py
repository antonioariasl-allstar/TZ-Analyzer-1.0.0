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
    log,
    solicitar_color_tema,
    atomic_write_json,
    add_user_synonym
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


def test_log_function():
    """Test función de logging"""
    print("🧪 Testing función log...")
    
    # Solo verificamos que no falla
    log("Test message desde unit test")
    print("✅ PASS: Función log ejecuta sin errores")


def test_solicitar_color_tema_default():
    """Test solicitar_color_tema con entrada vacía (default)"""
    print("🧪 Testing solicitar_color_tema con default...")
    
    # Config de prueba
    test_config = {
        "style": {
            "theme_hex": "#ff0000",
            "palette": [
                ["Rojo", "#ff0000"],
                ["Verde", "#00ff00"],
                ["Azul", "#0000ff"]
            ]
        }
    }
    
    # Mock de input que retorna string vacío (default)
    def mock_input(prompt):
        return ""
    
    result_config = solicitar_color_tema(test_config.copy(), input_mock=mock_input)
    
    assert result_config["style"]["theme_hex"] == "#ff0000", "Debe mantener color default"
    print("✅ PASS: Default color preservado correctamente")


def test_solicitar_color_tema_palette_selection():
    """Test solicitar_color_tema con selección de paleta"""
    print("🧪 Testing solicitar_color_tema con selección numérica...")
    
    # Config de prueba
    test_config = {
        "style": {
            "theme_hex": "#ff0000",
            "palette": [
                ["Rojo", "#ff0000"],
                ["Verde", "#00ff00"],
                ["Azul", "#0000ff"]
            ]
        }
    }
    
    # Mock de input que selecciona opción 2 (Verde)
    def mock_input(prompt):
        return "2"
    
    result_config = solicitar_color_tema(test_config.copy(), input_mock=mock_input)
    
    assert result_config["style"]["theme_hex"] == "#00ff00", "Debe seleccionar verde (#00ff00)"
    print("✅ PASS: Selección de paleta funciona correctamente")


def test_solicitar_color_tema_hex_manual():
    """Test solicitar_color_tema con HEX manual"""
    print("🧪 Testing solicitar_color_tema con HEX manual...")
    
    # Config de prueba sin paleta
    test_config = {
        "style": {
            "theme_hex": "#ff0000"
        }
    }
    
    # Mock de input que introduce HEX manual
    def mock_input(prompt):
        return "#123456"
    
    result_config = solicitar_color_tema(test_config.copy(), input_mock=mock_input)
    
    assert result_config["style"]["theme_hex"] == "#123456", "Debe usar HEX manual"
    print("✅ PASS: HEX manual funciona correctamente")


def test_solicitar_color_tema_invalid_input():
    """Test solicitar_color_tema con entrada inválida"""
    print("🧪 Testing solicitar_color_tema con entrada inválida...")
    
    # Config de prueba
    test_config = {
        "style": {
            "theme_hex": "#ff0000"
        }
    }
    
    # Mock de input que introduce valor inválido
    def mock_input(prompt):
        return "xyz123"
    
    result_config = solicitar_color_tema(test_config.copy(), input_mock=mock_input)
    
    assert result_config["style"]["theme_hex"] == "#ff0000", "Debe usar default por entrada inválida"
    print("✅ PASS: Validación de entrada inválida funciona")


def test_atomic_write_json():
    """Test escritura atómica de JSON con backup"""
    print("🧪 Testing atomic_write_json...")
    
    import tempfile
    import os
    import json
    
    # Crear directorio temporal para test
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test_config.json")
        
        # Test data
        test_data = {
            "test": "data",
            "number": 123,
            "array": [1, 2, 3]
        }
        
        # Escribir archivo
        atomic_write_json(test_file, test_data)
        
        # Verificar que existe
        assert os.path.exists(test_file), "Archivo debe existir después de escritura"
        
        # Verificar contenido
        with open(test_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        
        assert loaded_data == test_data, "Datos cargados deben coincidir con los escritos"
        
        # Test backup al sobrescribir
        new_data = {"updated": "content"}
        atomic_write_json(test_file, new_data)
        
        # Debe existir archivo de backup
        backup_files = [f for f in os.listdir(temp_dir) if f.startswith("test_config.json.backup")]
        assert len(backup_files) > 0, "Debe crear archivo de backup"
        
        # Verificar nuevo contenido
        with open(test_file, "r", encoding="utf-8") as f:
            updated_data = json.load(f)
        
        assert updated_data == new_data, "Archivo debe estar actualizado"
    
    print("✅ PASS: atomic_write_json funciona correctamente")


def test_add_user_synonym():
    """Test agregado de sinónimos dinámicos con persistencia"""
    print("🧪 Testing add_user_synonym...")
    
    import tempfile
    import os
    
    # Config de prueba
    test_config = {
        "synonyms_user": {
            "campo_existente": "lat"
        }
    }
    
    # Crear archivo temporal para persistencia
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_file = os.path.join(temp_dir, "config.json")
        
        # Test: Agregar nuevo sinónimo
        result_config = add_user_synonym(
            test_config.copy(), 
            "tel", 
            "numero_telefono", 
            temp_config_file
        )
        
        # Verificar que se agregó al CONFIG
        assert "numero_telefono" in result_config["synonyms_user"], "Debe agregar nuevo sinónimo"
        assert result_config["synonyms_user"]["numero_telefono"] == "tel", "Debe mapear correctamente"
        
        # Verificar que se persistió en archivo
        assert os.path.exists(temp_config_file), "Debe crear archivo de configuración"
        
        # Cargar y verificar persistencia
        import json
        with open(temp_config_file, "r", encoding="utf-8") as f:
            persisted_config = json.load(f)
        
        assert "numero_telefono" in persisted_config["synonyms_user"], "Debe persistir en JSON"
        
        # Test: No duplicar sinónimo existente
        original_size = len(result_config["synonyms_user"])
        result_config2 = add_user_synonym(
            result_config, 
            "tel", 
            "numero_telefono",  # Mismo sinónimo
            temp_config_file
        )
        
        assert len(result_config2["synonyms_user"]) == original_size, "No debe duplicar sinónimos"
    
    print("✅ PASS: add_user_synonym funciona correctamente")


def test_add_user_synonym_invalid_inputs():
    """Test add_user_synonym con entradas inválidas"""
    print("🧪 Testing add_user_synonym con entradas inválidas...")
    
    # Test: CONFIG inválido
    result1 = add_user_synonym(None, "canonico", "crudo")
    assert result1 is None, "Debe retornar CONFIG original si es inválido"
    
    # Test: Parámetros vacíos
    test_config = {"synonyms_user": {}}
    result2 = add_user_synonym(test_config, "", "crudo")
    assert len(result2["synonyms_user"]) == 0, "No debe agregar sinónimo con canonico vacío"
    
    result3 = add_user_synonym(test_config, "canonico", "")
    assert len(result3["synonyms_user"]) == 0, "No debe agregar sinónimo con crudo vacío"
    
    print("✅ PASS: Validación de entradas inválidas funciona")


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.config_manager")
    print("=" * 50)
    
    test_functions = [
        test_default_config_structure,
        test_cargar_config_default,
        test_cargar_config_archivo_real,
        test_normalize_key_for_synonyms,
        test_cfg_build_rename_map,
        test_log_function,
        test_solicitar_color_tema_default,
        test_solicitar_color_tema_palette_selection,
        test_solicitar_color_tema_hex_manual,
        test_solicitar_color_tema_invalid_input,
        test_atomic_write_json,
        test_add_user_synonym,
        test_add_user_synonym_invalid_inputs,
    ]

    tests_passed = 0
    total_tests = len(test_functions)

    for test_fn in test_functions:
        try:
            test_fn()
            tests_passed += 1
        except AssertionError as err:
            print(f"❌ {test_fn.__name__} falló: {err}")
        except Exception as err:
            print(f"❌ {test_fn.__name__} lanzó excepción: {err}")
    
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