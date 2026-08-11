"""tz_web.services_modo3 — servicio no interactivo de Modo 3 (mapeo manual
de antenas/ubicaciones).

Equivalente a ``tz_web.services.process_case()`` pero para el flujo de
ingreso manual: no hay archivo/hoja/mapeo/QC/filtros, solo una lista de
registros ya validados en ``tz_web.routes`` (ver ``tz_web.manual_validators``)
más color/nombre/carpeta de salida. Nunca llama a
``tz_core.manual_mode.modo_manual()`` (wizard interactivo de consola);
despacha directo a los mismos generadores que usa ese wizard
(``generar_kml``/``generar_kml_puntos_libres``) para no duplicar geometría
KML. Antes de generar, fija una entrada manual reproducible en JSON UTF-8;
los productos se crean en staging y solo se publican mediante el contrato
transaccional compartido de ``tz_web.output_transaction``.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from tz_core.bitacora_io import ensure_dir
from tz_core.config_loader import get_config
from tz_core.kml_generator import generar_kml, generar_kml_puntos_libres
from tz_core.utils import sanear_nombre_archivo
from tz_web.output_transaction import (
    ArtifactSpec,
    InputIntegrityError,
    OutputTransaction,
    finalize_output,
    sha256_file,
    verify_input_snapshot,
)
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
MODO3_SNAPSHOT_SCHEMA = "TZ_ANALYZER_MODO3_SNAPSHOT_V1"

_CAMPOS_REGISTRO_ANTENA = (
    "nombre", "lat", "lon", "azimut", "celda", "direccion", "detalle",
)
_CAMPOS_REGISTRO_PUNTO = (
    "nombre", "lat", "lon", "direccion", "detalle",
)
_CAMPOS_ESTILO_CARTOGRAFICO = (
    "theme_hex",
    "pin_icon_url",
    "pin_scale",
    "label_scale",
    "line_width",
    "line_abgr",
    "cone_opacity",
    "cone_half_degrees",
)


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


def _registros_realmente_procesados(
    tipo: str, registros: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Separa los datos cartograficos del identificador efimero de la UI.

    El ``id`` permite editar o eliminar filas dentro de la sesion, pero no se
    entrega al generador y por tanto no forma parte de la entrada analizada.
    Se preservan orden, valores tipados y campos opcionales del contrato real.
    """
    if tipo == MODO3_TIPO_ANTENA:
        campos = _CAMPOS_REGISTRO_ANTENA
    elif tipo == MODO3_TIPO_PUNTO_LIBRE:
        campos = _CAMPOS_REGISTRO_PUNTO
    else:
        raise ValueError(f"Tipo de Modo 3 no soportado: {tipo!r}.")
    return [
        {campo: copy.deepcopy(registro.get(campo)) for campo in campos}
        for registro in registros
    ]


def construir_snapshot_modo3(
    *,
    tipo: str,
    registros: List[Dict[str, Any]],
    config: Dict[str, Any],
    kml_opcional: bool,
) -> Dict[str, Any]:
    """Construye la fuente de verdad reproducible de una ejecucion manual."""
    registros_procesados = _registros_realmente_procesados(tipo, registros)
    style = config.get("style", {}) if isinstance(config, dict) else {}
    style_relevante = {
        campo: copy.deepcopy(style[campo])
        for campo in _CAMPOS_ESTILO_CARTOGRAFICO
        if campo in style
    }
    kml_aplica = tipo == MODO3_TIPO_ANTENA
    return {
        "schema": MODO3_SNAPSHOT_SCHEMA,
        "modo": "MODO_3",
        "tipo": tipo,
        "registros": registros_procesados,
        "configuracion_cartografica": {
            "generador": "antenas_flat" if kml_aplica else "puntos_libres",
            "flat": kml_aplica,
            "kml_opcional": bool(kml_opcional and kml_aplica),
            "kml": copy.deepcopy(config.get("kml", {})) if kml_aplica else {},
            "salida": {
                "solo_kmz": bool(config.get("salida", {}).get("solo_kmz", False)),
            },
            "style": style_relevante,
        },
    }


