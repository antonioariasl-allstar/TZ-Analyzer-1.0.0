"""tz_web.scope — fuente única de presentación del "Alcance" de un análisis.

Traduce ``case.filtro_tiempo``/``CaseRequest.filtro_tiempo`` (mismo contrato
que ``tz_core.time_filters.FiltroTiempo``: ``None`` = bitácora completa, o un
dict con ``tipo``/``dia``/``desde``/``hasta``/``hora_ini``/``hora_fin``) a un
texto legible, reutilizable tanto antes de ejecutar el análisis (Resumen)
como después (Resultados). No depende de ``tz_web.state`` ni
``tz_web.services`` (módulo hoja, sin ciclos de import) y no toca
``tz_core.time_filters`` — es puramente de presentación.

No incluye el prefijo "Alcance:": las plantillas que lo consumen ya rotulan
la etiqueta por separado (ver sección 4 del microbloque Modo 2, parte 2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

FiltroTiempo = Optional[Dict[str, Optional[str]]]

# Los campos de fecha llegan como ISO (controles HTML <input type="date">,
# ver configure_filtro_tiempo.html) o, en la Configuración heredada
# (configure.html), con el mismo control — se acepta DD/MM/AAAA además por
# si algún caso ya persistido usa ese formato.
_FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y")


def parse_fecha_iso(valor: Optional[str]) -> Optional[datetime]:
    """Parsea una fecha almacenada en ``filtro_tiempo`` a ``datetime``.

    Devuelve ``None`` si ``valor`` está vacío o no calza con ninguno de los
    formatos soportados, en vez de lanzar — quien llama decide qué hacer
    ante una fecha no reconocida (ver ``describir_alcance``/validación web)."""
    if not valor:
        return None
    texto = valor.strip()
    for formato in _FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def describir_alcance(filtro_tiempo: FiltroTiempo) -> str:
    """Texto de presentación del alcance temporal de un análisis.

    Modo 1 (o Modo 2 sin selección todavía) siempre llega aquí con
    ``filtro_tiempo=None`` -> "Bitácora completa". Para Modo 2 produce un
    texto natural por tipo de filtro (sección 4 del microbloque)."""
    if not filtro_tiempo:
        return "Bitácora completa"

    tipo = filtro_tiempo.get("tipo")

    if tipo == "dia":
        dia = parse_fecha_iso(filtro_tiempo.get("dia"))
        if dia is not None:
            return f"Día {dia.day} del mes {dia.month} del año {dia.year}"

    elif tipo == "rango_dias":
        desde = parse_fecha_iso(filtro_tiempo.get("desde"))
        hasta = parse_fecha_iso(filtro_tiempo.get("hasta"))
        if desde is not None and hasta is not None:
            return f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"

    elif tipo == "rango_horas":
        hora_ini = (filtro_tiempo.get("hora_ini") or "").strip()[:5]
        hora_fin = (filtro_tiempo.get("hora_fin") or "").strip()[:5]
        if hora_ini and hora_fin:
            return f"De {hora_ini} a {hora_fin}, aplicado a todos los días de la bitácora"

    elif tipo == "rango_horas_dia":
        dia = parse_fecha_iso(filtro_tiempo.get("dia"))
        hora_ini = (filtro_tiempo.get("hora_ini") or "").strip()[:5]
        hora_fin = (filtro_tiempo.get("hora_fin") or "").strip()[:5]
        if dia is not None and hora_ini and hora_fin:
            return f"{dia:%d/%m/%Y}, de {hora_ini} a {hora_fin}"

    # Defensivo: un filtro presente pero con datos que no se pudieron leer
    # (no debería ocurrir tras la validación web) nunca debe presentarse
    # como si no hubiera filtro alguno.
    return "Filtro temporal aplicado"
