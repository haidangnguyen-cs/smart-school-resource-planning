"""Primary and composite key constraint validation."""

from typing import Any

import pandas as pd


def validate_key_uniqueness(
    df: pd.DataFrame,
    key_cols: list[str],
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """Validate that key_cols uniquely identify rows and have zero nulls.

    Args:
        df: Input DataFrame.
        key_cols: Column or list of columns forming the composite primary key.
        raise_on_error: Whether to raise ValueError on fatal duplicate keys.

    Returns:
        Structured audit dictionary reporting key validity, duplicates, and null keys.
    """
    missing_cols = [col for col in key_cols if col not in df.columns]
    if missing_cols:
        if raise_on_error:
            raise KeyError(f"Key column(s) {missing_cols} missing from DataFrame columns.")
        return {
            "valid": False,
            "key_columns": key_cols,
            "total_rows": len(df),
            "unique_keys_count": 0,
            "null_key_rows": 0,
            "null_keys_count": 0,
            "duplicate_rows_count": 0,
            "errors": [f"Key column(s) {missing_cols} missing from DataFrame columns."],
            "sample_duplicates": [],
        }

    total_rows = len(df)
    null_key_rows = int(df[key_cols].isna().any(axis=1).sum())

    duplicated_mask = df.duplicated(subset=key_cols, keep=False)
    duplicate_rows_count = int(duplicated_mask.sum())
    unique_keys_count = int(df.drop_duplicates(subset=key_cols).shape[0])

    errors = []
    if null_key_rows > 0:
        errors.append(f"{null_key_rows} rows contain null values in primary key columns {key_cols}")

    if duplicate_rows_count > 0:
        errors.append(
            f"Found {duplicate_rows_count} duplicate rows violating primary key uniqueness on {key_cols}"
        )

    valid = (null_key_rows == 0) and (duplicate_rows_count == 0)

    if not valid and raise_on_error:
        raise ValueError(f"Key validation failed: {'; '.join(errors)}")

    sample_duplicates = []
    if duplicate_rows_count > 0:
        sample_duplicates = df[duplicated_mask][key_cols].head(10).to_dict(orient="records")

    return {
        "valid": valid,
        "key_columns": key_cols,
        "total_rows": total_rows,
        "unique_keys_count": unique_keys_count,
        "null_key_rows": null_key_rows,
        "null_keys_count": null_key_rows,
        "duplicate_rows_count": duplicate_rows_count,
        "errors": errors,
        "sample_duplicates": sample_duplicates,
    }
