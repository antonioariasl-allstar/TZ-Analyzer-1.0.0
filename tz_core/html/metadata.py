"""
Módulo de metadatos y datos de identificación del reporte HTML.

Módulo de generación de metadata HTML.
Contiene funciones para generar secciones de metadatos, identificación (IMEI/teléfono),
e inyección de metadatos técnicos post-escritura en el archivo HTML.

Nota arquitectónica: Este módulo mezcla dos responsabilidades:
- Generación: generate_metadata_section, build_identification_rows
- Post-escritura: inject_technical_metadata, _build_meta_block, _inject_block
"""
import re
from pathlib import Path
from typing import List, Optional

import pandas as pd

from tz_core.html_helpers import (
    fmt_datetime, first_nonempty_in, unique_values_in,
    fmt_imei_item, row_html, nunique_in, luhn_check, is_valid_imei
)
from tz_core.runtime_utils import collect_env_snapshot
from tz_core.bitacora_normalization import normalize_msisdn, normalize_imei
from tz_core.logging_utils import log


def generate_metadata_section(nombre_bitacora: str | None, hoja: str | None, rango_str: str, ident_rows: str) -> str:
    """
    Genera la sección de metadatos del HTML con tabla de información clave.
    
    Extrae la sección HTML-METADATOS que incluye:
    - <section class="meta"> container
    - Título "Metadatos" con estilo h2
    - Tabla con información de bitácora, hoja, periodo
    - Filas de identificación dinámicas (ident_rows)
    
    Args:
        nombre_bitacora (str | None): Nombre del archivo de bitácora analizado
        hoja (str | None): Nombre de la hoja específica procesada
        rango_str (str): String del rango temporal analizado (ej: "2024-01-01 a 2024-12-31")
        ident_rows (str): HTML de filas adicionales de identificación (IMEI, etc.)
        
    Returns:
        str: HTML completo de la sección metadatos
        
    Example:
        >>> metadata = generate_metadata_section(
        ...     "bitacora_test.xlsx", 
        ...     "Datos2024", 
        ...     "2024-01-01 a 2024-03-31",
        ...     "<tr><td><b>IMEI:</b></td><td>123456789</td></tr>"
        ... )
        >>> print("Metadatos" in metadata)
        True
    """
    return f"""  <section class="meta">
    <h2>Metadatos</h2>
    <table>
        <tr><td><b>Bitácora telefónica:</b></td><td class="mono">{nombre_bitacora or '—'}</td></tr>
        <tr><td><b>Hoja analizada:</b></td><td class="mono">{hoja or '—'}</td></tr>
        <tr><td><b>Periodo analizado:</b></td><td class="mono">{rango_str}</td></tr>
        {ident_rows}
    </table>

  </section>"""


def _calculate_imei_check_digit(base14: str) -> Optional[str]:
    """Calcula el dígito verificador Luhn para una base de 14 dígitos de IMEI.

    Prueba los dígitos finales 0-9 sobre ``base14`` usando luhn_check() y
    retorna, como texto, el primero que produce un IMEI de 15 dígitos válido.
    Retorna None si la entrada no tiene exactamente 14 dígitos o si ningún
    dígito produce un resultado válido.
    """
    if not (isinstance(base14, str) and len(base14) == 14 and base14.isdigit()):
        return None
    for digit in "0123456789":
        if luhn_check(base14 + digit):
            return digit
    return None


def _format_imei_entry(value: str) -> str:
    """Formatea un IMEI único normalizado para su presentación en Metadatos.

    Conserva siempre el valor reportado por la fuente (nunca se denomina
    "IMEI real" ni se oculta). Cuando el último dígito reportado tiene
    evidencia razonable de ser un dígito de reserva sin calcular (15 dígitos
    terminados en 0, o 14 dígitos sin dígito verificador), se muestra junto al
    valor reportado el IMEI reconstruido mediante Luhn, manteniendo
    trazabilidad entre ambos.
    """
    length = len(value)

    if length == 15:
        if is_valid_imei(value):
            return value
        if value.endswith("0"):
            check_digit = _calculate_imei_check_digit(value[:14])
            if check_digit is not None:
                reconstructed = value[:14] + check_digit
                return (
                    f"IMEI reportado: {value}<br>"
                    f"IMEI reconstruido (Luhn): {reconstructed}"
                )
        return f"{value} — inconsistencia de validación Luhn"

    if length == 14:
        check_digit = _calculate_imei_check_digit(value)
        if check_digit is not None:
            reconstructed = value + check_digit
            return (
                f"IMEI reportado: {value}<br>"
                f"IMEI reconstruido (Luhn): {reconstructed}"
            )
        return f"{value} — inconsistencia de validación Luhn"

    if length == 16:
        return f"{value} — posible IMEISV"

    return f"{value} — longitud no estándar"


