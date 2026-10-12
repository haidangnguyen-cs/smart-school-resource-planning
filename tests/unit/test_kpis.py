"""Unit tests for KPI formulas, growth calculations, peer-group segmentation, and distributions."""

import numpy as np
import pandas as pd

from school_planning.analytics.descriptive import (
    summarize_by_category,
    summarize_distributions,
    summarize_state_aggregates,
)
from school_planning.analytics.growth import compute_longitudinal_growth
from school_planning.analytics.kpis import (
    calculate_school_kpis,
    compute_growth_gap,
    compute_student_teacher_ratio,
)
from school_planning.analytics.segmentation import (
    BENCHMARKED_STATUS_LABEL,
    NON_OPERATIONAL_STATUS_LABEL,
    UNBENCHMARKED_STATUS_LABEL,
    classify_peer_group_eligibility,
    compute_peer_group_p90_thresholds,
)


class TestRatioFormulasAndZeroHandling:
    """Test student-teacher ratio calculation and edge cases."""

    def test_valid_ratio_calculation(self):
        df = pd.DataFrame({
            "total_students": [300.0, 450.0, 100.0],
            "teacher_fte": [20.0, 30.0, 10.0],
            "teacher_data_flag": ["Reported", "Reported", "Reported"],
            "zero_teacher_anomaly": [False, False, False],
        })
        ratios = compute_student_teacher_ratio(df)
        assert ratios.iloc[0] == 15.0
        assert ratios.iloc[1] == 15.0
        assert ratios.iloc[2] == 10.0

    def test_zero_teacher_and_anomaly_handling(self):
        df = pd.DataFrame({
            "total_students": [300.0, 450.0, 200.0],
            "teacher_fte": [0.0, 25.0, 20.0],
            "teacher_data_flag": ["Reported", "Reported", "Missing"],
            "zero_teacher_anomaly": [True, True, False],
        })
        ratios = compute_student_teacher_ratio(df)
        # 1st row has zero FTE -> NaN
        assert np.isnan(ratios.iloc[0])
        # 2nd row has positive FTE but zero_teacher_anomaly flag -> NaN
        assert np.isnan(ratios.iloc[1])
        # 3rd row has teacher_data_flag = Missing -> NaN
        assert np.isnan(ratios.iloc[2])

    def test_negative_or_missing_students_handling(self):
        df = pd.DataFrame({
            "total_students": [-1.0, np.nan, 300.0],
            "teacher_fte": [20.0, 20.0, 20.0],
        })
        ratios = compute_student_teacher_ratio(df)
        assert np.isnan(ratios.iloc[0])
        assert np.isnan(ratios.iloc[1])
        assert ratios.iloc[2] == 15.0

    def test_calculate_school_kpis_integration(self):
        df = pd.DataFrame({
            "school_id": ["01001"],
            "total_students": [300.0],
            "teacher_fte": [20.0],
        })
        augmented = calculate_school_kpis(df)
        assert "student_teacher_ratio" in augmented.columns
        assert augmented["student_teacher_ratio"].iloc[0] == 15.0


