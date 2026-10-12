# Business Requirements Specification — Smart School Resource Planning

## 1. Overview & Business Context

The **Smart School Resource Planning** system provides educational decision-makers with evidence-based intelligence on public school student enrollments, teacher staffing levels, and resource pressure dynamics. Public school systems operate under statutory requirements and fiscal constraints that necessitate transparent, audit-ready data transformations.

This document formalizes the business questions, functional requirements, analytical metrics, and acceptance criteria governing the solution.

---

## 2. Core Business Questions

The platform is designed to answer five foundational business questions:

### BQ-1: Staffing vs. Enrollment Trend Alignment
* **Question:** Which school districts and individual schools are experiencing student enrollment growth that is outpacing classroom teacher FTE growth over 1-year and multi-year horizons?
* **Decision Supported:** Identification of schools requiring immediate teacher recruitment authorizations versus schools where declining enrollment suggests natural attrition should be leveraged.

### BQ-2: Identification of Resource Pressure Outliers
* **Question:** Where are the schools with severe staffing pressure (e.g., student-to-teacher ratio in the top decile or exceeding statutory guidelines), and is this pressure chronic or acute?
* **Decision Supported:** Targeted allocation of supplemental instructional staff, emergency district relief, and class-load balancing.

### BQ-3: Data Integrity vs. True Operational Anomalies
* **Question:** Are apparent staffing shortages genuine operational deficits, or are they reporting artifacts caused by non-reporting (`DMS_FLAG != 'Reported'`), centralized LEA staff assignment, or specialized school configurations (e.g., adult education programs, zero-teacher administrative entities)?
* **Decision Supported:** Prevention of erroneous funding reallocations or public misreporting based on flawed data interpretations.

### BQ-4: Post-Pandemic Enrollment Trajectory
* **Question:** How did the 2020-21 COVID-19 pandemic disrupt enrollment and teacher allocations across verified school types (regular, vocational, special education) and charter governance, and which segments have rebounded?
* **Decision Supported:** Long-term capital planning, school boundary adjustments, and programmatic resource balancing using verified attributes in the CCD extracts.
* **Scope & Limitation Note:** Analysis across verified school types (`SCH_TYPE_TEXT`) and charter status (`CHARTER_TEXT`) is directly supported by the current CCD extracts. In contrast, geographic locale-level analysis (urban, suburban, town, rural) cannot be performed using the current 029, 052, and 059 components because they lack a verified locale attribute; locale analysis is formally documented as a planned future extension requiring a documented external enrichment source (such as NCES EDGE locale boundary datasets).

### BQ-5: Retrospective Aggregate Staffing Projections
* **Question:** What are the retrospective state-level aggregate student enrollment and teacher FTE projections for the 2023-24 school year generated from historical 2018-19 to 2022-23 trends under transparent baseline and drift scenarios?
* **Decision Supported:** Baseline reference projections for post-observation period planning. Because actual 2023-24 outcomes are absent from this dataset, the 2023-24 projection serves strictly as a retrospective baseline model demonstration; its empirical forecast accuracy cannot be evaluated within this workspace. True forecast accuracy is evaluated exclusively through the 2021-22 and 2022-23 historical backtesting folds.

---

## 3. Functional Requirements

### FR-1: Multi-Year Non-Fiscal CCD Ingestion
* **FR-1.1:** The system shall ingest five consecutive school years (2018-19 to 2022-23) across three distinct CCD components: Directory (`029`), Membership (`052`), and Staff (`059`).
* **FR-1.2:** The ingestion engine shall preserve all alphanumeric leading zeroes for state (`FIPST`), district (`LEAID`), and school (`NCESSCH`) identifiers.
* **FR-1.3:** The system shall accommodate schema shifts across years (e.g., column casing differences, column ordering, and header counts) without data truncation or corruption.

### FR-2: Deduplication and Grain Standardization
* **FR-2.1:** The ingestion engine shall enforce table grain:
  - Component `029` (Directory): Grain = `[NCESSCH, SCHOOL_YEAR]`; exactly 1 record per school per year.
  - Component `052` (Membership): Filter to contract indicator `Derived - Education Unit Total minus Adult Education Count` (`TOTAL_INDICATOR`), yielding grain = `[NCESSCH, SCHOOL_YEAR]`.
  - Component `059` (Staff): Grain = `[NCESSCH, SCHOOL_YEAR]`; exactly 1 record per school per year.
