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
from tz_core.kml_writer import Kml
import tz_core.kml_writer as sk

# Imports internos del framework tz_core
from tz_core.geo_utils import calcular_punto_final, generar_coordenadas_circulo
from tz_core.time_utils import clasificar_rango_sv, RANGOS_SV, normalize_hour_to_hhmmss
from tz_core.color_utils import hex_to_kml_color
from tz_core.format_utils import agregar_bloque, armar_descripcion_compacta
from tz_core.logging_utils import log
from tz_core.bitacora_normalization import (
    normalize_imei,
    normalize_msisdn,
    parse_date_series,
    clasificar_confiabilidad_duracion,
    DuracionEstado,
    es_valor_significativo,
)
from tz_core.site_inference import construir_identificador_sitio
from tz_core.validation_utils import tiene_valor
from tz_core.security_escaping import esc_kml_value as _esc

# Separador HTML compacto (usado en descripciones)
HR_COMPACT = '<div style="border-top:1px solid #bbb; margin:1px 0; height:0;"></div>'

# Cache global de estilos KML reutilizables (performance)
_REUSABLE_STYLES = None

# href del ícono de punto embebido en el KMZ para esta generación (AUD-08:
# reemplaza la dependencia remota a maps.google.com/mapfiles/...). Se
# resuelve una vez por documento vía kml.addfile() y se reutiliza en todos
# los estilos de punto; si el asset local no está disponible queda en None
# y el visor usa su propio ícono de pin por defecto (sin red).
_ICON_HREF = None
_KML_POINT_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "kml_point_icon.png")

# Nota de alcance breve, para burbujas individuales de sitios inferidos
# (HITO 2B). La nota extensa (con la mención a "TZ Analyzer") solo aparece
# una vez, como leyenda general del documento — ver GUIA_SITIOS_INFERIDOS_KML.
NOTA_SITIO_INFERIDO_BURBUJA = "Sitio inferido por coordenadas normalizadas."

GUIA_SITIOS_INFERIDOS_KML = (
    "Uno o más sitios fueron identificados mediante coordenadas normalizadas "
    "debido a que la bitácora no proporcionó nombre o código de antena. Estos "
    "identificadores son internos de TZ Analyzer."
)


