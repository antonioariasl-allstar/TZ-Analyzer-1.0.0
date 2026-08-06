"""FX-03 — fixture adversarial de contactos y pruebas de contrato P0-B.

No existe convención de fixtures Python compartidas en este proyecto
(ver `tests/test_build_top_contacts_sections.py` y otros: cada archivo de
test define su propio builder). Este archivo sigue esa convención y define
FX-03 como un helper local en vez de crear `tests/fixtures/`.

FX-03 cubre 22 casos adversariales especificados en la investigación P0-B
Hito 1 (ver docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md para el fundamento
técnico-normativo de cada regla). El número investigado (`tel`) es
constante ("70099999") en todas las filas; el caso de autocontacto (fila 9)
usa ese mismo valor como `contacto`.

Convención de nombres de test en este archivo:
  - `test_...`       pruebas de no regresión — deben pasar HOY.
  - `test_red_...`    pruebas rojas — fallan HOY por una causa semántica
                      documentada en el docstring de cada test. Ejecutar
                      selectivamente con `-k red` / `-k "not red"`.
  - `test_intl_...`   pruebas de contrato para numeración internacional
                      (Tarea 7); pueden ser verdes o rojas — se indica en
                      cada docstring.
"""
from __future__ import annotations

import pandas as pd
import pytest

from tz_core.bitacora_normalization import (
    normalize_event_fields,
    normalize_contact_fields,
    normalize_msisdn,
)
from tz_core.qc_type_classifier import classify_single
from tz_core.html.contacts import build_top_contacts_sections, calcular_metricas_contactos
from tz_core.analytics import construir_seccion_todos_contactos
from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.logging_utils import write_minimal_filter_log
from tz_core.capabilities import detectar_capacidades


TEL_INVESTIGADO = "70099999"

# Cada tupla: (n_caso, descripcion, contacto, interaccion)
_FX03_CASOS = [
    (1,  "movil_sv_plausible",              "70011111",                              "VOZ"),
    (2,  "mismo_movil_prefijo_503",         "+50370011111",                          "VOZ"),
    (3,  "mismo_movil_espacios_guiones",    "503 7001-1111",                         "VOZ"),
    (4,  "movil_float_punto_cero",          70011111.0,                              "VOZ"),
    (5,  "segundo_movil_valido",            "70021111",                              "VOZ"),
    (6,  "fijo_sv_plausible",               "22334455",                              "VOZ"),
    (7,  "internacional_con_mas",           "+50255551234",                          "VOZ"),
    (8,  "internacional_con_00",            "0050255551234",                         "VOZ"),
    (9,  "autocontacto",                    TEL_INVESTIGADO,                         "VOZ"),
    (10, "codigo_corto",                    "321",                                   "SMS"),
    (11, "alfanumerico_sms",                "6C0",                                   "SMS"),
    (12, "ipv4",                            "192.168.1.15",                          "VOZ"),
    (13, "ipv6",                            "2001:0db8:0:cd30:123:4567:89ab:cdef",   "VOZ"),
    (14, "dominio",                         "internet.claro.sv",                     "VOZ"),
    (15, "url",                             "http://x.sv/a",                         "VOZ"),
    (16, "apn",                             "apn.claro.sv",                          "DATOS"),
    (17, "datos_numerico_8_digitos",        "80012345",                              "DATOS"),
    (18, "datos_numerico_largo",            "800123456789012",                       "DATOS"),
    (19, "placeholder",                     "Sin Inf.",                              "DESCONOCIDO"),
    (20, "indeterminado",                   "54321",                                 "DESCONOCIDO"),
    (21, "mas_de_15_digitos",               "1234567890123456",                      "VOZ"),
    (22, "imei_imsi_like_15_digitos",       "123456789012345",                       "VOZ"),
]

_FX03_HORAS = [f"08:{i:02d}:00" for i in range(len(_FX03_CASOS))]
_FX03_DURACIONES = ["00:01:00"] * len(_FX03_CASOS)


