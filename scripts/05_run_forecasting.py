#!/usr/bin/env python3
"""05_run_forecasting.py - End-to-end forecasting feasibility and walk-forward backtesting runner.

Executes Phase 6 forecasting workflows per config/forecasting.yaml:
  1. Verifies constrained feasibility: documents why school-level forecasting is rejected (T=5)
     and establishes aggregate state-level pooling.
  2. Aggregates the longitudinal analytical panel to state-level annual time series with
     transparent reporting completeness metadata (reported count, missing count, coverage %).
  3. Executes chronological walk-forward expanding window backtesting:
       - Fold 1: Train [2018-19, 2019-20, 2020-21] -> Test [2021-22]
       - Fold 2: Train [2018-19, 2019-20, 2020-21, 2021-22] -> Test [2022-23]
     Evaluates candidate models (Naive Persistence, Linear Drift, 3-Year Moving Average).
     Excludes entities with missing ground truth or missing immediate prior training year.
  4. Generates retrospective 2023-24 scenario projections with policy bands (+/-1%, +/-2%)
     and calculates implied teacher staffing demand under constant historical ratio (and optional policy target ratio).
  5. Exports tables to outputs/tables/ and JSON audit report to outputs/reports/.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from school_planning.forecasting.backtesting import (
    DEFAULT_CANDIDATE_MODELS,
    DEFAULT_FOLDS,
    aggregate_state_time_series,
    run_walk_forward_backtest,
)
from school_planning.forecasting.models import REJECTED_MODELS
from school_planning.forecasting.scenarios import (
    DEFAULT_SCENARIO_BANDS,
    estimate_implied_staffing_demand,
    generate_projection_scenarios,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("05_run_forecasting")


def load_forecasting_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load config/forecasting.yaml."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "forecasting.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_forecasting_pipeline(
    project_root: Path = PROJECT_ROOT,
    panel_path: Path | None = None,
    output_tables_dir: Path | None = None,
    output_reports_dir: Path | None = None,
    aggregates_dir: Path | None = None,
    policy_target_ratio: float | None = None,
) -> dict[str, Any]:
    """Execute complete forecasting evaluation and scenario generation pipeline.

    Args:
        project_root: Repository root directory.
        panel_path: Path to school_year_panel.parquet.
        output_tables_dir: Directory for CSV summary tables.
        output_reports_dir: Directory for JSON evaluation reports.
        aggregates_dir: Directory for state annual aggregate parquets.
        policy_target_ratio: Optional policy target student-to-teacher ratio (e.g. 15.0).
          If None, calculates strictly the constant historical ratio scenario.

    Returns:
        Dictionary summarizing pipeline execution results and metrics.
    """
    start_t = time.time()
    logger.info("Starting Phase 6 Forecasting Feasibility and Backtesting Pipeline...")

    cfg = load_forecasting_config(project_root / "config" / "forecasting.yaml")
    fc_cfg = cfg.get("forecasting", {})

    if panel_path is None:
        panel_path = project_root / "data" / "processed" / "school_year_panel.parquet"

    if output_tables_dir is None:
        output_tables_dir = project_root / "outputs" / "tables"
    output_tables_dir.mkdir(parents=True, exist_ok=True)

    if output_reports_dir is None:
        output_reports_dir = project_root / "outputs" / "reports"
    output_reports_dir.mkdir(parents=True, exist_ok=True)

    if aggregates_dir is None:
        aggregates_dir = project_root / "data" / "processed" / "aggregates"
    aggregates_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Longitudinal Panel
    if not panel_path.exists():
        raise FileNotFoundError(
            f"Processed panel not found at {panel_path}. "
            "Run scripts/03_build_panel.py before running forecasting."
        )

    logger.info("Loading analytical panel from %s...", panel_path)
    panel_df = pd.read_parquet(panel_path)
    observed_years = sorted(panel_df["school_year"].unique())

    # Canonical internal state entity key (FIPST -> state_fips) and display field (state_name)
    state_key_col = "state_fips" if "state_fips" in panel_df.columns else "state_name"
    display_col = "state_name" if "state_name" in panel_df.columns and state_key_col != "state_name" else None

    all_states = sorted(panel_df[state_key_col].unique())
    fips_to_name: dict[Any, str] = {}
    if display_col:
        fips_to_name = panel_df.dropna(subset=[display_col]).groupby(state_key_col)[display_col].first().to_dict()

    logger.info(
        "Loaded panel: %d records across years: %s (%d states, entity key: %s)",
        len(panel_df),
        observed_years,
        len(all_states),
        state_key_col,
    )

    # Audit grid completeness (expected vs actual state-years)
    expected_grid_size = len(all_states) * len(observed_years)
    state_year_pairs = set(zip(panel_df[state_key_col], panel_df["school_year"], strict=False))
    missing_grid_pairs = []
    for s in all_states:
        for y in observed_years:
            if (s, y) not in state_year_pairs:
                grid_info: dict[str, Any] = {
                    state_key_col: s,
                    "school_year": y,
                }
                if display_col:
                    grid_info[display_col] = fips_to_name.get(s, str(s))
                missing_grid_pairs.append(grid_info)

    logger.info(
        "Grid check: %d observed state-year combinations out of %d expected (missing: %d: %s)",
        len(state_year_pairs),
        expected_grid_size,
        len(missing_grid_pairs),
        missing_grid_pairs,
    )

    # 2. State-Level Aggregation with Completeness Metadata
    logger.info("Aggregating operational facilities to state-level annual time series...")
    state_agg = aggregate_state_time_series(
        panel_df,
        target_cols=["total_students", "teacher_fte"],
        state_col=state_key_col,
        display_col=display_col,
        operational_only=True,
    )
    logger.info(
        "Constructed state time series: %d state-year observations across %d states.",
        len(state_agg),
        state_agg[state_key_col].nunique(),
    )

    # Save state aggregates
    state_agg_csv = output_tables_dir / "state_annual_aggregates.csv"
    state_agg.to_csv(state_agg_csv, index=False)
    state_agg_pq = aggregates_dir / "state_annual_aggregates.parquet"
    state_agg.to_parquet(state_agg_pq, index=False)
    logger.info("Saved state annual aggregates to %s and %s", state_agg_csv.name, state_agg_pq.name)

    # Audit zero-reported state-years
    audit_cols = [state_key_col, "school_year"]
    if display_col and display_col in state_agg.columns:
        audit_cols = [state_key_col, display_col, "school_year"]

    zero_reported_audit = {
        "total_students": state_agg[state_agg["reported_total_students_count"] == 0][
            audit_cols
        ].to_dict(orient="records"),
        "teacher_fte": state_agg[state_agg["reported_teacher_fte_count"] == 0][
            audit_cols
        ].to_dict(orient="records"),
    }

    # 3. Walk-Forward Backtesting
    logger.info("Executing walk-forward backtesting across candidate models...")
    all_preds: list[pd.DataFrame] = []
    all_summaries: list[pd.DataFrame] = []
    all_exclusions: list[pd.DataFrame] = []

    for target in ["total_students", "teacher_fte"]:
        logger.info("Evaluating backtesting folds for target: %s", target)
        preds, summary, exclusions = run_walk_forward_backtest(
            state_agg,
            target_col=target,
            entity_col=state_key_col,
            display_col=display_col,
            year_col="school_year",
            folds=DEFAULT_FOLDS,
            model_names=DEFAULT_CANDIDATE_MODELS,
        )
        all_preds.append(preds)
        all_summaries.append(summary)
        all_exclusions.append(exclusions)

    combined_preds = pd.concat(all_preds, ignore_index=True)
    combined_summary = pd.concat(all_summaries, ignore_index=True)
    combined_exclusions = pd.concat(all_exclusions, ignore_index=True)

    # Save backtest results and exclusions
    preds_csv = output_tables_dir / "backtest_predictions_detailed.csv"
    combined_preds.to_csv(preds_csv, index=False)
    summary_csv = output_tables_dir / "backtest_model_comparison.csv"
    combined_summary.to_csv(summary_csv, index=False)
    exclusions_csv = output_tables_dir / "backtest_exclusions.csv"
    combined_exclusions.to_csv(exclusions_csv, index=False)
    logger.info(
        "Saved backtest predictions to %s, comparison to %s, exclusions to %s",
        preds_csv.name,
        summary_csv.name,
        exclusions_csv.name,
    )

    logger.info("\n=== Walk-Forward Backtest Performance Summary (Overall Pooled) ===")
    pooled = combined_summary[combined_summary["fold_id"] == "overall_pooled"]
    for _, r in pooled.iterrows():
        logger.info(
            "  Target: %-15s | Model: %-20s | WAPE: %5.2f%% | MAE: %10.1f | RMSE: %10.1f",
            r["target_col"],
            r["model_name"],
            r["wape"],
            r["mae"],
            r["rmse"],
        )

    # 4. Retrospective 2023-24 Scenario Projections
    logger.info("Generating retrospective 2023-24 scenario projections...")
    proj_students = generate_projection_scenarios(
        state_agg,
        target_col="total_students",
        entity_col=state_key_col,
        display_col=display_col,
        year_col="school_year",
        target_projection_year="2023-24",
        expected_latest_year="2022-23",
        model_name="naive_persistence",
        scenario_bands=DEFAULT_SCENARIO_BANDS,
    )

    latest_teachers = (
        state_agg[state_agg["school_year"] == "2022-23"]
        .set_index(state_key_col)["teacher_fte"]
        .to_dict()
    )
    proj_students["latest_historical_teacher_fte"] = proj_students[state_key_col].map(latest_teachers)

    staffing_scenarios = estimate_implied_staffing_demand(
        proj_students,
        baseline_enrollment_col="baseline_projection",
        latest_teachers_col="latest_historical_teacher_fte",
        latest_students_col="latest_historical_value",
        target_ratio=policy_target_ratio,
    )

    scenarios_csv = output_tables_dir / "retrospective_2023_24_projections.csv"
    staffing_scenarios.to_csv(scenarios_csv, index=False)
    logger.info("Saved retrospective scenario projections to %s", scenarios_csv.name)

    # 5. Compile Comprehensive Forecasting Evaluation Report
    # National retrospective projections scope and coverage
    valid_mask = staffing_scenarios["is_latest_year_valid"].astype(bool)
    valid_scenarios = staffing_scenarios[valid_mask]
    invalid_scenarios = staffing_scenarios[~valid_mask]

    eligible_count = int(valid_mask.sum())
    excluded_count = int((~valid_mask).sum())
    excluded_entities_info = []
    excluded_names = []
    for _, r in invalid_scenarios.iterrows():
        entity_id_val = r[state_key_col]
        disp_val = r.get(display_col, entity_id_val) if display_col else entity_id_val
        excl_dict: dict[str, Any] = {
            state_key_col: entity_id_val,
            "latest_historical_year": r["latest_historical_year"],
            "reason": r["projection_status"],
        }
        if display_col:
            excl_dict[display_col] = disp_val
            excluded_names.append(f"{disp_val} ({entity_id_val})")
        else:
            excluded_names.append(str(entity_id_val))
        excluded_entities_info.append(excl_dict)

    excluded_names.sort()
    coverage_scope = (
        f"{eligible_count} of {len(staffing_scenarios)} states/jurisdictions with valid 2022-23 baseline observations "
        f"(excluding {', '.join(excluded_names)} due to incomplete/stale history)."
        if excluded_count > 0
        else f"All {eligible_count} states/jurisdictions."
    )

    report_data = {
        "pipeline": "Phase 6 Forecasting Feasibility and Backtesting",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "execution_time_seconds": round(time.time() - start_t, 2),
        "feasibility_assessment": {
            "status": fc_cfg.get("status", "Conditional / Constrained Feasibility"),
            "school_level_feasible": False,
            "school_level_rationale": fc_cfg.get("feasibility_assessment", {})
            .get("school_level", {})
            .get("rationale", "")
            .strip(),
            "aggregate_level_feasible": True,
            "aggregate_level_grain": "state_level",
            "aggregate_level_rationale": fc_cfg.get("feasibility_assessment", {})
            .get("aggregate_level", {})
            .get("rationale", "")
            .strip(),
            "rejected_models": REJECTED_MODELS,
        },
        "time_series_properties": {
            "time_series_length": len(observed_years),
            "school_years": observed_years,
            "entity_identifier_key": state_key_col,
            "display_name_key": display_col or state_key_col,
            "states_observed": len(all_states),
            "states_observed_count": len(all_states),
            "expected_grid_state_years": expected_grid_size,
            "observed_grid_state_years": len(state_year_pairs),
            "missing_grid_state_years": missing_grid_pairs,
            "covid_shock_period": "2020-21 (structural disruption)",
            "zero_reported_state_years": zero_reported_audit,
        },
        "backtesting_results": {
            "folds": DEFAULT_FOLDS,
            "candidate_models": DEFAULT_CANDIDATE_MODELS,
            "evaluation_basis": "reported_value_aggregates",
            "coverage_caution": (
                "Evaluation evaluated against reported-value aggregates; "
                "variations in reporting coverage across school years can influence measured errors."
            ),
            "metrics_summary": combined_summary.to_dict(orient="records"),
            "exclusions_count": len(combined_exclusions),
            "exclusions_summary": combined_exclusions.to_dict(orient="records"),
        },
        "retrospective_2023_24_projections": {
            "target_year": "2023-24",
            "timeframe_framing": (
                "Retrospective demonstration baseline only. Because actual 2023-24 outcomes "
                "are absent, accuracy cannot be evaluated on this target year."
            ),
            "policy_target_ratio_applied": policy_target_ratio,
            "policy_target_ratio_status": (
                f"Applied policy target ratio: {policy_target_ratio}"
                if policy_target_ratio is not None
                else (
                    "No explicit policy target ratio defined in config/forecasting.yaml or project specifications. "
                    "Staffing demand evaluated strictly under constant historical ratio scenario. "
                    "Policy target ratio remains an external decision requirement for stakeholders."
                )
            ),
            "eligible_entities_count": eligible_count,
            "excluded_entities_count": excluded_count,
            "excluded_entities": excluded_entities_info,
            "national_totals_coverage_scope": coverage_scope,
            "national_total_baseline_students": float(valid_scenarios["baseline_projection"].dropna().sum()),
            "national_total_scenario_low_minus_2pct": float(
                valid_scenarios["scenario_low_contraction_minus_2pct"].dropna().sum()
            ),
            "national_total_scenario_high_plus_2pct": float(
                valid_scenarios["scenario_high_expansion_plus_2pct"].dropna().sum()
            ),
            "national_implied_teacher_fte_constant_ratio": float(
                valid_scenarios["implied_teacher_fte_constant_ratio"].dropna().sum()
            ),
            "national_implied_teacher_fte_policy_target": (
                float(valid_scenarios["implied_teacher_fte_policy_target"].dropna().sum())
                if policy_target_ratio is not None and valid_scenarios["implied_teacher_fte_policy_target"].notna().any()
                else None
            ),
        },
        "data_caveats_and_limitations": [
            "T=5 annual observations limits estimation degrees of freedom.",
            "Covid-19 shock in 2020-21 creates a non-stationary shift in enrollment and staffing trajectories.",
            "Forecast accuracy is assessed strictly on backtesting folds 2021-22 and 2022-23.",
            "Student-to-teacher ratio is an administrative staffing indicator, not an observed class size metric.",
            "Missingness and non-reporting vary across states (e.g. CA 2019-20, IL/UT 2020-21 missing teacher FTE).",
            "Entities with missing ground truth or missing prior years are excluded from backtesting with documented reasons.",
            "Evaluation metrics are computed from reported-value aggregates; variations in reporting coverage across school years may influence measured errors.",
            "National retrospective scenario totals include only entities with valid 2022-23 baseline observations; stale-history entities are excluded to prevent distortion.",
        ],
    }

    report_path = output_reports_dir / "forecasting_evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    logger.info("Saved forecasting evaluation report to %s", report_path)

    elapsed = time.time() - start_t
    logger.info("Forecasting pipeline completed successfully in %.2fs", elapsed)

    return report_data


def main():
    """CLI entry point for scripts/05_run_forecasting.py."""
    parser = argparse.ArgumentParser(description="Run forecasting evaluation pipeline.")
    parser.add_argument("--panel-path", type=Path, help="Custom processed panel path.")
    parser.add_argument("--output-tables-dir", type=Path, help="Custom output tables directory.")
    parser.add_argument("--output-reports-dir", type=Path, help="Custom output reports directory.")
    parser.add_argument("--aggregates-dir", type=Path, help="Custom aggregates directory.")
    parser.add_argument(
        "--policy-target-ratio",
        type=float,
        default=None,
        help="Optional policy target student-to-teacher ratio (default: None, uses constant historical ratio).",
    )
    args = parser.parse_args()

    run_forecasting_pipeline(
        panel_path=args.panel_path,
        output_tables_dir=args.output_tables_dir,
        output_reports_dir=args.output_reports_dir,
        aggregates_dir=args.aggregates_dir,
        policy_target_ratio=args.policy_target_ratio,
    )


if __name__ == "__main__":
    main()
