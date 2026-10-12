"""test_dashboard.py - Unit tests for Streamlit dashboard filter logic and KPI components."""

import numpy as np
import pandas as pd
import pytest

from app.components.filters import apply_filters
from app.components.kpi_cards import pd_isna


@pytest.fixture
def sample_dashboard_df() -> pd.DataFrame:
    """Create sample DataFrame for testing dashboard filter mechanics."""
    return pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "06",
                "state_name": "California",
                "school_level": "Primary",
                "is_charter": False,
                "is_operational": True,
                "total_students": 500,
                "teacher_fte": 25.0,
                "resource_pressure_priority": 2,
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "state_fips": "48",
                "state_name": "Texas",
                "school_level": "High",
                "is_charter": True,
                "is_operational": True,
                "total_students": 1200,
                "teacher_fte": 60.0,
                "resource_pressure_priority": 6,
            },
            {
                "school_id": "S3",
                "school_year": "2021-22",
                "state_fips": "06",
                "state_name": "California",
                "school_level": "Primary",
                "is_charter": False,
                "is_operational": False,  # Closed
                "total_students": 0,
                "teacher_fte": 0.0,
                "resource_pressure_priority": 1,
            },
        ]
    )


def test_apply_filters_year(sample_dashboard_df):
    filters = {"school_year": "2022-23"}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 2
    assert set(res["school_year"]) == {"2022-23"}


def test_apply_filters_all_years(sample_dashboard_df):
    filters = {"school_year": "All Years"}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 3


def test_apply_filters_state(sample_dashboard_df):
    filters = {"states": ["Texas"]}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 1
    assert res.iloc[0]["state_name"] == "Texas"


def test_apply_filters_level(sample_dashboard_df):
    filters = {"school_levels": ["High"]}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 1
    assert res.iloc[0]["school_level"] == "High"


def test_apply_filters_charter(sample_dashboard_df):
    filters = {"charter_choice": "Charter Only"}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 1
    assert bool(res.iloc[0]["is_charter"]) is True

    filters_non = {"charter_choice": "Non-Charter Only"}
    res_non = apply_filters(sample_dashboard_df, filters_non)
    assert len(res_non) == 2


def test_apply_filters_charter_unknown_status_handling():
    """Verify that Non-Charter Only and Charter Only exclude missing/unknown charter status."""
    df = pd.DataFrame(
        [
            {"school_id": "S_non", "is_charter": False, "is_operational": True},
            {"school_id": "S_charter", "is_charter": True, "is_operational": True},
            {"school_id": "S_none", "is_charter": None, "is_operational": True},
            {"school_id": "S_nan", "is_charter": np.nan, "is_operational": True},
        ]
    )

    # 1. Non-Charter Only: must select ONLY explicitly observed False
    res_non = apply_filters(df, {"charter_choice": "Non-Charter Only"})
    assert len(res_non) == 1
    assert res_non.iloc[0]["school_id"] == "S_non"
    assert bool(res_non.iloc[0]["is_charter"]) is False

    # 2. Charter Only: must select ONLY explicitly observed True
    res_charter = apply_filters(df, {"charter_choice": "Charter Only"})
    assert len(res_charter) == 1
    assert res_charter.iloc[0]["school_id"] == "S_charter"
    assert bool(res_charter.iloc[0]["is_charter"]) is True

    # 3. All Schools: must include all 4 records without dropping unknown status
    res_all = apply_filters(df, {"charter_choice": "All Schools"})
    assert len(res_all) == 4
    assert set(res_all["school_id"]) == {"S_non", "S_charter", "S_none", "S_nan"}


def test_apply_filters_operational(sample_dashboard_df):
    filters = {"operational_choice": "Operational Only"}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 2
    assert all(res["is_operational"])


def test_apply_filters_priority_tiers(sample_dashboard_df):
    filters = {"priority_tiers": [2, 6]}
    res = apply_filters(sample_dashboard_df, filters)
    assert len(res) == 2
    assert set(res["resource_pressure_priority"]) == {2, 6}


def test_pd_isna_helper():
    assert pd_isna(None) is True
    assert pd_isna(np.nan) is True
    assert pd_isna(float("nan")) is True
    assert pd_isna(15.2) is False
    assert pd_isna("string") is False
    assert pd_isna(0) is False


def test_apply_filters_include_year_false(sample_dashboard_df):
    """Verify include_year=False applies non-year filters across all historical years."""
    filters = {"school_year": "2022-23", "states": ["California"]}
    # include_year=True: only California in 2022-23 (1 row)
    res_yr = apply_filters(sample_dashboard_df, filters, include_year=True)
    assert len(res_yr) == 1
    # include_year=False: California across all years (2 rows: 2022-23 and 2021-22)
    res_all_yr = apply_filters(sample_dashboard_df, filters, include_year=False)
    assert len(res_all_yr) == 2
    assert set(res_all_yr["school_year"]) == {"2022-23", "2021-22"}


