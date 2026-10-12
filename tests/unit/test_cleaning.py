"""Unit tests for cleaning, identifier normalization, missing values, duplicates, and pipeline."""

import numpy as np
import pandas as pd
import pytest

from school_planning.cleaning.cleaning_pipeline import (
    clean_component,
    clean_directory_dataframe,
    clean_membership_dataframe,
    clean_staff_dataframe,
)
from school_planning.cleaning.duplicates import detect_duplicates, resolve_duplicates
from school_planning.cleaning.identifiers import (
    normalize_fipst,
    normalize_identifiers_dataframe,
    normalize_leaid,
    normalize_ncessch,
    normalize_schid,
    standardize_school_year,
)
from school_planning.cleaning.missing_values import (
    clean_student_count,
    clean_teacher_fte,
    coerce_sentinel_values,
)
from school_planning.cleaning.normalization import (
    classify_operational_status,
    normalize_charter_status,
    strip_whitespace,
)


class TestIdentifierNormalization:
    """Tests for individual identifier normalization functions."""

    def test_normalize_ncessch_padding(self):
        # 11 digits with leading zero dropped
        assert normalize_ncessch("10000500871") == "010000500871"
        # Already 12 digits
        assert normalize_ncessch("010000500871") == "010000500871"
        # Numeric input
        assert normalize_ncessch(10000500871) == "010000500871"
        # Whitespace handling
        assert normalize_ncessch(" 010000500871 ") == "010000500871"

    def test_normalize_ncessch_null_and_empty(self):
        assert normalize_ncessch(None) is None
        assert normalize_ncessch("") is None
        assert normalize_ncessch(float("nan")) is None

    def test_normalize_leaid_padding(self):
        assert normalize_leaid("100005") == "0100005"
        assert normalize_leaid("0100005") == "0100005"
        assert normalize_leaid(100005) == "0100005"
        assert normalize_leaid(None) is None

    def test_normalize_fipst_padding(self):
        assert normalize_fipst("1") == "01"
        assert normalize_fipst("01") == "01"
        assert normalize_fipst(1) == "01"
        assert normalize_fipst(None) is None

    def test_normalize_schid(self):
        assert normalize_schid("0100871") == "0100871"
        assert normalize_schid("100871") == "0100871"
        assert normalize_schid(None) is None

    def test_standardize_school_year(self):
        # 9-character raw format
        assert standardize_school_year("2018-2019") == "2018-19"
        assert standardize_school_year("2022-2023") == "2022-23"
        # Already canonical format
        assert standardize_school_year("2018-19") == "2018-19"
        # Null and empty
        assert standardize_school_year(None) is None
        assert standardize_school_year("") is None

    def test_standardize_school_year_invalid(self):
        with pytest.raises(ValueError, match="Unrecognized school year format"):
            standardize_school_year("2018")


class TestDataFrameIdentifierNormalization:
    """Tests for DataFrame-level identifier normalization."""

    def test_normalize_identifiers_dataframe(self):
        df = pd.DataFrame(
            {
                "school_id": ["10000500871", "010000500879"],
                "district_id": ["100005", "0100005"],
                "state_fips": ["1", "01"],
                "school_year": ["2018-2019", "2019-2020"],
            }
        )
        normalized = normalize_identifiers_dataframe(df)

        assert normalized["school_id"].tolist() == ["010000500871", "010000500879"]
        assert normalized["district_id"].tolist() == ["0100005", "0100005"]
        assert normalized["state_fips"].tolist() == ["01", "01"]
        assert normalized["school_year"].tolist() == ["2018-19", "2019-20"]


