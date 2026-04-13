import pytest
import pandas as pd
import numpy as np
from tz_core.bitacora_normalization import normalize_contact_fields

# --- tel_limpio ---

def test_tel_limpio_formato_internacional():
    df = pd.DataFrame({"tel": ["+503 7000-1234"], "contacto": [""]})
    result = normalize_contact_fields(df)
    assert result["tel_limpio"].iloc[0] == "+50370001234"

def test_tel_limpio_sin_prefijo():
    df = pd.DataFrame({"tel": ["7000-1234"], "contacto": [""]})
    result = normalize_contact_fields(df)
    assert result["tel_limpio"].iloc[0] == "70001234"

def test_tel_limpio_sin_columna_tel():
    df = pd.DataFrame({"contacto": ["70001234"]})
    result = normalize_contact_fields(df)
    assert result["tel_limpio"].iloc[0] is None

# --- contacto_limpio ---

def test_contacto_limpio_con_separadores():
    df = pd.DataFrame({"tel": [""], "contacto": ["(503) 7000-1234"]})
    result = normalize_contact_fields(df)
    assert result["contacto_limpio"].iloc[0] == "50370001234"

def test_contacto_limpio_internacional():
    df = pd.DataFrame({"tel": [""], "contacto": ["+503 7000-1234"]})
    result = normalize_contact_fields(df)
    assert result["contacto_limpio"].iloc[0] == "+50370001234"

# --- contacto_valido ---

def test_contacto_valido_numero_normal():
    df = pd.DataFrame({"tel": [""], "contacto": ["70001234"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == True

def test_contacto_invalido_desconocido():
    df = pd.DataFrame({"tel": [""], "contacto": ["DESCONOCIDO"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_privado():
    df = pd.DataFrame({"tel": [""], "contacto": ["PRIVADO"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_vacio():
    df = pd.DataFrame({"tel": [""], "contacto": [""]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_nan():
    df = pd.DataFrame({"tel": [""], "contacto": [np.nan]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_todo_ceros():
    df = pd.DataFrame({"tel": [""], "contacto": ["00000000"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_muy_corto():
    df = pd.DataFrame({"tel": [""], "contacto": ["123"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_muy_largo():
    df = pd.DataFrame({"tel": [""], "contacto": ["1234567890123456"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_extension():
    df = pd.DataFrame({"tel": [""], "contacto": ["70001234 ext 123"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

def test_contacto_invalido_asterisco():
    df = pd.DataFrame({"tel": [""], "contacto": ["*123"]})
    result = normalize_contact_fields(df)
    assert result["contacto_valido"].iloc[0] == False

# --- tolerancia a errores ---

def test_df_vacio():
    df = pd.DataFrame({"tel": [], "contacto": []})
    result = normalize_contact_fields(df)
    assert "tel_limpio" in result.columns
    assert "contacto_limpio" in result.columns
    assert "contacto_valido" in result.columns

def test_sin_columnas_tel_ni_contacto():
    df = pd.DataFrame({"otro": ["valor"]})
    result = normalize_contact_fields(df)
    assert result["tel_limpio"].iloc[0] is None
    assert result["contacto_valido"].iloc[0] == False
