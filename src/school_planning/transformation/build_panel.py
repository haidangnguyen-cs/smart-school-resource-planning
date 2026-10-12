"""Analytical school-year panel builder enforcing 1:0..1 spine join contracts."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from school_planning.validation.key_checks import validate_key_uniqueness
from school_planning.validation.relationship_checks import validate_spine_relationships

logger = logging.getLogger(__name__)


def build_single_year_panel(
    directory_df: pd.DataFrame,
    staff_df: pd.DataFrame,
    membership_df: pd.DataFrame,
    join_keys: tuple[str, str] = ("school_id", "school_year"),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Construct analytical panel for a single school year via 1:0..1 spine left joins.

    Contract Invariants:
    1. Directory is the spine table; every directory record is preserved.
    2. Target keys in staff and membership must be strictly unique (1:0..1 cardinality).
    3. Exactly zero Cartesian row multiplication: len(panel) == len(directory).
    4. Unmatched spine records retain null measure values and are audited.

    Args:
        directory_df: Clean Directory spine DataFrame.
        staff_df: Clean Staff DataFrame.
        membership_df: Clean Membership DataFrame.
        join_keys: Composite primary key columns.

    Returns:
        Tuple of (panel DataFrame, reconciliation metrics dict).

    Raises:
        ValueError: If join invariants or key uniqueness are violated.
    """
    keys = list(join_keys)

    # 1. Validate key uniqueness on each input component
    for name, df in [("directory", directory_df), ("staff", staff_df), ("membership", membership_df)]:
        key_res = validate_key_uniqueness(df, key_cols=keys, raise_on_error=False)
        if not key_res["valid"]:
            raise ValueError(f"Input {name} table has duplicate keys: {key_res['errors']}")

    # 2. Validate spine relationship integrity
    staff_rel = validate_spine_relationships(
        spine_df=directory_df,
        target_df=staff_df,
        join_keys=keys,
        target_name="staff",
    )
    if not staff_rel["target_key_unique"]:
        raise ValueError(f"Staff relationship validation failed: {staff_rel['errors']}")

    mem_rel = validate_spine_relationships(
        spine_df=directory_df,
        target_df=membership_df,
        join_keys=keys,
        target_name="membership",
    )
    if not mem_rel["target_key_unique"]:
        raise ValueError(f"Membership relationship validation failed: {mem_rel['errors']}")

    # 3. Select columns from target components to avoid collisions
    staff_cols_to_merge = [c for c in staff_df.columns if c in keys or c not in directory_df.columns]
    staff_subset = staff_df[staff_cols_to_merge]

    # Perform left join with Staff
    panel = directory_df.merge(staff_subset, on=keys, how="left")

    mem_cols_to_merge = [c for c in membership_df.columns if c in keys or c not in panel.columns]
    mem_subset = membership_df[mem_cols_to_merge]

    # Perform left join with Membership
    panel = panel.merge(mem_subset, on=keys, how="left")

    # 4. Enforce invariant: output rows must equal spine rows
    if len(panel) != len(directory_df):
        raise ValueError(
            f"Join multiplied rows! Spine rows: {len(directory_df)}, Panel rows: {len(panel)}"
        )

    # Ensure zero duplicate keys in output panel
    panel_key_res = validate_key_uniqueness(panel, key_cols=keys, raise_on_error=False)
    if not panel_key_res["valid"]:
        raise ValueError(f"Output panel violates composite key uniqueness: {panel_key_res['errors']}")

    metrics = {
        "spine_rows": len(directory_df),
        "panel_rows": len(panel),
        "staff_records_matched": staff_rel["matched_keys_count"],
        "staff_unmatched_spine": staff_rel["unmatched_spine_keys_count"],
        "staff_match_rate": staff_rel["match_rate_pct"],
        "membership_records_matched": mem_rel["matched_keys_count"],
        "membership_unmatched_spine": mem_rel["unmatched_spine_keys_count"],
        "membership_match_rate": mem_rel["match_rate_pct"],
        "orphan_staff_records": staff_rel["unmatched_target_keys_count"],
        "orphan_membership_records": mem_rel["unmatched_target_keys_count"],
    }

    return panel, metrics


def build_longitudinal_panel(
    yearly_directories: list[pd.DataFrame],
    yearly_staff: list[pd.DataFrame],
    yearly_memberships: list[pd.DataFrame],
    join_keys: tuple[str, str] = ("school_id", "school_year"),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Assemble longitudinal analytical panel across multiple school years.

    Args:
        yearly_directories: List of cleaned Directory DataFrames (one per year).
        yearly_staff: List of cleaned Staff DataFrames (one per year).
        yearly_memberships: List of cleaned Membership DataFrames (one per year).
        join_keys: Composite primary key columns.

    Returns:
        Tuple of (consolidated longitudinal panel DataFrame, multi-year metrics dict).
    """
    if not (len(yearly_directories) == len(yearly_staff) == len(yearly_memberships)):
        raise ValueError("Mismatched count of yearly component DataFrames")

    yearly_panels = []
    yearly_metrics = {}

    for d_df, s_df, m_df in zip(yearly_directories, yearly_staff, yearly_memberships, strict=True):
        year_val = d_df["school_year"].iloc[0] if "school_year" in d_df.columns and not d_df.empty else "unknown"
        p_df, m_dict = build_single_year_panel(d_df, s_df, m_df, join_keys=join_keys)
        yearly_panels.append(p_df)
        yearly_metrics[year_val] = m_dict

    full_panel = pd.concat(yearly_panels, ignore_index=True)

    # Sort deterministically
    sort_cols = [c for c in list(join_keys) if c in full_panel.columns]
    if sort_cols:
        full_panel = full_panel.sort_values(sort_cols).reset_index(drop=True)

    # Verify overall composite primary key uniqueness
    key_res = validate_key_uniqueness(full_panel, key_cols=list(join_keys), raise_on_error=False)
    if not key_res["valid"]:
        raise ValueError(f"Longitudinal panel contains duplicate composite keys: {key_res['errors']}")

    overall_metrics = {
        "total_records": len(full_panel),
        "total_unique_schools": full_panel["school_id"].nunique() if "school_id" in full_panel.columns else 0,
        "school_years": sorted(full_panel["school_year"].unique().tolist()) if "school_year" in full_panel.columns else [],
        "yearly_metrics": yearly_metrics,
    }

    return full_panel, overall_metrics


def save_panel_parquet(
    panel_df: pd.DataFrame,
    output_path: Path | str,
) -> Path:
    """Save panel DataFrame to Parquet format.

    Args:
        panel_df: Consolidated analytical panel DataFrame.
        output_path: Destination path for Parquet file.

    Returns:
        Path to saved Parquet file.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    panel_df.to_parquet(out_file, engine="pyarrow", index=False)
    logger.info("Saved analytical panel (%d rows) to %s", len(panel_df), out_file)
    return out_file
