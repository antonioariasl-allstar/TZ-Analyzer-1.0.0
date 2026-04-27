"""
Tests unitarios para tz_core.data_loader - FASES 5.1, 5.2 y 5.3a

Cobertura de funciones extraídas:
- obtener_hojas_visibles()
- listar_todas_hojas()
- seleccionar_hoja_visible() (interactiva con input())
- seleccionar_hoja() (interactiva con input())
- cargar_excel_con_normalizacion() (sistema dual de columnas)

🚨 MINAS DETECTADAS:
- Dependencia opcional openpyxl
- Manejo de archivos Excel reales vs mocks
- Funciones interactivas que requieren mocking de input()
- Sistema dual de columnas (df.attrs + normalizadas)
"""

import pytest
import tempfile
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from tz_core.data_loader import (
    obtener_hojas_visibles, 
    listar_todas_hojas,
    seleccionar_hoja_visible,
    seleccionar_hoja
)


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


class TestSeleccionarHojaVisible:
    """Tests para función seleccionar_hoja_visible (interactiva)"""
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    def test_no_openpyxl_disponible(self, mock_obtener_hojas):
        """Test cuando openpyxl no está disponible"""
        mock_obtener_hojas.return_value = (None, "NO_OPENPYXL")
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado is None
            mock_print.assert_called_with("Aviso: 'openpyxl' no disponible; se usará la primera hoja por defecto.")
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    def test_error_carga_archivo(self, mock_obtener_hojas):
        """Test cuando hay error al cargar el archivo"""
        mock_obtener_hojas.return_value = (None, "LOAD_FAIL")
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado is None
            mock_print.assert_called_with("Aviso: no se pudo inspeccionar hojas; se usará la primera hoja por defecto.")
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    def test_sin_hojas_visibles(self, mock_obtener_hojas):
        """Test cuando no hay hojas visibles"""
        mock_obtener_hojas.return_value = ([], None)
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado is None
            mock_print.assert_called_with("No hay hojas visibles; se usará la primera hoja por defecto.")
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    def test_una_sola_hoja_visible(self, mock_obtener_hojas):
        """Test cuando hay una sola hoja visible"""
        mock_obtener_hojas.return_value = (["Datos"], None)
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado == "Datos"
            mock_print.assert_called_with("Hoja visible detectada: Datos")
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    @patch('tz_core.data_loader.safe_input')
    def test_seleccion_interactiva_primera_opcion(self, mock_input, mock_obtener_hojas):
        """Test selección interactiva - primera opción (Enter)"""
        mock_obtener_hojas.return_value = (["Datos", "Resumen", "Config"], None)
        mock_input.return_value = ""  # Enter = primera opción
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado == "Datos"
            # Verificar que se mostraron las opciones
            calls = mock_print.call_args_list
            assert any("Hojas visibles detectadas:" in str(call) for call in calls)
            assert any("[1] Datos" in str(call) for call in calls)
            assert any("Hoja seleccionada: Datos" in str(call) for call in calls)
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    @patch('tz_core.data_loader.safe_input')
    def test_seleccion_interactiva_segunda_opcion(self, mock_input, mock_obtener_hojas):
        """Test selección interactiva - segunda opción"""
        mock_obtener_hojas.return_value = (["Datos", "Resumen"], None)
        mock_input.return_value = "2"
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado == "Resumen"
            assert any("Hoja seleccionada: Resumen" in str(call) for call in mock_print.call_args_list)
    
    @patch('tz_core.data_loader.obtener_hojas_visibles')
    @patch('tz_core.data_loader.safe_input')
    def test_seleccion_interactiva_input_invalido_luego_valido(self, mock_input, mock_obtener_hojas):
        """Test selección interactiva - input inválido luego válido"""
        mock_obtener_hojas.return_value = (["Datos", "Resumen"], None)
        mock_input.side_effect = ["abc", "0", "3", "1"]  # Varios inválidos, luego válido
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja_visible("test.xlsx")
            
            assert resultado == "Datos"
            # Debe haber mostrado mensajes de error
            calls = mock_print.call_args_list
            error_messages = [call for call in calls if "Ingresá un número válido" in str(call)]
            assert len(error_messages) == 3  # 3 intentos fallidos