def _resolver_nombre_punto_kml(row, lat: float, lon: float) -> Tuple[str, bool]:
    """Resuelve el nombre visible de un punto KML y si es un sitio inferido.

    Prioridad (HITO 2B):
      1. antena_analitica, si existe y es significativa (ya prioriza antena
         real sobre sitio inferido por coordenadas — ver tz_core.site_inference).
      2. antena original, para bitácoras/llamadas que no pasaron por
         agregar_sitio_analitico (p.ej. DataFrames sintéticos en pruebas).
      3. Identificador neutral SITIO_<lat>_<long> derivado localmente de las
         coordenadas ya validadas del punto — nunca el literal genérico
         "Antena", que fusionaría puntos distintos sin antena reportada.

    Returns:
        (nombre_visible, es_sitio_inferido)
    """
    antena_analitica = row.get("antena_analitica", None)
    if es_valor_significativo(antena_analitica):
        valor = str(antena_analitica).strip()
        es_inferido = bool(row.get("sitio_inferido", False))
        return valor, es_inferido

    antena_original = row.get("antena", None)
    if es_valor_significativo(antena_original):
        return str(antena_original).strip(), False

    identificador = construir_identificador_sitio(lat, lon)
    if identificador:
        return identificador, True

    return "Antena", False


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

    # === DETERMINAR SI HAY AZIMUT VÁLIDO ===
    az_valido = False
    az = None
    try:
        _az_c = float(azimut_float)
        if not math.isnan(_az_c):
            az = _az_c % 360.0
            az_valido = True
    except Exception:
        pass

    # === INICIALIZAR ESTILOS REUTILIZABLES ===
    if _REUSABLE_STYLES is None:
        style_cfg = {}
        try:
            style_cfg = config.get("style", {}) if isinstance(config, dict) else {}
        except Exception:
            style_cfg = {}
        
        # Extraer parámetros de estilo (o defaults)
        theme_hex = style_cfg.get("theme_hex", "#ff00ff")
        # AUD-08: sin override explícito de config, usar el ícono local
        # embebido en el KMZ (_ICON_HREF); si no está disponible, no fijar
        # href y dejar que el visor use su ícono de pin por defecto (nunca
        # se cae de vuelta a la URL remota de maps.google.com).
        pin_icon_url = style_cfg.get("pin_icon_url") or _ICON_HREF
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
        if pin_icon_url:
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

        s_circle = sk.Style()
        # Círculo de referencia: solo contorno, sin relleno interior (diseño
        # aprobado — evita relleno tenue acumulado con múltiples activaciones
        # superpuestas sobre la misma antena). fill=0 en lugar de depender
        # solo de alpha 00, para que la intención quede explícita en el KML.
        s_circle.polystyle.color = hex_to_kml_color(theme_hex, 0)
        s_circle.polystyle.fill = 0
        s_circle.polystyle.outline = 1
        s_circle.linestyle.color = hex_to_kml_color(theme_hex, 200)
        s_circle.linestyle.width = 1.5

        _REUSABLE_STYLES = {
            "pin":    s_pin,
            "line":   s_line,
            "cone":   s_cone,
            "circle": s_circle,
        }

    # === CREAR PUNTO ===
    p = container.newpoint(name=nombre_compacto, coords=[(lon, lat)])
    if descripcion:
        p.description = f'<div style="line-height:1.10; font-size:14px">{descripcion}</div>'
    p.style = _REUSABLE_STYLES["pin"]

    # === SIEMPRE: círculo de referencia ===
    try:
        _radio = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
        coords_circulo = generar_coordenadas_circulo(lat, lon, _radio)
        circulo = container.newpolygon(name="Radio de referencia")
        circulo.outerboundaryis = coords_circulo
        circulo.style = _REUSABLE_STYLES["circle"]
    except Exception:
        pass

    # === SOLO SI AZIMUT VÁLIDO: línea y cono ===
    if az_valido:
        try:
            az_dist_km = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
            cone_half = (
                (config or {}).get("kml", {}).get("cone", {}).get("half_degrees")
                or (config or {}).get("style", {}).get("cone_half_degrees", 60)
            )
            cone_half = int(cone_half)
        except Exception:
            az_dist_km = 1.0
            cone_half = 60

        latf, lonf = calcular_punto_final(lat, lon, az, az_dist_km)
        linea = container.newlinestring(
            name=f"Azimut {int(round(az))}°",
            coords=[(lon, lat), (lonf, latf)]
        )
        linea.style = _REUSABLE_STYLES["line"]

        coords_cono = []
        paso = 5
        for ang in range(-cone_half, cone_half + 1, paso):
            lat_p, lon_p = calcular_punto_final(lat, lon, az + ang, az_dist_km)
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
                except Exception:
                    continue
                latf2, lonf2 = calcular_punto_final(lat, lon, az_s, az_dist_km)
                linea2 = container.newlinestring(
                    name=f"Azimut {int(round(az_s))}° (sec.)",
                    coords=[(lon, lat), (lonf2, latf2)]
                )
                linea2.style = _REUSABLE_STYLES["line"]
                coords_cono2 = []
                for ang in range(-cone_half, cone_half + 1, paso):
                    lat_p2, lon_p2 = calcular_punto_final(lat, lon, az_s + ang, az_dist_km)
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
    override_tops: Optional[dict] = None,
    duracion_estado: Optional[DuracionEstado] = None,
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
    global _REUSABLE_STYLES
    _REUSABLE_STYLES = None  # reset para que cada bitácora use su propio color
    if df.empty:
        log("[WARN] generar_kml: DataFrame vacío, generando KML sin puntos")

    # Estado único de confiabilidad de duración (Hito 2C): se calcula una sola
    # vez (o se recibe ya resuelto desde el pipeline de ingesta) y se propaga
    # a todas las burbujas para que KML/KMZ sea coherente con el informe HTML.
    if duracion_estado is None:
        duracion_estado = clasificar_confiabilidad_duracion(df)

    kml = Kml()
    descartadas = 0

    # Ícono de punto embebido en el KMZ (AUD-08): se registra una sola vez
    # por documento con kml.addfile() y todos los estilos de punto reusan el
    # mismo href. Sin dependencia remota a maps.google.com.
    global _ICON_HREF
    _ICON_HREF = None
    if os.path.exists(_KML_POINT_ICON_PATH):
        try:
            _ICON_HREF = kml.addfile(_KML_POINT_ICON_PATH)
        except Exception:
            _ICON_HREF = None

    # ScreenOverlay permanente (Nivel 1 de advertencia — spec sección 2.8)
    _assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    _png_path   = os.path.join(_assets_dir, "kmz_aviso_orientativo.png")
    if os.path.exists(_png_path):
        try:
            _png_href = kml.addfile(_png_path)
            _overlay  = kml.newscreenoverlay(name="Representación orientativa")
            _overlay.icon.href = _png_href
            _overlay.overlayxy = sk.OverlayXY(
                x=0, y=1,
                xunits=sk.Units.fraction, yunits=sk.Units.fraction
            )
            _overlay.screenxy = sk.ScreenXY(
                x=0.01, y=0.96,
                xunits=sk.Units.fraction, yunits=sk.Units.fraction
            )
            _overlay.size = sk.Size(
                x=360, y=60,
                xunits=sk.Units.pixels, yunits=sk.Units.pixels
            )
        except Exception:
            pass

    # === NORMALIZACIÓN DE FECHA/HORA ===
    if "fecha" in df.columns:
        try:
            _dt_series = parse_date_series(df["fecha"], dayfirst=True)
            df["_dt_kml_fecha"] = _dt_series
        except Exception:
            df["_dt_kml_fecha"] = pd.NaT
        try:
            df["fecha"] = df["_dt_kml_fecha"].dt.strftime("%d/%m/%Y")
            df["fecha"] = df["fecha"].fillna("Sin Inf.")
        except Exception:
            df["fecha"] = "Sin Inf."
    else:
        df["_dt_kml_fecha"] = pd.NaT
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

    # Columnas auxiliares para ordenamiento cronológico robusto
    df["_fila_original"] = range(len(df))
    try:
        df["_hora_kml_sort"] = pd.to_timedelta(
            df["hora"].replace("Sin Inf.", pd.NA),
            errors="coerce"
        )
        df["_hora_ausente"] = df["_hora_kml_sort"].isna()
    except Exception:
        df["_hora_kml_sort"] = pd.NaT
        df["_hora_ausente"] = True

    # Ordenar cronológicamente: fecha → hora ausente → hora → fila original
    try:
        df = df.sort_values(
            by=["_dt_kml_fecha", "_hora_ausente", "_hora_kml_sort", "_fila_original"],
            kind="stable",
            na_position="last"
        )
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

        # Nombre y descripción del punto (HITO 2B: antena_analitica > antena > sitio inferido)
        nombre_punto, es_sitio_inferido = _resolver_nombre_punto_kml(row, lat, lon)

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
            "sitio_inferido": es_sitio_inferido,
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

    # HITO 2B: nota general única cuando el KMZ contiene al menos un sitio inferido
    hay_sitio_inferido_global = any(it.get("sitio_inferido") for it in items)

    # Pre-calcular numeración y padding antes de construir carpetas
    total_activaciones = len(items)
    fechas_validas_set = {
        it["fecha"] for it in items
        if isinstance(it.get("fecha"), str) and it["fecha"] != "Sin Inf."
    }
    total_dias = len(fechas_validas_set)
    padding_dias = max(3, len(str(total_dias)))
    padding_act  = max(4, len(str(total_activaciones)))
    if total_activaciones > 300:
        log(f"[WARNING] KMZ: {total_activaciones} activaciones — puede afectar rendimiento en Google Earth.")
        print(f"\n[AVISO KMZ] {total_activaciones} activaciones detectadas. "
              f"El KMZ puede tardar en cargar en Google Earth.")

    # === MODO FLAT (sin carpetas) ===
    if flat:
        for it in items:
            n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
            desc_comp = armar_descripcion_compacta(
                it, n_all,
                suprimir_direccion_si_igual=False,
                config=config,
                hr_compact=HR_COMPACT,
                duracion_estado=duracion_estado,
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

    # Carpeta LEA PRIMERO — primera en el panel lateral
    _radio_lea    = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
    _origen_lea   = (config or {}).get("kml", {}).get("radio_origen", "predeterminado")
    _half_lea     = int(
        (config or {}).get("kml", {}).get("cone", {}).get("half_degrees")
        or (config or {}).get("style", {}).get("cone_half_degrees", 60)
    )
    _origen_legible = {
        "predeterminado": "valor predeterminado del sistema",
        "manual":         "valor definido por el usuario",
        "operadora":      "valor proporcionado por la operadora",
    }.get(str(_origen_lea).strip().lower(), str(_origen_lea).strip() or "no especificado")
    f_lea = raiz.newfolder(name="\u24d8 GU\u00cdA DEL MAPEO")
    f_lea.open = 0
    f_lea.description = (
        f"<b>Par\u00e1metros del an\u00e1lisis</b><br>"
        f"TZ Analyzer genera los siguientes elementos gr\u00e1ficos:<br><br>"
        f"<b>Radio gr\u00e1fico:</b> {_radio_lea} km<br>"
        f"<b>Apertura del sector:</b> {_half_lea * 2}\u00b0 (\u00b1{_half_lea}\u00b0)<br>"
        f"<b>Configuraci\u00f3n del radio:</b> {_esc(_origen_legible)}<br><br>"
        f"<b>\u00bfQu\u00e9 significa el c\u00edrculo?</b><br>"
        f"Representa una distancia gr\u00e1fica de referencia alrededor de la antena "
        f"registrada y facilita la lectura espacial del mapa<br><br>"
        f"<b>\u00bfQu\u00e9 significa el sector?</b><br>"
        f"Representa gr\u00e1ficamente la orientaci\u00f3n del sector conforme al azimut "
        f"registrado en la bit\u00e1cora y se muestra \u00fanicamente cuando dicho dato est\u00e1 disponible"
    )
    if hay_sitio_inferido_global:
        f_lea.description += (
            f"<br><br><b>\u00bfQu\u00e9 son los sitios SITIO_&lt;lat&gt;_&lt;long&gt;?</b><br>"
            f"{GUIA_SITIOS_INFERIDOS_KML}"
        )

    # Carpeta principal: todas_las_antenas
    f_todas = raiz.newfolder(name="todas_las_antenas")
    f_todas.open = 0
    folders_por_fecha = {}

    # Parámetros de radio y apertura para descripciones y LEA PRIMERO
    _radio_kml    = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
    _radio_origen = (config or {}).get("kml", {}).get("radio_origen", "predeterminado")
    _cone_half_kml = int(
        (config or {}).get("kml", {}).get("cone", {}).get("half_degrees")
        or (config or {}).get("style", {}).get("cone_half_degrees", 60)
    )

    # Crear carpetas de fecha con numeración secuencial
    fechas_validas_dt = sorted([
        datetime.strptime(f, "%d/%m/%Y")
        for f in fechas_validas_set
    ])
    for num_dia_idx, fch in enumerate(fechas_validas_dt, start=1):
        num_dia = str(num_dia_idx).zfill(padding_dias)
        nombre_dia = f"{num_dia} — {fch.strftime('%Y-%m-%d')}"
        carpeta_dia = f_todas.newfolder(name=nombre_dia)
        carpeta_dia.open = 0
        folders_por_fecha[fch.strftime("%d/%m/%Y")] = carpeta_dia

    # Carpeta para registros sin fecha (lazy init)
    folder_sin_fecha = None

    # Carpeta opcional: por_rango_horario
    incluir_rango = False
    try:
        incluir_rango = bool(config.get("kml", {}).get("incluir_por_rango_horario", False))
    except Exception:
        pass
    
    if incluir_rango:
        f_rangos = raiz.newfolder(name="por_rango_horario")
        f_rangos.open = 0
        rango_folders = {
            "manana":    f_rangos.newfolder(name=RANGOS_SV["manana"][0]),
            "tarde":     f_rangos.newfolder(name=RANGOS_SV["tarde"][0]),
            "noche":     f_rangos.newfolder(name=RANGOS_SV["noche"][0]),
            "madrugada": f_rangos.newfolder(name=RANGOS_SV["madrugada"][0]),
        }
        for folder in rango_folders.values():
            folder.open = 0
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
    f_top_global.open = 0
    f_top_por_rango = raiz.newfolder(name=_name_top_por_rango)
    f_top_por_rango.open = 0
    top_rango_folders = {
        "manana":    f_top_por_rango.newfolder(name=RANGOS_SV["manana"][0]),
        "tarde":     f_top_por_rango.newfolder(name=RANGOS_SV["tarde"][0]),
        "noche":     f_top_por_rango.newfolder(name=RANGOS_SV["noche"][0]),
        "madrugada": f_top_por_rango.newfolder(name=RANGOS_SV["madrugada"][0]),
    }
    for folder in top_rango_folders.values():
        folder.open = 0

    # === LLENAR CARPETAS ===

    # Poblar "todas_las_antenas": una subcarpeta por activación
    contador_act = 0
    for it in items:
        contador_act += 1
        num_act         = str(contador_act).zfill(padding_act)
        hora_display    = str(it.get("hora", "SinInf"))[:8]
        antena_truncada = str(it.get("antena", "Antena"))[:30]
        nombre_carpeta_act = f"{num_act} — {hora_display} — {antena_truncada}"

        _carpeta_fecha = folders_por_fecha.get(it["fecha"])
        if _carpeta_fecha is None:
            if folder_sin_fecha is None:
                folder_sin_fecha = f_todas.newfolder(name="Sin fecha determinada")
                folder_sin_fecha.open = 0
            _carpeta_fecha = folder_sin_fecha

        _carpeta_act = _carpeta_fecha.newfolder(name=nombre_carpeta_act)
        _carpeta_act.open = 0

        _az_val = it.get("azimut_f")
        _az_desc_valido = False
        _az_desc = None
        try:
            _az_desc = float(_az_val)
            _az_desc_valido = not math.isnan(_az_desc)
        except (TypeError, ValueError):
            pass
        _az_line = (
            f"<b>Azimut:</b> {int(round(_az_desc)) % 360}°<br>"
            if _az_desc_valido else ""
        )
        _apertura_line = (
            f"<b>Apertura:</b> {_cone_half_kml * 2}°<br>"
            if _az_desc_valido else ""
        )
        _carpeta_act.description = (
            f"<b>Activación global:</b> {num_act}<br>"
            f"<b>Fecha y hora:</b> {_esc(it.get('fecha', 'Sin Inf.'))} {_esc(hora_display)}<br>"
            f"<b>Antena:</b> {_esc(it.get('antena', ''))}<br>"
            f"{_az_line}"
            f"<b>Radio gráfico:</b> {_radio_kml} km<br>"
            f"{_apertura_line}"
            f"<b>Origen del radio:</b> {_esc(_radio_origen)}<br>"
            f"<hr>"
            f"<i>Representación gráfica construida a partir de la antena registrada, "
            f"el radio configurado y el azimut disponible en la bitácora</i>"
        )

        n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
        desc_comp = armar_descripcion_compacta(
            it, n_all,
            suprimir_direccion_si_igual=True,
            config=config,
            hr_compact=HR_COMPACT,
            duracion_estado=duracion_estado,
        )
        _crear_feature_kml(
            _carpeta_act,
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
                    "lon": it["lon"],
                    "sitio_inferido": bool(it.get("sitio_inferido")),
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
            _ant_line = f"<b>Antena:</b> {_esc(antena)}<br>"
            _dir_line = ""
            if direccion not in (None, "", "SinInf"):
                # Mostrar dirección solo si es diferente de antena (evitar redundancia)
                if _norm_text(direccion) != _norm_text(antena):
                    _dir_line = f"<b>{_label_dir_top}:</b> {_esc(direccion)}<br>"

            # Nota breve de sitio inferido (HITO 2B) — la nota extensa aparece
            # una sola vez, como leyenda general del documento.
            _sitio_inferido_line = (
                '<i style="color:#666;">Sitio inferido por coordenadas normalizadas.</i><br>'
                if datos.get("sitio_inferido") else ""
            )

            desc_core = f"""
<b>Total de activaciones:</b> {total}<br>
<hr>
<b>Número:</b> {_esc(numero)}<br>
<b>IMEI:</b> {_esc(imei)}<br>
<b>Alias:</b> {_esc(alias)}<br>
<b>Usuario:</b> {_esc(usuario)}<br>
<b>Abonado:</b> {_esc(abonado)}<br>
<hr>
{_ant_line}<b>Lat:</b> {lat} &nbsp; <b>Long:</b> {lon}<br>
<b>Celda:</b> {_esc(celda)}<br>
{_dir_line}
{_sitio_inferido_line}<hr>
<b>Azimut principal:</b> {_esc(az_p_disp)}° ({cuenta_principal} veces)<br>
<b>Azimuts secundarios:</b> {_esc(secundarios_text) if secundarios_text else 'Ninguno'}
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
    # AUD-08: ícono local embebido en el KMZ; sin dependencia remota a
    # maps.google.com. Si el asset no está disponible, no se fija href y el
    # visor usa su ícono de pin por defecto.
    icon_url = None
    if os.path.exists(_KML_POINT_ICON_PATH):
        try:
            icon_url = kml.addfile(_KML_POINT_ICON_PATH)
        except Exception:
            icon_url = None

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
        lineas_desc = [_esc(str(v).strip()) for v in (detalle, direccion) if tiene_valor(v)]
        if lineas_desc:
            pnt.description = "\n".join(lineas_desc)
            
        # Estilo: ícono blanco y color solo para la etiqueta
        if icon_url:
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
