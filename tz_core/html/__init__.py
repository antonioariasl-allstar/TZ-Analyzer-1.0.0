"""
TZ-Analyzer — HTML Generation Package
Sub-paquete que contiene todos los módulos de generación de HTML.
Organizado por responsabilidad: assembler, header, kpi, metadata, contacts, antennas.
Architecture: TZ-Analyzer v1.0.0 — tz_core.html package
"""

# Assembler - Función principal de orquestación
from .assembler import generar_informe_html

# Header - Logo, HTML head, body header
from .header import (
    build_logo_html,
    generate_html_header,
    generate_body_header,
)

# KPI - Métricas y sección de indicadores
from .kpi import (
    prepare_report_metrics,
    generate_kpi_section,
)

# Metadata - Sección de metadatos e inyección técnica
from .metadata import (
    generate_metadata_section,
    build_identification_rows,
    inject_technical_metadata,
)

# Contacts - Secciones de contactos top y completa
from .contacts import (
    build_top_contacts_sections,
    _construir_seccion_todos_contactos,
)

# Antennas - Tablas y secciones de antenas
from .antennas import (
    resolve_top_antennas_n,
    build_antennas_table,
    build_top_antennas_section,
    build_antennas_by_hour_section,
)

__all__ = [
    # Assembler
    'generar_informe_html',
    # Header
    'build_logo_html',
    'generate_html_header',
    'generate_body_header',
    # KPI
    'prepare_report_metrics',
    'generate_kpi_section',
    # Metadata
    'generate_metadata_section',
    'build_identification_rows',
    'inject_technical_metadata',
    # Contacts
    'build_top_contacts_sections',
    '_construir_seccion_todos_contactos',
    # Antennas
    'resolve_top_antennas_n',
    'build_antennas_table',
    'build_top_antennas_section',
    'build_antennas_by_hour_section',
]
