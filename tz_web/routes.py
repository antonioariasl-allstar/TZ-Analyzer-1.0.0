"""tz_web.routes — rutas HTTP de la aplicación local (Fase 2 Web).

Todas las rutas escuchan exclusivamente a través del servidor creado por
``tz_web.app.create_app()`` (host ``127.0.0.1``). Cada pantalla del flujo
(archivo, mapeo, configuración, procesamiento, resultados) tiene su propia
ruta GET (mostrar) y, cuando aplica, POST (avanzar); el estado de cada caso
vive en ``tz_web.state.Session`` — nunca en base de datos.

Ningún dato enviado por el navegador se usa directamente como ruta de
archivo a abrir: las acciones "abrir HTML/KMZ/hashes/carpeta" solo aceptan
un identificador cerrado (``kind``) y resuelven la ruta real desde el
``CaseResult`` guardado en el servidor (ver ``_resolve_open_path``).
"""

from __future__ import annotations

import colorsys
import copy
import os
import threading
import uuid
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session as flask_session,
    url_for,
)
from werkzeug.utils import secure_filename

from tz_core.bitacora_io import cargar_excel_con_normalizacion, listar_todas_hojas, obtener_hojas_visibles
from tz_core.capabilities import detectar_capacidades
from tz_core.config_loader import get_config
from tz_core.field_roles import WIZARD_ORDER_PRIMARY, WIZARD_ORDER_SECONDARY
from tz_core.folder_dialog import (
    FolderDialogBusyError,
    FolderDialogInterruptedError,
    FolderDialogUnavailableError,
    pick_folder,
)
from tz_core.mapping_wizard import FIELD_CONTEXT
from tz_core.user_paths import resolve_default_output_dir
from tz_web import help_content
from tz_web import lifecycle
from tz_web import manual_validators as mv
from tz_web import state
from tz_web.field_catalog import FIELD_DESCRIPTIONS, FIELD_GROUPS, FIELD_LABELS
from tz_web.output_transaction import (
    InputIntegrityError,
    OutputValidationError,
    RESULT_PARTIAL,
    RESULT_SUCCESS,
    create_input_snapshot,
    sha256_file,
)
from tz_web.services_modo3 import (
    MODO3_TIPO_ANTENA,
    MODO3_TIPO_PUNTO_LIBRE,
    MODO3_TIPOS_VALIDOS,
    Modo3Request,
    process_case_modo3,
    sugerir_nombre_modo3,
)
from tz_web.filter_catalog import FILTRO_TIEMPO_CATALOG, FILTRO_TIEMPO_ORDER
from tz_web.scope import describir_alcance, parse_fecha_iso
from tz_web.services import (
    CaseRequest,
    InvalidMappingError,
    ProgressUpdate,
    _apply_mapeo,
    _validate_mapeo,
    preview_suggested_case_name,
    process_case,
)

bp = Blueprint("tz_web", __name__)

# Puerta de proceso dedicada al selector. Se adquiere sin espera. Mientras
# esta tomada solo se lee lifecycle (selector -> lifecycle); lifecycle nunca
# adquiere esta puerta, por lo que no existe el orden inverso. Se libera antes
# de mutation_guard/state.run_lock().
_OUTPUT_FOLDER_SELECTOR_LOCK = threading.Lock()
_OUTPUT_FOLDER_SELECTOR_BUSY_MESSAGE = "Ya existe un selector de carpeta abierto."

CANONICAL_FIELDS: Tuple[str, ...] = WIZARD_ORDER_PRIMARY + WIZARD_ORDER_SECONDARY

CAPABILITY_LABELS: Dict[str, str] = {
    "identificacion": "Identificación",
    "cronologia": "Cronología",
    "filtros_temporales": "Filtros temporales",
    "antenas": "Antenas",
    "antenas_por_horario": "Antenas por horario",
    "kml": "Mapa KML/KMZ",
    "heatmap": "Mapa de calor",
    "contactos": "Contactos",
    "tipo_evento": "Tipo de evento",
    "duracion": "Duración",
    "orientacion": "Orientación (azimut)",
    "metadatos": "Metadatos",
    "hashes": "Hashes de integridad",
}

_TIPO_BITACORA_LABELS = {"": "Automático", "I": "Por IMEI", "T": "Por teléfono"}
_DURATION_UNIT_LABELS = {
    "milisegundos": "Milisegundos",
    "segundos": "Segundos",
    "minutos": "Minutos",
    "desconocida": "Desconocida (no calcular duración)",
}
_DATE_ORDER_LABELS = {"1": "DD/MM/AAAA", "2": "MM/DD/AAAA"}
MSG_CARPETA_SALIDA_REQUERIDA = (
    "Seleccione una carpeta de salida en \"Preparar análisis\" antes de generar el análisis."
)

_FILTRO_TIPO_LABELS = {
    "ninguno": "Sin filtro (bitácora completa)",
    "dia": "Día específico",
    "rango_dias": "Rango de días",
    "rango_horas_dia": "Rango de horas en un día específico",
    "rango_horas": "Rango de horas (todos los días)",
}

_OPEN_KIND_ATTRS = {
    "html": "html_path",
    "kmz": "kmz_path",
    "hashes": "hashes_path",
    "log": "log_path",
    "kml": "kml_path",
}

# Agrupación visual del formulario de mapeo (paginado en JS, sección 3 del
# encargo de mejora de flujo). Cubre exactamente los 14 campos canónicos,
# en 7 grupos de 2 campos cada uno. Única fuente de verdad: ``tz_web.field_catalog``
# — los templates y el JS de paginación leen ``FIELD_GROUPS`` desde ahí (vía
# este re-import), no la duplican.


# ---------------------------------------------------------------------------
# Sesión de trabajo — identificador mínimo en cookie firmada de Flask.
# ---------------------------------------------------------------------------


def _current_session(create: bool = True) -> Optional[state.Session]:
    session_id = flask_session.get("case_id")
    case = state.get_session(session_id)
    if case is None and create:
        case = state.create_session()
        flask_session["case_id"] = case.id
    elif case is not None:
        state.touch(case)
    return case


def _mutation_guard(redirect_endpoint: str):
    """Protege una ruta que cambia o descarta estado del caso.

    La política y el mensaje viven en un único punto. ``state.mutation_guard``
    conserva el mismo lock que usa la reserva de ejecución durante toda la
    vista, evitando una carrera entre comprobar el estado y mutarlo.
    """
    def _decorate(view):
        @wraps(view)
        def _guarded(*args, **kwargs):
            with state.mutation_guard() as allowed:
                if allowed:
                    return view(*args, **kwargs)

                # No usar _current_session(): incluso actualizar ``updated_at``
                # violaría el contrato de dejar el caso intacto al rechazar.
                case = state.get_session(flask_session.get("case_id"))
                flash(state.MSG_ANALYSIS_IN_PROGRESS, "error")
                if case is not None and case.status == state.STATUS_RUNNING:
                    return redirect(url_for("tz_web.processing_screen"))
                return redirect(url_for(redirect_endpoint))

        return _guarded
    return _decorate


def _flash_start_rejected(reason: Optional[str]) -> None:
    """Mensaje de UI para un arranque rechazado por ``try_start_run_detailed``
    (sección 1 del MB5): distingue "ya hay un análisis en curso" de "cierre
    pendiente", en vez de asumir siempre la primera causa."""
    message = (
        state.MSG_SHUTDOWN_PENDING
        if reason == state.RUN_START_REJECTED_SHUTDOWN
        else state.MSG_ANALYSIS_IN_PROGRESS
    )
    flash(message, "error")


def _open_with_default_app(path: str) -> None:
    """Abre ``path`` con la aplicación asociada del sistema operativo.

    Aislado en una función propia para que las pruebas puedan sustituirlo
    sin abrir aplicaciones reales durante la suite automatizada.
    """
    if hasattr(os, "startfile"):
        os.startfile(path)  # noqa: S606 - ruta ya validada contra CaseResult, ver _resolve_open_path


# ---------------------------------------------------------------------------
# Selector de carpeta de salida (MICROBLOQUE 6) — compartido por Modo 1/2
# ("Preparar análisis", configure_final.html) y Modo 3 (modo3_preparar.html).
#
# Deliberadamente NO usa ``_mutation_guard``/``state.mutation_guard()``
# alrededor de ``pick_folder()``: ese lock (``state._RUNNING_LOCK``) también
# lo necesitan ``try_start_run_detailed`` y ``lifecycle.request_shutdown``, y
# el diálogo nativo puede quedar abierto un tiempo indefinido mientras el
# usuario decide. Sostenerlo durante esa espera bloquearía cualquier otra
# mutación, el arranque de un análisis real y hasta el cierre del backend —
# justo lo que la sección de seguridad/concurrencia del encargo prohíbe. En
# su lugar: un chequeo previo barato (sin reservar nada) antes de abrir el
# diálogo, y un ``mutation_guard()`` acotado solo alrededor de la escritura
# final a la sesión, una vez que el usuario ya decidió.
# ---------------------------------------------------------------------------


def _reject_reason_for_mutation() -> Optional[str]:
    """Motivo de rechazo (``state.RUN_START_REJECTED_*``) para una operación
    que debe respetar "análisis activo"/"cierre pendiente" sin competir por
    el mismo cupo que ``try_start_run_detailed`` (que además reserva un
    turno de ejecución real — no aplica aquí, elegir una carpeta no es un
    análisis). ``None`` si la operación puede proceder."""
    if state.is_any_run_active():
        return state.RUN_START_REJECTED_BUSY
    if lifecycle.get_state() != lifecycle.RUNNING:
        return state.RUN_START_REJECTED_SHUTDOWN
    return None


def _message_for_rejection(reason: str) -> str:
    return (
        state.MSG_SHUTDOWN_PENDING
        if reason == state.RUN_START_REJECTED_SHUTDOWN
        else state.MSG_ANALYSIS_IN_PROGRESS
    )


@bp.route("/output-folder/select", methods=["POST"])
def select_output_folder():
    """Abre el selector nativo de carpetas y, si el usuario confirma una
    elección válida, la persiste en ``case.carpeta_salida``.

    Responde JSON siempre (endpoint consumido vía ``fetch`` desde
    configure_final.html/modo3_preparar.html, ver tzSeleccionarCarpetaSalida
    en app.js), nunca un redirect: no hay nada que renderizar de nuevo, y el
    botón que lo invoca no debe recargar el resto del formulario en curso
    (nombre de salida, tipo de bitácora, etc. — ver sección UX del encargo).
    """
    case = _current_session(create=False)
    if case is None:
        return jsonify({"status": "error", "message": "No hay una sesión activa."}), 400

    reason = _reject_reason_for_mutation()
    if reason is not None:
        return jsonify({"status": "error", "message": _message_for_rejection(reason)}), 409

    if not _OUTPUT_FOLDER_SELECTOR_LOCK.acquire(blocking=False):
        return jsonify({
            "status": "error",
            "message": _OUTPUT_FOLDER_SELECTOR_BUSY_MESSAGE,
        }), 409

    try:
        carpeta_inicial = case.carpeta_salida or resolve_default_output_dir(
            warn=lambda _msg: None
        )
        try:
            seleccionada = pick_folder(
                initial_dir=carpeta_inicial,
                cancel_requested=lambda: lifecycle.get_state() != lifecycle.RUNNING,
            )
        except FolderDialogInterruptedError:
            return jsonify({
                "status": "error",
                "message": state.MSG_SHUTDOWN_PENDING,
            }), 409
        except FolderDialogBusyError:
            # Defensa secundaria del registro para el caso extremo en que el
            # SO no confirme la muerte de un hijo anterior. El mutex cubre el
            # camino normal y este rechazo conserva la misma semantica HTTP.
            return jsonify({
                "status": "error",
                "message": _OUTPUT_FOLDER_SELECTOR_BUSY_MESSAGE,
            }), 409
        except FolderDialogUnavailableError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 502
    finally:
        _OUTPUT_FOLDER_SELECTOR_LOCK.release()

    if seleccionada is None:
        # Cancelado: la selección existente (si la había) no se toca.
        return jsonify({"status": "cancelled", "carpeta_salida": case.carpeta_salida}), 200

    # Reconfirmar bajo el lock real, acotado a la escritura: el diálogo pudo
    # haber estado abierto un buen rato, tiempo suficiente para que un
    # análisis arrancara o un cierre quedara pendiente mientras tanto.
    with state.mutation_guard() as allowed:
        if not allowed:
            return jsonify({"status": "error", "message": state.MSG_ANALYSIS_IN_PROGRESS}), 409
        if lifecycle.get_state() != lifecycle.RUNNING:
            return jsonify({"status": "error", "message": state.MSG_SHUTDOWN_PENDING}), 409
        try:
            carpeta_salida_abs = state.ensure_writable_dir(seleccionada)
        except OSError as exc:
            state.log_technical_error("select_output_folder.ensure_writable_dir", exc)
            return jsonify({
                "status": "error",
                "message": f"No se pudo usar la carpeta seleccionada: {exc}",
            }), 400
        case.carpeta_salida = carpeta_salida_abs
        state.touch(case)

    return jsonify({"status": "ok", "carpeta_salida": carpeta_salida_abs}), 200


