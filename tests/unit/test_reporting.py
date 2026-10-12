"""test_reporting.py - Unit tests for tables, charts, and deliverable report generators."""

import numpy as np
import pandas as pd
import pytest

from school_planning.reporting.charts import (
    plot_backtest_model_comparison,
    plot_longitudinal_trends,
    plot_projection_scenarios,
    plot_ratio_distribution,
    plot_resource_pressure_tiers,
    save_figure,
)
from school_planning.reporting.generate_report import (
    generate_all_deliverables,
)
from school_planning.reporting.tables import (
    dataframe_to_markdown,
    format_backtest_comparison_table,
    format_kpi_summary_table,
    format_projection_scenario_table,
    format_resource_pressure_tier_table,
    format_state_summary_table,
)


@pytest.fixture
def synthetic_panel_df() -> pd.DataFrame:
    """Create synthetic longitudinal panel for testing table and chart formatting."""
    records = []
    years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
    levels = ["Primary", "Middle", "High", "Other"]
    states = [("06", "California"), ("48", "Texas"), ("36", "New York")]

    for yr_idx, yr in enumerate(years):
        for s_idx in range(40):
            state_fips, state_name = states[s_idx % len(states)]
            lvl = levels[s_idx % len(levels)]
            students = 300.0 + (s_idx * 15.0) + (yr_idx * 5.0)
            teachers = 20.0 + (s_idx * 0.8) + (yr_idx * 0.2)
            ratio = students / teachers
            tier = (s_idx % 6) + 1

            records.append(
                {
                    "school_id": f"SCH_{s_idx:04d}",
                    "school_year": yr,
                    "state_fips": state_fips,
                    "state_name": state_name,
                    "school_level": lvl,
                    "is_operational": True,
                    "is_charter": (s_idx % 5 == 0),
                    "total_students": students,
                    "teacher_fte": teachers,
                    "student_teacher_ratio": ratio,
                    "resource_pressure_priority": tier,
                    "priority_tier": tier,
                }
            )

    return pd.DataFrame(records)


@pytest.fixture
def synthetic_backtest_df() -> pd.DataFrame:
    """Create synthetic backtesting summary DataFrame."""
    return pd.DataFrame(
        [
            {
                "fold_id": "fold_1",
                "test_year": "2021-22",
                "target_col": "total_students",
                "model_name": "naive_persistence",
                "n_observations": 55,
                "wape": 1.10,
                "mae": 9916.0,
                "rmse": 18616.0,
                "min_coverage_pct": 91.2,
                "median_coverage_pct": 99.9,
            },
            {
                "fold_id": "fold_1",
                "test_year": "2021-22",
                "target_col": "total_students",
                "model_name": "drift",
                "n_observations": 55,
                "wape": 1.82,
                "mae": 16323.0,
                "rmse": 36226.0,
                "min_coverage_pct": 91.2,
                "median_coverage_pct": 99.9,
            },
            {
                "fold_id": "fold_2",
                "test_year": "2022-23",
                "target_col": "total_students",
                "model_name": "naive_persistence",
                "n_observations": 55,
                "wape": 0.93,
                "mae": 8406.0,
                "rmse": 16783.0,
                "min_coverage_pct": 87.7,
                "median_coverage_pct": 100.0,
            },
        ]
    )


@pytest.fixture
def synthetic_projections_df() -> pd.DataFrame:
    """Create synthetic scenario projections DataFrame."""
    return pd.DataFrame(
        [
            {
                "state_fips": "06",
                "state_name": "California",
                "latest_historical_value": 5500000.0,
                "baseline_projection": 5480000.0,
                "scenario_low_contraction_minus_2pct": 5370400.0,
                "scenario_high_expansion_plus_2pct": 5589600.0,
                "latest_historical_teacher_fte": 280000.0,
                "implied_teacher_fte_constant_ratio": 278981.8,
                "implied_teacher_fte_policy_target": 365333.3,
                "is_latest_year_valid": True,
            },
            {
                "state_fips": "48",
                "state_name": "Texas",
                "latest_historical_value": 5200000.0,
                "baseline_projection": 5230000.0,
                "scenario_low_contraction_minus_2pct": 5125400.0,
                "scenario_high_expansion_plus_2pct": 5334600.0,
                "latest_historical_teacher_fte": 350000.0,
                "implied_teacher_fte_constant_ratio": 352019.2,
                "implied_teacher_fte_policy_target": 348666.7,
                "is_latest_year_valid": True,
            },
        ]
    )


