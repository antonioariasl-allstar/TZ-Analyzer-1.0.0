"""
Módulo de KPIs y métricas del reporte HTML.

Módulo de generación de KPIs HTML.
Contiene las funciones para calcular métricas del reporte (prepare_report_metrics)
y generar la sección visual de KPIs (generate_kpi_section).
"""
from datetime import datetime
import os
import pandas as pd
from pathlib import Path

from tz_core.bitacora_normalization import parse_date_series, sanitize_latlon
from tz_core.html_helpers import fmt_datetime as fmt_dt
from tz_core.logging_utils import log


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
            if "datetime_evento" in df.columns and df["datetime_evento"].notna().any():
                dt = pd.to_datetime(
                    df["datetime_evento"],
                    errors="coerce",
                ).dropna()
            elif "hora" in df.columns and df["hora"].notna().any():
                fechas = parse_date_series(df["fecha"], dayfirst=True).dt.normalize()
                horas = pd.to_timedelta(
                    df["hora"].astype(str).str.strip(),
                    errors="coerce",
                )
                dt = (fechas + horas).dropna()
            else:
                # Solo fecha: tomar 00:00 para el inicio y 23:59 para el fin
                fechas = parse_date_series(df["fecha"], dayfirst=True).dropna()
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
    _interp_oraciones = []
    if ant_uniq > 1:
        _interp_oraciones.append(
            "Se observa que el dispositivo registró actividad en múltiples antenas, "
            "lo que evidencia movilidad dentro del área analizada."
        )
    if top_pct >= 30.0:
        _interp_oraciones.append(
            "Se identifica concentración de actividad en una antena predominante, "
            "lo que puede sugerir un punto de permanencia recurrente."
        )
    if coord_invalidas > 0:
        _interp_oraciones.append(
            "Se registran interacciones sin coordenadas geográficas válidas, "
            "lo que limita parcialmente el análisis de cobertura espacial."
        )
    _interp_kpi_html = (
        '<p style="font-size:0.88em;color:#555;margin:12px 0 0 0;line-height:1.6;">'
        + " ".join(_interp_oraciones)
        + "</p>"
    ) if _interp_oraciones else ""
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
    {_interp_kpi_html}
  </section>"""