# ---------------------------------------------------------------------------
# Pantalla 1 — Archivo
# ---------------------------------------------------------------------------


def _list_sheets(path: str) -> List[str]:
    """Hojas visibles del archivo, con el mismo fallback que usa process_case."""
    visibles, _err = obtener_hojas_visibles(path)
    if visibles:
        return visibles
    return listar_todas_hojas(path) or []


def _reset_sheet_state(case: state.Session) -> None:
    """Limpia hoja/columnas/muestras/mapeo (pantallas 2 en adelante), sin
    tocar el archivo cargado."""
    case.sheet = None
    case.columns = []
    case.samples = {}
    case.mapping = None
    case.mapping_draft = None
    case.mapping_stage = "form"
    case.mapping_conflicts = []
    case.capabilities_preview = None


def _reset_file_state(case: state.Session) -> None:
    """Limpia archivo/hoja/mapeo (pantallas 1 y 2) en el estado de sesión.

    Solo toca campos del dataclass; el borrado del temporal en disco es
    responsabilidad de ``state.clear_uploaded_file`` (I/O separado de
    estado, ver ``change_file``/``upload``).
    """
    case.temp_path = None
    case.original_filename = None
    case.upload_dir = None
    case.upload_sha256 = None
    case.input_snapshot_path = None
    case.input_snapshot_sha256 = None
    case.available_sheets = []
    _reset_sheet_state(case)


@bp.route("/", methods=["GET"])
def cover_screen():
    return render_template("cover.html", show_nav=False)


@bp.route("/menu", methods=["GET"])
def menu_screen():
    return render_template("menu.html", show_nav=False)


@bp.route("/modo/<modo>", methods=["POST"])
@_mutation_guard("tz_web.menu_screen")
def select_mode(modo: str):
    """Entrada única y explícita para MODO_1/MODO_2/MODO_3.

    Elegir un modo significa iniciar deliberadamente otro análisis: se
    descarta el caso anterior (incluido su temporal) y se crea una ``Session``
    nueva, cuyos defaults impiden que filtros, identidad, resultados o
    registros manuales contaminen el flujo elegido.
    """
    if modo not in (state.MODO_1, state.MODO_2, state.MODO_3):
        abort(404)

    previous_id = flask_session.get("case_id")
    if previous_id:
        state.discard_session(previous_id)

    case = state.create_session()
    case.modo = modo
    state.touch(case)
    flask_session["case_id"] = case.id

    if modo == state.MODO_3:
        return redirect(url_for("tz_web.modo3_tipo_screen"))
    return redirect(url_for("tz_web.index"))


