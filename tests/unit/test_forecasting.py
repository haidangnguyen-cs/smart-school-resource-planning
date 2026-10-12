"""test_forecasting.py - Unit test suite for Phase 6 forecasting modules.

Tests:
  - Metric formulas and invariants (MAE, WAPE, MAPE, RMSE)
  - Baseline heuristics (Naive persistence, linear drift, moving average)
  - Model abstractions, registry, and rejected models contract
  - State-level aggregate time-series aggregation
  - Expanding-window walk-forward backtesting engine (Folds 1 & 2)
  - Retrospective 2023-24 scenario bands and implied staffing demand
"""

from typing import Any

import numpy as np
import pandas as pd
import pytest

from school_planning.forecasting.backtesting import (
    DEFAULT_CANDIDATE_MODELS,
    DEFAULT_FOLDS,
    aggregate_state_time_series,
    run_walk_forward_backtest,
)
from school_planning.forecasting.baselines import (
    predict_drift,
    predict_moving_average,
    predict_naive,
)
from school_planning.forecasting.metrics import (
    calculate_mae,
    calculate_mape,
    calculate_rmse,
    calculate_wape,
    evaluate_forecast_metrics,
)
from school_planning.forecasting.models import (
    MODEL_REGISTRY,
    REJECTED_MODELS,
    DriftForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    get_forecaster,
)
from school_planning.forecasting.scenarios import (
    estimate_implied_staffing_demand,
    generate_projection_scenarios,
)

# =============================================================================
# 1. Forecast Metric Calculation Tests
# =============================================================================

class TestForecastMetrics:
    """Test mathematical correctness and edge cases for evaluation metrics."""

    def test_mae_exact_calculation(self) -> None:
        y_true = [100.0, 200.0, 300.0]
        y_pred = [110.0, 190.0, 330.0]
        # errors: 10, 10, 30 -> mean: 50/3 = 16.666...
        assert calculate_mae(y_true, y_pred) == pytest.approx(50.0 / 3.0)

    def test_wape_preferred_metric_exact_calculation(self) -> None:
        y_true = [100.0, 200.0, 300.0]  # sum = 600
        y_pred = [110.0, 190.0, 330.0]  # sum abs error = 10 + 10 + 30 = 50
        # WAPE = 50 / 600 * 100 = 8.3333%
        assert calculate_wape(y_true, y_pred) == pytest.approx(50.0 / 600.0 * 100.0)

    def test_mape_exact_calculation(self) -> None:
        y_true = [100.0, 200.0]
        y_pred = [110.0, 190.0]
        # pct errors: 10/100 = 10%, 10/200 = 5% -> mean: 7.5%
        assert calculate_mape(y_true, y_pred) == pytest.approx(7.5)

    def test_mape_handles_zero_actuals_without_division_by_zero(self) -> None:
        y_true = [0.0, 100.0]
        y_pred = [10.0, 110.0]
        # Zero is excluded from MAPE calculation
        assert calculate_mape(y_true, y_pred) == pytest.approx(10.0)

    def test_rmse_exact_calculation(self) -> None:
        y_true = [100.0, 200.0]
        y_pred = [103.0, 196.0]
        # errors: 3, -4; squared: 9, 16; mean: 12.5; sqrt: 3.5355...
        assert calculate_rmse(y_true, y_pred) == pytest.approx(np.sqrt(12.5))

    def test_evaluate_forecast_metrics_dictionary(self) -> None:
        y_true = [500.0, 1000.0]
        y_pred = [520.0, 980.0]
        res = evaluate_forecast_metrics(y_true, y_pred)
        assert set(res.keys()) == {"mae", "wape", "mape", "rmse"}
        assert res["mae"] == pytest.approx(20.0)
        assert res["wape"] == pytest.approx(40.0 / 1500.0 * 100.0)

    def test_shape_mismatch_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Shape mismatch"):
            calculate_mae([1.0, 2.0], [1.0])

    def test_empty_series_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            calculate_mae([], [])

    def test_pairwise_nan_handling(self) -> None:
        y_true = [100.0, np.nan, 200.0]
        y_pred = [110.0, 150.0, 190.0]
        # Pairs: (100, 110) error 10, (200, 190) error 10 -> mean: 10
        assert calculate_mae(y_true, y_pred) == pytest.approx(10.0)


# =============================================================================
# 2. Baseline Forecaster Heuristic Tests
# =============================================================================

