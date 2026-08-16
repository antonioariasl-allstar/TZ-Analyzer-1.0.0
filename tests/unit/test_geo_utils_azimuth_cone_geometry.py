"""
F3.6 — Fuente de verdad única para la geometría del cono de azimut.

`resolve_azimuth_cone_geometry()` (tz_core.geo_utils) es la función que
tanto el ensamblador HTML como (conceptualmente) el generador KML consultan
para resolver radio (km) y semiancho (°) del cono desde config. Estas
pruebas fijan su contrato: misma cadena de fallback que
tz_core.kml_generator usa internamente (config.kml.azimuth_km,
config.kml.cone.half_degrees, reserva en config.style.cone_half_degrees).
"""
from tz_core.geo_utils import resolve_azimuth_cone_geometry


def test_config_none_usa_defaults_del_sistema():
    assert resolve_azimuth_cone_geometry(None) == (1.0, 60)


def test_config_vacio_usa_defaults_del_sistema():
    assert resolve_azimuth_cone_geometry({}) == (1.0, 60)


def test_config_productivo_actual():
    config = {"kml": {"azimuth_km": 1.5, "cone": {"half_degrees": 35}}}
    assert resolve_azimuth_cone_geometry(config) == (1.5, 35)


def test_config_alternativo():
    config = {"kml": {"azimuth_km": 2.0, "cone": {"half_degrees": 25}}}
    assert resolve_azimuth_cone_geometry(config) == (2.0, 25)


def test_half_degrees_reserva_en_style_cone_half_degrees():
    config = {"kml": {"azimuth_km": 1.5}, "style": {"cone_half_degrees": 45}}
    assert resolve_azimuth_cone_geometry(config) == (1.5, 45)


def test_half_degrees_cero_cae_a_reserva_por_falsy():
    # Replica el comportamiento (pre-existente en kml_generator) del operador
    # `or`: half_degrees=0 es falsy en Python y activa la reserva.
    config = {"kml": {"cone": {"half_degrees": 0}}, "style": {"cone_half_degrees": 45}}
    assert resolve_azimuth_cone_geometry(config) == (1.0, 45)
