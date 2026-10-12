"""Ingestion subpackage for data loading and source adapters."""

from school_planning.ingestion.manifest import SourceManifest, build_source_manifest
from school_planning.ingestion.readers import determine_encoding, read_csv_robust, stream_csv_chunks
from school_planning.ingestion.source_adapters import (
    load_directory_component,
    load_membership_component,
    load_staff_component,
)

__all__ = [
    "SourceManifest",
    "build_source_manifest",
    "determine_encoding",
    "load_directory_component",
    "load_membership_component",
    "load_staff_component",
    "read_csv_robust",
    "stream_csv_chunks",
]
