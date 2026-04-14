"""
mapping_wizard.py — Wizard interactivo para mapeo de columnas Excel → canónicas
=================================================================================

MIGRADO DE: script_principal_bitacoras_refactory.py L183-565 (Epic 15)
FECHA: 27/12/2025
RAZÓN: Modularización arquitectura híbrida (Epic 15 - Wizard QC completo)

⚡ ADVERTENCIA: Código crítico de 382 líneas extraído con máxima precaución.
Este módulo implementa el wizard interactivo QC manual marcado previamente
como "PELIGRO EXTREMO". La extracción se realizó con protocolo paranoico.

ARQUITECTURA:
- MappingWizard: Clase principal con separación de responsabilidades
- UI Layer: Interacción con usuario (input/print)
- Logic Layer: Procesamiento de mapeos y validaciones
- Data Layer: Aplicación de transformaciones a DataFrame

DEPENDENCIAS:
- pandas: Manipulación DataFrame
- input(): Interacción consola (17+ llamadas)

USO:
    from tz_core.mapping_wizard import MappingWizard
    
    wizard = MappingWizard(df, esenciales=["fecha", "tel", "lat", "long"], 
                           no_esenciales=["alias", "duracion"])
    df_mapeado, asignaciones = wizard.run()

COMPATIBILIDAD:
Mantiene firma exacta de _wizard_qc_mapeo() original para garantizar cero regresiones.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Any, Callable, Sequence

import pandas as pd


@dataclass
class WizardIO:
    """Abstrae interacción de consola para permitir pruebas sin `input`/`print`."""

    input_fn: Callable[[str], str] = input
    output_fn: Callable[[str], None] = print

    def prompt(self, message: str) -> str:
        """Obtiene entrada del usuario de forma resiliente."""
        try:
            return self.input_fn(message)
        except Exception:
            return ""

    def write(self, message: str) -> None:
        """Emite mensajes sin fallar si la salida personalizada explota."""
        try:
            self.output_fn(message)
        except Exception:
            pass


def apply_wizard_assignments(
    df: pd.DataFrame,
    assignments: Dict[str, Tuple[str, Any]],
    numeric_fields: Optional[Set[str]] = None,
    writer: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """Aplica asignaciones del wizard sobre una copia del DataFrame."""

    numeric_fields = set(numeric_fields or set())
    safe_write = writer or (lambda _msg: None)
    result = df.copy()

    # 1) Renombres / valores fijos
    for canonical, (tipo, val) in assignments.items():
        if tipo == "col":
            src = val
            if src != canonical:
                if src in result.columns:
                    result = result.rename(columns={src: canonical})
                else:
                    lowered = str(src).strip().lower()
                    for existing in list(result.columns):
                        if str(existing).strip().lower() == lowered:
                            result = result.rename(columns={existing: canonical})
                            break
        elif tipo == "fijo":
            result[canonical] = val

    # 2) Deduplicar columnas
    result = result.loc[:, ~result.columns.duplicated(keep="first")]

    # 3) Tipado numérico resiliente
    for column in numeric_fields:
        if column in result.columns:
            try:
                serie = result[column]
                if hasattr(serie, "squeeze"):
                    serie = serie.squeeze()
                result[column] = pd.to_numeric(serie, errors="coerce")
            except Exception as exc:
                safe_write(f"[QC] Aviso: no se pudo convertir '{column}' a numérico ({exc}); se deja como está.")

    # 4) Fallback antena/siteid
    if "antena" not in result.columns and "siteid" in result.columns:
        result = result.rename(columns={"siteid": "antena"})

    # 5) Deduplicar nuevamente en caso de fallback
    result = result.loc[:, ~result.columns.duplicated(keep="first")]
    return result


def normalize_wizard_datetime_fields(
    df: pd.DataFrame,
    warn_writer: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """Normaliza columnas 'fecha'/'hora' respetando el formato QC tradicional."""

    warn = warn_writer or (lambda _msg: None)

    try:
        fecha_dt: Optional[pd.Series] = None

        if "fecha" in df.columns:
            fecha_text = df["fecha"].astype(str).str.strip()
            fecha_dt = pd.Series(pd.NaT, index=fecha_text.index, dtype="datetime64[ns]")

            mask_iso = fecha_text.str.match(r"^\d{4}-\d{2}-\d{2}$")
            if mask_iso.any():
                fecha_dt.loc[mask_iso] = pd.to_datetime(
                    fecha_text.loc[mask_iso],
                    format="%Y-%m-%d",
                    errors="coerce",
                )

            mask_other = ~mask_iso
            if mask_other.any():
                fecha_dt.loc[mask_other] = pd.to_datetime(
                    fecha_text.loc[mask_other],
                    errors="coerce",
                    dayfirst=True,
                )

            df["fecha"] = fecha_dt.dt.strftime("%d/%m/%Y")

        if "hora" in df.columns:
            hora_text = df["hora"].astype(str).str.strip()
            hora_dt = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

            mask_hms = hora_text.str.match(r"^\d{1,2}:\d{2}(:\d{2})?$")
            if mask_hms.any():
                hora_fmt = hora_text.loc[mask_hms].str.replace(
                    r"^(\d{1,2}:\d{2})$",
                    r"\1:00",
                    regex=True,
                )
                hora_dt.loc[mask_hms] = pd.to_datetime(
                    hora_fmt,
                    format="%H:%M:%S",
                    errors="coerce",
                )

            mask_remaining = ~mask_hms & hora_text.ne("")
            if mask_remaining.any():
                prefixed = "1970-01-01 " + hora_text.loc[mask_remaining]
                def _strip_tz(v):
                    try:
                        ts = pd.to_datetime(v, dayfirst=True, errors="coerce")
                        if ts is pd.NaT:
                            return pd.NaT
                        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                            ts = ts.tz_localize(None)
                        return ts
                    except Exception:
                        return pd.NaT
                _parsed = prefixed.map(_strip_tz)
                hora_dt.loc[mask_remaining] = pd.to_datetime(_parsed, errors="coerce", utc=False)

            hora_out = pd.Series("", index=df.index, dtype=object)

            mask_ok = hora_dt.notna()
            if mask_ok.any():
                hora_out.loc[mask_ok] = hora_dt.loc[mask_ok].dt.strftime("%H:%M:%S")

            mask_bad = ~mask_ok & hora_text.ne("")
            if mask_bad.any():
                prefixed = "1970-01-01 " + hora_text.loc[mask_bad]
                hora_try = pd.to_datetime(prefixed, errors="coerce", dayfirst=True)
                mask_try = hora_try.notna()
                if mask_try.any():
                    target_idx = hora_text.loc[mask_bad].index[mask_try]
                    hora_out.loc[target_idx] = hora_try.loc[mask_try].dt.strftime("%H:%M:%S").values

            if fecha_dt is not None:
                mask_empty = hora_out.eq("")
                if mask_empty.any():
                    hora_from_fecha = fecha_dt.dt.strftime("%H:%M:%S")
                    fill_mask = mask_empty & fecha_dt.notna()
                    hora_out.loc[fill_mask] = hora_from_fecha.loc[fill_mask]

            df["hora"] = hora_out.replace("", "Sin Inf.")
        else:
            if fecha_dt is not None:
                hora_from_fecha = fecha_dt.dt.strftime("%H:%M:%S")
                df["hora"] = hora_from_fecha.where(fecha_dt.notna(), "Sin Inf.")
            else:
                df["hora"] = "Sin Inf."

    except Exception as exc:
        warn(f"[WARN] Normalización fecha/hora: {exc}")
        if "lat" in df.columns:
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        if "long" in df.columns:
            df["long"] = pd.to_numeric(df["long"], errors="coerce")

    return df


def finalize_manual_mapping_dataframe(
    df: pd.DataFrame,
    *,
    numeric_fields: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Ajustes post-wizard: sincroniza lon/long y fuerza campos numéricos."""

    if "lon" in df.columns and "long" not in df.columns:
        df["long"] = df["lon"]
    elif "long" in df.columns and "lon" not in df.columns:
        df["lon"] = df["long"]

    target_numeric = numeric_fields or ("lat", "lon", "long", "azimut")
    for column in target_numeric:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def apply_quick_remap_selection(
    df: pd.DataFrame,
    canonical: str,
    selection: str,
    columns_menu: List[str],
) -> pd.DataFrame:
    """Aplica una única selección del remapeo rápido sobre el DataFrame."""

    decision = resolve_non_essential_selection(selection, columns_menu)

    if decision.action == "fixed":
        df[canonical] = decision.fixed_value or ""
        return df

    if decision.action == "assign" and decision.column:
        column_name = decision.column
        if column_name != canonical and column_name in df.columns:
            return df.rename(columns={column_name: canonical})
        return df

    # Para acciones omit/show_menu/invalid no se modifica el DataFrame
    return df


