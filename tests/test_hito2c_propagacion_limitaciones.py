"""Hito 2C FX-02 — Propagación final de DuracionEstado y sección Limitaciones.

Cubre:
  1. assembler usa un único DuracionEstado y lo pasa a consumidores.
  2. Limitaciones declara contacto ausente.
  3. Limitaciones declara tipo ausente.
  4. Limitaciones declara duración ambigua.
  5. Limitaciones declara duración ausente.
  6. Limitaciones no duplica mensajes.
  11. IngestionResult.duracion_estado llega hasta generar_informe_html()
      (vía produce_case_outputs / generar_kml).
  12. Compatibilidad: llamadas antiguas sin el parámetro siguen funcionando.

No usa snapshots completos: cada prueba inspecciona solo el fragmento HTML
relevante (sección "Limitaciones del análisis") o intercepta llamadas con
monkeypatch/spies.
"""
import re
from pathlib import Path

import pandas as pd
import pytest

from tz_core.bitacora_normalization import DuracionEstado


def _extraer_limitaciones(html: str) -> str:
    m = re.search(r'<section id="limitaciones-analisis">(.*?)</section>', html, re.S)
    assert m, "No se encontró la sección 'Limitaciones del análisis' en el HTML."
    return m.group(1)


def _df_baseline() -> pd.DataFrame:
    """Bitácora con contacto, tipo de evento y duración (HH:MM:SS) disponibles."""
    return pd.DataFrame(
        {
            "fecha": ["01/01/2026", "02/01/2026"],
            "hora": ["08:00:00", "09:00:00"],
            "antena": ["ANT-A", "ANT-B"],
            "lat": [13.6929, 13.7000],
            "long": [-89.2182, -89.2100],
            "contacto": ["70011111", "70022222"],
            "interaccion": ["LLAMADA ENTRANTE", "SMS SALIENTE"],
            "duracion": ["00:01:00", "00:02:00"],
        }
    )


# ── 2/3/4/5: Limitaciones declara cada campo analítico ausente/ambiguo ─────

