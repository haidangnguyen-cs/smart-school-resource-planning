import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "01_audit_sources.py"
spec = importlib.util.spec_from_file_location("audit_sources_module", SCRIPT_PATH)
audit_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(audit_module)
run_source_audit = audit_module.run_source_audit


@pytest.fixture
def dummy_project(tmp_path: Path) -> Path:
    """Create a minimal temporary project structure with sources.yaml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    sources_yaml = config_dir / "sources.yaml"
    sources_yaml.write_text(
        """
components:
  directory:
    code: "029"
    files:
      "2018-19":
        filename: "dir_1819.csv"
        path: "data/raw/dir_1819.csv"
  staff:
    code: "059"
    files:
      "2018-19":
        filename: "staff_1819.csv"
        path: "data/raw/staff_1819.csv"
  membership:
    code: "052"
    files:
      "2018-19":
        filename: "mem_1819.csv"
        path: "data/raw/mem_1819.csv"
""",
        encoding="utf-8",
    )
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestAuditScriptFailurePaths:
    """Tests verifying that all failure paths aggregate into FAILED audit status."""

    def test_audit_fails_on_missing_source_files(self, dummy_project: Path):
        # No CSV files created in dummy_project data/raw/
        res = run_source_audit(project_root=dummy_project, years=["2018-19"], write_reports=False)

        assert res["status"] == "FAILED"
        assert len(res["errors"]) > 0
        error_text = " ".join(res["errors"])
        assert "Missing required Directory" in error_text
        assert "Missing required Staff" in error_text
        assert "Missing required Membership" in error_text

    def test_audit_fails_on_schema_validation_error(self, dummy_project: Path):
        raw_dir = dummy_project / "data" / "raw"

        # Directory missing required column 'school_status'
        df_dir = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "LEAID": ["0100005"],
                "FIPST": ["01"],
                "SCHOOL_YEAR": ["2018-2019"],
                "SCH_NAME": ["Test School"],
                # missing SY_STATUS_TEXT / school_status
            }
        )
        df_dir.to_csv(raw_dir / "dir_1819.csv", index=False)

        # Valid staff and membership
        df_staff = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "SCHOOL_YEAR": ["2018-2019"],
                "TEACHERS": [10.0],
                "DMS_FLAG": ["Reported"],
                "TOTAL_INDICATOR": ["Education Unit Total"],
            }
        )
        df_staff.to_csv(raw_dir / "staff_1819.csv", index=False)

        df_mem = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "SCHOOL_YEAR": ["2018-2019"],
                "STUDENT_COUNT": [100],
                "TOTAL_INDICATOR": ["Derived - Education Unit Total minus Adult Education Count"],
                "DMS_FLAG": ["Reported"],
            }
        )
        df_mem.to_csv(raw_dir / "mem_1819.csv", index=False)

        res = run_source_audit(project_root=dummy_project, years=["2018-19"], write_reports=False)

        assert res["status"] == "FAILED"
        assert any("Missing mandatory columns" in e for e in res["errors"])

    def test_audit_fails_on_relationship_integrity_error(self, dummy_project: Path):
        raw_dir = dummy_project / "data" / "raw"

        # Valid Directory
        df_dir = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "LEAID": ["0100005"],
                "FIPST": ["01"],
                "SCHOOL_YEAR": ["2018-2019"],
                "SCH_NAME": ["Test School"],
                "SY_STATUS_TEXT": ["Open"],
            }
        )
        df_dir.to_csv(raw_dir / "dir_1819.csv", index=False)

        # Staff with DUPLICATE join keys (violates 1:0..1 cardinality contract)
        df_staff = pd.DataFrame(
            {
                "NCESSCH": ["010000500871", "010000500871"],
                "SCHOOL_YEAR": ["2018-2019", "2018-2019"],
                "TEACHERS": [10.0, 12.0],
                "DMS_FLAG": ["Reported", "Reported"],
                "TOTAL_INDICATOR": ["Education Unit Total", "Education Unit Total"],
            }
        )
        df_staff.to_csv(raw_dir / "staff_1819.csv", index=False)

        df_mem = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "SCHOOL_YEAR": ["2018-2019"],
                "STUDENT_COUNT": [100],
                "TOTAL_INDICATOR": ["Derived - Education Unit Total minus Adult Education Count"],
                "DMS_FLAG": ["Reported"],
            }
        )
        df_mem.to_csv(raw_dir / "mem_1819.csv", index=False)

        res = run_source_audit(project_root=dummy_project, years=["2018-19"], write_reports=False)

        assert res["status"] == "FAILED"
        assert any("1:0..1" in e for e in res["errors"])

    def test_audit_fails_on_missing_directory_primary_key_column(self, dummy_project: Path):
        raw_dir = dummy_project / "data" / "raw"

        # Directory file missing NCESSCH primary key column entirely
        df_dir = pd.DataFrame(
            {
                "LEAID": ["0100005"],
                "FIPST": ["01"],
                "SCHOOL_YEAR": ["2018-2019"],
                "SCH_NAME": ["Test School Without NCESSCH"],
                "SY_STATUS_TEXT": ["Open"],
            }
        )
        df_dir.to_csv(raw_dir / "dir_1819.csv", index=False)

        # Valid staff and membership
        df_staff = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "SCHOOL_YEAR": ["2018-2019"],
                "TEACHERS": [10.0],
                "DMS_FLAG": ["Reported"],
                "TOTAL_INDICATOR": ["Education Unit Total"],
            }
        )
        df_staff.to_csv(raw_dir / "staff_1819.csv", index=False)

        df_mem = pd.DataFrame(
            {
                "NCESSCH": ["010000500871"],
                "SCHOOL_YEAR": ["2018-2019"],
                "STUDENT_COUNT": [100],
                "TOTAL_INDICATOR": ["Derived - Education Unit Total minus Adult Education Count"],
                "DMS_FLAG": ["Reported"],
            }
        )
        df_mem.to_csv(raw_dir / "mem_1819.csv", index=False)

        res = run_source_audit(project_root=dummy_project, years=["2018-19"], write_reports=False)

        assert res["status"] == "FAILED"
        assert len(res["errors"]) > 0
        assert any("school_id" in e for e in res["errors"])
        # Verify that structured report was safely generated without unhandled KeyError crash
        assert "2018-19" in res["year_summaries"]
        assert res["year_summaries"]["2018-19"]["directory"]["schema_valid"] is False
