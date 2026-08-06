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


def test_cargar_config_tras_eliminar_codigo_muerto():
    """Test que cargar_config sigue funcionando tras eliminar el add_user_synonym
    anidado (inalcanzable) que vivía después de los returns del try/except."""
    print("🧪 Testing cargar_config tras eliminar código muerto...")

    import inspect

    # La función ya no debe declarar un add_user_synonym anidado.
    fuente = inspect.getsource(cargar_config)
    assert "def add_user_synonym" not in fuente, (
        "cargar_config no debe contener una definición anidada de add_user_synonym"
    )

    config = cargar_config()
    assert isinstance(config, dict), "Debe retornar un diccionario"
    assert "kml" in config, "Debe contener sección kml"
    assert "azimuth_km" in config["kml"], "Debe contener azimuth_km"

    print("✅ PASS: cargar_config funciona correctamente sin el código muerto")


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


# ---------------------------------------------------------------------------
# Gate pre-PyInstaller v1.1: config base/usuario en modo frozen
# ---------------------------------------------------------------------------

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def test_cargar_config_normal_mode_sigue_leyendo_config_repo():
    """Modo normal: cargar_config debe seguir leyendo el config.json del repo
    (comportamiento histórico, sin fusión de config de usuario)."""
    assert getattr(sys, "frozen", False) is False

    config = cargar_config()
    assert "kml" in config
    # _info/_ejemplo son las únicas claves de synonyms_user en el repo real
    assert "_info" in (config.get("synonyms_user") or {})


def test_cargar_config_frozen_lee_base_desde_meipass(tmp_path, monkeypatch):
    """Modo frozen: la config base se lee desde sys._MEIPASS, no del repo."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    _write_json(bundle_dir / "config.json", {"kml": {"azimuth_km": 9.9}})

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))

    config = cargar_config()

    assert config["kml"]["azimuth_km"] == 9.9


def test_cargar_config_frozen_fusiona_synonyms_user_de_localappdata(tmp_path, monkeypatch):
    """Modo frozen: synonyms_user del archivo de usuario se fusiona sobre la base,
    conservando kml/branding/schema de la base intactos."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    _write_json(
        bundle_dir / "config.json",
        {
            "kml": {"azimuth_km": 1.5},
            "branding": {"logo_path": "logo.png"},
            "schema": {"fields": {"lat": {}}},
            "synonyms_user": {"_info": "no editar a mano"},
        },
    )

    localappdata = tmp_path / "localappdata"
    user_dir = localappdata / "TZ Analyzer"
    user_dir.mkdir(parents=True)
    _write_json(user_dir / "config.json", {"synonyms_user": {"numero": "tel"}})

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))

    config = cargar_config()

    assert config["kml"] == {"azimuth_km": 1.5}
    assert config["branding"] == {"logo_path": "logo.png"}
    assert config["schema"] == {"fields": {"lat": {}}}
    assert config["synonyms_user"]["_info"] == "no editar a mano"
    assert config["synonyms_user"]["numero"] == "tel"


def test_add_user_synonym_frozen_escribe_solo_localappdata_y_no_toca_meipass(tmp_path, monkeypatch):
    """Modo frozen: add_user_synonym debe escribir únicamente en LOCALAPPDATA,
    sin modificar el config.json base (_MEIPASS)."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    base_config_path = bundle_dir / "config.json"
    _write_json(base_config_path, {"kml": {"azimuth_km": 1.5}})
    original_bytes = base_config_path.read_bytes()

    localappdata = tmp_path / "localappdata"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))

    test_config = {"synonyms_user": {}}
    result = add_user_synonym(test_config, "tel", "numero_telefono")

    assert result["synonyms_user"]["numero_telefono"] == "tel"
    # _MEIPASS no debe modificarse
    assert base_config_path.read_bytes() == original_bytes
    # Debe existir el archivo de usuario en LOCALAPPDATA
    user_config_path = localappdata / "TZ Analyzer" / "config.json"
    assert user_config_path.exists()
    persisted = json.loads(user_config_path.read_text(encoding="utf-8"))
    assert persisted["synonyms_user"]["numero_telefono"] == "tel"


def test_add_user_synonym_frozen_segunda_carga_recupera_sinonimo(tmp_path, monkeypatch):
    """Tras escribir un sinónimo en modo frozen, una segunda carga de config
    (nuevo 'arranque' del proceso) debe recuperarlo."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    _write_json(bundle_dir / "config.json", {"kml": {"azimuth_km": 1.5}})

    localappdata = tmp_path / "localappdata"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))

    # Primera "sesión": agrega el sinónimo
    config_v1 = cargar_config()
    add_user_synonym(config_v1, "tel", "numero_telefono")

    # Segunda "sesión": nueva carga desde cero
    config_v2 = cargar_config()
    assert config_v2["synonyms_user"]["numero_telefono"] == "tel"


