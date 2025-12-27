"""
kml_generador.py — ARCHIVO OBSOLETO Y ARCHIVADO
================================================

⚠️ ADVERTENCIA: NO USAR ESTE ARCHIVO - SOLO REFERENCIA HISTÓRICA
📅 Fecha de archivado: 27/12/2025
🎯 Razón: Consolidación KML completada en Epic 14

MIGRACIÓN COMPLETA A: tz_core/kml_generator.py
-----------------------------------------------
Este archivo fue el generador KML original usado en modo QC manual (puntos libres).
Todas sus funciones han sido migradas y mejoradas en el módulo profesional.

FUNCIONES MIGRADAS:
-------------------
✅ generar_kml_puntos_libres() → tz_core/kml_generator.py (líneas ~730-833)
   - Generación de puntos libres con estilos personalizados
   - Filtrado de coordenadas inválidas
   - Soporte para íconos y etiquetas coloreadas
   - Exportación KMZ con separación opcional de carpetas

✅ hex_to_abgr() → tz_core/color_utils.py
   - Conversión de colores HEX a formato ABGR (Google Earth)
   - Usado por todos los generadores KML del sistema

ARQUITECTURA UNIFICADA:
-----------------------
Epic 14 consolidó toda la generación KML en un solo módulo profesional:
- tz_core/kml_generator.py (833 líneas)
  * generar_kml(): Modo complejo con carpetas/TOPs/estadísticas
  * generar_kml_puntos_libres(): Modo simple para QC manual
  * Estilos reusables y configuración centralizada
  * Validación robusta de coordenadas
  * Soporte completo para azimut y metadatos

CONTEXTO HISTÓRICO:
-------------------
Este archivo fue creado originalmente para el modo QC manual del TZ Analyzer,
generando KML con puntos libres sin estructura de carpetas. Durante la fase
de modularización (Epics 10-14), se migró toda su funcionalidad al módulo
unificado tz_core/kml_generator.py, eliminando duplicación de código y 
estableciendo una arquitectura KML profesional.

PARA USO ACTUAL: import from tz_core.kml_generator import generar_kml_puntos_libres

COMMITS RELACIONADOS:
---------------------
- 72fef1c: Epic 13 - Extracción generador KML a tz_core/
- 4599647: Epic 14 - Consolidación KML puntos libres
- c332599: Fix campo Antena en burbujas TOP
- d08a9e0: MERGE Epic 10-14 a main
- 9aa7039: Cleanup backup Epic 13

LÍNEAS ELIMINADAS DEL MONOLITO: 1,260 líneas (backup function)
ESTADO FINAL MONOLITO: 5,994 líneas (-516 desde baseline, -7.9%)

====================================================================
        CÓDIGO ORIGINAL ARCHIVADO PARA REFERENCIA
====================================================================
"""

