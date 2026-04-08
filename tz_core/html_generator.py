"""
TZ-Analyzer — HTML Generator Module

Módulo principal de generación de informes HTML para bitácoras telefónicas.
Contiene toda la lógica de construcción del reporte: estructura HTML, estilos,
componentes visuales (headers, KPIs, tablas de antenas), secciones de contenido
(interacciones, contactos, mapas de calor) e inyección de metadatos técnicos.

La función principal es generar_informe_html(), que orquesta todas las secciones.

Architecture: TZ-Analyzer v1.0.0 — tz_core package
"""

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import numpy as np

from tz_core.logging_utils import log
from tz_core.config_manager import cargar_config
from tz_core.dataframe_utils import pick_first_existing_column
from tz_core.html_helpers import (
    fmt_datetime as fmt_dt,
    first_nonempty_in,
    unique_values_in,
    fmt_imei_item,
    row_html,
    nunique_in,
    luhn_check,
    is_valid_imei,
)
from tz_core.runtime_utils import collect_env_snapshot
from tz_core.html_toc import apply_toc
from tz_core.time_utils import to_datetime_silent, normalize_hour_to_hhmmss
from tz_core.analytics import generar_historial_cambios_antena
from tz_core.file_utils import write_detailed_hashes_report
from tz_core.bitacora_normalization import (
    parse_duration_seconds,
    sanitize_latlon,
    normalize_msisdn,
    normalize_imei,
)
from tz_core.html.header import build_logo_html, generate_html_header, generate_body_header


def prepare_report_metrics(
    df: pd.DataFrame,
    archivo_kml: str,
    carpeta_salida: str,
    config: dict | None = None,
) -> dict:
    """Calcula todas las métricas y rutas necesarias para el informe HTML."""
    from datetime import datetime

    kml_name = os.path.basename(archivo_kml)
    kmz_name = os.path.splitext(kml_name)[0] + ".kmz"

    cfg = config if isinstance(config, dict) else {}
    if bool(cfg.get("salida", {}).get("separar_kml_kmz", False)):
        # El HTML se guarda en carpeta_salida (raíz). KML está en /kml y KMZ en /kmz
        kml_href = os.path.join("kml", kml_name) if os.path.basename(os.path.dirname(archivo_kml)).lower() == "kml" else kml_name
        kmz_rel = os.path.join("kmz", kmz_name)
        kmz_abs = os.path.join(carpeta_salida, kmz_rel)
        kmz_exists = os.path.exists(kmz_abs)
        kmz_link = f' | <a href="{kmz_rel}" download>Descargar KMZ</a>' if kmz_exists else ""
    else:
        kml_href = kml_name
        kmz_abs = os.path.join(carpeta_salida, kmz_name)
        kmz_exists = os.path.exists(kmz_abs)
        kmz_link = f' | <a href="{kmz_name}" download>Descargar KMZ</a>' if kmz_exists else ""

    # --- Métricas rápidas ---
    total = int(len(df))
    bbox_global = {"lat_min": -90.0, "lat_max": 90.0, "lon_min": -180.0, "lon_max": 180.0}
    df_coords = sanitize_latlon(df, bbox=bbox_global)
    lat_num = df_coords.get("lat", pd.Series(dtype=float))
    lon_num = df_coords.get("long", pd.Series(dtype=float))
    valid_coord = int((lat_num.notna() & lon_num.notna()).sum())
    coord_validas = int(valid_coord)
    coord_invalidas = int(total - coord_validas)

    # antenas únicas (mismo filtro que la tabla: sin nombres inválidos y con coords válidas)
    if "antena" in df.columns:
        s_ant = df["antena"].astype(str).str.strip()
        invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        m_name = ~s_ant.str.lower().isin(invalid_names)

        m_coord = lat_num.notna() & lon_num.notna()
        activaciones_total = len(df)
        coord_validas = int(m_coord.sum())
        coord_invalidas = int(activaciones_total - coord_validas)

        ant_series_f = s_ant[m_name & m_coord]
        ant_uniq = int(ant_series_f.nunique()) if not ant_series_f.empty else 0

        if not ant_series_f.empty:
            vc = ant_series_f.value_counts()
            top_antena = vc.index[0]
            top_count = int(vc.iloc[0])
            top_pct = (top_count / len(ant_series_f) * 100.0)
        else:
            top_antena, top_count, top_pct = "—", 0, 0.0
    else:
        ant_uniq = 0
        top_antena, top_count, top_pct = "—", 0, 0.0
        print(f"Antenas únicas (KPI): {ant_uniq} — Top antena: {top_antena} ({top_count})")

    # celdas únicas (robusto: usa LAC+CID si ambos; si no, el que exista)
    cel_label = "Celdas (CID) únicas"
    cel_uniq = 0
    try:
        has_cid = any(c in df.columns for c in ["celda", "cid", "cellid", "cell_id"])
        has_lac = any(c in df.columns for c in ["lac", "lac_id", "lacid"])
        if has_cid and has_lac:
            ccol = next(c for c in ["celda", "cid", "cellid", "cell_id"] if c in df.columns)
            lcol = next(c for c in ["lac", "lac_id", "lacid"] if c in df.columns)
            s_c = df[ccol].dropna().astype(str).str.strip()
            s_l = df[lcol].dropna().astype(str).str.strip()
            m_c = s_c != ""
            m_l = s_l != ""
            if (m_c.any() and m_l.any()):
                cel_label = "Parejas LAC+CID únicas"
                cel_uniq = int(df.loc[m_c.index[m_c] & m_l.index[m_l], [lcol, ccol]].drop_duplicates().shape[0])
            elif m_c.any():
                cel_label = "Celdas (CID) únicas"
                cel_uniq = int(s_c[m_c].nunique())
            elif m_l.any():
                cel_label = "LAC únicas"
                cel_uniq = int(s_l[m_l].nunique())
        elif has_cid:
            ccol = next(c for c in ["celda", "cid", "cellid", "cell_id"] if c in df.columns)
            s_c = df[ccol].dropna().astype(str).str.strip()
            s_c = s_c[s_c != ""]
            cel_uniq = int(s_c.nunique()) if not s_c.empty else 0
        elif has_lac:
            lcol = next(c for c in ["lac", "lac_id", "lacid"] if c in df.columns)
            s_l = df[lcol].dropna().astype(str).str.strip()
            s_l = s_l[s_l != ""]
            cel_label = "LAC únicas"
            cel_uniq = int(s_l.nunique()) if not s_l.empty else 0
    except Exception as e:
        log(f"[WARN] generar_informe_html: Error calculando celdas únicas: {e}")

    # rango de fechas/horas (visual dd/mm/aaaa HH:MM — dd/mm/aaaa HH:MM)
    rango_str = "Sin datos"

    if "fecha" in df.columns:
        # Preferir combinar fecha+hora si existe 'hora'
        dt = None
        try:
            if "hora" in df.columns and df["hora"].notna().any():
                dt = to_datetime_silent(
                    df["fecha"].astype(str).str.strip() + " " + df["hora"].astype(str).str.strip(),
                    dayfirst=True, errors="coerce"
                ).dropna()
            else:
                # Solo fecha: tomar 00:00 para el inicio y 23:59 para el fin
                fechas = to_datetime_silent(df["fecha"], dayfirst=True, errors="coerce").dropna()
                if not fechas.empty:
                    fmin = fechas.min().normalize()                        # 00:00
                    fmax = (fechas.max().normalize() + pd.Timedelta(hours=23, minutes=59))
                    rango_str = f"{fmt_dt(fmin)} — {fmt_dt(fmax)}"
                else:
                    rango_str = "Sin datos"
        except Exception as e:
            log(f"[WARN] generar_informe_html: Error procesando rango de fechas: {e}")
            dt = None

        if dt is not None and not dt.empty:
            min_ts, max_ts = dt.min(), dt.max()
            rango_str = f"{fmt_dt(min_ts)} — {fmt_dt(max_ts)}"
        elif dt is None:
            # ya se resolvió arriba (solo fecha) o quedó Sin datos
            rango_str = rango_str if "rango_str" in locals() else "Sin datos"
    else:
        rango_str = "Sin datos"

    # color tema para acentos (del CONFIG si está)
    try:
        theme_hex = cfg.get("style", {}).get("theme_hex", "#ff00ff")
    except Exception:
        theme_hex = "#ff00ff"

    # fecha/hora generación
    gen_dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return {
        "kml_name": kml_name,
        "kmz_name": kmz_name,
        "kml_href": kml_href,
        "kmz_link": kmz_link,
        "kmz_abs": kmz_abs,
        "total": total,
        "coord_validas": coord_validas,
        "coord_invalidas": coord_invalidas,
        "ant_uniq": ant_uniq,
        "top_antena": top_antena,
        "top_count": top_count,
        "top_pct": top_pct,
        "cel_uniq": cel_uniq,
        "cel_label": cel_label,
        "rango_str": rango_str,
        "theme_hex": theme_hex,
        "gen_dt": gen_dt,
    }


def resolve_top_antennas_n(config: dict | None, overrides: dict | None, default: int = 3) -> int:
    """Obtiene el Top N de antenas respetando overrides y config.

    Precedencia: overrides.antenas → config["top_antenas"] → config["html"]["top_antenas_n"] → default.
    Siempre devuelve un entero válido; ante errores o valores faltantes retorna `default`.
    """
    try:
        if overrides and isinstance(overrides, dict):
            if overrides.get("antenas") is not None:
                return int(overrides.get("antenas"))

        if config and isinstance(config, dict):
            if config.get("top_antenas") is not None:
                return int(config.get("top_antenas"))

            html_cfg = config.get("html", {}) or {}
            if html_cfg.get("top_antenas_n") is not None:
                return int(html_cfg.get("top_antenas_n"))

        return int(default)
    except Exception:
        return int(default)


def build_antennas_table(df: pd.DataFrame, config: dict | None = None) -> str:
    """Construye tabla HTML de todas las antenas con coords, conteo y azimuts frecuentes."""
    top_tab_html = "<p class='small'>No se encontraron antenas.</p>"
    if "antena" in df.columns:
        df_a = df.copy()
        df_a["antena"] = df_a.get("antena", "").astype(str).str.strip()
        _invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        df_a = df_a[~df_a["antena"].str.lower().isin(_invalid_names)]

        if not df_a.empty:
            # timestamp (fecha + hora si existe)
            if "fecha" in df_a.columns:
                hora_str = df_a.get("hora", "").astype(str).str[:8]
                ts = to_datetime_silent(
                    df_a["fecha"].astype(str).str.strip() + " " + hora_str,
                    errors="coerce", dayfirst=True
                )
                df_a["_ts"] = ts
            else:
                df_a["_ts"] = pd.NaT

            # azimut entero (para frecuencia)
            az = pd.to_numeric(df_a.get("azimut", pd.Series(dtype=float)), errors="coerce").round().astype("Int64")
            df_a["_az_i"] = az

            # coords numéricas validadas con helper central
            bbox_all = {"lat_min": -90.0, "lat_max": 90.0, "lon_min": -180.0, "lon_max": 180.0}
            try:
                df_a = sanitize_latlon(df_a, lat_col="lat", lon_col="long", bbox=bbox_all)
            except Exception:
                pass
            df_a["_lat"] = pd.to_numeric(df_a.get("lat", pd.Series(dtype=float)), errors="coerce")
            df_a["_lon"] = pd.to_numeric(df_a.get("long", pd.Series(dtype=float)), errors="coerce")
            df_a = df_a[df_a["_lat"].notna() & df_a["_lon"].notna()]

        # Construimos entradas y ordenamos por conteo (desc)
        entries = []
        for antenna, g in df_a.groupby("antena", dropna=False):
            cnt = int(len(g))
            lat_v = g["_lat"].dropna()
            lon_v = g["_lon"].dropna()
            lat_s = f"{lat_v.iloc[0]:.6f}" if not lat_v.empty else "—"
            lon_s = f"{lon_v.iloc[0]:.6f}" if not lon_v.empty else "—"
            azvc = g["_az_i"].dropna().value_counts().head(3)
            az_s = ", ".join([f"{int(k)}° ({int(v)})" for k, v in azvc.items()]) if not azvc.empty else "—"
            entries.append((cnt, antenna, lat_s, lon_s, az_s))

        entries.sort(key=lambda x: x[0], reverse=True)

        rows = []
        for idx, (cnt, antenna, lat_s, lon_s, az_s) in enumerate(entries, start=1):
            # Si hay coordenadas válidas, convertir la antena en link a Google Maps
            if lat_s != "—" and lon_s != "—":
                ant_cell = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{antenna}</a>'
            else:
                ant_cell = antenna

            rows.append(
                f"<tr>"
                f"<td class='mono'>{idx}</td>"
                f"<td>{ant_cell}</td>"
                f"<td class='mono nowrap'>{lat_s}</td>"
                f"<td class='mono nowrap'>{lon_s}</td>"
                f"<td class='mono'>{cnt:,}</td>"
                f"<td>{az_s}</td>"
                f"</tr>"
            )

        if rows:
            top_tab_html = (
                "<table class='tbl'>"
                "<thead><tr>"
                "<th>#</th><th>Antena</th><th>Lat</th><th>Long</th><th>Conteo</th><th>Azimuts frecuentes</th>"
                "</tr></thead><tbody>"
                + "".join(rows) +
                "</tbody></table>"
            )

    return top_tab_html


