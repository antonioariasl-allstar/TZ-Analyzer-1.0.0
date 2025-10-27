"""
Tests exhaustivos para tz_core.dataframe_utils

Valida el correcto funcionamiento de deduplicación de columnas DataFrame
con casos edge, errores, y validación de inmutabilidad.
"""

import pytest
import pandas as pd
import numpy as np

from tz_core.dataframe_utils import dedupe_columns


class TestDedupeColumns:
    """Tests exhaustivos para la función dedupe_columns."""
    
    def test_sin_duplicados(self):
        """Debe retornar copia sin modificaciones cuando no hay duplicados."""
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [4, 5, 6],
            'C': ['x', 'y', 'z']
        })
        
        result = dedupe_columns(df)
        
        # Verificar que resultado es correcto
        pd.testing.assert_frame_equal(result, df)
        
        # Verificar inmutabilidad (diferentes objetos)
        assert result is not df
        assert id(result) != id(df)
    
    def test_duplicados_simples(self):
        """Debe consolidar columnas duplicadas correctamente."""
        # Crear DataFrame con columnas duplicadas manualmente
        df = pd.DataFrame([[1, None, 4], [None, 2, 5], [3, None, 6]])
        df.columns = ['A', 'A', 'B']  # Forzar duplicados
        
        result = dedupe_columns(df)
        
        # Verificar estructura
        assert list(result.columns) == ['A', 'B']
        assert len(result.columns) == 2
        
        # Verificar consolidación correcta
        expected_a = [1, 2, 3]  # Primer no-vacío de cada fila
        assert result['A'].tolist() == expected_a
        assert result['B'].tolist() == [4, 5, 6]
    
    def test_multiples_duplicados(self):
        """Debe manejar múltiples grupos de columnas duplicadas."""
        # DataFrame con dos grupos de duplicados
        df = pd.DataFrame([
            [1, None, 'x', None, 10],
            [None, 2, None, 'y', 20], 
            [3, None, 'z', None, 30]
        ])
        df.columns = ['A', 'A', 'B', 'B', 'C']
        
        result = dedupe_columns(df)
        
        # Verificar estructura final
        assert list(result.columns) == ['A', 'B', 'C']
        assert len(result.columns) == 3
        
        # Verificar consolidación de ambos grupos
        assert result['A'].tolist() == [1, 2, 3]
        assert result['B'].tolist() == ['x', 'y', 'z']
        assert result['C'].tolist() == [10, 20, 30]
    
    def test_strings_vacios(self):
        """Debe tratar strings vacíos y en blanco como valores vacíos."""
        df = pd.DataFrame([
            ['', 'valor1'],
            ['  ', 'valor2'],  # Solo espacios
            ['real', ''],
            [None, 'valor3']
        ])
        df.columns = ['col', 'col']
        
        result = dedupe_columns(df)
        
        expected = ['valor1', 'valor2', 'real', 'valor3']
        assert result['col'].tolist() == expected
    
    def test_tipos_mixtos(self):
        """Debe preservar tipos de datos apropiadamente."""
        df = pd.DataFrame([
            [1, None],      # int + NaN
            [None, 2.5],    # NaN + float  
            [3, None],      # int + NaN
            [None, 'text']  # NaN + string
        ])
        df.columns = ['mixed', 'mixed']
        
        result = dedupe_columns(df)
        
        # Verificar consolidación correcta
        expected = [1.0, 2.5, 3.0, 'text']  # pandas puede convertir a object
        assert result['mixed'].tolist() == expected
    
    def test_dataframe_vacio(self):
        """Debe manejar DataFrame vacío correctamente."""
        df = pd.DataFrame()
        
        result = dedupe_columns(df)
        
        assert len(result) == 0
        assert len(result.columns) == 0
        assert result is not df  # Inmutabilidad
    
    def test_sin_filas(self):
        """Debe manejar DataFrame con columnas pero sin filas."""
        df = pd.DataFrame(columns=['A', 'A', 'B'])
        
        result = dedupe_columns(df)
        
        assert list(result.columns) == ['A', 'B']
        assert len(result) == 0
    
    def test_todos_nan(self):
        """Debe manejar columnas con todos valores NaN."""
        df = pd.DataFrame([
            [np.nan, np.nan],
            [np.nan, np.nan]
        ])
        df.columns = ['all_nan', 'all_nan']
        
        result = dedupe_columns(df)
        
        assert list(result.columns) == ['all_nan']
        assert result['all_nan'].isna().all()
    
    def test_inmutabilidad_original(self):
        """Debe preservar DataFrame original sin modificaciones."""
        original_data = {'A': [1, 2], 'A': [3, 4], 'B': [5, 6]}
        df = pd.DataFrame([[1, 3, 5], [2, 4, 6]])
        df.columns = ['A', 'A', 'B']
        
        # Backup para verificar inmutabilidad
        original_shape = df.shape
        original_columns = list(df.columns)
        
        result = dedupe_columns(df)
        
        # Original debe estar intacto
        assert df.shape == original_shape
        assert list(df.columns) == original_columns
        
        # Resultado debe ser diferente
        assert result.shape != df.shape
        assert list(result.columns) != list(df.columns)


