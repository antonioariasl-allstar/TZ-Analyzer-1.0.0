"""Clasificación única de campos canónicos de mapeo (HITO 3/4).

Único punto de verdad para qué campos existen y a qué grupo funcional /
capacidad de análisis pertenecen. Reemplaza las listas paralelas que antes
vivían duplicadas (e incluso contradichas entre sí) en ``mapping_wizard.py``
y ``manual_mapping_helpers.py``.

Ningún campo aparece en más de un grupo funcional. HITO 4 elimina el
vocabulario "esencial/no esencial" de este módulo: los nombres
``WIZARD_ORDER_PRIMARY``/``WIZARD_ORDER_SECONDARY`` describen únicamente el
orden de presentación en el wizard (qué se pregunta primero, con
navegación hacia atrás) — no implican que el motor aborte si el campo
falta. La única condición de aborto global vive en ``tz_core.capabilities``
(DataFrame vacío, sin datos procesables o error técnico).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────────────────
# Grupos funcionales — cada uno habilita una o más capacidades analíticas
# (ver tz_core.capabilities.detectar_capacidades).
# ─────────────────────────────────────────────────────────────────────────

IDENTIFICACION_FIELDS: Tuple[str, ...] = ("tel", "imei")
CRONOLOGIA_FIELDS: Tuple[str, ...] = ("fecha", "hora")
GEOLOCALIZACION_FIELDS: Tuple[str, ...] = ("antena", "lat", "long", "azimut")
COMUNICACIONES_FIELDS: Tuple[str, ...] = ("contacto", "interaccion", "duracion")
COMPLEMENTARIOS_FIELDS: Tuple[str, ...] = ("celda", "direccion", "imsi")
IDENTITY_METADATA_FIELDS: Tuple[str, ...] = ("alias", "nombre_usuario", "abonado")

FIELD_CATEGORIES: Dict[str, Tuple[str, ...]] = {
    "identificacion": IDENTIFICACION_FIELDS,
    "cronologia": CRONOLOGIA_FIELDS,
    "geolocalizacion": GEOLOCALIZACION_FIELDS,
    "comunicaciones": COMUNICACIONES_FIELDS,
    "complementarios": COMPLEMENTARIOS_FIELDS + IDENTITY_METADATA_FIELDS,
}

CATEGORY_LABELS: Dict[str, str] = {
    "identificacion": "Identificación",
    "cronologia": "Cronología",
    "geolocalizacion": "Geolocalización",
    "comunicaciones": "Comunicaciones",
    "complementarios": "Complementarios",
}

# Alias retenido por claridad semántica en manual_mapping_helpers.py /
# mapping_wizard.py: campos de identidad que el wizard pregunta por
# separado (overrides de alias/nombre_usuario/abonado), fuera del loop
# primario/secundario.
IDENTITY_FIELDS: Tuple[str, ...] = IDENTITY_METADATA_FIELDS

# Orden de presentación en el wizard: primero lo que habilita identificación,
# cronología, comunicaciones (contacto/interaccion) y geolocalización.
WIZARD_ORDER_PRIMARY: Tuple[str, ...] = (
    "fecha",
    "hora",
    "tel",
    "imei",
    "interaccion",
    "contacto",
    "lat",
    "long",
    "azimut",
    "antena",
)

# Resto de comunicaciones (duracion) + complementarios que no son campos de
# identidad (esos se preguntan aparte). Ningún campo se repite respecto de
# WIZARD_ORDER_PRIMARY.
WIZARD_ORDER_SECONDARY: Tuple[str, ...] = ("celda", "direccion", "imsi", "duracion")


def all_categorized_fields() -> List[str]:
    """Todos los campos únicos de la clasificación, en orden estable."""
    seen: List[str] = []
    for fields in FIELD_CATEGORIES.values():
        for field in fields:
            if field not in seen:
                seen.append(field)
    return seen


def category_of(field: str) -> str | None:
    """Devuelve la categoría a la que pertenece ``field``, si existe."""
    for category, fields in FIELD_CATEGORIES.items():
        if field in fields:
            return category
    return None


__all__ = [
    "IDENTIFICACION_FIELDS",
    "CRONOLOGIA_FIELDS",
    "GEOLOCALIZACION_FIELDS",
    "COMUNICACIONES_FIELDS",
    "COMPLEMENTARIOS_FIELDS",
    "IDENTITY_METADATA_FIELDS",
    "FIELD_CATEGORIES",
    "CATEGORY_LABELS",
    "IDENTITY_FIELDS",
    "WIZARD_ORDER_PRIMARY",
    "WIZARD_ORDER_SECONDARY",
    "all_categorized_fields",
    "category_of",
]
