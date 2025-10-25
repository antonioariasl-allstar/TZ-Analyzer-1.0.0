"""
Tests unitarios para tz_core.data_loader - FASE 5.1

Cobertura de funciones extraídas:
- obtener_hojas_visibles()
- listar_todas_hojas()

🚨 MINAS DETECTADAS:
- Dependencia opcional openpyxl
- Manejo de archivos Excel reales vs mocks
"""

import pytest
import tempfile
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from tz_core.data_loader import obtener_hojas_visibles, listar_todas_hojas


class TestObtenerHojasVisibles:
    """Tests para función obtener_hojas_visibles"""
    
    def test_sin_openpyxl(self):
        """Test cuando openpyxl no está disponible"""
        with patch('tz_core.data_loader.openpyxl', None):
            resultado, error = obtener_hojas_visibles("cualquier_archivo.xlsx")
            assert resultado is None
            assert error == "NO_OPENPYXL"
    
    def test_archivo_no_existe(self):
        """Test con archivo inexistente debe retornar LOAD_FAIL"""
        resultado, error = obtener_hojas_visibles("archivo_inexistente.xlsx")
        assert resultado is None
        assert error == "LOAD_FAIL"
    
    @patch('tz_core.data_loader.openpyxl')
    def test_hojas_visibles_exitoso(self, mock_openpyxl):
        """Test extracción exitosa de hojas visibles"""
        # Mock del workbook y worksheets
        mock_wb = MagicMock()
        mock_sheet1 = MagicMock()
        mock_sheet1.title = "Hoja1"
        mock_sheet1.sheet_state = "visible"
        
        mock_sheet2 = MagicMock()
        mock_sheet2.title = "Hoja2" 
        mock_sheet2.sheet_state = "hidden"
        
        mock_sheet3 = MagicMock()
        mock_sheet3.title = "Hoja3"
        # Sin sheet_state debe default a "visible"
        del mock_sheet3.sheet_state
        
        mock_wb.worksheets = [mock_sheet1, mock_sheet2, mock_sheet3]
        mock_openpyxl.load_workbook.return_value = mock_wb
        
        resultado, error = obtener_hojas_visibles("test.xlsx")
        
        assert error is None
        assert resultado == ["Hoja1", "Hoja3"]  # Solo las visibles
        mock_wb.close.assert_called_once()
    
    @patch('tz_core.data_loader.openpyxl')
    def test_excepcion_durante_carga(self, mock_openpyxl):
        """Test manejo de excepciones durante carga"""
        mock_openpyxl.load_workbook.side_effect = Exception("Error simulado")
        
        resultado, error = obtener_hojas_visibles("test.xlsx")
        
        assert resultado is None
        assert error == "LOAD_FAIL"


class TestListarTodasHojas:
    """Tests para función listar_todas_hojas"""
    
    def test_archivo_no_existe(self):
        """Test con archivo inexistente debe retornar None"""
        resultado = listar_todas_hojas("archivo_inexistente.xlsx")
        assert resultado is None
    
    @patch('pandas.ExcelFile')
    def test_listar_hojas_exitoso(self, mock_excel_file):
        """Test listado exitoso de todas las hojas"""
        mock_xls = MagicMock()
        mock_xls.sheet_names = ["Hoja1", "Hoja2", "HojaOculta"]
        mock_excel_file.return_value = mock_xls
        
        resultado = listar_todas_hojas("test.xlsx")
        
        assert resultado == ["Hoja1", "Hoja2", "HojaOculta"]
        mock_excel_file.assert_called_once_with("test.xlsx")
    
    @patch('pandas.ExcelFile')
    def test_excepcion_durante_lectura(self, mock_excel_file):
        """Test manejo de excepciones durante lectura"""
        mock_excel_file.side_effect = Exception("Error simulado")
        
        resultado = listar_todas_hojas("test.xlsx")
        
        assert resultado is None


# Fixtures para tests de integración con archivos reales
@pytest.fixture
def excel_temp():
    """Crea archivo Excel temporal para tests de integración"""
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        # Crear Excel simple con pandas
        df1 = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        df2 = pd.DataFrame({'col3': [4, 5, 6], 'col4': ['d', 'e', 'f']})
        
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            df1.to_excel(writer, sheet_name='Datos', index=False)
            df2.to_excel(writer, sheet_name='Resumen', index=False)
        
        yield f.name
        
        # Cleanup
        try:
            os.unlink(f.name)
        except:
            pass


class TestIntegracionArchivosReales:
    """Tests de integración con archivos Excel reales"""
    
    def test_listar_hojas_archivo_real(self, excel_temp):
        """Test con archivo Excel real"""
        resultado = listar_todas_hojas(excel_temp)
        
        assert resultado is not None
        assert "Datos" in resultado
        assert "Resumen" in resultado
        assert len(resultado) == 2