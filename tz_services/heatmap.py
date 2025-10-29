"""
tz_services.heatmap - Generador de Heatmaps HTML

Extracción de render_heatmap_html_for_day desde monolito con fachada temporal.
Genera mapas interactivos Leaflet.js para visualización de antenas por día.

Sprint 2B Fase 2B.2: Extracción física a módulos
Compatibilidad 100% con salida HTML original

Funcionalidades:
- Agrupación de antenas únicas por coordenadas redondeadas
- Cálculo de azimut principal por antena
- Generación de marcadores Leaflet.js con popups
- Manejo de zoom automático (1 marcador vs múltiples)
- JavaScript para interactividad (pantalla completa, invalidateSize)

Dependencias:
- pandas para manejo de fechas y DataFrames
- json para serialización de marcadores
- Funciones de logging externas

Variables de contexto requeridas:
- col_lat, col_long: Columnas de coordenadas
- col_antena: Columna de nombres de antenas  
- col_azimut: Columna de azimuts (opcional)
- d: Fecha del día (para formateo)

Fecha: 29 octubre 2025
"""

import json
import pandas as pd
from typing import Dict, Any, List, Optional, Callable


def build_heatmap_html(df_day: pd.DataFrame, day_id: str, config: Dict[str, Any], 
                      log_func: Optional[Callable] = None) -> str:
    """
    Fachada temporal para build_heatmap_html.
    
    Genera un mapa HTML que muestra TODAS las antenas únicas activadas en el día.
    Cada antena se muestra como un marcador con su nombre y conteo de activaciones.
    
    Args:
        df_day: DataFrame con datos del día filtrado
        day_id: ID del día (formato YYYYMMDD)
        config: Configuración con columnas y parámetros
        log_func: Función de logging (opcional)
        
    Returns:
        str: HTML completo del mapa con scripts Leaflet.js
        
    Configuración esperada:
        config = {
            "columns": {
                "lat": "lat",           # Columna latitud
                "long": "long",         # Columna longitud  
                "antena": "antena",     # Columna nombre antena
                "azimut": "azimut"      # Columna azimut (opcional)
            },
            "date_context": "2024-10-29"  # Fecha para formateo
        }
        
    Funcionalidad:
    - Agrupa antenas por coordenadas redondeadas (precisión ~1 metro)
    - Calcula azimut principal más frecuente por antena
    - Genera marcadores con popups informativos
    - Zoom automático: 1 marcador → zoom 12, múltiples → fitBounds
    - JavaScript para interactividad y pantalla completa
    
    Extracción de: render_heatmap_html_for_day (L2114-L2245) script_principal
    """
    # Función de logging por defecto
    def default_log(msg: str):
        print(f"[HEATMAP] {msg}")
    
    log = log_func or default_log
    
    # Extraer configuración de columnas
    columns = config.get("columns", {})
    col_lat = columns.get("lat")
    col_long = columns.get("long") 
    col_antena = columns.get("antena")
    col_azimut = columns.get("azimut")
    date_context = config.get("date_context", day_id)
    
    # Validación de entrada
    if df_day is None or df_day.empty:
        try:
            fecha_fmt = pd.to_datetime(date_context).strftime('%d/%m/%Y')
        except:
            fecha_fmt = str(date_context)
        return f"<div class='map-notice'>Sin datos de ubicación para {fecha_fmt}</div>"
    
    # Recolectar y agrupar TODAS las antenas únicas del día
    antenas_dict = {}
    total_filas = 0
    
    for _, rr in df_day.iterrows():
        total_filas += 1
        try:
            lat = float(rr[col_lat])
            lon = float(rr[col_long])
        except Exception:
            continue
        
        # Agrupar por antena (usar lat/lon/nombre como clave única)
        if col_antena and col_antena in df_day.columns:
            name = str(rr.get(col_antena, ''))
            if name and name != 'nan' and name != '':
                # Usar coordenadas redondeadas para agrupar antenas muy cercanas
                lat_round = round(lat, 5)  # ~1 metro de precisión
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
        try:
            fecha_fmt = pd.to_datetime(date_context).strftime('%d/%m/%Y')
        except:
            fecha_fmt = str(date_context)
        return f"<div class='map-notice'>Sin antenas válidas para mapear en {fecha_fmt} (se procesaron {total_filas} registros con coordenadas)</div>"

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
            'lat': item['lat'], 
            'lon': item['lon'], 
            'name': item['name'], 
            'count': item['count'], 
            'azimut': azimut_principal
        })
    
    num_antenas = len(markers)
    
    # Log para debugging
    log(f"[DEBUG] Día {day_id}: {total_filas} registros procesados, {num_antenas} antenas únicas mapeadas")
    for m in markers:
        log(f"  - {m['name']}: {m['count']} activaciones en ({m['lat']:.6f}, {m['lon']:.6f})")
    
    # Generar HTML del mapa
    return _generate_leaflet_html(markers, day_id, num_antenas)


