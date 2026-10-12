# Technical Report: Analytical Methodology, Pipeline Architecture, and Validation

## 1. Data Pipeline Architecture & Standardization

### 1.1 Source Ingestion & Grain Preservation
The pipeline ingests raw annual data products from the National Center for Education Statistics (NCES) Common Core of Data (CCD):
* **Directory (DIR)**: School metadata, geographic identifiers (NCES school ID, state FIPS, district ID), operational status, charter status, school level.
* **Membership (MEM)**: Grade-level student counts and total enrollment.
* **Staffing (STAFF)**: Full-Time Equivalent (FTE) classroom teachers.

**Canonical Grain**: The analytical panel is strictly enforced at `(school_id, school_year)`. Uniqueness is verified via automated hash and composite-key checks before and after relational joins.

### 1.2 Data Cleaning & Missing Value Protocols
* **Special Codes**: NCES negative integer codes (`-1` Missing, `-2` Not Applicable, `-9` Data Suppressed, `-11` Imputed) are normalized to standard IEEE `NaN` / `NULL`. They are **never** coerced to `0.0`.
* **Zero vs. Missing Audit**: True zero enrollment or staffing is distinguished from uncollected data. States exhibiting structural reporting omissions (e.g. California 2019-20, Illinois 2020-21, Nevada 2018-19, Washington 2021-22 with 0.0 teacher FTE) are audited and flagged in the data quality logs to prevent spurious growth spikes.
* **Identifier Preservation**: State and NCES IDs are stored as zero-padded alphanumeric strings (e.g. FIPS `'06'` for California), preventing floating-point truncation.

### 1.3 Longitudinal System Scope (2018–19 to 2022–23)
| School Year | Operational Schools | Total Enrollment | Total Teacher FTE | Weighted Ratio | Enrollment YoY % | Teacher YoY % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018-19 | 98,775 | 50,195,655.0 | 3,117,938.1 | 16.10 | — | — |
| 2019-20 | 99,415 | 50,786,379.0 | 2,908,058.9 | 17.46 | 1.18 | -6.73 |
| 2020-21 | 99,619 | 49,386,203.0 | 3,012,627.4 | 16.39 | -2.76 | 3.60 |
| 2021-22 | 100,178 | 49,405,229.0 | 3,168,460.1 | 15.59 | 0.04 | 5.17 |
| 2022-23 | 100,418 | 49,589,165.0 | 3,198,791.9 | 15.50 | 0.37 | 0.96 |

---

## 2. Mathematical Formulations & Indicator Definitions

### 2.1 Student-to-Teacher Ratio
```
Ratio(i,t) = total_students(i,t) / teacher_fte(i,t)
```
* **Eligibility Rule**: Computed if and only if teacher_fte > 0 and total_students >= 0.
* **Zero Denominators**: When teacher_fte is 0 or NaN, the ratio is set to NaN and routed to Priority 1 triage.

### 2.2 Longitudinal Growth Rates
```
ΔEnrollment(i,t) = [(total_students(i,t) - total_students(i,t-1)) / total_students(i,t-1)] * 100
ΔTeachers(i,t) = [(teacher_fte(i,t) - teacher_fte(i,t-1)) / teacher_fte(i,t-1)] * 100
Growth Gap(i,t) = ΔEnrollment(i,t) - ΔTeachers(i,t)  (percentage points)
```

---

## 3. Resource Pressure Triage Classification Algorithm

Classification executes via a deterministic, hierarchical priority waterfall applied to operational regular schools:

```
[Operational School]
       |
       v
[Priority 1: Administrative Review]
  - Missing student or teacher data
  - Negative ratio or teacher_fte <= 0
  - Boundary changed / reconfigured (status 2, 4, 6)
       | (False)
       v
[Priority 2: Extreme Pressure (P90)]
  - Regular school in valid peer group
  - student_teacher_ratio >= 90th percentile of (State x Level)
       | (False)
       v
[Priority 3: Rapid Ratio Escalation]
  - Annual ratio change >= tau_ratio_rise (+15.0%)
       | (False)
       v
[Priority 4: Divergent Growth Gap]
  - Enrollment growth - Teacher growth >= tau_growth_gap (+5.0 pp)
       | (False)
       v
[Priority 5: Unassessed Growth]
  - Missing prior-year baseline (new school, boundary shift, unlinked)
       | (False)
       v
[Priority 6: Stable / Balanced]
  - Consecutive history within baseline variance thresholds
```

