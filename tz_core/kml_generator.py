"""
MÓDULO: kml_generator.py
PROPÓSITO: Generación profesional de archivos KML/KMZ desde DataFrames procesados
EXTRAÍDO DE: script_principal_bitacoras_refactory.py (Epic 13)
LÍNEAS ORIGINALES: ~350 líneas (generar_kml + _crear_feature_kml + helpers)

MIGRACIÓN ÉPICA:
- Función principal: generar_kml() con estructura de carpetas configurable
- Función auxiliar: _crear_feature_kml() con estilos reutilizables
- Deduplicación inteligente por (antena, azimut_entero)
- Soporte para Top N dinámico y carpetas por rango horario
- Compatible con Protocolo Paranoico (validación exhaustiva)

DEPENDENCIAS:
- pandas: manipulación del DataFrame
- simplekml: generación de archivos KML/KMZ
- tz_core.geo_utils: calcular_punto_final (coordenadas geodésicas)
- tz_core.time_utils: clasificar_rango_sv, RANGOS_SV
- tz_core.color_utils: hex_to_kml_color
- tz_core.format_utils: agregar_bloque, armar_descripcion_compacta
- tz_core.logging_utils: log

ESTADO: Modularizado en Epic 13 (26/12/2025)
"""

import os
import math
import re
import logging
import unicodedata
from collections import Counter, defaultdict
from typing import Optional, Tuple

import pandas as pd
from simplekml import Kml
import simplekml as sk

# Imports internos del framework tz_core
from tz_core.geo_utils import calcular_punto_final
from tz_core.time_utils import clasificar_rango_sv, RANGOS_SV, normalize_hour_to_hhmmss
from tz_core.color_utils import hex_to_kml_color
from tz_core.format_utils import agregar_bloque, armar_descripcion_compacta
from tz_core.logging_utils import log
from tz_core.bitacora_normalization import (
    normalize_imei,
    normalize_msisdn,
    parse_date_series,
)

# Separador HTML compacto (usado en descripciones)
HR_COMPACT = '<div style="border-top:1px solid #bbb; margin:1px 0; height:0;"></div>'

# Cache global de estilos KML reutilizables (performance)
_REUSABLE_STYLES = None