def _generate_leaflet_html(markers: List[Dict[str, Any]], day_id: str, num_antenas: int) -> str:
    """
    Genera el HTML completo del mapa Leaflet.js con marcadores.
    
    Args:
        markers: Lista de marcadores con lat, lon, name, count, azimut
        day_id: ID único del día para elementos DOM
        num_antenas: Número total de antenas para mensaje informativo
        
    Returns:
        str: HTML completo con estilos, div del mapa y scripts JS
        
    Funcionalidad:
    - Crea div contenedor con botón pantalla completa
    - Serializa marcadores a JSON para JavaScript
    - Genera script Leaflet.js con lógica de zoom
    - Configura popups con información detallada
    - Registra mapa en window.__tzDailyMaps para control global
    """
    _markers_js = json.dumps(markers, ensure_ascii=False)
    div_id = f"heatmap-{day_id}"

    html = f'''<div style="margin:16px auto; max-width:95%; padding:0 20px;">
    <p style="font-size:12px; color:#666; margin:4px 0 8px;">
        Se muestran <strong>{num_antenas} antena(s)</strong> con coordenadas válidas de este día. 
        Haz clic en los marcadores para ver detalles de cada ubicación.
    </p>
    <div id="wrap-{div_id}" class="tz-map-wrap" style="position:relative;">
        <button class="tz-fs-btn" title="Pantalla completa" data-map-id="{div_id}" style="position:absolute; right:10px; top:10px; z-index:1000; background:#ffffffc9; border:1px solid #bbb; border-radius:6px; padding:6px 8px; cursor:pointer;">⛶</button>
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
        
                // Log para verificar que se agregó
                console.log('Marcador ' + (idx+1) + ': ' + m.name + ' en [' + m.lat + ', ' + m.lon + '] con ' + m.count + ' activaciones');
        
                var popupHtml = '' +
                    '<div style="font-family:sans-serif;min-width:180px;">' +
                    '<strong style="font-size:14px;">Antena #' + (idx+1) + '</strong><br>' +
                    '<strong style="font-size:13px;color:#333;">' + (m.name || '') + '</strong><br>' +
                    '<span style="font-size:12px;color:#666;">Activaciones: ' + (m.count || 0) + '</span><br>' +
                    '<span style="font-size:11px;color:#999;">Coordenadas: ' + (typeof m.lat==='number'? m.lat.toFixed(6): m.lat) + ', ' + (typeof m.lon==='number'? m.lon.toFixed(6): m.lon) + '</span>' +
                    ((m.azimut !== null && m.azimut !== undefined) ? "<br><span style=\'font-size:12px;color:#666;\'>Azimut principal: " + m.azimut + "°</span>" : '') +
                    '</div>';
                mk.bindPopup(popupHtml, {{ maxWidth: 250 }});
            }});

            // Registrar mapa y bounds para re-encuadre al cambiar de día
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


def create_heatmap_config(col_lat: str, col_long: str, col_antena: str, 
                         col_azimut: Optional[str], date_context: str) -> Dict[str, Any]:
    """
    Crea configuración estándar para build_heatmap_html.
    
    Args:
        col_lat: Nombre de columna latitud
        col_long: Nombre de columna longitud
        col_antena: Nombre de columna antena
        col_azimut: Nombre de columna azimut (puede ser None)
        date_context: Fecha de contexto para formateo
        
    Returns:
        Dict con configuración completa
        
    Helper para crear config desde variables de contexto del monolito.
    """
    return {
        "columns": {
            "lat": col_lat,
            "long": col_long,
            "antena": col_antena,
            "azimut": col_azimut
        },
        "date_context": date_context
    }


def validate_heatmap_data(df: pd.DataFrame, config: Dict[str, Any]) -> bool:
    """
    Valida que el DataFrame tiene las columnas requeridas para el heatmap.
    
    Args:
        df: DataFrame a validar
        config: Configuración con nombres de columnas
        
    Returns:
        bool: True si tiene columnas válidas, False si no
        
    Verificaciones:
    - DataFrame no vacío
    - Columnas lat/long existen
    - Al menos una fila con coordenadas válidas
    """
    if df is None or df.empty:
        return False
    
    columns = config.get("columns", {})
    col_lat = columns.get("lat")
    col_long = columns.get("long")
    
    if not col_lat or not col_long:
        return False
        
    if col_lat not in df.columns or col_long not in df.columns:
        return False
    
    # Verificar al menos una fila con coordenadas válidas
    try:
        for _, row in df.iterrows():
            lat = float(row[col_lat])
            lon = float(row[col_long])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return True
    except:
        pass
    
    return False