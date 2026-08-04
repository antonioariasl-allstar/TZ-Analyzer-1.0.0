"""
tz_core.analytics - MOTOR DE ANÁLISIS DE DATOS FORENSES
=======================================================

✅ ESTADO: EXTRACCIÓN FASE 9B - FUNCIONES DE ANALYTICS Y REPORTES
🎯 PROPÓSITO: Análisis especializado de patrones de antenas, movilidad y contactos
📍 DIFERENCIACIÓN: Lógica de analytics separada de generación HTML

RESPONSABILIDADES ESPECÍFICAS:
- analizar_antenas(): Análisis estadístico de activaciones por antena
- generar_historial_cambios_antena(): Detección de saltos geográficos
- construir_seccion_todos_contactos(): Generación de tablas de contactos
- construir_rangos_cfg(): Utilities para manejo de rangos horarios

DEPENDENCIAS:
- pandas: Operaciones de análisis de DataFrames
- datetime: Manejo temporal y rangos horarios  
- math: Cálculos geográficos (distancia haversine)
- tz_core.validation_utils: Funciones de validación
- tz_core.time_utils: Utilities de tiempo (en_rango_minutos)

CARACTERÍSTICAS ESPECIALES:
- Análisis de patrones de movilidad entre antenas
- Cálculo de distancias geográficas (fórmula haversine)
- Manejo de rangos horarios con soporte para cruce de medianoche
- Generación de reportes estadísticos de uso

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 1018-3020
FECHA MIGRACIÓN: 28 octubre 2025
FASE: 9B - Analytics (Riesgo Moderado)
"""

import os
import pandas as pd

from tz_core.bitacora_normalization import normalize_msisdn, parse_duration_seconds
import numpy as np
from datetime import time as _time, datetime as _dt
from typing import List, Dict, Any, Optional, Tuple
import math

# Imports de módulos tz_core
from tz_core.validation_utils import tiene_valor
from tz_core.time_utils import en_rango_minutos


def analizar_antenas(df: pd.DataFrame, archivo_salida: str) -> None:
    """
    Genera análisis estadístico completo de antenas y patrones de activación.
    
    Analiza:
    - Top 5 antenas más activadas con coordenadas y azimuts
    - Desglose por azimut para cada antena
    - Distribución por rangos horarios (madrugada, mañana, tarde, noche)
    - Antenas más activas por rango horario
    
    Args:
        df: DataFrame con columnas 'antena', 'lat', 'long', 'azimut', 'hora'
        archivo_salida: Ruta donde guardar el reporte de análisis
        
    Side Effects:
        Escribe archivo de texto con análisis estadístico completo
    """
    resumen = []

    if "antena" not in df.columns:
        resumen.append("No se encontró la columna 'antena' tras la normalización de encabezados.\n")
        resumen.append("Sugerencia: ajustar 'rename_map' para mapear el nombre real de la columna a 'antena'.\n\n")
        try:
            validas = df[(df.get("lat").notna()) & (df.get("long").notna())]
            resumen.append(f"Filas con coordenadas no vacías: {len(validas)}\n")
        except Exception:
            pass
        with open(archivo_salida, "w", encoding="utf-8") as f:
            f.writelines(resumen)
        return

    conteo_antenas = df["antena"].value_counts(dropna=False)
    top_5_antenas = conteo_antenas.head(5)

    resumen.append("Top 5 Antenas más activadas:\n")
    for antena, activaciones in top_5_antenas.items():
        detalles = df[df["antena"] == antena].iloc[0]
        resumen.append(
            f"Antena: {antena}\n"
            f"Activaciones: {activaciones}\n"
            f"Latitud: {detalles.get('lat', 'Sin Inf.')}\n"
            f"Longitud: {detalles.get('long', 'Sin Inf.')}\n"
            f"Azimut: {detalles.get('azimut', 'Sin Inf.')}\n"
        )

        azimuts = df[df["antena"] == antena]["azimut"].value_counts(dropna=False)
        resumen.append("  Desglose por azimut:\n")
        for azimut, cantidad in azimuts.items():
            resumen.append(f"    Azimut {azimut}: {cantidad} activaciones\n")
        resumen.append("\n")

    # Rangos horarios para análisis temporal
    rangos_horarios = {
        "Madrugada (00:00-05:59)": ("00:00:00", "05:59:59"),
        "Mañana (06:00-11:59)": ("06:00:00", "11:59:59"),
        "Tarde (12:00-17:59)": ("12:00:00", "17:59:59"),
        "Noche (18:00-23:59)": ("18:00:00", "23:59:59"),
    }

    resumen.append("Activaciones por rango horario:\n")
    # Optimización: una sola copia en lugar de dos (líneas 1248 y 1251 duplicadas)
    df_hora = df.copy()
    if "hora" in df.columns:
        df_hora["hora"] = df_hora["hora"].astype(str).str[:8]
    else:
        df_hora["hora"] = "Sin Inf."

    for rango, (inicio, fin) in rangos_horarios.items():
        if inicio < fin:
            activaciones = df_hora[(df_hora["hora"] >= inicio) & (df_hora["hora"] <= fin)]
        else:
            activaciones = df_hora[(df_hora["hora"] >= inicio) | (df_hora["hora"] <= fin)]
        resumen.append(f"{rango}: {len(activaciones)} activaciones\n")

        if "antena" in activaciones.columns:
            antenas_rango = activaciones["antena"].value_counts().head(3)
            resumen.append(f"  Antenas más activas en {rango}:\n")
            for antena, cantidad in antenas_rango.items():
                detalles = df[df["antena"] == antena].iloc[0]
                resumen.append(
                    f"    Antena: {antena}, Activaciones: {cantidad}, "
                    f"Latitud: {detalles.get('lat', 'Sin Inf.')}, "
                    f"Longitud: {detalles.get('long', 'Sin Inf.')}\n"
                )
        resumen.append("\n")

    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.writelines(resumen)