# -----------------------------------------------------------------------------
# Table Formatter Tests
# -----------------------------------------------------------------------------
def test_dataframe_to_markdown_empty():
    empty_df = pd.DataFrame()
    md = dataframe_to_markdown(empty_df)
    assert md == "*No data available.*"


def test_dataframe_to_markdown_formatting():
    df = pd.DataFrame(
        {
            "name": ["Alpha", "Beta"],
            "count": [1000, 2500000],
            "ratio": [15.234, np.nan],
        }
    )
    md = dataframe_to_markdown(df, headers=["Entity", "Total Count", "Student/Teacher Ratio"])
    assert "| Entity | Total Count | Student/Teacher Ratio |" in md
    assert "1,000" in md
    assert "2,500,000" in md
    assert "15.23" in md
    assert "—" in md  # NaN formatted cleanly


def test_format_kpi_summary_table(synthetic_panel_df):
    kpi_df = format_kpi_summary_table(synthetic_panel_df)
    assert len(kpi_df) == 5
    assert "school_year" in kpi_df.columns
    assert "operational_schools" in kpi_df.columns
    assert "weighted_ratio" in kpi_df.columns
    # Check that first year growth is NaN
    assert pd.isna(kpi_df.iloc[0]["enrollment_yoy_growth_pct"])
    # Subsequent year has numeric growth
    assert not pd.isna(kpi_df.iloc[1]["enrollment_yoy_growth_pct"])


def test_format_resource_pressure_tier_table(synthetic_panel_df):
    tier_df = format_resource_pressure_tier_table(synthetic_panel_df, school_year="2022-23")
    assert len(tier_df) == 6
    assert list(tier_df["tier_number"]) == [1, 2, 3, 4, 5, 6]
    # Sum of counts should equal total operational schools for that year (40)
    assert tier_df["school_count"].sum() == 40
    # Sum of percentages should be 100.0
    assert pytest.approx(tier_df["operational_pct"].sum(), 0.1) == 100.0


def test_format_state_summary_table(synthetic_panel_df):
    state_df = format_state_summary_table(synthetic_panel_df, school_year="2022-23")
    assert len(state_df) == 3
    assert "state_fips" in state_df.columns
    assert "state_name" in state_df.columns
    assert "total_triage_flagged" in state_df.columns
    # California, Texas, New York present
    assert set(state_df["state_name"]) == {"California", "Texas", "New York"}


def test_format_state_summary_table_missing_vs_zeros():
    """Verify that all-missing groups produce NaN while legitimate zeros are preserved."""
    panel = pd.DataFrame(
        [
            # State 01: All missing teachers (e.g., structural break)
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "01",
                "state_name": "StateMissing",
                "is_operational": True,
                "total_students": np.nan,
                "teacher_fte": np.nan,
                "resource_pressure_priority": 1,
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "state_fips": "01",
                "state_name": "StateMissing",
                "is_operational": True,
                "total_students": np.nan,
                "teacher_fte": np.nan,
                "resource_pressure_priority": 1,
            },
            # State 02: Legitimate observed zeros
            {
                "school_id": "S3",
                "school_year": "2022-23",
                "state_fips": "02",
                "state_name": "StateZero",
                "is_operational": True,
                "total_students": 0.0,
                "teacher_fte": 0.0,
                "resource_pressure_priority": 6,
            },
            # State 03: Normal reported values
            {
                "school_id": "S4",
                "school_year": "2022-23",
                "state_fips": "03",
                "state_name": "StateNormal",
                "is_operational": True,
                "total_students": 1000.0,
                "teacher_fte": 50.0,
                "resource_pressure_priority": 6,
            },
        ]
    )

    state_df = format_state_summary_table(panel, school_year="2022-23")
    assert len(state_df) == 3

    # Check State 01 (All Missing): MUST be NaN, NOT 0.0
    row_missing = state_df[state_df["state_fips"] == "01"].iloc[0]
    assert pd.isna(row_missing["total_students"])
    assert pd.isna(row_missing["total_teacher_fte"])
    assert pd.isna(row_missing["student_teacher_ratio"])

    # Check State 02 (Legitimate Observed Zeros): MUST be 0.0, NOT NaN
    row_zero = state_df[state_df["state_fips"] == "02"].iloc[0]
    assert row_zero["total_students"] == 0.0
    assert row_zero["total_teacher_fte"] == 0.0
    assert pd.isna(row_zero["student_teacher_ratio"])  # 0/0 is NaN

    # Check State 03 (Normal): Positive values
    row_norm = state_df[state_df["state_fips"] == "03"].iloc[0]
    assert row_norm["total_students"] == 1000.0
    assert row_norm["total_teacher_fte"] == 50.0
    assert row_norm["student_teacher_ratio"] == 20.0


