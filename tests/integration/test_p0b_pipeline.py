"""Tests de integración end-to-end para la cadena P0-B completa:
normalize_event_fields → normalize_contact_fields → construir_seccion_todos_contactos.
"""
import pandas as pd
from tz_core.bitacora_normalization import (
    normalize_event_fields,
    normalize_contact_fields,
    normalize_msisdn,
)
from tz_core.analytics import construir_seccion_todos_contactos


def _raw_df():
    return pd.DataFrame({
        "contacto":   ["70001234", "+50370001234", "192.168.1.1", "internet", "123", None],
        "interaccion": ["VOZ",     "VOZ",           "DATOS",       "DATOS",   "VOZ", "SMS"],
        "duracion":   ["00:01:00", "00:02:00",      "00:00:30",    "00:00:10", "00:00:20", "00:00:00"],
    })


# ── TEST 1: normalización completa ───────────────────────────────────────────

def test_p0b_normalizacion_end_to_end():
    df = _raw_df()
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)

    # Todas las columnas P0-B deben existir
    for col in [
        "tipo_evento_normalizado", "evento_valido_analisis",
        "contacto_limpio", "contacto_valido",
        "contacto_categoria", "contacto_motivo",
    ]:
        assert col in df.columns, f"Columna ausente: {col}"

    cats = df["contacto_categoria"].tolist()
    mots = df["contacto_motivo"].tolist()

    assert cats[0] == "telefonico_plausible"
    assert mots[0] == "voz_longitud_valida"

    assert cats[1] == "telefonico_plausible"
    assert mots[1] == "voz_longitud_valida"
    # Verificar contacto_limpio sin asumir formato interno
    _esperado_fila2 = normalize_msisdn("+50370001234")
    assert df["contacto_limpio"].iloc[1] == _esperado_fila2

    assert cats[2] == "tecnico_no_personal"
    assert mots[2] == "tipo_datos"

    assert cats[3] == "tecnico_no_personal"
    assert mots[3] == "tipo_datos"

    assert cats[4] == "indeterminado"
    assert mots[4] == "voz_longitud_corta"

    assert cats[5] == "tecnico_no_personal"
    assert mots[5] == "vacio_o_nulo"


# ── TEST 2: sección HTML end-to-end ──────────────────────────────────────────

def test_p0b_seccion_todos_contactos_end_to_end():
    df = _raw_df()
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)

    html = construir_seccion_todos_contactos(df)

    # Estructura principal
    assert 'id="todos-contactos"' in html
    assert "Contactos telefónicos plausibles" in html
    assert "Registros indeterminados" in html
    assert "Registros técnicos excluidos del análisis de contactos" in html
    assert "<details>" in html

    # Valores esperados en el HTML
    assert "70001234" in html

    _limpio_fila2 = normalize_msisdn("+50370001234")
    _digits_fila2 = _limpio_fila2.lstrip("+") if _limpio_fila2 else ""
    assert _digits_fila2 in html or (_limpio_fila2 and _limpio_fila2 in html)

    assert "123" in html
    assert "192.168.1.1" in html
    assert "internet" in html

    # La clasificación P0-B sí está disponible — no debe aparecer el fallback
    assert "la clasificación P0-B no está disponible" not in html

    # Motivo de DATOS se muestra como texto legible
    assert "Registro de sesión de datos" in html

    # El valor None no debe aparecer como "None" en el HTML
    assert ">None<" not in html
