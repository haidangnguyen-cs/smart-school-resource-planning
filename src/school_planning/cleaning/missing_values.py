"""Missing-value and sentinel code cleaning rules."""

from collections.abc import Sequence

import numpy as np
import pandas as pd


def coerce_sentinel_values(
    series: pd.Series,
    sentinels: Sequence[int | float] = (-1, -2, -1.0, -2.0),
) -> pd.Series:
    """Coerce NCES negative sentinel values to NaN.

    Args:
        series: Pandas Series containing numerical or object data.
        sentinels: Sequence of numeric values to replace with NaN. Default: (-1, -2).

    Returns:
        Series with sentinel values replaced by np.nan.
    """
    clean_series = series.copy()
    numeric_series = pd.to_numeric(clean_series, errors="coerce")
    is_sentinel = numeric_series.isin(sentinels) | (numeric_series < 0)
    clean_series[is_sentinel] = np.nan
    return clean_series


def clean_teacher_fte(
    df: pd.DataFrame,
    fte_col: str = "teacher_fte",
    flag_col: str = "teacher_data_flag",
    anomaly_col: str = "zero_teacher_anomaly",
) -> pd.DataFrame:
    """Clean teacher FTE according to NCES CCD quality contracts.

    Contract Rules:
    1. Negative sentinel values (-1, -2, < 0) coerced to NaN.
    2. Non-reported values (DMS_FLAG != 'Reported') coerced to NaN; NEVER treated as zero.
    3. Valid reported zero FTE (TEACHERS == 0.0 with DMS_FLAG == 'Reported') preserved,
       and flagged with zero_teacher_anomaly = True.
    4. Positive reported FTE flagged with zero_teacher_anomaly = False.

    Args:
        df: Input DataFrame containing staff data.
        fte_col: Column name for teacher FTE.
        flag_col: Column name for data missingness/suppression flag.
        anomaly_col: Target column name for zero-teacher anomaly flag.

    Returns:
        DataFrame with cleaned teacher FTE and anomaly flag.
    """
    result = df.copy()
    if fte_col not in result.columns:
        return result

    # Coerce to numeric float
    fte_numeric = pd.to_numeric(result[fte_col], errors="coerce")
    # Replace negative sentinels with NaN
    fte_numeric = coerce_sentinel_values(fte_numeric)

    # Flag-based rules if flag column is present
    if flag_col in result.columns:
        flag_series = result[flag_col].astype(str).str.strip()
        is_reported = flag_series == "Reported"
        # Non-reported rows must evaluate to NaN, never 0.0
        fte_numeric[~is_reported] = np.nan
    else:
        is_reported = pd.Series(True, index=result.index)

    result[fte_col] = fte_numeric

    # Zero-teacher anomaly flag
    is_zero = fte_numeric == 0.0
    result[anomaly_col] = (is_zero & is_reported).astype(bool)

    return result


def clean_student_count(
    df: pd.DataFrame,
    count_col: str = "total_students",
    flag_col: str = "enrollment_data_flag",
) -> pd.DataFrame:
    """Clean student enrollment count according to NCES CCD quality contracts.

    Contract Rules:
    1. Coerces non-numeric strings and negative values to NaN.
    2. Preserves valid integer student counts (>= 0).
    3. Preserves enrollment flag for data auditing.

    Args:
        df: Input DataFrame containing enrollment data.
        count_col: Column name for student count.
        flag_col: Column name for enrollment missingness flag.

    Returns:
        DataFrame with cleaned student enrollment count.
    """
    result = df.copy()
    if count_col not in result.columns:
        return result

    # Convert to numeric float/Int64
    count_numeric = pd.to_numeric(result[count_col], errors="coerce")
    count_numeric = coerce_sentinel_values(count_numeric)

    # Negative values are invalid for headcounts
    count_numeric[count_numeric < 0] = np.nan

    result[count_col] = count_numeric
    return result
