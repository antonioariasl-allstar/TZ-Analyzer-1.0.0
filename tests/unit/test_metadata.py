from __future__ import annotations

import pandas as pd

from tz_core.html.metadata import build_identification_rows
from tz_core.html_helpers import luhn_check


def _row_fragment(html: str, label: str) -> str:
    """Extrae el fragmento <tr>...</tr> correspondiente a una etiqueta dada."""
    marker = f"<b>{label}:</b>"
    start = html.find(marker)
    assert start != -1, f"No se encontro la fila '{label}' en: {html!r}"
    row_start = html.rfind("<tr>", 0, start)
    row_end = html.find("</tr>", start) + len("</tr>")
    return html[row_start:row_end]


def test_un_numero_y_un_imsi_ambas_filas_propias_sin_fusion():
    df = pd.DataFrame({
        "tel": ["70871087"],
        "imsi": ["706040021599843"],
    })

    ident_rows = build_identification_rows(df)

    tel_row = _row_fragment(ident_rows, "Número telefónico")
    imsi_row = _row_fragment(ident_rows, "IMSI")

    assert "70871087" in tel_row
    assert "IMSI" not in tel_row
    assert "706040021599843" in imsi_row


def test_un_imei_valido_de_15_digitos_aparece_sin_reconstruccion():
    df = pd.DataFrame({"imei": ["490154203237518"]})  # 15 digitos, Luhn OK

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert "490154203237518" in imei_row
    assert "IMEI reportado" not in imei_row
    assert "IMEI reconstruido" not in imei_row
    assert "inconsistencia" not in imei_row