class TestBaselineForecasters:
    """Test baseline heuristic forecasting logic."""

    def test_predict_naive_one_step(self) -> None:
        history = [100.0, 105.0, 110.0]
        pred = predict_naive(history, horizon=1)
        assert pred == pytest.approx(110.0)

    def test_predict_naive_multi_step(self) -> None:
        history = [100.0, 105.0, 110.0]
        preds = predict_naive(history, horizon=3)
        assert isinstance(preds, np.ndarray)
        assert np.allclose(preds, [110.0, 110.0, 110.0])

    def test_predict_naive_clips_negative_when_configured(self) -> None:
        history = [10.0, -5.0]
        pred = predict_naive(history, horizon=1, clip_non_negative=True)
        assert pred == 0.0

    def test_predict_drift_linear_progression(self) -> None:
        # History: [100, 110, 120] -> t=3 periods, total drift = 120 - 100 = 20, annual drift = 20 / 2 = 10
        # h=1 -> 120 + 10 = 130
        history = [100.0, 110.0, 120.0]
        pred = predict_drift(history, horizon=1)
        assert pred == pytest.approx(130.0)

    def test_predict_drift_multi_step(self) -> None:
        history = [100.0, 110.0, 120.0]
        preds = predict_drift(history, horizon=2)
        assert np.allclose(preds, [130.0, 140.0])

    def test_predict_drift_single_observation_fallback(self) -> None:
        history = [500.0]
        pred = predict_drift(history, horizon=1)
        assert pred == pytest.approx(500.0)

    def test_predict_drift_negative_truncation(self) -> None:
        # Steep decline: [100, 40] -> drift = -60 -> h=1: 40 - 60 = -20 -> clamped to 0.0
        history = [100.0, 40.0]
        pred = predict_drift(history, horizon=1, clip_non_negative=True)
        assert pred == 0.0

    def test_predict_moving_average_3_period(self) -> None:
        history = [80.0, 100.0, 110.0, 120.0]
        # Last 3: 100, 110, 120 -> mean = 110
        pred = predict_moving_average(history, window=3, horizon=1)
        assert pred == pytest.approx(110.0)

    def test_predict_moving_average_fewer_periods_than_window(self) -> None:
        history = [100.0, 120.0]
        # Window=3 but only 2 available -> mean(100, 120) = 110
        pred = predict_moving_average(history, window=3, horizon=1)
        assert pred == pytest.approx(110.0)

    def test_invalid_horizon_raises_error(self) -> None:
        with pytest.raises(ValueError, match="horizon"):
            predict_naive([10.0], horizon=0)

    def test_predict_drift_with_missing_interior_year_uses_elapsed_time(self) -> None:
        # Years: 2018-19 (100.0) and 2020-21 (120.0), missing 2019-20.
        # Elapsed time = 2020 - 2018 = 2 years.
        # Drift per year = (120 - 100) / 2 = 10.0.
        # Forecasting 2021-22 (1 year ahead of 2020-21): 120 + 10 * 1 = 130.0.
        # (If silent compression occurred ignoring time index, drift would be (120-100)/1 = 20, yielding 140.0)
        history = [100.0, 120.0]
        years = ["2018-19", "2020-21"]
        pred = predict_drift(history, horizon=1, years=years, target_year="2021-22")
        assert pred == pytest.approx(130.0)

    def test_predict_moving_average_with_missing_interior_year_does_not_average_across_gap(self) -> None:
        # Years: 2018-19 (100.0), 2019-20 (110.0), 2021-22 (130.0), missing 2020-21.
        # Window = 3.
        # Because 2020-21 is missing, the contiguous consecutive segment ending at 2021-22 is only [130.0].
        # It must NOT silently average across the gap to include 110.0 and 100.0.
        history = [100.0, 110.0, 130.0]
        years = ["2018-19", "2019-20", "2021-22"]
        pred = predict_moving_average(history, window=3, horizon=1, years=years, target_year="2022-23")
        assert pred == pytest.approx(130.0)


# =============================================================================
# 3. Model Classes and Registry Tests
# =============================================================================

class TestModelAbstractions:
    """Test object-oriented model wrappers and configuration contract."""

    def test_model_registry_availability(self) -> None:
        assert "naive_persistence" in MODEL_REGISTRY
        assert "drift" in MODEL_REGISTRY
        assert "moving_average_3yr" in MODEL_REGISTRY

    def test_get_forecaster_factory(self) -> None:
        naive = get_forecaster("naive_persistence")
        assert isinstance(naive, NaiveForecaster)
        assert naive.name == "naive_persistence"

        drift = get_forecaster("drift")
        assert isinstance(drift, DriftForecaster)

        ma = get_forecaster("moving_average_3yr")
        assert isinstance(ma, MovingAverageForecaster)

    def test_unknown_model_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown model_name"):
            get_forecaster("arima_order_5")

    def test_rejected_models_documented_contract(self) -> None:
        # Verification that rejected models per config/forecasting.yaml are recorded with rationales
        assert "high_order_arima" in REJECTED_MODELS
        assert "prophet" in REJECTED_MODELS
        assert "machine_learning_deep_learning" in REJECTED_MODELS
        for name, reason in REJECTED_MODELS.items():
            assert len(reason) > 20, f"Rejected model {name} lacks justification"

    def test_calling_predict_before_fit_raises_runtime_error(self) -> None:
        model = NaiveForecaster()
        with pytest.raises(RuntimeError, match="must be fitted"):
            model.predict()