* **FR-2.2:** Multi-source joins shall execute on `[school_id, school_year]` using a `1:0..1` (one-to-zero-or-one) left join paradigm from the Directory spine. Each source key in target tables (Staff, filtered Membership) must be unique to guarantee at most one match and prevent row multiplication. Unmatched spine records (~2-4%) are permitted, retained with null measure values, and audited in data quality logs without failing the pipeline.

### FR-3: Data Cleaning and Flag Harmonization
* **FR-3.1:** The system shall strictly separate reported numerical zeros (`TEACHERS == 0.0` with `DMS_FLAG == 'Reported'`) from non-reported/missing data (`DMS_FLAG in ('Missing', 'Not reported', 'Suppressed')`). Non-reported fields shall be stored as null (`NaN`), never coerced to zero.
* **FR-3.2:** Schools reporting zero teacher FTE with valid reported flags shall be assigned a diagnostic flag `zero_teacher_anomaly = True` and excluded from ratio denominators.
* **FR-3.3:** The system shall flag operational status cohorts (`Open`, `New` vs. `Closed`, `Inactive`) to ensure inactive schools do not distort operational staffing distributions.

### FR-4: Analytical KPI Calculation
* **FR-4.1:** The engine shall calculate standardized KPIs:
  1. `total_students`: Headcount enrollment.
  2. `teacher_fte`: Classroom teacher FTE.
  3. `student_teacher_ratio`: `total_students / teacher_fte` (null if FTE is zero or missing).
  4. `enrollment_growth_yoy_pct`: Consecutive-year percentage change for common-school longitudinal cohorts.
  5. `teacher_fte_growth_yoy_pct`: Consecutive-year percentage change for common-school longitudinal cohorts.
  6. `ratio_growth_yoy_pct`: Consecutive-year percentage change in student-to-teacher ratio for common-school longitudinal cohorts with positive reported ratios.
  7. `growth_gap_pct_points`: `enrollment_growth_yoy_pct - teacher_fte_growth_yoy_pct`.
* **FR-4.2:** Every calculated KPI shall be accompanied by an eligibility mask indicating whether the record satisfies all denominator, reporting, and cohort requirements.