class TestGrowthMetricsAndCohorts:
    """Test YoY growth rates and common-school cohort rules."""

    def test_growth_gap_formula(self):
        # 10% enrollment growth vs 2% staffing growth -> +8%p gap
        gap = compute_growth_gap(pd.Series([10.0]), pd.Series([2.0]))
        assert gap.iloc[0] == 8.0

        # 2% enrollment growth vs 5% staffing growth -> -3%p gap
        gap2 = compute_growth_gap(pd.Series([2.0]), pd.Series([5.0]))
        assert gap2.iloc[0] == -3.0

        # NaN propagation
        gap_nan = compute_growth_gap(pd.Series([np.nan]), pd.Series([5.0]))
        assert np.isnan(gap_nan.iloc[0])

    def test_longitudinal_growth_consecutive_years(self):
        panel = pd.DataFrame({
            "school_id": ["01001", "01001", "01002", "01002"],
            "school_year": ["2018-19", "2019-20", "2018-19", "2019-20"],
            "total_students": [300.0, 330.0, 200.0, 200.0],  # 01001 grew 10%, 01002 grew 0%
            "teacher_fte": [20.0, 20.0, 20.0, 25.0],        # 01001 grew 0%, 01002 grew 25%
        })

        res = compute_longitudinal_growth(panel)

        # First year of each school has no prior year -> growth is NaN
        assert np.isnan(res.loc[(res["school_id"] == "01001") & (res["school_year"] == "2018-19"), "enrollment_growth_yoy_pct"].iloc[0])

        # Second year of 01001
        row_01001_y2 = res.loc[(res["school_id"] == "01001") & (res["school_year"] == "2019-20")].iloc[0]
        assert row_01001_y2["enrollment_growth_yoy_pct"] == 10.0
        assert row_01001_y2["teacher_fte_growth_yoy_pct"] == 0.0
        assert row_01001_y2["growth_gap_pct_points"] == 10.0
        # Ratio went from 15.0 to 16.5 (+10%)
        assert round(row_01001_y2["ratio_growth_yoy_pct"], 2) == 10.0

        # Second year of 01002
        row_01002_y2 = res.loc[(res["school_id"] == "01002") & (res["school_year"] == "2019-20")].iloc[0]
        assert row_01002_y2["enrollment_growth_yoy_pct"] == 0.0
        assert row_01002_y2["teacher_fte_growth_yoy_pct"] == 25.0
        assert row_01002_y2["growth_gap_pct_points"] == -25.0
        # Ratio went from 10.0 to 8.0 (-20%)
        assert round(row_01002_y2["ratio_growth_yoy_pct"], 2) == -20.0

    def test_longitudinal_growth_non_consecutive_years_uncomputable(self):
        # Gap of 2 years: 2018-19 to 2020-21
        panel = pd.DataFrame({
            "school_id": ["01001", "01001"],
            "school_year": ["2018-19", "2020-21"],
            "total_students": [300.0, 330.0],
            "teacher_fte": [20.0, 20.0],
        })
        res = compute_longitudinal_growth(panel)
        # Year 2020-21 should NOT compute YoY growth from 2018-19
        assert np.isnan(res["enrollment_growth_yoy_pct"].iloc[1])

    def test_operational_continuity_in_longitudinal_growth(self):
        """Verify that growth metrics are computed only between consecutive operational records."""
        panel = pd.DataFrame({
            "school_id": [
                # School 1: Open -> Open (valid consecutive operational)
                "S_OPEN_OPEN", "S_OPEN_OPEN",
                # School 2: Closed -> Open (reopened/transition: must NOT compute growth)
                "S_CLOSED_OPEN", "S_CLOSED_OPEN",
                # School 3: Open -> Closed (closing transition: must NOT compute growth)
                "S_OPEN_CLOSED", "S_OPEN_CLOSED",
                # School 4: New -> Open (new school transition: valid consecutive operational)
                "S_NEW_OPEN", "S_NEW_OPEN",
            ],
            "school_year": [
                "2018-19", "2019-20",
                "2018-19", "2019-20",
                "2018-19", "2019-20",
                "2018-19", "2019-20",
            ],
            "school_status": [
                "Open", "Open",
                "Closed", "Open",
                "Open", "Closed",
                "New", "Open",
            ],
            "is_operational": [
                True, True,
                False, True,
                True, False,
                True, True,
            ],
            "total_students": [
                300.0, 330.0,
                200.0, 250.0,
                300.0, 100.0,
                150.0, 180.0,
            ],
            "teacher_fte": [
                20.0, 22.0,
                10.0, 15.0,
                20.0, 5.0,
                10.0, 12.0,
            ],
        })

        res = compute_longitudinal_growth(panel)

        # 1. Open -> Open: 10% enrollment growth, 10% teacher growth, 0.0 growth gap
        s_open = res[(res["school_id"] == "S_OPEN_OPEN") & (res["school_year"] == "2019-20")].iloc[0]
        assert s_open["enrollment_growth_yoy_pct"] == 10.0
        assert s_open["teacher_fte_growth_yoy_pct"] == 10.0
        assert s_open["growth_gap_pct_points"] == 0.0
        assert not np.isnan(s_open["ratio_growth_yoy_pct"])

        # 2. Closed -> Open: prior was non-operational -> all growth metrics must be NaN
        s_closed_open = res[(res["school_id"] == "S_CLOSED_OPEN") & (res["school_year"] == "2019-20")].iloc[0]
        assert np.isnan(s_closed_open["enrollment_growth_yoy_pct"])
        assert np.isnan(s_closed_open["teacher_fte_growth_yoy_pct"])
        assert np.isnan(s_closed_open["ratio_growth_yoy_pct"])
        assert np.isnan(s_closed_open["growth_gap_pct_points"])

        # 3. Open -> Closed: current is non-operational -> all growth metrics must be NaN
        s_open_closed = res[(res["school_id"] == "S_OPEN_CLOSED") & (res["school_year"] == "2019-20")].iloc[0]
        assert np.isnan(s_open_closed["enrollment_growth_yoy_pct"])
        assert np.isnan(s_open_closed["teacher_fte_growth_yoy_pct"])
        assert np.isnan(s_open_closed["ratio_growth_yoy_pct"])
        assert np.isnan(s_open_closed["growth_gap_pct_points"])

        # 4. New -> Open: both operational -> growth computed normally (20% enrollment, 20% staffing)
        s_new_open = res[(res["school_id"] == "S_NEW_OPEN") & (res["school_year"] == "2019-20")].iloc[0]
        assert s_new_open["enrollment_growth_yoy_pct"] == 20.0
        assert s_new_open["teacher_fte_growth_yoy_pct"] == 20.0
        assert s_new_open["growth_gap_pct_points"] == 0.0

        # Raw input values and panel rows are preserved
        assert len(res) == len(panel) == 8
        assert s_closed_open["total_students"] == 250.0
        assert s_closed_open["prior_total_students"] == 200.0



