"""app.components - Reusable UI widgets and presentation modules for the Streamlit dashboard."""

from app.components.charts import (
    render_backtest_error_chart,
    render_longitudinal_trend_chart,
    render_ratio_distribution_chart,
    render_scenario_projection_chart,
    render_triage_tier_donut,
)
from app.components.filters import apply_filters, render_sidebar_filters
from app.components.kpi_cards import render_kpi_card, render_kpi_grid

__all__ = [
    "apply_filters",
    "render_backtest_error_chart",
    "render_kpi_card",
    "render_kpi_grid",
    "render_longitudinal_trend_chart",
    "render_ratio_distribution_chart",
    "render_scenario_projection_chart",
    "render_sidebar_filters",
    "render_triage_tier_donut",
]
