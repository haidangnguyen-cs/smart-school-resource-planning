"""Resource pressure analysis and hierarchical triage classification.

Adheres strictly to Section 3.5 of docs/PROJECT_PLAN.md and config/kpi_definitions.yaml:
- Hierarchical, mutually exclusive categorization evaluated in strict priority order:
    1. Priority 1: Incomplete Data or Status Review
       (missing data, non-reported flags, reported 0.0 FTE / zero_teacher_anomaly,
        non-operational records, or transition-review statuses: 'Added',
        'Changed Boundary/Agency', 'Reopened')
    2. Priority 2: High Current Ratio
       (complete operational data AND regular school AND elementary/middle/high AND ratio >= P90;
        ties handled with inclusive inequality; unbenchmarked populations bypass Priority 2)
    3. Priority 3: Rapidly Rising Ratio
       (complete data, not P2, valid consecutive-year growth metrics, ratio_growth_yoy_pct >= tau_ratio_rise)
    4. Priority 4: Staffing Growth Deficit
       (complete data, not P2, not P3, valid growth metrics, growth_gap_pct_points >= tau_growth_gap)
    5. Priority 5: Growth Unassessed / Incomplete Growth Data
       (complete data, not P2, but consecutive-year growth metrics cannot be calculated,
        e.g. base year, new schools, prior-year missing/zero data; prevents unassessed defaulting to Stable)
    6. Priority 6: Stable / Balanced
       (complete data, not P2, not P3, not P4, assessed growth within normal bounds.
        Critical caveat: for unbenchmarked institutions, Stable denotes solely trend stability,
        NOT verified staffing adequacy)
- Candidate thresholds (tau_ratio_rise, tau_growth_gap) are provisional parameters for
  decision-support prototyping, subject to stakeholder calibration.
- Orthogonal peer_group_status dimension is preserved alongside tier classification.
"""

from typing import Any

import numpy as np
import pandas as pd

from school_planning.analytics.segmentation import (
    TRANSITION_REVIEW_STATUSES,
    classify_peer_group_eligibility,
    compute_peer_group_p90_thresholds,
)

# Canonical tier labels per config/kpi_definitions.yaml
PRIORITY_1_LABEL = "Incomplete Data or Status Review"
PRIORITY_2_LABEL = "High Current Ratio"
PRIORITY_3_LABEL = "Rapidly Rising Ratio"
PRIORITY_4_LABEL = "Staffing Growth Deficit"
PRIORITY_5_LABEL = "Growth Unassessed / Incomplete Growth Data"
PRIORITY_6_LABEL = "Stable / Balanced"

PRIORITY_TIER_ORDER: list[str] = [
    PRIORITY_1_LABEL,
    PRIORITY_2_LABEL,
    PRIORITY_3_LABEL,
    PRIORITY_4_LABEL,
    PRIORITY_5_LABEL,
    PRIORITY_6_LABEL,
]

PRIORITY_TIER_TO_CODE: dict[str, int] = {
    PRIORITY_1_LABEL: 1,
    PRIORITY_2_LABEL: 2,
    PRIORITY_3_LABEL: 3,
    PRIORITY_4_LABEL: 4,
    PRIORITY_5_LABEL: 5,
    PRIORITY_6_LABEL: 6,
}

# Provisional candidate thresholds per config/kpi_definitions.yaml
DEFAULT_TAU_RATIO_RISE = 15.0  # +15.0% YoY ratio increase (provisional)
DEFAULT_TAU_GROWTH_GAP = 5.0  # +5.0 percentage points growth gap (provisional)


