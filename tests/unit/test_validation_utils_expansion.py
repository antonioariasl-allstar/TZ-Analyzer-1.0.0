"""
Tests para FASE 2G: Expansion Validation Utils
==============================================

🎯 PROPÓSITO: Tests exhaustivos para nuevas funciones de validación avanzadas
📊 COBERTURA: Normal, errores, edge cases, compatibilidad backward
🚀 ESTRATEGIA: Testing express pero comprehensivo para micro-fase

Tests para funciones migradas en FASE 2G:
- to_object: Conversión tipos a object
- is_excel_serial: Detección seriales Excel  
- excel_serial_to_timestamp: Conversión seriales a timestamps
- to_float_safe: Conversión float tolerante con limpieza
- coerce_azimut: Validación azimut [0..360)
"""

import pytest
import pandas as pd
import numpy as np
import math
from datetime import datetime

from tz_core.validation_utils import (
    # Funciones básicas existentes
    tiene_valor, es_num, a_float,
    # Funciones avanzadas FASE 2G
    to_object, is_excel_serial, excel_serial_to_timestamp,
    to_float_safe, coerce_azimut,
    # Aliases de compatibilidad
    _to_object, _is_excel_serial, _excel_serial_to_timestamp,
    _to_float_safe, _coerce_azimut
)


class TestToObjectConversion:
    """Tests para to_object() - conversión a dtype object."""
    
    def test_to_object_basic(self):
        """Test conversión básica de columnas numéricas a object."""
        df = pd.DataFrame({
            'numeros': [1, 2, 3],
            'textos': ['a', 'b', 'c'],
            'floats': [1.1, 2.2, 3.3]
        })
        
        # Verificar tipos iniciales
        assert df['numeros'].dtype == 'int64'
        assert df['floats'].dtype == 'float64'
        
        # Convertir a object
        to_object(df, ['numeros', 'floats'])
        
        # Verificar conversión
        assert df['numeros'].dtype == 'O'
        assert df['floats'].dtype == 'O'
        assert df['textos'].dtype == 'O'  # Ya era object
        
    def test_to_object_nonexistent_columns(self):
        """Test manejo de columnas que no existen."""
        df = pd.DataFrame({'col1': [1, 2, 3]})
        
        # No debe fallar con columnas inexistentes
        to_object(df, ['col1', 'col_inexistente'])
        
        assert df['col1'].dtype == 'O'
        assert 'col_inexistente' not in df.columns
        
    def test_to_object_already_object(self):
        """Test que no afecte columnas ya en object."""
        df = pd.DataFrame({'textos': ['a', 'b', 'c']})
        original_dtype = df['textos'].dtype
        
        to_object(df, ['textos'])
        
        assert df['textos'].dtype == original_dtype == 'O'


class TestExcelSerialDetection:
    """Tests para is_excel_serial() - detección de seriales Excel."""
    
    def test_is_excel_serial_valid_numbers(self):
        """Test detección de números válidos como seriales Excel."""
        # Números positivos finitos deberían ser válidos
        assert is_excel_serial(1) == True
        assert is_excel_serial(44927) == True  # Feb 2023
        assert is_excel_serial(36526) == True  # Año 2000
        assert is_excel_serial(1.5) == True    # Con decimales
        
    def test_is_excel_serial_invalid_numbers(self):
        """Test rechazo de números inválidos."""
        assert is_excel_serial(0) == False      # Zero no válido
        assert is_excel_serial(-1) == False     # Negativos no válidos
        assert is_excel_serial(float('inf')) == False   # Infinito no válido
        assert is_excel_serial(float('-inf')) == False  # -Infinito no válido
        assert is_excel_serial(float('nan')) == False   # NaN no válido
        
    def test_is_excel_serial_non_numeric(self):
        """Test rechazo de valores no numéricos."""
        assert is_excel_serial("texto") == False
        assert is_excel_serial(None) == False
        assert is_excel_serial([1, 2, 3]) == False
        assert is_excel_serial({'a': 1}) == False
        
    def test_is_excel_serial_string_numbers(self):
        """Test conversión de strings numéricos."""
        assert is_excel_serial("44927") == True   # String numérico válido
        assert is_excel_serial("0") == False      # String "0" no válido
        assert is_excel_serial("-5") == False     # String negativo no válido


