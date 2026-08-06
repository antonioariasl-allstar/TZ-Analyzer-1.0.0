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


# --- CAPA 4b: formato ".0" (Tarea 1 — corrección de defecto de núcleo) ---
# Pruebas directas por tipo de entrada: int, float, string ".0", decimal no
# entero, IPv4, dominio, notación científica. Ver
# docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §8.0 para la causa raíz.

def test_punto_cero_entero_python_es_plausible():
    """int puro (sin sufijo .0 posible) — caso de control, no debe romperse."""
    assert _classify_contact_category(70021111, "70021111", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")


def test_punto_cero_float_python_es_plausible():
    """float real 70021111.0 (no string) — el caso exacto del defecto documentado."""
    assert _classify_contact_category(70021111.0, "70021111", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")


def test_punto_cero_string_es_plausible():
    """string "70021111.0" (exportación típica de Excel/CSV) — mismo defecto, vía string."""
    assert _classify_contact_category("70021111.0", "70021111", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")


def test_punto_cero_doble_cero_es_plausible():
    """string "70021111.00" — fracción de más de un cero, misma regla."""
    assert _classify_contact_category("70021111.00", "70021111", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")


def test_decimal_no_entero_no_se_convierte_en_telefono():
    """"70021111.5" tiene fracción no nula — debe seguir cayendo en formato_alfanumerico,
    NO convertirse en teléfono. El saneamiento de Tarea 1 es específico a fracción cero."""
    assert _classify_contact_category("70021111.5", None, "VOZ") == ("tecnico_no_personal", "formato_alfanumerico")


def test_ipv4_no_se_reinterpreta_como_decimal_punto_cero():
    """IPv4 sigue siendo IPv4 — el gate de IPv4 (4 octetos) corre antes y no debe
    verse afectado por el saneamiento de decimales .0 de un solo punto."""
    assert _classify_contact_category("192.168.1.0", None, "VOZ") == ("tecnico_no_personal", "ipv4")


def test_dominio_con_puntos_sigue_siendo_alfanumerico():
    """Un dominio (letras + puntos) no matchea el patrón "solo dígitos.solo ceros"
    y debe seguir cayendo en formato_alfanumerico, no convertirse en teléfono."""
    assert _classify_contact_category("internet.claro.sv", None, "VOZ") == ("tecnico_no_personal", "formato_alfanumerico")


def test_notacion_cientifica_no_afectada_por_saneamiento_punto_cero():
    """La notación científica ya se resolvía correctamente antes de Tarea 1 (el chequeo
    de científica corre antes del gate alfanumérico); el saneamiento nuevo no debe alterarla."""
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

def test_voz_digitos_5_es_indeterminado():
    # VOZ con 5 dígitos ya no supera el umbral mínimo de 8
    assert _classify_contact_category("70001", "70001", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_8_es_plausible():
    assert _classify_contact_category("70001234", "70001234", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_voz_digitos_11_con_prefijo_es_plausible():
    assert _classify_contact_category("+50370001234", "+50370001234", "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_voz_digitos_4_es_indeterminado():
    assert _classify_contact_category("7000", "7000", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_2_es_indeterminado():
    assert _classify_contact_category("70", "70", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_6_es_indeterminado():
    assert _classify_contact_category("700012", "700012", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_7_es_indeterminado():
    assert _classify_contact_category("7000123", "7000123", "VOZ") == ("indeterminado", "voz_longitud_corta")

def test_voz_digitos_16_es_longitud_excesiva():
    assert _classify_contact_category("1234567890123456", "1234567890123456", "VOZ") == ("indeterminado", "longitud_excesiva")

def test_sms_digitos_16_es_longitud_excesiva():
    assert _classify_contact_category("1234567890123456", "1234567890123456", "SMS") == ("indeterminado", "longitud_excesiva")


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


# --- Tarea 2: prudencia con bloques de 15 dígitos sin evidencia de formato ---

def test_15_digitos_sin_evidencia_es_indeterminado():
    limpio = "1" * 15
    assert _classify_contact_category(limpio, limpio, "VOZ") == (
        "indeterminado", "identificador_15_digitos_no_confirmado"
    )

def test_15_digitos_sms_sin_evidencia_es_indeterminado():
    limpio = "1" * 15
    assert _classify_contact_category(limpio, limpio, "SMS") == (
        "indeterminado", "identificador_15_digitos_no_confirmado"
    )

def test_15_digitos_con_prefijo_mas_es_plausible():
    raw = "+" + ("1" * 14)  # 14 dígitos tras el "+", 15 en total normalizado
    limpio = "1" * 15
    assert _classify_contact_category(raw, limpio, "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_15_digitos_con_prefijo_00_es_plausible():
    raw = "00" + ("1" * 13)
    limpio = "1" * 15
    assert _classify_contact_category(raw, limpio, "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_14_digitos_sin_evidencia_sigue_plausible():
    """La prudencia de Tarea 2 aplica solo a exactamente 15 dígitos, no a 14."""
    limpio = "1" * 14
    assert _classify_contact_category(limpio, limpio, "VOZ") == ("telefonico_plausible", "voz_longitud_valida")

def test_16_digitos_sigue_siendo_longitud_excesiva():
    """16 dígitos sigue cayendo en longitud_excesiva (E.164), no en la regla de 15."""
    limpio = "1" * 16
    assert _classify_contact_category(limpio, limpio, "VOZ") == ("indeterminado", "longitud_excesiva")


# --- Tarea 3: autocontacto ---

def test_autocontacto_mismo_numero_es_tecnico():
    assert _classify_contact_category("70099999", "70099999", "VOZ", "70099999") == (
        "tecnico_no_personal", "autocontacto"
    )

def test_autocontacto_numeros_distintos_no_es_autocontacto():
    assert _classify_contact_category("70011111", "70011111", "VOZ", "70099999") == (
        "telefonico_plausible", "voz_longitud_valida"
    )

def test_autocontacto_sin_tel_limpio_no_es_autocontacto():
    """tel_limpio=None (parámetro no provisto) — comportamiento por defecto sin cambios."""
    assert _classify_contact_category("70099999", "70099999", "VOZ") == (
        "telefonico_plausible", "voz_longitud_valida"
    )

def test_autocontacto_datos_prevalece_sobre_autocontacto():
    """DATOS se evalúa antes que autocontacto (§6-D del contrato: DATOS prevalece siempre)."""
    assert _classify_contact_category("70099999", "70099999", "DATOS", "70099999") == (
        "tecnico_no_personal", "tipo_datos"
    )


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
    # tel distinto de contacto: un mismo valor en ambas columnas activaría la
    # exclusión de autocontacto (Tarea 3, P0-B), que no es lo que este test cubre.
    df = pd.DataFrame({
        "tel": ["70009999"],
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
    """Sin columna tipo_evento_normalizado → DESCONOCIDO → indeterminado si formato válido.

    tel distinto de contacto: un mismo valor activaría la exclusión de
    autocontacto (Tarea 3, P0-B), que no es lo que este test cubre.
    """
    df = pd.DataFrame({
        "tel": ["70009999"],
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