def classify_resource_pressure(
    df: pd.DataFrame,
    tau_ratio_rise: float = DEFAULT_TAU_RATIO_RISE,
    tau_growth_gap: float = DEFAULT_TAU_GROWTH_GAP,
    ratio_col: str = "student_teacher_ratio",
    students_col: str = "total_students",
    teachers_col: str = "teacher_fte",
    flag_col: str = "teacher_data_flag",
    operational_col: str = "is_operational",
    status_col: str = "school_status",
    type_col: str = "school_type",
    level_col: str = "school_level",
    year_col: str = "school_year",
    ratio_growth_col: str = "ratio_growth_yoy_pct",
    growth_gap_col: str = "growth_gap_pct_points",
    anomaly_col: str = "zero_teacher_anomaly",
    p90_col: str = "peer_group_p90_ratio",
    above_p90_col: str = "is_above_p90_ratio",
) -> pd.DataFrame:
    """Classify each facility into a hierarchical, mutually exclusive Resource Pressure category.

    Evaluated in strict priority order adhering to config/kpi_definitions.yaml:
      Priority 1: Incomplete Data or Status Review
      Priority 2: High Current Ratio
      Priority 3: Rapidly Rising Ratio
      Priority 4: Staffing Growth Deficit
      Priority 5: Growth Unassessed / Incomplete Growth Data
      Priority 6: Stable / Balanced

    Args:
        df: Input panel DataFrame (optionally pre-augmented with peer groups and growth).
        tau_ratio_rise: Provisional threshold for rapidly rising ratio (percent YoY).
        tau_growth_gap: Provisional threshold for enrollment-staffing growth gap (percentage points).
        ratio_col: Student-to-teacher ratio column.
        students_col: Student enrollment column.
        teachers_col: Teacher FTE column.
        flag_col: Teacher data flag column (e.g. 'Reported').
        operational_col: Boolean operational status column.
        status_col: School status string column.
        type_col: School type column.
        level_col: School level column.
        year_col: School year column.
        ratio_growth_col: YoY ratio growth column.
        growth_gap_col: Enrollment-staffing growth gap column.
        anomaly_col: Zero-teacher anomaly flag column.
        p90_col: Peer-group P90 ratio column (computed if missing).
        above_p90_col: Above-P90 boolean flag column (computed if missing).

    Returns:
        Augmented DataFrame with:
          - resource_pressure_tier: Canonical tier label (Priority 1 through 6).
          - resource_pressure_priority: Integer code (1 through 6).
          - peer_group_status: Orthogonal classification dimension.
          - has_valid_growth_metrics: Boolean flag for valid growth metrics.
          - tau_ratio_rise: Threshold applied.
          - tau_growth_gap: Threshold applied.
    """
    res = df.copy()

    # 1. Ensure peer group eligibility and P90 thresholds are present
    if above_p90_col not in res.columns or p90_col not in res.columns:
        res, _ = compute_peer_group_p90_thresholds(
            res,
            ratio_col=ratio_col,
            year_col=year_col,
            level_col=level_col,
            type_col=type_col,
            operational_col=operational_col,
            status_col=status_col,
        )
    elif "peer_group_status" not in res.columns:
        res = classify_peer_group_eligibility(
            res,
            school_type_col=type_col,
            school_level_col=level_col,
            operational_col=operational_col,
            status_col=status_col,
        )

    # 2. Evaluate Priority 1: Incomplete Data or Status Review
    # Conditions:
    # - total_students is null or < 0
    # - teacher_fte is null or < 0
    # - teacher_data_flag != 'Reported' (when flag column present)
    # - teacher_fte == 0.0 or zero_teacher_anomaly == True
    # - is_operational is False
    # - school_status in TRANSITION_REVIEW_STATUSES ('Added', 'Changed Boundary/Agency', 'Reopened')
    # - student_teacher_ratio is null or < 0.0 (valid zero ratio with positive FTE is not P1)
    students = pd.to_numeric(res[students_col], errors="coerce") if students_col in res.columns else pd.Series(np.nan, index=res.index)
    teachers = pd.to_numeric(res[teachers_col], errors="coerce") if teachers_col in res.columns else pd.Series(np.nan, index=res.index)
    ratios = pd.to_numeric(res[ratio_col], errors="coerce") if ratio_col in res.columns else pd.Series(np.nan, index=res.index)

    missing_students = students.isna() | (students < 0)
    missing_teachers = teachers.isna() | (teachers < 0)
    zero_teachers = (teachers == 0.0)

    if anomaly_col in res.columns:
        zero_teachers = zero_teachers | res[anomaly_col].fillna(False).astype(bool)

    non_reported_flag = pd.Series(False, index=res.index)
    if flag_col in res.columns:
        non_reported_flag = res[flag_col].fillna("").astype(str).str.strip() != "Reported"

    not_operational = pd.Series(False, index=res.index)
    if operational_col in res.columns:
        not_operational = ~res[operational_col].fillna(False).astype(bool)

    is_transition_status = pd.Series(False, index=res.index)
    if status_col in res.columns:
        is_transition_status = res[status_col].astype(str).str.strip().isin(TRANSITION_REVIEW_STATUSES)

    missing_or_invalid_ratio = ratios.isna() | (ratios < 0.0)

    is_p1 = (
        missing_students
        | missing_teachers
        | non_reported_flag
        | zero_teachers
        | not_operational
        | is_transition_status
        | missing_or_invalid_ratio
    )

    # 3. Evaluate Priority 2: High Current Ratio
    # Complete operational data AND is_above_p90_ratio is True
    # Note: is_above_p90_ratio already requires is_p90_eligible (Regular School + Elementary/Middle/High + Operational)
    is_above_p90 = res[above_p90_col].fillna(False).astype(bool) if above_p90_col in res.columns else pd.Series(False, index=res.index)
    is_p2 = (~is_p1) & is_above_p90

    # 4. Evaluate Growth Metrics Availability
    # Both ratio growth and growth gap must be valid non-null numbers
    ratio_growth = pd.to_numeric(res[ratio_growth_col], errors="coerce") if ratio_growth_col in res.columns else pd.Series(np.nan, index=res.index)
    growth_gap = pd.to_numeric(res[growth_gap_col], errors="coerce") if growth_gap_col in res.columns else pd.Series(np.nan, index=res.index)

    has_valid_growth = ratio_growth.notna() & growth_gap.notna()
    res["has_valid_growth_metrics"] = has_valid_growth

    # 5. Evaluate Priority 3: Rapidly Rising Ratio
    # Complete data, not P2, has valid growth metrics, and ratio_growth_yoy_pct >= tau_ratio_rise
    is_p3 = (~is_p1) & (~is_p2) & has_valid_growth & (ratio_growth >= tau_ratio_rise)

    # 6. Evaluate Priority 4: Staffing Growth Deficit
    # Complete data, not P2, not P3, has valid growth metrics, and growth_gap_pct_points >= tau_growth_gap
    is_p4 = (~is_p1) & (~is_p2) & (~is_p3) & has_valid_growth & (growth_gap >= tau_growth_gap)

    # 7. Evaluate Priority 5: Growth Unassessed / Incomplete Growth Data
    # Complete data, not P2, but consecutive-year growth metrics cannot be calculated
    is_p5 = (~is_p1) & (~is_p2) & (~has_valid_growth)

    # 8. Evaluate Priority 6: Stable / Balanced
    # Complete data, not P2, not P3, not P4, and growth is assessed within normal bounds
    is_p6 = (~is_p1) & (~is_p2) & (~is_p3) & (~is_p4) & has_valid_growth & (ratio_growth < tau_ratio_rise) & (growth_gap < tau_growth_gap)

    # Deterministic assignment using np.select
    tier_conditions = [is_p1, is_p2, is_p3, is_p4, is_p5, is_p6]
    tier_labels = [
        PRIORITY_1_LABEL,
        PRIORITY_2_LABEL,
        PRIORITY_3_LABEL,
        PRIORITY_4_LABEL,
        PRIORITY_5_LABEL,
        PRIORITY_6_LABEL,
    ]
    priority_codes = [1, 2, 3, 4, 5, 6]

    res["resource_pressure_tier"] = np.select(tier_conditions, tier_labels, default=PRIORITY_1_LABEL)
    res["resource_pressure_priority"] = np.select(tier_conditions, priority_codes, default=1).astype(int)

    # Record provisional thresholds used for auditability
    res["tau_ratio_rise"] = tau_ratio_rise
    res["tau_growth_gap"] = tau_growth_gap

    return res


