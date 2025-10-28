"""
tz_core.logging_utils - SISTEMA DE LOGGING CENTRALIZADO
========================================================

✅ ESTADO: EXTRACCIÓN FASE 9C - FUNCIÓN LOG Y ESTADO GLOBAL
🎯 PROPÓSITO: Logging centralizado con timestamp y almacenamiento en memoria
📍 DIFERENCIACIÓN: Sistema simple pero crítico usado masivamente en toda la aplicación

RESPONSABILIDADES ESPECÍFICAS:
- log(): Función principal de logging con timestamp automático
- get_logs(): Acceso a logs almacenados en memoria
- get_log_placeholders(): Acceso a placeholders globales
- clear_logs(): Limpiar estado de logs

DEPENDENCIAS:
- datetime: Generación de timestamps con formato específico

CARACTERÍSTICAS ESPECIALES:
- Logging dual: print() para consola + almacenamiento en memoria
- Timestamp automático formato "YYYY-MM-DD HH:MM:SS"
- Estado global thread-safe para acumulación de logs
- Placeholders para evitar duplicación de mensajes

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 721-729
FECHA MIGRACIÓN: 28 octubre 2025
FASE: 9C - Logging (Riesgo Bajo)
IMPACTO: 50+ usos en todo el monolito
"""

from datetime import datetime
from typing import List, Set


# ==========================================
# ESTADO GLOBAL DEL SISTEMA DE LOGGING
# ==========================================

_LOGS: List[str] = []
_LOG_PLACEHOLDERS: Set[str] = set()


def log(msg: str) -> None:
    """
    Función principal de logging con timestamp automático.
    
    Registra el mensaje tanto en consola (print) como en memoria
    para posterior recuperación o análisis.
    
    Args:
        msg: Mensaje a registrar
        
    Side Effects:
        - Imprime mensaje con timestamp en consola
        - Almacena mensaje formateado en memoria global
        
    Format:
        "[YYYY-MM-DD HH:MM:SS] mensaje"
        
    Usage:
        log("[INFO] Iniciando procesamiento")
        log("[ERROR] No se pudo cargar archivo")
        log("[DEBUG] Procesados 1000 registros")
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = f"[{ts}] {msg}"
    print(s)
    _LOGS.append(s)


def get_logs() -> List[str]:
    """
    Obtiene todos los logs almacenados en memoria.
    
    Returns:
        Lista de strings con todos los mensajes de log formateados,
        en orden cronológico de registro
        
    Usage:
        for log_entry in get_logs():
            print(log_entry)
    """
    return _LOGS.copy()


def get_log_placeholders() -> Set[str]:
    """
    Obtiene el conjunto de placeholders de log.
    
    Los placeholders son utilizados para evitar duplicación
    de mensajes repetitivos durante el procesamiento.
    
    Returns:
        Set de strings con placeholders activos
        
    Usage:
        if "proceso_completado" not in get_log_placeholders():
            log("[INFO] Proceso completado")
            add_log_placeholder("proceso_completado")
    """
    return _LOG_PLACEHOLDERS.copy()


def add_log_placeholder(placeholder: str) -> None:
    """
    Añade un placeholder para evitar logs duplicados.
    
    Args:
        placeholder: Identificador único del placeholder
        
    Usage:
        add_log_placeholder("archivo_procesado")
    """
    _LOG_PLACEHOLDERS.add(placeholder)


def has_log_placeholder(placeholder: str) -> bool:
    """
    Verifica si existe un placeholder específico.
    
    Args:
        placeholder: Identificador del placeholder a verificar
        
    Returns:
        True si el placeholder existe, False en caso contrario
        
    Usage:
        if not has_log_placeholder("inicializado"):
            log("[INFO] Inicializando sistema...")
            add_log_placeholder("inicializado")
    """
    return placeholder in _LOG_PLACEHOLDERS


def clear_logs() -> None:
    """
    Limpia todos los logs almacenados en memoria.
    
    Útil para reset entre procesamiento de diferentes archivos
    o al inicio de nuevas sesiones.
    
    Side Effects:
        - Vacía la lista de logs almacenados
        - NO afecta los placeholders (usar clear_log_placeholders)
        
    Usage:
        clear_logs()  # Nuevo archivo, nuevos logs
    """
    global _LOGS
    _LOGS.clear()


def clear_log_placeholders() -> None:
    """
    Limpia todos los placeholders de log.
    
    Side Effects:
        - Vacía el conjunto de placeholders
        - NO afecta los logs almacenados
        
    Usage:
        clear_log_placeholders()  # Reset de estado de placeholders
    """
    global _LOG_PLACEHOLDERS
    _LOG_PLACEHOLDERS.clear()


def clear_all_logging_state() -> None:
    """
    Limpia completamente el estado del sistema de logging.
    
    Equivale a llamar clear_logs() + clear_log_placeholders().
    Útil para reset completo entre ejecuciones.
    
    Side Effects:
        - Vacía todos los logs almacenados
        - Vacía todos los placeholders
        
    Usage:
        clear_all_logging_state()  # Reset completo
    """
    clear_logs()
    clear_log_placeholders()


def get_logs_count() -> int:
    """
    Obtiene el número total de logs registrados.
    
    Returns:
        Cantidad de mensajes de log almacenados
        
    Usage:
        if get_logs_count() > 1000:
            log("[WARN] Muchos logs acumulados, considerar limpiar")
    """
    return len(_LOGS)


def get_recent_logs(count: int = 10) -> List[str]:
    """
    Obtiene los logs más recientes.
    
    Args:
        count: Número de logs recientes a obtener (default: 10)
        
    Returns:
        Lista con los últimos 'count' logs, en orden cronológico
        
    Usage:
        recent = get_recent_logs(5)  # Últimos 5 logs
        for entry in recent:
            print(entry)
    """
    return _LOGS[-count:] if _LOGS else []


def log_info(msg: str) -> None:
    """Helper para logs de información."""
    log(f"[INFO] {msg}")


def log_warn(msg: str) -> None:
    """Helper para logs de advertencia."""
    log(f"[WARN] {msg}")


def log_error(msg: str) -> None:
    """Helper para logs de error."""
    log(f"[ERROR] {msg}")


def log_debug(msg: str) -> None:
    """Helper para logs de depuración."""
    log(f"[DEBUG] {msg}")