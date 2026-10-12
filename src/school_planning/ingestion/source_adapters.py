"""Adapters for NCES CCD Directory (029), Membership (052), and Staff (059) components."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from school_planning.cleaning.identifiers import normalize_identifiers_dataframe
from school_planning.ingestion.readers import read_csv_robust, stream_csv_chunks

DEFAULT_ID_DTYPES = {
    "NCESSCH": str,
    "LEAID": str,
    "FIPST": str,
    "ST": str,
    "SCHID": str,
    "ST_SCHID": str,
    "SCHOOL_YEAR": str,
    "SY_STATUS": str,
    "SCH_TYPE": str,
}


def _load_column_mapping_config(mapping_path: Path | None = None) -> dict[str, Any]:
    """Load column mapping configuration file."""
    if mapping_path is None:
        # Default relative to package root
        mapping_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "column_mapping.yaml"
    if mapping_path.exists():
        with open(mapping_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _apply_mapping(df: pd.DataFrame, component_section: str, mapping_cfg: dict[str, Any] | None) -> pd.DataFrame:
    """Rename columns according to the component mapping configuration."""
    if not mapping_cfg:
        return df
    section = mapping_cfg.get(component_section, {})
    mappings = section.get("mappings", {})
    rename_dict = {}
    for raw_col, spec in mappings.items():
        target = spec.get("target")
        if target and raw_col in df.columns:
            rename_dict[raw_col] = target
    return df.rename(columns=rename_dict)


def load_directory_component(
    filepath: Path | str,
    mapping_cfg: dict[str, Any] | None = None,
    apply_rename: bool = True,
) -> pd.DataFrame:
    """Load and normalize Directory (029) component.

    Args:
        filepath: Path to the raw 029 CSV file.
        mapping_cfg: Optional column mapping configuration dict.
        apply_rename: Whether to rename columns to standardized internal names.

    Returns:
        pd.DataFrame with normalized identifiers and canonical school year.
    """
    df, _ = read_csv_robust(filepath, dtype=DEFAULT_ID_DTYPES)
    df = normalize_identifiers_dataframe(df)

    if apply_rename:
        if mapping_cfg is None:
            mapping_cfg = _load_column_mapping_config()
        df = _apply_mapping(df, "directory", mapping_cfg)

    return df


def load_membership_component(
    filepath: Path | str,
    indicator: str = "Derived - Education Unit Total minus Adult Education Count",
    primary_indicator: str | None = None,
    chunksize: int = 250_000,
    mapping_cfg: dict[str, Any] | None = None,
    apply_rename: bool = True,
) -> pd.DataFrame:
    """Load and normalize Membership (052) component using streaming chunk filtering.

    Filters strictly to the contracted total indicator to isolate the 1:1 school-year grain
    without memory exhaustion on large (~2.3 GB) multi-million row files.

    Args:
        filepath: Path to the raw 052 CSV file.
        indicator: Aggregation indicator to isolate (default primary contract indicator).
        primary_indicator: Optional alias for indicator.
        chunksize: Rows per chunk during streaming.
        mapping_cfg: Optional column mapping configuration dict.
        apply_rename: Whether to rename columns to standardized internal names.

    Returns:
        pd.DataFrame containing filtered school-level enrollment totals.
    """
    target_indicator = primary_indicator if primary_indicator is not None else indicator
    filtered_chunks = []
    for chunk in stream_csv_chunks(filepath, chunksize=chunksize, dtype=DEFAULT_ID_DTYPES):
        if "TOTAL_INDICATOR" not in chunk.columns:
            raise KeyError(
                f"Raw Membership source '{filepath}' missing required indicator column 'TOTAL_INDICATOR'."
            )
        match = chunk[chunk["TOTAL_INDICATOR"] == target_indicator]
        if not match.empty:
            filtered_chunks.append(match)

    if not filtered_chunks:
        df = pd.DataFrame()
    else:
        df = pd.concat(filtered_chunks, ignore_index=True)

    df = normalize_identifiers_dataframe(df)

    # Clean student count numeric values
    if "STUDENT_COUNT" in df.columns:
        # Convert non-numeric or negative values to NaN
        numeric_students = pd.to_numeric(df["STUDENT_COUNT"], errors="coerce")
        df["STUDENT_COUNT"] = np.where(numeric_students >= 0, numeric_students, np.nan)

    if apply_rename:
        if mapping_cfg is None:
            mapping_cfg = _load_column_mapping_config()
        df = _apply_mapping(df, "membership", mapping_cfg)

    return df


def load_staff_component(
    filepath: Path | str,
    mapping_cfg: dict[str, Any] | None = None,
    apply_rename: bool = True,
) -> pd.DataFrame:
    """Load and normalize Staff (059) component.

    Implements strict missing-value and zero-teacher anomaly policies:
    - Reported zeros (TEACHERS == 0.0 with DMS_FLAG == 'Reported') are retained with a flag.
    - Non-reported values (DMS_FLAG != 'Reported') or negative values are coerced to null (NaN).

    Args:
        filepath: Path to the raw 059 CSV file.
        mapping_cfg: Optional column mapping configuration dict.
        apply_rename: Whether to rename columns to standardized internal names.

    Returns:
        pd.DataFrame containing normalized staffing records.
    """
    df, _ = read_csv_robust(filepath, dtype=DEFAULT_ID_DTYPES)
    df = normalize_identifiers_dataframe(df)

    if "TEACHERS" in df.columns:
        # Convert raw to numeric float
        numeric_teachers = pd.to_numeric(df["TEACHERS"], errors="coerce")

        if "DMS_FLAG" in df.columns:
            # Determine reported status
            is_reported = df["DMS_FLAG"] == "Reported"
            # Initialize zero anomaly flag
            df["zero_teacher_anomaly"] = is_reported & (numeric_teachers == 0.0)
            # Enforce contract: non-reported or negative must be NaN
            valid_reported = is_reported & (numeric_teachers >= 0.0)
            df["TEACHERS"] = np.where(valid_reported, numeric_teachers, np.nan)
        else:
            df["zero_teacher_anomaly"] = numeric_teachers == 0.0
            df["TEACHERS"] = np.where(numeric_teachers >= 0.0, numeric_teachers, np.nan)

    if apply_rename:
        if mapping_cfg is None:
            mapping_cfg = _load_column_mapping_config()
        df = _apply_mapping(df, "staff", mapping_cfg)

    return df
