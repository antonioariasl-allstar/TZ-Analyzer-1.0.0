#!/usr/bin/env python3
"""
Test end-to-end Sprint 1 Fase 1.1 
Valida que el script principal funcione con tz_services
"""

import subprocess
import sys
import time
from pathlib import Path

def test_script_loads():
    """Test que el script cargue sin errores"""
    print("🔍 TEST: Script carga sin errores...")
    
    try:
        # Ejecutar script con timeout para evitar colgado en input
        proc = subprocess.Popen(
            [sys.executable, 'script_principal_bitacoras_refactory.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar 3 segundos y terminar
        time.sleep(3)
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=2)
        
        # Validar que llegó al menú principal
        if "T  Z   A N A L Y Z E R" in stdout and "Seleccione el modo" in stdout:
            print("  ✅ Script carga correctamente")
            print("  ✅ Menú principal desplegado")
            print("  ✅ Imports tz_services funcionan")
            return True
        else:
            print(f"  ❌ Script no llegó al menú: {stdout[:200]}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error ejecutando script: {e}")
        return False

def test_tz_services_independent():
    """Test que tz_services funcione independientemente"""
    print("🔍 TEST: tz_services independiente...")
    
    try:
        # Agregar path para encontrar tz_services
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # Test imports
        import tz_services
        from tz_services import validar_columnas, validar_datos
        from tz_services.validation import valid_latlon_vals
        
        # Test funcional básico
        import pandas as pd
        df_test = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        
        # Test validar_columnas
        missing = validar_columnas(df_test, ['a', 'c'])
        assert missing == ['c'], f"Expected ['c'], got {missing}"
        
        # Test validar_datos  
        df_result, errors = validar_datos(df_test, ['a', 'b'])
        assert isinstance(df_result, pd.DataFrame), "Should return DataFrame"
        assert isinstance(errors, list), "Should return error list"
        
        # Test valid_latlon_vals
        assert valid_latlon_vals(13.5, -89.0) == True, "Valid SV coords should pass"
        assert valid_latlon_vals(0, 0) == False, "Origin should fail"
        
        print("  ✅ Import tz_services: OK")
        print("  ✅ Funciones públicas: OK") 
        print("  ✅ validar_columnas: OK")
        print("  ✅ validar_datos: OK")
        print("  ✅ valid_latlon_vals: OK")
        return True
        
    except Exception as e:
        print(f"  ❌ Error en tz_services: {e}")
        return False

def main():
    """Ejecutar todos los tests"""
    print("🧪 TEST END-TO-END SPRINT 1 FASE 1.1")
    print("=" * 45)
    
    tests = [
        test_tz_services_independent,
        test_script_loads
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 45)
    print(f"RESULTADO: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 FASE 1.1 VALIDADA - Ready para commit")
        return True
    else:
        print("❌ Fallos detectados - Revisar antes de commit")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)