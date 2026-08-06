"""Servicio no interactivo de ejecución de análisis (Fase 1 Web).

``process_case()`` es una orquestación delgada, equivalente al flujo útil de
``main()`` en ``script_principal_bitacoras_refactory.py``, pero sin ninguna
de las partes que en ``main()`` son exclusivamente UI de consola. No duplica
lógica analítica: cada paso llama directamente a la misma función de
``tz_core`` que usa el CLI histórico.

Correspondencia con ``main()`` (qué se replica como orden de llamadas y qué
se omite por ser UI de consola):

    main()                                         process_case()
    ------------------------------------------      ------------------------
    collect_manual_mode_context (menú 1/2/3 +        OMITIDO — la opción se
      banner + color interactivo)                    deriva de CaseRequest
                                                       (con/sin filtro_tiempo)
                                                       y color_hex se aplica
                                                       directo a una copia
                                                       de config, sin prompt.
    gather_dataset_metadata(select_file=              REPLICADO tal cual —
      seleccionar_archivo, select_sheet=               select_file/select_sheet
      seleccionar_hoja_visible, ...)                   son funciones que
                                                        devuelven el valor ya
                                                        decidido en CaseRequest.
    _pick_color / solicitar_color_tema               OMITIDO — reemplazado
                                                       por mutación directa de
                                                       config["style"]["theme_hex"].
    log_dataset_stats("carga_inicial", ...)          REPLICADO (reuso directo).
    MappingWizard / run_manual_mapping_fn            OMITIDO — el mapeo ya fue
      (wizard conversacional interactivo)              decidido por el llamador
                                                        (CaseRequest.mapeo) y se
                                                        aplica con las mismas
                                                        funciones puras que usa
                                                        el wizard internamente
                                                        (apply_wizard_assignments,
                                                        finalize_manual_mapping_dataframe).
    run_ingestion_pipeline(...)                      REPLICADO tal cual, con
                                                       manual_qc_mapping=True y
                                                       run_manual_mapping_fn=None
                                                       (el mapeo ya está aplicado),
                                                       y con todos los callbacks
                                                       de decisión inyectados
                                                       desde CaseRequest.
    run_health_checks(...)                           REPLICADO (reuso directo).
    prepare_output_setup (identidad + nombre +        REPLICADO usando sus
      overrides de Top N + rutas)                      funciones puras
                                                        constituyentes
                                                        (prompt_case_identity,
                                                        suggest_case_name,
                                                        prompt_output_routing)
                                                        con callbacks que
                                                        devuelven decisiones ya
                                                        tomadas en CaseRequest,
                                                        en vez de prompts. El
                                                        nombre candidato se
                                                        hace único por
                                                        ejecución antes de
                                                        llegar a
                                                        prompt_output_routing
                                                        (ver
                                                        _generate_unique_case_name,
                                                        exclusivo de tz_web —
                                                        no toca
                                                        suggest_case_name).
    write_minimal_filter_log_if_needed               REPLICADO (reuso directo).
    prep_meta_unicos (alias/usuario/abonado)          REPLICADO (reuso directo);
                                                       identity_overrides (si se
                                                       proveen) se aplican antes.
    generar_kml(...)                                 REPLICADO, pero envuelto en
                                                       try/except propio: main()
                                                       deja esta llamada sin
                                                       proteger (una falla la
                                                       propagaría sin control);
                                                       process_case() la
                                                       degrada a un producto
                                                       parcial en vez de abortar
                                                       todo el análisis.
    run_outputs_flow -> produce_case_outputs         produce_case_outputs se
                                                       llama DIRECTO, sin pasar
                                                       por run_outputs_flow: ese
                                                       wrapper añade un
                                                       except Exception genérico
                                                       que colapsa cualquier
                                                       fallo a None sin
                                                       distinguirlo — aquí se
                                                       prefiere dejar que
                                                       produce_case_outputs (que
                                                       ya maneja cada producto
                                                       de forma independiente)
                                                       hable por sí mismo.
    print() / log() global como canal principal      OMITIDO — todo pasa por
                                                       un logger local a esta
                                                       ejecución (ver más abajo);
                                                       nunca se usa
                                                       tz_core.logging_utils (su
                                                       estado es un módulo
                                                       global compartido entre
                                                       ejecuciones) ni se
                                                       redirige sys.stdout.

CONFIG — nunca se muta el dict cacheado por ``tz_core.config_loader.get_config()``:
se toma una copia profunda (``copy.deepcopy``) al inicio de cada ejecución y
solo esa copia recibe los overrides de esta corrida (solo_kmz, theme_hex,
top_antenas, top_contactos). config.json nunca se escribe: los tres
callbacks que en el flujo interactivo podrían persistir sinónimos
(``wizard_io_factory``, ``persist_synonym_fn``, ``validate_schema_fn``) se
inyectan como funciones canario que fallan ruidosamente si algo las invoca
— bajo ``manual_qc_mapping=True`` con mapeo ya aplicado, ``run_ingestion_pipeline``
nunca debería llamarlas; si lo hiciera, es un defecto y debe romper el test.

LOGS — cada llamada a ``process_case()`` usa una lista de log en memoria
propia (closure local, no estado de módulo), por lo que dos ejecuciones
consecutivas (incluso concurrentes en el futuro, si se levantara la
restricción de ejecución serial) nunca comparten ni mezclan sus logs.

EJECUCIÓN SERIAL — un ``threading.Lock`` de módulo con adquisición no
bloqueante protege contra una segunda ejecución simultánea; si el lock ya
está tomado, se lanza ``AnalysisInProgressError`` de inmediato (sin esperar).
El lock siempre se libera en un ``finally``.
"""

