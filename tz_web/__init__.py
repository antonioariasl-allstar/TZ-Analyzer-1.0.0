"""tz_web — capa de servicio no interactiva (Fase 1 Web).

Expone ``process_case()`` como punto de entrada único: orquesta un análisis
completo (archivo + hoja + mapeo + opciones + carpeta de salida -> HTML +
KMZ + hashes + logs) sin consola, sin Tkinter y sin monkeypatching, para que
una futura app web (Fase 2+) pueda invocarlo directamente.

Ver ``tz_web.services`` para el detalle de diseño y las excepciones de
dominio disponibles.
"""

from tz_web.services import (
    AnalysisInProgressError,
    CaseFileNotFoundError,
    CaseLoadError,
    CaseRequest,
    CaseResult,
    InvalidMappingError,
    OutputDirectoryError,
    ProgressUpdate,
    SheetNotFoundError,
    process_case,
)

__all__ = [
    "process_case",
    "CaseRequest",
    "CaseResult",
    "ProgressUpdate",
    "AnalysisInProgressError",
    "CaseFileNotFoundError",
    "CaseLoadError",
    "InvalidMappingError",
    "OutputDirectoryError",
    "SheetNotFoundError",
]