def generar_historial_cambios_antena(df: pd.DataFrame, max_saltos: int = 100) -> List[Dict[str, Any]]:
    """
    Extrae la secuencia de saltos entre antenas (cambios de antena en el tiempo).
    
    Detecta cambios de antena ordenados cronológicamente y calcula:
    - Antena origen y destino del salto
    - Timestamp del cambio
    - Coordenadas de origen y destino  
    - Distancia geográfica en kilómetros (fórmula haversine)
    
    Args:
        df: DataFrame con columnas 'antena', 'fecha y hora' (o similar), 'lat', 'long'
        max_saltos: Límite máximo de saltos a retornar (para no saturar HTML)
    
    Returns:
        Lista de diccionarios con: {origen, destino, timestamp, lat_origen, lon_origen, 
                                   lat_destino, lon_destino, distancia_km}
    """
    try:
        # Detectar columnas de antena y timestamp
        cols_low = {c.lower(): c for c in df.columns}
        col_ant = None
        col_ts = None
        col_lat = None
        col_lon = None
        
        for name_var in ["antena", "antenanombre", "antena_nombre"]:
            if name_var in cols_low:
                col_ant = cols_low[name_var]
                break
        
        for name_var in ["fecha y hora", "fechahora", "datetime", "timestamp", "fecha_hora", "fechayhora"]:
            if name_var in cols_low:
                col_ts = cols_low[name_var]
                break
        
        for name_var in ["lat", "latitud"]:
            if name_var in cols_low:
                col_lat = cols_low[name_var]
                break
        
        for name_var in ["long", "lon", "longitud"]:
            if name_var in cols_low:
                col_lon = cols_low[name_var]
                break
        
        if not col_ant or not col_ts:
            return []
        
        # Copiar y limpiar
        work_df = df.copy()
        work_df[col_ant] = work_df[col_ant].astype(str).str.strip()
        
        # Convertir timestamp
        work_df['_ts'] = pd.to_datetime(work_df[col_ts], errors='coerce')
        
        # Filtrar válidos y sin antena = '0' o vacío
        work_df = work_df[
            (work_df['_ts'].notna()) &
            (work_df[col_ant] != '') &
            (work_df[col_ant] != '0') &
            (work_df[col_ant].notna())
        ].sort_values('_ts').reset_index(drop=True)
        
        if len(work_df) < 2:
            return []
        
        # Convertir lat/lon
        if col_lat and col_lat in work_df.columns:
            work_df[col_lat] = pd.to_numeric(work_df[col_lat], errors='coerce')
        if col_lon and col_lon in work_df.columns:
            work_df[col_lon] = pd.to_numeric(work_df[col_lon], errors='coerce')
        
        # Detectar saltos (cambios de antena)
        saltos = []
        for i in range(1, len(work_df)):
            ant_prev = str(work_df.iloc[i-1][col_ant]).strip()
            ant_curr = str(work_df.iloc[i][col_ant]).strip()
            ts_curr = work_df.iloc[i]['_ts']
            
            if ant_prev != ant_curr:
                lat_prev = work_df.iloc[i-1].get(col_lat) if col_lat else None
                lon_prev = work_df.iloc[i-1].get(col_lon) if col_lon else None
                lat_curr = work_df.iloc[i].get(col_lat) if col_lat else None
                lon_curr = work_df.iloc[i].get(col_lon) if col_lon else None
                
                # Calcular distancia si hay coords
                dist_km = None
                if (lat_prev is not None and lon_prev is not None and 
                    lat_curr is not None and lon_curr is not None and
                    not (pd.isna(lat_prev) or pd.isna(lon_prev) or pd.isna(lat_curr) or pd.isna(lon_curr))):
                    try:
                        lon1, lat1, lon2, lat2 = map(math.radians, [float(lon_prev), float(lat_prev), float(lon_curr), float(lat_curr)])
                        dlon = lon2 - lon1
                        dlat = lat2 - lat1
                        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                        c = 2 * math.asin(math.sqrt(a))
                        dist_km = 6371 * c
                    except Exception:
                        dist_km = None
                
                saltos.append({
                    'origen': ant_prev,
                    'destino': ant_curr,
                    'timestamp': ts_curr,
                    'lat_origen': lat_prev,
                    'lon_origen': lon_prev,
                    'lat_destino': lat_curr,
                    'lon_destino': lon_curr,
                    'distancia_km': dist_km
                })
                
                if len(saltos) >= max_saltos:
                    break
        
        return saltos
    except Exception as e:
        # Note: log function would need to be imported or replaced with print/logging
        print(f"[WARNING] Error generando historial de cambios de antena: {e}")
        return []


