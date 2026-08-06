"""Pulido UX pre-empaquetado — 6 mejoras de claridad, redacción y consistencia visual.

Cubre las verificaciones de la Tarea 8:
1. Terminología externa de contactos (sin "plausible"/"plausibles" visible).
2. Resumen ejecutivo (nueva estructura narrativa).
3. Indicadores (tarjeta "Celdas (CID) únicas" retirada).
4. Antenas con mayor número de activaciones (título y nota nuevos).
5. Contactos con más comunicación (nota única, títulos "Ranking por...").
6. Formato de fechas en análisis de perfiles (DD/MM/AAAA en vez de ISO).

No modifica categorías internas (``contacto_categoria``, ``telefonico_plausible``)
ni contratos analíticos: solo verifica presentación externa.
"""
import re

import pandas as pd

from tz_core.bitacora_normalization import DuracionEstado
from tz_core.html import assembler as asm
from tz_core.html.antennas import build_top_antennas_section
from tz_core.html.contacts import build_top_contacts_sections, interpretar_contactos
from tz_core.html.kpi import generate_kpi_section


def _duracion_segura():
    return DuracionEstado(
        estado="segura", unidad="segundos", columna="duracion",
        columna_original="duracion", motivo="test",
    )


def _duracion_ambigua():
    return DuracionEstado(
        estado="ambigua", unidad="desconocida", columna="duracion",
        columna_original="duracion", motivo="test",
    )


# ───────────────────────────────────────────────────────────────────────────
# Mejora 1 — Terminología externa de contactos
# ───────────────────────────────────────────────────────────────────────────

def _df_p0b_basica():
    return pd.DataFrame(
        {
            "fecha": ["01/03/2024", "02/03/2024", "03/03/2024"],
            "hora": ["08:00:00", "09:00:00", "10:00:00"],
            "tel": ["70011111"] * 3,
            "contacto": ["70022222", "70022222", "70033333"],
            "duracion": [60, 120, 30],
            "antena": ["ANT-A", "ANT-A", "ANT-B"],
            "lat": [13.7, 13.7, 13.71],
            "long": [-89.2, -89.2, -89.21],
            "contacto_categoria": [
                "telefonico_plausible", "telefonico_plausible", "telefonico_plausible",
            ],
            "contacto_limpio": ["70022222", "70022222", "70033333"],
        }
    )


def test_html_visible_no_usa_palabra_plausible(tmp_path):
    df = _df_p0b_basica()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = asm.generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="term", hoja=None, nombre_bitacora=None, config={},
    )
    contenido = html_path and open(html_path, encoding="utf-8").read()
    assert contenido, "No se generó el informe HTML."
    assert "plausible" not in contenido.lower(), (
        "El HTML visible no debe usar la palabra 'plausible'/'plausibles'."
    )


def test_categoria_interna_telefonico_plausible_intacta():
    df = _df_p0b_basica()
    # La categoría interna debe permanecer sin cambios (contrato P0-B).
    assert set(df["contacto_categoria"].unique()) == {"telefonico_plausible"}
    cnt_html, dur_html, _ = build_top_contacts_sections(df, config={}, duracion_estado=_duracion_segura())
    # La tabla renderizada usa el número limpio, nunca la palabra "plausible".
    assert "plausible" not in cnt_html.lower()
    assert "plausible" not in dur_html.lower()


# ───────────────────────────────────────────────────────────────────────────
# Mejora 2 — Resumen ejecutivo
# ───────────────────────────────────────────────────────────────────────────

def test_resumen_numero_periodo_total():
    html = asm._construir_resumen_ejecutivo(
        total=25, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None,
        rango_str="01/03/2024 08:00 — 05/03/2024 18:00",
        tel_val="70011111",
    )
    assert "número 70011111" in html
    assert "del 01/03/2024 al 05/03/2024" in html
    assert "<strong>25</strong> interacciones" in html
    assert "dispositivo registró" not in html


def test_resumen_solo_imei():
    html = asm._construir_resumen_ejecutivo(
        total=8, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None,
        rango_str="Sin datos", imei_val="356938035643809",
    )
    assert "IMEI 356938035643809" in html
    assert "terminal telefónica identificada" in html


