# BACKUP DE LA FUNCIÓN DEL DROPDOWN
# Guardado el 23 de octubre de 2025
# Esta función reemplaza _construir_seccion_interacciones con dropdown dinámico

def _construir_seccion_interacciones(df, dias=3, columnas_config=None):
    """
    Construye una sección HTML con 'Interacciones de los últimos N días registrados en bitácora'.
    - Subsecciones por fecha (dd/mm/aaaa), orden: más reciente -> más antiguo.
    - Por cada fecha: tabla por contacto con #interacciones, duración acumulada, antena top y sus coords/azimut.
    - Si una fecha no tiene antenas válidas: muestra nota.
    """

    # Helpers
    def _pick_col(df, candidatos):
        for c in candidatos:
            if c in df.columns:
                return c
        return None

    def _to_datetime_series(df):
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

    # Column mapping
    columnas_config = columnas_config or {}
    col_contacto = _pick_col(df, [
        columnas_config.get('tel_contacto', 'tel_contacto'),
        columnas_config.get('destino', 'destino'),
        columnas_config.get('b_party', 'b_party'),
        columnas_config.get('to', 'to'),
        columnas_config.get('callee', 'callee'),
        columnas_config.get('contacto', 'contacto'),
    ]) or 'tel_contacto'  # si no existe, más abajo se maneja

    col_duracion = _pick_col(df, [
        columnas_config.get('duracion', 'duracion'),
        'dur', 'duration', 'segundos', 'tiempo'
    ])
    col_antena = _pick_col(df, [
        columnas_config.get('antena', 'antena'),
        'nombre_antena', 'site_name', 'cell_name'
    ])
    col_lat = _pick_col(df, [
        columnas_config.get('lat', 'lat'),
        'latitud', 'latitude'
    ])
    col_long = _pick_col(df, [
        columnas_config.get('long', 'long'),
        'lon', 'longitud', 'lng', 'longitude'
    ])
    col_azimut = _pick_col(df, [
        columnas_config.get('azimut', 'azimut'),
        'azimuth', 'azi', 'angulo'
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
        # Aproximación para El Salvador
        _bbox_cfg = {"lat_min": 12.9, "lat_max": 14.5, "lon_min": -90.3, "lon_max": -87.6}

    def _valid_latlon_vals(lt, lg):
        """True si lat/lon son numéricas, no NaN, no (0,0) y dentro del bbox SV."""
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
        """Versión por fila: usa nombres de columnas detectados arriba."""
        if col_lat and col_long and (col_lat in row) and (col_long in row):
            return _valid_latlon_vals(row[col_lat], row[col_long])
        return False
    # === TOP-ANTENA-1A (fin) ===

    # Si no hay df razonable, retorna vacío (no rompe HTML)
    if df is None or df.empty:
        return ""

    # Construcción de datetime y fecha
    dt = _to_datetime_series(df)
    df_local = df.copy()
    df_local['_dt'] = dt
    df_local['_fecha'] = df_local['_dt'].dt.date
    df_local = df_local[df_local['_fecha'].notna()]
    if df_local.empty:
        return ""

    # Últimos N días distintos a partir del máximo
    fechas_ord = sorted(df_local['_fecha'].dropna().unique().tolist(), reverse=True)
    if not fechas_ord:
        return ""
    # Ignorar el parámetro 'dias' para desplegar TODOS los días disponibles
    # (preservamos lectura de CONFIG pero no limitamos aquí)
    try:
        if 'CONFIG' in globals() and isinstance(CONFIG, dict):
            _ = CONFIG.get("html", {}).get("interacciones_ultimos_dias", None)
    except Exception:
        pass
    fechas_sel = fechas_ord

    # Si no hay columna de contacto, crea una genérica SIN DETERMINAR
    if col_contacto not in df_local.columns:
        df_local['_contacto'] = 'SIN DETERMINAR'
    else:
        df_local['_contacto'] = df_local[col_contacto].fillna('SIN DETERMINAR').astype(str).str.strip()
        df_local.loc[df_local['_contacto'] == '', '_contacto'] = 'SIN DETERMINAR'

    # Duración en segundos: si viene string tipo hh:mm:ss, conviértelo
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

    # HTML build
    out = []
    out.append('<section id="interacciones-recientes">')
    out.append('<h2>Interacciones diarias</h2>')
    out.append(f'<p>Nota: Se muestran <strong>{len(fechas_sel)}</strong> día(s) con actividad.</p>')

    # Dropdown selector de día + banner de rango
    try:
        cnt_por_fecha = df_local['_fecha'].value_counts().to_dict()
    except Exception:
        cnt_por_fecha = {d: int((df_local['_fecha'] == d).sum()) for d in fechas_sel}

    dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    fmin = min(fechas_sel)
    fmax = max(fechas_sel)
    out.append(f"""
<div style="background:#e7f3ff;border-left:4px solid #2196F3;padding:12px;margin:12px 0;">
  <strong>📅 Rango:</strong> {pd.to_datetime(fmin).strftime('%d/%m/%Y')} — {pd.to_datetime(fmax).strftime('%d/%m/%Y')}
</div>
<div style="margin:12px 0 18px 0;">
  <label for="dia-selector" style="font-weight:600;margin-right:8px;">Seleccionar día:</label>
  <select id="dia-selector" style="padding:8px;font-size:1rem;border:1px solid #ccc;border-radius:4px;">
""")
    for d in fechas_sel:
        _dt = pd.to_datetime(d)
        label = f"🗓️ {dias_es[_dt.weekday()]} {_dt.day:02d} {meses_es[_dt.month-1]} {_dt.year} — {cnt_por_fecha.get(d, 0)} interacciones"
        out.append(f'<option value="{_dt.strftime("%Y-%m-%d")}">{label}</option>')
    out.append('</select></div>')

    # Recorre fechas seleccionadas
    for d in fechas_sel:
        _dt = pd.to_datetime(d)
        _fecha_str = _dt.strftime("%Y-%m-%d")
        out.append(f'<div id="content-{_fecha_str}" class="day-content" style="display:none;">')
        df_d = df_local[df_local['_fecha'] == d]
        # (... resto del código de renderizado por día ...)
        
        # NOTA: El código completo está en el archivo script_principal_bitacoras_refactory.py
        # líneas 2407-3030. Este backup solo muestra la estructura principal.
        
        out.append('</div>')

    out.append('</section>')
    # JS: mostrar/ocultar contenedores + fix Leaflet en contenedor oculto
    out.append("""
<script>
(function(){
    function showDay(dateStr){
        var all = document.querySelectorAll('#interacciones-recientes .day-content');
        all.forEach(function(el){ el.style.display = 'none'; });
        var el = document.getElementById('content-' + dateStr);
        if(el){ el.style.display = 'block'; setTimeout(function(){ window.dispatchEvent(new Event('resize')); }, 0); }
    }
    var sel = document.getElementById('dia-selector');
    if(sel){ sel.addEventListener('change', function(){ showDay(this.value); });
             if(sel.options.length>0){ showDay(sel.options[0].value); } }
})();
</script>
""")
    return "".join(out)