def _fallback_todos_contactos(mensaje: str) -> str:
    """Retorna bloque HTML declarativo para sección Todos los contactos cuando no hay datos."""
    return (
        '<section id="todos-contactos">'
        '<h2>Todos los contactos</h2>'
        f'<p style="font-size:13px; color:#444; margin-bottom:8px;">{mensaje}</p>'
        '</section>'
    )


def construir_seccion_todos_contactos(df: pd.DataFrame, columnas_config: Optional[Dict[str, str]] = None) -> str:
    """
    Construye sección HTML 'Todos los contactos' separada en tres bloques P0-B.

    Bloque A: contactos telefónicos plausibles (agrupados por contacto_limpio).
    Bloque B: registros indeterminados (agrupados por valor original + motivo).
    Bloque C: registros técnicos en <details> (agrupados por valor + tipo + motivo).

    Args:
        df: DataFrame con datos de contactos/llamadas
        columnas_config: Mapeo opcional de nombres de columnas

    Returns:
        String con HTML de la sección completa con tres bloques P0-B,
        o fallback declarativo si los datos no están disponibles.
    """
    import html as _html

    try:
        if df is None or df.empty:
            return _fallback_todos_contactos(
                "No se registraron interacciones en el período analizado."
            )

        cols_cfg = columnas_config or {}
        candidatos = [
            cols_cfg.get("tel_contacto"),
            "tel_contacto",
            "contacto",
            "_contacto",
            "_contacto_raw",
            "telefono_contacto",
            "numero_contacto",
            "destino",
            "origen",
        ]
        c_col = next((c for c in candidatos if c and c in df.columns), None)
        if not c_col:
            return _fallback_todos_contactos(
                "No se identificó una columna de contacto en la bitácora. "
                "Verificar el mapeo de columnas."
            )

        # Verificar presencia de columnas P0-B antes de cualquier cálculo
        _p0b_cols = ["contacto_categoria", "contacto_limpio", "contacto_motivo", "tipo_evento_normalizado"]
        if any(col not in df.columns for col in _p0b_cols):
            return _fallback_todos_contactos(
                "No fue posible separar los contactos por categoría porque la clasificación "
                "P0-B no está disponible en los datos procesados."
            )

        d = df.copy()

        # Calcular _sec sobre la copia completa antes de filtrar por categoría
        if "_sec" in d.columns:
            sec = pd.to_numeric(d["_sec"], errors="coerce").fillna(0)
        elif "duracion" in d.columns:
            d_dur = d["duracion"].map(lambda x: parse_duration_seconds(x, default=0.0))
            sec = pd.to_numeric(d_dur, errors="coerce").fillna(0)
        else:
            sec = 0
        d["_sec"] = pd.to_numeric(sec, errors="coerce").fillna(0).astype(int)

        _MOTIVO_DISPLAY = {
            "vacio_o_nulo":                   "Valor vacío o nulo",
            "tipo_datos":                     "Registro de sesión de datos",
            "ipv4":                           "Dirección IPv4",
            "formato_alfanumerico":           "Formato alfanumérico — no telefónico",
            "solo_ceros":                     "Valor compuesto solo por ceros",
            "sin_contacto_limpio":            "Sin valor normalizado disponible",
            "limpio_no_numerico":             "Valor normalizado no numérico",
            "longitud_insuficiente":          "Longitud insuficiente para clasificar",
            "sin_clasificacion":              "Sin clasificación — tipo de evento no reconocido",
            "voz_longitud_corta":             "Voz — longitud corta, plausibilidad reducida",
            "sms_longitud_ambigua":           "SMS — longitud ambigua",
            "desconocido_longitud_plausible": "Tipo desconocido — longitud sin clasificar",
            "longitud_excesiva":              "Longitud superior a 15 dígitos",
            "desconocido_longitud_corta":     "Tipo desconocido — longitud corta",
            "voz_longitud_valida":            "Voz — longitud válida",
            "sms_longitud_valida":            "SMS — longitud válida",
            "sin_columna_contacto":           "Columna de contacto no disponible",
            "sin_clasificacion_error":        "Error interno en clasificación",
        }

        def _safe(v):
            if v is None:
                return "—"
            s = str(v).strip()
            return "—" if s.lower() in ("none", "nan", "") else s

        out = []
        out.append('<section id="todos-contactos">')
        out.append('<h2>Todos los contactos</h2>')
        out.append(
            '<div style="font-size:13px; color:#444; margin-bottom:8px;">'
            'Esta sección separa los números con formato telefónico de los registros '
            'de longitud menor y los técnicos. Los registros técnicos no participan en el análisis '
            'de contactos, pero se conservan para trazabilidad.'
            '</div>'
        )

        # --- BLOQUE A: Contactos telefónicos plausibles ---
        da = d[d["contacto_categoria"] == "telefonico_plausible"].copy()
        out.append('<h3>Números con formato telefónico</h3>')
        if da.empty:
            out.append(
                '<p style="font-size:13px; color:#444;">'
                'No se registraron números con formato telefónico en el período analizado.'
                '</p>'
            )
        else:
            ga = da.groupby("contacto_limpio", dropna=False)
            tba = (
                pd.DataFrame({
                    "contacto_norm": ga.size().index,
                    "conteo": ga.size().values,
                    "minutos": (ga["_sec"].sum() / 60.0).round().astype(int).values,
                })
                .sort_values(["conteo", "minutos"], ascending=False)
                .reset_index(drop=True)
            )
            out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
            out.append(
                '<thead><tr>'
                '<th>#</th><th>Contacto normalizado</th><th>Conteo de interacciones</th><th>Minutos acumulados</th>'
                '</tr></thead><tbody>'
            )
            for i, row in tba.iterrows():
                out.append(
                    "<tr>"
                    f"<td class='mono' style='text-align:center'>{i + 1}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['contacto_norm']))}</td>"
                    f"<td class='mono' style='text-align:center'>{int(row['conteo']):,}</td>"
                    f"<td class='mono' style='text-align:center'>{int(row['minutos']):,}</td>"
                    "</tr>"
                )
            out.append("</tbody></table></div>")

        # --- BLOQUE B: Registros indeterminados ---
        db = d[d["contacto_categoria"] == "indeterminado"].copy()
        out.append('<h3>Números o códigos de longitud menor</h3>')
        if db.empty:
            out.append(
                '<p style="font-size:13px; color:#444;">'
                'No se encontraron registros indeterminados en el período analizado.'
                '</p>'
            )
        else:
            gb = db.groupby([c_col, "contacto_limpio", "contacto_motivo"], dropna=False)
            tbb = (
                pd.DataFrame({
                    "valor_original": [k[0] for k in gb.size().index],
                    "valor_norm": [k[1] for k in gb.size().index],
                    "motivo": [k[2] for k in gb.size().index],
                    "conteo": gb.size().values,
                })
                .sort_values("conteo", ascending=False)
                .reset_index(drop=True)
            )
            out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
            out.append(
                '<thead><tr>'
                '<th>#</th><th>Valor original</th><th>Valor normalizado</th><th>Conteo</th><th>Motivo</th>'
                '</tr></thead><tbody>'
            )
            for i, row in tbb.iterrows():
                out.append(
                    "<tr>"
                    f"<td class='mono' style='text-align:center'>{i + 1}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['valor_original']))}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['valor_norm']))}</td>"
                    f"<td class='mono' style='text-align:center'>{int(row['conteo']):,}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_MOTIVO_DISPLAY.get(_safe(row['motivo']), _safe(row['motivo'])))}</td>"
                    "</tr>"
                )
            out.append("</tbody></table></div>")

        # --- BLOQUE C: Registros técnicos (colapsable) ---
        dc = d[d["contacto_categoria"] == "tecnico_no_personal"].copy()
        total_tec = len(dc)
        out.append(
            f'<details><summary>'
            f'<strong>Registros técnicos y de datos'
            f' ({total_tec:,} registros)</strong>'
            f'</summary>'
        )
        if dc.empty:
            out.append(
                '<p style="font-size:13px; color:#444;">'
                'No se encontraron registros técnicos en el período analizado.'
                '</p>'
            )
        else:
            gc = dc.groupby(
                [c_col, "contacto_limpio", "tipo_evento_normalizado", "contacto_motivo"],
                dropna=False,
            )
            tbc = (
                pd.DataFrame({
                    "valor_original": [k[0] for k in gc.size().index],
                    "valor_norm": [k[1] for k in gc.size().index],
                    "tipo_evento": [k[2] for k in gc.size().index],
                    "motivo": [k[3] for k in gc.size().index],
                    "conteo": gc.size().values,
                })
                .sort_values("conteo", ascending=False)
                .reset_index(drop=True)
            )
            out.append('<div class="tabla-scroll"><table class="tabla-compacta">')
            out.append(
                '<thead><tr>'
                '<th>#</th><th>Valor original</th><th>Valor normalizado</th>'
                '<th>Tipo de evento</th><th>Conteo</th><th>Motivo</th>'
                '</tr></thead><tbody>'
            )
            for i, row in tbc.iterrows():
                out.append(
                    "<tr>"
                    f"<td class='mono' style='text-align:center'>{i + 1}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['valor_original']))}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['valor_norm']))}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_safe(row['tipo_evento']))}</td>"
                    f"<td class='mono' style='text-align:center'>{int(row['conteo']):,}</td>"
                    f"<td class='mono' style='text-align:center'>{_html.escape(_MOTIVO_DISPLAY.get(_safe(row['motivo']), _safe(row['motivo'])))}</td>"
                    "</tr>"
                )
            out.append("</tbody></table></div>")
        out.append("</details>")

        out.append("</section>")
        return "\n".join(out)
    except Exception as exc:
        print(f"[WARN] construir_seccion_todos_contactos: {exc}")
        return _fallback_todos_contactos(
            "No fue posible generar esta sección con los datos disponibles."
        )