def build_top_antennas_section(
    df: pd.DataFrame,
    config: dict | None,
    overrides: dict | None,
) -> str:
    """Genera la sección HTML de "Antenas más activadas" (Top N).

    - Usa `resolve_top_antennas_n` para obtener N respetando overrides/config.
    - Filtra antenas vacías/"0" y coordenadas inválidas o fuera del bbox SV.
    - Devuelve HTML listo para insertar; en caso de error o datos insuficientes, devuelve "".
    """
    try:
        if df is None or df.empty:
            return ""

        # Bounding box: config -> fallback SV
        bbox = None
        try:
            if isinstance(config, dict):
                bbox = (config.get("geografia", {}) or {}).get("sv_bbox")
        except Exception:
            bbox = None

        if not (isinstance(bbox, dict) and all(k in bbox for k in ("lat_min", "lat_max", "lon_min", "lon_max"))):
            bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

        top_n = resolve_top_antennas_n(config, overrides, default=3)

        # Columnas
        col_ant = pick_first_existing_column(df, ["antena", "nombre_antena", "cell_name"])
        col_lat = pick_first_existing_column(df, ["lat", "latitud", "latitude"])
        col_lon = pick_first_existing_column(df, ["long", "lon", "longitud", "lng", "longitude"])
        col_az = pick_first_existing_column(df, ["azimut", "azimuth", "azi", "angulo"])

        if not col_ant:
            return ""

        def _valid_latlon(lt, lg):
            """Valida si coordenadas lat/lon son válidas y dentro del bbox configurado."""
            try:
                lt = float(lt)
                lg = float(lg)
                if np.isnan(lt) or np.isnan(lg):
                    return False
                if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                    return False
                return (bbox["lat_min"] <= lt <= bbox["lat_max"]) and (bbox["lon_min"] <= lg <= bbox["lon_max"])
            except Exception:
                return False

        dfv = df.copy()
        dfv[col_ant] = dfv[col_ant].astype(str).str.strip()
        dfv = dfv[dfv[col_ant].notna() & (dfv[col_ant] != "") & (dfv[col_ant] != "0")]

        if col_lat and col_lon and col_lat in dfv.columns and col_lon in dfv.columns:
            dfv = dfv[dfv.apply(lambda r: _valid_latlon(r[col_lat], r[col_lon]), axis=1)]

        if dfv.empty:
            return ""

        top = (
            dfv.groupby(col_ant)
            .size()
            .reset_index(name="activaciones")
            .sort_values("activaciones", ascending=False)
        )
        if int(top_n) > 0:
            top = top.head(int(top_n))

        filas = []
        for _, r0 in top.iterrows():
            ant = str(r0[col_ant])
            sub = dfv[dfv[col_ant] == ant]

            lt = float(sub[col_lat].astype(float).mean()) if (col_lat and col_lat in sub.columns) else None
            lg = float(sub[col_lon].astype(float).mean()) if (col_lon and col_lon in sub.columns) else None

            az_dom, desg = "—", "—"
            if col_az and (col_az in sub.columns):
                vc = (
                    sub[col_az]
                    .astype(str)
                    .str.strip()
                    .replace({"": np.nan, "nan": np.nan})
                    .dropna()
                    .value_counts()
                )
                if not vc.empty:
                    az_dom = str(vc.index[0])
                    parts = [
                        f"Azimut {int(float(k))}: {int(v)} {'vez' if int(v)==1 else 'veces'}"
                        for k, v in vc.head(3).items()
                    ]
                    desg = "<br>".join(parts) + (" …" if len(vc) > 3 else "")

            if (lt is not None) and (lg is not None):
                url = f"https://www.google.com/maps?q={lt:.6f},{lg:.6f}"
                ant_fmt = f'<a href="{url}" target="_blank" rel="noopener">{ant}</a>'
                lt_fmt, lg_fmt = f"{lt:.6f}", f"{lg:.6f}"
            else:
                ant_fmt, lt_fmt, lg_fmt = ant, "—", "—"

            filas.append((ant_fmt, int(r0["activaciones"]), lt_fmt, lg_fmt, az_dom, desg))

        out: list[str] = []
        out.append('<section id="resumen-antenas">')
        out.append(f'<h2>Antenas más activadas (Top {top_n})</h2>')
        out.append('<p class="nota"><b>Nota:</b> En esta sección se muestra un top list de las antenas más activadas en el periodo analizado; seguidamente se muestra la ubicación de esas antenas segun sus coordenadas.</p>')
        out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
        out.append('<thead><tr>'
                  '<th>#</th>'
                  '<th>Antena</th>'
                  '<th>Latitud</th>'
                  '<th>Longitud</th>'
                  '<th>Activaciones</th>'
                  '<th>Azimut</th>'
                  '</tr></thead><tbody>')
        for idx, (ant_fmt, act, lt_fmt, lg_fmt, az_dom, desg) in enumerate(filas, start=1):
            out.append('<tr>'
                      f'<td>{idx}</td>'
                      f'<td>{ant_fmt}</td>'
                      f'<td>{lt_fmt}</td>'
                      f'<td>{lg_fmt}</td>'
                      f'<td>{act}</td>'
                      f'<td>{desg}</td>'
                      '</tr>')
        out.append('</tbody></table></div>')
        out.append(
            """
<style>
#resumen-antenas .tabla-compacta { border-collapse: collapse; width:100%; font-size:1rem; }
#resumen-antenas .tabla-compacta th, #resumen-antenas .tabla-compacta td { border:1px solid #ddd; padding:6px 8px; text-align:left; }
#resumen-antenas .tabla-compacta th { background:#f2f2f2; }
#resumen-antenas .tabla-scroll { overflow-x:auto; }
</style>
"""
        )
        out.append('</section>')
        return "".join(out)
    except Exception as exc:  # defensivo: no romper el flujo principal
        log(f"[WARNING] build_top_antennas_section fallback: {exc}")
        return ""
    
def build_antennas_by_hour_section(
    df: pd.DataFrame,
    config: dict | None,
    overrides: dict | None,
) -> str:
    """Genera la sección "Antenas por rango horario".

    - Respeta overrides/config para el Top N (resolve_top_antennas_n).
    - Agrupa por rangos: Madrugada, Mañana, Tarde, Noche.
    - Filtra antenas vacías/0 y coords inválidas.
    """

    try:
        if df is None or df.empty:
            return ""

        col_ant = pick_first_existing_column(df, ["antena", "antenanombre", "antena_nombre"])
        col_lat = pick_first_existing_column(df, ["lat", "latitud"])
        col_lon = pick_first_existing_column(df, ["lon", "long", "longitud"])
        col_hora = pick_first_existing_column(
            df,
            [
                "hora",
                "hora_utc",
                "hora_local",
                "hora_llamada",
                "hora_evento",
                "hora_local_sv",
                "hora_sv",
                "time",
            ],
        )
        col_fecha_hora = pick_first_existing_column(
            df,
            [
                "fecha y hora",
                "fechahora",
                "fecha_hora",
                "datetime",
                "timestamp",
            ],
        )
        col_az = pick_first_existing_column(df, ["azimut", "azimuth", "azi", "angulo"])

        if not col_ant:
            return ""

        def _to_hour_series():
            """Extrae hora como entero de columna de hora usando normalización o pandas."""
            import warnings

            if col_hora is not None:
                # 1) Normalizar con helper tolerante a separadores variados
                norm = df[col_hora].map(normalize_hour_to_hhmmss)
                if norm.notna().any():
                    return norm.map(lambda v: int(v.split(":")[0]) if v else np.nan)

                # 2) Fallback silencioso a pandas
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="Could not infer format*", category=UserWarning)
                    s = pd.to_datetime(df[col_hora], errors="coerce").dt.hour

                # 3) Fallback manual si la mayoría sigue en NaN
                if s.isna().mean() > 0.5:
                    def _hh(x):
                        """Extrae componente de hora (entero) de un valor datetime/string en formato HH:MM:SS."""
                        try:
                            x = str(x)
                            return int(x.split(":")[0])
                        except Exception:
                            return np.nan

                    s = df[col_hora].map(_hh)
                return s

            if col_fecha_hora is not None:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="Could not infer format*", category=UserWarning)
                    return pd.to_datetime(df[col_fecha_hora], errors="coerce").dt.hour
            return None

        hours = _to_hour_series()
        if hours is None:
            return ""

        try:
            invalid_ratio = float(hours.isna().mean()) if len(hours) else 0.0
            if invalid_ratio > 0.2:
                log(
                    f"[WARNING] Antenas por rango horario: {invalid_ratio*100:.1f}% de horas no se pudieron normalizar; revisa formato de 'hora'/'fecha_hora'."
                )
        except Exception:
            pass

        def _lab(h):
            """Genera etiqueta de periodo del día según la hora (Mañana/Tarde/Noche)."""
            if h is None or np.isnan(h):
                return None
            h = int(h)
            if 6 <= h <= 11:
                return "Mañana (06:00–11:59)"
            if 12 <= h <= 17:
                return "Tarde (12:00–17:59)"
            if 18 <= h <= 23:
                return "Noche (18:00–23:59)"
            return "Madrugada (00:00–05:59)"

        labels_orden = [
            "Madrugada (00:00–05:59)",
            "Mañana (06:00–11:59)",
            "Tarde (12:00–17:59)",
            "Noche (18:00–23:59)",
        ]

        def _fmt(x):
            """Formatea número flotante con 6 decimales o retorna '—' si falla."""
            try:
                x = float(x)
                return f"{x:.6f}"
            except Exception:
                return "—"

        def _first_valid_geo(sub_ant):
            """Retorna las primeras coordenadas válidas (lat, lon) no-cero de un subset de antenas."""
            if col_lat and col_lon:
                tmp = sub_ant[[col_lat, col_lon]].dropna()
                if not tmp.empty:
                    t2 = tmp[(tmp[col_lat] != 0) | (tmp[col_lon] != 0)]
                    if not t2.empty:
                        r = t2.iloc[0]
                        return float(r[col_lat]), float(r[col_lon])
            return (None, None)

        top_n = resolve_top_antennas_n(config, overrides, default=3)

        out: list[str] = []
        out.append('<section id="antenas-rangos">')
        out.append('<h2>Antenas por rango horario</h2>')
        out.append('<p class="nota"><b>Nota:</b> Si desea verificar la ubicación de una antena, puede hacer clic en el nombre para abrir su posición en Google Maps.</p>')
        out.append('<style>#antenas-rangos h3.sub{background:#f7f7f7;border:1px solid #e6e6e6;border-radius:6px;padding:.5rem .75rem;margin:1rem 0 .5rem}#antenas-rangos .mono{font-family:ui-monospace,Menlo,Consolas,monospace}#antenas-rangos .nowrap{white-space:nowrap}</style>')

        rangos = hours.map(_lab)
        for lab in labels_orden:
            mask = rangos == lab
            total = int(mask.sum())
            if total == 0:
                continue
            sub = df[mask]

            tmp = sub.copy()
            tmp["_lat"] = pd.to_numeric(tmp.get(col_lat, pd.Series(dtype=float)), errors="coerce")
            tmp["_lon"] = pd.to_numeric(tmp.get(col_lon, pd.Series(dtype=float)), errors="coerce")
            valid_geo = (
                tmp["_lat"].between(-90, 90)
                & tmp["_lon"].between(-180, 180)
                & ~((tmp["_lat"].abs() < 1e-9) & (tmp["_lon"].abs() < 1e-9))
            )
            ant_str = tmp[col_ant].astype(str).str.strip()
            valid_ant = (ant_str != "") & (ant_str != "0") & (~ant_str.str.match(r"(?i)(sin\s*inf\.?|s/i)$"))

            sub_valid = tmp[valid_geo & valid_ant]

            conteo = sub_valid[col_ant].value_counts(dropna=False)
            top_series = conteo
            if int(top_n) > 0:
                top_series = conteo.head(int(top_n))

            out.append(f'<h3 class="sub">{lab} <span class="sub">({total} activaciones)</span></h3>')
            out.append('<table class="tbl"><thead><tr><th>#</th><th>Antena</th><th>Latitud</th><th>Longitud</th><th>Conteo</th><th>Azimuts frecuentes</th></tr></thead><tbody>')

            for idx, (ant, cnt) in enumerate(top_series.items(), start=1):
                sub_ant = sub_valid[sub_valid[col_ant] == ant]

                lat, lon = _first_valid_geo(sub_ant)
                lat_s = _fmt(lat) if lat is not None else "—"
                lon_s = _fmt(lon) if lon is not None else "—"

                if lat is not None and lon is not None:
                    ant_html = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{ant}</a>'
                else:
                    ant_html = f"{ant}"

                az_s = "—"
                if col_az and (col_az in sub_ant.columns):
                    try:
                        azv = pd.to_numeric(sub_ant[col_az], errors="coerce").round().dropna().astype(int)
                        vc = azv.value_counts().head(3)
                        if not vc.empty:
                            parts = [
                                f"Azimut {int(k)}: {int(v)} {'vez' if int(v)==1 else 'veces'}" for k, v in vc.items()
                            ]
                            az_s = "<br>".join(parts)
                    except Exception:
                        pass

                out.append(
                    f"<tr><td class='mono'>{idx}</td>"
                    f"<td>{ant_html}</td>"
                    f"<td class='mono nowrap'>{lat_s}</td>"
                    f"<td class='mono nowrap'>{lon_s}</td>"
                    f"<td class='mono'>{int(cnt):,}</td>"
                    f"<td>{az_s}</td></tr>"
                )

            out.append("</tbody></table>")

        out.append("</section>")
        sec_html = "\n".join(out)
        log(f"[DEBUG] Antenas por horario: {len(sec_html)} chars")
        return sec_html
    except Exception:
        return ""


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


