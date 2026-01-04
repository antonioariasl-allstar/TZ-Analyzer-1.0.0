"""Helpers relacionados con schema/aliasado de columnas para TZ Analyzer."""
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence
import json
import re

import numpy as np

import pandas as pd

from .text_utils import normalize_header_key
from .logging_utils import log as core_log
from .dataframe_utils import dedupe_columns


def build_schema_synonym_map(
    schema_fields: Optional[Mapping[str, Any]] = None,
    target_alias: Optional[Mapping[str, str]] = None,
    normalizer: Callable[[Any], str] = normalize_header_key,
) -> Dict[str, str]:
    """Construye un diccionario normalizado de sinónimos → nombre canónico.

    Args:
        schema_fields: Mapa tomado de `CONFIG.schema.fields`.
        target_alias: Reemplazos finales para columnas (`lon` → `long`).
        normalizer: Función para normalizar los encabezados (por defecto, ASCII + `_`).

    Returns:
        Diccionario donde cada alias normalizado apunta al nombre canónico deseado.
    """

    schema_fields = schema_fields or {}
    target_alias = target_alias or {}
    synonym_map: Dict[str, str] = {}

    for canonical, meta in schema_fields.items():
        target = target_alias.get(canonical, canonical)
        synonyms: Iterable[Any]
        if isinstance(meta, Mapping):
            raw_synonyms = meta.get("synonyms", [])
            if isinstance(raw_synonyms, (list, tuple, set)):
                synonyms = raw_synonyms
            elif raw_synonyms:
                synonyms = [raw_synonyms]
            else:
                synonyms = []
        else:
            synonyms = []

        for candidate in [canonical, *list(synonyms)]:
            normalized = normalizer(candidate)
            if normalized:
                synonym_map[normalized] = target

    return synonym_map


def has_location_coverage(
    present_columns: Iterable[str],
    location_alternatives: Optional[Iterable[Iterable[str]]] = None,
    target_alias: Optional[Mapping[str, str]] = None,
) -> bool:
    """Replica la verificación local `_has_location_ok` del monolito.

    Args:
        present_columns: Columnas actualmente disponibles en el DataFrame.
        location_alternatives: Grupos válidos de columnas equivalentes a una
            ubicación completa (p. ej. ["lat", "lon"] o ["antena"]).
        target_alias: Reemplazos finales (lon→long, etc.) para armonizar nombres.

    Returns:
        True si existe al menos una alternativa completa presente.
    """

    if not present_columns:
        return False

    present = set(present_columns)
    target_alias = target_alias or {}
    alts = list(location_alternatives or [])
    if not alts:
        return True

    return any(
        all(target_alias.get(col, col) in present for col in alt)
        for alt in alts
    )


def collect_missing_required_fields(
    present_columns: Iterable[str],
    *,
    subject_mode: str,
    fields_meta: Optional[Mapping[str, Any]] = None,
    target_alias: Optional[Mapping[str, str]] = None,
) -> list[str]:
    """Replica la lógica `_need_fields` para campos esenciales no ubicados.

    Args:
        present_columns: Columnas disponibles tras normalización inicial.
        subject_mode: Modo sujeto detectado ("tel" o "imei").
        fields_meta: Metadata tomada de `schema.fields` (con required/required_mode).
        target_alias: Alias finales para mapear canónicos (lon→long, etc.).

    Returns:
        Lista de canónicos faltantes (sin ubicación) en el mismo orden que antes.
    """

    present = set(present_columns or [])
    subject_mode = (subject_mode or "tel").lower()
    target_alias = target_alias or {}
    fields_meta = fields_meta or {}

    req = set()
    req.add("imei" if subject_mode == "imei" else "tel")

    if "timestamp" in present:
        req.add("timestamp")
    else:
        req.update(["fecha", "hora"])

    req.update(["contacto", "interaccion"])

    for key, meta in fields_meta.items():
        if not hasattr(meta, "get"):
            continue
        tgt = target_alias.get(key, key)
        if meta.get("required") is True:
            req.add(tgt)
        if str(meta.get("required_mode", "")).lower() == subject_mode:
            req.add(tgt)

    return [field for field in req if field not in present]


