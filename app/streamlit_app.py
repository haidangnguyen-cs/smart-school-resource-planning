"""streamlit_app.py - Decision-Support Dashboard for Smart School Resource Planning.

Multi-tab interactive dashboard providing:
  Tab 1: 📊 System Overview (Longitudinal Trends & National KPIs)
  Tab 2: 🗺️ Geographic Analysis (State Rankings & Disparities)
  Tab 3: 🚨 Resource Pressure Triage (Priority 1–6 Waterfall & Queues)
  Tab 4: 🔍 Data Quality & Caveats (Reporting Completeness, Missingness, Structural Breaks)
  Tab 5: 📈 Forecasting & Scenarios (Feasibility Assessment, Walk-Forward Backtesting, Policy Staffing Slider)
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from app.components.charts import (
    render_backtest_error_chart,
    render_longitudinal_trend_chart,
    render_ratio_distribution_chart,
    render_scenario_projection_chart,
    render_triage_tier_donut,
)
from app.components.filters import apply_filters, render_sidebar_filters
from app.components.kpi_cards import render_kpi_grid

# -----------------------------------------------------------------------------
# Page Configuration & Rich Aesthetics CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart School Resource Planning",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Header Banner */
.main-header {
    background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%);
    color: white;
    padding: 24px 32px;
    border-radius: 16px;
    margin-bottom: 24px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}
.main-header h1 {
    font-size: 2.2rem;
    font-weight: 800;
    margin: 0;
    color: #F8FAFC;
    letter-spacing: -0.02em;
}
.main-header p {
    font-size: 1.05rem;
    color: #94A3B8;
    margin-top: 6px;
    margin-bottom: 0;
}

/* Badge tags */
.badge-tag {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-primary { background-color: #DBEAFE; color: #1E40AF; }
.badge-warning { background-color: #FEF3C7; color: #92400E; }
.badge-danger { background-color: #FEE2E2; color: #991B1B; }
.badge-success { background-color: #D1FAE5; color: #065F46; }

/* Clean table headers */
.stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Loading & Caching
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading analytical data panel...")
def load_data_panel() -> pd.DataFrame:
    """Load augmented analytical panel or fallback to base panel."""
    root = Path.cwd()
    aug_path = root / "data" / "processed" / "school_year_panel_augmented.parquet"
    base_path = root / "data" / "processed" / "school_year_panel.parquet"

    path = aug_path if aug_path.exists() else base_path
    if not path.exists():
        st.error(f"Data file not found at {path}. Please run pipeline scripts first.")
        return pd.DataFrame()

    df = pd.read_parquet(path)
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
    return df


@st.cache_data
def load_supplementary_data() -> dict[str, Any]:
    """Load backtesting results, scenario projections, and state aggregates."""
    root = Path.cwd()
    supp = {}

    bt_path = root / "outputs" / "tables" / "backtest_model_comparison.csv"
    supp["backtest"] = pd.read_csv(bt_path) if bt_path.exists() else None

    proj_path = root / "outputs" / "tables" / "retrospective_2023_24_projections.csv"
    supp["projections"] = (
        pd.read_csv(proj_path, dtype={"state_fips": str}) if proj_path.exists() else None
    )

    state_path = root / "outputs" / "tables" / "state_annual_aggregates.csv"
    supp["state_aggregates"] = (
        pd.read_csv(state_path, dtype={"state_fips": str}) if state_path.exists() else None
    )

    p1_path = root / "outputs" / "tables" / "resource_pressure_triage_queue_p1.csv"
    supp["p1_queue"] = (
        pd.read_csv(p1_path, dtype={"school_id": str, "state_fips": str})
        if p1_path.exists()
        else None
    )

    p2_path = root / "outputs" / "tables" / "resource_pressure_triage_queue_p2.csv"
    supp["p2_queue"] = (
        pd.read_csv(p2_path, dtype={"school_id": str, "state_fips": str})
        if p2_path.exists()
        else None
    )

    eval_path = root / "outputs" / "reports" / "forecasting_evaluation_report.json"
    supp["eval_report"] = (
        json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.exists() else None
    )

    return supp


# -----------------------------------------------------------------------------
# Main Application Flow
# -----------------------------------------------------------------------------
def main() -> None:
    # Header Banner
    st.markdown(
        """
        <div class="main-header">
            <h1>🎓 Smart School Resource Planning</h1>
            <p>Evidence-Based Decision Support & Resource Pressure Analytics across U.S. Public Schools (2018–19 to 2022–23)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_full = load_data_panel()
    if df_full.empty:
        st.stop()

    supp_data = load_supplementary_data()

    # Sidebar Filter Controls
    filters = render_sidebar_filters(df_full)
    non_year_cohort = apply_filters(df_full, filters, include_year=False)

    # Reference year determination for snapshot indicators
    selected_year = filters.get("school_year", "2022-23")
    is_all_years_mode = selected_year == "All Years"

    available_years = sorted(non_year_cohort["school_year"].dropna().unique().tolist())
    latest_available_year = available_years[-1] if available_years else "2022-23"
    ref_year = latest_available_year if is_all_years_mode else selected_year

    # Snapshot cohort for reference year with all non-year filters applied
    target_cohort = non_year_cohort[non_year_cohort["school_year"] == ref_year].copy()
    is_op_only = filters.get("operational_choice") == "Operational Only"

    # Tabs definition
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊 System Overview",
            "🗺️ Geographic Analysis",
            "🚨 Resource Pressure Triage",
            "🔍 Data Quality & Caveats",
            "📈 Forecasting & Scenarios",
        ]
    )

    # =========================================================================
    # TAB 1: System Overview
    # =========================================================================
    with tab1:
        st.markdown("### 📊 Macro Educational System Performance")
        if is_all_years_mode:
            st.caption(
                f"ℹ️ **Snapshot KPI Reference Period: {ref_year}** "
                f"(Latest available year used for snapshot cards; full 5-year longitudinal trajectory is displayed below)."
            )
        else:
            st.caption(f"**Reference School Year**: {ref_year}")

        # Compute dynamic macro metrics on target snapshot cohort using missing-aware aggregation
        op_mask = (
            target_cohort["is_operational"].fillna(False).astype(bool)
            if "is_operational" in target_cohort.columns
            else pd.Series(True, index=target_cohort.index)
        )
        operational_schools_count = int(op_mask.sum())
        total_facilities_count = len(target_cohort)

        raw_students = (
            target_cohort["total_students"].sum(min_count=1)
            if "total_students" in target_cohort.columns
            else np.nan
        )
        raw_teachers = (
            target_cohort["teacher_fte"].sum(min_count=1)
            if "teacher_fte" in target_cohort.columns
            else np.nan
        )
        total_students = float(raw_students) if pd.notna(raw_students) else np.nan
        total_teachers = float(raw_teachers) if pd.notna(raw_teachers) else np.nan
        weighted_ratio = (
            total_students / total_teachers
            if pd.notna(total_students) and pd.notna(total_teachers) and total_teachers > 0
            else np.nan
        )

        # Previous year for YoY comparisons using the SAME non-year cohort filters
        prev_students = None
        prev_teachers = None
        year_order = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        if ref_year in year_order and year_order.index(ref_year) > 0:
            prev_yr = year_order[year_order.index(ref_year) - 1]
            prev_yr_df = non_year_cohort[non_year_cohort["school_year"] == prev_yr]
            if not prev_yr_df.empty:
                raw_prev_s = (
                    prev_yr_df["total_students"].sum(min_count=1)
                    if "total_students" in prev_yr_df.columns
                    else np.nan
                )
                raw_prev_t = (
                    prev_yr_df["teacher_fte"].sum(min_count=1)
                    if "teacher_fte" in prev_yr_df.columns
                    else np.nan
                )
                prev_students = float(raw_prev_s) if pd.notna(raw_prev_s) else None
                prev_teachers = float(raw_prev_t) if pd.notna(raw_prev_t) else None

        school_title = "Operational Schools"
        school_subtitle = (
            f"{ref_year} Active reported facilities"
            if is_op_only
            else f"{ref_year} Active ({total_facilities_count:,} all facilities)"
        )

        render_kpi_grid(
            operational_schools=operational_schools_count,
            total_students=total_students,
            total_teachers=total_teachers,
            weighted_ratio=weighted_ratio,
            prev_students=prev_students,
            prev_teachers=prev_teachers,
            school_title=school_title,
            school_subtitle=school_subtitle,
            reference_year=ref_year,
        )

        st.markdown("---")

        col_left, col_right = st.columns([3, 2])
        with col_left:
            st.markdown("#### 📈 Longitudinal Enrollment & Staffing Trajectory")
            render_longitudinal_trend_chart(
                non_year_cohort,
                operational_only=is_op_only,
            )

        with col_right:
            st.markdown("#### 🎯 Ratio Distribution by School Level")
            render_ratio_distribution_chart(
                non_year_cohort,
                school_year=ref_year,
                operational_only=is_op_only,
            )

        st.markdown("---")
        st.markdown("#### 📋 Longitudinal System Performance Table")
        from school_planning.reporting.tables import format_kpi_summary_table

        kpi_table = format_kpi_summary_table(
            non_year_cohort,
            operational_only=is_op_only,
        )
        st.dataframe(
            kpi_table.style.format(
                {
                    "operational_schools": "{:,}",
                    "all_facilities": "{:,}",
                    "total_enrollment": "{:,.0f}",
                    "total_teacher_fte": "{:,.1f}",
                    "weighted_ratio": "{:.2f}",
                    "enrollment_yoy_growth_pct": "{:+.2f}%",
                    "teacher_yoy_growth_pct": "{:+.2f}%",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    # =========================================================================
    # TAB 2: Geographic Analysis
    # =========================================================================
    with tab2:
        st.markdown("### 🗺️ State & Regional Resource Disparities")

        from school_planning.reporting.tables import format_state_summary_table

        state_table = format_state_summary_table(
            non_year_cohort,
            school_year=ref_year,
            operational_only=is_op_only,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"#### State Rankings & Triage Summary ({ref_year})")
        with col2:
            sort_options = [
                "total_students",
                "student_teacher_ratio",
                "total_triage_flagged",
                "operational_schools",
            ]
            if "all_facilities" in state_table.columns and not is_op_only:
                sort_options.append("all_facilities")
            sort_by = st.selectbox(
                "Sort Table By",
                sort_options,
            )

        if state_table.empty:
            st.info("No state records match the selected filter criteria.")
        else:
            state_sorted = state_table.sort_values(
                sort_by, ascending=False, na_position="last"
            ).reset_index(drop=True)

            st.dataframe(
                state_sorted.style.format(
                    {
                        "operational_schools": "{:,}",
                        "all_facilities": "{:,}",
                        "total_students": "{:,.0f}",
                        "total_teacher_fte": "{:,.1f}",
                        "student_teacher_ratio": "{:.2f}",
                        "priority_1_review": "{:,}",
                        "priority_2_p90": "{:,}",
                        "priority_3_rising": "{:,}",
                        "priority_4_gap": "{:,}",
                        "total_triage_flagged": "{:,}",
                    },
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

            st.markdown("---")
            st.markdown("#### 🔍 State-Level Drill Down")

            # FIPS-based geographic identity with display name label
            fips_list = state_sorted["state_fips"].unique().tolist()
            fips_to_name = dict(
                zip(state_sorted["state_fips"], state_sorted["state_name"], strict=False)
            )

            selected_drill_fips = st.selectbox(
                "Select State / Jurisdiction for Deep-Dive Inspection",
                options=fips_list,
                format_func=lambda fips: f"{fips_to_name.get(fips, fips)} (FIPS: {fips})",
                index=0,
            )

            if selected_drill_fips:
                drill_df = target_cohort[
                    target_cohort["state_fips"].astype(str).str.zfill(2)
                    == str(selected_drill_fips).zfill(2)
                ]
                drill_op_mask = (
                    drill_df["is_operational"].fillna(False).astype(bool)
                    if "is_operational" in drill_df.columns
                    else pd.Series(True, index=drill_df.index)
                )
                drill_op_schools = int(drill_op_mask.sum())
                drill_all_facilities = len(drill_df)

                raw_drill_s = (
                    drill_df["total_students"].sum(min_count=1)
                    if "total_students" in drill_df.columns
                    else np.nan
                )
                raw_drill_t = (
                    drill_df["teacher_fte"].sum(min_count=1)
                    if "teacher_fte" in drill_df.columns
                    else np.nan
                )
                drill_s_disp = f"{raw_drill_s:,.0f}" if pd.notna(raw_drill_s) else "—"
                drill_t_disp = f"{raw_drill_t:,.1f}" if pd.notna(raw_drill_t) else "—"
                drill_ratio_disp = (
                    f"{raw_drill_s / raw_drill_t:.2f}:1"
                    if pd.notna(raw_drill_s) and pd.notna(raw_drill_t) and raw_drill_t > 0
                    else "—"
                )

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if is_op_only or drill_op_schools == drill_all_facilities:
                        st.metric("Operational Schools", f"{drill_op_schools:,}")
                    else:
                        st.metric(
                            "Operational Schools",
                            f"{drill_op_schools:,}",
                            help=f"All reported facilities in cohort: {drill_all_facilities:,}",
                        )
                with c2:
                    st.metric("Total Enrollment", drill_s_disp)
                with c3:
                    st.metric("Total Teacher FTE", drill_t_disp)
                with c4:
                    st.metric("State Weighted Ratio", drill_ratio_disp)

    # =========================================================================
    # TAB 3: Resource Pressure Triage
    # =========================================================================
    with tab3:
        st.markdown("### 🚨 Multi-Tier Resource Pressure Triage Framework")

        st.info(
            "**Operational Protocol**: Triage categories are evaluated in strict priority order. "
            "Schools in **Priority 1** require administrative data audit before capital or personnel intervention. "
            "**Priority 2** highlights facilities crossing the 90th percentile of their state and level peer group."
        )

        col_donut, col_desc = st.columns([1, 1])
        with col_donut:
            st.markdown(f"#### Priority Distribution ({ref_year})")
            render_triage_tier_donut(
                non_year_cohort,
                school_year=ref_year,
                operational_only=is_op_only,
            )

        with col_desc:
            st.markdown("#### Triage Waterfall Hierarchy")
            st.markdown(
                """
                1. <span class="badge-tag badge-danger">Priority 1: Administrative Review</span><br>
                   Missing student/teacher data, zero reported teachers, or campus reconfigurations.
                2. <span class="badge-tag badge-warning">Priority 2: Extreme Pressure (P90)</span><br>
                   Active regular schools at or above 90th percentile ratio of national peer group (School Year × School Level).
                3. <span class="badge-tag badge-warning">Priority 3: Rapid Ratio Escalation</span><br>
                   Year-over-year ratio growth crossing provisional threshold (tau_ratio_rise = +15.0%).
                4. <span class="badge-tag badge-primary">Priority 4: Divergent Growth Gap</span><br>
                   Enrollment growth outpacing staffing growth by >= 5.0 percentage points.
                5. <span class="badge-tag badge-primary">Priority 5: Unassessed Growth</span><br>
                   Newly opened or reconfigured facilities lacking consecutive prior baseline.
                6. <span class="badge-tag badge-success">Priority 6: Stable / Balanced</span><br>
                   Consecutive longitudinal trends within expected variance bounds.
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown(f"#### 📂 Interactive Field Triage Queues ({ref_year})")

        queue_type = st.radio(
            "Select Operational Queue",
            ["Priority 1: Administrative Review Queue", "Priority 2: Extreme Pressure (P90) Queue"],
            horizontal=True,
        )

        raw_q = (
            supp_data.get("p1_queue")
            if queue_type.startswith("Priority 1")
            else supp_data.get("p2_queue")
        )
        q_label = (
            "Priority 1: Administrative Review"
            if queue_type.startswith("Priority 1")
            else "Priority 2: Extreme Pressure (P90)"
        )
        q_file_name = (
            "priority_1_triage_queue.csv"
            if queue_type.startswith("Priority 1")
            else "priority_2_triage_queue.csv"
        )

        if raw_q is None:
            st.warning(
                f"⚠️ {q_label} file is missing or not generated. "
                "Please run deliverable generation scripts."
            )
        elif raw_q.empty:
            st.info(f"ℹ️ {q_label} is empty.")
        else:
            # Filter queue rows by ref_year and matching cohort using stable identifiers (school_id, school_year, state_fips)
            target_keys = (
                target_cohort[["school_id", "school_year", "state_fips"]].drop_duplicates().copy()
            )
            target_keys["school_id"] = target_keys["school_id"].astype(str)
            target_keys["school_year"] = target_keys["school_year"].astype(str)
            target_keys["state_fips"] = target_keys["state_fips"].astype(str).str.zfill(2)

            q_df = raw_q.copy()
            q_df["school_id"] = q_df["school_id"].astype(str)
            q_df["school_year"] = q_df["school_year"].astype(str)
            q_df["state_fips"] = q_df["state_fips"].astype(str).str.zfill(2)

            filtered_q = q_df.merge(
                target_keys, on=["school_id", "school_year", "state_fips"], how="inner"
            )

            q_count = len(filtered_q)
            st.markdown(f"**Showing {q_label} ({q_count:,} flagged records in {ref_year})**")

            if filtered_q.empty:
                st.info(
                    f"No records in {q_label} match the selected cohort filters for {ref_year}."
                )
            else:
                st.dataframe(filtered_q.head(100), use_container_width=True, hide_index=True)
                csv_data = filtered_q.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"📥 Download Filtered {q_label} (CSV)",
                    data=csv_data,
                    file_name=f"{ref_year}_{q_file_name}",
                    mime="text/csv",
                )

    # =========================================================================
    # TAB 4: Data Quality & Caveats
    # =========================================================================
    with tab4:
        st.markdown("### 🔍 Data Quality, Coverage, and Structural Reporting Breaks")

        st.warning(
            "**Data Governance Warning**: Under no circumstances should student-to-teacher ratio be treated as "
            "an empirical measure of classroom size. Special education resource teachers, reading coaches, and "
            "itinerant specialists are counted in the FTE denominator without reducing general education class headcounts."
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### NCES Negative Code Normalization")
            st.markdown(
                """
                | Special Code | Source Meaning | Pipeline Handling |
                | :--- | :--- | :--- |
                | `-1` | Missing | IEEE `NaN` / Null (Never coerced to 0) |
                | `-2` | Not Applicable | IEEE `NaN` / Null |
                | `-9` | Suppressed (Privacy) | IEEE `NaN` / Null |
                | `-11` | Imputed Data | Flagged & Retained |
                """
            )

        with c2:
            st.markdown("#### Known Structural Reporting Breaks")
            st.markdown(
                """
                | Jurisdiction | Affected Year | Observed Impact | Pipeline Routing |
                | :--- | :--- | :--- | :--- |
                | **California** | 2019–20 | 0.0 Teacher FTE reported statewide | Flagged; growth suppressed |
                | **Illinois** | 2020–21 | Teacher FTE uncollected | Flagged; routed to P1 review |
                | **Nevada** | 2018–19 | Partial FTE suppression | Flagged; audited |
                | **Washington** | 2021–22 | FTE reporting format break | Flagged; audited |
                """
            )

        st.markdown("---")
        st.markdown("#### Longitudinal Coverage by School Year")
        from school_planning.reporting.tables import format_kpi_summary_table

        cov_table = format_kpi_summary_table(
            non_year_cohort,
            operational_only=is_op_only,
        )
        cov_cols = [
            "school_year",
            "operational_schools",
        ]
        if not is_op_only and "all_facilities" in cov_table.columns:
            cov_cols.append("all_facilities")
        cov_cols.extend(
            [
                "total_enrollment",
                "total_teacher_fte",
                "weighted_ratio",
            ]
        )
        st.dataframe(
            cov_table[cov_cols].style.format(
                {
                    "operational_schools": "{:,}",
                    "all_facilities": "{:,}",
                    "total_enrollment": "{:,.0f}",
                    "total_teacher_fte": "{:,.1f}",
                    "weighted_ratio": "{:.2f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    # =========================================================================
    # TAB 5: Forecasting & Scenarios
    # =========================================================================
    with tab5:
        st.markdown("### 📈 Time-Series Feasibility, Backtesting & Policy Scenarios")

        st.info(
            "**Scientific Feasibility Assessment**: Individual school-level forecasting over T=5 annual observations "
            "is mathematically and statistically indefensible. With degrees of freedom near zero, boundary changes, "
            "and the unmodeled COVID-19 structural break, complex models (ARIMA, Prophet, LSTM) severely overfit. "
            "Forecasting is restricted to **state aggregate levels**, where variance is pooled and error is rigorously evaluated."
        )

        col_bt, col_wape = st.columns([3, 2])
        with col_bt:
            st.markdown("#### Walk-Forward Backtesting Model Comparison")
            if supp_data.get("backtest") is not None:
                render_backtest_error_chart(supp_data["backtest"])

        with col_wape:
            st.markdown("#### Backtesting Performance Metrics")
            if supp_data.get("backtest") is not None:
                from school_planning.reporting.tables import format_backtest_comparison_table

                bt_fmt = format_backtest_comparison_table(supp_data["backtest"])
                st.dataframe(
                    bt_fmt[["fold_id", "model_display", "wape", "mae", "rmse"]].style.format(
                        {
                            "wape": "{:.2f}%",
                            "mae": "{:,.1f}",
                            "rmse": "{:,.1f}",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("---")
        st.markdown("### 🎚️ Interactive Policy Staffing Demand Simulation")
        st.markdown(
            "Adjust the **Policy Target Student-to-Teacher Ratio** slider below to dynamically simulate "
            "implied classroom teacher demand under 2023–24 baseline enrollment projections:"
        )

        col_slider, _col_spacer = st.columns([2, 3])
        with col_slider:
            policy_ratio = st.slider(
                "Policy Target Ratio (Students per Teacher FTE)",
                min_value=10.0,
                max_value=25.0,
                value=15.0,
                step=0.5,
                help="Statutory or target student-to-teacher ratio benchmark.",
            )

        if supp_data.get("projections") is not None:
            proj_data = supp_data["projections"].copy()
            if filters.get("selected_fips"):
                selected_fips_norm = {str(f).zfill(2) for f in filters["selected_fips"]}
                proj_data = proj_data[
                    proj_data["state_fips"].astype(str).str.zfill(2).isin(selected_fips_norm)
                ]
            elif filters.get("states"):
                proj_data = proj_data[proj_data["state_name"].isin(filters["states"])]

            if proj_data.empty:
                st.info("No scenario projections match the selected state filter criteria.")
            else:
                render_scenario_projection_chart(
                    proj_data, policy_target_ratio=policy_ratio, top_n=10
                )


if __name__ == "__main__":
    main()
