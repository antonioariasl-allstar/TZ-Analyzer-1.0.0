"""Tests para los helpers de tz_core.schema_utils."""

import pandas as pd
import unicodedata

from tz_core.schema_utils import (
    build_schema_synonym_map,
    has_location_coverage,
    collect_missing_required_fields,
    ensure_placeholder_columns,
    preview_column_mapping,
    _en_bbox_sv,
    _es_columna_valida_para,
)
from tz_core.text_utils import normalize_header_key


def _strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


class TestBuildSchemaSynonymMap:
    def test_normaliza_aliases_y_sinonimos(self):
        schema_fields = {
            "lat": {"synonyms": ["Latitud", "lat." ]},
            "lon": {"synonyms": ["Longitud"]},
        }
        target_alias = {"lon": "long"}

        result = build_schema_synonym_map(schema_fields, target_alias=target_alias)

        assert result[normalize_header_key("lat")] == "lat"
        assert result[normalize_header_key("latitud")] == "lat"
        assert result[normalize_header_key("longitud")] == "long"
        assert result[normalize_header_key("lon")] == "long"


class TestHasLocationCoverage:
    def test_true_cuando_hay_alt_con_alias(self):
        present = {"lat", "long"}
        alts = [["lat", "lon"], ["antena"]]
        target_alias = {"lon": "long"}

        assert has_location_coverage(present, alts, target_alias) is True

    def test_false_sin_alternativa(self):
        present = {"lat"}
        alts = [["lat", "lon"], ["antena"]]
        target_alias = {"lon": "long"}

        assert has_location_coverage(present, alts, target_alias) is False


class TestCollectMissingRequiredFields:
    def test_incluye_campos_por_modo_sujeto(self):
        present = ["imei", "contacto"]
        fields_meta = {"alias": {"required": True}}

        missing = collect_missing_required_fields(
            present,
            subject_mode="imei",
            fields_meta=fields_meta,
        )

        assert set(missing) == {"fecha", "hora", "interaccion", "alias"}


class TestEnBboxSV:
    def test_coordenada_dentro_bbox_default(self):
        assert _en_bbox_sv(13.5, -89.0) is True

    def test_rechaza_coordenadas_invalidas(self):
        assert _en_bbox_sv(0, 0) is False
        assert _en_bbox_sv("abc", "xyz") is False

    def test_bbox_personalizado(self):
        bbox = {"lat_min": -10, "lat_max": 10, "lon_min": -10, "lon_max": 10}
        assert _en_bbox_sv(5, 5, bbox=bbox) is True
        assert _en_bbox_sv(20, 5, bbox=bbox) is False


class TestEsColumnaValidaPara:
    def test_lat_long_numerica(self):
        serie = pd.Series(["13.1", "14.0", "12.99"])
        ok, _ = _es_columna_valida_para("lat", serie)
        assert ok is True

    def test_lat_long_rechaza_texto(self):
        serie = pd.Series(["abc", "14.0"])
        ok, msg = _es_columna_valida_para("long", serie)
        assert ok is False
        assert "numerica" in _strip_accents(msg.lower())

    def test_hora_formato_valido(self):
        serie = pd.Series(["12:00:00", "23:59:59"])
        ok, _ = _es_columna_valida_para("hora", serie)
        assert ok is True

    def test_hora_formato_invalido(self):
        serie = pd.Series(["126000", "25:00:00"])
        ok, msg = _es_columna_valida_para("hora", serie)
        assert ok is False
        assert "HH:MM:SS" in msg

    def test_fecha_valida(self):
        serie = pd.Series(["01/01/2024", "15/02/2024"])
        ok, _ = _es_columna_valida_para("fecha", serie)
        assert ok is True

    def test_fecha_invalida(self):
        serie = pd.Series(["not-a-date", "2024/13/01"])
        ok, msg = _es_columna_valida_para("fecha", serie)
        assert ok is False
        assert "no parecen fechas" in msg

    def test_tel_valido(self):
        serie = pd.Series(["5031234567", "+503-7654321"])
        ok, _ = _es_columna_valida_para("tel", serie)
        assert ok is True

    def test_tel_invalido(self):
        serie = pd.Series(["sin datos", "abc"])
        ok, msg = _es_columna_valida_para("tel", serie)
        assert ok is False
        assert "numeros telefonicos" in _strip_accents(msg.lower())

    def test_default_no_restringe(self):
        serie = pd.Series(["cualquier cosa", None])
        ok, _ = _es_columna_valida_para("otros", serie)
        assert ok is True


class TestEnsurePlaceholderColumns:
    def test_agrega_columnas_con_placeholder(self):
        df = pd.DataFrame({"lat": [13.5]})

        added = ensure_placeholder_columns(df, ["abonado", "alias"])

        assert set(added) == {"abonado", "alias"}
        assert (df["abonado"] == "SinInf").all()
        assert (df["alias"] == "SinInf").all()

    def test_respeta_alias_y_placeholder_personalizado(self):
        df = pd.DataFrame()
        target_alias = {"abonado": "abonado_final"}

        added = ensure_placeholder_columns(
            df,
            ["abonado"],
            placeholder="N/A",
            target_alias=target_alias,
        )

        assert added == ["abonado_final"]
        assert "abonado_final" in df.columns
        assert (df["abonado_final"] == "N/A").all()


class TestPreviewColumnMapping:
    def test_confirma_mapeo_tras_preview(self):
        serie = pd.Series(["1", "2"])
        salidas: list[str] = []

        result = preview_column_mapping(
            serie,
            "col_src",
            "tel",
            muestras_fn=lambda s, n: ["a", "b"],
            validator_fn=lambda canon, _: (True, ""),
            input_fn=lambda _: "s",
            output_fn=salidas.append,
        )

        assert result is True
        assert any("Previsualización" in linea for linea in salidas)

    def test_rechaza_al_no_validar_tipo(self):
        serie = pd.Series(["x"])
        salidas: list[str] = []

        result = preview_column_mapping(
            serie,
            "col_src",
            "tel",
            muestras_fn=lambda s, n: ["x"],
            validator_fn=lambda canon, _: (False, "motivo"),
            input_fn=lambda _: "s",
            output_fn=salidas.append,
        )

        assert result is False
        assert any("motivo" in linea for linea in salidas)
