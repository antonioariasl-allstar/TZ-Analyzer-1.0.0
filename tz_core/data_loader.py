"""
tz_core.data_loader - Carga y manejo de archivos de datos

Módulo especializado en la carga de archivos Excel, CSV y TSV con manejo
inteligente de hojas de cálculo, detección de encoding y validaciones.

🚨 ESTADO: FASE 5.3a - Extracción del sistema cardiovascular de carga Excel
🚨 ARQUITECTURA CRÍTICA: Sistema dual de columnas implementado

HISTORIA DE REFACTORIZACIÓN:
- Fase 5.1: Funciones puras extraídas
- Fase 5.2: Funciones interactivas extraídas  
- Fase 5.3a: Sistema cardiovascular dual extraído (ACTUAL)

SISTEMA CARDIOVASCULAR DUAL:
Durante el análisis de Fase 5.3 se descubrió que el monolito original mantiene
INTENCIONALMENTE dos versiones de nombres de columnas:

1. df.attrs["orig_cols"] - Columnas originales del archivo (UI)
2. df.columns normalizadas - Columnas procesadas (algoritmo)

Esta NO es una duplicación accidental sino una decisión arquitectónica
crítica para preservar tanto la presentación como la funcionalidad.

⚠️ ADVERTENCIA PARA FUTUROS DESARROLLADORES:
No "optimizar" eliminando el sistema dual - ambas versiones son necesarias.
La UI necesita mostrar nombres reales, el algoritmo necesita nombres limpiados.

Funciones extraídas:
- obtener_hojas_visibles(): Detección de hojas visibles vs ocultas en Excel
- listar_todas_hojas(): Listado completo de hojas usando pandas
- seleccionar_hoja_visible(): Selección interactiva de hojas visibles 
- seleccionar_hoja(): Selección maestra con doble estrategia (visibles/todas)
- cargar_excel_con_normalizacion(): Carga Excel con sistema cardiovascular dual
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


def cargar_excel_con_normalizacion(ruta_excel: str, hoja_elegida: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """
    Carga archivo Excel con preservación del sistema de columnas dual.
    
    🚨 ARQUITECTURA CRÍTICA - SISTEMA CARDIOVASCULAR DUAL 🚨
    
    Durante la refactorización se descubrió que el sistema original mantiene
    INTENCIONALMENTE dos versiones de los nombres de columnas:
    
    1. df.attrs["orig_cols"] (línea 6545 original):
       - Columnas RAW tal como aparecen en el archivo Excel
       - Preserva espacios, caracteres especiales, formato original
       - Usado por la interfaz de usuario para mostrar nombres reales
       - NUNCA debe ser modificado después de la carga
    
    2. Columnas normalizadas del DataFrame (líneas 6549-6557 original):
       - Headers limpiados con .strip() para el algoritmo
       - Remueve espacios en blanco, estandariza formato
       - Usado internamente por la lógica de procesamiento
       - Se almacena snapshot antes de normalizar
    
    Esta dualidad NO ES UN BUG sino una decisión arquitectónica deliberada
    para mantener tanto la presentación original como la funcionalidad interna.
    
    TIMING CRÍTICO (basado en análisis de líneas originales):
    - Línea 6543: pd.read_excel() - Carga inicial
    - Línea 6545: df.attrs["orig_cols"] - ANTES de normalización
    - Líneas 6549-6557: Normalización de headers - DESPUÉS de backup
    - Línea 7551: df._orig_cols - Snapshot post-normalización
    
    Args:
        ruta_excel: Ruta al archivo Excel
        hoja_elegida: Hoja específica a cargar, None para selección automática
        
    Returns:
        Tuple con (DataFrame con sistema dual preservado, nombre_hoja_utilizada)
        
    Raises:
        ValueError: Si el archivo no puede ser cargado
        
    Ejemplo:
        Archivo Excel con columna "  Timestamp  "
        - df.attrs["orig_cols"] = ["  Timestamp  "] 
        - df.columns = ["Timestamp"] (normalizado)
        
    Historia:
        Extraído del monolito en Fase 5.3a usando metodología campo minado.
        Preserva comportamiento exacto del sistema cardiovascular original.
    """
    try:
        # PASO 1: Carga inicial Excel (réplica exacta línea 6543 original)
        if hoja_elegida:
            df = pd.read_excel(ruta_excel, sheet_name=hoja_elegida)
            hoja_usada = hoja_elegida
        else:
            df = pd.read_excel(ruta_excel)
            hoja_usada = "primera_hoja"
        
        # PASO 2: Backup INMEDIATO de columnas originales (línea 6545 del cardiovascular)
        # ⚠️ CRÍTICO: Debe ejecutarse ANTES de cualquier normalización
        # Preserva nombres exactos del archivo para mostrar en UI
        df.attrs["orig_cols"] = list(df.columns)
        
        # PASO 3: Snapshot para debugging y verificación de integridad
        # Este snapshot documenta el estado pre-normalización
        cols_originales_snapshot = list(df.columns)
        
        # PASO 4: Normalización de headers para algoritmo (líneas 6549-6557 cardiovascular)
        # ⚠️ CRÍTICO: Solo después del backup de originales
        # Remueve espacios en blanco que interfieren con procesamiento
        df.columns = [str(col).strip() for col in df.columns]
        
        # VALIDACIÓN: Verificar que el sistema dual está operacional
        assert "orig_cols" in df.attrs, "Sistema dual falló: orig_cols no preservado"
        assert len(df.attrs["orig_cols"]) == len(df.columns), "Sistema dual falló: conteo inconsistente"
        
        return df, hoja_usada
        
    except Exception as e:
        raise ValueError(f"Error cargando Excel {ruta_excel}: {str(e)}")