def perform_quick_remap_batch(
    df: pd.DataFrame,
    columns_menu: List[str],
    operations: List[Tuple[str, str]],
) -> pd.DataFrame:
    """Aplica una lista de selecciones de remapeo rápido de forma pura."""

    result = df
    for canonical, selection in operations:
        result = apply_quick_remap_selection(result, canonical, selection, columns_menu)

    return result.loc[:, ~result.columns.duplicated(keep="first")]


def collect_quick_remap_operations(
    prompt_fn: Callable[[str], str],
    write_fn: Callable[[str], None],
    columns_menu: List[str],
    canonicals: List[str],
    per_line: int = 6,
) -> List[Tuple[str, str]]:
    """Recolecta las selecciones del remapeo rápido respetando '?' y prompts."""

    operations: List[Tuple[str, str]] = []
    for canonical in canonicals:
        prompt_msg = (
            f"→ Elegí columna para {canonical} (n / 'F valor' / Enter=omitir — '?' para ver menú): "
        )
        while True:
            selection = prompt_fn(prompt_msg).strip()
            decision = resolve_non_essential_selection(selection, columns_menu)
            if decision.action == "show_menu":
                write_fn(format_columns_menu(columns_menu, per_line=per_line))
                prompt_msg = f"→ Elegí columna para **{canonical}**: "
                continue
            operations.append((canonical, selection))
            break
    return operations


FIELD_CONTEXT: Dict[str, Dict[str, str]] = {
    "fecha": {
        "desc": "Fecha del evento telefónico",
        "hint": "Formatos comunes: DD/MM/YYYY, YYYY-MM-DD",
    },
    "hora": {
        "desc": "Hora del evento",
        "hint": "Formatos: HH:MM:SS o columna con fecha+hora completa",
    },
    "tel": {
        "desc": "Número telefónico investigado (origen)",
        "hint": "Ej: 50370001234, +50370001234, 70001234",
    },
    "imei": {
        "desc": "IMEI del dispositivo móvil investigado",
        "hint": "15 dígitos. Ej: 860766049463800",
    },
    "interaccion": {
        "desc": "Tipo de evento: llamada, SMS, datos",
        "hint": "Valores típicos: VOZ, SMS, DATOS, LLAMADA",
    },
    "contacto": {
        "desc": "Número con quien se comunicó el investigado",
        "hint": "Número destino de la llamada o mensaje",
    },
    "lat": {
        "desc": "Latitud GPS de la antena (posición Norte-Sur)",
        "hint": "Rango El Salvador: 13.0 a 14.5",
    },
    "long": {
        "desc": "Longitud GPS de la antena (posición Este-Oeste)",
        "hint": "Rango El Salvador: -90.1 a -87.7 (negativa)",
    },
    "azimut": {
        "desc": "Orientación de la antena en grados",
        "hint": "0-360° (0=Norte, 90=Este, 180=Sur, 270=Oeste)",
    },
    "antena": {
        "desc": "Código o nombre de la antena/celda",
        "hint": "Ej: 39512-0473-3, BTS_12345, nombre de sitio",
    },
    "celda": {
        "desc": "Código identificador de celda telefónica",
        "hint": "Opcional. Complementa la antena",
    },
    "direccion": {
        "desc": "Dirección física donde está la antena",
        "hint": "Opcional. Puede ser la misma columna que antena",
    },
    "imsi": {
        "desc": "IMSI de la tarjeta SIM",
        "hint": "Opcional. 15 dígitos",
    },
    "duracion": {
        "desc": "Duración de la llamada o evento",
        "hint": "Opcional. En segundos, minutos o HH:MM:SS",
    },
}


