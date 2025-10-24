# NUEVA IMPLEMENTACION COMPLETA DE _construir_seccion_interacciones
# Esta es solo referencia temporal - se copiará al archivo principal

def _construir_seccion_interacciones(df, dias=None, columnas_config=None):
    """
    Construye sección HTML 'Interacciones por día' con selector dropdown dinámico.
    - Dropdown con TODOS los días disponibles (ordenados del más reciente al más antiguo)
    - Por cada día: resumen estadístico + mapa de antenas + tabla detallada de interacciones
    - JavaScript con lazy loading de mapas (se crean solo al seleccionar el día)
    - Validaciones: mensaje si no hay datos, alerta si >365 días, rango de fechas visible
    
    Args:
        df: DataFrame con datos de la bitácora
        dias: Deprecado (se ignora; ahora se muestran todos los días disponibles)
        columnas_config: Diccionario de mapeo de columnas (opcional)
    
    Returns:
        String HTML con la sección completa
    """
    import json
    
    out = []
    out.append('<section id="interacciones-recientes">')
    out.append('<h2>Interacciones diarias</h2>')

    if df is None or df.empty:
        out.append("<p><em>No hay datos.</em></p></section>")
        return "".join(out)

    # ========== FUNCIONES AUXILIARES ==========
    def _pick_col(df, candidatos):
        """Retorna la 1ra col de candidatos que exista en df.columns (case-insensitive), o None."""
        cols_lower = {c.lower(): c for c in df.columns if isinstance(c, str)}
        for cand in candidatos:
            if isinstance(cand, str) and cand.lower() in cols_lower:
                return cols_lower[cand.lower()]
        return None

    def _to_datetime_series(df):
        """Intenta convertir col 'Fecha y Hora' -> datetime, con fallback."""
        # Intento 1: combinación fecha + hora
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
        """Convierte total_seconds a HH:MM:SS"""
        try:
            total_seconds = float(total_seconds)
        except Exception:
            return "00:00:00"
        if pd.isna(total_seconds):
            return "00:00:00"
        total_seconds = int(round(total_seconds))
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _is_sv_bbox(lat, lon):
        """True si coords dentro de El Salvador aprox."""
        if pd.isna(lat) or pd.isna(lon):
            return False
        return (13.0 <= lat <= 14.5) and (-90.2 <= lon <= -87.5)

    # ========== DETECCION DE COLUMNAS ==========
    columnas_config = columnas_config or {}
    col_contacto = _pick_col(df, ['contacto', 'tel_contacto', 'destino', 'b_party', 'to', 'callee'])
    col_duracion = _pick_col(df, ['duracion', 'dur', 'duration', 'segundos', 'tiempo'])
    col_antena = _pick_col(df, ['antena', 'nombre_antena', 'site_name', 'cell_name'])
    col_lat = _pick_col(df, ['lat', 'latitud', 'latitude'])
    col_lon = _pick_col(df, ['long', 'lon', 'longitud', 'lng', 'longitude'])
    col_azimut = _pick_col(df, ['azimut', 'azimuth', 'azi', 'angulo'])
    col_tipo = _pick_col(df, ['tipo', 'type', 'eventtype'])

    # ========== EXTRACCION DE FECHAS Y AGRUPACION POR DIA ==========
    df_work = df.copy()
    dt_series = _to_datetime_series(df_work)
    df_work["_dt"] = dt_series
    df_work = df_work.dropna(subset=["_dt"])

    if df_work.empty:
        out.append("<p><em>No se encontraron fechas válidas.</em></p></section>")
        return "".join(out)

    df_work["_date"] = df_work["_dt"].dt.date
    all_dates = sorted(df_work["_date"].unique(), reverse=True)  # Más reciente primero

    # Alerta si hay >365 días
    if len(all_dates) > 365:
        out.append("""
<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin-bottom:16px;">
    <strong>⚠️ Bitácora extensa:</strong> Se detectaron más de 365 días de datos. 
    El selector puede tardar en cargar.
</div>
""")

    # Banner con rango de fechas
    fecha_min = min(all_dates).strftime("%d/%m/%Y")
    fecha_max = max(all_dates).strftime("%d/%m/%Y")
    out.append(f"""
<div style="background:#e7f3ff;border-left:4px solid #2196F3;padding:12px;margin-bottom:16px;">
    <strong>📅 Rango:</strong> {fecha_min} — {fecha_max} ({len(all_dates)} días con actividad)
</div>
""")

    # ========== CONSTRUCCION DEL DROPDOWN ==========
    out.append('<div style="margin:20px 0;">')
    out.append('<label for="dia-selector" style="font-weight:600;margin-right:8px;">Seleccionar día:</label>')
    out.append('<select id="dia-selector" style="padding:8px;font-size:1rem;border:1px solid #ccc;border-radius:4px;">')

    # Opciones: "🗓️ NombreDia DD Mes YYYY — N interacciones"
    dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    for fecha in all_dates:
        fecha_str = fecha.strftime("%Y-%m-%d")
        dia_semana = dias_es[fecha.weekday()]
        mes_nombre = meses_es[fecha.month - 1]
        num_interacciones = len(df_work[df_work["_date"] == fecha])
        
        label = f"🗓️ {dia_semana} {fecha.day:02d} {mes_nombre} {fecha.year} — {num_interacciones} interacciones"
        out.append(f'<option value="{fecha_str}">{label}</option>')

    out.append('</select>')
    out.append('</div>')

    # ========== CONTENEDORES POR DIA (ocultos inicialmente) ==========
    dias_data = {}  # {fecha_str: {interacciones: [...], antennas: {...}, summary: {...}}}

    for fecha in all_dates:
        fecha_str = fecha.strftime("%Y-%m-%d")
        df_dia = df_work[df_work["_date"] == fecha].copy()
        df_dia = df_dia.sort_values("_dt")  # Cronológico

        # ========== CALCULAR RESUMEN KPIs ==========
        num_interacciones = len(df_dia)
        duracion_total = 0
        if col_duracion:
            duracion_total = df_dia[col_duracion].sum() if not df_dia[col_duracion].isna().all() else 0

        antennas_unicas = set()
        if col_antena:
            antennas_unicas = set(df_dia[col_antena].dropna().unique())

        contactos_unicos = set()
        if col_contacto:
            contactos_unicos = set(df_dia[col_contacto].dropna().unique())

        # ========== EXTRAER ANTENNAS CON COORDS (deduplicadas) ==========
        antennas_map = {}  # {nombre_antena: {lat, lon, count}}
        if col_antena and col_lat and col_lon:
            for ant_name in antennas_unicas:
                subset = df_dia[df_dia[col_antena] == ant_name]
                lat_vals = subset[col_lat].dropna()
                lon_vals = subset[col_lon].dropna()
                if not lat_vals.empty and not lon_vals.empty:
                    lat = lat_vals.iloc[0]
                    lon = lon_vals.iloc[0]
                    if _is_sv_bbox(lat, lon):
                        antennas_map[ant_name] = {
                            "lat": round(float(lat), 6),
                            "lon": round(float(lon), 6),
                            "count": len(subset)
                        }

        # ========== EXTRAER INTERACCIONES PARA TABLA ==========
        interacciones_list = []
        max_rows = 500  # Límite por día
        for idx, row in df_dia.head(max_rows).iterrows():
            hora = row["_dt"].strftime("%H:%M:%S") if pd.notna(row["_dt"]) else ""
            contacto = row[col_contacto] if col_contacto and pd.notna(row.get(col_contacto)) else ""
            tipo = row[col_tipo] if col_tipo and pd.notna(row.get(col_tipo)) else ""
            duracion = _fmt_hms(row[col_duracion]) if col_duracion and pd.notna(row.get(col_duracion)) else "00:00:00"
            antena = row[col_antena] if col_antena and pd.notna(row.get(col_antena)) else ""
            lat = round(float(row[col_lat]), 6) if col_lat and pd.notna(row.get(col_lat)) else None
            lon = round(float(row[col_lon]), 6) if col_lon and pd.notna(row.get(col_lon)) else None
            azimut = int(row[col_azimut]) if col_azimut and pd.notna(row.get(col_azimut)) else None

            interacciones_list.append({
                "hora": hora,
                "contacto": contacto,
                "tipo": tipo,
                "duracion": duracion,
                "antena": antena,
                "lat": lat,
                "lon": lon,
                "azimut": azimut
            })

        # Guardar datos del día
        dias_data[fecha_str] = {
            "interacciones": interacciones_list,
            "antennas": antennas_map,
            "summary": {
                "num_interacciones": num_interacciones,
                "duracion_total": _fmt_hms(duracion_total),
                "num_antennas": len(antennas_unicas),
                "num_contactos": len(contactos_unicos)
            }
        }

        # ========== HTML DEL CONTENEDOR ==========
        out.append(f'<div id="content-{fecha_str}" class="day-content" style="display:none;margin-top:20px;">')

        # KPIs
        out.append('<div class="kpis-summary" style="display:flex;gap:20px;margin-bottom:20px;flex-wrap:wrap;">')
        out.append(f'<div style="background:#e3f2fd;padding:12px 16px;border-radius:6px;flex:1;min-width:150px;">')
        out.append(f'<div style="font-size:0.85rem;color:#1565c0;">Interacciones</div>')
        out.append(f'<div style="font-size:1.5rem;font-weight:700;color:#0d47a1;">{num_interacciones}</div>')
        out.append('</div>')

        out.append(f'<div style="background:#f3e5f5;padding:12px 16px;border-radius:6px;flex:1;min-width:150px;">')
        out.append(f'<div style="font-size:0.85rem;color:#6a1b9a;">Antenas únicas</div>')
        out.append(f'<div style="font-size:1.5rem;font-weight:700;color:#4a148c;">{len(antennas_unicas)}</div>')
        out.append('</div>')

        out.append(f'<div style="background:#fff3e0;padding:12px 16px;border-radius:6px;flex:1;min-width:150px;">')
        out.append(f'<div style="font-size:0.85rem;color:#e65100;">Duración total</div>')
        out.append(f'<div style="font-size:1.5rem;font-weight:700;color:#bf360c;">{_fmt_hms(duracion_total)}</div>')
        out.append('</div>')

        out.append(f'<div style="background:#e8f5e9;padding:12px 16px;border-radius:6px;flex:1;min-width:150px;">')
        out.append(f'<div style="font-size:0.85rem;color:#2e7d32;">Contactos únicos</div>')
        out.append(f'<div style="font-size:1.5rem;font-weight:700;color:#1b5e20;">{len(contactos_unicos)}</div>')
        out.append('</div>')
        out.append('</div>')

        # Mini-mapa (360px)
        out.append(f'<div id="map-{fecha_str}" style="width:100%;height:360px;margin:20px 0;border:1px solid #ccc;border-radius:4px;"></div>')

        # Tabla de interacciones
        out.append('<h3 style="margin-top:24px;">Detalle de interacciones</h3>')
        if len(df_dia) > max_rows:
            out.append(f'<p style="color:#b45309;"><em>⚠️ Mostrando las primeras {max_rows} de {len(df_dia)} interacciones</em></p>')

        out.append('<div class="tabla-scroll" style="overflow-x:auto;">')
        out.append('<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">')
        out.append('<thead><tr style="background:#f5f5f5;border-bottom:2px solid #ddd;">')
        out.append('<th style="padding:8px;text-align:left;">#</th>')
        out.append('<th style="padding:8px;text-align:left;">Hora</th>')
        out.append('<th style="padding:8px;text-align:left;">Contacto</th>')
        out.append('<th style="padding:8px;text-align:left;">Tipo</th>')
        out.append('<th style="padding:8px;text-align:left;">Duración</th>')
        out.append('<th style="padding:8px;text-align:left;">Antena</th>')
        out.append('<th style="padding:8px;text-align:left;">Coords</th>')
        out.append('<th style="padding:8px;text-align:left;">Azimut</th>')
        out.append('</tr></thead><tbody>')

        for i, inter in enumerate(interacciones_list, 1):
            tipo_badge = ""
            if inter["tipo"]:
                color = "#4caf50" if "SMS" in inter["tipo"].upper() else "#2196f3"
                tipo_badge = f'<span style="background:{color};color:white;padding:2px 6px;border-radius:3px;font-size:0.75rem;">{inter["tipo"]}</span>'

            coords_str = ""
            if inter["lat"] is not None and inter["lon"] is not None:
                coords_str = f'{inter["lat"]:.6f}, {inter["lon"]:.6f}'

            azimut_str = f'{inter["azimut"]}°' if inter["azimut"] is not None else ""

            out.append(f'<tr style="border-bottom:1px solid #eee;">')
            out.append(f'<td style="padding:6px;">{i}</td>')
            out.append(f'<td style="padding:6px;">{inter["hora"]}</td>')
            out.append(f'<td style="padding:6px;">{inter["contacto"]}</td>')
            out.append(f'<td style="padding:6px;">{tipo_badge}</td>')
            out.append(f'<td style="padding:6px;">{inter["duracion"]}</td>')
            out.append(f'<td style="padding:6px;">{inter["antena"]}</td>')
            out.append(f'<td style="padding:6px;font-family:monospace;font-size:0.85rem;">{coords_str}</td>')
            out.append(f'<td style="padding:6px;">{azimut_str}</td>')
            out.append('</tr>')

        out.append('</tbody></table>')
        out.append('</div>')  # tabla-scroll
        out.append('</div>')  # day-content

    # ========== SERIALIZAR DATOS COMO JSON ==========
    out.append('<script>')
    out.append(f'var diasData = {json.dumps(dias_data, ensure_ascii=False)};')
    out.append('</script>')

    # ========== JAVASCRIPT PARA NAVEGACION Y MAPAS ==========
    out.append("""
<script>
(function() {
    var maps = {};  // Cache de mapas creados
    var selector = document.getElementById('dia-selector');
    
    function showDay(dateStr) {
        // Ocultar todos los contenedores
        var allContents = document.querySelectorAll('.day-content');
        allContents.forEach(function(el) { el.style.display = 'none'; });
        
        // Mostrar el seleccionado
        var content = document.getElementById('content-' + dateStr);
        if (content) {
            content.style.display = 'block';
            
            // Lazy load del mapa
            if (!maps[dateStr]) {
                createMap(dateStr);
            }
        }
    }
    
    function createMap(dateStr) {
        var mapId = 'map-' + dateStr;
        var mapEl = document.getElementById(mapId);
        if (!mapEl) return;
        
        var data = diasData[dateStr];
        if (!data || !data.antennas) return;
        
        // Crear mapa Leaflet
        var map = L.map(mapId).setView([13.7, -89.2], 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Añadir marcadores de antennas
        var bounds = [];
        for (var antName in data.antennas) {
            var ant = data.antennas[antName];
            var marker = L.marker([ant.lat, ant.lon]).addTo(map);
            marker.bindPopup('<b>' + antName + '</b><br>' + 
                           ant.count + ' interacciones<br>' +
                           'Coords: ' + ant.lat.toFixed(6) + ', ' + ant.lon.toFixed(6));
            bounds.push([ant.lat, ant.lon]);
        }
        
        // Auto-zoom a bounds
        if (bounds.length > 0) {
            map.fitBounds(bounds, {padding: [20, 20]});
        }
        
        maps[dateStr] = map;
    }
    
    // Event listener del selector
    selector.addEventListener('change', function() {
        showDay(this.value);
    });
    
    // Mostrar el primer día por defecto
    if (selector.options.length > 0) {
        var firstDate = selector.options[0].value;
        selector.value = firstDate;
        showDay(firstDate);
    }
})();
</script>
""")

    # ========== CSS ==========
    out.append("""
<style>
#interacciones-recientes .tabla-scroll { overflow-x: auto; }
#interacciones-recientes tr:hover { background: #f9f9f9; }
#interacciones-recientes th { font-weight: 600; }
</style>
""")

    out.append('</section>')
    return "".join(out)
