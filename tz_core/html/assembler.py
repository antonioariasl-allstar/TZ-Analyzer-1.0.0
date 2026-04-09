"""
TZ-Analyzer — HTML Assembler
Orquesta el ensamblaje final del informe HTML completo.
Llama a todos los builders de secciones, reordena contenido,
inyecta CSS/JS, genera heatmaps y escribe el archivo final.
Architecture: TZ-Analyzer v1.0.0 — tz_core.html package
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
from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.bitacora_normalization import (
    parse_duration_seconds,
    sanitize_latlon,
    normalize_msisdn,
    normalize_imei,
)
from .header import build_logo_html, generate_html_header, generate_body_header
from .kpi import prepare_report_metrics, generate_kpi_section
from .metadata import generate_metadata_section, build_identification_rows, inject_technical_metadata
from .contacts import build_top_contacts_sections, _construir_seccion_todos_contactos
from .antennas import (
    resolve_top_antennas_n,
    build_antennas_table,
    build_top_antennas_section,
    build_antennas_by_hour_section
)

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

