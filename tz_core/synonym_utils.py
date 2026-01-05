"""Helpers for managing user-defined column synonyms."""

from typing import Any, Callable, Tuple


def persist_user_synonym(
    *,
    config: Any,
    rename_map: Any,
    canonical: str,
    encabezado: str,
    cfg_add_user_synonym: Callable[[Any, str, str], Any],
    cfg_build_rename_map: Callable[[Any], Any],
    logger: Callable[[str], None] | None = None,
) -> Tuple[Any, Any]:
    """Persist a user-added synonym and rebuild the rename map.

    Returns the updated (config, rename_map) tuple. On error, returns the inputs unchanged.
    """

    try:
        new_config = cfg_add_user_synonym(config, canonical, encabezado)
        new_rename_map = cfg_build_rename_map(new_config)
        return new_config, new_rename_map
    except Exception as exc:
        if logger:
            try:
                logger(f"[WARN][synonyms] No se pudo persistir el sinónimo: {exc}")
            except Exception:
                pass
        return config, rename_map
