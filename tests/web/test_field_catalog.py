"""FASE 2 WEB — Catálogo central reutilizable de los 14 campos canónicos
(``tz_web.field_catalog``, OBJETIVO B del microbloque de separación
Preparar/Resumen + catálogo)."""
from __future__ import annotations

from tz_core.field_roles import WIZARD_ORDER_PRIMARY, WIZARD_ORDER_SECONDARY
from tz_web.field_catalog import (
    CANONICAL_FIELDS,
    FIELD_CATALOG,
    FIELD_DESCRIPTIONS,
    FIELD_GROUPS,
    FIELD_LABELS,
    description_for,
    label_for,
)

EXPECTED_LABELS = {
    "fecha": "Fecha",
    "hora": "Hora",
    "duracion": "Duración",
    "interaccion": "Tipo de interacción",
    "tel": "Número analizado",
    "contacto": "Contacto",
    "imei": "IMEI",
    "imsi": "IMSI",
    "lat": "Latitud",
    "long": "Longitud",
    "azimut": "Azimut",
    "antena": "Antena",
    "celda": "Celda",
    "direccion": "Dirección",
}

EXPECTED_GROUPS = (
    ("Tiempo", ("fecha", "hora")),
    ("Evento", ("duracion", "interaccion")),
    ("Telefonía", ("tel", "contacto")),
    ("Identificación técnica", ("imei", "imsi")),
    ("Ubicación", ("lat", "long")),
    ("Cobertura", ("azimut", "antena")),
    ("Antena", ("celda", "direccion")),
)


def test_catalogo_contiene_exactamente_los_14_campos_canonicos():
    assert len(FIELD_CATALOG) == 14
    assert set(FIELD_CATALOG.keys()) == set(EXPECTED_LABELS.keys())
    # Mismos 14 campos que usa el motor (tz_core.field_roles), solo con
    # presentación distinta — ninguna clave interna se inventa ni se pierde.
    assert set(FIELD_CATALOG.keys()) == set(WIZARD_ORDER_PRIMARY) | set(WIZARD_ORDER_SECONDARY)
    assert set(CANONICAL_FIELDS) == set(FIELD_CATALOG.keys())


def test_etiquetas_visibles_coinciden_con_las_aprobadas():
    assert FIELD_LABELS == EXPECTED_LABELS
    for campo, etiqueta in EXPECTED_LABELS.items():
        assert label_for(campo) == etiqueta
        assert FIELD_CATALOG[campo].label == etiqueta


def test_descripciones_no_vacias_para_los_14_campos():
    assert set(FIELD_DESCRIPTIONS.keys()) == set(EXPECTED_LABELS.keys())
    for campo, descripcion in FIELD_DESCRIPTIONS.items():
        assert descripcion
        assert description_for(campo) == descripcion


def test_los_7_grupos_y_su_orden_son_correctos():
    assert FIELD_GROUPS == EXPECTED_GROUPS
    assert len(FIELD_GROUPS) == 7
    for _nombre, campos in FIELD_GROUPS:
        assert len(campos) == 2


def test_orden_de_catalogo_sigue_el_orden_de_grupos():
    esperado = [campo for _grupo, campos in EXPECTED_GROUPS for campo in campos]
    assert list(FIELD_CATALOG.keys()) == esperado
    for indice, campo in enumerate(esperado, start=1):
        assert FIELD_CATALOG[campo].order == indice


def test_campo_desconocido_cae_a_valores_por_defecto_seguros():
    assert label_for("no_existe") == "no_existe"
    assert description_for("no_existe") == ""


def test_descripcion_antena_usa_site_id_y_no_confunde_con_celda():
    """OBJETIVO 4 del microbloque: la descripción de 'antena' debe hablar de
    identificador/torre/sitio (Site ID) sin usar 'antena/celda' como
    sinónimos — Celda es un campo independiente del catálogo."""
    descripcion = FIELD_DESCRIPTIONS["antena"]
    assert "Site ID" in descripcion
    assert "antena/celda" not in descripcion.lower()
    assert "celda" not in descripcion.lower()


def test_descripcion_direccion_no_es_exclusivamente_postal():
    """La descripción de 'direccion' debe funcionar también con columnas
    como 'Lugares de Cobertura', no solo con direcciones postales."""
    descripcion = FIELD_DESCRIPTIONS["direccion"]
    assert "postal" not in descripcion.lower()
    assert "cobertura" in descripcion.lower()
