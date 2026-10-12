"""Peer-group segmentation, stratum classification, and P90 baseline calculation.

Adheres strictly to config/project.yaml and config/kpi_definitions.yaml:
- Operational cohort contract: Only active institutions (school_status in ['Open', 'New'],
  is_operational == True) form the benchmark baseline sample and are evaluated for Priority 2.
- Structural peer group eligibility: school_type == 'Regular School' AND school_level in ['Elementary', 'Middle', 'High'].
- Full benchmark eligibility (is_p90_eligible): Requires BOTH structural eligibility AND active operational status.
- Non-operational ('Closed', 'Inactive', 'Future') and transition-review ('Added', 'Changed Boundary/Agency', 'Reopened')
  schools bypass Priority 2 and are preserved in the full panel for administrative review (is_above_p90_ratio == False).
- Strict catch-all unbenchmarked rule: any other level (Secondary, Other, Adult Ed, Not applicable, Not reported, etc.)
  or non-regular school type is classified as 'Unbenchmarked / Specialized Peer Group'.
- Stratification: ['school_year', 'school_level']
- In the absence of statutory standards, unbenchmarked populations bypass P90 evaluation; no arbitrary thresholds are invented.
"""

from typing import Any

import numpy as np
import pandas as pd

ELIGIBLE_SCHOOL_TYPE = "Regular School"
ELIGIBLE_SCHOOL_LEVELS = {"Elementary", "Middle", "High"}

# Operational status contracts per config/project.yaml
ACTIVE_STATUSES = {"Open", "New"}
TRANSITION_REVIEW_STATUSES = {"Added", "Changed Boundary/Agency", "Reopened"}
INACTIVE_STATUSES = {"Closed", "Inactive", "Future"}

BENCHMARKED_STATUS_LABEL = "Benchmarked (Regular School P90)"
UNBENCHMARKED_STATUS_LABEL = "Unbenchmarked / Specialized Peer Group"
NON_OPERATIONAL_STATUS_LABEL = "Non-Operational / Status Review"


def classify_peer_group_eligibility(
    df: pd.DataFrame,
    school_type_col: str = "school_type",
    school_level_col: str = "school_level",
    operational_col: str = "is_operational",
    status_col: str = "school_status",
) -> pd.DataFrame:
    """Classify institutions into eligible P90 benchmarked pools vs unbenchmarked peer groups.

    Distinguishes structural eligibility (school type and level) from operational eligibility
    (Open/New active status per config/project.yaml).

    Args:
        df: Input DataFrame containing school characteristics.
        school_type_col: Column containing school type (e.g. 'Regular School').
        school_level_col: Column containing instructional level.
        operational_col: Column containing boolean operational flag.
        status_col: Column containing school status text category.

    Returns:
        DataFrame augmented with:
          - is_structurally_eligible: Boolean flag (Regular School + Elementary/Middle/High).
          - is_operational: Boolean flag (active cohort Open/New, excluding transition review).
          - is_p90_eligible: Boolean flag (both structurally eligible AND operational).
          - peer_group_status: Orthogonal classification label.
          - peer_group_stratum: Stratum key (e.g. 'Elementary') for eligible schools, else 'Unbenchmarked'.
    """
    res = df.copy()

    type_series = res[school_type_col].astype(str).str.strip() if school_type_col in res.columns else pd.Series("", index=res.index)
    level_series = res[school_level_col].astype(str).str.strip() if school_level_col in res.columns else pd.Series("", index=res.index)

    # 1. Structural eligibility: Regular School and standard grade spans
    is_regular = type_series == ELIGIBLE_SCHOOL_TYPE
    is_standard_level = level_series.isin(ELIGIBLE_SCHOOL_LEVELS)
    is_structurally_eligible = is_regular & is_standard_level

    # 2. Operational eligibility: Active-only cohort ('Open', 'New') per config/project.yaml
    if operational_col in res.columns:
        is_operational = res[operational_col].fillna(False).astype(bool)
    elif status_col in res.columns:
        is_operational = res[status_col].astype(str).str.strip().isin(ACTIVE_STATUSES)
    else:
        is_operational = pd.Series(True, index=res.index)

    # Transition-review statuses are placed in explicit administrative review bucket and are not operational
    if status_col in res.columns:
        is_transition = res[status_col].astype(str).str.strip().isin(TRANSITION_REVIEW_STATUSES)
        is_operational = is_operational & (~is_transition)

    # 3. P90 baseline & evaluation eligibility requires BOTH structural and operational eligibility
    is_p90_eligible = is_structurally_eligible & is_operational

    res["is_structurally_eligible"] = is_structurally_eligible
    res["is_operational"] = is_operational
    res["is_p90_eligible"] = is_p90_eligible

    # Peer group status label:
    # - If eligible operational school -> Benchmarked (Regular School P90)
    # - If non-operational / transition review -> Non-Operational / Status Review (when operational/status info present)
    # - If operational but non-eligible structure -> Unbenchmarked / Specialized Peer Group
    if operational_col in res.columns or status_col in res.columns:
        status_conditions = [
            is_p90_eligible,
            ~is_operational,
        ]
        status_choices = [
            BENCHMARKED_STATUS_LABEL,
            NON_OPERATIONAL_STATUS_LABEL,
        ]
        res["peer_group_status"] = np.select(status_conditions, status_choices, default=UNBENCHMARKED_STATUS_LABEL)
    else:
        # Backward compatibility for inputs lacking operational status columns
        res["peer_group_status"] = np.where(
            is_structurally_eligible,
            BENCHMARKED_STATUS_LABEL,
            UNBENCHMARKED_STATUS_LABEL,
        )

    res["peer_group_stratum"] = np.where(
        is_p90_eligible,
        level_series,
        "Unbenchmarked",
    )

    return res