def generate_kpi_section(
    total: int, 
    coord_validas: int, 
    coord_invalidas: int, 
    ant_uniq: int, 
    cel_uniq: int, 
    cel_label: str,
    top_antena: str, 
    top_count: int, 
    top_pct: float
) -> str:
    """
    Genera la sección de KPIs/Indicadores del HTML con tarjetas de métricas clave.
    
    Extrae la sección HTML-INDICADORES-KPI que incluye:
    - <section> container con título "Indicadores"
    - Grid de tarjetas KPI con clase "kpis"
    - Tarjeta de registros totales
    - Tarjeta de coordenadas válidas/inválidas con subtotal
    - Tarjeta de antenas únicas
    - Tarjeta de celdas únicas con etiqueta dinámica
    - Tarjeta de top antena con porcentaje
    
    Args:
        total (int): Número total de registros en el dataset
        coord_validas (int): Registros con coordenadas geográficas válidas
        coord_invalidas (int): Registros con coordenadas inválidas o faltantes
        ant_uniq (int): Cantidad única de antenas identificadas
        cel_uniq (int): Cantidad única de celdas identificadas  
        cel_label (str): Etiqueta descriptiva para el tipo de celda
        top_antena (str): Identificador de la antena más frecuente
        top_count (int): Número de registros de la antena top
        top_pct (float): Porcentaje que representa la antena top del total
        
    Returns:
        str: HTML completo de la sección de indicadores KPI
        
    Example:
        >>> kpis = generate_kpi_section(1500, 1450, 50, 25, 40, "Celdas LTE", "ANT001", 300, 20.0)
        >>> print("1,500" in kpis and "20.0%" in kpis)
        True
    """
    return f"""  <section>
    <h2>Indicadores</h2>
    <div class="kpis">
      <div class="card">
        <div class="n">{total:,}</div>
        <div class="label">Registros totales</div>
      </div>
      <div class="kpi">
        <div class="num">{coord_validas:,}</div>
        <div class="lbl">Con coordenadas válidas</div>
        <div class="sub">({coord_invalidas:,} inválidas)</div>
      </div>

      <div class="card">
        <div class="n">{ant_uniq:,}</div>
        <div class="label">Antenas únicas</div>
      </div>
      <div class="card">
        <div class="n">{cel_uniq:,}</div>
        <div class="label">{cel_label}</div>
      </div>
      <div class="card">
        <div class="n">{top_antena}</div>
        <div class="label">Top antena ({top_count:,} — {top_pct:.1f}%)</div>
      </div>
    </div>
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


def build_top_contacts_sections(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    overrides: Optional[dict] = None,
) -> Tuple[str, str, int]:
    """Genera HTML para top contactos por conteo y por duración.

    Retorna (html_conteo, html_duracion, top_n_usado).
    """

    if df is None:
        df = pd.DataFrame()

    def _to_seconds_any(x) -> float:
        """Convierte duración en cualquier formato a segundos usando parse_duration_seconds."""
        try:
            return float(parse_duration_seconds(x, default=0.0))
        except Exception:
            return 0.0

    def _fmt_hms(sec: float) -> str:
        """Formatea segundos a formato HH:MM:SS o MM:SS según duración."""
        sec = int(round(sec))
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    contact_cols = [
        "tel_contacto",
        "contacto",
        "destino",
        "b_number",
        "bnumber",
        "numero_contacto",
        "callednumber",
        "to",
        "receptor",
        "receptor_numero",
        "numero_destino",
    ]
    dur_cols = ["duracion", "duration", "segundos", "tiempo"]
    c_col = next((c for c in contact_cols if c in df.columns), None)
    d_col = next((c for c in dur_cols if c in df.columns), None)

    note_no_dur = (
        "<p class='small' style='color:#666;background:#f7f7f7;border:1px solid #eee;padding:.5rem .75rem;border-radius:6px'>"
        "Se omite por no disponer de la columna <code>duracion</code>."
        "</p>"
    )
    note_zero_dur = "<p class='note muted'>No hay minutos acumulados &gt; 0 en el período; se omite la tabla.</p>"

    if not d_col:
        log("HTML: se omitió la subtabla 'Por minutos acumulados' por falta de 'duracion'.")

    top_contactos_cnt_html = "<p class='small'>No hay columna de contacto.</p>"
    top_contactos_dur_html = note_no_dur if not d_col else "<p class='small'>No hay columna de contacto.</p>"

    def _resolve_top_limit() -> int:
        """Resuelve el límite de top contactos desde overrides, config o default 10."""
        try:
            if overrides and isinstance(overrides, dict) and overrides.get("contactos") is not None:
                return int(overrides.get("contactos"))
        except Exception:
            pass
        try:
            if config and isinstance(config, dict):
                if config.get("top_contactos") is not None:
                    return int(config.get("top_contactos"))
                html_cfg = config.get("html", {}) or {}
                return int(html_cfg.get("top_contactos_n", 10))
        except Exception:
            pass
        return 10

    _topC = _resolve_top_limit()

    if c_col:
        d = df.copy()
        d["_contacto_raw"] = d[c_col].astype(str).str.strip()
        d["_contacto"] = d["_contacto_raw"].map(lambda v: normalize_msisdn(v) or v)
        d = d[(d["_contacto"] != "") & d["_contacto"].notna()]

        if not d.empty:
            if d_col:
                d["_sec"] = d[d_col].map(_to_seconds_any)
            else:
                d["_sec"] = 0.0

            d["_c_norm"] = d["_contacto"].str.replace(r"\D+", "", regex=True)
            d.loc[d["_c_norm"] == "", "_c_norm"] = d["_contacto"]

            g_cnt = (
                d.groupby("_c_norm", dropna=False)
                .size()
                .sort_values(ascending=False)
            )
            if int(_topC) > 0:
                g_cnt = g_cnt.head(int(_topC))
            total_cnt = int(len(d))
            rows = []
            for i, (k, n) in enumerate(g_cnt.items(), start=1):
                pct = (float(n) / total_cnt * 100.0) if total_cnt else 0.0
                rows.append(
                    f"<tr>"
                    f"<td class='right mono'>{i}</td>"
                    f"<td class='mono'>{k}</td>"
                    f"<td class='mono'>{int(n):,} <span class='small'>({pct:.1f}%)</span></td>"
                    f"</tr>"
                )
                rows.append(
                    f"<tr class='barrow'><td colspan='3'>"
                    f"<div class='bar'><div class='fill' style='width:{pct:.1f}%;'></div></div>"
                    f"</td></tr>"
                )
            if rows:
                top_contactos_cnt_html = (
                    "<table class='tbl'>"
                    "<thead><tr><th class='right'>#</th><th>Contacto</th><th>Interacciones</th></tr></thead>"
                    "<tbody>" + "".join(rows) + "</tbody></table>"
                )

            if d_col:
                g_dur = (
                    d.groupby("_c_norm", dropna=False)["_sec"]
                    .sum()
                    .sort_values(ascending=False)
                )
                if int(_topC) > 0:
                    g_dur = g_dur.head(int(_topC))

                total_sec = float(pd.to_numeric(d["_sec"], errors="coerce").fillna(0).sum())

                if total_sec <= 0:
                    top_contactos_dur_html = note_zero_dur
                    log("HTML: se omitió 'Por minutos acumulados' porque la suma total de 'duracion' es 0.")
                else:
                    rows = []
                    for i, (k, tot) in enumerate(g_dur.items(), start=1):
                        pct = (float(tot) / total_sec * 100.0) if total_sec > 0 else 0.0
                        rows.append(
                            f"<tr>"
                            f"<td class='right mono'>{i}</td>"
                            f"<td class='mono'>{k}</td>"
                            f"<td class='mono'>{_fmt_hms(tot)} <span class='small'>({pct:.1f}%)</span></td>"
                            f"</tr>"
                        )
                        rows.append(
                            f"<tr class='barrow'><td colspan='3'>"
                            f"<div class='bar'><div class='fill' style='width:{pct:.1f}%;'></div></div>"
                            f"</td></tr>"
                        )
                    if rows:
                        top_contactos_dur_html = (
                            "<table class='tbl'>"
                            "<thead><tr><th class='right'>#</th><th>Contacto</th><th>Duración total</th></tr></thead>"
                            "<tbody>" + "\n".join(rows) + "</tbody></table>"
                        )

    return top_contactos_cnt_html, top_contactos_dur_html, _topC

# ==============================================================================
# EPIC 16A: Extracción de sección de interacciones (776 líneas)
# ==============================================================================

def construir_seccion_interacciones(df, dias=3, columnas_config=None, CONFIG=None):
    """
    Construye una secci├│n HTML con 'Interacciones de los ├║ltimos N d├¡as registrados en bit├ícora'.
    - Subsecciones por fecha (dd/mm/aaaa), orden: m├ís reciente -> m├ís antiguo.
    - Por cada fecha: tabla por contacto con #interacciones, duraci├│n acumulada, antena top y sus coords/azimut.
    - Si una fecha no tiene antenas v├ílidas: muestra nota.
    
    Args:
        df: DataFrame con datos de interacciones
        dias: N├║mero de d├¡as a mostrar (default: 3)
        columnas_config: Configuraci├│n de columnas personalizadas
        CONFIG: Diccionario de configuraci├│n global (si None, se obtiene autom├íticamente)
    """
    
    # Obtener configuraci├│n si no se proporciona
    if CONFIG is None:
        CONFIG = cargar_config()

    # Helpers
    def _pick_col(df, candidatos):
        """Selecciona y retorna la primera columna existente de una lista de candidatas."""
        for c in candidatos:
            if c and c in df.columns:  # Ignora None y strings vac├¡os
                return c
        return None

    def _to_datetime_series(df):
        """Convierte DataFrame a Series datetime combinando fecha+hora o columnas datetime."""
        # Intento 1: combinaci├│n fecha + hora
        if 'fecha' in df.columns and 'hora' in df.columns:
            try:
                return pd.to_datetime(df['fecha'].astype(str).str.strip() + ' ' + df['hora'].astype(str).str.strip(),
                                      dayfirst=True, errors='coerce')
            except Exception:
                pass
        # Intento 2: columnas comunes
        for c in ['datetime', 'fecha_hora', 'timestamp', 'fec_hor', 'fechaHora']:
            if c in df.columns:
                s = pd.to_datetime(df[c], dayfirst=True, errors='coerce')
                if s.notna().any():
                    return s
        # Intento 3: solo fecha
        if 'fecha' in df.columns:
            s = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
            return s
        return pd.Series(pd.NaT, index=df.index)

    def _fmt_hms(total_seconds):
        """Formatea segundos totales a formato HH:MM:SS con manejo de errores."""
        try:
            total_seconds = float(total_seconds)
        except Exception:
            return "00:00:00"
        if np.isnan(total_seconds):
            return "00:00:00"
        total_seconds = int(round(total_seconds))
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    # Column mapping - buscar primero por config, luego por nombres can├│nicos y fallbacks
    columnas_config = columnas_config or {}
    
    # Si viene mapeado desde config, usar ese nombre; si no, buscar por nombres est├índar
    col_contacto = _pick_col(df, [
        columnas_config.get('contacto'),
        columnas_config.get('tel_contacto'),
        columnas_config.get('destino'),
        columnas_config.get('b_party'),
        'contacto', 'tel_contacto', 'destino', 'b_party', 'to', 'callee'
    ]) or 'tel_contacto'  # si no existe, m├ís abajo se maneja

    col_duracion = _pick_col(df, [
        columnas_config.get('duracion'),
        'duracion', 'dur', 'duration', 'segundos', 'tiempo'
    ])
    col_antena = _pick_col(df, [
        columnas_config.get('antena'),
        'antena', 'nombre_antena', 'site_name', 'cell_name'
    ])
    col_lat = _pick_col(df, [
        columnas_config.get('lat'),
        'lat', 'latitud', 'latitude'
    ])
    col_long = _pick_col(df, [
        columnas_config.get('long'),
        columnas_config.get('lon'),
        'long', 'lon', 'longitud', 'lng', 'longitude'
    ])
    col_azimut = _pick_col(df, [
        columnas_config.get('azimut'),
        'azimut', 'azimuth', 'azi', 'angulo'
    ])

    # Columnas adicionales para la tabla detallada
    col_tipo = _pick_col(df, [
        columnas_config.get('tipo'),
        'tipo', 'interaccion', 'tipo_interaccion', 'interaction', 'tipo_llamada'
    ])
    col_celda = _pick_col(df, [
        columnas_config.get('celda'),
        'celda', 'cod_celda_inicial', 'cell_id', 'cgi'
    ])
    col_hora = _pick_col(df, [
        columnas_config.get('hora'),
        'hora', 'hora_inicial', 'time', 'timestamp'
    ])

    # === TOP-ANTENA-1A: bbox y validadores de coordenadas ===
    # Intentar leer bounding box (SV) desde config; si no, usar fallback
    try:
        _bbox_cfg = None
        if 'CONFIG' in globals() and isinstance(CONFIG, dict):
            _bbox_cfg = CONFIG.get("geografia", {}).get("sv_bbox", None)
    except Exception:
        _bbox_cfg = None

    if not (isinstance(_bbox_cfg, dict) and all(k in _bbox_cfg for k in ("lat_min","lat_max","lon_min","lon_max"))):
        # Aproximaci├│n para El Salvador
        _bbox_cfg = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

    def _valid_latlon_vals(lt, lg):
        """True si lat/lon son num├®ricas, no NaN, no (0,0) y dentro del bbox SV."""
        try:
            lt = float(lt); lg = float(lg)
            if np.isnan(lt) or np.isnan(lg):
                return False
            if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                return False
            return (_bbox_cfg["lat_min"] <= lt <= _bbox_cfg["lat_max"]) and (_bbox_cfg["lon_min"] <= lg <= _bbox_cfg["lon_max"])
        except Exception:
            return False

    def _es_valida_latlon_row(row):
        """Versi├│n por fila: usa nombres de columnas detectados arriba."""
        if col_lat and col_long and (col_lat in row) and (col_long in row):
            return _valid_latlon_vals(row[col_lat], row[col_long])
        return False
    # === TOP-ANTENA-1A (fin) ===

    # Si no hay df razonable, retorna vac├¡o (no rompe HTML)
    if df is None or df.empty:
        return ""

    # Construcci├│n de datetime y fecha
    dt = _to_datetime_series(df)
    df_local = df.copy()
    df_local['_dt'] = dt
    df_local['_fecha'] = df_local['_dt'].dt.date
    df_local = df_local[df_local['_fecha'].notna()]
    if df_local.empty:
        return ""

    # TODOS los d├¡as con actividad (ordenados de m├ís reciente a m├ís antiguo)
    fechas_ord = sorted(df_local['_fecha'].dropna().unique().tolist(), reverse=True)
    if not fechas_ord:
        return ""
    # Ya no limitamos por 'dias', mostramos TODOS los d├¡as con actividad
    fechas_sel = fechas_ord

    # Si no hay columna de contacto, crea una gen├®rica SIN DETERMINAR
    if col_contacto not in df_local.columns:
        df_local['_contacto'] = 'SIN DETERMINAR'
    else:
        df_local['_contacto'] = df_local[col_contacto].fillna('SIN DETERMINAR').astype(str).str.strip()
        df_local.loc[df_local['_contacto'] == '', '_contacto'] = 'SIN DETERMINAR'

    # Duraci├│n en segundos: si viene string tipo hh:mm:ss, convi├®rtelo
    if col_duracion and col_duracion in df_local.columns:
        ser_dur = df_local[col_duracion]
        if pd.api.types.is_numeric_dtype(ser_dur):
            df_local['_dur_sec'] = pd.to_numeric(ser_dur, errors='coerce').fillna(0)
        else:
            df_local['_dur_sec'] = ser_dur.map(parse_duration_seconds)
    else:
        df_local['_dur_sec'] = 0

    # HTML con dropdown y tabla por registro (con paginaci├│n 20 + ver m├ís de 10)
    out = []
    out.append('<section id="interacciones-recientes">')
    out.append('<h2>Filtrar interacciones por fecha</h2>')
    out.append(f'<p>Nota: Se muestran <strong>{len(fechas_sel)}</strong> d├¡a(s) con actividad.</p>')

    # Banner de rango + dropdown (solo fechas)
    fmin = min(fechas_sel)
    fmax = max(fechas_sel)
    out.append(f"""
<div style="background:#e7f3ff;border-left:4px solid #2196F3;padding:12px;margin:12px 0;">
  <strong>­ƒôà Rango:</strong> {pd.to_datetime(fmin).strftime('%d/%m/%Y')} ÔÇö {pd.to_datetime(fmax).strftime('%d/%m/%Y')}
</div>
<div style="margin:12px 0 18px 0;">
  <label for="dia-selector" style="font-weight:600;margin-right:8px;">Seleccionar d├¡a:</label>
  <select id="dia-selector" style="padding:8px;font-size:1rem;border:1px solid #ccc;border-radius:4px;">