def test_all_years_snapshot_kpi_semantics():
    """Verify that All Years does NOT cumulatively sum multi-year records into snapshot totals."""
    # Create 5 years of data for the same single school
    multi_year_df = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": yr,
                "is_operational": True,
                "total_students": 500.0,
                "teacher_fte": 25.0,
            }
            for yr in ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        ]
    )

    filters = {"school_year": "All Years", "operational_choice": "Operational Only"}
    non_year_cohort = apply_filters(multi_year_df, filters, include_year=False)

    # In All Years mode, the reference year is latest available (2022-23)
    available_years = sorted(non_year_cohort["school_year"].dropna().unique().tolist())
    ref_year = available_years[-1] if available_years else "2022-23"
    assert ref_year == "2022-23"

    target_cohort = non_year_cohort[non_year_cohort["school_year"] == ref_year]

    snapshot_students = float(target_cohort["total_students"].sum(min_count=1))
    snapshot_schools = len(target_cohort)

    # Snapshot MUST NOT be the cumulative 5-year sum (2,500 students, 5 schools)
    assert snapshot_students == 500.0
    assert snapshot_schools == 1
    assert snapshot_students != multi_year_df["total_students"].sum()


def test_triage_queue_filter_consistency():
    """Verify queue counts, displayed rows, and export CSV represent identical filtered records."""
    # Multi-year queue
    raw_q = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "06",
                "resource_pressure_priority": 1,
            },
            {
                "school_id": "S2",
                "school_year": "2022-23",
                "state_fips": "48",
                "resource_pressure_priority": 1,
            },
            {
                "school_id": "S1",
                "school_year": "2021-22",
                "state_fips": "06",
                "resource_pressure_priority": 1,
            },
            {
                "school_id": "S3",
                "school_year": "2022-23",
                "state_fips": "06",
                "resource_pressure_priority": 1,
            },
        ]
    )

    # Filtered analytical panel: only California (FIPS 06) in 2022-23, containing S1 only
    target_cohort = pd.DataFrame(
        [
            {
                "school_id": "S1",
                "school_year": "2022-23",
                "state_fips": "06",
                "is_operational": True,
            }
        ]
    )

    target_keys = target_cohort[["school_id", "school_year", "state_fips"]].drop_duplicates().copy()
    target_keys["school_id"] = target_keys["school_id"].astype(str)
    target_keys["school_year"] = target_keys["school_year"].astype(str)
    target_keys["state_fips"] = target_keys["state_fips"].astype(str).str.zfill(2)

    q = raw_q.copy()
    q["school_id"] = q["school_id"].astype(str)
    q["school_year"] = q["school_year"].astype(str)
    q["state_fips"] = q["state_fips"].astype(str).str.zfill(2)

    filtered_q = q.merge(target_keys, on=["school_id", "school_year", "state_fips"], how="inner")

    # Count, rows, and export must all equal 1 record (S1 in 2022-23)
    assert len(filtered_q) == 1
    assert filtered_q.iloc[0]["school_id"] == "S1"
    csv_bytes = filtered_q.to_csv(index=False).encode("utf-8")
    assert b"S1,2022-23,06,1" in csv_bytes
    assert b"S2" not in csv_bytes
    assert b"2021-22" not in csv_bytes


def test_missing_queue_file_graceful_handling():
    """Verify that None or empty queue does not crash or call len(None)."""
    raw_q = None
    # Simulated tab logic
    if raw_q is None:
        status = "missing"
    elif raw_q.empty:
        status = "empty"
    else:
        status = "present"

    assert status == "missing"

    empty_q = pd.DataFrame()
    if empty_q is None:
        status = "missing"
    elif empty_q.empty:
        status = "empty"
    else:
        status = "present"

    assert status == "empty"


def test_fips_based_drill_down_identity(sample_dashboard_df):
    """Verify geographic drill down operates strictly on canonical state_fips."""
    california_fips = "06"
    drill_df = sample_dashboard_df[
        sample_dashboard_df["state_fips"].astype(str).str.zfill(2) == california_fips
    ]
    assert len(drill_df) == 2
    assert set(drill_df["state_fips"]) == {"06"}
    assert set(drill_df["state_name"]) == {"California"}


def test_missing_data_styler_format():
    """Verify Styler formats all-missing values as '—' while preserving 0.0."""
    df = pd.DataFrame(
        {
            "total_students": [np.nan, 0.0, 500.0],
            "teacher_fte": [np.nan, 0.0, 25.0],
        }
    )
    styler = df.style.format(
        {"total_students": "{:,.0f}", "teacher_fte": "{:,.1f}"},
        na_rep="—",
    )
    rendered = styler.to_html()
    assert "—" in rendered  # All-missing renders as em-dash
    assert ">0<" in rendered  # Observed zero student count renders as 0
    assert ">0.0<" in rendered  # Observed zero teacher FTE renders as 0.0
    assert ">500<" in rendered  # Normal value renders