class TestSeleccionarHoja:
    """Tests para función seleccionar_hoja (estrategia doble fallback)"""
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    def test_exitoso_con_hojas_visibles(self, mock_seleccionar_visible):
        """Test exitoso usando hojas visibles"""
        mock_seleccionar_visible.return_value = "Datos"
        
        resultado = seleccionar_hoja("test.xlsx")
        
        assert resultado == "Datos"
        mock_seleccionar_visible.assert_called_once_with("test.xlsx")
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    @patch('tz_core.data_loader.listar_todas_hojas')
    def test_fallback_a_todas_las_hojas_sin_hojas(self, mock_listar_todas, mock_seleccionar_visible):
        """Test fallback cuando no hay hojas disponibles"""
        mock_seleccionar_visible.return_value = None
        mock_listar_todas.return_value = None
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja("test.xlsx")
            
            assert resultado is None
            mock_print.assert_called_with("No se pudo listar hojas; se usará la primera hoja por defecto.")
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    @patch('tz_core.data_loader.listar_todas_hojas')
    def test_fallback_una_sola_hoja_todas(self, mock_listar_todas, mock_seleccionar_visible):
        """Test fallback con una sola hoja en listado completo"""
        mock_seleccionar_visible.return_value = None
        mock_listar_todas.return_value = ["Datos"]
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja("test.xlsx")
            
            assert resultado == "Datos"
            mock_print.assert_called_with("Hoja detectada (todas): Datos")
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    @patch('tz_core.data_loader.listar_todas_hojas')
    @patch('tz_core.data_loader.safe_input')
    def test_fallback_seleccion_interactiva_enter(self, mock_input, mock_listar_todas, mock_seleccionar_visible):
        """Test fallback con selección interactiva - Enter (primera hoja)"""
        mock_seleccionar_visible.return_value = None
        mock_listar_todas.return_value = ["Datos", "Resumen"]
        mock_input.return_value = ""  # Enter
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja("test.xlsx")
            
            assert resultado == "Datos"
            calls = mock_print.call_args_list
            assert any("Hojas detectadas (todas):" in str(call) for call in calls)
            assert any("Hoja seleccionada: Datos" in str(call) for call in calls)
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    @patch('tz_core.data_loader.listar_todas_hojas')
    @patch('tz_core.data_loader.safe_input')
    def test_fallback_seleccion_interactiva_numero(self, mock_input, mock_listar_todas, mock_seleccionar_visible):
        """Test fallback con selección interactiva - número específico"""
        mock_seleccionar_visible.return_value = None
        mock_listar_todas.return_value = ["Datos", "Resumen", "Config"]
        mock_input.return_value = "3"
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja("test.xlsx")
            
            assert resultado == "Config"
            assert any("Hoja seleccionada: Config" in str(call) for call in mock_print.call_args_list)
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    @patch('tz_core.data_loader.listar_todas_hojas')
    @patch('tz_core.data_loader.safe_input')
    def test_fallback_inputs_invalidos_luego_valido(self, mock_input, mock_listar_todas, mock_seleccionar_visible):
        """Test fallback con inputs inválidos luego válido"""
        mock_seleccionar_visible.return_value = None
        mock_listar_todas.return_value = ["Datos", "Resumen"]
        mock_input.side_effect = ["abc", "0", "3", "2"]  # Inválidos, luego válido
        
        with patch('builtins.print') as mock_print:
            resultado = seleccionar_hoja("test.xlsx")
            
            assert resultado == "Resumen"
            # Debe haber mostrado mensajes de error
            calls = mock_print.call_args_list
            error_messages = [call for call in calls if "Número inválido" in str(call)]
            assert len(error_messages) == 3
    
    @patch('tz_core.data_loader.seleccionar_hoja_visible')
    def test_excepcion_en_seleccionar_visible(self, mock_seleccionar_visible):
        """Test manejo de excepción en seleccionar_hoja_visible"""
        mock_seleccionar_visible.side_effect = Exception("Error simulado")
        
        with patch('tz_core.data_loader.listar_todas_hojas') as mock_listar_todas:
            mock_listar_todas.return_value = ["Datos"]
            
            with patch('builtins.print') as mock_print:
                resultado = seleccionar_hoja("test.xlsx")
                
                assert resultado == "Datos"
                mock_print.assert_called_with("Hoja detectada (todas): Datos")


