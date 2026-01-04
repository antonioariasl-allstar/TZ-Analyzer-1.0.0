"""
Utilidades para operaciones de archivos e I/O.

Este módulo contiene funciones especializadas para manejo de archivos,
copia de recursos y escritura de archivos de verificación.

Funciones:
- escribe_hashes_txt: Genera archivos de hash para verificación de integridad
- copiar_logo_a_salida: Copia archivos de recursos con validación y fallbacks

Todas las funciones son helpers de I/O puros extraídos del monolito principal
para mejorar reutilización y testing.
"""

import os
import shutil
from typing import Callable, List, Tuple, Optional
from .utils import sha256_de_archivo


def escribe_hashes_txt(dest_path: str, pares: List[Tuple[str, str]]) -> None:
    """
    Escribe archivo HASHES.txt con formato SHA256 para verificación forense.
    
    Args:
        dest_path: Ruta del archivo de destino para escribir hashes
        pares: Lista de tuplas (ruta_absoluta, ruta_relativa) de archivos a procesar
        
    Formato de salida:
        SHA256  <hex_hash>  <ruta_relativa>
        # ERROR hashing <archivo>: <mensaje> (para errores)
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


def copiar_logo_a_salida(logo_src: str, carpeta_salida: str) -> Optional[str]:
    """
    Copia archivo de logo a carpeta de salida con validación robusta.
    
    Args:
        logo_src: Ruta del archivo logo (absoluta o relativa)
        carpeta_salida: Directorio de destino
        
    Returns:
        str: Nombre del archivo (basename) copiado, o None si falla
        
    Características:
    - Acepta rutas absolutas y relativas
    - Busca en directorio del script si ruta relativa no existe
    - Crea directorio destino si no existe
    - Evita copiar archivo sobre sí mismo
    - Manejo robusto de errores
    """
    try:
        if not logo_src:
            return None

        # Acepta ruta absoluta o relativa; normalizamos
        logo_abs = os.path.abspath(logo_src)
        if not os.path.exists(logo_abs):
            # Si viene relativa al directorio del script, probamos ahí
            # Usamos __file__ del módulo para obtener directorio base
            import tz_core
            base = os.path.dirname(os.path.dirname(os.path.abspath(tz_core.__file__)))
            logo_abs = os.path.join(base, logo_src)
            if not os.path.exists(logo_abs):
                return None

        # Crear directorio destino si no existe
        os.makedirs(carpeta_salida, exist_ok=True)
        dest = os.path.join(carpeta_salida, os.path.basename(logo_abs))

        # Evitar copiar sobre sí mismo
        if os.path.abspath(logo_abs) != os.path.abspath(dest):
            shutil.copy2(logo_abs, dest)

        return os.path.basename(dest)
    except Exception:
        return None


def relocate_kmz_file(
    *,
    case_name: str,
    source_folder: str,
    target_folder: str,
    logger: Optional[Callable[[str], None]] = None,
    exists_fn: Callable[[str], bool] = os.path.isfile,
    remove_fn: Callable[[str], None] = os.remove,
    move_fn: Callable[[str, str], None] = os.replace,
) -> Optional[str]:
    """Ensure the KMZ generated in a temporary folder lives alongside the KML."""

    if not case_name:
        return None

    filename = f"{case_name}_mapeo.kmz"
    src = os.path.join(source_folder, filename)
    dst = os.path.join(target_folder, filename)

    if not exists_fn(src):
        return None

    try:
        os.makedirs(target_folder, exist_ok=True)
    except Exception:
        pass

    try:
        if exists_fn(dst):
            remove_fn(dst)
    except Exception:
        pass

    try:
        move_fn(src, dst)
    except Exception:
        return None

    if logger:
        try:
            logger(f"[DEBUG] KMZ reubicado a: {dst}")
        except Exception:
            pass

    return dst


# Aliases para compatibilidad con script principal
_escribe_hashes_txt = escribe_hashes_txt
_copiar_logo_a_salida = copiar_logo_a_salida
_relocate_kmz_file = relocate_kmz_file