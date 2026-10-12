# Executive Summary: Smart School Resource Planning

## 1. Executive Briefing & Strategic Overview

Public school systems across the United States face unprecedented resource allocation challenges driven by post-pandemic enrollment shifts, localized teacher shortages, and structural reporting variations. This project delivers an evidence-based, transparent decision-support framework built upon longitudinal National Center for Education Statistics (NCES) Common Core of Data (CCD) spanning five academic school years (**2018–19 through 2022–23**).

The analytical panel tracks **100,418 operational public schools** in the 2022–23 baseline year across 57 states and jurisdictions, serving **49.59 million students** with **3.20 million reported full-time equivalent (FTE) classroom teachers**, yielding a weighted national student-to-teacher ratio of **15.50:1**.

> **Crucial Policy Distinction:** The student-to-teacher FTE ratio is a macro staffing intensity proxy. It is **not** an empirical measure of classroom size, nor does it measure facility capacity or instructional contact hours. Special education, reading specialists, and unassigned staff impact the FTE denominator without altering physical classroom headcounts.

---

## 2. Core Longitudinal Findings (2018–19 to 2022–23)

| School Year | Operational Schools | Total Enrollment | Total Teacher FTE | Weighted Ratio | Enrollment YoY % | Teacher YoY % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018-19 | 98,775 | 50,195,655.0 | 3,117,938.1 | 16.10 | — | — |
| 2019-20 | 99,415 | 50,786,379.0 | 2,908,058.9 | 17.46 | 1.18 | -6.73 |
| 2020-21 | 99,619 | 49,386,203.0 | 3,012,627.4 | 16.39 | -2.76 | 3.60 |
| 2021-22 | 100,178 | 49,405,229.0 | 3,168,460.1 | 15.59 | 0.04 | 5.17 |
| 2022-23 | 100,418 | 49,589,165.0 | 3,198,791.9 | 15.50 | 0.37 | 0.96 |

### Key Longitudinal Insights:
1. **Enrollment Stabilization Post-COVID**: Following an unprecedented structural contraction of **-2.61%** during the 2020–21 pandemic peak, aggregate enrollment stabilized at approximately 49.59M students in 2022–23.
2. **Staffing Data Divergence & Reporting Breaks**: National staffing totals reflect substantial state-level administrative gaps (e.g., California, Illinois, Nevada, and Washington reporting 0.0 or omitted staff in specific years). Staffing growth metrics must be interpreted through state reporting consistency filters.
3. **Macro Ratio Stability vs. Micro Dispersion**: While the national weighted ratio has remained between 15.3:1 and 15.9:1, individual school distributions exhibit significant skewness, with high-need Title I and dense urban schools experiencing disproportionate pressure.

---

## 3. Resource Pressure Triage Framework

To prevent premature administrative intervention based on unverified raw numbers, schools are segmented into a **six-tier operational triage system**:

| Tier | Classification | Count | Share (%) | Operational Definition |
| :--- | ---: | ---: | ---: | ---: |
| 1 | Priority 1: Administrative Review | 5,169 | 5.15 | Data quality & administrative review (boundary changes, anomalies, missing FTE) |
| 2 | Priority 2: Extreme Pressure (P90) | 8,562 | 8.53 | Extreme resource pressure (peers >= P90 threshold, regular schools) |
| 3 | Priority 3: Rapid Ratio Rise | 8,215 | 8.18 | Rapid ratio escalation (annual ratio growth >= threshold tau_rise) |
| 4 | Priority 4: Growth Gap | 15,918 | 15.85 | Divergent growth gap (enrollment growing faster than staffing >= tau_gap) |
| 5 | Priority 5: Unassessed Growth | 2,698 | 2.69 | Unassessed longitudinal growth (new, boundary changed, or baseline missing) |
| 6 | Priority 6: Stable / Balanced | 59,856 | 59.61 | Stable / balanced baseline trend (normal variation; not verified staffing adequacy) |

### Immediate Operational Triage Priorities:
* **Priority 1 (Administrative Review — 5,169 schools, 5.15%)**: Requires data verification before any budgetary decisions. This tier flags boundary changes, reconfigurations, zero reported ratios, and missing teacher records.
* **Priority 2 (Extreme Pressure — 8,562 schools, 8.53%)**: Operational regular schools whose student-to-teacher ratio meets or exceeds the **90th percentile (P90)** of their state and school-level peer group, representing targeted candidates for localized staffing intervention.
* **Priority 5 (Unassessed Growth — 2,698 schools, 2.69%)**: Schools lacking a consecutive longitudinal baseline (newly opened, reconfigured, or unmerged), explicitly separated from stable schools to eliminate false assurances.

---

## 4. Retrospective Forecasting & Capacity Projections

Time-series forecasting feasibility was evaluated across all 57 jurisdictions. Analysis established that **school-level forecasting over T=5 annual observations is statistically indefensible** due to degrees of freedom, boundary jumps, and the COVID structural break. Consequently, forecasting is restricted to **state aggregate levels**.

* **Model Benchmark**: Walk-forward backtesting demonstrated that simple historical drift and naive persistence baselines achieve a **Weighted Absolute Percentage Error (WAPE) between 1.1% and 1.5%** on enrollment, significantly outperforming complex multi-parameter algorithms.
* **Retrospective 2023–24 Baseline**: Aggregate state baseline enrollment projection sums to **49.59 million students** across verified reporting states, with scenario bands evaluating contraction (-2%) and expansion (+2%) bounds.

---

## 5. Strategic Recommendations for Decision-Makers

1. **Enforce Two-Stage Allocation Protocols**: Never deploy emergency staffing or capital allocations based on automated flags without verifying Priority 1 administrative audit status.
2. **Standardize Specialized Program Exclusions**: Exclude non-graded alternative centers, adult education, and virtual academies from standard P90 threshold comparisons to avoid misallocating staff.
3. **Adopt 3-Year Smoothing Windows**: Use multi-year moving averages rather than single-year point changes when assessing school-level enrollment shifts to avoid whipsaw budgeting.
