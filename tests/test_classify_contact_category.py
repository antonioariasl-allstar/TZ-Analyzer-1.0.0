"""Tests para _classify_contact_category y columnas P0-B en normalize_contact_fields."""
import pytest
import pandas as pd
import numpy as np
from tz_core.bitacora_normalization import _classify_contact_category, normalize_contact_fields


# --- CAPA 1: vacío / nulo ---

def test_raw_none_es_tecnico():
    assert _classify_contact_category(None, None, "VOZ") == ("tecnico_no_personal", "vacio_o_nulo")

def test_raw_nan_es_tecnico():
    assert _classify_contact_category(float("nan"), None, "VOZ") == ("tecnico_no_personal", "vacio_o_nulo")

def test_raw_vacio_es_tecnico():
    assert _classify_contact_category("", None, "VOZ") == ("tecnico_no_personal", "vacio_o_nulo")

def test_raw_espacios_es_tecnico():
    assert _classify_contact_category("   ", None, "VOZ") == ("tecnico_no_personal", "vacio_o_nulo")


# --- CAPA 2: DATOS siempre técnico ---

def test_datos_numerico_es_tecnico():
    assert _classify_contact_category("70001234", "70001234", "DATOS") == ("tecnico_no_personal", "tipo_datos")

def test_datos_alfanumerico_es_tecnico():
    assert _classify_contact_category("internet.tigo.sv", None, "DATOS") == ("tecnico_no_personal", "tipo_datos")

def test_datos_ip_es_tecnico():
    assert _classify_contact_category("192.168.1.1", None, "DATOS") == ("tecnico_no_personal", "tipo_datos")


# --- CAPA 3: IPv4 ---

def test_ipv4_privado_es_tecnico():
    assert _classify_contact_category("192.168.1.1", None, "VOZ") == ("tecnico_no_personal", "ipv4")

def test_ipv4_publico_es_tecnico():
    assert _classify_contact_category("8.8.8.8", None, "SMS") == ("tecnico_no_personal", "ipv4")


# --- CAPA 4: alfanumérico / hex ---

def test_hex_corto_6c0_es_tecnico():
    assert _classify_contact_category("6C0", None, "SMS") == ("tecnico_no_personal", "formato_alfanumerico")

def test_hex_corto_4d4_es_tecnico():
    assert _classify_contact_category("4D4", None, "SMS") == ("tecnico_no_personal", "formato_alfanumerico")

def test_hex_largo_es_tecnico():
    assert _classify_contact_category("DC7A53935A605A", None, "SMS") == ("tecnico_no_personal", "formato_alfanumerico")

def test_hex_alfanumerico_es_tecnico():
    assert _classify_contact_category("7381C040", None, "SMS") == ("tecnico_no_personal", "formato_alfanumerico")

def test_apn_texto_es_tecnico():
    assert _classify_contact_category("internet.tigo.sv", None, "VOZ") == ("tecnico_no_personal", "formato_alfanumerico")

def test_texto_desconocido_es_tecnico():
    assert _classify_contact_category("DESCONOCIDO", None, "VOZ") == ("tecnico_no_personal", "formato_alfanumerico")


# --- CAPA 4: notación científica válida no bloqueada ---

