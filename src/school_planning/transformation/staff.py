"""Staff (059) transformation module for analytical panel preparation."""

from pathlib import Path

import pandas as pd

from school_planning.cleaning.cleaning_pipeline import clean_staff_dataframe
from school_planning.ingestion.source_adapters import load_staff_component


def transform_staff(
    source: Path | str | pd.DataFrame,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Transform and normalize Staff source into analytical component.

    Implements strict missing-value handling, zero-teacher anomaly preservation,
    and sentinel negative code coercion.

    Args:
        source: Path to raw CSV file or loaded DataFrame.
        duplicate_policy: Duplicate handling policy ('fail', 'drop').

    Returns:
        Standardized, cleaned Staff DataFrame at [school_id, school_year] grain.
    """
    if isinstance(source, (str, Path)):
        df = load_staff_component(source, apply_rename=True)
    else:
        df = source.copy()

    clean_df = clean_staff_dataframe(df, duplicate_policy=duplicate_policy)
    return clean_df
