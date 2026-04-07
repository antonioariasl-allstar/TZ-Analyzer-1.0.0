from __future__ import annotations

"""Dataclasses compartidas que definen las estructuras de datos del pipeline de TZ Analyzer."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ManualModeContext:
    """Resultado de la recolección de modo manual/autómatico."""

    option: str
    config: Dict[str, Any]


@dataclass
class DatasetMetadata:
    """Información del archivo seleccionado y su DataFrame resultante."""

    archivo: str
    hoja: Optional[str]
    dataframe: Any
    columnas: List[str]
    hoja_usada: Optional[str] = None


@dataclass
class CaseIdentity:
    """Detalles del caso para construir nombres de archivos/carpeta."""

    mode: str
    primary_id: Optional[str]
    alias_short: str
    base_name: str


@dataclass
class TopSelection:
    """Valores seleccionados para los tops de antenas/contactos."""

    antennas: int
    contacts: int


@dataclass
class OutputRouting:
    """Información completa de carpetas/archivos generados para el caso."""

    base_name: str
    base_folder: str
    case_folder: str
    output_folder: str
    kml_folder: Optional[str]
    kml_path: str
    kmz_path: str


@dataclass
class CaseNameSuggestion:
    """Información generada para sugerir un nombre base del caso."""

    base_name: str
    principal_id: str
    alias_id: str
    tel_part: str
    alias_part: str
    date_range_label: str
    filter_suffix: str