from __future__ import annotations

import copy
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from tz_core.analytics import construir_seccion_todos_contactos
from tz_core.bitacora_io import (
    cargar_excel_con_normalizacion,
    ensure_dir,
    listar_todas_hojas,
    obtener_hojas_visibles,
)
from tz_core.config_loader import get_config
from tz_core.exceptions import ArchivoNoProcesableError
from tz_core.file_utils import escribe_hashes_txt, relocate_kmz_file
from tz_core.health_utils import log_dataset_stats, run_health_checks
from tz_core.html.assembler import generar_informe_html
from tz_core.ingestion_pipeline import run_ingestion_pipeline
from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.kml_generator import generar_kml
from tz_core.manual_flow import write_minimal_filter_log_if_needed
from tz_core.mapping_wizard import (
    _check_duplicate_column_assignments,
    apply_wizard_assignments,
    finalize_manual_mapping_dataframe,
)
from tz_core.output_pipeline import produce_case_outputs
from tz_core.schema_utils import prep_meta_unicos
from tz_core.time_filters import FiltroTiempo, aplicar_filtros_tiempo
from tz_core.ui_utils import (
    gather_dataset_metadata,
    prompt_case_identity,
    prompt_output_routing,
    suggest_case_name,
)
from tz_core.user_paths import default_output_cwd_fn
from tz_core.utils import sanear_nombre_archivo
from tz_core.validation_utils import validar_datos

__all__ = [
    "CaseRequest",
    "CaseResult",
    "ProgressUpdate",
    "process_case",
    "AnalysisInProgressError",
    "ArchivoNoProcesableError",
    "CaseFileNotFoundError",
    "CaseLoadError",
    "InvalidMappingError",
    "OutputDirectoryError",
    "SheetNotFoundError",
]


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------
# ArchivoNoProcesableError se reexporta desde tz_core.exceptions (ya existe y
# la lanza run_ingestion_pipeline); las siguientes son nuevas, propias de la
# frontera de este servicio.


class CaseFileNotFoundError(Exception):
    """El archivo de entrada no existe o no es un archivo regular."""


class SheetNotFoundError(Exception):
    """La hoja solicitada no existe en el archivo Excel de entrada."""


class CaseLoadError(Exception):
    """El archivo existe pero no pudo cargarse (formato corrupto/ilegible)."""


class InvalidMappingError(Exception):
    """El mapeo de columnas provisto es inválido (vacío, tipo desconocido o
    columna referenciada inexistente)."""


class OutputDirectoryError(Exception):
    """La carpeta de salida no pudo crearse o usarse (p. ej. sin permisos)."""


class AnalysisInProgressError(Exception):
    """Ya hay un análisis en ejecución; TZ Analyzer v1.1 solo permite uno a
    la vez (ver sección 9 del encargo de Fase 1 Web)."""


