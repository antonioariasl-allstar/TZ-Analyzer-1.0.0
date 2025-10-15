"""
kml_generador.py — Generación de KML/KMZ

Secciones:
  1) Imports y constantes
  2) Geodesia / cálculos de soporte
  3) Armado de descripciones (HTML para burbujas)
  4) Generación KML principal
"""

# === 1) Imports y constantes ===
from simplekml import Kml
import math

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
                # Si tiene fracción, no “inventar” formato: devolvemos el original
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
        _add_if(desc, "Detalle", row.get("detalle"))

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
