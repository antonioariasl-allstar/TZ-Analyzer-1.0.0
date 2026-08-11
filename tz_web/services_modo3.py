"""tz_web.services_modo3 — servicio no interactivo de Modo 3 (mapeo manual
de antenas/ubicaciones, microbloque 2).

Equivalente a ``tz_web.services.process_case()`` pero para el flujo de
ingreso manual: no hay archivo/hoja/mapeo/QC/filtros, solo una lista de
registros ya validados en ``tz_web.routes`` (ver ``tz_web.manual_validators``)
más color/nombre/carpeta de salida. Nunca llama a
``tz_core.manual_mode.modo_manual()`` (wizard interactivo de consola);
despacha directo a los mismos generadores que usa ese wizard
(``generar_kml``/``generar_kml_puntos_libres``) para no duplicar geometría
KML, y reutiliza los helpers genéricos de ``tz_web.services`` que no
dependen de conceptos de bitácora (nombre único de carpeta, log de
ejecución).
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from tz_core.bitacora_io import ensure_dir
from tz_core.config_loader import get_config
from tz_core.file_utils import escribe_hashes_txt
from tz_core.kml_generator import generar_kml, generar_kml_puntos_libres
from tz_core.utils import sanear_nombre_archivo
from tz_web.services import (
    CaseResult,
    OutputDirectoryError,
    ProgressUpdate,
    _generate_unique_case_name,
    _write_execution_log,
)

MODO3_TIPO_ANTENA = "antena"
MODO3_TIPO_PUNTO_LIBRE = "punto_libre"
MODO3_TIPOS_VALIDOS: Tuple[str, ...] = (MODO3_TIPO_ANTENA, MODO3_TIPO_PUNTO_LIBRE)


@dataclass
class Modo3Request:
    """Entrada explícita y tipada para ``process_case_modo3()``. Deliberadamente
    más chica que ``CaseRequest``: sin ``ruta_archivo``/``mapeo``/``hoja``/
    ``filtro_tiempo``/``tipo_bitacora``/``identity_overrides``/Top N, que no
    tienen sentido para un mapa armado a mano."""

    tipo: str
    registros: List[Dict[str, Any]]
    carpeta_salida: str
    color_hex: Optional[str] = None
    kml_opcional: bool = False
    output_base_name: Optional[str] = None
    on_progress: Optional[Callable[[ProgressUpdate], None]] = None


def sugerir_nombre_modo3(tipo: str, registros: List[Dict[str, Any]]) -> str:
    """Nombre de salida sugerido para Modo 3: estable y simple (tipo de mapa
    + cantidad de registros), sin depender de identidad telefónica como
    ``tz_core.ui_utils.suggest_case_name`` (pensado para bitácoras con
    tel/IMEI) — un mapa manual no tiene ese concepto."""
    prefijo = "antenas_manual" if tipo == MODO3_TIPO_ANTENA else "puntos_manual"
    cantidad = len(registros)
    base = f"{prefijo}_{cantidad}" if cantidad else prefijo
    return sanear_nombre_archivo(base, prefijo)


# ---------------------------------------------------------------------------
# Adaptación de registros — único lugar que traduce el contrato limpio de la
# UI (sección 4/5 del microbloque 1) al contrato heredado que exige
# generar_kml()/generar_kml_puntos_libres() (campos de bitácora que el
# usuario de Modo 3 nunca ve ni completa, ver sección 6 del microbloque 2).
# ---------------------------------------------------------------------------


def _registro_antena_a_fila(registro: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "antena": registro["nombre"],
        "lat": registro["lat"],
        "long": registro["lon"],
        "azimut": registro.get("azimut"),
        "celda": registro.get("celda"),
        "direccion": registro.get("direccion"),
        "detalle": registro.get("detalle"),
        "fecha": None,
        "hora": None,
        # Campos heredados del CLI/bitácora que esta interfaz no solicita:
        # se rellenan con None, nunca se exponen al usuario.
        "tel": None,
        "imei": None,
        "alias": None,
        "usuario": None,
        "abonado": None,
        "lac": None,
        "interaccion": None,
        "tel_contacto": None,
        "duracion": None,
    }


def _registro_punto_a_fila(registro: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "antena": registro["nombre"],
        "lat": registro["lat"],
        "long": registro["lon"],
        "direccion": registro.get("direccion"),
        "detalle": registro.get("detalle"),
    }


def construir_dataframe_modo3(tipo: str, registros: List[Dict[str, Any]]) -> pd.DataFrame:
    """Helper de adaptación claramente identificado (sección 6): construye el
    DataFrame que ``generar_kml``/``generar_kml_puntos_libres`` esperan, a
    partir de los registros con el contrato limpio de la UI."""
    if tipo == MODO3_TIPO_ANTENA:
        filas = [_registro_antena_a_fila(r) for r in registros]
    else:
        filas = [_registro_punto_a_fila(r) for r in registros]
    return pd.DataFrame(filas)


def process_case_modo3(request: Modo3Request) -> CaseResult:
    """Genera KMZ (+ KML opcional para antenas) / hashes / log a partir de
    ``request.registros`` — sin HTML (``CaseResult.html_path`` queda
    ``None``). Nunca lanza para un error de un producto individual (se
    refleja en ``warnings``/``errors`` como hace ``process_case()``); solo
    lanza para una carpeta de salida inválida (``OutputDirectoryError``, ya
    conocida por ``tz_web.state.translate_error``) o si no hay registros."""

    logs: List[str] = []
    sequence = 0

    def _log(msg: str) -> None:
        logs.append(msg)

    def _emit(stage: str, message: str) -> None:
        nonlocal sequence
        sequence += 1
        _log(f"[{stage}] {message}")
        if request.on_progress:
            request.on_progress(ProgressUpdate(stage=stage, message=message, sequence=sequence))

    carpeta_caso: Optional[str] = None
    nombre_salida: Optional[str] = None

    try:
        _emit("preparando", "Validando registros y preparando carpeta de salida")

        if not request.registros:
            raise ValueError("No hay registros para generar el mapa.")

        try:
            carpeta_base = ensure_dir(request.carpeta_salida)
        except OSError as exc:
            raise OutputDirectoryError(f"No se pudo preparar la carpeta de salida: {exc}") from exc

        candidato_base = (
            sanear_nombre_archivo(request.output_base_name, sugerir_nombre_modo3(request.tipo, request.registros))
            if request.output_base_name
            else sugerir_nombre_modo3(request.tipo, request.registros)
        )
        nombre_salida = _generate_unique_case_name(carpeta_base, candidato_base)
        carpeta_caso = os.path.join(carpeta_base, nombre_salida)
        ensure_dir(carpeta_caso)

        config = copy.deepcopy(get_config() or {})
        config.setdefault("salida", {})
        # generar_kml_puntos_libres() solo produce KMZ (ver
        # tz_core/kml_generator.py): "KML opcional" no tiene efecto real ahí,
        # así que no se le atribuye una semántica que el generador no ofrece.
        kml_aplica = request.tipo == MODO3_TIPO_ANTENA
        solo_kmz = not (request.kml_opcional and kml_aplica)
        config["salida"]["solo_kmz"] = solo_kmz
        if request.color_hex:
            config.setdefault("style", {})["theme_hex"] = request.color_hex

        df = construir_dataframe_modo3(request.tipo, request.registros)

        _emit("generando_cartografia", f"Generando cartografía ({len(request.registros)} registro(s))")

        archivo_kml = os.path.join(carpeta_caso, f"{nombre_salida}_mapeo.kml")
        kml_path: Optional[str] = None
        kmz_path: Optional[str] = None
        descartadas = 0

        if kml_aplica:
            _ruta, descartadas = generar_kml(df, archivo_kml, config=config, flat=True)
            if not solo_kmz and os.path.isfile(archivo_kml):
                kml_path = archivo_kml
            kmz_candidato = os.path.splitext(archivo_kml)[0] + ".kmz"
            if os.path.isfile(kmz_candidato):
                kmz_path = kmz_candidato
        else:
            _ruta_kmz, descartadas = generar_kml_puntos_libres(df, archivo_kml, config)
            if _ruta_kmz and os.path.isfile(_ruta_kmz):
                kmz_path = _ruta_kmz

        warnings_list: List[str] = []
        errors_list: List[str] = []
        if kmz_path is None:
            errors_list.append("No se pudo generar el mapa KMZ.")
        if descartadas:
            warnings_list.append(f"Se descartaron {descartadas} registro(s) por coordenadas inválidas.")

        _emit("generando_hashes", "Calculando hashes de integridad")

        # Los productos realmente generados (nunca hashes.txt sobre sí
        # mismo): se escribe ANTES del log, así el log tampoco entra en su
        # propio archivo de hashes (mismo orden que produce_case_outputs()
        # usa para Modo 1/2).
        pares: List[Tuple[str, str]] = []
        if kmz_path:
            pares.append((os.path.abspath(kmz_path), os.path.basename(kmz_path)))
        if kml_path:
            pares.append((os.path.abspath(kml_path), os.path.basename(kml_path)))

        hashes_path: Optional[str] = os.path.join(carpeta_caso, f"{nombre_salida}_hashes.txt")
        try:
            escribe_hashes_txt(hashes_path, pares)
            if not os.path.isfile(hashes_path):
                hashes_path = None
        except OSError:
            hashes_path = None
            errors_list.append("No se pudo generar el archivo de hashes.")

        _emit("finalizando", "Escribiendo log de ejecución")

        _log(f"Modo manual (Modo 3) — tipo: {request.tipo}")
        _log(f"Registros procesados: {len(request.registros)}")
        _log(f"Coordenadas descartadas: {descartadas}")
        _log(f"Color: {request.color_hex or '(por defecto)'}")
        productos = [p for p in ("KMZ" if kmz_path else None, "KML" if kml_path else None,
                                  "Hashes" if hashes_path else None) if p]
        _log(f"Productos generados: {', '.join(productos) if productos else 'ninguno'}")
        _log(f"Carpeta de salida: {carpeta_caso}")
        _log("Resultado final: éxito" if kmz_path else "Resultado final: fallo (sin KMZ)")

        log_path = _write_execution_log(carpeta_caso, nombre_salida, logs)

        summary = {
            "tipo": request.tipo,
            "registros_totales": len(request.registros),
            "coordenadas_descartadas": descartadas,
        }

        _emit("completado", "Análisis finalizado")

        return CaseResult(
            success=True,
            output_dir=carpeta_caso,
            html_path=None,
            kmz_path=kmz_path,
            kml_path=kml_path,
            hashes_path=hashes_path,
            log_path=log_path,
            logs=logs,
            warnings=warnings_list,
            errors=errors_list,
            summary=summary,
        )
    except Exception:
        if carpeta_caso and nombre_salida:
            _write_execution_log(carpeta_caso, f"{nombre_salida}_fallo", logs)
        raise
