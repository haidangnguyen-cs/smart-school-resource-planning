"""Schema, column presence, and data type validation."""

from typing import Any

import pandas as pd


def validate_dataframe_schema(
    df: pd.DataFrame,
    required_columns: list[str],
    expected_types: dict[str, str | type] | None = None,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """Validate DataFrame column presence and basic data types.

    Args:
        df: Input DataFrame.
        required_columns: Mandatory columns that must exist.
        expected_types: Optional mapping of column names to expected types ('string', 'numeric').
        raise_on_error: Whether to raise ValueError on fatal schema violations.

    Returns:
        Structured dictionary reporting validation outcome, missing columns, and errors.
    """
    missing = [c for c in required_columns if c not in df.columns]
    errors = []
    warnings = []
    type_mismatches = []

    if missing:
        errors.append(f"Missing mandatory columns: {missing}")

    if expected_types:
        for col, exp_type in expected_types.items():
            if col not in df.columns:
                continue
            series = df[col]
            if exp_type in ("string", str):
                # Verify non-null values are strings or object dtype
                if not (pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)):
                    type_mismatches.append(f"{col}: expected string, got {series.dtype}")
            elif exp_type in ("numeric", float, int) and not pd.api.types.is_numeric_dtype(series):
                type_mismatches.append(f"{col}: expected numeric, got {series.dtype}")

    if type_mismatches:
        errors.extend(type_mismatches)

    valid = len(errors) == 0

    if not valid and raise_on_error:
        raise ValueError(f"Schema validation failed: {'; '.join(errors)}")

    return {
        "valid": valid,
        "missing_columns": missing,
        "type_mismatches": type_mismatches,
        "errors": errors,
        "warnings": warnings,
        "total_columns": len(df.columns),
        "total_rows": len(df),
    }
