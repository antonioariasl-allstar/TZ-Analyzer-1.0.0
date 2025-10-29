"""
tz_core.ui_utils - UTILIDADES DE INTERFAZ DE USUARIO
==================================================

✅ ESTADO: EXTRACCIÓN INCREMENTAL - HELPERS DE UI PUROS
🎯 PROPÓSITO: Funciones de interfaz de usuario y input del usuario
📍 DIFERENCIACIÓN: UI helpers sin lógica de negocio crítica

RESPONSABILIDADES ESPECÍFICAS:
- solicitar_overrides_topn(): Override temporal de configuración Top N
- Helpers de input y validación de usuario
- Funciones de interfaz sin side effects complejos

DEPENDENCIAS:
- Ninguna: Solo Python estándar (print, input, int, exception handling)

EXTRAÍDO DESDE: script_principal_bitacoras_refactory.py líneas 7322-7359
FECHA EXTRACCIÓN: 29 octubre 2025
"""

from typing import Dict, Optional, Any


def solicitar_overrides_topn(config: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """
    Pide Top N de antenas y de contactos solo para esta ejecución (override temporal).
    
    EXTRAÍDO DE: script_principal_bitacoras_refactory.py líneas 7322-7359
    
    Args:
        config: Diccionario de configuración con estructura:
                config.get('html', {}).get('top_antenas_n', default)
                config.get('html', {}).get('top_contactos_n', default)
    
    Returns:
        Dict con overrides como {'antenas': int?, 'contactos': int?} 
        o None si no se cambia nada.
        
    Functionality:
        1. Extrae valores default de configuración
        2. Solicita input del usuario para override temporal
        3. Parsea valores con validación (> 0)
        4. Maneja caso especial "mismo" para contactos = antenas
        5. Retorna dict con overrides válidos
    """
    try:
        defA = int(config.get('html', {}).get('top_antenas_n', 3))
        defC = int(config.get('html', {}).get('top_contactos_n', 10))
    except Exception:
        defA, defC = 3, 10

    print("\n( Opcional ) Ajuste de Top N para esta ejecución:")
    sa = input(f"Top N de ANTENAS (Enter={defA}): ").strip()
    sc = input(f"Top N de CONTACTOS (Enter={defC}, escribe 'mismo' para usar el de antenas): ").strip()

    ovr = {}

    def _parse(x):
        try:
            v = int(x)
            return v if v > 0 else None
        except Exception:
            return None

    if sa:
        va = _parse(sa)
        if va:
            ovr['antenas'] = va

    if sc:
        if sc.lower() == 'mismo' and 'antenas' in ovr:
            ovr['contactos'] = ovr['antenas']
        else:
            vc = _parse(sc)
            if vc:
                ovr['contactos'] = vc

    return ovr if ovr else None


# Alias para compatibilidad con nombres originales del monolito
_solicitar_overrides_topn = solicitar_overrides_topn