class TestMissingValuesAndSentinels:
    """Tests for missing-value rules and sentinel coercion."""

    def test_coerce_sentinel_values(self):
        s = pd.Series([10.0, -1.0, -2.0, 0.0, -99.0, np.nan])
        cleaned = coerce_sentinel_values(s)
        assert cleaned.iloc[0] == 10.0
        assert np.isnan(cleaned.iloc[1])
        assert np.isnan(cleaned.iloc[2])
        assert cleaned.iloc[3] == 0.0
        assert np.isnan(cleaned.iloc[4])
        assert np.isnan(cleaned.iloc[5])

    def test_clean_teacher_fte(self):
        df = pd.DataFrame(
            {
                "school_id": ["01001", "01002", "01003", "01004", "01005"],
                "teacher_fte": [25.5, 0.0, 0.0, -1.0, 15.0],
                "teacher_data_flag": [
                    "Reported",
                    "Reported",
                    "Missing",
                    "Reported",
                    "Not reported",
                ],
            }
        )
        cleaned = clean_teacher_fte(df)

        # 01001: positive reported
        assert cleaned.loc[0, "teacher_fte"] == 25.5
        assert (
            cleaned.loc[0, "zero_teacher_anomaly"] is False
            or cleaned.loc[0, "zero_teacher_anomaly"] == 0
        )

        # 01002: valid reported zero -> preserved and flagged
        assert cleaned.loc[1, "teacher_fte"] == 0.0
        assert bool(cleaned.loc[1, "zero_teacher_anomaly"]) is True

        # 01003: zero but flag == 'Missing' -> must be NaN, NEVER 0.0
        assert np.isnan(cleaned.loc[2, "teacher_fte"])
        assert bool(cleaned.loc[2, "zero_teacher_anomaly"]) is False

        # 01004: negative sentinel (-1.0) -> NaN
        assert np.isnan(cleaned.loc[3, "teacher_fte"])

        # 01005: non-reported flag -> NaN
        assert np.isnan(cleaned.loc[4, "teacher_fte"])

    def test_clean_student_count(self):
        df = pd.DataFrame(
            {
                "school_id": ["01001", "01002", "01003", "01004"],
                "total_students": ["500", "0", "-1", "N/A"],
                "enrollment_data_flag": ["Reported", "Reported", "Reported", "Missing"],
            }
        )
        cleaned = clean_student_count(df)

        assert cleaned.loc[0, "total_students"] == 500
        assert cleaned.loc[1, "total_students"] == 0
        assert np.isnan(cleaned.loc[2, "total_students"])
        assert np.isnan(cleaned.loc[3, "total_students"])


class TestDuplicatesHandling:
    """Tests for duplicate detection and policy resolution."""

    def test_detect_duplicates(self):
        df = pd.DataFrame(
            {
                "school_id": ["01001", "01001", "01002"],
                "school_year": ["2018-19", "2018-19", "2018-19"],
                "val": [1, 2, 3],
            }
        )
        dups = detect_duplicates(df, subset=("school_id", "school_year"))
        assert len(dups) == 2
        assert dups["school_id"].tolist() == ["01001", "01001"]

    def test_resolve_duplicates_fail_policy(self):
        df = pd.DataFrame(
            {
                "school_id": ["01001", "01001", "01002"],
                "school_year": ["2018-19", "2018-19", "2018-19"],
            }
        )
        with pytest.raises(ValueError, match="Detected 2 duplicate rows"):
            resolve_duplicates(df, subset=("school_id", "school_year"), policy="fail")

    def test_resolve_duplicates_drop_policy(self):
        df = pd.DataFrame(
            {
                "school_id": ["01001", "01001", "01002"],
                "school_year": ["2018-19", "2018-19", "2018-19"],
                "val": [10, 20, 30],
            }
        )
        deduped = resolve_duplicates(df, subset=("school_id", "school_year"), policy="keep_first")
        assert len(deduped) == 2
        assert deduped.loc[deduped["school_id"] == "01001", "val"].iloc[0] == 10