@bp.route("/analizador", methods=["GET"])
def index():
    case = _current_session(create=False)
    if case is None:
        flash("Seleccione primero un modo de análisis.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if case.modo == state.MODO_3:
        return redirect(url_for("tz_web.modo3_tipo_screen"))
    return render_template("index.html", case=case)


@bp.route("/upload", methods=["POST"])
@_mutation_guard("tz_web.index")
def upload():
    case = _current_session(create=False)
    if case is None or case.modo not in (state.MODO_1, state.MODO_2):
        flash("Seleccione primero el Modo 1 o el Modo 2 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))

    upload_file = request.files.get("archivo")
    if upload_file is None or not upload_file.filename:
        flash("Seleccione un archivo antes de continuar.", "error")
        return redirect(url_for("tz_web.index"))

    _, ext = os.path.splitext(upload_file.filename)
    if ext.lower() not in state.ALLOWED_UPLOAD_EXTENSIONS:
        flash(
            f"Formato no soportado ({ext or 'sin extensión'}). Use "
            f"{' o '.join(state.ALLOWED_UPLOAD_EXTENSIONS)}.",
            "error",
        )
        return redirect(url_for("tz_web.index"))

    safe_name = secure_filename(upload_file.filename) or "archivo_cargado"
    upload_dir = os.path.join(state.UPLOAD_ROOT, case.id)
    # Una nueva subida reemplaza cualquier archivo previo de esta sesión.
    state.clear_uploaded_file(case)
    _reset_file_state(case)
    os.makedirs(upload_dir, exist_ok=True)
    case.upload_dir = upload_dir
    dest_path = os.path.join(upload_dir, safe_name)

    def _reject_staged_upload() -> None:
        state.clear_uploaded_file(case)
        case.upload_dir = None

    try:
        upload_file.save(dest_path)
    except OSError as exc:
        _reject_staged_upload()
        state.log_technical_error("upload.save", exc)
        flash("No se pudo guardar el archivo subido.", "error")
        return redirect(url_for("tz_web.index"))

    if os.path.getsize(dest_path) > state.MAX_UPLOAD_BYTES:
        _reject_staged_upload()
        flash(
            f"El archivo supera el límite permitido de "
            f"{state.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            "error",
        )
        return redirect(url_for("tz_web.index"))

    try:
        hojas = _list_sheets(dest_path)
    except Exception as exc:  # noqa: BLE001 - error de lectura de un archivo ajeno, se traduce
        _reject_staged_upload()
        state.log_technical_error("upload.list_sheets", exc)
        flash("El archivo no pudo leerse. Verifique que sea un Excel válido y no esté dañado.", "error")
        return redirect(url_for("tz_web.index"))

    if not hojas:
        _reject_staged_upload()
        flash("El archivo no tiene hojas visibles para analizar.", "error")
        return redirect(url_for("tz_web.index"))

    # Nuevo archivo reinicia cualquier estado de mapeo/configuración previo.
    try:
        upload_sha256 = sha256_file(dest_path)
    except OSError as exc:
        try:
            _reject_staged_upload()
        except OSError:
            case.upload_dir = None
        state.log_technical_error("upload.sha256", exc)
        flash("No se pudo registrar la integridad del archivo subido.", "error")
        return redirect(url_for("tz_web.index"))

    case.temp_path = dest_path
    case.original_filename = upload_file.filename
    case.upload_dir = upload_dir
    case.upload_sha256 = upload_sha256
    case.available_sheets = hojas
    state.touch(case)

    return redirect(url_for("tz_web.index"))


@bp.route("/file/change", methods=["POST"])
@_mutation_guard("tz_web.index")
def change_file():
    """Acción "Cambiar archivo": limpia archivo/hoja/mapeo de la sesión
    actual (sin usar discard_session, que reiniciaría toda la sesión) y
    elimina de forma segura el temporal de subida."""
    case = _current_session(create=False)
    if case is not None:
        state.clear_uploaded_file(case)
        _reset_file_state(case)
        state.touch(case)
    return redirect(url_for("tz_web.index"))


@bp.route("/sheet", methods=["POST"])
@_mutation_guard("tz_web.index")
def select_sheet():
    case = _current_session(create=False)
    if case is None or not case.temp_path:
        flash("Primero cargue un archivo.", "error")
        return redirect(url_for("tz_web.index"))

    hoja = (request.form.get("hoja") or "").strip()
    if hoja not in case.available_sheets:
        flash("Seleccione una hoja válida de la lista.", "error")
        return redirect(url_for("tz_web.index"))

    try:
        df, hoja_real = cargar_excel_con_normalizacion(case.temp_path, hoja)
    except Exception as exc:  # noqa: BLE001 - traducido a mensaje de usuario
        state.log_technical_error("select_sheet.load", exc)
        flash("No se pudo cargar la hoja seleccionada.", "error")
        return redirect(url_for("tz_web.index"))

    _reset_sheet_state(case)
    case.sheet = hoja_real
    case.columns = [str(c) for c in df.columns]
    case.samples = _build_samples(df)
    state.touch(case)

    return redirect(url_for("tz_web.preview_screen"))


@bp.route("/sheet/change", methods=["POST"])
@_mutation_guard("tz_web.index")
def change_sheet():
    """Acción "Cambiar hoja": conserva el archivo cargado, descarta la hoja
    elegida (y cualquier mapeo dependiente de ella) y regresa a la
    selección de hoja."""
    case = _current_session(create=False)
    if case is not None:
        _reset_sheet_state(case)
        state.touch(case)
    return redirect(url_for("tz_web.index"))


@bp.route("/preview", methods=["GET"])
def preview_screen():
    case = _current_session(create=False)
    if case is None or not case.columns:
        flash("Primero cargue un archivo y seleccione una hoja.", "error")
        return redirect(url_for("tz_web.index"))
    return render_template("preview.html", case=case)


def _build_samples(df: pd.DataFrame, limit: int = 3) -> Dict[str, List[str]]:
    """Hasta ``limit`` filas de muestra, coherentes entre columnas (misma
    fila del DataFrame en todas las columnas), con vacíos/nulos como "—"."""
    if df.empty:
        return {str(col): [] for col in df.columns}
    muestra = df.head(limit)
    samples: Dict[str, List[str]] = {}
    for col in df.columns:
        valores = []
        for val in muestra[col].tolist():
            try:
                es_nulo = bool(pd.isna(val))
            except (TypeError, ValueError):
                es_nulo = False
            valores.append("—" if es_nulo else str(val))
        samples[str(col)] = valores
    return samples


# ---------------------------------------------------------------------------
# Pantalla 2 — Mapeo
# ---------------------------------------------------------------------------


def _parse_mapping_form(
    case: state.Session,
) -> Tuple[Dict[str, Tuple[str, Any]], List[str], Optional[str]]:
    """Construye el dict de mapeo desde el formulario.

    Devuelve ``(mapeo, campos_conflictivos, error)``. ``mapeo`` conserva
    una entrada por cada campo canónico tal como llegó del formulario —
    incluidas las inválidas — para que, si hay error, la pantalla de mapeo
    pueda volver a mostrarse con todo lo ya elegido en vez de perderlo
    (ver corrección UX de recuperación de mapeo). ``campos_conflictivos``
    lista, en el orden de ``CANONICAL_FIELDS``, los campos a resaltar
    (columna duplicada, columna inválida o valor fijo vacío); el primero de
    la lista es el que la pantalla debe enfocar. ``error`` es ``None``
    cuando no hay ningún problema.
    """
    mapeo: Dict[str, Tuple[str, Any]] = {}
    columnas_usadas: Dict[str, List[str]] = {}
    conflictivos: List[str] = []
    mensajes: List[str] = []

    for campo in CANONICAL_FIELDS:
        tipo = request.form.get(f"tipo_{campo}", "omitido")
        if tipo == "col":
            columna = (request.form.get(f"col_{campo}") or "").strip()
            mapeo[campo] = ("col", columna or None)
            if not columna or columna not in case.columns:
                conflictivos.append(campo)
                mensajes.append(f"Seleccione una columna válida para '{campo}'.")
            else:
                columnas_usadas.setdefault(columna, []).append(campo)
        elif tipo == "fijo":
            valor = (request.form.get(f"fijo_{campo}") or "").strip()
            mapeo[campo] = ("fijo", valor or None)
            if not valor:
                conflictivos.append(campo)
                mensajes.append(f"Indique un valor fijo para '{campo}' o cambie la asignación a 'Omitir'.")
        else:
            mapeo[campo] = ("omitido", None)

    duplicadas = {col: campos for col, campos in columnas_usadas.items() if len(campos) > 1}
    if duplicadas:
        for campos in duplicadas.values():
            conflictivos.extend(campos)
        detalle = "; ".join(f"'{col}' → {', '.join(campos)}" for col, campos in duplicadas.items())
        mensajes.append(f"Una misma columna no puede asignarse a más de un campo: {detalle}.")

    orden = {campo: indice for indice, campo in enumerate(CANONICAL_FIELDS)}
    campos_conflictivos = sorted(set(conflictivos), key=lambda campo: orden.get(campo, 0))
    error = " ".join(mensajes) if mensajes else None
    return mapeo, campos_conflictivos, error


_DURACION_ESTADO_WEB_LABELS: Dict[str, str] = {
    "omitida": "Omitida",
    "pendiente": "Pendiente de configuración",
    "disponible": "Disponible",
}


def _resolver_estado_duracion_web(case: state.Session) -> Optional[Tuple[str, str]]:
    """Reinterpreta, solo para la pantalla de revisión, el estado de la
    capacidad 'duracion' calculada por ``detectar_capacidades`` (no se toca
    esa función ni su resultado real, solo cómo se presenta):

    - 'duracion' omitida en el mapeo -> "Omitida".
    - 'duracion' mapeada pero sin unidad válida decidida todavía -> "Pendiente
      de configuración" en vez de "No disponible".
    - 'duracion' mapeada con unidad válida (milisegundos/segundos/minutos)
      -> "Disponible", sin que la ausencia de unidad la marque como no
      disponible.

    Devuelve ``None`` cuando no corresponde anular la etiqueta calculada por
    el motor (p. ej. ya está "disponible" porque el formato es
    autodescriptivo y no depende de la unidad elegida aquí).
    """
    if not case.mapping_draft:
        return None

    tipo, _valor = case.mapping_draft.get("duracion", ("omitido", None))
    if tipo != "col":
        return "omitida", _DURACION_ESTADO_WEB_LABELS["omitida"]

    if not case.capabilities_preview:
        return None
    cap = case.capabilities_preview.get("capacidades", {}).get("duracion")
    if cap and cap.get("disponible"):
        return None

    if case.duration_unit_decision in ("milisegundos", "segundos", "minutos"):
        return "disponible", _DURACION_ESTADO_WEB_LABELS["disponible"]
    return "pendiente", _DURACION_ESTADO_WEB_LABELS["pendiente"]


def _build_mapping_review(case: state.Session, canonical_fields: Tuple[str, ...]) -> List[Dict[str, Any]]:
    """Fila por campo canónico para la tabla horizontal de revisión, con la
    muestra tomada de ``case.samples`` (ya construido en la capa web al
    elegir la hoja) — no depende de tz_core."""
    filas: List[Dict[str, Any]] = []
    if not case.mapping_draft:
        return filas
    for campo in canonical_fields:
        tipo, valor = case.mapping_draft.get(campo, ("omitido", None))
        muestra = "—"
        if tipo == "col" and valor is not None:
            valores = (case.samples or {}).get(valor, [])
            if valores:
                muestra = valores[0]
        if campo == "azimut":
            muestra = _format_azimut_display(muestra)
        filas.append({"campo": campo, "tipo": tipo, "valor": valor, "muestra": muestra})
    return filas


def _format_azimut_display(valor: Any) -> Any:
    """Presentación visual del azimut (sección 1 del microbloque): un valor
    entero como 20.0 se muestra como '20'; un valor con fracción real como
    22.5 se conserva intacto. Solo afecta cómo se pinta esta muestra, nunca
    el DataFrame ni el valor original guardado en el estado."""
    if valor in (None, "—"):
        return valor
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return valor
    if numero.is_integer():
        return str(int(numero))
    return valor


@bp.route("/mapping", methods=["GET"])
def mapping_screen():
    case = _current_session(create=False)
    if case is None or not case.columns:
        flash("Primero cargue un archivo y seleccione una hoja.", "error")
        return redirect(url_for("tz_web.index"))

    return render_template(
        "mapping.html",
        case=case,
        canonical_fields=CANONICAL_FIELDS,
        field_groups=FIELD_GROUPS,
        field_context=FIELD_CONTEXT,
        field_labels=FIELD_LABELS,
        field_descriptions=FIELD_DESCRIPTIONS,
        capability_labels=CAPABILITY_LABELS,
        duration_unit_labels=_DURATION_UNIT_LABELS,
        duracion_estado_web=_resolver_estado_duracion_web(case),
        mapping_review=_build_mapping_review(case, CANONICAL_FIELDS),
        mapping_conflicts=case.mapping_conflicts,
    )


@bp.route("/mapping", methods=["POST"])
@_mutation_guard("tz_web.mapping_screen")
def mapping_submit():
    case = _current_session(create=False)
    if case is None or not case.columns:
        flash("Primero cargue un archivo y seleccione una hoja.", "error")
        return redirect(url_for("tz_web.index"))

    mapeo, conflictos, error = _parse_mapping_form(case)
    if error:
        # Conserva lo ya elegido: la pantalla de mapeo vuelve a mostrarse con
        # todas las asignaciones previas intactas y solo los campos
        # conflictivos señalados, en vez de forzar a repetir el mapeo
        # completo (ver corrección UX de recuperación de mapeo).
        case.mapping_draft = mapeo
        case.mapping_conflicts = conflictos
        case.mapping_stage = "form"
        state.touch(case)
        flash(error, "error")
        return redirect(url_for("tz_web.mapping_screen"))

    # La unidad de duración se decide aquí (mismo bloque donde se mapea
    # 'duracion') y se guarda en el estado ANTES de calcular la vista previa
    # de capacidades, para que la revisión ya pueda leerla. No se toca si
    # 'duracion' no fue mapeada como columna, para no pisar una decisión
    # previa (p.ej. ya tomada en Configuración) sin motivo.
    if mapeo.get("duracion", ("omitido", None))[0] == "col":
        unidad = request.form.get("duration_unit_decision", "desconocida")
        if unidad not in _DURATION_UNIT_LABELS:
            unidad = "desconocida"
        case.duration_unit_decision = unidad

    try:
        df, _hoja = cargar_excel_con_normalizacion(case.temp_path, case.sheet)
        _validate_mapeo(df, mapeo)
    except InvalidMappingError as exc:
        # Validación server-side de forma (p. ej. mapeo vacío): también
        # conserva el borrador para no perder lo ya elegido, aunque aquí el
        # motor no distingue campos individuales a resaltar.
        case.mapping_draft = mapeo
        case.mapping_conflicts = []
        case.mapping_stage = "form"
        state.touch(case)
        flash(state.translate_error(exc), "error")
        return redirect(url_for("tz_web.mapping_screen"))
    except Exception as exc:  # noqa: BLE001 - archivo dejó de ser legible entre pasos
        state.log_technical_error("mapping_submit.reload", exc)
        flash("No se pudo releer el archivo para validar el mapeo. Cargue el archivo nuevamente.", "error")
        return redirect(url_for("tz_web.index"))

    try:
        preview_df = _apply_mapeo(df.copy(), mapeo, output_fn=lambda _msg: None)
        capabilities = detectar_capacidades(preview_df)
    except Exception as exc:  # noqa: BLE001 - la vista previa nunca debe tumbar la pantalla
        state.log_technical_error("mapping_submit.preview", exc)
        capabilities = None

    case.mapping_draft = mapeo
    case.mapping_conflicts = []
    case.capabilities_preview = _serialize_capabilities(capabilities) if capabilities else None
    case.mapping_stage = "review"
    state.touch(case)

    return redirect(url_for("tz_web.mapping_screen"))


def _serialize_capabilities(report: Any) -> Dict[str, Any]:
    return {
        "procesable": report.procesable,
        "bloqueos_globales": list(report.bloqueos_globales),
        "capacidades": {
            nombre: {"disponible": cap.disponible, "estado": cap.estado, "motivo": cap.motivo}
            for nombre, cap in report.capacidades.items()
        },
    }


@bp.route("/mapping/confirm", methods=["POST"])
@_mutation_guard("tz_web.mapping_screen")
def mapping_confirm():
    case = _current_session(create=False)
    if case is None or not case.mapping_draft:
        flash("No hay un mapeo pendiente de confirmar.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    case.mapping = case.mapping_draft
    case.mapping_draft = None
    case.mapping_stage = "form"
    case.mapping_conflicts = []
    state.touch(case)

    if case.modo == state.MODO_2:
        return redirect(url_for("tz_web.configure_filtro_tiempo_screen"))
    return redirect(url_for("tz_web.configure_screen"))


@bp.route("/mapping/edit", methods=["POST"])
@_mutation_guard("tz_web.mapping_screen")
def mapping_edit():
    """"Volver a editar" desde la Revisión del mapeo: conserva íntegramente
    ``mapping_draft`` (Usar columna/Omitir, columna elegida, unidad de
    duración y cualquier otro dato del borrador actual) y solo cambia la
    vista a la pantalla de edición paginada, que arranca en el Grupo 1 de 7
    pero repuebla cada grupo con los valores ya guardados en el borrador."""
    case = _current_session(create=False)
    if case is not None:
        case.mapping_stage = "form"
        state.touch(case)
    return redirect(url_for("tz_web.mapping_screen"))


# ---------------------------------------------------------------------------
# Pantalla 2B (solo Modo 2) — Filtro temporal
#
# Se inserta entre "Revisión del mapeo" e "Identificación" (sección 3 del
# microbloque Modo 2): el Modo 1 nunca la alcanza porque mapping_confirm()
# solo redirige aquí cuando ``case.modo == state.MODO_2``. Todavía NO aplica
# el filtro al DataFrame (sección 10, fuera de alcance de este microbloque):
# solo persiste la selección en ``case.filtro_tiempo``, el mismo campo que ya
# consume ``CaseRequest`` para la ejecución real (sección 7).
# ---------------------------------------------------------------------------

# Tipos habilitados según el estado de la capacidad "filtros_temporales" ya
# calculada por detectar_capacidades() (sección 4): no se recalcula
# disponibilidad por separado, solo se traduce su "estado" a los tipos de
# filtro que la pantalla debe ofrecer.
_FILTRO_TIPOS_SOLO_FECHA: Tuple[str, ...] = ("dia", "rango_dias")


def _capacidad_filtros_temporales(case: state.Session) -> Optional[Dict[str, Any]]:
    if not case.capabilities_preview:
        return None
    return case.capabilities_preview.get("capacidades", {}).get("filtros_temporales")


def _filtro_tiempo_tipos_habilitados(case: state.Session) -> Tuple[str, ...]:
    """Tipos de filtro que la pantalla debe ofrecer para ``case``, a partir
    únicamente de ``case.capabilities_preview`` (sección 4):

    - fecha y hora disponibles (estado "disponible"): los 4 tipos.
    - solo fecha disponible (estado "parcial"): solo "dia" y "rango_dias".
    - sin fecha parseable (no disponible): ninguno (pantalla bloqueada).
    """
    cap = _capacidad_filtros_temporales(case)
    if not cap or not cap.get("disponible"):
        return ()
    if cap.get("estado") == "parcial":
        return _FILTRO_TIPOS_SOLO_FECHA
    return FILTRO_TIEMPO_ORDER


def _parse_filtro_tiempo_modo2(
    tipos_habilitados: Tuple[str, ...],
) -> Tuple[Optional[Dict[str, Optional[str]]], Optional[str]]:
    """Como ``_parse_filtro_tiempo()``, pero para el Modo 2: no admite
    "ninguno" (sección 5, el Modo 2 no ofrece "Sin filtro") y rechaza
    cualquier tipo que la capacidad de esta bitácora no habilite (defensa
    adicional a que el HTML ya deshabilite esas opciones)."""
    tipo = request.form.get("filtro_tipo", "")
    if tipo not in ("dia", "rango_dias", "rango_horas_dia", "rango_horas"):
        return None, "Seleccione un tipo de filtro temporal válido."
    if tipo not in tipos_habilitados:
        return None, "El tipo de filtro seleccionado no está disponible para esta bitácora."

    def _get(name: str) -> Optional[str]:
        valor = (request.form.get(name) or "").strip()
        return valor or None

    if tipo == "dia":
        dia = _get("filtro_dia")
        if not dia:
            return None, "Indique el día para el filtro."
        return {"tipo": "dia", "dia": dia, "desde": None, "hasta": None, "hora_ini": None, "hora_fin": None}, None

    if tipo == "rango_dias":
        desde, hasta = _get("filtro_desde"), _get("filtro_hasta")
        if not desde or not hasta:
            return None, "Indique el rango de fechas completo (inicial y final)."
        fecha_desde, fecha_hasta = parse_fecha_iso(desde), parse_fecha_iso(hasta)
        if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
            return None, "La fecha inicial del rango debe ser anterior o igual a la fecha final."
        return {
            "tipo": "rango_dias", "dia": None, "desde": desde, "hasta": hasta,
            "hora_ini": None, "hora_fin": None,
        }, None

    if tipo == "rango_horas_dia":
        dia = _get("filtro_dia")
        hora_ini, hora_fin = _get("filtro_hora_ini"), _get("filtro_hora_fin")
        if not dia or not hora_ini or not hora_fin:
            return None, "Indique el día y el rango de horas completo (inicial y final)."
        return {
            "tipo": "rango_horas_dia", "dia": dia, "desde": None, "hasta": None,
            "hora_ini": hora_ini, "hora_fin": hora_fin,
        }, None

    hora_ini, hora_fin = _get("filtro_hora_ini"), _get("filtro_hora_fin")
    if not hora_ini or not hora_fin:
        return None, "Indique el rango de horas completo (inicial y final)."
    return {
        "tipo": "rango_horas", "dia": None, "desde": None, "hasta": None,
        "hora_ini": hora_ini, "hora_fin": hora_fin,
    }, None


@bp.route("/configure/filtro-tiempo", methods=["GET"])
def configure_filtro_tiempo_screen():
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    if case.modo != state.MODO_2:
        return redirect(url_for("tz_web.configure_screen"))

    tipos_habilitados = _filtro_tiempo_tipos_habilitados(case)
    return render_template(
        "configure_filtro_tiempo.html",
        case=case,
        bloqueado=not tipos_habilitados,
        tipos_habilitados=tipos_habilitados,
        filtro_catalog=FILTRO_TIEMPO_CATALOG,
        filtro_orden=FILTRO_TIEMPO_ORDER,
    )


@bp.route("/configure/filtro-tiempo", methods=["POST"])
@_mutation_guard("tz_web.configure_filtro_tiempo_screen")
def configure_filtro_tiempo_submit():
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    if case.modo != state.MODO_2:
        return redirect(url_for("tz_web.configure_screen"))

    tipos_habilitados = _filtro_tiempo_tipos_habilitados(case)
    if not tipos_habilitados:
        flash(
            "Esta bitácora no dispone de una fecha reconocible para aplicar filtros temporales.",
            "error",
        )
        return redirect(url_for("tz_web.configure_filtro_tiempo_screen"))

    filtro, error = _parse_filtro_tiempo_modo2(tipos_habilitados)
    if error:
        flash(error, "error")
        return redirect(url_for("tz_web.configure_filtro_tiempo_screen"))

    case.filtro_tiempo = filtro
    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        case.mapping_draft = case.mapping
        case.mapping_stage = "review"
        state.touch(case)
        return redirect(url_for("tz_web.mapping_screen"))

    return redirect(url_for("tz_web.configure_screen"))


# ---------------------------------------------------------------------------
# Pantalla 3 — Configuración
# ---------------------------------------------------------------------------


@bp.route("/configure", methods=["GET"])
def configure_screen():
    """Paso 3 — subpantalla 3A: Identificación de la bitácora.

    Es la primera subpantalla interna del Paso 3 (sección 2 del
    microbloque). El resto de Configuración (tipo de bitácora, carpeta de
    salida, filtros, etc. — ver ``configure_legacy_screen``) queda diferido
    a subpantallas posteriores todavía no desarrolladas."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    return render_template("configure_identity.html", case=case)


@bp.route("/configure", methods=["POST"])
@_mutation_guard("tz_web.configure_screen")
def configure_identity_submit():
    """Guarda (o vacía, si se omite) la identificación de la bitácora de la
    subpantalla 3A y avanza a la siguiente subpantalla de Configuración."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    accion = request.form.get("accion", "siguiente")
    if accion == "omitir":
        case.identity_overrides = {}
    else:
        identity_overrides: Dict[str, str] = {}
        for campo in ("alias", "nombre_usuario", "abonado"):
            valor = (request.form.get(f"identidad_{campo}") or "").strip()
            if valor:
                identity_overrides[campo] = valor
        case.identity_overrides = identity_overrides
    state.touch(case)

    return redirect(url_for("tz_web.configure_options_screen"))


@bp.route("/configure/back-to-mapping", methods=["POST"])
@_mutation_guard("tz_web.mapping_screen")
def configure_back_to_mapping():
    """"Volver al mapeo" desde la subpantalla 3A: regresa a la Revisión del
    mapeo (repoblando ``mapping_draft`` a partir del mapeo ya confirmado)
    sin perder el mapeo confirmado, la hoja, el archivo ni la unidad de
    duración decidida."""
    case = _current_session(create=False)
    if case is not None and case.mapping:
        case.mapping_draft = case.mapping
        case.mapping_stage = "review"
        state.touch(case)
    return redirect(url_for("tz_web.mapping_screen"))


@bp.route("/configure/opciones", methods=["GET"])
def configure_options_screen():
    """Paso 3 — subpantalla 3B: Opciones del análisis (Top de antenas y de
    contactos). Reutiliza los mismos nombres internos, valores por defecto y
    validaciones que ya existían para estos campos en la Configuración
    heredada (ver ``_parse_int_field``)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    return render_template("configure_options.html", case=case)


@bp.route("/configure/opciones", methods=["POST"])
@_mutation_guard("tz_web.configure_options_screen")
def configure_options_submit():
    """Guarda Top de antenas/contactos de la subpantalla 3B y navega según
    el botón pulsado ('anterior' -> 3A, 'siguiente' -> 3C)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    top_antenas, err = _parse_int_field("top_antenas")
    if err:
        flash(err, "error")
        return redirect(url_for("tz_web.configure_options_screen"))
    top_contactos, err = _parse_int_field("top_contactos")
    if err:
        flash(err, "error")
        return redirect(url_for("tz_web.configure_options_screen"))

    case.top_antenas = top_antenas
    case.top_contactos = top_contactos
    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.configure_screen"))
    return redirect(url_for("tz_web.configure_outputs_screen"))


@bp.route("/configure/productos", methods=["GET"])
def configure_outputs_screen():
    """Paso 3 — subpantalla 3C: Productos de salida. HTML, KMZ y hashes son
    productos siempre incluidos por el motor (no se ofrecen como opciones
    desmarcables); el único producto real que se decide aquí es el KML
    suelto opcional."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    return render_template("configure_outputs.html", case=case)


@bp.route("/configure/productos", methods=["POST"])
@_mutation_guard("tz_web.configure_outputs_screen")
def configure_outputs_submit():
    """Guarda la decisión de KML opcional de la subpantalla 3C.

    ``kml_opcional`` activado -> ``solo_kmz=False`` (se conserva el KML
    suelto junto al KMZ); desactivado -> ``solo_kmz=True`` (comportamiento
    actual por defecto). No cambia el comportamiento interno de
    ``generar_kml()``, solo el valor de configuración que ya consumía."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    case.kml_opcional = request.form.get("kml_opcional") == "on"
    case.solo_kmz = not case.kml_opcional
    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.configure_options_screen"))
    return redirect(url_for("tz_web.configure_color_screen"))


def _theme_palette() -> List[Tuple[str, str]]:
    """Paleta de colores del tema, tal como la usa el motor (``config.json``
    -> ``style.palette``): lista de pares (nombre, "#RRGGBB")."""
    style = get_config().get("style", {}) or {}
    return [(nombre, hex_valor) for nombre, hex_valor in (style.get("palette") or [])]


_PALETTE_GROUP_ORDER = ("Principales", "Azules/Cian", "Verdes", "Rojos/Rosas", "Amarillos/Naranjas", "Morados")
_PALETTE_PRINCIPALES_COUNT = 8


def _palette_hue_group(hex_valor: str) -> str:
    """Clasifica un color por matiz (HSV) en una de las categorías visuales
    de ``_PALETTE_GROUP_ORDER``. Solo agrupa la presentación en pantalla
    (sección 11 del encargo estético); no modifica valores hex ni nombres
    de la paleta real del motor."""
    h = hex_valor.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    hue, _sat, _val = colorsys.rgb_to_hsv(r, g, b)
    hue_deg = hue * 360
    if hue_deg < 20 or hue_deg >= 330:
        return "Rojos/Rosas"
    if hue_deg < 70:
        return "Amarillos/Naranjas"
    if hue_deg < 170:
        return "Verdes"
    if hue_deg < 255:
        return "Azules/Cian"
    return "Morados"


def _grouped_palette() -> List[Tuple[str, List[Tuple[str, str]]]]:
    """Reorganiza ``_theme_palette()`` en grupos visuales (sección 11:
    demasiados colores presentados al mismo nivel). No cambia el orden
    interno de cada grupo, ni los valores hex/nombres — solo agrupa la
    presentación para que la pantalla de selección de color sea más legible."""
    paleta = _theme_palette()
    principales = paleta[:_PALETTE_PRINCIPALES_COUNT]
    resto = paleta[_PALETTE_PRINCIPALES_COUNT:]

    grupos: Dict[str, List[Tuple[str, str]]] = {nombre: [] for nombre in _PALETTE_GROUP_ORDER}
    grupos["Principales"] = list(principales)
    for nombre, hex_valor in resto:
        grupos[_palette_hue_group(hex_valor)].append((nombre, hex_valor))

    return [(nombre, grupos[nombre]) for nombre in _PALETTE_GROUP_ORDER if grupos[nombre]]


def _default_theme_hex() -> str:
    style = get_config().get("style", {}) or {}
    return style.get("theme_hex", "#76ff03")


@bp.route("/configure/color", methods=["GET"])
def configure_color_screen():
    """Paso 3 — subpantalla 3D: Color de la bitácora. Reutiliza la paleta
    controlada del motor (``config.json`` -> ``style.palette``) en lugar de
    un selector de color libre; ``case.color_hex`` es exactamente el mismo
    campo que ya consumía la Configuración heredada (``None`` = usar
    ``style.theme_hex`` por defecto)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    selected_color = case.color_hex or _default_theme_hex()
    return render_template(
        "configure_color.html",
        case=case,
        palette=_theme_palette(),
        palette_groups=_grouped_palette(),
        selected_color=selected_color,
        color_action_url=url_for("tz_web.configure_color_submit"),
    )


@bp.route("/configure/color", methods=["POST"])
@_mutation_guard("tz_web.configure_color_screen")
def configure_color_submit():
    """Guarda el color elegido en la subpantalla 3D y navega según el botón
    pulsado ('anterior' -> 3C, 'siguiente' -> 3E)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.configure_outputs_screen"))

    color_hex = (request.form.get("color_hex") or "").strip()
    paleta_hex = {hex_valor.lower() for _, hex_valor in _theme_palette()}
    if not color_hex or color_hex.lower() not in paleta_hex:
        flash("Elija uno de los colores disponibles en la paleta.", "error")
        return redirect(url_for("tz_web.configure_color_screen"))

    case.color_hex = color_hex
    state.touch(case)
    return redirect(url_for("tz_web.configure_final_screen"))


def _color_name_for_hex(hex_valor: Optional[str]) -> Optional[str]:
    if not hex_valor:
        return None
    for nombre, valor in _theme_palette():
        if valor.lower() == hex_valor.lower():
            return nombre
    return None


@bp.route("/configure/final", methods=["GET"])
def configure_final_screen():
    """Paso 3 — subpantalla 3E: Preparar análisis.

    Únicamente tipo de bitácora, nombre de salida y ubicación de salida (ver
    sección "OBJETIVO A" del microbloque de separación Preparar/Resumen). El
    resumen completo del análisis vive en su propia subpantalla
    (``configure_resumen_screen``), alcanzable solo pulsando "Continuar al
    resumen" aquí."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    # El tipo de bitácora (ya persistido de una visita anterior a esta misma
    # subpantalla) se evalúa ANTES de calcular el nombre sugerido, para que
    # la sugerencia siempre corresponda a la última decisión guardada.
    tipo_bitacora_actual = case.tipo_bitacora
    # Sin fallback silencioso a una carpeta por defecto (MICROBLOQUE 6): el
    # contrato histórico exige que el usuario elija explícitamente la
    # ubicación de salida — ``None`` aquí significa "todavía no elegida", y
    # la plantilla lo muestra como tal en vez de una ruta que TZ Analyzer
    # nunca comunicó como una decisión real del usuario.
    carpeta_salida = case.carpeta_salida

    suggested_name = None
    if not case.output_base_name:
        suggested_name = preview_suggested_case_name(
            ruta_archivo=case.temp_path,
            hoja=case.sheet,
            mapeo=case.mapping,
            identity_overrides=case.identity_overrides,
            tipo_bitacora=tipo_bitacora_actual,
            filtro_tiempo=case.filtro_tiempo,
        )

    return render_template(
        "configure_final.html",
        case=case,
        carpeta_salida=carpeta_salida,
        suggested_name=suggested_name,
        tipo_bitacora_labels=_TIPO_BITACORA_LABELS,
    )


@bp.route("/configure/final/preview-name", methods=["POST"])
def configure_final_preview_name():
    """Recalcula el nombre sugerido para un ``tipo_bitacora`` candidato, sin
    guardarlo en la sesión (eso solo ocurre al enviar el formulario de 3E).

    Endpoint ligero para que el nombre sugerido reaccione de inmediato al
    cambiar "Tipo de bitácora" en la misma pantalla, reutilizando
    ``preview_suggested_case_name`` (misma fuente de verdad que ya usaba
    ``configure_final_screen``) en vez de duplicar esa lógica en JavaScript.
    """
    case = _current_session(create=False)
    if case is None or not case.mapping:
        return jsonify({"suggested_name": None}), 400

    tipo_bitacora = request.form.get("tipo_bitacora", "")
    if tipo_bitacora not in ("", "I", "T"):
        tipo_bitacora = ""

    suggested_name = preview_suggested_case_name(
        ruta_archivo=case.temp_path,
        hoja=case.sheet,
        mapeo=case.mapping,
        identity_overrides=case.identity_overrides,
        tipo_bitacora=tipo_bitacora,
        filtro_tiempo=case.filtro_tiempo,
    )
    return jsonify({"suggested_name": suggested_name})


@bp.route("/configure/final", methods=["POST"])
@_mutation_guard("tz_web.configure_final_screen")
def configure_final_submit():
    """Guarda tipo de bitácora y nombre de salida de la subpantalla 3E y
    navega según el botón pulsado ('anterior' -> 3D, 'siguiente' -> Resumen).

    No inicia el análisis: eso solo ocurre al confirmar en la subpantalla de
    Resumen (``configure_resumen_submit``)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    # Tipo de bitácora se evalúa/guarda antes que el nombre de salida, para
    # que cualquier nombre sugerido calculado después ya lo tenga en cuenta.
    tipo_bitacora = request.form.get("tipo_bitacora", "")
    if tipo_bitacora not in ("", "I", "T"):
        tipo_bitacora = ""
    case.tipo_bitacora = tipo_bitacora

    if request.form.get("nombre_modo") == "manual":
        nombre_manual = (request.form.get("output_base_name") or "").strip()
        case.output_base_name = nombre_manual or None
    else:
        case.output_base_name = None

    # Modo 1: sin filtro temporal, siempre (nunca pasó por Filtro temporal).
    # Modo 2: se preserva exactamente la selección ya guardada por
    # configure_filtro_tiempo_submit — no se reconstruye desde este
    # formulario, que no tiene esos campos (sección 1 del microbloque Modo 2
    # parte 2).
    if case.modo != state.MODO_2:
        case.filtro_tiempo = None

    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.configure_color_screen"))

    return redirect(url_for("tz_web.configure_resumen_screen"))


@bp.route("/configure/resumen", methods=["GET"])
def configure_resumen_screen():
    """Paso 3 — subpantalla final: Resumen del análisis.

    Presentación compacta de todas las decisiones tomadas en 3A-3E antes de
    iniciar el análisis. "Generar análisis" (``configure_resumen_submit``)
    es el único punto donde arranca la tarea (Paso 4)."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    carpeta_salida = case.carpeta_salida

    suggested_name = None
    if not case.output_base_name:
        suggested_name = preview_suggested_case_name(
            ruta_archivo=case.temp_path,
            hoja=case.sheet,
            mapeo=case.mapping,
            identity_overrides=case.identity_overrides,
            tipo_bitacora=case.tipo_bitacora,
            filtro_tiempo=case.filtro_tiempo,
        )

    html_cfg = get_config().get("html", {}) or {}

    return render_template(
        "configure_resumen.html",
        case=case,
        carpeta_salida=carpeta_salida,
        suggested_name=suggested_name,
        color_name=_color_name_for_hex(case.color_hex) or _color_name_for_hex(_default_theme_hex()),
        selected_color_hex=case.color_hex or _default_theme_hex(),
        default_top_antenas=int(html_cfg.get("top_antenas_n", 10)),
        default_top_contactos=int(html_cfg.get("top_contactos_n", 10)),
        alcance=describir_alcance(case.filtro_tiempo),
    )


@bp.route("/configure/resumen", methods=["POST"])
@_mutation_guard("tz_web.configure_resumen_screen")
def configure_resumen_submit():
    """"Anterior" regresa a Preparar análisis sin tocar nada; "Generar
    análisis" valida la carpeta de salida segura e inicia el análisis (Paso
    4) — único punto de arranque de la tarea en todo el flujo."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.configure_final_screen"))

    # Sin selección explícita, no se arranca (MICROBLOQUE 6): nunca se
    # sustituye en silencio por Documents\TZ Analyzer ni %TEMP% — se manda
    # de vuelta a "Preparar análisis", donde vive el selector.
    if not case.carpeta_salida:
        flash(MSG_CARPETA_SALIDA_REQUERIDA, "error")
        return redirect(url_for("tz_web.configure_final_screen"))

    try:
        carpeta_salida_abs = state.ensure_writable_dir(case.carpeta_salida)
    except OSError as exc:
        state.log_technical_error("configure_resumen_submit.ensure_dir", exc)
        flash("No se pudo preparar la carpeta de salida seleccionada.", "error")
        return redirect(url_for("tz_web.configure_final_screen"))

    case.carpeta_salida = carpeta_salida_abs
    state.touch(case)

    started, reason = _start_task(case)
    if not started:
        _flash_start_rejected(reason)
        return redirect(url_for("tz_web.configure_resumen_screen"))

    return redirect(url_for("tz_web.processing_screen"))