def prep_meta_unicos(
    df,
    campos: Iterable[tuple[str, str]],
    *,
    logger: Optional[Callable[[str], None]] = None,
):
    """Replica `_prep_meta_unicos` para rellenar alias/usuario/abonado vacíos."""

    log_fn = logger or core_log

    for etiqueta, col in campos:
        serie = df[col] if col in df.columns else None

        vacio = True
        if serie is not None:
            try:
                vacio = bool(
                    serie.isna().all() or (serie.astype(str).str.strip() == "").all()
                )
            except Exception:
                vacio = True

        if (col not in df.columns) or vacio:
            df[col] = ""
            if log_fn:
                try:
                    log_fn(f"[QC] {col} no presente/vacío; se deja vacío (no se imprime en salida).")
                except Exception:
                    pass

    return df


def ensure_placeholder_columns(
    df,
    missing_fields: Iterable[str],
    *,
    placeholder: str = "SinInf",
    target_alias: Optional[Mapping[str, str]] = None,
    logger: Optional[Callable[[str], None]] = None,
):
    """Garantiza columnas canónicas presentes rellenando con un placeholder.

    Se usa cuando el wizard está en modo QC manual: en lugar de volver a preguntar
    por campos esenciales faltantes, se agregan columnas con un valor sentinela
    para que el pipeline posterior (HTML/KML) no falle.
    """

    target_alias = target_alias or {}
    added: list[str] = []
    log_fn = logger or core_log

    for field in missing_fields or []:
        canonical = target_alias.get(field, field)
        if canonical in df.columns:
            continue
        df[canonical] = placeholder
        added.append(canonical)
        if log_fn:
            try:
                log_fn(f"[WIZARD] '{canonical}' se rellena con placeholder '{placeholder}'.")
            except Exception:
                pass

    return added


def _muestras_columna(serie, n: int = 5) -> list[str]:
    """Devuelve una vista previa de hasta *n* valores no vacíos de la serie."""

    try:
        vals = [str(v) for v in serie.dropna().astype(str).head(n).tolist()]
        if not vals:
            vals = ["(sin datos visibles)"]
        return vals
    except Exception:
        return ["(error al leer muestras)"]


def _es_numero(valor: Any) -> bool:
    """Indica si el valor puede interpretarse como número (permite coma decimal)."""

    try:
        float(str(valor).replace(",", "."))
        return True
    except Exception:
        return False


def _en_bbox_sv(lat: Any, lon: Any, bbox: Optional[Mapping[str, float]] = None) -> bool:
    """Valida si una coordenada cae dentro del bounding box de SV (o el provisto)."""

    fallback_bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}
    bbox_ok = isinstance(bbox, Mapping) and all(k in bbox for k in fallback_bbox)
    bbox = bbox if bbox_ok else fallback_bbox

    try:
        lat = float(lat)
        lon = float(lon)
        if abs(lat) < 1e-9 and abs(lon) < 1e-9:
            return False
        return bbox["lat_min"] <= lat <= bbox["lat_max"] and bbox["lon_min"] <= lon <= bbox["lon_max"]
    except Exception:
        return False


def _es_columna_valida_para(
    canonico: str,
    serie,
) -> tuple[bool, str]:
    """Replica las validaciones heurísticas usadas por el wizard QC."""

    name = (canonico or "").strip().lower()
    smps = _muestras_columna(serie, n=5)

    if name in {"lat", "long"}:
        nums = sum(1 for v in smps if _es_numero(v))
        if nums < max(1, len(smps)):
            return False, f"La columna para '{canonico}' debería ser numérica; muestras: {', '.join(smps)}"
        return True, ""

    if name == "hora":
        pat = re.compile(r"^\d{2}:\d{2}:\d{2}$")
        ok = sum(1 for v in smps if pat.match(str(v).strip()[:8]) is not None)
        if ok < max(1, len(smps)):
            return False, f"Se espera formato HH:MM:SS; muestras: {', '.join(smps)}"
        return True, ""

    if name == "fecha":
        conv = pd.to_datetime(pd.Series(smps), errors="coerce", dayfirst=True)
        if conv.isna().any():
            return False, f"Algunas muestras no parecen fechas; muestras: {', '.join(smps)}"
        return True, ""

    if name in {"tel", "contacto", "tel_contacto"}:
        ok = sum(1 for v in smps if re.search(r"\d{7,}", v) is not None)
        if ok < max(1, len(smps)):
            return False, f"Se esperan números telefónicos; muestras: {', '.join(smps)}"
        return True, ""

    if name in {"azimut", "lac", "celda"}:
        nums = sum(1 for v in smps if _es_numero(v))
        if nums < max(1, len(smps)):
            return False, f"Se esperan valores numéricos; muestras: {', '.join(smps)}"
        return True, ""

    return True, ""


