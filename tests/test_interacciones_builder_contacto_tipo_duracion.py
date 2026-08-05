"""Hito 2A FX-02 — Pruebas unitarias de la sección "Filtrar interacciones por
fecha" (tz_core/interacciones_builder.py).

Cubren el contrato de contacto válido (es_valor_significativo), el lenguaje
neutral cuando falta el tipo de evento, y el tratamiento de duración
segura/ambigua/ausente descrito en el Hito 2A. Complementan, sin sustituir,
las pruebas rojas de auditoría en test_fx02_placeholder_contacto_ausente.py.
"""
import re

import pandas as pd

from tz_core.bitacora_normalization import clasificar_confiabilidad_duracion
from tz_core.interacciones_builder import construir_seccion_interacciones


def _df(**cols) -> pd.DataFrame:
    """Bitácora mínima de un solo día para aislar el comportamiento bajo prueba."""
    base = {
        "fecha": ["2026-08-01"] * len(next(iter(cols.values()))),
        "hora": None,
    }
    n = len(next(iter(cols.values())))
    base["hora"] = [f"{8 + i:02d}:00:00" for i in range(n)]
    base.update(cols)
    return pd.DataFrame(base)


# ── Contacto ─────────────────────────────────────────────────────────────

def test_contacto_parcialmente_vacio_no_altera_conteo():
    df = _df(contacto=["70011111", "", "70011111", "SIN DETERMINAR"])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"Contactos únicos:</strong>\s*1", html), (
        "Debe contarse un único contacto válido ('70011111'); los valores vacíos "
        "y el placeholder 'SIN DETERMINAR' no deben sumar contactos adicionales."
    )


def test_todos_los_contactos_invalidos_da_cero():
    df = _df(contacto=["", "N/A", "-", "sin determinar"])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"Contactos únicos:</strong>\s*0", html), (
        "Si ningún valor de contacto es significativo, el conteo debe ser 0."
    )


def test_placeholder_visible_no_genera_alerta_de_concentracion():
    df = _df(contacto=["-", "-", "-", "-", "70011111"])
    html = construir_seccion_interacciones(df, config={})

    assert "Concentración" not in html, (
        "Con un único contacto válido minoritario (1/5) no debe dispararse una "
        "alerta de concentración, y el placeholder dominante ('-') nunca puede "
        "ser sujeto de una alerta aunque domine el conteo de filas."
    )


# ── Tipo de evento ───────────────────────────────────────────────────────

def test_tipo_presente_con_valores_validos_conserva_lenguaje_actual():
    df = _df(interaccion=["LLAMADA ENTRANTE", "SMS SALIENTE"])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"<h3>Se muestran las interacciones del día", html)
    assert re.search(r"<span><strong>Interacciones:</strong>", html)
    assert "El tipo de evento no está disponible" not in html


def test_tipo_presente_pero_vacio_usa_lenguaje_neutral():
    df = _df(interaccion=["", "", None])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"<h3>Se muestran los registros disponibles del día", html)
    assert re.search(r"<span><strong>Registros:</strong>", html)
    assert "El tipo de evento no está disponible en la bitácora." in html


# ── Duración ─────────────────────────────────────────────────────────────

def test_duracion_segura_hhmmss_conserva_calculo():
    df = _df(duracion=["00:05:00", "00:10:00"])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"<strong>Duración:</strong>\s*00:15:00", html), (
        "HH:MM:SS es un formato autodescriptivo: debe sumarse tal cual (5+10 min)."
    )


def test_duracion_segura_segundos_conserva_calculo():
    df = _df(duracion_seg=[30, 90])
    html = construir_seccion_interacciones(df, config={})

    assert re.search(r"<strong>Duración:</strong>\s*00:02:00", html), (
        "Encabezado que declara segundos explícitamente: 30+90=120s = 00:02:00."
    )


def test_duracion_segura_minutos_convierte_correctamente():
    df = _df(duracion=[5, 10])
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="minutos")
    assert estado.estado == "segura" and estado.unidad == "minutos"

    html = construir_seccion_interacciones(df, config={}, duracion_estado=estado)

    assert re.search(r"<strong>Duración:</strong>\s*00:15:00", html), (
        "Unidad resuelta como minutos: (5+10) min deben convertirse a 900s = 00:15:00."
    )


def test_duracion_ambigua_omite_calculos():
    df = _df(duracion=[30, 5400])
    html = construir_seccion_interacciones(df, config={})

    assert not re.search(r"<strong>Duración:</strong>", html), (
        "Columna numérica genérica sin unidad confirmada: no debe presentarse KPI "
        "de duración ni una conversión HH:MM:SS."
    )
    assert re.search(
        r"unidad de los valores reportados no pudo confirmarse", html, re.I
    )
    assert "Concentración (duración)" not in html


def test_duracion_ausente_no_fabrica_00_00_00():
    df = _df(contacto=["70011111", "70022222"])
    html = construir_seccion_interacciones(df, config={})

    assert not re.search(r"<strong>Duración:</strong>", html), (
        "Sin columna de duración no debe fabricarse un KPI de duración ni un "
        "valor cero (00:00:00)."
    )
    assert re.search(r"Duración no disponible", html, re.I)