def test_limitaciones_declara_contacto_ausente(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline().drop(columns=["contacto"])
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Contacto no disponible" in limitaciones
    assert "Tipo de evento no disponible" not in limitaciones
    assert "unidad de duración no confirmada" not in limitaciones
    assert "Duración no disponible" not in limitaciones


def test_limitaciones_declara_tipo_ausente(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline().drop(columns=["interaccion"])
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Tipo de evento no disponible" in limitaciones
    assert "Contacto no disponible" not in limitaciones
    assert "unidad de duración no confirmada" not in limitaciones
    assert "Duración no disponible" not in limitaciones


def test_limitaciones_declara_duracion_ambigua(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline()
    df["duracion"] = [30, 5400]  # enteros de unidad ambigua
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "unidad de duración no confirmada" in limitaciones
    assert "Contacto no disponible" not in limitaciones
    assert "Tipo de evento no disponible" not in limitaciones
    assert "Duración no disponible" not in limitaciones


def test_limitaciones_declara_duracion_ausente(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline().drop(columns=["duracion"])
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert "Duración no disponible" in limitaciones
    assert "Contacto no disponible" not in limitaciones
    assert "Tipo de evento no disponible" not in limitaciones
    assert "unidad de duración no confirmada" not in limitaciones


def test_limitaciones_no_duplica_mensajes(tmp_path):
    """Con los tres campos ausentes a la vez, cada ítem aparece una sola vez."""
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline().drop(columns=["contacto", "interaccion"])
    df["duracion"] = [30, 5400]
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    limitaciones = _extraer_limitaciones(Path(html_path).read_text(encoding="utf-8"))

    assert limitaciones.count("Contacto no disponible") == 1
    assert limitaciones.count("Tipo de evento no disponible") == 1
    assert limitaciones.count("unidad de duración no confirmada") == 1


# ── 1: assembler calcula DuracionEstado una sola vez y lo comparte ─────────

def test_assembler_calcula_duracion_estado_una_sola_vez(tmp_path, monkeypatch):
    import tz_core.html.assembler as assembler_mod

    llamadas = []
    original = assembler_mod.clasificar_confiabilidad_duracion

    def spy(df, *a, **kw):
        llamadas.append(1)
        return original(df, *a, **kw)

    monkeypatch.setattr(assembler_mod, "clasificar_confiabilidad_duracion", spy)

    df = _df_baseline()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    assembler_mod.generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )

    assert len(llamadas) == 1, (
        "generar_informe_html debe clasificar la duración una sola vez y "
        "compartir el mismo DuracionEstado con todos sus consumidores."
    )


def test_assembler_propaga_mismo_objeto_a_consumidores(tmp_path, monkeypatch):
    import tz_core.html.assembler as assembler_mod

    capturado = {}

    def fake_top_contacts(df, config, overrides, *, duracion_estado=None):
        capturado["top_contacts"] = duracion_estado
        return "", "", 10

    def fake_interacciones(df, dias, cols, *, config=None, logger=None, duracion_estado=None):
        capturado["interacciones"] = duracion_estado
        return '<section id="interacciones-recientes"></section>'

    def fake_todos(df, cols, *, duracion_estado=None):
        capturado["todos_contactos"] = duracion_estado
        return '<section id="todos-contactos"></section>'

    monkeypatch.setattr(assembler_mod, "build_top_contacts_sections", fake_top_contacts)
    monkeypatch.setattr(assembler_mod, "construir_seccion_interacciones", fake_interacciones)
    monkeypatch.setattr(assembler_mod, "_construir_seccion_todos_contactos", fake_todos)

    df = _df_baseline()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    assembler_mod.generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )

    assert capturado["top_contacts"] is not None
    assert capturado["top_contacts"] is capturado["interacciones"]
    assert capturado["top_contacts"] is capturado["todos_contactos"]


# ── 11: IngestionResult.duracion_estado llega hasta generar_informe_html() ─

def test_produce_case_outputs_propaga_duracion_estado_a_todos_los_consumidores(tmp_path):
    from tz_core.output_pipeline import produce_case_outputs

    estado = DuracionEstado(
        estado="segura", unidad="segundos",
        columna="duracion", columna_original="duracion", motivo="test",
    )
    capturado = {}

    def fake_generar_html(**kwargs):
        capturado["html"] = kwargs.get("duracion_estado")
        return str(tmp_path / "out.html")

    def fake_interactions(df, dias, cols, *, config=None, logger=None, duracion_estado=None):
        capturado["interacciones"] = duracion_estado
        return "inter"

    def fake_contacts(df, cols, *, duracion_estado=None):
        capturado["contactos"] = duracion_estado
        return "contacts"

    df = pd.DataFrame({"antena": ["A"], "lat": [13.7], "long": [-88.9]})

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
        build_interactions_section=fake_interactions,
        build_contacts_section=fake_contacts,
        generar_html_fn=fake_generar_html,
        relocate_kmz_fn=lambda **kw: None,
        write_hashes_fn=lambda *a, **kw: None,
        summarize_fn=lambda **kw: None,
        duracion_estado=estado,
    )

    assert capturado["html"] is estado
    assert capturado["interacciones"] is estado
    assert capturado["contactos"] is estado


def test_generar_kml_no_recalcula_duracion_estado_si_se_provee(tmp_path, monkeypatch):
    import tz_core.kml_generator as kml_mod
    from tz_core.bitacora_normalization import clasificar_confiabilidad_duracion as real_clasificar

    df = pd.DataFrame(
        {"antena": ["A"], "lat": [13.7], "long": [-88.9], "duracion": ["00:01:00"]}
    )
    estado = real_clasificar(df)

    llamadas = []

    def spy(*a, **kw):
        llamadas.append(1)
        return real_clasificar(*a, **kw)

    monkeypatch.setattr(kml_mod, "clasificar_confiabilidad_duracion", spy)

    kml_mod.generar_kml(
        df, str(tmp_path / "out.kml"), config={}, flat=True, duracion_estado=estado,
    )

    assert llamadas == [], (
        "generar_kml no debe reclasificar la duración cuando ya recibe un "
        "DuracionEstado resuelto por el pipeline de ingesta."
    )


# ── 12: compatibilidad — llamadas antiguas sin el parámetro siguen funcionando ─

def test_generar_informe_html_compatible_sin_duracion_estado(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_baseline()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df, archivo_kml=str(kml_path), carpeta_salida=str(tmp_path),
        nombre_salida="caso", hoja=None, nombre_bitacora=None, config={},
    )
    assert html_path and Path(html_path).exists()


def test_generar_kml_compatible_sin_duracion_estado(tmp_path):
    from tz_core.kml_generator import generar_kml

    df = pd.DataFrame(
        {"antena": ["A"], "lat": [13.7], "long": [-88.9], "duracion": ["00:01:00"]}
    )
    ruta, descartadas = generar_kml(df, str(tmp_path / "out.kml"), config={}, flat=True)
    assert ruta
    assert descartadas == 0


def test_produce_case_outputs_compatible_sin_duracion_estado(tmp_path):
    from tz_core.output_pipeline import produce_case_outputs

    df = pd.DataFrame({"antena": ["A"], "lat": [13.7], "long": [-88.9]})

    result = produce_case_outputs(
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
        build_contacts_section=lambda df, cols: "contacts",
        generar_html_fn=lambda **kw: str(tmp_path / "out.html"),
        relocate_kmz_fn=lambda **kw: None,
        write_hashes_fn=lambda *a, **kw: None,
        summarize_fn=lambda **kw: None,
    )
    assert result.interactions_html == "inter"
    assert result.contacts_html == "contacts"
