import os
from pathlib import Path

import pandas as pd

from tz_core.file_utils import relocate_kmz_file
from tz_core.output_pipeline import produce_case_outputs


def test_produce_outputs_generates_assets(tmp_path):
    df = pd.DataFrame({"antena": ["A"], "lat": [13.7], "long": [-88.9]})
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    out_dir = tmp_path / "salida"
    out_dir.mkdir()

    nombre_salida = "caso_mapeo"
    kml_path = out_dir / f"{nombre_salida}.kml"
    kml_path.write_text("kml", encoding="utf-8")
    kmz_src = base_dir / f"{nombre_salida}_mapeo.kmz"
    kmz_src.write_text("kmz", encoding="utf-8")

    archivo_entrada = tmp_path / "bitacora.xlsx"
    archivo_entrada.write_text("excel", encoding="utf-8")
    log_file = tmp_path / "log.txt"
    log_file.write_text("log", encoding="utf-8")
    html_target = out_dir / f"{nombre_salida}.html"

    logs: list[str] = []
    outputs: list[str] = []
    summary_calls = []
    hashes_written = {}

    def generar_html(df, archivo_kml, carpeta_salida, nombre, hoja, nombre_bitacora):
        html_target.write_text("html", encoding="utf-8")
        return str(html_target)

    def write_hashes(dest, pairs):
        Path(dest).write_text("hashes", encoding="utf-8")
        hashes_written["path"] = dest
        hashes_written["pairs"] = pairs

    def summary_stub(**kwargs):
        summary_calls.append(kwargs)

    section_events = []

    result = produce_case_outputs(
        df=df,
        config={"html": {"interacciones_ultimos_dias": 5}},
        nombre_salida=nombre_salida,
        archivo_kml=str(kml_path),
        carpeta_base=str(base_dir),
        carpeta_salida=str(out_dir),
        archivo_entrada=str(archivo_entrada),
        hoja="Hoja1",
        error_report_path="errores.txt",
        discarded_coords=2,
        build_interactions_section=lambda df, dias, cols: f"inter_{dias}",
        build_contacts_section=lambda df, cols: "contacts",
        generar_html_fn=generar_html,
        relocate_kmz_fn=relocate_kmz_file,
        write_hashes_fn=write_hashes,
        summarize_fn=summary_stub,
        logger=logs.append,
        output_fn=outputs.append,
        path_exists=os.path.exists,
        cwd_fn=os.getcwd,
        log_file_path=str(log_file),
        set_interactions_section=lambda html: section_events.append(("inter", html)),
        set_contacts_section=lambda html: section_events.append(("contacts", html)),
    )

    assert result.informe_html == str(html_target)
    assert result.kmz_path == str(out_dir / f"{nombre_salida}_mapeo.kmz")
    assert result.hashes_path == hashes_written["path"]
    assert result.interactions_html == "inter_5"
    assert result.contacts_html == "contacts"
    assert any("Informe HTML generado" in msg for msg in outputs)
    assert any(msg.startswith("[DEBUG] Interacciones") for msg in logs)
    assert summary_calls and summary_calls[0]["discarded_coords"] == 2
    assert Path(result.hashes_path).exists()
    assert len(hashes_written["pairs"]) >= 3
    assert ("inter", "inter_5") in section_events
    assert ("contacts", "contacts") in section_events


def test_produce_outputs_handles_interaction_errors(tmp_path):
    df = pd.DataFrame({"antena": ["A"]})
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    out_dir = tmp_path / "salida"
    out_dir.mkdir()

    nombre_salida = "caso_mapeo"
    kml_path = out_dir / f"{nombre_salida}.kml"
    kml_path.write_text("kml", encoding="utf-8")
    kmz_src = base_dir / f"{nombre_salida}_mapeo.kmz"
    kmz_src.write_text("kmz", encoding="utf-8")
    html_target = out_dir / f"{nombre_salida}.html"

    outputs: list[str] = []
    logs: list[str] = []

    def bad_interactions(*args, **kwargs):
        raise ValueError("boom")

    def generar_html(df, archivo_kml, carpeta_salida, nombre, hoja, nombre_bitacora):
        html_target.write_text("html", encoding="utf-8")
        return str(html_target)

    section_flag = {}

    result = produce_case_outputs(
        df=df,
        config={},
        nombre_salida=nombre_salida,
        archivo_kml=str(kml_path),
        carpeta_base=str(base_dir),
        carpeta_salida=str(out_dir),
        archivo_entrada=None,
        hoja=None,
        error_report_path=None,
        discarded_coords=0,
        build_interactions_section=bad_interactions,
        build_contacts_section=lambda df, cols: "contacts",
        generar_html_fn=generar_html,
        relocate_kmz_fn=relocate_kmz_file,
        write_hashes_fn=lambda *_args, **_kwargs: None,
        summarize_fn=lambda **_kwargs: None,
        logger=logs.append,
        output_fn=outputs.append,
        path_exists=os.path.exists,
        cwd_fn=os.getcwd,
        log_file_path=None,
        set_interactions_section=lambda html: section_flag.setdefault("inter", html),
    )

    assert result.interactions_html == ""
    assert any("Interacciones falló" in msg for msg in logs)
    assert result.contacts_html == "contacts"
    assert any("Informe HTML generado" in msg for msg in outputs)
    assert section_flag.get("inter") == ""


def test_generar_informe_html_inserta_interacciones(tmp_path, monkeypatch):
    import script_principal_bitacoras_refactory as monolith

    # Forzar config mínima y sección precalculada
    monkeypatch.setattr(monolith, "CONFIG", {}, raising=False)
    monkeypatch.setattr(
        monolith,
        "HTML_SECCION_INTERACCIONES",
        '<section id="interacciones-recientes">ok</section>',
        raising=False,
    )

    df = pd.DataFrame(
        {
            "fecha": ["01/01/2020"],
            "hora": ["00:00:00"],
            "antena": ["A"],
            "lat": [13.7],
            "long": [-88.9],
        }
    )

    out_dir = tmp_path
    kml_path = out_dir / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = monolith.generar_informe_html(
        df,
        str(kml_path),
        str(out_dir),
        "caso",
        hoja=None,
        nombre_bitacora=None,
    )

    contenido = Path(html_path).read_text(encoding="utf-8")
    assert "interacciones-recientes" in contenido


def test_generar_informe_html_inserta_todos_contactos(tmp_path, monkeypatch):
    import script_principal_bitacoras_refactory as monolith

    # Forzar config mínima y sección precalculada
    monkeypatch.setattr(monolith, "CONFIG", {}, raising=False)
    monkeypatch.setattr(
        monolith,
        "HTML_SECCION_TODOS_CONTACTOS",
        '<section id="todos-contactos">ok</section>',
        raising=False,
    )

    df = pd.DataFrame(
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

    out_dir = tmp_path
    kml_path = out_dir / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = monolith.generar_informe_html(
        df,
        str(kml_path),
        str(out_dir),
        "caso",
        hoja=None,
        nombre_bitacora=None,
    )

    contenido = Path(html_path).read_text(encoding="utf-8")
    assert "todos-contactos" in contenido
