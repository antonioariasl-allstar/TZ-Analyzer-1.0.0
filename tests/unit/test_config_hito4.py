"""Pruebas HITO 4 — coherencia de config.json con la política de capacidades.

Casos 1-5 del hito: ningún campo analítico individual es un requisito
global; ``requisitos_modulo`` declara la matriz mínima aprobada; ``duracion``
es el canónico oficial (con ``duracion_seg`` como alias explícito); y
alias/nombre_usuario/abonado son tres campos de ``schema.fields``
independientes (ya no fusionados bajo un único "usuario").
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")


@pytest.fixture(scope="module")
def config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def schema_fields(config: dict) -> dict:
    return (config.get("schema") or {}).get("fields") or {}


class TestSinRequeridosGlobales:
    """Caso 1 y 2: ningún campo analítico individual queda marcado como
    requisito universal (``required: true``) en config.json."""

    def test_contacto_no_es_required_global(self, schema_fields):
        assert schema_fields["contacto"].get("required") is not True

    def test_interaccion_no_es_required_global(self, schema_fields):
        assert schema_fields["interaccion"].get("required") is not True

    @pytest.mark.parametrize("campo", ["azimut", "fecha", "hora"])
    def test_campo_no_exige_globalmente(self, schema_fields, campo):
        assert schema_fields[campo].get("required") is not True

    def test_lat_long_no_exigen_globalmente(self, schema_fields):
        assert schema_fields["lat"].get("required") is not True
        assert schema_fields["long"].get("required") is not True

    def test_tel_no_es_required_global_solo_por_modo(self, schema_fields):
        """tel usa required_mode (identificación condicional al modo del
        sujeto), no required=True (requisito universal)."""
        assert schema_fields["tel"].get("required") is not True
        assert "required_mode" in schema_fields["tel"]


class TestRequisitosModulo:
    """Caso 3: requisitos_modulo contiene la matriz mínima aprobada."""

    def test_requisitos_modulo_presente(self, config):
        assert "requisitos_modulo" in config

    def test_matriz_minima_aprobada(self, config):
        requisitos = config["requisitos_modulo"]

        assert requisitos["identificacion"]["uno_de"] == ["tel", "imei"]
        assert requisitos["cronologia"]["minimos"] == ["fecha"]
        assert requisitos["cronologia"]["recomendables"] == ["hora"]
        assert requisitos["antenas"]["minimos"] == ["antena"]
        assert set(requisitos["antenas"]["recomendables"]) == {"lat", "long", "azimut", "hora"}
        assert requisitos["kml"]["minimos_por_fila"] == ["lat", "long"]
        assert set(requisitos["kml"]["recomendables"]) == {"antena", "azimut"}
        assert requisitos["contactos"]["minimos"] == ["contacto"]
        assert requisitos["contactos"]["recomendables"] == ["duracion"]
        assert requisitos["tipo_evento"]["minimos"] == ["interaccion"]


class TestDuracionCanonica:
    """Caso 4: duracion es el canónico oficial; duracion_seg es alias explícito."""

    def test_duracion_es_clave_canonica(self, schema_fields):
        assert "duracion" in schema_fields
        assert "duracion_seg" not in schema_fields

    def test_duracion_seg_sigue_siendo_alias(self, schema_fields):
        sinonimos = schema_fields["duracion"]["synonyms"]
        assert "duracion_seg" in sinonimos

    def test_segundos_y_duration_seconds_son_alias(self, schema_fields):
        sinonimos = schema_fields["duracion"]["synonyms"]
        assert "segundos" in sinonimos
        assert "duration_seconds" in sinonimos


class TestLongCanonico:
    """Caso 2 (complementario): la divergencia lon/long queda resuelta sin
    romper el pipeline — 'long' es la clave canónica; 'lon' sigue siendo
    alias reconocido."""

    def test_long_es_clave_canonica(self, schema_fields):
        assert "long" in schema_fields
        assert "lon" not in schema_fields

    def test_lon_sigue_siendo_alias(self, schema_fields):
        assert "lon" in schema_fields["long"]["synonyms"]


class TestIdentidadIndependiente:
    """Caso 5: alias, nombre_usuario y abonado permanecen tres campos
    independientes (schema.fields.usuario ya no los fusiona)."""

    def test_usuario_fusionado_ya_no_existe(self, schema_fields):
        assert "usuario" not in schema_fields

    def test_tres_campos_independientes_presentes(self, schema_fields):
        assert "alias" in schema_fields
        assert "nombre_usuario" in schema_fields
        assert "abonado" in schema_fields

    def test_sinonimos_no_se_solapan_entre_los_tres(self, schema_fields):
        alias_syn = set(schema_fields["alias"]["synonyms"])
        nombre_syn = set(schema_fields["nombre_usuario"]["synonyms"])
        abonado_syn = set(schema_fields["abonado"]["synonyms"])

        assert alias_syn & nombre_syn == set()
        assert alias_syn & abonado_syn == set()
        assert nombre_syn & abonado_syn == set()


class TestColumnasNormalizables:
    """La antigua 'columnas_esenciales' ya no sugiere bloqueo global: se
    renombró conceptualmente a 'columnas_normalizables'."""

    def test_columnas_esenciales_ya_no_existe(self, config):
        assert "columnas_esenciales" not in (config.get("entradas") or {})

    def test_columnas_normalizables_presente(self, config):
        assert "columnas_normalizables" in config["entradas"]