class TestExcelSerialConversion:
    """Tests para excel_serial_to_timestamp() - conversión a timestamps."""
    
    def test_excel_serial_to_timestamp_valid(self):
        """Test conversión exitosa de seriales válidos."""
        # Serial conocido: 44927 = 2023-02-15
        result = excel_serial_to_timestamp(44927)
        assert result is not None
        assert isinstance(result, pd.Timestamp)
        assert result.year == 2023
        assert result.month == 2
        assert result.day == 15
        
    def test_excel_serial_to_timestamp_epoch(self):
        """Test conversión del día 1 de Excel."""
        # Serial 1 = 1899-12-31 (día después del origin)
        result = excel_serial_to_timestamp(1)
        assert result is not None
        assert result.year == 1899
        assert result.month == 12
        assert result.day == 31
        
    def test_excel_serial_to_timestamp_invalid(self):
        """Test manejo de valores inválidos."""
        assert excel_serial_to_timestamp("invalid") is None
        assert excel_serial_to_timestamp(None) is None
        assert excel_serial_to_timestamp(float('nan')) is None
        assert excel_serial_to_timestamp([1, 2, 3]) is None
        
    def test_excel_serial_to_timestamp_string_numbers(self):
        """Test conversión de strings numéricos."""
        result = excel_serial_to_timestamp("44927")
        assert result is not None
        assert result.year == 2023


class TestToFloatSafe:
    """Tests para to_float_safe() - conversión tolerante a float."""
    
    def test_to_float_safe_clean_data(self):
        """Test conversión de datos limpios."""
        series = pd.Series([1, 2.5, "3.14", "42"])
        result, invalid_count = to_float_safe(series)
        
        expected = [1.0, 2.5, 3.14, 42.0]
        assert result.tolist() == expected
        assert invalid_count == 0
        
    def test_to_float_safe_comma_decimals(self):
        """Test conversión de comas decimales a puntos."""
        series = pd.Series(["3,14", "2,71", "1,0"])
        result, invalid_count = to_float_safe(series)
        
        expected = [3.14, 2.71, 1.0]
        assert result.tolist() == expected
        assert invalid_count == 0
        
    def test_to_float_safe_whitespace_cleaning(self):
        """Test eliminación de espacios en blanco."""
        series = pd.Series([" 3.14 ", "\t2.71\n", "  42  "])
        result, invalid_count = to_float_safe(series)
        
        expected = [3.14, 2.71, 42.0]
        assert result.tolist() == expected
        assert invalid_count == 0
        
    def test_to_float_safe_invalid_data(self):
        """Test manejo de datos inválidos."""
        series = pd.Series(["texto", None, "invalid", ""])
        result, invalid_count = to_float_safe(series)
        
        assert all(np.isnan(result))
        assert invalid_count == 4
        
    def test_to_float_safe_mixed_data(self):
        """Test mezcla de datos válidos e inválidos."""
        series = pd.Series(["3,14", " 2.71 ", "texto", None, "42"])
        result, invalid_count = to_float_safe(series)
        
        assert result.iloc[0] == 3.14
        assert result.iloc[1] == 2.71
        assert np.isnan(result.iloc[2])  # "texto"
        assert np.isnan(result.iloc[3])  # None
        assert result.iloc[4] == 42.0
        assert invalid_count == 2