### FR-5: Resource Pressure Categorization
* **FR-5.1:** The system shall classify each school facility into a hierarchical, mutually exclusive Resource Pressure category evaluated in strict priority order:
  - **Priority 1: Incomplete Data or Status Review:** Highest priority. Triggered if enrollment is missing, teacher FTE is missing/unreported/suppressed, reported teacher FTE is zero (`zero_teacher_anomaly`), school status is non-operational, or school status is a transition-review category (`Added`, `Changed Boundary/Agency`, `Reopened`) requiring administrative verification before routine tier assignment.
  - **Priority 2: High Current Ratio:** Complete operational data and `student_teacher_ratio >= P90` strictly for regular schools belonging to the exact set of standard instructional levels (`Elementary`, `Middle`, `High`; ties handled with inclusive $\ge$). Every school level outside this set (including `Secondary`, `Other`, `Prekindergarten`, `Ungraded`, `Adult Education`, `Not applicable`, `Not reported`, or unexpected values) and every non-regular school type is classified as unbenchmarked and bypasses Priority 2 to prevent invalid peer-group comparisons without authoritative statutory standards.
  - **Priority 3: Rapidly Rising Ratio:** Complete data, ratio < P90 (or unbenchmarked peer group), valid consecutive-year growth metrics, and annual ratio growth $\ge \tau_{\text{ratio_rise}}$ (candidate threshold, e.g. +15.0%, explicitly marked as a provisional parameter for decision-support prototyping, to be calibrated in Phase 5).
  - **Priority 4: Staffing Growth Deficit:** Complete data, ratio < P90 (or unbenchmarked peer group), not rapidly rising, valid consecutive-year growth metrics, and `growth_gap_pct_points >= \tau_{\text{growth_gap}}$ (candidate threshold, e.g. +5.0 pp, explicitly marked as a provisional parameter for decision-support prototyping, to be calibrated in Phase 5).
  - **Priority 5: Growth Unassessed / Incomplete Growth Data:** Complete data, ratio < P90 (or unbenchmarked peer group), but consecutive-year growth metrics cannot be calculated (e.g. 2018-19 base year, new schools, or prior-year record exists but prior-year enrollment or teacher FTE was missing, non-reported, or zero). Explicitly prevents unassessed schools from defaulting to Stable.
  - **Priority 6: Stable / Balanced:** Complete data, ratio < P90 (or unbenchmarked peer group), growth successfully assessed, within normal operating variation. For unbenchmarked schools, assignment to this tier indicates strictly that longitudinal trend indicators did not cross provisional escalation thresholds; it does NOT certify or imply that staffing has been shown to be adequate, balanced, or compliant with specialized program standards.

### FR-6: Constrained Forecasting & Scenario Generation
* **FR-6.1:** Statistical forecasting shall be executed strictly at aggregate grains (State-level `FIPST`), with school-level forecasting explicitly disabled.
* **FR-6.2:** The engine shall execute three baseline models:
  - `Naive Persistence` ($y_{t+1} = y_t$).
  - `Linear Drift` ($y_{t+1} = y_t + \bar{\Delta}$).
  - `3-Year Moving Average`.
* **FR-6.3:** Model performance shall be validated exclusively via expanding-window walk-forward backtesting on historical holdout years with observed ground truth:
  - Fold 1: Test year 2021-22 (trained on 2018-19 to 2020-21).
  - Fold 2: Test year 2022-23 (trained on 2018-19 to 2021-22).
  Evaluation metrics shall report MAE, WAPE, and MAPE.
* **FR-6.4:** Forecasts shall be bounded by +/- 1% and +/- 2% scenario sensitivity intervals. The 2023-24 projection shall be described strictly as a retrospective projection based on the full 5-year historical series (2018-19 to 2022-23). The system shall explicitly NOT claim that 2023-24 forecast accuracy can be evaluated within this workspace, because actual 2023-24 outcomes are absent from the dataset.

### FR-7: Interactive User Interface (Streamlit)
* **FR-7.1:** The application shall provide five dedicated views:
  1. Overview (National & State trends).
  2. Geographic Comparison (Inter-state & Inter-district benchmarking).
  3. Resource Pressure Explorer (Facility-level search and tier filtering).
  4. Data Quality & Coverage Center (Missingness rates, flag distributions, unmatched audit).
  5. State Forecast & Scenario Planner (Aggregate projections and model comparisons).
* **FR-7.2:** Every visualization and table displaying student-to-teacher ratio shall include a prominent caveat disclaimer: *"Staffing ratio reflects aggregate facility allocations and does not represent average classroom class size."*

---

## 4. Non-Functional Requirements

| ID | Requirement Category | Specification |
| :--- | :--- | :--- |
| **NFR-1** | **Reproducibility** | Entire pipeline runnable from a clean checkout via `uv run` with exact pinned dependencies in `uv.lock`. |
| **NFR-2** | **Memory Efficiency** | Raw 052 Membership files are ~2.2–2.5 GB each (11,948,167 rows verified for 2018-19; complete row counts for other years remain unverified). Ingestion must use chunked/streaming parsing with column selection and predicate pushdown filtering on `TOTAL_INDICATOR = 'Derived - Education Unit Total minus Adult Education Count'` to ensure peak memory does not exceed standard 8GB RAM workstations. |
| **NFR-3** | **Data Integrity** | String typing for identifiers (`NCESSCH`: 12-char fixed, `LEAID`: 7-char fixed, `FIPST`: 2-char fixed) strictly enforced across all interim and processed Parquet schemas. |
| **NFR-4** | **Auditability** | Every pipeline execution generates machine-readable JSON/Markdown quality logs recording row counts, null rates, and dropped records at each transformation stage. |
| **NFR-5** | **Code Quality** | Strict linting compliance under `ruff` with zero fatal warnings; test suite with high coverage over transformation, key integrity, and formula calculations. |

---

## 5. Acceptance Criteria

1. **Sign-off on Contract:** All 6 configuration files (`project.yaml`, `sources.yaml`, `column_mapping.yaml`, `quality_rules.yaml`, `kpi_definitions.yaml`, `forecasting.yaml`) are syntactically valid YAML and logically consistent with verified Phase 0 raw file audits.
2. **Deterministic Join Validation:** Verified 1:0..1 left join between Directory spine, Membership, and Staff components on synthetic and sample fixtures with target key uniqueness and zero row multiplication.
3. **Transparent Quality Contract:** Explicit documentation of missing data handling, zero-teacher handling, and adult education exclusion.
