"""backtesting.py - Walk-forward backtesting engine for education demand forecasting.

Executes expanding window time-ordered backtesting per config/forecasting.yaml:
  Fold 1: Train [2018-19, 2019-20, 2020-21] -> Test [2021-22] (Post-shock recovery)
  Fold 2: Train [2018-19, 2019-20, 2020-21, 2021-22] -> Test [2022-23] (Final holdout)

Features:
  - Explicit reporting completeness metadata (contributing schools, reported count, missing count, coverage %)
  - Never coerces non-reported missing values to zero in state aggregates
  - Explicit time index and temporal gap validation in backtesting folds
  - Transparent exclusion logging for entities with missing ground truth or missing prior years
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from school_planning.forecasting.baselines import school_year_to_start_year
from school_planning.forecasting.metrics import evaluate_forecast_metrics
from school_planning.forecasting.models import get_forecaster

DEFAULT_FOLDS: list[dict[str, Any]] = [
    {
        "fold_id": "fold_1",
        "train_years": ["2018-19", "2019-20", "2020-21"],
        "test_year": "2021-22",
        "description": "Post-shock recovery validation step",
    },
    {
        "fold_id": "fold_2",
        "train_years": ["2018-19", "2019-20", "2020-21", "2021-22"],
        "test_year": "2022-23",
        "description": "Final holdout validation step",
    },
]

DEFAULT_CANDIDATE_MODELS: list[str] = [
    "naive_persistence",
    "drift",
    "moving_average_3yr",
]


def aggregate_state_time_series(
    panel_df: pd.DataFrame,
    target_cols: Sequence[str] = ("total_students", "teacher_fte"),
    state_col: str = "state_fips",
    display_col: str | None = "state_name",
    year_col: str = "school_year",
    operational_col: str = "is_operational",
    operational_only: bool = True,
) -> pd.DataFrame:
    """Aggregate school-level panel data into state-level annual time series with reporting completeness metadata.

    In accordance with config/forecasting.yaml and config/quality_rules.yaml:
      - Uses canonical state_fips (FIPST) as internal jurisdiction entity key.
      - Preserves state_name as display field when present in panel_df.
      - Reported values are summed.
      - Missing values are NOT coerced to zero; if zero schools report, state sum is NaN.
      - Explicit completeness metrics are generated for each target column:
          * contributing_operational_school_count
          * reported_{target}_school_count
          * missing_{target}_school_count
          * {target}_reporting_coverage_pct
          * is_{target}_complete_census

    Args:
        panel_df: Input school-year analytical panel.
        target_cols: Target variables to aggregate.
        state_col: Geographic aggregation key column (default: 'state_fips').
        display_col: Display name column to retain (default: 'state_name').
        year_col: School year temporal column.
        operational_col: Boolean operational status column.
        operational_only: If True, restricts aggregation to active operational cohort.

    Returns:
        Aggregated DataFrame with grain: (state_col, year_col) and explicit completeness metadata.
    """
    df = panel_df.copy()

    # Determine effective grouping key (allow fallback to display_col if state_col missing from legacy mock)
    effective_state_col = state_col
    if effective_state_col not in df.columns and display_col and display_col in df.columns:
        effective_state_col = display_col

    if operational_only and operational_col in df.columns:
        df = df[df[operational_col].fillna(False).astype(bool)]

    # Group by state and school year
    records: list[dict[str, Any]] = []

    for (state, year), grp in df.groupby([effective_state_col, year_col]):
        total_schools = len(grp)
        row: dict[str, Any] = {
            effective_state_col: state,
        }

        if display_col and display_col in grp.columns and display_col != effective_state_col:
            display_vals = grp[display_col].dropna()
            row[display_col] = display_vals.iloc[0] if len(display_vals) > 0 else str(state)

        row[year_col] = year
        row["school_count"] = total_schools
        row["contributing_operational_school_count"] = total_schools

        for col in target_cols:
            if col in grp.columns:
                series = pd.to_numeric(grp[col], errors="coerce")
                valid_mask = series.notna()
                reported_count = int(valid_mask.sum())
                missing_count = int((~valid_mask).sum())
                coverage_pct = (
                    round((reported_count / total_schools) * 100.0, 2)
                    if total_schools > 0
                    else 0.0
                )

                if reported_count > 0:
                    reported_sum = float(series[valid_mask].sum())
                else:
                    reported_sum = float(np.nan)

                row[f"reported_{col}_sum"] = reported_sum
                row[f"reported_{col}_count"] = reported_count
                row[f"missing_{col}_count"] = missing_count
                row[f"{col}_reporting_coverage_pct"] = coverage_pct
                row[f"is_{col}_complete_census"] = bool(missing_count == 0)

                # Keep col as primary access field (points to reported sum)
                row[col] = reported_sum
            else:
                row[f"reported_{col}_sum"] = float(np.nan)
                row[f"reported_{col}_count"] = 0
                row[f"missing_{col}_count"] = total_schools
                row[f"{col}_reporting_coverage_pct"] = 0.0
                row[f"is_{col}_complete_census"] = False
                row[col] = float(np.nan)

        records.append(row)

    res_df = pd.DataFrame(records)
    if not res_df.empty:
        res_df = res_df.sort_values([effective_state_col, year_col]).reset_index(drop=True)
    return res_df


def get_expected_prior_year(year_str: str) -> str:
    """Return the immediately preceding school year string.

    Example: '2021-22' -> '2020-21'
    """
    start_yr = school_year_to_start_year(year_str)
    prev_start = start_yr - 1
    prev_end = (prev_start + 1) % 100
    return f"{prev_start}-{prev_end:02d}"


def run_walk_forward_backtest(
    aggregate_df: pd.DataFrame,
    target_col: str = "total_students",
    entity_col: str = "state_fips",
    display_col: str | None = "state_name",
    year_col: str = "school_year",
    folds: list[dict[str, Any]] | None = None,
    model_names: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Execute walk-forward expanding window backtesting with explicit temporal gap auditing.

    Excludes entities with:
      - Missing or un-reported ground truth in test year
      - No valid training history in train years
      - Missing immediate prior year before test year (preventing multi-year gap masquerading as 1-step forecast)

    Args:
        aggregate_df: State- or district-level longitudinal DataFrame with completeness columns.
        target_col: Target variable name.
        entity_col: Entity identifier column (default: 'state_fips').
        display_col: Display name column to retain (default: 'state_name').
        year_col: School year column.
        folds: List of fold specifications (defaults to DEFAULT_FOLDS).
        model_names: List of model names to evaluate (defaults to DEFAULT_CANDIDATE_MODELS).

    Returns:
        Tuple of:
          1. Detailed predictions DataFrame (evaluated entity-fold-model observations).
          2. Summary metrics DataFrame (performance metrics per fold and model, plus overall).
          3. Exclusions DataFrame (entities excluded from evaluation with explicit reason).
    """
    if folds is None:
        folds = DEFAULT_FOLDS
    if model_names is None:
        model_names = DEFAULT_CANDIDATE_MODELS

    # Determine effective grouping key (allow fallback to display_col if entity_col missing from legacy mock)
    effective_entity_col = entity_col
    if effective_entity_col not in aggregate_df.columns and display_col and display_col in aggregate_df.columns:
        effective_entity_col = display_col

    # Build entity -> display name mapping if display_col is present
    entity_display_map: dict[Any, str] = {}
    if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
        entity_display_map = (
            aggregate_df.dropna(subset=[display_col])
            .groupby(effective_entity_col)[display_col]
            .first()
            .to_dict()
        )

    pred_records: list[dict[str, Any]] = []
    exclusion_records: list[dict[str, Any]] = []

    for fold in folds:
        fold_id = fold["fold_id"]
        train_years = fold["train_years"]
        test_year = fold["test_year"]
        desc = fold.get("description", "")
        expected_prior_year = get_expected_prior_year(test_year)

        train_data = aggregate_df[aggregate_df[year_col].isin(train_years)]
        test_data = aggregate_df[aggregate_df[year_col] == test_year]

        # Map test data by entity
        test_records_by_entity = {
            row[effective_entity_col]: row
            for _, row in test_data.iterrows()
        }

        # Unique entities observed across the aggregate dataset
        all_entities = sorted(aggregate_df[effective_entity_col].unique())

        for entity in all_entities:
            disp_name = entity_display_map.get(entity, str(entity))

            # 1. Check test year ground truth
            test_row = test_records_by_entity.get(entity)
            if test_row is None:
                excl_row: dict[str, Any] = {
                    "fold_id": fold_id,
                    "test_year": test_year,
                    "entity_id": entity,
                    effective_entity_col: entity,
                }
                if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
                    excl_row[display_col] = disp_name
                excl_row["target_col"] = target_col
                excl_row["reason"] = f"No data recorded in test year {test_year}"
                exclusion_records.append(excl_row)
                continue

            actual_val = test_row.get(target_col)
            coverage_col = f"{target_col}_reporting_coverage_pct"
            test_cov = test_row.get(coverage_col, 100.0)

            if pd.isna(actual_val) or actual_val <= 0.0:
                excl_row = {
                    "fold_id": fold_id,
                    "test_year": test_year,
                    "entity_id": entity,
                    effective_entity_col: entity,
                }
                if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
                    excl_row[display_col] = disp_name
                excl_row["target_col"] = target_col
                excl_row["reason"] = f"No reported ground truth in test year {test_year} (actual value is null or zero)"
                exclusion_records.append(excl_row)
                continue

            # 2. Check training history
            entity_train = train_data[train_data[effective_entity_col] == entity].sort_values(year_col)
            valid_train = entity_train.dropna(subset=[target_col])
            valid_train = valid_train[valid_train[target_col] > 0.0]

            if len(valid_train) == 0:
                excl_row = {
                    "fold_id": fold_id,
                    "test_year": test_year,
                    "entity_id": entity,
                    effective_entity_col: entity,
                }
                if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
                    excl_row[display_col] = disp_name
                excl_row["target_col"] = target_col
                excl_row["reason"] = f"Zero valid reported training observations in {train_years}"
                exclusion_records.append(excl_row)
                continue

            hist_years = valid_train[year_col].tolist()
            hist_vals = valid_train[target_col].tolist()
            latest_train_year = hist_years[-1]

            # 3. Check for immediate prior year continuity
            if latest_train_year != expected_prior_year:
                excl_row = {
                    "fold_id": fold_id,
                    "test_year": test_year,
                    "entity_id": entity,
                    effective_entity_col: entity,
                }
                if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
                    excl_row[display_col] = disp_name
                excl_row.update({
                    "target_col": target_col,
                    "expected_prior_year": expected_prior_year,
                    "actual_latest_train_year": latest_train_year,
                    "reason": (
                        f"latest_train_year_gap: Missing immediate prior school year ({expected_prior_year}) "
                        f"in training history; latest observed training year is {latest_train_year}."
                    ),
                })
                exclusion_records.append(excl_row)
                continue

            # Check if training series has interior gaps
            year_ints = [school_year_to_start_year(y) for y in hist_years]
            has_interior_gaps = any(
                year_ints[i] - year_ints[i - 1] > 1
                for i in range(1, len(year_ints))
            )

            # Evaluate each candidate model
            for model_name in model_names:
                try:
                    forecaster = get_forecaster(model_name)
                    forecaster.fit(hist_vals, years=hist_years)
                    pred = float(forecaster.predict(horizon=1, target_year=test_year))
                except (ValueError, RuntimeError, TypeError):
                    pred = float(np.nan)

                abs_err = abs(actual_val - pred) if not np.isnan(pred) else np.nan
                pct_err = (
                    abs_err / actual_val * 100.0
                    if not np.isnan(abs_err) and actual_val > 0
                    else np.nan
                )

                pred_row: dict[str, Any] = {
                    "fold_id": fold_id,
                    "fold_description": desc,
                    "test_year": test_year,
                    effective_entity_col: entity,
                }
                if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
                    pred_row[display_col] = disp_name
                pred_row.update({
                    "target_col": target_col,
                    "actual": float(actual_val),
                    "model_name": model_name,
                    "predicted": pred,
                    "error": pred - actual_val if not np.isnan(pred) else np.nan,
                    "abs_error": abs_err,
                    "pct_error": pct_err,
                    "train_years_used": ",".join(hist_years),
                    "train_obs_count": len(hist_vals),
                    "has_interior_gaps": has_interior_gaps,
                    "test_coverage_pct": test_cov,
                })
                pred_records.append(pred_row)

    pred_df = pd.DataFrame(pred_records)
    exclusions_df = pd.DataFrame(exclusion_records)

    if pred_df.empty:
        return pred_df, pd.DataFrame(), exclusions_df

    # Calculate summary metrics per fold and model
    summary_records: list[dict[str, Any]] = []

    for (fold_id, model_name), grp in pred_df.groupby(["fold_id", "model_name"]):
        valid_grp = grp.dropna(subset=["actual", "predicted"])
        if len(valid_grp) == 0:
            continue

        test_year = grp["test_year"].iloc[0]
        metrics = evaluate_forecast_metrics(valid_grp["actual"], valid_grp["predicted"])

        cov_series = pd.to_numeric(valid_grp["test_coverage_pct"], errors="coerce").dropna()
        n_complete = int((cov_series >= 100.0).sum())
        n_partial = int((cov_series < 100.0).sum())
        min_cov = float(round(cov_series.min(), 2)) if len(cov_series) > 0 else float(np.nan)
        med_cov = float(round(cov_series.median(), 2)) if len(cov_series) > 0 else float(np.nan)
        mean_cov = float(round(cov_series.mean(), 2)) if len(cov_series) > 0 else float(np.nan)

        summary_records.append({
            "fold_id": fold_id,
            "test_year": test_year,
            "target_col": target_col,
            "model_name": model_name,
            "n_observations": len(valid_grp),
            "n_complete_census_obs": n_complete,
            "n_partial_coverage_obs": n_partial,
            "min_coverage_pct": min_cov,
            "median_coverage_pct": med_cov,
            "mean_coverage_pct": mean_cov,
            "evaluation_basis": "reported_value_aggregates",
            "coverage_caution": (
                "Evaluation evaluated against reported-value aggregates; "
                "variations in reporting coverage across school years can influence measured errors."
            ),
            "mae": metrics["mae"],
            "wape": metrics["wape"],
            "mape": metrics["mape"],
            "rmse": metrics["rmse"],
        })

    # Overall pooled cross-fold summary per model
    for model_name, grp in pred_df.groupby("model_name"):
        valid_grp = grp.dropna(subset=["actual", "predicted"])
        if len(valid_grp) == 0:
            continue

        metrics = evaluate_forecast_metrics(valid_grp["actual"], valid_grp["predicted"])
        cov_series = pd.to_numeric(valid_grp["test_coverage_pct"], errors="coerce").dropna()
        n_complete = int((cov_series >= 100.0).sum())
        n_partial = int((cov_series < 100.0).sum())
        min_cov = float(round(cov_series.min(), 2)) if len(cov_series) > 0 else float(np.nan)
        med_cov = float(round(cov_series.median(), 2)) if len(cov_series) > 0 else float(np.nan)
        mean_cov = float(round(cov_series.mean(), 2)) if len(cov_series) > 0 else float(np.nan)

        summary_records.append({
            "fold_id": "overall_pooled",
            "test_year": "all_folds",
            "target_col": target_col,
            "model_name": model_name,
            "n_observations": len(valid_grp),
            "n_complete_census_obs": n_complete,
            "n_partial_coverage_obs": n_partial,
            "min_coverage_pct": min_cov,
            "median_coverage_pct": med_cov,
            "mean_coverage_pct": mean_cov,
            "evaluation_basis": "reported_value_aggregates",
            "coverage_caution": (
                "Evaluation evaluated against reported-value aggregates; "
                "variations in reporting coverage across school years can influence measured errors."
            ),
            "mae": metrics["mae"],
            "wape": metrics["wape"],
            "mape": metrics["mape"],
            "rmse": metrics["rmse"],
        })

    summary_df = pd.DataFrame(summary_records)
    sort_order = {"fold_1": 1, "fold_2": 2, "overall_pooled": 3}
    summary_df["sort_key"] = summary_df["fold_id"].map(sort_order).fillna(99)
    summary_df = summary_df.sort_values(["sort_key", "model_name"]).drop(columns=["sort_key"]).reset_index(drop=True)

    return pred_df, summary_df, exclusions_df
