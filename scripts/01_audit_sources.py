#!/usr/bin/env python3
"""01_audit_sources.py - Source inspection, checksum verification, and quality audit script.

Executes the NCES data ingestion and quality validation protocol across all 15 NCES CCD raw source files:
1. Builds machine-readable source file manifest with SHA-256 hashes and schema counts.
2. Validates schema compliance, key uniqueness, and business rules across components.
3. Verifies 1:0..1 join integrity between Directory spine and target components.
4. Generates audit outputs in outputs/quality_reports/.
"""

import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from school_planning.ingestion.manifest import build_source_manifest
from school_planning.ingestion.source_adapters import (
    load_directory_component,
    load_membership_component,
    load_staff_component,
)
from school_planning.validation.business_rules import validate_business_rules
from school_planning.validation.key_checks import validate_key_uniqueness
from school_planning.validation.relationship_checks import validate_spine_relationships
from school_planning.validation.schema_checks import validate_dataframe_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit_sources")


def run_source_audit(
    project_root: Path = PROJECT_ROOT,
    years: list[str] | None = None,
    write_reports: bool = True,
) -> dict:
    """Run comprehensive source audit across all available CCD components and years."""
    reports_dir = project_root / "outputs" / "quality_reports"
    if write_reports:
        reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Step 1: Generating source file manifest and SHA-256 checksums...")
    start_t = time.time()
    manifest = build_source_manifest(project_root=project_root, compute_hashes=True)
    if write_reports:
        manifest_path = reports_dir / "source_manifest.json"
        manifest.save_json(manifest_path)
        # Also save inventory mirror for backward compatibility with existing inventory consumers
        manifest.save_json(reports_dir / "source_inventory.json")
    logger.info("Manifest generated with %d files in %.2fs", len(manifest.entries), time.time() - start_t)

    # Years to evaluate
    if years is None:
        years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]

    year_summaries = {}
    overall_errors = []

    logger.info("Step 2: Auditing components and join relationships across all %d school years...", len(years))

    for year in years:
        logger.info("Auditing School Year: %s", year)
        year_entry = {}

        # Locate raw files
        dir_file = next(
            (e.relative_path for e in manifest.entries if e.component == "directory" and e.school_year == year),
            None,
        )
        staff_file = next(
            (e.relative_path for e in manifest.entries if e.component == "staff" and e.school_year == year),
            None,
        )
        mem_file = next(
            (e.relative_path for e in manifest.entries if e.component == "membership" and e.school_year == year),
            None,
        )

        # 1. Directory
        dir_df = None
        if not dir_file or not (project_root / dir_file).exists():
            overall_errors.append(f"[{year}] Missing required Directory (029) component file.")
        else:
            full_path = project_root / dir_file
            dir_df = load_directory_component(full_path)
            schema_res = validate_dataframe_schema(
                dir_df,
                required_columns=["school_id", "district_id", "state_fips", "school_year", "school_name", "school_status"],
            )
            has_dir_keys = all(col in dir_df.columns for col in ["school_id", "school_year"])
            if has_dir_keys:
                key_res = validate_key_uniqueness(dir_df, key_cols=["school_id", "school_year"])
            else:
                key_res = {
                    "valid": False,
                    "errors": ["Directory key uniqueness skipped: missing primary key columns."],
                    "duplicate_rows_count": 0,
                }
            biz_res = validate_business_rules(dir_df)

            year_entry["directory"] = {
                "rows": len(dir_df),
                "schema_valid": schema_res["valid"],
                "key_valid": key_res["valid"],
                "duplicates": key_res["duplicate_rows_count"],
                "status_distribution": biz_res.get("status_checks", {}).get("status_distribution", {}),
            }
            if not schema_res["valid"]:
                overall_errors.extend(schema_res["errors"])
            if not key_res["valid"]:
                overall_errors.extend(key_res["errors"])
            if not biz_res["valid"]:
                overall_errors.extend(biz_res["errors"])

        # 2. Staff
        staff_df = None
        if not staff_file or not (project_root / staff_file).exists():
            overall_errors.append(f"[{year}] Missing required Staff (059) component file.")
        else:
            full_path = project_root / staff_file
            staff_df = load_staff_component(full_path)
            schema_res = validate_dataframe_schema(
                staff_df,
                required_columns=["school_id", "school_year", "teacher_fte", "teacher_data_flag"],
            )
            has_staff_keys = all(col in staff_df.columns for col in ["school_id", "school_year"])
            if has_staff_keys:
                key_res = validate_key_uniqueness(staff_df, key_cols=["school_id", "school_year"])
            else:
                key_res = {
                    "valid": False,
                    "errors": ["Staff key uniqueness skipped: missing primary key columns."],
                    "duplicate_rows_count": 0,
                }
            biz_res = validate_business_rules(staff_df)

            year_entry["staff"] = {
                "rows": len(staff_df),
                "schema_valid": schema_res["valid"],
                "key_valid": key_res["valid"],
                "duplicates": key_res["duplicate_rows_count"],
                "zero_teacher_anomalies": int(staff_df["zero_teacher_anomaly"].sum()) if "zero_teacher_anomaly" in staff_df.columns else 0,
                "missing_teacher_fte": int(staff_df["teacher_fte"].isna().sum()) if "teacher_fte" in staff_df.columns else 0,
            }
            if not schema_res["valid"]:
                overall_errors.extend(schema_res["errors"])
            if not key_res["valid"]:
                overall_errors.extend(key_res["errors"])
            if not biz_res["valid"]:
                overall_errors.extend(biz_res["errors"])

        # 3. Membership (Streaming chunk loader)
        mem_df = None
        if not mem_file or not (project_root / mem_file).exists():
            overall_errors.append(f"[{year}] Missing required Membership (052) component file.")
        else:
            full_path = project_root / mem_file
            mem_df = load_membership_component(full_path)
            schema_res = validate_dataframe_schema(
                mem_df,
                required_columns=["school_id", "school_year", "total_students", "enrollment_total_indicator"],
            )
            has_mem_keys = all(col in mem_df.columns for col in ["school_id", "school_year"])
            if has_mem_keys:
                key_res = validate_key_uniqueness(mem_df, key_cols=["school_id", "school_year"])
            else:
                key_res = {
                    "valid": False,
                    "errors": ["Membership key uniqueness skipped: missing primary key columns."],
                    "duplicate_rows_count": 0,
                }
            biz_res = validate_business_rules(mem_df)

            year_entry["membership"] = {
                "filtered_rows": len(mem_df),
                "schema_valid": schema_res["valid"],
                "key_valid": key_res["valid"],
                "duplicates": key_res["duplicate_rows_count"],
                "missing_students": biz_res.get("student_checks", {}).get("missing_enrollment_count", 0),
                "zero_students": biz_res.get("student_checks", {}).get("zero_enrollment_count", 0),
            }
            if not schema_res["valid"]:
                overall_errors.extend(schema_res["errors"])
            if not key_res["valid"]:
                overall_errors.extend(key_res["errors"])
            if not biz_res["valid"]:
                overall_errors.extend(biz_res["errors"])

        # 4. Join Relationships with Directory Spine
        can_check_staff_rel = (
            dir_df is not None
            and staff_df is not None
            and all(col in dir_df.columns for col in ["school_id", "school_year"])
            and all(col in staff_df.columns for col in ["school_id", "school_year"])
        )
        if can_check_staff_rel:
            rel_staff = validate_spine_relationships(
                dir_df, staff_df, join_keys=["school_id", "school_year"], target_name="staff"
            )
            year_entry["spine_vs_staff"] = {
                "match_rate_pct": rel_staff["match_rate_pct"],
                "unmatched_spine": rel_staff["unmatched_spine_keys_count"],
                "unmatched_target": rel_staff["unmatched_target_keys_count"],
                "cardinality_valid": rel_staff["target_key_unique"],
            }
            if not rel_staff["valid"]:
                overall_errors.extend(rel_staff["errors"])
        else:
            overall_errors.append(f"[{year}] Cannot validate spine vs staff relationship: missing Directory or Staff key columns/data.")
            year_entry["spine_vs_staff"] = {"cardinality_valid": False, "match_rate_pct": 0.0}

        can_check_mem_rel = (
            dir_df is not None
            and mem_df is not None
            and all(col in dir_df.columns for col in ["school_id", "school_year"])
            and all(col in mem_df.columns for col in ["school_id", "school_year"])
        )
        if can_check_mem_rel:
            rel_mem = validate_spine_relationships(
                dir_df, mem_df, join_keys=["school_id", "school_year"], target_name="membership"
            )
            year_entry["spine_vs_membership"] = {
                "match_rate_pct": rel_mem["match_rate_pct"],
                "unmatched_spine": rel_mem["unmatched_spine_keys_count"],
                "unmatched_target": rel_mem["unmatched_target_keys_count"],
                "cardinality_valid": rel_mem["target_key_unique"],
            }
            if not rel_mem["valid"]:
                overall_errors.extend(rel_mem["errors"])
        else:
            overall_errors.append(f"[{year}] Cannot validate spine vs membership relationship: missing Directory or Membership key columns/data.")
            year_entry["spine_vs_membership"] = {"cardinality_valid": False, "match_rate_pct": 0.0}

        year_summaries[year] = year_entry

    audit_summary = {
        "status": "PASSED" if len(overall_errors) == 0 else "FAILED",
        "errors": overall_errors,
        "files_audited": len(manifest.entries),
        "year_summaries": year_summaries,
    }

    if write_reports:
        report_path = reports_dir / "source_audit_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_summary, f, indent=2)
        logger.info("Source audit completed successfully. Report written to %s", report_path)

    return audit_summary


if __name__ == "__main__":
    result = run_source_audit()
    print("\n" + "=" * 60)
    print(f"SOURCE AUDIT SUMMARY - Status: {result['status']}")
    print(f"Files Audited: {result['files_audited']}")
    for yr, data in result["year_summaries"].items():
        print(f"\n[{yr}]")
        dir_rows = data.get("directory", {}).get("rows", "N/A")
        staff_rows = data.get("staff", {}).get("rows", "N/A")
        mem_rows = data.get("membership", {}).get("filtered_rows", "N/A")
        staff_match = data.get("spine_vs_staff", {}).get("match_rate_pct", "N/A")
        mem_match = data.get("spine_vs_membership", {}).get("match_rate_pct", "N/A")
        print(f"  Directory spine rows: {dir_rows}")
        print(f"  Staff rows: {staff_rows} (Match: {staff_match}%)")
        print(f"  Membership filtered rows: {mem_rows} (Match: {mem_match}%)")
    print("=" * 60)
    if result["status"] != "PASSED":
        sys.exit(1)
