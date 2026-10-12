"""filters.py - Dynamic sidebar filter controls and DataFrame filtering logic."""

from typing import Any

import pandas as pd
import streamlit as st


def render_sidebar_filters(df: pd.DataFrame) -> dict[str, Any]:
    """Render interactive sidebar controls and collect filter parameters.

    Args:
        df: Input analytical DataFrame.

    Returns:
        Dictionary of active filter parameters.
    """
    st.sidebar.markdown("### 🎛️ Analysis Filters")

    # School Year filter
    available_years = sorted(df["school_year"].dropna().unique().tolist(), reverse=True)
    default_year = "2022-23" if "2022-23" in available_years else available_years[0]
    selected_year = st.sidebar.selectbox(
        "School Year",
        options=["All Years"] + available_years,
        index=available_years.index(default_year) + 1 if default_year in available_years else 0,
        help="Select evaluation school year. Multi-year comparisons require 'All Years'.",
    )

    # State / Jurisdiction filter - key by state_fips while displaying state_name
    if "state_fips" in df.columns and "state_name" in df.columns:
        state_pairs = (
            df[["state_fips", "state_name"]].dropna().drop_duplicates().sort_values("state_name")
        )
        fips_list = state_pairs["state_fips"].tolist()
        fips_to_name = dict(zip(state_pairs["state_fips"], state_pairs["state_name"], strict=False))

        selected_fips = st.sidebar.multiselect(
            "State / Jurisdiction",
            options=fips_list,
            format_func=lambda fips: fips_to_name.get(fips, fips),
            default=[],
            help="Filter to specific states or jurisdictions by FIPS. Leave empty for all.",
        )
        selected_states = [fips_to_name[f] for f in selected_fips if f in fips_to_name]
    else:
        state_col = "state_name" if "state_name" in df.columns else "state_fips"
        available_states = sorted([str(s) for s in df[state_col].dropna().unique().tolist()])
        selected_states = st.sidebar.multiselect(
            "State / Jurisdiction",
            options=available_states,
            default=[],
            help="Filter to specific states or jurisdictions. Leave empty for all.",
        )
        selected_fips = []

    # School Level filter
    if "school_level" in df.columns:
        available_levels = sorted(df["school_level"].dropna().unique().tolist())
        selected_levels = st.sidebar.multiselect(
            "School Level",
            options=available_levels,
            default=[],
            help="Filter by school instructional level (Primary, Middle, High, Other). Leave empty for all.",
        )
    else:
        selected_levels = []

    # Charter Status filter
    charter_choice = st.sidebar.radio(
        "Charter Status",
        options=["All Schools", "Non-Charter Only", "Charter Only"],
        index=0,
        horizontal=True,
    )

    # Operational Status filter
    op_choice = st.sidebar.radio(
        "Operational Status",
        options=["Operational Only", "Include Inactive / Closed"],
        index=0,
        horizontal=True,
    )

    # Priority Tier filter
    tier_col = (
        "resource_pressure_priority"
        if "resource_pressure_priority" in df.columns
        else ("priority_tier" if "priority_tier" in df.columns else None)
    )
    if tier_col:
        tier_options = [
            "Priority 1: Administrative Review",
            "Priority 2: Extreme Pressure (P90)",
            "Priority 3: Rapid Ratio Rise",
            "Priority 4: Growth Gap",
            "Priority 5: Unassessed Growth",
            "Priority 6: Stable / Balanced",
        ]
        tier_codes_map = {opt: i + 1 for i, opt in enumerate(tier_options)}
        selected_tier_labels = st.sidebar.multiselect(
            "Resource Pressure Tier",
            options=tier_options,
            default=[],
            help="Filter by triage priority category. Leave empty for all.",
        )
        selected_tiers = [tier_codes_map[opt] for opt in selected_tier_labels]
    else:
        selected_tiers = []

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<small style='color: #64748B;'>Data Source: NCES CCD Longitudinal Panel (2018–19 to 2022–23)<br>"
        "Target grain: <code>(school_id, school_year)</code></small>",
        unsafe_allow_html=True,
    )

    return {
        "school_year": selected_year,
        "selected_fips": selected_fips,
        "states": selected_states,
        "school_levels": selected_levels,
        "charter_choice": charter_choice,
        "operational_choice": op_choice,
        "priority_tiers": selected_tiers,
    }


def apply_filters(
    df: pd.DataFrame,
    filters: dict[str, Any],
    include_year: bool = True,
) -> pd.DataFrame:
    """Apply collected filter criteria to the analytical DataFrame.

    Args:
        df: Input DataFrame.
        filters: Dictionary returned by render_sidebar_filters.
        include_year: If True, applies school_year filter when not 'All Years'.
            If False, retains all school years (useful for longitudinal trends
            and prior-year cohort comparisons).

    Returns:
        Filtered DataFrame copy.
    """
    filtered = df.copy()

    # 1. School Year (applied only when include_year=True)
    if include_year and filters.get("school_year") and filters["school_year"] != "All Years":
        filtered = filtered[filtered["school_year"] == filters["school_year"]]

    # 2. State / Jurisdiction (FIPS-first, with fallback to state_name)
    if filters.get("selected_fips") and "state_fips" in filtered.columns:
        selected_fips_norm = {str(f).zfill(2) for f in filters["selected_fips"]}
        filtered = filtered[
            filtered["state_fips"].astype(str).str.zfill(2).isin(selected_fips_norm)
        ]
    elif filters.get("states"):
        state_col = "state_name" if "state_name" in filtered.columns else "state_fips"
        filtered = filtered[filtered[state_col].astype(str).isin(filters["states"])]

    # 3. School Level
    if filters.get("school_levels") and "school_level" in filtered.columns:
        filtered = filtered[filtered["school_level"].isin(filters["school_levels"])]

    # 4. Charter Status (strictly explicitly observed values; missing/unknown never coerced)
    if "is_charter" in filtered.columns:
        if filters.get("charter_choice") == "Non-Charter Only":
            filtered = filtered[filtered["is_charter"].notna() & filtered["is_charter"].eq(False)]
        elif filters.get("charter_choice") == "Charter Only":
            filtered = filtered[filtered["is_charter"].notna() & filtered["is_charter"].eq(True)]

    # 5. Operational Status
    if (
        "is_operational" in filtered.columns
        and filters.get("operational_choice") == "Operational Only"
    ):
        filtered = filtered[filtered["is_operational"].fillna(False).astype(bool)]

    # 6. Priority Tiers
    tier_col = (
        "resource_pressure_priority"
        if "resource_pressure_priority" in filtered.columns
        else ("priority_tier" if "priority_tier" in filtered.columns else None)
    )
    if filters.get("priority_tiers") and tier_col:
        filtered = filtered[filtered[tier_col].isin(filters["priority_tiers"])]

    return filtered