def test_resumen_sin_identificador():
    html = asm._construir_resumen_ejecutivo(
        total=3, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None, rango_str="Sin datos",
    )
    assert "La bitácora analizada" in html
    assert "número" not in html
    assert "IMEI" not in html


def test_resumen_mismo_contacto_top_frecuencia_y_duracion():
    metricas = {
        "70022222": {"total_interacciones": 10, "total_duracion_seg": 3661.0},
        "70033333": {"total_interacciones": 4, "total_duracion_seg": 60.0},
    }
    html = asm._construir_resumen_ejecutivo(
        total=14, orden=["70022222", "70033333"], metricas=metricas,
        df=pd.DataFrame({"antena": ["A"]}), top_antena=None, _log=lambda m: None,
        duracion_estado=_duracion_segura(),
    )
    assert "El contacto con mayor frecuencia fue <strong>70022222</strong>, con 10 registros." in html
    assert "Este mismo contacto acumuló la mayor duración de comunicación, con 01:01:01." in html


def test_resumen_contactos_distintos_en_frecuencia_y_duracion():
    metricas = {
        "70022222": {"total_interacciones": 10, "total_duracion_seg": 30.0},
        "70033333": {"total_interacciones": 2, "total_duracion_seg": 5000.0},
    }
    html = asm._construir_resumen_ejecutivo(
        total=12, orden=["70022222", "70033333"], metricas=metricas,
        df=pd.DataFrame({"antena": ["A"]}), top_antena=None, _log=lambda m: None,
        duracion_estado=_duracion_segura(),
    )
    assert "El contacto con mayor frecuencia fue <strong>70022222</strong>, con 10 registros, mientras que <strong>70033333</strong> acumuló la mayor duración de comunicación" in html


def test_resumen_sin_contactos_no_dice_no_disponible():
    html = asm._construir_resumen_ejecutivo(
        total=6, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None,
    )
    assert "contacto" not in html.lower()
    assert "no disponible" not in html.lower()


def test_resumen_sin_duracion_confirmada_solo_frecuencia():
    metricas = {"70022222": {"total_interacciones": 5, "total_duracion_seg": 999.0}}
    html = asm._construir_resumen_ejecutivo(
        total=5, orden=["70022222"], metricas=metricas,
        df=pd.DataFrame({"antena": ["A"]}), top_antena=None, _log=lambda m: None,
        duracion_estado=_duracion_ambigua(),
    )
    assert "El contacto con mayor frecuencia fue <strong>70022222</strong>, con 5 registros." in html
    assert "duración" not in html.lower()


def test_resumen_sin_antena_omite_oracion_geografica():
    html = asm._construir_resumen_ejecutivo(
        total=5, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena="—", _log=lambda m: None,
    )
    assert "activaciones" not in html.lower()
    assert "antena" not in html.lower()


def test_resumen_sitio_inferido():
    df = pd.DataFrame(
        {
            "antena_analitica": ["SITIO_13.700000_-89.200000"] * 2,
            "sitio_inferido": [True, True],
        }
    )
    html = asm._construir_resumen_ejecutivo(
        total=5, orden=[], metricas={}, df=df,
        top_antena="SITIO_13.700000_-89.200000", _log=lambda m: None,
    )
    assert "El sitio inferido con mayor número de activaciones fue" in html
    assert "La antena con mayor número de activaciones" not in html


def test_resumen_sin_periodo_no_inventa_fechas():
    html = asm._construir_resumen_ejecutivo(
        total=7, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None, _log=lambda m: None, rango_str="Sin datos", tel_val="70011111",
    )
    assert "período" not in html.lower()
    assert re.search(r"\d{2}/\d{2}/\d{4}", html) is None


def test_resumen_no_incluye_franja_horaria():
    html = asm._construir_resumen_ejecutivo(
        total=5, orden=[], metricas={}, df=pd.DataFrame({"antena": ["A"], "hora": ["08:00:00"]}),
        top_antena=None, _log=lambda m: None,
    )
    assert "franja" not in html.lower()
    assert "concentró" not in html.lower()


# ───────────────────────────────────────────────────────────────────────────
# Mejora 3 — Indicadores (tarjeta CID retirada)
# ───────────────────────────────────────────────────────────────────────────

