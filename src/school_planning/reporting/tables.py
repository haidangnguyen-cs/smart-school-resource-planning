"""tables.py - Formatted presentation and summary tables for management and technical reporting.

Provides standard formatting routines for:
  - Longitudinal KPI summaries (enrollment, staffing, ratios, growth)
  - Multi-tier resource pressure classification summaries
  - State-level operational and triage summaries
  - Walk-forward backtesting model comparison tables
  - Retrospective 2023-24 scenario projection tables
  - Markdown table serializers
"""

from typing import Any

import numpy as np
import pandas as pd


def dataframe_to_markdown(
    df: pd.DataFrame,
    headers: list[str] | None = None,
    align: list[str] | None = None,
) -> str:
    """Serialize a DataFrame to standard GitHub-flavored Markdown table format.

    Args:
        df: Input DataFrame.
        headers: Optional custom header titles.
        align: Optional column alignments ('left', 'center', 'right').

    Returns:
        Formatted markdown table string.
    """
    if df.empty:
        return "*No data available.*"

    col_names = list(headers) if headers is not None else [str(c) for c in df.columns]
    num_cols = len(col_names)

    # Format cell values cleanly
    formatted_rows: list[list[str]] = []
    for _, row in df.iterrows():
        row_cells = []
        for val in row:
            if pd.isna(val):
                row_cells.append("—")
            elif isinstance(val, float):
                row_cells.append(f"{val:,.2f}" if abs(val) < 1000 else f"{val:,.1f}")
            elif isinstance(val, (int, np.integer)):
                row_cells.append(f"{val:,}")
            else:
                row_cells.append(str(val))
        formatted_rows.append(row_cells)

    # Alignments
    if align is None:
        align_markers = [":---" if i == 0 else "---:" for i in range(num_cols)]
    else:
        align_map = {"left": ":---", "center": ":---:", "right": "---:"}
        align_markers = [align_map.get(a.lower(), "---:") for a in align]

    header_line = "| " + " | ".join(col_names) + " |"
    separator_line = "| " + " | ".join(align_markers) + " |"
    data_lines = ["| " + " | ".join(r) + " |" for r in formatted_rows]

    return "\n".join([header_line, separator_line] + data_lines)


def format_kpi_summary_table(
    panel_df: pd.DataFrame,
    operational_only: bool | None = None,
) -> pd.DataFrame:
    """Format longitudinal system KPI summary table across school years.

    Calculates operational school counts, total students, total teacher FTE,
    weighted ratio, and year-over-year growths.

    Args:
        panel_df: Longitudinal school-year analytical panel.
        operational_only: Whether to restrict to operational facilities. If None,
            preserves the existing operational status filter on panel_df.

    Returns:
        Formatted DataFrame with columns ready for reporting.
    """
    df = panel_df.copy()
    if operational_only is True and "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]
    elif operational_only is None and "is_operational" in df.columns:
        # Default behavior: filter operational only if not already filtered
        df = df[df["is_operational"].fillna(False).astype(bool)]

    records: list[dict[str, Any]] = []
    years = sorted(df["school_year"].unique())

    prev_enrollment = None
    prev_teachers = None

    for yr in years:
        yr_df = df[df["school_year"] == yr]
        total_facilities = len(yr_df)
        if "is_operational" in yr_df.columns:
            op_mask = yr_df["is_operational"].fillna(False).astype(bool)
            operational_schools = int(op_mask.sum())
        else:
            operational_schools = total_facilities

        # Use sum(min_count=1) to preserve all-missing as NaN, while preserving legitimate observed 0.0
        raw_students = (
            yr_df["total_students"].sum(min_count=1)
            if "total_students" in yr_df.columns
            else np.nan
        )
        raw_teachers = (
            yr_df["teacher_fte"].sum(min_count=1) if "teacher_fte" in yr_df.columns else np.nan
        )

        students_sum = float(raw_students) if pd.notna(raw_students) else np.nan
        teachers_sum = float(raw_teachers) if pd.notna(raw_teachers) else np.nan

        weighted_ratio = (
            round(students_sum / teachers_sum, 2)
            if pd.notna(students_sum) and pd.notna(teachers_sum) and teachers_sum > 0
            else np.nan
        )

        enrollment_growth = (
            round(((students_sum - prev_enrollment) / prev_enrollment) * 100.0, 2)
            if pd.notna(students_sum)
            and prev_enrollment is not None
            and pd.notna(prev_enrollment)
            and prev_enrollment > 0
            else np.nan
        )

        teacher_growth = (
            round(((teachers_sum - prev_teachers) / prev_teachers) * 100.0, 2)
            if pd.notna(teachers_sum)
            and prev_teachers is not None
            and pd.notna(prev_teachers)
            and prev_teachers > 0
            else np.nan
        )

        prev_enrollment = students_sum
        prev_teachers = teachers_sum

        rec = {
            "school_year": yr,
            "operational_schools": operational_schools,
        }
        if operational_only is False:
            rec["all_facilities"] = total_facilities
        rec.update(
            {
                "total_enrollment": students_sum,
                "total_teacher_fte": teachers_sum,
                "weighted_ratio": weighted_ratio,
                "enrollment_yoy_growth_pct": enrollment_growth,
                "teacher_yoy_growth_pct": teacher_growth,
            }
        )
        records.append(rec)

    return pd.DataFrame(records)


