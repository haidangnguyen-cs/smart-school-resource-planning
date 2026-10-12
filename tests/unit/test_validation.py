"""Unit tests for schema, key, relationship, and business rule validation."""

import pandas as pd
import pytest

from school_planning.validation.business_rules import validate_business_rules
from school_planning.validation.key_checks import validate_key_uniqueness
from school_planning.validation.relationship_checks import validate_spine_relationships
from school_planning.validation.schema_checks import validate_dataframe_schema


class TestSchemaValidation:
    """Tests for schema checking module."""

    def test_schema_valid(self):
        df = pd.DataFrame(
            {
                "school_id": ["010000500871", "010000500879"],
                "teacher_fte": [25.0, 30.5],
            }
        )
        res = validate_dataframe_schema(
            df,
            required_columns=["school_id", "teacher_fte"],
            expected_types={"school_id": "string", "teacher_fte": "numeric"},
        )
        assert res["valid"] is True
        assert len(res["errors"]) == 0

    def test_schema_missing_columns(self):
        df = pd.DataFrame({"school_id": ["010000500871"]})
        res = validate_dataframe_schema(
            df,
            required_columns=["school_id", "missing_col"],
            raise_on_error=False,
        )
        assert res["valid"] is False
        assert any("Missing mandatory columns" in e for e in res["errors"])

    def test_schema_raise_on_error(self):
        df = pd.DataFrame({"school_id": ["010000500871"]})
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_dataframe_schema(
                df,
                required_columns=["school_id", "missing_col"],
                raise_on_error=True,
            )


class TestKeyValidation:
    """Tests for composite primary key uniqueness and null-key checks."""

    def test_keys_unique(self):
        df = pd.DataFrame(
            {
                "school_id": ["010000500871", "010000500879"],
                "school_year": ["2018-19", "2018-19"],
            }
        )
        res = validate_key_uniqueness(df, key_cols=["school_id", "school_year"])
        assert res["valid"] is True
        assert res["duplicate_rows_count"] == 0

    def test_keys_duplicates_detected(self):
        df = pd.DataFrame(
            {
                "school_id": ["010000500871", "010000500871"],
                "school_year": ["2018-19", "2018-19"],
            }
        )
        res = validate_key_uniqueness(
            df, key_cols=["school_id", "school_year"], raise_on_error=False
        )
        assert res["valid"] is False
        assert res["duplicate_rows_count"] == 2

    def test_keys_null_detected(self):
        df = pd.DataFrame(
            {
                "school_id": ["010000500871", None],
                "school_year": ["2018-19", "2018-19"],
            }
        )
        res = validate_key_uniqueness(
            df, key_cols=["school_id", "school_year"], raise_on_error=False
        )
        assert res["valid"] is False
        assert res["null_keys_count"] == 1


class TestRelationshipValidation:
    """Tests for Directory spine 1:0..1 relationship validation."""

    def test_spine_relationship_valid_1_to_0_or_1(self):
        spine_df = pd.DataFrame(
            {
                "school_id": ["01", "02", "03"],
                "school_year": ["2018-19", "2018-19", "2018-19"],
            }
        )
        target_df = pd.DataFrame(
            {
                "school_id": ["01", "02"],
                "school_year": ["2018-19", "2018-19"],
                "teacher_fte": [20.0, 30.0],
            }
        )
        res = validate_spine_relationships(
            spine_df, target_df, join_keys=["school_id", "school_year"], target_name="staff"
        )

        assert res["valid"] is True
        assert res["target_key_unique"] is True
        assert (
            res["unmatched_spine_keys_count"] == 1
        )  # 03 is in spine but not in target (1:0..1 allowed)
        assert res["unmatched_target_keys_count"] == 0

    def test_spine_relationship_duplicate_in_target_fails(self):
        spine_df = pd.DataFrame(
            {
                "school_id": ["01"],
                "school_year": ["2018-19"],
            }
        )
        target_df = pd.DataFrame(
            {
                "school_id": ["01", "01"],
                "school_year": ["2018-19", "2018-19"],
                "teacher_fte": [20.0, 25.0],
            }
        )
        res = validate_spine_relationships(
            spine_df,
            target_df,
            join_keys=["school_id", "school_year"],
            target_name="staff",
            raise_on_error=False,
        )
        assert res["valid"] is False
        assert res["target_key_unique"] is False
        assert any("1:0..1" in e for e in res["errors"])


class TestBusinessRulesValidation:
    """Tests for business rules checks."""

    def test_business_rules_detection(self):
        df = pd.DataFrame(
            {
                "school_id": ["01", "02", "03"],
                "school_year": ["2018-19", "2018-19", "2018-19"],
                "total_students": [100, 0, -5],
                "teacher_fte": [10.0, 0.0, None],
                "zero_teacher_anomaly": [False, True, False],
                "school_status": ["Open", "Open", "Closed"],
            }
        )
        res = validate_business_rules(df)

        assert res["teacher_checks"]["zero_teacher_count"] == 1
        assert res["student_checks"]["zero_enrollment_count"] == 1
        assert res["student_checks"]["negative_enrollment_count"] == 1
        assert res["status_checks"]["status_distribution"] == {"Open": 2, "Closed": 1}
