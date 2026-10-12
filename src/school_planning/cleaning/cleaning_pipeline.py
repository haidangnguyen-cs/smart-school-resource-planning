"""Coordinated cleaning pipeline applying contract normalization rules."""

import logging
from typing import Any

import pandas as pd

from school_planning.cleaning.duplicates import resolve_duplicates
from school_planning.cleaning.identifiers import normalize_identifiers_dataframe
from school_planning.cleaning.missing_values import clean_student_count, clean_teacher_fte
from school_planning.cleaning.normalization import (
    classify_operational_status,
    normalize_charter_status,
    strip_whitespace,
)

logger = logging.getLogger(__name__)


def clean_directory_dataframe(
    df: pd.DataFrame,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Clean and normalize school directory (029) component.

    Args:
        df: Input DataFrame with Directory data.
        duplicate_policy: Policy for handling duplicate keys ('fail', 'drop').

    Returns:
        Cleaned Directory DataFrame.
    """
    clean_df = df.copy()
    clean_df = strip_whitespace(clean_df)
    clean_df = normalize_identifiers_dataframe(clean_df)
    clean_df = classify_operational_status(clean_df)
    clean_df = normalize_charter_status(clean_df)

    if "school_id" in clean_df.columns and "school_year" in clean_df.columns:
        clean_df = resolve_duplicates(
            clean_df,
            subset=["school_id", "school_year"],
            policy=duplicate_policy,
        )

    return clean_df


def clean_membership_dataframe(
    df: pd.DataFrame,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Clean and normalize student membership (052) component.

    Args:
        df: Input DataFrame with Membership data.
        duplicate_policy: Policy for handling duplicate keys ('fail', 'drop').

    Returns:
        Cleaned Membership DataFrame.
    """
    clean_df = df.copy()
    clean_df = strip_whitespace(clean_df)
    clean_df = normalize_identifiers_dataframe(clean_df)
    clean_df = clean_student_count(clean_df)

    if "school_id" in clean_df.columns and "school_year" in clean_df.columns:
        clean_df = resolve_duplicates(
            clean_df,
            subset=["school_id", "school_year"],
            policy=duplicate_policy,
        )

    return clean_df


def clean_staff_dataframe(
    df: pd.DataFrame,
    duplicate_policy: str = "fail",
) -> pd.DataFrame:
    """Clean and normalize staff FTE (059) component.

    Args:
        df: Input DataFrame with Staff data.
        duplicate_policy: Policy for handling duplicate keys ('fail', 'drop').

    Returns:
        Cleaned Staff DataFrame.
    """
    clean_df = df.copy()
    clean_df = strip_whitespace(clean_df)
    clean_df = normalize_identifiers_dataframe(clean_df)
    clean_df = clean_teacher_fte(clean_df)

    if "school_id" in clean_df.columns and "school_year" in clean_df.columns:
        clean_df = resolve_duplicates(
            clean_df,
            subset=["school_id", "school_year"],
            policy=duplicate_policy,
        )

    return clean_df


def clean_component(
    df: pd.DataFrame,
    component: str,
    duplicate_policy: str = "fail",
    **kwargs: Any,
) -> pd.DataFrame:
    """Route DataFrame through component-specific cleaning pipeline.

    Args:
        df: Input DataFrame.
        component: Name of the component ('directory', 'membership', 'staff').
        duplicate_policy: Duplicate handling policy ('fail', 'drop').
        **kwargs: Additional options.

    Returns:
        Cleaned DataFrame.
    """
    comp_norm = component.lower()
    if comp_norm in ("directory", "029"):
        return clean_directory_dataframe(df, duplicate_policy=duplicate_policy)
    if comp_norm in ("membership", "052"):
        return clean_membership_dataframe(df, duplicate_policy=duplicate_policy)
    if comp_norm in ("staff", "059"):
        return clean_staff_dataframe(df, duplicate_policy=duplicate_policy)

    raise ValueError(f"Unknown component type for cleaning: {component}")
