"""HITO 4 — Propagación de CapabilitiesReport y extensión de Limitaciones.

Cubre:
  8.  CapabilitiesReport llega hasta generar_informe_html (vía
      produce_case_outputs) y sin proveerlo, generar_informe_html sigue
      funcionando (lo calcula internamente).
  9.  Limitaciones declara identificación ausente.
  10. Limitaciones declara cronología ausente.
  11. Limitaciones declara hora ausente (cronología parcial).
  12. Limitaciones declara antena nominal ausente.
  13. Limitaciones declara geoespacial (KML/heatmap) no disponible.
  14. Limitaciones declara orientación ausente.
  15. Ninguno de los mensajes nuevos duplica los ya existentes (contacto/
      tipo de evento/duración), ni se repite a sí mismo.

No usa golden/snapshots completos: cada prueba inspecciona solo el
fragmento HTML de la sección "Limitaciones del análisis".
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from tz_core.capabilities import detectar_capacidades


def _extraer_limitaciones(html: str) -> str:
    m = re.search(r'<section id="limitaciones-analisis">(.*?)</section>', html, re.S)
    assert m, "No se encontró la sección 'Limitaciones del análisis' en el HTML."
    return m.group(1)


def _df_completa() -> pd.DataFrame:
    """Bitácora con todos los campos analíticos disponibles."""
    return pd.DataFrame(
        {
            "fecha": ["01/01/2026", "02/01/2026"],
            "hora": ["08:00:00", "09:00:00"],
            "tel": ["70011111", "70011111"],
            "imei": ["352005090177850", "352005090177850"],
            "antena": ["ANT-A", "ANT-B"],
            "lat": [13.6929, 13.7000],
            "long": [-89.2182, -89.2100],
            "azimut": [45, 120],
            "contacto": ["70022222", "70033333"],
            "interaccion": ["LLAMADA ENTRANTE", "SMS SALIENTE"],
            "duracion": ["00:01:00", "00:02:00"],
        }
    )


def _generar(df: pd.DataFrame, tmp_path, **kwargs) -> str:
    from tz_core.html.assembler import generar_informe_html

    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")
    return generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
        **kwargs,
    )


# ── 9-14: Limitaciones declara cada capacidad ausente/parcial ─────────────

def test_limitaciones_declara_identificacion_ausente(tmp_path):
    df = _df_completa().drop(columns=["tel", "imei"])
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Identificación no disponible" in limitaciones
    assert "número telefónico o IMEI utilizable" in limitaciones


def test_limitaciones_declara_cronologia_ausente(tmp_path):
    df = _df_completa().drop(columns=["fecha"])
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Cronología no disponible" in limitaciones
    assert "filtros temporales no están" in limitaciones


def test_limitaciones_declara_hora_ausente(tmp_path):
    """Fecha disponible pero hora sin valores utilizables → cronología parcial.

    Se deja la columna 'hora' presente pero vacía (en vez de eliminarla) para
    reflejar lo que produce el pipeline real (normalize_temporal_fields
    garantiza la columna) y para no ejercitar un bug preexistente y no
    relacionado con Hito 4 en tz_core.html.antennas.build_antennas_table,
    que asume 'hora' presente como columna cuando 'antena' también lo está.
    """
    df = _df_completa()
    df["hora"] = ""
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Hora no disponible" in limitaciones
    assert "Cronología no disponible" not in limitaciones


def test_limitaciones_declara_antena_nominal_ausente(tmp_path):
    df = _df_completa().drop(columns=["antena"])
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Antena nominal no disponible" in limitaciones


def test_limitaciones_declara_geoespacial_no_disponible(tmp_path):
    df = _df_completa().drop(columns=["lat", "long"])
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "KML/heatmap no disponibles" in limitaciones
    assert "análisis geoespacial" in limitaciones


def test_limitaciones_declara_orientacion_ausente(tmp_path):
    df = _df_completa().drop(columns=["azimut"])
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Orientación no disponible" in limitaciones
    assert "sectores y" in limitaciones


def test_limitaciones_bitacora_completa_no_declara_ausencias(tmp_path):
    """Control: con todo disponible, ninguno de los mensajes nuevos aparece."""
    df = _df_completa()
    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    for frase in (
        "Identificación no disponible",
        "Cronología no disponible",
        "Hora no disponible",
        "Antena nominal no disponible",
        "KML/heatmap no disponibles",
        "Orientación no disponible",
    ):
        assert frase not in limitaciones


# ── 15: sin duplicaciones ──────────────────────────────────────────────────

def test_limitaciones_no_duplica_mensajes_nuevos_ni_existentes(tmp_path):
    """Con múltiples ausencias simultáneas (capacidades + contacto/tipo/
    duración), cada mensaje aparece una única vez y no se contradicen."""
    df = _df_completa().drop(
        columns=["tel", "imei", "fecha", "antena", "lat", "long", "azimut",
                 "contacto", "interaccion"]
    )
    df["duracion"] = [30, 5400]  # unidad ambigua

    html_path = _generar(df, tmp_path)
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    for frase in (
        "Identificación no disponible",
        "Cronología no disponible",
        "Antena nominal no disponible",
        "KML/heatmap no disponibles",
        "Orientación no disponible",
        "Contacto no disponible",
        "Tipo de evento no disponible",
        "unidad de duración no confirmada",
    ):
        assert limitaciones.count(frase) == 1, f"'{frase}' debe aparecer exactamente una vez"

    # Hora ausente no debe aparecer: ya está cubierto por "Cronología no disponible"
    # (fecha también ausente en este escenario).
    assert "Hora no disponible" not in limitaciones


# ── 8: CapabilitiesReport llega hasta generar_informe_html ────────────────

def test_produce_case_outputs_propaga_capabilities_report(tmp_path):
    from tz_core.output_pipeline import produce_case_outputs

    df = _df_completa()
    reporte = detectar_capacidades(df)
    capturado = {}

    def fake_generar_html(**kwargs):
        capturado["html"] = kwargs.get("capabilities_report")
        return str(tmp_path / "out.html")

    produce_case_outputs(
        df=df,
        config={},
        nombre_salida="caso",
        archivo_kml=str(tmp_path / "caso.kml"),
        carpeta_base=str(tmp_path),
        carpeta_salida=str(tmp_path),
        archivo_entrada=None,
        hoja=None,
        error_report_path=None,
        discarded_coords=0,
        build_interactions_section=lambda df, dias, cols, **kw: "inter",
        build_contacts_section=lambda df, cols, **kw: "contacts",
        generar_html_fn=fake_generar_html,
        relocate_kmz_fn=lambda **kw: None,
        write_hashes_fn=lambda *a, **kw: None,
        summarize_fn=lambda **kw: None,
        capabilities_report=reporte,
    )

    assert capturado["html"] is reporte


def test_run_outputs_flow_propaga_capabilities_report(tmp_path):
    from tz_core.output_runner import run_outputs_flow

    df = _df_completa()
    reporte = detectar_capacidades(df)
    capturado = {}

    def fake_produce(**kwargs):
        capturado["capabilities_report"] = kwargs.get("capabilities_report")
        return {"html": None, "kmz": None, "hashes": None}

    run_outputs_flow(
        df=df,
        config={},
        nombre_salida="caso",
        archivo_kml=str(tmp_path / "caso.kml"),
        carpeta_base=str(tmp_path),
        carpeta_salida=str(tmp_path),
        archivo_entrada=None,
        hoja=None,
        archivo_errores=None,
        desc_coords=0,
        build_interactions_section=lambda *a, **kw: "inter",
        build_contacts_section=lambda *a, **kw: "contacts",
        generar_html_fn=lambda **kw: None,
        relocate_kmz_fn=lambda **kw: None,
        write_hashes_fn=lambda *a, **kw: None,
        produce_fn=fake_produce,
        summarize_fn=lambda **kw: None,
        logger=lambda _msg: None,
        output_fn=lambda _msg: None,
        path_exists=lambda _p: False,
        cwd_fn=lambda: str(tmp_path),
        log_file_path=None,
        set_interactions_section=lambda _html: None,
        set_contacts_section=lambda _html: None,
        capabilities_report=reporte,
    )

    assert capturado["capabilities_report"] is reporte


def test_generar_informe_html_compatible_sin_capabilities_report(tmp_path):
    """Compatibilidad: sin proveer capabilities_report, se calcula internamente
    y el HTML se genera igual (no rompe llamadores existentes)."""
    df = _df_completa().drop(columns=["tel", "imei"])
    html_path = _generar(df, tmp_path)

    assert html_path and Path(html_path).exists()
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))
    assert "Identificación no disponible" in limitaciones


# ── Bloque "Capacidades analíticas" retirado (Pulido UX v1.1) ─────────────
# La tarjeta compacta duplicaba información ya presente en "Limitaciones del
# análisis"; se eliminó sin sustituto para no repetir contenido. Las tres
# pruebas siguientes reemplazan (no simplemente eliminan) la cobertura previa
# de la tarjeta: (1) el bloque ya no aparece bajo el Resumen Ejecutivo,
# (2) "Limitaciones del análisis" sigue presente, y (3) capabilities_report
# sigue gobernando su contenido (la desconexión de la tarjeta no desconectó
# el pipeline de detección de capacidades).

def test_resumen_capacidades_ya_no_aparece_bajo_resumen_ejecutivo(tmp_path):
    df = _df_completa().drop(columns=["tel", "imei"])
    html_path = _generar(df, tmp_path)
    html = Path(html_path).read_text(encoding="utf-8")

    assert 'id="resumen-capacidades"' not in html
    assert "Capacidades analíticas:" not in html

    # El bloque no debe reaparecer en ningún punto del documento, no solo
    # inmediatamente bajo el resumen ejecutivo.
    assert html.count('id="resumen-capacidades"') == 0


def test_limitaciones_del_analisis_sigue_presente_tras_retirar_capacidades(tmp_path):
    df = _df_completa().drop(columns=["tel", "imei"])
    html_path = _generar(df, tmp_path)
    html = Path(html_path).read_text(encoding="utf-8")

    assert 'id="limitaciones-analisis"' in html
    assert "<h2>Limitaciones del análisis</h2>" in html
    limitaciones = _extraer_limitaciones(html)
    assert "número telefónico o IMEI utilizable" in limitaciones


def test_capabilities_report_sigue_gobernando_limitaciones_sin_tarjeta(tmp_path):
    """capabilities_report debe seguir siendo la única fuente de verdad para
    "Limitaciones del análisis": la tarjeta compacta que antes leía el mismo
    objeto ya no existe, pero el objeto sigue propagándose hasta el HTML."""
    from tz_core.capabilities import detectar_capacidades

    df = _df_completa()
    df["hora"] = ""  # antenas/cronología parcial: hora ausente, fecha presente
    reporte = detectar_capacidades(df)
    assert reporte.capacidad("cronologia").estado == "parcial"

    html_path = _generar(df, tmp_path, capabilities_report=reporte)
    html = Path(html_path).read_text(encoding="utf-8")

    assert 'id="resumen-capacidades"' not in html
    limitaciones = _extraer_limitaciones(html)
    assert "Hora no disponible" in limitaciones


def test_generar_informe_html_usa_capabilities_report_provisto(tmp_path, monkeypatch):
    """Cuando se provee capabilities_report, no se recalcula (mismo objeto)."""
    import tz_core.html.assembler as assembler_mod

    df = _df_completa()
    reporte = detectar_capacidades(df)

    llamadas = []
    original = assembler_mod.detectar_capacidades

    def spy(*a, **kw):
        llamadas.append(1)
        return original(*a, **kw)

    monkeypatch.setattr(assembler_mod, "detectar_capacidades", spy)

    _generar(df, tmp_path, capabilities_report=reporte)

    assert llamadas == [], (
        "generar_informe_html no debe recalcular capacidades cuando ya "
        "recibe un CapabilitiesReport resuelto por el pipeline de ingesta."
    )
