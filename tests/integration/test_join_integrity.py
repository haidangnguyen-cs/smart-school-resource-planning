"""Integration tests for Directory spine 1:0..1 left joins, key uniqueness, and panel invariants."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from school_planning.transformation.build_panel import (
    build_longitudinal_panel,
    build_single_year_panel,
    save_panel_parquet,
)
from school_planning.transformation.directory import transform_directory
from school_planning.transformation.membership import transform_membership
from school_planning.transformation.staff import transform_staff

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestJoinIntegrityAndInvariants:
    """Integration test suite for 1:0..1 spine joins and panel invariants."""

    def test_single_year_panel_construction_from_fixtures(self):
        dir_path = FIXTURES_DIR / "sample_directory.csv"
        staff_path = FIXTURES_DIR / "sample_staff.csv"
        mem_path = FIXTURES_DIR / "sample_membership.csv"

        d_df = transform_directory(dir_path)
        s_df = transform_staff(staff_path)
        m_df = transform_membership(mem_path)

        panel, metrics = build_single_year_panel(d_df, s_df, m_df)

        # Invariant 1: Exactly zero Cartesian row multiplication
        assert len(panel) == len(d_df)
        assert metrics["panel_rows"] == len(d_df)

        # Invariant 2: Output panel composite primary key uniqueness
        assert not panel.duplicated(subset=["school_id", "school_year"]).any()

        # Invariant 3: Required columns present in consolidated panel
        assert "school_id" in panel.columns
        assert "district_id" in panel.columns
        assert "school_year" in panel.columns
        assert "school_status" in panel.columns
        assert "is_operational" in panel.columns
        assert "status_bucket" in panel.columns
        assert "total_students" in panel.columns
        assert "teacher_fte" in panel.columns
        assert "zero_teacher_anomaly" in panel.columns

        # Invariant 4: Unmatched spine records retain NaN for missing measures
        # If any directory school is not in staff, its teacher_fte must be NaN
        staff_keys = set(s_df["school_id"].unique())
        unmatched_staff_schools = panel[~panel["school_id"].isin(staff_keys)]
        if not unmatched_staff_schools.empty:
            assert unmatched_staff_schools["teacher_fte"].isna().all()

    def test_duplicate_in_target_fails_before_join(self):
        # Create directory spine
        d_df = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "school_status": ["Open", "Open"],
            }
        )
        # Create staff target with duplicate key
        s_df = pd.DataFrame(
            {
                "school_id": ["01001", "01001"],  # Duplicate!
                "school_year": ["2018-19", "2018-19"],
                "teacher_fte": [20.0, 25.0],
                "zero_teacher_anomaly": [False, False],
            }
        )
        m_df = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "total_students": [300.0, 400.0],
            }
        )

        with pytest.raises(ValueError, match="Input staff table has duplicate keys"):
            build_single_year_panel(d_df, s_df, m_df)

    def test_longitudinal_panel_multi_year_assembly(self):
        # Year 1
        d1 = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "school_status": ["Open", "Open"],
            }
        )
        s1 = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "teacher_fte": [20.0, 30.0],
                "zero_teacher_anomaly": [False, False],
            }
        )
        m1 = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "total_students": [300.0, 450.0],
            }
        )

        # Year 2
        d2 = pd.DataFrame(
            {
                "school_id": ["01001", "01002", "01003"],
                "school_year": ["2019-20", "2019-20", "2019-20"],
                "school_status": ["Open", "Open", "New"],
            }
        )
        s2 = pd.DataFrame(
            {
                "school_id": ["01001", "01002", "01003"],
                "school_year": ["2019-20", "2019-20", "2019-20"],
                "teacher_fte": [21.0, 30.0, 15.0],
                "zero_teacher_anomaly": [False, False, False],
            }
        )
        m2 = pd.DataFrame(
            {
                "school_id": ["01001", "01002", "01003"],
                "school_year": ["2019-20", "2019-20", "2019-20"],
                "total_students": [320.0, 450.0, 200.0],
            }
        )

        full_panel, metrics = build_longitudinal_panel(
            yearly_directories=[d1, d2],
            yearly_staff=[s1, s2],
            yearly_memberships=[m1, m2],
        )

        assert len(full_panel) == 5  # 2 rows in year 1 + 3 rows in year 2
        assert metrics["total_records"] == 5
        assert metrics["total_unique_schools"] == 3
        assert metrics["school_years"] == ["2018-19", "2019-20"]
        assert not full_panel.duplicated(subset=["school_id", "school_year"]).any()

    def test_parquet_serialization_and_reloading(self, tmp_path):
        d_df = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "school_status": ["Open", "Open"],
            }
        )
        s_df = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "teacher_fte": [20.0, 30.0],
                "zero_teacher_anomaly": [False, False],
            }
        )
        m_df = pd.DataFrame(
            {
                "school_id": ["01001", "01002"],
                "school_year": ["2018-19", "2018-19"],
                "total_students": [300.0, np.nan],
            }
        )

        panel, _ = build_single_year_panel(d_df, s_df, m_df)
        out_pq = tmp_path / "test_panel.parquet"
        save_panel_parquet(panel, out_pq)

        assert out_pq.exists()
        reloaded = pd.read_parquet(out_pq)
        assert len(reloaded) == 2
        assert list(reloaded.columns) == list(panel.columns)
        assert reloaded["school_id"].tolist() == ["01001", "01002"]

    def test_transform_membership_missing_indicator_raises(self):
        bad_df = pd.DataFrame(
            {
                "school_id": ["01001"],
                "school_year": ["2018-19"],
                "total_students": [300.0],
            }
        )
        with pytest.raises(KeyError, match="missing indicator column"):
            transform_membership(bad_df)
