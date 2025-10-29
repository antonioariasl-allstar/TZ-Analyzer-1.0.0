"""
tz_cli.handlers.file_handler - MANEJADOR DE ARCHIVOS CLI
=======================================================

✅ ESTADO: SPRINT 3 - HANDLERS MODULARES
🎯 PROPÓSITO: Centralizar lógica selección y validación archivos
📍 DIFERENCIACIÓN: Abstrae file I/O del script principal para CLI

RESPONSABILIDADES ESPECÍFICAS:
- Override seleccionar_archivo() con argumentos CLI
- Validación archivos entrada (Excel, TSV, CSV)
- Detección automática formato y estructura
- Bridge entre CLI args y funciones originales

FUNCIONES ORIGINALES:
- seleccionar_archivo() de utilidades.py
- _seleccionar_hoja_visible() de script principal
- Validaciones formato en main()

INTEGRACIÓN CLI:
- --file FILE: Override selección interactiva
- --sheet NAME|NUMBER: Override selección hoja
- Validación previa a procesamiento
- Error handling user-friendly

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3 Fase 3.2
"""

import os
from pathlib import Path
from typing import Optional, Union, Tuple, Dict, Any
import pandas as pd

class FileHandler:
    """
    Handler centralizado para operaciones de archivos en CLI
    
    Abstrae la selección y validación de archivos de entrada,
    proporcionando overrides para argumentos CLI vs selección interactiva.
    """
    
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
    
    def get_input_file(self, cli_file: Optional[str] = None) -> Optional[str]:
        """
        Obtiene archivo de entrada: CLI arg o selección interactiva
        
        Args:
            cli_file: Archivo especificado en CLI (override)
            
        Returns:
            Path al archivo seleccionado o None si cancelado
        """
        if cli_file:
            # Validar archivo CLI
            file_path = Path(cli_file)
            if not file_path.exists():
                raise FileNotFoundError(f"Archivo no encontrado: {cli_file}")
            if not file_path.is_file():
                raise ValueError(f"Path no es archivo: {cli_file}")
            
            if not self.quiet:
                print(f"📁 Usando archivo CLI: {file_path.name}")
            
            return str(file_path.absolute())
        
        else:
            # Selección interactiva usando función original
            from utilidades import seleccionar_archivo
            
            if not self.quiet:
                print("📁 Seleccione archivo de entrada...")
            
            return seleccionar_archivo()
    
    def get_sheet_selection(self, file_path: str, cli_sheet: Optional[str] = None) -> Union[str, int, None]:
        """
        Obtiene selección de hoja Excel: CLI arg o selección interactiva
        
        Args:
            file_path: Path al archivo Excel
            cli_sheet: Hoja especificada en CLI (nombre o número)
            
        Returns:
            Hoja seleccionada (str nombre o int índice) o None para primera
        """
        if cli_sheet:
            # Validar hoja CLI
            if cli_sheet.isdigit():
                sheet_index = int(cli_sheet)
                # TODO: Validar que índice existe en archivo
                if not self.quiet:
                    print(f"📊 Usando hoja CLI: índice {sheet_index}")
                return sheet_index
            else:
                # TODO: Validar que nombre existe en archivo
                if not self.quiet:
                    print(f"📊 Usando hoja CLI: '{cli_sheet}'")
                return cli_sheet
        
        else:
            # Selección interactiva usando función original
            from script_principal_bitacoras_refactory import _seleccionar_hoja_visible
            
            if not self.quiet:
                print("📊 Seleccionando hoja Excel...")
            
            return _seleccionar_hoja_visible(file_path)
    
    def validate_input_file(self, file_path: str) -> Dict[str, Any]:
        """
        Valida archivo de entrada y retorna información estructura
        
        Args:
            file_path: Path al archivo a validar
            
        Returns:
            Dict con información validación (filas, columnas, hojas, errores)
        """
        file_path_obj = Path(file_path)
        result = {
            'file': str(file_path_obj.absolute()),
            'name': file_path_obj.name,
            'extension': file_path_obj.suffix.lower(),
            'size': file_path_obj.stat().st_size,
            'status': 'unknown',
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validar extensión
            valid_extensions = ['.xlsx', '.xls', '.tsv', '.csv']
            if result['extension'] not in valid_extensions:
                result['warnings'].append(f"Extensión no estándar: {result['extension']}")
            
            # Intentar cargar y analizar estructura
            if result['extension'] in ['.xlsx', '.xls']:
                # Excel file
                try:
                    # Detectar hojas disponibles
                    xlsx_file = pd.ExcelFile(file_path)
                    result['sheets'] = xlsx_file.sheet_names
                    result['sheet_count'] = len(xlsx_file.sheet_names)
                    
                    # Analizar primera hoja
                    df = pd.read_excel(file_path, sheet_name=0, nrows=5)  # Solo primeras 5 filas
                    result['columns'] = list(df.columns)
                    result['column_count'] = len(df.columns)
                    
                    # Estimar filas totales (más eficiente que cargar todo)
                    df_full = pd.read_excel(file_path, sheet_name=0)
                    result['rows'] = len(df_full)
                    
                except Exception as e:
                    result['errors'].append(f"Error leyendo Excel: {e}")
                    
            elif result['extension'] in ['.tsv', '.csv']:
                # Texto delimitado
                try:
                    delimiter = '\t' if result['extension'] == '.tsv' else ','
                    
                    # Analizar estructura
                    df = pd.read_csv(file_path, delimiter=delimiter, nrows=5)
                    result['columns'] = list(df.columns)
                    result['column_count'] = len(df.columns)
                    
                    # Contar filas (más eficiente)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        result['rows'] = sum(1 for _ in f) - 1  # -1 para header
                        
                except Exception as e:
                    result['errors'].append(f"Error leyendo CSV/TSV: {e}")
            
            # Determinar status final
            if result['errors']:
                result['status'] = 'invalid'
            elif result['warnings']:
                result['status'] = 'valid_with_warnings'
            else:
                result['status'] = 'valid'
                
        except Exception as e:
            result['errors'].append(f"Error general validación: {e}")
            result['status'] = 'invalid'
        
        return result
    
    def get_output_directory(self, cli_output_dir: Optional[str] = None) -> str:
        """
        Obtiene directorio salida: CLI arg o selección interactiva
        
        Args:
            cli_output_dir: Directorio especificado en CLI
            
        Returns:
            Path al directorio de salida
        """
        if cli_output_dir:
            # Validar y crear directorio CLI
            output_path = Path(cli_output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            if not self.quiet:
                print(f"📂 Usando directorio CLI: {output_path.name}")
            
            return str(output_path.absolute())
        
        else:
            # Selección interactiva usando función original
            from utilidades import seleccionar_carpeta
            
            if not self.quiet:
                print("📂 Seleccione directorio de salida...")
            
            selected = seleccionar_carpeta()
            return selected if selected else os.getcwd()

def create_file_handler(quiet: bool = False) -> FileHandler:
    """Factory para crear FileHandler con configuración"""
    return FileHandler(quiet=quiet)