def _fx03_raw_df() -> pd.DataFrame:
    """DataFrame crudo FX-03: fecha, hora, tel, contacto, interaccion,
    duracion, antena, lat, long, azimut. Duración autodescriptiva
    (HH:MM:SS) para que la unidad no distraiga las aserciones."""
    n = len(_FX03_CASOS)
    return pd.DataFrame({
        "fecha": ["05/08/2026"] * n,
        "hora": _FX03_HORAS,
        "tel": [TEL_INVESTIGADO] * n,
        "contacto": [c[2] for c in _FX03_CASOS],
        "interaccion": [c[3] for c in _FX03_CASOS],
        "duracion": _FX03_DURACIONES,
        "antena": ["ANT-001"] * n,
        "lat": [13.7000] * n,
        "long": [-89.2000] * n,
        "azimut": [90] * n,
    })


def _fx03_p0b_df() -> pd.DataFrame:
    """FX-03 con columnas P0-B ya calculadas (normalize_event_fields + normalize_contact_fields)."""
    df = _fx03_raw_df()
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    return df


def _caso(nombre: str) -> tuple:
    """Ubica un caso FX-03 por nombre descriptivo; retorna (n, nombre, contacto, interaccion)."""
    for c in _FX03_CASOS:
        if c[1] == nombre:
            return c
    raise KeyError(nombre)


# ═══════════════════════════════════════════════════════════════════════
# PRUEBAS DE NO REGRESIÓN (Tarea 5) — deben pasar HOY
# ═══════════════════════════════════════════════════════════════════════

def test_datos_no_entra_a_top_contactos():
    """Caso 16/17/18 (APN, DATOS 8 y 15 dígitos) no aparecen en el ranking."""
    df = _fx03_p0b_df()
    cnt_html, dur_html, _ = build_top_contacts_sections(df)
    assert "80012345" not in cnt_html
    assert "800123456789012" not in cnt_html
    assert "apn.claro.sv" not in cnt_html


def test_codigo_corto_no_entra_a_ranking():
    """Caso 10 (código corto '321') cae en indeterminado — longitud insuficiente para SMS."""
    df = _fx03_p0b_df()
    fila = df[df["contacto"] == "321"].iloc[0]
    assert fila["contacto_categoria"] == "indeterminado"
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert ">321<" not in cnt_html


def test_alfanumerico_no_entra_a_ranking():
    """Caso 11 ('6C0') es formato_alfanumerico, técnico, fuera de ranking."""
    df = _fx03_p0b_df()
    fila = df[df["contacto"] == "6C0"].iloc[0]
    assert fila["contacto_categoria"] == "tecnico_no_personal"
    assert fila["contacto_motivo"] == "formato_alfanumerico"
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "6C0" not in cnt_html


def test_ip_no_entra_a_ranking():
    """Caso 12 (IPv4) y caso 13 (IPv6) quedan técnicos y fuera del ranking.

    IPv4 tiene motivo dedicado ('ipv4'); IPv6 cae en 'formato_alfanumerico'
    (sin motivo dedicado — ver limitación §8.2 del contrato). El efecto
    (exclusión del ranking) es correcto en ambos casos.
    """
    df = _fx03_p0b_df()
    ipv4 = df[df["contacto"] == "192.168.1.15"].iloc[0]
    ipv6 = df[df["contacto"] == "2001:0db8:0:cd30:123:4567:89ab:cdef"].iloc[0]
    assert (ipv4["contacto_categoria"], ipv4["contacto_motivo"]) == ("tecnico_no_personal", "ipv4")
    assert ipv6["contacto_categoria"] == "tecnico_no_personal"
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "192.168.1.15" not in cnt_html
    assert "2001:0db8" not in cnt_html


def test_fijo_plausible_no_se_excluye_por_ser_fijo():
    """Caso 6 (fijo SV, prefijo '2', 8 dígitos, VOZ) es telefonico_plausible igual que un móvil."""
    df = _fx03_p0b_df()
    fila = df[df["contacto"] == "22334455"].iloc[0]
    assert fila["contacto_categoria"] == "telefonico_plausible"
    assert fila["contacto_motivo"] == "voz_longitud_valida"
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "22334455" in cnt_html