def test_format_kpi_summary_table_missing_vs_zeros():
    """Verify that KPI summary table preserves NaN for all-missing years and 0.0 for zero years."""
    panel = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2021-22",
                "is_operational": True,
                "total_students": np.nan,
                "teacher_fte": np.nan,
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "is_operational": True,
                "total_students": 0.0,
                "teacher_fte": 0.0,
            },
        ]
    )
    kpi_df = format_kpi_summary_table(panel)
    assert len(kpi_df) == 2

    # 2021-22 should be NaN
    row_21 = kpi_df[kpi_df["school_year"] == "2021-22"].iloc[0]
    assert pd.isna(row_21["total_enrollment"])
    assert pd.isna(row_21["total_teacher_fte"])

    # 2022-23 should be 0.0
    row_22 = kpi_df[kpi_df["school_year"] == "2022-23"].iloc[0]
    assert row_22["total_enrollment"] == 0.0
    assert row_22["total_teacher_fte"] == 0.0


def test_operational_vs_all_reported_facilities_counts():
    """Verify operational_schools counts only is_operational==True, while all_facilities counts all rows."""
    panel = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "06",
                "state_name": "California",
                "is_operational": True,
                "total_students": 500.0,
                "teacher_fte": 25.0,
                "resource_pressure_priority": 2,
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "state_fips": "06",
                "state_name": "California",
                "is_operational": False,  # Inactive / Closed facility
                "total_students": 0.0,
                "teacher_fte": 0.0,
                "resource_pressure_priority": 1,
            },
        ]
    )

    # 1. KPI summary table when operational_only=False
    kpi_inc = format_kpi_summary_table(panel, operational_only=False)
    assert len(kpi_inc) == 1
    assert kpi_inc.iloc[0]["operational_schools"] == 1
    assert kpi_inc.iloc[0]["all_facilities"] == 2

    # 2. KPI summary table when operational_only=True
    kpi_op = format_kpi_summary_table(panel, operational_only=True)
    assert len(kpi_op) == 1
    assert kpi_op.iloc[0]["operational_schools"] == 1
    assert "all_facilities" not in kpi_op.columns

    # 3. State summary table when operational_only=False
    state_inc = format_state_summary_table(panel, school_year="2022-23", operational_only=False)
    assert len(state_inc) == 1
    assert state_inc.iloc[0]["operational_schools"] == 1
    assert state_inc.iloc[0]["all_facilities"] == 2

    # 4. State summary table when operational_only=True
    state_op = format_state_summary_table(panel, school_year="2022-23", operational_only=True)
    assert len(state_op) == 1
    assert state_op.iloc[0]["operational_schools"] == 1
    assert "all_facilities" not in state_op.columns


def test_non_operational_records_do_not_inflate_priority_counts_or_percentages():
    """Verify non-operational records do not inflate operational-cohort priority counts or percentages."""
    panel = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "06",
                "state_name": "California",
                "is_operational": True,
                "total_students": 500.0,
                "teacher_fte": 25.0,
                "resource_pressure_priority": 2,  # Operational P2
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "state_fips": "06",
                "state_name": "California",
                "is_operational": False,  # Non-operational facility
                "total_students": 0.0,
                "teacher_fte": 0.0,
                "resource_pressure_priority": 1,  # Inactive P1
            },
        ]
    )

    # State summary: priority tiers must evaluate strictly on the operational cohort
    state_df = format_state_summary_table(panel, school_year="2022-23", operational_only=False)
    row = state_df.iloc[0]
    assert row["operational_schools"] == 1
    assert row["all_facilities"] == 2
    assert row["priority_1_review"] == 0  # Inactive facility must NOT inflate P1
    assert row["priority_2_p90"] == 1  # Only S1 is operational P2
    assert row["priority_3_rising"] == 0
    assert row["priority_4_gap"] == 0
    assert row["total_triage_flagged"] == 1  # 1, not 2

    # Resource pressure tier table: denominator and counts must evaluate strictly on operational cohort
    tier_df = format_resource_pressure_tier_table(panel, school_year="2022-23")
    assert tier_df["school_count"].sum() == 1  # Only operational school
    p1_row = tier_df[tier_df["tier_number"] == 1].iloc[0]
    p2_row = tier_df[tier_df["tier_number"] == 2].iloc[0]
    assert p1_row["school_count"] == 0
    assert p1_row["operational_pct"] == 0.0
    assert p2_row["school_count"] == 1
    assert pytest.approx(p2_row["operational_pct"], 0.1) == 100.0
    assert pytest.approx(tier_df["operational_pct"].sum(), 0.1) == 100.0