@bp.route("/configure/legacy", methods=["GET"])
def configure_legacy_screen():
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    default_output = case.carpeta_salida or resolve_default_output_dir(warn=lambda _msg: None)
    return render_template(
        "configure.html",
        case=case,
        default_output=default_output,
        tipo_bitacora_labels=_TIPO_BITACORA_LABELS,
        duration_unit_labels=_DURATION_UNIT_LABELS,
        date_order_labels=_DATE_ORDER_LABELS,
        filtro_tipo_labels=_FILTRO_TIPO_LABELS,
    )


def _parse_int_field(name: str) -> Tuple[Optional[int], Optional[str]]:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None, None
    try:
        valor = int(raw)
    except ValueError:
        return None, f"'{name}' debe ser un número entero."
    if valor <= 0:
        return None, f"'{name}' debe ser mayor que cero."
    return valor, None


def _parse_filtro_tiempo() -> Tuple[Optional[Dict[str, Optional[str]]], Optional[str]]:
    tipo = request.form.get("filtro_tipo", "ninguno")
    if tipo == "ninguno":
        return None, None
    if tipo not in ("dia", "rango_dias", "rango_horas_dia", "rango_horas"):
        return None, "Tipo de filtro temporal no reconocido."

    def _get(name: str) -> Optional[str]:
        valor = (request.form.get(name) or "").strip()
        return valor or None

    if tipo == "dia":
        dia = _get("filtro_dia")
        if not dia:
            return None, "Indique el día para el filtro."
        return {"tipo": "dia", "dia": dia, "desde": None, "hasta": None, "hora_ini": None, "hora_fin": None}, None

    if tipo == "rango_dias":
        desde, hasta = _get("filtro_desde"), _get("filtro_hasta")
        if not desde or not hasta:
            return None, "Indique el rango de días completo (desde/hasta)."
        return {
            "tipo": "rango_dias", "dia": None, "desde": desde, "hasta": hasta,
            "hora_ini": None, "hora_fin": None,
        }, None

    if tipo == "rango_horas_dia":
        dia = _get("filtro_dia")
        if not dia:
            return None, "Indique el día para el filtro de horas."
        return {
            "tipo": "rango_horas_dia", "dia": dia, "desde": None, "hasta": None,
            "hora_ini": _get("filtro_hora_ini"), "hora_fin": _get("filtro_hora_fin"),
        }, None

    return {
        "tipo": "rango_horas", "dia": None, "desde": None, "hasta": None,
        "hora_ini": _get("filtro_hora_ini"), "hora_fin": _get("filtro_hora_fin"),
    }, None