# =============================================================================
# 4. State Aggregation and Time Series Tests
# =============================================================================

class TestStateAggregation:
    """Test aggregation of school-level panel data into state time series."""

    @pytest.fixture
    def mock_panel(self) -> pd.DataFrame:
        return pd.DataFrame({
            "school_id": ["S1", "S2", "S3", "S1", "S2", "S3"],
            "state_name": ["Texas", "Texas", "Texas", "Texas", "Texas", "Texas"],
            "school_year": ["2018-19", "2018-19", "2018-19", "2019-20", "2019-20", "2019-20"],
            "is_operational": [True, True, False, True, True, True],
            "total_students": [500.0, 300.0, 200.0, 520.0, 310.0, 220.0],
            "teacher_fte": [25.0, 15.0, 10.0, 26.0, 16.0, 11.0],
        })

    def test_aggregate_operational_only_filters_closed_schools(self, mock_panel: pd.DataFrame) -> None:
        agg = aggregate_state_time_series(mock_panel, operational_only=True)
        # Year 2018-19: S1 (500) + S2 (300) = 800 (S3 is inactive False)
        # Year 2019-20: S1 (520) + S2 (310) + S3 (220) = 1050
        assert len(agg) == 2
        y18 = agg[agg["school_year"] == "2018-19"].iloc[0]
        assert y18["total_students"] == pytest.approx(800.0)
        assert y18["teacher_fte"] == pytest.approx(40.0)
        assert y18["school_count"] == 2

        y19 = agg[agg["school_year"] == "2019-20"].iloc[0]
        assert y19["total_students"] == pytest.approx(1050.0)
        assert y19["teacher_fte"] == pytest.approx(53.0)
        assert y19["school_count"] == 3

    def test_aggregate_all_schools_includes_inactive(self, mock_panel: pd.DataFrame) -> None:
        agg = aggregate_state_time_series(mock_panel, operational_only=False)
        y18 = agg[agg["school_year"] == "2018-19"].iloc[0]
        # With operational_only=False, S3 is included: 500 + 300 + 200 = 1000
        assert y18["total_students"] == pytest.approx(1000.0)
        assert y18["school_count"] == 3
        assert y18["contributing_operational_school_count"] == 3

    def test_aggregate_reporting_coverage_and_missing_values_metadata(self) -> None:
        # 3 operational schools in Texas for 2021-22
        # S1: both reported
        # S2: missing teacher_fte
        # S3: missing both students and teachers
        panel = pd.DataFrame({
            "school_id": ["S1", "S2", "S3"],
            "state_name": ["Texas", "Texas", "Texas"],
            "school_year": ["2021-22", "2021-22", "2021-22"],
            "is_operational": [True, True, True],
            "total_students": [500.0, 300.0, np.nan],
            "teacher_fte": [25.0, np.nan, np.nan],
        })
        agg = aggregate_state_time_series(panel, operational_only=True)
        assert len(agg) == 1
        row = agg.iloc[0]

        assert row["contributing_operational_school_count"] == 3
        # Students: 2 reported (sum=800.0), 1 missing -> 66.67% coverage, not complete census
        assert row["reported_total_students_sum"] == pytest.approx(800.0)
        assert row["reported_total_students_count"] == 2
        assert row["missing_total_students_count"] == 1
        assert row["total_students_reporting_coverage_pct"] == pytest.approx(66.67, abs=0.01)
        assert not bool(row["is_total_students_complete_census"])
        assert row["total_students"] == pytest.approx(800.0)

        # Teachers: 1 reported (sum=25.0), 2 missing -> 33.33% coverage, not complete census
        assert row["reported_teacher_fte_sum"] == pytest.approx(25.0)
        assert row["reported_teacher_fte_count"] == 1
        assert row["missing_teacher_fte_count"] == 2
        assert row["teacher_fte_reporting_coverage_pct"] == pytest.approx(33.33, abs=0.01)
        assert not bool(row["is_teacher_fte_complete_census"])
        assert row["teacher_fte"] == pytest.approx(25.0)

    def test_aggregate_zero_reporting_yields_nan_not_zero(self) -> None:
        # All operational schools in Guam for 2022-23 have missing teacher_fte
        panel = pd.DataFrame({
            "school_id": ["G1", "G2"],
            "state_name": ["Guam", "Guam"],
            "school_year": ["2022-23", "2022-23"],
            "is_operational": [True, True],
            "total_students": [400.0, 600.0],
            "teacher_fte": [np.nan, np.nan],
        })
        agg = aggregate_state_time_series(panel, operational_only=True)
        assert len(agg) == 1
        row = agg.iloc[0]

        assert row["contributing_operational_school_count"] == 2
        assert row["reported_teacher_fte_count"] == 0
        assert row["missing_teacher_fte_count"] == 2
        assert row["teacher_fte_reporting_coverage_pct"] == 0.0
        assert not bool(row["is_teacher_fte_complete_census"])
        # Crucial: must be NaN, NOT 0.0, so that 0 teachers is not erroneously imputed
        assert np.isnan(row["reported_teacher_fte_sum"])
        assert np.isnan(row["teacher_fte"])


