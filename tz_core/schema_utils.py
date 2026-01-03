"""Helpers relacionados con schema/aliasado de columnas para TZ Analyzer."""
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .text_utils import normalize_header_key


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
