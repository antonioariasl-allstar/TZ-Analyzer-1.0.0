"""Output generation wrapper to keep monolith thin."""

from typing import Any, Callable, Optional


def run_outputs_flow(
    *,
    df,
    config,
    override_tops=None,
    nombre_salida: str,
    archivo_kml: str,
    carpeta_base: str,
    carpeta_salida: str,
    archivo_entrada: str,
    hoja: Any,
    archivo_errores: str,
    desc_coords: Any,
    build_interactions_section: Callable[..., Any],
    build_contacts_section: Callable[..., Any],
    generar_html_fn: Callable[..., Any],
    relocate_kmz_fn: Callable[..., Any],
    write_hashes_fn: Callable[..., Any],
    produce_fn: Callable[..., Any],
    summarize_fn: Callable[..., Any],
    logger: Callable[[str], None],
    output_fn: Callable[[str], None],
    path_exists: Callable[[str], bool],
    cwd_fn: Callable[[], str],
    log_file_path: Optional[str],
    set_interactions_section: Callable[[str], None],
    set_contacts_section: Callable[[str], None],
):
    """Run HTML/KML outputs and log summary; swallow errors to avoid hard fail."""

    logger("[salidas] Construyendo salidas HTML/KML…")

    try:
        resultado_salidas = produce_fn(
            df=df,
            config=config,
            override_tops=override_tops,
            nombre_salida=nombre_salida,
            archivo_kml=archivo_kml,
            carpeta_base=carpeta_base,
            carpeta_salida=carpeta_salida,
            archivo_entrada=archivo_entrada,
            hoja=hoja,
            error_report_path=archivo_errores,
            discarded_coords=desc_coords,
            build_interactions_section=build_interactions_section,
            build_contacts_section=build_contacts_section,
            generar_html_fn=generar_html_fn,
            relocate_kmz_fn=relocate_kmz_fn,
            write_hashes_fn=write_hashes_fn,
            summarize_fn=summarize_fn,
            logger=logger,
            output_fn=output_fn,
            path_exists=path_exists,
            cwd_fn=cwd_fn,
            log_file_path=log_file_path,
            set_interactions_section=set_interactions_section,
            set_contacts_section=set_contacts_section,
        )

        try:
            if isinstance(resultado_salidas, dict):
                html_path = resultado_salidas.get("html")
                kmz_path = resultado_salidas.get("kmz")
                hashes_path = resultado_salidas.get("hashes")
            else:
                html_path = getattr(resultado_salidas, "informe_html", None)
                kmz_path = getattr(resultado_salidas, "kmz_path", None)
                hashes_path = getattr(resultado_salidas, "hashes_path", None)
            logger(f"[salidas] HTML={html_path} KMZ={kmz_path} HASHES={hashes_path}")
        except Exception:
            pass

        return resultado_salidas
    except Exception as e:
        output_fn(f"[ERROR] Bloque HTML/KML falló: {e}")
        return None