def _crear_feature_kml(
    container, 
    nombre_punto: str, 
    lon: float, 
    lat: float, 
    descripcion: Optional[str], 
    azimut_float: Optional[float], 
    config: dict, 
    azimuts_extra: Optional[list] = None
):
    """
    Crea un punto KML con línea de azimut y cono de cobertura.
    
    CARACTERÍSTICAS:
    - Estilos reutilizables (pin/línea/cono) para optimizar tamaño KML
    - Compactación inteligente del nombre para visualización
    - Sanitización de descripciones (elimina campos vacíos/NaN)
    - Soporte para azimuts secundarios (múltiples líneas/conos por punto)
    
    Args:
        container: Folder o Kml donde crear el feature
        nombre_punto: Nombre completo de la antena
        lon, lat: Coordenadas WGS84
        descripcion: HTML para el popup (puede incluir <br>)
        azimut_float: Ángulo en grados (0-360)
        config: Diccionario de configuración (CONFIG global)
        azimuts_extra: Lista de azimuts secundarios opcionales
    """
    global _REUSABLE_STYLES
    
    # === SANITIZACIÓN DE DESCRIPCIÓN ===
    try:
        # Compactación del nombre para el campo 'name' del KML
        def compactar_nombre_antena_kml(nombre: str) -> str:
            """Compacta nombre según reglas de CONFIG.kml.name_compaction"""
            try:
                nc = (config or {}).get("kml", {}).get("name_compaction", {})
            except Exception:
                nc = {}
            prefer_before = int(nc.get("prefer_before_comma", 2) or 0)
            max_words = int(nc.get("max_words", 5) or 5)
            max_chars = int(nc.get("max_chars", 40) or 40)
            stopwords = set(str(w).lower() for w in nc.get("stopwords", 
                ["el","la","los","las","de","del","y","en","a","al","por","para","con","un","una"]))
            
            if not nombre:
                return ""
            nombre = str(nombre).strip()
            
            # Prioridad 1: tomar N secciones antes de coma
            if "," in nombre and prefer_before > 0:
                secciones = [s.strip() for s in nombre.split(",")]
                if len(secciones) >= prefer_before:
                    parte = ", ".join(secciones[:prefer_before])
                else:
                    parte = ", ".join(secciones)
            else:
                # Prioridad 2: primeras N palabras significativas
                palabras = [w for w in re.split(r'\s+', nombre) 
                           if w and w.lower() not in stopwords]
                parte = " ".join(palabras[:max_words])
            
            # Truncar si excede max_chars
            if len(parte) > max_chars:
                return parte[:max(0, max_chars-3)] + "..."
            return parte

        nombre_compacto = compactar_nombre_antena_kml(nombre_punto) if nombre_punto else nombre_punto

        # Sanitizar descripción: eliminar líneas vacías y marcadores de dato faltante
        if descripcion:
            parts = re.split(r'<br\s*/?>', str(descripcion))
            
            # Filtrar líneas vacías o con marcadores "Sin Inf"
            parts = [
                p for p in parts
                if p and p.strip() and not any(tok in p for tok in (
                    "> SinInf", "> Sin Inf.", "> None", "> nan", "> NaN"
                ))
            ]
            
            # Normalizar IDs numéricos (quitar .0 al final de TEL/IMEI)
            def _fix_id_line(s: str) -> str:
                """Elimina el '.0' de números en líneas de IMEI/Número para formato limpio."""
                if ("<b>IMEI" in s) or ("<b>Número" in s) or ("<b>Numero" in s):
                    return re.sub(r'(\d+)\.0\b', r'\1', s)
                return s
            
            parts = [_fix_id_line(p) for p in parts]
            descripcion = "<br>".join(parts)
    except Exception:
        pass  # Si falla sanitización, usar valores originales

    # === VALIDACIÓN DE AZIMUT ===
    try:
        az = float(azimut_float)
    except Exception:
        return  # No dibujar si azimut no es numérico
    
    if isinstance(az, float) and math.isnan(az):
        return
    
    # Normalizar a rango [0, 360)
    az = az % 360.0
    az_int = int(round(az)) % 360

    # === INICIALIZAR ESTILOS REUTILIZABLES ===
    if _REUSABLE_STYLES is None:
        style_cfg = {}
        try:
            style_cfg = config.get("style", {}) if isinstance(config, dict) else {}
        except Exception:
            style_cfg = {}
        
        # Extraer parámetros de estilo (o defaults)
        theme_hex = style_cfg.get("theme_hex", "#ff00ff")
        pin_icon_url = style_cfg.get("pin_icon_url", 
            "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png")
        pin_scale = float(style_cfg.get("pin_scale", 1.1))
        label_scale = float(style_cfg.get("label_scale", 1.2))
        line_width = float(style_cfg.get("line_width", 5))
        line_abgr = style_cfg.get("line_abgr", None)
        cone_opac = float(style_cfg.get("cone_opacity", 0.35))

        # Convertir colores a formato KML (AABBGGRR)
        pin_color = hex_to_kml_color(theme_hex, 255)
        line_color = line_abgr if line_abgr else hex_to_kml_color(theme_hex, 255)
        cone_color = hex_to_kml_color(theme_hex, int(max(0, min(1.0, cone_opac)) * 255))

        # Crear objetos Style una sola vez
        s_pin = sk.Style()
        s_pin.iconstyle.color = pin_color
        s_pin.iconstyle.scale = pin_scale
        s_pin.iconstyle.icon.href = pin_icon_url
        s_pin.labelstyle.color = pin_color
        s_pin.labelstyle.scale = label_scale

        s_line = sk.Style()
        s_line.linestyle.color = line_color
        s_line.linestyle.width = line_width

        s_cone = sk.Style()
        s_cone.polystyle.color = cone_color
        s_cone.polystyle.fill = 1
        s_cone.polystyle.outline = 1

        _REUSABLE_STYLES = {
            "pin": s_pin,
            "line": s_line,
            "cone": s_cone,
        }

    # === CREAR PUNTO ===
    p = container.newpoint(name=nombre_compacto, coords=[(lon, lat)])
    if descripcion:
        p.description = f'<div style="line-height:1.10; font-size:14px">{descripcion}</div>'
    p.style = _REUSABLE_STYLES["pin"]

    # === CREAR LÍNEA Y CONO DE AZIMUT ===
    try:
        az = float(azimut_float) if azimut_float is not None else float("nan")
    except Exception:
        az = float("nan")

    if not (isinstance(az, float) and math.isnan(az)):
        # Parámetros de azimut desde config
        try:
            az_dist_km = config.get("kml", {}).get("azimuth_km", 1.5)
            # Priorizar kml.cone.half_degrees, luego style.cone_half_degrees
            cone_half = config.get("kml", {}).get("cone", {}).get("half_degrees")
            if cone_half is None:
                cone_half = config.get("style", {}).get("cone_half_degrees", 35)
        except Exception:
            az_dist_km = 1.5
            cone_half = 35

        # Calcular punto final de la línea
        latf, lonf = calcular_punto_final(lat, lon, az, float(az_dist_km))

        # Crear LÍNEA
        linea = container.newlinestring(
            name=f"Azimut {int(round(az))}°",
            coords=[(lon, lat), (lonf, latf)]
        )
        linea.style = _REUSABLE_STYLES["line"]

        # Crear CONO (polígono)
        coords_cono = []
        paso = 5
        for ang in range(-int(cone_half), int(cone_half) + 1, paso):
            lat_p, lon_p = calcular_punto_final(lat, lon, az + ang, float(az_dist_km))
            coords_cono.append((lon_p, lat_p))
        coords_cono.append((lon, lat))
        
        pol = container.newpolygon(name=f"Cono Azimut {int(round(az))}°")
        pol.outerboundaryis = coords_cono
        pol.style = _REUSABLE_STYLES["cone"]
        
        # === AZIMUTS SECUNDARIOS (opcional) ===
        if azimuts_extra:
            for az_s in azimuts_extra:
                try:
                    az_s = float(az_s)
                except:
                    continue

                # Línea secundaria
                latf2, lonf2 = calcular_punto_final(lat, lon, az_s, float(az_dist_km))
                linea2 = container.newlinestring(
                    name=f"Azimut {int(round(az_s))}° (sec.)",
                    coords=[(lon, lat), (lonf2, latf2)]
                )
                linea2.style = _REUSABLE_STYLES["line"]

                # Cono secundario
                coords_cono2 = []
                for ang in range(-int(cone_half), int(cone_half) + 1, paso):
                    lat_p2, lon_p2 = calcular_punto_final(lat, lon, az_s + ang, float(az_dist_km))
                    coords_cono2.append((lon_p2, lat_p2))
                coords_cono2.append((lon, lat))

                pol2 = container.newpolygon(name=f"Cono Azimut {int(round(az_s))}° (sec.)")
                pol2.outerboundaryis = coords_cono2
                pol2.style = _REUSABLE_STYLES["cone"]


