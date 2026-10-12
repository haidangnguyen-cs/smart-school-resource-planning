"""scenarios.py - Retrospective scenario projection and implied staffing demand analysis.

Implements retrospective 2023-24 projection framing with scenario bounds per config/forecasting.yaml:
  - Baseline point projection using verified historical window (2018-19 to 2022-23)
  - Fixed policy scenario bands (-2.0%, -1.0%, Baseline, +1.0%, +2.0%)
  - Explicit consecutive year-over-year historical growth bounds (ignoring non-consecutive jumps)
  - Validation that the latest observed year corresponds to 2022-23 before presenting as a 1-year projection
  - Implied staffing requirement calculations under constant historical ratio and optional policy target ratio
"""

from typing import Any

import numpy as np
import pandas as pd

from school_planning.forecasting.baselines import school_year_to_start_year
from school_planning.forecasting.models import get_forecaster

DEFAULT_SCENARIO_BANDS: list[dict[str, Any]] = [
    {"label": "low_contraction_minus_2pct", "pct_shift": -2.0, "description": "Contraction band (-2.0%)"},
    {"label": "mild_contraction_minus_1pct", "pct_shift": -1.0, "description": "Mild contraction (-1.0%)"},
    {"label": "baseline_projection", "pct_shift": 0.0, "description": "Model baseline point projection"},
    {"label": "mild_expansion_plus_1pct", "pct_shift": 1.0, "description": "Mild expansion (+1.0%)"},
    {"label": "high_expansion_plus_2pct", "pct_shift": 2.0, "description": "Expansion band (+2.0%)"},
]


