"""Identifier normalization and canonical school-year formatting."""

import re
from typing import Any

import pandas as pd

SCHOOL_YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def _to_clean_string(val: Any) -> str | None:
    """Helper to convert value to stripped string, handling nulls and floats."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, float):
        if val.is_integer():
            val = int(val)
        else:
            return str(val).strip()
    s = str(val).strip()
    return s if s != "" else None


def normalize_ncessch(val: Any) -> str | None:
    """Normalize NCES School ID to 12-character zero-padded string."""
    clean = _to_clean_string(val)
    if clean is None:
        return None
    # Strip scientific notation if accidentally represented
    if clean.isdigit() and len(clean) <= 12:
        return clean.zfill(12)
    return clean.zfill(12) if clean.isdigit() else clean


def normalize_leaid(val: Any) -> str | None:
    """Normalize LEA ID to 7-character zero-padded string."""
    clean = _to_clean_string(val)
    if clean is None:
        return None
    if clean.isdigit() and len(clean) <= 7:
        return clean.zfill(7)
    return clean.zfill(7) if clean.isdigit() else clean


def normalize_fipst(val: Any) -> str | None:
    """Normalize State FIPS code to 2-character zero-padded string."""
    clean = _to_clean_string(val)
    if clean is None:
        return None
    if clean.isdigit() and len(clean) <= 2:
        return clean.zfill(2)
    return clean.zfill(2) if clean.isdigit() else clean


def normalize_schid(val: Any) -> str | None:
    """Normalize raw SCHID audit string to 7-character zero-padded string.

    Note: SCHID is preserved strictly as an empirical audit string and must never
    be used as a join key or primary entity key.
    """
    clean = _to_clean_string(val)
    if clean is None:
        return None
    if clean.isdigit() and len(clean) <= 7:
        return clean.zfill(7)
    return clean


def standardize_school_year(val: Any) -> str | None:
    """Convert raw school year representations to canonical YYYY-YY (length 7).

    Examples:
        '2018-2019' -> '2018-19'
        '2018-19'   -> '2018-19'
    """
    clean = _to_clean_string(val)
    if clean is None:
        return None
    if SCHOOL_YEAR_PATTERN.match(clean):
        return clean
    if len(clean) == 9 and clean[4] == "-":
        start_year = clean[:4]
        end_year_short = clean[-2:]
        transformed = f"{start_year}-{end_year_short}"
        if SCHOOL_YEAR_PATTERN.match(transformed):
            return transformed
    raise ValueError(f"Unrecognized school year format: '{val}' (expected YYYY-YYYY or YYYY-YY)")


def normalize_identifiers_dataframe(
    df: pd.DataFrame,
    school_id_col: str = "NCESSCH",
    district_id_col: str = "LEAID",
    state_fips_col: str = "FIPST",
    schid_col: str = "SCHID",
    year_col: str = "SCHOOL_YEAR",
) -> pd.DataFrame:
    """Apply identifier normalization and school-year standardization across a DataFrame."""
    out = df.copy()

    for col in (school_id_col, "school_id"):
        if col in out.columns:
            out[col] = out[col].apply(normalize_ncessch)
            break

    for col in (district_id_col, "district_id"):
        if col in out.columns:
            out[col] = out[col].apply(normalize_leaid)
            break

    for col in (state_fips_col, "state_fips"):
        if col in out.columns:
            out[col] = out[col].apply(normalize_fipst)
            break

    for col in (schid_col, "schid"):
        if col in out.columns:
            out[col] = out[col].apply(normalize_schid)
            break

    for col in (year_col, "school_year"):
        if col in out.columns:
            out[col] = out[col].apply(standardize_school_year)
            break

    return out