def collect_essential_mapping_assignments(
    canonicals: List[str],
    columns_menu: List[str],
    prompt_fn: Callable[[str], str],
    write_fn: Callable[[str], None],
    etiquetas: Optional[Dict[str, str]] = None,
    initial_assignments: Optional[Dict[str, Tuple[str, Any]]] = None,
    initial_used_columns: Optional[Set[str]] = None,
    initial_pendings: Optional[List[str]] = None,
    per_line: int = 6,
    df: Optional["pd.DataFrame"] = None,
) -> Tuple[Dict[str, Tuple[str, Any]], Set[str], List[str]]:
    """Itera el loop de esenciales devolviendo estructuras actualizadas."""

    assignments = dict(initial_assignments or {})
    used_columns = set(initial_used_columns or set())
    pendientes = list(initial_pendings or [])
    etiquetas = etiquetas or {}

    i = 0
    while i < len(canonicals):
        canonical = canonicals[i]
        go_back = False

        etiqueta_visible = etiquetas.get(canonical, canonical)
        ctx = FIELD_CONTEXT.get(canonical, {})
        desc = ctx.get("desc", "")
        hint = ctx.get("hint", "")
        write_fn(format_columns_menu(columns_menu, per_line=per_line))
        if desc:
            write_fn(f"\n  📌 {etiqueta_visible}: {desc}")
        if hint:
            write_fn(f"     {hint}")
        prompt_msg = (
            f"→ Columna para {etiqueta_visible} (número — '?' menú / Enter=omitir): "
        )

        while True:
            raw_input = prompt_fn(prompt_msg)
            selection = (raw_input or "").strip()
            decision = resolve_essential_column_selection(selection, columns_menu, used_columns)

            if decision.action == "show_menu":
                write_fn(format_columns_menu(columns_menu, per_line=per_line))
                prompt_msg = f"→ Elegí columna para **{canonical}**: "
                continue

            if decision.action == "omit":
                previous = assignments.get(canonical)
                if previous and previous[0] == "col" and previous[1]:
                    used_columns.discard(previous[1])
                if canonical not in pendientes:
                    pendientes.append(canonical)
                assignments[canonical] = ("omitido", None)
                confirm_resp = prompt_fn("Campo omitido. (S=Confirmar, A=Atrás): ").strip().upper()
                if confirm_resp == "A":
                    go_back = True
                break

            if decision.action == "assign" and decision.column:
                previous = assignments.get(canonical)
                if previous and previous[0] == "col" and previous[1]:
                    used_columns.discard(previous[1])
                assignments[canonical] = ("col", decision.column)
                used_columns.add(decision.column)
                while canonical in pendientes:
                    pendientes.remove(canonical)
                if df is not None:
                    preview_column_sample(df, decision.column, write_fn)
                confirm_resp = prompt_fn("¿Es correcta? (S=Sí, N=Elegir otra, A=Atrás): ").strip().upper()
                if confirm_resp == "N":
                    assignments[canonical] = ("omitido", None)
                    used_columns.discard(decision.column)
                    continue
                elif confirm_resp == "A":
                    assignments[canonical] = ("omitido", None)
                    used_columns.discard(decision.column)
                    go_back = True
                    break
                else:
                    break

            if decision.action == "duplicate" and decision.column:
                write_fn(
                    f"  [QC] Advertencia: la columna '{decision.column}' ya fue asignada a otro esencial. Elegí otra."
                )
                prompt_msg = f"→ Elegí columna para **{canonical}**: "
                continue

            prompt_msg = "  [QC] Entrada inválida. Debe ser un número de la lista (o Enter=omitir): "

        if go_back:
            if i > 0:
                prev_canonical = canonicals[i - 1]
                prev_assign = assignments.get(prev_canonical)
                if prev_assign and prev_assign[0] == "col":
                    used_columns.discard(prev_assign[1])
                assignments[prev_canonical] = ("omitido", None)
                if prev_canonical not in pendientes:
                    pendientes.append(prev_canonical)
                i -= 1
            # Si i == 0, repite el primer campo sin retroceder más
        else:
            i += 1

    _detect_shared_datetime(assignments, df, prompt_fn, write_fn)
    return assignments, used_columns, pendientes


def collect_non_essential_mapping_assignments(
    canonicals: List[str],
    columns_menu: List[str],
    prompt_fn: Callable[[str], str],
    write_fn: Callable[[str], None],
    etiquetas: Optional[Dict[str, str]] = None,
    initial_assignments: Optional[Dict[str, Tuple[str, Any]]] = None,
    per_line: int = 6,
    df: Optional["pd.DataFrame"] = None,
) -> Dict[str, Tuple[str, Any]]:
    """Itera el loop de no esenciales devolviendo asignaciones actualizadas."""

    assignments = dict(initial_assignments or {})
    etiquetas = etiquetas or {}

    for canonical in canonicals:
        etiqueta_visible = etiquetas.get(canonical, canonical)
        ctx = FIELD_CONTEXT.get(canonical, {})
        desc = ctx.get("desc", "")
        hint = ctx.get("hint", "")
        write_fn(format_columns_menu(columns_menu, per_line=per_line))
        if desc:
            write_fn(f"\n  📌 {etiqueta_visible}: {desc}")
        if hint:
            write_fn(f"     {hint}")
        prompt_msg = (
            f"→ Columna para {etiqueta_visible} (n / 'F valor' / Enter=omitir — '?' menú): "
        )

        while True:
            raw_input = prompt_fn(prompt_msg)
            selection = raw_input if isinstance(raw_input, str) else ""
            decision = resolve_non_essential_selection(selection, columns_menu)

            if decision.action == "show_menu":
                write_fn(format_columns_menu(columns_menu, per_line=per_line))
                prompt_msg = f"→ Elegí columna para **{canonical}**: "
                continue

            if decision.action == "omit":
                assignments[canonical] = ("omitido", None)
                break

            if decision.action == "fixed":
                assignments[canonical] = ("fijo", decision.fixed_value or "")
                break

            if decision.action == "assign" and decision.column:
                if df is not None:
                    preview_column_sample(df, decision.column, write_fn)
                confirm = prompt_fn("  ¿Correcto? (S=Sí, N=Elegir otra): ").strip().upper()
                if confirm == "S":
                    assignments[canonical] = ("col", decision.column)
                    break
                elif confirm == "N":
                    continue
                else:
                    write_fn("  Entrada inválida. Use S o N.")
                    continue
            if decision.action == "invalid":
                write_fn("  Entrada inválida. Use número, 'F valor' o Enter.")
                continue
            assignments[canonical] = ("omitido", None)
            break

    return assignments


