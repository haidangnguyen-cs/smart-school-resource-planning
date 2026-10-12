"""Normalization of column names, data types, categories, and operational status."""

from typing import Any

import numpy as np
import pandas as pd


def normalize_column_names(
    df: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    """Rename DataFrame columns according to contract mapping.

    Args:
        df: Input DataFrame.
        mapping: Dictionary mapping raw column names to target names.

    Returns:
        DataFrame with renamed columns.
    """
    return df.rename(columns=mapping)


def strip_whitespace(
    df: pd.DataFrame,
    string_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Strip leading and trailing whitespace from string columns.

    Args:
        df: Input DataFrame.
        string_cols: Optional list of columns to strip. If None, strips all object/string columns.

    Returns:
        DataFrame with stripped strings.
    """
    result = df.copy()
    cols = (
        string_cols
        if string_cols is not None
        else result.select_dtypes(include=["object", "string"]).columns
    )

    for col in cols:
        if col in result.columns:
            result[col] = result[col].astype(str).str.strip()
            # Restore genuine NaN where string became 'nan' or empty string
            result[col] = result[col].replace({"": np.nan, "nan": np.nan, "None": np.nan})

    return result


def classify_operational_status(
    df: pd.DataFrame,
    status_col: str = "school_status",
) -> pd.DataFrame:
    """Classify school facilities into active, inactive, and transition review buckets.

    Contract Rules:
    - Active: ['Open', 'New'] -> is_operational = True, status_bucket = 'active'
    - Inactive: ['Closed', 'Inactive', 'Future'] -> is_operational = False, status_bucket = 'inactive'
    - Transition Review: ['Added', 'Changed Boundary/Agency', 'Reopened'] ->
        is_operational = False, status_bucket = 'transition_review' (routed to Priority 1 review)
    - All other values -> is_operational = False, status_bucket = 'other'

    Args:
        df: Input DataFrame containing school status.
        status_col: Column name containing operational status text.

    Returns:
        DataFrame augmented with 'is_operational' (bool) and 'status_bucket' (str).
    """
    result = df.copy()
    if status_col not in result.columns:
        result["is_operational"] = False
        result["status_bucket"] = "unknown"
        return result

    raw_status = result[status_col].astype(str).str.strip()

    active_statuses = {"Open", "New"}
    inactive_statuses = {"Closed", "Inactive", "Future"}
    transition_statuses = {"Added", "Changed Boundary/Agency", "Reopened"}

    is_active = raw_status.isin(active_statuses)
    result["is_operational"] = is_active

    conditions = [
        raw_status.isin(active_statuses),
        raw_status.isin(inactive_statuses),
        raw_status.isin(transition_statuses),
    ]
    choices = [
        "active",
        "inactive",
        "transition_review",
    ]
    result["status_bucket"] = np.select(conditions, choices, default="other")

    return result


def normalize_charter_status(
    df: pd.DataFrame,
    charter_col: str = "is_charter",
) -> pd.DataFrame:
    """Normalize charter school flag into boolean or standardized indicator.

    Args:
        df: Input DataFrame.
        charter_col: Column name containing charter text ('Yes', 'No', 1, 0).

    Returns:
        DataFrame with normalized charter status.
    """
    result = df.copy()
    if charter_col not in result.columns:
        return result

    raw_charter = result[charter_col].astype(str).str.strip().str.lower()
    is_charter_bool = pd.Series(np.nan, index=result.index, dtype="object")

    is_charter_bool[raw_charter.isin(["yes", "1", "true"])] = True
    is_charter_bool[raw_charter.isin(["no", "0", "false"])] = False

    result[charter_col] = is_charter_bool
    return result


def enforce_column_types(
    df: pd.DataFrame,
    type_specs: dict[str, Any],
) -> pd.DataFrame:
    """Coerce DataFrame columns into explicit target data types.

    Args:
        df: Input DataFrame.
        type_specs: Mapping of column names to target pandas/python types.

    Returns:
        DataFrame with enforced column types.
    """
    result = df.copy()
    for col, target_type in type_specs.items():
        if col not in result.columns:
            continue

        if target_type in ("string", str):
            result[col] = result[col].astype("string")
        elif target_type in ("integer_or_null", "Int64"):
            result[col] = pd.to_numeric(result[col], errors="coerce").astype("Int64")
        elif target_type in ("float_or_null", "float", float):
            result[col] = pd.to_numeric(result[col], errors="coerce").astype(float)
        elif target_type in ("bool", bool):
            result[col] = result[col].astype(bool)

    return result