# =============================================================================
# 5. Walk-Forward Backtesting Engine Tests
# =============================================================================

class TestWalkForwardBacktesting:
    """Test expanding window validation engine and fold structure."""

    @pytest.fixture
    def mock_5yr_state_series(self) -> pd.DataFrame:
        # Create a synthetic 5-year series for California and New York
        years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        ca_students = [6_000_000.0, 6_050_000.0, 5_900_000.0, 5_850_000.0, 5_820_000.0]
        ny_students = [2_500_000.0, 2_520_000.0, 2_450_000.0, 2_430_000.0, 2_410_000.0]

        rows = []
        for yr, ca_s, ny_s in zip(years, ca_students, ny_students):
            rows.append({"state_name": "California", "school_year": yr, "total_students": ca_s})
            rows.append({"state_name": "New York", "school_year": yr, "total_students": ny_s})
        return pd.DataFrame(rows)

    def test_default_folds_contract(self) -> None:
        assert len(DEFAULT_FOLDS) == 2
        f1, f2 = DEFAULT_FOLDS
        assert f1["fold_id"] == "fold_1"
        assert f1["train_years"] == ["2018-19", "2019-20", "2020-21"]
        assert f1["test_year"] == "2021-22"

        assert f2["fold_id"] == "fold_2"
        assert f2["train_years"] == ["2018-19", "2019-20", "2020-21", "2021-22"]
        assert f2["test_year"] == "2022-23"

    def test_backtest_execution_and_predictions(self, mock_5yr_state_series: pd.DataFrame) -> None:
        preds, summary, exclusions = run_walk_forward_backtest(
            mock_5yr_state_series,
            target_col="total_students",
            entity_col="state_name",
            year_col="school_year",
        )

        assert not preds.empty
        assert not summary.empty
        assert exclusions.empty

        # 2 states * 2 folds * 3 candidate models = 12 prediction records
        assert len(preds) == 12

        # Check fold 1 naive prediction for California
        # Train years: 2018-19 (6.0M), 2019-20 (6.05M), 2020-21 (5.9M) -> last value = 5.9M
        # Test year: 2021-22 actual = 5.85M
        ca_f1_naive = preds[
            (preds["state_name"] == "California")
            & (preds["fold_id"] == "fold_1")
            & (preds["model_name"] == "naive_persistence")
        ].iloc[0]
        assert ca_f1_naive["actual"] == pytest.approx(5_850_000.0)
        assert ca_f1_naive["predicted"] == pytest.approx(5_900_000.0)
        assert ca_f1_naive["error"] == pytest.approx(50_000.0)
        assert ca_f1_naive["abs_error"] == pytest.approx(50_000.0)

    def test_backtest_summary_metrics_structure(self, mock_5yr_state_series: pd.DataFrame) -> None:
        _, summary, _ = run_walk_forward_backtest(
            mock_5yr_state_series,
            target_col="total_students",
            entity_col="state_name",
        )

        # Expect 3 fold buckets: fold_1, fold_2, overall_pooled for each of 3 models -> 9 rows
        assert len(summary) == 9
        assert set(summary["model_name"].unique()) == set(DEFAULT_CANDIDATE_MODELS)
        assert set(summary["fold_id"].unique()) == {"fold_1", "fold_2", "overall_pooled"}

        for _, row in summary.iterrows():
            assert row["mae"] >= 0.0
            assert row["wape"] >= 0.0
            assert row["rmse"] >= 0.0
            assert row["n_observations"] in (2, 4)  # 2 entities per fold, 4 pooled

    def test_backtest_excludes_entity_with_temporal_gap_before_test_year(self) -> None:
        # State A has complete history
        # State B has 2018-19, 2019-20, but is missing 2020-21 (the immediate prior year for Fold 1 test year 2021-22)
        rows = [
            # State A
            {"state_name": "State_A", "school_year": "2018-19", "total_students": 100.0},
            {"state_name": "State_A", "school_year": "2019-20", "total_students": 105.0},
            {"state_name": "State_A", "school_year": "2020-21", "total_students": 110.0},
            {"state_name": "State_A", "school_year": "2021-22", "total_students": 115.0},
            # State B
            {"state_name": "State_B", "school_year": "2018-19", "total_students": 200.0},
            {"state_name": "State_B", "school_year": "2019-20", "total_students": 210.0},
            # Note: State B lacks 2020-21!
            {"state_name": "State_B", "school_year": "2021-22", "total_students": 220.0},
        ]
        df = pd.DataFrame(rows)

        f1 = [{
            "fold_id": "fold_1",
            "train_years": ["2018-19", "2019-20", "2020-21"],
            "test_year": "2021-22",
        }]

        preds, _, exclusions = run_walk_forward_backtest(
            df,
            target_col="total_students",
            entity_col="state_name",
            folds=f1,
        )

        # State A should be evaluated, State B should be excluded rather than compressing 2019-20 -> 2021-22 as a 1-year step
        assert "State_A" in preds["state_name"].values
        assert "State_B" not in preds["state_name"].values

        assert not exclusions.empty
        b_excl = exclusions[exclusions["entity_id"] == "State_B"].iloc[0]
        assert b_excl["fold_id"] == "fold_1"
        assert "latest_train_year_gap" in b_excl["reason"]
        assert b_excl["expected_prior_year"] == "2020-21"
        assert b_excl["actual_latest_train_year"] == "2019-20"

    def test_backtest_excludes_entity_missing_test_year_ground_truth(self) -> None:
        # State C has complete train history, but test year 2021-22 has np.nan (e.g. un-reported state)
        rows = [
            {"state_name": "State_C", "school_year": "2018-19", "total_students": 100.0},
            {"state_name": "State_C", "school_year": "2019-20", "total_students": 105.0},
            {"state_name": "State_C", "school_year": "2020-21", "total_students": 110.0},
            {"state_name": "State_C", "school_year": "2021-22", "total_students": np.nan},
        ]
        df = pd.DataFrame(rows)

        f1 = [{
            "fold_id": "fold_1",
            "train_years": ["2018-19", "2019-20", "2020-21"],
            "test_year": "2021-22",
        }]

        preds, _, exclusions = run_walk_forward_backtest(
            df,
            target_col="total_students",
            entity_col="state_name",
            folds=f1,
        )

        assert preds.empty
        assert len(exclusions) == 1
        c_excl = exclusions.iloc[0]
        assert c_excl["entity_id"] == "State_C"
        assert "null or zero" in c_excl["reason"] or "missing" in c_excl["reason"].lower()

    def test_backtest_summary_coverage_metadata_reporting(self) -> None:
        # Entity A: complete census reporting (100%)
        # Entity B: partial reporting (80%)
        rows = []
        for yr in ["2018-19", "2019-20", "2020-21", "2021-22"]:
            rows.append({
                "state_name": "State_Complete",
                "school_year": yr,
                "total_students": 1000.0,
                "total_students_reporting_coverage_pct": 100.0,
            })
            rows.append({
                "state_name": "State_Partial",
                "school_year": yr,
                "total_students": 2000.0,
                "total_students_reporting_coverage_pct": 80.0,
            })
        df = pd.DataFrame(rows)

        f1 = [{
            "fold_id": "fold_1",
            "train_years": ["2018-19", "2019-20", "2020-21"],
            "test_year": "2021-22",
        }]

        _, summary, _ = run_walk_forward_backtest(
            df,
            target_col="total_students",
            entity_col="state_name",
            folds=f1,
        )

        assert not summary.empty
        # Check that fold_1 summary records contain coverage metadata
        f1_naive = summary[
            (summary["fold_id"] == "fold_1") & (summary["model_name"] == "naive_persistence")
        ].iloc[0]

        assert f1_naive["n_observations"] == 2
        assert f1_naive["n_complete_census_obs"] == 1
        assert f1_naive["n_partial_coverage_obs"] == 1
        assert f1_naive["min_coverage_pct"] == pytest.approx(80.0)
        assert f1_naive["median_coverage_pct"] == pytest.approx(90.0)
        assert f1_naive["evaluation_basis"] == "reported_value_aggregates"
        assert "reported-value aggregates" in f1_naive["coverage_caution"]