def test_indicadores_sin_tarjeta_cid():
    html = generate_kpi_section(
        total=100, coord_validas=90, coord_invalidas=10, ant_uniq=5,
        cel_uniq=12, cel_label="Celdas (CID) únicas", top_antena="ANT-A",
        top_count=40, top_pct=44.4,
    )
    assert "Celdas (CID) únicas" not in html
    assert "Registros totales" in html
    assert "Con coordenadas válidas" in html
    assert "Antenas únicas" in html
    assert "Top antena" in html


# ───────────────────────────────────────────────────────────────────────────
# Mejora 4 — Antenas con mayor número de activaciones
# ───────────────────────────────────────────────────────────────────────────

def _df_antenas():
    return pd.DataFrame(
        {
            "antena": ["ANT-A", "ANT-A", "ANT-B", "ANT-A"],
            "lat": [13.70, 13.70, 13.71, 13.70],
            "long": [-89.20, -89.20, -89.21, -89.20],
            "azimut": [45, 45, 90, 45],
        }
    )


def test_antenas_titulo_nuevo():
    html = build_top_antennas_section(_df_antenas(), config={}, overrides=None)
    assert "Antenas con mayor número de activaciones (Top 3)" in html
    assert "más activadas" not in html
    assert "top list" not in html.lower()


def test_antenas_nota_menciona_mapa_y_google_maps():
    html = build_top_antennas_section(_df_antenas(), config={}, overrides=None)
    assert "mapa incorporado" in html
    assert "Google Maps" in html


def test_antenas_variante_sitio_inferido():
    df = _df_antenas().rename(columns={"antena": "antena_analitica"})
    df["sitio_inferido"] = [True, True, True, True]
    html = build_top_antennas_section(df, config={}, overrides=None)
    assert "Antenas/Sitios con mayor número de activaciones" in html
    assert "antenas o sitios con mayor número de activaciones" in html


# ───────────────────────────────────────────────────────────────────────────
# Mejora 5 — Contactos con más comunicación
# ───────────────────────────────────────────────────────────────────────────

def test_rankings_una_sola_nota_principal(tmp_path):
    df = _df_p0b_basica()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")
    html_path = asm.generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="rank", hoja=None, nombre_bitacora=None, config={},
    )
    contenido = open(html_path, encoding="utf-8").read()
    assert contenido.count("Ambos rankings incluyen únicamente contactos válidos") == 1
    assert "Ranking por número de interacciones" in contenido
    assert "Ranking por duración acumulada" in contenido
    assert "Top List" not in contenido


def test_rankings_sin_nota_interna_en_primera_tabla():
    df = _df_p0b_basica()
    cnt_html, dur_html, _ = build_top_contacts_sections(df, config={}, duracion_estado=_duracion_segura())
    assert "El ranking considera únicamente números con formato telefónico" not in cnt_html
    assert "El ranking considera únicamente números con formato telefónico" not in dur_html


# ───────────────────────────────────────────────────────────────────────────
# Mejora 6 — Formato de fechas en análisis de perfiles
# ───────────────────────────────────────────────────────────────────────────

def test_fecha_iso_se_muestra_ddmmaaaa():
    metricas = {
        "70022222": {
            "total_interacciones": 3, "total_duracion_seg": 120.0,
            "promedio_duracion_seg": 40.0, "dias_activos": 1,
            "primer_contacto": "2024-03-15", "ultimo_contacto": "2024-03-15",
            "duracion_confiable": True,
        }
    }
    resultado = interpretar_contactos(
        metricas, total_interacciones=3, total_duracion=120.0,
        duracion_estado=_duracion_segura(),
    )
    narrativa = resultado["70022222"]["narrativa"]
    assert "15/03/2024" in narrativa
    assert "2024-03-15" not in narrativa


def test_fecha_ausente_se_omite_sin_nat_ni_nan():
    metricas = {
        "70022222": {
            "total_interacciones": 3, "total_duracion_seg": 120.0,
            "promedio_duracion_seg": 40.0, "dias_activos": 6,
            "primer_contacto": None, "ultimo_contacto": None,
            "duracion_confiable": True,
        }
    }
    resultado = interpretar_contactos(
        metricas, total_interacciones=3, total_duracion=120.0,
        duracion_estado=_duracion_segura(),
    )
    narrativa = resultado["70022222"]["narrativa"]
    assert "NaT" not in narrativa
    assert "nan" not in narrativa.lower()
    assert "Última interacción registrada" not in narrativa
