"""kpi_cards.py - Modern styled metric cards and KPI grid components for Streamlit."""

from typing import Any

import streamlit as st


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    delta: str | None = None,
    delta_color: str = "normal",  # "normal", "inverse", "off"
    border_color: str = "#E2E8F0",
    bg_gradient: str = "linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)",
) -> None:
    """Render a single modern styled KPI card using HTML/CSS container."""
    delta_html = ""
    if delta:
        color = (
            "#0D9488"
            if delta_color == "normal"
            else ("#E11D48" if delta_color == "inverse" else "#64748B")
        )
        arrow = (
            "↑ "
            if not delta.startswith("-") and not delta.startswith("—")
            else ("↓ " if delta.startswith("-") else "")
        )
        delta_html = f"<div style='font-size: 0.85rem; font-weight: 600; color: {color}; margin-top: 4px;'>{arrow}{delta}</div>"

    sub_html = (
        f"<div style='font-size: 0.8rem; color: #64748B; margin-top: 2px;'>{subtitle}</div>"
        if subtitle
        else ""
    )

    card_html = f"""
    <div style='
        background: {bg_gradient};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 12px;
    '>
        <div style='font-size: 0.85rem; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.05em;'>
            {title}
        </div>
        <div style='font-size: 1.85rem; font-weight: 700; color: #0F172A; line-height: 1.2; margin-top: 6px;'>
            {value}
        </div>
        {delta_html}
        {sub_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_kpi_grid(
    operational_schools: int,
    total_students: float,
    total_teachers: float,
    weighted_ratio: float,
    p1_review_count: int = 0,
    p2_extreme_count: int = 0,
    prev_students: float | None = None,
    prev_teachers: float | None = None,
    school_title: str = "Operational Schools",
    school_subtitle: str = "Active reported facilities",
    reference_year: str = "",
) -> None:
    """Render a 4 or 6-column standardized metric grid across the page width."""
    # Compute deltas
    student_delta = None
    if prev_students and prev_students > 0 and not pd_isna(total_students):
        pct = ((total_students - prev_students) / prev_students) * 100.0
        student_delta = f"{pct:+.2f}% YoY"

    teacher_delta = None
    if prev_teachers and prev_teachers > 0 and not pd_isna(total_teachers):
        pct = ((total_teachers - prev_teachers) / prev_teachers) * 100.0
        teacher_delta = f"{pct:+.2f}% YoY"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_kpi_card(
            title=school_title,
            value=f"{operational_schools:,}" if operational_schools is not None else "—",
            subtitle=school_subtitle,
            border_color="#CBD5E1",
        )

    with col2:
        if pd_isna(total_students):
            val_str = "—"
        elif total_students >= 1e6:
            val_str = f"{total_students / 1e6:.2f}M"
        else:
            val_str = f"{total_students:,.0f}"
        render_kpi_card(
            title="Total Enrollment",
            value=val_str,
            subtitle=f"{reference_year} Verified student membership"
            if reference_year
            else "Verified student membership",
            delta=student_delta,
            delta_color="normal",
            border_color="#93C5FD",
        )

    with col3:
        if pd_isna(total_teachers):
            val_str = "—"
        elif total_teachers >= 1e6:
            val_str = f"{total_teachers / 1e6:.2f}M"
        else:
            val_str = f"{total_teachers:,.1f}"
        render_kpi_card(
            title="Total Teacher FTE",
            value=val_str,
            subtitle=f"{reference_year} Classroom teachers FTE"
            if reference_year
            else "Classroom teachers FTE",
            delta=teacher_delta,
            delta_color="normal",
            border_color="#99F6E4",
        )

    with col4:
        ratio_str = (
            f"{weighted_ratio:.2f}:1" if weighted_ratio and not pd_isna(weighted_ratio) else "—"
        )
        render_kpi_card(
            title="Weighted Ratio",
            value=ratio_str,
            subtitle="Students per Teacher FTE",
            border_color="#FCA5A5",
        )


def pd_isna(val: Any) -> bool:
    """Safe check for NaN/None values."""
    if val is None:
        return True
    try:
        import numpy as np

        return bool(np.isnan(val))
    except (TypeError, ValueError):
        return False
