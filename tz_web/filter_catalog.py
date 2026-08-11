"""tz_web.filter_catalog — catálogo central de los filtros temporales del
Modo 2 (bitácora filtrada por tiempo).

Única fuente de verdad para cómo se PRESENTAN los cuatro tipos de filtro
temporal en la capa web (etiqueta, utilidad, qué hará y ejemplo). No
redefine el contrato de datos que ya usa ``case.filtro_tiempo``/
``CaseRequest`` (claves ``tipo``/``dia``/``desde``/``hasta``/``hora_ini``/
``hora_fin``) — esas claves siguen siendo las que ``tz_web.services``/
``tz_core`` esperan. Pensado para reutilizarse también en Resumen/
Resultados cuando lo necesiten, sin duplicar estos textos en cada plantilla.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import NamedTuple, Tuple


class FiltroTiempoEntry(NamedTuple):
    key: str
    label: str
    utilidad: str
    hara: str
    ejemplo: str


FILTRO_TIEMPO_ORDER: Tuple[str, ...] = ("dia", "rango_dias", "rango_horas", "rango_horas_dia")

FILTRO_TIEMPO_CATALOG: "OrderedDict[str, FiltroTiempoEntry]" = OrderedDict(
    (
        (
            "dia",
            FiltroTiempoEntry(
                key="dia",
                label="Día específico",
                utilidad="Analizar toda la actividad registrada durante una fecha determinada.",
                hara="Conservará únicamente los eventos correspondientes al día seleccionado.",
                ejemplo="Día X del mes X del año XXXX.",
            ),
        ),
        (
            "rango_dias",
            FiltroTiempoEntry(
                key="rango_dias",
                label="Rango de fechas",
                utilidad="Examinar la actividad desarrollada durante un período concreto de varios días.",
                hara=(
                    "Conservará los eventos comprendidos entre la fecha inicial y la fecha final, "
                    "incluyendo ambos días."
                ),
                ejemplo="Del día X al día Y del mes X del año XXXX.",
            ),
        ),
        (
            "rango_horas",
            FiltroTiempoEntry(
                key="rango_horas",
                label="Rango de horas",
                utilidad=(
                    "Identificar patrones de actividad asociados a una misma franja horaria a lo "
                    "largo de los distintos días de la bitácora."
                ),
                hara=(
                    "Conservará, en cada día disponible, únicamente los eventos comprendidos "
                    "dentro del horario seleccionado."
                ),
                ejemplo="Actividad registrada entre las 20:00 y las 00:00 horas durante los días contenidos en la bitácora.",
            ),
        ),
        (
            "rango_horas_dia",
            FiltroTiempoEntry(
                key="rango_horas_dia",
                label="Rango de horas en un día específico",
                utilidad="Examinar una ventana temporal directamente relacionada con un hecho puntual ocurrido en una fecha determinada.",
                hara=(
                    "Conservará únicamente los eventos del día seleccionado comprendidos entre la "
                    "hora inicial y final indicadas."
                ),
                ejemplo="Actividad registrada entre las 20:00 y las 23:30 horas del día X del mes X del año XXXX.",
            ),
        ),
    )
)
