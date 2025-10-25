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