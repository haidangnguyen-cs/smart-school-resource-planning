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
from school_planning.analytics.resource_pressure import (
    DEFAULT_TAU_GROWTH_GAP,
    DEFAULT_TAU_RATIO_RISE,
    PRIORITY_1_LABEL,
    PRIORITY_2_LABEL,
    PRIORITY_3_LABEL,
    PRIORITY_4_LABEL,
    PRIORITY_5_LABEL,
    PRIORITY_6_LABEL,
    PRIORITY_TIER_ORDER,
    classify_resource_pressure,
    extract_triage_queue,
    summarize_resource_pressure_by_level,
    summarize_resource_pressure_by_state,
    summarize_resource_pressure_tiers,
)
from school_planning.analytics.segmentation import (
    BENCHMARKED_STATUS_LABEL,
    ELIGIBLE_SCHOOL_LEVELS,
    ELIGIBLE_SCHOOL_TYPE,
    NON_OPERATIONAL_STATUS_LABEL,
    UNBENCHMARKED_STATUS_LABEL,
    classify_peer_group_eligibility,
    compute_peer_group_p90_thresholds,
)

__all__ = [
    "BENCHMARKED_STATUS_LABEL",
    "DEFAULT_TAU_GROWTH_GAP",
    "DEFAULT_TAU_RATIO_RISE",
    "ELIGIBLE_SCHOOL_LEVELS",
    "ELIGIBLE_SCHOOL_TYPE",
    "NON_OPERATIONAL_STATUS_LABEL",
    "PRIORITY_1_LABEL",
    "PRIORITY_2_LABEL",
    "PRIORITY_3_LABEL",
    "PRIORITY_4_LABEL",
    "PRIORITY_5_LABEL",
    "PRIORITY_6_LABEL",
    "PRIORITY_TIER_ORDER",
    "UNBENCHMARKED_STATUS_LABEL",
    "calculate_school_kpis",
    "classify_peer_group_eligibility",
    "classify_resource_pressure",
    "compute_growth_gap",
    "compute_longitudinal_growth",
    "compute_peer_group_p90_thresholds",
    "compute_student_teacher_ratio",
    "extract_triage_queue",
    "summarize_by_category",
    "summarize_distributions",
    "summarize_resource_pressure_by_level",
    "summarize_resource_pressure_by_state",
    "summarize_resource_pressure_tiers",
    "summarize_state_aggregates",
]
