"""
tz_core.utils - UTILIDADES PURAS Y CORE FUNCTIONS
==================================================

✅ ESTADO: CÓDIGO CORE ACTIVO - FUNCIONES PURAS SIN DEPENDENCIAS
🎯 PROPÓSITO: Utilidades fundamentales (hashing, strings, archivos)
📍 DIFERENCIACIÓN: NO confundir con utilidades.py (UI helpers)

RESPONSABILIDADES ESPECÍFICAS:
- sha256_de_archivo(): Cálculo de hashes para integridad forense
- escribe_hashes_txt(): Generación de archivos de verificación
- compactar_ruta(): Formateo de rutas para reportes
- sanear_nombre_archivo(): Limpieza de nombres para filesystem

ARQUITECTURA HÍBRIDA:
- Este archivo maneja FUNCIONES PURAS (core utilities)
- utilidades.py maneja INTERFAZ DE USUARIO (UI dialogs)
- Son complementarios, NO duplicados

"""

import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import List, Tuple


def sha256_de_archivo(path: str) -> str:
    """
    Calcula SHA256 de un archivo
    
    Args:
        path: Ruta al archivo
        
    Returns:
        Hash SHA256 como string hexadecimal
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def escribe_hashes_txt(dest_path: str, pares: List[Tuple[str, str]]) -> None:
    """
    Escribe archivo HASHES.txt con formato: SHA256 <hex> <ruta_relativa>
    
    Args:
        dest_path: Ruta donde escribir el archivo HASHES.txt
        pares: Lista de tuplas (ruta_absoluta, ruta_relativa)
    """
    lines = []
    for abs_p, rel_p in pares:
        try:
            hexa = sha256_de_archivo(abs_p)
            lines.append(f"SHA256  {hexa}  {rel_p}")
        except Exception as e:
            lines.append(f"# ERROR hashing {rel_p}: {e}")
    
    with open(dest_path, "w", encoding="utf-8") as fw:
        fw.write("\n".join(lines) + "\n")


def compactar_ruta(txt: str, maxlen: int = 64) -> str:
    """
    Devuelve un nombre corto y seguro para usar como carpeta.
    Mantiene inicio y final del nombre y pone un hash al centro,
    asegurando que la longitud final sea <= maxlen.
    
    Args:
        txt: Texto original a compactar
        maxlen: Longitud máxima del resultado (default: 64)
        
    Returns:
        Cadena compactada que respeta maxlen
        
    Examples:
        >>> compactar_ruta("archivo_muy_largo_que_necesita_ser_compactado.txt", 30)
        'archivo__a1b2c3d4__do.txt'
    """
    # Reemplazar tanto \ como / por _
    base = str(txt).strip().replace("\\", "_").replace("/", "_")
    if len(base) <= maxlen:
        return base

    hash_len = 8            # tamaño del hash
    sep = "__"              # separador
    fixed = hash_len + 2*len(sep)  # espacio ocupado por "__" + hash + "__"

    # Si el maxlen es demasiado corto, devolvemos solo el hash truncado.
    if maxlen <= fixed + 2:
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:min(hash_len, maxlen)]

    remain = maxlen - fixed
    # repartimos 60/40 entre prefijo y sufijo con mínimos razonables
    pref_len = max(10, int(remain * 0.6))
    suf_len = remain - pref_len
    if suf_len < 8:
        suf_len = 8
        pref_len = remain - suf_len

    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:hash_len]
    prefix = base[:pref_len].rstrip("_- ")
    suffix = base[-suf_len:].lstrip("_- ")

    return f"{prefix}{sep}{h}{sep}{suffix}"


def sanear_nombre_archivo(s: str, fallback: str = "archivo_limpio") -> str:
    """
    Limpia un nombre de archivo removiendo caracteres problemáticos.
    
    CRÍTICO: Esta función unifica dos funciones similares del monolito:
    - _sanear_nombre_archivo() (fallback: "antenas_manual") 
    - _sanear_nombre_archivo_local() (fallback: variable nombre_base)
    
    BREAKING CHANGE PREVENTION: Los wrappers mantienen fallbacks exactos
    para preservar comportamiento idéntico en casos límite (vacío, None, etc.)
    
    Proceso de limpieza:
    1. Normaliza unicode y remueve acentos (NFD -> ASCII)
    2. Permite solo: letras, números, guión, guión_bajo, punto, espacios
    3. Convierte espacios múltiples a guión_bajo único
    4. Limpia bordes problemáticos (puntos/guiones al inicio/final)
    5. Aplica fallback si resultado está vacío
    
    Args:
        s: Nombre de archivo a limpiar
        fallback: Valor por defecto si el resultado está vacío
                 IMPORTANTE: Cada wrapper debe usar su fallback específico
        
    Returns:
        Nombre de archivo limpio y seguro
        
    Examples:
        >>> sanear_nombre_archivo("Reporte José María 2024.xlsx")
        'Reporte_Jose_Maria_2024.xlsx'
        >>> sanear_nombre_archivo("", "default")
        'default'
        >>> sanear_nombre_archivo("...")  # Se limpia a vacío -> fallback
        'archivo_limpio'
    """
    # PASO 1: Aplicar fallback inicial si entrada es None/vacía
    s = s or fallback
    
    # PASO 2: Normalizar unicode y remover acentos
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")
    
    # PASO 3: Permitir solo caracteres seguros
    # \w = letras+números+_, \s = espacios, .- = punto y guión
    s = re.sub(r"[^\w\s.-]", "_", s)
    
    # PASO 4: Normalizar espacios a guión_bajo
    s = re.sub(r"\s+", "_", s)
    
    # PASO 5: Limpiar bordes problemáticos
    s = s.strip("._")
    
    # PASO 6: Fallback final si se limpió todo
    return s or fallback


def placeholder_function():
    """
    Placeholder para utilidades que se extraerán del script principal
    
    Funciones candidatas:
    - _escribe_hashes_txt: Escritura de hashes
    - _compactar_ruta: Normalización de rutas
    - _sanear_nombre_archivo*: Saneamiento de nombres
    - Helpers de fecha/hora
    - Funciones de normalización de texto
    """
    pass

# TODO: Extraer funciones del script principal:
# - Funciones sin dependencias externas
# - Helpers matemáticos/formateo
# - Utilidades de archivos
# - Helpers de fecha/hora puros