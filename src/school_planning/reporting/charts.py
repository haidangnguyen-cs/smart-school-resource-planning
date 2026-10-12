"""charts.py - Static visualization generators for executive and technical deliverables.

Generates high-resolution publication-quality charts for:
  - Longitudinal enrollment and staffing trends
  - Student-teacher ratio distribution by school level
  - Multi-tier resource pressure classification distribution
  - Walk-forward backtest model error comparison (WAPE)
  - Retrospective 2023-24 enrollment projection scenarios with policy staffing bands
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for headless and script environments
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Clean modern styling constants
PALETTE = {
    "primary": "#1E3A8A",  # Deep blue
    "secondary": "#0D9488",  # Teal
    "accent": "#4F46E5",  # Indigo
    "warning": "#D97706",  # Amber
    "danger": "#E11D48",  # Rose / Red
    "neutral": "#64748B",  # Slate
    "light_bg": "#F8FAFC",  # Slate 50
    "dark_text": "#0F172A",  # Slate 900
    "grid": "#E2E8F0",  # Slate 200
}

TIER_COLORS = {
    1: "#E11D48",  # Rose - Admin review / missing data
    2: "#EA580C",  # Orange - Extreme pressure P90
    3: "#D97706",  # Amber - Rapid ratio escalation
    4: "#CA8A04",  # Yellow-Amber - Growth gap
    5: "#94A3B8",  # Slate - Unassessed growth
    6: "#0D9488",  # Teal - Stable / balanced
}


def _apply_figure_styling(ax: plt.Axes, title: str, xlabel: str = "", ylabel: str = "") -> None:
    """Apply consistent modern typography and grid styling to a Matplotlib axes."""
    ax.set_facecolor(PALETTE["light_bg"])
    ax.grid(True, linestyle="--", alpha=0.5, color=PALETTE["grid"], zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(PALETTE["neutral"])
    ax.spines["bottom"].set_color(PALETTE["neutral"])
    ax.tick_params(colors=PALETTE["dark_text"], labelsize=10)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color=PALETTE["dark_text"], pad=12)
    if xlabel:
        ax.set_xlabel(
            xlabel, fontsize=10, fontweight="bold", color=PALETTE["dark_text"], labelpad=8
        )
    if ylabel:
        ax.set_ylabel(
            ylabel, fontsize=10, fontweight="bold", color=PALETTE["dark_text"], labelpad=8
        )


def plot_longitudinal_trends(
    panel_df: pd.DataFrame,
    output_path: Path | str | None = None,
) -> plt.Figure:
    """Generate dual-axis line chart of national enrollment, teacher FTE, and weighted ratio over time.

    Args:
        panel_df: Longitudinal analytical panel or state annual aggregates.
        output_path: Optional path to save the generated PNG.

    Returns:
        Matplotlib Figure object.
    """
    df = panel_df.copy()
    if "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]

    # Group by school_year
    grouped = (
        df.groupby("school_year")
        .agg(
            {
                "total_students": "sum",
                "teacher_fte": "sum",
            }
        )
        .reset_index()
    )

    grouped["weighted_ratio"] = grouped.apply(
        lambda r: r["total_students"] / r["teacher_fte"] if r["teacher_fte"] > 0 else np.nan,
        axis=1,
    )

    fig, ax1 = plt.subplots(figsize=(10, 5.5), facecolor="white")
    _apply_figure_styling(
        ax1,
        title="National Public School Enrollment, Teacher FTE, and Ratio Trends (2018–19 to 2022–23)",
        xlabel="School Year",
        ylabel="Total Count (Millions)",
    )

    x = np.arange(len(grouped))
    years = grouped["school_year"].tolist()

    # Millions scaling
    students_millions = grouped["total_students"] / 1e6
    teachers_millions = grouped["teacher_fte"] / 1e6

    line1 = ax1.plot(
        x,
        students_millions,
        marker="o",
        linewidth=2.5,
        color=PALETTE["primary"],
        label="Student Enrollment (M)",
        zorder=3,
    )
    line2 = ax1.plot(
        x,
        teachers_millions,
        marker="s",
        linewidth=2.5,
        color=PALETTE["secondary"],
        label="Teacher FTE (M)",
        zorder=3,
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels(years)
    ax1.set_ylim(bottom=0, top=max(students_millions.max() * 1.15, 60))

    # Annotate values
    for i, (sm, tm) in enumerate(zip(students_millions, teachers_millions, strict=False)):
        ax1.annotate(
            f"{sm:.2f}M",
            (x[i], sm),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=PALETTE["primary"],
        )
        ax1.annotate(
            f"{tm:.2f}M",
            (x[i], tm),
            textcoords="offset points",
            xytext=(0, -14),
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=PALETTE["secondary"],
        )

    # Secondary axis for weighted ratio
    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["right"].set_color(PALETTE["danger"])
    line3 = ax2.plot(
        x,
        grouped["weighted_ratio"],
        marker="^",
        linewidth=2.0,
        linestyle="--",
        color=PALETTE["danger"],
        label="Weighted Student/Teacher Ratio",
        zorder=4,
    )
    ax2.set_ylabel(
        "Student-to-Teacher Ratio",
        color=PALETTE["danger"],
        fontsize=10,
        fontweight="bold",
        labelpad=8,
    )
    ax2.tick_params(colors=PALETTE["danger"], labelsize=10)
    ax2.set_ylim(bottom=10, top=22)

    for i, r in enumerate(grouped["weighted_ratio"]):
        if not np.isnan(r):
            ax2.annotate(
                f"{r:.1f}:1",
                (x[i], r),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=9,
                fontweight="bold",
                color=PALETTE["danger"],
            )

    # Combined legend
    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", framealpha=0.9, facecolor="white")

    plt.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return fig


def plot_ratio_distribution(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    output_path: Path | str | None = None,
) -> plt.Figure:
    """Generate boxplot comparing student-to-teacher ratio distributions across school levels.

    Args:
        panel_df: Analytical school panel.
        school_year: Target school year.
        output_path: Optional path to save chart.

    Returns:
        Matplotlib Figure object.
    """
    df = panel_df[panel_df["school_year"] == school_year].copy()
    if "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]

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

    # Filter to reasonable positive ratios (< 50) for readable boxplot
    valid_df = df[
        (df["student_teacher_ratio"].notna())
        & (df["student_teacher_ratio"] > 0)
        & (df["student_teacher_ratio"] <= 50)
    ].copy()

    level_order = ["Primary", "Middle", "High", "Other"]
    valid_df = valid_df[valid_df["school_level"].isin(level_order)]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    _apply_figure_styling(
        ax,
        title=f"Student-to-Teacher Ratio Distribution by School Level ({school_year})",
        xlabel="School Level",
        ylabel="Student-to-Teacher Ratio (Capped at 50 for visualization)",
    )

    data_to_plot = [
        valid_df[valid_df["school_level"] == lvl]["student_teacher_ratio"].values
        for lvl in level_order
    ]

    box = ax.boxplot(
        data_to_plot,
        tick_labels=level_order,
        patch_artist=True,
        medianprops={"color": PALETTE["danger"], "linewidth": 2},
        whiskerprops={"color": PALETTE["neutral"], "linewidth": 1.2},
        capprops={"color": PALETTE["neutral"], "linewidth": 1.2},
        flierprops={"marker": ".", "markersize": 2, "alpha": 0.2, "color": PALETTE["neutral"]},
    )

    colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["accent"], PALETTE["warning"]]
    for patch, color in zip(box["boxes"], colors, strict=False):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)
        patch.set_edgecolor(PALETTE["dark_text"])

    # Annotate medians
    for i, data in enumerate(data_to_plot):
        if len(data) > 0:
            med = np.median(data)
            ax.text(
                i + 1,
                med + 0.8,
                f"Med: {med:.1f}",
                ha="center",
                fontsize=9,
                fontweight="bold",
                color=PALETTE["dark_text"],
            )

    plt.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return fig


def plot_resource_pressure_tiers(
    panel_df: pd.DataFrame,
    school_year: str = "2022-23",
    output_path: Path | str | None = None,
) -> plt.Figure:
    """Generate horizontal bar chart displaying resource pressure triage tier counts and operational percentages.

    Args:
        panel_df: Panel with priority_tier or resource_pressure_priority column.
        school_year: Target school year.
        output_path: Optional path to save chart.

    Returns:
        Matplotlib Figure object.
    """
    df = panel_df[panel_df["school_year"] == school_year].copy()
    if "is_operational" in df.columns:
        df = df[df["is_operational"].fillna(False).astype(bool)]

    total_op = len(df)
    tier_col = (
        "resource_pressure_priority"
        if "resource_pressure_priority" in df.columns
        else ("priority_tier" if "priority_tier" in df.columns else None)
    )
    tier_counts = df[tier_col].value_counts().to_dict() if tier_col else {}

    tier_labels = [
        "Priority 1: Administrative Review\n(Missing FTE / Boundary Changed)",
        "Priority 2: Extreme Pressure\n(Peers ≥ P90 Ratio)",
        "Priority 3: Rapid Ratio Rise\n(Δ Ratio ≥ +15%)",
        "Priority 4: Divergent Growth Gap\n(Enrollment - Staffing ≥ +5 pp)",
        "Priority 5: Unassessed Growth\n(New School / Missing Prior Baseline)",
        "Priority 6: Stable / Balanced\n(Within Baseline Bounds)",
    ]

    counts = [tier_counts.get(i, 0) for i in range(1, 7)]
    pcts = [(c / total_op * 100.0) if total_op > 0 else 0.0 for c in counts]
    colors = [TIER_COLORS[i] for i in range(1, 7)]

    # Reverse order for top-to-bottom Priority 1 -> 6 display
    tier_labels.reverse()
    counts.reverse()
    pcts.reverse()
    colors.reverse()

    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="white")
    _apply_figure_styling(
        ax,
        title=f"Multi-Tier Resource Pressure Triage Distribution ({school_year}, N={total_op:,} Operational Schools)",
        xlabel="Number of Operational Schools",
        ylabel="",
    )

    y_pos = np.arange(len(tier_labels))
    bars = ax.barh(
        y_pos,
        counts,
        color=colors,
        alpha=0.85,
        edgecolor=PALETTE["dark_text"],
        height=0.65,
        zorder=3,
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(tier_labels, fontsize=9.5)
    ax.set_xlim(0, max(counts) * 1.18 if max(counts) > 0 else 100)

    for bar, cnt, pct in zip(bars, counts, pcts, strict=False):
        width = bar.get_width()
        ax.text(
            width + (max(counts) * 0.015),
            bar.get_y() + bar.get_height() / 2,
            f"{cnt:,} ({pct:.1f}%)",
            va="center",
            ha="left",
            fontsize=9.5,
            fontweight="bold",
            color=PALETTE["dark_text"],
        )

    plt.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return fig


def plot_backtest_model_comparison(
    summary_df: pd.DataFrame,
    output_path: Path | str | None = None,
) -> plt.Figure:
    """Generate bar chart comparing WAPE (Weighted Absolute Percentage Error) across forecasting models and folds.

    Args:
        summary_df: Summary DataFrame produced by backtesting.
        output_path: Optional path to save chart.

    Returns:
        Matplotlib Figure object.
    """
    df = summary_df.copy()
    # Filter to total_students target
    df_students = df[df["target_col"] == "total_students"].copy()
    if df_students.empty:
        df_students = df.copy()

    model_display_names = {
        "naive_persistence": "Naive (y_t)",
        "drift": "Drift (Trend)",
        "moving_average_3yr": "3-Yr Moving Avg",
    }
    df_students["model_short"] = (
        df_students["model_name"].map(model_display_names).fillna(df_students["model_name"])
    )

    folds = sorted(df_students["fold_id"].unique())
    models = ["naive_persistence", "drift", "moving_average_3yr"]
    models_present = [m for m in models if m in df_students["model_name"].unique()]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    _apply_figure_styling(
        ax,
        title="Walk-Forward Backtesting Error by Model and Test Fold (Target: Total Enrollment)",
        xlabel="Backtest Evaluation Fold (Test Year)",
        ylabel="Weighted Absolute Percentage Error (WAPE %)",
    )

    x = np.arange(len(folds))
    bar_width = 0.25
    color_map = {
        "naive_persistence": PALETTE["primary"],
        "drift": PALETTE["secondary"],
        "moving_average_3yr": PALETTE["warning"],
    }

    for i, m in enumerate(models_present):
        m_vals = []
        for f in folds:
            row = df_students[(df_students["fold_id"] == f) & (df_students["model_name"] == m)]
            m_vals.append(row["wape"].values[0] if not row.empty else 0.0)

        offset = (i - (len(models_present) - 1) / 2) * bar_width
        bars = ax.bar(
            x + offset,
            m_vals,
            width=bar_width,
            label=model_display_names.get(m, m),
            color=color_map.get(m, PALETTE["accent"]),
            alpha=0.85,
            edgecolor=PALETTE["dark_text"],
            zorder=3,
        )

        for bar, val in zip(bars, m_vals, strict=False):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.1,
                    f"{val:.2f}%",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    fontweight="bold",
                )

    ax.set_xticks(x)
    fold_labels = []
    for f in folds:
        sub = df_students[df_students["fold_id"] == f]
        t_yr = sub["test_year"].iloc[0] if "test_year" in sub.columns and not sub.empty else ""
        if f == "overall_pooled":
            fold_labels.append("Pooled\n(All Folds)")
        elif t_yr:
            fold_labels.append(f"{str(f).replace('_', ' ').title()}\n({t_yr})")
        else:
            fold_labels.append(str(f).replace("_", " ").title())
    ax.set_xticklabels(fold_labels)
    ax.set_ylim(0, max(df_students["wape"].max() * 1.25, 4.0))
    ax.legend(loc="upper right", framealpha=0.9, facecolor="white")

    plt.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return fig


def plot_projection_scenarios(
    projections_df: pd.DataFrame,
    top_n: int = 10,
    output_path: Path | str | None = None,
) -> plt.Figure:
    """Generate scenario fan/error-bar plot of retrospective 2023-24 projections for top states.

    Args:
        projections_df: DataFrame from generate_projection_scenarios().
        top_n: Number of largest states to plot.
        output_path: Optional path to save chart.

    Returns:
        Matplotlib Figure object.
    """
    df = projections_df.copy()
    if "is_latest_year_valid" in df.columns:
        df = df[df["is_latest_year_valid"]].copy()

    df = df.sort_values("baseline_projection", ascending=False).head(top_n).copy()
    df = df.iloc[::-1].copy()  # Reverse for horizontal plot

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="white")
    _apply_figure_styling(
        ax,
        title=f"Retrospective 2023–24 Enrollment Projections & Scenario Bands (Top {top_n} Jurisdictions)",
        xlabel="Projected Student Enrollment (Millions)",
        ylabel="",
    )

    y_pos = np.arange(len(df))
    labels = df["state_name"].tolist() if "state_name" in df.columns else df["state_fips"].tolist()

    baseline_m = df["baseline_projection"].values / 1e6
    low_m = df["scenario_low_contraction_minus_2pct"].values / 1e6
    high_m = df["scenario_high_expansion_plus_2pct"].values / 1e6
    hist_m = df["latest_historical_value"].values / 1e6

    # Plot scenario intervals
    for y, low, high, base, hist in zip(y_pos, low_m, high_m, baseline_m, hist_m, strict=False):
        ax.plot([low, high], [y, y], color=PALETTE["secondary"], linewidth=3.5, alpha=0.5, zorder=2)
        ax.scatter(
            hist,
            y,
            color=PALETTE["neutral"],
            s=45,
            marker="|",
            linewidths=2.5,
            zorder=3,
            label="2022-23 Actual" if y == 0 else "",
        )
        ax.scatter(
            base,
            y,
            color=PALETTE["primary"],
            s=60,
            marker="o",
            zorder=4,
            label="Baseline Proj" if y == 0 else "",
        )
        ax.scatter(
            low,
            y,
            color=PALETTE["warning"],
            s=30,
            marker="<",
            zorder=4,
            label="Low (-2%)" if y == 0 else "",
        )
        ax.scatter(
            high,
            y,
            color=PALETTE["danger"],
            s=30,
            marker=">",
            zorder=4,
            label="High (+2%)" if y == 0 else "",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.legend(loc="lower right", framealpha=0.9, facecolor="white")

    plt.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return fig


def save_figure(fig: plt.Figure, filepath: Path | str, dpi: int = 200) -> None:
    """Save a Matplotlib figure ensuring parent directories exist and memory is freed.

    Args:
        fig: Matplotlib Figure.
        filepath: Destination path.
        dpi: Output resolution.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