def format_columns_menu(cols: List[str], per_line: int = 6) -> str:
    """Formatea un menú numerado horizontal para mostrar columnas."""

    rows: List[str] = []
    current: List[str] = []

    for index, column in enumerate(cols, start=1):
        current.append(f"[{index}] {column}")
        if len(current) == per_line:
            rows.append("  " + "  |  ".join(current))
            current = []

    if current:
        rows.append("  " + "  |  ".join(current))

    return "\n".join(rows)


def preview_column_sample(
    df: pd.DataFrame,
    column_name: str,
    write_fn: Callable[[str], None],
    max_rows: int = 3,
) -> None:
    """Muestra valores de ejemplo de una columna seleccionada."""
    if column_name not in df.columns:
        return
    sample = df[column_name].dropna().head(max_rows)
    if sample.empty:
        write_fn(f"  (columna '{column_name}' está vacía)")
        return
    write_fn(f"  Vista previa de '{column_name}':")
    for val in sample:
        write_fn(f"    {val}")


def build_mapping_intro_lines(
    title: str,
    columns_menu: List[str],
    instructions: Optional[str] = None,
    show_header_once: bool = False,
    per_line: int = 6,
    show_columns: bool = True,
) -> List[str]:
    """Genera las líneas estándar para introducir un bloque de mapeo."""

    lines: List[str] = []
    if show_header_once:
        lines.append("\n[QC] Columnas disponibles (una sola vez):")
    if show_columns:
        lines.append(format_columns_menu(columns_menu, per_line=per_line))
    lines.append(f"\n[QC] === Mapeo {title} ===")
    if instructions:
        lines.append(instructions)
    return lines


def build_remap_menu_order(
    essentials: List[str],
    non_essentials: List[str],
    fixed_order: Optional[List[str]] = None,
) -> List[str]:
    """Devuelve la lista ordenada de canónicos para remapeo unitario."""

    fixed = fixed_order or [
        "tel",
        "lat",
        "lon",
        "fecha",
        "hora",
        "azimut",
        "imei",
        "antena",
        "interaccion",
        "contacto",
        "alias",
        "nombre_usuario",
        "abonado",
        "celda",
        "direccion",
        "imsi",
        "duracion",
    ]

    base = list(dict.fromkeys(essentials + non_essentials))
    ordered = [canonical for canonical in fixed if canonical in base]
    ordered += [canonical for canonical in base if canonical not in ordered]
    return ordered


def format_mapping_summary(assignments: Dict[str, Tuple[str, Any]]) -> List[str]:
    """Genera las filas de resumen según las asignaciones actuales."""

    lines: List[str] = []
    for canonical, (kind, value) in assignments.items():
        if kind == "col":
            lines.append(f"  {canonical:12s} <- columna '{value}'")
        elif kind == "fijo":
            lines.append(f"  {canonical:12s} <- fijo '{value}'")
        else:
            lines.append(f"  {canonical:12s} <- omitido")
    return lines


def build_pending_warning_lines(pendientes: List[str]) -> List[str]:
    """Construye los mensajes de advertencia para esenciales omitidos."""

    if not pendientes:
        return []
    joined = ", ".join(pendientes)
    return [
        "\n[QC] Aviso: omitiste canónicos ESENCIALES: " + joined,
        "Podés volver a ejecutar para completar esos campos, o continuar bajo tu responsabilidad.",
    ]


def build_preview_table(df: pd.DataFrame, ordered_columns: List[str], max_rows: int = 3) -> Optional[str]:
    """Devuelve representación textual del preview respetando el orden indicado."""

    try:
        subset = df.head(max_rows)
        if ordered_columns:
            cols = [c for c in ordered_columns if c in subset.columns]
            subset = subset[cols]
        return str(subset)
    except Exception:
        return None


def needs_identity_field_prompt(df: pd.DataFrame, field: str) -> bool:
    """Indica si un campo de identidad falta o está vacío."""

    if field not in df.columns:
        return True

    serie = df[field]
    try:
        if serie.isna().all():
            return True
        texto = serie.astype(str).str.strip()
        return (texto == "").all()
    except Exception:
        return True


def collect_identity_overrides(
    df: pd.DataFrame,
    fields: Sequence[str],
    prompt_fn: Callable[[str], str],
) -> Dict[str, str]:
    """Recolecta valores fijos para campos de identidad faltantes."""

    overrides: Dict[str, str] = {}
    for field in fields:
        if not needs_identity_field_prompt(df, field):
            continue

        _field_hints = {
            "alias": "→ Alias (identificador corto del caso o sujeto; se usa en nombres de archivo): ",
            "nombre_usuario": "→ Nombre_usuario (nombre descriptivo del investigado o referencia visible en informe): ",
            "abonado": "→ Abonado (titular de la línea o SIM, si aplica): ",
        }
        try:
            response = prompt_fn(
                _field_hints.get(field, f"→ {field.capitalize()} para toda la ejecución (Enter=omitir): ")
            )
        except Exception:
            response = ""

        if not isinstance(response, str):
            response = ""

        value = response.strip()
        if value:
            overrides[field] = value

    return overrides


