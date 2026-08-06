"""
TZ-Analyzer — Interacciones Builder

Genera la sección HTML de interacciones recientes en el informe de bitácora.
Incluye tablas de detalle por día, mapas de calor de antenas, y cálculos
de distancia/desplazamiento entre activaciones.

Architecture: TZ-Analyzer v1.0.0 — tz_core package
"""

from __future__ import annotations

import json
from html import escape as _html_escape
from math import radians, sin, cos, sqrt, atan2
from typing import Any, Callable, Dict, Optional
from string import Template

import numpy as np
import pandas as pd

from tz_core.dataframe_utils import pick_first_existing_column
from tz_core.bitacora_normalization import (
    sanitize_latlon,
    parse_duration_seconds,
    clasificar_confiabilidad_duracion,
    DuracionEstado,
    es_valor_significativo,
    normalize_imei,
)
from tz_core.html_helpers import fmt_imei_item
from tz_core.time_utils import _to_datetime_series, _fmt_hms

# Nota HITO 2A — texto idéntico al de tz_core.html.antennas; se duplica aquí
# (en vez de importarlo) para no crear un ciclo con tz_core.html.__init__,
# que importa .assembler y este módulo a su vez importa interacciones_builder.
_NOTA_SITIOS_INFERIDOS = (
    "Uno o más identificadores de sitio fueron generados por TZ Analyzer a "
    "partir de coordenadas normalizadas. No corresponden necesariamente a la "
    "nomenclatura oficial del operador."
)
_BADGE_SITIO_INFERIDO = (
    ' <span class="tz-badge-inferido" '
    'style="font-size:0.75em;color:#888;font-style:italic;margin-left:6px;" '
    'title="Identificador generado por TZ Analyzer a partir de coordenadas normalizadas">'
    "Inferido por coordenadas</span>"
)


def _valor_predominante(df: pd.DataFrame, columna: Optional[str]) -> Optional[str]:
    """Devuelve el valor más frecuente y significativo de ``columna``, o None."""
    if not columna or columna not in df.columns:
        return None
    serie = df[columna]
    mask = serie.map(es_valor_significativo)
    if not bool(mask.any()):
        return None
    valores = serie.loc[mask].astype(str).str.strip()
    try:
        return str(valores.value_counts().idxmax())
    except Exception:
        return str(valores.iloc[0])


def _construir_sujeto_analizado_html(
    df: pd.DataFrame,
    col_tel: Optional[str],
    col_imei: Optional[str],
) -> str:
    """Construye la línea "Número/IMEI analizado" mostrada antes del selector de fecha.

    HITO 4: identifica el teléfono o IMEI de la bitácora analizada sin
    repetirlo como columna en cada fila. Prioriza tel (modo por defecto del
    esquema); si además hay IMEI, lo muestra como línea secundaria breve.
    """
    tel_val = _valor_predominante(df, col_tel)
    imei_val = _valor_predominante(df, col_imei)
    if imei_val:
        # Reutiliza el mismo saneamiento que metadata.py (build_identification_rows)
        # para que el IMEI se muestre igual en Metadatos y aquí (sin sufijo ".0").
        imei_val = normalize_imei(fmt_imei_item(imei_val)) or imei_val

    if tel_val:
        html = (
            '<p class="sujeto-analizado">'
            f"<strong>Número analizado:</strong> {_html_escape(tel_val)}</p>"
        )
        if imei_val:
            html += (
                '<p class="sujeto-analizado-secundario" style="font-size:0.85em;color:#666;margin-top:-6px;">'
                f"IMEI: {_html_escape(imei_val)}</p>"
            )
        return html
    if imei_val:
        return (
            '<p class="sujeto-analizado">'
            f"<strong>IMEI analizado:</strong> {_html_escape(imei_val)}</p>"
        )
    return (
        '<p class="sujeto-analizado">'
        "<strong>Identificador analizado:</strong> no disponible</p>"
    )


