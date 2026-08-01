"""Regresión del selector diario de la sección de interacciones HTML."""

import pandas as pd

from tz_core.interacciones_builder import construir_seccion_interacciones


def test_selector_interacciones_conserva_rango_mayo_julio():
    """El selector debe derivarse de datetime_evento sin invertir mes y día."""
    df = pd.DataFrame({
        "fecha": ["2026-05-01 00:00:00", "2026-07-28 00:00:00"],
        "hora": ["09:00:14", "17:16:31"],
        "datetime_evento": pd.to_datetime([
            "2026-05-01 09:00:14",
            "2026-07-28 17:16:31",
        ]),
        "contacto": ["70000001", "70000002"],
        "duracion": [0, 120],
        "lat": [13.67560667, 13.663242],
        "long": [-89.27647667, -89.248115],
        "antena": ["INCATE", "CTMSEL"],
        "azimut": [122, 330],
        "interaccion": ["MENSAJE ENTRANTE", "LLAMADA SALIENTE"],
    })

    html = construir_seccion_interacciones(df, config={})

    assert "01/05/2026" in html
    assert "28/07/2026" in html
    assert 'value="2026-05-01"' in html
    assert 'value="2026-07-28"' in html
    assert "05/01/2026" not in html
    assert "2026-01-05" not in html