""")
    for d in fechas_sel:
        _dt = pd.to_datetime(d)
        label = _dt.strftime("%d/%m/%Y")
        out.append(f'<option value="{_dt.strftime("%Y-%m-%d")}">{label}</option>')
    out.append('</select></div>')

    # Recorre fechas seleccionadas
    for d in fechas_sel:
        df_d = df_local[df_local['_fecha'] == d].copy()
        # Orden cronol├│gico por hora/_dt
        try:
            df_d = df_d.sort_values(by=['_dt'])
        except Exception:
            pass

        # ┬┐Fecha con alguna antena v├ílida?
        antenas_validas = False
        if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
            antenas_validas = df_d[col_lat].notna().any() and df_d[col_long].notna().any()

        fecha_h = pd.to_datetime(d).strftime("%d/%m/%Y")
        out.append(f'<div id="content-{pd.to_datetime(d).strftime("%Y-%m-%d")}" class="day-content" style="display:none;">')
        out.append(f'<h3>Se muestran las interacciones del d├¡a: {fecha_h}</h3>')

        # KPIs del d├¡a
        total_dia = int(len(df_d))
        dur_total_dia = _fmt_hms(df_d['_dur_sec'].sum() if '_dur_sec' in df_d.columns else 0)

        # Validador de coordenadas con bbox El Salvador
        def _es_valida_latlon_row(row):
            """Valida si la fila tiene coordenadas lat/lon válidas y dentro del bbox."""
            try:
                lt = float(row[col_lat]) if (col_lat and col_lat in df_d.columns) else None
                lg = float(row[col_long]) if (col_long and col_long in df_d.columns) else None
                if lt is None or lg is None:
                    return False
                if np.isnan(lt) or np.isnan(lg):
                    return False
                if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                    return False
                # BBOX El Salvador
                try:
                    if 'CONFIG' in globals() and isinstance(CONFIG, dict):
                        bbox = CONFIG.get("geografia", {}).get("sv_bbox", None)
                        if bbox and isinstance(bbox, dict):
                            lat_min = bbox.get("lat_min", 12.9)
                            lat_max = bbox.get("lat_max", 14.5)
                            lon_min = bbox.get("lon_min", -90.3)
                            lon_max = bbox.get("lon_max", -87.6)
                        else:
                            lat_min, lat_max, lon_min, lon_max = 12.9, 14.5, -90.3, -87.6
                    else:
                        lat_min, lat_max, lon_min, lon_max = 12.9, 14.5, -90.3, -87.6
                    return (lat_min <= lt <= lat_max) and (lon_min <= lg <= lon_max)
                except Exception:
                    return True  # si falla el bbox, al menos validamos que no sea 0,0
            except Exception:
                return False

        if total_dia > 0:
            if col_antena and (col_antena in df_d.columns):
                _valid_rows = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
                antenas_unicas = int(_valid_rows[col_antena].dropna().astype(str).nunique()) if not _valid_rows.empty else 0
            else:
                antenas_unicas = 0
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                sin_antena_cnt = int((~df_d.apply(_es_valida_latlon_row, axis=1)).sum())
            else:
                sin_antena_cnt = total_dia
            pct_sin_antena = (sin_antena_cnt / total_dia) * 100.0
        else:
            antenas_unicas = 0
            pct_sin_antena = 0.0

        contactos_unicos = int(df_d['_contacto'].nunique()) if '_contacto' in df_d.columns else 0
        out.append(
            f'<p class="kpis-dia">'
            f'<span><strong>Interacciones:</strong> {total_dia}</span>'
            f' &nbsp;|&nbsp; <span><strong>Duraci├│n:</strong> {dur_total_dia}</span>'
            f' &nbsp;|&nbsp; <span><strong>Antenas ├║nicas:</strong> {antenas_unicas}</span>'
            f' &nbsp;|&nbsp; <span><strong>Contactos ├║nicos:</strong> {contactos_unicos}</span>'
            f' &nbsp;|&nbsp; <span><strong>Sin antena v├ílida:</strong> {pct_sin_antena:.0f}%</span>'
            f'</p>'
        )

        if not antenas_validas:
            out.append('<p><em>Nota:</em> Esta fecha no registr├│ antenas v├ílidas en la bit├ícora.</p>')

        if df_d.empty:
            out.append('<p>Sin interacciones registradas.</p>')
            out.append('</div>')
            continue

        # Tabla detallada por registro
        include_celda = bool(col_celda) and (col_celda in df_d.columns)
        out.append('<div class="tabla-scroll">')
        out.append('<table class="tabla-compacta">')
        thead_cols = ["#","contacto","hora","tipo de interacci├│n","duraci├│n","antena","lat","long","azimut"]
        if include_celda:
            thead_cols.append("celda")
        out.append('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in thead_cols) + '</tr></thead><tbody>')

        def _fmt_coord(val):
            """Formatea coordenada numérica a string con 6 decimales o '—' si es inválida."""
            try:
                if val is None:
                    return 'ÔÇö'
                val_f = float(val)
                if np.isnan(val_f):
                    return 'ÔÇö'
                return f"{val_f:.6f}"
            except Exception:
                return 'ÔÇö'

        def _fmt_az(v):
            """Formatea valor de azimut a string entero redondeado o '—' si es inválido."""
            if v is None:
                return 'ÔÇö'
            try:
                f = float(v)
                return f"{int(round(f))}"
            except Exception:
                s = str(v).strip()
                return s if s else 'ÔÇö'

        def _fmt_hora(row):
            """Formatea hora de fila extrayendo de columna hora o datetime, retorna '—' si falla."""
            try:
                if col_hora and (col_hora in row.index):
                    s = str(row[col_hora]).strip()
                    return s if s else 'ÔÇö'
                if pd.notna(row.get('_dt')):
                    return pd.to_datetime(row['_dt']).strftime('%H:%M:%S')
            except Exception:
                pass
            return 'ÔÇö'

        def _ant_fmt_link(ant, lt, lg):
            """Formatea nombre de antena como enlace HTML a Google Maps si tiene coordenadas válidas."""
            try:
                if ant and (lt is not None) and (lg is not None):
                    lt_f = float(lt); lg_f = float(lg)
                    if not (np.isnan(lt_f) or np.isnan(lg_f)):
                        url = f"https://www.google.com/maps?q={lt_f:.6f},{lg_f:.6f}"
                        return f'<a href="{url}" target="_blank" rel="noopener">{ant}</a>'
            except Exception:
                pass
            return (str(ant).strip() if str(ant).strip() else 'ÔÇö')

        # Render filas: 20 visibles, resto ocultas; bot├│n "Ver m├ís" muestra +10
        for idx, (_, r) in enumerate(df_d.iterrows(), start=1):
            contacto = str(r.get('_contacto', 'SIN DETERMINAR'))
            hora_val = _fmt_hora(r)
            tipo_val = (str(r.get(col_tipo, '')).strip() if col_tipo and (col_tipo in r.index) else 'ÔÇö')
            dur_hms = _fmt_hms(r.get('_dur_sec', 0))
            ant_val = _ant_fmt_link(r.get(col_antena, ''), r.get(col_lat, None), r.get(col_long, None)) if col_antena else 'ÔÇö'
            lat_val = _fmt_coord(r.get(col_lat, None))
            long_val = _fmt_coord(r.get(col_long, None))
            az_val = _fmt_az(r.get(col_azimut, None)) if col_azimut else 'ÔÇö'
            celda_val = (str(r.get(col_celda, '')).strip() if (include_celda and (col_celda in r.index)) else None)

            row_cls = '' if idx <= 20 else ' style="display:none" class="row-hidden"'
            tds = [
                f'<td class="mono">{idx}</td>',
                f'<td>{contacto}</td>',
                f'<td class="mono nowrap">{hora_val}</td>',
                f'<td>{tipo_val}</td>',
                f'<td class="mono nowrap">{dur_hms}</td>',
                f'<td>{ant_val}</td>',
                f'<td class="mono nowrap">{lat_val}</td>',
                    f'<td class="mono nowrap">{long_val}</td>',
                    f'<td class="mono">{az_val}┬░</td>'
                ]
            if include_celda:
                tds.append(f'<td class="mono">{(celda_val if celda_val else "ÔÇö")}</td>')
            out.append('<tr data-day="' + pd.to_datetime(d).strftime('%Y-%m-%d') + '"' + row_cls + '>' + ''.join(tds) + '</tr>')

        out.append('</tbody></table></div>')

        # Bot├│n Ver m├ís (incrementa de 10 en 10) - solo si hay m├ís de 20 registros
        if len(df_d) > 20:
            out.append(
                f"<div style='margin:10px 0;'>"
                f"<button class='ver-mas-btn' data-day='{pd.to_datetime(d).strftime('%Y-%m-%d')}' "
                f"style='padding:8px 12px;border:1px solid #ccc;border-radius:6px;background:#f8f8f8;cursor:pointer;'>Ver m├ís registros</button>"
                f"</div>"
            )
        # === ALERTAS-2: avisos por fecha (concentraci├│n, movilidad, calidad) ===
        # Helper: distancia (km)
        def _haversine_km(lat1, lon1, lat2, lon2):
            """Calcula distancia en kilómetros entre dos puntos usando fórmula haversine."""
            from math import radians, sin, cos, sqrt, atan2
            R = 6371.0
            lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c

        # Helper: enmascarar contacto si est├í activado en CONFIG
        def _mask_contact(s):
            """Enmascara número de contacto para privacidad según configuración, reemplazando con '*'."""
            try:
                if 'CONFIG' in globals() and isinstance(CONFIG, dict):
                    cfg = CONFIG.get("html", {})
                    if cfg.get("enmascarar_contactos", False):
                        ult = int(cfg.get("enmascarar_ultimos", 4))
                        s = str(s)
                        return ("*" * max(0, len(s) - ult)) + s[-ult:]
            except Exception:
                pass
            return str(s)

        alertas = []

        # Agregaci├│n m├¡nima por contacto para alertas de concentraci├│n
        try:
            if total_dia > 0:
                agg = (df_d.groupby('_contacto')
                              .agg(interacciones=('_contacto', 'size'),
                                   dur_total=('_dur_sec', 'sum'))
                              .reset_index())
            else:
                agg = pd.DataFrame()
        except Exception:
            agg = pd.DataFrame()

        # 1) Concentraci├│n por interacciones
        if total_dia > 0 and not agg.empty:
            agg_sorted = agg.sort_values(['interacciones', 'dur_total'], ascending=[False, False])
            top_row_inter = agg_sorted.iloc[0]
            prop_inter = top_row_inter['interacciones'] / total_dia
            if prop_inter >= 0.60:
                alertas.append(
                    f"Concentraci├│n (interacciones): {_mask_contact(top_row_inter['_contacto'])} acumula "
                    f"{prop_inter:.0%} del d├¡a ({int(top_row_inter['interacciones'])}/{total_dia})."
                )

        # 1b) Concentraci├│n por duraci├│n
        sum_dur = float(df_d['_dur_sec'].sum()) if '_dur_sec' in df_d.columns else 0.0
        if sum_dur > 0 and not agg.empty:
            agg_sorted_d = agg.sort_values(['dur_total', 'interacciones'], ascending=[False, False])
            top_row_dur = agg_sorted_d.iloc[0]
            prop_dur = float(top_row_dur['dur_total']) / sum_dur if sum_dur else 0.0
            if prop_dur >= 0.60:
                alertas.append(
                    f"Concentraci├│n (duraci├│n): {_mask_contact(top_row_dur['_contacto'])} acumula "
                    f"{prop_dur:.0%} del d├¡a ({_fmt_hms(top_row_dur['dur_total'])} de {_fmt_hms(sum_dur)})."
                )

        # 2) Movilidad: top 2 celdas v├ílidas separadas > 2 km
        try:
            if col_antena and (col_lat in df_d.columns) and (col_long in df_d.columns):
                dfv = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
                if not dfv.empty:
                    top2 = (dfv.groupby(col_antena)
                            .agg(cnt=(col_antena, 'size'),
                                    lat=(col_lat, 'mean'),
                                    lon=(col_long, 'mean'))
                            .sort_values('cnt', ascending=False)
                            .head(2)
                            .reset_index())
                    if len(top2) >= 2:
                        a1, a2 = str(top2.loc[0, col_antena]), str(top2.loc[1, col_antena])
                        dist_km = _haversine_km(top2.loc[0, 'lat'], top2.loc[0, 'lon'],
                                                top2.loc[1, 'lat'], top2.loc[1, 'lon'])
                        if dist_km >= 2.0:
                            alertas.append(f"Movilidad: '{a1}' Ôåö '{a2}' Ôëê {dist_km:.1f} km (top 2 celdas del d├¡a).")
        except Exception:
            pass

        # 3) Calidad: % sin antena v├ílida alto
        try:
            if total_dia > 0 and pct_sin_antena >= 30:
                alertas.append(f"Calidad: {pct_sin_antena:.0f}% de {total_dia} registros sin antena v├ílida.")
        except Exception:
            pass

        # Render de alertas si hay al menos una
        if alertas:
            out.append('<div class="alertas-dia"><ul>')
            for a in alertas:
                out.append(f'<li class="alerta-item">{a}</li>')
            out.append('</ul></div>')
        # === ALERTAS-2 (fin) ===

        # === Mini-heatmap diario: genera un peque├▒o mapa por fecha ===
        # Se muestra DESPU├ëS de las tablas y alertas
        try:
            # preparar filas v├ílidas con lat/lon (usa el validador ya definido arriba con bbox)
            if col_lat and col_long and (col_lat in df_d.columns) and (col_long in df_d.columns):
                df_points = df_d[df_d.apply(_es_valida_latlon_row, axis=1)]
            else:
                df_points = df_d.iloc[0:0]

            day_str = pd.to_datetime(d).strftime('%Y%m%d')

            def render_heatmap_html_for_day(df_day, day_id):
                """
                Genera un mapa que muestra TODAS las antenas ├║nicas activadas en el d├¡a.
                Cada antena se muestra como un marcador con su nombre y conteo de activaciones.
                """
                antenas_dict = {}
                total_filas = 0
                if df_day is None or df_day.empty:
                    return f"<div class='map-notice'>Sin datos de ubicaci├│n para {pd.to_datetime(d).strftime('%d/%m/%Y')}</div>"
                
                # Recolectar y agrupar TODAS las antenas ├║nicas del d├¡a
                for _, rr in df_day.iterrows():
                    total_filas += 1
                    try:
                        lat = float(rr[col_lat])
                        lon = float(rr[col_long])
                    except Exception:
                        continue
                    
                    # Agrupar por antena (usar lat/lon/nombre como clave ├║nica)
                    if col_antena and col_antena in df_day.columns:
                        name = str(rr.get(col_antena, ''))
                        if name and name != 'nan' and name != '':
                            # Usar coordenadas redondeadas para agrupar antenas muy cercanas
                            lat_round = round(lat, 5)  # ~1 metro de precisi├│n
                            lon_round = round(lon, 5)
                            key = (lat_round, lon_round, name)
                            if key not in antenas_dict:
                                antenas_dict[key] = {'lat': lat, 'lon': lon, 'name': name, 'count': 0, 'azs': {}}
                            antenas_dict[key]['count'] += 1
                            # Registrar azimut si existe
                            if col_azimut and (col_azimut in df_day.columns):
                                try:
                                    azv = rr.get(col_azimut, None)
                                    if azv is not None and str(azv).strip() != '':
                                        azf = int(round(float(azv)))
                                        antenas_dict[key]['azs'][azf] = antenas_dict[key]['azs'].get(azf, 0) + 1
                                except Exception:
                                    pass

                if not antenas_dict:
                    return f"<div class='map-notice'>Sin antenas v├ílidas para mapear en {pd.to_datetime(d).strftime('%d/%m/%Y')} (se procesaron {total_filas} registros con coordenadas)</div>"

                # Convertir TODAS las antenas a lista (sin limitar a top N)
                # Convertir a lista y calcular azimut principal por antena
                markers = []
                for item in antenas_dict.values():
                    azimut_principal = None
                    if item.get('azs'):
                        try:
                            azimut_principal = max(item['azs'].items(), key=lambda t: t[1])[0]
                        except Exception:
                            azimut_principal = None
                    markers.append({
                        'lat': item['lat'], 'lon': item['lon'], 'name': item['name'], 'count': item['count'], 'azimut': azimut_principal
                    })
                num_antenas = len(markers)
                
                # Log para debugging
                log(f"[DEBUG] D├¡a {day_id}: {total_filas} registros procesados, {num_antenas} antenas ├║nicas mapeadas")
                for m in markers:
                    log(f"  - {m['name']}: {m['count']} activaciones en ({m['lat']:.6f}, {m['lon']:.6f})")
                
                _markers_js = json.dumps(markers, ensure_ascii=False)
                div_id = f"heatmap-{day_id}"

                html = f'''<div style="margin:16px auto; max-width:95%; padding:0 20px;">
    <p style="font-size:12px; color:#666; margin:4px 0 8px;">
        Se muestran <strong>{num_antenas} antena(s)</strong> con coordenadas v├ílidas de este d├¡a. 
        Haz clic en los marcadores para ver detalles de cada ubicaci├│n.
    </p>
    <div id="wrap-{div_id}" class="tz-map-wrap" style="position:relative;">
        <button class="tz-fs-btn" title="Pantalla completa" data-map-id="{div_id}" style="position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;">ÔøÂ</button>
        <div id="{div_id}" style="height:clamp(420px, 70vh, 720px); width:100%; margin-bottom:12px; border:1px solid #ddd; border-radius:6px;"></div>
    </div>
</div>
<script>
    (function(){{
        var markers = {_markers_js};
        if (!Array.isArray(markers) || markers.length === 0) return;
        try {{
            var map = L.map('{div_id}', {{ scrollWheelZoom: false }});
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OpenStreetMap' }}).addTo(map);
      
            // Crear bounds a partir de todos los marcadores
            var latlngs = markers.map(function(m){{ return [m.lat, m.lon]; }});
            var bounds = L.latLngBounds(latlngs);
            
            // Si solo hay 1 marcador, usar zoom 12; si hay varios, fitBounds con padding muy generoso
            if (markers.length === 1) {{
                map.setView([markers[0].lat, markers[0].lon], 12);
            }} else {{
                try {{ 
                    map.fitBounds(bounds, {{ padding: [80, 80] }}); 
                }} catch(e) {{ 
                    map.setView(latlngs[0], 10); 
                }}
            }}
      
            // Agregar TODOS los marcadores de antenas
            markers.forEach(function(m, idx) {{
                var mk = L.marker([m.lat, m.lon]).addTo(map);
        
                // Log para verificar que se agreg├│
                console.log('Marcador ' + (idx+1) + ': ' + m.name + ' en [' + m.lat + ', ' + m.lon + '] con ' + m.count + ' activaciones');
        
                var popupHtml = '' +
                    '<div style="font-family:sans-serif;min-width:180px;">' +
                    '<strong style="font-size:14px;">Antena #' + (idx+1) + '</strong><br>' +
                    '<strong style="font-size:13px;color:#333;">' + (m.name || '') + '</strong><br>' +
                    '<span style="font-size:12px;color:#666;">Activaciones: ' + (m.count || 0) + '</span><br>' +
                    '<span style="font-size:11px;color:#999;">Coordenadas: ' + (typeof m.lat==='number'? m.lat.toFixed(6): m.lat) + ', ' + (typeof m.lon==='number'? m.lon.toFixed(6): m.lon) + '</span>' +
                    ((m.azimut !== null && m.azimut !== undefined) ? "<br><span style=\'font-size:12px;color:#666;\'>Azimut principal: " + m.azimut + "┬░</span>" : '') +
                    '</div>';
                mk.bindPopup(popupHtml, {{ maxWidth: 250 }});
            }});

            // Registrar mapa y bounds para re-encuadre al cambiar de d├¡a
            try {{
                window.__tzDailyMaps = window.__tzDailyMaps || {{}};
                window.__tzDailyMaps['{div_id}'] = {{
                    map: map,
                    bounds: bounds,
                    markersCount: markers.length,
                    center: (latlngs && latlngs.length>0) ? latlngs[0] : null,
                    wrapperId: 'wrap-{div_id}'
                }};
            }} catch(e) {{}}
        }} catch(err) {{ console.error('heatmap-day error', err); }}
    }})();
</script>'''
                return html

            sec_day_heatmap = render_heatmap_html_for_day(df_points, day_str)
            out.append(sec_day_heatmap)
        except Exception as e:
            # no bloquear la generaci├│n por un fallo en el mapa
            log(f"[WARN] Error generando mini-heatmap para {day_str}: {e}")
            import traceback
            log(traceback.format_exc())

        # Cerrar contenedor del d├¡a
        out.append('</div>')  # cierra day-content

    # Estilos m├¡nimos (reusa tu CSS si ya existe; ac├í defensivo)
    out.append("""
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
""")
    out.append("""