def build_identification_rows(df: pd.DataFrame, config: Optional[dict] = None) -> str:
    """Construye la tabla de identificación (número, IMEI, alias, usuario, abonado, IMSI).

    Número telefónico, IMEI e IMSI se construyen como filas independientes: ninguna
    depende de las otras, y ninguna desaparece por tener un único valor reportado.

    La lógica se extrajo desde generar_informe_html() para mantener una sola fuente de verdad.
    """
    if df is None or df.empty:
        return ""

    tel_cols = ["tel","telefono","numero","msisdn","a_number","origen","from","callingnumber","num"]
    alias_cols = ["alias","alias_usuario","apodo"]
    user_cols = ["usuario","nombre_usuario","suscriptor","user_name"]
    abon_cols = ["abonado","titular","owner","subscriber"]
    imei_cols = ["imei","imei1","imei_1"]
    imsi_cols = ["imsi","imsi1","imsi_1","imsi_origen"]

    alias_val = first_nonempty_in(df, alias_cols)
    user_val = first_nonempty_in(df, user_cols)
    abon_val = first_nonempty_in(df, abon_cols)

    def _ask_if_missing(label_visible: str, current_value, col_name: str):
        """Pregunta al usuario si falta un dato y retorna el valor ingresado o actual."""
        try:
            val_actual = (str(current_value).strip() if current_value is not None else "")
        except Exception:
            val_actual = ""
        if val_actual:
            return current_value
        try:
            entrada = ""
        except Exception:
            entrada = ""
        if entrada:
            try:
                df[col_name] = entrada
            except Exception:
                pass
            return entrada
        return current_value

    alias_val = _ask_if_missing("alias", alias_val, "alias")
    user_val = _ask_if_missing("nombre_usuario", user_val, "usuario")
    abon_val = _ask_if_missing("abonado", abon_val, "abonado")

    ali_n = nunique_in(df, alias_cols)
    usr_n = nunique_in(df, user_cols)
    abo_n = nunique_in(df, abon_cols)

    def _fmt_uni(val, count):
        """Formatea valor único para display: retorna 'múltiples' si count>1, valor si existe, None sino."""
        if count > 1:
            return f"múltiples ({count})"
        if val:
            return val
        return None

    alias_disp = _fmt_uni(alias_val, ali_n)
    user_disp = _fmt_uni(user_val, usr_n)
    abon_disp = _fmt_uni(abon_val, abo_n)

    ali_list, ali_more = unique_values_in(df, alias_cols, max_items=8)
    usr_list, usr_more = unique_values_in(df, user_cols, max_items=8)
    abo_list, abo_more = unique_values_in(df, abon_cols, max_items=8)

    def _dedup_preserve_order(values):
        """Deduplica una lista de valores preservando el orden de primera aparición."""
        seen = set()
        out = []
        for v in values:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    def _row_single_or_list(label: str, values: List[str], extra: int, fallback: Optional[str]) -> str:
        """Construye una fila con un valor único, una lista de valores, o un fallback si no hay ninguno.

        No depende de otras columnas y nunca desaparece por tener un solo valor
        reportado, a diferencia de pasar directamente por row_html() con n<=1.
        """
        n = len(values)
        if n == 0:
            if fallback is None:
                return row_html(label, None, 0, [], 0, mono=True)
            return row_html(label, fallback, 1, [], 0, mono=True)
        if n == 1:
            return row_html(label, values[0], 1, [], 0, mono=True)
        return row_html(label, None, n, values, extra, mono=True)

    # --- Número telefónico: fila independiente, sin fusionar IMSI en su texto ---
    tel_raw, tel_extra = unique_values_in(df, tel_cols, max_items=8)
    tel_values = _dedup_preserve_order(
        [normalize_msisdn(x) for x in tel_raw if normalize_msisdn(x)]
    )
    tel_row = _row_single_or_list("Número telefónico", tel_values, tel_extra, fallback=None)

    # --- IMEI: fila independiente. El valor reportado por la fuente se conserva
    #     siempre; el tratamiento por longitud/Luhn se delega a _format_imei_entry. ---
    imei_raw, imei_extra = unique_values_in(df, imei_cols, max_items=20)
    imei_candidates = []
    for x in imei_raw:
        v = normalize_imei(fmt_imei_item(x))
        if not v:
            # normalize_imei ya descarta vacíos/NaN/None/nan/sufijo .0 y placeholders
            # no numéricos (p.ej. "S/I", "N/A"): quedan como None y se excluyen aquí.
            continue
        if set(v) == {"0"}:
            # Placeholder de "sin valor" (todo ceros), no un IMEI reportado real.
            continue
        imei_candidates.append(v)
    imei_candidates = _dedup_preserve_order(imei_candidates)

    imei_values = [_format_imei_entry(v) for v in imei_candidates]
    imei_row = _row_single_or_list("IMEI", imei_values, imei_extra, fallback="IMEI no disponible")

    # --- IMSI: fila independiente; mismo criterio de limpieza ya usado antes en
    #     este módulo (14-16 dígitos), sin aplicar Luhn (no aplica a IMSI). ---
    imsi_raw, imsi_extra = unique_values_in(df, imsi_cols, max_items=20)
    imsi_candidates = []
    for item in imsi_raw:
        try:
            s = str(item).strip()
            try:
                f = float(s)
                if f.is_integer():
                    s = str(int(f))
            except Exception:
                pass
            s = re.sub(r"\D", "", s)
            if 14 <= len(s) <= 16:
                imsi_candidates.append(s)
        except Exception:
            continue
    imsi_candidates = _dedup_preserve_order(imsi_candidates)
    imsi_row = _row_single_or_list("IMSI", imsi_candidates, imsi_extra, fallback="IMSI no disponible")

    ident_rows = ""
    ident_rows += tel_row
    ident_rows += imei_row
    ident_rows += imsi_row
    ident_rows += row_html("Alias", alias_disp, ali_n, ali_list, ali_more, mono=False)
    ident_rows += row_html("Usuario", user_disp, usr_n, usr_list, usr_more, mono=False)
    ident_rows += row_html("Abonado", abon_disp, abo_n, abo_list, abo_more, mono=False)

    return ident_rows


