"""Longitudinal growth calculations across common-school cohorts.

Adheres strictly to config/kpi_definitions.yaml:
- enrollment_growth_yoy_pct: ((students[t] - students[t-1]) / students[t-1]) * 100
- teacher_fte_growth_yoy_pct: ((teachers[t] - teachers[t-1]) / teachers[t-1]) * 100
- ratio_growth_yoy_pct: ((ratio[t] - ratio[t-1]) / ratio[t-1]) * 100
- growth_gap_pct_points: enrollment_growth_yoy_pct - teacher_fte_growth_yoy_pct
- Zero denominator handling: yields NaN if prior-year denominator <= 0 or missing
- Common-school cohort rule: growth rates require consecutive presence of the same school_id
"""

import numpy as np
import pandas as pd

from school_planning.analytics.kpis import compute_growth_gap, compute_student_teacher_ratio


def compute_longitudinal_growth(
    panel_df: pd.DataFrame,
    school_id_col: str = "school_id",
    year_col: str = "school_year",
    students_col: str = "total_students",
    teachers_col: str = "teacher_fte",
    ratio_col: str = "student_teacher_ratio",
    operational_col: str = "is_operational",
    status_col: str = "school_status",
) -> pd.DataFrame:
    """Compute YoY longitudinal growth metrics on an analytical panel.

    Sorts by [school_id, school_year], computes lagged values per school, and
    calculates percentage changes for enrollment, staffing, and ratio.
    When operational status is present, growth metrics are computed only if both
    the current and immediately preceding consecutive records are active/operational.

    Args:
        panel_df: Consolidated panel DataFrame.
        school_id_col: School identifier column name.
        year_col: School year column name (e.g. '2018-19').
        students_col: Student headcount column name.
        teachers_col: Teacher FTE column name.
        ratio_col: Staffing ratio column name (computed if not present).
        operational_col: Column indicating operational status (bool).
        status_col: Column containing status text (e.g. 'Open', 'Closed').

    Returns:
        DataFrame augmented with lagged values and YoY growth rates:
          - prior_school_year
          - prior_total_students
          - prior_teacher_fte
          - prior_student_teacher_ratio
          - prior_is_operational (if operational column present)
          - enrollment_growth_yoy_pct
          - teacher_fte_growth_yoy_pct
          - ratio_growth_yoy_pct
          - growth_gap_pct_points
    """
    df = panel_df.copy()

    # Ensure ratio is present
    if ratio_col not in df.columns:
        df[ratio_col] = compute_student_teacher_ratio(
            df,
            students_col=students_col,
            teachers_col=teachers_col,
        )

    # Sort deterministically by school_id and school_year
    df = df.sort_values([school_id_col, year_col]).reset_index(drop=True)

    # Group by school_id and shift by 1 period
    grouped = df.groupby(school_id_col)

    df["prior_school_year"] = grouped[year_col].shift(1)
    df["prior_total_students"] = grouped[students_col].shift(1)
    df["prior_teacher_fte"] = grouped[teachers_col].shift(1)
    df["prior_student_teacher_ratio"] = grouped[ratio_col].shift(1)

    # Operational continuity check
    if operational_col in df.columns:
        df["prior_is_operational"] = grouped[operational_col].shift(1)
        curr_op = df[operational_col].fillna(False).astype(bool)
        prior_op = df["prior_is_operational"].fillna(False).astype(bool)
        operational_continuous = curr_op & prior_op
    elif status_col in df.columns:
        is_op = df[status_col].astype(str).str.strip().isin({"Open", "New"})
        curr_op = is_op
        prior_status = grouped[status_col].shift(1)
        prior_op = prior_status.astype(str).str.strip().isin({"Open", "New"})
        operational_continuous = curr_op & prior_op
    else:
        operational_continuous = pd.Series(True, index=df.index)

    # Determine whether consecutive year (e.g., 2018-19 -> 2019-20)
    # A gap in years would mean YoY is uncomputable
    is_consecutive = df.apply(
        lambda row: _are_years_consecutive(row["prior_school_year"], row[year_col]),
        axis=1,
    )

    # 1. Enrollment YoY Growth Rate
    curr_students = pd.to_numeric(df[students_col], errors="coerce")
    prior_students = pd.to_numeric(df["prior_total_students"], errors="coerce")

    valid_enroll_growth = (
        is_consecutive
        & operational_continuous
        & curr_students.notna()
        & prior_students.notna()
        & (prior_students > 0)
    )
    df["enrollment_growth_yoy_pct"] = np.where(
        valid_enroll_growth,
        ((curr_students - prior_students) / prior_students) * 100.0,
        np.nan,
    )

    # 2. Teacher FTE YoY Growth Rate
    curr_teachers = pd.to_numeric(df[teachers_col], errors="coerce")
    prior_teachers = pd.to_numeric(df["prior_teacher_fte"], errors="coerce")

    valid_teacher_growth = (
        is_consecutive
        & operational_continuous
        & curr_teachers.notna()
        & prior_teachers.notna()
        & (prior_teachers > 0.0)
    )
    df["teacher_fte_growth_yoy_pct"] = np.where(
        valid_teacher_growth,
        ((curr_teachers - prior_teachers) / prior_teachers) * 100.0,
        np.nan,
    )

    # 3. Ratio YoY Growth Rate
    curr_ratio = pd.to_numeric(df[ratio_col], errors="coerce")
    prior_ratio = pd.to_numeric(df["prior_student_teacher_ratio"], errors="coerce")

    valid_ratio_growth = (
        is_consecutive
        & operational_continuous
        & curr_ratio.notna()
        & prior_ratio.notna()
        & (prior_ratio > 0.0)
    )
    df["ratio_growth_yoy_pct"] = np.where(
        valid_ratio_growth,
        ((curr_ratio - prior_ratio) / prior_ratio) * 100.0,
        np.nan,
    )

    # 4. Growth Gap (Percentage Points)
    df["growth_gap_pct_points"] = compute_growth_gap(
        df["enrollment_growth_yoy_pct"],
        df["teacher_fte_growth_yoy_pct"],
    )

    return df


def _are_years_consecutive(prior_yr: str | None, curr_yr: str) -> bool:
    """Check if two school-year strings in YYYY-YY format represent consecutive years."""
    if not prior_yr or not isinstance(prior_yr, str) or len(prior_yr) != 7:
        return False
    if not curr_yr or not isinstance(curr_yr, str) or len(curr_yr) != 7:
        return False
    try:
        prior_start = int(prior_yr[:4])
        curr_start = int(curr_yr[:4])
        return curr_start - prior_start == 1
    except ValueError:
        return False
