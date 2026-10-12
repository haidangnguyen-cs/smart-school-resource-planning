"""06_generate_deliverables.py - Pipeline execution script for reports and figures.

Loads analytical processed datasets, generates static high-resolution figures in
outputs/figures/, and compiles markdown deliverable documents in deliverables/.
"""

import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from school_planning.reporting.charts import (
    plot_backtest_model_comparison,
    plot_longitudinal_trends,
    plot_projection_scenarios,
    plot_ratio_distribution,
    plot_resource_pressure_tiers,
    save_figure,
)
from school_planning.reporting.generate_report import generate_all_deliverables

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_deliverables")


def main() -> int:
    start_time = time.perf_counter()
    root_dir = Path.cwd()

    aug_path = root_dir / "data" / "processed" / "school_year_panel_augmented.parquet"
    panel_path = (
        aug_path
        if aug_path.exists()
        else (root_dir / "data" / "processed" / "school_year_panel.parquet")
    )
    if not panel_path.exists():
        logger.error(f"Required processed panel not found at {panel_path}")
        return 1

    logger.info(f"Loading processed school-year panel from {panel_path}...")
    panel_df = pd.read_parquet(panel_path)
    logger.info(f"Loaded panel: {len(panel_df):,} rows, {len(panel_df.columns)} columns.")

    # State summary
    state_agg_path = root_dir / "outputs" / "tables" / "state_annual_aggregates.csv"
    if state_agg_path.exists():
        state_df = pd.read_csv(state_agg_path, dtype={"state_fips": str})
    else:
        state_df = panel_df

    # Backtest summary
    backtest_path = root_dir / "outputs" / "tables" / "backtest_model_comparison.csv"
    backtest_df = pd.read_csv(backtest_path) if backtest_path.exists() else None

    # Projections
    proj_path = root_dir / "outputs" / "tables" / "retrospective_2023_24_projections.csv"
    proj_df = pd.read_csv(proj_path, dtype={"state_fips": str}) if proj_path.exists() else None

    # Evaluation report JSON
    eval_path = root_dir / "outputs" / "reports" / "forecasting_evaluation_report.json"
    eval_report = json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.exists() else None

    # 1. Generate Figures
    fig_dir = root_dir / "outputs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Generating static figures in {fig_dir}...")

    # Longitudinal trends
    fig1 = plot_longitudinal_trends(panel_df)
    f1_path = fig_dir / "longitudinal_trends.png"
    save_figure(fig1, f1_path)
    logger.info(f"Saved: {f1_path.name} ({f1_path.stat().st_size:,} bytes)")

    # Ratio distribution
    fig2 = plot_ratio_distribution(panel_df, school_year="2022-23")
    f2_path = fig_dir / "ratio_distribution.png"
    save_figure(fig2, f2_path)
    logger.info(f"Saved: {f2_path.name} ({f2_path.stat().st_size:,} bytes)")

    # Resource pressure tiers
    fig3 = plot_resource_pressure_tiers(panel_df, school_year="2022-23")
    f3_path = fig_dir / "resource_pressure_tiers.png"
    save_figure(fig3, f3_path)
    logger.info(f"Saved: {f3_path.name} ({f3_path.stat().st_size:,} bytes)")

    # Backtest comparison
    if backtest_df is not None:
        fig4 = plot_backtest_model_comparison(backtest_df)
        f4_path = fig_dir / "backtest_model_comparison.png"
        save_figure(fig4, f4_path)
        logger.info(f"Saved: {f4_path.name} ({f4_path.stat().st_size:,} bytes)")

    # Projections
    if proj_df is not None:
        fig5 = plot_projection_scenarios(proj_df, top_n=10)
        f5_path = fig_dir / "retrospective_scenario_projections.png"
        save_figure(fig5, f5_path)
        logger.info(f"Saved: {f5_path.name} ({f5_path.stat().st_size:,} bytes)")

    # 2. Generate Deliverable Markdown Documents
    deliv_dir = root_dir / "deliverables"
    deliv_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Compiling deliverable documents in {deliv_dir}...")

    files_written = generate_all_deliverables(
        panel_df=panel_df,
        state_summary_df=state_df,
        backtest_df=backtest_df,
        projections_df=proj_df,
        evaluation_report=eval_report,
        output_dir=deliv_dir,
    )

    for name, path in files_written.items():
        logger.info(f"Deliverable compiled: {name} -> {path.name} ({path.stat().st_size:,} bytes)")

    elapsed = round(time.perf_counter() - start_time, 2)
    logger.info(f"All deliverables and figures generated successfully in {elapsed}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