def summarize_resource_pressure_tiers(
    df: pd.DataFrame,
    year_col: str = "school_year",
    tier_col: str = "resource_pressure_tier",
    priority_col: str = "resource_pressure_priority",
    ratio_col: str = "student_teacher_ratio",
    ratio_growth_col: str = "ratio_growth_yoy_pct",
    growth_gap_col: str = "growth_gap_pct_points",
    school_id_col: str = "school_id",
    operational_col: str = "is_operational",
) -> pd.DataFrame:
    """Produce structured summary of resource pressure tier counts and metrics.

    Computes:
      - Observation counts per tier and school year
      - Operational observation counts per tier (intersection of tier and operational mask)
      - Share of total panel records
      - Share of active operational cohort records
      - Unique school IDs observed per tier
      - Median staffing ratio, median ratio growth, and median growth gap

    Args:
        df: Classified DataFrame with resource_pressure_tier.
        year_col: School year column.
        tier_col: Resource pressure tier column.
        priority_col: Resource pressure priority code column.
        ratio_col: Ratio column.
        ratio_growth_col: Ratio growth column.
        growth_gap_col: Growth gap column.
        school_id_col: School ID column.
        operational_col: Operational flag column.

    Returns:
        Summary DataFrame sorted by [school_year, resource_pressure_priority].
    """
    rows: list[dict[str, Any]] = []

    years = sorted(df[year_col].dropna().unique().tolist()) if year_col in df.columns else ["All"]

    for yr in years:
        sub = df[df[year_col] == yr] if year_col in df.columns else df
        tot_records = len(sub)

        op_mask = sub[operational_col].fillna(False).astype(bool) if operational_col in sub.columns else pd.Series(True, index=sub.index)
        tot_op_records = int(op_mask.sum())

        for tier in PRIORITY_TIER_ORDER:
            tier_mask = sub[tier_col] == tier
            cnt = int(tier_mask.sum())
            if cnt == 0 and tot_records == 0:
                continue

            tier_sub = sub[tier_mask]
            op_tier_mask = tier_mask & op_mask
            op_cnt = int(op_tier_mask.sum())

            pct_panel = round(cnt / tot_records * 100, 2) if tot_records > 0 else 0.0
            pct_op = round(op_cnt / tot_op_records * 100, 2) if tot_op_records > 0 else 0.0

            unique_schools = int(tier_sub[school_id_col].nunique()) if school_id_col in tier_sub.columns else cnt

            valid_ratios = tier_sub[ratio_col].dropna() if ratio_col in tier_sub.columns else pd.Series(dtype=float)
            med_ratio = round(float(valid_ratios.median()), 2) if not valid_ratios.empty else np.nan

            valid_rg = tier_sub[ratio_growth_col].dropna() if ratio_growth_col in tier_sub.columns else pd.Series(dtype=float)
            med_rg = round(float(valid_rg.median()), 2) if not valid_rg.empty else np.nan

            valid_gg = tier_sub[growth_gap_col].dropna() if growth_gap_col in tier_sub.columns else pd.Series(dtype=float)
            med_gg = round(float(valid_gg.median()), 2) if not valid_gg.empty else np.nan

            rows.append({
                "school_year": yr,
                "resource_pressure_priority": PRIORITY_TIER_TO_CODE.get(tier, 0),
                "resource_pressure_tier": tier,
                "observation_count": cnt,
                "operational_observation_count": op_cnt,
                "pct_of_panel": pct_panel,
                "pct_of_operational": pct_op,
                "unique_schools_count": unique_schools,
                "median_student_teacher_ratio": med_ratio,
                "median_ratio_growth_pct": med_rg,
                "median_growth_gap_pp": med_gg,
            })

    res_df = pd.DataFrame(rows)
    if not res_df.empty and "school_year" in res_df.columns and "resource_pressure_priority" in res_df.columns:
        res_df = res_df.sort_values(["school_year", "resource_pressure_priority"]).reset_index(drop=True)
    return res_df