def compute_peer_group_p90_thresholds(
    df: pd.DataFrame,
    ratio_col: str = "student_teacher_ratio",
    year_col: str = "school_year",
    level_col: str = "school_level",
    type_col: str = "school_type",
    operational_col: str = "is_operational",
    status_col: str = "school_status",
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Calculate empirical P90 ratio thresholds per (school_year, school_level) stratum.

    Only active operational Regular Elementary/Middle/High schools with valid ratios (>= 0.0)
    are included in threshold computation. Full panel records are preserved. Non-operational
    and transition-review schools do not influence thresholds and are never flagged as above-P90.

    Args:
        df: Input panel DataFrame.
        ratio_col: Student-to-teacher ratio column.
        year_col: School year column.
        level_col: School level column.
        type_col: School type column.
        operational_col: Operational flag column.
        status_col: School status column.

    Returns:
        Tuple of:
          - DataFrame augmented with `peer_group_p90_ratio` and `is_above_p90_ratio`.
          - Dictionary of stratum metadata (count, p90 value, min, max, median).
    """
    classified = classify_peer_group_eligibility(
        df,
        school_type_col=type_col,
        school_level_col=level_col,
        operational_col=operational_col,
        status_col=status_col,
    )

    # Only eligible active operational Regular Elementary/Middle/High schools with valid non-negative ratios (>= 0.0)
    # are included in the baseline threshold computation per KPI contract.
    eligible_mask = (
        classified["is_p90_eligible"]
        & classified[ratio_col].notna()
        & (classified[ratio_col] >= 0.0)
    )

    eligible_df = classified[eligible_mask]

    thresholds_dict: dict[str, dict[str, Any]] = {}

    # Calculate P90 per (school_year, school_level) on the operational benchmark cohort
    grouped = eligible_df.groupby([year_col, level_col])

    stratum_p90_map: dict[tuple[str, str], float] = {}

    for (yr, lvl), group in grouped:
        ratios = group[ratio_col].dropna()
        if not ratios.empty:
            p90_val = float(ratios.quantile(0.90))
            stratum_p90_map[(str(yr), str(lvl))] = p90_val

            key = f"{yr}_{lvl}"
            thresholds_dict[key] = {
                "school_year": str(yr),
                "school_level": str(lvl),
                "sample_size": len(ratios),
                "p90_ratio": round(p90_val, 2),
                "median_ratio": round(float(ratios.median()), 2),
                "mean_ratio": round(float(ratios.mean()), 2),
                "p10_ratio": round(float(ratios.quantile(0.10)), 2),
            }

    # Map P90 back to dataframe (strictly for is_p90_eligible records)
    def _lookup_p90(row: pd.Series) -> float:
        if not row["is_p90_eligible"]:
            return np.nan
        key = (str(row[year_col]), str(row[level_col]))
        return stratum_p90_map.get(key, np.nan)

    classified["peer_group_p90_ratio"] = classified.apply(_lookup_p90, axis=1)

    # Boolean flag: meets or exceeds peer-group P90 (inclusive per Priority 2 contract)
    # Requires is_p90_eligible (active operational + structurally eligible).
    # Non-operational and transition-review schools are NEVER flagged as above P90.
    valid_comparison = (
        classified["is_p90_eligible"]
        & classified[ratio_col].notna()
        & classified["peer_group_p90_ratio"].notna()
    )
    classified["is_above_p90_ratio"] = np.where(
        valid_comparison,
        classified[ratio_col] >= classified["peer_group_p90_ratio"],
        False,
    )

    return classified, thresholds_dict
