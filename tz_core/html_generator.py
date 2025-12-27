"""
TZ-Analyzer-1.0.0 HTML Generator Module

Módulo especializado para la generación de secciones HTML del informe de bitácora.
Extraído de generar_informe_html() para mejorar modularidad y mantenibilidad.

FASE 2 - HTML Generator Extraction Epic
Responsabilidades:
- Generación de estructura HTML base (head, styles, body)
- Componentes visuales (headers, metadatos, KPIs)
- Secciones de contenido especializado

Author: AI Agent + Human Collaboration
Last Modified: 2025-12-27
Architecture: TZ-Analyzer Professional v1.0.0
"""

# Imports necesarios para construir_seccion_interacciones
import json
import pandas as pd
import numpy as np
from tz_core.logging_utils import log
from tz_core.config_manager import cargar_config

def generate_html_header(theme_hex: str, nombre_salida: str) -> str:
    """
    Genera el bloque <head> completo del HTML con CSS y dependencias.
    
    Extrae la sección HTML-HEADER-COMPLETE que incluye:
    - DOCTYPE, html lang, meta charset
    - Título del documento  
    - Viewport responsivo
    - CSS completo con variables CSS, tipografía normalizada
    - Dependencias Leaflet para mapas
    
    Args:
        theme_hex (str): Color principal en formato hexadecimal (ej: "#ff6b35")
        nombre_salida (str): Nombre del caso/análisis para el título
        
    Returns:
        str: HTML completo desde <!DOCTYPE hasta </head>
        
    Example:
        >>> header = generate_html_header("#007acc", "caso_xyz")
        >>> print(header[:50])
        <!DOCTYPE html>
        <html lang="es">
        <head>
    """
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de Bitácora — {nombre_salida}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ 
  --accent: {theme_hex};
}}
* {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  margin: 20px;
  color: #222;
}}
h1 {{ margin: 0 0 6px 0; font-size: 20px; }}
h2 {{ margin: 18px 0 10px; font-size: 16px; color: #333; }}
.small {{ color:#666; font-size: 12px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background: var(--accent); color:white; font-size:12px; }}
.kpis {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
  gap: 10px;
  margin-top: 10px;
}}
.card {{
  border: 1px solid #e6e6e6;
  border-radius: 10px;
  padding: 10px;
}}
.card .n {{
  font-size: 18px; font-weight: 700; color:#111; margin: 2px 0 6px;
}}
.card .label {{ color:#555; font-size: 12px; }}
.links a {{ color: var(--accent); text-decoration: none; }}
.links a:hover {{ text-decoration: underline; }}
.meta table {{ border-collapse: collapse; font-size: 12px; }}
.meta td {{ padding: 2px 6px; vertical-align: top; }}
hr {{ border:0; border-top:1px solid #ddd; margin:14px 0; }}

/* tablas */
table.tbl{{width:100%;border-collapse:collapse;font-size:12px}}
table.tbl th,table.tbl td{{border:1px solid #e6e6e6;padding:6px 8px;text-align:left}}
table.tbl th{{background:#fafafa}}
.nowrap{{white-space:nowrap}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}

/* listas compactas */
ul.list{{margin:4px 0 0 16px;padding:0}}
ul.list li{{font-size:12px; line-height:1.2}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}}
.sub{{font-size:12px;color:#666;margin-top:2px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.right{{text-align:right}}
.bar{{height:8px;background:#eee;border-radius:4px}}
.bar .fill{{height:100%;background:var(--accent,#ff00ff);border-radius:4px}}
/* === TIPOGRAFÍA BASE (normalizada) === */
:root{{ --fs-base: 15px; --lh-base: 1.45; }}
html, body{{ font-size: var(--fs-base); line-height: var(--lh-base); }}
main, section, p, li, td, th, div, span{{ font-size: inherit; line-height: inherit; }}
.mono{{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: inherit; }}
small{{ font-size: 0.92em; }}
table{{ font-size: 1em; }}
/* encabezados de sección */
/* encabezados de sección */
section > h2{{background:#000;color:#fff;padding:8px 10px;border-radius:6px;margin:18px 0 10px}}
/* separador visual entre secciones */
section{{margin-top:22px}}
.barrow td{{padding-top:0}}
/* estilos para mini-mapas por día */
.map-notice{{ padding:12px; background:#f0f0f0; border:1px solid #ddd; border-radius:6px; color:#666; text-align:center; font-size:13px; }}
</style>

<!-- Dependencias de Leaflet para mapas de calor -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

</head>"""

# TODO: Más funciones se añadirán en FASE 2.2, 2.3, 2.4...
# - generate_body_header()
# - generate_metadata_section() 
# - generate_kpi_section()
# - generate_top_antenas_section()
# etc.


def generate_body_header(logo_html: str, nombre_salida: str, hoja: str | None, gen_dt: str, config_dict: dict = None) -> str:
    """
    Genera el bloque <body><header> completo del HTML con branding y título.
    
    Extrae la sección HTML-BODY-HEADER que incluye:
    - Apertura <body>
    - <header> con layout flexbox
    - Logo posicionado a la izquierda
    - Texto de branding (TZ Analyzer + versión)
    - Título principal del informe con badge
    - Metadatos de generación (fecha + hoja)
    
    Args:
        logo_html (str): HTML del logo a mostrar (lado izquierdo)
        nombre_salida (str): Nombre del caso/análisis para mostrar en badge
        hoja (str | None): Nombre de la hoja analizada (opcional)
        gen_dt (str): Fecha/hora de generación formateada
        config_dict (dict, optional): Dict de configuración para obtener versión
        
    Returns:
        str: HTML completo desde <body> hasta </header>
        
    Example:
        >>> header = generate_body_header(
        ...     "<img src='logo.png'/>", 
        ...     "caso_xyz", 
        ...     "Hoja1", 
        ...     "2025-10-27 15:30"
        ... )
        >>> print(header[:20])
        <body>
          <header>
    """
    # Obtener versión de CONFIG o usar default
    if config_dict:
        version = (config_dict.get('brand', {}) or {}).get('version', 'Versión 1.0.0')
    else:
        version = 'Versión 1.0.0'
    
    # Construir texto de hoja si existe
    hoja_text = f' — Hoja: {hoja}' if hoja else ''
    
    return f"""<body>
  <header>
    <div class="brand-row" style="display:flex;align-items:center;gap:16px;padding:8px 0;justify-content:flex-start;">
  <!-- Logo a la izquierda -->
  {logo_html}

  <!-- Texto a la derecha -->
  <div style="line-height:1.25;">
    <div style="font-size:22px;font-weight:700;margin:0;">
      TZ Analyzer — {version}
    </div>

    <h1 style="font-size:20px;font-weight:700;margin:4px 0 0 0;">
      Informe de Bitácora — <span class="badge">{nombre_salida}</span>
    </h1>

    <div class="small" style="margin-top:4px;">
      Generado: {gen_dt}{hoja_text}
    </div>
  </div>
</div>
  </header>"""


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
        for c in candidatos:
            if c and c in df.columns:  # Ignora None y strings vac├¡os
                return c
        return None

    def _to_datetime_series(df):
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
            # Parse formatos comunes
            def _parse_dur(x):
                x = str(x).strip()
                if not x or x.lower() in ('nan', 'none'):
                    return 0
                if x.isdigit():
                    return float(x)
                parts = x.split(':')
                try:
                    parts = [int(p) for p in parts]
                    if len(parts) == 3:
                        return parts[0]*3600 + parts[1]*60 + parts[2]
                    if len(parts) == 2:
                        return parts[0]*60 + parts[1]
                except Exception:
                    pass
                return 0
            df_local['_dur_sec'] = ser_dur.map(_parse_dur)
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
            if v is None:
                return 'ÔÇö'
            try:
                f = float(v)
                return f"{int(round(f))}"
            except Exception:
                s = str(v).strip()
                return s if s else 'ÔÇö'

        def _fmt_hora(row):
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



