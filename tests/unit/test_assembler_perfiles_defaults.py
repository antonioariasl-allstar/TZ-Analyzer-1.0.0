"""
H2 — Blindaje del análisis de perfiles de contactos en generar_informe_html.

Verifica que una excepción interna en calcular_metricas_contactos o
interpretar_contactos no produce NameError/UnboundLocalError, que el
informe HTML se completa igualmente, y que el resumen ejecutivo puede
construirse con los defaults seguros (_metricas={}, _orden=[]).
"""
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tz_core.html import assembler as asm


def _df_con_contactos():
    return pd.DataFrame(
        {
            "fecha": ["01/01/2020"],
            "hora": ["00:00:00"],
            "antena": ["A"],
            "lat": [13.7],
            "long": [-88.9],
            "contacto": ["123"],
            "duracion": [30],
        }
    )


def test_excepcion_en_calcular_metricas_contactos_no_rompe_informe(tmp_path):
    df = _df_con_contactos()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    with patch.object(
        asm, "calcular_metricas_contactos", side_effect=RuntimeError("boom-metricas")
    ):
        html_path = asm.generar_informe_html(
            df=df,
            archivo_kml=str(kml_path),
            carpeta_salida=str(tmp_path),
            nombre_salida="casoA",
            hoja=None,
            nombre_bitacora=None,
            config={},
        )

    contenido = Path(html_path).read_text(encoding="utf-8")
    assert Path(html_path).exists()
    assert "resumen-ejecutivo" in contenido
    # El análisis de perfiles no se genera si la métrica falló, pero el resto del informe sí.
    assert "Análisis de perfiles de comunicación" not in contenido


def test_excepcion_en_interpretar_contactos_no_rompe_informe(tmp_path):
    df = _df_con_contactos()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    with patch.object(
        asm, "interpretar_contactos", side_effect=RuntimeError("boom-interpretar")
    ):
        html_path = asm.generar_informe_html(
            df=df,
            archivo_kml=str(kml_path),
            carpeta_salida=str(tmp_path),
            nombre_salida="casoB",
            hoja=None,
            nombre_bitacora=None,
            config={},
        )

    contenido = Path(html_path).read_text(encoding="utf-8")
    assert Path(html_path).exists()
    assert "resumen-ejecutivo" in contenido
    assert "Análisis de perfiles de comunicación" not in contenido


def test_resumen_ejecutivo_acepta_defaults_vacios_coherentes():
    logs = []
    html = asm._construir_resumen_ejecutivo(
        total=5,
        orden=[],
        metricas={},
        df=pd.DataFrame({"antena": ["A"]}),
        top_antena=None,
        _log=logs.append,
    )
    assert "resumen-ejecutivo" in html
    # Con defaults vacíos igual se arma la oración base con el total, sin inventar datos.
    assert "<strong>5</strong> interacciones" in html
    assert not logs


def test_generar_informe_html_caso_normal_intacto(tmp_path):
    df = _df_con_contactos()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = asm.generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="casoNormal",
        hoja=None,
        nombre_bitacora=None,
        config={},
    )

    contenido = Path(html_path).read_text(encoding="utf-8")
    assert Path(html_path).exists()
    assert "resumen-ejecutivo" in contenido
