"""Unit tests for cleaning and identifier normalization."""

import pandas as pd
import pytest

from school_planning.cleaning.identifiers import (
    normalize_fipst,
    normalize_identifiers_dataframe,
    normalize_leaid,
    normalize_ncessch,
    normalize_schid,
    standardize_school_year,
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
        df = pd.DataFrame({
            "school_id": ["10000500871", "010000500879"],
            "district_id": ["100005", "0100005"],
            "state_fips": ["1", "01"],
            "school_year": ["2018-2019", "2019-2020"],
        })
        normalized = normalize_identifiers_dataframe(df)

        assert normalized["school_id"].tolist() == ["010000500871", "010000500879"]
        assert normalized["district_id"].tolist() == ["0100005", "0100005"]
        assert normalized["state_fips"].tolist() == ["01", "01"]
        assert normalized["school_year"].tolist() == ["2018-19", "2019-20"]
