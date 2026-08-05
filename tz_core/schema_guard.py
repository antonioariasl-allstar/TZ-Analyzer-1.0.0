"""Schema validation guard used by the monolith pipeline.

HITO 3 — política de producto: ningún campo analítico individual (tel,
imei, fecha, hora, contacto, interaccion, antena, lat/long, azimut) es un
bloqueante global. La única razón para abortar la ejecución es que
``tz_core.capabilities.detectar_capacidades`` determine que el DataFrame
no es procesable (vacío, sin columnas, o sin ningún valor analíticamente
significativo) — es decir, un problema técnico real, no la ausencia de
una columna opcional. Un campo con formato inválido desactiva su propia
capacidad (vía ``detectar_capacidades``); no aborta el motor completo.
"""

from typing import Callable

from tz_core.bitacora_utils import coalesce_cols as _coalesce_cols, fmt_lista as _fmt_lista
from tz_core.bitacora_normalization import (
    validate_time_sample as _valida_formato_hora,
    validate_date_parsable as _valida_fecha_parsible,
    validate_latlon as _valida_latlon,
)
from tz_core.capabilities import detectar_capacidades


def validate_schema_or_abort(
    df,
    *,
    config: dict,
    logger: Callable[[str], None],
    output_fn: Callable[[str], None],
) -> bool:
    """Verifica bloqueantes globales reales y aborta solo en ese caso.

    No exige columnas esenciales (lat/long/azimut/fecha/hora/tel, etc.)
    como requisito universal: se apoya en ``detectar_capacidades`` para
    decidir si el DataFrame es procesable. Las validaciones de formato
    (hora HH:MM:SS, fecha parseable, lat/long dentro de bbox) se conservan
    como avisos informativos cuando el campo está presente, pero ya no
    abortan la ejecución por sí solas.
    """

    try:
        avisos: list = []

        if _coalesce_cols(df, "hora"):
            ok_hora, smp_h = _valida_formato_hora(df["hora"].astype(str))
            if not ok_hora:
                avisos.append(f"- 'hora' debería verse como HH:MM:SS; muestras: {_fmt_lista(smp_h)}")

        if _coalesce_cols(df, "fecha"):
            ok_fecha, smp_f = _valida_fecha_parsible(df["fecha"])
            if not ok_fecha:
                avisos.append(f"- 'fecha' no es parseable en algunas filas; muestras: {_fmt_lista(smp_f)}")

        if _coalesce_cols(df, "lat") and _coalesce_cols(df, "long", "lon"):
            bbox = (config or {}).get("geografia", {}).get("sv_bbox", None)
            if not _valida_latlon(df, bbox=bbox):
                avisos.append("- 'lat/long' no tienen registros válidos (no 0,0; dentro de SV).")

        if avisos:
            msg = (
                "\n[SCHEMA] Aviso: algunos campos presentes no cumplen el formato esperado; "
                "la(s) capacidad(es) asociada(s) quedará(n) limitada(s), pero la ejecución continúa:\n"
                + "".join(a + "\n" for a in avisos)
            )
            try:
                logger(f"[WARN][schema] {msg}")
            except Exception:
                pass
            output_fn(msg)

        report = detectar_capacidades(df, config=config)

        if not report.procesable:
            motivo = _fmt_lista(report.bloqueos_globales)
            guia = []
            guia.append("\n[SCHEMA] No se puede continuar: el archivo no tiene datos procesables.\n")
            guia.append(f"- Motivo: {motivo}\n")
            guia.append("\nSugerencias:\n")
            guia.append("• Revisá que el archivo/hoja no esté vacío.\n")
            guia.append("• Revisá que las columnas traigan valores reales (no solo placeholders vacíos).\n")
            msg = "".join(guia)
            try:
                logger(f"[FATAL][schema] {msg}")
            except Exception:
                pass
            output_fn(msg)
            raise SystemExit(2)

        try:
            logger(
                "[schema] Validación OK: datos procesables "
                "(ningún campo analítico individual bloquea la ejecución)."
            )
        except Exception:
            pass
        return True
    except SystemExit:
        raise
    except Exception:
        # En caso de error inesperado, permite continuar (comportamiento conservador)
        return True
