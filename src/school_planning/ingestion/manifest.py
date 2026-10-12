"""Source file inventory, checksum verification, and manifest generator."""

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceFileEntry:
    component: str
    component_code: str
    school_year: str
    filename: str
    relative_path: str
    size_bytes: int
    size_mb: float
    column_count: int
    columns: list[str]
    sha256: str
    encoding_detected: str
    row_count: int | None = None


class SourceManifest:
    """Manages the inventory of raw source files and their integrity metadata."""

    def __init__(self, entries: list[SourceFileEntry] | None = None):
        self.entries = entries or []

    def add_entry(self, entry: SourceFileEntry) -> None:
        self.entries.append(entry)

    def to_dict(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.entries]

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "file_count": len(self.entries),
            "components": sorted({e.component for e in self.entries}),
            "years": sorted({e.school_year for e in self.entries}),
            "total_size_mb": round(sum(e.size_mb for e in self.entries), 2),
        }

    def save_json(self, destination: Path | str) -> None:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


def compute_sha256(filepath: Path | str, chunk_size: int = 65536) -> str:
    """Compute the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def inspect_file_header(filepath: Path | str) -> tuple[list[str], str]:
    """Read CSV header using deterministic encoding cascade."""
    from school_planning.ingestion.readers import determine_encoding

    path = Path(filepath)
    enc = determine_encoding(path)
    with open(path, "r", encoding=enc) as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, enc


def build_source_manifest(
    project_root: Path | str,
    sources_cfg_path: Path | str | None = None,
    compute_hashes: bool = True,
    count_rows_fast: bool = False,
) -> SourceManifest:
    """Build a complete source manifest based on config/sources.yaml and actual files.

    Args:
        project_root: Root directory of the repository.
        sources_cfg_path: Path to config/sources.yaml.
        compute_hashes: Whether to compute full SHA-256 checksums.
        count_rows_fast: Whether to count rows by reading lines (may be slow on 2.3GB files).

    Returns:
        SourceManifest containing verified entries for all source files.
    """
    root = Path(project_root)
    if sources_cfg_path is None:
        sources_cfg_path = root / "config" / "sources.yaml"

    with open(sources_cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    manifest = SourceManifest()
    components = cfg.get("components", cfg.get("sources", {}).get("components", {}))

    for comp_name, comp_info in components.items():
        comp_code = comp_info.get("code", comp_info.get("component_code", ""))
        files_dict = comp_info.get("files", comp_info.get("years", {}))
        for year, file_info in files_dict.items():
            rel_path = file_info.get("path")
            full_path = root / rel_path
            filename = file_info.get("filename", full_path.name)

            if not full_path.exists():
                continue

            size_bytes = full_path.stat().st_size
            size_mb = round(size_bytes / (1024 * 1024), 2)
            header, enc = inspect_file_header(full_path)
            sha256_hash = compute_sha256(full_path) if compute_hashes else ""

            row_count = None
            if count_rows_fast:
                with open(full_path, "rb") as f:
                    row_count = sum(1 for _ in f) - 1

            entry = SourceFileEntry(
                component=comp_name,
                component_code=comp_code,
                school_year=year,
                filename=filename,
                relative_path=rel_path,
                size_bytes=size_bytes,
                size_mb=size_mb,
                column_count=len(header),
                columns=header,
                sha256=sha256_hash,
                encoding_detected=enc,
                row_count=row_count,
            )
            manifest.add_entry(entry)

    return manifest