def test_formato_punto_cero_se_sanea_en_contacto_limpio():
    """contacto_limpio despoja el sufijo '.0' correctamente (aislado de la
    categoría — ver test_red_formato_punto_cero_deberia_ser_plausible para
    la categoría, que SÍ está afectada por el defecto crítico documentado)."""
    df = _fx03_p0b_df()
    idx_caso4 = _caso("movil_float_punto_cero")[0] - 1
    fila = df.iloc[idx_caso4]
    assert fila["contacto_limpio"] == "70011111"


def test_formatos_nacionales_equivalentes_se_consolidan():
    """Casos 2 y 3 (mismo número +503, con y sin separadores) consolidan al
    mismo contacto_limpio y se agrupan como una sola entrada en el ranking."""
    df = _fx03_p0b_df()
    limpio_2 = df[df["contacto"] == "+50370011111"]["contacto_limpio"].iloc[0]
    limpio_3 = df[df["contacto"] == "503 7001-1111"]["contacto_limpio"].iloc[0]
    assert limpio_2 == limpio_3 == "50370011111"
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert "2 <span" in cnt_html  # se agruparon en una fila con conteo=2


def test_seccion_tecnica_conserva_trazabilidad():
    """El Bloque C ('Registros técnicos') conserva valor original, normalizado,
    tipo de evento, conteo y motivo legible para un identificador DATOS."""
    df = _fx03_p0b_df()
    html = construir_seccion_todos_contactos(df)
    assert "80012345" in html
    assert "Registro de sesión de datos" in html
    assert "DATOS" in html


def test_kml_no_se_afecta_por_columnas_p0b(tmp_path):
    """generar_kml no falla ni cambia su comportamiento por la presencia de
    columnas P0-B (contacto_categoria/contacto_limpio/...) en el DataFrame."""
    import zipfile
    import tz_core.kml_generator as kml_mod
    from tz_core.kml_generator import generar_kml

    cfg = {"kml": {"azimuth_km": 1.0}, "style": {"theme_hex": "#ff0000"}, "salida": {"solo_kmz": True}}

    df_sin_p0b = _fx03_raw_df()
    df_con_p0b = _fx03_p0b_df()

    # Mismo nombre base en subcarpetas separadas: generar_kml usa el nombre
    # de archivo como <name> de la carpeta raíz del KML, así que un nombre
    # distinto por sí solo produciría una diferencia espuria no relacionada
    # con P0-B.
    (tmp_path / "sin_p0b").mkdir()
    (tmp_path / "con_p0b").mkdir()

    kml_mod._REUSABLE_STYLES = None
    out1 = str(tmp_path / "sin_p0b" / "salida.kml")
    generar_kml(df_sin_p0b, out1, cfg)
    assert (tmp_path / "sin_p0b" / "salida.kmz").exists()

    kml_mod._REUSABLE_STYLES = None
    out2 = str(tmp_path / "con_p0b" / "salida.kml")
    generar_kml(df_con_p0b, out2, cfg)
    assert (tmp_path / "con_p0b" / "salida.kmz").exists()

    import re

    def _normalizar(xml_bytes: bytes) -> bytes:
        # simplekml asigna id="N" y estilos "#N" con un contador global
        # incremental por proceso; dos generaciones sucesivas dentro del
        # mismo proceso difieren en esos IDs aunque el contenido geoespacial
        # sea idéntico. Se normalizan antes de comparar.
        out = re.sub(rb'id="\d+"', b'id="N"', xml_bytes)
        out = re.sub(rb'#\d+', b'#N', out)
        return out

    with zipfile.ZipFile(str(tmp_path / "sin_p0b" / "salida.kmz")) as z1, zipfile.ZipFile(str(tmp_path / "con_p0b" / "salida.kmz")) as z2:
        doc1 = _normalizar(z1.read("doc.kml"))
        doc2 = _normalizar(z2.read("doc.kml"))
    assert doc1 == doc2, "El KML no debe cambiar por la sola presencia de columnas P0-B"


