"""Schema validation guard used by the monolith pipeline."""

from typing import Any, Callable, Iterable

from tz_core.bitacora_utils import coalesce_cols as _coalesce_cols, fmt_lista as _fmt_lista
from tz_core.bitacora_normalization import (
    validate_time_sample as _valida_formato_hora,
    validate_date_parsable as _valida_fecha_parsible,
    validate_latlon as _valida_latlon,
)


def validate_schema_or_abort(
    df,
    *,
    config: dict,
    logger: Callable[[str], None],
    output_fn: Callable[[str], None],
) -> bool:
    """Validate minimal schema/typing and abort execution with guidance if invalid."""

    try:
        esenciales_cfg: Iterable[str] = (config or {}).get("entradas", {}).get("columnas_esenciales", []) or []
        esenciales = set(esenciales_cfg)
        if "long" in esenciales and "lon" not in esenciales:
            esenciales.add("lon")

        headers = list(df.columns)
        faltan = [c for c in esenciales if c not in headers]
        if "long" in faltan and "lon" in headers:
            faltan.remove("long")
        if "lon" in faltan and "long" in headers:
            faltan.remove("lon")

        alts = (config or {}).get("schema", {}).get("location_alternatives", []) or []

        def _alt_ok(alt_group):
            """Verifica si existe al menos una columna válida del grupo alternativo en el DataFrame."""
            cols_needed = []
            for c in alt_group:
                if c == "lon":
                    cols_needed.append(_coalesce_cols(df, "long", "lon"))
                else:
                    cols_needed.append(c if c in df.columns else None)
            return all(col is not None for col in cols_needed)

        hay_alt_loc = any(_alt_ok(g) for g in alts) if alts else True

        problemas = []
        if faltan:
            problemas.append(f"- Faltan columnas esenciales: {_fmt_lista(faltan)}")
        if not hay_alt_loc:
            problemas.append("- No se cumple ninguna alternativa de localización (p. ej., (lat+long) o (antena)).")

        if _coalesce_cols(df, "hora"):
            ok_hora, smp_h = _valida_formato_hora(df["hora"].astype(str))
            if not ok_hora:
                problemas.append(f"- 'hora' debería verse como HH:MM:SS; muestras: {_fmt_lista(smp_h)}")

        if _coalesce_cols(df, "fecha"):
            ok_fecha, smp_f = _valida_fecha_parsible(df["fecha"])
            if not ok_fecha:
                problemas.append(f"- 'fecha' no es parseable en algunas filas; muestras: {_fmt_lista(smp_f)}")

        if _coalesce_cols(df, "lat") and _coalesce_cols(df, "long", "lon"):
            bbox = (config or {}).get("geografia", {}).get("sv_bbox", None)
            if not _valida_latlon(df, bbox=bbox):
                problemas.append("- 'lat/long' no tienen registros válidos (no 0,0; dentro de SV).")

        if problemas:
            guia = []
            guia.append("\n[SCHEMA] No se puede continuar. Ajustá los encabezados o agrega sinónimos:\n")
            guia.extend(p + "\n" for p in problemas)
            guia.append("\nSugerencias:\n")
            guia.append("• Revisá 'entradas.columnas_esenciales' en config.json.\n")
            guia.append("• Usá el wizard para mapear encabezados raros (se persisten en synonyms_user).\n")
            guia.append("• Para 'long' también se acepta 'lon' (sinónimo en schema.fields).\n")
            msg = "".join(guia)
            try:
                logger(f"[FATAL][schema] {msg}")
            except Exception:
                pass
            output_fn(msg)
            raise SystemExit(2)
        else:
            try:
                logger("[schema] Validación OK: esenciales presentes y tipos mínimos razonables.")
            except Exception:
                pass
            return True
    except SystemExit:
        raise
    except Exception:
        # En caso de error inesperado, permite continuar (comportamiento conservador)
        return True
