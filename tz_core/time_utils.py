#!/usr/bin/env python3
"""
tz_core.time_utils - Utilidades de tiempo para TZ Analyzer

Funciones puras para manipulación, conversión y clasificación de tiempo.
Extraídas del script_principal_bitacoras_refactory.py para modularización.

Módulo de bajo riesgo - funciones sin estado y sin dependencias externas complejas.
"""

from datetime import time as _time
from typing import Optional, List, Dict, Tuple, Any

# Definición de rangos horarios para clasificación "SV" (usado en carpetas de KML)
# Formato: clave -> (nombre_carpeta, hora_inicio, hora_fin)
RANGOS_SV = {
    "madrugada": ("madrugada_0000-0559", _time(0, 0, 0),  _time(6, 0, 0)),    # 00:00–05:59
    "manana":    ("manana_0600-1159",    _time(6, 0, 0),  _time(12, 0, 0)),   # 06:00–11:59
    "tarde":     ("tarde_1200-1759",     _time(12, 0, 0), _time(18, 0, 0)),   # 12:00–17:59
    "noche":     ("noche_1800-2359",     _time(18, 0, 0), _time(23, 59, 59)), # 18:00–23:59
}


def hhmmss_to_time_or_none(hh: Any) -> Optional[_time]:
    """
    Convierte una cadena en formato HH:MM:SS a objeto datetime.time.
    
    Args:
        hh: Cadena con formato HH:MM:SS (se toman máx. 8 caracteres)
    
    Returns:
        datetime.time si la conversión es exitosa, None en caso de error
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
    """
    if ini <= fin:
        return ini <= t <= fin
    return (t >= ini) or (t <= fin)


def clasificar_rango_sv(hhmmss: str) -> Optional[str]:
    """
    Clasifica una hora HH:MM:SS en uno de los rangos SV predefinidos
    (madrugada, manana, tarde, noche) según RANGOS_SV.
    
    Args:
        hhmmss: Cadena con formato HH:MM:SS
    
    Returns:
        Clave del rango ('madrugada', 'manana', 'tarde', 'noche') o None si no aplica
    """
    t = hhmmss_to_time_or_none(hhmmss)
    if t is None:
        return None
    for clave, (_, ini, fin) in RANGOS_SV.items():
        if en_rango_tiempo(t, ini, fin):
            return clave
    return None


def parse_hhmmss_to_minutes(s: Optional[str]) -> Optional[int]:
    """
    Convierte 'HH:MM' o 'HH:MM:SS' a minutos desde 00:00. 
    
    Args:
        s: Cadena con formato HH:MM o HH:MM:SS
        
    Returns:
        Minutos desde 00:00 o None si no se puede convertir
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        # ignorar segundos si vienen
        return hh * 60 + mm
    except Exception:
        return None


def minutes_from_any(hora: Any) -> Optional[int]:
    """
    Acepta: datetime.time, datetime.datetime, pandas.Timestamp, str 'HH:MM(:SS)'.
    Devuelve minutos desde 00:00 o None.
    
    Args:
        hora: Objeto de tiempo en diversos formatos
        
    Returns:
        Minutos desde 00:00 o None si no se puede convertir
    """
    try:
        # pandas.Timestamp o datetime
        if hasattr(hora, "hour") and hasattr(hora, "minute"):
            return int(hora.hour) * 60 + int(hora.minute)
        if isinstance(hora, _time):
            return hora.hour * 60 + hora.minute
        # string
        return parse_hhmmss_to_minutes(str(hora))
    except Exception:
        return None


def construir_rangos_cfg(rangos_cfg: List[Dict[str, Any]]) -> List[Tuple[str, int, int]]:
    """
    Convierte configuración de rangos a formato de minutos.
    
    Args:
        rangos_cfg: Lista de diccionarios con "nombre", "inicio", "fin"
        
    Returns:
        Lista de tuplas (nombre, minutos_inicio, minutos_fin)
    """
    res = []
    for r in rangos_cfg:
        n = str(r.get("nombre", "")).strip() or "Rango"
        mi = parse_hhmmss_to_minutes(r.get("inicio"))
        mf = parse_hhmmss_to_minutes(r.get("fin"))
        if mi is None or mf is None:
            continue
        res.append((n, mi, mf))
    return res


def en_rango_minutos(minutos: int, ini: int, fin: int) -> bool:
    """
    True si 'minutos' cae dentro del rango [ini..fin] en minutos.
    Soporta cruce de medianoche: si ini > fin, el rango pasa por 00:00.
    
    Args:
        minutos: Minutos desde 00:00 a verificar
        ini: Minutos de inicio del rango
        fin: Minutos de fin del rango
        
    Returns:
        True si está dentro del rango, False en caso contrario
    """
    if ini <= fin:
        return ini <= minutos <= fin
    # Cruce de medianoche: ejemplo 18:01–01:00 -> minutos >= ini O minutos <= fin
    return minutos >= ini or minutos <= fin


def etiqueta_rango(hora: Any, rangos_cfg: List[Dict[str, Any]], default: str = "Sin rango") -> str:
    """
    Devuelve el 'nombre' del rango del config que contiene 'hora'.
    'hora' puede ser time/datetime/Timestamp o str 'HH:MM(:SS)'.
    
    Args:
        hora: Objeto de tiempo en diversos formatos
        rangos_cfg: Lista de diccionarios con configuración de rangos
        default: Valor por defecto si no coincide ningún rango
        
    Returns:
        Nombre del rango que contiene la hora o valor por defecto
    """
    m = minutes_from_any(hora)
    if m is None:
        return default
    rangos = construir_rangos_cfg(rangos_cfg)
    for nombre, mi, mf in rangos:
        if en_rango_minutos(m, mi, mf):
            return nombre
    return default


# Funciones auxiliares para mantener compatibilidad con nombres originales
# TODO: Deprecar en futuras versiones cuando se complete la modularización
def _hhmmss_to_time_or_none(hh: Any) -> Optional[_time]:
    """Alias para compatibilidad hacia atrás."""
    return hhmmss_to_time_or_none(hh)

def _en_rango(t: _time, ini: _time, fin: _time) -> bool:
    """Alias para compatibilidad hacia atrás."""
    return en_rango_tiempo(t, ini, fin)

def _clasificar_rango_sv(hhmmss: str) -> Optional[str]:
    """Alias para compatibilidad hacia atrás."""
    return clasificar_rango_sv(hhmmss)

def _parse_hhmmss_to_minutes(s: Optional[str]) -> Optional[int]:
    """Alias para compatibilidad hacia atrás."""
    return parse_hhmmss_to_minutes(s)

def _minutes_from_any(hora: Any) -> Optional[int]:
    """Alias para compatibilidad hacia atrás."""
    return minutes_from_any(hora)

def _construir_rangos_cfg(rangos_cfg: List[Dict[str, Any]]) -> List[Tuple[str, int, int]]:
    """Alias para compatibilidad hacia atrás."""
    return construir_rangos_cfg(rangos_cfg)

def _en_rango_minutos(minutos: int, ini: int, fin: int) -> bool:
    """Alias para compatibilidad hacia atrás."""
    return en_rango_minutos(minutos, ini, fin)