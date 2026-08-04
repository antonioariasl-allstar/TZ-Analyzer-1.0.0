"""Tests para construir_seccion_todos_contactos() — bloques P0-B."""
import pytest
import pandas as pd
from tz_core.analytics import construir_seccion_todos_contactos


def _df_completo():
    """DataFrame con una fila por cada categoría P0-B."""
    return pd.DataFrame({
        "contacto":                ["70001234",          "7000",        "192.168.1.1"],
        "contacto_categoria":      ["telefonico_plausible", "indeterminado", "tecnico_no_personal"],
        "contacto_limpio":         ["70001234",          "7000",        None],
        "contacto_motivo":         ["voz_longitud_valida", "voz_longitud_corta", "ipv4"],
        "tipo_evento_normalizado": ["VOZ",               "VOZ",         "VOZ"],
        "_sec":                    [120,                 0,             0],
    })


def test_genera_los_tres_bloques():
    result = construir_seccion_todos_contactos(_df_completo())
    assert "Números con formato telefónico" in result
    assert "Números o códigos de longitud menor" in result
    assert "Registros técnicos y de datos" in result


def test_tecnicos_dentro_de_details():
    result = construir_seccion_todos_contactos(_df_completo())
    idx_details = result.index("<details>")
    idx_titulo = result.index("Registros técnicos y de datos")
    assert idx_details < idx_titulo


def test_categoria_vacia_muestra_nota_declarativa():
    df = pd.DataFrame({
        "contacto":                ["70001234"],
        "contacto_categoria":      ["telefonico_plausible"],
        "contacto_limpio":         ["70001234"],
        "contacto_motivo":         ["voz_longitud_valida"],
        "tipo_evento_normalizado": ["VOZ"],
        "_sec":                    [60],
    })
    result = construir_seccion_todos_contactos(df)
    assert "No se encontraron registros indeterminados" in result
    assert "No se encontraron registros técnicos" in result


def test_falta_columna_p0b_activa_fallback():
    df = pd.DataFrame({
        "contacto": ["70001234"],
        "contacto_limpio": ["70001234"],
        "contacto_motivo": ["voz_longitud_valida"],
        "tipo_evento_normalizado": ["VOZ"],
        "_sec": [60],
        # contacto_categoria ausente deliberadamente
    })
    result = construir_seccion_todos_contactos(df)
    assert "clasificación\nP0-B no está disponible" in result or "clasificación P0-B no está disponible" in result


def test_valores_con_caracteres_especiales_escapados():
    df = pd.DataFrame({
        "contacto":                ["<script>"],
        "contacto_categoria":      ["tecnico_no_personal"],
        "contacto_limpio":         [None],
        "contacto_motivo":         ["formato_alfanumerico"],
        "tipo_evento_normalizado": ["VOZ"],
        "_sec":                    [0],
    })
    result = construir_seccion_todos_contactos(df)
    assert "&lt;script&gt;" in result
    assert "<script>" not in result.split('<section')[1]  # fuera de la etiqueta de apertura


def test_motivos_internos_muestran_texto_legible():
    df = pd.DataFrame({
        "contacto":                ["192.168.1.1"],
        "contacto_categoria":      ["tecnico_no_personal"],
        "contacto_limpio":         [None],
        "contacto_motivo":         ["ipv4"],
        "tipo_evento_normalizado": ["VOZ"],
        "_sec":                    [0],
    })
    result = construir_seccion_todos_contactos(df)
    assert "Dirección IPv4" in result
    # el código interno no debe aparecer en las celdas de la tabla
    assert ">ipv4<" not in result


def test_conteo_y_minutos_de_plausibles_son_correctos():
    df = pd.DataFrame({
        "contacto":                ["50312345678", "50312345678"],
        "contacto_categoria":      ["telefonico_plausible", "telefonico_plausible"],
        "contacto_limpio":         ["50312345678", "50312345678"],
        "contacto_motivo":         ["voz_longitud_valida", "voz_longitud_valida"],
        "tipo_evento_normalizado": ["VOZ", "VOZ"],
        "_sec":                    [60, 60],
    })
    result = construir_seccion_todos_contactos(df)
    # conteo = 2, minutos = 60+60=120 seg → 2 min
    assert ">2<" in result