def generar_kml(
    df: pd.DataFrame, 
    archivo_salida_kml: str, 
    config: dict,
    flat: bool = False,
    override_tops: Optional[dict] = None
) -> Tuple[str, int]:
    """
    Genera archivo KML/KMZ a partir del DataFrame procesado.
    
    ESTRUCTURA DE SALIDA:
    - Modo flat (flat=True): todos los puntos en raíz, sin carpetas
    - Modo carpetas (flat=False, default):
        * todas_las_antenas/ (organizadas por fecha)
        * top_N_las_mas_activadas/ (global, deduplicadas)
        * top_N_por_rango_horario/ (mañana/tarde/noche/madrugada)
        * por_rango_horario/ (opcional según config.kml.incluir_por_rango_horario)
    
    DEDUPLICACIÓN:
    - Agrupa por (antena, azimut_entero) para evitar puntos duplicados
    - Muestra contador de activaciones en burbuja de descripción
    - Identifica azimut principal y secundarios con estadísticas
    
    Args:
        df: DataFrame con columnas canónicas (lat, long, azimut, fecha, hora, etc.)
        archivo_salida_kml: Ruta completa donde guardar el archivo .kml
        config: Diccionario CONFIG con toda la configuración del sistema
        flat: Si True, genera estructura plana sin carpetas
        override_tops: Diccionario para sobreescribir Top N (ej. {'antenas': 5})
    
    Returns:
        Tuple[str, int]: (ruta_archivo_kml, puntos_descartados)
    
    Raises:
        None: Maneja errores internamente con log() y continúa
    """
    # === VALIDACIÓN DE ENTRADA ===
    if df is None:
        log("[ERROR] generar_kml: DataFrame es None, abortando")
        return "", 0
    # La normalización de presentación del KML no debe modificar el DataFrame
    # que posteriormente consume el informe HTML.
    df = df.copy(deep=True)
    if df.empty:
        log("[WARN] generar_kml: DataFrame vacío, generando KML sin puntos")

    kml = Kml()
    descartadas = 0

    # === NORMALIZACIÓN DE FECHA/HORA ===
    if "fecha" in df.columns:
        try:
            df["fecha"] = parse_date_series(
                df["fecha"],
                dayfirst=True,
            ).dt.strftime("%d/%m/%Y")
            df["fecha"] = df["fecha"].fillna("Sin Inf.")
        except Exception:
            df["fecha"] = "Sin Inf."
    else:
        df["fecha"] = "Sin Inf."

    # Detectar mejor columna de hora y normalizar a HH:MM:SS tolerando separadores variados
    hora_candidates = [
        "hora",
        "hora_local",
        "hora_llamada",
        "hora_evento",
        "hora_utc",
        "hora_local_sv",
        "hora_sv",
        "time",
    ]

    col_hora = next((c for c in hora_candidates if c in df.columns), None)
    if col_hora and col_hora != "hora":
        df["hora"] = df[col_hora]
    elif "hora" not in df.columns:
        df["hora"] = "Sin Inf."

    try:
        horas_norm = df["hora"].apply(normalize_hour_to_hhmmss)
        try:
            invalid_ratio = float(horas_norm.isna().mean()) if len(horas_norm) else 0.0
            if invalid_ratio > 0.2:
                log(
                    f"[WARNING] KML rango horario: {invalid_ratio*100:.1f}% de horas no se pudieron normalizar; revisa formato de columnas de hora."
                )
        except Exception:
            pass

        df["hora"] = horas_norm.where(horas_norm.notna(), "Sin Inf.")
    except Exception:
        df["hora"] = "Sin Inf."

    # Ordenar por fecha y hora
    try:
        df = df.sort_values(by=["fecha", "hora"])
    except Exception:
        pass

    # === PREPARAR ITEMS (un dict por cada fila válida) ===
    kml_cfg = (config or {}).get("kml", {})
    desc_spec = kml_cfg.get("description", [])

    def _first_available(row_obj, *cols):
        """Return first column with a meaningful value for backwards compatibility."""
        for col in cols:
            if not col:
                continue
            val = row_obj.get(col, None)
            if pd.isna(val):
                continue
            if isinstance(val, str):
                if not val.strip() or val.strip().lower() in {"nan", "none"}:
                    continue
            return val
        return None
    items = []

    for _, row in df.iterrows():
        # Validar coordenadas
        lat_raw = row.get("lat", None)
        lon_raw = row.get("long", None)
        
        if lat_raw in ("Sin Inf.", "S/I", None, "") or lon_raw in ("Sin Inf.", "S/I", None, ""):
            descartadas += 1
            continue
        
        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except Exception:
            descartadas += 1
            continue

        # Descartar (0,0) y coordenadas fuera de rango
        if (abs(lat) < 1e-9 and abs(lon) < 1e-9):
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue

        # Procesar azimut (puede faltar)
        azimut_float = None
        azimut_int = None
        try:
            az = row.get("azimut", None)
            if az is not None and str(az).strip() not in {"", "Sin Inf.", "S/I"}:
                azimut_float = float(az)
                azimut_int = int(round(azimut_float))
        except Exception:
            pass

        # Nombre y descripción del punto
        nombre_punto = row.get("antena", "Antena") if str(row.get("antena", "")).strip() else "Antena"
        
        partes = []
        for bloque in desc_spec:
            agregar_bloque(partes, row, [(etq, col) for etq, col in bloque])
        if partes and partes[-1] == "<hr>":
            partes.pop()
        descripcion = "\n".join(partes) if partes else None

        # Clasificación por rango horario
        rango = clasificar_rango_sv(row.get("hora", None))

        # Almacenar item con todos los campos necesarios
        tel_val = normalize_msisdn(row.get("tel", None)) or row.get("tel", None)
        imei_val = normalize_imei(row.get("imei", None)) or row.get("imei", None)
        items.append({
            "antena": nombre_punto,
            "antena_completa": row.get("antena", None),
            "lon": lon,
            "long": lon,
            "lat": lat,
            "azimut_f": azimut_float,
            "azimut_i": azimut_int,
            "rango": rango,
            "alias": _first_available(row, "alias", "alias_usuario"),
            "usuario": _first_available(row, "nombre_usuario", "usuario"),
            "abonado": row.get("abonado", None),
            "tel": tel_val,
            "imei": imei_val,
            "tel_contacto": row.get("tel_contacto", row.get("contacto", None)),
            "fecha": row.get("fecha", None),
            "hora": row.get("hora", None),
            "azimut": row.get("azimut", None),
            "celda": row.get("celda", None),
            "lac": row.get("lac", None),
            "direccion": row.get("direccion", row.get("detalle", row.get("antena", None))),
            "interaccion": row.get("interaccion", None),
            "duracion": row.get("duracion", None),
            "desc": descripcion,
        })

    # Contador global para deduplicación
    pair_counter_all = Counter((it["antena"], it["azimut_i"]) for it in items)

    # === MODO FLAT (sin carpetas) ===
    if flat:
        for it in items:
            n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
            desc_comp = armar_descripcion_compacta(
                it, n_all, 
                suprimir_direccion_si_igual=False, 
                config=config, 
                hr_compact=HR_COMPACT
            )
            _crear_feature_kml(kml, it["antena"], it["lon"], it["lat"], 
                             desc_comp, it["azimut_f"], config)

        # Guardar archivos
        solo_kmz = bool(config.get("salida", {}).get("solo_kmz", False))
        
        if not solo_kmz:
            try:
                kml.save(archivo_salida_kml)
            except Exception as e:
                logging.error(f"Error al guardar KML '{archivo_salida_kml}': {e}")

        try:
            kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
            kml.savekmz(kmz_path)
        except Exception as e:
            logging.error(f"Error al guardar KMZ '{kmz_path}': {e}")

        return archivo_salida_kml, descartadas

    # === MODO CARPETAS (estructura completa) ===
    from datetime import datetime
    
    nombre_raiz = os.path.splitext(os.path.basename(archivo_salida_kml))[0]
    raiz = kml.newfolder(name=nombre_raiz)

    # Carpeta principal: todas_las_antenas
    f_todas = raiz.newfolder(name="todas_las_antenas")
    folders_por_fecha = {}

    def obtener_carpeta_fecha(fecha_dt):
        """Helper para obtener/crear carpeta por fecha"""
        if fecha_dt == "Sin Inf." or not fecha_dt:
            return None
        if isinstance(fecha_dt, str):
            try:
                fecha_dt = datetime.fromisoformat(fecha_dt)
            except Exception:
                try:
                    fecha_dt = datetime.strptime(fecha_dt, "%d/%m/%Y")
                except:
                    fecha_dt = datetime.strptime(fecha_dt, "%Y-%m-%d")
        fecha_str = f"{fecha_dt.timetuple().tm_yday:03d}-{fecha_dt.strftime('%Y-%m-%d')}"
        if fecha_str not in folders_por_fecha:
            folders_por_fecha[fecha_str] = f_todas.newfolder(name=fecha_str)
        return folders_por_fecha[fecha_str]

    # Carpeta opcional: por_rango_horario
    incluir_rango = False
    try:
        incluir_rango = bool(config.get("kml", {}).get("incluir_por_rango_horario", False))
    except Exception:
        pass
    
    if incluir_rango:
        f_rangos = raiz.newfolder(name="por_rango_horario")
        rango_folders = {
            "manana": f_rangos.newfolder(name=RANGOS_SV["manana"][0]),
            "tarde": f_rangos.newfolder(name=RANGOS_SV["tarde"][0]),
            "noche": f_rangos.newfolder(name=RANGOS_SV["noche"][0]),
            "madrugada": f_rangos.newfolder(name=RANGOS_SV["madrugada"][0]),
        }
    else:
        rango_folders = {}

    # Determinar Top N dinámico
    try:
        if override_tops and isinstance(override_tops, dict) and (override_tops.get('antenas') is not None):
            _topN_ant = int(override_tops.get('antenas'))
        else:
            _topN_ant = int(config.get("top_antenas", config.get("html", {}).get("top_antenas_n", 3)))
    except Exception:
        _topN_ant = 3

    _name_top_global = ("top_las_mas_activadas" if (_topN_ant is None or _topN_ant <= 0) 
                       else f"top_{_topN_ant}_las_mas_activadas")
    _name_top_por_rango = ("top_por_rango_horario" if (_topN_ant is None or _topN_ant <= 0)
                          else f"top_{_topN_ant}_por_rango_horario")

    f_top_global = raiz.newfolder(name=_name_top_global)
    f_top_por_rango = raiz.newfolder(name=_name_top_por_rango)
    top_rango_folders = {
        "manana": f_top_por_rango.newfolder(name=RANGOS_SV["manana"][0]),
        "tarde": f_top_por_rango.newfolder(name=RANGOS_SV["tarde"][0]),
        "noche": f_top_por_rango.newfolder(name=RANGOS_SV["noche"][0]),
        "madrugada": f_top_por_rango.newfolder(name=RANGOS_SV["madrugada"][0]),
    }

    # === LLENAR CARPETAS ===
    
    # 1) Crear carpetas por fecha en orden cronológico
    fechas_unicas = sorted({
        datetime.strptime(it["fecha"], "%Y-%m-%d") if "-" in it["fecha"]
        else datetime.strptime(it["fecha"], "%d/%m/%Y")
        for it in items
        if isinstance(it["fecha"], str) and it["fecha"] != "Sin Inf."
    })
    for fch in fechas_unicas:
        obtener_carpeta_fecha(fch)

    # 2) Poblar "todas_las_antenas" (un punto por activación, sin dedup)
    for it in items:
        n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
        desc_comp = armar_descripcion_compacta(
            it, n_all,
            suprimir_direccion_si_igual=True,
            config=config,
            hr_compact=HR_COMPACT
        )
        _carpeta = obtener_carpeta_fecha(it["fecha"])
        if _carpeta is not None:
            _crear_feature_kml(
                _carpeta,
                it["antena"], it["lon"], it["lat"],
                desc_comp, it["azimut_f"], config
            )

    # 3) Preparar contadores para deduplicación
    pair_global = Counter((it["antena"], it["azimut_i"]) for it in items)
    ant_global = Counter(it["antena"] for it in items)

    items_by_rango = defaultdict(list)
    _rango_keys_validos = set(RANGOS_SV.keys())
    for it in items:
        if it["rango"] in _rango_keys_validos:
            items_by_rango[it["rango"]].append(it)
    
    pair_por_rango = {r: Counter((it["antena"], it["azimut_i"]) for it in lst) 
                     for r, lst in items_by_rango.items()}
    ant_por_rango = {r: Counter(it["antena"] for it in lst) 
                    for r, lst in items_by_rango.items()}

    # === HELPER PARA DEDUPLICACIÓN ===
    def _crear_dedup(container, iterable, pair_counter):
        """Crea puntos con deduplicación por (antena, lat, lon)"""
        # Agrupar por ubicación
        grupos = {}
        for it in iterable:
            key = (it["antena"], it["lat"], it["lon"])
            az = str(it.get("azimut_f", "SinInf")).strip()
            if key not in grupos:
                grupos[key] = {
                    "items": [],
                    "azimuts": {},
                    "antena": it["antena"],
                    "lat": it["lat"],
                    "lon": it["lon"]
                }
            grupos[key]["items"].append(it)
            grupos[key]["azimuts"][az] = grupos[key]["azimuts"].get(az, 0) + 1

        # Crear un punto por grupo con estadísticas
        for (antena, lat, lon), datos in grupos.items():
            total = sum(datos["azimuts"].values())
            az_principal = max(datos["azimuts"], key=datos["azimuts"].get)
            az_sec = [az for az, _c in sorted(datos["azimuts"].items(), 
                                              key=lambda t: t[1], reverse=True) 
                     if az != az_principal]
            cuenta_principal = datos["azimuts"][az_principal]

            # Helpers de normalización
            def _sin_tildes(s):
                """Elimina acentos y tildes de un string reemplazándolos con caracteres ASCII."""
                return (s.replace("á","a").replace("é","e").replace("í","i")
                       .replace("ó","o").replace("ú","u").replace("Á","A")
                       .replace("É","E").replace("Í","I").replace("Ó","O")
                       .replace("Ú","U").replace("ñ","n").replace("Ñ","N"))

            def _norm_key(k):
                """Normaliza clave de columna: sin tildes, minúsculas, sin espacios."""
                return _sin_tildes(str(k).strip().lower())

            def _norm_val(v):
                """Normaliza valor: retorna 'SinInf' si es None, NaN o vacío, sino el string del valor."""
                try:
                    if v is None: return "SinInf"
                    if isinstance(v, float) and math.isnan(v): return "SinInf"
                    s = str(v).strip()
                    return "SinInf" if s == "" or s.lower() == "nan" else s
                except:
                    s = str(v).strip()
                    return "SinInf" if s == "" else s

            def getv_group(*cands):
                """Obtiene primer valor no-SinInf de candidatos normalizados"""
                cand_norm = [_norm_key(c) for c in cands]
                for it_row in datos["items"]:
                    row = {_norm_key(k): _norm_val(v) for k, v in it_row.items()}
                    for cn in cand_norm:
                        val = row.get(cn, "SinInf")
                        if val != "SinInf":
                            return val
                return "SinInf"

            # Extraer campos comunes del grupo
            numero_raw = getv_group('tel','numero','msisdn_origen','msisdn','telefono')
            imei_raw = getv_group('imei','imei_origen')
            numero = normalize_msisdn(numero_raw) or numero_raw
            imei = normalize_imei(imei_raw) or imei_raw
            alias = getv_group('alias','alias_usuario','alias_contacto')
            usuario = getv_group('nombre_usuario','usuario')
            abonado = getv_group('abonado','nombre_abonado')
            celda = getv_group('cod_celda_inicial','celda')
            direccion = getv_group('ubicacion_inicio','direccion')

            # Formatear azimuts sin .0
            def _fmt_az(v):
                """Formatea azimut: entero si es entero, decimal sin ceros trailing, o string original."""
                try:
                    f = float(v)
                    return str(int(f)) if f.is_integer() else str(f).rstrip('0').rstrip('.')
                except:
                    return str(v)

            az_p_disp = _fmt_az(az_principal)
            secundarios_text = ", ".join(
                f"{_fmt_az(a)}° ({c})"
                for a, c in sorted(
                    ((a, c) for a, c in datos["azimuts"].items() if a != az_principal),
                    key=lambda t: t[1], reverse=True
                )
            )

            # Etiqueta configurable
            try:
                _label_dir_top = config.get("kml", {}).get("labels", {}).get("direccion", "Direccion")
            except Exception:
                _label_dir_top = "Direccion"

            def _norm_text(s):
                """Normaliza texto: NFKD, sin acentos, espacios normalizados, minúsculas."""
                if s is None:
                    return ""
                try:
                    s = str(s)
                    s = unicodedata.normalize("NFKD", s)
                    s = "".join(ch for ch in s if not unicodedata.combining(ch))
                    s = re.sub(r"\s+", " ", s).strip().lower()
                    return s
                except Exception:
                    return str(s).strip().lower()

            # En carpetas TOP: Mostrar "Antena:" siempre + "Dirección:" solo si es diferente
            _ant_line = f"<b>Antena:</b> {antena}<br>"
            _dir_line = ""
            if direccion not in (None, "", "SinInf"):
                # Mostrar dirección solo si es diferente de antena (evitar redundancia)
                if _norm_text(direccion) != _norm_text(antena):
                    _dir_line = f"<b>{_label_dir_top}:</b> {direccion}<br>"

            desc_core = f"""
<b>Total de activaciones:</b> {total}<br>
<hr>
<b>Número:</b> {numero}<br>
<b>IMEI:</b> {imei}<br>
<b>Alias:</b> {alias}<br>
<b>Usuario:</b> {usuario}<br>
<b>Abonado:</b> {abonado}<br>
<hr>
{_ant_line}<b>Lat:</b> {lat} &nbsp; <b>Long:</b> {lon}<br>
<b>Celda:</b> {celda}<br>
{_dir_line}
<hr>
<b>Azimut principal:</b> {az_p_disp}° ({cuenta_principal} veces)<br>
<b>Azimuts secundarios:</b> {secundarios_text if secundarios_text else 'Ninguno'}
"""

            _crear_feature_kml(container, antena, lon, lat, desc_core, 
                             az_principal, config, azimuts_extra=az_sec)

    # 4) Poblar carpeta "por_rango_horario" (opcional)
    if incluir_rango and rango_folders:
        for clave, folder in rango_folders.items():
            lst = items_by_rango.get(clave, [])
            if lst:
                _crear_dedup(folder, lst, pair_por_rango.get(clave, {}))

    # 5) Top N Global (deduplicado)
    _n_eff = None if (isinstance(_topN_ant, int) and _topN_ant <= 0) else int(_topN_ant)
    topN_global = ant_global.most_common(_n_eff)
    
    for i, (ant, _) in enumerate(topN_global, start=1):
        sub = f_top_global.newfolder(name=f"{i}_{ant}")
        lst = [it for it in items if it["antena"] == ant]
        _crear_dedup(sub, lst, pair_global)

    # 6) Top N por rango horario (deduplicado)
    for clave, padre in top_rango_folders.items():
        c = ant_por_rango.get(clave, None)
        if not c:
            continue
        topN_r = c.most_common(_n_eff)
        items_r = items_by_rango.get(clave, [])
        for i, (ant, _) in enumerate(topN_r, start=1):
            sub = padre.newfolder(name=f"{i}_{ant}")
            lst = [it for it in items_r if it["antena"] == ant]
            _crear_dedup(sub, lst, pair_por_rango.get(clave, {}))

    # === GUARDAR ARCHIVOS ===
    solo_kmz = bool(config.get("salida", {}).get("solo_kmz", False))

    if not solo_kmz:
        try:
            kml.save(archivo_salida_kml)
        except Exception:
            pass

    try:
        kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
        kml.savekmz(kmz_path)
    except Exception:
        pass

    return archivo_salida_kml, descartadas