def preview_column_mapping(
    serie,
    source_name: str,
    target_name: str,
    *,
    muestras_fn: Callable[[Any, int], list[str]] = _muestras_columna,
    validator_fn: Callable[[str, Any], tuple[bool, str]] = _es_columna_valida_para,
    input_fn: Optional[Callable[[str], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    sample_size: int = 5,
):
    """Muestra valores y confirma con el usuario antes de mapear una columna."""

    input_cb = input_fn or input  # type: ignore[arg-type]
    output_cb = output_fn or print

    samples = muestras_fn(serie, n=sample_size)
    output_cb(f"\n[WIZARD] Previsualización de '{source_name}' para mapear a '{target_name}':")
    for idx, value in enumerate(samples, 1):
        output_cb(f"   {idx}. {value}")

    ok_tipo, motivo = validator_fn(target_name, serie)
    if not ok_tipo:
        output_cb(f"[WIZARD] Esta columna no parece ser '{target_name}': {motivo}")
        output_cb("Volvé a elegir otra columna para este canónico.")
        return False

    resp = (input_cb(f"[CONFIRMAR] ¿Seguro que '{source_name}' → '{target_name}'? (S/N): ") or "").strip().lower()
    if resp not in ("s", "si", "sí"):
        output_cb("Cancelado. Elegí otra columna.")
        return False

    return True


def confirm_column_mapping_with_preview(
    df: pd.DataFrame,
    source_name: str,
    target_name: str,
    *,
    preview_fn: Callable[..., bool] = preview_column_mapping,
    muestras_fn: Callable[[Any, int], list[str]] = _muestras_columna,
    validator_fn: Callable[[str, Any], tuple[bool, str]] = _es_columna_valida_para,
    post_map_validator: Optional[Callable[[pd.DataFrame], tuple[bool, str]]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    synonyms_user: Optional[Mapping[str, Any]] = None,
    persist_synonym_fn: Optional[Callable[[str, str], None]] = None,
    logger: Optional[Callable[[str], None]] = None,
) -> Optional[pd.DataFrame]:
    """Ejecuta preview/confirmación y aplica el mapeo con rollback ante fallos."""

    if source_name not in df.columns:
        return df

    input_cb = input_fn or input  # type: ignore[arg-type]
    output_cb = output_fn or print
    log_fn = logger or core_log

    confirmado = preview_fn(
        df[source_name],
        source_name,
        target_name,
        muestras_fn=muestras_fn,
        validator_fn=validator_fn,
        input_fn=input_cb,
        output_fn=output_cb,
    )
    if not confirmado:
        return None

    synonyms_user = synonyms_user or {}
    current_target = synonyms_user.get(source_name)
    target_norm = str(target_name).strip().lower()
    if current_target is not None:
        current_norm = str(current_target).strip().lower()
        if current_norm and current_norm != target_norm:
            output_cb(f"[WIZARD] Conflicto: '{source_name}' ya está registrado como sinónimo de '{current_target}'.")
            resp = (input_cb("¿Deseás SOBREESCRIBIR ese registro? (S/N): ") or "").strip().lower()
            if resp not in ("s", "si", "sí"):
                output_cb("No se aplicó el mapeo por conflicto. Volvé a elegir.")
                return None

    renamed = df.rename(columns={source_name: target_name})
    if post_map_validator is not None:
        ok_schema, motivo = post_map_validator(renamed)
        if not ok_schema:
            output_cb(f"[WIZARD] Se revirtió el mapeo por inconsistencia: {motivo}")
            return None

    if persist_synonym_fn is not None:
        try:
            persist_synonym_fn(target_name, source_name)
        except Exception as exc:  # pragma: no cover - log defensivo
            if log_fn:
                try:
                    log_fn(f"[WARN][synonyms] No se pudo persistir el sinónimo: {exc}")
                except Exception:
                    pass

    if log_fn:
        try:
            log_fn(f"WIZARD: la columna '{source_name}' fue mapeada a '{target_name}'.")
        except Exception:
            pass

    return renamed


def run_schema_location_assistant(
    df: pd.DataFrame,
    *,
    original_columns: Sequence[str],
    config: Optional[Mapping[str, Any]] = None,
    alias_visibles: Optional[Mapping[str, str]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
    persist_synonym_fn: Optional[Callable[[str, str], None]] = None,
    validate_schema_fn: Optional[Callable[[pd.DataFrame], Any]] = None,
    logger: Optional[Callable[[str], None]] = None,
    target_alias: Optional[Mapping[str, str]] = None,
    config_path: Optional[str] = "config.json",
) -> pd.DataFrame:
    """Asistente interactivo para garantizar ubicación y campos esenciales."""

    alias_visibles = alias_visibles or {}
    input_cb = input_fn or (lambda message: input(message))  # type: ignore[arg-type]
    output_cb = output_fn or print
    log_fn = logger or core_log
    config_dict = dict(config) if isinstance(config, Mapping) else {}

    schema_cfg = dict(config_dict.get("schema", {}) or {})
    fields_meta = schema_cfg.get("fields", {}) or {}
    location_alts = schema_cfg.get("location_alternatives", [["lat", "lon"], ["antena"]])
    subject_mode = str(schema_cfg.get("subject_default_mode", "tel")).lower() or "tel"

    alias_map = {"lon": "long", "duracion_seg": "duracion"}
    if isinstance(target_alias, Mapping):
        alias_map.update(target_alias)

    columns_menu = list(dict.fromkeys(list(original_columns or []) + list(df.columns)))
    present = set(columns_menu)

    def _normalize(value: Any) -> str:
        try:
            return normalize_header_key(value)
        except Exception:
            return ""

    def _rename_like(df_obj: pd.DataFrame, source: str, target: str) -> pd.DataFrame:
        if source == target:
            return df_obj
        if source in df_obj.columns:
            return df_obj.rename(columns={source: target})
        src_norm = _normalize(source)
        for existing in list(df_obj.columns):
            if _normalize(existing) == src_norm:
                return df_obj.rename(columns={existing: target})
        return df_obj

    def _prompt_index(message: str, limit: int, default: Optional[int] = None) -> Optional[int]:
        raw = (input_cb(message) or "").strip()
        if raw == "" and default is not None:
            return default
        try:
            idx = int(raw)
        except Exception:
            return default
        if 1 <= idx <= limit:
            return idx
        return default

    if not has_location_coverage(present, location_alts, alias_map):
        output_cb("\n[WIZARD] Falta UBICACIÓN. Elegí alternativa:")
        for idx, alt in enumerate(location_alts, 1):
            alt_view = " + ".join([alias_map.get(val, val) for val in alt])
            output_cb(f"  [{idx}] {alt_view}")
        choice_idx = _prompt_index("→ Opción (#, Enter=1): ", len(location_alts), default=1) or 1
        choice = location_alts[choice_idx - 1]

        for tgt in choice:
            canonical = alias_map.get(tgt, tgt)
            if canonical in present:
                continue
            label = alias_visibles.get(tgt, tgt)
            output_cb(f"\n[WIZARD] Elegí la columna para '{label}':")
            for idx, column in enumerate(columns_menu, 1):
                output_cb(f"  [{idx}] {column}")
            pick = _prompt_index("→ Columna (# o Enter=omitir): ", len(columns_menu))
            if pick is None:
                continue
            source = columns_menu[pick - 1]
            df = _rename_like(df, source, canonical)
            present.add(canonical)
            if canonical not in columns_menu:
                columns_menu.append(canonical)

    missing = collect_missing_required_fields(
        present,
        subject_mode=subject_mode,
        fields_meta=fields_meta,
        target_alias=alias_map,
    )
    if missing:
        output_cb("\n[WIZARD] Faltan campos esenciales: " + ", ".join(missing))
        output_cb("Elegí la columna correspondiente (número). Enter = saltar.\nColumnas disponibles:")
        for idx, column in enumerate(columns_menu, 1):
            output_cb(f"  [{idx}] {column}")
        for canonical in missing:
            label = alias_visibles.get(canonical, canonical)
            pick = _prompt_index(
                f"→ ¿Cuál columna corresponde a '{label}'? (# o Enter): ",
                len(columns_menu),
            )
            if pick is None:
                continue
            source = columns_menu[pick - 1]
            real_target = alias_map.get(canonical, canonical)
            df = _rename_like(df, source, real_target)
            present.add(real_target)
            if real_target not in columns_menu:
                columns_menu.append(real_target)

    def _persist_config_snapshot() -> None:
        if not (isinstance(config_dict, Mapping) and config_path):
            return
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config_dict, handle, ensure_ascii=False, indent=2)
        output_cb("[WIZARD] Validación completada. Config guardada (sin cambios de sinónimos).")

    try:
        _persist_config_snapshot()
    except Exception:
        output_cb("[WIZARD] Aviso: no se pudo escribir config.json; se continúa sin persistir.")

    df = dedupe_columns(df)

    def _smoke_schema_postmap(df_check: pd.DataFrame) -> tuple[bool, str]:
        esenciales = (config_dict.get("entradas", {}) or {}).get("columnas_esenciales", []) or []
        faltan = [col for col in esenciales if col not in df_check.columns]
        if faltan:
            return False, f"Faltan columnas esenciales tras el mapeo: {', '.join(faltan)}"

        if "lat" in df_check.columns and "long" in df_check.columns:
            try:
                lt = pd.to_numeric(df_check["lat"], errors="coerce")
                lg = pd.to_numeric(df_check["long"], errors="coerce")
                mask_valid = (~lt.isna()) & (~lg.isna()) & (lt != 0) & (lg != 0)
                if not mask_valid.any():
                    return False, "No quedaron coordenadas válidas (lat/long) tras el mapeo."
            except Exception:
                return False, "Coordenadas inválidas tras el mapeo."
        return True, ""

    def _ask_map_col(df_obj: pd.DataFrame, colname: str) -> Optional[pd.DataFrame]:
        if colname in df_obj.columns:
            return df_obj
        output_cb(
            f"\n[WIZARD] Falta columna esencial de ubicación: '{colname}'. Elegí la columna correspondiente (número). Enter=omitir."
        )
        cols_list = list(df_obj.columns)
        for idx, column in enumerate(cols_list, 1):
            output_cb(f"  [{idx}] {column}")
        pick = _prompt_index("→ ¿Cuál columna corresponde? (# o Enter): ", len(cols_list))
        if pick is None:
            return df_obj
        source = cols_list[pick - 1]
        if source != colname and source in df_obj.columns:
            user_synonyms = dict(config_dict.get("synonyms_user", {}) or {})
            mapped_df = confirm_column_mapping_with_preview(
                df_obj,
                source,
                colname,
                preview_fn=preview_column_mapping,
                muestras_fn=_muestras_columna,
                validator_fn=_es_columna_valida_para,
                post_map_validator=_smoke_schema_postmap,
                input_fn=input_cb,
                output_fn=output_cb,
                synonyms_user=user_synonyms,
                persist_synonym_fn=persist_synonym_fn,
                logger=log_fn,
            )
            if mapped_df is None:
                return None
            df_obj = mapped_df

        if validate_schema_fn is not None:
            validate_schema_fn(df_obj)
        return df_obj

    for need in ("lat", "long", "antena"):
        updated_df = _ask_map_col(df, need)
        if updated_df is None:
            return df
        df = updated_df

    df = dedupe_columns(df)

    faltan_ub = [col for col in ("lat", "long") if col not in df.columns]
    if faltan_ub:
        output_cb(
            "\n[ERROR] No se puede continuar: faltan columnas esenciales de ubicación -> " + ", ".join(faltan_ub)
        )
        output_cb("Revise los encabezados de la hoja o use el wizard para mapearlos correctamente.")
        raise SystemExit(2)

    if "lat" in df.columns and "long" in df.columns and "antena" not in df.columns:
        def _fmt_coord(value: Any) -> str:
            try:
                return f"{float(value):.6f}"
            except Exception:
                return ""

        lat_key = df["lat"].map(_fmt_coord)
        lon_key = df["long"].map(_fmt_coord)
        mask = (lat_key != "") & (lon_key != "")
        pairs = pd.Series(list(zip(lat_key, lon_key)), index=df.index)
        uniq_pairs = pd.unique(pairs[mask])
        mapdict = {pair: f"Antena {idx}" for idx, pair in enumerate(uniq_pairs, start=1)}
        if log_fn:
            try:
                log_fn(f"Antena fallback: se crearon {len(mapdict)} grupos por par (lat,long).")
            except Exception:
                pass
        df["antena"] = np.where(mask, pairs.map(mapdict), "Antena —")
        df = dedupe_columns(df)

    return df
