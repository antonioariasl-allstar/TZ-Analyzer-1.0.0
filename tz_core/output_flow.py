"""Output flow helpers to reduce monolith surface."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from datetime import datetime


@dataclass
class OutputSetup:
    """Configuración de rutas, nombres de archivo y parámetros para la generación de salida."""
    nombre_salida: str
    carpeta_base: str
    carpeta_salida: str
    archivo_kml: str
    archivo_kmz: str
    carpeta_kml: str
    top_antenas: int
    top_contactos: int
    identity: Any
    suggestion: Any
    base_auto: str


def prepare_output_setup(
    df,
    config,
    time_filters,
    nombre_base: str,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    timestamp_fn: Optional[Callable[[], Any]] = None,
    now_fn: Optional[Callable[[], Any]] = None,
    sanitize_fn: Callable[[str, str], str],
    prompt_case_identity: Callable[..., Any],
    suggest_case_name: Callable[..., Any],
    collect_top_overrides: Callable[..., Any],
    prompt_output_routing: Callable[..., Any],
    select_folder: Callable[..., Any],
    cwd_fn: Callable[[], str],
    ensure_dir: Callable[[str], None],
) -> OutputSetup:
    """Resolve identity, naming, top overrides y rutas de salida."""

    def _sanear_nombre_archivo_local(s: str) -> str:
        """Sanitiza nombre de archivo eliminando caracteres no válidos y espacios."""
        return sanitize_fn(s, nombre_base)

    identity = prompt_case_identity(
        df=df,
        input_fn=input_fn,
        output_fn=output_fn,
        now_fn=now_fn or datetime.now,
    )

    suggestion = suggest_case_name(
        df=df,
        identity=identity,
        filters=time_filters.filters if getattr(time_filters, "enabled", False) else None,
        timestamp_fn=timestamp_fn or datetime.now,
        sanitize_fn=_sanear_nombre_archivo_local,
    )
    base_auto = suggestion.base_name

    def _default_top(key: str, fallback: int) -> int:
        """Obtiene valor de configuración HTML con fallback por defecto."""
        try:
            return int(config.get("html", {}).get(key, fallback))
        except Exception:
            return fallback

    selection = collect_top_overrides(
        input_fn=input_fn,
        output_fn=output_fn,
        default_antennas=_default_top("top_antenas_n", 10),
        default_contacts=_default_top("top_contactos_n", 10),
    )
    top_antenas = selection.antennas
    top_contactos = selection.contacts

    # Propagar a config para que HTML/KMZ usen estos valores
    try:
        if isinstance(config, dict):
            config["top_antenas"] = top_antenas
            config["top_contactos"] = top_contactos
    except Exception:
        pass

    routing = prompt_output_routing(
        base_name=base_auto,
        input_fn=input_fn,
        output_fn=output_fn,
        sanitize_fn=_sanear_nombre_archivo_local,
        select_folder=select_folder,
        cwd_fn=cwd_fn,
        ensure_dir=ensure_dir,
        separate_kml=bool(config.get("salida", {}).get("separar_kml_kmz", False)) if isinstance(config, dict) else False,
    )

    return OutputSetup(
        nombre_salida=routing.base_name,
        carpeta_base=routing.base_folder,
        carpeta_salida=routing.output_folder,
        archivo_kml=routing.kml_path,
        archivo_kmz=routing.kmz_path,
        carpeta_kml=routing.kml_folder,
        top_antenas=top_antenas,
        top_contactos=top_contactos,
        identity=identity,
        suggestion=suggestion,
        base_auto=base_auto,
    )
