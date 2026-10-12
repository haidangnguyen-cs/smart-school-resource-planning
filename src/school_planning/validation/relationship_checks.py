"""Relationship, join integrity, and spine cardinality validation."""

from typing import Any

import pandas as pd


def validate_spine_relationships(
    spine_df: pd.DataFrame,
    target_df: pd.DataFrame,
    join_keys: list[str],
    target_name: str = "target",
    expected_match_rate_min: float = 0.90,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """Validate 1:0..1 left join relationship from Directory spine to a target component.

    Adheres strictly to ADR-09 and config/quality_rules.yaml:
    - Target keys must be strictly unique (prevents Cartesian row explosion).
    - Spine match rate is verified against expected minimum (typically >= 96%).
    - Unmatched spine records are expected (~2-4%) and permitted as valid audit cases.

    Args:
        spine_df: Directory spine DataFrame.
        target_df: Target component DataFrame (Staff or Membership).
        join_keys: Columns forming the join key (e.g. ['school_id', 'school_year']).
        target_name: Informational label for error messages.
        expected_match_rate_min: Minimum acceptable match rate for spine records (0.0 - 1.0).
        raise_on_error: Whether to raise ValueError on fatal integrity violations.

    Returns:
        Structured dictionary reporting join cardinality, match rates, and integrity findings.
    """
    missing_spine = [col for col in join_keys if col not in spine_df.columns]
    missing_target = [col for col in join_keys if col not in target_df.columns]
    if missing_spine or missing_target:
        errs = []
        if missing_spine:
            errs.append(f"Join key(s) {missing_spine} missing from spine DataFrame.")
        if missing_target:
            errs.append(f"Join key(s) {missing_target} missing from target '{target_name}' DataFrame.")
        if raise_on_error:
            raise KeyError("; ".join(errs))
        return {
            "valid": False,
            "target_name": target_name,
            "target_key_unique": False,
            "match_rate_pct": 0.0,
            "unmatched_spine_keys_count": len(spine_df),
            "unmatched_target_keys_count": len(target_df),
            "errors": errs,
            "warnings": [],
        }

    spine_rows = len(spine_df)
    target_rows = len(target_df)

    # 1. Target uniqueness check: Target must NOT have duplicates on join_keys
    target_dups = int(target_df.duplicated(subset=join_keys).sum())
    target_key_unique = target_dups == 0

    errors = []
    warnings = []

    if not target_key_unique:
        errors.append(
            f"Target table '{target_name}' contains {target_dups} duplicate keys on {join_keys}. "
            "Violates 1:0..1 cardinality contract and would cause Cartesian row multiplication."
        )

    # 2. Key set comparisons
    spine_keys_set = set(spine_df[join_keys].itertuples(index=False, name=None))
    target_keys_set = set(target_df[join_keys].itertuples(index=False, name=None))

    matched_keys = spine_keys_set.intersection(target_keys_set)
    unmatched_spine = spine_keys_set.difference(target_keys_set)
    unmatched_target = target_keys_set.difference(spine_keys_set)

    matched_count = len(matched_keys)
    unmatched_spine_count = len(unmatched_spine)
    unmatched_target_count = len(unmatched_target)

    match_rate_pct = (matched_count / len(spine_keys_set) * 100) if spine_keys_set else 0.0

    if (match_rate_pct / 100.0) < expected_match_rate_min:
        warnings.append(
            f"Spine match rate ({match_rate_pct:.2f}%) with '{target_name}' is below expected threshold "
            f"({expected_match_rate_min * 100:.1f}%)."
        )

    if unmatched_target_count > 0:
        warnings.append(
            f"Target table '{target_name}' contains {unmatched_target_count} records not present in the Directory spine."
        )

    valid = len(errors) == 0

    if not valid and raise_on_error:
        raise ValueError(f"Relationship validation failed: {'; '.join(errors)}")

    return {
        "valid": valid,
        "target_name": target_name,
        "cardinality": "1:0..1",
        "target_key_unique": target_key_unique,
        "spine_rows": spine_rows,
        "target_rows": target_rows,
        "matched_keys_count": matched_count,
        "unmatched_spine_keys_count": unmatched_spine_count,
        "unmatched_target_keys_count": unmatched_target_count,
        "match_rate_pct": round(match_rate_pct, 2),
        "errors": errors,
        "warnings": warnings,
    }