def test_add_user_synonym_frozen_json_usuario_corrupto_continua_con_advertencia(tmp_path, monkeypatch, capsys):
    """Archivo de usuario corrupto: cargar_config no debe fallar, debe continuar
    con advertencia visible en consola."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    _write_json(bundle_dir / "config.json", {"kml": {"azimuth_km": 1.5}})

    localappdata = tmp_path / "localappdata"
    user_dir = localappdata / "TZ Analyzer"
    user_dir.mkdir(parents=True)
    (user_dir / "config.json").write_text("{esto no es json", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))

    config = cargar_config()

    assert config["kml"]["azimuth_km"] == 1.5  # sigue funcionando con la base
    captured = capsys.readouterr()
    assert "no se pudo leer" in captured.out.lower()


def test_add_user_synonym_frozen_permission_error_al_escribir_genera_advertencia(tmp_path, monkeypatch, capsys):
    """PermissionError al escribir el archivo de usuario: debe avisar visible/
    capturable en consola, sin lanzar excepción."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))

    def _boom(*args, **kwargs):
        raise PermissionError("acceso denegado")

    monkeypatch.setattr("tz_core.user_paths.tempfile.mkstemp", _boom)

    test_config = {"synonyms_user": {}}
    # No debe lanzar excepción
    result = add_user_synonym(test_config, "tel", "numero_telefono")

    assert result["synonyms_user"]["numero_telefono"] == "tel"  # en memoria sí se agrega
    captured = capsys.readouterr()
    assert "no se pudo guardar" in captured.out.lower()


def test_add_user_synonym_archivo_usuario_ausente_no_falla(tmp_path, monkeypatch):
    """Primera ejecución sin archivo de usuario previo: no debe fallar."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    _write_json(bundle_dir / "config.json", {"kml": {"azimuth_km": 1.5}})

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata_nuevo"))

    config = cargar_config()
    assert config["kml"]["azimuth_km"] == 1.5


def test_config_json_repo_conserva_hash_identico_tras_operaciones_frozen(tmp_path, monkeypatch):
    """Ejercitar el flujo frozen no debe tocar el config.json real del repo."""
    import hashlib

    repo_config = Path(__file__).resolve().parent.parent.parent / "config.json"
    hash_before = hashlib.sha256(repo_config.read_bytes()).hexdigest()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle_inexistente"), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))

    # cargar_config con _MEIPASS inválido cae a DEFAULT_CONFIG (no toca el repo)
    cargar_config()
    add_user_synonym({"synonyms_user": {}}, "tel", "numero_telefono")

    hash_after = hashlib.sha256(repo_config.read_bytes()).hexdigest()
    assert hash_before == hash_after


def main():
    """Ejecutar todos los tests"""
    print("🏗️  TESTS UNITARIOS - tz_core.config_manager")
    print("=" * 50)
    
    test_functions = [
        test_default_config_structure,
        test_cargar_config_default,
        test_cargar_config_archivo_real,
        test_cargar_config_tras_eliminar_codigo_muerto,
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