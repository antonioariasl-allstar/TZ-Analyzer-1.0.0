"""Helpers for manual mapping wizard setup and execution."""

from typing import Any, Dict, List, Optional, Tuple
import warnings

import pandas as pd

from tz_core.mapping_wizard import WizardIO, MappingWizard


def prepare_manual_mapping(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Prepare DataFrame and canonical lists for manual QC mapping."""

    esenciales_qc = [
        "fecha",
        "hora",
        "tel",
        "imei",
        "interaccion",
        "contacto",
        "lat",
        "long",
        "azimut",
        "antena",
    ]
    no_esenciales_qc = ["celda", "direccion", "imsi", "duracion"]

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