class TestPeerGroupSegmentationAndP90:
    """Test peer-group categorization and empirical P90 baselines."""

    def test_peer_group_eligibility_classification(self):
        df = pd.DataFrame({
            "school_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "school_type": [
                "Regular School",
                "Regular School",
                "Regular School",
                "Special Education School",
                "Regular School",
                "Career and Technical School",
            ],
            "school_level": [
                "Elementary",
                "Middle",
                "High",
                "Elementary",
                "Secondary",  # Not eligible
                "High",        # Non-regular type
            ],
        })

        res = classify_peer_group_eligibility(df)

        assert res["is_p90_eligible"].tolist() == [True, True, True, False, False, False]
        assert res["peer_group_status"].iloc[0] == BENCHMARKED_STATUS_LABEL
        assert res["peer_group_status"].iloc[3] == UNBENCHMARKED_STATUS_LABEL
        assert res["peer_group_status"].iloc[4] == UNBENCHMARKED_STATUS_LABEL
        assert res["peer_group_status"].iloc[5] == UNBENCHMARKED_STATUS_LABEL

    def test_compute_peer_group_p90_thresholds(self):
        # Create synthetic cohort of Elementary schools with known distribution
        ratios = [10.0, 12.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 25.0, 30.0]
        df = pd.DataFrame({
            "school_id": [f"S{i}" for i in range(len(ratios))],
            "school_year": ["2018-19"] * len(ratios),
            "school_type": ["Regular School"] * len(ratios),
            "school_level": ["Elementary"] * len(ratios),
            "student_teacher_ratio": ratios,
        })

        # Add one unbenchmarked school with ratio 35.0
        unbenchmarked = pd.DataFrame({
            "school_id": ["S_UNBENCH"],
            "school_year": ["2018-19"],
            "school_type": ["Special Education School"],
            "school_level": ["Elementary"],
            "student_teacher_ratio": [35.0],
        })
        full_df = pd.concat([df, unbenchmarked], ignore_index=True)

        res, thresholds = compute_peer_group_p90_thresholds(full_df)

        key = "2018-19_Elementary"
        assert key in thresholds
        assert thresholds[key]["sample_size"] == 10
        expected_p90 = float(pd.Series(ratios).quantile(0.90))
        assert thresholds[key]["p90_ratio"] == round(expected_p90, 2)

        # Unbenchmarked school does not get a peer-group P90 and is not flagged above P90
        unbench_row = res[res["school_id"] == "S_UNBENCH"].iloc[0]
        assert np.isnan(unbench_row["peer_group_p90_ratio"])
        assert bool(unbench_row["is_above_p90_ratio"]) is False

        # Highest regular school (ratio 30.0 >= p90 ~25.5) should be flagged
        highest_reg = res[res["school_id"] == "S9"].iloc[0]
        assert bool(highest_reg["is_above_p90_ratio"]) is True

    def test_p90_boundary_inclusive_equality(self):
        """Verify that a school whose ratio exactly equals its stratum P90 is flagged under inclusive >= contract."""
        df = pd.DataFrame({
            "school_id": [f"S{i}" for i in range(10)],
            "school_year": ["2018-19"] * 10,
            "school_type": ["Regular School"] * 10,
            "school_level": ["Middle"] * 10,
            "student_teacher_ratio": [10.0, 12.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 25.0, 25.0],
        })
        res, thresholds = compute_peer_group_p90_thresholds(df)
        p90_val = thresholds["2018-19_Middle"]["p90_ratio"]
        # In this dataset, p90_val is 25.0 (the 90th percentile of [10..25, 25])
        assert p90_val == 25.0

        # Schools S8 and S9 have ratio == 25.0 == p90_val -> must be True under ratio >= P90
        s8_row = res[res["school_id"] == "S8"].iloc[0]
        s9_row = res[res["school_id"] == "S9"].iloc[0]
        assert bool(s8_row["is_above_p90_ratio"]) is True
        assert bool(s9_row["is_above_p90_ratio"]) is True

    def test_zero_ratio_included_in_p90_sample(self):
        """Verify that valid zero-ratio schools (total_students == 0, teacher_fte > 0) are included in P90 baseline."""
        df = pd.DataFrame({
            "school_id": ["S_ZERO", "S_POS1", "S_POS2"],
            "school_year": ["2018-19"] * 3,
            "school_type": ["Regular School"] * 3,
            "school_level": ["Elementary"] * 3,
            "student_teacher_ratio": [0.0, 15.0, 20.0],
        })
        res, thresholds = compute_peer_group_p90_thresholds(df)
        assert thresholds["2018-19_Elementary"]["sample_size"] == 3
        zero_row = res[res["school_id"] == "S_ZERO"].iloc[0]
        assert bool(zero_row["is_p90_eligible"]) is True
        assert not np.isnan(zero_row["peer_group_p90_ratio"])
        assert bool(zero_row["is_above_p90_ratio"]) is False


