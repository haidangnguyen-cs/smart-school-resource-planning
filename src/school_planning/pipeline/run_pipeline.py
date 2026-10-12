"""run_pipeline.py - Central pipeline runner and stage orchestrator.

Coordinates execution across:
  Stage 1: Audit sources and manifests
  Stage 2: Normalize identifiers and data schemas
  Stage 3: Build analytical school-year panel
  Stage 4: Run exploratory data analysis and resource pressure triage
  Stage 5: Run forecasting feasibility, backtesting, and scenarios
  Stage 6: Generate figures, deliverables, and report summaries
"""

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("school_planning.pipeline")

PIPELINE_STAGES = [
    {
        "stage_id": 1,
        "name": "Audit Sources",
        "script": "scripts/01_audit_sources.py",
        "description": "Inspect raw inputs, verify schemas, generate source manifest and audit logs",
    },
    {
        "stage_id": 2,
        "name": "Normalize Data",
        "script": "scripts/02_normalize_data.py",
        "description": "Normalize identifiers, types, missing values, and handle negative NCES codes",
    },
    {
        "stage_id": 3,
        "name": "Build Panel",
        "script": "scripts/03_build_panel.py",
        "description": "Join directory, membership, and staff into school-year analytical panel",
    },
    {
        "stage_id": 4,
        "name": "Run Analytics & Triage",
        "script": "scripts/04_run_analytics.py",
        "description": "Calculate system KPIs, segmentations, and six-tier resource pressure classification",
    },
    {
        "stage_id": 5,
        "name": "Run Forecasting",
        "script": "scripts/05_run_forecasting.py",
        "description": "Perform walk-forward backtesting, model comparison, and 2023-24 scenarios",
    },
    {
        "stage_id": 6,
        "name": "Generate Deliverables",
        "script": "scripts/06_generate_deliverables.py",
        "description": "Produce publication figures and compile executive & technical deliverables",
    },
]


def run_pipeline(
    start_stage: int = 1,
    end_stage: int = 6,
    base_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Execute pipeline stages sequentially from start_stage to end_stage.

    Args:
        start_stage: First stage index to run (1-6).
        end_stage: Last stage index to run (1-6).
        base_dir: Project root directory (default: current working directory).

    Returns:
        Summary dictionary with stage execution statuses and timings.
    """
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    results: list[dict[str, Any]] = []
    overall_start = time.perf_counter()

    for stage in PIPELINE_STAGES:
        s_id = stage["stage_id"]
        if s_id < start_stage or s_id > end_stage:
            continue

        script_path = root / stage["script"]
        logger.info(f"--- [Stage {s_id}] {stage['name']} ---")
        t0 = time.perf_counter()

        if not script_path.exists():
            error_msg = f"Script not found: {script_path}"
            logger.error(error_msg)
            results.append(
                {
                    "stage_id": s_id,
                    "name": stage["name"],
                    "status": "FAILED",
                    "error": error_msg,
                    "elapsed_seconds": 0.0,
                }
            )
            return {
                "success": False,
                "failed_stage": s_id,
                "stages": results,
                "total_elapsed_seconds": round(time.perf_counter() - overall_start, 2),
            }

        cmd = [sys.executable, str(script_path)]
        proc = subprocess.run(cmd, check=False, cwd=root, capture_output=True, text=True)
        elapsed = round(time.perf_counter() - t0, 2)

        if proc.returncode != 0:
            logger.error(f"Stage {s_id} failed with exit code {proc.returncode}:\n{proc.stderr}")
            results.append(
                {
                    "stage_id": s_id,
                    "name": stage["name"],
                    "status": "FAILED",
                    "returncode": proc.returncode,
                    "stderr": proc.stderr[-2000:] if proc.stderr else "",
                    "elapsed_seconds": elapsed,
                }
            )
            return {
                "success": False,
                "failed_stage": s_id,
                "stages": results,
                "total_elapsed_seconds": round(time.perf_counter() - overall_start, 2),
            }

        logger.info(f"Stage {s_id} completed successfully in {elapsed}s.")
        results.append(
            {
                "stage_id": s_id,
                "name": stage["name"],
                "status": "SUCCESS",
                "returncode": 0,
                "elapsed_seconds": elapsed,
            }
        )

    return {
        "success": True,
        "failed_stage": None,
        "stages": results,
        "total_elapsed_seconds": round(time.perf_counter() - overall_start, 2),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    res = run_pipeline()
    sys.exit(0 if res["success"] else 1)