def format_resource_pressure_tier_table(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    operational_only: bool | None = None,
) -> pd.DataFrame:
    """Format resource pressure tier breakdown table for the specified school year.

    Resource pressure tiers are strictly evaluated on the operational cohort.

    Args:
        panel_df: Panel with resource pressure columns (e.g. priority_tier, tier_label).
        school_year: Target evaluation year (default: '2022-23').
        operational_only: Parameter retained for interface consistency; operational
            filtering is strictly enforced on tier metrics regardless of selection.

    Returns:
        Summary DataFrame per priority tier with counts and operational shares.
    """
    df = panel_df[panel_df["school_year"] == school_year].copy()
    if "is_operational" in df.columns:
        operational_df = df[df["is_operational"].fillna(False).astype(bool)]
    else:
        operational_df = df

    tier_descriptions = {
        1: "Data quality & administrative review (boundary changes, anomalies, missing FTE)",
        2: "Extreme resource pressure (peers >= P90 threshold, regular schools)",
        3: "Rapid ratio escalation (annual ratio growth >= threshold tau_rise)",
        4: "Divergent growth gap (enrollment growing faster than staffing >= tau_gap)",
        5: "Unassessed longitudinal growth (new, boundary changed, or baseline missing)",
        6: "Stable / balanced baseline trend (normal variation; not verified staffing adequacy)",
    }

    tier_labels = {
        1: "Priority 1: Administrative Review",
        2: "Priority 2: Extreme Pressure (P90)",
        3: "Priority 3: Rapid Ratio Rise",
        4: "Priority 4: Growth Gap",
        5: "Priority 5: Unassessed Growth",
        6: "Priority 6: Stable / Balanced",
    }

    total_op = len(operational_df)
    tier_col = (
        "resource_pressure_priority"
        if "resource_pressure_priority" in operational_df.columns
        else ("priority_tier" if "priority_tier" in operational_df.columns else None)
    )
    tier_counts = operational_df[tier_col].value_counts().to_dict() if tier_col else {}

    records: list[dict[str, Any]] = []
    for tier in range(1, 7):
        cnt = tier_counts.get(tier, 0)
        pct = round((cnt / total_op) * 100.0, 2) if total_op > 0 else 0.0
        records.append(
            {
                "tier_number": tier,
                "tier_label": tier_labels.get(tier, f"Priority {tier}"),
                "school_count": cnt,
                "operational_pct": pct,
                "description": tier_descriptions.get(tier, ""),
            }
        )

    return pd.DataFrame(records)


