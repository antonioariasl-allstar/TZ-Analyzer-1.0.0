"""Pruebas para tz_core.field_roles (HITO 3/4 — clasificación única de campos).

Garantiza que la clasificación compartida por mapping_wizard.py y
manual_mapping_helpers.py no tenga campos duplicados/contradictorios entre
categorías, que cubra exactamente el universo de campos declarado, y que el
vocabulario "esencial/no esencial" no aparezca en los nombres públicos del
módulo (HITO 4 — ningún grupo funcional se presenta como bloqueante global).
"""

from __future__ import annotations

import tz_core.field_roles as field_roles
from tz_core.field_roles import (
    CATEGORY_LABELS,
    COMPLEMENTARIOS_FIELDS,
    COMUNICACIONES_FIELDS,
    CRONOLOGIA_FIELDS,
    FIELD_CATEGORIES,
    GEOLOCALIZACION_FIELDS,
    IDENTIFICACION_FIELDS,
    IDENTITY_FIELDS,
    IDENTITY_METADATA_FIELDS,
    WIZARD_ORDER_PRIMARY,
    WIZARD_ORDER_SECONDARY,
    all_categorized_fields,
    category_of,
)


class TestClasificacionSinDuplicados:
    def test_ningun_campo_repetido_entre_categorias(self):
        vistos: set[str] = set()
        for fields in FIELD_CATEGORIES.values():
            for field in fields:
                assert field not in vistos, f"'{field}' aparece en más de una categoría"
                vistos.add(field)

    def test_orden_primario_y_secundario_no_se_solapan(self):
        """Caso 14: wizard no duplica campos entre los dos órdenes de presentación."""
        assert set(WIZARD_ORDER_PRIMARY) & set(WIZARD_ORDER_SECONDARY) == set()

    def test_identity_fields_fuera_de_ambos_ordenes(self):
        """alias/nombre_usuario/abonado se preguntan aparte; no deben estar
        en ninguno de los dos órdenes (evita doble pregunta)."""
        assert set(IDENTITY_FIELDS) & set(WIZARD_ORDER_PRIMARY) == set()
        assert set(IDENTITY_FIELDS) & set(WIZARD_ORDER_SECONDARY) == set()

    def test_cobertura_completa_sin_huecos(self):
        todos = set(all_categorized_fields())
        cubiertos = set(WIZARD_ORDER_PRIMARY) | set(WIZARD_ORDER_SECONDARY) | set(IDENTITY_FIELDS)
        assert todos == cubiertos

    def test_contacto_e_interaccion_no_estan_en_orden_secundario(self):
        """No deben aparecer contradictoriamente en el orden secundario
        mientras también están en el primario."""
        assert "contacto" not in WIZARD_ORDER_SECONDARY
        assert "interaccion" not in WIZARD_ORDER_SECONDARY
        assert "imei" not in WIZARD_ORDER_SECONDARY

    def test_category_labels_cubre_todas_las_categorias(self):
        assert set(CATEGORY_LABELS.keys()) == set(FIELD_CATEGORIES.keys())

    def test_category_of_resuelve_categoria_correcta(self):
        assert category_of("tel") == "identificacion"
        assert category_of("lat") == "geolocalizacion"
        assert category_of("duracion") == "comunicaciones"
        assert category_of("campo_inexistente") is None

    def test_grupos_funcionales_declarados_sin_solapamiento(self):
        grupos = [
            IDENTIFICACION_FIELDS,
            CRONOLOGIA_FIELDS,
            GEOLOCALIZACION_FIELDS,
            COMUNICACIONES_FIELDS,
            COMPLEMENTARIOS_FIELDS,
            IDENTITY_METADATA_FIELDS,
        ]
        vistos: set[str] = set()
        for grupo in grupos:
            for campo in grupo:
                assert campo not in vistos, f"'{campo}' aparece en más de un grupo funcional"
                vistos.add(campo)


class TestSinVocabularioEsencial:
    """Caso 6: el wizard/field_roles no usa la palabra 'esenciales' para
    nombrar grupos funcionales públicos."""

    def test_nombres_publicos_no_contienen_esencial(self):
        for nombre in field_roles.__all__:
            assert "esencial" not in nombre.lower(), (
                f"'{nombre}' usa vocabulario 'esencial' para un grupo funcional"
            )

    def test_default_esenciales_ya_no_existe(self):
        assert not hasattr(field_roles, "DEFAULT_ESENCIALES")
        assert not hasattr(field_roles, "DEFAULT_NO_ESENCIALES")
