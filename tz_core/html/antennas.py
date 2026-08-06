"""
Módulo para la generación de secciones HTML de antenas.

Contiene:
- resolve_top_antennas_n: Resuelve el Top N desde config/overrides
- build_antennas_table: Tabla completa de todas las antenas con coords y azimuts
- build_top_antennas_section: Sección HTML Top N de antenas más activadas
- build_antennas_by_hour_section: Sección HTML de antenas por rango horario
"""

import numpy as np
import pandas as pd

from tz_core.bitacora_normalization import parse_date_series, sanitize_latlon
from tz_core.dataframe_utils import pick_first_existing_column
from tz_core.logging_utils import log
from tz_core.time_utils import normalize_hour_to_hhmmss


NOTA_SITIOS_INFERIDOS = (
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


def _nota_sitios_inferidos_html() -> str:
    return f'<p class="nota nota-sitios-inferidos"><em>Nota:</em> {NOTA_SITIOS_INFERIDOS}</p>'


def _resolver_columna_antena(df: pd.DataFrame, *alias_adicionales: str) -> "str | None":
    """Resuelve la columna a usar como identidad de antena/sitio en HTML.

    Prioriza ``antena_analitica`` (HITO 2A): ya contiene la antena real
    cuando es significativa, o el identificador ``SITIO_<lat>_<long>``
    inferido por coordenadas cuando no la hay. Si no existe (la bitácora no
    pasó por el enriquecimiento del pipeline de ingesta), cae a la antena
    original / alias de compatibilidad, igual que antes de HITO 2A.
    """
    if "antena_analitica" in df.columns:
        return "antena_analitica"
    return pick_first_existing_column(df, list(alias_adicionales))


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
    """Construye tabla HTML de todas las antenas/sitios con coords, conteo y azimuts frecuentes.

    Usa ``antena_analitica`` (HITO 2A) cuando existe: antena real cuando es
    significativa, o el identificador ``SITIO_<lat>_<long>`` inferido por
    coordenadas cuando no la hay. La antena original nunca se descarta: sigue
    siendo la fuente de ``antena_analitica`` cuando es significativa.
    """
    top_tab_html = "<p class='nota'>Campo de antena no disponible en esta bitácora.</p>"
    col_ant = _resolver_columna_antena(df, "antena")
    if col_ant:
        df_a = df.copy()
        df_a[col_ant] = df_a.get(col_ant, "").astype(str).str.strip()
        _invalid_names = {"", "0", "null", "none", "nan", "sin inf", "sin inf.", "s/i"}
        df_a = df_a[~df_a[col_ant].str.lower().isin(_invalid_names)]

        if not df_a.empty:
            # timestamp (fecha + hora si existe)
            if "fecha" in df_a.columns:
                fechas = parse_date_series(df_a["fecha"], dayfirst=True).dt.normalize()
                if "hora" in df_a.columns:
                    horas = pd.to_timedelta(
                        df_a["hora"].astype(str).str[:8],
                        errors="coerce",
                    )
                    df_a["_ts"] = fechas + horas
                else:
                    df_a["_ts"] = pd.NaT
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

        tiene_col_inferido = "sitio_inferido" in df_a.columns

        # Construimos entradas y ordenamos por conteo (desc)
        entries = []
        hay_sitio_inferido = False
        for antenna, g in df_a.groupby(col_ant, dropna=False):
            cnt = int(len(g))
            lat_v = g["_lat"].dropna()
            lon_v = g["_lon"].dropna()
            lat_s = f"{lat_v.iloc[0]:.6f}" if not lat_v.empty else "—"
            lon_s = f"{lon_v.iloc[0]:.6f}" if not lon_v.empty else "—"
            azvc = g["_az_i"].dropna().value_counts().head(3)
            az_s = ", ".join([f"{int(k)}° ({int(v)})" for k, v in azvc.items()]) if not azvc.empty else "—"
            es_inferido = bool(tiene_col_inferido and g["sitio_inferido"].fillna(False).astype(bool).any())
            hay_sitio_inferido = hay_sitio_inferido or es_inferido
            entries.append((cnt, antenna, lat_s, lon_s, az_s, es_inferido))

        entries.sort(key=lambda x: x[0], reverse=True)

        rows = []
        for idx, (cnt, antenna, lat_s, lon_s, az_s, es_inferido) in enumerate(entries, start=1):
            # Si hay coordenadas válidas, convertir la antena en link a Google Maps
            if lat_s != "—" and lon_s != "—":
                ant_cell = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{antenna}</a>'
            else:
                ant_cell = antenna
            if es_inferido:
                ant_cell += _BADGE_SITIO_INFERIDO

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
            nota_html = _nota_sitios_inferidos_html() if hay_sitio_inferido else ""
            th_antena = "Antena/Sitio" if hay_sitio_inferido else "Antena"
            top_tab_html = (
                nota_html
                + "<table class='tbl'>"
                "<thead><tr>"
                f"<th>#</th><th>{th_antena}</th><th>Lat</th><th>Long</th><th>Conteo</th><th>Azimuts frecuentes</th>"
                "</tr></thead><tbody>"
                + "".join(rows) +
                "</tbody></table>"
            )
        else:
            top_tab_html = "<p class='nota'>No se registraron antenas con coordenadas válidas en el período analizado.</p>"
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
            return (
                '<section id="resumen-antenas">'
                "<h2>Antenas con mayor número de activaciones</h2>"
                '<p class="nota">No se registraron eventos en esta bitácora. '
                "Análisis de antenas no generado.</p>"
                "</section>"
            )

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
        col_ant = _resolver_columna_antena(df, "antena", "nombre_antena", "cell_name")
        col_lat = pick_first_existing_column(df, ["lat", "latitud", "latitude"])
        col_lon = pick_first_existing_column(df, ["long", "lon", "longitud", "lng", "longitude"])
        col_az = pick_first_existing_column(df, ["azimut", "azimuth", "azi", "angulo"])

        if not col_ant:
            return (
                '<section id="resumen-antenas">'
                "<h2>Antenas con mayor número de activaciones</h2>"
                '<p class="nota">Campo de antena no mapeado en esta bitácora. '
                "Análisis de antenas no generado.</p>"
                "</section>"
            )

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
            return (
                '<section id="resumen-antenas">'
                "<h2>Antenas con mayor número de activaciones</h2>"
                '<p class="nota">No se registraron antenas válidas para el período analizado. '
                "Análisis de antenas no generado.</p>"
                "</section>"
            )

        top = (
            dfv.groupby(col_ant)
            .size()
            .reset_index(name="activaciones")
            .sort_values("activaciones", ascending=False)
        )
        if int(top_n) > 0:
            top = top.head(int(top_n))

        tiene_col_inferido = "sitio_inferido" in dfv.columns
        hay_sitio_inferido = False
        filas = []
        for _, r0 in top.iterrows():
            ant = str(r0[col_ant])
            sub = dfv[dfv[col_ant] == ant]

            lt = float(sub[col_lat].astype(float).mean()) if (col_lat and col_lat in sub.columns) else None
            lg = float(sub[col_lon].astype(float).mean()) if (col_lon and col_lon in sub.columns) else None

            es_inferido = bool(tiene_col_inferido and sub["sitio_inferido"].fillna(False).astype(bool).any())
            hay_sitio_inferido = hay_sitio_inferido or es_inferido

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
            if es_inferido:
                ant_fmt += _BADGE_SITIO_INFERIDO

            filas.append((ant_fmt, int(r0["activaciones"]), lt_fmt, lg_fmt, az_dom, desg))

        tiene_mojibake = dfv[col_ant].astype(str).str.contains("?", regex=False).any()
        out: list[str] = []
        out.append('<section id="resumen-antenas">')
        _titulo_antenas = "Antenas/Sitios" if hay_sitio_inferido else "Antenas"
        out.append(f'<h2>{_titulo_antenas} con mayor número de activaciones (Top {top_n})</h2>')
        if tiene_mojibake:
            out.append(
                '<div class="aviso-dato">'
                "\u26a0 Se detectaron posibles caracteres no normalizados en nombres de antena. "
                "Esto puede deberse a la calidad del archivo de origen."
                "</div>"
            )
        _sujeto_nota_antenas = "antenas o sitios" if hay_sitio_inferido else "antenas"
        out.append(
            '<p class="nota"><b>Nota:</b> En esta sección se muestran las '
            f'{_sujeto_nota_antenas} con mayor número de activaciones durante el período '
            "analizado y su ubicación según las coordenadas registradas. Puede consultar la "
            "ubicación en el mapa incorporado o hacer clic en el nombre de la antena para "
            "abrirla en Google Maps.</p>"
        )
        if hay_sitio_inferido:
            out.append(_nota_sitios_inferidos_html())
        _th_antena_top = "Antena/Sitio" if hay_sitio_inferido else "Antena"
        out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
        out.append('<thead><tr>'
                  '<th>#</th>'
                  f'<th>{_th_antena_top}</th>'
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
#resumen-antenas .aviso-dato { background:#fff8e1; border-left:4px solid #f9a825; padding:8px 12px; margin-bottom:12px; font-size:0.95rem; }
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
            return (
                '<section id="antenas-rangos">'
                "<h2>Antenas por rango horario</h2>"
                '<p class="nota">No se registraron eventos en esta bitácora. '
                "Análisis por rango horario no generado.</p>"
                "</section>"
            )

        col_ant = _resolver_columna_antena(df, "antena", "antenanombre", "antena_nombre")
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
            return (
                '<section id="antenas-rangos">'
                "<h2>Antenas por rango horario</h2>"
                '<p class="nota">Campo de antena no mapeado en esta bitácora. '
                "Análisis por rango horario no generado.</p>"
                "</section>"
            )

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
            return (
                '<section id="antenas-rangos">'
                "<h2>Antenas por rango horario</h2>"
                '<p class="nota">Información de hora no disponible en esta bitácora. '
                "Análisis por rango horario no generado.</p>"
                "</section>"
            )

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
        tiene_col_inferido = "sitio_inferido" in df.columns
        hay_sitio_inferido_global = bool(
            tiene_col_inferido and df["sitio_inferido"].fillna(False).astype(bool).any()
        )
        _th_antena_rangos = "Antena/Sitio" if hay_sitio_inferido_global else "Antena"

        out: list[str] = []
        out.append('<section id="antenas-rangos">')
        out.append('<h2>Antenas por rango horario</h2>')
        out.append('<p class="nota"><b>Nota:</b> Si desea verificar la ubicación de una antena, puede hacer clic en el nombre para abrir su posición en Google Maps.</p>')
        if hay_sitio_inferido_global:
            out.append(_nota_sitios_inferidos_html())
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
            out.append(f'<table class="tbl"><thead><tr><th>#</th><th>{_th_antena_rangos}</th><th>Latitud</th><th>Longitud</th><th>Conteo</th><th>Azimuts frecuentes</th></tr></thead><tbody>')

            for idx, (ant, cnt) in enumerate(top_series.items(), start=1):
                sub_ant = sub_valid[sub_valid[col_ant] == ant]

                lat, lon = _first_valid_geo(sub_ant)
                lat_s = _fmt(lat) if lat is not None else "—"
                lon_s = _fmt(lon) if lon is not None else "—"

                if lat is not None and lon is not None:
                    ant_html = f'<a href="https://www.google.com/maps?q={lat_s},{lon_s}" target="_blank" rel="noopener">{ant}</a>'
                else:
                    ant_html = f"{ant}"
                if tiene_col_inferido and bool(sub_ant["sitio_inferido"].fillna(False).astype(bool).any()):
                    ant_html += _BADGE_SITIO_INFERIDO

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