# === Utilidad para convertir color HEX a ABGR (simplekml) ===
def hex_to_abgr(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f'ff{b}{g}{r}'
    return 'ff0000ff'  # fallback azul

# === Generador de puntos libres ===
def generar_kml_puntos_libres(df, archivo_salida_kml, config):
    """
    Genera un archivo KMZ con puntos libres (antenas) usando ícono blanco y color de etiqueta.
    Filtra coordenadas inválidas y aplica estilos según config.

    Args:
        df (pd.DataFrame): DataFrame con los puntos a graficar.
        archivo_salida_kml (str): Ruta de salida para el archivo KML/KMZ.
        config (dict): Diccionario de configuración global.
    Returns:
        None. El archivo KMZ se guarda en disco.
    """
    kml = Kml()
    descartadas = 0
    color_hex = config.get("style", {}).get("theme_hex", "#ff0000")
    abgr_color = hex_to_abgr(color_hex)
    icon_url = "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png"

    for idx, row in df.iterrows():
        lat = row.get("lat", None)
        lon = row.get("long", None)
        nombre = row.get("antena", "Punto")
        detalle = row.get("detalle", "")
        direccion = row.get("direccion", "")
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
    import os
    try:
        kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
        kml.savekmz(kmz_path)
        try:
            from shutil import copy2
            if bool((config or {}).get("salida", {}).get("separar_kml_kmz", False)):
                parent = os.path.basename(os.path.dirname(archivo_salida_kml)).lower()
                if parent == "kml":
                    base_dir = os.path.dirname(os.path.dirname(archivo_salida_kml))
                    kmz_dir = os.path.join(base_dir, "kmz")
                    os.makedirs(kmz_dir, exist_ok=True)
                    copy2(kmz_path, os.path.join(kmz_dir, os.path.basename(kmz_path)))
        except Exception:
            pass
    except Exception:
        pass
    return kmz_path, descartadas
"""
kml_generador.py — Generación de KML/KMZ

Secciones:
  1) Imports y constantes
  2) Geodesia / cálculos de soporte
  3) Armado de descripciones (HTML para burbujas)
  4) Generación KML principal
"""

# === 1) Imports y constantes ===
from simplekml import Kml, Style
import math
import pandas as pd
import os
import shutil

# === 2) Geodesia / cálculos de soporte ===
def calcular_punto_final(lat, lon, azimut, distancia_km):
    """
    Calcula el punto final a partir de (lat, lon), un azimut (grados)
    y una distancia (km) sobre una esfera de radio R=6371 km.
    Devuelve (lat_final, lon_final) en grados decimales.
    """
    R = 6371.0

    # A radianes
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    azimut_rad = math.radians(azimut)

    # Fórmulas de navegación esférica
    lat_final = math.asin(
        math.sin(lat_rad) * math.cos(distancia_km / R)
        + math.cos(lat_rad) * math.sin(distancia_km / R) * math.cos(azimut_rad)
    )

    lon_final = lon_rad + math.atan2(
        math.sin(azimut_rad) * math.sin(distancia_km / R) * math.cos(lat_rad),
        math.cos(distancia_km / R) - math.sin(lat_rad) * math.sin(lat_final),
    )

    # De vuelta a grados
    return math.degrees(lat_final), math.degrees(lon_final)

def generar_kml(df, archivo_salida_kml, top_5_antenas, antenas_por_periodo):
    """Auto-doc: función generar_kml (docstring generado para estructurar)."""
    kml = Kml()
    df = df.sort_values(by=["fecha", "hora"])
    descartadas = 0
    for _, row in df.iterrows():
        if row["lat"] == "S/I" or row["lon"] == "S/I":
            continue
        lat, lon = float(row["lat"]), float(row["lon"])
        azimut = float(row["azimut"]) if "azimut" in row and row["azimut"] != "S/I" else 0
        
        # Normalizar coordenadas (acepta coma decimal y strings)
        def _to_float(v):
            if v is None:
                return None
            s = str(v).strip().replace(",", ".")
            try:
                return float(s)
            except Exception:
                return None

        lat = _to_float(lat)
        lon = _to_float(lon)
        if lat is None or lon is None:
            continue  # saltar esta fila; no abortar toda la exportación


        punto = kml.newpoint(name=row["antena"], coords=[(lon, lat)])

        # --- Helpers locales para limpiar IDs y omitir vacíos en popup ---
        def _fmt_id(v):
            """
            Formatea un ID (TEL/IMEI):
            - Si es entero (inclusive '352005090177850.0' o '3.5200509017785e+14'), devuelve sin decimales ni exponente.
            - Si no es un entero exacto, devuelve el string original (no trunca).
            - 'S/I', 'SinInf', 'sin inf' → devuelve "" (para que el caller lo omita).
            - Si no es numérico, devuelve el string tal cual.
            """
            s = "" if v is None else str(v).strip()
            if not s:
                return s

            low = s.lower()
            if low in {"sininf", "sininf.", "sin inf", "s/i", "s/i."}:
                return ""

            # Normalizar separadores y espacios para la detección numérica
            s_try = s.replace(" ", "").replace(",", ".")

            import re
            from decimal import Decimal, InvalidOperation

            # ¿Parece número? (permite exponente)
            if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?", s_try, flags=re.IGNORECASE):
                return s  # no numérico → devolver tal cual

            try:
                d = Decimal(s_try)
                # Si es entero exacto → devolver sin exponentes ni decimales
                if d == d.to_integral_value():
                    return str(int(d))
                # Si tiene fracción, no "inventar" formato: devolvemos el original
                return s
            except InvalidOperation:
                return s


        def _add_if(desc_list, label, value):
            s = "" if value is None else str(value).strip()
            if not s or s.lower() in {"sininf", "sininf.", "sin inf", "s/i", "s/i."}:
                return
            desc_list.append(f"{label}: {s}")

        # Construir descripción omitiendo vacíos y formateando IDs
        desc = []
        _add_if(desc, "Fecha", row.get("fecha"))
        _add_if(desc, "Hora", row.get("hora"))

        # TEL / IMEI (formateados y omitidos si quedan vacíos)
        tel_fmt = _fmt_id(row.get("tel"))
        if tel_fmt:
            desc.append(f"Tel: {tel_fmt}")

        imei_fmt = _fmt_id(row.get("imei"))
        if imei_fmt:
            desc.append(f"IMEI: {imei_fmt}")


        # Separador visual
        desc.append("<hr>")

        _add_if(desc, "Antena", row.get("antena"))
        _add_if(desc, "Detalle", row.get("direccion"))

        punto.description = "<br>".join(desc)
        # -- Dibujar la línea de azimut si es válido (permitir 0°) --
        try:
            az_val = float(azimut)
        except Exception:
            az_val = float('nan')

        if not math.isnan(az_val):
            az_val = az_val % 360.0  # normaliza a 0..359.999
            # 1.5 km por defecto para que se vea claro en GE
            lat2, lon2 = calcular_punto_final(lat, lon, az_val, 1.5)
            line = kml.newlinestring(
                name=f"Azimut {int(round(az_val))}°",
                coords=[(lon, lat), (lon2, lat2)]
            )
            # Estilo sencillo y visible; ABGR en KML (magenta)
            line.style.linestyle.color = "ffff00ff"
            line.style.linestyle.width = 2

    kml.save(archivo_salida_kml)
    return archivo_salida_kml

# === Generador de antenas ===
def generar_kml_antenas(df: pd.DataFrame, archivo_salida_kml: str, config: dict, flat: bool=False):
    """Genera KML/KMZ para antenas usando estilos reusables y azimut opcional."""
    kml = Kml(); descartadas = 0
    styles = _crear_estilos_reusables(config)
    solo_kmz = bool((config or {}).get("salida", {}).get("solo_kmz", False))

    # Normalizar fecha/hora como strings tolerantes
    if "fecha" in df.columns:
        try: df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
        except Exception: df["fecha"] = "Sin Inf."
    else: df["fecha"] = "Sin Inf."
    if "hora" in df.columns:
        try: df["hora"] = df["hora"].astype(str).str[:8]
        except Exception: df["hora"] = "Sin Inf."
    else: df["hora"] = "Sin Inf."

    # Construir items base
    items = []
    for _, row in df.iterrows():
        lat_raw = row.get("lat"); lon_raw = row.get("long")
        if lat_raw in ("Sin Inf.", "S/I", None, "") or lon_raw in ("Sin Inf.", "S/I", None, ""):
            descartadas += 1; continue
        try:
            lat = float(lat_raw); lon = float(lon_raw)
        except Exception:
            descartadas += 1; continue
        if (abs(lat) < 1e-9 and abs(lon) < 1e-9) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            descartadas += 1; continue
        az_f = None; az_i = None
        try:
            az = row.get("azimut", None)
            if az is not None and str(az).strip() not in {"", "Sin Inf.", "S/I"}:
                az_f = float(az); az_i = int(round(az_f))
        except Exception:
            pass
        nombre = row.get("antena", "Antena") if str(row.get("antena", "")).strip() else "Antena"
        items.append({
            "antena": nombre, "lon": lon, "lat": lat,
            "azimut_f": az_f, "azimut_i": az_i,
            "fecha": row.get("fecha"), "hora": row.get("hora"),
            "direccion": row.get("direccion", row.get("detalle")),
            "tel": row.get("tel"), "imei": row.get("imei"),
            "alias": row.get("alias"), "usuario": row.get("usuario"), "abonado": row.get("abonado"),
            "celda": row.get("celda"), "lac": row.get("lac"),
            "interaccion": row.get("interaccion"), "tel_contacto": row.get("tel_contacto"), "duracion": row.get("duracion"),
        })

    # Helper: descripción básica para popup
    def _fmt_id(v):
        s = "" if v is None else str(v).strip()
        if not s:
            return s
        low = s.lower()
        if low in {"sininf", "sininf.", "sin inf", "s/i", "s/i."}:
            return ""
        s_try = s.replace(" ", "").replace(",", ".")
        import re
        from decimal import Decimal, InvalidOperation
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?", s_try, flags=re.IGNORECASE):
            return s
        try:
            d = Decimal(s_try)
            if d == d.to_integral_value():
                return str(int(d))
            return s
        except InvalidOperation:
            return s

    def _add_if(lst, label, value):
        s = "" if value is None else str(value).strip()
        if not s or s.lower() in {"sininf", "sininf.", "sin inf", "s/i", "s/i."}:
            return
        lst.append(f"{label}: {s}")

    def _descripcion(it: dict) -> str:
        desc = []
        _add_if(desc, "Fecha", it.get("fecha"))
        _add_if(desc, "Hora", it.get("hora"))
        tel_fmt = _fmt_id(it.get("tel"))
        if tel_fmt:
            desc.append(f"Tel: {tel_fmt}")
        imei_fmt = _fmt_id(it.get("imei"))
        if imei_fmt:
            desc.append(f"IMEI: {imei_fmt}")
        if desc:
            desc.append("<hr>")
        _add_if(desc, "Antena", it.get("antena"))
        _add_if(desc, "Detalle", it.get("direccion") or it.get("detalle"))
        return "<br>".join(desc)

    # Crear puntos (flat)
    if flat:
        for it in items:
            p = kml.newpoint(name=it["antena"], coords=[(it["lon"], it["lat"])])
            p.style = styles["pin"]
            try:
                p.description = _descripcion(it)
            except Exception:
                pass
            az = it["azimut_f"]
            if az is not None:
                try:
                    dist = (config.get("kml", {}).get("azimuth_km", 1.5))
                except Exception:
                    dist = 1.5
                latf, lonf = _calcular_punto_final(it["lat"], it["lon"], float(az), float(dist))
                ln = kml.newlinestring(name=f"Azimut {int(round(az))}°", coords=[(it["lon"], it["lat"]), (lonf, latf)])
                ln.style = styles["line"]
        # Guardar KML y KMZ
        if not solo_kmz:
            try: 
                kml.save(archivo_salida_kml)
            except Exception as e:
                print(f"[ERROR kml_generador] Al guardar KML '{archivo_salida_kml}': {e}")
                import traceback
                traceback.print_exc()
        try:
            kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
            kml.savekmz(kmz_path)
            try:
                if bool((config or {}).get("salida", {}).get("separar_kml_kmz", False)):
                    parent = os.path.basename(os.path.dirname(archivo_salida_kml)).lower()
                    if parent == "kml":
                        base_dir = os.path.dirname(os.path.dirname(archivo_salida_kml))
                        kmz_dir = os.path.join(base_dir, "kmz")
                        os.makedirs(kmz_dir, exist_ok=True)
                        shutil.copy2(kmz_path, os.path.join(kmz_dir, os.path.basename(kmz_path)))
            except Exception:
                pass
        except Exception as e:
            print(f"[ERROR kml_generador] Al guardar KMZ '{kmz_path}': {e}")
            import traceback
            traceback.print_exc()
        return archivo_salida_kml, descartadas

    # Estructura por carpetas (simplificada)
    root_name = os.path.splitext(os.path.basename(archivo_salida_kml))[0]
    raiz = kml.newfolder(name=root_name)
    todas = raiz.newfolder(name="todas_las_antenas")
    for it in items:
        p = todas.newpoint(name=it["antena"], coords=[(it["lon"], it["lat"])])
        p.style = styles["pin"]
        try:
            p.description = _descripcion(it)
        except Exception:
            pass
    try:
        if not solo_kmz:
            kml.save(archivo_salida_kml)
    except Exception as e:
        print(f"[ERROR kml_generador (2)] Al guardar KML '{archivo_salida_kml}': {e}")
        import traceback
        traceback.print_exc()
    try:
        kmz_path = os.path.splitext(archivo_salida_kml)[0] + ".kmz"
        kml.savekmz(kmz_path)
        try:
            if bool((config or {}).get("salida", {}).get("separar_kml_kmz", False)):
                parent = os.path.basename(os.path.dirname(archivo_salida_kml)).lower()
                if parent == "kml":
                    base_dir = os.path.dirname(os.path.dirname(archivo_salida_kml))
                    kmz_dir = os.path.join(base_dir, "kmz")
                    os.makedirs(kmz_dir, exist_ok=True)
                    shutil.copy2(kmz_path, os.path.join(kmz_dir, os.path.basename(kmz_path)))
        except Exception as e:
            print(f"[ERROR kml_generador (3)] Copiar KMZ a carpeta separada: {e}")
            import traceback
            traceback.print_exc()
    except Exception as e:
        print(f"[ERROR kml_generador (4)] Al guardar KMZ '{kmz_path}': {e}")
        import traceback
        traceback.print_exc()
    return archivo_salida_kml, descartadas

# === Helpers internos: estilos y geodesia ===
def _crear_estilos_reusables(config: dict) -> dict:
    """Crea estilos (pin blanco con etiqueta coloreada; línea de azimut) reutilizables."""
    theme_hex = (config or {}).get("style", {}).get("theme_hex", "#ff0000")
    label_color = hex_to_abgr(theme_hex)

    # Estilo del pin: ícono blanco con label coloreado
    pin_style = Style()
    pin_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png"
    pin_style.iconstyle.scale = float((config or {}).get("style", {}).get("pin_scale", 1.2))
    pin_style.labelstyle.color = label_color
    pin_style.labelstyle.scale = float((config or {}).get("style", {}).get("label_scale", 1.2))

    # Estilo de línea para azimut
    line_style = Style()
    line_style.linestyle.color = (config or {}).get("style", {}).get("line_abgr", "ffff00ff")  # magenta por defecto
    try:
        line_style.linestyle.width = float((config or {}).get("style", {}).get("line_width", 2))
    except Exception:
        line_style.linestyle.width = 2

    return {"pin": pin_style, "line": line_style}


def _calcular_punto_final(lat: float, lon: float, azimut: float, distancia_km: float):
    """Wrapper para mantener nombre interno; delega a calcular_punto_final ya definido."""
    return calcular_punto_final(lat, lon, azimut, distancia_km)
