# Policy and Operational Recommendations for Resource Allocation

## 1. Governance & Data Architecture Recommendations (For State Education Agencies)

### Recommendation 1.1: Mandate Standardized FTE Reporting Across All Operating Districts
* **Evidence**: Over four major states (California, Illinois, Nevada, Washington) exhibited complete or partial structural reporting breaks where teacher FTE was reported as 0.0 or omitted entirely in statewide NCES submissions.
* **Action**: Implement automated pre-submission schema validation that rejects zero FTE for operational campuses unless accompanied by an explicit shared-facility or administrative agreement.
* **Expected Impact**: Eliminates 5,169 schools nationwide currently requiring manual administrative review due to reporting ambiguities.

### Recommendation 1.2: Establish Common School Cohort Tracking for Capital Planning
* **Evidence**: Compositional churn (new school openings, school closures, and boundary reconfigurations) accounts for the majority of unassessed growth classifications (Priority 5, representing 86.7% of operational schools in single-year delta views).
* **Action**: State registries should maintain persistent campus lineages (`predecessor_school_id`) that persist across boundary reorganizations.

---

## 2. Resource Allocation & Staffing Triage (For District Superintendents & Planners)

### Recommendation 2.1: Establish a Two-Stage Resource Deployment Gate
* **Evidence**: In 2022–23, 8,562 operational regular schools crossed the state-level P90 student-to-teacher ratio threshold (Priority 2).
* **Action**:
  1. **Stage 1 (Automated Filter)**: Identify Priority 2 candidates via the dashboard.
  2. **Stage 2 (Root-Cause Investigation)**: Before allocating full-time positions, audit whether the ratio reflects genuine instructional deficits or specialized program staffing (e.g., dual-enrollment, unassigned specialists, or part-time aides).
* **Risk Avoided**: Prevents costly over-hiring in facilities where low reported FTE is an artifact of shared itinerant staffing.

### Recommendation 2.2: Apply Policy Target Staffing Simulations
* **Evidence**: Maintaining a constant student-to-teacher ratio during student enrollment expansion or contraction requires dynamically tracking implied FTE demands.
* **Action**: Districts should utilize the retrospective scenario bands (+/-2%) to test budget resilience against unexpected student migration.

---

## 3. Methodological Caveats for Analysts & Decision-Makers

1. **Class Size Fallacy**: Under no circumstances should executive briefings equate student-to-teacher ratio with average class size. Ratio is a macro fiscal indicator; class size depends on scheduling, elective offerings, and specialized pull-out services.
2. **Charter vs. Regular Differences**: Charter schools frequently employ contracted or part-time instructional providers that may not be captured uniformly in CCD FTE counts. Cross-sector comparisons must be explicitly qualified.
3. **Provisional Thresholds**: Thresholds tau_ratio_rise = +15.0% and tau_growth_gap = +5.0 pp are provisional engineering baselines. Local education agencies should calibrate these parameters against regional collective bargaining agreements and state statutory staffing minimums.
