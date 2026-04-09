"""
TZ-Analyzer — HTML Generator (Legacy Compatibility Module)
Este módulo mantiene compatibilidad con imports legacy.
La implementación real está en tz_core.html.*

NOTA: pd y np se re-exportan SOLO para compatibilidad con tests existentes.
Esto será eliminado en una fase futura cuando los tests se refactoricen.

Architecture: TZ-Analyzer v1.0.0 — tz_core package
"""

# Assembler principal
from tz_core.html.assembler import generar_informe_html

# KPI functions
from tz_core.html.kpi import (
    generate_kpi_section,
    prepare_report_metrics,
)

# Contacts functions
from tz_core.html.contacts import build_top_contacts_sections

# Antennas functions
from tz_core.html.antennas import (
    build_antennas_table,
    build_top_antennas_section,
    build_antennas_by_hour_section,
    resolve_top_antennas_n,
)

# Metadata functions (incluye privadas para tests)
from tz_core.html.metadata import (
    generate_metadata_section,
    build_identification_rows,
    inject_technical_metadata,
    _build_meta_block,  # Private, solo para tests
    _inject_block,      # Private, solo para tests
)

# Runtime utils (para tests que hacen monkeypatch)
from tz_core.runtime_utils import collect_env_snapshot

# Header functions
from tz_core.html.header import (
    build_logo_html,
    generate_html_header,
    generate_body_header,
)

# Dependencies re-exported ONLY for test compatibility (TEMPORARY)
# TODO(F6): Refactor tests to import pandas/numpy directly
import pandas as pd
import numpy as np

__all__ = [
    # Main assembler
    "generar_informe_html",
    # KPI
    "generate_kpi_section",
    "prepare_report_metrics",
    # Contacts
    "build_top_contacts_sections",
    # Antennas
    "build_antennas_table",
    "build_top_antennas_section",
    "build_antennas_by_hour_section",
    "resolve_top_antennas_n",
    # Metadata
    "generate_metadata_section",
    "build_identification_rows",
    "inject_technical_metadata",
    "_build_meta_block",
    "_inject_block",
    "collect_env_snapshot",
    # Header
    "build_logo_html",
    "generate_html_header",
    "generate_body_header",
    # Dependencies (temporary)
    "pd",
    "np",
]