class TestCasosEdge:
    """Tests para casos edge y manejo de errores."""
    
    def test_input_none(self):
        """Debe retornar None para input None."""
        result = dedupe_columns(None)
        assert result is None
    
    def test_input_no_dataframe(self):
        """Debe lanzar TypeError para input no-DataFrame."""
        with pytest.raises(TypeError, match="Input debe ser un pandas DataFrame"):
            dedupe_columns([1, 2, 3])
        
        with pytest.raises(TypeError, match="Input debe ser un pandas DataFrame"):
            dedupe_columns("not a dataframe")
    
    def test_una_sola_fila(self):
        """Debe manejar DataFrames con una sola fila."""
        df = pd.DataFrame([[1, None, 3]])
        df.columns = ['A', 'A', 'B']
        
        result = dedupe_columns(df)
        
        assert list(result.columns) == ['A', 'B']
        assert result.iloc[0]['A'] == 1
        assert result.iloc[0]['B'] == 3
    
    def test_columnas_con_caracteres_especiales(self):
        """Debe manejar nombres de columnas con caracteres especiales."""
        df = pd.DataFrame([[1, 2], [3, 4]])
        df.columns = ['col con espacios', 'col con espacios']
        
        result = dedupe_columns(df)
        
        assert list(result.columns) == ['col con espacios']
        assert result['col con espacios'].tolist() == [1, 3]


class TestCompatibilidad:
    """Tests de compatibilidad con alias."""
    
    def test_alias_existe(self):
        """El alias _dedupe_columns debe existir."""
        from tz_core.dataframe_utils import _dedupe_columns
        
        # Debe ser la misma función
        assert _dedupe_columns is dedupe_columns
    
    def test_alias_funciona(self):
        """El alias debe funcionar igual que la función principal."""
        from tz_core.dataframe_utils import _dedupe_columns
        
        df = pd.DataFrame([[1, None], [None, 2]])
        df.columns = ['test', 'test']
        
        result1 = dedupe_columns(df)
        result2 = _dedupe_columns(df)
        
        pd.testing.assert_frame_equal(result1, result2)


class TestIntegracion:
    """Tests de integración con casos reales."""
    
    def test_caso_real_excel_headers(self):
        """Simula caso real de headers duplicados de Excel."""
        # Simular carga Excel con headers problemáticos
        df = pd.DataFrame([
            ['2020-01-01', '', '12:00'],
            ['2020-01-02', '2020-01-02', ''],
            ['', '2020-01-03', '14:00']
        ])
        df.columns = ['fecha', 'fecha', 'hora']  # Headers duplicados típicos
        
        result = dedupe_columns(df)
        
        assert list(result.columns) == ['fecha', 'hora']
        
        # Verificar consolidación inteligente
        expected_fechas = ['2020-01-01', '2020-01-02', '2020-01-03']
        assert result['fecha'].tolist() == expected_fechas
    
    def test_performance_dataframe_grande(self):
        """Verificar que funciona con DataFrames más grandes."""
        # Crear DataFrame "grande" para test de performance
        import time
        
        data = []
        for i in range(1000):
            data.append([i, None, i*2, None, f"row_{i}"])
        
        df = pd.DataFrame(data)
        df.columns = ['A', 'A', 'B', 'B', 'C']
        
        start_time = time.time()
        result = dedupe_columns(df)
        end_time = time.time()
        
        # Verificar resultado correcto
        assert list(result.columns) == ['A', 'B', 'C']
        assert len(result) == 1000
        
        # Performance básica (no debe tardar más de 1 segundo)
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Función tardó {execution_time:.2f}s - demasiado lenta"