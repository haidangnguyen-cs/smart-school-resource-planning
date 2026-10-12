#!/usr/bin/env python3
"""03_build_panel.py - Construct validated longitudinal analytical panel from normalized components.

Joins Directory (spine), Staff, and Membership components via 1:0..1 left joins,
enforcing strict grain invariants and generating reconciliation audit reports.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from school_planning.transformation.build_panel import (
    build_longitudinal_panel,
    save_panel_parquet,
)
from school_planning.transformation.directory import transform_directory
from school_planning.transformation.membership import transform_membership
from school_planning.transformation.staff import transform_staff

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("03_build_panel")


def load_sources_config(config_path: Path | None = None) -> dict:
    """Load sources.yaml configuration."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "sources.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_and_save_panel(
    project_root: Path = PROJECT_ROOT,
    years: list[str] | None = None,
    interim_dir: Path | None = None,
    output_dir: Path | None = None,
    reports_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Build and save analytical panel and reconciliation report.

    Args:
        project_root: Project root directory.
        years: List of school years to include.
        interim_dir: Directory containing normalized Parquet files.
        output_dir: Directory to save processed panel.
        reports_dir: Directory to save quality reconciliation report.

    Returns:
        Tuple of (longitudinal panel DataFrame, reconciliation report dict).
    """
    if years is None:
        years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]

    if interim_dir is None:
        interim_dir = project_root / "data" / "interim" / "normalized"

    if output_dir is None:
        output_dir = project_root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    if reports_dir is None:
        reports_dir = project_root / "outputs" / "quality_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources_cfg = load_sources_config(project_root / "config" / "sources.yaml")
    cfg_components = sources_cfg.get("components", {})

    yearly_directories: list[pd.DataFrame] = []
    yearly_staff: list[pd.DataFrame] = []
    yearly_memberships: list[pd.DataFrame] = []

    logger.info("Loading normalized components across %d school years...", len(years))
    start_t = time.time()

    for yr in years:
        year_slug = yr.replace("-", "_")
        dir_pq = interim_dir / f"directory_{year_slug}.parquet"
        staff_pq = interim_dir / f"staff_{year_slug}.parquet"
        mem_pq = interim_dir / f"membership_{year_slug}.parquet"

        # Load from interim Parquet if available, else load from raw via transformation
        if dir_pq.exists():
            d_df = pd.read_parquet(dir_pq)
        else:
            raw_path = project_root / cfg_components["directory"]["files"][yr]["path"]
            logger.info("Loading Directory from raw: %s", raw_path.name)
            d_df = transform_directory(raw_path)

        if staff_pq.exists():
            s_df = pd.read_parquet(staff_pq)
        else:
            raw_path = project_root / cfg_components["staff"]["files"][yr]["path"]
            logger.info("Loading Staff from raw: %s", raw_path.name)
            s_df = transform_staff(raw_path)

        if mem_pq.exists():
            m_df = pd.read_parquet(mem_pq)
        else:
            raw_path = project_root / cfg_components["membership"]["files"][yr]["path"]
            logger.info("Loading Membership from raw: %s", raw_path.name)
            m_df = transform_membership(raw_path)

        yearly_directories.append(d_df)
        yearly_staff.append(s_df)
        yearly_memberships.append(m_df)

    logger.info("Assembling longitudinal panel across all school years...")
    panel_df, panel_metrics = build_longitudinal_panel(
        yearly_directories=yearly_directories,
        yearly_staff=yearly_staff,
        yearly_memberships=yearly_memberships,
    )

    # Save processed panel
    out_file = output_dir / "school_year_panel.parquet"
    save_panel_parquet(panel_df, out_file)

    # Compile comprehensive reconciliation report
    status_distribution = {}
    if "school_status" in panel_df.columns:
        status_distribution = panel_df["school_status"].value_counts(dropna=False).to_dict()

    missingness_summary = {
        "missing_teacher_fte": int(panel_df["teacher_fte"].isna().sum())
        if "teacher_fte" in panel_df.columns
        else 0,
        "zero_teacher_anomalies": int((panel_df["zero_teacher_anomaly"] == True).sum())
        if "zero_teacher_anomaly" in panel_df.columns
        else 0,
        "missing_total_students": int(panel_df["total_students"].isna().sum())
        if "total_students" in panel_df.columns
        else 0,
    }

    report = {
        "panel_file": str(out_file),
        "total_records": len(panel_df),
        "total_unique_schools": int(panel_df["school_id"].nunique())
        if "school_id" in panel_df.columns
        else 0,
        "school_years": panel_metrics["school_years"],
        "yearly_metrics": panel_metrics["yearly_metrics"],
        "status_distribution": status_distribution,
        "missingness_summary": missingness_summary,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    report_path = reports_dir / "panel_reconciliation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Reconciliation report saved to %s", report_path)
    logger.info("Panel construction complete in %.2fs", time.time() - start_t)

    return panel_df, report


def main():
    """CLI entry point for 03_build_panel.py."""
    parser = argparse.ArgumentParser(description="Build analytical school-year panel.")
    parser.add_argument("--years", nargs="+", help="Specific school years to include.")
    parser.add_argument("--interim-dir", type=Path, help="Custom interim Parquet directory.")
    parser.add_argument("--output-dir", type=Path, help="Custom output directory.")
    parser.add_argument("--reports-dir", type=Path, help="Custom reports directory.")
    args = parser.parse_args()

    build_and_save_panel(
        years=args.years,
        interim_dir=args.interim_dir,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
    )


if __name__ == "__main__":
    main()
