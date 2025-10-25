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