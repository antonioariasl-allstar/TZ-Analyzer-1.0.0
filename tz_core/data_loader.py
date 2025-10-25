"""
tz_core.data_loader - Carga y manejo de archivos de datos

Módulo especializado en la carga de archivos Excel, CSV y TSV con manejo
inteligente de hojas de cálculo, detección de encoding y validaciones.

🚨 ESTADO: FASE 5.1 - Extracción de funciones puras de manejo de hojas
Minas detectadas: Dependencia opcional openpyxl, funciones interactivas

Funciones extraídas:
- obtener_hojas_visibles(): Detección de hojas visibles vs ocultas en Excel
- listar_todas_hojas(): Listado completo de hojas usando pandas
"""

import pandas as pd
from typing import List, Tuple, Optional

# Importación condicional de openpyxl para detección de hojas ocultas
try:
    import openpyxl
except ImportError:
    openpyxl = None


def obtener_hojas_visibles(ruta_excel: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Obtiene lista de hojas visibles en un archivo Excel usando openpyxl.
    
    Args:
        ruta_excel: Ruta al archivo Excel
        
    Returns:
        Tuple con (lista_hojas_visibles, error_code)
        - Si éxito: (["Hoja1", "Hoja2"], None)
        - Si no openpyxl: (None, "NO_OPENPYXL")
        - Si error carga: (None, "LOAD_FAIL")
    """
    if openpyxl is None:
        return None, "NO_OPENPYXL"
    
    try:
        wb = openpyxl.load_workbook(ruta_excel, read_only=True, data_only=True)
        visibles = [
            ws.title for ws in wb.worksheets 
            if getattr(ws, "sheet_state", "visible") == "visible"
        ]
        wb.close()
        return visibles, None
    except Exception:
        return None, "LOAD_FAIL"


def listar_todas_hojas(ruta_excel: str) -> Optional[List[str]]:
    """
    Lista todas las hojas de un archivo Excel usando pandas.
    
    Args:
        ruta_excel: Ruta al archivo Excel
        
    Returns:
        Lista de nombres de hojas o None si hay error
    """
    try:
        xls = pd.ExcelFile(ruta_excel)
        return list(xls.sheet_names)
    except Exception:
        return None