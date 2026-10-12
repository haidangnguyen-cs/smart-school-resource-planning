"""Domain-specific business quality rules and anomaly detection."""

from typing import Any

import pandas as pd


def validate_teacher_fte_rules(df: pd.DataFrame) -> dict[str, Any]:
    """Validate teacher FTE missingness, reported zeros, and non-negativity.

    Adheres strictly to ADR-03:
    - Non-reported FTE (DMS_FLAG != 'Reported') must NOT be coerced to 0.0.
    - Reported 0.0 FTE must be identified and flagged as zero_teacher_anomaly.
    - All positive FTE values must be > 0.0.
    """
    errors = []
    warnings = []
    anomalies = {}

    fte_col = (
        "teacher_fte"
        if "teacher_fte" in df.columns
        else ("TEACHERS" if "TEACHERS" in df.columns else None)
    )
    flag_col = (
        "teacher_data_flag"
        if "teacher_data_flag" in df.columns
        else ("DMS_FLAG" if "DMS_FLAG" in df.columns else None)
    )

    if fte_col is None:
        return {"checked": False, "reason": "No teacher FTE column present"}

    # 1. Non-negativity check
    numeric_fte = pd.to_numeric(df[fte_col], errors="coerce")
    negatives = int((numeric_fte < 0.0).sum())
    if negatives > 0:
        errors.append(f"Found {negatives} records with negative teacher FTE.")

    # 2. Reported zero anomaly check
    if flag_col and flag_col in df.columns:
        is_reported = df[flag_col] == "Reported"
        reported_zeros = int((is_reported & (numeric_fte == 0.0)).sum())
        non_reported = int((~is_reported).sum())
        non_reported_zeros = int((~is_reported & (numeric_fte == 0.0)).sum())

        anomalies["reported_zeros_count"] = reported_zeros
        anomalies["non_reported_count"] = non_reported

        if non_reported_zeros > 0:
            errors.append(
                f"Found {non_reported_zeros} records where non-reported staff data was coerced to 0.0. "
                "Violates ADR-03: non-reported data must be represented as NaN."
            )
    else:
        reported_zeros = int((numeric_fte == 0.0).sum())
        anomalies["zeros_count"] = reported_zeros

    valid = len(errors) == 0
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "zero_teacher_count": reported_zeros,
        "anomalies": anomalies,
    }


def validate_student_enrollment_rules(df: pd.DataFrame) -> dict[str, Any]:
    """Validate enrollment non-negativity and indicator validity."""
    errors = []
    warnings = []

    enrollment_col = (
        "total_students"
        if "total_students" in df.columns
        else ("STUDENT_COUNT" if "STUDENT_COUNT" in df.columns else None)
    )

    if enrollment_col is None:
        return {"checked": False, "reason": "No student enrollment column present"}

    numeric_enrollment = pd.to_numeric(df[enrollment_col], errors="coerce")
    negatives = int((numeric_enrollment < 0).sum())
    if negatives > 0:
        errors.append(f"Found {negatives} records with negative student enrollment.")

    zeros = int((numeric_enrollment == 0).sum())
    missing = int(numeric_enrollment.isna().sum())

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "negative_enrollment_count": negatives,
        "zero_enrollment_count": zeros,
        "missing_enrollment_count": missing,
    }


def validate_status_scoping_rules(df: pd.DataFrame) -> dict[str, Any]:
    """Validate operational status distributions and verify transition statuses."""
    status_col = (
        "school_status"
        if "school_status" in df.columns
        else ("SY_STATUS_TEXT" if "SY_STATUS_TEXT" in df.columns else None)
    )
    if status_col is None:
        return {"checked": False, "reason": "No school status column present"}

    status_counts = df[status_col].value_counts(dropna=False).to_dict()

    transition_statuses = ["Added", "Changed Boundary/Agency", "Reopened"]
    transition_count = sum(status_counts.get(s, 0) for s in transition_statuses)

    return {
        "valid": True,
        "status_distribution": status_counts,
        "transition_review_count": transition_count,
    }


def validate_business_rules(df: pd.DataFrame) -> dict[str, Any]:
    """Execute all relevant business quality checks on a DataFrame."""
    teacher_check = validate_teacher_fte_rules(df)
    student_check = validate_student_enrollment_rules(df)
    status_check = validate_status_scoping_rules(df)

    all_errors = []
    for check in (teacher_check, student_check, status_check):
        if isinstance(check, dict) and check.get("errors"):
            all_errors.extend(check["errors"])

    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "teacher_checks": teacher_check,
        "student_checks": student_check,
        "status_checks": status_check,
    }
