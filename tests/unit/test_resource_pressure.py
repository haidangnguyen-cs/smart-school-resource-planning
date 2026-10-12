"""Unit and regression tests for resource pressure classification and triage.

Adheres to config/kpi_definitions.yaml, docs/PROJECT_PLAN.md (Section 3.5),
and docs/stakeholder_workflows.md:
- Priority ordering: P1 > P2 > P3 > P4 > P5 > P6
- Priority 1: Incomplete data, 0.0 FTE / zero anomaly, non-operational, transition statuses
- Priority 2: High current ratio (inclusive ratio >= P90) strictly for regular elementary/middle/high
- Unbenchmarked bypass: specialized types and non-standard levels bypass Priority 2
- Priority 3: Rapidly rising ratio (ratio_growth >= tau_ratio_rise)
- Priority 4: Staffing growth deficit (growth_gap >= tau_growth_gap)
- Priority 5: Growth unassessed / incomplete growth data (prevents defaulting to Stable)
- Priority 6: Stable / balanced (with orthogonal peer_group_status tracking)
- Summary tables and triage queue generation
"""

import numpy as np
import pandas as pd
import pytest

from school_planning.analytics.resource_pressure import (
    DEFAULT_TAU_GROWTH_GAP,
    DEFAULT_TAU_RATIO_RISE,
    PRIORITY_1_LABEL,
    PRIORITY_2_LABEL,
    PRIORITY_3_LABEL,
    PRIORITY_4_LABEL,
    PRIORITY_5_LABEL,
    PRIORITY_6_LABEL,
    PRIORITY_TIER_ORDER,
    classify_resource_pressure,
    extract_triage_queue,
    summarize_resource_pressure_by_level,
    summarize_resource_pressure_by_state,
    summarize_resource_pressure_tiers,
)
from school_planning.analytics.segmentation import (
    BENCHMARKED_STATUS_LABEL,
    NON_OPERATIONAL_STATUS_LABEL,
    UNBENCHMARKED_STATUS_LABEL,
)


class TestResourcePressureConstants:
    """Validate canonical tier constants and provisional parameter defaults."""

    def test_constants_contract(self):
        assert DEFAULT_TAU_RATIO_RISE == 15.0
        assert DEFAULT_TAU_GROWTH_GAP == 5.0
        assert len(PRIORITY_TIER_ORDER) == 6
        assert PRIORITY_TIER_ORDER[0] == PRIORITY_1_LABEL
        assert PRIORITY_TIER_ORDER[1] == PRIORITY_2_LABEL
        assert PRIORITY_TIER_ORDER[2] == PRIORITY_3_LABEL
        assert PRIORITY_TIER_ORDER[3] == PRIORITY_4_LABEL
        assert PRIORITY_TIER_ORDER[4] == PRIORITY_5_LABEL
        assert PRIORITY_TIER_ORDER[5] == PRIORITY_6_LABEL


class TestPriorityOrderingAndHierarchy:
    """Validate strict evaluation order of resource pressure tiers."""

    def test_p1_takes_precedence_over_p2_for_high_ratio_anomalies(self):
        """A school with ratio >= P90 but zero-teacher anomaly or non-operational status must be P1."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_01",
                    "school_year": "2018-19",
                    "school_name": "Anomaly School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 500.0,
                    "teacher_fte": 0.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": True,
                    "student_teacher_ratio": np.nan,
                    "peer_group_p90_ratio": 20.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_1_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 1

    def test_p2_takes_precedence_over_p3_and_p4(self):
        """A regular school with ratio >= P90 is P2 even if it also has rapid ratio growth or growth deficit."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_02",
                    "school_year": "2019-20",
                    "school_name": "High Ratio Escalating",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 600.0,
                    "teacher_fte": 20.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 30.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": True,
                    "ratio_growth_yoy_pct": 25.0,  # >= 15.0%
                    "growth_gap_pct_points": 12.0,  # >= 5.0 pp
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_2_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 2

    def test_p3_takes_precedence_over_p4(self):
        """When ratio < P90, a school meeting both P3 (ratio rise) and P4 (growth gap) is classified as P3."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_03",
                    "school_year": "2019-20",
                    "school_name": "Rising and Deficit School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 16.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 18.0,  # >= 15.0% (P3)
                    "growth_gap_pct_points": 8.0,  # >= 5.0 pp (P4)
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_3_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 3

    def test_p4_evaluated_when_ratio_growth_below_threshold(self):
        """When ratio < P90 and ratio growth < tau_ratio_rise, growth gap >= tau_growth_gap triggers P4."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_04",
                    "school_year": "2019-20",
                    "school_name": "Staffing Deficit School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 450.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 18.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 5.0,  # < 15.0% (Not P3)
                    "growth_gap_pct_points": 7.5,  # >= 5.0 pp (P4)
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_4_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 4

    def test_p5_unassessed_growth_prevents_defaulting_to_stable(self):
        """A school with complete current data and ratio < P90 but missing growth metrics is P5, never Stable."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_05",
                    "school_year": "2018-19",  # Base year
                    "school_name": "Base Year School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 16.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": np.nan,  # Missing growth
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_5_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 5
        assert (
            res["has_valid_growth_metrics"].iloc[0] is False
            or res["has_valid_growth_metrics"].iloc[0] == 0
        )

    def test_p6_stable_balanced_for_assessed_normal_variation(self):
        """A school with assessed growth where all metrics are within normal bounds is P6."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_06",
                    "school_year": "2019-20",
                    "school_name": "Stable School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 16.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 2.0,  # < 15.0%
                    "growth_gap_pct_points": 1.5,  # < 5.0 pp
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res["resource_pressure_priority"].iloc[0] == 6


