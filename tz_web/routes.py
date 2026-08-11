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

import os
import threading
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
from tz_core.mapping_wizard import FIELD_CONTEXT
from tz_core.user_paths import resolve_default_output_dir
from tz_web import state
from tz_web.field_catalog import FIELD_DESCRIPTIONS, FIELD_GROUPS, FIELD_LABELS
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


def _open_with_default_app(path: str) -> None:
    """Abre ``path`` con la aplicación asociada del sistema operativo.

    Aislado en una función propia para que las pruebas puedan sustituirlo
    sin abrir aplicaciones reales durante la suite automatizada.
    """
    if hasattr(os, "startfile"):
        os.startfile(path)  # noqa: S606 - ruta ya validada contra CaseResult, ver _resolve_open_path


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
    case.available_sheets = []
    _reset_sheet_state(case)


@bp.route("/", methods=["GET"])
def cover_screen():
    return render_template("cover.html", show_nav=False)


@bp.route("/menu", methods=["GET"])
def menu_screen():
    return render_template("menu.html", show_nav=False)


@bp.route("/modo/<int:n>", methods=["POST"])
def mode_pending(n: int):
    if n not in (2, 3):
        abort(404)
    flash("Modo pendiente de incorporación web.", "error")
    return redirect(url_for("tz_web.menu_screen"))


@bp.route("/analizador", methods=["GET"])
def index():
    case = _current_session()
    return render_template("index.html", case=case)


@bp.route("/upload", methods=["POST"])
def upload():
    case = _current_session()

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
    os.makedirs(upload_dir, exist_ok=True)
    dest_path = os.path.join(upload_dir, safe_name)

    try:
        upload_file.save(dest_path)
    except OSError as exc:
        state.log_technical_error("upload.save", exc)
        flash("No se pudo guardar el archivo subido.", "error")
        return redirect(url_for("tz_web.index"))

    if os.path.getsize(dest_path) > state.MAX_UPLOAD_BYTES:
        os.remove(dest_path)
        flash(
            f"El archivo supera el límite permitido de "
            f"{state.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            "error",
        )
        return redirect(url_for("tz_web.index"))

    try:
        hojas = _list_sheets(dest_path)
    except Exception as exc:  # noqa: BLE001 - error de lectura de un archivo ajeno, se traduce
        state.log_technical_error("upload.list_sheets", exc)
        os.remove(dest_path)
        flash("El archivo no pudo leerse. Verifique que sea un Excel válido y no esté dañado.", "error")
        return redirect(url_for("tz_web.index"))

    if not hojas:
        os.remove(dest_path)
        flash("El archivo no tiene hojas visibles para analizar.", "error")
        return redirect(url_for("tz_web.index"))

    # Nuevo archivo reinicia cualquier estado de mapeo/configuración previo.
    _reset_file_state(case)
    case.temp_path = dest_path
    case.original_filename = upload_file.filename
    case.upload_dir = upload_dir
    case.available_sheets = hojas
    state.touch(case)

    return redirect(url_for("tz_web.index"))


@bp.route("/file/change", methods=["POST"])
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


def _parse_mapping_form(case: state.Session) -> Tuple[Dict[str, Tuple[str, Any]], Optional[str]]:
    """Construye el dict de mapeo desde el formulario.

    Devuelve ``(mapeo, error)``; ``error`` no es None si hay una asignación
    de columna duplicada (impedida aquí, de forma más estricta que el aviso
    no bloqueante del motor) o un valor fijo vacío.
    """
    mapeo: Dict[str, Tuple[str, Any]] = {}
    columnas_usadas: Dict[str, List[str]] = {}

    for campo in CANONICAL_FIELDS:
        tipo = request.form.get(f"tipo_{campo}", "omitido")
        if tipo == "col":
            columna = (request.form.get(f"col_{campo}") or "").strip()
            if not columna or columna not in case.columns:
                return {}, f"Seleccione una columna válida para '{campo}'."
            mapeo[campo] = ("col", columna)
            columnas_usadas.setdefault(columna, []).append(campo)
        elif tipo == "fijo":
            valor = (request.form.get(f"fijo_{campo}") or "").strip()
            if not valor:
                return {}, f"Indique un valor fijo para '{campo}' o cambie la asignación a 'Omitir'."
            mapeo[campo] = ("fijo", valor)
        else:
            mapeo[campo] = ("omitido", None)

    duplicadas = {col: campos for col, campos in columnas_usadas.items() if len(campos) > 1}
    if duplicadas:
        detalle = "; ".join(f"'{col}' → {', '.join(campos)}" for col, campos in duplicadas.items())
        return {}, f"Una misma columna no puede asignarse a más de un campo: {detalle}."

    return mapeo, None


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
    )


