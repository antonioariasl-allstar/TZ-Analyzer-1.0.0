"""
Tests para tz_core.validation_utils

Valida el correcto funcionamiento de los validadores y conversores de datos.
"""

import pytest
import math
import numpy as np
import pandas as pd

from tz_core.validation_utils import tiene_valor, es_num, a_float


class TestTieneValor:
    """Tests para la función tiene_valor."""
    
    def test_valores_validos(self):
        """Debe retornar True para valores válidos."""
        assert tiene_valor(42) == True
        assert tiene_valor(0) == True
        assert tiene_valor(3.14) == True
        assert tiene_valor("hello") == True
        assert tiene_valor("0") == True
        assert tiene_valor([1, 2, 3]) == True
        assert tiene_valor({"key": "value"}) == True
    
    def test_valores_nulos(self):
        """Debe retornar False para valores nulos."""
        assert tiene_valor(None) == False
        assert tiene_valor(float('nan')) == False
    
    def test_strings_vacios(self):
        """Debe retornar False para strings vacíos y espacios."""
        assert tiene_valor("") == False
        assert tiene_valor("   ") == False
        assert tiene_valor("\t\n") == False
    
    def test_indicadores_sin_informacion(self):
        """Debe retornar False para indicadores comunes de falta de información."""
        indicadores = [
            "sin inf.", "sin inf", "s/i", "sininf", 
            "none", "null", "n/a", "na", "--", "—",
            "SIN INF", "NONE", "NULL", "N/A"  # mayúsculas
        ]
        for indicador in indicadores:
            assert tiene_valor(indicador) == False, f"Falló con: '{indicador}'"


class TestEsNum:
    """Tests para la función es_num."""
    
    def test_numeros_validos(self):
        """Debe retornar True para números válidos."""
        assert es_num(42) == True
        assert es_num(0) == True
        assert es_num(-17) == True
        assert es_num(3.14) == True
        assert es_num(-2.5) == True
        assert es_num(np.int32(42)) == True
        assert es_num(np.float64(3.14)) == True
    
    def test_no_numeros(self):
        """Debe retornar False para no-números."""
        assert es_num("hello") == False
        assert es_num("42") == False  # string
        assert es_num([1, 2, 3]) == False
        assert es_num({"key": "value"}) == False
        assert es_num(None) == False
    
    def test_valores_nan(self):
        """Debe retornar False para valores NaN."""
        assert es_num(float('nan')) == False
        assert es_num(np.nan) == False
        assert es_num(pd.NA) == False
    
    def test_manejo_excepciones(self):
        """Debe manejar excepciones graciosamente."""
        # Objeto que puede causar excepción en isinstance
        class ProblematicObject:
            def __instancecheck__(self, instance):
                raise Exception("Test exception")
        
        # No debe fallar, debe retornar False
        assert es_num(ProblematicObject()) == False


class TestAFloat:
    """Tests para la función a_float."""
    
    def test_conversiones_exitosas(self):
        """Debe convertir exitosamente valores numéricos válidos."""
        assert a_float(42) == 42.0
        assert a_float("42") == 42.0
        assert a_float("3.14") == 3.14
        assert a_float("3,14") == 3.14  # coma como decimal
        assert a_float(-17) == -17.0
        assert a_float("-2.5") == -2.5
        assert a_float("0") == 0.0
    
    def test_conversiones_fallidas(self):
        """Debe retornar None para valores que no se pueden convertir."""
        assert a_float("hello") is None
        assert a_float("") is None
        assert a_float("abc123") is None
        assert a_float([1, 2, 3]) is None
        assert a_float({"key": "value"}) is None
        assert a_float(None) is None
    
    def test_valores_infinitos(self):
        """Debe retornar None para valores infinitos."""
        assert a_float(float('inf')) is None
        assert a_float(float('-inf')) is None
        assert a_float("inf") is None
        assert a_float("-inf") is None
    
    def test_casos_especiales(self):
        """Debe manejar casos especiales correctamente."""
        # NaN debe ser None (no es finite)
        result = a_float(float('nan'))
        assert result is None
        
        # Espacios deben ser manejados
        assert a_float("  42  ") == 42.0


class TestCompatibilidad:
    """Tests de compatibilidad con aliases."""
    
    def test_aliases_existen(self):
        """Los aliases deben existir para compatibilidad."""
        from tz_core.validation_utils import _tiene_valor, _es_num, _a_float
        
        # Deben ser la misma función
        assert _tiene_valor is tiene_valor
        assert _es_num is es_num
        assert _a_float is a_float
    
    def test_aliases_funcionan(self):
        """Los aliases deben funcionar igual que las funciones principales."""
        from tz_core.validation_utils import _tiene_valor, _es_num, _a_float
        
        assert _tiene_valor(42) == tiene_valor(42)
        assert _es_num(3.14) == es_num(3.14)
        assert _a_float("3,14") == a_float("3,14")