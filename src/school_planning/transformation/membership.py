"""Membership (052) transformation module for analytical panel preparation."""

from pathlib import Path

import pandas as pd

from school_planning.cleaning.cleaning_pipeline import clean_membership_dataframe
from school_planning.ingestion.source_adapters import load_membership_component

DEFAULT_PRIMARY_INDICATOR = "Derived - Education Unit Total minus Adult Education Count"


def transform_membership(
    source: Path | str | pd.DataFrame,
    indicator: str = DEFAULT_PRIMARY_INDICATOR,
    chunksize: int = 250_000,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Transform and normalize Membership source into analytical component.

    Filters strictly to the primary contract indicator to isolate the 1:1 school-year grain.

    Args:
        source: Path to raw CSV file or loaded DataFrame.
        indicator: Aggregation indicator to isolate (default primary contract indicator).
        chunksize: Streaming chunk size when reading from file.
        duplicate_policy: Duplicate handling policy ('fail', 'drop').

    Returns:
        Standardized, cleaned Membership DataFrame at [school_id, school_year] grain.
    """
    if isinstance(source, (str, Path)):
        df = load_membership_component(
            source,
            indicator=indicator,
            chunksize=chunksize,
            apply_rename=True,
        )
    else:
        df = source.copy()
        if "TOTAL_INDICATOR" in df.columns:
            df = df[df["TOTAL_INDICATOR"] == indicator].copy()
        elif "enrollment_total_indicator" in df.columns:
            df = df[df["enrollment_total_indicator"] == indicator].copy()
        else:
            raise KeyError(
                "Membership input DataFrame missing indicator column: neither "
                "'TOTAL_INDICATOR' nor 'enrollment_total_indicator' was found."
            )

    clean_df = clean_membership_dataframe(df, duplicate_policy=duplicate_policy)
    return clean_df
