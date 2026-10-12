"""Descriptive statistical profiling, distribution analysis, and aggregations.

Provides distribution summaries, state-level aggregations, missingness profiling,
and category breakdowns for the analytical school-year panel.
"""

from typing import Any

import numpy as np
import pandas as pd


def summarize_distributions(
    df: pd.DataFrame,
    metric_cols: list[str] | None = None,
    operational_only: bool = True,
    operational_col: str = "is_operational",
) -> pd.DataFrame:
    """Compute detailed distribution metrics across continuous variables.

    Calculates: count, missing_count, missing_pct, mean, std, min, p10, p25,
    median (p50), p75, p90, max, IQR.

    Args:
        df: Input panel DataFrame.
        metric_cols: Columns to profile. Defaults to core numeric metrics.
        operational_only: If True and operational_col is present, profile only active operational schools.
        operational_col: Column containing boolean operational flag.

    Returns:
        Summary DataFrame indexed by metric name.
    """
    data = df
    if operational_only and operational_col in df.columns:
        data = df[df[operational_col].fillna(False).astype(bool)]

    if metric_cols is None:
        metric_cols = [
            "total_students",
            "teacher_fte",
            "student_teacher_ratio",
            "enrollment_growth_yoy_pct",
            "teacher_fte_growth_yoy_pct",
            "ratio_growth_yoy_pct",
            "growth_gap_pct_points",
        ]

    rows = []
    total_len = len(data)

    for col in metric_cols:
        if col not in data.columns:
            continue

        series = pd.to_numeric(data[col], errors="coerce").dropna()
        n_missing = int(data[col].isna().sum())
        missing_pct = round((n_missing / total_len * 100), 2) if total_len > 0 else 0.0

        if series.empty:
            rows.append(
                {
                    "metric": col,
                    "count": 0,
                    "missing_count": n_missing,
                    "missing_pct": missing_pct,
                    "mean": np.nan,
                    "std": np.nan,
                    "min": np.nan,
                    "p10": np.nan,
                    "p25": np.nan,
                    "median": np.nan,
                    "p75": np.nan,
                    "p90": np.nan,
                    "max": np.nan,
                    "iqr": np.nan,
                }
            )
            continue

        q25 = float(series.quantile(0.25))
        q75 = float(series.quantile(0.75))

        rows.append(
            {
                "metric": col,
                "count": len(series),
                "missing_count": n_missing,
                "missing_pct": missing_pct,
                "mean": round(float(series.mean()), 2),
                "std": round(float(series.std()), 2),
                "min": round(float(series.min()), 2),
                "p10": round(float(series.quantile(0.10)), 2),
                "p25": round(q25, 2),
                "median": round(float(series.median()), 2),
                "p75": round(q75, 2),
                "p90": round(float(series.quantile(0.90)), 2),
                "max": round(float(series.max()), 2),
                "iqr": round(q75 - q25, 2),
            }
        )

    return pd.DataFrame(rows).set_index("metric") if rows else pd.DataFrame()


def summarize_by_category(
    df: pd.DataFrame,
    category_col: str,
    metrics: list[str] | None = None,
    year_col: str | None = "school_year",
    operational_only: bool = True,
    operational_col: str = "is_operational",
) -> pd.DataFrame:
    """Summarize counts and key metric medians/means by a categorical dimension.

    Produces summaries grouped by both school_year (if present) and category_col,
    so annual comparisons remain interpretable and school_count has a clear per-year meaning.

    Args:
        df: Input panel DataFrame.
        category_col: Categorical column to segment by.
        metrics: Continuous metric columns to summarize.
        year_col: School year column. If present in df, grouping includes school_year.
        operational_only: If True and operational_col is present, summarize operational schools.
        operational_col: Column containing boolean operational flag.

    Returns:
        DataFrame with summary statistics grouped by [school_year, category_col] (or [category_col]).
    """
    data = df
    if operational_only and operational_col in df.columns:
        data = df[df[operational_col].fillna(False).astype(bool)]

    if metrics is None:
        metrics = ["total_students", "teacher_fte", "student_teacher_ratio"]

    available_metrics = [m for m in metrics if m in data.columns]

    agg_dict: dict[str, Any] = {"school_id": "count"}
    for m in available_metrics:
        agg_dict[m] = ["median", "mean"]

    if year_col and year_col in data.columns and category_col != year_col:
        group_cols = [year_col, category_col]
    else:
        group_cols = [category_col]

    grouped = data.groupby(group_cols, dropna=False).agg(agg_dict)
    # Flatten multi-level columns
    grouped.columns = ["_".join(c).strip("_") for c in grouped.columns.values]
    grouped = grouped.rename(columns={"school_id_count": "school_count"})
    return grouped.reset_index().sort_values(group_cols).reset_index(drop=True)


def summarize_state_aggregates(
    df: pd.DataFrame,
    state_col: str = "state_fips",
    year_col: str = "school_year",
    operational_only: bool = True,
    operational_col: str = "is_operational",
) -> pd.DataFrame:
    """Compute aggregate state-level totals and weighted staffing ratios.

    Aggregate Student-to-Teacher Ratio is calculated as:
      sum(total_students) / sum(teacher_fte)
    which represents the state-wide system resource allocation.
    """
    data = df
    if operational_only and operational_col in df.columns:
        data = df[df[operational_col].fillna(False).astype(bool)]

    grouped = (
        data.groupby([state_col, year_col], dropna=False)
        .agg(
            school_count=("school_id", "count"),
            total_students=("total_students", "sum"),
            total_teacher_fte=("teacher_fte", "sum"),
            median_school_ratio=("student_teacher_ratio", "median"),
        )
        .reset_index()
        .sort_values([state_col, year_col])
        .reset_index(drop=True)
    )

    grouped["system_student_teacher_ratio"] = np.where(
        grouped["total_teacher_fte"] > 0,
        grouped["total_students"] / grouped["total_teacher_fte"],
        np.nan,
    )
    grouped["system_student_teacher_ratio"] = grouped["system_student_teacher_ratio"].round(2)
    return grouped