def summarize_resource_pressure_by_state(
    df: pd.DataFrame,
    state_col: str = "state_fips",
    year_col: str = "school_year",
    tier_col: str = "resource_pressure_tier",
    operational_col: str = "is_operational",
) -> pd.DataFrame:
    """Summarize tier distribution across geographic states.

    Args:
        df: Classified DataFrame with resource_pressure_tier.
        state_col: State column name (e.g. 'state_fips' or 'state_code').
        year_col: School year column.
        tier_col: Resource pressure tier column.
        operational_col: Operational flag column.

    Returns:
        DataFrame with state-level tier counts and operational proportions.
    """
    if state_col not in df.columns:
        return pd.DataFrame()

    group_cols = [state_col]
    if year_col in df.columns:
        group_cols.append(year_col)

    grouped = df.groupby(group_cols)
    rows: list[dict[str, Any]] = []

    for name, group in grouped:
        st = name[0] if isinstance(name, tuple) else name
        yr = name[1] if isinstance(name, tuple) and len(name) > 1 else "All"

        tot = len(group)
        op_cnt = int(group[operational_col].fillna(False).astype(bool).sum()) if operational_col in group.columns else tot

        row_data: dict[str, Any] = {
            state_col: st,
            "school_year": yr,
            "total_records": tot,
            "operational_records": op_cnt,
        }

        # Counts for each priority tier
        for code, label in enumerate(PRIORITY_TIER_ORDER, start=1):
            tier_cnt = int((group[tier_col] == label).sum())
            row_data[f"p{code}_count"] = tier_cnt
            row_data[f"p{code}_pct"] = round(tier_cnt / tot * 100, 2) if tot > 0 else 0.0

        rows.append(row_data)

    res_df = pd.DataFrame(rows)
    if not res_df.empty:
        sort_cols = [c for c in ["school_year", state_col] if c in res_df.columns]
        if sort_cols:
            res_df = res_df.sort_values(sort_cols).reset_index(drop=True)
    return res_df