<style>
#interacciones-recientes .kpis-dia { margin: 4px 0 10px 0; font-size: 0.95rem; color: #333; }
#interacciones-recientes .kpis-dia span { display: inline-block; margin-right: 10px; }
</style>
""")
    out.append("""
<style>
#interacciones-recientes .alertas-dia { margin: 8px 0 18px 0; }
#interacciones-recientes .alertas-dia ul { margin: 0 0 0 18px; padding: 0; }
#interacciones-recientes .alerta-item { color: #b45309; }
</style>
""")
    # JS: mostrar/ocultar contenedores + ver m├ís por d├¡a
    out.append("""
<script>
(function(){
    function showDay(dateStr){
        var all = document.querySelectorAll('#interacciones-recientes .day-content');
        all.forEach(function(el){ el.style.display = 'none'; });
        var el = document.getElementById('content-' + dateStr);
        if(el){
            el.style.display = 'block';
            // Reencuadrar el mapa del d├¡a mostrado (Leaflet necesita invalidateSize en contenedores que estaban ocultos)
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

    // Ver m├ís: revela 10 filas ocultas por click
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

    // Delegaci├│n: bot├│n de pantalla completa en mapas diarios
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
            // Entrar a pseudo pantalla completa
            wrap.setAttribute('data-prev-scroll', String(window.scrollY||0));
            mapEl.setAttribute('data-prev-height', mapEl.style.height || '');
            // Estilos para overlay
            wrap.style.position = 'fixed';
            wrap.style.inset = '0';
            wrap.style.zIndex = '9999';
            mapEl.style.height = '100%';
            document.body.style.overflow = 'hidden';
        } else {
            // Salir
            var prevH = mapEl.getAttribute('data-prev-height') || '';
            mapEl.style.height = prevH;
            wrap.style.position = 'relative';
            wrap.style.inset = '';
            wrap.style.zIndex = '';
            document.body.style.overflow = '';
            var sy = parseInt(wrap.getAttribute('data-prev-scroll')||'0',10) || 0;
            window.scrollTo(0, sy);
        }
        // Recalcular mapa
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
""")

    out.append('</section>')
    return "".join(out)
def _construir_seccion_todos_contactos(df, columnas_config=None):
    """Wrapper de compatibilidad - usa tz_core.analytics.construir_seccion_todos_contactos"""
    from tz_core.analytics import construir_seccion_todos_contactos as contactos_modular
    return contactos_modular(df, columnas_config)


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

def generar_informe_html(
    df: pd.DataFrame,
    archivo_kml: str,
    carpeta_salida: str,
    nombre_salida: str,
    hoja: str | None = None,
    nombre_bitacora: str | None = None,
    config: dict | None = None,
    override_tops: dict | None = None,
    html_seccion_interacciones: str | None = None,
    html_seccion_todos_contactos: str | None = None,
    logger=None,
) -> str:
    """
    Genera un informe HTML sencillo (portada + KPIs + enlaces) en la misma carpeta del KML.
    Retorna la ruta del HTML generado.
    """
    _log = logger if logger else print
    # Validación defensiva de entrada
    if df is None:
        _log("[ERROR] generar_informe_html: DataFrame es None, abortando")
        return ""
    if df.empty:
        _log("[WARN] generar_informe_html: DataFrame vacío, generando reporte mínimo")
        # Continuar para crear archivo con mensaje de ausencia de datos
    
    from datetime import datetime
    
    metrics = prepare_report_metrics(
        df, archivo_kml, carpeta_salida,
        config if config is not None else None,
    )
    kml_name = metrics["kml_name"]
    kmz_name = metrics["kmz_name"]
    kml_href = metrics["kml_href"]
    kmz_link = metrics["kmz_link"]
    kmz_abs = metrics["kmz_abs"]
    total = metrics["total"]
    coord_validas = metrics["coord_validas"]
    coord_invalidas = metrics["coord_invalidas"]
    ant_uniq = metrics["ant_uniq"]
    top_antena = metrics["top_antena"]
    top_count = metrics["top_count"]
    top_pct = metrics["top_pct"]
    cel_uniq = metrics["cel_uniq"]
    cel_label = metrics["cel_label"]
    rango_str = metrics["rango_str"]
    theme_hex = metrics["theme_hex"]
    gen_dt = metrics["gen_dt"]

    # --- Identificación del número analizado (delegada a tz_core.html_generator) ---
    ident_rows = build_identification_rows(
        df,
        config if config is not None else None,
    )


    # --- Top contactos (delegado a tz_core.html_generator) ---
    overrides_ctx = (
        override_tops
        if override_tops is not None
        else None
    )
    top_contactos_cnt_html, top_contactos_dur_html, _topC = build_top_contacts_sections(
        df,
        config if config is not None else None,
        overrides_ctx,
    )


    # HTML (sencillo, sin frameworks)
    html_path = os.path.join(carpeta_salida, f"{nombre_salida}_informe.html")
    # --- Top antenas (tabla) ---
    top_tab_html = build_antennas_table(
        df, config if config is not None else None
    )


    # === TOPC (para títulos "Top N" en HTML) ===
    try:
        if override_tops is not None and override_tops.get('contactos'):
            _topC = int(override_tops.get('contactos'))
        elif config is not None:
            _topC = int(config.get("html", {}).get("top_contactos_n", 10))
        else:
            _topC = 10
    except Exception:
        _topC = 10

    logo_html = build_logo_html(
        config if config is not None else None
    )

    html_header = generate_html_header(theme_hex, nombre_salida)
    body_header = generate_body_header(logo_html, nombre_salida, hoja, gen_dt, config)
    metadata_section = generate_metadata_section(nombre_bitacora, hoja, rango_str, ident_rows)
    kpi_section = generate_kpi_section(total, coord_validas, coord_invalidas, ant_uniq, cel_uniq, cel_label, top_antena, top_count, top_pct)
    
    html = f"""{html_header}
{body_header}

{metadata_section}

{kpi_section}

    <section>
    <h2>Top antenas</h2>
    {top_tab_html}
  </section>
  
    <section>
    <h2>Contactos con más comunicación</h2>
    <p class="nota"><b>Nota:</b> en esta sección se muestran dos TOP LIST de los principales contactos con los que registra mayor interacciones tanto entrantes como salientes. el primer top list se construyo a partir del recuento de las interacciones tanto salietes como entrantes; el segundo se construyo a partir de los contactos con los que acumula más minutos tanto en interaciones entrantes como salientes. Le servirá para detectar patrones en la comunicación del número analizado.</p>
    <div class="two">
      <div>
        <h3 class="small">Top List por recuento de interacciones <span class="sub">(Top {_topC})</span></h3>
        {top_contactos_cnt_html}
      </div>
      <div>
        <h3 class="small">Top List por recuento de minutos acumulados <span class="sub">(Top {_topC})</span></h3>
        {top_contactos_dur_html}
      </div>
    </div>
  </section>

</body>
</html>
"""
    # --- TÍTULO H1 desde config.brand (name + version) ---
    try:
        _brand = config.get("brand", {}) if isinstance(config, dict) else {}
        _bname = str(_brand.get("name", "")).strip()
        _bver  = str(_brand.get("version", "")).strip()
        if _bname and _bver:
            _title = f"{_bname} — {_bver}"
        elif _bname:
            _title = _bname
        elif _bver:
            _title = _bver
        else:
            _title = ""
        _h1 = f'<h1 class="title">{_title}</h1>' if _title else ""
    except Exception:
        _h1 = ""

    # Índice de navegación: delegar en helper centralizado
    html = apply_toc(html)

    # === HTML-BRANDING-1: Marca de agua (usa config.branding) ===
    try:
        _br = (config or {}).get("branding", {}) if config is not None else {}
        _mw_on   = bool(_br.get("mostrar_marca_agua", True))
        _mw_txt  = str(_br.get("marca_agua_texto", "CONFIDENCIAL"))
        _mw_opac = float(_br.get("marca_agua_opacidad", 0.08))
        _mw_print= bool(_br.get("marca_agua_en_impresion", True))

        if _mw_on and _mw_txt:
            _css_wm = f"""
.wm{{position:fixed;top:40%;left:50%;transform:translate(-50%,-50%) rotate(-28deg);color:#000;opacity:{_mw_opac};font-size:72px;font-weight:800;letter-spacing:.15em;white-space:nowrap;pointer-events:none;user-select:none;z-index:0}}
@media print{{ .wm{{display:{'block' if _mw_print else 'none'};position:fixed}} }}
"""
            # inyectar CSS en <style>
            html = html.replace("</style>", _css_wm + "</style>", 1)
            # insertar la marca de agua después del </header>
            html = html.replace("</header>", "</header>\n  " + f"<div class='wm'>{_mw_txt}</div>", 1)
    except Exception:
        pass

    # === HTML-INTERACCIONES-1: sección Interacciones recientes (dropdown por día) ===
    try:
        # Preferir la sección ya generada por produce_case_outputs; si no existe, construirla aquí.
        sec_inter = (html_seccion_interacciones or "").strip()

        if not sec_inter:
            cfg_html = config.get("html", {}) if (config is not None) else {}
            cfg_cols = config.get("columnas", {}) if (config is not None) else {}
            try:
                dias_cfg = int(cfg_html.get("interacciones_ultimos_dias", 3))
            except Exception:
                dias_cfg = 3
            sec_inter = construir_seccion_interacciones(df, dias_cfg, cfg_cols, config=config, logger=_log)

        if sec_inter:
            anchor = "<h2>Indicadores</h2>"
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_inter + html[j+10:]
                else:
                    html += sec_inter
            else:
                html += sec_inter
    except Exception:
        pass

    # === HTML-CONTACTOS-ALL-1: sección Todos los contactos ===
    try:
        sec_todos = (html_seccion_todos_contactos or "").strip()

        if not sec_todos:
            cfg_cols = config.get("columnas", {}) if (config is not None) else {}
            sec_todos = _construir_seccion_todos_contactos(df, cfg_cols)

        if sec_todos:
            anchor = '<h2 id="interacciones">Contactos con más comunicación</h2>'
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_todos + html[j+10:]
                else:
                    html += sec_todos
            else:
                html += sec_todos
    except Exception:
        pass

    # === HTML-ANTENAS-SIMPLE-1: sección Top antenas (delegada al helper) ===
    try:
        sec_ant = build_top_antennas_section(
            df,
            config,
            override_tops,
        )

        if sec_ant:
            anchor = "<h2>Indicadores</h2>"
            i = html.find(anchor)
            if i != -1:
                j = html.find("</section>", i)
                if j != -1:
                    html = html[:j+10] + "\n" + sec_ant + html[j+10:]
                else:
                    html += sec_ant
            else:
                html += sec_ant

    except Exception:
        pass

    # REORDENAR-SECCIONES-1: mover “Top antenas” al final y renombrar
    try:
        _hdr = "<h2>Top antenas</h2>"
        pos = html.find(_hdr)
        if pos != -1:
            ini = html.rfind("<section", 0, pos)
            fin = html.find("</section>", pos)
            if ini != -1 and fin != -1:
                bloque = html[ini:fin+10]
                # renombrar encabezado
                bloque = bloque.replace(
                    "<h2>Top antenas</h2>",
                    "<h2>Todas las antenas que ha activado en el período analizado</h2>"
                )
                # agregar nota explicativa después del h2
                bloque = bloque.replace(
                    "<h2>Todas las antenas que ha activado en el período analizado</h2>",
                    '<h2>Todas las antenas que ha activado en el período analizado</h2><div style="font-size:13px; color:#444; margin-bottom:8px;">Esta lista muestra todas las antenas que el usuario del número analizado ha activado durante el período analizado. Cada registro corresponde a una antena donde se ha detectado actividad, sin importar la frecuencia o duración de la conexión.</div><p class="nota"><b>Nota:</b> Si desea verificar la ubicación de una antena, puede hacer clic en el nombre para abrir su posición en Google Maps.</p>'
                )
                # quitar del lugar original
                html = html[:ini] + html[fin+10:]
                # insertar al final (antes de </body>)
                if "</body>" in html:
                    html = html.replace("</body>", bloque + "\n</body>")
                else:
                    html += bloque
    except Exception:
        pass

    # --- REORDENAR-SECCIONES-1: deja "Top antenas" después de "Indicadores"
    #     y manda "Todas las antenas..." hasta el final, ANTES de escribir el archivo.
    try:
        # Columnas y validadores reutilizados por heatmap/rangos
        def _pick_col(_df, candidatos):
            """Selecciona y retorna la primera columna existente de una lista de candidatas."""
            for c in candidatos:
                if c in _df.columns:
                    return c
            return None

        col_ant = _pick_col(df, ["antena", "nombre_antena", "cell_name"])
        col_lat = _pick_col(df, ["lat", "latitud", "latitude"])
        col_lon = _pick_col(df, ["long", "lon", "longitud", "lng", "longitude"])
        col_az  = _pick_col(df, ["azimut", "azimuth", "azi", "angulo"])

        try:
            _bbox = config.get("geografia", {}).get("sv_bbox", None) if (config is not None) else None
        except Exception:
            _bbox = None
        if not (isinstance(_bbox, dict) and all(k in _bbox for k in ("lat_min","lat_max","lon_min","lon_max"))):
            _bbox = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

        def _valid_latlon(lt, lg):
            """Valida si coordenadas lat/lon son válidas y dentro del bbox configurado."""
            try:
                lt = float(lt); lg = float(lg)
                if np.isnan(lt) or np.isnan(lg):
                    return False
                if abs(lt) < 1e-9 and abs(lg) < 1e-9:
                    return False
                return (_bbox["lat_min"] <= lt <= _bbox["lat_max"]) and (_bbox["lon_min"] <= lg <= _bbox["lon_max"])
            except Exception:
                return False

        # === HTML-ANTENAS-RANGOS-1: Antenas por rango horario (debajo del Top antenas) ===
        # Además, prepararemos la nueva sección de "Mapa de calor de actividad" (heatmap)
        # para insertarla entre "Antenas más activadas" y "Contactos con más comunicación".
        sec_ant_rangos = ""
        sec_heatmap = ""
        sec_recientes = ""
        try:
            sec_ant_rangos = build_antennas_by_hour_section(
                df,
                config,
                override_tops,
            )
        except Exception:
            sec_ant_rangos = ""

        # === HTML-HISTORIAL-CAMBIOS-1: Generar bloque de Historial de cambios de antena ===
        sec_historial = ""
        try:
            saltos = generar_historial_cambios_antena(df, max_saltos=100)
            if saltos:
                out = []
                out.append('<section id="historial-cambios">')
                out.append('<h2>Historial de cambios de antena</h2>')
                out.append('<p class="nota"><b>Nota:</b> Esta tabla muestra los cambios de antena detectados en orden cronológico. Cada fila representa un momento en que el dispositivo cambió de una antena a otra.</p>')
                out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
                out.append('<thead><tr>'
                          '<th>#</th>'
                          '<th>Fecha y Hora</th>'
                          '<th>Antena Origen</th>'
                          '<th>Antena Destino</th>'
                          '<th>Distancia (km)</th>'
                          '</tr></thead><tbody>')
                
                for idx, salto in enumerate(saltos, start=1):
                    ts_str = salto['timestamp'].strftime('%d/%m/%Y %H:%M:%S') if salto['timestamp'] else '—'
                    origen = salto['origen']
                    destino = salto['destino']
                    
                    # Formato distancia
                    if salto['distancia_km'] is not None:
                        dist_str = f"{salto['distancia_km']:.2f}"
                    else:
                        dist_str = '—'
                    
                    out.append('<tr>'
                              f'<td>{idx}</td>'
                              f'<td>{ts_str}</td>'
                              f'<td>{origen}</td>'
                              f'<td>{destino}</td>'
                              f'<td>{dist_str}</td>'
                              '</tr>')
                
                out.append('</tbody></table></div>')
                out.append("""
<style>
#historial-cambios .tabla-compacta { border-collapse: collapse; width:100%; font-size:0.95rem; }
#historial-cambios .tabla-compacta th, #historial-cambios .tabla-compacta td { border:1px solid #ddd; padding:6px 8px; text-align:left; }
#historial-cambios .tabla-compacta th { background:#f2f2f2; font-weight:600; }
#historial-cambios .tabla-scroll { overflow-x:auto; }
</style>
""")
                out.append('</section>')
                sec_historial = "\n".join(out)
                _log(f"[DEBUG] Historial de cambios: {len(saltos)} saltos detectados")
        except Exception as e:
            _log(f"[WARNING] Error generando historial de cambios: {e}")
            sec_historial = ""

        # === HTML-HEATMAP-1: Generar bloque de Mapa de Calor de actividad ===
        # Contrato de datos: puntos [lat, lon, weight] donde weight se normaliza (0..1) por
        # la frecuencia de activaciones (conteo por coordenada redondeada). Este bloque es
        # autónomo y se insertará entre el resumen de antenas y el bloque de contactos.
        # MEJORA: Incluye marcadores (pines) de las antenas Top N para hacerlo más comprensible.
        try:
            if col_lat and col_lon and (col_lat in df.columns) and (col_lon in df.columns):
                import json as _json
                _tmp = df.copy()
                _tmp["_lat"] = pd.to_numeric(_tmp.get(col_lat, pd.Series(dtype=float)), errors="coerce")
                _tmp["_lon"] = pd.to_numeric(_tmp.get(col_lon, pd.Series(dtype=float)), errors="coerce")
                _valid = (
                    _tmp["_lat"].between(-90, 90) &
                    _tmp["_lon"].between(-180, 180) &
                    ~((_tmp["_lat"].abs() < 1e-9) & (_tmp["_lon"].abs() < 1e-9))
                )
                _geo = _tmp.loc[_valid, ["_lat", "_lon"]]
                # Agrupar por coord redondeada para evitar duplicados excesivos
                if not _geo.empty:
                    _geo["_latr"] = _geo["_lat"].round(5)
                    _geo["_lonr"] = _geo["_lon"].round(5)
                    _grp = _geo.groupby(["_latr", "_lonr"]).size().reset_index(name="cnt").sort_values("cnt", ascending=False)
                    # Cap en cantidad de puntos para tamaño de HTML (ej. top 1500)
                    _grp = _grp.head(1500)
                    _max = float(_grp["cnt"].max()) if not _grp.empty else 0.0
                    heat_points = []
                    if _max > 0:
                        for _, rr in _grp.iterrows():
                            w = float(rr["cnt"]) / _max
                            heat_points.append([float(rr["_latr"]), float(rr["_lonr"]), round(w, 4)])
                    
                    # NUEVO: Preparar marcadores de antenas Top N (mismo criterio que sec_ant)
                    markers_data = []
                    if col_ant and (col_ant in df.columns):
                        try:
                            # Obtener top_N del config (respeta overrides) con default 5
                            _topN_markers = resolve_top_antennas_n(
                                config,
                                override_tops,
                                default=5,
                            )
                            
                            _dfv = df.copy()
                            _dfv[col_ant] = _dfv[col_ant].astype(str).str.strip()
                            _dfv = _dfv[_dfv[col_ant].notna() & (_dfv[col_ant] != "") & (_dfv[col_ant] != "0")]
                            if (col_lat in _dfv.columns) and (col_lon in _dfv.columns):
                                _dfv = _dfv[_dfv.apply(lambda r: _valid_latlon(r[col_lat], r[col_lon]), axis=1)]
                            
                            if not _dfv.empty:
                                _top = (_dfv.groupby(col_ant)
                                        .size()
                                        .reset_index(name="activaciones")
                                        .sort_values("activaciones", ascending=False))
                                if int(_topN_markers) > 0:
                                    _top = _top.head(int(_topN_markers))
                                
                                for _, _r in _top.iterrows():
                                    _ant = str(_r[col_ant])
                                    _sub = _dfv[_dfv[col_ant] == _ant]
                                    _lt = float(_sub[col_lat].astype(float).mean()) if (col_lat in _sub.columns) else None
                                    _lg = float(_sub[col_lon].astype(float).mean()) if (col_lon in _sub.columns) else None
                                    _act = int(_r["activaciones"])
                                    
                                    # Extraer azimuts únicos si existen
                                    _azimuts = []
                                    if col_az and (col_az in _sub.columns):
                                        try:
                                            _az_vals = (_sub[col_az].astype(str).str.strip()
                                                       .replace({"": np.nan, "nan": np.nan})
                                                       .dropna()
                                                       .apply(lambda x: int(float(x))))
                                            _az_counts = _az_vals.value_counts().sort_values(ascending=False)
                                            _azimuts = [{"deg": int(k), "n": int(v)} for k, v in _az_counts.items()]
                                        except Exception:
                                            pass
                                    
                                    if (_lt is not None) and (_lg is not None):
                                        markers_data.append({
                                            "lat": round(_lt, 6),
                                            "lon": round(_lg, 6),
                                            "name": _ant,
                                            "count": _act,
                                            "azimuts": _azimuts
                                        })
                        except Exception:
                            pass
                    
                    # Si no hay puntos suficientes, omitimos la sección
                    if heat_points:
                        _heat_js = _json.dumps(heat_points, ensure_ascii=False)
                        _markers_js = _json.dumps(markers_data, ensure_ascii=False)
                        # Sección integrada al bloque de "Antenas más activadas":
                        # sin H2 ni nota, para que el mapa se perciba como parte del resumen de antenas.
                        sec_heatmap = f"""
<section id=\"heatmap-actividad\">
    <!-- Nota informativa: este mapa forma parte de "Antenas más activadas" -->
    <p class=\"nota\">Nota: Recomendación: para mejorar la visualización del mapa desde un celular, hágalo con la pantalla horizontal; al hacer clic en un punto de la antena se desplegará la información y se habilitará el azimut.</p>
    <div id=\"wrap-heatmap\" class=\"tz-map-wrap\" style=\"position:relative; margin:0 40px;\">
            <button class=\"tz-fs-btn\" title=\"Pantalla completa\" data-map-id=\"heatmap\" style=\"position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;\">⛶</button>\n        <div id=\"heatmap\" style=\"height:560px; border:1px solid #ddd; border-radius:8px; overflow:hidden;\"></div>
    </div>

  <script>
    (function() {{
      const heatData = { _heat_js };
      const markers = { _markers_js };
      if (!Array.isArray(heatData) || heatData.length === 0) return;
      
      const map = L.map('heatmap', {{ scrollWheelZoom: false }});
      const tiles = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap'
      }}).addTo(map);
      
                    // === Utilidades para dibujar la orientación (azimut principal) ===
                    const AZ_COLOR = '#e74c3c';
                    const AZ_LINE_LEN_M = 1500;      // longitud de la flecha
                    const AZ_LINE_WEIGHT = 5;         // grosor de la línea del azimut
                    const AZ_CONE_HALF_DEG = 30;      // medio ángulo del cono (±30°)
                    const AZ_CONE_STEPS = 24;         // discretización del arco
            // Convertir grados a radianes
            const toRad = d => d * Math.PI / 180;
            // Convertir radianes a grados
            const toDeg = r => r * 180 / Math.PI;
            // Calcula un punto destino a partir de lat, lon, rumbo (grados) y distancia (m)
            function destinationPoint(lat, lon, bearingDeg, distanceM) {{
                const R = 6371000; // radio medio de la Tierra, en metros
                const δ = distanceM / R;
                const θ = toRad(bearingDeg);
                const φ1 = toRad(lat);
                const λ1 = toRad(lon);
                const sinφ1 = Math.sin(φ1), cosφ1 = Math.cos(φ1);
                const sinδ = Math.sin(δ), cosδ = Math.cos(δ);
                const sinφ2 = sinφ1 * cosδ + cosφ1 * sinδ * Math.cos(θ);
                const φ2 = Math.asin(sinφ2);
                const y = Math.sin(θ) * sinδ * cosφ1;
                const x = cosδ - sinφ1 * sinφ2;
                const λ2 = λ1 + Math.atan2(y, x);
                return [toDeg(φ2), ((toDeg(λ2) + 540) % 360) - 180]; // normaliza longitud a [-180,180]
            }}
            // Selecciona el azimut principal: mayor 'n'; si empata, el menor grado
            function principalAzimut(azimuts) {{
                if (!Array.isArray(azimuts) || azimuts.length === 0) return null;
                let best = null;
                azimuts.forEach(a => {{
                    const n = (a && typeof a.n === 'number') ? a.n : 0;
                    const d = (a && typeof a.deg === 'number') ? a.deg : null;
                    if (d === null) return;
                    if (!best || n > best.n || (n === best.n && d < best.deg)) best = {{ deg: d, n }};
                }});
                return best ? best.deg : null;
            }}
                    // Construye un polígono en forma de cono desde el punto de origen
                    function buildCone(lat, lon, bearingDeg, halfDeg, radiusM, steps) {{
                        const pts = [];
                        pts.push([lat, lon]);
                        const start = bearingDeg - halfDeg;
                        const end = bearingDeg + halfDeg;
                        const cnt = Math.max(3, steps|0);
                        for (let i = 0; i <= cnt; i++) {{
                            const b = start + (i * (end - start) / cnt);
                            pts.push(destinationPoint(lat, lon, b, radiusM));
                        }}
                        pts.push([lat, lon]);
                        return pts;
                    }}
                    let currentAzLine = null; // polyline activo del último popup
                    let currentAzCone = null; // polígono del cono activo

      // Agregar capa de calor
      const latlngs = heatData.map(p => [p[0], p[1]]);
      const bounds = L.latLngBounds(latlngs);
      try {{ map.fitBounds(bounds.pad(0.15)); }} catch(e) {{ map.setView(latlngs[0], 12); }}
      L.heatLayer(heatData, {{ radius: 22, blur: 18, maxZoom: 16, minOpacity: 0.3 }}).addTo(map);
      
      // Agregar marcadores de antenas Top N
      if (Array.isArray(markers) && markers.length > 0) {{
        markers.forEach((m, idx) => {{
          const marker = L.marker([m.lat, m.lon], {{
            title: m.name
          }}).addTo(map);
          
          // Construir popup con información completa
          let popupContent = `<div style="font-family:sans-serif; font-size:13px;">`;
          popupContent += `<strong style="font-size:14px;">${{m.name}}</strong><br>`;
          popupContent += `<span style="color:#666;">Activaciones: ${{m.count.toLocaleString()}}</span><br>`;
                    popupContent += `<span style="color:#666;">Coordenadas: ${{m.lat.toFixed(6)}}, ${{m.lon.toFixed(6)}}</span>`;
          
          // Agregar azimuts si existen
                                if (m.azimuts && m.azimuts.length > 0) {{
                                    m.azimuts.forEach(a => {{
                                        popupContent += `<br><span style=\"color:#666;\">Azimut ${{a.deg}}°</span>`;
                                    }});
                                }}
          
          popupContent += `</div>`;
          marker.bindPopup(popupContent);

                                // Dibuja la flecha y el cono del azimut principal al abrir el popup; limpia al cerrar
                    marker.on('popupopen', () => {{
                                    if (currentAzLine) {{ try {{ map.removeLayer(currentAzLine); }} catch(e) {{}} currentAzLine = null; }}
                                    if (currentAzCone) {{ try {{ map.removeLayer(currentAzCone); }} catch(e) {{}} currentAzCone = null; }}
                        const bearing = principalAzimut(m.azimuts);
                        if (typeof bearing === 'number' && isFinite(bearing)) {{
                            const p1 = [m.lat, m.lon];
                                        const p2 = destinationPoint(m.lat, m.lon, bearing, AZ_LINE_LEN_M);
                                        currentAzLine = L.polyline([p1, p2], {{ color: AZ_COLOR, weight: AZ_LINE_WEIGHT, opacity: 1.0 }}).addTo(map);
                                        const conePts = buildCone(m.lat, m.lon, bearing, AZ_CONE_HALF_DEG, AZ_LINE_LEN_M, AZ_CONE_STEPS);
                                        currentAzCone = L.polygon(conePts, {{ color: AZ_COLOR, weight: 1, opacity: 0.9, fillColor: AZ_COLOR, fillOpacity: 0.18 }}).addTo(map);
                        }}
                    }});
                    marker.on('popupclose', () => {{
                                    if (currentAzLine) {{ try {{ map.removeLayer(currentAzLine); }} catch(e) {{}} currentAzLine = null; }}
                                    if (currentAzCone) {{ try {{ map.removeLayer(currentAzCone); }} catch(e) {{}} currentAzCone = null; }}
                    }});
        }});
      }}
      // Registrar mapa global para fullscreen
      try {{
        window.__tzDailyMaps = window.__tzDailyMaps || {{}};
        window.__tzDailyMaps['heatmap'] = {{
          map: map,
          bounds: bounds,
          markersCount: (Array.isArray(markers) && markers.length>0) ? markers.length : latlngs.length,
          center: bounds.getCenter(),
          wrapperId: 'wrap-heatmap'
        }};
      }} catch(e) {{}}
    }})();
  </script>
</section>
"""
                        _log(f"[DEBUG] Heatmap: {len(sec_heatmap)} chars, puntos={len(heat_points)}")
        except Exception:
            sec_heatmap = ""

        # 1) Mover "Top antenas" inmediatamente después de "Indicadores" (si aún no lo está)
        idx_ind = html.find("<h2>Indicadores</h2>")
        idx_top = html.find("<h2>Top antenas</h2>")
        if idx_ind != -1 and idx_top != -1 and idx_top < idx_ind:
            fin_top = html.find("</section>", idx_top)
            bloque_top = html[idx_top: fin_top + 10]  # incluye </section>
            # quita el bloque de donde estaba
            html = html[:idx_top] + html[fin_top + 10:]
            # inserta justo después de la sección "Indicadores"
            fin_ind = html.find("</section>", idx_ind)
            html = html[:fin_ind + 10] + "\n  " + bloque_top + "\n  " + html[fin_ind + 10:]

                # REORDENAR-SECCIONES-2: mover "<h2>Contactos con más comunicación" debajo de "Antenas más activadas"
        try:
            # 2A) Insertar primero el HEATMAP (si existe) y luego mover
            #     el bloque "Contactos con más comunicación" inmediatamente
            #     después del heatmap. Si no hay heatmap, va debajo del resumen.
            hdr_resumen = "<h2>Antenas más activadas"
            idx_res = html.find(hdr_resumen)
            if idx_res != -1:
                # localizar bloque de "<h2>Contactos con más comunicación"
                # primero busca con id, si no, por el H2 plano
                idx_int = html.find('id="interacciones"')
                if idx_int == -1:
                    idx_int = html.find("<h2>Contactos con más comunicación")
                if idx_int != -1:
                    ini_int = html.rfind("<section", 0, idx_int)
                    fin_int = html.find("</section>", idx_int)
                    if ini_int != -1 and fin_int != -1:
                        bloque_int = html[ini_int:fin_int+10]
                        # quitar del lugar original
                        html = html[:ini_int] + html[fin_int+10:]
                        # 2A.1) Insertar HEATMAP justo después del resumen (si lo tenemos)
                        fin_res = html.find("</section>", idx_res)
                        insert_pos = fin_res + 10 if fin_res != -1 else -1

                        # Insertar heatmap primero (si existe)
                        if fin_res != -1 and sec_heatmap:
                            html = html[:fin_res+10] + "\n" + sec_heatmap + html[fin_res+10:]
                            idx_hm = html.find('id="heatmap-actividad"', fin_res)
                            if idx_hm != -1:
                                fin_hm = html.find("</section>", idx_hm)
                                if fin_hm != -1:
                                    insert_pos = fin_hm + 10

                        # Finalmente insertar el bloque de contactos (interacciones)
                        if insert_pos != -1:
                            html = html[:insert_pos] + "\n" + bloque_int + html[insert_pos:]

            # 2B) Insertar "Antenas por rango horario" debajo de "Interacciones" (si existe); si no, debajo del resumen
            if sec_ant_rangos:
                # intentar ponerlo después del bloque de interacciones recién reubicado
                i_int = html.find('id="interacciones"')
                if i_int == -1:
                    i_int = html.find("<h2>Contactos con más comunicación")
                if i_int != -1:
                    j_int = html.find("</section>", i_int)
                    if j_int != -1:
                        html = html[:j_int+10] + "\n" + sec_ant_rangos + html[j_int+10:]
                else:
                    # fallback: debajo de "Antenas más activadas"
                    i = html.find(hdr_resumen)
                    if i != -1:
                        j = html.find("</section>", i)
                        if j != -1:
                            html = html[:j+10] + "\n" + sec_ant_rangos + html[j+10:]
                    else:
                        # si no hay ninguna de las dos, mándalo al final
                        if "</body>" in html:
                            html = html.replace("</body>", sec_ant_rangos + "\n</body>")
                        else:
                            html += sec_ant_rangos

            # 2C) Insertar "Historial de cambios de antena" debajo de "Antenas por rango horario" (si existe)
            if sec_historial:
                # intentar ponerlo después del bloque de antenas por rango
                i_rangos = html.find('id="antenas-rangos"')
                if i_rangos != -1:
                    j_rangos = html.find("</section>", i_rangos)
                    if j_rangos != -1:
                        html = html[:j_rangos+10] + "\n" + sec_historial + html[j_rangos+10:]
                else:
                    # fallback: después de interacciones
                    i_int = html.find('id="interacciones"')
                    if i_int == -1:
                        i_int = html.find("<h2>Contactos con más comunicación")
                    if i_int != -1:
                        j_int = html.find("</section>", i_int)
                        if j_int != -1:
                            html = html[:j_int+10] + "\n" + sec_historial + html[j_int+10:]
                    else:
                        # último fallback: al final
                        if "</body>" in html:
                            html = html.replace("</body>", sec_historial + "\n</body>")
                        else:
                            html += sec_historial
        except Exception:
            pass

        # REORDENAR-SECCIONES-3: enviar "Todos los contactos" al final del documento
        try:
            idx_tc = html.find('id="todos-contactos"')
            if idx_tc != -1:
                ini_tc = html.rfind("<section", 0, idx_tc)
                fin_tc = html.find("</section>", idx_tc)
                if ini_tc != -1 and fin_tc != -1:
                    bloque_tc = html[ini_tc:fin_tc+10]
                    # quitar del lugar original
                    html = html[:ini_tc] + html[fin_tc+10:]
                    # insertarlo ANTES de </body> (última sección)
                    if "</body>" in html:
                        html = html.replace("</body>", bloque_tc + "\n</body>", 1)
                        # === JS: Auto-agregar correlativo (#) a tablas que NO lo tengan ===
                        _js_autonum = """
                        <script>
                        (function() {
                        try {
                            var tables = document.querySelectorAll('section table');
                            tables.forEach(function(t) {
                            // ¿Ya está marcado con índice? (o ya tiene '#' primero)
                            var thFirst = t.querySelector('thead tr th:first-child') || t.querySelector('tr:first-child th:first-child');
                            var hasHash = thFirst && thFirst.textContent && thFirst.textContent.trim() === '#';
                            if (t.classList.contains('has-index') || hasHash) {
                                // ya tienen índice (p.ej., Top antenas), solo asegurar clase para el CSS
                                if (!t.classList.contains('has-index')) t.classList.add('has-index');
                                return;
                            }

                            // 1) Insertar TH '#' al inicio del encabezado (crea THEAD si no hay)
                            var thead = t.querySelector('thead');
                            if (!thead) {
                                thead = document.createElement('thead');
                                var firstRow = t.querySelector('tr');
                                if (firstRow) {
                                var trHead = document.createElement('tr');
                                // Crear celdas de encabezado según número de columnas
                                var thAuto = document.createElement('th');
                                thAuto.textContent = '#';
                                trHead.appendChild(thAuto);
                                // Duplicar estructura de la primera fila como encabezado (vacío)
                                var cells = firstRow.children;
                                for (var i = 0; i < cells.length; i++) {
                                    var th = document.createElement('th');
                                    // si la primera fila ya es header, se respetará después
                                    trHead.appendChild(th);
                                }
                                thead.appendChild(trHead);
                                t.insertBefore(thead, t.firstChild);
                                }
                            } else {
                                // Hay thead: insertamos '#' como primera celda de la primera fila de encabezado
                                var tr0 = thead.querySelector('tr');
                                if (tr0) {
                                var thHash = document.createElement('th');
                                thHash.textContent = '#';
                                tr0.insertBefore(thHash, tr0.firstChild);
                                }
                            }

                            // 2) Numerar cuerpo: insertar TD (1..n) como primera celda en cada fila del tbody
                            var rows = t.querySelectorAll('tbody tr');
                            if (rows.length === 0) { rows = t.querySelectorAll('tr'); } // fallback si no hay tbody
                            var n = 1;
                            rows.forEach(function(r) {
                                var td = document.createElement('td');
                                td.textContent = String(n++);
                                // estilos mínimos para que no rompa
                                td.style.textAlign = 'center';
                                r.insertBefore(td, r.firstChild);
                            });

                            // 3) Marcar la tabla para que reciba el CSS de columna angosta
                            t.classList.add('has-index');
                            });
                        } catch(e) { /* silencioso */ }
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_autonum + "</body>", 1)
                        # === JS: ajustar offset según altura del header y hacer scroll con margen ===
                        _js_anchor = """
                        <script>
                        (function(){
                        try{
                            // 1) Medir header y setear --anchor-offset (con pequeño colchón)
                            var hdr = document.querySelector('header');
                            var offset = 96; // default
                            if (hdr){
                            var rect = hdr.getBoundingClientRect();
                            offset = Math.round(rect.height + 12); // colchón extra
                            }
                            document.documentElement.style.setProperty('--anchor-offset', offset + 'px');

                            // 2) Interceptar clics del TOC para asegurar scroll con offset (cross-browser)
                            var links = document.querySelectorAll('.toc a[href^="#"]');
                            links.forEach(function(a){
                            a.addEventListener('click', function(e){
                                e.preventDefault();
                                var id = this.getAttribute('href').slice(1);
                                var el = document.getElementById(id);
                                if (!el) return;

                                // Calcular posición considerando el offset
                                var y = el.getBoundingClientRect().top + window.pageYOffset - offset;

                                // Scroll suave; si no soporta, cae en instantáneo
                                window.scrollTo({ top: y, behavior: 'smooth' });

                                // Actualizar hash sin saltos “raros”
                                history.replaceState(null, '', '#' + id);
                            });
                            });

                            // 3) Si el usuario llega con hash en la URL, re-posicionar con offset
                            if (location.hash && document.getElementById(location.hash.slice(1))){
                            var target = document.getElementById(location.hash.slice(1));
                            var y = target.getBoundingClientRect().top + window.pageYOffset - offset;
                            window.scrollTo(0, y);
                            }
                        }catch(e){}
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_anchor + "</body>", 1)

                        # === JS: detectar pastillas claras y aplicar .need-contrast ===
                        _js_contrast = """
                        <script>
                        (function(){
                        try{
                            // Seleccionamos elementos "chip/pastilla" más comunes en el header/subtítulos
                            var sels = [
                            'header .badge','header .chip','header .pill','header .tag',
                            'header span','header a.badge','header a.chip','header a.pill','header a.tag'
                            ];
                            var nodes = document.querySelectorAll(sels.join(','));
                            var THRESH = 0.85; // luminancia: >0.85 lo consideramos "claro"

                            function parseRGB(s){
                            // soporta "rgb(r,g,b)" o "rgba(r,g,b,a)"
                            var m = s.match(/rgba?\\((\\d+),(\\d+),(\\d+)/i);
                            if(!m) return null;
                            return {r:+m[1], g:+m[2], b:+m[3]};
                            }
                            function relLum(c){
                            // WCAG relative luminance
                            function n(x){ x/=255; return (x<=0.03928)? x/12.92 : Math.pow((x+0.055)/1.055,2.4); }
                            var R=n(c.r), G=n(c.g), B=n(c.b);
                            return 0.2126*R + 0.7152*G + 0.0722*B;
                            }

                            nodes.forEach(function(el){
                            var cs = getComputedStyle(el);
                            // ignorar elementos sin color de fondo
                            var bg = cs.backgroundColor;
                            if(!bg || bg === 'transparent') return;
                            var rgb = parseRGB(bg);
                            if(!rgb) return;
                            var L = relLum(rgb);
                            if(L > THRESH){
                                el.classList.add('need-contrast'); // activa borde y texto oscuro
                            }
                            });
                        }catch(e){}
                        })();
                        </script>
                        """
                        html = html.replace("</body>", _js_contrast + "</body>", 1)

                        # === CSS: columna de correlativo (#) SOLO en tablas con .has-index — AJUSTE FINO (28px móvil) ===
                        _css_idx = """
                        <style>
                        /* Desktop / tablet: compacto (44px) */
                        .has-index th:first-child,
                        .has-index td:first-child {
                            text-align: center !important;
                            width: 44px;
                            min-width: 44px;
                            max-width: 44px;
                            padding-left: 4px;
                            padding-right: 4px;
                        }
                        /* Móvil vertical: ultra compacto (28px) */
                        @media (max-width: 640px) {
                            .has-index th:first-child,
                            .has-index td:first-child {
                            width: 28px;
                            min-width: 28px;
                            max-width: 28px;
                            font-size: 12px;
                            padding-left: 2px;
                            padding-right: 2px;
                            }
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_idx + "</style>", 1)
                        # === CSS OVERRIDE (header + menú) para contraste seguro ===
                        _css_hdr = """
                        <style>
                        /* Texto del header en gris oscuro (legible sobre fondo blanco) */
                        header, header * { color: #444 !important; }

                        /* Enlaces del menú (TOC) dentro del header: gris oscuro y con hover subrayado */
                        header nav a,
                        .toc a {
                            color: #444 !important;
                            text-decoration: none;
                        }
                        header nav a:hover,
                        .toc a:hover { text-decoration: underline; }

                        /* Pastillas/etiquetas del header: texto oscuro + contorno suave */
                        header .badge,
                        header .chip,
                        header .pill,
                        header .tag,
                        header span.badge,
                        header span.pill {
                            color: #111 !important;
                            box-shadow: inset 0 0 0 1px rgba(0,0,0,.28);
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_hdr + "</style>", 1)
                        # === CSS: TOC como botones azules con alto contraste ===
                        _css_tocbtn = """
                        <style>
                        /* Contenedor del TOC: filas envolventes y espacio entre botones */
                        .toc{
                            display: flex;
                            flex-wrap: wrap;
                            gap: 8px;
                            margin: 6px 0 10px;
                        }
                        /* Cada enlace del TOC luce como botón “pill” azul */
                        .toc a{
                            display: inline-block;
                            background: #0B57D0;             /* azul accesible */
                            color: #fff !important;           /* texto blanco, alto contraste */
                            padding: 6px 12px;
                            border-radius: 9999px;            /* pastilla */
                            border: 1px solid rgba(0,0,0,.15);
                            text-decoration: none !important;
                            font-weight: 500;
                            line-height: 1.1;
                            box-shadow: 0 1px 0 rgba(0,0,0,.06);
                            transition: filter .12s ease, transform .06s ease;
                        }
                        .toc a:hover{ filter: brightness(.92); }
                        .toc a:active{ transform: translateY(1px); }
                        .toc a:focus{
                            outline: 2px solid #003C99;       /* foco visible */
                            outline-offset: 2px;
                        }

                        /* Móvil: botones un poco más compactos */
                        @media (max-width: 640px){
                            .toc{ gap: 6px; }
                            .toc a{ padding: 5px 10px; font-size: 14px; }
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_tocbtn + "</style>", 1)
                        # === CSS: líneas/bordes para la tabla de "Todos los contactos" ===
                        _css_tc_lines = """
                        <style>
                        /* Solo afecta la sección con id="todos-contactos" */
                        #todos-contactos table{
                            width: 100%;
                            border-collapse: collapse;
                        }
                        #todos-contactos thead th{
                            background: #f7f7f7;
                            border-top: 1px solid #e6e6e6;
                            border-bottom: 1px solid #e6e6e6;
                        }
                        #todos-contactos tbody td{
                            border-bottom: 1px solid #eaeaea;
                        }
                        /* (Opcional) líneas verticales suaves como en otras tablas */
                        #todos-contactos th:not(:last-child),
                        #todos-contactos td:not(:last-child){
                            border-right: 1px solid #f0f0f0;
                        }
                        /* Hover sutil para lectura */
                        #todos-contactos tbody tr:hover{
                            background: #fafafa;
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_tc_lines + "</style>", 1)

                        # === CSS: margen para anclas y scroll suave ===
                        _css_anchor = """
                        <style>
                        :root { --anchor-offset: 96px; } /* valor seguro; JS lo ajusta a la altura real */
                        /* Cualquier sección con id (#meta, #antenas, #todos-contactos, etc.) dejará colchón arriba */
                        section[id] { scroll-margin-top: var(--anchor-offset); }

                        /* Scroll suave nativo (fallback con JS abajo) */
                        html { scroll-behavior: smooth; }
                        </style>
                        """
                        html = html.replace("</style>", _css_anchor + "</style>", 1)


                        # === CSS: contraste para pastillas claras ===
                        _css_contrast = """
                        <style>
                        .need-contrast{
                            /* contorno discreto para que destaque en fondo blanco */
                            box-shadow: inset 0 0 0 1px rgba(0,0,0,.28);
                            color: #111 !important;            /* texto oscuro para legibilidad */
                        }
                        </style>
                        """
                        html = html.replace("</style>", _css_contrast + "</style>", 1)


                    else:
                        html += bloque_tc
        except Exception:
            pass


        # REORDENAR-SECCIONES-3: asegurar "Todos los contactos" quede como última sección (antes del pie)
        try:
            idx_tc = html.find('<section id="todos-contactos">')
            if idx_tc != -1:
                ini_tc = html.rfind("<section", 0, idx_tc)
                fin_tc = html.find("</section>", idx_tc)
                if ini_tc != -1 and fin_tc != -1:
                    bloque_tc = html[ini_tc:fin_tc+10]
                    # quitar del lugar original
                    html = html.replace(bloque_tc, "")
                    # reinsertar al final del <body> (antes del pie legal)
                    html = html.replace("</body>", bloque_tc + "\n</body>")
        except Exception:
            pass

    except Exception:
        # si algo falla, no bloquees la generación del HTML
        pass

        # STICKY-HEADER-1: CSS adicional para que el encabezado de las tablas quede fijo al hacer scroll
    css_sticky = """
<style>
/* Encabezados fijos para tablas largas (más contraste) */
.tbl thead th,
.tabla-compacta thead th{
  position: sticky;
  top: 0;
  z-index: 2;
  background: #e9ecef !important;   /* gris más oscuro */
  color:#111;
  box-shadow: 0 1px 0 rgba(0,0,0,.16);
  background-clip: padding-box;
}
</style>

"""
    # Inyectar el CSS extra justo antes de cerrar el <body>
    html = html.replace("</body>", css_sticky + "\n</body>")

    # --- ESCRIBIR ARCHIVO ---

    # === HTML-BRANDING-2: Pie legal + byline (al FINAL del <body>) ===
    try:
        br = (config or {}).get("branding", {}) if config is not None else {}
        _pl_on   = bool(br.get("mostrar_pie_legal", True))
        _pl_txt  = str(br.get("pie_legal_texto", ""))
        _by_txt  = str(br.get("byline_texto", ""))
        _pl_prnt = bool(br.get("pie_legal_en_impresion", True))

        if _pl_on and (_pl_txt or _by_txt):
            # 1) CSS del pie (lo metemos en <head>)
            _disp = "block" if _pl_prnt else "none"
            _css_pl = f"""
            <style>
                .legal {{
                    margin-top:30px;
                    padding:10px 0;
                    border-top:1px solid #eee;
                    color:#666;
                    font-size:12px;
                    line-height:1.35;
                    text-align:center !important;
                }}
                .legal .legal-text {{
                    display:block;
                    text-align:center !important;
                }}
                .legal .by {{
                    float:none;
                    display:block;
                    margin-top:6px;
                    color:#444;
                    text-align:center !important;
                }}
                @media print {{
                    .legal {{ display:{_disp} }}
                }}
            </style>
            """



            html = html.replace("</style>", "</style>" + _css_pl, 1)

            # --- FOOTER legal + byline desde config.branding (robusto) ---
            try:
                _branding = config.get("branding", {}) if isinstance(config, dict) else {}
                _legal   = str(_branding.get("pie_legal_texto", "")).strip()
                _byline  = str(_branding.get("byline_texto", "")).strip()

                # Construir footer solo si hay algo que mostrar
                _footer_html = ""
                if _legal or _byline:
                    _by  = f'<span class="by" style="display:block;text-align:center">{_byline}</span>' if _byline else ""
                    # Eliminar cualquier mención de fecha o versión al final del pie legal
                    _legal_sin_fecha = re.sub(r'Generado.*?\d{2}/\d{2}/\d{4}.*?Versi[óo]n.*', '', _legal, flags=re.I)
                    _txt = f'<span class="legal-text">{_legal_sin_fecha.strip()}</span>' if _legal_sin_fecha.strip() else ""
                    _footer_html = (
                        f'<footer class="legal" style="text-align:center">'
                        f'<span class="legal-text" style="display:block;text-align:center">{_txt}</span>'
                        f'{_by}'
                        f'</footer>'
                    )


                    # 0) Eliminar cualquier footer previo (ambas comillas)
                    html = html.replace("<footer class='legal'>", "<footer class=\"legal\">")
                    html = html.replace('<footer class="legal">', "")

                    # 1) Insertar ANTES del cierre de </body> (posición segura)
                    _tag = "</body>"
                    _pos = html.rfind(_tag)
                    if _pos != -1:
                        html = html[:_pos] + _footer_html + _tag + html[_pos+len(_tag):]
                    else:
                        # 2) Si por alguna razón no hay </body>, lo agregamos al final
                        html += _footer_html
            except Exception:
                pass

    except Exception:
        pass

    # FORZAR-ULTIMO: mover "Todos los contactos" al final del documento (antes del footer si existe)
    try:
        idx_tc = html.find('id="todos-contactos"')
        if idx_tc != -1:
            ini_tc = html.rfind("<section", 0, idx_tc)
            fin_tc = html.find("</section>", idx_tc)
            if ini_tc != -1 and fin_tc != -1:
                bloque_tc = html[ini_tc:fin_tc+10]
                # quitar del lugar original
                html = html[:ini_tc] + html[fin_tc+10:]

                # Buscar CUALQUIER footer class="legal" con o sin atributos extra
                m = re.search(r"<footer\s+class=['\"]legal['\"][^>]*>", html, flags=re.I)
                foot_i = m.start() if m else -1


                if foot_i != -1:
                    # Insertar ANTES del footer (queda como última sección visible)
                    html = html[:foot_i] + bloque_tc + html[foot_i:]
                elif "</body>" in html:
                    # Fallback: justo antes de </body>
                    html = html.replace("</body>", bloque_tc + "\n</body>", 1)
                else:
                    # Último fallback: al final del documento
                    html += bloque_tc
    except Exception:
        pass


        # TOC-REFRESH: reconstruir índice final (orden objetivo) y reemplazar el anterior
    try:
        def _has(id_): 
            """Verifica si el HTML contiene un elemento con el ID especificado."""
            return f'id="{id_}"' in html

        _links = []
        if _has("meta"):
            _links.append('<a href="#meta">Metadatos</a>')
        if _has("resumen-antenas"):
            _links.append('<a href="#resumen-antenas">Antenas más activadas</a>')
        # Heatmap integrado en el resumen de antenas: no incluir enlace específico en el TOC.
        if _has("interacciones"):
            _links.append('<a href="#interacciones">Contactos con más comunicación</a>')
        # Rangos: aceptar cualquiera de los dos IDs posibles
        if _has("antenas-rangos") or _has("rangos"):
            _id_rangos = "antenas-rangos" if _has("antenas-rangos") else "rangos"
            _links.append(f'<a href="#{_id_rangos}">Antenas por rango horario</a>')
        if _has("historial-cambios"):
            _links.append('<a href="#historial-cambios">Historial de cambios de antena</a>')
        if _has("interacciones-recientes"):
            _links.append('<a href="#interacciones-recientes">Interacciones recientes</a>')
        if _has("top-antenas"):
            _links.append('<a href="#top-antenas">Todas las antenas</a>')
        if _has("todos-contactos"):
            _links.append('<a href="#todos-contactos">Todos los contactos</a>')

        if _links:
            _toc_html = '<nav id="toc" class="toc" style="z-index:999; background:#fff; border-bottom:1px solid #e5e7eb; box-shadow:0 2px 6px rgba(0,0,0,.06); padding:8px 12px;">' + ' ... '.join(_links) + '</nav>'
            # Si ya existe un TOC, reemplazarlo; si no, insertarlo después del </header>
            i = html.find('<nav id="toc"')
            if i != -1:
                j = html.find("</nav>", i)
                if j != -1:
                    html = html[:i] + _toc_html + html[j+6:]
            else:
                html = html.replace("</header>", "</header>\n  " + _toc_html, 1)
    except Exception:
        pass


    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    try:
        inject_technical_metadata(
            html_path,
            config if config is not None else None,
        )
    except Exception:
        pass

    # --- HASHES de salida: HTML, KML y KMZ (si existen) ---
    try:
        archivos = []
        # HTML recién generado
        if os.path.exists(html_path):
            archivos.append(("HTML", html_path))
        # KML (ruta absoluta recibida por parámetro)
        if archivo_kml and os.path.exists(archivo_kml):
            archivos.append(("KML", archivo_kml))
        # KMZ (si existe, en la ruta resuelta más arriba)
        try:
            if 'kmz_abs' in locals() and kmz_abs and os.path.exists(kmz_abs):
                archivos.append(("KMZ", kmz_abs))
        except Exception:
            pass

        if archivos:
            txt_hash = os.path.join(carpeta_salida, f"{nombre_salida}_hashes.txt")
            write_detailed_hashes_report(txt_hash, archivos)
            try:
                _log(f"[INFO] Hashes guardados en: {txt_hash}")
            except Exception:
                print(f"[INFO] Hashes guardados en: {txt_hash}")
    except Exception:
        # Nunca bloquear la generación por hashes
        pass


    return html_path