class TestCargarExcelConNormalizacion:
    """
    Tests para función cargar_excel_con_normalizacion - FASE 5.3a
    
    🚨 ARQUITECTURA CRÍTICA - SISTEMA DUAL DE COLUMNAS 🚨
    
    Estos tests validan el comportamiento del sistema dual de columnas
    descubierto durante la refactorización:
    
    - df.attrs["orig_cols"]: Columnas exactas del archivo (para UI)  
    - df.columns: Columnas normalizadas (para algoritmo)
    
    ⚠️ ADVERTENCIA: Estos tests documentan comportamiento intencional,
    NO un bug. Cualquier "optimización" que elimine la dualidad
    ROMPERÁ la funcionalidad del sistema.
    
    Los tests verifican:
    1. Preservación de nombres originales en attrs
    2. Normalización correcta de headers
    3. Consistencia entre ambos sistemas
    4. Integridad de datos tras el proceso
    """
    
    def test_carga_exitosa_con_sistema_dual(self):
        """Test carga exitosa preservando sistema dual de columnas"""
        # Crear archivo Excel temporal de prueba
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            df_test = pd.DataFrame({
                'Columna 1  ': [1, 2, 3],
                '  Columna 2': [4, 5, 6],
                'Columna 3': [7, 8, 9]
            })
            df_test.to_excel(tmp.name, index=False)
            tmp_path = tmp.name
        
        try:
            from tz_core.data_loader import cargar_excel_con_normalizacion
            df_resultado, hoja_usada = cargar_excel_con_normalizacion(tmp_path)
            
            # Verificar sistema dual de columnas
            assert "orig_cols" in df_resultado.attrs
            assert df_resultado.attrs["orig_cols"] == ['Columna 1  ', '  Columna 2', 'Columna 3']
            
            # Verificar normalización de headers
            assert list(df_resultado.columns) == ['Columna 1', 'Columna 2', 'Columna 3']
            
            # Verificar datos preservados
            assert len(df_resultado) == 3
            assert df_resultado.iloc[0, 0] == 1
            
            # Verificar hoja usada
            assert hoja_usada == "primera_hoja"
            
        finally:
            os.unlink(tmp_path)
    
    def test_carga_con_hoja_especifica(self):
        """Test carga con hoja específica"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            with pd.ExcelWriter(tmp.name) as writer:
                pd.DataFrame({'Col1': [1, 2]}).to_excel(writer, sheet_name='Hoja1', index=False)
                pd.DataFrame({'Col2': [3, 4]}).to_excel(writer, sheet_name='Hoja2', index=False)
            tmp_path = tmp.name
        
        try:
            from tz_core.data_loader import cargar_excel_con_normalizacion
            df_resultado, hoja_usada = cargar_excel_con_normalizacion(tmp_path, 'Hoja2')
            
            assert hoja_usada == 'Hoja2'
            assert 'Col2' in df_resultado.columns
            assert df_resultado.attrs["orig_cols"] == ['Col2']
            
        finally:
            os.unlink(tmp_path)
    
    def test_error_archivo_inexistente(self):
        """Test error con archivo inexistente"""
        from tz_core.data_loader import cargar_excel_con_normalizacion
        
        with pytest.raises(ValueError, match="Error cargando Excel"):
            cargar_excel_con_normalizacion("archivo_inexistente.xlsx")
    
    def test_preservacion_tipos_originales(self):
        """Test preservación de tipos de datos originales"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            df_test = pd.DataFrame({
                'Enteros': [1, 2, 3],
                'Flotantes': [1.1, 2.2, 3.3],
                'Texto': ['A', 'B', 'C']
            })
            df_test.to_excel(tmp.name, index=False)
            tmp_path = tmp.name
        
        try:
            from tz_core.data_loader import cargar_excel_con_normalizacion
            df_resultado, _ = cargar_excel_con_normalizacion(tmp_path)
            
            # Verificar tipos preservados
            assert df_resultado['Enteros'].dtype == 'int64'
            assert df_resultado['Flotantes'].dtype == 'float64'
            assert df_resultado['Texto'].dtype == 'object'
            
            # Verificar sistema dual intacto
            assert df_resultado.attrs["orig_cols"] == ['Enteros', 'Flotantes', 'Texto']
            
        finally:
            os.unlink(tmp_path)