class TestNormalizationAndScoping:
    """Tests for status classification, whitespace stripping, and charter normalization."""

    def test_classify_operational_status(self):
        df = pd.DataFrame(
            {
                "school_status": [
                    "Open",
                    "New",
                    "Closed",
                    "Inactive",
                    "Future",
                    "Added",
                    "Changed Boundary/Agency",
                    "Reopened",
                    "Unknown Status",
                ]
            }
        )
        result = classify_operational_status(df)

        assert result["is_operational"].tolist() == [
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        ]

        expected_buckets = [
            "active",
            "active",
            "inactive",
            "inactive",
            "inactive",
            "transition_review",
            "transition_review",
            "transition_review",
            "other",
        ]
        assert result["status_bucket"].tolist() == expected_buckets

    def test_normalize_charter_status(self):
        df = pd.DataFrame({"is_charter": ["Yes", "No", "1", "0", "UNKNOWN"]})
        result = normalize_charter_status(df)
        assert result["is_charter"].iloc[0] is True
        assert result["is_charter"].iloc[1] is False
        assert result["is_charter"].iloc[2] is True
        assert result["is_charter"].iloc[3] is False
        assert np.isnan(result["is_charter"].iloc[4])

    def test_strip_whitespace(self):
        df = pd.DataFrame(
            {
                "text": ["  hello ", "world  ", ""],
                "num": [1, 2, 3],
            }
        )
        result = strip_whitespace(df)
        assert result["text"].iloc[0] == "hello"
        assert result["text"].iloc[1] == "world"
        assert np.isnan(result["text"].iloc[2])


class TestCleaningPipelineOrchestration:
    """Tests for component-level cleaning pipeline orchestrators."""

    def test_clean_directory_dataframe(self):
        df = pd.DataFrame(
            {
                "school_id": [" 10000500871 "],
                "district_id": ["100005"],
                "state_fips": ["1"],
                "school_year": ["2018-2019"],
                "school_status": [" Open "],
                "is_charter": [" Yes "],
            }
        )
        cleaned = clean_directory_dataframe(df)
        assert cleaned["school_id"].iloc[0] == "010000500871"
        assert cleaned["district_id"].iloc[0] == "0100005"
        assert cleaned["state_fips"].iloc[0] == "01"
        assert cleaned["school_year"].iloc[0] == "2018-19"
        assert bool(cleaned["is_operational"].iloc[0]) is True
        assert cleaned["status_bucket"].iloc[0] == "active"
        assert bool(cleaned["is_charter"].iloc[0]) is True

    def test_clean_membership_dataframe(self):
        df = pd.DataFrame(
            {
                "school_id": ["10000500871"],
                "school_year": ["2018-2019"],
                "total_students": [" 450 "],
                "enrollment_data_flag": ["Reported"],
            }
        )
        cleaned = clean_membership_dataframe(df)
        assert cleaned["school_id"].iloc[0] == "010000500871"
        assert cleaned["school_year"].iloc[0] == "2018-19"
        assert cleaned["total_students"].iloc[0] == 450.0

    def test_clean_staff_dataframe(self):
        df = pd.DataFrame(
            {
                "school_id": ["10000500871"],
                "school_year": ["2018-2019"],
                "teacher_fte": ["0.0"],
                "teacher_data_flag": ["Reported"],
            }
        )
        cleaned = clean_staff_dataframe(df)
        assert cleaned["school_id"].iloc[0] == "010000500871"
        assert cleaned["school_year"].iloc[0] == "2018-19"
        assert cleaned["teacher_fte"].iloc[0] == 0.0
        assert bool(cleaned["zero_teacher_anomaly"].iloc[0]) is True

    def test_clean_component_routing(self):
        df = pd.DataFrame(
            {
                "school_id": ["010000500871"],
                "school_year": ["2018-19"],
                "school_status": ["Open"],
            }
        )
        res = clean_component(df, "directory")
        assert "is_operational" in res.columns

        with pytest.raises(ValueError, match="Unknown component type"):
            clean_component(df, "invalid_comp")