class TestDescriptiveAnalytics:
    """Test summary statistics and aggregations."""

    def test_summarize_distributions(self):
        df = pd.DataFrame({
            "total_students": [100.0, 200.0, 300.0, 400.0, 500.0],
            "teacher_fte": [10.0, 20.0, 30.0, 40.0, 50.0],
            "student_teacher_ratio": [10.0, 10.0, 10.0, 10.0, 10.0],
        })
        summary = summarize_distributions(df)
        assert "total_students" in summary.index
        assert summary.loc["total_students", "count"] == 5
        assert summary.loc["total_students", "median"] == 300.0
        assert summary.loc["student_teacher_ratio", "mean"] == 10.0

    def test_summarize_state_aggregates(self):
        df = pd.DataFrame({
            "school_id": ["S1", "S2", "S3"],
            "state_fips": ["01", "01", "02"],
            "school_year": ["2018-19", "2018-19", "2018-19"],
            "total_students": [300.0, 600.0, 200.0],
            "teacher_fte": [20.0, 30.0, 10.0],
            "student_teacher_ratio": [15.0, 20.0, 20.0],
        })
        state_aggs = summarize_state_aggregates(df)
        # State 01: 900 students, 50 teachers -> system ratio 18.0
        s01 = state_aggs[state_aggs["state_fips"] == "01"].iloc[0]
        assert s01["school_count"] == 2
        assert s01["total_students"] == 900.0
        assert s01["total_teacher_fte"] == 50.0
        assert s01["system_student_teacher_ratio"] == 18.0

    def test_summarize_by_category(self):
        df = pd.DataFrame({
            "school_id": ["S1", "S2", "S3"],
            "school_level": ["Elementary", "Elementary", "High"],
            "total_students": [300.0, 500.0, 1000.0],
            "teacher_fte": [20.0, 25.0, 50.0],
            "student_teacher_ratio": [15.0, 20.0, 20.0],
        })
        cat_summary = summarize_by_category(df, "school_level")
        elem_row = cat_summary[cat_summary["school_level"] == "Elementary"].iloc[0]
        assert elem_row["school_count"] == 2
        assert elem_row["total_students_mean"] == 400.0


