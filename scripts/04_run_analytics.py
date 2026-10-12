#!/usr/bin/env python3
"""04_run_analytics.py - Run EDA profiling and calculate core KPIs on the analytical panel.

Generates:
1. Augmented analytical panel with KPIs, growth rates, and peer-group P90 classifications.
2. Distribution summaries and categorical breakdowns saved to outputs/tables/.
3. Structured EDA insights report saved to outputs/reports/eda_summary.json.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from school_planning.analytics import (
    BENCHMARKED_STATUS_LABEL,
    DEFAULT_TAU_GROWTH_GAP,
    DEFAULT_TAU_RATIO_RISE,
    NON_OPERATIONAL_STATUS_LABEL,
    PRIORITY_1_LABEL,
    PRIORITY_2_LABEL,
    PRIORITY_3_LABEL,
    PRIORITY_4_LABEL,
    PRIORITY_5_LABEL,
    PRIORITY_6_LABEL,
    UNBENCHMARKED_STATUS_LABEL,
    calculate_school_kpis,
    classify_resource_pressure,
    compute_longitudinal_growth,
    compute_peer_group_p90_thresholds,
    extract_triage_queue,
    summarize_by_category,
    summarize_distributions,
    summarize_resource_pressure_by_level,
    summarize_resource_pressure_by_state,
    summarize_resource_pressure_tiers,
    summarize_state_aggregates,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("04_run_analytics")


def run_analytics_pipeline(
    panel_path: Path | None = None,
    tables_dir: Path | None = None,
    reports_dir: Path | None = None,
    augmented_panel_path: Path | None = None,
    tau_ratio_rise: float = DEFAULT_TAU_RATIO_RISE,
    tau_growth_gap: float = DEFAULT_TAU_GROWTH_GAP,
) -> dict:
    """Execute complete analytics pipeline on the school-year panel.

    Args:
        panel_path: Path to input school_year_panel.parquet.
        tables_dir: Destination directory for summary CSV tables.
        reports_dir: Destination directory for JSON summary reports.
        augmented_panel_path: Destination path for augmented analytical panel.
        tau_ratio_rise: Provisional threshold for rapidly rising ratio (percent YoY).
        tau_growth_gap: Provisional threshold for enrollment-staffing growth gap (percentage points).

    Returns:
        Structured dictionary of EDA summary metrics and empirical findings.
    """
    if panel_path is None:
        panel_path = PROJECT_ROOT / "data" / "processed" / "school_year_panel.parquet"

    if tables_dir is None:
        tables_dir = PROJECT_ROOT / "outputs" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    if reports_dir is None:
        reports_dir = PROJECT_ROOT / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not panel_path.exists():
        raise FileNotFoundError(f"Processed analytical panel not found at {panel_path}. Run 03_build_panel.py first.")

    logger.info("Loading analytical panel from %s...", panel_path)
    df = pd.read_parquet(panel_path)
    total_records = len(df)
    logger.info("Loaded %d records across %d schools.", total_records, df["school_id"].nunique())

    start_time = time.time()

    # 1. Compute core cross-sectional KPIs
    logger.info("Calculating core cross-sectional KPIs...")
    df = calculate_school_kpis(df)

    # 2. Compute longitudinal growth metrics
    logger.info("Computing longitudinal YoY growth across common-school cohorts...")
    df = compute_longitudinal_growth(df)

    # 3. Classify peer groups and calculate empirical P90 thresholds on operational cohort
    logger.info("Calculating empirical peer-group P90 ratio baselines on active operational cohort...")
    df, p90_thresholds = compute_peer_group_p90_thresholds(df)

    # 4. Classify facilities into 6-tier resource pressure hierarchy
    logger.info("Classifying facilities into 6-tier resource pressure hierarchy...")
    df = classify_resource_pressure(
        df,
        tau_ratio_rise=tau_ratio_rise,
        tau_growth_gap=tau_growth_gap,
    )

    # 5. Generate distribution profiling (operational cohort)
    logger.info("Profiling distribution metrics on operational cohort...")
    dist_df = summarize_distributions(df)
    dist_df.to_csv(tables_dir / "kpi_distributions.csv")

    # 6. Categorical summaries (grouped by [school_year, category] on operational cohort)
    logger.info("Generating categorical breakdowns by school year on operational cohort...")
    if "school_level" in df.columns:
        level_summary = summarize_by_category(df, "school_level")
        level_summary.to_csv(tables_dir / "summary_by_school_level.csv", index=False)

    if "school_type" in df.columns:
        type_summary = summarize_by_category(df, "school_type")
        type_summary.to_csv(tables_dir / "summary_by_school_type.csv", index=False)

    if "is_charter" in df.columns:
        charter_summary = summarize_by_category(df, "is_charter")
        charter_summary.to_csv(tables_dir / "summary_by_charter_status.csv", index=False)

    # Preserve status breakdown across the full panel for administrative audit and review
    if "school_status" in df.columns:
        status_summary = summarize_by_category(df, "school_status", operational_only=False)
        status_summary.to_csv(tables_dir / "summary_by_school_status.csv", index=False)

    # 7. State-level aggregates (operational cohort)
    if "state_fips" in df.columns:
        state_summary = summarize_state_aggregates(df)
        state_summary.to_csv(tables_dir / "state_aggregates.csv", index=False)

    # 8. Resource pressure summaries and triage queues
    logger.info("Generating resource pressure summary tables and triage queues...")
    rp_tier_summary = summarize_resource_pressure_tiers(df)
    rp_tier_summary.to_csv(tables_dir / "resource_pressure_tier_summary.csv", index=False)

    if "state_fips" in df.columns:
        rp_state_summary = summarize_resource_pressure_by_state(df)
        rp_state_summary.to_csv(tables_dir / "resource_pressure_by_state.csv", index=False)

    if "school_level" in df.columns:
        rp_level_summary = summarize_resource_pressure_by_level(df)
        rp_level_summary.to_csv(tables_dir / "resource_pressure_by_level.csv", index=False)

    p1_queue = extract_triage_queue(df, priority=1)
    p1_queue.to_csv(tables_dir / "resource_pressure_triage_queue_p1.csv", index=False)

    p2_queue = extract_triage_queue(df, priority=2)
    p2_queue.to_csv(tables_dir / "resource_pressure_triage_queue_p2.csv", index=False)

    # Save augmented panel back to processed directory (preserving all full panel rows)
    if augmented_panel_path is None:
        augmented_panel_path = PROJECT_ROOT / "data" / "processed" / "school_year_panel_augmented.parquet"
    augmented_panel_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(augmented_panel_path, index=False)
    logger.info("Saved augmented panel to %s.", augmented_panel_path)

    # 7. Formulate empirical insights based on active operational cohort
    operational_mask = df["is_operational"].fillna(False).astype(bool) if "is_operational" in df.columns else pd.Series(True, index=df.index)
    operational_df = df[operational_mask]
    operational_records = len(operational_df)

    valid_ratios = operational_df["student_teacher_ratio"].dropna()
    median_ratio = round(float(valid_ratios.median()), 2) if not valid_ratios.empty else 0.0
    mean_ratio = round(float(valid_ratios.mean()), 2) if not valid_ratios.empty else 0.0
    iqr_ratio = round(float(valid_ratios.quantile(0.75) - valid_ratios.quantile(0.25)), 2) if not valid_ratios.empty else 0.0
    skewness_ratio = round(float(valid_ratios.skew()), 2) if len(valid_ratios) > 2 else 0.0

    # Mutually exclusive observation breakdown across the entire panel:
    # a. Benchmarked operational observations (active Regular Elementary/Middle/High)
    # b. Unbenchmarked operational observations (active specialized models or non-standard spans)
    # c. Non-operational / status review observations (Closed, Inactive, Future, Added, Reopened, etc.)
    if "peer_group_status" in df.columns:
        benchmarked_op_mask = df["peer_group_status"] == BENCHMARKED_STATUS_LABEL
        unbenchmarked_op_mask = df["peer_group_status"] == UNBENCHMARKED_STATUS_LABEL
        non_op_status_review_mask = df["peer_group_status"] == NON_OPERATIONAL_STATUS_LABEL
    else:
        benchmarked_op_mask = df["is_p90_eligible"].fillna(False).astype(bool) if "is_p90_eligible" in df.columns else operational_mask
        unbenchmarked_op_mask = operational_mask & ~benchmarked_op_mask
        non_op_status_review_mask = ~operational_mask

    benchmarked_op_obs_count = int(benchmarked_op_mask.sum())
    unbenchmarked_op_obs_count = int(unbenchmarked_op_mask.sum())
    non_op_status_review_obs_count = int(non_op_status_review_mask.sum())

    benchmarked_op_pct_of_operational = round(benchmarked_op_obs_count / operational_records * 100, 2) if operational_records > 0 else 0.0
    unbenchmarked_op_pct_of_operational = round(unbenchmarked_op_obs_count / operational_records * 100, 2) if operational_records > 0 else 0.0
    non_op_pct_of_panel = round(non_op_status_review_obs_count / total_records * 100, 2) if total_records > 0 else 0.0

    # Unique school IDs observed in each category (may overlap across years if a school changes status)
    benchmarked_op_schools_count = int(df.loc[benchmarked_op_mask, "school_id"].nunique())
    unbenchmarked_op_schools_count = int(df.loc[unbenchmarked_op_mask, "school_id"].nunique())
    non_op_status_review_schools_count = int(df.loc[non_op_status_review_mask, "school_id"].nunique())

    above_p90_obs_count = int(df["is_above_p90_ratio"].sum()) if "is_above_p90_ratio" in df.columns else 0
    above_p90_schools_count = int(df.loc[df["is_above_p90_ratio"], "school_id"].nunique()) if "is_above_p90_ratio" in df.columns else 0

    # Insight 1: Staffing ratio distribution baseline on active operational cohort
    insight_1 = (
        f"Nationally, the operational student-to-teacher ratio distribution baseline is {median_ratio}:1 "
        f"(mean: {mean_ratio}:1, interquartile range: {iqr_ratio}:1, sample skewness: {skewness_ratio:+.2f} "
        f"across {len(valid_ratios):,} active operational school-year observations in Open/New status)."
    )

    # Insight 2: Peer-group eligibility & stratification
    insight_2 = (
        f"Strict peer-group segmentation on the operational cohort classifies {benchmarked_op_obs_count:,} observations "
        f"({benchmarked_op_schools_count:,} distinct school IDs observed, {benchmarked_op_pct_of_operational}% of operational observations) as eligible "
        f"for regular-school P90 benchmarking. An additional {unbenchmarked_op_obs_count:,} active operational observations "
        f"({unbenchmarked_op_schools_count:,} distinct school IDs observed, {unbenchmarked_op_pct_of_operational}% of operational observations) belong to specialized instructional models "
        f"or non-standard grade spans (unbenchmarked peer groups). Finally, {non_op_status_review_obs_count:,} panel observations "
        f"({non_op_status_review_schools_count:,} distinct school IDs observed, {non_op_pct_of_panel}% of total panel records) represent non-operational "
        f"or transition-review records preserved for administrative audit."
    )

    # Insight 3: Elevated ratio concentration
    insight_3 = (
        f"Among eligible operational regular school-year observations, exactly {above_p90_obs_count:,} observations "
        f"({above_p90_schools_count:,} distinct school IDs observed) meet or exceed their respective stratum P90 baseline, "
        f"identifying them as candidates for high-ratio staffing investigation under Priority 2 review. "
        f"Non-operational and transition-review schools are strictly excluded from Priority 2 candidate flags."
    )

    eda_summary = {
        "panel_records": total_records,
        "operational_records": operational_records,
        "non_operational_records": non_op_status_review_obs_count,
        "unique_schools": int(df["school_id"].nunique()),
        "operational_unique_schools": int(operational_df["school_id"].nunique()),
        "school_years": sorted(df["school_year"].unique().tolist()),
        "median_student_teacher_ratio": median_ratio,
        "mean_student_teacher_ratio": mean_ratio,
        "iqr_student_teacher_ratio": iqr_ratio,
        "skewness_student_teacher_ratio": skewness_ratio,
        "benchmarked_operational_observations_count": benchmarked_op_obs_count,
        "unbenchmarked_operational_observations_count": unbenchmarked_op_obs_count,
        "non_operational_status_review_observations_count": non_op_status_review_obs_count,
        "benchmarked_operational_unique_schools_observed_count": benchmarked_op_schools_count,
        "unbenchmarked_operational_unique_schools_observed_count": unbenchmarked_op_schools_count,
        "non_operational_status_review_unique_schools_observed_count": non_op_status_review_schools_count,
        "above_p90_observations_count": above_p90_obs_count,
        "above_p90_unique_schools_observed_count": above_p90_schools_count,
        "p90_thresholds_by_stratum": p90_thresholds,
        "evidence_based_insights": [
            insight_1,
            insight_2,
            insight_3,
        ],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(time.time() - start_time, 2),
    }

    tier_counts = {
        tier: int((df["resource_pressure_tier"] == tier).sum())
        for tier in [
            PRIORITY_1_LABEL,
            PRIORITY_2_LABEL,
            PRIORITY_3_LABEL,
            PRIORITY_4_LABEL,
            PRIORITY_5_LABEL,
            PRIORITY_6_LABEL,
        ]
    }
    tier_operational_counts = {
        tier: int(((df["resource_pressure_tier"] == tier) & operational_mask).sum())
        for tier in [
            PRIORITY_1_LABEL,
            PRIORITY_2_LABEL,
            PRIORITY_3_LABEL,
            PRIORITY_4_LABEL,
            PRIORITY_5_LABEL,
            PRIORITY_6_LABEL,
        ]
    }
    tier_percentages_of_panel = {
        tier: round(count / total_records * 100, 2) if total_records > 0 else 0.0
        for tier, count in tier_counts.items()
    }
    tier_percentages_of_operational = {
        tier: round(op_count / operational_records * 100, 2) if operational_records > 0 else 0.0
        for tier, op_count in tier_operational_counts.items()
    }
    tier_unique_schools = {
        tier: int(df.loc[df["resource_pressure_tier"] == tier, "school_id"].nunique())
        for tier in tier_counts
    }

    rp_summary = {
        "panel_records": total_records,
        "operational_records": operational_records,
        "tau_ratio_rise": tau_ratio_rise,
        "tau_growth_gap": tau_growth_gap,
        "tier_counts": tier_counts,
        "tier_operational_counts": tier_operational_counts,
        "tier_percentages_of_panel": tier_percentages_of_panel,
        "tier_percentages_of_operational": tier_percentages_of_operational,
        "tier_unique_schools": tier_unique_schools,
        "provisional_threshold_notice": (
            "tau_ratio_rise (+15.0%) and tau_growth_gap (+5.0 pp) are provisional candidate parameters "
            "for decision-support prototyping, subject to stakeholder calibration before operational use."
        ),
        "unbenchmarked_stable_interpretation_caveat": (
            "For schools with peer_group_status == 'Unbenchmarked / Specialized Peer Group', "
            "assignment to Priority 6 (Stable / Balanced) denotes solely that available longitudinal trend indicators "
            "did not cross provisional escalation thresholds. It does NOT imply or certify that the school's absolute "
            "staffing levels or student-to-teacher ratio have been shown to be adequate, balanced, or compliant with "
            "programmatic guidelines."
        ),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(time.time() - start_time, 2),
    }

    rp_report_path = reports_dir / "resource_pressure_summary.json"
    with open(rp_report_path, "w", encoding="utf-8") as f:
        json.dump(rp_summary, f, indent=2)
    logger.info("Resource pressure summary report written to %s.", rp_report_path)

    eda_summary["resource_pressure_tier_counts"] = tier_counts
    eda_summary["resource_pressure_tier_operational_counts"] = tier_operational_counts

    report_path = reports_dir / "eda_summary.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(eda_summary, f, indent=2)

    logger.info("EDA summary report written to %s in %.2fs.", report_path, eda_summary["elapsed_seconds"])
    return eda_summary


def main():
    parser = argparse.ArgumentParser(description="Run EDA profiling and calculate core KPIs.")
    parser.add_argument("--panel-path", type=Path, default=None, help="Path to school_year_panel.parquet")
    parser.add_argument("--tables-dir", type=Path, default=None, help="Output directory for CSV tables")
    parser.add_argument("--reports-dir", type=Path, default=None, help="Output directory for reports")
    parser.add_argument(
        "--tau-ratio-rise",
        type=float,
        default=DEFAULT_TAU_RATIO_RISE,
        help="Provisional threshold for YoY ratio rise (percent)",
    )
    parser.add_argument(
        "--tau-growth-gap",
        type=float,
        default=DEFAULT_TAU_GROWTH_GAP,
        help="Provisional threshold for growth gap (percentage points)",
    )
    args = parser.parse_args()

    run_analytics_pipeline(
        panel_path=args.panel_path,
        tables_dir=args.tables_dir,
        reports_dir=args.reports_dir,
        tau_ratio_rise=args.tau_ratio_rise,
        tau_growth_gap=args.tau_growth_gap,
    )


if __name__ == "__main__":
    main()
