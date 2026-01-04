import pandas as pd

from tz_core.logging_utils import write_minimal_filter_log


def test_write_minimal_filter_log_basic(tmp_path):
    df = pd.DataFrame(
        {
            "lat": [13.5, None, 0],
            "long": [-89.2, -90.1, 0],
            "antena": ["Site 1", "Site 2", ""],
            "tel_contacto": ["503111111", "", None],
        }
    )

    salida = tmp_path / "log_minimo.txt"
    result_path = write_minimal_filter_log(df, "Filtro demo", salida)

    contenido = salida.read_text(encoding="utf-8")

    assert result_path == str(salida)
    assert "Filtro aplicado: Filtro demo" in contenido
    assert "Registros tras filtro: 3" in contenido
    assert "Antenas únicas (válidas): 1" in contenido
    assert "Contactos únicos: 1" in contenido


def test_write_minimal_filter_log_sin_columnas(tmp_path):
    df = pd.DataFrame({"foo": [1, 2, 3]})

    salida = tmp_path / "log_minimo.txt"
    write_minimal_filter_log(df, "Sin columnas", salida)

    contenido = salida.read_text(encoding="utf-8")
    assert "Antenas únicas (válidas): 0" in contenido
    assert "Contactos únicos: 0" in contenido
