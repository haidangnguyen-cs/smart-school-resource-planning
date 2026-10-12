"""Core Key Performance Indicator (KPI) formulas and computations.

Adheres strictly to config/kpi_definitions.yaml and the project data contract:
- student_teacher_ratio: total_students / teacher_fte when teacher_fte > 0.0
- Zero denominator handling: sets ratio to NaN when teacher_fte == 0.0 or zero_teacher_anomaly is True
- Caveat: student_teacher_ratio measures high-level staffing allocation, NOT class size.
- growth_gap_pct_points: enrollment_growth_yoy_pct - teacher_fte_growth_yoy_pct
"""

import numpy as np
import pandas as pd


def compute_student_teacher_ratio(
    df: pd.DataFrame,
    students_col: str = "total_students",
    teachers_col: str = "teacher_fte",
    flag_col: str = "teacher_data_flag",
    anomaly_col: str = "zero_teacher_anomaly",
) -> pd.Series:
    """Compute Student-to-Teacher Ratio with explicit zero-denominator and anomaly handling.

    Formula: total_students / teacher_fte
    Eligibility:
      - total_students is not null and >= 0
      - teacher_fte is not null and > 0.0
      - teacher_data_flag == 'Reported' (if flag column present)
      - zero_teacher_anomaly is False (if anomaly column present)

    Args:
        df: Input DataFrame containing student and teacher counts.
        students_col: Name of column containing student enrollment headcount.
        teachers_col: Name of column containing teacher FTE.
        flag_col: Optional column indicating teacher reporting status ('Reported').
        anomaly_col: Optional boolean column indicating zero-teacher anomalies.

    Returns:
        pd.Series of float ratio values with invalid/zero cases coerced to NaN.
    """
    students = (
        pd.to_numeric(df[students_col], errors="coerce")
        if students_col in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    teachers = (
        pd.to_numeric(df[teachers_col], errors="coerce")
        if teachers_col in df.columns
        else pd.Series(np.nan, index=df.index)
    )

    # Valid mask
    valid_students = students.notna() & (students >= 0)
    valid_teachers = teachers.notna() & (teachers > 0.0)

    # Respect teacher_data_flag if present
    if flag_col in df.columns:
        valid_flag = df[flag_col].astype(str).str.strip().str.lower() == "reported"
        valid_teachers = valid_teachers & valid_flag

    # Respect zero_teacher_anomaly if present
    if anomaly_col in df.columns:
        not_anomalous = ~df[anomaly_col].fillna(False).astype(bool)
        valid_teachers = valid_teachers & not_anomalous

    eligible_mask = valid_students & valid_teachers

    ratio = pd.Series(np.nan, index=df.index, dtype="float64")
    ratio.loc[eligible_mask] = students.loc[eligible_mask] / teachers.loc[eligible_mask]
    return ratio


def compute_growth_gap(
    enrollment_growth: pd.Series,
    teacher_growth: pd.Series,
) -> pd.Series:
    """Compute Enrollment-Staffing Growth Gap in percentage points.

    Formula: enrollment_growth_yoy_pct - teacher_fte_growth_yoy_pct
    Interpretation:
      - Positive gap: enrollment outgrowing staffing (increasing resource pressure).
      - Negative gap: staffing expanding faster than enrollment.
      - NaN if either growth rate is null or uncomputable.

    Args:
        enrollment_growth: Series of YoY enrollment growth percentages.
        teacher_growth: Series of YoY teacher FTE growth percentages.

    Returns:
        pd.Series of percentage point difference values.
    """
    eg = pd.to_numeric(enrollment_growth, errors="coerce")
    tg = pd.to_numeric(teacher_growth, errors="coerce")
    return eg - tg


def calculate_school_kpis(
    df: pd.DataFrame,
    students_col: str = "total_students",
    teachers_col: str = "teacher_fte",
    flag_col: str = "teacher_data_flag",
    anomaly_col: str = "zero_teacher_anomaly",
) -> pd.DataFrame:
    """Calculate core cross-sectional KPIs on an analytical DataFrame.

    Adds:
      - student_teacher_ratio: Headcount per teacher FTE.

    Args:
        df: Input DataFrame.
        students_col: Name of student count column.
        teachers_col: Name of teacher count column.
        flag_col: Name of reporting flag column.
        anomaly_col: Name of zero-teacher anomaly column.

    Returns:
        DataFrame with added KPI columns.
    """
    result = df.copy()
    result["student_teacher_ratio"] = compute_student_teacher_ratio(
        result,
        students_col=students_col,
        teachers_col=teachers_col,
        flag_col=flag_col,
        anomaly_col=anomaly_col,
    )
    return result