def execute_confirm_loop_flow(
    initial_df: pd.DataFrame,
    prompt_fn: Callable[[str], str],
    write_fn: Callable[[str], None],
    perform_remap: Callable[[pd.DataFrame], pd.DataFrame],
    perform_restart: Callable[[], Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]],
    fetch_assignments: Callable[[], Dict[str, Tuple[str, Any]]],
) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
    """Orquesta el loop de confirmación usando callbacks de remap y restart."""

    df = initial_df

    while True:
        write_fn("\n[QC] Confirmar mapeo — S=Confirmar y continuar; N=Volver a mapear; R=Remapear uno:")
        decision = resolve_confirm_loop_option(prompt_fn("→ Opción (S/N/R): "))

        if decision.action == "confirm":
            return df, fetch_assignments()

        if decision.action == "restart":
            return perform_restart()

        if decision.action == "remap":
            df = perform_remap(df)
            continue

        write_fn(decision.message or "[QC] Opción inválida. Escribí S, N o R.")


def execute_wizard_lifecycle(
    perform_initial_flow: Callable[[], pd.DataFrame],
    confirm_loop_fn: Callable[[pd.DataFrame], Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]],
) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
    """Encadena el flujo inicial y el loop de confirmación en un helper reutilizable."""

    df_temp = perform_initial_flow()
    return confirm_loop_fn(df_temp)


@dataclass
class RemapTargetSelection:
    """Resultado de interpretar la elección de canónico a remapear."""

    canonical: Optional[str]
    display_index: Optional[int]
    error: Optional[str] = None


def resolve_remap_target_selection(
    available: List[str],
    selection: str,
) -> RemapTargetSelection:
    """Convierte la selección del usuario (número/nombre) en canónico válido."""

    raw = selection.strip()
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(available):
            return RemapTargetSelection(canonical=available[idx - 1], display_index=idx)
        return RemapTargetSelection(canonical=None, display_index=None, error="[QC] Número fuera de rango.")

    lowered = raw.lower()
    for pos, canonical in enumerate(available, start=1):
        if canonical.lower() == lowered:
            return RemapTargetSelection(canonical=canonical, display_index=pos)

    return RemapTargetSelection(
        canonical=None,
        display_index=None,
        error="[QC] Canónico inválido. Usá número o nombre de la lista.",
    )


@dataclass
class ConfirmLoopDecision:
    """Describe la acción resultante del loop de confirmación."""

    action: str  # "confirm", "restart", "remap", "invalid"
    message: Optional[str] = None


def resolve_confirm_loop_option(selection: str) -> ConfirmLoopDecision:
    """Normaliza la opción ingresada en el loop S/N/R."""

    normalized = selection.strip().upper()
    if normalized in ("S", ""):
        return ConfirmLoopDecision(action="confirm")
    if normalized == "N":
        return ConfirmLoopDecision(action="restart")
    if normalized == "R":
        return ConfirmLoopDecision(action="remap")
    return ConfirmLoopDecision(action="invalid", message="[QC] Opción inválida. Escribí S, N o R.")


@dataclass
class EssentialSelectionDecision:
    """Resultado de interpretar la entrada de un esencial."""

    action: str  # "show_menu", "omit", "assign", "invalid", "duplicate"
    column: Optional[str] = None


def resolve_essential_column_selection(
    selection: str,
    columns_menu: List[str],
    used_columns: Set[str],
) -> EssentialSelectionDecision:
    """Normaliza la selección hecha para un campo esencial."""

    sel = selection.strip()
    if sel == "?":
        return EssentialSelectionDecision(action="show_menu")
    if not sel:
        return EssentialSelectionDecision(action="omit")

    try:
        idx = int(sel)
    except Exception:
        return EssentialSelectionDecision(action="invalid")

    if not (1 <= idx <= len(columns_menu)):
        return EssentialSelectionDecision(action="invalid")

    column = columns_menu[idx - 1]
    if column in used_columns:
        return EssentialSelectionDecision(action="duplicate", column=column)

    return EssentialSelectionDecision(action="assign", column=column)


@dataclass
class NonEssentialSelectionDecision:
    """Resultado de interpretar la entrada de un no esencial."""

    action: str  # "show_menu", "omit", "fixed", "assign", "invalid"
    column: Optional[str] = None
    fixed_value: Optional[str] = None


def resolve_non_essential_selection(
    selection: str,
    columns_menu: List[str],
) -> NonEssentialSelectionDecision:
    """Normaliza la selección hecha para un campo no esencial."""

    sel = selection.strip()
    if sel == "?":
        return NonEssentialSelectionDecision(action="show_menu")
    if not sel:
        return NonEssentialSelectionDecision(action="omit")
    if sel.upper().startswith("F "):
        return NonEssentialSelectionDecision(action="fixed", fixed_value=sel[2:].strip())

    try:
        idx = int(sel)
    except Exception:
        return NonEssentialSelectionDecision(action="invalid")

    if not (1 <= idx <= len(columns_menu)):
        return NonEssentialSelectionDecision(action="invalid")

    return NonEssentialSelectionDecision(action="assign", column=columns_menu[idx - 1])


@dataclass
class RemapSingleSelectionResult:
    """Describe el resultado de aplicar un remapeo unitario sobre un campo."""

    applied: bool
    show_menu: bool = False
    duplicate_column: Optional[str] = None


def apply_remap_single_selection(
    canonical: str,
    selection: str,
    columns_menu: List[str],
    is_essential: bool,
    assignments: Dict[str, Tuple[str, Any]],
    used_columns: Set[str],
) -> RemapSingleSelectionResult:
    """Normaliza la selección del usuario y actualiza asignaciones/usos."""

    sel = selection.strip()
    if sel == "?":
        return RemapSingleSelectionResult(applied=False, show_menu=True)

    if is_essential:
        if not sel:
            assignments[canonical] = ("omitido", None)
            return RemapSingleSelectionResult(applied=True)

        try:
            idx = int(sel)
        except Exception:
            assignments[canonical] = ("omitido", None)
            return RemapSingleSelectionResult(applied=True)

        if not (1 <= idx <= len(columns_menu)):
            assignments[canonical] = ("omitido", None)
            return RemapSingleSelectionResult(applied=True)

        column_name = columns_menu[idx - 1]
        if column_name in used_columns:
            return RemapSingleSelectionResult(applied=False, duplicate_column=column_name)

        previous = assignments.get(canonical)
        if previous and previous[0] == "col":
            used_columns.discard(previous[1])

        assignments[canonical] = ("col", column_name)
        used_columns.add(column_name)
        return RemapSingleSelectionResult(applied=True)

    # No esencial
    if not sel:
        assignments[canonical] = ("omitido", None)
        return RemapSingleSelectionResult(applied=True)

    if sel.upper().startswith("F "):
        assignments[canonical] = ("fijo", sel[2:].strip())
        return RemapSingleSelectionResult(applied=True)

    try:
        idx = int(sel)
    except Exception:
        assignments[canonical] = ("omitido", None)
        return RemapSingleSelectionResult(applied=True)

    if 1 <= idx <= len(columns_menu):
        assignments[canonical] = ("col", columns_menu[idx - 1])
        return RemapSingleSelectionResult(applied=True)

    assignments[canonical] = ("omitido", None)
    return RemapSingleSelectionResult(applied=True)


