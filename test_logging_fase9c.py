"""
Test de verificación para extracción de logging - FASE 9C
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_logging_extraction():
    """Verifica que la extracción del logging funciona correctamente"""
    
    # Test 1: Import directo del módulo
    from tz_core.logging_utils import log, get_logs, clear_all_logging_state
    
    # Limpiar estado anterior
    clear_all_logging_state()
    
    # Test 2: Función log básica
    log("Test message")
    logs = get_logs()
    assert len(logs) == 1
    assert "Test message" in logs[0]
    assert "202" in logs[0]  # Parte del timestamp del año
    
    # Test 3: Compatibilidad con wrapper en monolito
    import script_principal_bitacoras_refactory as monolito
    
    # Limpiar logs para esta prueba
    clear_all_logging_state()
    
    # Usar función wrapper
    monolito.log("Mensaje desde wrapper")
    
    # Verificar que funciona
    logs = get_logs()
    assert len(logs) == 1
    assert "Mensaje desde wrapper" in logs[0]
    
    # Test 4: Variables globales simuladas
    assert hasattr(monolito, 'LOGS')
    assert hasattr(monolito, 'LOG_PLACEHOLDERS')
    
    # Test 5: Acceso tipo lista a LOGS
    assert len(monolito.LOGS) == 1
    assert "Mensaje desde wrapper" in monolito.LOGS[0]
    
    # Test 6: Placeholders
    monolito.LOG_PLACEHOLDERS.add("test_placeholder")
    assert "test_placeholder" in monolito.LOG_PLACEHOLDERS
    
    print("✅ FASE 9C: Todos los tests de logging pasaron correctamente")
    return True

if __name__ == "__main__":
    test_logging_extraction()