def test_format_state_summary_table_fips_identity():
    """Verify FIPS code is the primary key and state_name is preserved as display."""
    panel = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "48",
                "state_name": "Texas",
                "is_operational": True,
                "total_students": 500.0,
                "teacher_fte": 25.0,
                "resource_pressure_priority": 1,
            }
        ]
    )
    res = format_state_summary_table(panel, school_year="2022-23")
    assert res.iloc[0]["state_fips"] == "48"
    assert res.iloc[0]["state_name"] == "Texas"


def test_format_backtest_comparison_table(synthetic_backtest_df):
    comp_df = format_backtest_comparison_table(synthetic_backtest_df)
    assert "model_display" in comp_df.columns
    assert "Naive Persistence (y_t)" in comp_df["model_display"].values


def test_format_projection_scenario_table(synthetic_projections_df):
    proj_fmt = format_projection_scenario_table(synthetic_projections_df, top_n=1)
    assert len(proj_fmt) == 1
    assert proj_fmt.iloc[0]["state_name"] == "California"


# -----------------------------------------------------------------------------
# Chart Generator Tests
# -----------------------------------------------------------------------------
def test_plot_longitudinal_trends(synthetic_panel_df, tmp_path):
    out_file = tmp_path / "test_trends.png"
    fig = plot_longitudinal_trends(synthetic_panel_df, output_path=out_file)
    assert fig is not None
    assert out_file.exists()
    assert out_file.stat().st_size > 0
    save_figure(fig, out_file)


def test_plot_ratio_distribution(synthetic_panel_df, tmp_path):
    out_file = tmp_path / "test_box.png"
    fig = plot_ratio_distribution(synthetic_panel_df, school_year="2022-23", output_path=out_file)
    assert fig is not None
    assert out_file.exists()
    save_figure(fig, out_file)


def test_plot_resource_pressure_tiers(synthetic_panel_df, tmp_path):
    out_file = tmp_path / "test_tiers.png"
    fig = plot_resource_pressure_tiers(
        synthetic_panel_df, school_year="2022-23", output_path=out_file
    )
    assert fig is not None
    assert out_file.exists()
    save_figure(fig, out_file)


def test_plot_backtest_model_comparison(synthetic_backtest_df, tmp_path):
    out_file = tmp_path / "test_bt.png"
    fig = plot_backtest_model_comparison(synthetic_backtest_df, output_path=out_file)
    assert fig is not None
    assert out_file.exists()
    save_figure(fig, out_file)


def test_plot_projection_scenarios(synthetic_projections_df, tmp_path):
    out_file = tmp_path / "test_proj.png"
    fig = plot_projection_scenarios(synthetic_projections_df, top_n=2, output_path=out_file)
    assert fig is not None
    assert out_file.exists()
    save_figure(fig, out_file)


# -----------------------------------------------------------------------------
# Deliverables Generation Tests
# -----------------------------------------------------------------------------
def test_generate_all_deliverables(
    synthetic_panel_df, synthetic_projections_df, synthetic_backtest_df, tmp_path
):
    state_df = format_state_summary_table(synthetic_panel_df, school_year="2022-23")
    written = generate_all_deliverables(
        panel_df=synthetic_panel_df,
        state_summary_df=state_df,
        backtest_df=synthetic_backtest_df,
        projections_df=synthetic_projections_df,
        output_dir=tmp_path,
    )

    assert "executive_summary" in written
    assert "technical_report" in written
    assert "recommendations" in written
    assert "presentation_outline" in written

    for p in written.values():
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert len(content) > 100
        assert "# " in content
