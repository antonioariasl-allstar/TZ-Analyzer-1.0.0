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
Last Modified: 2025-01-27
Architecture: TZ-Analyzer Professional v1.0.0
"""

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