def summarize_resource_pressure_by_level(
    df: pd.DataFrame,
    level_col: str = "school_level",
    year_col: str = "school_year",
    tier_col: str = "resource_pressure_tier",
) -> pd.DataFrame:
    """Summarize tier distribution across instructional school levels.

    Args:
        df: Classified DataFrame with resource_pressure_tier.
        level_col: School level column.
        year_col: School year column.
        tier_col: Resource pressure tier column.

    Returns:
        DataFrame with level-level tier counts.
    """
    if level_col not in df.columns:
        return pd.DataFrame()

    group_cols = [level_col]
    if year_col in df.columns:
        group_cols.append(year_col)

    grouped = df.groupby(group_cols)
    rows: list[dict[str, Any]] = []

    for name, group in grouped:
        lvl = name[0] if isinstance(name, tuple) else name
        yr = name[1] if isinstance(name, tuple) and len(name) > 1 else "All"
        tot = len(group)

        row_data: dict[str, Any] = {
            level_col: lvl,
            "school_year": yr,
            "total_records": tot,
        }

        for code, label in enumerate(PRIORITY_TIER_ORDER, start=1):
            tier_cnt = int((group[tier_col] == label).sum())
            row_data[f"p{code}_count"] = tier_cnt
            row_data[f"p{code}_pct"] = round(tier_cnt / tot * 100, 2) if tot > 0 else 0.0

        rows.append(row_data)

    res_df = pd.DataFrame(rows)
    if not res_df.empty:
        sort_cols = [c for c in ["school_year", level_col] if c in res_df.columns]
        if sort_cols:
            res_df = res_df.sort_values(sort_cols).reset_index(drop=True)
    return res_df


def extract_triage_queue(
    df: pd.DataFrame,
    priority: int | None = None,
    school_year: str | None = None,
) -> pd.DataFrame:
    """Extract prioritized action queue for decision-makers and administrative review.

    Args:
        df: Classified panel DataFrame.
        priority: Optional integer code (1 through 6) to filter to a specific queue.
        school_year: Optional school year filter string.

    Returns:
        DataFrame containing key triage attributes sorted by priority and ratio.
    """
    queue_cols = [
        "school_id",
        "school_year",
        "school_name",
        "state_fips",
        "district_id",
        "school_type",
        "school_level",
        "school_status",
        "is_operational",
        "peer_group_status",
        "student_teacher_ratio",
        "peer_group_p90_ratio",
        "ratio_growth_yoy_pct",
        "growth_gap_pct_points",
        "resource_pressure_priority",
        "resource_pressure_tier",
    ]
    present_cols = [c for c in queue_cols if c in df.columns]
    res = df[present_cols].copy()

    if school_year is not None and "school_year" in res.columns:
        res = res[res["school_year"] == school_year]

    if priority is not None and "resource_pressure_priority" in res.columns:
        res = res[res["resource_pressure_priority"] == priority]

    # Sort deterministically
    sort_cols = []
    ascending_list = []
    if "resource_pressure_priority" in res.columns:
        sort_cols.append("resource_pressure_priority")
        ascending_list.append(True)
    if "student_teacher_ratio" in res.columns:
        sort_cols.append("student_teacher_ratio")
        ascending_list.append(False)  # Highest ratio first within priority
    if "school_id" in res.columns:
        sort_cols.append("school_id")
        ascending_list.append(True)

    if sort_cols:
        res = res.sort_values(sort_cols, ascending=ascending_list).reset_index(drop=True)

    return res
