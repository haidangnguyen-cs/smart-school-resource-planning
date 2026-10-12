"""charts.py - Interactive chart renderers for the Streamlit decision-support dashboard."""

import numpy as np
import pandas as pd
import streamlit as st

# Clean color palette
PALETTE = {
    "primary": "#1E3A8A",  # Deep blue
    "secondary": "#0D9488",  # Teal
    "accent": "#4F46E5",  # Indigo
    "warning": "#D97706",  # Amber
    "danger": "#E11D48",  # Rose
    "neutral": "#64748B",  # Slate
    "light_bg": "#F8FAFC",  # Slate 50
    "dark_text": "#0F172A",  # Slate 900
}

TIER_COLORS = {
    1: "#E11D48",  # Rose - Priority 1 Admin Review
    2: "#EA580C",  # Orange - Priority 2 Extreme P90
    3: "#D97706",  # Amber - Priority 3 Rapid Rise
    4: "#CA8A04",  # Yellow-Amber - Priority 4 Growth Gap
    5: "#94A3B8",  # Slate - Priority 5 Unassessed
    6: "#0D9488",  # Teal - Priority 6 Stable / Balanced
}


def render_longitudinal_trend_chart(
    panel_df: pd.DataFrame,
    operational_only: bool | None = None,
) -> None:
    """Render dual-metric line chart showing national enrollment and staffing trajectory."""
    df = panel_df.copy()
    if operational_only is True and "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]
    elif operational_only is False:
        pass
    # If operational_only is None, preserve panel_df as provided by caller

    agg = (
        df.groupby("school_year")
        .agg(
            {
                "total_students": lambda s: s.sum(min_count=1),
                "teacher_fte": lambda s: s.sum(min_count=1),
            }
        )
        .reset_index()
    )

    agg["total_students_m"] = agg["total_students"] / 1e6
    agg["teacher_fte_m"] = agg["teacher_fte"] / 1e6
    agg["weighted_ratio"] = agg.apply(
        lambda r: (
            r["total_students"] / r["teacher_fte"]
            if pd.notna(r["total_students"]) and pd.notna(r["teacher_fte"]) and r["teacher_fte"] > 0
            else np.nan
        ),
        axis=1,
    )

    chart_data = agg.set_index("school_year")[["total_students_m", "teacher_fte_m"]]
    chart_data.columns = ["Students (Millions)", "Teachers FTE (Millions)"]

    st.line_chart(chart_data, color=["#1E3A8A", "#0D9488"], height=320)

    # Ratio trend metrics below chart
    cols = st.columns(len(agg))
    for i, (_, row) in enumerate(agg.iterrows()):
        with cols[i]:
            st.metric(
                label=f"{row['school_year']} Ratio",
                value=f"{row['weighted_ratio']:.2f}:1"
                if not np.isnan(row["weighted_ratio"])
                else "—",
            )


