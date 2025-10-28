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