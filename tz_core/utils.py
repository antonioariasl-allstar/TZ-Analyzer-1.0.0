"""
tz_core.utils - Utilidades comunes y helpers
Funciones puras sin dependencias cruzadas
"""

import hashlib
import os
import re
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