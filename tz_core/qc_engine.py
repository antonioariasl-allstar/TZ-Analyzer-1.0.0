# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
from tz_core.qc_type_classifier import classify_interaction_type

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

    # --- CONTACTO (peso 30) ---
    if "contacto" not in df.columns:
        pct_contacto = 100.0
        flags["contacto"] = {"ausente": True, "pct_vacio": 100.0, "severidad": "CRITICA"}
        penalizacion += 30
        bloqueante = True
        resumen.append("CRITICO: columna 'contacto' ausente — penalización máxima")
    else:
        vacios = df["contacto"].isna() | (df["contacto"].astype(str).str.strip() == "")
        pct_contacto = round(vacios.sum() / n * 100, 1)
        sev = "CRITICA" if pct_contacto > 30 else ("ADVERTENCIA" if pct_contacto > 10 else "OK")
        pen = round(30 * pct_contacto / 100)
        flags["contacto"] = {"pct_vacio": pct_contacto, "severidad": sev}
        penalizacion += pen
        if pct_contacto > 30:
            bloqueante = True
        if pct_contacto > 0:
            resumen.append(f"{sev}: contacto vacío en {pct_contacto}% de registros")

    # --- TIPO / INTERACCION (peso 30) ---
    if "interaccion" not in df.columns:
        flags["tipo"] = {"ausente": True, "pct_desconocido": 100.0, "severidad": "CRITICA"}
        penalizacion += 30
        bloqueante = True
        resumen.append("CRITICO: columna 'interaccion' ausente — penalización máxima")
    else:
        clasificados = classify_interaction_type(df["interaccion"])
        pct_desc = round((clasificados == "DESCONOCIDO").sum() / n * 100, 1)
        conteos = clasificados.value_counts().to_dict()
        sev = "CRITICA" if pct_desc > 30 else ("ADVERTENCIA" if pct_desc > 10 else "OK")
        pen = round(30 * pct_desc / 100)
        flags["tipo"] = {"pct_desconocido": pct_desc, "conteos": conteos, "severidad": sev}
        penalizacion += pen
        if pct_desc > 30:
            bloqueante = True
        if pct_desc > 0:
            resumen.append(f"{sev}: tipo DESCONOCIDO en {pct_desc}% de registros")

    # --- FECHA (peso 20) ---
    if "fecha" not in df.columns:
        flags["fecha"] = {"ausente": True, "pct_invalida": 100.0, "severidad": "CRITICA"}
        penalizacion += 20
        bloqueante = True
        resumen.append("CRITICO: columna 'fecha' ausente — penalización máxima")
    else:
        invalidas = df["fecha"].isna() | (df["fecha"].astype(str).str.strip().isin(["", "SinInf", "nan", "None"]))
        pct_fecha = round(invalidas.sum() / n * 100, 1)
        sev = "CRITICA" if pct_fecha > 30 else ("ADVERTENCIA" if pct_fecha > 10 else "OK")
        pen = round(20 * pct_fecha / 100)
        flags["fecha"] = {"pct_invalida": pct_fecha, "severidad": sev}
        penalizacion += pen
        if pct_fecha > 30:
            bloqueante = True
        if pct_fecha > 0:
            resumen.append(f"{sev}: fecha inválida/vacía en {pct_fecha}% de registros")

    # --- COORDENADAS (peso 10) ---
    if "lat" not in df.columns or "long" not in df.columns:
        flags["coords"] = {"ausente": True, "pct_nula": 100.0, "severidad": "ADVERTENCIA"}
        penalizacion += 10
        resumen.append("ADVERTENCIA: columnas lat/long ausentes — penalización máxima")
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
        pen = round(10 * pct_coords / 100)
        flags["coords"] = {"pct_nula": pct_coords, "severidad": sev}
        penalizacion += pen
        if pct_coords > 0:
            resumen.append(f"{sev}: coordenadas nulas/inválidas en {pct_coords}% de registros")

    # --- ANTENA (peso 5) ---
    if "antena" not in df.columns:
        flags["antena"] = {"ausente": True, "pct_vacia": 100.0, "severidad": "INFO"}
        penalizacion += 5
        resumen.append("INFO: columna 'antena' ausente — penalización máxima")
    else:
        vacias_ant = df["antena"].isna() | (df["antena"].astype(str).str.strip().isin(["", "nan", "None", "SinInf", "0"]))
        pct_ant = round(vacias_ant.sum() / n * 100, 1)
        sev = "INFO" if pct_ant > 0 else "OK"
        pen = round(5 * pct_ant / 100)
        flags["antena"] = {"pct_vacia": pct_ant, "severidad": sev}
        penalizacion += pen
        if pct_ant > 0:
            resumen.append(f"{sev}: antena vacía en {pct_ant}% de registros")

    # --- DURACION (peso 5, opcional) ---
    if "duracion" in df.columns:
        nulas_dur = df["duracion"].isna()
        pct_dur = round(nulas_dur.sum() / n * 100, 1)
        sev = "INFO" if pct_dur > 0 else "OK"
        pen = round(5 * pct_dur / 100)
        flags["duracion"] = {"pct_nula": pct_dur, "severidad": sev}
        penalizacion += pen
        if pct_dur > 0:
            resumen.append(f"{sev}: duración nula en {pct_dur}% de registros")

    score = max(0, 100 - penalizacion)
    if not resumen:
        resumen.append("OK: sin problemas detectados")

    return QCResult(score=score, flags=flags, bloqueante=bloqueante, resumen=resumen)
