"""Clasificador básico de tipo de interacción para QC Engine.

Clasifica cada registro de una bitácora en: VOZ, SMS, DATOS, DESCONOCIDO.
Función pura sin side effects. No modifica datos, solo clasifica.
"""

from __future__ import annotations
import pandas as pd
from typing import Dict

# Keywords por categoría — se buscan con "in" sobre el texto uppercased.
# Orden importa: DATOS primero (para que "GPRS" no matchee con otra cosa).
_KEYWORDS: Dict[str, list[str]] = {
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


def classify_single(value) -> str:
    """Clasifica un valor individual de tipo de interacción."""
    if value is None:
        return "DESCONOCIDO"
    text = str(value).strip().upper()
    if not text or text in ("NAN", "NONE", "NULL", "N/A", "NA", "SIN INF.", "SIN INF", "S/I", "--"):
        return "DESCONOCIDO"
    for category, keywords in _KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "DESCONOCIDO"


def classify_interaction_type(series: pd.Series) -> pd.Series:
    """Clasifica una columna completa de tipos de interacción.

    Parameters
    ----------
    series : pd.Series
        Columna con valores crudos de tipo de interacción.

    Returns
    -------
    pd.Series
        Serie con valores VOZ, SMS, DATOS o DESCONOCIDO.
    """
    return series.map(classify_single)


def get_type_summary(classified: pd.Series) -> dict:
    """Genera resumen de conteos y porcentajes por categoría.

    Parameters
    ----------
    classified : pd.Series
        Serie ya clasificada (output de classify_interaction_type).

    Returns
    -------
    dict
        {"VOZ": {"count": n, "pct": float}, ...}
    """
    total = len(classified)
    if total == 0:
        return {}
    counts = classified.value_counts()
    return {
        cat: {
            "count": int(counts.get(cat, 0)),
            "pct": round(counts.get(cat, 0) / total * 100, 1),
        }
        for cat in ["VOZ", "SMS", "DATOS", "DESCONOCIDO"]
    }