@bp.route("/mapping", methods=["POST"])
def mapping_submit():
    case = _current_session(create=False)
    if case is None or not case.columns:
        flash("Primero cargue un archivo y seleccione una hoja.", "error")
        return redirect(url_for("tz_web.index"))

    mapeo, error = _parse_mapping_form(case)
    if error:
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
def mapping_confirm():
    case = _current_session(create=False)
    if case is None or not case.mapping_draft:
        flash("No hay un mapeo pendiente de confirmar.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    case.mapping = case.mapping_draft
    case.mapping_draft = None
    case.mapping_stage = "form"
    state.touch(case)
    return redirect(url_for("tz_web.configure_screen"))


@bp.route("/mapping/edit", methods=["POST"])
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
        selected_color=selected_color,
    )


@bp.route("/configure/color", methods=["POST"])
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
    carpeta_salida = case.carpeta_salida or resolve_default_output_dir(warn=lambda _msg: None)

    suggested_name = None
    if not case.output_base_name:
        suggested_name = preview_suggested_case_name(
            ruta_archivo=case.temp_path,
            hoja=case.sheet,
            mapeo=case.mapping,
            identity_overrides=case.identity_overrides,
            tipo_bitacora=tipo_bitacora_actual,
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
    )
    return jsonify({"suggested_name": suggested_name})


@bp.route("/configure/final", methods=["POST"])
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

    # Modo 1 (sección 4 del microbloque): sin filtro temporal, siempre.
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

    carpeta_salida = case.carpeta_salida or resolve_default_output_dir(warn=lambda _msg: None)

    suggested_name = None
    if not case.output_base_name:
        suggested_name = preview_suggested_case_name(
            ruta_archivo=case.temp_path,
            hoja=case.sheet,
            mapeo=case.mapping,
            identity_overrides=case.identity_overrides,
            tipo_bitacora=case.tipo_bitacora,
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
    )


@bp.route("/configure/resumen", methods=["POST"])
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

    carpeta_resuelta = case.carpeta_salida or resolve_default_output_dir(warn=lambda _msg: None)
    try:
        carpeta_salida_abs = state.ensure_writable_dir(carpeta_resuelta)
    except OSError as exc:
        state.log_technical_error("configure_resumen_submit.ensure_dir", exc)
        flash("No se pudo preparar la carpeta de salida segura del sistema.", "error")
        return redirect(url_for("tz_web.configure_resumen_screen"))

    case.carpeta_salida = carpeta_salida_abs
    state.touch(case)

    started = _start_task(case)
    if not started:
        flash(state.MSG_ANALYSIS_IN_PROGRESS, "error")
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

    started = _start_task(case)
    if not started:
        flash(state.MSG_ANALYSIS_IN_PROGRESS, "error")
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
# Pantalla 4 — Procesamiento
# ---------------------------------------------------------------------------