@dataclass
class RemapSingleFlowDecision:
    """Describe la acción UI posterior a solicitar remapeo individual."""

    show_menu: bool = False
    duplicate_column: Optional[str] = None
    prompt_message: Optional[str] = None


def resolve_remap_single_flow(
    canonical: str,
    selection: str,
    columns_menu: List[str],
    is_essential: bool,
    assignments: Dict[str, Tuple[str, Any]],
    used_columns: Set[str],
) -> RemapSingleFlowDecision:
    """Aplica la selección e indica si hace falta mostrar menú o advertencias."""

    result = apply_remap_single_selection(
        canonical=canonical,
        selection=selection,
        columns_menu=columns_menu,
        is_essential=is_essential,
        assignments=assignments,
        used_columns=used_columns,
    )

    if result.show_menu:
        prompt = (
            f"→ Elegí columna para **{canonical}** (número — '?' menú / Enter=omitir): "
            if is_essential
            else f"→ Elegí columna para {canonical} (n / 'F valor' / Enter=omitir — '?' menú): "
        )
        return RemapSingleFlowDecision(show_menu=True, prompt_message=prompt)

    if result.duplicate_column:
        return RemapSingleFlowDecision(duplicate_column=result.duplicate_column)

    return RemapSingleFlowDecision()


def confirm_remap_selection(
    prompt_fn: Callable[[str], str],
    canonical: str,
    display_index: int,
) -> bool:
    """Pide confirmación textual y retorna True solo si el usuario responde 's'."""

    response = prompt_fn(
        f"[QC] Remapearás: [{display_index}] {canonical}. ¿Confirmás? (s/N): "
    ).strip().lower()
    return response == "s"


def _detect_shared_datetime(
    assignments: Dict[str, Tuple[str, Any]],
    df: Optional["pd.DataFrame"],
    prompt_fn: Callable[[str], str],
    write_fn: Callable[[str], None],
) -> None:
    """Detecta columna fecha/hora compartida con datetime completo y ofrece separación."""

    fecha_assign = assignments.get("fecha")
    hora_assign = assignments.get("hora")

    if not (
        fecha_assign and fecha_assign[0] == "col"
        and hora_assign and hora_assign[0] == "col"
        and fecha_assign[1] == hora_assign[1]
    ):
        return

    if df is None or fecha_assign[1] not in df.columns:
        return

    col = fecha_assign[1]
    sample = df[col].dropna().head(5)
    if sample.empty:
        return

    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
    has_time = parsed.dropna().apply(
        lambda ts: ts.hour != 0 or ts.minute != 0 or ts.second != 0
    )
    sample_str = sample.astype(str)
    looks_like_datetime = sample_str.str.contains(r"[ T]\d{2}:\d{2}", regex=True)

    if not (has_time.any() or looks_like_datetime.any()):
        return

    write_fn(
        f"\n  [QC] Se detectó que 'fecha' y 'hora' usan la misma columna ('{col}') con datetime completo.\n"
        f"  Opciones:\n"
        f"    [1] Separar automáticamente: fecha = YYYY-MM-DD / hora = HH:MM:SS\n"
        f"    [2] Mantener como está\n"
        f"    [3] Remapear hora"
    )
    resp = prompt_fn("  → Opción (1/2/3, Enter=1): ").strip()
    if resp == "" or resp == "1":
        assignments["_datetime_split"] = ("fijo", col)
    elif resp == "3":
        assignments["hora"] = ("omitido", None)


