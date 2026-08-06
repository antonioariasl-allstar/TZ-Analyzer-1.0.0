"""Fuente única de verdad para clasificación de tipo de evento (VOZ/SMS/DATOS).

Reutilizada por `bitacora_normalization.normalize_event_fields` (P0-B) y por
`qc_type_classifier.classify_single` (score de completitud QC) para que ambos
módulos clasifiquen igual el mismo valor crudo. Ver
docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §10 para el diseño aprobado.

Módulo sin dependencias de `tz_core` (solo stdlib) para no introducir ciclos
de importación con `bitacora_normalization.py` ni `qc_type_classifier.py`.
"""

from __future__ import annotations

import re
from typing import Dict, List

# Términos cortos/genéricos con riesgo real de coincidir por accidente dentro
# de un valor más largo no relacionado (nombre de antena, texto libre). Estos
# exigen coincidencia de token completo (delimitado por no alfanuméricos) en
# vez de subcadena simple. El resto de términos se considera seguro con "in"
# simple (ver docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §10).
_TOKEN_MATCH_TERMS = frozenset({"WAP", "NAV", "TEXT", "SHORT", "RING"})

# Orden importa: DATOS primero para que "GPRS"/"PDP"/etc. no queden atrapados
# por un término genérico de otra categoría evaluado antes.
_KEYWORDS: Dict[str, List[str]] = {
    "DATOS": [
        "DATA", "DATOS", "GPRS", "INTERNET", "NAV", "NAVEGACION",
        "BROWSE", "WAP", "APN", "PDP",
    ],
    "SMS": [
        "SMS", "MENSAJE", "MESSAGE", "TEXT", "MO-SMS", "MT-SMS",
        "SHORT", "SMSC",
    ],
    "VOZ": [
        "CALL", "VOZ", "VOICE", "MTC", "MOC", "MFC",
        "INCOMING", "OUTGOING", "ENTRANTE", "SALIENTE",
        "LLAMADA", "RING", "CONFERENCE", "CONF",
    ],
}

_PLACEHOLDER_VALUES = frozenset({
    "NAN", "NONE", "NULL", "N/A", "NA", "SIN INF.", "SIN INF", "S/I", "--",
})


def _contiene_termino(text: str, termino: str) -> bool:
    if termino in _TOKEN_MATCH_TERMS:
        return re.search(rf"\b{re.escape(termino)}\b", text) is not None
    return termino in text


def classify_event_type(value: object) -> str:
    """Clasifica un valor crudo de tipo de interacción en VOZ/SMS/DATOS/DESCONOCIDO."""
    if value is None:
        return "DESCONOCIDO"
    text = str(value).strip().upper()
    if not text or text in _PLACEHOLDER_VALUES:
        return "DESCONOCIDO"
    for categoria, keywords in _KEYWORDS.items():
        for kw in keywords:
            if _contiene_termino(text, kw):
                return categoria
    return "DESCONOCIDO"


__all__ = ["classify_event_type"]