def _start_task(case: state.Session) -> bool:
    """Impide doble envío: una sola sesión activa a la vez a nivel web,
    además del threading.Lock propio de process_case()."""
    if case.status == state.STATUS_RUNNING:
        return True  # ya en curso para esta sesión: no reintentar, solo continuar a /processing
    if not state.try_start_run(case.id):
        return False

    case.status = state.STATUS_RUNNING
    case.task_started = True
    case.stage = None
    case.stage_message = "En cola"
    case.sequence = 0
    case.percent = 0
    case.result = None
    case.error_message = None
    import time as _time
    case.started_at = _time.time()

    def _on_progress(update: ProgressUpdate) -> None:
        case.stage = update.stage
        case.stage_message = update.message
        case.sequence = update.sequence
        case.percent = state.STAGE_PERCENT.get(update.stage, case.percent)
        state.touch(case)

    request_obj = CaseRequest(
        ruta_archivo=case.temp_path,
        carpeta_salida=case.carpeta_salida,
        mapeo=dict(case.mapping),
        hoja=case.sheet,
        filtro_tiempo=case.filtro_tiempo,
        tipo_bitacora=case.tipo_bitacora,
        identity_overrides=case.identity_overrides or None,
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
            case.result = result
            case.status = state.STATUS_SUCCESS
        except Exception as exc:  # noqa: BLE001 - frontera del worker: se traduce, nunca se propaga
            state.log_technical_error("process_case", exc)
            case.error_message = state.translate_error(exc)
            case.status = state.STATUS_FAILED
        finally:
            case.finished_at = _time.time()
            state.finish_run(case.id)
            state.touch(case)

    threading.Thread(target=_worker, daemon=True).start()
    return True


@bp.route("/processing", methods=["GET"])
def processing_screen():
    case = _current_session(create=False)
    if case is None or not case.task_started:
        flash("Primero configure y confirme el análisis.", "error")
        return redirect(url_for("tz_web.configure_screen"))
    if case.status in (state.STATUS_SUCCESS, state.STATUS_FAILED):
        return redirect(url_for("tz_web.results_screen"))
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
    if case is None or case.status not in (state.STATUS_SUCCESS, state.STATUS_FAILED):
        flash("Aún no hay resultados disponibles.", "error")
        return redirect(url_for("tz_web.index"))
    return render_template("results.html", case=case)


@bp.route("/results/back-to-mapping", methods=["POST"])
def results_back_to_mapping():
    """"Volver a revisar mapeo" desde un resultado FAILED: repuebla
    ``mapping_draft`` a partir del mapeo ya confirmado (mismo patrón que
    ``configure_back_to_mapping``) y regresa a "Revisión del mapeo", sin
    perder archivo, hoja, mapeo ni Configuración 3A-3E (color, productos,
    Top N, unidad de duración, etc. — ningún campo de esas pantallas se
    toca aquí). Solo se limpia el estado terminal de la corrida fallida
    (``error_message``/``result``/``finished_at``/progreso), que ya no
    corresponde a la corrida que viene."""
    case = _current_session(create=False)
    if case is None or not case.mapping:
        flash("Primero confirme el mapeo de columnas.", "error")
        return redirect(url_for("tz_web.mapping_screen"))

    case.mapping_draft = case.mapping
    case.mapping_stage = "review"
    case.status = state.STATUS_PENDING
    case.error_message = None
    case.result = None
    case.stage = None
    case.stage_message = ""
    case.sequence = 0
    case.percent = 0
    case.task_started = False
    case.started_at = None
    case.finished_at = None
    state.touch(case)
    return redirect(url_for("tz_web.mapping_screen"))


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
def new_case():
    session_id = flask_session.get("case_id")
    if session_id:
        state.discard_session(session_id)
    flask_session.pop("case_id", None)
    return redirect(url_for("tz_web.menu_screen"))


# ---------------------------------------------------------------------------
# Activos estáticos controlados (logo reutilizado sin duplicar, sección 3)
# ---------------------------------------------------------------------------

_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tz_core", "assets", "Logo TZ.png"
)


@bp.route("/assets/logo", methods=["GET"])
def logo_asset():
    if not os.path.isfile(_LOGO_PATH):
        abort(404)
    return send_file(_LOGO_PATH, mimetype="image/png", max_age=3600)


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