def generate_projection_scenarios(
    aggregate_df: pd.DataFrame,
    target_col: str = "total_students",
    entity_col: str = "state_fips",
    display_col: str | None = "state_name",
    year_col: str = "school_year",
    target_projection_year: str = "2023-24",
    expected_latest_year: str = "2022-23",
    model_name: str = "naive_persistence",
    scenario_bands: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Generate retrospective point projections with policy scenario bounds and temporal gap validation.

    Note on Timeframe Framing (per config/forecasting.yaml):
      Because the source window ends in 2022-23 and the current year is 2026,
      the 2023-24 output is strictly framed as a retrospective projection, not
      an upcoming forecast. Because actual 2023-24 outcomes are absent from this
      dataset, its forecast accuracy cannot be evaluated.

    Args:
        aggregate_df: State- or district-level longitudinal DataFrame.
        target_col: Column to project (e.g. 'total_students' or 'teacher_fte').
        entity_col: Entity identifier column (default: 'state_fips').
        display_col: Display name column to retain (default: 'state_name').
        year_col: School year column.
        target_projection_year: Canonical label for projection period (default: '2023-24').
        expected_latest_year: Expected most recent historical year (default: '2022-23').
        model_name: Selected candidate model name.
        scenario_bands: List of scenario band definitions.

    Returns:
        DataFrame with projected baseline values, scenario bands, and temporal validation flags.
    """
    if scenario_bands is None:
        scenario_bands = DEFAULT_SCENARIO_BANDS

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

    records: list[dict[str, Any]] = []
    sorted_df = aggregate_df.sort_values([effective_entity_col, year_col])

    for entity, grp in sorted_df.groupby(effective_entity_col):
        # Filter to non-null, positive values
        valid_grp = grp.dropna(subset=[target_col])
        valid_grp = valid_grp[valid_grp[target_col] > 0.0]

        if len(valid_grp) == 0:
            continue

        disp_name = entity_display_map.get(entity, str(entity))
        history = valid_grp[target_col].tolist()
        history_years = valid_grp[year_col].tolist()
        latest_actual = history[-1]
        latest_year = history_years[-1]

        # Verify whether the latest year corresponds to expected_latest_year
        is_latest_year_valid = bool(latest_year == expected_latest_year)
        if is_latest_year_valid:
            history_status = f"Complete (through {latest_year})"
        else:
            history_status = f"Incomplete: latest observed year is {latest_year}, not {expected_latest_year}"

        # Check for temporal gaps in history
        year_ints = [school_year_to_start_year(y) for y in history_years]
        has_temporal_gaps = any(
            year_ints[i] - year_ints[i - 1] > 1
            for i in range(1, len(year_ints))
        )

        # Compute strictly consecutive annual YoY growth rates
        consecutive_growths: list[float] = []
        for i in range(1, len(history)):
            prev_val = history[i - 1]
            curr_val = history[i]
            # Only compute YoY rate if observation is exactly 1 calendar step apart
            if year_ints[i] - year_ints[i - 1] == 1 and prev_val > 0:
                consecutive_growths.append((curr_val - prev_val) / prev_val * 100.0)

        if len(consecutive_growths) > 0:
            min_hist_growth = float(np.min(consecutive_growths))
            max_hist_growth = float(np.max(consecutive_growths))
            avg_hist_growth = float(np.mean(consecutive_growths))
            hist_min_bound = max(0.0, latest_actual * (1.0 + min_hist_growth / 100.0))
            hist_max_bound = max(0.0, latest_actual * (1.0 + max_hist_growth / 100.0))
        else:
            min_hist_growth = float(np.nan)
            max_hist_growth = float(np.nan)
            avg_hist_growth = float(np.nan)
            hist_min_bound = float(np.nan)
            hist_max_bound = float(np.nan)

        # Fit model passing explicit temporal index
        forecaster = get_forecaster(model_name)
        forecaster.fit(history, years=history_years)
        raw_pred = forecaster.predict(horizon=1, target_year=target_projection_year)
        if isinstance(raw_pred, np.ndarray):
            candidate_base_pred = float(raw_pred.ravel()[-1])
        else:
            candidate_base_pred = float(raw_pred)

        # Exclude invalid latest-year entities from numerical projections (set to NaN)
        if is_latest_year_valid:
            base_pred = candidate_base_pred
            final_hist_min_bound = hist_min_bound
            final_hist_max_bound = hist_max_bound
        else:
            base_pred = float(np.nan)
            final_hist_min_bound = float(np.nan)
            final_hist_max_bound = float(np.nan)

        row: dict[str, Any] = {
            effective_entity_col: entity,
        }
        if display_col and display_col in aggregate_df.columns and display_col != effective_entity_col:
            row[display_col] = disp_name

        row.update({
            "target_col": target_col,
            "projection_year": target_projection_year,
            "model_applied": model_name,
            "latest_historical_year": latest_year,
            "is_latest_year_valid": is_latest_year_valid,
            "history_status": history_status,
            "projection_status": history_status,
            "years_observed_count": len(history),
            "has_temporal_gaps": has_temporal_gaps,
            "consecutive_yoy_intervals_count": len(consecutive_growths),
            "latest_historical_value": latest_actual,
            "baseline_projection": base_pred,
            "hist_min_yoy_growth_pct": min_hist_growth,
            "hist_max_yoy_growth_pct": max_hist_growth,
            "hist_avg_yoy_growth_pct": avg_hist_growth,
            "scenario_hist_min_bound": final_hist_min_bound,
            "scenario_hist_max_bound": final_hist_max_bound,
        })

        # Compute scenario bands relative to baseline projection
        for band in scenario_bands:
            pct_shift = band["pct_shift"]
            band_label = band["label"]
            if is_latest_year_valid and not np.isnan(base_pred):
                projected_band_val = max(0.0, base_pred * (1.0 + pct_shift / 100.0))
            else:
                projected_band_val = float(np.nan)
            row[f"scenario_{band_label}"] = projected_band_val

        records.append(row)

    return pd.DataFrame(records)


def estimate_implied_staffing_demand(
    projections_df: pd.DataFrame,
    baseline_enrollment_col: str = "baseline_projection",
    latest_teachers_col: str = "latest_historical_teacher_fte",
    latest_students_col: str = "latest_historical_value",
    target_ratio: float | None = None,
) -> pd.DataFrame:
    """Calculate implied teacher staffing requirements from enrollment projections.

    Answers core resource planning question:
      Given projected student enrollment, how many teacher FTEs are required
      under constant historical ratio vs. optional policy target ratio?

    Args:
        projections_df: Projections DataFrame from generate_projection_scenarios.
        baseline_enrollment_col: Column with projected student enrollment.
        latest_teachers_col: Column with latest historical teacher FTE.
        latest_students_col: Column with latest historical student count.
        target_ratio: Optional policy target ratio (e.g. 15.0). If None, calculates
          strictly the constant historical ratio scenario.

    Returns:
        Augmented DataFrame with implied staffing demand and staffing gaps.
    """
    res = projections_df.copy()

    students = res[latest_students_col]
    teachers = (
        res[latest_teachers_col]
        if latest_teachers_col in res.columns
        else pd.Series(np.nan, index=res.index)
    )

    # 1. Historical Constant Ratio Scenario
    hist_ratio = np.where((teachers > 0) & (students >= 0), students / teachers, np.nan)
    res["historical_student_teacher_ratio"] = hist_ratio

    proj_students = res[baseline_enrollment_col]
    implied_staff_const = np.where(hist_ratio > 0, proj_students / hist_ratio, np.nan)
    res["implied_teacher_fte_constant_ratio"] = implied_staff_const
    # Backwards-compatible alias
    res["implied_teacher_fte_baseline"] = implied_staff_const

    if latest_teachers_col in res.columns:
        res["implied_staffing_gap_constant_ratio"] = implied_staff_const - teachers
        res["implied_staffing_gap_baseline"] = implied_staff_const - teachers

    # Also compute implied staff under +/- 2% scenario bands for constant ratio
    for band_col in ["scenario_low_contraction_minus_2pct", "scenario_high_expansion_plus_2pct"]:
        if band_col in res.columns:
            band_name = band_col.replace("scenario_", "")
            band_students = res[band_col]
            res[f"implied_teacher_fte_{band_name}"] = np.where(
                hist_ratio > 0, band_students / hist_ratio, np.nan
            )

    # 2. Policy Target Ratio Scenario (when explicitly configured)
    if target_ratio is not None and target_ratio > 0:
        res["policy_target_ratio_applied"] = float(target_ratio)
        implied_staff_target = proj_students / target_ratio
        res["implied_teacher_fte_policy_target"] = implied_staff_target
        if latest_teachers_col in res.columns:
            res["implied_staffing_gap_policy_target"] = implied_staff_target - teachers
        else:
            res["implied_staffing_gap_policy_target"] = np.nan
    else:
        res["policy_target_ratio_applied"] = np.nan
        res["implied_teacher_fte_policy_target"] = np.nan
        res["implied_staffing_gap_policy_target"] = np.nan

    if "is_latest_year_valid" in res.columns:
        invalid_mask = ~res["is_latest_year_valid"].astype(bool)
        for c in [
            "implied_teacher_fte_constant_ratio",
            "implied_teacher_fte_baseline",
            "implied_staffing_gap_constant_ratio",
            "implied_staffing_gap_baseline",
            "implied_teacher_fte_policy_target",
            "implied_staffing_gap_policy_target",
            "implied_teacher_fte_low_contraction_minus_2pct",
            "implied_teacher_fte_high_expansion_plus_2pct",
        ]:
            if c in res.columns:
                res.loc[invalid_mask, c] = np.nan

    return res
