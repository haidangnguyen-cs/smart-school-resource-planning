"""Directory (029) transformation module for analytical panel preparation."""

from pathlib import Path

import pandas as pd

from school_planning.cleaning.cleaning_pipeline import clean_directory_dataframe
from school_planning.ingestion.source_adapters import load_directory_component


def transform_directory(
    source: Path | str | pd.DataFrame,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Transform and normalize Directory source into analytical component.

    Args:
        source: Path to raw CSV file or loaded DataFrame.
        duplicate_policy: Duplicate handling policy ('fail', 'drop').

    Returns:
        Standardized, cleaned Directory DataFrame at [school_id, school_year] grain.
    """
    if isinstance(source, (str, Path)):
        df = load_directory_component(source, apply_rename=True)
    else:
        df = source.copy()

    clean_df = clean_directory_dataframe(df, duplicate_policy=duplicate_policy)
    return clean_df