# ---------------------------------------------------------------------------
# Contrato tipado
# ---------------------------------------------------------------------------

_PROGRESS_STAGES = (
    "validando_entrada",
    "cargando_archivo",
    "aplicando_mapeo",
    "normalizando_y_qc",
    "aplicando_filtros",
    "generando_productos",
    "verificando_resultados",
    "finalizado",
)


@dataclass(frozen=True)
class ProgressUpdate:
    """Evento emitido en una transición real del flujo de ``process_case()``.

    ``stage`` es uno de ``_PROGRESS_STAGES`` (mismo orden en que se emiten
    dentro de una ejecución exitosa); ``sequence`` es un contador 1-based
    dentro de la ejecución actual, útil para que un consumidor detecte
    eventos fuera de orden o perdidos.
    """

    stage: str
    message: str
    sequence: int


@dataclass
class CaseRequest:
    """Entrada explícita y tipada para ``process_case()``.

    Todo lo que en el flujo interactivo de ``main()`` requeriría un prompt
    tiene aquí un campo con una decisión ya tomada. Ningún campo dispara
    ``input()``, ``safe_input`` ni Tkinter.
    """

    # Entrada de datos
    ruta_archivo: str
    carpeta_salida: str
    mapeo: Dict[str, Tuple[str, Any]]
    hoja: Optional[str] = None

    # Filtros temporales ya estructurados (None = bitácora completa, sin
    # filtro; formato idéntico al que produce tz_core.time_filters.FiltroTiempo)
    filtro_tiempo: Optional[FiltroTiempo] = None

    # Identidad del caso/sujeto
    tipo_bitacora: str = ""  # "I" (IMEI) | "T" (TEL) | "" (auto)
    identity_overrides: Optional[Dict[str, str]] = None  # alias/nombre_usuario/abonado

    # Opciones de salida
    top_antenas: Optional[int] = None  # None = usar default de config.json
    top_contactos: Optional[int] = None
    color_hex: Optional[str] = None  # None = usar theme_hex de config.json
    solo_kmz: Optional[bool] = None  # None = usar config.json tal cual
    output_base_name: Optional[str] = None  # None = usar el nombre sugerido

    # Decisiones ante ambigüedad/QC (solo se usan si el motor las necesita)
    date_order_decision: str = "1"  # "1"=DD/MM/AAAA, "2"=MM/DD/AAAA
    duration_unit_decision: str = "desconocida"  # milisegundos|segundos|minutos|desconocida
    qc_bloqueante_decision: str = "S"  # "S"=continuar pese a la advertencia QC

    # Progreso
    on_progress: Optional[Callable[[ProgressUpdate], None]] = None


@dataclass
class CaseResult:
    """Resultado estructurado de ``process_case()``.

    ``success`` es True siempre que la función retorne (no lance una
    excepción de dominio): un producto individual faltante se refleja como
    ``None`` en su campo de ruta + una entrada en ``warnings``/``errors``,
    nunca como una afirmación falsa de que el archivo existe.
    """

    success: bool
    output_dir: Optional[str] = None
    html_path: Optional[str] = None
    kmz_path: Optional[str] = None
    hashes_path: Optional[str] = None
    log_path: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ejecución serial (sección 9)
# ---------------------------------------------------------------------------

_EXECUTION_LOCK = threading.Lock()

# Campos que MappingWizard tipa como numéricos al aplicar asignaciones
# (tz_core.mapping_wizard.MappingWizard.__init__: self.tipar_numericos).
# Se replica aquí el mismo conjunto porque _apply_mapeo llama directamente a
# apply_wizard_assignments (función pura), no al wizard.
_NUMERIC_MAPPING_FIELDS = {"lat", "long", "azimut", "duracion"}

_IDENTITY_FIELDS = ("alias", "nombre_usuario", "abonado")


def _canary(name: str) -> Callable[..., Any]:
    """Callback que revienta si algo lo invoca.

    Se inyecta en los puntos de ``run_ingestion_pipeline`` que solo se
    alcanzan bajo mapeo interactivo (``manual_qc_mapping=False`` o
    ``run_manual_mapping_fn`` provisto) — ninguno de los dos aplica aquí, así
    que si alguno de estos callbacks se invoca, es un defecto real del
    servicio (una ruta de código asumida muerta que no lo está) y debe
    fallar ruidosamente en vez de arrastrar comportamiento interactivo
    silencioso.
    """

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(
            f"{name} no debía invocarse en process_case(): el mapeo ya fue "
            "decidido de forma no interactiva (CaseRequest.mapeo)."
        )

    return _raise