# ============================================================================
# GENERACIÓN KML MODO PUNTOS LIBRES (QC MANUAL)
# ============================================================================
def generar_kml_puntos_libres(df, archivo_salida_kml, config):
    """
    Genera un archivo KMZ con puntos libres (antenas) usando ícono blanco y color de etiqueta.
    Filtra coordenadas inválidas y aplica estilos según config.
    
    MODO: QC Manual (puntos simples sin estructura de carpetas)
    USO: Wizard QC manual en script_principal_bitacoras_refactory.py (L5149)
    
    MIGRADO DE: kml_generador.py (raíz) → Epic 14 Consolidación KML
    FECHA: 26/12/2025
    
    Args:
        df (pd.DataFrame): DataFrame con los puntos a graficar.
        archivo_salida_kml (str): Ruta de salida para el archivo KML/KMZ.
        config (dict): Diccionario de configuración global.
        
    Returns:
        tuple: (ruta_kmz, descartadas) - Ruta del archivo KMZ generado y número de coordenadas descartadas
        
    CARACTERÍSTICAS:
    - Ícono blanco (wht-blank.png) para todos los puntos
    - Color de etiqueta según theme_hex de config
    - Filtrado de coordenadas inválidas (S/I, None, fuera de rango)
    - Descripción simple: detalle + direccion
    - Solo genera KMZ (no KML por separado)
    """
    kml = Kml()
    descartadas = 0
    
    # Obtener estilo del config
    color_hex = config.get("style", {}).get("theme_hex", "#ff0000")
    abgr_color = hex_to_kml_color(color_hex)
    icon_url = "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png"

    for idx, row in df.iterrows():
        lat = row.get("lat", None)
        lon = row.get("long", None)
        nombre = row.get("antena", "Punto")
        detalle = row.get("detalle", "")
        direccion = row.get("direccion", "")
        
        # Filtrar coordenadas inválidas
        if lat in (None, "", "Sin Inf.", "S/I") or lon in (None, "", "Sin Inf.", "S/I"):
            descartadas += 1
            continue
            
        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            descartadas += 1
            continue
            
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            descartadas += 1
            continue

        # Crear punto KML
        pnt = kml.newpoint(name=nombre, coords=[(lon, lat)])
        desc = f"{detalle}\n{direccion}".strip()
        if desc:
            pnt.description = desc
            
        # Estilo: ícono blanco y color solo para la etiqueta
        pnt.style.iconstyle.icon.href = icon_url
        pnt.style.iconstyle.scale = 1.2
        pnt.style.labelstyle.color = abgr_color
        pnt.style.labelstyle.scale = 1.2

    # Solo guardar KMZ
    try:
        kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
        kml.savekmz(kmz_path)
        
        # Opcional: copiar a carpeta separada kmz/
        try:
            import shutil
            if bool((config or {}).get("salida", {}).get("separar_kml_kmz", False)):
                parent = os.path.basename(os.path.dirname(archivo_salida_kml)).lower()
                if parent == "kml":
                    base_dir = os.path.dirname(os.path.dirname(archivo_salida_kml))
                    kmz_dir = os.path.join(base_dir, "kmz")
                    os.makedirs(kmz_dir, exist_ok=True)
                    shutil.copy2(kmz_path, os.path.join(kmz_dir, os.path.basename(kmz_path)))
        except Exception:
            pass
            
    except Exception:
        kmz_path = None
        
    return kmz_path, descartadas