def render_ratio_distribution_chart(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    operational_only: bool | None = None,
) -> None:
    """Render bar chart of median student-to-teacher ratio by school level."""
    df = panel_df.copy()
    if "school_year" in df.columns and school_year != "All Years":
        df = df[df["school_year"] == school_year]
    if operational_only is True and "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]
    elif operational_only is False:
        pass

    if "student_teacher_ratio" not in df.columns:
        df["student_teacher_ratio"] = df.apply(
            lambda r: (
                r["total_students"] / r["teacher_fte"]
                if pd.notna(r.get("teacher_fte"))
                and r.get("teacher_fte", 0) > 0
                and pd.notna(r.get("total_students"))
                and r.get("total_students", 0) >= 0
                else np.nan
            ),
            axis=1,
        )

    valid = df[
        (df["student_teacher_ratio"].notna())
        & (df["student_teacher_ratio"] > 0)
        & (df["student_teacher_ratio"] <= 60)
    ]

    if "school_level" in valid.columns:
        level_stats = (
            valid.groupby("school_level")["student_teacher_ratio"]
            .agg(
                Median="median",
                P25=lambda x: x.quantile(0.25),
                P75=lambda x: x.quantile(0.75),
                Schools="count",
            )
            .reset_index()
        )

        level_order = ["Primary", "Middle", "High", "Other"]
        level_stats["sort_key"] = level_stats["school_level"].map(
            lambda x: level_order.index(x) if x in level_order else 99
        )
        level_stats = level_stats.sort_values("sort_key").drop(columns=["sort_key"])

        st.bar_chart(
            level_stats.set_index("school_level")["Median"],
            color="#4F46E5",
            height=280,
        )

        # Detailed summary table
        st.dataframe(
            level_stats.style.format(
                {
                    "Median": "{:.2f}",
                    "P25": "{:.2f}",
                    "P75": "{:.2f}",
                    "Schools": "{:,}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_triage_tier_donut(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    operational_only: bool | None = None,
) -> None:
    """Render horizontal bar chart of the 6 Priority Resource Pressure Tiers.

    Priority tiers are strictly evaluated on the documented operational cohort.
    """
    df = panel_df.copy()
    if "school_year" in df.columns and school_year != "All Years":
        df = df[df["school_year"] == school_year]
    # Priority tiers are defined strictly on the operational cohort:
    if "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]

    tier_col = (
        "resource_pressure_priority"
        if "resource_pressure_priority" in df.columns
        else ("priority_tier" if "priority_tier" in df.columns else None)
    )

    total_op = len(df)
    tier_counts = df[tier_col].value_counts().to_dict() if tier_col else {}

    tier_labels = {
        1: "Priority 1: Administrative Review",
        2: "Priority 2: Extreme Pressure (P90)",
        3: "Priority 3: Rapid Ratio Rise",
        4: "Priority 4: Growth Gap",
        5: "Priority 5: Unassessed Growth",
        6: "Priority 6: Stable / Balanced",
    }

    tier_data = []
    for t in range(1, 7):
        cnt = tier_counts.get(t, 0)
        pct = (cnt / total_op * 100.0) if total_op > 0 else 0.0
        tier_data.append(
            {
                "Tier": tier_labels.get(t, f"Priority {t}"),
                "Schools": cnt,
                "Share (%)": round(pct, 2),
            }
        )

    tier_df = pd.DataFrame(tier_data)

    st.bar_chart(
        tier_df.set_index("Tier")["Schools"],
        color="#EA580C",
        height=300,
    )

    st.dataframe(
        tier_df.style.format(
            {
                "Schools": "{:,}",
                "Share (%)": "{:.2f}%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_backtest_error_chart(backtest_df: pd.DataFrame) -> None:
    """Render walk-forward backtest error comparison chart."""
    df = backtest_df.copy()
    df_students = df[df["target_col"] == "total_students"].copy()
    if df_students.empty:
        df_students = df.copy()

    model_display = {
        "naive_persistence": "Naive (Persistence)",
        "drift": "Linear Drift (Trend)",
        "moving_average_3yr": "3-Year Moving Average",
    }
    df_students["Model"] = (
        df_students["model_name"].map(model_display).fillna(df_students["model_name"])
    )

    # Pivot for clean display
    piv = df_students.pivot(index="fold_id", columns="Model", values="wape")
    st.bar_chart(piv, height=300)

    st.caption("WAPE (%) by fold across candidate enrollment forecasting models. Lower is better.")


def render_scenario_projection_chart(
    projections_df: pd.DataFrame,
    policy_target_ratio: float = 15.0,
    top_n: int = 10,
) -> None:
    """Render interactive scenario fan chart and implied staffing simulation."""
    df = projections_df.copy()
    if "is_latest_year_valid" in df.columns:
        df = df[df["is_latest_year_valid"]].copy()

    df = df.sort_values("baseline_projection", ascending=False).head(top_n).copy()

    # Dynamic calculation of implied staffing demand under user's policy ratio
    df["implied_fte_custom_target"] = (df["baseline_projection"] / policy_target_ratio).round(1)
    df["fte_gap_vs_actual"] = (
        df["implied_fte_custom_target"] - df["latest_historical_teacher_fte"]
    ).round(1)

    chart_cols = [
        "state_name",
        "latest_historical_value",
        "baseline_projection",
        "scenario_low_contraction_minus_2pct",
        "scenario_high_expansion_plus_2pct",
    ]
    present_cols = [c for c in chart_cols if c in df.columns]

    plot_df = df[present_cols].set_index("state_name")
    plot_df.columns = ["2022-23 Actual", "Baseline Proj", "Low (-2%)", "High (+2%)"]

    st.bar_chart(plot_df, height=340)

    st.markdown(f"#### 🎯 Implied Staffing Demand (Policy Target: **{policy_target_ratio:.1f}:1**)")
    disp_cols = [
        "state_fips",
        "state_name",
        "latest_historical_value",
        "baseline_projection",
        "latest_historical_teacher_fte",
        "implied_fte_custom_target",
        "fte_gap_vs_actual",
    ]
    disp_present = [c for c in disp_cols if c in df.columns]
    summary_table = df[disp_present].copy()

    st.dataframe(
        summary_table.style.format(
            {
                "latest_historical_value": "{:,.0f}",
                "baseline_projection": "{:,.0f}",
                "latest_historical_teacher_fte": "{:,.1f}",
                "implied_fte_custom_target": "{:,.1f}",
                "fte_gap_vs_actual": "{:+,.1f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
