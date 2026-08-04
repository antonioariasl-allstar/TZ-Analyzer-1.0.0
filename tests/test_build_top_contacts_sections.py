"""Tests para build_top_contacts_sections() — rama P0-B y rama legacy."""
import pandas as pd
import pytest
from tz_core.html.contacts import build_top_contacts_sections


def _df_p0b(categorias, contactos_limpios, contactos_raw=None, durs=None):
    """DataFrame mínimo con columnas P0-B pre-pobladas."""
    n = len(categorias)
    return pd.DataFrame({
        "contacto":                contactos_raw or [f"700{i:04d}" for i in range(n)],
        "contacto_categoria":      categorias,
        "contacto_limpio":         contactos_limpios,
        "contacto_motivo":         ["voz_longitud_valida"] * n,
        "tipo_evento_normalizado": ["VOZ"] * n,
        "duracion":                durs or [60] * n,
    })


# ── CONTRATO DE RETORNO ─────────────────────────────────────────────────────

def test_retorna_tupla_str_str_int_siempre():
    df = _df_p0b(["telefonico_plausible"], ["70001234"])
    result = build_top_contacts_sections(df)
    assert isinstance(result, tuple) and len(result) == 3
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)
    assert isinstance(result[2], int)


def test_retorna_tupla_str_str_int_sin_columnas_p0b():
    df = pd.DataFrame({"contacto": ["70001234"], "duracion": [60]})
    result = build_top_contacts_sections(df)
    assert isinstance(result, tuple) and len(result) == 3


# ── RAMA P0-B — FILTRO Y CLAVE ──────────────────────────────────────────────

def test_p0b_excluye_tecnicos_e_indeterminados_del_ranking():
    df = _df_p0b(
        categorias=["telefonico_plausible", "tecnico_no_personal", "indeterminado"],
        contactos_limpios=["70001234", None, "7000"],
        contactos_raw=["70001234", "192.168.1.1", "7000"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "70001234" in cnt_html
    assert "192.168.1.1" not in cnt_html
    assert ">7000<" not in cnt_html


def test_p0b_usa_contacto_limpio_como_clave_de_agrupacion():
    """Dos filas con mismo contacto_limpio deben agruparse como un único contacto."""
    df = _df_p0b(
        categorias=["telefonico_plausible", "telefonico_plausible"],
        contactos_limpios=["50370001234", "50370001234"],
        contactos_raw=["+503 7000-1234", "50370001234"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "50370001234" in cnt_html
    assert "2 <span" in cnt_html  # conteo = 2, una sola entrada


# ── NOTA DE EXCLUSIONES ─────────────────────────────────────────────────────

def test_nota_con_ambos_tipos_excluidos():
    df = _df_p0b(
        categorias=[
            "telefonico_plausible", "telefonico_plausible",
            "tecnico_no_personal", "tecnico_no_personal",
            "indeterminado", "indeterminado",
        ],
        contactos_limpios=["70001234", "70005678", None, None, "700", "701"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "El ranking considera únicamente números con formato telefónico" in cnt_html


def test_nota_solo_tecnicos_usa_estos():
    df = _df_p0b(
        categorias=["telefonico_plausible", "tecnico_no_personal", "tecnico_no_personal"],
        contactos_limpios=["70001234", None, None],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "El ranking considera" in cnt_html
    assert "registros indeterminados" not in cnt_html


def test_nota_solo_indeterminados_usa_estos():
    df = _df_p0b(
        categorias=["telefonico_plausible", "indeterminado", "indeterminado"],
        contactos_limpios=["70001234", "700", "701"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "El ranking considera" in cnt_html
    assert "registros técnicos" not in cnt_html


def test_nota_siempre_visible_en_p0b():
    df = _df_p0b(
        categorias=["telefonico_plausible", "telefonico_plausible"],
        contactos_limpios=["70001234", "70005678"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "registros técnicos" not in cnt_html
    assert "registros indeterminados" not in cnt_html
    assert "El ranking considera únicamente números con formato telefónico" in cnt_html


# ── FALLBACK CUANDO NO HAY PLAUSIBLES ──────────────────────────────────────

def test_fallback_sin_telefonicos_menciona_formato_telefonico():
    df = _df_p0b(
        categorias=["tecnico_no_personal", "tecnico_no_personal", "indeterminado"],
        contactos_limpios=[None, None, "700"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "formato telefónico" in cnt_html


def test_fallback_sin_telefonicos_incluye_nota_metodologica():
    df = _df_p0b(
        categorias=["tecnico_no_personal", "indeterminado"],
        contactos_limpios=[None, "700"],
    )
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "El ranking considera" in cnt_html


# ── RAMA LEGACY ────────────────────────────────────────────────────────────

def test_legacy_sin_columnas_p0b_incluye_todos_los_contactos():
    """Sin contacto_categoria: todos los valores entran al ranking sin filtro."""
    df = pd.DataFrame({
        "contacto": ["70001234", "70001234", "abcdef"],
        "duracion":  [60, 60, 3600],
    })
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "70001234" in cnt_html
    assert "abcdef" in cnt_html


def test_legacy_sin_columnas_p0b_no_genera_nota_de_exclusion():
    df = pd.DataFrame({
        "contacto": ["70001234", "192.168.1.1"],
        "duracion":  [60, 3600],
    })
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "El ranking considera" not in cnt_html
    assert "registros técnicos" not in cnt_html