def test_notacion_cientifica_voz_plausible():
    # 7.5E+10 → limpio "75000000000" (11 dígitos) → VOZ ≥ 5 → plausible
    assert _classify_contact_category("7.5E+10", "75000000000", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")


# --- CAPA 5: solo ceros ---

def test_solo_ceros_es_tecnico():
    assert _classify_contact_category("00000000", "00000000", "VOZ") == ("tecnico_no_personal", "solo_ceros")


# --- CAPA 6: contacto_limpio no disponible ---

def test_limpio_none_es_tecnico():
    assert _classify_contact_category("70001234", None, "VOZ") == ("tecnico_no_personal", "sin_contacto_limpio")

def test_limpio_nan_es_tecnico():
    assert _classify_contact_category("70001234", float("nan"), "VOZ") == ("tecnico_no_personal", "sin_contacto_limpio")


# --- CAPA 7: longitud 0–1 → técnico, no indeterminado ---

def test_longitud_1_es_tecnico():
    assert _classify_contact_category("5", "5", "VOZ") == ("tecnico_no_personal", "longitud_insuficiente")

def test_longitud_1_sms_es_tecnico():
    assert _classify_contact_category("5", "5", "SMS") == ("tecnico_no_personal", "longitud_insuficiente")


# --- Matriz VOZ ---

def test_voz_digitos_5_es_plausible():
    assert _classify_contact_category("70001", "70001", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_voz_digitos_8_es_plausible():
    assert _classify_contact_category("70001234", "70001234", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_voz_digitos_11_con_prefijo_es_plausible():
    assert _classify_contact_category("+50370001234", "+50370001234", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_voz_digitos_4_es_indeterminado():
    assert _classify_contact_category("7000", "7000", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_2_es_indeterminado():
    assert _classify_contact_category("70", "70", "VOZ") == ("indeterminado", "voz_longitud_corta")


# --- Matriz SMS ---

def test_sms_digitos_8_es_plausible():
    assert _classify_contact_category("70001234", "70001234", "SMS") == ("telefonico_plausible", "sms_longitud_valida")

def test_sms_digitos_11_es_plausible():
    assert _classify_contact_category("50370001234", "50370001234", "SMS") == ("telefonico_plausible", "sms_longitud_valida")

def test_sms_digitos_7_es_indeterminado():
    assert _classify_contact_category("7000123", "7000123", "SMS") == ("indeterminado", "sms_longitud_ambigua")

def test_sms_digitos_5_es_indeterminado():
    assert _classify_contact_category("70001", "70001", "SMS") == ("indeterminado", "sms_longitud_ambigua")

def test_sms_digitos_4_es_indeterminado():
    assert _classify_contact_category("7000", "7000", "SMS") == ("indeterminado", "sms_longitud_ambigua")


# --- Matriz DESCONOCIDO ---

def test_desconocido_digitos_8_es_indeterminado():
    assert _classify_contact_category("70001234", "70001234", "DESCONOCIDO") == ("indeterminado", "desconocido_longitud_plausible")

def test_desconocido_digitos_5_es_indeterminado():
    assert _classify_contact_category("70001", "70001", "DESCONOCIDO") == ("indeterminado", "desconocido_longitud_plausible")

def test_desconocido_digitos_4_es_indeterminado():
    assert _classify_contact_category("7000", "7000", "DESCONOCIDO") == ("indeterminado", "desconocido_longitud_corta")

def test_desconocido_digitos_2_es_indeterminado():
    assert _classify_contact_category("70", "70", "DESCONOCIDO") == ("indeterminado", "desconocido_longitud_corta")


# --- Integración via normalize_contact_fields ---

def test_integracion_datos_produce_tecnico():
    df = pd.DataFrame({
        "tel": ["70001234"],
        "contacto": ["70001234"],
        "tipo_evento_normalizado": ["DATOS"],
    })
    result = normalize_contact_fields(df)
    assert result["contacto_categoria"].iloc[0] == "tecnico_no_personal"
    assert result["contacto_motivo"].iloc[0] == "tipo_datos"

def test_integracion_voz_plausible():
    df = pd.DataFrame({
        "tel": ["70001234"],
        "contacto": ["70001234"],
        "tipo_evento_normalizado": ["VOZ"],
    })
    result = normalize_contact_fields(df)
    assert result["contacto_categoria"].iloc[0] == "telefonico_plausible"
    assert result["contacto_motivo"].iloc[0] == "voz_longitud_valida"

def test_integracion_hex_sms_es_tecnico():
    df = pd.DataFrame({
        "tel": ["70001234"],
        "contacto": ["6C0"],
        "tipo_evento_normalizado": ["SMS"],
    })
    result = normalize_contact_fields(df)
    assert result["contacto_categoria"].iloc[0] == "tecnico_no_personal"
    assert result["contacto_motivo"].iloc[0] == "formato_alfanumerico"

def test_integracion_sin_tipo_evento_normalizado():
    """Sin columna tipo_evento_normalizado → DESCONOCIDO → indeterminado si formato válido."""
    df = pd.DataFrame({
        "tel": ["70001234"],
        "contacto": ["70001234"],
    })
    result = normalize_contact_fields(df)
    assert result["contacto_categoria"].iloc[0] == "indeterminado"

def test_integracion_columnas_presentes():
    """Las cuatro columnas derivadas siempre deben existir en el resultado."""
    df = pd.DataFrame({
        "tel": ["70001234"],
        "contacto": ["70001234"],
        "tipo_evento_normalizado": ["VOZ"],
    })
    result = normalize_contact_fields(df)
    for col in ["contacto_limpio", "contacto_valido", "contacto_categoria", "contacto_motivo"]:
        assert col in result.columns, f"Columna ausente: {col}"

def test_integracion_sin_columna_contacto():
    """Sin columna contacto → fallback categoria/motivo presentes."""
    df = pd.DataFrame({"tel": ["70001234"]})
    result = normalize_contact_fields(df)
    assert result["contacto_categoria"].iloc[0] == "tecnico_no_personal"
    assert result["contacto_motivo"].iloc[0] == "sin_columna_contacto"
