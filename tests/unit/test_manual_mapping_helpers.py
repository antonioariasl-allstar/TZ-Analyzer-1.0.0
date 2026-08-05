"""Pruebas para tz_core.manual_mapping_helpers (HITO 3/4).

Caso 15: manual_mapping_helpers debe reutilizar la misma clasificación de
campos que mapping_wizard.MappingWizard, en vez de mantener una lista
literal paralela que pueda divergir en silencio.
"""

from __future__ import annotations

import pandas as pd

from tz_core.field_roles import WIZARD_ORDER_PRIMARY, WIZARD_ORDER_SECONDARY
from tz_core.manual_mapping_helpers import prepare_manual_mapping
from tz_core.mapping_wizard import MappingWizard


class TestPrepareManualMappingUsaClasificacionCompartida:
    def test_devuelve_las_mismas_listas_que_field_roles(self):
        df = pd.DataFrame({"a": [1], "b": [2]})

        _df_ready, esenciales, no_esenciales = prepare_manual_mapping(df)

        assert esenciales == list(WIZARD_ORDER_PRIMARY)
        assert no_esenciales == list(WIZARD_ORDER_SECONDARY)

    def test_coincide_con_los_defaults_de_mappingwizard(self):
        """No deben existir dos listas paralelas incompatibles: la que usa
        `prepare_manual_mapping` y la que usa `MappingWizard` por defecto
        deben ser exactamente la misma."""
        df = pd.DataFrame({"a": [1]})

        _df_ready, esenciales, no_esenciales = prepare_manual_mapping(df)

        assert esenciales == MappingWizard._default_esenciales()
        assert no_esenciales == MappingWizard._default_no_esenciales()

    def test_ninguna_lista_tiene_campos_duplicados_entre_si(self):
        df = pd.DataFrame({"a": [1]})

        _df_ready, esenciales, no_esenciales = prepare_manual_mapping(df)

        assert set(esenciales) & set(no_esenciales) == set()