@bp.route("/configure/legacy", methods=["POST"])
@_mutation_guard("tz_web.configure_legacy_screen")
def configure_legacy_submit():
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    carpeta_salida = (request.form.get("carpeta_salida") or "").strip()
    if not carpeta_salida:
        flash("Indique una carpeta de salida.", "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))

    try:
        carpeta_salida_abs = state.ensure_writable_dir(carpeta_salida)
    except OSError as exc:
        state.log_technical_error("configure_submit.ensure_dir", exc)
        flash(f"No se pudo usar la carpeta de salida indicada: {exc}", "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))

    top_antenas, err = _parse_int_field("top_antenas")
    if err:
        flash(err, "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))
    top_contactos, err = _parse_int_field("top_contactos")
    if err:
        flash(err, "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))

    color_hex = (request.form.get("color_hex") or "").strip() or None
    if color_hex and not _es_color_hex_valido(color_hex):
        flash("El color debe tener el formato #RRGGBB.", "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))

    filtro_tiempo, err = _parse_filtro_tiempo()
    if err:
        flash(err, "error")
        return redirect(url_for("tz_web.configure_legacy_screen"))

    tipo_bitacora = request.form.get("tipo_bitacora", "")
    if tipo_bitacora not in ("", "I", "T"):
        tipo_bitacora = ""

    identity_overrides = {}
    for campo in ("alias", "nombre_usuario", "abonado"):
        valor = (request.form.get(f"identidad_{campo}") or "").strip()
        if valor:
            identity_overrides[campo] = valor

    case.carpeta_salida = carpeta_salida_abs
    case.top_antenas = top_antenas
    case.top_contactos = top_contactos
    case.color_hex = color_hex
    case.solo_kmz = request.form.get("solo_kmz") == "on"
    case.output_base_name = (request.form.get("output_base_name") or "").strip() or None
    case.tipo_bitacora = tipo_bitacora
    case.identity_overrides = identity_overrides
    case.filtro_tiempo = filtro_tiempo
    case.date_order_decision = request.form.get("date_order_decision", "1")
    case.duration_unit_decision = request.form.get("duration_unit_decision", "desconocida")
    case.qc_bloqueante_decision = request.form.get("qc_bloqueante_decision", "S")
    state.touch(case)

    started, reason = _start_task(case)
    if not started:
        _flash_start_rejected(reason)
        return redirect(url_for("tz_web.configure_legacy_screen"))

    return redirect(url_for("tz_web.processing_screen"))


def _es_color_hex_valido(valor: str) -> bool:
    if not valor.startswith("#") or len(valor) != 7:
        return False
    try:
        int(valor[1:], 16)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Modo 3 — Mapeo manual de antenas/ubicaciones (microbloque 1)
#
# Flujo propio, independiente del de archivo/hoja/mapeo de bitácoras (Modos
# 1/2): selección de tipo -> alta/listado/edición/eliminación de registros.
# Todo el estado vive en case.modo3_tipo/case.modo3_registros (sección 3);
# no se genera KMZ/KML/hashes/log todavía (eso queda para el siguiente
# microbloque, ver modo3_continuar_screen).
# ---------------------------------------------------------------------------

def _modo3_guard(case: Optional[state.Session]) -> bool:
    """True si ``case`` corresponde a una sesión de Modo 3 activa."""
    return case is not None and case.modo == state.MODO_3


@bp.route("/modo3/tipo", methods=["GET"])
def modo3_tipo_screen():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    return render_template("modo3_tipo.html", case=case, show_nav=False)


@bp.route("/modo3/tipo", methods=["POST"])
@_mutation_guard("tz_web.modo3_tipo_screen")
def modo3_tipo_submit():
    """Guarda el tipo de registro elegido (sección 2). Si ya hay registros
    cargados de un tipo distinto al elegido, bloquea el cambio (sección 8):
    no se descartan registros silenciosamente, el usuario debe eliminarlos
    primero."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))

    tipo = request.form.get("tipo", "")
    if tipo not in MODO3_TIPOS_VALIDOS:
        flash("Seleccione un tipo de registro válido.", "error")
        return redirect(url_for("tz_web.modo3_tipo_screen"))

    if case.modo3_registros and case.modo3_tipo != tipo:
        flash(
            "Ya hay registros cargados del tipo actual. Elimínelos antes de "
            "cambiar entre Antenas/Celdas y Puntos libres.",
            "error",
        )
        return redirect(url_for("tz_web.modo3_tipo_screen"))

    case.modo3_tipo = tipo
    state.touch(case)
    return redirect(url_for("tz_web.modo3_registros_screen"))


def _modo3_parse_antena(form) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    nombre, error = mv.parse_nombre(form.get("nombre"), mv.MAX_NOMBRE_ANTENA, "El nombre/identificador")
    if error:
        return None, error
    lat, lon, error = mv.parse_lat_lon(form.get("lat"), form.get("lon"), permitir_cero_cero=False)
    if error:
        return None, error
    azimut, error = mv.parse_azimut(form.get("azimut"))
    if error:
        return None, error
    celda, error = mv.parse_texto_opcional(form.get("celda"), mv.MAX_CELDA, "La celda")
    if error:
        return None, error
    direccion, error = mv.parse_texto_opcional(form.get("direccion"), mv.MAX_DIRECCION_ANTENA, "La dirección")
    if error:
        return None, error
    detalle, error = mv.parse_texto_opcional(form.get("detalle"), mv.MAX_DETALLE_ANTENA, "El detalle/observaciones")
    if error:
        return None, error
    return {
        "nombre": nombre, "lat": lat, "lon": lon, "azimut": azimut,
        "celda": celda, "direccion": direccion, "detalle": detalle,
    }, None


def _modo3_parse_punto_libre(form) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    nombre, error = mv.parse_nombre(form.get("nombre"), mv.MAX_NOMBRE_PUNTO, "El nombre del lugar")
    if error:
        return None, error
    lat, lon, error = mv.parse_lat_lon(form.get("lat"), form.get("lon"), permitir_cero_cero=True)
    if error:
        return None, error
    direccion, error = mv.parse_texto_opcional(form.get("direccion"), mv.MAX_DIRECCION_PUNTO, "La dirección")
    if error:
        return None, error
    detalle, error = mv.parse_texto_opcional(form.get("detalle"), mv.MAX_DETALLE_PUNTO, "El detalle/descripción")
    if error:
        return None, error
    return {"nombre": nombre, "lat": lat, "lon": lon, "direccion": direccion, "detalle": detalle}, None


@bp.route("/modo3/registros", methods=["GET"])
def modo3_registros_screen():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not case.modo3_tipo:
        flash("Seleccione primero el tipo de registros a agregar.", "error")
        return redirect(url_for("tz_web.modo3_tipo_screen"))

    editar_id = request.args.get("editar")
    registro_editar = None
    if editar_id:
        registro_editar = next((r for r in case.modo3_registros if r["id"] == editar_id), None)

    return render_template(
        "modo3_registros.html",
        case=case,
        registro_editar=registro_editar,
        show_nav=False,
    )


@bp.route("/modo3/registros", methods=["POST"])
@_mutation_guard("tz_web.modo3_registros_screen")
def modo3_registro_guardar():
    """Alta o edición de un registro (sección 4/5/7): si el formulario trae
    ``registro_id`` de un registro existente, se reemplaza en el mismo lugar
    de la lista (no se duplica); si no, se agrega uno nuevo. El formulario
    se limpia (nueva alta) al volver a la pantalla, mientras que la lista ya
    cargada se conserva."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not case.modo3_tipo:
        flash("Seleccione primero el tipo de registros a agregar.", "error")
        return redirect(url_for("tz_web.modo3_tipo_screen"))

    if case.modo3_tipo == MODO3_TIPO_ANTENA:
        datos, error = _modo3_parse_antena(request.form)
    else:
        datos, error = _modo3_parse_punto_libre(request.form)

    registro_id = (request.form.get("registro_id") or "").strip()

    if error:
        flash(error, "error")
        if registro_id:
            return redirect(url_for("tz_web.modo3_registros_screen", editar=registro_id))
        return redirect(url_for("tz_web.modo3_registros_screen"))

    if registro_id:
        existente = next((r for r in case.modo3_registros if r["id"] == registro_id), None)
        if existente is None:
            flash("El registro que intenta editar ya no existe.", "error")
            return redirect(url_for("tz_web.modo3_registros_screen"))
        datos["id"] = registro_id
        case.modo3_registros = [datos if r["id"] == registro_id else r for r in case.modo3_registros]
    else:
        datos["id"] = uuid.uuid4().hex[:10]
        case.modo3_registros.append(datos)

    state.touch(case)
    return redirect(url_for("tz_web.modo3_registros_screen"))


@bp.route("/modo3/registros/<registro_id>/eliminar", methods=["POST"])
@_mutation_guard("tz_web.modo3_registros_screen")
def modo3_registro_eliminar(registro_id: str):
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))

    antes = len(case.modo3_registros)
    case.modo3_registros = [r for r in case.modo3_registros if r["id"] != registro_id]
    if len(case.modo3_registros) == antes:
        flash("El registro indicado ya no existe.", "error")
    state.touch(case)
    return redirect(url_for("tz_web.modo3_registros_screen"))


def _modo3_require_registros(case: state.Session) -> bool:
    """True si ``case`` tiene registros — condición común a todas las
    pantallas posteriores a Ingreso manual (Productos/Color/Preparar/
    Resumen), que nunca deben alcanzarse sin al menos un registro (sección
    13: "Debe impedir continuar si no hay registros")."""
    return bool(case.modo3_registros)


@bp.route("/modo3/productos", methods=["GET"])
def modo3_productos_screen():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))
    return render_template("modo3_productos.html", case=case, show_nav=False)


@bp.route("/modo3/productos", methods=["POST"])
@_mutation_guard("tz_web.modo3_productos_screen")
def modo3_productos_submit():
    """Guarda el producto opcional (KML suelto). Reutiliza case.kml_opcional/
    case.solo_kmz — los mismos campos que ya usa Configuración de Modo 1/2
    (sección 9: no duplicar estado). Para Puntos libres se fuerza a False:
    generar_kml_puntos_libres() solo produce KMZ (ver services_modo3), así
    que ofrecer la casilla ahí sería prometer algo que el generador no
    hace."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    if case.modo3_tipo == MODO3_TIPO_ANTENA:
        case.kml_opcional = request.form.get("kml_opcional") == "on"
    else:
        case.kml_opcional = False
    case.solo_kmz = not case.kml_opcional
    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.modo3_registros_screen"))
    return redirect(url_for("tz_web.modo3_color_screen"))


@bp.route("/modo3/color", methods=["GET"])
def modo3_color_screen():
    """Reutiliza el mismo template/selector de color que Modo 1/2
    (``configure_color.html``, paleta de ``config.json`` -> ``style.palette``)
    con guardas y navegación propias de Modo 3 en vez de las de
    Configuración (sección 2: no tocar la semántica gráfica del core)."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    selected_color = case.color_hex or _default_theme_hex()
    return render_template(
        "configure_color.html",
        case=case,
        palette=_theme_palette(),
        palette_groups=_grouped_palette(),
        selected_color=selected_color,
        color_action_url=url_for("tz_web.modo3_color_submit"),
        heading="Modo 3 — Color del mapa",
        step_label="Seleccione el color que se aplicará al mapa generado.",
        es_modo3=True,
        show_nav=False,
    )


@bp.route("/modo3/color", methods=["POST"])
@_mutation_guard("tz_web.modo3_color_screen")
def modo3_color_submit():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.modo3_productos_screen"))

    color_hex = (request.form.get("color_hex") or "").strip()
    paleta_hex = {hex_valor.lower() for _, hex_valor in _theme_palette()}
    if not color_hex or color_hex.lower() not in paleta_hex:
        flash("Elija uno de los colores disponibles en la paleta.", "error")
        return redirect(url_for("tz_web.modo3_color_screen"))

    case.color_hex = color_hex
    state.touch(case)
    return redirect(url_for("tz_web.modo3_preparar_screen"))


@bp.route("/modo3/preparar", methods=["GET"])
def modo3_preparar_screen():
    """Equivalente a "Preparar análisis" (configure_final.html) pero sin
    tipo de bitácora, filtro temporal, Top N ni identidad telefónica
    (sección 3): solo tipo, cantidad, nombre de salida y carpeta base."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    carpeta_salida = case.carpeta_salida
    suggested_name = None
    if not case.output_base_name:
        suggested_name = sugerir_nombre_modo3(case.modo3_tipo, case.modo3_registros)

    return render_template(
        "modo3_preparar.html",
        case=case,
        carpeta_salida=carpeta_salida,
        suggested_name=suggested_name,
        show_nav=False,
    )


@bp.route("/modo3/preparar", methods=["POST"])
@_mutation_guard("tz_web.modo3_preparar_screen")
def modo3_preparar_submit():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    if request.form.get("nombre_modo") == "manual":
        nombre_manual = (request.form.get("output_base_name") or "").strip()
        case.output_base_name = nombre_manual or None
    else:
        case.output_base_name = None
    state.touch(case)

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.modo3_color_screen"))
    return redirect(url_for("tz_web.modo3_resumen_screen"))


@bp.route("/modo3/resumen", methods=["GET"])
def modo3_resumen_screen():
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    carpeta_salida = case.carpeta_salida
    suggested_name = None
    if not case.output_base_name:
        suggested_name = sugerir_nombre_modo3(case.modo3_tipo, case.modo3_registros)

    return render_template(
        "modo3_resumen.html",
        case=case,
        carpeta_salida=carpeta_salida,
        suggested_name=suggested_name,
        color_name=_color_name_for_hex(case.color_hex) or _color_name_for_hex(_default_theme_hex()),
        selected_color_hex=case.color_hex or _default_theme_hex(),
        show_nav=False,
    )


_THREAD_START_ERROR_MESSAGE = (
    "No se pudo iniciar el procesamiento en segundo plano. Intente generar "
    "el análisis nuevamente."
)


def _log_technical_error_best_effort(context: str, exc: BaseException) -> None:
    """El log técnico nunca puede impedir una transición terminal."""
    try:
        state.log_technical_error(context, exc)
    except Exception:  # noqa: BLE001 - logging es deliberadamente best-effort
        pass


def _mark_run_failed(
    case: state.Session,
    exc: BaseException,
    context: str,
    *,
    user_message: Optional[str] = None,
) -> None:
    """Fija y libera el fallo antes de intentar escribir el log técnico."""
    try:
        translated = user_message or state.translate_error(exc)
    except Exception:  # noqa: BLE001 - ni la traducción puede dejar RUNNING
        translated = user_message or "Ocurrió un error inesperado durante el análisis."
    try:
        error_code = state.error_code_for(exc)
    except Exception:  # noqa: BLE001 - el código es auxiliar, FAILED es obligatorio
        error_code = None

    import time as _time

    # Orden contractual: terminal completo -> liberar reserva -> touch -> log.
    with state.terminal_run(case.id):
        case.error_message = translated
        case.error_code = error_code
        case.status = state.STATUS_FAILED
        case.finished_at = _time.time()
    state.touch(case)
    _log_technical_error_best_effort(context, exc)


def _start_task_modo3(case: state.Session) -> Tuple[bool, Optional[str]]:
    """Arranca el análisis de Modo 3 en segundo plano. Mismo mecanismo de
    exclusión y de progreso que ``_start_task`` (sección 10): una sola
    sesión activa a la vez a nivel web (``state.try_start_run_detailed``), y
    el mismo ``case.status``/``stage``/``percent``/``/status`` — no se
    inventa un segundo sistema de progreso.

    Devuelve ``(iniciado, motivo_rechazo)``: ``motivo_rechazo`` es ``None``
    salvo cuando ``iniciado`` es ``False``, en cuyo caso es uno de
    ``state.RUN_START_REJECTED_*`` para que el llamador elija el mensaje
    correcto (análisis en curso vs. cierre pendiente)."""
    if case.task_started or case.status in (
        state.STATUS_SUCCESS, state.STATUS_PARTIAL, state.STATUS_FAILED
    ):
        return True, None
    started, reason = state.try_start_run_detailed(case.id)
    if not started:
        return False, reason

    case.status = state.STATUS_RUNNING
    case.task_started = True
    case.stage = None
    case.stage_message = "En cola"
    case.sequence = 0
    case.percent = 0
    case.result = None
    case.error_message = None
    case.error_code = None
    import time as _time
    case.started_at = _time.time()

    def _on_progress(update: ProgressUpdate) -> None:
        case.stage = update.stage
        case.stage_message = update.message
        case.sequence = update.sequence
        case.percent = state.STAGE_PERCENT.get(update.stage, case.percent)
        state.touch(case)

    try:
        request_obj = Modo3Request(
            tipo=case.modo3_tipo,
            registros=copy.deepcopy(case.modo3_registros),
            carpeta_salida=case.carpeta_salida,
            color_hex=case.color_hex,
            kml_opcional=case.kml_opcional,
            output_base_name=case.output_base_name,
            on_progress=_on_progress,
        )

        def _worker() -> None:
            import time as _time
            try:
                result = process_case_modo3(request_obj)
            except Exception as exc:  # noqa: BLE001 - frontera terminal del worker
                _mark_run_failed(case, exc, "process_case_modo3")
                return

            result_status = getattr(result, "status", None)
            if result_status not in (RESULT_SUCCESS, RESULT_PARTIAL):
                _mark_run_failed(
                    case,
                    OutputValidationError(
                        "El procesamiento no produjo un estado final publicable."
                    ),
                    "process_case_modo3.result_status",
                )
                return
            with state.terminal_run(case.id):
                case.result = result
                case.status = (
                    state.STATUS_PARTIAL
                    if result_status == RESULT_PARTIAL
                    else state.STATUS_SUCCESS
                )
                case.finished_at = _time.time()
            state.touch(case)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
    except Exception as exc:  # noqa: BLE001 - rollback de reserva/preparación/start
        case.task_started = False
        _mark_run_failed(
            case,
            exc,
            "process_case_modo3.thread_start",
            user_message=_THREAD_START_ERROR_MESSAGE,
        )
    return True, None


@bp.route("/modo3/resumen", methods=["POST"])
@_mutation_guard("tz_web.modo3_resumen_screen")
def modo3_resumen_submit():
    """"Anterior" regresa a Preparar salida; "Generar análisis" valida la
    carpeta de salida (misma validación ya existente, ``state.
    ensure_writable_dir``) e inicia el análisis — único punto de arranque de
    la tarea, igual que ``configure_resumen_submit`` para Modo 1/2."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))
    if not _modo3_require_registros(case):
        flash("Agregue al menos un registro antes de continuar.", "error")
        return redirect(url_for("tz_web.modo3_registros_screen"))

    if request.form.get("accion", "siguiente") == "anterior":
        return redirect(url_for("tz_web.modo3_preparar_screen"))

    if not case.carpeta_salida:
        flash(MSG_CARPETA_SALIDA_REQUERIDA, "error")
        return redirect(url_for("tz_web.modo3_preparar_screen"))

    try:
        carpeta_salida_abs = state.ensure_writable_dir(case.carpeta_salida)
    except OSError as exc:
        state.log_technical_error("modo3_resumen_submit.ensure_dir", exc)
        flash("No se pudo preparar la carpeta de salida seleccionada.", "error")
        return redirect(url_for("tz_web.modo3_preparar_screen"))

    case.carpeta_salida = carpeta_salida_abs
    state.touch(case)

    started, reason = _start_task_modo3(case)
    if not started:
        _flash_start_rejected(reason)
        return redirect(url_for("tz_web.modo3_resumen_screen"))

    return redirect(url_for("tz_web.processing_screen"))


@bp.route("/modo3/results/back", methods=["POST"])
@_mutation_guard("tz_web.results_screen")
def modo3_results_back():
    """"Volver a preparar salida" desde un resultado FAILED de Modo 3
    (sección 12): los registros manuales viven en ``case.modo3_registros`` y
    nunca se tocan durante el pipeline ni aquí — solo se limpia el estado
    terminal de la corrida fallida (mismo ``_reset_terminal_run_state`` que
    usan las recuperaciones de Modo 1/2), sin repetir el ingreso."""
    case = _current_session(create=False)
    if not _modo3_guard(case):
        flash("Seleccione primero el Modo 3 desde el menú principal.", "error")
        return redirect(url_for("tz_web.menu_screen"))

    if case.status != state.STATUS_FAILED:
        flash("Solo una ejecuci\u00f3n fallida puede volver a preparar la salida.", "error")
        return redirect(url_for("tz_web.results_screen"))

    _reset_terminal_run_state(case)
    state.touch(case)
    return redirect(url_for("tz_web.modo3_preparar_screen"))


# ---------------------------------------------------------------------------
# Pantalla 4 — Procesamiento
# ---------------------------------------------------------------------------


def _start_task(case: state.Session) -> Tuple[bool, Optional[str]]:
    """Impide doble envío: una sola sesión activa a la vez a nivel web,
    además del threading.Lock propio de process_case().

    Devuelve ``(iniciado, motivo_rechazo)`` — ver ``_start_task_modo3``."""
    if case.task_started or case.status in (
        state.STATUS_SUCCESS, state.STATUS_PARTIAL, state.STATUS_FAILED
    ):
        return True, None  # ya en curso para esta sesión: no reintentar, solo continuar a /processing
    started, reason = state.try_start_run_detailed(case.id)
    if not started:
        return False, reason

    case.status = state.STATUS_RUNNING
    case.task_started = True
    case.stage = None
    case.stage_message = "En cola"
    case.sequence = 0
    case.percent = 0
    case.result = None
    case.error_message = None
    case.error_code = None
    import time as _time
    case.started_at = _time.time()

    def _on_progress(update: ProgressUpdate) -> None:
        case.stage = update.stage
        case.stage_message = update.message
        case.sequence = update.sequence
        case.percent = state.STAGE_PERCENT.get(update.stage, case.percent)
        state.touch(case)

    try:
        if not case.temp_path or not case.upload_dir or not case.upload_sha256:
            raise InputIntegrityError(
                "No existe una entrada aceptada con integridad registrada para esta ejecuci\u00f3n."
            )
        input_snapshot = create_input_snapshot(
            case.temp_path,
            os.path.join(case.upload_dir, ".execution-snapshots"),
            expected_sha256=case.upload_sha256,
            original_name=case.original_filename,
        )
        case.input_snapshot_path = input_snapshot.path
        case.input_snapshot_sha256 = input_snapshot.sha256

        request_obj = CaseRequest(
            ruta_archivo=input_snapshot.path,
            carpeta_salida=case.carpeta_salida,
            mapeo=copy.deepcopy(case.mapping),
            hoja=case.sheet,
            input_sha256=input_snapshot.sha256,
            input_original_name=input_snapshot.original_name,
            mode=case.modo,
            filtro_tiempo=copy.deepcopy(case.filtro_tiempo),
            tipo_bitacora=case.tipo_bitacora,
            identity_overrides=copy.deepcopy(case.identity_overrides) or None,
            top_antenas=case.top_antenas,
            top_contactos=case.top_contactos,
            color_hex=case.color_hex,
            solo_kmz=case.solo_kmz,
            output_base_name=case.output_base_name,
            date_order_decision=case.date_order_decision,
            duration_unit_decision=case.duration_unit_decision,
            qc_bloqueante_decision=case.qc_bloqueante_decision,
            on_progress=_on_progress,
        )

        def _worker() -> None:
            import time as _time
            try:
                result = process_case(request_obj)
            except Exception as exc:  # noqa: BLE001 - frontera terminal del worker
                _mark_run_failed(case, exc, "process_case")
                return

            result_status = getattr(result, "status", None)
            if result_status not in (RESULT_SUCCESS, RESULT_PARTIAL):
                _mark_run_failed(
                    case,
                    OutputValidationError(
                        "El procesamiento no produjo un estado final publicable."
                    ),
                    "process_case.result_status",
                )
                return
            with state.terminal_run(case.id):
                case.result = result
                case.status = (
                    state.STATUS_PARTIAL
                    if result_status == RESULT_PARTIAL
                    else state.STATUS_SUCCESS
                )
                case.finished_at = _time.time()
            state.touch(case)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
    except Exception as exc:  # noqa: BLE001 - rollback de reserva/preparación/start
        case.task_started = False
        _mark_run_failed(
            case,
            exc,
            "process_case.thread_start",
            user_message=(
                None if isinstance(exc, InputIntegrityError) else _THREAD_START_ERROR_MESSAGE
            ),
        )
    return True, None


@bp.route("/processing", methods=["GET"])
def processing_screen():
    case = _current_session(create=False)
    if case is not None and case.status in (
        state.STATUS_SUCCESS, state.STATUS_PARTIAL, state.STATUS_FAILED
    ):
        return redirect(url_for("tz_web.results_screen"))
    if case is None or not case.task_started:
        flash("Primero configure y confirme el análisis.", "error")
        return redirect(url_for("tz_web.configure_screen"))
    return render_template("processing.html", case=case)


@bp.route("/status", methods=["GET"])
def status_json():
    case = _current_session(create=False)
    if case is None:
        return jsonify({"error": "sin_sesion"}), 404
    return jsonify({
        "status": case.status,
        "stage": case.stage,
        "stage_label": state.STAGE_LABELS.get(case.stage or "", case.stage_message),
        "message": case.stage_message,
        "sequence": case.sequence,
        "percent": case.percent,
    })


# ---------------------------------------------------------------------------
# Pantalla 5 — Resultados
# ---------------------------------------------------------------------------


@bp.route("/results", methods=["GET"])
def results_screen():
    case = _current_session(create=False)
    if case is None or case.status not in (
        state.STATUS_SUCCESS, state.STATUS_PARTIAL, state.STATUS_FAILED
    ):
        flash("Aún no hay resultados disponibles.", "error")
        return redirect(url_for("tz_web.index"))
    return render_template(
        "results.html",
        case=case,
        es_modo3=(case.modo == state.MODO_3),
        mostrar_volver_filtro=(
            case.status == state.STATUS_FAILED
            and case.modo == state.MODO_2
            and case.error_code == state.ERROR_CODE_FILTRO_SIN_REGISTROS
        ),
        mostrar_volver_modo3=(case.status == state.STATUS_FAILED and case.modo == state.MODO_3),
    )


def _reset_terminal_run_state(case: state.Session) -> None:
    """Limpia el estado terminal de una corrida FAILED/PARTIAL (``error_message``/
    ``error_code``/``result``/``finished_at``/progreso), común a ambas
    acciones de recuperación desde Resultados (``results_back_to_mapping``/
    ``results_back_to_filtro_tiempo``) — ninguna toca archivo, hoja, mapeo ni
    Configuración 3A-3E."""
    case.status = state.STATUS_PENDING
    case.error_message = None
    case.error_code = None
    case.result = None
    case.stage = None
    case.stage_message = ""
    case.sequence = 0
    case.percent = 0
    case.task_started = False
    case.started_at = None
    case.finished_at = None


@bp.route("/results/back-to-products", methods=["POST"])
@_mutation_guard("tz_web.results_screen")
def results_back_to_products():
    """Desde PARTIAL vuelve a la seleccion del producto opcional.

    La entrada/snapshot y toda la configuracion permanecen intactos; solo se
    habilita una nueva ejecucion deliberada.
    """
    case = _current_session(create=False)
    if case is None or case.status != state.STATUS_PARTIAL:
        flash("No hay una ejecuci\u00f3n parcial para reconfigurar.", "error")
        return redirect(url_for("tz_web.results_screen"))

    _reset_terminal_run_state(case)
    state.touch(case)
    if case.modo == state.MODO_3:
        return redirect(url_for("tz_web.modo3_productos_screen"))
    return redirect(url_for("tz_web.configure_outputs_screen"))


@bp.route("/results/back-to-mapping", methods=["POST"])
@_mutation_guard("tz_web.results_screen")
def results_back_to_mapping():
    """"Volver a revisar mapeo" desde un resultado FAILED: repuebla
    ``mapping_draft`` a partir del mapeo ya confirmado (mismo patrón que
    ``configure_back_to_mapping``) y regresa a "Revisión del mapeo", sin
    perder archivo, hoja, mapeo ni Configuración 3A-3E (color, productos,
    Top N, unidad de duración, etc. — ningún campo de esas pantallas se
    toca aquí). Solo se limpia el estado terminal de la corrida fallida."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    if case.status != state.STATUS_FAILED:
        flash("Solo una ejecuci\u00f3n fallida puede volver al mapeo.", "error")
        return redirect(url_for("tz_web.results_screen"))

    case.mapping_draft = case.mapping
    case.mapping_stage = "review"
    _reset_terminal_run_state(case)
    state.touch(case)
    return redirect(url_for("tz_web.mapping_screen"))


@bp.route("/results/back-to-filtro-tiempo", methods=["POST"])
@_mutation_guard("tz_web.results_screen")
def results_back_to_filtro_tiempo():
    """"Volver a revisar filtro temporal" desde un resultado FAILED por
    filtro temporal sin registros (sección 9 del microbloque Modo 2 parte
    2): a diferencia de ``results_back_to_mapping``, no repuebla
    ``mapping_draft`` ni toca la etapa de mapeo — vuelve directo a Filtro
    temporal para que el usuario corrija solo la selección temporal, sin
    repetir archivo/mapeo/configuración."""
    case = _current_session(create=False)
    if case is None or not case.mapping or case.modo != state.MODO_2:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))
    if (
        case.status != state.STATUS_FAILED
        or case.error_code != state.ERROR_CODE_FILTRO_SIN_REGISTROS
    ):
        flash("Este resultado no corresponde a un filtro temporal sin registros.", "error")
        return redirect(url_for("tz_web.results_screen"))

    _reset_terminal_run_state(case)
    state.touch(case)
    return redirect(url_for("tz_web.configure_filtro_tiempo_screen"))


def _resolve_open_path(case: state.Session, kind: str) -> Optional[str]:
    if case.result is None:
        return None
    if kind == "folder":
        path = case.result.output_dir
        is_valid = bool(path and os.path.isdir(path))
    else:
        attr = _OPEN_KIND_ATTRS.get(kind)
        if attr is None:
            return None
        path = getattr(case.result, attr, None)
        is_valid = bool(path and os.path.isfile(path))

    if not is_valid or not case.result.output_dir:
        return None

    output_dir_abs = os.path.abspath(case.result.output_dir)
    path_abs = os.path.abspath(path)
    if os.path.commonpath([path_abs, output_dir_abs]) != output_dir_abs:
        return None
    return path_abs


@bp.route("/open/<kind>", methods=["POST"])
def open_product(kind: str):
    case = _current_session(create=False)
    if case is None:
        abort(404)

    path = _resolve_open_path(case, kind)
    if path is None:
        flash("El producto solicitado no está disponible.", "error")
        return redirect(url_for("tz_web.results_screen"))

    try:
        _open_with_default_app(path)
    except OSError as exc:
        state.log_technical_error("open_product", exc)
        flash("No se pudo abrir el elemento con la aplicación predeterminada del sistema.", "error")

    return redirect(url_for("tz_web.results_screen"))


@bp.route("/new", methods=["POST"])
@_mutation_guard("tz_web.menu_screen")
def new_case():
    session_id = flask_session.get("case_id")
    if session_id:
        state.discard_session(session_id)
    flask_session.pop("case_id", None)
    return redirect(url_for("tz_web.menu_screen"))


# ---------------------------------------------------------------------------
# Ayuda / Manual de usuario (MICROBLOQUE 6-2) — documentación estática local.
#
# Deliberadamente NO usa ``_current_session()``/``state.Session``: el manual
# debe funcionar sin caso abierto, sin tocar la sesión del navegador (ni
# siquiera crearla) y sin competir con ``mutation_guard``/``lifecycle`` — ver
# sección de seguridad del encargo: AYUDA es documentación estática, no una
# pantalla operativa, y no debe reflejar datos del caso en curso.
# ---------------------------------------------------------------------------


@bp.route("/help", methods=["GET"])
def help_screen():
    return render_template(
        "help.html",
        help_sections=help_content.HELP_SECTIONS,
        help_version_label=help_content.HELP_VERSION_LABEL,
    )


# ---------------------------------------------------------------------------
# Activos estáticos controlados (logo reutilizado sin duplicar, sección 3)
# ---------------------------------------------------------------------------
# Fase 2 (identidad visual): el logo anterior ("Logo TZ.png") llevaba el
# texto "TZ ANALYZER" incorporado en la propia imagen, lo que lo volvía
# ilegible al reducirse en el header. Se reemplaza por los assets aprobados
# en tz_core/assets/branding/ (sin texto incorporado): el icono de app para
# superficies pequeñas (header, portada, encabezado de AYUDA) y el isotipo
# principal para superficies con más espacio (sección "Acerca de" de AYUDA).
# "Logo TZ.png" se conserva como asset legacy sin eliminarse, pero deja de
# ser una dependencia activa de estas rutas.
#
# TZ_Analyzer_icono_app.png es además la fuente canónica identificada para
# el futuro icono del ejecutable empaquetado ("TZ Analyzer.exe"), pendiente
# de MB7/ONEDIR — no se genera ningún .ico en esta fase.
_BRANDING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tz_core", "assets", "branding"
)
_LOGO_PATH = os.path.join(_BRANDING_DIR, "TZ_Analyzer_icono_app.png")
_LOGO_ISOTIPO_PATH = os.path.join(_BRANDING_DIR, "TZ_Analyzer_isotipo_principal.png")


@bp.route("/assets/logo", methods=["GET"])
def logo_asset():
    if not os.path.isfile(_LOGO_PATH):
        abort(404)
    return send_file(_LOGO_PATH, mimetype="image/png", max_age=3600)


@bp.route("/assets/logo-isotipo", methods=["GET"])
def logo_isotipo_asset():
    if not os.path.isfile(_LOGO_ISOTIPO_PATH):
        abort(404)
    return send_file(_LOGO_ISOTIPO_PATH, mimetype="image/png", max_age=3600)


# ---------------------------------------------------------------------------
# Errores HTTP
# ---------------------------------------------------------------------------


@bp.app_errorhandler(413)
def request_entity_too_large(_exc):
    flash(
        f"El archivo supera el límite permitido de "
        f"{state.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        "error",
    )
    return redirect(url_for("tz_web.index"))
