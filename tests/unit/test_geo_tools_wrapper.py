import math

from tz_services import geo_tools
from tz_core import geo_utils


def test_wrapper_exports_same_functions():
    assert geo_tools.grados_a_radianes is geo_utils.grados_a_radianes
    assert geo_tools.calcular_punto_final is geo_utils.calcular_punto_final


def test_calcular_punto_final_matches_geo_utils():
    lat1, lon1 = geo_tools.calcular_punto_final(0.0, 0.0, 90.0, 1.0)
    lat2, lon2 = geo_utils.calcular_punto_final(0.0, 0.0, 90.0, 1.0)
    assert math.isclose(lat1, lat2) and math.isclose(lon1, lon2)
