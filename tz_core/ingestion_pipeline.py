"""Pipeline de ingesta y normalización previo a la generación de reportes.

Extrae la orquestación que antes vivía en el monolito para dejar el DataFrame
listo tras mapeo de schema, normalización de fecha/hora y filtros de tiempo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from tz_core.manual_flow import (
    TimeFilterResult,
    apply_time_filter_prompt,
    normalize_and_validate_schema,
)
from tz_core.mapping_wizard import (
    finalize_manual_mapping_dataframe,
    normalize_wizard_datetime_fields,
)
from tz_core.bitacora_normalization import (
    normalize_temporal_fields,
    normalize_contact_fields,
    normalize_event_fields,
    clasificar_confiabilidad_duracion,
    requiere_pregunta_qc_duracion,
    preguntar_unidad_duracion_qc,
    DuracionEstado,
)
from tz_core.capabilities import Capacidad, CapabilitiesReport, detectar_capacidades
from tz_core.qc_engine import run_qc
from tz_core.site_inference import agregar_sitio_analitico
from tz_core.ui_utils import safe_input, UserCancelledError


@dataclass
class IngestionResult:
    """Resultado del pipeline de ingesta."""

    dataframe: pd.DataFrame
    time_filters: TimeFilterResult
    errores: List[str]
    duracion_encabezado_original: Optional[str] = None
    duracion_estado: Optional[DuracionEstado] = None
    capabilities_report: Optional[CapabilitiesReport] = None


# ─────────────────────────────────────────────────────────────────────────
# Resumen CLI de capacidades (HITO 2 — símbolos ASCII, compatibles con
# consola Windows sin codepage UTF-8)
# ─────────────────────────────────────────────────────────────────────────

_ETIQUETAS_CAPACIDADES_CLI: tuple[tuple[str, str], ...] = (
    ("identificacion", "Identificación"),
    ("cronologia", "Cronología"),
    ("filtros_temporales", "Filtros temporales"),
    ("antenas", "Antenas"),
    ("antenas_por_horario", "Antenas por horario"),
    ("kml", "KML"),
    ("heatmap", "Heatmap"),
    ("contactos", "Contactos"),
    ("tipo_evento", "Tipo de evento"),
    ("duracion", "Duración"),
    ("metadatos", "Metadatos"),
)

_ETIQUETA_ESTADO_CLI = {
    "disponible": "[OK]",
    "parcial": "[PARCIAL]",
    "no_disponible": "[NO DISPONIBLE]",
    "bloqueada": "[BLOQUEADA]",
}

_CAMPO_HUMANO_CLI = {
    "tel": "teléfono",
    "imei": "IMEI",
    "fecha": "fecha",
    "hora": "hora",
    "antena": "antena",
    "contacto": "contacto válido",
    "interaccion": "interacción",
    "lat": "coordenadas",
    "long": "coordenadas",
    "lat_long_validos": "coordenadas válidas",
    "azimut": "azimut",
    "duracion": "duración",
}


def _detalle_capacidad_cli(nombre: str, capacidad: Capacidad) -> Optional[str]:
    """Sufijo informativo opcional para una línea del resumen de capacidades."""
    if capacidad.estado in ("no_disponible", "bloqueada", "parcial") and capacidad.faltantes:
        campo = _CAMPO_HUMANO_CLI.get(capacidad.faltantes[0], capacidad.faltantes[0])
        prefijo = "parcial — falta" if capacidad.estado == "parcial" else "falta"
        return f"{prefijo} {campo}"
    if nombre == "duracion" and capacidad.estado == "disponible":
        partes = capacidad.motivo.split(":")
        if len(partes) >= 2 and partes[0] == "duracion_segura":
            return f"unidad confirmada: {partes[1]}"
    return None


def _formatear_linea_capacidad_cli(nombre: str, etiqueta: str, capacidad: Capacidad) -> str:
    tag = _ETIQUETA_ESTADO_CLI.get(capacidad.estado, "[?]")
    linea = f"{tag} {etiqueta}"
    detalle = _detalle_capacidad_cli(nombre, capacidad)
    if detalle:
        linea += f" — {detalle}"
    return linea


def imprimir_resumen_capacidades(
    capabilities_report: CapabilitiesReport,
    *,
    output_fn: Callable[[str], None],
) -> None:
    """Imprime el resumen de capacidades detectadas usando símbolos ASCII.

    No incluye 'hashes' (no depende de campos analíticos, no aporta al
    resumen de qué puede analizarse) ni 'orientacion' (no forma parte de la
    lista mínima solicitada para esta vista).
    """
    output_fn("\nCapacidades detectadas:\n")
    for nombre, etiqueta in _ETIQUETAS_CAPACIDADES_CLI:
        capacidad = capabilities_report.capacidad(nombre)
        output_fn(_formatear_linea_capacidad_cli(nombre, etiqueta, capacidad))


def resolve_date_dayfirst(
    df: pd.DataFrame,
    *,
    config: Optional[Dict[str, Any]],
    prompt_fn: Callable[[str], str] = safe_input,
    output_fn: Optional[Callable[[str], None]] = None,
) -> bool:
    """Resuelve el orden de fechas antes de normalizarlas.

    ``excel.date_order`` admite ``DMY``, ``MDY`` o ``ASK``. En modo ``ASK``
    se decide automáticamente cuando una de las dos primeras posiciones es
    mayor que 12; si todas las muestras son ambiguas, se solicita confirmación.
    """
    out = output_fn or (lambda _msg: None)
    excel_cfg = ((config or {}).get("excel") or {})
    configured = str(excel_cfg.get("date_order", "DMY")).strip().upper()

    if configured == "DMY":
        return True
    if configured == "MDY":
        return False
    if configured not in {"ASK", "AUTO"}:
        raise ValueError(
            "excel.date_order debe ser DMY, MDY, ASK o AUTO; "
            f"se recibió {configured!r}"
        )

    if "fecha" not in df.columns:
        return True

    samples = df["fecha"].dropna().astype(str).str.strip()
    parts = samples.str.extract(r"^(\d{1,2})[/-](\d{1,2})[/-]\d{4}(?:\D|$)")
    parts = parts.dropna().astype(int)
    if parts.empty:
        return True

    first_over_12 = bool((parts[0] > 12).any())
    second_over_12 = bool((parts[1] > 12).any())
    if first_over_12 and second_over_12:
        raise ValueError(
            "La columna fecha mezcla formatos DD/MM y MM/DD; "
            "corrija el archivo antes de continuar."
        )
    if first_over_12:
        return True
    if second_over_12:
        return False

    out("\n[FECHAS] Todas las fechas muestreadas son ambiguas (día y mes <= 12).")
    out("  [1] DD/MM/AAAA  — día/mes/año")
    out("  [2] MM/DD/AAAA  — mes/día/año")
    while True:
        response = prompt_fn("  → Formato del archivo (1/2, C=cancelar): ").strip().upper()
        if response == "1":
            return True
        if response == "2":
            return False
        if response == "C":
            raise UserCancelledError("Importación cancelada al confirmar el formato de fecha.")
        out("  Opción inválida. Escriba 1, 2 o C.")


def run_ingestion_pipeline(
    *,
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]],
    original_columns: List[str],
    manual_qc_mapping: bool,
    alias_visibles: Optional[List[str]],
    wizard_io_factory: Callable[[], Any],
    persist_synonym_fn: Callable[..., None],
    validate_schema_fn: Callable[[pd.DataFrame], None],
    validar_datos_fn: Callable[[pd.DataFrame, List[str]], tuple[pd.DataFrame, List[str]]],
    time_filter_option: str,
    solicitar_filtros_fn: Callable[[], Any],
    aplicar_filtros_fn: Callable[[pd.DataFrame, Any], tuple[pd.DataFrame, str]],
    logger: Optional[Callable[[str], None]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    run_manual_mapping_fn: Optional[Callable[..., Any]] = None,
    config_path: str = "config.json",
    preguntar_unidad_duracion_fn: Callable[[], str] = preguntar_unidad_duracion_qc,
) -> IngestionResult:
    """Ejecuta normalización de schema, QC manual opcional y filtros de tiempo.

    Devuelve el DataFrame listo para downstream junto con los filtros aplicados
    y cualquier lista de errores de validación devuelta por el validador.
    """

    log = logger or (lambda _msg: None)
    out = output_fn or (lambda _msg: None)
    cfg = config or {}

    # HITO 4: columnas_normalizables (antes columnas_esenciales) indica qué
    # columnas reciben normalización de formato en validar_datos_fn — no es
    # un requisito global del motor (ver tz_core.capabilities).
    columnas_normalizables = (
        (cfg.get("entradas") or {}).get("columnas_normalizables") or ["antena", "lat", "long"]
    )
    if "long" in columnas_normalizables and "lon" not in columnas_normalizables:
        columnas_normalizables = list(dict.fromkeys(list(columnas_normalizables) + ["lon"]))

    df_norm = normalize_and_validate_schema(
        df=df,
        config=cfg,
        original_columns=original_columns,
        manual_qc_mapping=manual_qc_mapping,
        alias_visibles=alias_visibles,
        wizard_io_factory=wizard_io_factory,
        persist_synonym_fn=persist_synonym_fn,
        validate_schema_fn=validate_schema_fn,
        logger=log,
        output_fn=out,
        config_path=config_path,
    )

    duracion_encabezado_original: Optional[str] = None
    if manual_qc_mapping and run_manual_mapping_fn:
        out("\n[QC] Iniciando wizard QC (mapeo manual).")
        wizard_io = wizard_io_factory()
        df_norm, mapeo_asignaciones = run_manual_mapping_fn(df_norm, wizard_io=wizard_io)
        df_norm = finalize_manual_mapping_dataframe(df_norm)

        duracion_asignada = mapeo_asignaciones.get("duracion")
        if duracion_asignada and duracion_asignada[0] == "col":
            duracion_encabezado_original = duracion_asignada[1]

    dayfirst = resolve_date_dayfirst(
        df_norm,
        config=cfg,
        prompt_fn=safe_input,
        output_fn=out,
    )
    df_norm = normalize_temporal_fields(df_norm, dayfirst=dayfirst)
    df_norm = normalize_event_fields(df_norm, col_tipo="interaccion")
    df_norm = normalize_contact_fields(df_norm)
    df_norm = normalize_wizard_datetime_fields(
        df_norm,
        warn_writer=lambda msg: out(msg),
        dayfirst=dayfirst,
    )

    df_norm, errores = validar_datos_fn(df_norm, columnas_normalizables)

    duracion_estado = clasificar_confiabilidad_duracion(
        df_norm,
        encabezado_original=duracion_encabezado_original,
    )
    if requiere_pregunta_qc_duracion(duracion_estado):
        unidad_respuesta = preguntar_unidad_duracion_fn()
        duracion_estado = clasificar_confiabilidad_duracion(
            df_norm,
            encabezado_original=duracion_encabezado_original,
            unidad_declarada=unidad_respuesta,
        )

    # --- Inferencia de identidad analítica de sitio (HITO 2A) — se ejecuta
    # una sola vez, después de la normalización/mapeo/validación técnica y
    # antes de detectar_capacidades/run_qc, para que ambos consumidores vean
    # ya antena_analitica/sitio_inferido. Resuelve columnas por los nombres
    # canónicos (antena/lat/long) ya normalizados arriba; no muta df_norm ni
    # sobrescribe la antena original.
    bbox_cfg = ((cfg.get("geografia") or {}).get("sv_bbox"))
    df_norm = agregar_sitio_analitico(df_norm, bbox=bbox_cfg)

    # --- Capacidades analíticas (HITO 2) — se calcula una sola vez, con el
    # df normalizado y la duracion_estado ya definitiva, y se reutiliza tanto
    # para el resumen CLI como para la decisión de aborto más abajo. ---
    capabilities_report = detectar_capacidades(
        df_norm,
        duracion_estado=duracion_estado,
        config=cfg,
    )

    # --- QC Engine ---
    try:
        qc_result = run_qc(df_norm)
    except Exception as e:
        logging.error(f"[QC] run_qc falló inesperadamente: {type(e).__name__}: {e}")
        qc_result = None
    if qc_result is not None:
        out("")
        for linea in qc_result.resumen:
            out(f"  {linea}")
        out(f"\nCompletitud del archivo para análisis integral: {qc_result.score}/100")

    imprimir_resumen_capacidades(capabilities_report, output_fn=out)

    if not capabilities_report.procesable:
        out("\n[BLOQUEADO] El archivo no tiene datos procesables — no se puede continuar.")
        out(f"  Motivo: {', '.join(capabilities_report.bloqueos_globales)}")
        import sys
        sys.exit(0)

    # Salvaguarda para errores técnicos reales no modelados como capacidades
    # (p.ej. una futura condición de run_qc distinta de la ausencia de campos
    # analíticos). En la práctica, con capabilities_report.procesable ya
    # validado arriba, este bloqueante ya no se activa por contacto,
    # interaccion, fecha, hora, coordenadas o antena ausentes.
    if qc_result is not None and qc_result.bloqueante:
        out("\n⚠️  ADVERTENCIA: se detectó un problema técnico que puede comprometer el análisis.")
        respuesta = safe_input("¿Desea continuar de todas formas? (S/N, C=cancelar): ").upper()
        if respuesta != "S":
            import sys
            sys.exit(0)

    time_filters: TimeFilterResult = apply_time_filter_prompt(
        option=time_filter_option,
        df=df_norm,
        solicitar_fn=solicitar_filtros_fn,
        aplicar_fn=aplicar_filtros_fn,
        output_fn=out,
    )

    return IngestionResult(
        dataframe=time_filters.dataframe,
        time_filters=time_filters,
        errores=list(errores or []),
        duracion_encabezado_original=duracion_encabezado_original,
        duracion_estado=duracion_estado,
        capabilities_report=capabilities_report,
    )