def serializar_snapshot_modo3(snapshot: Dict[str, Any]) -> bytes:
    """Devuelve JSON UTF-8 canonico, terminado siempre en una nueva linea LF."""
    texto = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return texto.encode("utf-8") + b"\n"


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
    """Genera y publica KMZ, snapshot, manifiesto y log; KML es degradable.

    La ausencia o invalidez de KMZ, snapshot o manifiesto impide publicar y
    lanza. Si se solicitó KML separado pero el KMZ obligatorio es válido, se
    publica un resultado ``partial`` con advertencia explícita.
    """

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
    transaction: Optional[OutputTransaction] = None

    try:
        _emit("preparando", "Validando registros y preparando carpeta de salida")

        if not request.registros:
            raise ValueError("No hay registros para generar el mapa.")
        if request.tipo not in MODO3_TIPOS_VALIDOS:
            raise ValueError(f"Tipo de Modo 3 no soportado: {request.tipo!r}.")

        try:
            carpeta_base = ensure_dir(request.carpeta_salida)
        except OSError as exc:
            raise OutputDirectoryError(f"No se pudo preparar la carpeta de salida: {exc}") from exc

        candidato_base = (
            sanear_nombre_archivo(request.output_base_name, sugerir_nombre_modo3(request.tipo, request.registros))
            if request.output_base_name
            else sugerir_nombre_modo3(request.tipo, request.registros)
        )
        candidato_unico = _generate_unique_case_name(carpeta_base, candidato_base)
        transaction = OutputTransaction.reserve(carpeta_base, candidato_unico)
        nombre_salida = transaction.name
        carpeta_caso = transaction.work_dir

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

        snapshot = construir_snapshot_modo3(
            tipo=request.tipo,
            registros=request.registros,
            config=config,
            kml_opcional=request.kml_opcional,
        )
        snapshot_path = os.path.join(
            carpeta_caso, f"{nombre_salida}_entrada_modo3.json"
        )
        with open(snapshot_path, "xb") as snapshot_file:
            snapshot_file.write(serializar_snapshot_modo3(snapshot))
        snapshot_sha256 = sha256_file(snapshot_path)

        # El DataFrame nace de la misma copia tipada que se serializo; no se
        # vuelve a leer estado mutable de Session ni se incluyen sus ids UI.
        registros_procesados = copy.deepcopy(snapshot["registros"])
        df = construir_dataframe_modo3(request.tipo, registros_procesados)

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
        if descartadas:
            warnings_list.append(f"Se descartaron {descartadas} registro(s) por coordenadas inválidas.")

        _emit("generando_hashes", "Validando productos y calculando hashes de integridad")
        _emit("finalizando", "Cerrando log y publicando resultados")

        _log(f"Modo manual (Modo 3) — tipo: {request.tipo}")
        _log(f"Registros procesados: {len(registros_procesados)}")
        _log(f"Coordenadas descartadas: {descartadas}")
        _log(f"Color: {request.color_hex or '(por defecto)'}")
        productos = [
            producto
            for producto in (
                "KMZ" if kmz_path else None,
                "KML" if kml_path else None,
                "Snapshot JSON",
            )
            if producto
        ]
        _log(f"Productos generados antes de validar: {', '.join(productos)}")
        _log(f"Carpeta final reservada: {transaction.final_dir}")

        # Politica B: el log se cierra antes del manifiesto, se publica junto
        # al caso, pero queda explicitamente fuera del conjunto hash.
        log_path_staging = _write_execution_log(carpeta_caso, nombre_salida, logs)

        # El digest aceptado se calculo antes de generar cartografia. Esta
        # comprobacion impide que un cambio posterior se legitime con un hash
        # nuevo al cerrar el manifiesto.
        if sha256_file(snapshot_path) != snapshot_sha256:
            raise InputIntegrityError(
                "El snapshot manual cambió durante el procesamiento."
            )

        publication = finalize_output(
            transaction,
            artifacts=(
                ArtifactSpec(role="kmz", path=kmz_path, required=True),
                ArtifactSpec(
                    role="kml",
                    path=kml_path,
                    required=False,
                    requested=bool(request.kml_opcional and kml_aplica),
                ),
                ArtifactSpec(
                    role="snapshot_json",
                    path=snapshot_path,
                    required=True,
                ),
            ),
            mode="3",
            manifest_name=f"{nombre_salida}_hashes.txt",
            input_metadata={
                "kind": "manual_json",
                "snapshot_name": os.path.basename(snapshot_path),
                "snapshot_sha256": snapshot_sha256,
            },
            excluded_paths=(log_path_staging,) if log_path_staging else (),
            pre_publish_check=lambda: verify_input_snapshot(
                snapshot_path, snapshot_sha256
            ),
        )

        warnings_list.extend(publication.warnings)
        kmz_final = publication.artifacts.get("kmz")
        kml_final = publication.artifacts.get("kml")
        snapshot_final = publication.artifacts.get("snapshot_json")
        log_path = None
        if log_path_staging:
            candidato_log = os.path.join(
                publication.final_dir, os.path.basename(log_path_staging)
            )
            if os.path.isfile(candidato_log):
                log_path = candidato_log

        summary = {
            "tipo": request.tipo,
            "registros_totales": len(registros_procesados),
            "coordenadas_descartadas": descartadas,
            "result_status": publication.status,
            "snapshot_path": snapshot_final,
            "snapshot_sha256": snapshot_sha256,
        }

        _emit("completado", "Análisis finalizado")

        return CaseResult(
            success=True,
            status=publication.status,
            output_dir=publication.final_dir,
            html_path=None,
            kmz_path=kmz_final,
            kml_path=kml_final,
            hashes_path=publication.manifest_path,
            log_path=log_path,
            logs=logs,
            warnings=warnings_list,
            errors=errors_list,
            summary=summary,
        )
    except Exception:
        if transaction is not None:
            transaction.abort()
        raise
