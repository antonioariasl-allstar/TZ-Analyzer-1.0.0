"""
Módulo de tablas de contactos del reporte HTML.

Extraído de html_generator.py en Fase F4.4.
Contiene funciones para generar secciones de top contactos (por conteo y duración)
y wrapper para la sección completa de todos los contactos.
"""
from typing import Optional, Tuple

import pandas as pd

from tz_core.bitacora_normalization import normalize_msisdn, parse_duration_seconds
from tz_core.logging_utils import log
from tz_core.analytics import construir_seccion_todos_contactos


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


def _construir_seccion_todos_contactos(df, columnas_config=None):
    """Wrapper de compatibilidad - usa tz_core.analytics.construir_seccion_todos_contactos"""
    from tz_core.analytics import construir_seccion_todos_contactos as contactos_modular
    return contactos_modular(df, columnas_config)