def test_imei_15_digitos_terminado_en_cero_muestra_reconstruccion_luhn():
    reportado = "123456789012340"
    reconstruido_esperado = "123456789012347"
    df = pd.DataFrame({"imei": [reportado]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert f"IMEI reportado: {reportado}" in imei_row
    assert f"IMEI reconstruido (Luhn): {reconstruido_esperado}" in imei_row
    assert luhn_check(reconstruido_esperado) is True
    assert "no superada" not in imei_row


def test_imei_15_digitos_terminado_en_cero_caso_real():
    reportado = "352971685312360"
    reconstruido_esperado = "352971685312361"
    df = pd.DataFrame({"imei": [reportado]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert f"IMEI reportado: {reportado}" in imei_row
    assert f"IMEI reconstruido (Luhn): {reconstruido_esperado}" in imei_row
    assert luhn_check(reconstruido_esperado) is True


def test_imei_14_digitos_agrega_digito_calculado_y_reconstruido():
    reportado = "49015420323751"  # 14 digitos
    reconstruido_esperado = "490154203237518"  # digito verificador calculado: 8
    df = pd.DataFrame({"imei": [reportado]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert f"IMEI reportado: {reportado}" in imei_row
    assert f"IMEI reconstruido (Luhn): {reconstruido_esperado}" in imei_row
    assert luhn_check(reconstruido_esperado) is True


def test_imei_15_digitos_no_terminado_en_cero_luhn_invalido_se_conserva():
    reportado = "490154203237519"  # 15 digitos, no termina en 0, Luhn falla
    df = pd.DataFrame({"imei": [reportado]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert reportado in imei_row
    assert "inconsistencia de validación Luhn" in imei_row
    assert "IMEI reconstruido" not in imei_row


def test_imei_16_digitos_se_conserva_como_posible_imeisv():
    reportado = "1234567890123456"
    df = pd.DataFrame({"imei": [reportado]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert reportado in imei_row
    assert "posible IMEISV" in imei_row
    assert "IMEI reconstruido" not in imei_row
    assert "Luhn" not in imei_row


def test_varios_imei_cada_uno_conserva_su_tratamiento_propio():
    valido = "490154203237518"
    terminado_en_cero = "123456789012340"
    reconstruido_esperado = "123456789012347"
    imeisv = "1234567890123456"
    df = pd.DataFrame({"imei": [valido, terminado_en_cero, imeisv]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert valido in imei_row
    assert f"IMEI reportado: {terminado_en_cero}" in imei_row
    assert f"IMEI reconstruido (Luhn): {reconstruido_esperado}" in imei_row
    assert f"{imeisv} — posible IMEISV" in imei_row


def test_imei_duplicados_aparece_una_sola_vez():
    df = pd.DataFrame({
        "imei": ["490154203237518", "490154203237518", "490154203237518"],
    })

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert imei_row.count("490154203237518") == 1


def test_imei_con_sufijo_punto_cero_aparece_limpio():
    df = pd.DataFrame({"imei": ["490154203237518.0"]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert "490154203237518" in imei_row
    assert "490154203237518.0" not in imei_row


def test_columna_imei_ausente_muestra_no_disponible():
    df = pd.DataFrame({"tel": ["70871087"]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert "IMEI no disponible" in imei_row


def test_columna_imei_con_valores_no_utilizables_muestra_no_disponible():
    df = pd.DataFrame({"imei": ["S/I", "N/A", "0", "", None]})

    ident_rows = build_identification_rows(df)
    imei_row = _row_fragment(ident_rows, "IMEI")

    assert "IMEI no disponible" in imei_row


def test_un_imsi_valido_aparece_en_su_propia_fila():
    df = pd.DataFrame({"imsi": ["706040021599843"]})

    ident_rows = build_identification_rows(df)
    imsi_row = _row_fragment(ident_rows, "IMSI")

    assert "706040021599843" in imsi_row


def test_varios_imsi_con_duplicados_aparecen_solo_los_unicos():
    df = pd.DataFrame({
        "imsi": ["706040021599843", "706040021599843", "706040021599999"],
    })

    ident_rows = build_identification_rows(df)
    imsi_row = _row_fragment(ident_rows, "IMSI")

    assert imsi_row.count("706040021599843") == 1
    assert "706040021599999" in imsi_row


def test_columna_imsi_ausente_muestra_no_disponible():
    df = pd.DataFrame({"tel": ["70871087"]})

    ident_rows = build_identification_rows(df)
    imsi_row = _row_fragment(ident_rows, "IMSI")

    assert "IMSI no disponible" in imsi_row


def test_columna_imsi_con_valores_no_utilizables_muestra_no_disponible():
    df = pd.DataFrame({"imsi": ["", None, "12"]})  # "12" no tiene 14-16 digitos

    ident_rows = build_identification_rows(df)
    imsi_row = _row_fragment(ident_rows, "IMSI")

    assert "IMSI no disponible" in imsi_row


def test_html_no_fusiona_imsi_dentro_de_fila_telefonica():
    df = pd.DataFrame({
        "tel": ["70871087", "70000001"],
        "imsi": ["706040021599843", "706040021599999"],
    })

    ident_rows = build_identification_rows(df)
    tel_row = _row_fragment(ident_rows, "Número telefónico")

    assert "IMSI" not in tel_row
    assert ident_rows.count("<b>IMSI:</b>") == 1


def test_numero_telefonico_unico_no_desaparece():
    df = pd.DataFrame({"tel": ["70871087"]})

    ident_rows = build_identification_rows(df)
    tel_row = _row_fragment(ident_rows, "Número telefónico")

    assert "70871087" in tel_row


def test_varios_numeros_telefonicos_muestran_lista_de_unicos():
    df = pd.DataFrame({"tel": ["70871087", "70871087", "70000001"]})

    ident_rows = build_identification_rows(df)
    tel_row = _row_fragment(ident_rows, "Número telefónico")

    assert tel_row.count("70871087") == 1
    assert "70000001" in tel_row


def test_sin_numero_utilizable_mantiene_comportamiento_actual_sin_fila():
    df = pd.DataFrame({"imei": ["490154203237518"]})

    ident_rows = build_identification_rows(df)

    assert "<b>Número telefónico:</b>" not in ident_rows
