"""Helpers for manual mapping wizard setup and execution."""

import builtins
from typing import Any, Dict, List, Optional, Tuple, Callable
import warnings

import pandas as pd

from tz_core.mapping_wizard import WizardIO, MappingWizard
from tz_core.field_roles import WIZARD_ORDER_PRIMARY, WIZARD_ORDER_SECONDARY


def prepare_manual_mapping(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Prepare DataFrame and canonical lists for manual QC mapping.

    HITO 3/4: reutiliza la misma clasificación de ``tz_core.field_roles`` que
    usa ``MappingWizard`` por defecto, en vez de mantener una lista literal
    paralela que podía divergir silenciosamente de la del wizard.
    """

    esenciales_qc = list(WIZARD_ORDER_PRIMARY)
    no_esenciales_qc = list(WIZARD_ORDER_SECONDARY)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Pandas doesn't allow columns to be created via a new attribute name*",
            category=UserWarning,
        )
        try:
            df._orig_cols = list(df.columns)
        except Exception:
            pass

    df.attrs["_orig_cols"] = list(df.columns)
    return df, esenciales_qc, no_esenciales_qc


def build_wizard_io(
    log_to_system: Optional[bool] = None,
    *,
    log_enabled_default: bool = True,
    log_debug: Optional[Callable[[str], None]] = None,
    log_info: Optional[Callable[[str], None]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
) -> WizardIO:
    """Create a WizardIO with optional logging hooks.

    ``input_fn``/``output_fn`` se resuelven aquí, en tiempo de llamada, en
    vez de quedar fijados como default de firma (``= input``) capturado en
    tiempo de importación. Esto permite que un llamador no interactivo
    inyecte ambos explícitamente sin depender de la referencia a
    ``builtins.input``/``print`` vigente cuando se importó este módulo.
    """

    log_enabled = log_enabled_default if log_to_system is None else bool(log_to_system)
    resolved_input = input_fn if input_fn is not None else builtins.input
    resolved_output = output_fn if output_fn is not None else builtins.print

    def _wizard_input(message: str) -> str:
        """Callback de entrada para el wizard con logging opcional."""
        if log_enabled and log_debug:
            try:
                log_debug(f"[Wizard Prompt] {message.strip()}")
            except Exception:
                pass

        try:
            return resolved_input(message)
        except Exception:
            return ""

    def _wizard_output(message: str) -> None:
        """Callback de salida para el wizard con impresión y logging opcional."""
        resolved_output(message)
        if log_enabled and log_info:
            try:
                log_info(message)
            except Exception:
                pass

    return WizardIO(input_fn=_wizard_input, output_fn=_wizard_output)


def run_manual_mapping(
    df: pd.DataFrame,
    *,
    esenciales: Optional[List[str]] = None,
    no_esenciales: Optional[List[str]] = None,
    wizard_io: Optional[WizardIO] = None,
) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
    """Instantiate MappingWizard with defaults and return (df_mapped, assignments)."""

    df_ready, default_esenciales, default_no_esenciales = prepare_manual_mapping(df)
    wizard = MappingWizard(
        df_ready,
        esenciales if esenciales is not None else default_esenciales,
        no_esenciales if no_esenciales is not None else default_no_esenciales,
        io=wizard_io or WizardIO(),
    )
    return wizard.run()