def _build_meta_block(snapshot: dict[str, str], modo: str, mostrar_versiones: bool) -> str:
    """Construye el bloque HTML con la información técnica configurable."""
    etiquetas = [
        ("Sistema operativo", snapshot.get("so")),
        ("Python", snapshot.get("python")),
        ("Zona horaria", snapshot.get("tz")),
        ("Fecha/hora", snapshot.get("fecha_hora")),
    ]

    if mostrar_versiones:
        etiquetas.append(("TZ Analyzer", snapshot.get("tz_analysis")))
        etiquetas.append(("Versión config", snapshot.get("version_config")))

    if modo == "ampliado":
        etiquetas.append(("Hostname", snapshot.get("hostname")))
        etiquetas.append(("Usuario", snapshot.get("usuario")))

    filas = [
        f'<div class="meta-row"><span class="lbl">{label}:</span> '
        f'<span class="mono">{value}</span></div>'
        for label, value in etiquetas
        if value
    ]

    if not filas:
        return ""

    contenido = "".join(filas)
    return (
        '<div class="metainfo meta-tecnica" '
        'style="margin:8px 0 12px 0; padding:10px; border:1px dashed #d1d5db; '
        'background:#f9fafb; font-size:12px;">'
        f'<div class="title" style="font-weight:600;margin-bottom:4px;">Metadatos técnicos ({modo})</div>'
        f"{contenido}"
        "</div>"
    )


def _inject_block(html: str, block: str) -> tuple[str, bool]:
    """Inyecta un bloque HTML antes de la primera sección con 'meta' en su etiqueta."""
    lower_html = html.lower()
    idx = lower_html.find("<section")
    while idx != -1:
        close = html.find(">", idx)
        if close == -1:
            break
        window = lower_html[idx: min(len(lower_html), idx + 200)]
        if "meta" in window:
            injected_html = html[:close+1] + "\n" + block + html[close+1:]
            return injected_html, True
        idx = lower_html.find("<section", close)

    body_idx = lower_html.find("<body")
    if body_idx != -1:
        body_close = html.find(">", body_idx)
        if body_close != -1:
            injected_html = html[:body_close+1] + "\n" + block + html[body_close+1:]
            return injected_html, True

    return html + block, bool(block)


def inject_technical_metadata(html_path: str, config: dict | None = None) -> bool:
    """Inyecta metadatos técnicos en el informe HTML si la configuración lo habilita."""
    meta_cfg = ((config or {}).get("html") or {}).get("metadatos_tecnicos") or {}
    if not meta_cfg.get("enabled"):
        return False

    path = Path(html_path or "")
    if not path.is_file():
        return False

    try:
        html = path.read_text(encoding="utf-8")
    except Exception:
        return False

    if "metainfo meta-tecnica" in html:
        return False

    snapshot = collect_env_snapshot(config)
    modo = (meta_cfg.get("modo") or "minimo").lower()
    block = _build_meta_block(snapshot, modo, bool(meta_cfg.get("mostrar_versiones", False)))
    if not block:
        return False

    new_html, injected = _inject_block(html, block)
    if not injected:
        return False

    try:
        path.write_text(new_html, encoding="utf-8")
        log("[meta] Metadatos técnicos inyectados (según config).")
    except Exception:
        return False

    return True
