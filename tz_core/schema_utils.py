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
