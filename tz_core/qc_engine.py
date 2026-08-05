# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
from tz_core.qc_type_classifier import classify_interaction_type

# Pesos de penalización. contacto/interaccion se redujeron a la mitad de su
# peso original (30 -> 15): dejaron de ser bloqueantes (ver detectar_capacidades
# en tz_core.capabilities, que ya modela su ausencia como capacidades
# "contactos"/"tipo_evento" no disponibles, no como un error global) y un
# peso de 30 sobre 100 exageraba su impacto en el score para una bitácora
# parcial pero analíticamente válida (p.ej. FX-02).
PESO_CONTACTO = 15
PESO_INTERACCION = 15
PESO_FECHA = 20
PESO_HORA = 10
PESO_COORDS = 10
PESO_ANTENA = 5
PESO_DURACION = 5
PESO_MOJIBAKE = 5
PESO_DATETIME_DUP = 5


@dataclass
class QCResult:
    score: int
    flags: dict
    bloqueante: bool
    resumen: list[str]

def run_qc(df: pd.DataFrame) -> QCResult:
    """
    Evalúa calidad del DataFrame post-ingesta.
    Detecta y reporta problemas. NO corrige ni transforma.
    Entrada: DataFrame con columnas canónicas post-wizard.
    Salida: QCResult con score, flags, bloqueante y resumen legible.

    ``bloqueante`` ahora solo se activa ante un DataFrame vacío (error
    técnico real). La ausencia/vacío de contacto, interaccion, fecha, hora,
    coordenadas o antena ya no bloquea el motor de QC: esas ausencias se
    modelan como capacidades no disponibles vía
    ``tz_core.capabilities.detectar_capacidades``, y es
    ``CapabilitiesReport.procesable`` — no este ``bloqueante`` — quien decide
    si el pipeline de ingesta debe abortar (ver ``run_ingestion_pipeline``).

    Nota sobre el score: hoy mezcla completitud (columnas ausentes), validez
    (porcentaje de valores vacíos/inválidos) y, de forma indirecta, señales
    de capacidad (fecha/hora/antena/coords). No mide "calidad" en un sentido
    absoluto — una bitácora con score bajo puede seguir siendo válida para
    varias capacidades analíticas. Se reporta con la etiqueta "Completitud
    del archivo para análisis integral" en vez de "Calidad del archivo" para
    reflejar esto. Rediseñarlo como score de completitud puro (separado de
    validez/capacidades) queda fuera de este hito.
    """
    n = len(df)
    if n == 0:
        return QCResult(
            score=0,
            flags={"error": "DataFrame vacío"},
            bloqueante=True,
            resumen=["ERROR: DataFrame vacío"]
        )

    flags = {}
    penalizacion = 0
    bloqueante = False
    resumen = []

    # --- CONTACTO (peso 15 — capacidad "contactos"; ausencia/vacío ya no bloquea) ---
    if "contacto" not in df.columns:
        pct_contacto = 100.0
        flags["contacto"] = {"ausente": True, "pct_vacio": 100.0, "severidad": "ADVERTENCIA"}
        penalizacion += PESO_CONTACTO
        resumen.append("ADVERTENCIA: columna 'contacto' ausente — capacidad de contactos no disponible")
    else:
        vacios = df["contacto"].isna() | (df["contacto"].astype(str).str.strip() == "")
        pct_contacto = round(vacios.sum() / n * 100, 1)
        sev = "ADVERTENCIA" if pct_contacto > 0 else "OK"
        pen = round(PESO_CONTACTO * pct_contacto / 100)
        flags["contacto"] = {"pct_vacio": pct_contacto, "severidad": sev}
        penalizacion += pen
        if pct_contacto > 0:
            resumen.append(f"{sev}: contacto vacío en {pct_contacto}% de registros")

    # --- TIPO / INTERACCION (peso 15 — capacidad "tipo_evento"; ausencia ya no bloquea) ---
    if "interaccion" not in df.columns:
        flags["tipo"] = {"ausente": True, "pct_desconocido": 100.0, "severidad": "ADVERTENCIA"}
        penalizacion += PESO_INTERACCION
        resumen.append("ADVERTENCIA: columna 'interaccion' ausente — capacidad de tipo de evento no disponible")
    else:
        clasificados = classify_interaction_type(df["interaccion"])
        pct_desc = round((clasificados == "DESCONOCIDO").sum() / n * 100, 1)
        conteos = clasificados.value_counts().to_dict()
        sev = "ADVERTENCIA" if pct_desc > 0 else "OK"
        pen = round(PESO_INTERACCION * pct_desc / 100)
        flags["tipo"] = {"pct_desconocido": pct_desc, "conteos": conteos, "severidad": sev}
        penalizacion += pen
        if pct_desc > 0:
            resumen.append(f"{sev}: tipo DESCONOCIDO en {pct_desc}% de registros")

    # --- FECHA (peso 20). Advertencia fuerte pero ya no bloquea el motor: la
    # capacidad "cronologia"/"filtros_temporales" queda no disponible, el
    # resto del análisis (identificación, antenas, KML, contactos) continúa.
    if "fecha" not in df.columns:
        flags["fecha"] = {"ausente": True, "pct_invalida": 100.0, "severidad": "CRITICA"}
        penalizacion += PESO_FECHA
        resumen.append("CRITICO: columna 'fecha' ausente — cronología y filtros temporales no disponibles")
    else:
        invalidas = df["fecha"].isna() | (df["fecha"].astype(str).str.strip().isin(["", "SinInf", "nan", "None"]))
        pct_fecha = round(invalidas.sum() / n * 100, 1)
        sev = "CRITICA" if pct_fecha > 30 else ("ADVERTENCIA" if pct_fecha > 10 else "OK")
        pen = round(PESO_FECHA * pct_fecha / 100)
        flags["fecha"] = {"pct_invalida": pct_fecha, "severidad": sev}
        penalizacion += pen
        if pct_fecha > 0:
            resumen.append(f"{sev}: fecha inválida/vacía en {pct_fecha}% de registros")

    # --- HORA (peso 10) ---
    if "hora" not in df.columns:
        flags["hora"] = {"ausente": True, "pct_invalida": 100.0, "severidad": "ADVERTENCIA"}
        penalizacion += PESO_HORA
        resumen.append("ADVERTENCIA: columna 'hora' ausente — antenas por horario y detalle temporal no disponibles")
    else:
        invalidas_h = df["hora"].isna() | (df["hora"].astype(str).str.strip().isin(["", "SinInf", "nan", "None"]))
        pct_hora = round(invalidas_h.sum() / n * 100, 1)
        sev = "ADVERTENCIA" if pct_hora > 10 else "OK"
        pen = round(PESO_HORA * pct_hora / 100)
        flags["hora"] = {"pct_invalida": pct_hora, "severidad": sev}
        penalizacion += pen
        if pct_hora > 0:
            resumen.append(f"{sev}: hora inválida/vacía en {pct_hora}% de registros")

    # --- COORDENADAS (peso 10) ---
    if "lat" not in df.columns or "long" not in df.columns:
        flags["coords"] = {"ausente": True, "pct_nula": 100.0, "severidad": "ADVERTENCIA"}
        penalizacion += PESO_COORDS
        resumen.append("ADVERTENCIA: columnas lat/long ausentes — KML y heatmap no disponibles")
    else:
        nulas = df["lat"].isna() | df["long"].isna()
        try:
            lat_num = pd.to_numeric(df["lat"], errors="coerce")
            long_num = pd.to_numeric(df["long"], errors="coerce")
            invalidas_val = (lat_num == 0) & (long_num == 0)
            nulas = nulas | invalidas_val
        except Exception:
            pass
        pct_coords = round(nulas.sum() / n * 100, 1)
        sev = "ADVERTENCIA" if pct_coords > 10 else "OK"
        pen = round(PESO_COORDS * pct_coords / 100)
        flags["coords"] = {"pct_nula": pct_coords, "severidad": sev}
        penalizacion += pen
        if pct_coords > 0:
            resumen.append(f"{sev}: coordenadas nulas/inválidas en {pct_coords}% de registros")

    # --- ANTENA (peso 5) ---
    if "antena" not in df.columns:
        flags["antena"] = {"ausente": True, "pct_vacia": 100.0, "severidad": "INFO"}
        penalizacion += PESO_ANTENA
        resumen.append("INFO: columna 'antena' ausente — capacidad de antenas no disponible")
    else:
        vacias_ant = df["antena"].isna() | (df["antena"].astype(str).str.strip().isin(["", "nan", "None", "SinInf", "0"]))
        pct_ant = round(vacias_ant.sum() / n * 100, 1)
        sev = "INFO" if pct_ant > 0 else "OK"
        pen = round(PESO_ANTENA * pct_ant / 100)
        flags["antena"] = {"pct_vacia": pct_ant, "severidad": sev}
        penalizacion += pen
        if pct_ant > 0:
            resumen.append(f"{sev}: antena vacía en {pct_ant}% de registros")

    # --- DURACION (peso 5, opcional) ---
    if "duracion" in df.columns:
        nulas_dur = df["duracion"].isna()
        pct_dur = round(nulas_dur.sum() / n * 100, 1)
        sev = "INFO" if pct_dur > 0 else "OK"
        pen = round(PESO_DURACION * pct_dur / 100)
        flags["duracion"] = {"pct_nula": pct_dur, "severidad": sev}
        penalizacion += pen
        if pct_dur > 0:
            resumen.append(f"{sev}: duración nula en {pct_dur}% de registros")

    # --- MOJIBAKE en columnas string (peso 5) ---
    str_cols = df.select_dtypes(include="object").columns.tolist()
    tiene_interrogante = any(
        df[c].astype(str).str.contains(r"\?", regex=True).any()
        for c in str_cols
    )
    if tiene_interrogante:
        flags["mojibake"] = {"severidad": "ADVERTENCIA"}
        penalizacion += PESO_MOJIBAKE
        resumen.append("ADVERTENCIA: se detectaron caracteres no normalizados ('?') en columnas de texto")

    # --- FECHA/HORA DUPLICADA (peso 5) ---
    if "fecha" in df.columns and "hora" in df.columns:
        sample_f = df["fecha"].dropna().astype(str).head(10)
        sample_h = df["hora"].dropna().astype(str).head(10)
        if len(sample_f) > 0 and sample_f.equals(sample_h.reset_index(drop=True)) if len(sample_f) == len(sample_h) else False:
            flags["datetime_duplicado"] = {"severidad": "ADVERTENCIA"}
            penalizacion += PESO_DATETIME_DUP
            resumen.append("ADVERTENCIA: 'fecha' y 'hora' contienen valores idénticos — posible columna datetime compartida")

    score = max(0, 100 - penalizacion)
    if not resumen:
        resumen.append("OK: sin problemas detectados")

    return QCResult(score=score, flags=flags, bloqueante=bloqueante, resumen=resumen)
