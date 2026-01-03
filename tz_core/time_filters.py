"""
Utilidades de filtros de tiempo para TZ Analyzer.

Incluye funciones para solicitar filtros de fecha/hora de manera interactiva y
aplicarlos sobre DataFrames de pandas, reutilizables desde el monolito o
cualquier interfaz futura.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

FiltroTiempo = Optional[Dict[str, Optional[str]]]


def solicitar_filtros_tiempo() -> FiltroTiempo:
    """Solicita al usuario un filtro temporal y regresa su configuración.

    Regresa un diccionario con las posibles claves:
    - tipo: "dia" | "rango_dias" | "rango_horas_dia" | "rango_horas"
    - dia, desde, hasta, hora_ini, hora_fin: valores string o None
    """
    print("\nSeleccione el filtro de tiempo:")
    print("[1] Día específico")
    print("[2] Rango de días")
    print("[3] Rango de horas en un día específico")
    print("[4] Rango de horas (aplicado a todos los días)")
    resp = input("Opción (1/2/3/4, Enter=sin filtro): ").strip()
    if resp not in ("1", "2", "3", "4"):
        return None

    if resp == "1":
        dia = input("Ingrese el día (dd/mm/yyyy): ").strip()
        return {
            "tipo": "dia",
            "dia": dia,
            "desde": None,
            "hasta": None,
            "hora_ini": None,
            "hora_fin": None,
        }

    if resp == "2":
        d1 = input("Desde (dd/mm/yyyy): ").strip()
        d2 = input("Hasta (dd/mm/yyyy): ").strip()
        return {
            "tipo": "rango_dias",
            "dia": None,
            "desde": d1,
            "hasta": d2,
            "hora_ini": None,
            "hora_fin": None,
        }

    if resp == "3":
        dia = input("Día (dd/mm/yyyy): ").strip()
        h1 = input("Hora inicio (HH:MM, Enter=usar presets SV): ").strip()
        h2 = input("Hora fin (HH:MM, Enter=usar presets SV): ").strip()
        h1 = (h1 + ":00") if (h1 and len(h1) == 5) else (h1 if h1 else None)
        h2 = (h2 + ":00") if (h2 and len(h2) == 5) else (h2 if h2 else None)
        return {
            "tipo": "rango_horas_dia",
            "dia": dia,
            "desde": None,
            "hasta": None,
            "hora_ini": h1,
            "hora_fin": h2,
        }

    # resp == "4"
    h1 = input("Hora inicio (HH:MM, Enter=usar presets SV): ").strip()
    h2 = input("Hora fin (HH:MM, Enter=usar presets SV): ").strip()
    h1 = (h1 + ":00") if (h1 and len(h1) == 5) else (h1 if h1 else None)
    h2 = (h2 + ":00") if (h2 and len(h2) == 5) else (h2 if h2 else None)
    return {
        "tipo": "rango_horas",
        "dia": None,
        "desde": None,
        "hasta": None,
        "hora_ini": h1,
        "hora_fin": h2,
    }


def aplicar_filtros_tiempo(df: pd.DataFrame, filtros: FiltroTiempo) -> Tuple[pd.DataFrame, str]:
    """Aplica filtros temporales sobre un DataFrame y regresa (df_filtrado, resumen).

    Args:
        df: DataFrame original a filtrar. Debe contener columnas 'fecha' y/o 'hora'.
        filtros: Diccionario generado por `solicitar_filtros_tiempo`.
    """
    if not filtros:
        return df, "Sin filtro de tiempo"

    tipo = filtros.get("tipo")
    resumen = ""

    fecha = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce") if "fecha" in df.columns else None
    hora = pd.to_timedelta(df["hora"].astype(str), errors="coerce") if "hora" in df.columns else None

    mask = pd.Series([True] * len(df), index=df.index)

    if tipo == "dia" and fecha is not None:
        try:
            dia = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce").normalize()
            mask &= fecha.dt.normalize() == dia
            resumen = f"Día: {filtros.get('dia')}"
        except Exception:
            pass

    elif tipo == "rango_dias" and fecha is not None:
        d1 = pd.to_datetime(filtros.get("desde"), dayfirst=True, errors="coerce")
        d2 = pd.to_datetime(filtros.get("hasta"), dayfirst=True, errors="coerce")
        if pd.notna(d1):
            d1 = d1.normalize()
        if pd.notna(d2):
            d2 = d2.normalize()
        if pd.notna(d1):
            mask &= fecha.dt.normalize() >= d1
        if pd.notna(d2):
            mask &= fecha.dt.normalize() <= d2
        resumen = f"Rango de días: {filtros.get('desde')} → {filtros.get('hasta')}"

    elif tipo == "rango_horas_dia" and fecha is not None and hora is not None:
        dia = pd.to_datetime(filtros.get("dia"), dayfirst=True, errors="coerce")
        h_ini = filtros.get("hora_ini")
        h_fin = filtros.get("hora_fin")
        if pd.notna(dia) and h_ini and h_fin:
            try:
                dia = dia.normalize()
                t1 = pd.to_timedelta(h_ini)
                t2 = pd.to_timedelta(h_fin)
                mask &= fecha.dt.normalize() == dia
                if t1 <= t2:
                    mask &= (hora >= t1) & (hora <= t2)
                else:
                    mask &= (hora >= t1) | (hora <= t2)
                resumen = f"Rango de horas en día {filtros.get('dia')}: {h_ini} → {h_fin}"
            except Exception:
                resumen = "Rango de horas en día (entrada inválida, sin filtrar)"

    elif tipo == "rango_horas" and hora is not None:
        h_ini = filtros.get("hora_ini")
        h_fin = filtros.get("hora_fin")
        if h_ini and h_fin:
            try:
                t1 = pd.to_timedelta(h_ini)
                t2 = pd.to_timedelta(h_fin)
                if t1 <= t2:
                    mask &= (hora >= t1) & (hora <= t2)
                else:
                    mask &= (hora >= t1) | (hora <= t2)
                resumen = f"Rango de horas: {h_ini} → {h_fin}"
            except Exception:
                resumen = "Rango de horas (entrada inválida, sin filtrar)"
        else:
            resumen = "Rango de horas (usando presets SV)"

    df_filtrado = df.loc[mask].copy()
    return df_filtrado, resumen


# Aliases de compatibilidad para código legacy
_def_alias = solicitar_filtros_tiempo
_aplicar_alias = aplicar_filtros_tiempo


def _solicitar_filtros_tiempo() -> FiltroTiempo:  # pragma: no cover - compat
    return _def_alias()


def _aplicar_filtros_tiempo(df: pd.DataFrame, filtros: FiltroTiempo) -> Tuple[pd.DataFrame, str]:  # pragma: no cover
    return _aplicar_alias(df, filtros)