def test_datos_prevalece_aunque_valor_parezca_internacional():
    """Un valor con apariencia de número internacional (+50255551234) pero
    evento DATOS se clasifica tecnico_no_personal/tipo_datos, no telefonico_plausible."""
    df = pd.DataFrame({"contacto": ["+50255551234"], "interaccion": ["DATOS"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_categoria"].iloc[0] == "tecnico_no_personal"
    assert df["contacto_motivo"].iloc[0] == "tipo_datos"


def test_valor_original_internacional_se_conserva():
    """El valor original de un contacto internacional se conserva sin alterar
    en la sección 'Todos los contactos' (Bloque A)."""
    df = _fx03_p0b_df()
    html = construir_seccion_todos_contactos(df)
    limpio_internacional = normalize_msisdn("+50255551234")
    assert limpio_internacional in html


# ═══════════════════════════════════════════════════════════════════════
# PRUEBAS ROJAS — DEFECTO CRÍTICO DE NÚCLEO (no es ruta legacy)
# ═══════════════════════════════════════════════════════════════════════

def test_red_formato_punto_cero_deberia_ser_plausible():
    """RED — defecto crítico en `_classify_contact_category`.

    Causa exacta: el paso 5 de `_classify_contact_category`
    (bitacora_normalization.py) construye `raw_phone_stripped` con
    `re.sub(r"[\\s\\+\\-\\(\\)]", "", raw_str)` sobre el valor CRUDO; el
    patrón no incluye el punto decimal, así que "70011111.0" (float o
    string) falla `.isdigit()` y no matchea notación científica, cayendo
    en `formato_alfanumerico` ANTES de llegar al paso 7, que sí usaría
    `contacto_limpio` (ya correctamente saneado a "70011111" por
    `normalize_msisdn`). Resultado: `contacto_valido=True` pero
    `contacto_categoria="tecnico_no_personal"` para la misma fila —
    contradicción interna. Ver docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §8.0.
    """
    df = _fx03_p0b_df()
    fila = df[df["hora"] == _FX03_HORAS[3]].iloc[0]  # caso 4: movil_float_punto_cero
    assert fila["contacto_valido"] is True or bool(fila["contacto_valido"]) is True
    assert fila["contacto_categoria"] == "telefonico_plausible", (
        f"Se esperaba telefonico_plausible; el defecto de núcleo produce "
        f"{fila['contacto_categoria']!r}/{fila['contacto_motivo']!r}"
    )


def test_red_punto_cero_consolida_con_forma_entera_del_mismo_numero():
    """RED — consecuencia directa del defecto anterior: el caso 4 (float .0
    de "70011111") debería aparecer en el ranking junto al caso 1
    (mismo número, forma entera) pero hoy queda excluido por completo.

    Se aísla el DataFrame a solo los casos 1 y 4 (mismo número, dos formas)
    para evitar falsos positivos por coincidencia de substring: el string
    consolidado del caso 2/3 ("50370011111") contiene "70011111" como
    substring, lo que haría pasar una aserción laxa por una razón
    incorrecta.
    """
    df = _fx03_p0b_df()
    idx_caso1 = _caso("movil_sv_plausible")[0] - 1
    idx_caso4 = _caso("movil_float_punto_cero")[0] - 1
    sub = df.iloc[[idx_caso1, idx_caso4]].copy()
    cnt_html, _, _ = build_top_contacts_sections(sub)
    assert ">70011111<" in cnt_html
    assert ">2<" in cnt_html or "(2)" in cnt_html or "2 <span" in cnt_html, (
        "Se esperaba un único contacto '70011111' con conteo=2 (casos 1 y 4 "
        "consolidados); el defecto de núcleo excluye el caso 4 del todo"
    )


# ═══════════════════════════════════════════════════════════════════════
# PRUEBAS ROJAS — CONTRATO DE PRODUCTO (Tarea 2, aprobado en este hito)
# ═══════════════════════════════════════════════════════════════════════

def test_red_autocontacto_no_tiene_motivo_dedicado():
    """RED — `_classify_contact_category` no recibe `tel_limpio` y no puede
    comparar contacto_limpio == tel_limpio; no existe el motivo 'autocontacto'.
    Contrato §6-C exige motivo dedicado y categoría tecnico_no_personal."""
    df = _fx03_p0b_df()
    fila = df[df["contacto"] == TEL_INVESTIGADO].iloc[0]
    assert fila["contacto_motivo"] == "autocontacto", (
        f"Se obtuvo motivo={fila['contacto_motivo']!r}, categoria={fila['contacto_categoria']!r} "
        f"— no existe distinción de autocontacto hoy"
    )
    assert fila["contacto_categoria"] == "tecnico_no_personal"


def test_red_autocontacto_no_entra_a_ranking():
    """RED — sin exclusión de autocontacto, el número investigado marcándose
    a sí mismo hoy SÍ puede aparecer como un contacto plausible en el ranking."""
    df = _fx03_p0b_df()
    cnt_html, _, _ = build_top_contacts_sections(df)
    assert TEL_INVESTIGADO not in cnt_html, (
        "El autocontacto apareció en el ranking — contrato §6-C exige exclusión"
    )


def test_red_imsi_like_no_asciende_automaticamente_a_plausible():
    """RED — Tarea 7 punto 5. Un bloque de 15 dígitos sin evidencia adicional
    de formato (+/00) puede ser un IMSI (ITU-T E.212, 15 dígitos exactos:
    MCC+MNC+MSIN), no necesariamente un MSISDN. Hoy, con tipo VOZ, un valor
    de 15 dígitos asciende directo a telefonico_plausible sin ninguna
    heurística de prudencia adicional (ver contrato §5 y matriz §9)."""
    df = _fx03_p0b_df()
    fila = df[df["contacto"] == "123456789012345"].iloc[0]
    assert fila["contacto_categoria"] == "indeterminado", (
        f"Se esperaba prudencia (indeterminado) ante un bloque de 15 dígitos "
        f"sin evidencia de formato internacional; se obtuvo "
        f"{fila['contacto_categoria']!r} — el sistema no distingue MSISDN de IMSI"
    )


# ═══════════════════════════════════════════════════════════════════════
# PRUEBAS ROJAS — RUTAS LEGACY (auditoría previa, confirmadas aquí con FX-03)
# ═══════════════════════════════════════════════════════════════════════

def test_red_interacciones_builder_cuenta_datos_como_contacto_unico():
    """RED — interacciones_builder.py usa solo es_valor_significativo(), no
    contacto_categoria. Un identificador DATOS/IP/dominio/URL/APN cuenta
    como 'contacto único' del día y puede aparecer en la tabla como si
    fuera un contacto interpersonal válido."""
    df = _fx03_p0b_df()
    html = construir_seccion_interacciones(df, dias=1, columnas_config={})
    # El HTML de interacciones no debería listar valores técnicos como contacto
    assert "80012345" not in html, "Identificador DATOS apareció como contacto en interacciones_builder"
    assert "192.168.1.15" not in html, "IPv4 apareció como contacto en interacciones_builder"
    assert "internet.claro.sv" not in html, "Dominio apareció como contacto en interacciones_builder"


def test_red_interacciones_builder_no_consolida_formatos_equivalentes():
    """RED — interacciones_builder agrupa por el string crudo strippeado
    (`_contacto`), sin `normalize_msisdn`/`contacto_limpio`. Los casos 2 y 3
    (mismo número +503, con y sin separadores) deberían contar como 1
    contacto único del día, pero hoy cuentan como 2."""
    df = _fx03_p0b_df()
    # Aislar solo los 2 registros de formatos equivalentes + antena/lat/long ya presentes en FX-03
    sub = df[df["contacto"].isin(["+50370011111", "503 7001-1111"])].copy()
    html = construir_seccion_interacciones(sub, dias=1, columnas_config={})
    import re
    m = re.search(r"Contactos únicos:</strong>\s*(\d+)", html)
    assert m is not None, "No se encontró el KPI 'Contactos únicos' en el HTML"
    assert int(m.group(1)) == 1, (
        f"Se esperaba 1 contacto único (mismo número, 2 formatos); "
        f"interacciones_builder reportó {m.group(1)}"
    )


def test_red_log_minimo_diverge_de_contactos_plausibles_del_html():
    """RED — write_minimal_filter_log calcula 'Contactos únicos' sobre
    'tel_contacto' crudo con un set de placeholders propio, sin
    contacto_categoria. El conteo de log_minimo.txt debería coincidir con
    el número de contactos telefonico_plausible únicos que muestra el HTML,
    pero usa una fuente y un criterio distintos."""
    df = _fx03_p0b_df().rename(columns={"contacto": "tel_contacto"})
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        out_path = os.path.join(d, "log_minimo.txt")
        write_minimal_filter_log(df, "FX-03", out_path)
        contenido = open(out_path, encoding="utf-8").read()

    # Contactos telefonico_plausible únicos reales según P0-B (casos 1,2,3,5,6,7,8; el 4 y el 9
    # dependen de los defectos ya cubiertos arriba, se excluyen de este cálculo de referencia)
    df_p0b = _fx03_p0b_df()
    esperado = df_p0b[df_p0b["contacto_categoria"] == "telefonico_plausible"]["contacto_limpio"].nunique()

    import re
    m = re.search(r"Contactos únicos: (\d+)", contenido)
    assert m is not None
    reportado = int(m.group(1))
    assert reportado == esperado, (
        f"log_minimo.txt reportó {reportado} contactos únicos (fuente: tel_contacto crudo); "
        f"el HTML/P0-B reporta {esperado} telefonico_plausible únicos — fuentes divergentes"
    )


def test_red_capabilities_declara_contactos_disponible_sin_plausibles():
    """RED — capabilities.py::_detectar_contactos usa `contacto_valido`
    (validez estructural 7-15 dígitos) en vez de `contacto_categoria`. Un
    dataset compuesto solo por identificadores DATOS numéricos (8-15
    dígitos, contacto_valido=True, contacto_categoria=tecnico_no_personal
    en el 100% de las filas) hoy declara la capacidad 'contactos' como
    disponible, aunque ningún registro sea un contacto interpersonal real."""
    df = pd.DataFrame({
        "contacto": ["80012345", "80099999", "80011111"],
        "interaccion": ["DATOS", "DATOS", "DATOS"],
        "fecha": ["05/08/2026"] * 3,
        "hora": ["08:00:00", "08:01:00", "08:02:00"],
    })
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert (df["contacto_categoria"] == "tecnico_no_personal").all()
    assert (df["contacto_valido"] == True).all()  # noqa: E712

    report = detectar_capacidades(df)
    cap = report.capacidad("contactos")
    assert cap.estado == "no_disponible", (
        f"capabilities declaró 'contactos'={cap.estado!r} usando solo identificadores "
        f"DATOS numéricos sin ningún telefonico_plausible"
    )


def test_red_gprs_pdp_wap_divergen_entre_qc_y_p0b():
    """RED — Tarea 6-G. qc_type_classifier reconoce GPRS/PDP/WAP/APN/NAV/
    BROWSE como DATOS; normalize_event_fields (P0-B) solo reconoce el
    término literal 'DATOS'. Un valor 'GPRS' es DATOS para el score de QC
    pero DESCONOCIDO para P0-B — divergencia de vocabulario documentada en
    docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §10."""
    terminos_datos_qc = ["GPRS", "PDP", "WAP", "NAV", "BROWSE"]
    for termino in terminos_datos_qc:
        qc_resultado = classify_single(termino)
        assert qc_resultado == "DATOS"

        df = pd.DataFrame({"interaccion": [termino]})
        df = normalize_event_fields(df, col_tipo="interaccion")
        p0b_resultado = df["tipo_evento_normalizado"].iloc[0]

        assert p0b_resultado == "DATOS", (
            f"'{termino}': qc_type_classifier={qc_resultado!r} pero "
            f"normalize_event_fields={p0b_resultado!r} — vocabularios divergentes"
        )


# ═══════════════════════════════════════════════════════════════════════
# TAREA 7 — NÚMEROS INTERNACIONALES: PRUEBAS DE CONTRATO
# ═══════════════════════════════════════════════════════════════════════

def test_intl_numero_con_mas_no_se_descarta():
    """Verde — Tarea 7.1. '+50255551234' (Guatemala, 11 dígitos) no se descarta."""
    df = pd.DataFrame({"contacto": ["+50255551234"], "interaccion": ["VOZ"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_categoria"].iloc[0] == "telefonico_plausible"


def test_intl_prefijo_00_normaliza_equivalente_a_mas():
    """Verde (por efecto colateral, no por diseño intencional) — Tarea 7.2.
    '0050255551234' y '+50255551234' terminan en el mismo contacto_limpio
    porque `_normalize_decimal_string` usa `Decimal()`, que descarta ceros
    a la izquierda. Ver docs/P0B_CONTRATO_CLASIFICACION_CONTACTOS.md §8.1
    para la advertencia sobre la fragilidad de este comportamiento."""
    limpio_mas = normalize_msisdn("+50255551234")
    limpio_00 = normalize_msisdn("0050255551234")
    assert limpio_mas == limpio_00 == "50255551234"


def test_intl_numero_10_a_15_digitos_no_es_longitud_excesiva():
    """Verde — Tarea 7.3. Un internacional plausible de 11 dígitos no cae
    en longitud_excesiva (ese motivo solo aplica a más de 15 dígitos)."""
    df = pd.DataFrame({"contacto": ["+50255551234"], "interaccion": ["VOZ"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_motivo"].iloc[0] != "longitud_excesiva"


def test_intl_mas_de_15_digitos_se_mantiene_indeterminado():
    """Verde — Tarea 7.4. 16 dígitos supera el máximo E.164 (15) y se
    mantiene indeterminado con motivo longitud_excesiva."""
    df = pd.DataFrame({"contacto": ["1234567890123456"], "interaccion": ["VOZ"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_categoria"].iloc[0] == "indeterminado"
    assert df["contacto_motivo"].iloc[0] == "longitud_excesiva"


def test_red_intl_imsi_like_no_se_convierte_automaticamente():
    """RED — Tarea 7.5, mismo defecto que test_red_imsi_like_no_asciende_automaticamente_a_plausible
    pero aislado sin el resto de FX-03 (ver ese test para la causa completa)."""
    df = pd.DataFrame({"contacto": ["502215001234567"], "interaccion": ["VOZ"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_categoria"].iloc[0] == "indeterminado", (
        "Un bloque de 15 dígitos con forma de IMSI ascendió a telefonico_plausible "
        "sin evidencia adicional de formato — el sistema no distingue MSISDN de IMSI"
    )


def test_intl_datos_prevalece_sobre_apariencia_internacional():
    """Verde — Tarea 7.6, ya cubierto arriba como test_datos_prevalece_aunque_valor_parezca_internacional;
    se repite aquí bajo el nombre de la sección de contrato internacional por trazabilidad de la Tarea 7."""
    df = pd.DataFrame({"contacto": ["+50255551234"], "interaccion": ["DATOS"]})
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert df["contacto_categoria"].iloc[0] == "tecnico_no_personal"
    assert df["contacto_motivo"].iloc[0] == "tipo_datos"


def test_intl_valor_original_se_conserva():
    """Verde — Tarea 7.7. El valor original de un internacional se conserva
    sin alterar en la columna 'contacto' (no se sobrescribe in-place)."""
    df = pd.DataFrame({"contacto": ["+50255551234"], "interaccion": ["VOZ"]})
    original = df["contacto"].copy()
    df = normalize_event_fields(df, col_tipo="interaccion")
    df = normalize_contact_fields(df)
    assert (df["contacto"] == original).all()