class TestPriority1AdministrativeReviewConditions:
    """Validate all conditions routing records to Priority 1."""

    @pytest.mark.parametrize(
        "status",
        ["Added", "Changed Boundary/Agency", "Reopened"],
    )
    def test_transition_statuses_routed_to_p1(self, status: str):
        """Transition-review statuses must be routed to Priority 1 regardless of reported ratios."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_TRANS",
                    "school_year": "2018-19",
                    "school_name": f"School {status}",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": status,
                    "is_operational": False,  # transition statuses are not operational per config
                    "total_students": 400.0,
                    "teacher_fte": 20.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 20.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_1_LABEL

    @pytest.mark.parametrize(
        "flag",
        ["Missing", "Not reported", "Suppressed"],
    )
    def test_non_reported_teacher_flag_routed_to_p1(self, flag: str):
        """Non-reported teacher FTE flags must be routed to Priority 1."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_FLAG",
                    "school_year": "2018-19",
                    "school_name": "Non-reported Flag School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": np.nan,
                    "teacher_data_flag": flag,
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": np.nan,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_1_LABEL

    def test_non_operational_statuses_routed_to_p1(self):
        """Closed, Inactive, and Future records are routed to Priority 1."""
        for st in ["Closed", "Inactive", "Future"]:
            df = pd.DataFrame(
                [
                    {
                        "school_id": f"SCH_{st}",
                        "school_year": "2018-19",
                        "school_name": f"School {st}",
                        "school_type": "Regular School",
                        "school_level": "Elementary",
                        "school_status": st,
                        "is_operational": False,
                        "total_students": 0.0,
                        "teacher_fte": 0.0,
                        "teacher_data_flag": "Reported",
                        "zero_teacher_anomaly": False,
                        "student_teacher_ratio": np.nan,
                        "peer_group_p90_ratio": 22.0,
                        "is_above_p90_ratio": False,
                        "ratio_growth_yoy_pct": np.nan,
                        "growth_gap_pct_points": np.nan,
                    }
                ]
            )
            res = classify_resource_pressure(df)
            assert res["resource_pressure_tier"].iloc[0] == PRIORITY_1_LABEL

    def test_operational_zero_ratio_school_not_classified_as_p1(self):
        """An operational Open school with 0 enrollment, positive FTE, and ratio 0.0 is NOT Priority 1.

        Per config/kpi_definitions.yaml, total_students >= 0 and teacher_fte > 0 yields a valid
        student_teacher_ratio == 0.0. Zero ratio alone must not cause Priority 1; its resulting tier
        follows available growth metrics and other rules.
        """
        # Case A: unassessed growth metrics -> Priority 5 (Growth Unassessed), not Priority 1
        df_unassessed = pd.DataFrame(
            [
                {
                    "school_id": "SCH_ZERO_RATIO_UNASSESSED",
                    "school_year": "2018-19",
                    "school_name": "Zero Enrollment School Unassessed",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 0.0,
                    "teacher_fte": 10.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 0.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res_a = classify_resource_pressure(df_unassessed)
        assert res_a["resource_pressure_tier"].iloc[0] != PRIORITY_1_LABEL
        assert res_a["resource_pressure_tier"].iloc[0] == PRIORITY_5_LABEL
        assert res_a["resource_pressure_priority"].iloc[0] == 5

        # Case B: assessed stable growth metrics -> Priority 6 (Stable / Balanced), not Priority 1
        df_stable = pd.DataFrame(
            [
                {
                    "school_id": "SCH_ZERO_RATIO_STABLE",
                    "school_year": "2019-20",
                    "school_name": "Zero Enrollment School Stable",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 0.0,
                    "teacher_fte": 10.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 0.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 0.0,  # < tau_ratio_rise (15.0%)
                    "growth_gap_pct_points": 0.0,  # < tau_growth_gap (5.0 pp)
                }
            ]
        )
        res_b = classify_resource_pressure(df_stable)
        assert res_b["resource_pressure_tier"].iloc[0] != PRIORITY_1_LABEL
        assert res_b["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res_b["resource_pressure_priority"].iloc[0] == 6


class TestPriority2PeerGroupBypassAndTieHandling:
    """Validate Priority 2 regular peer-group scope, tie handling, and unbenchmarked bypass."""

    def test_inclusive_p90_tie_is_priority_2(self):
        """Ratio exactly equal to P90 threshold must be classified as Priority 2."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_TIE",
                    "school_year": "2018-19",
                    "school_name": "Tie School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 500.0,
                    "teacher_fte": 20.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 25.0,
                    "peer_group_p90_ratio": 25.0,  # Exact tie
                    "is_above_p90_ratio": True,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_2_LABEL

    @pytest.mark.parametrize(
        "school_type",
        ["Special Education School", "Alternative School", "Career and Technical School"],
    )
    def test_specialized_school_types_bypass_p2(self, school_type: str):
        """Specialized schools with ratio > P90 bypass Priority 2."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_SPEC",
                    "school_year": "2019-20",
                    "school_name": "Specialized School",
                    "school_type": school_type,
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 100.0,
                    "teacher_fte": 2.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 50.0,  # Very high ratio
                    "peer_group_p90_ratio": np.nan,  # Unbenchmarked
                    "is_above_p90_ratio": False,  # Bypasses P90
                    "ratio_growth_yoy_pct": 2.0,
                    "growth_gap_pct_points": 1.0,
                }
            ]
        )
        res = classify_resource_pressure(df)
        # Bypasses Priority 2; since growth is assessed and < thresholds, lands in Stable / Balanced
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res["peer_group_status"].iloc[0] == UNBENCHMARKED_STATUS_LABEL

    @pytest.mark.parametrize(
        "level",
        ["Secondary", "Other", "Adult Education", "Not applicable", "Not reported", "Ungraded"],
    )
    def test_non_standard_levels_bypass_p2(self, level: str):
        """Schools with non-standard grade levels bypass Priority 2."""
        df = pd.DataFrame(
            [
                {
                    "school_id": f"SCH_{level}",
                    "school_year": "2019-20",
                    "school_name": f"School {level}",
                    "school_type": "Regular School",
                    "school_level": level,
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 500.0,
                    "teacher_fte": 10.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 50.0,
                    "peer_group_p90_ratio": np.nan,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 2.0,
                    "growth_gap_pct_points": 1.0,
                }
            ]
        )
        res = classify_resource_pressure(df)
        assert res["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res["peer_group_status"].iloc[0] == UNBENCHMARKED_STATUS_LABEL


class TestProvisionalThresholdCustomization:
    """Validate that provisional candidate parameters can be customized for stakeholder sensitivity testing."""

    def test_custom_tau_ratio_rise_changes_classification(self):
        """A school with ratio growth 18.0% is P3 at default 15%, but P6 if threshold is raised to 20%."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_THRESH",
                    "school_year": "2019-20",
                    "school_name": "Threshold School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 16.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 18.0,
                    "growth_gap_pct_points": 2.0,
                }
            ]
        )

        # Default tau_ratio_rise = 15.0 -> Priority 3
        res_default = classify_resource_pressure(df, tau_ratio_rise=15.0)
        assert res_default["resource_pressure_tier"].iloc[0] == PRIORITY_3_LABEL

        # Raised tau_ratio_rise = 20.0 -> Priority 6
        res_custom = classify_resource_pressure(df, tau_ratio_rise=20.0)
        assert res_custom["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res_custom["tau_ratio_rise"].iloc[0] == 20.0

    def test_custom_tau_growth_gap_changes_classification(self):
        """A school with growth gap 7.0 pp is P4 at default 5.0 pp, but P6 if threshold is raised to 10.0 pp."""
        df = pd.DataFrame(
            [
                {
                    "school_id": "SCH_GAP",
                    "school_year": "2019-20",
                    "school_name": "Gap School",
                    "school_type": "Regular School",
                    "school_level": "Elementary",
                    "school_status": "Open",
                    "is_operational": True,
                    "total_students": 400.0,
                    "teacher_fte": 25.0,
                    "teacher_data_flag": "Reported",
                    "zero_teacher_anomaly": False,
                    "student_teacher_ratio": 16.0,
                    "peer_group_p90_ratio": 22.0,
                    "is_above_p90_ratio": False,
                    "ratio_growth_yoy_pct": 2.0,
                    "growth_gap_pct_points": 7.0,
                }
            ]
        )

        # Default tau_growth_gap = 5.0 -> Priority 4
        res_default = classify_resource_pressure(df, tau_growth_gap=5.0)
        assert res_default["resource_pressure_tier"].iloc[0] == PRIORITY_4_LABEL

        # Raised tau_growth_gap = 10.0 -> Priority 6
        res_custom = classify_resource_pressure(df, tau_growth_gap=10.0)
        assert res_custom["resource_pressure_tier"].iloc[0] == PRIORITY_6_LABEL
        assert res_custom["tau_growth_gap"].iloc[0] == 10.0


class TestSummaryTablesAndTriageQueues:
    """Validate summary aggregation functions and triage queue generation."""

    @pytest.fixture
    def multi_tier_classified_df(self) -> pd.DataFrame:
        """Create a synthetic panel containing both non-operational and operational P1 records plus P2-P6."""
        return pd.DataFrame(
            [
                # S1_non_op: P1 (non-operational)
                {
                    "school_id": "S1_NON_OP",
                    "school_year": "2019-20",
                    "school_name": "Closed A",
                    "state_fips": "01",
                    "school_level": "Elementary",
                    "is_operational": False,
                    "student_teacher_ratio": np.nan,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                    "resource_pressure_tier": PRIORITY_1_LABEL,
                    "resource_pressure_priority": 1,
                    "peer_group_status": NON_OPERATIONAL_STATUS_LABEL,
                },
                # S1_op: P1 (operational but incomplete teacher data)
                {
                    "school_id": "S1_OP",
                    "school_year": "2019-20",
                    "school_name": "Incomplete B",
                    "state_fips": "01",
                    "school_level": "Elementary",
                    "is_operational": True,
                    "student_teacher_ratio": np.nan,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                    "resource_pressure_tier": PRIORITY_1_LABEL,
                    "resource_pressure_priority": 1,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
                # S2: P2 (high ratio >= P90)
                {
                    "school_id": "S2",
                    "school_year": "2019-20",
                    "school_name": "High Ratio C",
                    "state_fips": "01",
                    "school_level": "Elementary",
                    "is_operational": True,
                    "student_teacher_ratio": 28.0,
                    "ratio_growth_yoy_pct": 5.0,
                    "growth_gap_pct_points": 2.0,
                    "resource_pressure_tier": PRIORITY_2_LABEL,
                    "resource_pressure_priority": 2,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
                # S3: P3 (rising ratio)
                {
                    "school_id": "S3",
                    "school_year": "2019-20",
                    "school_name": "Rising D",
                    "state_fips": "02",
                    "school_level": "High",
                    "is_operational": True,
                    "student_teacher_ratio": 18.0,
                    "ratio_growth_yoy_pct": 20.0,
                    "growth_gap_pct_points": 2.0,
                    "resource_pressure_tier": PRIORITY_3_LABEL,
                    "resource_pressure_priority": 3,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
                # S4: P4 (growth deficit)
                {
                    "school_id": "S4",
                    "school_year": "2019-20",
                    "school_name": "Deficit E",
                    "state_fips": "02",
                    "school_level": "High",
                    "is_operational": True,
                    "student_teacher_ratio": 17.0,
                    "ratio_growth_yoy_pct": 3.0,
                    "growth_gap_pct_points": 8.0,
                    "resource_pressure_tier": PRIORITY_4_LABEL,
                    "resource_pressure_priority": 4,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
                # S5: P5 (unassessed growth)
                {
                    "school_id": "S5",
                    "school_year": "2019-20",
                    "school_name": "New School F",
                    "state_fips": "01",
                    "school_level": "Middle",
                    "is_operational": True,
                    "student_teacher_ratio": 15.0,
                    "ratio_growth_yoy_pct": np.nan,
                    "growth_gap_pct_points": np.nan,
                    "resource_pressure_tier": PRIORITY_5_LABEL,
                    "resource_pressure_priority": 5,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
                # S6: P6 (stable)
                {
                    "school_id": "S6",
                    "school_year": "2019-20",
                    "school_name": "Stable G",
                    "state_fips": "01",
                    "school_level": "Middle",
                    "is_operational": True,
                    "student_teacher_ratio": 15.0,
                    "ratio_growth_yoy_pct": 1.0,
                    "growth_gap_pct_points": 1.0,
                    "resource_pressure_tier": PRIORITY_6_LABEL,
                    "resource_pressure_priority": 6,
                    "peer_group_status": BENCHMARKED_STATUS_LABEL,
                },
            ]
        )

    def test_summarize_resource_pressure_tiers(self, multi_tier_classified_df):
        """Verify tier summary computes counts, operational counts, percentages, and metrics."""
        summary = summarize_resource_pressure_tiers(multi_tier_classified_df)
        assert len(summary) == 6
        assert "resource_pressure_priority" in summary.columns
        assert "observation_count" in summary.columns
        assert "operational_observation_count" in summary.columns
        assert "pct_of_panel" in summary.columns
        assert "pct_of_operational" in summary.columns

        # Sum of observation counts must equal total panel records (7)
        assert summary["observation_count"].sum() == 7
        # Sum of operational counts must equal total operational records (6)
        assert summary["operational_observation_count"].sum() == 6

        # Check P1: 2 observations total (1 non-op, 1 op)
        p1_row = summary[summary["resource_pressure_priority"] == 1].iloc[0]
        assert p1_row["observation_count"] == 2
        assert p1_row["operational_observation_count"] == 1
        assert p1_row["pct_of_panel"] == 28.57
        assert p1_row["pct_of_operational"] == 16.67  # 1 operational out of 6 operational

        # Check P2: 1 observation, operational count is 1, median ratio is 28.0
        p2_row = summary[summary["resource_pressure_priority"] == 2].iloc[0]
        assert p2_row["observation_count"] == 1
        assert p2_row["operational_observation_count"] == 1
        assert p2_row["pct_of_operational"] == 16.67
        assert p2_row["median_student_teacher_ratio"] == 28.0

        # Operational percentages must sum to ~100% across all 6 tiers
        total_pct_op = summary["pct_of_operational"].sum()
        assert pytest.approx(total_pct_op, abs=0.5) == 100.0

    def test_operational_percentage_excludes_non_operational_records(
        self, multi_tier_classified_df
    ):
        """Regression test: non-operational records contribute to panel count but NOT operational percentage."""
        summary = summarize_resource_pressure_tiers(multi_tier_classified_df)
        p1_row = summary[summary["resource_pressure_priority"] == 1].iloc[0]

        # Non-operational record is in observation_count
        assert p1_row["observation_count"] == 2
        # But excluded from operational_observation_count and pct_of_operational numerator
        assert p1_row["operational_observation_count"] == 1
        # If non-operational had been included in the numerator, pct_of_operational would be 2/6 = 33.33%
        assert p1_row["pct_of_operational"] == 16.67
        assert p1_row["pct_of_operational"] < 33.0

    def test_summarize_resource_pressure_by_state(self, multi_tier_classified_df):
        """Verify state aggregation groups by state and computes per-tier counts."""
        state_sum = summarize_resource_pressure_by_state(multi_tier_classified_df)
        assert len(state_sum) == 2  # State 01 and State 02
        assert "state_fips" in state_sum.columns
        assert "p1_count" in state_sum.columns
        assert "p2_count" in state_sum.columns

        st01 = state_sum[state_sum["state_fips"] == "01"].iloc[0]
        assert st01["total_records"] == 5
        assert st01["operational_records"] == 4
        assert st01["p1_count"] == 2
        assert st01["p2_count"] == 1

    def test_summarize_resource_pressure_by_level(self, multi_tier_classified_df):
        """Verify level aggregation groups by instructional level."""
        level_sum = summarize_resource_pressure_by_level(multi_tier_classified_df)
        assert len(level_sum) == 3  # Elementary, High, Middle
        assert "school_level" in level_sum.columns

    def test_extract_triage_queue_filtering_and_sorting(self, multi_tier_classified_df):
        """Verify triage queue extraction supports priority filtering and deterministic sorting."""
        p2_queue = extract_triage_queue(multi_tier_classified_df, priority=2)
        assert len(p2_queue) == 1
        assert p2_queue["school_id"].iloc[0] == "S2"
        assert p2_queue["resource_pressure_priority"].iloc[0] == 2

        all_queue = extract_triage_queue(multi_tier_classified_df)
        assert len(all_queue) == 7
        # Must be sorted by priority ascending (1 to 6)
        priorities = all_queue["resource_pressure_priority"].tolist()
        assert priorities == sorted(priorities)
