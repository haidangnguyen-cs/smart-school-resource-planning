"""school_planning.reporting - Formatting, static visualization, and deliverable reporting modules."""

from school_planning.reporting.charts import (
    plot_backtest_model_comparison,
    plot_longitudinal_trends,
    plot_projection_scenarios,
    plot_ratio_distribution,
    plot_resource_pressure_tiers,
    save_figure,
)
from school_planning.reporting.generate_report import (
    generate_all_deliverables,
    generate_executive_summary,
    generate_presentation_outline,
    generate_recommendations,
    generate_technical_report,
)
from school_planning.reporting.tables import (
    dataframe_to_markdown,
    format_backtest_comparison_table,
    format_kpi_summary_table,
    format_projection_scenario_table,
    format_resource_pressure_tier_table,
    format_state_summary_table,
)

__all__ = [
    "dataframe_to_markdown",
    "format_backtest_comparison_table",
    "format_kpi_summary_table",
    "format_projection_scenario_table",
    "format_resource_pressure_tier_table",
    "format_state_summary_table",
    "generate_all_deliverables",
    "generate_executive_summary",
    "generate_presentation_outline",
    "generate_recommendations",
    "generate_technical_report",
    "plot_backtest_model_comparison",
    "plot_longitudinal_trends",
    "plot_projection_scenarios",
    "plot_ratio_distribution",
    "plot_resource_pressure_tiers",
    "save_figure",
]