# ========================================
# UTILITIES PARA RANGOS HORARIOS
# ========================================

def _parse_hhmmss_to_minutes(s: Optional[str]) -> Optional[int]:
    """
    Convierte 'HH:MM' o 'HH:MM:SS' a minutos desde 00:00.
    
    Args:
        s: String con formato de hora
        
    Returns:
        Minutos desde medianoche o None si no se puede parsear
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        # ignorar segundos si vienen
        return hh * 60 + mm
    except Exception:
        return None


def _minutes_from_any(hora: Any) -> Optional[int]:
    """
    Acepta: datetime.time, datetime.datetime, pandas.Timestamp, str 'HH:MM(:SS)'.
    
    Args:
        hora: Objeto temporal de cualquier tipo soportado
        
    Returns:
        Minutos desde 00:00 o None si no se puede convertir
    """
    try:
        # pandas.Timestamp o datetime
        if hasattr(hora, "hour") and hasattr(hora, "minute"):
            return int(hora.hour) * 60 + int(hora.minute)
        if isinstance(hora, _time):
            return hora.hour * 60 + hora.minute
        # string
        return _parse_hhmmss_to_minutes(str(hora))
    except Exception:
        return None


def construir_rangos_cfg(rangos_cfg: List[Dict[str, str]]) -> List[Tuple[str, int, int]]:
    """
    Construye lista de rangos horarios desde configuración.
    
    Args:
        rangos_cfg: Lista de diccionarios con formato:
                   [{"nombre": "Mañana", "inicio": "06:00", "fin": "11:59"}, ...]
    
    Returns:
        Lista de tuplas [(nombre, minutos_inicio, minutos_fin)]
    """
    res = []
    for r in rangos_cfg:
        n = str(r.get("nombre", "")).strip() or "Rango"
        mi = _parse_hhmmss_to_minutes(r.get("inicio"))
        mf = _parse_hhmmss_to_minutes(r.get("fin"))
        if mi is None or mf is None:
            continue
        res.append((n, mi, mf))
    return res


def _en_rango_minutos_local(minutos: int, ini: int, fin: int) -> bool:
    """
    Determina si un tiempo en minutos cae dentro de un rango.
    
    Soporta cruce de medianoche: si ini > fin, el rango pasa por 00:00.
    
    Args:
        minutos: Minutos desde medianoche (0-1439)
        ini: Minutos de inicio del rango
        fin: Minutos de fin del rango
        
    Returns:
        True si los minutos caen dentro del rango
    """
    return en_rango_minutos(minutos, ini, fin)


def etiqueta_rango(hora: Any, rangos_cfg: List[Dict[str, str]], default: str = "Sin rango") -> str:
    """
    Devuelve el nombre del rango horario que contiene la hora dada.
    
    Args:
        hora: Objeto temporal (time/datetime/Timestamp o str 'HH:MM(:SS)')
        rangos_cfg: Lista de configuración de rangos
        default: Etiqueta por defecto si no coincide ningún rango
        
    Returns:
        Nombre del rango que contiene la hora o default
    """
    m = _minutes_from_any(hora)
    if m is None:
        return default
    rangos = construir_rangos_cfg(rangos_cfg)
    for nombre, mi, mf in rangos:
        if _en_rango_minutos_local(m, mi, mf):
            return nombre
    return default