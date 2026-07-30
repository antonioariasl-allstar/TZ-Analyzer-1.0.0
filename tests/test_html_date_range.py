import pandas as pd

from tz_core.html.kpi import prepare_report_metrics


def test_html_range_prefers_datetime_evento_and_preserves_may_to_july(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2026-05-01 00:00:00", "2026-07-28 00:00:00"],
        "hora": ["09:00:14", "17:16:31"],
        "datetime_evento": pd.to_datetime([
            "2026-05-01 09:00:14",
            "2026-07-28 17:16:31",
        ]),
        "lat": [13.67560667, 13.663242],
        "long": [-89.27647667, -89.248115],
        "antena": ["INCATE", "CTMSEL"],
    })

    metrics = prepare_report_metrics(
        df,
        archivo_kml=str(tmp_path / "case.kml"),
        carpeta_salida=str(tmp_path),
        config={},
    )

    assert metrics["rango_str"] == (
        "01/05/2026 09:00 — 28/07/2026 17:16"
    )
