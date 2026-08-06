"""Clasificador básico de tipo de interacción para QC Engine.

Clasifica cada registro de una bitácora en: VOZ, SMS, DATOS, DESCONOCIDO.
Función pura sin side effects. No modifica datos, solo clasifica.
"""

from __future__ import annotations
import pandas as pd

from tz_core.event_classification import classify_event_type


def classify_single(value) -> str:
    """Clasifica un valor individual de tipo de interacción.

    Delegado a `tz_core.event_classification.classify_event_type` — fuente
    única de verdad compartida con `normalize_event_fields` (P0-B) para que
    ambos clasifiquen igual el mismo valor. Ver
    docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §10.
    """
    return classify_event_type(value)


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