def _validate_mapeo(df: Any, mapeo: Dict[str, Tuple[str, Any]]) -> None:
    """Valida la forma del mapeo antes de aplicarlo (sección 7: 'mapeo inválido').

    No duplica reglas de negocio de mapeo (eso lo hace
    ``apply_wizard_assignments``); solo verifica precondiciones de forma que,
    si se ignoraran, producirían un DataFrame silenciosamente incompleto en
    vez de un error claro.
    """

    if not mapeo:
        raise InvalidMappingError("El mapeo de columnas está vacío.")

    columnas_lower = {str(c).strip().lower() for c in df.columns}
    algo_asignado = False

    for canonical, assignment in mapeo.items():
        if not (isinstance(assignment, tuple) and len(assignment) == 2):
            raise InvalidMappingError(
                f"Asignación inválida para '{canonical}': se esperaba una "
                f"tupla (tipo, valor), se recibió {assignment!r}."
            )
        tipo, valor = assignment
        if tipo not in ("col", "fijo", "omitido"):
            raise InvalidMappingError(
                f"Tipo de asignación inválido para '{canonical}': {tipo!r} "
                "(debe ser 'col', 'fijo' u 'omitido')."
            )
        if tipo == "col":
            if not valor or (
                valor not in df.columns
                and str(valor).strip().lower() not in columnas_lower
            ):
                raise InvalidMappingError(
                    f"La columna '{valor}' asignada a '{canonical}' no existe "
                    "en el archivo de entrada."
                )
            algo_asignado = True
        elif tipo == "fijo":
            algo_asignado = True

    if not algo_asignado:
        raise InvalidMappingError(
            "El mapeo no asigna ningún campo (todas las entradas son 'omitido')."
        )


def _apply_mapeo(
    df: Any,
    mapeo: Dict[str, Tuple[str, Any]],
    *,
    output_fn: Callable[[str], None],
) -> Any:
    """Aplica el mapeo ya decidido usando las mismas funciones puras que
    ``MappingWizard`` usa internamente (``apply_wizard_assignments``,
    ``finalize_manual_mapping_dataframe``), sin conducir el wizard como
    conversación simulada."""

    _check_duplicate_column_assignments(mapeo, output_fn)
    mapped = apply_wizard_assignments(
        df, mapeo, numeric_fields=_NUMERIC_MAPPING_FIELDS, writer=output_fn
    )
    return finalize_manual_mapping_dataframe(mapped)


def _generate_unique_case_name(carpeta_base: str, candidate: str) -> str:
    """Garantiza un nombre de carpeta de caso distinto por ejecución.

    Exclusivo de ``tz_web``: no toca ``tz_core.ui_utils.suggest_case_name``
    ni ``prompt_case_identity``, cuyo timestamp embebido tiene precisión de
    minuto — suficiente para una invocación humana del CLI, insuficiente
    para un servicio que puede recibir dos ``process_case()`` dentro del
    mismo minuto (ver corrección precommit de unicidad de carpeta).

    Estrategia en dos capas:
    1. Sufijo de alta resolución (HHMMSS + microsegundos) sobre el nombre
       candidato — evita la colisión típica entre dos ejecuciones reales.
    2. Sufijo incremental ``_02``, ``_03``... como red de seguridad final,
       por si ``carpeta_base/candidato_unico`` ya existiera en disco pese al
       sufijo de alta resolución (reloj no monotónico en algunos entornos,
       o el mismo ``output_base_name`` explícito reutilizado a propósito).

    ``candidate`` debe llegar ya saneado (ver ``sanear_nombre_archivo``): la
    función solo concatena dígitos y guiones bajos, por lo que el resultado
    permanece válido como nombre de archivo/carpeta.
    """

    marca = datetime.now().strftime("%H%M%S%f")
    base_unica = f"{candidate}_{marca}"

    if not os.path.exists(os.path.join(carpeta_base, base_unica)):
        return base_unica

    intento = 2
    while True:
        candidato = f"{base_unica}_{intento:02d}"
        if not os.path.exists(os.path.join(carpeta_base, candidato)):
            return candidato
        intento += 1