# =============================================================================
# 6. Scenario Projections and Staffing Demand Tests
# =============================================================================

class TestScenarioProjections:
    """Test retrospective 2023-24 scenario bands and implied staffing."""

    @pytest.fixture
    def mock_state_ts(self) -> pd.DataFrame:
        return pd.DataFrame({
            "state_name": ["Ohio", "Ohio", "Ohio"],
            "school_year": ["2020-21", "2021-22", "2022-23"],
            "total_students": [1_000_000.0, 1_010_000.0, 1_020_000.0],
            "teacher_fte": [60_000.0, 60_500.0, 61_000.0],
        })

    def test_generate_projection_scenarios_bands(self, mock_state_ts: pd.DataFrame) -> None:
        scenarios = generate_projection_scenarios(
            mock_state_ts,
            target_col="total_students",
            entity_col="state_name",
            model_name="naive_persistence",
        )

        assert len(scenarios) == 1
        row = scenarios.iloc[0]
        assert row["state_name"] == "Ohio"
        assert row["projection_year"] == "2023-24"
        assert row["baseline_projection"] == pytest.approx(1_020_000.0)

        # -2% scenario: 1,020,000 * 0.98 = 999,600
        assert row["scenario_low_contraction_minus_2pct"] == pytest.approx(999_600.0)
        # +2% scenario: 1,020,000 * 1.02 = 1,040,400
        assert row["scenario_high_expansion_plus_2pct"] == pytest.approx(1_040_400.0)

        # Historical growth:
        # 2020-21 -> 2021-22: +1.0%
        # 2021-22 -> 2022-23: +0.9901%
        assert row["hist_min_yoy_growth_pct"] > 0.0
        assert row["hist_max_yoy_growth_pct"] > 0.0

    def test_estimate_implied_staffing_demand(self, mock_state_ts: pd.DataFrame) -> None:
        scenarios = generate_projection_scenarios(
            mock_state_ts,
            target_col="total_students",
            entity_col="state_name",
            model_name="naive_persistence",
        )
        # Add latest teacher FTE
        scenarios["latest_historical_teacher_fte"] = 61_000.0

        staffing = estimate_implied_staffing_demand(
            scenarios,
            baseline_enrollment_col="baseline_projection",
            latest_teachers_col="latest_historical_teacher_fte",
            latest_students_col="latest_historical_value",
        )

        row = staffing.iloc[0]
        # Historical ratio = 1,020,000 / 61,000 = 16.7213...
        # Under constant historical ratio and naive projection (1,020,000), implied teachers = 61,000
        assert row["implied_teacher_fte_baseline"] == pytest.approx(61_000.0)
        assert row["implied_staffing_gap_baseline"] == pytest.approx(0.0, abs=1e-5)

        # Under +2% expansion (1,040,400 students), implied teachers = 1,040,400 / 16.7213... = 62,220.0 (+1,220 teachers)
        assert row["implied_teacher_fte_high_expansion_plus_2pct"] == pytest.approx(62_220.0)

    def test_generate_projection_scenarios_flags_incomplete_history_lacking_latest_year(self) -> None:
        # State Alaska has historical observations ending in 2021-22 (lacking 2022-23)
        df = pd.DataFrame({
            "state_name": ["Alaska", "Alaska"],
            "school_year": ["2020-21", "2021-22"],
            "total_students": [130_000.0, 128_000.0],
        })
        scenarios = generate_projection_scenarios(
            df,
            target_col="total_students",
            entity_col="state_name",
        )
        assert len(scenarios) == 1
        row = scenarios.iloc[0]
        assert not bool(row["is_latest_year_valid"])
        assert row["latest_historical_year"] == "2021-22"
        assert "Incomplete" in row["projection_status"] and "2021-22" in row["projection_status"]

    def test_generate_projection_scenarios_calculates_yoy_growth_only_on_consecutive_years(self) -> None:
        # State has 2018-19 (100.0), 2019-20 (110.0), and 2022-23 (120.0)
        # 2018-19 -> 2019-20 is consecutive (+10.0%)
        # 2019-20 -> 2022-23 spans 3 years, so it must NOT be computed as a single-year YoY growth rate!
        df = pd.DataFrame({
            "state_name": ["Hawaii", "Hawaii", "Hawaii"],
            "school_year": ["2018-19", "2019-20", "2022-23"],
            "total_students": [100.0, 110.0, 120.0],
        })
        scenarios = generate_projection_scenarios(
            df,
            target_col="total_students",
            entity_col="state_name",
        )
        assert len(scenarios) == 1
        row = scenarios.iloc[0]
        # Only 2018-19 -> 2019-20 was consecutive, so min and max YoY are both 10.0%
        assert row["hist_min_yoy_growth_pct"] == pytest.approx(10.0)
        assert row["hist_max_yoy_growth_pct"] == pytest.approx(10.0)

    def test_estimate_implied_staffing_demand_with_and_without_target_ratio(self) -> None:
        scenarios = pd.DataFrame([{
            "state_name": "State_X",
            "projection_year": "2023-24",
            "baseline_projection": 150_000.0,
            "scenario_low_contraction_minus_2pct": 147_000.0,
            "scenario_high_expansion_plus_2pct": 153_000.0,
            "latest_historical_value": 150_000.0,
            "latest_historical_teacher_fte": 10_000.0,
        }])

        # Case 1: Without target_ratio (historical constant ratio only)
        staffing_historical = estimate_implied_staffing_demand(
            scenarios.copy(),
            target_ratio=None,
        )
        row1 = staffing_historical.iloc[0]
        # Historical ratio = 150,000 / 10,000 = 15.0
        assert row1["implied_teacher_fte_constant_ratio"] == pytest.approx(10_000.0)
        assert pd.isna(row1["policy_target_ratio_applied"])
        assert pd.isna(row1["implied_teacher_fte_policy_target"])

        # Case 2: With policy target_ratio = 12.0
        staffing_policy = estimate_implied_staffing_demand(
            scenarios.copy(),
            target_ratio=12.0,
        )
        row2 = staffing_policy.iloc[0]
        # Historical constant ratio should still be present
        assert row2["implied_teacher_fte_constant_ratio"] == pytest.approx(10_000.0)
        # Policy target ratio metrics
        assert row2["policy_target_ratio_applied"] == 12.0
        # Implied policy teachers: 150,000 / 12.0 = 12,500.0
        assert row2["implied_teacher_fte_policy_target"] == pytest.approx(12_500.0)
        # Implied staffing gap: 12,500 - 10,000 = +2,500 teachers
        assert row2["implied_staffing_gap_policy_target"] == pytest.approx(2_500.0)

    def test_generate_projection_scenarios_excludes_invalid_entity_from_projections(self) -> None:
        # Entity A: valid history ending in 2022-23 (100k students)
        # Entity B: stale history ending in 2020-21 (50k students)
        df = pd.DataFrame([
            {"state_name": "State_Valid", "school_year": "2021-22", "total_students": 98_000.0, "teacher_fte": 6_000.0},
            {"state_name": "State_Valid", "school_year": "2022-23", "total_students": 100_000.0, "teacher_fte": 6_100.0},
            {"state_name": "State_Stale", "school_year": "2019-20", "total_students": 52_000.0, "teacher_fte": 3_500.0},
            {"state_name": "State_Stale", "school_year": "2020-21", "total_students": 50_000.0, "teacher_fte": 3_400.0},
        ])

        scenarios = generate_projection_scenarios(
            df,
            target_col="total_students",
            entity_col="state_name",
        )
        assert len(scenarios) == 2

        valid_row = scenarios[scenarios["state_name"] == "State_Valid"].iloc[0]
        assert bool(valid_row["is_latest_year_valid"]) is True
        assert valid_row["baseline_projection"] == pytest.approx(100_000.0)
        assert valid_row["scenario_low_contraction_minus_2pct"] == pytest.approx(98_000.0)

        stale_row = scenarios[scenarios["state_name"] == "State_Stale"].iloc[0]
        assert bool(stale_row["is_latest_year_valid"]) is False
        assert stale_row["latest_historical_year"] == "2020-21"
        assert pd.isna(stale_row["baseline_projection"])
        assert pd.isna(stale_row["scenario_low_contraction_minus_2pct"])
        assert pd.isna(stale_row["scenario_high_expansion_plus_2pct"])

        # When calculating national totals over valid entities:
        valid_mask = scenarios["is_latest_year_valid"].astype(bool)
        national_total = float(scenarios.loc[valid_mask, "baseline_projection"].dropna().sum())
        # Must equal State_Valid only (100,000.0), NOT 150,000.0!
        assert national_total == pytest.approx(100_000.0)

    def test_generate_projection_scenarios_one_observation_history_unassessed_growth(self) -> None:
        # Entity with only one historical observation in 2022-23
        df = pd.DataFrame([
            {"state_name": "State_OneObs", "school_year": "2022-23", "total_students": 50_000.0},
        ])

        scenarios = generate_projection_scenarios(
            df,
            target_col="total_students",
            entity_col="state_name",
        )
        assert len(scenarios) == 1
        row = scenarios.iloc[0]

        # Baseline projection and fixed percentage bands should be valid numbers
        assert bool(row["is_latest_year_valid"]) is True
        assert row["baseline_projection"] == pytest.approx(50_000.0)
        assert row["scenario_low_contraction_minus_2pct"] == pytest.approx(49_000.0)
        assert row["scenario_high_expansion_plus_2pct"] == pytest.approx(51_000.0)

        # But historical growth statistics and derived bounds must be NaN (unassessed), NOT 0.0!
        assert row["consecutive_yoy_intervals_count"] == 0
        assert pd.isna(row["hist_min_yoy_growth_pct"])
        assert pd.isna(row["hist_max_yoy_growth_pct"])
        assert pd.isna(row["hist_avg_yoy_growth_pct"])
        assert pd.isna(row["scenario_hist_min_bound"])
        assert pd.isna(row["scenario_hist_max_bound"])