def format_state_summary_table(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    operational_only: bool | None = None,
) -> pd.DataFrame:
    """Format state-level summary table with operational counts, ratios, and triage tiers.

    Args:
        panel_df: School-year analytical panel.
        school_year: Target school year.
        operational_only: Whether to restrict to operational facilities. If False,
            preserves all facilities while keeping operational metrics distinct.

    Returns:
        State aggregate summary DataFrame sorted by total enrollment descending.
    """
    df = panel_df[panel_df["school_year"] == school_year].copy()
    if operational_only is True and "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]
    elif operational_only is False:
        pass
    elif "is_operational" in df.columns:
        # Default: if caller has not explicitly pre-filtered, use operational
        df = df[df["is_operational"].fillna(False).astype(bool)]

    state_col = "state_fips" if "state_fips" in df.columns else "state_name"
    display_col = "state_name" if "state_name" in df.columns else state_col

    records: list[dict[str, Any]] = []

    for state_val, grp in df.groupby(state_col):
        disp_name = (
            grp[display_col].dropna().iloc[0]
            if display_col in grp.columns and len(grp[display_col].dropna()) > 0
            else str(state_val)
        )
        total_facilities = len(grp)
        if "is_operational" in grp.columns:
            op_mask = grp["is_operational"].fillna(False).astype(bool)
            op_schools = int(op_mask.sum())
            grp_op = grp[op_mask]
        else:
            op_schools = total_facilities
            grp_op = grp

        # Use sum(min_count=1) to preserve all-missing as NaN, while preserving legitimate observed 0.0
        raw_students = (
            grp["total_students"].sum(min_count=1) if "total_students" in grp.columns else np.nan
        )
        raw_teachers = (
            grp["teacher_fte"].sum(min_count=1) if "teacher_fte" in grp.columns else np.nan
        )

        tot_students = float(raw_students) if pd.notna(raw_students) else np.nan
        tot_teachers = float(raw_teachers) if pd.notna(raw_teachers) else np.nan
        ratio = (
            round(tot_students / tot_teachers, 2)
            if pd.notna(tot_students) and pd.notna(tot_teachers) and tot_teachers > 0
            else np.nan
        )

        tier_col = (
            "resource_pressure_priority"
            if "resource_pressure_priority" in grp_op.columns
            else ("priority_tier" if "priority_tier" in grp_op.columns else None)
        )
        # Priority triage counts must be evaluated strictly on the operational cohort:
        p1_cnt = int((grp_op[tier_col] == 1).sum()) if tier_col else 0
        p2_cnt = int((grp_op[tier_col] == 2).sum()) if tier_col else 0
        p3_cnt = int((grp_op[tier_col] == 3).sum()) if tier_col else 0
        p4_cnt = int((grp_op[tier_col] == 4).sum()) if tier_col else 0

        action_required = p1_cnt + p2_cnt + p3_cnt + p4_cnt

        rec = {
            "state_fips": str(state_val),
            "state_name": disp_name,
            "operational_schools": op_schools,
        }
        if operational_only is False:
            rec["all_facilities"] = total_facilities
        rec.update(
            {
                "total_students": tot_students,
                "total_teacher_fte": tot_teachers,
                "student_teacher_ratio": ratio,
                "priority_1_review": p1_cnt,
                "priority_2_p90": p2_cnt,
                "priority_3_rising": p3_cnt,
                "priority_4_gap": p4_cnt,
                "total_triage_flagged": action_required,
            }
        )
        records.append(rec)

    res = pd.DataFrame(records)
    if not res.empty:
        res = res.sort_values("total_students", ascending=False, na_position="last").reset_index(
            drop=True
        )
    return res


def format_backtest_comparison_table(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Format backtest model comparison table with error metrics.

    Args:
        summary_df: Summary DataFrame produced by run_walk_forward_backtest().

    Returns:
        Formatted comparison table.
    """
    df = summary_df.copy()
    model_labels = {
        "naive_persistence": "Naive Persistence (y_t)",
        "drift": "Linear Drift (Trend)",
        "moving_average_3yr": "3-Year Moving Average",
    }
    df["model_display"] = df["model_name"].map(model_labels).fillna(df["model_name"])

    cols_order = [
        "fold_id",
        "target_col",
        "model_display",
        "n_observations",
        "wape",
        "mae",
        "rmse",
        "min_coverage_pct",
        "median_coverage_pct",
    ]
    present_cols = [c for c in cols_order if c in df.columns]
    return df[present_cols].copy()


def format_projection_scenario_table(
    projections_df: pd.DataFrame,
    top_n: int | None = None,
) -> pd.DataFrame:
    """Format retrospective scenario projections table.

    Args:
        projections_df: DataFrame from generate_projection_scenarios() / estimate_implied_staffing_demand().
        top_n: Optional limit to top N entities by baseline enrollment.

    Returns:
        Formatted table suitable for display and reporting.
    """
    df = projections_df.copy()

    # Sort by baseline projection descending
    if "baseline_projection" in df.columns:
        df = df.sort_values("baseline_projection", ascending=False)
    if top_n is not None:
        df = df.head(top_n)

    keep_cols = [
        "state_fips",
        "state_name",
        "latest_historical_value",
        "baseline_projection",
        "scenario_low_contraction_minus_2pct",
        "scenario_high_expansion_plus_2pct",
        "latest_historical_teacher_fte",
        "implied_teacher_fte_constant_ratio",
        "implied_teacher_fte_policy_target",
        "is_latest_year_valid",
    ]
    present_cols = [c for c in keep_cols if c in df.columns]
    return df[present_cols].reset_index(drop=True)