class TestCoerceAzimut:
    """Tests para coerce_azimut() - validación de azimut."""
    
    def test_coerce_azimut_valid_range(self):
        """Test valores de azimut válidos [0, 360)."""
        series = pd.Series([0, 90, 180, 270, 359])
        result, invalid_count = coerce_azimut(series)
        
        expected = [0.0, 90.0, 180.0, 270.0, 359.0]
        assert result.tolist() == expected
        assert invalid_count == 0
        
    def test_coerce_azimut_boundary_cases(self):
        """Test casos límite del rango de azimut."""
        series = pd.Series([0, 359.9, 360, -0.1])
        result, invalid_count = coerce_azimut(series)
        
        assert result.iloc[0] == 0.0      # 0 válido
        assert result.iloc[1] == 359.9    # Casi 360 válido
        assert np.isnan(result.iloc[2])   # 360 inválido
        assert np.isnan(result.iloc[3])   # Negativo inválido
        assert invalid_count == 2
        
    def test_coerce_azimut_string_numbers(self):
        """Test conversión de strings numéricos."""
        series = pd.Series(["90", "180.5", "270"])
        result, invalid_count = coerce_azimut(series)
        
        expected = [90.0, 180.5, 270.0]
        assert result.tolist() == expected
        assert invalid_count == 0
        
    def test_coerce_azimut_invalid_data(self):
        """Test datos completamente inválidos."""
        series = pd.Series(["N", "S", "texto", None, float('inf')])
        result, invalid_count = coerce_azimut(series)
        
        assert all(np.isnan(result))
        assert invalid_count == 5
        
    def test_coerce_azimut_out_of_range(self):
        """Test valores fuera del rango válido."""
        series = pd.Series([-10, -1, 360, 361, 720])
        result, invalid_count = coerce_azimut(series)
        
        assert all(np.isnan(result))
        assert invalid_count == 5


class TestBackwardCompatibility:
    """Tests de compatibilidad backward con aliases."""
    
    def test_alias_functions_exist(self):
        """Verificar que existan todos los aliases de compatibilidad."""
        # Aliases básicos
        assert _to_object is to_object
        assert _is_excel_serial is is_excel_serial
        assert _excel_serial_to_timestamp is excel_serial_to_timestamp
        assert _to_float_safe is to_float_safe
        assert _coerce_azimut is coerce_azimut
        
    def test_alias_functions_work(self):
        """Verificar que los aliases funcionen correctamente."""
        # Test _is_excel_serial
        assert _is_excel_serial(44927) == True
        assert _is_excel_serial("invalid") == False
        
        # Test _to_float_safe
        series = pd.Series(["3,14", "texto"])
        result, invalid = _to_float_safe(series)
        assert result.iloc[0] == 3.14
        assert np.isnan(result.iloc[1])
        assert invalid == 1


class TestEdgeCasesAndRobustness:
    """Tests de edge cases y robustez general."""
    
    def test_empty_series_handling(self):
        """Test manejo de Series vacías."""
        empty_series = pd.Series([], dtype=object)
        
        result, invalid = to_float_safe(empty_series)
        assert len(result) == 0
        assert invalid == 0
        
        result, invalid = coerce_azimut(empty_series)
        assert len(result) == 0
        assert invalid == 0
        
    def test_single_value_series(self):
        """Test Series con un solo valor."""
        single_series = pd.Series(["3,14"])
        
        result, invalid = to_float_safe(single_series)
        assert len(result) == 1
        assert result.iloc[0] == 3.14
        assert invalid == 0
        
    def test_large_numbers_handling(self):
        """Test manejo de números muy grandes."""
        # Excel serial muy grande pero válido
        large_serial = 999999
        assert is_excel_serial(large_serial) == True
        
        result = excel_serial_to_timestamp(large_serial)
        assert result is not None
        
    def test_unicode_string_handling(self):
        """Test manejo de strings Unicode."""
        unicode_series = pd.Series(["3·14", "2,71", "π"])
        result, invalid = to_float_safe(unicode_series)
        
        # "3·14" debería fallar (· no es punto decimal estándar)
        # "2,71" debería convertirse a 2.71
        # "π" debería fallar
        assert np.isnan(result.iloc[0])  # "3·14" falla
        assert result.iloc[1] == 2.71     # "2,71" se convierte
        assert np.isnan(result.iloc[2])  # "π" falla
        assert invalid == 2