# =============================================================================
# 7. Pipeline Integration and Artifact Generation Tests
# =============================================================================

class TestForecastingPipelineExecution:
    """Test end-to-end execution of scripts/05_run_forecasting.py in isolated directory."""

    @pytest.fixture
    def mock_pipeline_data(self, tmp_path: pytest.TempPathFactory) -> dict[str, Any]:
        import importlib.util
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "05_run_forecasting.py"
        spec = importlib.util.spec_from_file_location("run_forecasting_mod", script_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run_fn = mod.run_forecasting_pipeline

        # Create synthetic 5-year panel for 3 states
        years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        states = ["California", "Texas", "Florida"]

        records = []
        for yr_idx, yr in enumerate(years):
            for s_idx, state in enumerate(states):
                for sch_idx in range(5):
                    sch_id = f"SCH_{s_idx}_{sch_idx}"
                    records.append({
                        "school_id": sch_id,
                        "state_name": state,
                        "school_year": yr,
                        "is_operational": True,
                        "total_students": 500.0 + yr_idx * 10.0 + sch_idx * 50.0,
                        "teacher_fte": 25.0 + yr_idx * 0.5 + sch_idx * 2.5,
                    })

        panel_df = pd.DataFrame(records)
        panel_file = tmp_path / "test_panel.parquet"
        panel_df.to_parquet(panel_file, index=False)

        tables_dir = tmp_path / "tables"
        reports_dir = tmp_path / "reports"
        agg_dir = tmp_path / "aggregates"

        return {
            "run_fn": run_fn,
            "panel_path": panel_file,
            "tables_dir": tables_dir,
            "reports_dir": reports_dir,
            "aggregates_dir": agg_dir,
        }

    def test_pipeline_execution_generates_all_required_artifacts(
        self,
        mock_pipeline_data: dict[str, Any],
    ) -> None:
        run_fn = mock_pipeline_data["run_fn"]
        report = run_fn(
            panel_path=mock_pipeline_data["panel_path"],
            output_tables_dir=mock_pipeline_data["tables_dir"],
            output_reports_dir=mock_pipeline_data["reports_dir"],
            aggregates_dir=mock_pipeline_data["aggregates_dir"],
        )

        assert report["pipeline"] == "Phase 6 Forecasting Feasibility and Backtesting"
        assert report["time_series_properties"]["time_series_length"] == 5
        assert report["time_series_properties"]["states_observed"] == 3

        # Verify output files exist on disk
        tables_dir = mock_pipeline_data["tables_dir"]
        reports_dir = mock_pipeline_data["reports_dir"]
        agg_dir = mock_pipeline_data["aggregates_dir"]

        assert (tables_dir / "state_annual_aggregates.csv").exists()
        assert (tables_dir / "backtest_predictions_detailed.csv").exists()
        assert (tables_dir / "backtest_model_comparison.csv").exists()
        assert (tables_dir / "backtest_exclusions.csv").exists()
        assert (tables_dir / "retrospective_2023_24_projections.csv").exists()
        assert (agg_dir / "state_annual_aggregates.parquet").exists()
        assert (reports_dir / "forecasting_evaluation_report.json").exists()

        # Check table contents
        comp_df = pd.read_csv(tables_dir / "backtest_model_comparison.csv")
        assert not comp_df.empty
        assert set(comp_df["model_name"].unique()) == set(DEFAULT_CANDIDATE_MODELS)
        assert set(comp_df["target_col"].unique()) == {"total_students", "teacher_fte"}

        proj_df = pd.read_csv(tables_dir / "retrospective_2023_24_projections.csv")
        assert len(proj_df) == 3
        assert "baseline_projection" in proj_df.columns
        assert "scenario_low_contraction_minus_2pct" in proj_df.columns
        assert "scenario_high_expansion_plus_2pct" in proj_df.columns
        assert "implied_teacher_fte_baseline" in proj_df.columns

        # Verify new coverage and scope metadata in report
        assert report["backtesting_results"]["evaluation_basis"] == "reported_value_aggregates"
        assert "coverage_caution" in report["backtesting_results"]
        assert report["retrospective_2023_24_projections"]["eligible_entities_count"] == 3
        assert report["retrospective_2023_24_projections"]["excluded_entities_count"] == 0
        assert "national_totals_coverage_scope" in report["retrospective_2023_24_projections"]