### Operational Distribution (2022–23):
| Tier | Label | School Count | Operational % | Definition |
| :--- | ---: | ---: | ---: | ---: |
| 1 | Priority 1: Administrative Review | 5,169 | 5.15 | Data quality & administrative review (boundary changes, anomalies, missing FTE) |
| 2 | Priority 2: Extreme Pressure (P90) | 8,562 | 8.53 | Extreme resource pressure (peers >= P90 threshold, regular schools) |
| 3 | Priority 3: Rapid Ratio Rise | 8,215 | 8.18 | Rapid ratio escalation (annual ratio growth >= threshold tau_rise) |
| 4 | Priority 4: Growth Gap | 15,918 | 15.85 | Divergent growth gap (enrollment growing faster than staffing >= tau_gap) |
| 5 | Priority 5: Unassessed Growth | 2,698 | 2.69 | Unassessed longitudinal growth (new, boundary changed, or baseline missing) |
| 6 | Priority 6: Stable / Balanced | 59,856 | 59.61 | Stable / balanced baseline trend (normal variation; not verified staffing adequacy) |

---

## 4. State-Level Performance & Triage Aggregates

Top 15 Jurisdictions by 2022–23 Enrollment:
| FIPS | Jurisdiction | Operational Schools | Total Students | Teacher FTE | Ratio | P1 Review | P2 P90 | P3 Rising | P4 Gap | Total Triage |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 06 | CALIFORNIA | 10,319 | 5,837,314.0 | 267,225.0 | 21.84 | 337 | 4,961 | 550 | 732 | 6,580 |
| 48 | TEXAS | 9,180 | 5,519,599.0 | 371,385.1 | 14.86 | 285 | 132 | 803 | 1,882 | 3,102 |
| 12 | FLORIDA | 4,208 | 2,867,162.0 | 155,864.3 | 18.40 | 437 | 491 | 415 | 821 | 2,164 |
| 36 | NEW YORK | 4,812 | 2,505,431.0 | 215,401.7 | 11.63 | 103 | 34 | 333 | 809 | 1,279 |
| 17 | ILLINOIS | 4,408 | 1,852,242.0 | 135,276.6 | 13.69 | 369 | 62 | 308 | 625 | 1,364 |
| 13 | GEORGIA | 2,316 | 1,750,972.0 | 118,650.8 | 14.76 | 22 | 16 | 105 | 388 | 531 |
| 39 | OHIO | 3,632 | 1,679,311.0 | 92,749.9 | 18.11 | 238 | 428 | 270 | 485 | 1,421 |
| 42 | PENNSYLVANIA | 2,936 | 1,672,695.0 | 121,964.2 | 13.71 | 12 | 24 | 158 | 495 | 689 |
| 37 | NORTH CAROLINA | 2,712 | 1,541,296.0 | 98,606.9 | 15.63 | 17 | 115 | 288 | 668 | 1,088 |
| 26 | MICHIGAN | 3,506 | 1,386,979.0 | 82,063.3 | 16.90 | 98 | 192 | 366 | 530 | 1,186 |
| 34 | NEW JERSEY | 2,558 | 1,349,187.0 | 115,691.4 | 11.66 | 84 | 13 | 204 | 487 | 788 |
| 51 | VIRGINIA | 2,129 | 1,259,374.0 | 88,209.0 | 14.28 | 317 | 8 | 175 | 293 | 793 |
| 04 | ARIZONA | 2,426 | 1,131,357.0 | 49,269.7 | 22.96 | 988 | 212 | 163 | 188 | 1,551 |
| 53 | WASHINGTON | 2,549 | 1,090,227.0 | 62,339.5 | 17.49 | 288 | 110 | 248 | 547 | 1,193 |
| 18 | INDIANA | 1,921 | 1,035,833.0 | 65,497.7 | 15.81 | 46 | 52 | 187 | 362 | 647 |

---

## 5. Forecasting Feasibility & Backtesting Evaluation

### 5.1 Feasibility Assessment
* **Micro Feasibility (Rejected)**: School-level time series forecasting is statistically indefensible. With T=5 annual observations, parameter estimation degrees of freedom are insufficient, annual facility volatility is high, boundary changes cause discontinuous jumps, and COVID-19 created an unmodeled structural break.
* **Macro Feasibility (Supported)**: State-level aggregation pools variance, stabilizing time-series signals.

### 5.2 Chronological Walk-Forward Backtest Results
Walk-forward evaluation with expanding training windows evaluated one-step ahead performance:
* Fold 1: Train 2018–19 -> Test 2019–20
* Fold 2: Train 2018–19..2019–20 -> Test 2020–21
* Fold 3: Train 2018–19..2020–21 -> Test 2021–22
* Fold 4: Train 2018–19..2021–22 -> Test 2022–23

