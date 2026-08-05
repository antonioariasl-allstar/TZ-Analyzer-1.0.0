"""Health and dataset sanity helpers shared across pipelines."""

from typing import Callable, Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from tz_core.capabilities import CapabilitiesReport


def log_dataset_stats(stage: str, df: pd.DataFrame, logger: Optional[Callable[[str], None]] = None) -> None:
    """Log basic dataset counters for a given stage."""

    logger = logger or (lambda msg: None)
    try:
        total = len(df)
        cols = len(df.columns)
        lat_ok = 0
        if "lat" in df.columns and ("long" in df.columns or "lon" in df.columns):
            lat_series = pd.to_numeric(df.get("lat"), errors="coerce")
            lon_series = pd.to_numeric(df.get("long", df.get("lon")), errors="coerce")
            lat_ok = int((lat_series.notna() & lon_series.notna()).sum())

        hora_missing = None
        if "hora" in df.columns:
            hora_missing = int(df["hora"].isna().sum())

        parts = [f"[{stage}] filas={total}", f"cols={cols}"]
        if lat_ok:
            parts.append(f"coord_validas={lat_ok}")
        if hora_missing is not None:
            parts.append(f"horas_sin_inf={hora_missing}")

        logger(" ".join(parts))
    except Exception:
        pass


def _describir_limitaciones(capabilities_report: "CapabilitiesReport") -> list[str]:
    """Traduce capacidades no disponibles/parciales a líneas informativas.

    Puramente informativo: nunca dispara un prompt ni bloquea la ejecución.
    """
    etiquetas = {
        "kml": "KML",
        "heatmap": "Heatmap",
        "antenas": "Antenas nominales",
        "antenas_por_horario": "Antenas por horario",
        "cronologia": "Cronología (fecha/hora)",
        "identificacion": "Identificación (tel/imei)",
        "contactos": "Contactos",
        "tipo_evento": "Tipo de evento",
        "duracion": "Duración",
        "orientacion": "Orientación (azimut)",
    }
    lineas = []
    for nombre, etiqueta in etiquetas.items():
        capacidad = capabilities_report.capacidades.get(nombre)
        if capacidad is None:
            continue
        if capacidad.estado == "no_disponible":
            lineas.append(f"[health] {etiqueta}: no disponible ({capacidad.motivo}).")
        elif capacidad.estado == "parcial":
            lineas.append(f"[health] {etiqueta}: parcial ({capacidad.motivo}).")
    return lineas


def run_health_checks(
    df: pd.DataFrame,
    *,
    min_coord_ratio: float = 0.05,
    max_hora_missing_ratio: float = 0.25,
    logger: Optional[Callable[[str], None]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    capabilities_report: Optional["CapabilitiesReport"] = None,
) -> bool:
    """Validate minimal signal before generating outputs; return True to proceed.

    HITO 3 — cuando se provee ``capabilities_report`` (ver
    ``tz_core.capabilities.detectar_capacidades``), la decisión de
    aborto/continuación se delega en él:

    - ``procesable=False`` -> aborta (sin prompt: ya es una decisión tomada
      aguas arriba por un bloqueante global real).
    - ``procesable=True`` -> informa qué capacidades quedan no disponibles
      o parciales (coords, hora, etc. por separado, no en un único prompt
      genérico) y continúa sin preguntar nada por esos faltantes
      analíticos.

    Sin ``capabilities_report`` (compatibilidad con llamadores que aún no
    lo propagan), conserva el comportamiento anterior: solo el DataFrame
    vacío bloquea de forma dura; las demás señales (coords, hora) generan
    un prompt de confirmación, ya que en ese caso no hay una fuente
    centralizada que ya haya evaluado si son riesgos reales o capacidades
    simplemente no disponibles.
    """

    logger = logger or (lambda msg: None)
    output_fn = output_fn or (lambda msg: None)
    input_fn = input_fn or input

    try:
        total = len(df)
        if total == 0:
            msg = "[health] No hay registros para procesar después de filtros."
            try:
                logger(msg)
            except Exception:
                pass
            output_fn(msg)
            return False

        if capabilities_report is not None:
            if not capabilities_report.procesable:
                motivo = ", ".join(capabilities_report.bloqueos_globales) or "sin_datos_procesables"
                msg = f"[health] Bloqueante global: {motivo}."
                try:
                    logger(msg)
                except Exception:
                    pass
                output_fn(msg)
                output_fn("Ejecución detenida: el archivo no tiene datos procesables.")
                return False

            for linea in _describir_limitaciones(capabilities_report):
                try:
                    logger(linea)
                except Exception:
                    pass
                output_fn(linea)

            try:
                logger("[health] OK: procesable=True; continúa sin prompt por faltantes analíticos.")
            except Exception:
                pass
            return True

        # --- Compatibilidad sin CapabilitiesReport (comportamiento previo) ---
        lat_ok = 0
        if "lat" in df.columns and ("long" in df.columns or "lon" in df.columns):
            lat_series = pd.to_numeric(df.get("lat"), errors="coerce")
            lon_series = pd.to_numeric(df.get("long", df.get("lon")), errors="coerce")
            lat_ok = int((lat_series.notna() & lon_series.notna()).sum())

        hora_missing = None
        if "hora" in df.columns:
            hora_missing = int(df["hora"].isna().sum())

        warnings_found = []

        if lat_ok == 0:
            warnings_found.append("[health] No hay coordenadas válidas (lat/long).")
        else:
            coord_ratio = lat_ok / total
            if coord_ratio < min_coord_ratio:
                warnings_found.append(
                    f"[health] Solo {lat_ok} de {total} filas tienen coordenadas ({coord_ratio:.1%})."
                )

        if hora_missing is not None and hora_missing > 0:
            hora_ratio = hora_missing / total
            if hora_ratio > max_hora_missing_ratio:
                warnings_found.append(
                    f"[health] {hora_missing} filas sin hora ({hora_ratio:.1%}); revisá la normalización."
                )

        if not warnings_found:
            try:
                logger("[health] OK: señales mínimas suficientes para continuar.")
            except Exception:
                pass
            return True

        for w in warnings_found:
            try:
                logger(w)
            except Exception:
                pass
            output_fn(w)

        try:
            resp = (input_fn("Continuar a salidas a pesar de las alertas? [s/N]: ") or "").strip().lower()
        except Exception:
            resp = ""

        if resp in {"s", "si", "y", "yes"}:
            try:
                logger("[health] Continuando bajo responsabilidad del usuario.")
            except Exception:
                pass
            return True

        try:
            logger("[health] Ejecución abortada por alertas de calidad.")
        except Exception:
            pass
        output_fn("Ejecución detenida por salud insuficiente. Ajustá los datos y reintenta.")
        return False
    except Exception:
        # If any unexpected error occurs, allow continuation to avoid blocking the flow.
        return True
