"""
Utilidades para manejo y clasificación de tiempo.

Este módulo contiene funciones puras para procesamiento temporal,
incluyendo conversión de strings, rangos temporales y clasificación.

Funciones:
- hhmmss_to_time_or_none: Convierte HH:MM:SS a datetime.time
- en_rango_tiempo: Verifica si tiempo está en rango (soporta medianoche)
- en_rango_minutos: Verifica si minutos están en rango (versión enteros)
- clasificar_rango_sv: Clasifica hora en rangos SV predefinidos

Todas las funciones son helpers matemáticos puros extraídos del monolito principal
para mejorar reutilización y testing.
"""

from datetime import time as _time
from typing import Optional, Dict, Tuple

# Constantes para clasificación SV (importadas desde script principal)
RANGOS_SV = {
    "madrugada": ("madrugada_0000-0559", _time(0, 0, 0),  _time(5, 59, 59)),   # 00:00–05:59
    "manana":    ("manana_0600-1159",    _time(6, 0, 0),  _time(11, 59, 59)),  # 06:00–11:59
    "tarde":     ("tarde_1200-1759",     _time(12, 0, 0), _time(17, 59, 59)),  # 12:00–17:59
    "noche":     ("noche_1800-2359",     _time(18, 0, 0), _time(23, 59, 59)),  # 18:00–23:59
}


def hhmmss_to_time_or_none(hh) -> Optional[_time]:
    """
    Convierte una cadena en formato HH:MM:SS a objeto datetime.time.
    
    Args:
        hh: Cadena con formato HH:MM:SS (se toman máx. 8 caracteres)
    
    Returns:
        datetime.time si la conversión es exitosa, None en caso de error
    
    Examples:
        >>> hhmmss_to_time_or_none("14:30:15")
        datetime.time(14, 30, 15)
        >>> hhmmss_to_time_or_none("invalid")
        None
        >>> hhmmss_to_time_or_none("25:00:00")
        None
    """
    try:
        h, m, s = str(hh).strip()[:8].split(":")
        return _time(int(h), int(m), int(s))
    except Exception:
        return None


def en_rango_tiempo(t: _time, ini: _time, fin: _time) -> bool:
    """
    Verifica si un tiempo t está dentro del rango [ini, fin].
    Soporta rangos que cruzan medianoche (ej: 22:00 a 02:00).
    
    Args:
        t: Tiempo a verificar
        ini: Tiempo de inicio del rango
        fin: Tiempo de fin del rango
    
    Returns:
        True si t está dentro del rango, False en caso contrario
    
    Examples:
        >>> t = _time(14, 30)
        >>> ini = _time(12, 0)
        >>> fin = _time(18, 0)
        >>> en_rango_tiempo(t, ini, fin)
        True
        >>> # Rango que cruza medianoche
        >>> en_rango_tiempo(_time(1, 0), _time(22, 0), _time(6, 0))
        True
    """
    if ini <= fin:
        return ini <= t <= fin
    return (t >= ini) or (t <= fin)


def en_rango_minutos(minutos: int, ini: int, fin: int) -> bool:
    """
    Verifica si un valor en minutos está dentro del rango [ini, fin].
    Soporta rangos que cruzan medianoche.
    
    Args:
        minutos: Minutos desde medianoche (0-1439)
        ini: Minutos de inicio del rango
        fin: Minutos de fin del rango
    
    Returns:
        True si minutos está dentro del rango, False en caso contrario
    
    Examples:
        >>> en_rango_minutos(870, 720, 1080)  # 14:30 entre 12:00-18:00
        True
        >>> # Rango que cruza medianoche (22:00-06:00)
        >>> en_rango_minutos(60, 1320, 360)  # 01:00 entre 22:00-06:00
        True
    """
    if ini <= fin:
        return ini <= minutos <= fin
    # Cruce de medianoche: ejemplo 18:01–01:00 -> minutos >= ini O minutos <= fin
    return minutos >= ini or minutos <= fin


def clasificar_rango_sv(hhmmss: str) -> Optional[str]:
    """
    Clasifica una hora HH:MM:SS en uno de los rangos SV predefinidos
    (madrugada, manana, tarde, noche) según RANGOS_SV.
    
    Args:
        hhmmss: Cadena con formato HH:MM:SS
    
    Returns:
        Clave del rango ('madrugada', 'manana', 'tarde', 'noche') o None si no aplica
    
    Examples:
        >>> clasificar_rango_sv("14:30:00")
        'tarde'
        >>> clasificar_rango_sv("03:15:00")
        'madrugada'
        >>> clasificar_rango_sv("invalid")
        None
    """
    t = hhmmss_to_time_or_none(hhmmss)
    if t is None:
        return None
    for clave, (_, ini, fin) in RANGOS_SV.items():
        if en_rango_tiempo(t, ini, fin):
            return clave
    return None


# Aliases para compatibilidad con código existente
_hhmmss_to_time_or_none = hhmmss_to_time_or_none
_en_rango = en_rango_tiempo  # alias principal para tiempo
_en_rango_minutos = en_rango_minutos
_clasificar_rango_sv = clasificar_rango_sv