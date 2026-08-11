"""tz_web.field_catalog — catálogo central de los 14 campos canónicos.

Única fuente de verdad para cómo se PRESENTAN los campos canónicos del
mapeo en la capa web (etiqueta visible, descripción breve, grupo de
agrupación visual y orden dentro de su grupo). No redefine ni reinterpreta
las claves internas del motor (``tz_core.field_roles``/``tz_core.mapping_wizard``)
— esas claves (``fecha``, ``hora``, ``tel``, etc.) se mantienen intactas y
siguen siendo las que ``tz_web.services``/``tz_core`` esperan.

Las plantillas (mapeo, revisión horizontal, y cualquier pantalla futura que
necesite mostrar estos 14 campos) deben leer las etiquetas/grupos de aquí
en vez de hardcodearlas, para que exista un único lugar que editar si algún
día cambia una etiqueta o el agrupamiento visual.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, NamedTuple, Tuple

# ---------------------------------------------------------------------------
# Grupos visuales (orden de presentación) — 7 grupos de 2 campos cada uno.
# ---------------------------------------------------------------------------

FIELD_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Tiempo", ("fecha", "hora")),
    ("Evento", ("duracion", "interaccion")),
    ("Telefonía", ("tel", "contacto")),
    ("Identificación técnica", ("imei", "imsi")),
    ("Ubicación", ("lat", "long")),
    ("Cobertura", ("azimut", "antena")),
    ("Antena", ("celda", "direccion")),
)

_LABELS: Dict[str, str] = {
    "fecha": "Fecha",
    "hora": "Hora",
    "duracion": "Duración",
    "interaccion": "Tipo de interacción",
    "tel": "Número analizado",
    "contacto": "Contacto",
    "imei": "IMEI",
    "imsi": "IMSI",
    "lat": "Latitud",
    "long": "Longitud",
    "azimut": "Azimut",
    "antena": "Antena",
    "celda": "Celda",
    "direccion": "Dirección",
}

_DESCRIPTIONS: Dict[str, str] = {
    "fecha": "Fecha del evento telefónico.",
    "hora": "Hora del evento telefónico.",
    "duracion": "Duración registrada del evento.",
    "interaccion": "Clasificación del evento, por ejemplo voz, SMS o datos.",
    "tel": "Número telefónico objeto del análisis.",
    "contacto": "Número con el que interactuó el número analizado.",
    "imei": "Identificador del dispositivo asociado al evento.",
    "imsi": "Identificador de la SIM asociada al evento.",
    "lat": "Coordenada geográfica de la antena.",
    "long": "Coordenada geográfica de la antena.",
    "azimut": "Orientación de cobertura de la antena.",
    "antena": "Identificador o nombre de la antena, torre o sitio (Site ID). Ejemplo: \"Sitio 042 - Zona Norte\".",
    "celda": "Identificador de la celda.",
    "direccion": (
        "Dirección física, ubicación o dirección de cobertura asociada a la antena. "
        "Ejemplo: columnas como \"Lugares de Cobertura\"."
    ),
}


class FieldEntry(NamedTuple):
    key: str
    label: str
    description: str
    group: str
    order: int


def _build_catalog() -> "OrderedDict[str, FieldEntry]":
    catalog: "OrderedDict[str, FieldEntry]" = OrderedDict()
    order = 1
    for group_name, fields in FIELD_GROUPS:
        for key in fields:
            catalog[key] = FieldEntry(
                key=key,
                label=_LABELS[key],
                description=_DESCRIPTIONS[key],
                group=group_name,
                order=order,
            )
            order += 1
    return catalog


# Los 14 campos canónicos, en el mismo orden de presentación que FIELD_GROUPS.
FIELD_CATALOG: "OrderedDict[str, FieldEntry]" = _build_catalog()

CANONICAL_FIELDS: Tuple[str, ...] = tuple(FIELD_CATALOG.keys())

FIELD_LABELS: Dict[str, str] = {key: entry.label for key, entry in FIELD_CATALOG.items()}
FIELD_DESCRIPTIONS: Dict[str, str] = {key: entry.description for key, entry in FIELD_CATALOG.items()}


def label_for(field: str) -> str:
    entry = FIELD_CATALOG.get(field)
    return entry.label if entry else field


def description_for(field: str) -> str:
    entry = FIELD_CATALOG.get(field)
    return entry.description if entry else ""