def construir_seccion_interacciones(
    df: pd.DataFrame,
    dias: int = 3,
    columnas_config: Optional[Dict[str, Any]] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
    logger: Optional[Callable[[str], None]] = None,
    duracion_estado: Optional[DuracionEstado] = None,
) -> str:
    """Construye la sección HTML de interacciones recientes (usa lógica original)."""

    log = logger or (lambda msg: None)
    columnas_config = columnas_config or {}
    cfg = config or {}

    col_contacto = pick_first_existing_column(
        df,
        [
            columnas_config.get("contacto"),
            columnas_config.get("tel_contacto"),
            columnas_config.get("destino"),
            columnas_config.get("b_party"),
            "contacto",
            "tel_contacto",
            "destino",
            "b_party",
            "to",
            "callee",
        ],
    ) or "tel_contacto"

    col_duracion = pick_first_existing_column(
        df,
        [
            columnas_config.get("duracion"),
            "duracion",
            "duration",
            "dur",
            "duracion_seg",
            "duracion_llamada",
        ],
    )
    col_lat = pick_first_existing_column(df, [columnas_config.get("lat"), "lat", "latitude", "latitud"])
    col_long = pick_first_existing_column(df, [columnas_config.get("long"), columnas_config.get("lon"), "long", "lon", "longitud"])
    # HITO 2A: antena_analitica prioriza la antena real cuando es
    # significativa, y cae al identificador SITIO_<lat>_<long> inferido por
    # coordenadas cuando no la hay (ver tz_core.site_inference). Se usa como
    # identificador único para agrupaciones, tabla y marcadores de heatmap.
    col_antena = "antena_analitica" if "antena_analitica" in df.columns else pick_first_existing_column(
        df,
        [
            columnas_config.get("antena"),
            "antena",
            "celda",
            "cellname",
            "cell",
            "site",
        ],
    )
    hay_sitio_inferido = bool(
        "sitio_inferido" in df.columns
        and df["sitio_inferido"].fillna(False).astype(bool).any()
    )
    col_azimut = pick_first_existing_column(df, [columnas_config.get("azimut"), "azimut", "azimuth", "azi", "angulo"])
    col_tel = pick_first_existing_column(df, [columnas_config.get("tel"), "tel"])
    col_imei = pick_first_existing_column(df, [columnas_config.get("imei"), "imei"])
    col_tipo = pick_first_existing_column(
        df,
        [
            columnas_config.get("tipo"),
            "tipo",
            "interaccion",
            "tipo_interaccion",
            "interaction",
            "tipo_llamada",
        ],
    )
    col_celda = pick_first_existing_column(df, [columnas_config.get("celda"), "celda", "cod_celda_inicial", "cell_id", "cgi"])
    col_hora = pick_first_existing_column(df, [columnas_config.get("hora"), "hora", "hora_inicial", "time", "timestamp"])

    bbox_cfg = None
    try:
        bbox_cfg = cfg.get("geografia", {}).get("sv_bbox", None)
    except Exception:
        bbox_cfg = None

    if not (isinstance(bbox_cfg, dict) and all(k in bbox_cfg for k in ("lat_min", "lat_max", "lon_min", "lon_max"))):
        bbox_cfg = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

    has_latlon = pd.Series(False, index=df.index)
    if col_lat and col_long:
        try:
            df = sanitize_latlon(df, lat_col=col_lat, lon_col=col_long, bbox=bbox_cfg)
            has_latlon = df[col_lat].notna() & df[col_long].notna()
        except Exception:
            pass

    def _es_valida_latlon_row(row):
        """Valida si la fila tiene coordenadas lat/lon válidas consultando has_latlon por índice."""
        try:
            return bool(has_latlon.loc[row.name])
        except Exception:
            return False

    if df is None or df.empty:
        return (
            '<section id="interacciones-recientes">'
            "<h2>Filtrar interacciones por fecha</h2>"
            '<p class="nota">No se registraron eventos en esta bitácora. '
            "Filtro por fecha no generado.</p>"
            "</section>"
        )

    dt = _to_datetime_series(df)
    df_local = df.copy()
    df_local["_has_latlon"] = has_latlon.reindex(df_local.index, fill_value=False)
    df_local["_dt"] = dt
    df_local["_fecha"] = df_local["_dt"].dt.date
    df_local = df_local[df_local["_fecha"].notna()]
    if df_local.empty:
        return (
            '<section id="interacciones-recientes">'
            "<h2>Filtrar interacciones por fecha</h2>"
            '<p class="nota">La información de fecha no pudo ser procesada en esta bitácora. '
            "Filtro por fecha no generado.</p>"
            "</section>"
        )

    fechas_ord = sorted(df_local["_fecha"].dropna().unique().tolist(), reverse=True)
    if not fechas_ord:
        return (
            '<section id="interacciones-recientes">'
            "<h2>Filtrar interacciones por fecha</h2>"
            '<p class="nota">Fecha no disponible en esta bitácora. '
            "Filtro por fecha no generado.</p>"
            "</section>"
        )
    fechas_sel = fechas_ord  # ya no se limita por `dias`

    if col_contacto not in df_local.columns:
        df_local["_contacto_valido"] = False
        df_local["_contacto"] = "No disponible"
    else:
        raw_contacto = df_local[col_contacto]
        df_local["_contacto_valido"] = raw_contacto.map(es_valor_significativo)
        contacto_visible = raw_contacto.astype(str).str.strip()
        df_local["_contacto"] = contacto_visible.where(df_local["_contacto_valido"], "No disponible")

    if duracion_estado is None:
        duracion_estado = clasificar_confiabilidad_duracion(df, columnas_config=columnas_config)

    duracion_disponible = duracion_estado.estado == "segura"
    dur_col_effective = duracion_estado.columna if duracion_estado.columna else col_duracion

    if duracion_disponible and dur_col_effective and dur_col_effective in df_local.columns:
        ser_dur = df_local[dur_col_effective]
        unidad = duracion_estado.unidad
        if unidad == "hhmmss":
            df_local["_dur_sec"] = ser_dur.map(parse_duration_seconds)
        else:
            numeric_dur = pd.to_numeric(ser_dur, errors="coerce").fillna(0.0)
            if unidad == "minutos":
                df_local["_dur_sec"] = numeric_dur * 60
            elif unidad == "milisegundos":
                df_local["_dur_sec"] = numeric_dur / 1000
            else:
                df_local["_dur_sec"] = numeric_dur
    else:
        df_local["_dur_sec"] = np.nan

    if col_tipo and col_tipo in df_local.columns:
        hay_tipo_evento = bool(df_local[col_tipo].map(es_valor_significativo).any())
    else:
        hay_tipo_evento = False

    out: list[str] = []
    out.append('<section id="interacciones-recientes">')
    out.append('<h2>Filtrar interacciones por fecha</h2>')
    out.append(_construir_sujeto_analizado_html(df, col_tel, col_imei))
    out.append(f'<p>Nota: Se muestran <strong>{len(fechas_sel)}</strong> día(s) con actividad.</p>')

    if not bool(df_local["_contacto_valido"].any()):
        out.append(
            '<p class="nota-contacto"><em>Nota:</em> No se identificó contacto válido '
            "en la bitácora.</p>"
        )

    if not hay_tipo_evento:
        out.append(
            '<p class="nota-tipo-evento"><em>Nota:</em> El tipo de evento no está '
            "disponible en la bitácora.</p>"
        )

    if duracion_estado.estado == "ambigua":
        out.append(
            '<p class="nota-duracion"><em>Nota:</em> Duración no calculada: la unidad '
            "de los valores reportados no pudo confirmarse.</p>"
        )
    elif duracion_estado.estado == "ausente":
        out.append(
            '<p class="nota-duracion"><em>Nota:</em> Duración no disponible: no se '
            "identificó una columna de duración utilizable en la bitácora.</p>"
        )

    if hay_sitio_inferido:
        out.append(
            f'<p class="nota nota-sitios-inferidos"><em>Nota:</em> {_NOTA_SITIOS_INFERIDOS}</p>'
        )

    fmin = min(fechas_sel)
    fmax = max(fechas_sel)
    out.append(
        f"""
<div style="background:#e7f3ff;border-left:4px solid #2196F3;padding:12px;margin:12px 0;">
  <strong>📅 Rango:</strong> {pd.to_datetime(fmin).strftime('%d/%m/%Y')} — {pd.to_datetime(fmax).strftime('%d/%m/%Y')}
</div>
<div style="margin:12px 0 18px 0;">
  <label for="dia-selector" style="font-weight:600;margin-right:8px;">Seleccionar día:</label>
  <select id="dia-selector" style="padding:8px;font-size:1rem;border:1px solid #ccc;border-radius:4px;">
"""
    )
    for d in fechas_sel:
        _dt = pd.to_datetime(d)
        label = _dt.strftime("%d/%m/%Y")
        out.append(f'<option value="{_dt.strftime("%Y-%m-%d")}">{label}</option>')
    out.append("</select></div>")

    for d in fechas_sel:
        df_d = df_local[df_local["_fecha"] == d].copy()
        try:
            df_d = df_d.sort_values(by=["_dt"])
        except Exception:
            pass

        antenas_validas = False
        if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
            antenas_validas = df_d["_has_latlon"].any()

        fecha_h = pd.to_datetime(d).strftime("%d/%m/%Y")
        out.append(f'<div id="content-{pd.to_datetime(d).strftime("%Y-%m-%d")}" class="day-content" style="display:none;">')
        if hay_tipo_evento:
            out.append(f"<h3>Se muestran las interacciones del día: {fecha_h}</h3>")
        else:
            out.append(f"<h3>Se muestran los registros disponibles del día: {fecha_h}</h3>")

        total_dia = int(len(df_d))
        out.append(
            '<p class="fecha-registros-seleccionados">'
            f"<strong>Fecha seleccionada:</strong> {fecha_h} "
            f"&nbsp;|&nbsp; <strong>Registros mostrados:</strong> {total_dia}</p>"
        )
        dur_total_dia = (
            _fmt_hms(df_d["_dur_sec"].sum() if "_dur_sec" in df_d.columns else 0)
            if duracion_disponible
            else None
        )

        if total_dia > 0:
            if col_antena and (col_antena in df_d.columns):
                _valid_rows = df_d[df_d["_has_latlon"]]
                antenas_unicas = int(_valid_rows[col_antena].dropna().astype(str).nunique()) if not _valid_rows.empty else 0
            else:
                antenas_unicas = 0
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                sin_antena_cnt = int((~df_d["_has_latlon"]).sum())
            else:
                sin_antena_cnt = total_dia
            pct_sin_antena = (sin_antena_cnt / total_dia) * 100.0
        else:
            antenas_unicas = 0
            pct_sin_antena = 0.0

        contactos_unicos = (
            int(df_d.loc[df_d["_contacto_valido"], "_contacto"].nunique())
            if "_contacto_valido" in df_d.columns
            else 0
        )
        kpi_label_registros = "Interacciones" if hay_tipo_evento else "Registros"
        dur_kpi_html = (
            f' &nbsp;|&nbsp; <span><strong>Duración:</strong> {dur_total_dia}</span>'
            if duracion_disponible
            else ""
        )
        out.append(
            f'<p class="kpis-dia">'
            f'<span><strong>{kpi_label_registros}:</strong> {total_dia}</span>'
            f'{dur_kpi_html}'
            f' &nbsp;|&nbsp; <span><strong>Antenas únicas:</strong> {antenas_unicas}</span>'
            f' &nbsp;|&nbsp; <span><strong>Contactos únicos:</strong> {contactos_unicos}</span>'
            f' &nbsp;|&nbsp; <span><strong>Sin antena válida:</strong> {pct_sin_antena:.0f}%</span>'
            f"</p>"
        )

        if not antenas_validas:
            out.append('<p><em>Nota:</em> Esta fecha no registró antenas válidas en la bitácora.</p>')

        if df_d.empty:
            out.append('<p>Sin interacciones registradas.</p>')
            out.append('</div>')
            continue

        include_celda = bool(col_celda) and (col_celda in df_d.columns)
        out.append('<div class="tabla-scroll">')
        out.append('<table class="tabla-compacta">')
        thead_cols = [
            "#", "contacto", "hora",
            "tipo de interacción" if hay_tipo_evento else "tipo de evento",
            "duración", "antena/sitio" if hay_sitio_inferido else "antena", "lat", "long", "azimut",
        ]
        if include_celda:
            thead_cols.append("celda")
        out.append('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in thead_cols) + '</tr></thead><tbody>')

        def _fmt_coord(val):
            """Formatea coordenada numérica a string con 6 decimales o '—' si es inválida."""
            try:
                if val is None:
                    return "—"
                val_f = float(val)
                if np.isnan(val_f):
                    return "—"
                return f"{val_f:.6f}"
            except Exception:
                return "—"

        def _fmt_az(v):
            """Formatea valor de azimut a string entero redondeado o '—' si es inválido."""
            if v is None:
                return "—"
            try:
                f = float(v)
                return f"{int(round(f))}"
            except Exception:
                s = str(v).strip()
                return s if s else "—"

        def _fmt_hora(row):
            """Formatea hora de fila extrayendo de columna hora o datetime, retorna '—' si falla."""
            try:
                if col_hora and (col_hora in row.index):
                    s = str(row[col_hora]).strip()
                    return s if s else "—"
                if pd.notna(row.get("_dt")):
                    return pd.to_datetime(row["_dt"]).strftime("%H:%M:%S")
            except Exception:
                pass
            return "—"

        def _ant_fmt_link(ant, lt, lg):
            """Formatea nombre de antena como enlace HTML a Google Maps si tiene coordenadas válidas."""
            try:
                if ant and (lt is not None) and (lg is not None):
                    lt_f = float(lt)
                    lg_f = float(lg)
                    if not (np.isnan(lt_f) or np.isnan(lg_f)):
                        url = f"https://www.google.com/maps?q={lt_f:.6f},{lg_f:.6f}"
                        return f'<a href="{url}" target="_blank" rel="noopener">{ant}</a>'
            except Exception:
                pass
            return str(ant).strip() if str(ant).strip() else "—"

        for idx, (_, r) in enumerate(df_d.iterrows(), start=1):
            contacto = str(r.get("_contacto", "No disponible"))
            hora_val = _fmt_hora(r)
            if col_tipo and (col_tipo in r.index) and es_valor_significativo(r.get(col_tipo)):
                tipo_val = str(r.get(col_tipo)).strip()
            else:
                tipo_val = "No disponible"
            dur_hms = _fmt_hms(r.get("_dur_sec", 0)) if duracion_disponible else "No disponible"
            ant_val = _ant_fmt_link(r.get(col_antena, ""), r.get(col_lat, None), r.get(col_long, None)) if col_antena else "—"
            if hay_sitio_inferido and bool(r.get("sitio_inferido", False)):
                ant_val += _BADGE_SITIO_INFERIDO
            lat_val = _fmt_coord(r.get(col_lat, None))
            long_val = _fmt_coord(r.get(col_long, None))
            az_val = _fmt_az(r.get(col_azimut, None)) if col_azimut else "—"
            celda_val = str(r.get(col_celda, "")).strip() if (include_celda and (col_celda in r.index)) else None

            row_cls = "" if idx <= 20 else ' style="display:none" class="row-hidden"'
            tds = [
                f'<td class="mono">{idx}</td>',
                f"<td>{contacto}</td>",
                f'<td class="mono nowrap">{hora_val}</td>',
                f"<td>{tipo_val}</td>",
                f'<td class="mono nowrap">{dur_hms}</td>',
                f"<td>{ant_val}</td>",
                f'<td class="mono nowrap">{lat_val}</td>',
                f'<td class="mono nowrap">{long_val}</td>',
                f'<td class="mono">{az_val}°</td>',
            ]
            if include_celda:
                tds.append(f'<td class="mono">{(celda_val if celda_val else "—")}</td>')
            out.append('<tr data-day="' + pd.to_datetime(d).strftime("%Y-%m-%d") + '"' + row_cls + '>' + ''.join(tds) + '</tr>')

        out.append("</tbody></table></div>")

        if len(df_d) > 20:
            out.append(
                f"<div style='margin:10px 0;'>"
                f"<button class='ver-mas-btn' data-day='{pd.to_datetime(d).strftime('%Y-%m-%d')}' "
                f"style='padding:8px 12px;border:1px solid #ccc;border-radius:6px;background:#f8f8f8;cursor:pointer;'>Ver más registros</button>"
                f"</div>"
            )

        def _haversine_km(lat1, lon1, lat2, lon2):
            """Calcula distancia en kilómetros entre dos puntos usando fórmula haversine."""
            lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return 6371.0 * c

        def _mask_contact(s):
            """Enmascara número de contacto para privacidad según configuración, reemplazando con '*'."""
            try:
                html_cfg = cfg.get("html", {}) if isinstance(cfg, dict) else {}
                if html_cfg.get("enmascarar_contactos", False):
                    ult = int(html_cfg.get("enmascarar_ultimos", 4))
                    s = str(s)
                    return ("*" * max(0, len(s) - ult)) + s[-ult:]
            except Exception:
                pass
            return str(s)

        alertas = []

        try:
            if total_dia > 0:
                df_contactos_validos = df_d[df_d["_contacto_valido"]]
                if not df_contactos_validos.empty:
                    agg = (
                        df_contactos_validos.groupby("_contacto")
                        .agg(interacciones=("_contacto", "size"), dur_total=("_dur_sec", "sum"))
                        .reset_index()
                    )
                else:
                    agg = pd.DataFrame()
            else:
                agg = pd.DataFrame()
        except Exception:
            agg = pd.DataFrame()

        if total_dia > 0 and not agg.empty:
            agg_sorted = agg.sort_values(["interacciones", "dur_total"], ascending=[False, False])
            top_row_inter = agg_sorted.iloc[0]
            prop_inter = top_row_inter["interacciones"] / total_dia
            if prop_inter >= 0.60:
                alertas.append(
                    f"Concentración (interacciones): {_mask_contact(top_row_inter['_contacto'])} acumula "
                    f"{prop_inter:.0%} del día ({int(top_row_inter['interacciones'])}/{total_dia})."
                )

        if duracion_disponible:
            sum_dur = float(df_d["_dur_sec"].sum()) if "_dur_sec" in df_d.columns else 0.0
            if sum_dur > 0 and not agg.empty:
                agg_sorted_d = agg.sort_values(["dur_total", "interacciones"], ascending=[False, False])
                top_row_dur = agg_sorted_d.iloc[0]
                prop_dur = float(top_row_dur["dur_total"]) / sum_dur if sum_dur else 0.0
                if prop_dur >= 0.60:
                    alertas.append(
                        f"Concentración (duración): {_mask_contact(top_row_dur['_contacto'])} acumula "
                        f"{prop_dur:.0%} del día ({_fmt_hms(top_row_dur['dur_total'])} de {_fmt_hms(sum_dur)})."
                    )

        try:
            if col_antena and (col_lat in df_d.columns) and (col_long in df_d.columns):
                dfv = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
                if not dfv.empty:
                    top2 = (
                        dfv.groupby(col_antena)
                        .agg(cnt=(col_antena, "size"), lat=(col_lat, "mean"), lon=(col_long, "mean"))
                        .sort_values("cnt", ascending=False)
                        .head(2)
                        .reset_index()
                    )
                    if len(top2) >= 2:
                        a1, a2 = str(top2.loc[0, col_antena]), str(top2.loc[1, col_antena])
                        dist_km = _haversine_km(top2.loc[0, "lat"], top2.loc[0, "lon"], top2.loc[1, "lat"], top2.loc[1, "lon"])
                        if dist_km >= 2.0:
                            alertas.append(f"Movilidad: '{a1}' ↔ '{a2}' ≈ {dist_km:.1f} km (top 2 celdas del día).")
        except Exception:
            pass

        try:
            if total_dia > 0 and pct_sin_antena >= 30:
                alertas.append(f"Calidad: {pct_sin_antena:.0f}% de {total_dia} registros sin antena válida.")
        except Exception:
            pass

        if alertas:
            out.append('<div class="alertas-dia"><ul>')
            for a in alertas:
                out.append(f'<li class="alerta-item">{a}</li>')
            out.append('</ul></div>')

        try:
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                df_points = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
            else:
                df_points = df_d.iloc[0:0]

            day_str = pd.to_datetime(d).strftime("%Y%m%d")

            def render_heatmap_html_for_day(df_day, day_id):
                """
                Genera mapa de calor HTML con Leaflet para antenas activadas en un día.
                Incluye clústeres de puntos y tooltips con información de antena.
                """
                antenas_dict: Dict[tuple, Dict[str, Any]] = {}
                total_filas = 0
                if df_day is None or df_day.empty:
                    return f"<div class='map-notice'>Sin datos de ubicación para {pd.to_datetime(d).strftime('%d/%m/%Y')}</div>"

                for _, rr in df_day.iterrows():
                    total_filas += 1
                    try:
                        lat = float(rr[col_lat])
                        lon = float(rr[col_long])
                    except Exception:
                        continue

                    if col_antena and col_antena in df_day.columns:
                        name = str(rr.get(col_antena, ""))
                        if name and name != "nan":
                            lat_round = round(lat, 5)
                            lon_round = round(lon, 5)
                            key = (lat_round, lon_round, name)
                            if key not in antenas_dict:
                                antenas_dict[key] = {"lat": lat, "lon": lon, "name": name, "count": 0, "azs": {}}
                            antenas_dict[key]["count"] += 1
                            if col_azimut and (col_azimut in df_day.columns):
                                try:
                                    azv = rr.get(col_azimut, None)
                                    if azv is not None and str(azv).strip() != "":
                                        azf = int(round(float(azv)))
                                        antenas_dict[key]["azs"][azf] = antenas_dict[key]["azs"].get(azf, 0) + 1
                                except Exception:
                                    pass

                if not antenas_dict:
                    return f"<div class='map-notice'>Sin antenas válidas para mapear en {pd.to_datetime(d).strftime('%d/%m/%Y')} (se procesaron {total_filas} registros con coordenadas)</div>"

                markers = []
                for item in antenas_dict.values():
                    azimut_principal = None
                    if item.get("azs"):
                        try:
                            azimut_principal = max(item["azs"].items(), key=lambda t: t[1])[0]
                        except Exception:
                            azimut_principal = None
                    markers.append({"lat": item["lat"], "lon": item["lon"], "name": item["name"], "count": item["count"], "azimut": azimut_principal})
                num_antenas = len(markers)

                log(f"[DEBUG] Día {day_id}: {total_filas} registros procesados, {num_antenas} antenas únicas mapeadas")
                for m in markers:
                    log(f"  - {m['name']}: {m['count']} activaciones en ({m['lat']:.6f}, {m['lon']:.6f})")

                _markers_js = json.dumps(markers, ensure_ascii=False)
                div_id = f"heatmap-{day_id}"

                template = Template("""
<div style="margin:16px auto; max-width:95%; padding:0 20px;">
    <p style="font-size:12px; color:#666; margin:4px 0 8px;">
        Se muestran <strong>${num_antenas} antena(s)</strong> con coordenadas válidas de este día. 
        Haz clic en los marcadores para ver detalles de cada ubicación.
    </p>
    <div id="wrap-${div_id}" class="tz-map-wrap" style="position:relative;">
        <button class="tz-fs-btn" title="Pantalla completa" data-map-id="${div_id}" style="position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;">⛶</button>
        <div id="${div_id}" style="height:clamp(420px, 70vh, 720px); width:100%; margin-bottom:12px; border:1px solid #ddd; border-radius:6px;"></div>
    </div>
</div>
<script>
    (function(){
        var markers = ${markers_js};
        if (!Array.isArray(markers) || markers.length === 0) return;
        try {
            var map = L.map('${div_id}', { scrollWheelZoom: false });
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);
      
            var latlngs = markers.map(function(m){ return [m.lat, m.lon]; });
            var bounds = L.latLngBounds(latlngs);
            
            if (markers.length === 1) {
                map.setView([markers[0].lat, markers[0].lon], 12);
            } else {
                try { 
                    map.fitBounds(bounds, { padding: [80, 80] }); 
                } catch(e) { 
                    map.setView(latlngs[0], 10); 
                }
            }
      
            markers.forEach(function(m, idx) {
                var mk = L.marker([m.lat, m.lon]).addTo(map);
                console.log('Marcador ' + (idx+1) + ': ' + m.name + ' en [' + m.lat + ', ' + m.lon + '] con ' + m.count + ' activaciones');
                var popupHtml = '' +
                    '<div style="font-family:sans-serif;min-width:180px;">' +
                    '<strong style="font-size:14px;">Antena #' + (idx+1) + '</strong><br>' +
                    '<strong style="font-size:13px;color:#333;">' + (m.name || '') + '</strong><br>' +
                    '<span style="font-size:12px;color:#666;">Activaciones: ' + (m.count || 0) + '</span><br>' +
                    '<span style="font-size:11px;color:#999;">Coordenadas: ' + (typeof m.lat==='number'? m.lat.toFixed(6): m.lat) + ', ' + (typeof m.lon==='number'? m.lon.toFixed(6): m.lon) + '</span>' +
                    ((m.azimut !== null && m.azimut !== undefined) ? "<br><span style='font-size:12px;color:#666;'>Azimut principal: " + m.azimut + "°</span>" : '') +
                    '</div>';
                mk.bindPopup(popupHtml, { maxWidth: 250 });
            });

            try {
                window.__tzDailyMaps = window.__tzDailyMaps || {};
                window.__tzDailyMaps['${div_id}'] = {
                    map: map,
                    bounds: bounds,
                    markersCount: markers.length,
                    center: (latlngs && latlngs.length>0) ? latlngs[0] : null,
                    wrapperId: 'wrap-${div_id}'
                };
            } catch(e) {}
        } catch(err) { console.error('heatmap-day error', err); }
    })();
</script>""")
                html = template.substitute(
                    num_antenas=num_antenas,
                    div_id=div_id,
                    markers_js=_markers_js,
                )
                return html

            sec_day_heatmap = render_heatmap_html_for_day(df_points, day_str)
            out.append(sec_day_heatmap)
        except Exception as e:
            log(f"[WARN] Error generando mini-heatmap para {day_str}: {e}")
            try:
                import traceback
                log(traceback.format_exc())
            except Exception:
                pass

        out.append("</div>")

    out.append(
        """
<style>
#interacciones-recientes .tabla-compacta { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
#interacciones-recientes .tabla-compacta th, 
#interacciones-recientes .tabla-compacta td { border: 1px solid #ddd; padding: 16px 32px; text-align: center; }
#interacciones-recientes .tabla-compacta th { background: #f2f2f2; }
#interacciones-recientes .tabla-scroll { overflow-x: auto; }
#interacciones-recientes tr.resalte { font-weight: 600; }
#interacciones-recientes .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
#interacciones-recientes .nowrap { white-space: nowrap; }
</style>
"""
    )
    out.append(
        """
<style>
#interacciones-recientes .kpis-dia { margin: 4px 0 10px 0; font-size: 0.95rem; color: #333; }
#interacciones-recientes .kpis-dia span { display: inline-block; margin-right: 10px; }
</style>
"""
    )
    out.append(
        """
<style>
#interacciones-recientes .alertas-dia { margin: 8px 0 18px 0; }
#interacciones-recientes .alertas-dia ul { margin: 0 0 0 18px; padding: 0; }
#interacciones-recientes .alerta-item { color: #b45309; }
</style>
"""
    )
    out.append(
        """
<script>
(function(){
    function showDay(dateStr){
        var all = document.querySelectorAll('#interacciones-recientes .day-content');
        all.forEach(function(el){ el.style.display = 'none'; });
        var el = document.getElementById('content-' + dateStr);
        if(el){
            el.style.display = 'block';
            setTimeout(function(){
                try {
                    var key = 'heatmap-' + String(dateStr).replace(/-/g,'');
                    var reg = (window.__tzDailyMaps || {})[key];
                    if (reg && reg.map) {
                        reg.map.invalidateSize();
                        if (reg.markersCount === 1 && reg.center) {
                            reg.map.setView(reg.center, 12);
                        } else if (reg.bounds) {
                            reg.map.fitBounds(reg.bounds, { padding: [80, 80] });
                        }
                    }
                } catch(e) {}
            }, 0);
        }
    }
    var sel = document.getElementById('dia-selector');
    if(sel){ sel.addEventListener('change', function(){ showDay(this.value); });
             if(sel.options.length>0){ showDay(sel.options[0].value); } }

    document.querySelectorAll('#interacciones-recientes .ver-mas-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
            var day = this.getAttribute('data-day');
            var rows = document.querySelectorAll('tr[data-day="' + day + '"].row-hidden');
            var reveal = 10;
            var count = 0;
            for(var i=0;i<rows.length && count<reveal;i++,count++){
                rows[i].style.display = 'table-row';
                rows[i].classList.remove('row-hidden');
            }
            if(document.querySelectorAll('tr[data-day="' + day + '"].row-hidden').length === 0){
                this.style.display = 'none';
            }
        });
    });

    document.addEventListener('click', function(ev){
        var btn = ev.target.closest('.tz-fs-btn');
        if(!btn) return;
        var mapId = btn.getAttribute('data-map-id');
        var reg = (window.__tzDailyMaps || {})[mapId];
        if(!reg || !reg.map) return;
        var wrap = document.getElementById('wrap-' + mapId);
        if(!wrap) return;
        var mapEl = document.getElementById(mapId);
        if(!mapEl) return;

        var fs = wrap.classList.toggle('tz-fs-active');
        if(fs){
            wrap.setAttribute('data-prev-scroll', String(window.scrollY||0));
            mapEl.setAttribute('data-prev-height', mapEl.style.height || '');
            wrap.style.position = 'fixed';
            wrap.style.inset = '0';
            wrap.style.zIndex = '9999';
            mapEl.style.height = '100%';
            document.body.style.overflow = 'hidden';
        } else {
            var prevH = mapEl.getAttribute('data-prev-height') || '';
            mapEl.style.height = prevH;
            wrap.style.position = 'relative';
            wrap.style.inset = '';
            wrap.style.zIndex = '';
            document.body.style.overflow = '';
            var sy = parseInt(wrap.getAttribute('data-prev-scroll')||'0',10) || 0;
            window.scrollTo(0, sy);
        }
        setTimeout(function(){
            try{
                reg.map.invalidateSize();
                if (reg.markersCount === 1 && reg.center) {
                    reg.map.setView(reg.center, fs ? 13 : 12);
                } else if (reg.bounds) {
                    reg.map.fitBounds(reg.bounds, { padding: fs ? [100,100] : [80,80] });
                }
            }catch(e){}
        }, 50);
    });
})();
</script>
"""
    )

    out.append("</section>")
    return "".join(out)
