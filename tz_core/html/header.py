"""
Módulo de generación de encabezados HTML.

Extraído de html_generator.py en Fase F4.
Contiene las funciones para construir el logo, encabezado HTML (<head>) 
y encabezado del cuerpo (<body><header>).
"""
import base64
import mimetypes
import os


def build_logo_html(config: dict | None = None) -> str:
    """Construye el bloque <img> con logo embebido en base64 o fallback SVG inline."""
    try:
        # Config y atributos visibles
        _br_all = (config or {}) if config is not None else {}
        _brand = _br_all.get("brand", {}) or {}
        _branding = _br_all.get("branding", {}) or {}

        # Alt y ancho deseado
        _alt = (
            str((_branding.get("logo_alt") or "")).strip()
            or str(((_brand.get("logo") or {}).get("alt") or "")).strip()
            or str(_brand.get("name") or "TZ Analyzer").strip()
        )
        try:
            _w = int(((_brand.get("logo") or {}).get("width_px") or 120))
        except Exception:
            _w = 120

        # 1) Si en config viene un base64 directo, úsalo
        _b64_cfg = _branding.get("logo_base64") or (_brand.get("logo") or {}).get("base64")
        if isinstance(_b64_cfg, str) and _b64_cfg.strip():
            b64 = _b64_cfg.strip()
            if b64.startswith("data:"):
                src = b64
            else:
                # asumir PNG por defecto
                src = f"data:image/png;base64,{b64}"
            return f'<img src="{src}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'

        # 2) Intentar archivo local si la ruta existe (robusto, nombres candidatos)
        _script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _candidates = []
        # a) paths declarados en config
        for key_path in [(_branding.get("logo_path") or ""), (((_brand.get("logo") or {}).get("path")) or "")]:
            p = str(key_path or "").strip()
            if p:
                _candidates.append(p)
        # a.1) subdirectorio assets/ (ubicación canónica del logo)
        _assets_dir = os.path.join(_script_dir, "assets")
        for _logo_name in ["Logo TZ.png", "logo_tz.png", "Logo_TZ.png", "logo.png", "logo.svg", "Logo.png", "Logo.svg"]:
            _candidates.append(os.path.join(_assets_dir, _logo_name))
        # a.2) mismo directorio tz_core/ (legacy)
        _candidates.extend([
            "logo_tz.png", "Logo TZ.png", "Logo_TZ.png", "logo.png", "logo.svg", "Logo.png", "Logo.svg"
        ])
        # a.3) raíz del proyecto (fallback)
        _project_root = os.path.dirname(_script_dir)
        for _logo_name in ["Logo TZ.png", "logo_tz.png", "Logo_TZ.png", "logo.png", "Logo.png"]:
            _candidates.append(os.path.join(_project_root, _logo_name))

        for rel in _candidates:
            try:
                p_abs = rel if os.path.isabs(rel) else os.path.join(_script_dir, rel)
                if os.path.exists(p_abs) and os.path.isfile(p_abs):
                    mime, _ = mimetypes.guess_type(p_abs)
                    mime = mime or ("image/svg+xml" if p_abs.lower().endswith(".svg") else "image/png")
                    with open(p_abs, "rb") as fh:
                        data = fh.read()
                    b64 = base64.b64encode(data).decode("ascii")
                    return f'<img src="data:{mime};base64,{b64}" alt="{_alt}" style="height:{_w}px;max-height:{_w}px"/>'
            except Exception:
                continue

        # 3) Fallback: SVG inline accesible (sin archivos)
        _svg = (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{_w}' height='{int(_w*0.38)}' viewBox='0 0 320 120' role='img' aria-label='{_alt}'>"
            "<rect width='320' height='120' fill='#0B57D0' rx='12'/>"
            "<text x='50%' y='53%' dominant-baseline='middle' text-anchor='middle' font-family='Segoe UI, Roboto, Arial, sans-serif' font-size='40' fill='white' font-weight='700'>TZ Analyzer</text>"
            "</svg>"
        )
        svg_uri = "data:image/svg+xml;utf8," + _svg.replace("\n", "")
        return f"<img src='{svg_uri}' alt='{_alt}' style='height:{_w}px;max-height:{_w}px'/>"
    except Exception:
        # ante cualquier problema, evita romper: deja un placeholder textual
        return "<div style='font-weight:700;font-size:18px'>TZ Analyzer</div>"

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