class MappingWizard:
    """
    Wizard interactivo profesional para mapeo de columnas Excel → canónicas.
    
    ⚡ CÓDIGO CRÍTICO: Extraído de monolito con protocolo paranoico.
    Esta clase reemplaza _wizard_qc_mapeo() sin modificar comportamiento.
    
    Attributes:
        original_df: DataFrame original (inmutable)
        cols_menu: Lista de columnas disponibles para mapeo
        esenciales: Lista de campos canónicos esenciales
        no_esenciales: Lista de campos canónicos no esenciales
        asignadas: Dict de mapeos {canónico: (tipo, valor)}
        usadas: Set de columnas ya asignadas (evita duplicados)
        pendientes: Lista de esenciales omitidos
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        esenciales: Optional[List[str]] = None,
        no_esenciales: Optional[List[str]] = None,
        io: Optional[WizardIO] = None,
    ):
        """
        Inicializa wizard con DataFrame y configuración de campos.
        
        Args:
            df: DataFrame con columnas a mapear
            esenciales: Lista de campos canónicos esenciales (default: fecha/hora/tel/lat/long/etc)
            no_esenciales: Lista de campos canónicos no esenciales (default: alias/duracion/etc)
            io: Abstracción de entrada/salida para pruebas (default: usa `input`/`print`).
        """
        # Estado inmutable
        self.original_df = df
        self.cols_menu = list(map(str, getattr(df, "_orig_cols", list(df.columns))))
        
        # Configuración de campos
        self.esenciales = esenciales if esenciales is not None else self._default_esenciales()
        self.no_esenciales = no_esenciales if no_esenciales is not None else self._default_no_esenciales()
        self.etiquetas_mapeo = self._build_labels()
        self.tipar_numericos = {"lat", "long", "azimut", "duracion"}
        self.io = io or WizardIO()
        
        # Estado mutable (tracking de mapeos)
        self.asignadas: Dict[str, Tuple[str, Any]] = {}  # canónico -> (tipo, valor)
        self.usadas: Set[str] = set()  # columnas ya tomadas
        self.pendientes: List[str] = []  # esenciales omitidos

    # =========================================================================
    # === IO HELPERS ===
    # =========================================================================

    def _prompt(self, message: str) -> str:
        """Delega prompt al objeto WizardIO."""
        return self.io.prompt(message)

    def _write(self, message: str) -> None:
        """Delega escritura al objeto WizardIO."""
        self.io.write(message)
    
    # =========================================================================
    # === CONFIGURACIÓN Y DEFAULTS ===
    # =========================================================================
    
    @staticmethod
    def _default_esenciales() -> List[str]:
        """Retorna lista default de campos esenciales."""
        return ["fecha", "hora", "tel", "imei", "interaccion", "contacto", 
                "lat", "long", "azimut", "antena"]
    
    @staticmethod
    def _default_no_esenciales() -> List[str]:
        """Retorna lista default de campos no esenciales."""
        return ["alias", "nombre_usuario", "abonado", "celda", "direccion", 
                "imei", "imsi", "duracion", "contacto", "interaccion"]
    
    @staticmethod
    def _build_labels() -> Dict[str, str]:
        """Construye diccionario de etiquetas amigables para mapeo."""
        return {
            "tel": "Tel u Origen",
            "contacto": "Contacto o Destino",
            "interaccion": "Interacción o Tipo"
        }
    
    # =========================================================================
    # === PUBLIC API - PUNTO DE ENTRADA ===
    # =========================================================================
    
    def run(self) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
        """
        Ejecuta wizard completo de mapeo interactivo.
        
        Flujo:
        1. Mapear campos esenciales (input usuario)
        2. Mapear campos no esenciales (input usuario)
        3. Mostrar resumen
        4. Preguntar identidad (alias/nombre_usuario/abonado)
        5. Mostrar vista previa
        6. Remapeo rápido opcional
        7. Aplicar mapeo al DataFrame
        8. Confirmación (S/N/R loop)
        
        Returns:
            Tuple[DataFrame mapeado, Dict asignaciones]
        """
        return execute_wizard_lifecycle(
            perform_initial_flow=self._perform_initial_mapping_flow,
            confirm_loop_fn=self._confirm_loop,
        )

    def _perform_initial_mapping_flow(self) -> pd.DataFrame:
        """Ejecuta las fases iniciales (mapeo, identidad, preview y remap rápido)."""

        self._map_essentials()
        self._map_non_essentials()
        self._show_summary()

        df_temp = self._apply_mapping()
        df_temp = self._handle_identity_fields(df_temp)
        self._show_preview(df_temp)
        df_temp = self._quick_remap(df_temp)
        return df_temp
    
    # =========================================================================
    # === UI LAYER - INTERACCIÓN CON USUARIO ===
    # =========================================================================
    
    def _menu_horizontal(self, cols: List[str], per_line: int = 6) -> str:
        """Muestra menú de columnas en formato horizontal delegando a format_columns_menu."""
        return format_columns_menu(cols, per_line)
    
    def _show_summary(self) -> None:
        """Muestra resumen visual de todos los mapeos realizados."""
        self._write("\n[QC] === Resumen de mapeo ===")
        for line in format_mapping_summary(self.asignadas):
            self._write(line)

        for warning in build_pending_warning_lines(self.pendientes):
            self._write(warning)
    
    def _show_preview(self, df: pd.DataFrame) -> None:
        """Muestra vista previa de las primeras 3 filas del DataFrame mapeado."""
        preview_text = build_preview_table(df, self.esenciales + self.no_esenciales)
        if preview_text is None:
            return
        self._write("\n[QC] Vista previa (3 filas):")
        self._write(preview_text)
    
    # =========================================================================
    # === LOGIC LAYER - PROCESAMIENTO DE MAPEOS ===
    # =========================================================================
    
    def _map_essentials(self) -> None:
        """
        Mapea todos los campos esenciales mediante interacción con usuario.
        
        Muestra menú de columnas una sola vez y delega el loop completo
        a un helper puro que devuelve asignaciones/pendientes/usos.
        """
        for line in build_mapping_intro_lines(
            title="ESENCIALES",
            columns_menu=self.cols_menu,
            instructions=None,
            show_header_once=True,
        ):
            self._write(line)

        asignadas, usadas, pendientes = collect_essential_mapping_assignments(
            canonicals=self.esenciales,
            columns_menu=self.cols_menu,
            prompt_fn=self._prompt,
            write_fn=self._write,
            etiquetas=self.etiquetas_mapeo,
            initial_assignments=self.asignadas,
            initial_used_columns=self.usadas,
            initial_pendings=self.pendientes,
            per_line=6,
            df=self.original_df,
        )
        self.asignadas = asignadas
        self.usadas = usadas
        self.pendientes = pendientes
    
    def _map_non_essentials(self) -> None:
        """
        Mapea todos los campos no esenciales mediante interacción con usuario.
        
        Muestra menú de columnas y delega el loop al helper puro de
        no esenciales para obtener asignaciones actualizadas.
        """
        for line in build_mapping_intro_lines(
            title="NO ESENCIALES",
            columns_menu=self.cols_menu,
            instructions="  Podés: elegir número, escribir 'F <valor fijo>' o Enter=omitir.",
            show_columns=False,
        ):
            self._write(line)

        self.asignadas = collect_non_essential_mapping_assignments(
            canonicals=self.no_esenciales,
            columns_menu=self.cols_menu,
            prompt_fn=self._prompt,
            write_fn=self._write,
            etiquetas=self.etiquetas_mapeo,
            initial_assignments=self.asignadas,
            per_line=6,
            df=self.original_df,
        )
    
    def _apply_mapping(self) -> pd.DataFrame:
        """
        Aplica todos los mapeos al DataFrame y retorna copia modificada.
        
        Operaciones:
        1. Rename columnas según asignaciones "col"
        2. Asignar valores fijos según asignaciones "fijo"
        3. Eliminar columnas duplicadas
        4. Tipar campos numéricos (lat/long/azimut/duracion)
        5. Fallback antena/siteid
        
        Returns:
            DataFrame con mapeo aplicado
        """
        return apply_wizard_assignments(
            self.original_df,
            self.asignadas,
            numeric_fields=self.tipar_numericos,
            writer=self._write,
        )
    
    def _handle_identity_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pregunta por campos de identidad (alias/nombre_usuario/abonado) si faltan o están vacíos.
        
        Args:
            df: DataFrame con mapeo aplicado
        
        Returns:
            DataFrame con campos de identidad agregados si usuario los proveyó
        """
        overrides = collect_identity_overrides(
            df=df,
            fields=("alias", "nombre_usuario", "abonado"),
            prompt_fn=self._prompt,
        )

        for field, value in overrides.items():
            df[field] = value
        return df
    
    def _quick_remap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ofrece remapeo rápido de campos recomendados omitidos (ej. duracion).
        
        Args:
            df: DataFrame con mapeo aplicado
        
        Returns:
            DataFrame potencialmente con campos adicionales mapeados
        """
        recomendadas = ["duracion"]
        falt = [c for c in recomendadas if c not in df.columns]
        if falt:
            self._write("\n[QC] Aviso: omitiste asignar -> " + ", ".join(falt))
            resp = self._prompt("¿Querés mapearlas ahora? (s/N): ").strip().lower()
            if resp == "s":
                operations = collect_quick_remap_operations(
                    prompt_fn=self._prompt,
                    write_fn=self._write,
                    columns_menu=self.cols_menu,
                    canonicals=list(falt),
                )
                df = perform_quick_remap_batch(df, self.cols_menu, operations)
        return df
    
    # =========================================================================
    # === CONFIRMATION LAYER - LOOP S/N/R ===
    # =========================================================================
    
    def _confirm_loop(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
        """Loop de confirmación: delega en execute_confirm_loop_flow."""

        def _perform_remap(current_df: pd.DataFrame) -> pd.DataFrame:
            """Ejecuta remapeo de un campo en el loop de confirmación y retorna DataFrame actualizado."""
            self._remap_single_field()
            updated = self._apply_mapping()
            updated = self._handle_identity_fields(updated)
            self._show_summary()
            return updated

        def _perform_restart() -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
            """Reinicia el wizard desde cero creando nueva instancia de MappingWizard."""
            self._write("[QC] Reiniciando mapeo completo...")
            new_wizard = MappingWizard(
                self.original_df,
                self.esenciales,
                self.no_esenciales,
                io=self.io,
            )
            return new_wizard.run()

        def _fetch_assignments() -> Dict[str, Tuple[str, Any]]:
            """Retorna las asignaciones actuales de mapeo."""
            return self.asignadas

        return execute_confirm_loop_flow(
            initial_df=df,
            prompt_fn=self._prompt,
            write_fn=self._write,
            perform_remap=_perform_remap,
            perform_restart=_perform_restart,
            fetch_assignments=_fetch_assignments,
        )
    
    def _remap_single_field(self) -> None:
        """
        Remapea un solo campo canónico (opción R del loop de confirmación).
        
        Flujo:
        1. Mostrar menú de canónicos disponibles
        2. Usuario elige por número o nombre
        3. Confirmar selección
        4. Reasignar columna/fijo/omitir
        5. Actualizar self.asignadas
        """
        todos = build_remap_menu_order(self.esenciales, self.no_esenciales)
        
        self._write("\n[QC] ¿Qué canónico querés remapear?")
        self._write("  " + "  |  ".join(f"[{i+1}] {c}" for i, c in enumerate(todos)))
        
        target = self._prompt("→ Escribí **número o nombre** (ej. 4 o fecha): ").strip()
        selection = resolve_remap_target_selection(todos, target)
        if selection.error:
            self._write(selection.error)
            return

        can = selection.canonical
        if not can:
            return
        display_index = selection.display_index or (todos.index(can) + 1)
        
        # Confirmación explícita
        if not confirm_remap_selection(self._prompt, can, display_index):
            return
        
        # Mostrar menú de columnas
        self._write(self._menu_horizontal(self.cols_menu, per_line=6))
        
        is_essential = can in self.esenciales
        prompt_msg = (
            f"→ Elegí columna para **{can}** (número — '?' menú / Enter=omitir): "
            if is_essential
            else f"→ Elegí columna para {can} (n / 'F valor' / Enter=omitir — '?' menú): "
        )

        while True:
            sel = self._prompt(prompt_msg).strip()
            flow = resolve_remap_single_flow(
                canonical=can,
                selection=sel,
                columns_menu=self.cols_menu,
                is_essential=is_essential,
                assignments=self.asignadas,
                used_columns=self.usadas,
            )

            if flow.show_menu:
                self._write(self._menu_horizontal(self.cols_menu, per_line=6))
                prompt_msg = flow.prompt_message or prompt_msg
                continue

            if flow.duplicate_column:
                self._write(f"  [QC] '{flow.duplicate_column}' ya está usada por otro esencial.")
                prompt_msg = (
                    f"→ Elegí columna para **{can}** (número — '?' menú / Enter=omitir): "
                    if is_essential
                    else f"→ Elegí columna para {can} (n / 'F valor' / Enter=omitir — '?' menú): "
                )
                continue

            break


# =========================================================================
# === WRAPPER FUNCIÓN PARA COMPATIBILIDAD COMPLETA ===
# =========================================================================

def wizard_qc_mapeo(
    df: pd.DataFrame,
    esenciales: Optional[List[str]] = None,
    no_esenciales: Optional[List[str]] = None,
    io: Optional[WizardIO] = None,
) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
    """
    Wrapper función para compatibilidad 100% con _wizard_qc_mapeo() original.
    
    Mantiene firma exacta y comportamiento idéntico. Este wrapper permite
    reemplazar llamadas directas sin modificar código cliente.
    
    Args:
        df: DataFrame con columnas a mapear
        esenciales: Lista de campos canónicos esenciales (opcional)
        no_esenciales: Lista de campos canónicos no esenciales (opcional)
        io: Implementación personalizada de IO (opcional)
    
    Returns:
        Tuple[DataFrame mapeado, Dict asignaciones]
    
    Ejemplo:
        >>> df, asignaciones = wizard_qc_mapeo(df, esenciales=["fecha", "tel"])
    """
    wizard = MappingWizard(df, esenciales, no_esenciales, io=io)
    return wizard.run()
