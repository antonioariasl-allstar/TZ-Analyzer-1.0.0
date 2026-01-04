"""
🔧 TZ-Analyzer HTML Helper Functions

Funciones auxiliares extraídas de generar_informe_html para modularización.
Estas funciones manejan formateo, validación y generación de elementos HTML.

EXTRAÍDO DE: script_principal_bitacoras_refactory.py líneas 3207-5790
FECHA: 27 de octubre de 2025
FASE: 1.1 - Creación de módulo base

FUNCIONES INCLUIDAS:
- _fmt_dt: Formateo de fecha/hora
- _first_nonempty_in: Primer valor no vacío en columnas DataFrame
- _nunique_in: Contar únicos en columnas DataFrame  
- _unique_values_in: Valores únicos con límite
- _fmt_imei_item: Formateo de IMEI
- _row_html: Generación de filas HTML
- _luhn_check: Validación Luhn para IMEI
- _is_valid_imei: Validador IMEI completo

DEPENDENCIAS:
- pandas as pd
- typing (para type hints)
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import pandas as pd

from tz_core.bitacora_normalization import normalize_imei


# ================================================================
# 📅 FUNCIONES DE FORMATEO DE FECHA/HORA
# ================================================================

def fmt_datetime(ts) -> str:
    """
    Formatea timestamp a formato dd/mm/yyyy HH:MM.
    
    EXTRAÍDO DE: generar_informe_html línea 3342
    """
    return ts.strftime("%d/%m/%Y %H:%M")


# ================================================================
# 📊 FUNCIONES DE ANÁLISIS DE DATAFRAME
# ================================================================

def first_nonempty_in(df: pd.DataFrame, cols: List[str]) -> Optional[str]:
    """
    Obtiene el primer valor no vacío de las columnas especificadas.
    
    EXTRAÍDO DE: generar_informe_html línea 3387
    
    Args:
        df: DataFrame a analizar
        cols: Lista de nombres de columnas candidatas
        
    Returns:
        Primer valor no vacío encontrado, None si no hay ninguno
    """
    for c in cols:
        if c in df.columns:
            s = df[c].dropna().astype(str).str.strip()
            s = s[s != ""]
            if not s.empty:
                return s.iloc[0]
    return None


def nunique_in(df: pd.DataFrame, cols: List[str]) -> int:
    """
    Cuenta valores únicos TOTALES en las columnas especificadas.
    
    EXTRAÍDO DE: generar_informe_html línea 3396
    
    Args:
        df: DataFrame a analizar
        cols: Lista de nombres de columnas candidatas
        
    Returns:
        Número TOTAL de valores únicos entre todas las columnas
    """
    all_values = []
    for c in cols:
        if c in df.columns:
            s = df[c].dropna().astype(str).str.strip()
            s = s[s != ""]
            if not s.empty:
                all_values.extend(s.tolist())
    
    # Contar únicos totales
    return len(set(all_values)) if all_values else 0


def unique_values_in(df: pd.DataFrame, cols: List[str], max_items: int = 8) -> Tuple[List[str], int]:
    """
    Obtiene valores únicos de las columnas con límite.
    
    EXTRAÍDO DE: generar_informe_html línea 3405
    
    Args:
        df: DataFrame a analizar
        cols: Lista de nombres de columnas candidatas
        max_items: Número máximo de items a retornar
        
    Returns:
        Tupla (lista_valores_únicos, cantidad_extra)
    """
    vals = []
    for c in cols:
        if c in df.columns:
            s = df[c].dropna().astype(str).str.strip()
            s = s[s != ""]
            if not s.empty:
                vals.extend(s.tolist())

    # De-duplicar manteniendo orden
    seen = set()
    uniq = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    
    if not uniq:
        return [], 0
    
    extra = max(0, len(uniq) - max_items)
    return uniq[:max_items], extra


# ================================================================
# 📱 FUNCIONES DE VALIDACIÓN Y FORMATO IMEI
# ================================================================

def fmt_imei_item(x: str) -> str:
    """
    Formatea un item IMEI (convierte float a int si es necesario).
    
    EXTRAÍDO DE: generar_informe_html línea 3426
    """
    normalized = normalize_imei(x)
    if normalized:
        return normalized
    try:
        f = float(str(x))
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return str(x)


def luhn_check(num: str) -> bool:
    """
    Valida IMEI de 15 dígitos con algoritmo Luhn.
    
    EXTRAÍDO DE: generar_informe_html línea 3446
    """
    s = 0
    parity = len(num) % 2
    for i, ch in enumerate(num):
        d = ord(ch) - 48  # int(ch)
        if (i % 2) == parity:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return (s % 10) == 0


def is_valid_imei(val: str) -> bool:
    """
    Validador completo de IMEI/IMEISV.
    
    EXTRAÍDO DE: generar_informe_html línea 3459
    
    Acepta:
      - IMEI de 15 dígitos (Luhn OK)
      - IMEISV de 16 dígitos (sin checkdigit) si los primeros 14 no son todo ceros
    
    Rechaza: vacío, '0', 'null', 'none', 'nan', 'sin inf', 's/i', 
             todos ceros, longitudes != 15/16 o no numérico
    """
    raw = str(val).strip().lower()
    if raw in {"", "0", "null", "none", "nan", "sin inf.", "sin inf", "s/i"}:
        return False
    
    # Conservar solo dígitos
    s = "".join(ch for ch in raw if ch.isdigit())
    if not s or set(s) == {"0"}:
        return False
    
    if len(s) == 15:
        return luhn_check(s)
    if len(s) == 16:  # IMEISV
        return not set(s[:14]) == {"0"}
    return False


# ================================================================
# 🎨 FUNCIONES DE GENERACIÓN HTML
# ================================================================

def row_html(label: str, single: Optional[str], n: int, lst: List[str], extra: int, mono: bool = False) -> str:
    """
    Genera una fila HTML para mostrar datos.
    
    EXTRAÍDO DE: generar_informe_html línea 3435
    
    Args:
        label: Etiqueta de la fila
        single: Valor único (si n <= 1)
        n: Número total de valores
        lst: Lista de valores a mostrar
        extra: Cantidad de valores adicionales no mostrados
        mono: Si usar fuente monoespaciada
        
    Returns:
        String con HTML de la fila
    """
    if n > 1 and lst:
        cls = 'list mono' if mono else 'list'
        items = "".join(f"<li>{v}</li>" for v in lst)
        more = f"<li>… y {extra} más</li>" if extra > 0 else ""
        return f"<tr><td><b>{label}:</b></td><td><ul class=\"{cls}\">{items}{more}</ul></td></tr>\n"
    elif single:
        return f"<tr><td><b>{label}:</b></td><td>{single}</td></tr>\n"
    else:
        return ""


# ================================================================
# 📋 GRUPOS DE COLUMNAS CANÓNICAS
# ================================================================

# Definiciones de grupos de columnas sinónimas utilizadas en el análisis
COLUMN_GROUPS = {
    "tel": ["tel", "telefono", "numero", "msisdn", "a_number", "origen", "from", "callingnumber", "num"],
    "alias": ["alias", "alias_usuario", "apodo"],
    "user": ["usuario", "nombre_usuario", "suscriptor", "user_name"],
    "abonado": ["abonado", "titular", "owner", "subscriber"],
    "imei": ["imei", "imei1", "imei_1"],
    "imsi": ["imsi", "imsi1", "imsi_1", "imsi_origen"]
}


# ================================================================
# 🧪 FUNCIONES DE TESTING Y VALIDACIÓN
# ================================================================

def validate_module() -> bool:
    """
    Valida que todas las funciones del módulo están disponibles y funcionan.
    
    Returns:
        True si todas las validaciones pasan
    """
    try:
        # Test fmt_datetime
        from datetime import datetime
        test_dt = datetime(2025, 10, 27, 15, 30)
        assert fmt_datetime(test_dt) == "27/10/2025 15:30"
        
        # Test DataFrame functions
        test_df = pd.DataFrame({
            'col1': ['', 'value1', None],
            'col2': [None, '', 'value2']
        })
        assert first_nonempty_in(test_df, ['col1', 'col2']) == 'value1'
        assert nunique_in(test_df, ['col1', 'col2']) == 2
        
        # Test IMEI functions
        assert luhn_check("490154203237518") == True  # IMEI válido
        assert is_valid_imei("490154203237518") == True
        assert is_valid_imei("000000000000000") == False
        
        # Test HTML generation
        html = row_html("Test", "value", 1, [], 0)
        assert "Test" in html and "value" in html
        
        return True
    except Exception as e:
        print(f"ERROR en validacion del modulo: {e}")
        return False


if __name__ == "__main__":
    # Auto-test al ejecutar el módulo directamente
    if validate_module():
        print("MODULO HTML_HELPERS VALIDADO EXITOSAMENTE")
    else:
        print("MODULO HTML_HELPERS FALLO VALIDACION")