class TestOperationalCohortContractRegressions:
    """Regression tests for active operational cohort contract (config/project.yaml)."""

    def test_structural_vs_operational_eligibility_distinction(self):
        """Verify structural peer-group eligibility is distinct from operational eligibility."""
        df = pd.DataFrame({
            "school_id": ["S_ACT_REG", "S_INACT_REG", "S_ACT_SPEC", "S_INACT_SPEC", "S_TRANS_REG"],
            "school_type": [
                "Regular School",
                "Regular School",
                "Special Education School",
                "Special Education School",
                "Regular School",
            ],
            "school_level": [
                "Elementary",
                "Elementary",
                "Elementary",
                "Elementary",
                "Elementary",
            ],
            "is_operational": [True, False, True, False, False],
            "school_status": ["Open", "Closed", "Open", "Inactive", "Added"],
        })

        res = classify_peer_group_eligibility(df)

        # Structural eligibility: Regular Elementary
        assert res["is_structurally_eligible"].tolist() == [True, True, False, False, True]
        # Operational eligibility: Open/New, excluding transition review
        assert res["is_operational"].tolist() == [True, False, True, False, False]
        # P90 benchmark eligibility: structurally eligible AND operational
        assert res["is_p90_eligible"].tolist() == [True, False, False, False, False]

        # Status labels
        assert res["peer_group_status"].iloc[0] == BENCHMARKED_STATUS_LABEL
        assert res["peer_group_status"].iloc[1] == NON_OPERATIONAL_STATUS_LABEL
        assert res["peer_group_status"].iloc[2] == UNBENCHMARKED_STATUS_LABEL
        assert res["peer_group_status"].iloc[3] == NON_OPERATIONAL_STATUS_LABEL
        assert res["peer_group_status"].iloc[4] == NON_OPERATIONAL_STATUS_LABEL

    def test_inactive_high_ratio_school_does_not_influence_p90_or_get_flagged(self):
        """Verify inactive and transition-review high-ratio schools do not distort P90 thresholds or get flagged."""
        # 10 active Regular Elementary schools with ratios [10..25]
        active_ratios = [10.0, 12.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 25.0, 25.0]
        active_df = pd.DataFrame({
            "school_id": [f"S_ACT_{i}" for i in range(len(active_ratios))],
            "school_year": ["2018-19"] * len(active_ratios),
            "school_type": ["Regular School"] * len(active_ratios),
            "school_level": ["Elementary"] * len(active_ratios),
            "student_teacher_ratio": active_ratios,
            "is_operational": [True] * len(active_ratios),
            "school_status": ["Open"] * len(active_ratios),
        })

        # Inactive school with extreme outlier ratio (100.0)
        inactive_df = pd.DataFrame({
            "school_id": ["S_INACTIVE_EXTREME"],
            "school_year": ["2018-19"],
            "school_type": ["Regular School"],
            "school_level": ["Elementary"],
            "student_teacher_ratio": [100.0],
            "is_operational": [False],
            "school_status": ["Closed"],
        })

        # Transition-review school with high ratio (80.0)
        transition_df = pd.DataFrame({
            "school_id": ["S_TRANSITION_REVIEW"],
            "school_year": ["2018-19"],
            "school_type": ["Regular School"],
            "school_level": ["Elementary"],
            "student_teacher_ratio": [80.0],
            "is_operational": [False],
            "school_status": ["Added"],
        })

        full_panel = pd.concat([active_df, inactive_df, transition_df], ignore_index=True)

        res, thresholds = compute_peer_group_p90_thresholds(full_panel)

        # 1. Benchmark sample contains strictly the 10 active eligible schools
        key = "2018-19_Elementary"
        assert key in thresholds
        assert thresholds[key]["sample_size"] == 10

        # 2. P90 threshold is exactly 25.0 (calculated strictly from the 10 active schools, not inflated by 100 or 80)
        assert thresholds[key]["p90_ratio"] == 25.0

        # 3. Inactive high-ratio school does NOT receive an above-P90 flag
        inactive_row = res[res["school_id"] == "S_INACTIVE_EXTREME"].iloc[0]
        assert bool(inactive_row["is_p90_eligible"]) is False
        assert bool(inactive_row["is_above_p90_ratio"]) is False
        assert np.isnan(inactive_row["peer_group_p90_ratio"])

        # 4. Transition-review school does NOT receive an above-P90 flag
        trans_row = res[res["school_id"] == "S_TRANSITION_REVIEW"].iloc[0]
        assert bool(trans_row["is_p90_eligible"]) is False
        assert bool(trans_row["is_above_p90_ratio"]) is False
        assert np.isnan(trans_row["peer_group_p90_ratio"])

        # 5. Active schools with ratio >= P90 remain flagged
        s8_row = res[res["school_id"] == "S_ACT_8"].iloc[0]
        s9_row = res[res["school_id"] == "S_ACT_9"].iloc[0]
        assert bool(s8_row["is_above_p90_ratio"]) is True
        assert bool(s9_row["is_above_p90_ratio"]) is True

        # 6. Full panel records are preserved (all 12 rows retained for audit/status review)
        assert len(res) == len(full_panel) == 12

    def test_operational_summary_metrics_exclude_non_operational_records(self):
        """Verify operational summary distributions and state aggregates exclude non-operational records."""
        df = pd.DataFrame({
            "school_id": ["S1", "S2", "S3", "S_CLOSED_1", "S_CLOSED_2"],
            "state_fips": ["01", "01", "01", "01", "01"],
            "school_year": ["2018-19"] * 5,
            "school_level": ["Elementary", "Elementary", "Elementary", "Elementary", "Elementary"],
            "total_students": [100.0, 200.0, 300.0, 9999.0, 8888.0],
            "teacher_fte": [10.0, 20.0, 30.0, 1.0, 1.0],
            "student_teacher_ratio": [10.0, 10.0, 10.0, 9999.0, 8888.0],
            "is_operational": [True, True, True, False, False],
        })

        # summarize_distributions on operational cohort
        dist = summarize_distributions(df)
        assert dist.loc["total_students", "count"] == 3
        assert dist.loc["total_students", "mean"] == 200.0
        assert dist.loc["student_teacher_ratio", "mean"] == 10.0

        # summarize_state_aggregates on operational cohort
        state_aggs = summarize_state_aggregates(df)
        assert state_aggs["school_count"].iloc[0] == 3
        assert state_aggs["total_students"].iloc[0] == 600.0
        assert state_aggs["total_teacher_fte"].iloc[0] == 60.0
        assert state_aggs["system_student_teacher_ratio"].iloc[0] == 10.0

    def test_multi_year_categorical_summaries_distinguish_school_years(self):
        """Verify categorical summaries distinguish school-year observations and do not pool across years."""
        df = pd.DataFrame({
            "school_id": ["S1", "S2", "S3", "S1", "S2", "S3", "S4", "S5"],
            "school_year": [
                "2018-19", "2018-19", "2018-19",  # Year 1: 2 Elementary, 1 High
                "2019-20", "2019-20", "2019-20", "2019-20", "2019-20",  # Year 2: 3 Elementary, 2 High
            ],
            "school_level": [
                "Elementary", "Elementary", "High",
                "Elementary", "Elementary", "Elementary", "High", "High",
            ],
            "total_students": [200.0, 300.0, 800.0, 210.0, 310.0, 400.0, 850.0, 900.0],
            "teacher_fte": [10.0, 15.0, 40.0, 10.0, 15.0, 20.0, 40.0, 45.0],
            "student_teacher_ratio": [20.0, 20.0, 20.0, 21.0, 20.67, 20.0, 21.25, 20.0],
            "is_operational": [True] * 8,
        })

        summary = summarize_by_category(df, "school_level")

        # Must have 4 distinct year-level slices
        assert len(summary) == 4
        assert "school_year" in summary.columns
        assert "school_level" in summary.columns

        # Verify exact year slices
        y1_elem = summary[(summary["school_year"] == "2018-19") & (summary["school_level"] == "Elementary")].iloc[0]
        assert y1_elem["school_count"] == 2

        y1_high = summary[(summary["school_year"] == "2018-19") & (summary["school_level"] == "High")].iloc[0]
        assert y1_high["school_count"] == 1

        y2_elem = summary[(summary["school_year"] == "2019-20") & (summary["school_level"] == "Elementary")].iloc[0]
        assert y2_elem["school_count"] == 3

        y2_high = summary[(summary["school_year"] == "2019-20") & (summary["school_level"] == "High")].iloc[0]
        assert y2_high["school_count"] == 2

    def test_peer_group_and_operational_counts_in_pipeline(self, tmp_path, monkeypatch):
        """Verify analytics pipeline reports mutually exclusive peer-group and operational categories."""
        import importlib.util
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent
        script_path = project_root / "scripts" / "04_run_analytics.py"
        spec = importlib.util.spec_from_file_location("run_analytics_script", script_path)
        assert spec is not None and spec.loader is not None
        run_analytics_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_analytics_mod)

        # Isolate PROJECT_ROOT to temporary directory so tests never write to repository
        monkeypatch.setattr(run_analytics_mod, "PROJECT_ROOT", tmp_path)

        # Create panel with:
        # 1. Eligible active school (Regular School, Elementary, Open)
        # 2. Active but structurally unbenchmarked school (Special Education School, Elementary, Open)
        # 3. Closed school (Regular School, Elementary, Closed)
        panel_df = pd.DataFrame({
            "school_id": ["S_ELIGIBLE", "S_UNBENCH_ACT", "S_CLOSED"],
            "school_year": ["2018-19", "2018-19", "2018-19"],
            "school_name": ["School A", "School B", "School C"],
            "school_type": ["Regular School", "Special Education School", "Regular School"],
            "school_level": ["Elementary", "Elementary", "Elementary"],
            "school_status": ["Open", "Open", "Closed"],
            "is_operational": [True, True, False],
            "total_students": [300.0, 50.0, 0.0],
            "teacher_fte": [20.0, 10.0, 0.0],
            "teacher_data_flag": ["Reported", "Reported", "Reported"],
            "zero_teacher_anomaly": [False, False, False],
            "state_fips": ["01", "01", "01"],
            "is_charter": [False, False, False],
        })

        panel_file = tmp_path / "test_panel.parquet"
        panel_df.to_parquet(panel_file, index=False)
        tables_dir = tmp_path / "tables"
        reports_dir = tmp_path / "reports"

        summary = run_analytics_mod.run_analytics_pipeline(
            panel_path=panel_file,
            tables_dir=tables_dir,
            reports_dir=reports_dir,
        )

        # 1. Total panel records
        assert summary["panel_records"] == 3
        assert summary["operational_records"] == 2
        assert summary["non_operational_records"] == 1

        # 2. Mutually exclusive observation categories
        assert summary["benchmarked_operational_observations_count"] == 1
        assert summary["unbenchmarked_operational_observations_count"] == 1
        assert summary["non_operational_status_review_observations_count"] == 1

        # 3. Unique school IDs observed per category
        assert summary["benchmarked_operational_unique_schools_observed_count"] == 1
        assert summary["unbenchmarked_operational_unique_schools_observed_count"] == 1
        assert summary["non_operational_status_review_unique_schools_observed_count"] == 1

        # 4. Sum of mutually exclusive observation categories equals total panel records
        assert (
            summary["benchmarked_operational_observations_count"]
            + summary["unbenchmarked_operational_observations_count"]
            + summary["non_operational_status_review_observations_count"]
        ) == summary["panel_records"]
