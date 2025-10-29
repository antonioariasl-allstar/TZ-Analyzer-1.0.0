"""
tz_cli.validators.file_validators - VALIDADORES ARCHIVOS CLI
===========================================================

✅ ESTADO: SPRINT 3 - VALIDADORES MODULARES
🎯 PROPÓSITO: Validación especializada archivos entrada y batch
📍 DIFERENCIACIÓN: Validadores específicos CLI vs validaciones generales

RESPONSABILIDADES ESPECÍFICAS:
- Validación archivos Excel/TSV/CSV antes de procesamiento
- Validación archivos batch para modo manual
- Detección estructura y problemas comunes
- Reportes validación user-friendly para CLI

TIPOS VALIDACIÓN:
- validate_input_file(): Bitácoras principales
- validate_batch_file(): Archivos batch modo manual
- validate_structure(): Estructura columnas requeridas
- validate_data_types(): Tipos de datos y rangos

INTEGRACIÓN:
- Comando 'tzanalysis validate' 
- Pre-validación en comandos process/run
- Validación batch en comando manual
- Error reporting contextual

FECHA CREACIÓN: 29 octubre 2025 - Sprint 3 Fase 3.2
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import json
import csv

def validate_input_file(file_path: str, sheet: Optional[str] = None, 
                       detailed: bool = False) -> Dict[str, Any]:
    """
    Valida archivo de entrada principal (bitácora)
    
    Verifica estructura, columnas, tipos de datos y detecta
    problemas comunes antes del procesamiento.
    
    Args:
        file_path: Path al archivo a validar
        sheet: Hoja específica (para Excel)
        detailed: Incluir análisis detallado
        
    Returns:
        Dict con resultado validación
    """
    result = {
        'file': file_path,
        'status': 'unknown',
        'errors': [],
        'warnings': [],
        'info': {}
    }
    
    try:
        file_obj = Path(file_path)
        
        # Validaciones básicas
        if not file_obj.exists():
            result['errors'].append("Archivo no encontrado")
            result['status'] = 'invalid'
            return result
        
        if not file_obj.is_file():
            result['errors'].append("Path no es un archivo")
            result['status'] = 'invalid'
            return result
        
        # Información básica
        result['info']['size'] = file_obj.stat().st_size
        result['info']['extension'] = file_obj.suffix.lower()
        
        # Validar por tipo
        if result['info']['extension'] in ['.xlsx', '.xls']:
            _validate_excel_file(file_obj, sheet, detailed, result)
        elif result['info']['extension'] in ['.tsv', '.csv']:
            _validate_text_file(file_obj, detailed, result)
        else:
            result['warnings'].append(f"Tipo archivo no estándar: {result['info']['extension']}")
        
        # Determinar status final
        if result['errors']:
            result['status'] = 'invalid'
        elif result['warnings']:
            result['status'] = 'valid_with_warnings'
        else:
            result['status'] = 'valid'
            
    except Exception as e:
        result['errors'].append(f"Error general: {e}")
        result['status'] = 'error'
    
    return result

def validate_batch_file(file_path: str) -> Dict[str, Any]:
    """
    Valida archivo batch para modo manual
    
    Verifica formato JSON/CSV y estructura de registros
    para entrada manual de antenas.
    
    Args:
        file_path: Path al archivo batch
        
    Returns:
        Dict con resultado validación
    """
    result = {
        'file': file_path,
        'status': 'unknown',
        'errors': [],
        'warnings': [],
        'records': 0,
        'format': 'unknown'
    }
    
    try:
        file_obj = Path(file_path)
        
        if not file_obj.exists():
            result['errors'].append("Archivo batch no encontrado")
            result['status'] = 'invalid'
            return result
        
        # Detectar formato
        extension = file_obj.suffix.lower()
        
        if extension == '.json':
            result['format'] = 'json'
            _validate_json_batch(file_obj, result)
        elif extension in ['.csv', '.tsv']:
            result['format'] = 'csv'
            _validate_csv_batch(file_obj, result)
        else:
            result['errors'].append(f"Formato batch no soportado: {extension}")
            result['status'] = 'invalid'
            return result
        
        # Status final
        if result['errors']:
            result['status'] = 'invalid'
        elif result['warnings']:
            result['status'] = 'valid_with_warnings'
        else:
            result['status'] = 'valid'
            
    except Exception as e:
        result['errors'].append(f"Error validando batch: {e}")
        result['status'] = 'error'
    
    return result

def _validate_excel_file(file_obj: Path, sheet: Optional[str], detailed: bool, result: Dict):
    """Validación específica archivos Excel"""
    try:
        # Detectar hojas
        xlsx_file = pd.ExcelFile(str(file_obj))
        result['info']['sheets'] = xlsx_file.sheet_names
        result['info']['sheet_count'] = len(xlsx_file.sheet_names)
        
        # Seleccionar hoja a validar
        sheet_to_validate = sheet if sheet else 0
        
        if isinstance(sheet_to_validate, str) and sheet_to_validate not in xlsx_file.sheet_names:
            result['errors'].append(f"Hoja '{sheet_to_validate}' no encontrada")
            return
        
        # Cargar muestra para análisis
        df_sample = pd.read_excel(str(file_obj), sheet_name=sheet_to_validate, nrows=10)
        result['info']['columns'] = list(df_sample.columns)
        result['info']['column_count'] = len(df_sample.columns)
        
        # Contar filas totales
        df_full = pd.read_excel(str(file_obj), sheet_name=sheet_to_validate)
        result['info']['rows'] = len(df_full)
        
        if result['info']['rows'] == 0:
            result['errors'].append("Archivo vacío (0 filas de datos)")
            return
        
        # Validaciones estructura
        _validate_column_structure(df_sample, result)
        
        if detailed:
            _detailed_data_analysis(df_full, result)
            
    except Exception as e:
        result['errors'].append(f"Error procesando Excel: {e}")

def _validate_text_file(file_obj: Path, detailed: bool, result: Dict):
    """Validación específica archivos CSV/TSV"""
    try:
        # Detectar delimitador
        delimiter = '\t' if file_obj.suffix.lower() == '.tsv' else ','
        
        # Cargar muestra
        df_sample = pd.read_csv(str(file_obj), delimiter=delimiter, nrows=10)
        result['info']['columns'] = list(df_sample.columns)
        result['info']['column_count'] = len(df_sample.columns)
        
        # Contar filas
        with open(str(file_obj), 'r', encoding='utf-8') as f:
            result['info']['rows'] = sum(1 for _ in f) - 1  # -1 header
        
        if result['info']['rows'] == 0:
            result['errors'].append("Archivo vacío (0 filas de datos)")
            return
        
        # Validaciones estructura
        _validate_column_structure(df_sample, result)
        
        if detailed:
            df_full = pd.read_csv(str(file_obj), delimiter=delimiter)
            _detailed_data_analysis(df_full, result)
            
    except Exception as e:
        result['errors'].append(f"Error procesando CSV/TSV: {e}")

def _validate_column_structure(df: pd.DataFrame, result: Dict):
    """Valida estructura básica de columnas"""
    
    # Columnas esperadas (flexible)
    expected_patterns = [
        ['tel', 'telefono', 'phone'],
        ['lat', 'latitud', 'latitude'],
        ['lon', 'long', 'longitud', 'longitude'],
        ['antena', 'antenna', 'cell'],
        ['fecha', 'date', 'timestamp']
    ]
    
    columns_lower = [col.lower() for col in df.columns]
    
    # Verificar patrones comunes
    found_patterns = 0
    for pattern in expected_patterns:
        if any(p in columns_lower for p in pattern):
            found_patterns += 1
    
    if found_patterns < 3:
        result['warnings'].append("Estructura de columnas no estándar - verificar mapeo")
    
    # Columnas duplicadas
    if len(df.columns) != len(set(df.columns)):
        result['errors'].append("Columnas duplicadas detectadas")
    
    # Columnas vacías
    empty_cols = [col for col in df.columns if df[col].isna().all()]
    if empty_cols:
        result['warnings'].append(f"Columnas completamente vacías: {empty_cols}")

def _detailed_data_analysis(df: pd.DataFrame, result: Dict):
    """Análisis detallado de datos"""
    
    analysis = {
        'null_percentages': {},
        'data_types': {},
        'unique_counts': {},
        'potential_issues': []
    }
    
    for col in df.columns:
        # Porcentajes nulos
        null_pct = (df[col].isna().sum() / len(df)) * 100
        analysis['null_percentages'][col] = round(null_pct, 2)
        
        # Tipos de datos detectados
        analysis['data_types'][col] = str(df[col].dtype)
        
        # Conteos únicos
        analysis['unique_counts'][col] = df[col].nunique()
        
        # Detectar problemas potenciales
        if null_pct > 50:
            analysis['potential_issues'].append(f"Columna '{col}': >50% valores nulos")
        
        if analysis['unique_counts'][col] == 1:
            analysis['potential_issues'].append(f"Columna '{col}': valor único (posible constante)")
    
    result['info']['detailed_analysis'] = analysis

def _validate_json_batch(file_obj: Path, result: Dict):
    """Validación específica archivos batch JSON"""
    try:
        with open(str(file_obj), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Estructura esperada
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and 'registros' in data:
            records = data['registros']
        else:
            result['errors'].append("Estructura JSON inválida - esperado lista o {registros: [...]}")
            return
        
        result['records'] = len(records)
        
        if result['records'] == 0:
            result['warnings'].append("Archivo batch vacío")
            return
        
        # Validar registros
        _validate_batch_records(records, result)
        
    except json.JSONDecodeError as e:
        result['errors'].append(f"JSON inválido: {e}")
    except Exception as e:
        result['errors'].append(f"Error procesando JSON: {e}")

def _validate_csv_batch(file_obj: Path, result: Dict):
    """Validación específica archivos batch CSV"""
    try:
        delimiter = '\t' if file_obj.suffix.lower() == '.tsv' else ','
        
        records = []
        with open(str(file_obj), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                records.append(row)
        
        result['records'] = len(records)
        
        if result['records'] == 0:
            result['warnings'].append("Archivo batch vacío")
            return
        
        # Validar registros
        _validate_batch_records(records, result)
        
    except Exception as e:
        result['errors'].append(f"Error procesando CSV: {e}")

def _validate_batch_records(records: List[Dict], result: Dict):
    """Valida registros individuales de batch"""
    
    errors = []
    
    for i, record in enumerate(records[:10]):  # Validar primeros 10
        # Campos requeridos
        if 'antena' not in record or not record['antena']:
            errors.append(f"Registro {i+1}: Campo 'antena' requerido")
        
        # Coordenadas
        if 'lat' not in record:
            errors.append(f"Registro {i+1}: Campo 'lat' requerido")
        else:
            try:
                lat = float(record['lat'])
                if not (-90 <= lat <= 90):
                    errors.append(f"Registro {i+1}: Latitud fuera de rango: {lat}")
            except (ValueError, TypeError):
                errors.append(f"Registro {i+1}: Latitud inválida: {record['lat']}")
        
        lon_key = 'lon' if 'lon' in record else 'long'
        if lon_key not in record:
            errors.append(f"Registro {i+1}: Campo 'lon' o 'long' requerido")
        else:
            try:
                lon = float(record[lon_key])
                if not (-180 <= lon <= 180):
                    errors.append(f"Registro {i+1}: Longitud fuera de rango: {lon}")
            except (ValueError, TypeError):
                errors.append(f"Registro {i+1}: Longitud inválida: {record[lon_key]}")
    
    # Agregar errores encontrados
    result['errors'].extend(errors[:5])  # Máximo 5 errores
    
    if len(errors) > 5:
        result['warnings'].append(f"Encontrados {len(errors)-5} errores adicionales")