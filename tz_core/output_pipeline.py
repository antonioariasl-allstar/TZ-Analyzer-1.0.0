"""Pipelines de salida para el flujo manual.

Este módulo agrupa la generación de secciones HTML, informes y archivos
auxiliares como HASHES.txt, permitiendo pruebas unitarias aisladas.
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pandas as pd

from tz_core.bitacora_normalization import clasificar_confiabilidad_duracion, DuracionEstado


def _accepts_kwarg(fn: Callable[..., Any], name: str) -> bool:
    """Indica si `fn` acepta el parámetro nombrado `name` (o **kwargs genéricos).

    Permite propagar `duracion_estado` a callables reales sin romper stubs/tests
    existentes que no lo esperan.
    """
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        p.name == name or p.kind == inspect.Parameter.VAR_KEYWORD
        for p in params
    )


@dataclass
class ProduceOutputsResult:
    """Resultado de `produce_case_outputs`."""

    informe_html: Optional[str]
    kmz_path: Optional[str]
    hashes_path: Optional[str]
    interactions_html: str
    contacts_html: str


def produce_case_outputs(
    *,
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]],
    override_tops: Optional[Dict[str, Any]] = None,
    nombre_salida: str,
    archivo_kml: str,
    carpeta_base: str,
    carpeta_salida: str,
    archivo_entrada: Optional[str],
    hoja: Optional[str],
    error_report_path: Optional[str],
    discarded_coords: int,
    build_interactions_section: Callable[[pd.DataFrame, int, Dict[str, Any]], str],
    build_contacts_section: Callable[[pd.DataFrame, Dict[str, Any]], str],
    generar_html_fn: Callable[..., str],
    relocate_kmz_fn: Callable[..., Optional[str]],
    write_hashes_fn: Callable[[str, list[tuple[str, str]]], None],
    summarize_fn: Callable[..., None],
    logger: Optional[Callable[[str], None]] = None,
    output_fn: Callable[[str], None] = print,
    path_exists: Callable[[str], bool] = os.path.exists,
    cwd_fn: Callable[[], str] = os.getcwd,
    log_file_path: Optional[str] = None,
    set_interactions_section: Callable[[str], None] = lambda _html: None,
    set_contacts_section: Callable[[str], None] = lambda _html: None,
    duracion_estado: Optional[DuracionEstado] = None,
) -> ProduceOutputsResult:
    """Genera secciones HTML, informe y archivos auxiliares para el caso actual.

    `duracion_estado` (opcional): resultado ya resuelto de
    `clasificar_confiabilidad_duracion`, propagado desde `IngestionResult`.
    Si se omite, se calcula una sola vez aquí y se comparte con todos los
    consumidores (interacciones, contactos, informe HTML) de esta ejecución.
    """

    cfg = config or {}

    if duracion_estado is None:
        duracion_estado = clasificar_confiabilidad_duracion(df)

    try:
        dias_cfg = int(cfg.get("html", {}).get("interacciones_ultimos_dias", 3))
    except Exception:
        dias_cfg = 3

    try:
        columnas_cfg = cfg.get("columnas", {}) or {}
    except Exception:
        columnas_cfg = {}

    interactions_html = ""
    try:
        interactions_html = build_interactions_section(
            df, dias_cfg, columnas_cfg, config=cfg, logger=logger,
            duracion_estado=duracion_estado,
        )
        if logger:
            logger(f"[DEBUG] Interacciones: {len(interactions_html)} chars")
    except Exception as exc:
        if logger:
            logger(f"[ERROR] Interacciones falló: {exc}")
        interactions_html = ""

    try:
        set_interactions_section(interactions_html)
    except Exception:
        pass

    contacts_html = ""
    try:
        if _accepts_kwarg(build_contacts_section, "duracion_estado"):
            contacts_html = build_contacts_section(
                df, columnas_cfg, duracion_estado=duracion_estado
            )
        else:
            contacts_html = build_contacts_section(df, columnas_cfg)
    except Exception:
        contacts_html = ""

    try:
        set_contacts_section(contacts_html)
    except Exception:
        pass

    informe_html: Optional[str] = None
    nombre_bitacora = os.path.basename(archivo_entrada) if archivo_entrada else None
    try:
        _html_kwargs: Dict[str, Any] = dict(
            df=df,
            archivo_kml=archivo_kml,
            carpeta_salida=carpeta_salida,
            nombre_salida=nombre_salida,
            hoja=hoja,
            nombre_bitacora=nombre_bitacora,
            config=config,
            override_tops=override_tops,
            html_seccion_interacciones=interactions_html,
            html_seccion_todos_contactos=contacts_html,
            logger=logger,
        )
        if _accepts_kwarg(generar_html_fn, "duracion_estado"):
            _html_kwargs["duracion_estado"] = duracion_estado
        informe_html = generar_html_fn(**_html_kwargs)
        output_fn(f"Informe HTML generado en: {informe_html}")
    except Exception as exc:
        output_fn(f"[ERROR] No se pudo generar el HTML: {exc}")
        informe_html = None

    kmz_path: Optional[str] = None
    try:
        kmz_path = relocate_kmz_fn(
            case_name=nombre_salida,
            source_folder=carpeta_base,
            target_folder=carpeta_salida,
            logger=logger,
        )
    except Exception as exc:
        output_fn(f"[WARN] No se pudo reubicar KMZ: {exc}")
    if kmz_path is None and archivo_kml:
        kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"

    hashes_path: Optional[str] = None
    try:
        pares: list[tuple[str, str]] = []
        if archivo_entrada and path_exists(archivo_entrada):
            pares.append((os.path.abspath(archivo_entrada), os.path.basename(archivo_entrada)))
        if informe_html and path_exists(informe_html):
            pares.append((os.path.abspath(informe_html), os.path.basename(informe_html)))

        kmz_candidate = os.path.splitext(archivo_kml)[0] + ".kmz" if archivo_kml else None
        kmz_present = False
        if kmz_candidate and path_exists(kmz_candidate):
            pares.append((os.path.abspath(kmz_candidate), os.path.basename(kmz_candidate)))
            kmz_present = True

        if log_file_path and path_exists(log_file_path):
            pares.append((os.path.abspath(log_file_path), os.path.basename(log_file_path)))

        dest_dir: Optional[str] = None
        if informe_html and path_exists(informe_html):
            dest_dir = os.path.dirname(os.path.abspath(informe_html))
        elif kmz_present and kmz_candidate:
            dest_dir = os.path.dirname(os.path.abspath(kmz_candidate))
        elif carpeta_salida:
            dest_dir = carpeta_salida
        else:
            dest_dir = cwd_fn()

        os.makedirs(dest_dir, exist_ok=True)
        hashes_path = os.path.join(dest_dir, f"{nombre_salida}_hashes.txt")
        write_hashes_fn(hashes_path, pares)
        if logger:
            logger(f"[hashes] Generado {os.path.basename(hashes_path)}")
    except Exception as exc:
        if logger:
            logger(f"[WARN][hashes] No se pudo generar HASHES.txt: {exc}")
        hashes_path = None

    try:
        summarize_fn(
            config=config,
            output_fn=output_fn,
            kml_path=archivo_kml,
            error_report_path=error_report_path,
            discarded_coords=discarded_coords,
            path_exists=path_exists,
        )
    except Exception:
        # Se mantiene silencioso para no interrumpir el flujo principal.
        pass

    return ProduceOutputsResult(
        informe_html=informe_html,
        kmz_path=kmz_path,
        hashes_path=hashes_path,
        interactions_html=interactions_html,
        contacts_html=contacts_html,
    )
