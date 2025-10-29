"""
tz_io.file_io - UTILIDADES DE E/S DE ARCHIVOS
===========================================

✅ ESTADO: MIGRACIÓN DESDE tz_core - OPERACIONES DE ARCHIVOS
🎯 PROPÓSITO: Funciones especializadas para manejo de archivos e I/O
📁 RESPONSABILIDADES: Verificación de integridad, copia de recursos

FUNCIONES PRINCIPALES:
- escribe_hashes_txt(): Genera archivos SHA256 para verificación forense
- copiar_logo_a_salida(): Copia recursos con validación y fallbacks robustos

DEPENDENCIAS:
- os, shutil: Operaciones de sistema de archivos
- tz_utils.crypto: Funciones de hash (cuando se implemente)

MIGRADO DESDE: tz_core/file_utils.py
FECHA MIGRACIÓN: 29 octubre 2025
"""

import os
import shutil
from typing import List, Tuple, Optional

# Temporal: importar desde tz_core hasta migrar crypto utils
try:
    from tz_core.utils import sha256_de_archivo
except ImportError:
    # Fallback si no está disponible
    import hashlib
    def sha256_de_archivo(ruta_archivo: str) -> str:
        """Calcula SHA256 de un archivo."""
        with open(ruta_archivo, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()


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
            # Buscar directorio base del proyecto
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base = os.path.dirname(os.path.dirname(current_dir))  # Subir 2 niveles desde tz_io
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


# Aliases para compatibilidad con script principal
_escribe_hashes_txt = escribe_hashes_txt
_copiar_logo_a_salida = copiar_logo_a_salida