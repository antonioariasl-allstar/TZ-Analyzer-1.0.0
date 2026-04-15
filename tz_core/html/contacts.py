"""
Módulo de tablas de contactos del reporte HTML.

Módulo de generación de secciones HTML de contactos.
Contiene funciones para generar secciones de top contactos (por conteo y duración)
y wrapper para la sección completa de todos los contactos.
"""
from typing import Optional, Tuple

import pandas as pd

from tz_core.bitacora_normalization import normalize_msisdn, parse_duration_seconds
from tz_core.logging_utils import log
from tz_core.analytics import construir_seccion_todos_contactos


# ── helpers de detección ──────────────────────────────────────────────────────

_CONTACT_COLS = [
    "tel_contacto", "contacto", "destino", "b_number", "bnumber",
    "numero_contacto", "callednumber", "to", "receptor",
    "receptor_numero", "numero_destino",
]
_DUR_COLS   = ["duracion", "duration", "segundos", "tiempo"]
_FECHA_COLS = ["fecha", "date", "fecha_hora", "datetime", "fecha_inicio"]


def _detectar_columnas(df: pd.DataFrame):
    """Detecta columnas de contacto, duración y fecha disponibles en df."""
    c_col = next((c for c in _CONTACT_COLS if c in df.columns), None)
    d_col = next((c for c in _DUR_COLS     if c in df.columns), None)
    f_col = next((c for c in _FECHA_COLS   if c in df.columns), None)
    return None, c_col, f_col, d_col  # origen_col, destino_col, fecha_col, duracion_col


def calcular_metricas_contactos(
    df: pd.DataFrame,
    origen_col: str | None = None,
    destino_col: str | None = None,
    fecha_col: str | None = None,
    duracion_col: str | None = None,
) -> dict:
    """
    Calcula métricas enriquecidas por contacto para interpretación forense.
    No modifica df. No genera HTML. Solo retorna datos.

    Retorna dict: { numero_normalizado: { métricas } }
    """
    if df is None or df.empty:
        return {}

    if not all([destino_col or origen_col, fecha_col, duracion_col]):
        origen_col_, destino_col_, fecha_col_, duracion_col_ = _detectar_columnas(df)
        origen_col   = origen_col   or origen_col_
        destino_col  = destino_col  or destino_col_
        fecha_col    = fecha_col    or fecha_col_
        duracion_col = duracion_col or duracion_col_

    c_col = destino_col or origen_col
    if not c_col or c_col not in df.columns:
        return {}

    cols = [c_col]
    if duracion_col and duracion_col in df.columns:
        cols.append(duracion_col)
    if fecha_col and fecha_col in df.columns:
        cols.append(fecha_col)
    d = df[cols].copy()

    d["_contacto"] = (
        d[c_col].astype(str).str.strip()
        .map(lambda v: normalize_msisdn(v) or v)
    )
    d = d[(d["_contacto"] != "") & d["_contacto"].notna()]
    if d.empty:
        return {}

    d["_c_norm"] = d["_contacto"].str.replace(r"\D+", "", regex=True)
    d.loc[d["_c_norm"] == "", "_c_norm"] = d["_contacto"]

    if duracion_col and duracion_col in d.columns:
        d["_sec"] = d[duracion_col].map(
            lambda x: float(parse_duration_seconds(x, default=0.0))
        )
    else:
        d["_sec"] = 0.0

    if fecha_col and fecha_col in d.columns:
        d["_fecha"] = pd.to_datetime(d[fecha_col], errors="coerce").dt.normalize()
    else:
        d["_fecha"] = pd.NaT

    resultado = {}
    for numero, grupo in d.groupby("_c_norm", dropna=False):
        total_int = len(grupo)
        total_dur = float(grupo["_sec"].sum())
        prom_dur  = round(total_dur / total_int, 2) if total_int > 0 else 0.0

        fechas_validas = grupo["_fecha"].dropna()
        dias_activos   = int(fechas_validas.nunique()) if not fechas_validas.empty else 0
        primer_c = fechas_validas.min().date().isoformat() if not fechas_validas.empty else None
        ultimo_c = fechas_validas.max().date().isoformat() if not fechas_validas.empty else None

        resultado[numero] = {
            "total_interacciones":   total_int,
            "total_duracion_seg":    total_dur,
            "promedio_duracion_seg": prom_dur,
            "dias_activos":          dias_activos,
            "primer_contacto":       primer_c,
            "ultimo_contacto":       ultimo_c,
        }

    return resultado


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

    g_cnt = pd.Series(dtype=float)
    g_dur = pd.Series(dtype=float)

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

            g_dur = pd.Series(dtype=float)
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
                            "<thead><tr><th class='right'>#</th><th>Contacto</th><th>Duráción total</th></tr></thead>"
                            "<tbody>" + "\n".join(rows) + "</tbody></table>"
                        )

    # Análisis de perfiles de comunicación
    analisis_html = ""
    if not g_cnt.empty and c_col:
        # Obtener sets de contactos en cada top
        set_cnt = set(g_cnt.index)
        set_dur = set(g_dur.index) if not g_dur.empty else set()

        # Clasificar contactos
        dominantes = sorted(set_cnt & set_dur)  # En ambos tops
        solo_duracion = sorted(set_dur - set_cnt) if set_dur else []  # Solo en duración
        solo_frecuencia = sorted(set_cnt - set_dur)  # Solo en frecuencia

        # Construir líneas del análisis
        lineas = []

        if dominantes:
            nums_dom = ", ".join(str(n) for n in dominantes)
            lineas.append(f"• <strong>Dominantes ({len(dominantes)}):</strong> {nums_dom} — lideran en frecuencia y duración")

        if solo_duracion:
            nums_conv = ", ".join(str(n) for n in solo_duracion)
            lineas.append(f"• <strong>Conversadores ({len(solo_duracion)}):</strong> {nums_conv} — alta duración, baja frecuencia")

        if solo_frecuencia:
            nums_brev = ", ".join(str(n) for n in solo_frecuencia)
            lineas.append(f"• <strong>Contactos breves ({len(solo_frecuencia)}):</strong> {nums_brev} — alta frecuencia, baja duración")

        # Generar HTML solo si hay algo que mostrar
        if lineas:
            contenido = "<br>".join(lineas)
            analisis_html = (
                f'<div style="background:#f8f9fa;border-left:4px solid var(--accent);'
                f'padding:12px 16px;margin:16px 0;border-radius:4px;font-size:0.9em;">'
                f'<strong>Observación — Análisis de patrones de comunicación:</strong><br>'
                f'{contenido}'
                f'</div>'
            )

    # Insertar análisis al final de la sección (después de ambas tablas)
    if analisis_html:
        top_contactos_dur_html = top_contactos_dur_html + analisis_html

    return top_contactos_cnt_html, top_contactos_dur_html, _topC


