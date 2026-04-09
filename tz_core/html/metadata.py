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
from typing import Optional

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


def build_identification_rows(df: pd.DataFrame, config: Optional[dict] = None) -> str:
    """Construye la tabla de identificación (número, IMEI, alias, usuario, abonado, IMSI).

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

    tel_val = normalize_msisdn(first_nonempty_in(df, tel_cols)) or first_nonempty_in(df, tel_cols)
    alias_val = first_nonempty_in(df, alias_cols)
    user_val = first_nonempty_in(df, user_cols)
    abon_val = first_nonempty_in(df, abon_cols)
    imei_raw = first_nonempty_in(df, imei_cols)
    imsi_raw = first_nonempty_in(df, imsi_cols)

    def _coerce_float_str(value):
        """Convierte valor a float y retorna string formateado o el valor original si falla."""
        if value is None:
            return None
        try:
            f_val = float(str(value))
            if f_val.is_integer():
                return str(int(f_val))
            return str(value)
        except Exception:
            return str(value)

    imei_val = normalize_imei(imei_raw) or (_coerce_float_str(imei_raw) if imei_raw is not None else None)
    imsi_val = _coerce_float_str(imsi_raw) if imsi_raw is not None else None

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

    tel_n = nunique_in(df, tel_cols)
    ali_n = nunique_in(df, alias_cols)
    usr_n = nunique_in(df, user_cols)
    abo_n = nunique_in(df, abon_cols)
    ime_n = nunique_in(df, imei_cols)
    imsi_n = nunique_in(df, imsi_cols)

    def _fmt_uni(val, count):
        """Formatea valor único para display: retorna 'múltiples' si count>1, valor si existe, None sino."""
        if count > 1:
            return f"múltiples ({count})"
        if val:
            return val
        return None

    tel_disp = _fmt_uni(tel_val, tel_n)
    alias_disp = _fmt_uni(alias_val, ali_n)
    user_disp = _fmt_uni(user_val, usr_n)
    abon_disp = _fmt_uni(abon_val, abo_n)
    imei_disp = _fmt_uni(imei_val, ime_n)
    imsi_disp = _fmt_uni(imsi_val, imsi_n)

    tel_list, tel_more = unique_values_in(df, tel_cols, max_items=8)
    tel_list = [normalize_msisdn(x) for x in tel_list if normalize_msisdn(x)]
    tel_n = len(set(tel_list)) if tel_list else tel_n
    tel_disp = _fmt_uni(tel_val, tel_n)
    tel_more = max(0, tel_n - len(tel_list))
    ali_list, ali_more = unique_values_in(df, alias_cols, max_items=8)
    usr_list, usr_more = unique_values_in(df, user_cols, max_items=8)
    abo_list, abo_more = unique_values_in(df, abon_cols, max_items=8)
    imei_list, imei_more = unique_values_in(df, imei_cols, max_items=20)
    imsi_list, imsi_more = unique_values_in(df, imsi_cols, max_items=20)

    imei_list = [normalize_imei(fmt_imei_item(x)) for x in imei_list]
    imei_list = [x for x in imei_list if x and is_valid_imei(x)]
    if not imei_list:
        imei_disp = None
        imei_more = 0

    cleaned_imsis = []
    for item in imsi_list:
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
                cleaned_imsis.append(s)
        except Exception:
            continue
    imsi_list = cleaned_imsis
    if not imsi_list:
        imsi_disp = None
        imsi_more = 0

    ident_rows = ""
    if tel_list and imsi_list:
        tel_imsi = []
        for tel in tel_list:
            imsis = set()
            for _, row in df.iterrows():
                row_tel = normalize_msisdn(row.get("tel", "")) or str(row.get("tel", "")).strip()
                if row_tel == str(tel):
                    imsi_value = row.get("imsi", "")
                    if imsi_value:
                        imsis.add(str(imsi_value).strip())
            if imsis:
                tel_imsi.append(f"{tel} — IMSI: {', '.join(imsis)}")
            else:
                tel_imsi.append(str(tel))
        ident_rows += row_html("Número telefónico", None, len(tel_imsi), tel_imsi, 0, mono=True)
    else:
        ident_rows += row_html("Número telefónico", tel_disp, tel_n, tel_list, tel_more, mono=True)

    ident_rows += row_html("IMEI", imei_disp, ime_n, imei_list, imei_more, mono=True)
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
