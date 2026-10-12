"""Key duplicate detection and resolution under documented quality rules."""

from collections.abc import Sequence

import pandas as pd


def detect_duplicates(
    df: pd.DataFrame,
    subset: Sequence[str] = ("school_id", "school_year"),
) -> pd.DataFrame:
    """Identify duplicate records based on primary key subset.

    Args:
        df: Input DataFrame.
        subset: Sequence of column names forming the primary key.

    Returns:
        DataFrame containing all duplicate rows (both original and copies).
    """
    key_cols = [c for c in subset if c in df.columns]
    if len(key_cols) != len(subset):
        missing = set(subset) - set(df.columns)
        raise KeyError(f"Missing key columns for duplicate detection: {missing}")

    return df[df.duplicated(subset=key_cols, keep=False)].copy()


def resolve_duplicates(
    df: pd.DataFrame,
    subset: Sequence[str] = ("school_id", "school_year"),
    policy: str = "fail",
    keep: str = "first",
) -> pd.DataFrame:
    """Enforce duplicate resolution policy under data contracts.

    Supported policies:
    - 'fail': Raise ValueError if duplicates exist (default).
    - 'drop': Drop duplicate records, keeping the designated instance ('first', 'last').
    - 'keep_first': Deterministic deduplication retaining the first row.

    Args:
        df: Input DataFrame.
        subset: Sequence of column names forming the key.
        policy: Duplicate handling policy ('fail', 'drop', 'keep_first').
        keep: Which duplicate to keep when dropping ('first', 'last').

    Returns:
        Deduplicated DataFrame.

    Raises:
        ValueError: If policy is 'fail' and duplicates are detected.
    """
    key_cols = [c for c in subset if c in df.columns]
    if len(key_cols) != len(subset):
        missing = set(subset) - set(df.columns)
        raise KeyError(f"Missing key columns for duplicate resolution: {missing}")

    dups = df.duplicated(subset=key_cols, keep=False)
    dup_count = dups.sum()

    if dup_count == 0:
        return df.copy()

    if policy == "fail":
        sample_dup_keys = df.loc[dups, key_cols].head(5).to_dict(orient="records")
        raise ValueError(
            f"Detected {dup_count} duplicate rows on key {list(subset)}. "
            f"Sample duplicate keys: {sample_dup_keys}"
        )

    if policy in ("drop", "keep_first"):
        keep_rule = "first" if policy == "keep_first" else keep
        return df.drop_duplicates(subset=key_cols, keep=keep_rule).copy()

    raise ValueError(f"Unknown duplicate resolution policy: {policy}")