def interpretar_contactos(
    metricas: dict,
    total_interacciones: int,
    total_duracion: float,
) -> dict:
    """
    Interpreta métricas por contacto y retorna categoría, etiquetas y narrativa.
    Autosuficiente: calcula rankings internamente desde metricas.
    No genera HTML. No depende de build_top_contacts_sections.
    """
    if not metricas or total_interacciones <= 0:
        return {}

    # --- Rankings internos ---
    por_frec = sorted(metricas.keys(), key=lambda n: (-metricas[n]["total_interacciones"], n))
    por_dur  = sorted(metricas.keys(), key=lambda n: (-metricas[n]["total_duracion_seg"], n))
    rank_frec = {n: i + 1 for i, n in enumerate(por_frec)}
    rank_dur  = {n: i + 1 for i, n in enumerate(por_dur)}

    # --- Fecha máxima del dataset ---
    fechas = [m["ultimo_contacto"] for m in metricas.values() if m.get("ultimo_contacto")]
    max_fecha = max(fechas) if fechas else None

    resultado = {}
    for numero, m in metricas.items():
        ti   = m["total_interacciones"]
        td   = m["total_duracion_seg"]
        prom = m["promedio_duracion_seg"]
        dias = m["dias_activos"]
        ult  = m.get("ultimo_contacto")

        pct_i = (ti / total_interacciones * 100.0) if total_interacciones > 0 else 0.0
        pct_d = (td / total_duracion * 100.0) if total_duracion > 0 else 0.0
        rf    = rank_frec[numero]
        rd    = rank_dur[numero]

        # --- Categoría ---
        if pct_i >= 15 and pct_d >= 15 and rf <= 3 and rd <= 3:
            categoria = "dominante"
        elif pct_d >= 15 and pct_i < 15 and prom > 300:
            categoria = "conversador"
        elif pct_i >= 15 and pct_d < 15:
            categoria = "frecuente"
        else:
            categoria = "breve"

        # --- Etiquetas ---
        etiquetas = []
        if pct_i >= 30 or pct_d >= 30:
            etiquetas.append("alta_concentracion")
        if dias >= 5:
            etiquetas.append("relacion_sostenida")
        if max_fecha and ult:
            from datetime import date, timedelta
            try:
                d_max = date.fromisoformat(max_fecha)
                d_ult = date.fromisoformat(ult)
                if d_ult >= d_max - timedelta(days=7):
                    etiquetas.append("contacto_reciente")
            except ValueError:
                pass
        if prom < 30:
            etiquetas.append("llamadas_breves")
        if prom > 300:
            etiquetas.append("llamadas_largas")

        # --- Narrativa ---
        lineas = []
        if categoria == "dominante":
            lineas.append(f"Concentra {pct_i:.1f}% de las interacciones y {pct_d:.1f}% de la duración total.")
            lineas.append(f"Ocupa la posición #{rf} en frecuencia y #{rd} en duración acumulada.")
        elif categoria == "conversador":
            lineas.append(f"Representa {pct_d:.1f}% de la duración total con duración promedio de {int(prom)}s por interacción.")
            lineas.append(f"Patrón de pocas interacciones prolongadas.")
        elif categoria == "frecuente":
            lineas.append(f"Concentra {pct_i:.1f}% de las interacciones con duración promedio baja ({int(prom)}s).")
            lineas.append(f"Patrón de contacto repetitivo y breve.")
        else:
            lineas.append(f"Participación de {pct_i:.1f}% en frecuencia y {pct_d:.1f}% en duración.")

        if "relacion_sostenida" in etiquetas:
            lineas.append(f"Contacto activo en {dias} días distintos del período analizado.")
        if "contacto_reciente" in etiquetas:
            lineas.append(f"Última interacción registrada: {ult}.")

        resultado[numero] = {
            "categoria":  categoria,
            "etiquetas":  etiquetas,
            "narrativa":  " ".join(lineas),
        }

    return resultado


def _construir_seccion_todos_contactos(df, columnas_config=None):
    """Wrapper de compatibilidad - usa tz_core.analytics.construir_seccion_todos_contactos"""
    from tz_core.analytics import construir_seccion_todos_contactos as contactos_modular
    return contactos_modular(df, columnas_config)
