#!/usr/bin/env python3
"""02_normalize_data.py - Normalize NCES CCD raw source components into interim Parquet files.

Extracts, cleans, and standardizes Directory (029), Membership (052), and Staff (059)
for all 5 school years, saving normalized extracts to data/interim/normalized/.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from school_planning.transformation.directory import transform_directory
from school_planning.transformation.membership import transform_membership
from school_planning.transformation.staff import transform_staff

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("02_normalize_data")


def load_sources_config(config_path: Path | None = None) -> dict:
    """Load sources.yaml configuration."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "sources.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_all_sources(
    project_root: Path = PROJECT_ROOT,
    years: list[str] | None = None,
    components: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, list[str]]:
    """Normalize source files across years and components.

    Args:
        project_root: Root directory of the repository.
        years: List of school years to process.
        components: List of components to process ('directory', 'membership', 'staff').
        output_dir: Destination directory for normalized interim Parquet files.

    Returns:
        Dictionary mapping component to list of generated Parquet file paths.
    """
    sources_cfg = load_sources_config(project_root / "config" / "sources.yaml")
    cfg_components = sources_cfg.get("components", {})

    if output_dir is None:
        output_dir = project_root / "data" / "interim" / "normalized"
    output_dir.mkdir(parents=True, exist_ok=True)

    if years is None:
        years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]

    if components is None:
        components = ["directory", "staff", "membership"]

    generated_files: dict[str, list[str]] = {comp: [] for comp in components}

    for comp in components:
        comp_info = cfg_components.get(comp, {})
        files_map = comp_info.get("files", {})

        for yr in years:
            file_meta = files_map.get(yr)
            if not file_meta:
                logger.warning("No file metadata found for %s (%s)", comp, yr)
                continue

            rel_path = file_meta.get("path")
            src_path = project_root / rel_path
            if not src_path.exists():
                logger.error("Source file does not exist: %s", src_path)
                continue

            logger.info("Normalizing %s for %s from %s...", comp, yr, src_path.name)
            start_t = time.time()

            if comp == "directory":
                clean_df = transform_directory(src_path)
            elif comp == "staff":
                clean_df = transform_staff(src_path)
            elif comp == "membership":
                clean_df = transform_membership(src_path)
            else:
                logger.warning("Unknown component: %s", comp)
                continue

            year_slug = yr.replace("-", "_")
            out_file = output_dir / f"{comp}_{year_slug}.parquet"
            clean_df.to_parquet(out_file, engine="pyarrow", index=False)

            elapsed = time.time() - start_t
            logger.info(
                "Saved %s (%d rows) to %s in %.2fs",
                comp,
                len(clean_df),
                out_file.name,
                elapsed,
            )
            generated_files[comp].append(str(out_file))

    return generated_files


def main():
    """CLI entry point for 02_normalize_data.py."""
    parser = argparse.ArgumentParser(description="Normalize NCES CCD sources into interim Parquet files.")
    parser.add_argument("--years", nargs="+", help="Specific school years to process (e.g. 2018-19).")
    parser.add_argument("--components", nargs="+", help="Specific components (directory, membership, staff).")
    parser.add_argument("--output-dir", type=Path, help="Custom output directory.")
    args = parser.parse_args()

    normalize_all_sources(
        years=args.years,
        components=args.components,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
