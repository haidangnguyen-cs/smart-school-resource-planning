"""Unit tests for ingestion readers, streaming, and component loaders."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from school_planning.ingestion.manifest import build_source_manifest
from school_planning.ingestion.readers import (
    determine_encoding,
    read_csv_robust,
    stream_csv_chunks,
)
from school_planning.ingestion.source_adapters import (
    load_directory_component,
    load_membership_component,
    load_staff_component,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestCSVReaders:
    """Tests for low-level CSV readers and encoding resolution."""

    def test_determine_encoding_utf8(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".csv") as f:
            f.write("col1,col2\nhello,world\n")
            path = Path(f.name)

        try:
            assert determine_encoding(path) == "utf-8"
        finally:
            path.unlink()

    def test_determine_encoding_windows1252(self):
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as f:
            # 0x96 is an en-dash in windows-1252, invalid in UTF-8
            f.write(b"col1,col2\nMontclair\x96High,100\n")
            path = Path(f.name)

        try:
            assert determine_encoding(path) == "windows-1252"
        finally:
            path.unlink()

    def test_determine_encoding_chunk_boundary_straddle(self):
        # Construct content where multi-byte UTF-8 character straddles a chunk boundary
        # chunk_size = 16: first 15 bytes ASCII, followed by 2-byte UTF-8 char (b'\xc3\xa9' -> 'é')
        # byte index 15 is \xc3 (end of chunk 1), byte index 16 is \xa9 (start of chunk 2)
        prefix = b"0123456789abcde"  # 15 bytes
        utf8_char = "é".encode()  # 2 bytes: b'\xc3\xa9'
        suffix = b",extra_valid_text\n"
        content_valid = prefix + utf8_char + suffix

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as f:
            f.write(content_valid)
            path_valid = Path(f.name)

        try:
            assert determine_encoding(path_valid, chunk_size=16) == "utf-8"
        finally:
            path_valid.unlink()

        # Ensure invalid UTF-8 still falls back to windows-1252 even if boundary straddling occurred
        content_invalid_utf8 = prefix + utf8_char + b"\nMontclair\x96High,100\n"
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as f:
            f.write(content_invalid_utf8)
            path_invalid = Path(f.name)

        try:
            assert determine_encoding(path_invalid, chunk_size=16) == "windows-1252"
        finally:
            path_invalid.unlink()

    def test_read_csv_robust(self):
        sample_path = FIXTURES_DIR / "sample_directory.csv"
        df, enc = read_csv_robust(sample_path)
        assert len(df) == 5
        assert "NCESSCH" in df.columns
        assert "SCHOOL_YEAR" in df.columns
        assert enc in ("utf-8", "windows-1252")

    def test_stream_csv_chunks(self):
        sample_path = FIXTURES_DIR / "sample_directory.csv"
        chunks = list(stream_csv_chunks(sample_path, chunksize=2))
        assert len(chunks) == 3
        total_rows = sum(len(c) for c in chunks)
        assert total_rows == 5

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_csv_robust(Path("nonexistent_path_to_file.csv"))


class TestSourceAdapters:
    """Tests for component-specific ingestion adapters."""

    def test_load_directory_component(self):
        sample_path = FIXTURES_DIR / "sample_directory.csv"
        df = load_directory_component(sample_path)

        assert len(df) == 5
        assert "school_id" in df.columns
        assert "district_id" in df.columns
        assert "state_fips" in df.columns
        assert "school_year" in df.columns
        assert "school_name" in df.columns
        assert "school_status" in df.columns

        # Verify identifier zero-padding
        assert df["school_id"].iloc[0] == "010000500871"
        assert df["district_id"].iloc[0] == "0100005"
        assert df["state_fips"].iloc[0] == "01"
        # Canonical school year
        assert df["school_year"].iloc[0] == "2018-19"

    def test_load_membership_component_filtering(self):
        sample_path = FIXTURES_DIR / "sample_membership.csv"
        df = load_membership_component(
            sample_path,
            primary_indicator="Derived - Education Unit Total minus Adult Education Count",
            chunksize=2,
        )

        # In fixture: 6 rows total, 1 is 'Education Unit Total', 5 are 'Derived ...'
        assert len(df) == 5
        assert "school_id" in df.columns
        assert "total_students" in df.columns
        assert df["school_year"].iloc[0] == "2018-19"
        assert (
            df["enrollment_total_indicator"]
            == "Derived - Education Unit Total minus Adult Education Count"
        ).all()

    def test_load_membership_component_missing_indicator_raises(self, tmp_path):
        bad_csv = tmp_path / "bad_membership.csv"
        bad_csv.write_text(
            "NCESSCH,YEAR,STUDENT_COUNT\n010000500871,2018-2019,450\n",
            encoding="utf-8",
        )
        with pytest.raises(KeyError, match="missing required indicator column 'TOTAL_INDICATOR'"):
            load_membership_component(bad_csv)

    def test_load_staff_component_anomalies_and_missing(self):
        sample_path = FIXTURES_DIR / "sample_staff.csv"
        df = load_staff_component(sample_path)

        assert len(df) == 5
        assert "school_id" in df.columns
        assert "teacher_fte" in df.columns
        assert "zero_teacher_anomaly" in df.columns

        # Check negative value coercion (-1 becomes NaN)
        # 4th row has -1
        assert np.isnan(df.loc[df["school_id"] == "010000600002", "teacher_fte"].iloc[0])

        # Check zero teacher anomaly flag
        # 3rd row has 0.0
        row_zero = df.loc[df["school_id"] == "010000500889"].iloc[0]
        assert row_zero["teacher_fte"] == 0.0
        assert row_zero["zero_teacher_anomaly"] is True or row_zero["zero_teacher_anomaly"] == 1


class TestManifest:
    """Tests for source file manifest builder."""

    def test_build_source_manifest(self, tmp_path):
        # Create temporary dummy source files
        sources_dir = tmp_path / "data" / "raw"
        sources_dir.mkdir(parents=True, exist_ok=True)
        sample_file = sources_dir / "sample.csv"
        sample_file.write_text("NCESSCH,LEAID\n010000500871,0100005\n", encoding="utf-8")

        # Create temporary sources.yaml
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
        filename: "sample.csv"
        path: "data/raw/sample.csv"
""",
            encoding="utf-8",
        )

        manifest = build_source_manifest(
            project_root=tmp_path, sources_cfg_path=sources_yaml, compute_hashes=True
        )
        assert len(manifest.entries) == 1
        entry = manifest.entries[0]
        assert entry.component == "directory"
        assert entry.school_year == "2018-19"
        assert entry.encoding_detected in ("utf-8", "windows-1252")
        assert len(entry.sha256) == 64
        summary = manifest.to_summary_dict()
        assert summary["file_count"] == 1
        assert summary["components"] == ["directory"]
        assert summary["years"] == ["2018-19"]
