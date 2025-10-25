"""
tz_core.data_loader - Carga y manejo de archivos de datos

Módulo especializado en la carga de archivos Excel, CSV y TSV con manejo
inteligente de hojas de cálculo, detección de encoding y validaciones.

🚨 ESTADO: FASE 5.2 - Extracción de funciones interactivas de selección de hojas
Minas detectadas: Funciones con input() requieren mocking para tests

Funciones extraídas:
- obtener_hojas_visibles(): Detección de hojas visibles vs ocultas en Excel
- listar_todas_hojas(): Listado completo de hojas usando pandas
- seleccionar_hoja_visible(): Selección interactiva de hojas visibles 
- seleccionar_hoja(): Selección maestra con doble estrategia (visibles/todas)
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


def seleccionar_hoja_visible(ruta_excel: str) -> Optional[str]:
    """
    Selecciona una hoja de entre las hojas visibles del Excel.
    
    Si no hay openpyxl disponible o hay errores, retorna None.
    Si hay una sola hoja visible, la retorna automáticamente.
    Si hay múltiples hojas visibles, solicita selección interactiva.
    
    Args:
        ruta_excel: Ruta al archivo Excel
        
    Returns:
        Nombre de la hoja seleccionada o None si hay problemas
    """
    visibles, err = obtener_hojas_visibles(ruta_excel)
    
    if err == "NO_OPENPYXL":
        print("Aviso: 'openpyxl' no disponible; se usará la primera hoja por defecto.")
        return None
    if err == "LOAD_FAIL":
        print("Aviso: no se pudo inspeccionar hojas; se usará la primera hoja por defecto.")
        return None
    if not visibles:
        print("No hay hojas visibles; se usará la primera hoja por defecto.")
        return None
    if len(visibles) == 1:
        print(f"Hoja visible detectada: {visibles[0]}")
        return visibles[0]

    print("Hojas visibles detectadas:")
    for i, name in enumerate(visibles, 1):
        print(f"  [{i}] {name}")
    
    while True:
        resp = input("Elegí el número de la hoja a procesar (Enter = 1): ").strip()
        idx = 1 if resp == "" else int(resp) if resp.isdigit() else None
        if idx and 1 <= idx <= len(visibles):
            elegido = visibles[idx - 1]
            print(f"Hoja seleccionada: {elegido}")
            return elegido
        print("Ingresá un número válido (1..N).")


def seleccionar_hoja(ruta_excel: str) -> Optional[str]:
    """
    Selecciona una hoja Excel usando estrategia de doble fallback.
    
    1) Intenta primero con hojas VISIBLES (openpyxl)
    2) Si falla, usa TODAS las hojas (pandas) 
    3) Si todo falla, retorna None (usar primera hoja por defecto)
    
    Args:
        ruta_excel: Ruta al archivo Excel
        
    Returns:
        Nombre de la hoja seleccionada o None si hay que usar la primera por defecto
    """
    # 1) Intento con hojas visibles
    try:
        elegido = seleccionar_hoja_visible(ruta_excel)
        if elegido is not None:
            return elegido
    except Exception:
        pass

    # 2) Fallback: todas las hojas
    hojas = listar_todas_hojas(ruta_excel)
    if not hojas:
        print("No se pudo listar hojas; se usará la primera hoja por defecto.")
        return None

    if len(hojas) == 1:
        print(f"Hoja detectada (todas): {hojas[0]}")
        return hojas[0]

    print("Hojas detectadas (todas):")
    for i, h in enumerate(hojas, 1):
        print(f"  [{i}] {h}")
    
    while True:
        resp = input("Elegí el número de la hoja a procesar (Enter = 1): ").strip()
        if resp == "":
            elegido = hojas[0]
            break
        if resp.isdigit() and 1 <= int(resp) <= len(hojas):
            elegido = hojas[int(resp) - 1]
            break
        print("Número inválido. Probá de nuevo.")
    
    print(f"Hoja seleccionada: {elegido}")
    return elegido