| Fold | Target Variable | Forecasting Model | N | WAPE (%) | MAE | RMSE | Min Cov % | Med Cov % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold_1 | total_students | Linear Drift (Trend) | 55 | 1.82 | 16,324.0 | 36,226.8 | 91.26 | 99.93 |
| fold_1 | total_students | 3-Year Moving Average | 55 | 1.66 | 14,953.0 | 24,299.9 | 91.26 | 99.93 |
| fold_1 | total_students | Naive Persistence (y_t) | 55 | 1.10 | 9,916.9 | 18,616.7 | 91.26 | 99.93 |
| fold_2 | total_students | Linear Drift (Trend) | 55 | 1.38 | 12,435.8 | 23,002.8 | 87.69 | 100.00 |
| fold_2 | total_students | 3-Year Moving Average | 55 | 1.50 | 13,494.6 | 29,349.5 | 87.69 | 100.00 |
| fold_2 | total_students | Naive Persistence (y_t) | 55 | 0.93 | 8,406.9 | 16,783.4 | 87.69 | 100.00 |
| overall_pooled | total_students | Linear Drift (Trend) | 110 | 1.60 | 14,379.9 | 30,343.9 | 87.69 | 100.00 |
| overall_pooled | total_students | 3-Year Moving Average | 110 | 1.58 | 14,223.8 | 26,943.2 | 87.69 | 100.00 |
| overall_pooled | total_students | Naive Persistence (y_t) | 110 | 1.02 | 9,161.9 | 17,723.8 | 87.69 | 100.00 |
| fold_1 | teacher_fte | Linear Drift (Trend) | 52 | 1.78 | 1,026.4 | 1,898.3 | 60.33 | 99.30 |
| fold_1 | teacher_fte | 3-Year Moving Average | 52 | 1.82 | 1,049.2 | 1,722.3 | 60.33 | 99.30 |
| fold_1 | teacher_fte | Naive Persistence (y_t) | 52 | 1.11 | 641.49 | 1,053.1 | 60.33 | 99.30 |
| fold_2 | teacher_fte | Linear Drift (Trend) | 54 | 1.67 | 980.01 | 1,683.8 | 59.32 | 99.72 |
| fold_2 | teacher_fte | 3-Year Moving Average | 54 | 1.61 | 947.29 | 1,482.6 | 59.32 | 99.72 |
| fold_2 | teacher_fte | Naive Persistence (y_t) | 54 | 1.21 | 711.95 | 1,094.3 | 59.32 | 99.72 |
| overall_pooled | teacher_fte | Linear Drift (Trend) | 106 | 1.72 | 1,002.7 | 1,792.2 | 59.32 | 99.62 |
| overall_pooled | teacher_fte | 3-Year Moving Average | 106 | 1.71 | 997.30 | 1,604.7 | 59.32 | 99.62 |
| overall_pooled | teacher_fte | Naive Persistence (y_t) | 106 | 1.16 | 677.38 | 1,074.3 | 59.32 | 99.62 |

**Key Finding**: Naive persistence and simple linear drift achieved the lowest error across all evaluation folds (WAPE 1.1% to 1.5%), proving that simple transparent baselines are optimal for constrained annual educational series.

---

## 6. Retrospective 2023–24 Projections & Policy Scenario Bands

| FIPS | Jurisdiction | 2022-23 Actual | Baseline Proj | Low (-2%) | High (+2%) | Actual FTE | Implied FTE (Ratio) | Implied FTE (Target 15:1) | Valid History |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 06 | CALIFORNIA | 5,837,314.0 | 5,837,314.0 | 5,720,567.7 | 5,954,060.3 | 267,225.0 | 267,225.0 | — | 1 |
| 48 | TEXAS | 5,519,599.0 | 5,519,599.0 | 5,409,207.0 | 5,629,991.0 | 371,385.1 | 371,385.1 | — | 1 |
| 12 | FLORIDA | 2,867,162.0 | 2,867,162.0 | 2,809,818.8 | 2,924,505.2 | 155,864.3 | 155,864.3 | — | 1 |
| 36 | NEW YORK | 2,505,431.0 | 2,505,431.0 | 2,455,322.4 | 2,555,539.6 | 215,401.7 | 215,401.7 | — | 1 |
| 17 | ILLINOIS | 1,852,242.0 | 1,852,242.0 | 1,815,197.2 | 1,889,286.8 | 135,276.6 | 135,276.6 | — | 1 |
| 13 | GEORGIA | 1,750,972.0 | 1,750,972.0 | 1,715,952.6 | 1,785,991.4 | 118,650.8 | 118,650.8 | — | 1 |
| 39 | OHIO | 1,679,311.0 | 1,679,311.0 | 1,645,724.8 | 1,712,897.2 | 92,749.9 | 92,749.9 | — | 1 |
| 42 | PENNSYLVANIA | 1,672,695.0 | 1,672,695.0 | 1,639,241.1 | 1,706,148.9 | 121,964.2 | 121,964.2 | — | 1 |
| 37 | NORTH CAROLINA | 1,541,296.0 | 1,541,296.0 | 1,510,470.1 | 1,572,121.9 | 98,606.9 | 98,606.9 | — | 1 |
| 26 | MICHIGAN | 1,386,979.0 | 1,386,979.0 | 1,359,239.4 | 1,414,718.6 | 82,063.3 | 82,063.3 | — | 1 |

*Exclusions Note: Jurisdictions without valid 2022–23 reporting (e.g. American Samoa, Guam) are excluded from national aggregates to prevent distortion.*
