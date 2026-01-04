"""
Utilidades para manipulación de pandas DataFrames.

Este módulo contiene funciones especializadas para operaciones comunes
con DataFrames, incluyendo deduplicación de columnas.
"""

import pandas as pd
import numpy as np
import difflib
from collections import Counter
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .text_utils import normalize_header_key


def dedupe_columns(df):
    """
    Elimina columnas duplicadas consolidando sus valores.
    
    Para columnas con el mismo nombre, toma el primer valor no vacío
    de cada fila, priorizando la primera columna encontrada.
    
    Args:
        df: pandas DataFrame con posibles columnas duplicadas
        
    Returns:
        pandas DataFrame sin columnas duplicadas
        
    Raises:
        TypeError: Si input no es DataFrame válido
    """
    # Validación básica
    if df is None:
        return None
    
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input debe ser un pandas DataFrame")
    
    # Crear copia para inmutabilidad
    result_df = df.copy()
    
    # Obtener lista de columnas
    cols = list(result_df.columns)
    if not cols:
        return result_df
    
    # Detectar duplicados
    counts = Counter(cols)
    dup_names = [n for n, c in counts.items() if c > 1]
    if not dup_names:
        return result_df
    
    # Construir nuevo DataFrame con columnas únicas preservando el orden original
    new_cols: List[str] = []
    new_series: List[pd.Series] = []
    seen: set[str] = set()

    def _clean_value(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        return np.nan if s == "" else val

    for idx, name in enumerate(result_df.columns):
        if name in seen:
            continue

        # Posiciones de columnas duplicadas con este nombre
        same_columns = [i for i, col in enumerate(result_df.columns) if col == name]

        if len(same_columns) == 1:
            # Columna única, se mantiene sin cambios
            new_cols.append(name)
            new_series.append(result_df.iloc[:, idx])
            seen.add(name)
            continue

        dup_df = result_df.iloc[:, same_columns].copy()
        cleaned = dup_df.map(_clean_value)

        if cleaned.empty:
            combined = pd.Series(np.nan, index=result_df.index)
        else:
            valid = ~cleaned.isna()
            arr = cleaned.to_numpy(dtype=object, copy=False)
            valid_arr = valid.to_numpy(dtype=bool, copy=False)
            has_any = valid_arr.any(axis=1)
            first_idx = valid_arr.argmax(axis=1)
            row_indices = np.arange(len(cleaned))
            chosen = arr[row_indices, first_idx]
            combined = pd.Series(list(chosen), index=result_df.index)
            combined = combined.where(has_any, np.nan)

        new_cols.append(name)
        new_series.append(combined)
        seen.add(name)

    result_df = pd.concat(new_series, axis=1)
    result_df.columns = new_cols
    return result_df


# Alias para compatibilidad con script principal
_dedupe_columns = dedupe_columns


def pick_first_existing_column(df: pd.DataFrame, candidates: Iterable[Optional[str]]) -> Optional[str]:
    """Devuelve la primera columna existente en `df` dentro de la lista `candidates`."""
    for col in candidates:
        if col and col in df.columns:
            return col
    return None


def _pick_col(df: pd.DataFrame, candidates: Iterable[Optional[str]]) -> Optional[str]:  # pragma: no cover
    return pick_first_existing_column(df, candidates)


def apply_schema_renames(
    df: pd.DataFrame,
    synonym_map: Optional[Dict[str, str]] = None,
    *,
    manual_qc_mapping: bool = False,
    fuzzy_cutoff: float = 0.84,
    normalizer: Optional[Callable[[object], str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Genera/aplica `rename_map` usando coincidencias exactas y fuzzy."""

    synonym_map = synonym_map or {}
    if normalizer is None:
        normalizer = normalize_header_key

    if df is None or df.empty or not synonym_map:
        return df, {}

    rename_map: Dict[str, str] = {}
    columns = list(df.columns)

    for col in columns:
        normalized = normalizer(col)
        if normalized and normalized in synonym_map:
            rename_map[col] = synonym_map[normalized]

    remaining = [c for c in columns if c not in rename_map]
    if remaining:
        candidate_keys = list(synonym_map.keys())
        for col in remaining:
            normalized = normalizer(col)
            if not normalized:
                continue
            matches = difflib.get_close_matches(normalized, candidate_keys, n=1, cutoff=fuzzy_cutoff)
            if matches:
                rename_map[col] = synonym_map[matches[0]]

    if not manual_qc_mapping and rename_map:
        df = df.rename(columns=rename_map)

    return df, rename_map


def coalesce_duplicates(
    df: pd.DataFrame,
    prefer: Optional[List[str]] = None,
    original_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Fusiona columnas duplicadas manteniendo el primer valor no vacío por fila."""
    if df is None or df.empty:
        return df

    prefer = prefer or []
    columns_union = list(dict.fromkeys((original_columns or []) + list(df.columns)))
    cols = list(df.columns)
    seen = set()

    def _clean_series(series: pd.Series) -> pd.Series:
        cleaned = series.astype(object).copy()
        invalid = {"", "sin inf", "sin inf.", "nan", "none", "null", "s/i"}
        return cleaned.where(~cleaned.astype(str).str.strip().str.lower().isin(invalid), None)

    for col in columns_union:
        if col in seen or col not in df.columns:
            continue
        positions = [idx for idx, current in enumerate(cols) if current == col]
        if len(positions) <= 1:
            seen.add(col)
            continue

        series_group = [df.iloc[:, pos] for pos in positions]
        base = None
        for series in series_group:
            cleaned = _clean_series(series)
            if base is None:
                base = cleaned
            else:
                mask = (base.isna()) | (base.astype(str).str.strip() == "")
                base = base.where(~mask, cleaned)

        df[col] = base
        drop_positions = positions[1:]
        df = df.drop(columns=[cols[pos] for pos in drop_positions])
        cols = list(df.columns)
        seen.add(col)

    return df


def _coalesce_duplicates(
    df: pd.DataFrame,
    prefer: Optional[List[str]] = None,
    original_columns: Optional[List[str]] = None,
) -> pd.DataFrame:  # pragma: no cover
    return coalesce_duplicates(df, prefer=prefer, original_columns=original_columns)