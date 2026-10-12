"""Analytics and KPI module for smart-school-resource-planning."""

from school_planning.analytics.descriptive import (
    summarize_by_category,
    summarize_distributions,
    summarize_state_aggregates,
)
from school_planning.analytics.growth import compute_longitudinal_growth
from school_planning.analytics.kpis import (
    calculate_school_kpis,
    compute_growth_gap,
    compute_student_teacher_ratio,
)
from school_planning.analytics.segmentation import (
    BENCHMARKED_STATUS_LABEL,
    ELIGIBLE_SCHOOL_LEVELS,
    ELIGIBLE_SCHOOL_TYPE,
    UNBENCHMARKED_STATUS_LABEL,
    classify_peer_group_eligibility,
    compute_peer_group_p90_thresholds,
)

__all__ = [
    "BENCHMARKED_STATUS_LABEL",
    "ELIGIBLE_SCHOOL_LEVELS",
    "ELIGIBLE_SCHOOL_TYPE",
    "UNBENCHMARKED_STATUS_LABEL",
    "calculate_school_kpis",
    "classify_peer_group_eligibility",
    "compute_growth_gap",
    "compute_longitudinal_growth",
    "compute_peer_group_p90_thresholds",
    "compute_student_teacher_ratio",
    "summarize_by_category",
    "summarize_distributions",
    "summarize_state_aggregates",
]