def _write_execution_log(folder: str, base_name: str, logs: List[str]) -> Optional[str]:
    """Escribe el log de esta ejecución a disco; nunca lanza (I/O best-effort)."""

    try:
        ensure_dir(folder)
        path = os.path.join(folder, f"{base_name}_ejecucion_log.txt")
        with open(path, "w", encoding="utf-8", errors="ignore") as fh:
            fh.write("\n".join(logs))
        return path
    except OSError:
        return None


def process_case(request: CaseRequest) -> CaseResult:
    """Ejecuta un análisis completo de punta a punta, sin ninguna interacción.

    Ver el docstring del módulo para la correspondencia detallada con
    ``main()``. Lanza excepciones de dominio (``CaseFileNotFoundError``,
    ``SheetNotFoundError``, ``CaseLoadError``, ``InvalidMappingError``,
    ``OutputDirectoryError``, ``ArchivoNoProcesableError``,
    ``AnalysisInProgressError``) para condiciones que impiden producir un
    resultado; para fallos parciales de un producto individual (HTML, KMZ o
    hashes) retorna un ``CaseResult`` con esa ruta en ``None`` y el motivo en
    ``warnings``/``errors``.
    """

    if not _EXECUTION_LOCK.acquire(blocking=False):
        raise AnalysisInProgressError(
            "Ya hay un análisis en ejecución; espere a que finalice antes de iniciar otro."
        )

    logs: List[str] = []
    sequence = 0
    carpeta_salida_abs: Optional[str] = None
    nombre_salida = "proceso"

    def _log(msg: str) -> None:
        logs.append(str(msg))

    def _emit(stage: str, message: str) -> None:
        nonlocal sequence
        sequence += 1
        _log(f"[{stage}] {message}")
        if request.on_progress is not None:
            request.on_progress(ProgressUpdate(stage=stage, message=message, sequence=sequence))

    try:
        try:
            # ---- 1. validando_entrada ------------------------------------
            _emit("validando_entrada", "Verificando archivo, hoja y carpeta de salida")

            ruta = (request.ruta_archivo or "").strip().strip('"')
            if not ruta or not os.path.isfile(ruta):
                raise CaseFileNotFoundError(
                    f"No se encontró el archivo de entrada: {request.ruta_archivo!r}"
                )

            if request.hoja:
                visibles, _err = obtener_hojas_visibles(ruta)
                disponibles = visibles if visibles else (listar_todas_hojas(ruta) or [])
                if disponibles and request.hoja not in disponibles:
                    raise SheetNotFoundError(
                        f"La hoja {request.hoja!r} no existe en el archivo. "
                        f"Hojas disponibles: {disponibles}"
                    )

            if not request.carpeta_salida:
                raise OutputDirectoryError("Debe indicarse una carpeta de salida explícita.")
            try:
                carpeta_salida_abs = ensure_dir(request.carpeta_salida)
            except OSError as exc:
                raise OutputDirectoryError(
                    f"No se pudo crear/usar la carpeta de salida: {exc}"
                ) from exc

            config = copy.deepcopy(get_config() or {})
            config.setdefault("salida", {})
            if request.solo_kmz is not None:
                config["salida"]["solo_kmz"] = bool(request.solo_kmz)
            if request.color_hex:
                config.setdefault("style", {})["theme_hex"] = request.color_hex

            # ---- 2. cargando_archivo -------------------------------------
            _emit("cargando_archivo", f"Cargando '{os.path.basename(ruta)}'")

            dataset = gather_dataset_metadata(
                log_fn=_log,
                select_file=lambda: ruta,
                select_sheet=lambda _archivo: request.hoja,
                load_dataframe=cargar_excel_con_normalizacion,
                output_fn=_log,
            )
            if dataset is None:
                raise CaseLoadError(
                    f"No se pudo cargar el archivo Excel: {request.ruta_archivo!r} "
                    "(ver logs para el detalle)."
                )

            df = dataset.dataframe
            hoja = dataset.hoja
            cols_originales = list(dataset.columnas)
            log_dataset_stats("carga_inicial", df, logger=_log)

            # ---- 3. aplicando_mapeo ---------------------------------------
            _emit("aplicando_mapeo", "Aplicando mapeo de columnas decidido")

            _validate_mapeo(df, request.mapeo)
            df = _apply_mapeo(df, request.mapeo, output_fn=_log)

            if request.identity_overrides:
                for campo, valor in request.identity_overrides.items():
                    if campo in _IDENTITY_FIELDS and valor:
                        df[campo] = valor

            # ---- 4. normalizando_y_qc --------------------------------------
            _emit("normalizando_y_qc", "Normalizando fecha/hora y ejecutando QC")

            ingestion = run_ingestion_pipeline(
                df=df,
                config=config,
                original_columns=cols_originales,
                manual_qc_mapping=True,
                alias_visibles=None,
                wizard_io_factory=_canary("wizard_io_factory"),
                persist_synonym_fn=_canary("persist_synonym_fn"),
                validate_schema_fn=_canary("validate_schema_fn"),
                validar_datos_fn=validar_datos,
                time_filter_option="2" if request.filtro_tiempo else "1",
                solicitar_filtros_fn=lambda: request.filtro_tiempo,
                aplicar_filtros_fn=aplicar_filtros_tiempo,
                logger=_log,
                output_fn=_log,
                run_manual_mapping_fn=None,
                preguntar_unidad_duracion_fn=lambda: request.duration_unit_decision,
                date_order_prompt_fn=lambda _msg: request.date_order_decision,
                qc_bloqueante_prompt_fn=lambda _msg: request.qc_bloqueante_decision,
            )

            df = ingestion.dataframe
            log_dataset_stats("post_ingestion", df, logger=_log)

            # ---- 5. aplicando_filtros --------------------------------------
            _emit(
                "aplicando_filtros",
                ingestion.time_filters.summary or "Sin filtro de tiempo",
            )

            if df.empty:
                raise ArchivoNoProcesableError(
                    "No hay registros para procesar después de aplicar filtros."
                )

            if not run_health_checks(
                df,
                logger=_log,
                output_fn=_log,
                capabilities_report=ingestion.capabilities_report,
            ):
                raise ArchivoNoProcesableError(
                    "Los chequeos de salud de datos impidieron continuar."
                )

            # ---- 6. generando_productos -------------------------------------
            _emit("generando_productos", "Generando KML/KMZ, HTML y hashes")

            nombre_base = os.path.splitext(os.path.basename(ruta))[0]

            identity = prompt_case_identity(
                df=df,
                input_fn=lambda _msg: request.tipo_bitacora,
                output_fn=_log,
                now_fn=datetime.now,
            )
            suggestion = suggest_case_name(
                df=df,
                identity=identity,
                filters=ingestion.time_filters.filters if ingestion.time_filters.enabled else None,
                timestamp_fn=datetime.now,
                sanitize_fn=lambda s: sanear_nombre_archivo(s, nombre_base),
            )
            base_auto = suggestion.base_name

            try:
                top_antenas = (
                    int(request.top_antenas)
                    if request.top_antenas is not None
                    else int(config.get("html", {}).get("top_antenas_n", 10))
                )
            except (TypeError, ValueError):
                top_antenas = 10
            try:
                top_contactos = (
                    int(request.top_contactos)
                    if request.top_contactos is not None
                    else int(config.get("html", {}).get("top_contactos_n", 10))
                )
            except (TypeError, ValueError):
                top_contactos = 10

            config["top_antenas"] = top_antenas
            config["top_contactos"] = top_contactos
            override_tops = {"antenas": top_antenas, "contactos": top_contactos}

            # Nombre candidato (override explícito del llamador, o el
            # sugerido por suggest_case_name) saneado y luego hecho único
            # por ejecución — ver _generate_unique_case_name: el timestamp
            # embebido por suggest_case_name tiene precisión de minuto, que
            # no basta para un servicio con más de una corrida por minuto.
            candidato_base = sanear_nombre_archivo(
                request.output_base_name or base_auto, base_auto
            )
            nombre_unico = _generate_unique_case_name(carpeta_salida_abs, candidato_base)

            routing = prompt_output_routing(
                base_name=base_auto,
                input_fn=lambda _msg: nombre_unico,
                output_fn=_log,
                sanitize_fn=lambda s: sanear_nombre_archivo(s, base_auto),
                select_folder=lambda: carpeta_salida_abs,
                cwd_fn=default_output_cwd_fn,
                ensure_dir=ensure_dir,
                separate_kml=bool(config.get("salida", {}).get("separar_kml_kmz", False)),
            )

            nombre_salida = routing.base_name
            carpeta_base = routing.base_folder
            carpeta_salida_caso = routing.output_folder
            archivo_kml = routing.kml_path

            write_minimal_filter_log_if_needed(
                result=ingestion.time_filters,
                df=df,
                output_folder=carpeta_salida_caso,
                logger=_log,
            )

            df = prep_meta_unicos(
                df,
                [(f, f) for f in _IDENTITY_FIELDS],
                logger=_log,
            )

            desc_coords = 0
            try:
                archivo_kml, desc_coords = generar_kml(
                    df,
                    archivo_kml,
                    config=config,
                    flat=False,
                    override_tops=override_tops,
                    duracion_estado=ingestion.duracion_estado,
                )
            except Exception as exc:  # noqa: BLE001 - degradado a producto parcial, ver docstring
                _log(f"[ERROR] Generación de KML/KMZ falló: {exc}")

            outputs = produce_case_outputs(
                df=df,
                config=config,
                override_tops=override_tops,
                nombre_salida=nombre_salida,
                archivo_kml=archivo_kml,
                carpeta_base=carpeta_base,
                carpeta_salida=carpeta_salida_caso,
                archivo_entrada=ruta,
                hoja=hoja,
                error_report_path=None,
                discarded_coords=desc_coords,
                build_interactions_section=construir_seccion_interacciones,
                build_contacts_section=construir_seccion_todos_contactos,
                generar_html_fn=generar_informe_html,
                relocate_kmz_fn=relocate_kmz_file,
                write_hashes_fn=escribe_hashes_txt,
                summarize_fn=lambda **_kwargs: None,
                logger=_log,
                output_fn=_log,
                path_exists=os.path.exists,
                cwd_fn=default_output_cwd_fn,
                log_file_path=None,
                duracion_estado=ingestion.duracion_estado,
                capabilities_report=ingestion.capabilities_report,
            )

            # ---- 7. verificando_resultados -----------------------------------
            _emit(
                "verificando_resultados",
                "Comprobando existencia física de los productos generados",
            )

            warnings_list: List[str] = []
            errors_list: List[str] = []

            def _verify(reported: Optional[str], label: str) -> Optional[str]:
                if not reported:
                    warnings_list.append(f"No se generó el producto: {label}.")
                    return None
                if not os.path.isfile(reported):
                    errors_list.append(
                        f"El producto {label} fue reportado pero no existe físicamente: {reported}"
                    )
                    return None
                return reported

            html_path = _verify(outputs.informe_html, "informe HTML")
            kmz_path = _verify(outputs.kmz_path, "KMZ")
            hashes_path = _verify(outputs.hashes_path, "hashes")

            for line in logs:
                if "[ERROR]" in line:
                    errors_list.append(line)
                elif "[WARN]" in line:
                    warnings_list.append(line)

            log_path = _write_execution_log(carpeta_salida_caso, nombre_salida, logs)

            _emit("finalizado", "Análisis finalizado")

            summary = {
                "filas_totales": int(len(df)),
                "coordenadas_descartadas": int(desc_coords),
                "capacidades_procesable": (
                    bool(ingestion.capabilities_report.procesable)
                    if ingestion.capabilities_report is not None
                    else None
                ),
                "filtro_tiempo": ingestion.time_filters.summary,
                "top_antenas": top_antenas,
                "top_contactos": top_contactos,
            }

            return CaseResult(
                success=True,
                output_dir=carpeta_salida_caso,
                html_path=html_path,
                kmz_path=kmz_path,
                hashes_path=hashes_path,
                log_path=log_path,
                logs=list(logs),
                warnings=warnings_list,
                errors=errors_list,
                summary=summary,
            )
        except Exception:
            if carpeta_salida_abs:
                _write_execution_log(carpeta_salida_abs, f"{nombre_salida}_fallo", logs)
            raise
    finally:
        _EXECUTION_LOCK.release()
