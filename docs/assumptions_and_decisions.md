# Architectural Decisions & Assumptions Log

## 1. Overview

This document records the foundational architectural decisions, analytical assumptions, and empirical findings established during the initial source audit and data contract specification of the **Smart School Resource Planning** project. Each decision records the business and technical context, alternatives considered, chosen approach, and documented rationale.

---

## 2. Decision Log

### ADR-01: Selection of Primary Operational Enrollment Indicator (`TOTAL_INDICATOR`)

* **Date:** 2026-10-12
* **Context:** The NCES CCD Component `052` (Membership) reports student enrollment across multiple indicator rows per school. In the verified 2018-19 full-file scan, two school-level total indicators were observed and compared:
  1. `Education Unit Total`
  2. `Derived - Education Unit Total minus Adult Education Count`
* **Empirical Verification:**
  - Header comparison covered all 15 source files.
  - Full Membership indicator cohort set equality was verified exclusively for 2018-19 (`ccd_sch_052_1819_l_1a_091019.csv`).
  - Both indicators contain exactly 99,533 unique schools (`NCESSCH`), proving exact set equality across reporting institutions in 2018-19.
  - Of the 99,533 schools, exactly 99,287 schools (99.75%) exhibit identical student counts between the two indicators.
  - Exactly 246 schools (0.25%) exhibit differences, where `Education Unit Total` includes Adult Education enrollment (ranging from 1 to 5,082 adult students).
  - *Caveat:* Full Membership indicator cohort set equality was verified for 2018-19 only; indicator domains and cohort equivalence across the remaining four school years (2019-20 through 2022-23) are verified via chunked streaming data ingestion.
* **Decision:**
  - Establish `Derived - Education Unit Total minus Adult Education Count` as the exclusive primary operational contract indicator for `total_students` in the primary analytical panel.
  - The primary panel filters strictly to this single indicator to guarantee a strict 1:1 school-year grain.
  - If `Education Unit Total` is retained, it must be stored as an auxiliary audit column (`total_students_with_adult_ed`), never as additional rows.
* **Rationale:**
  - The project's core purpose is K-12 public school classroom resource allocation. Including adult education headcounts distorts student-to-teacher FTE staffing ratios in regular elementary and secondary settings. Admitting both indicators as rows would cause duplicate keys and double-count enrollments.

---

### ADR-02: Identifier Normalization and the `SCHID` Structural Discrepancy

* **Date:** 2026-10-12
* **Context:** Official NCES documentation states that the 12-digit school ID (`NCESSCH`) is constructed as:
  $$\text{NCESSCH} = \text{LEAID (7 digits)} + \text{SCHID (5 digits)}$$
  Header comparison covered all 15 source files and confirmed the presence of `SCHID`. A full-record relationship audit was performed on the 2018-19 and 2022-23 Directory extracts (102k+ records per file, 0 mismatches); it was not performed as a full-record audit across all five years. This audit revealed that the raw column `SCHID` contains 7 alphanumeric characters matching `FIPST (2 chars) + NCESSCH[-5:]`, rather than the official 5-digit local school code or the last 7 characters of `NCESSCH`.
* **Decision:**
  1. Mandate `NCESSCH` (12 characters, fixed-width string with leading zeroes) as the immutable primary key for all school entities.
  2. Mandate `LEAID` (7 characters, fixed-width string with leading zeroes) as the primary key for school districts.
  3. Mandate `FIPST` (2 characters, fixed-width string with leading zeroes) as the state FIPS code.
  4. Retain `SCHID` as a raw passthrough string for provenance audit, but prohibit its use as a join key or composite key component.
  5. Distinguish observed data release artifacts from official NCES data dictionary definitions in all project documentation.
* **Rationale:**
  - Enforcing string typing with zero-padding prevents catastrophic numerical truncation (e.g., FIPS `01` dropping to `1`, or LEAID `0100005` dropping to `100005`). Discarding `SCHID` as a key prevents invalid join mappings.

---

### ADR-03: Treatment of Zero Teacher FTE vs. Non-Reported Missing Data (`DMS_FLAG`)

* **Date:** 2026-10-12
* **Context:** In Component `059` (Staff), teacher FTE (`TEACHERS`) is qualified by a data flag (`DMS_FLAG`). In the verified source audit of the 2018-19 Staff file (`ccd_sch_059_1819_l_1a_091019.csv`, 99,911 total rows):
  - 96,780 schools (96.87%) have `DMS_FLAG == 'Reported'`:
    - 95,353 schools (95.44%) report positive FTE (`TEACHERS > 0.0`).
    - 1,427 schools (1.43%) report zero FTE (`TEACHERS == 0.0`).
  - 3,131 schools (3.13%) have non-reported flags (`DMS_FLAG` in `['Missing', 'Not reported', 'Suppressed']`):
    - 2,225 schools (2.23%) are `Missing`.
    - 749 schools (0.75%) are `Not reported`.
    - 157 schools (0.16%) are `Suppressed`.
* **Decision:**
  1. **Missing Data Policy:** Records with non-reported flags (3,131 in 2018-19) shall NEVER be coerced to zero. They shall be represented as null (`NaN`) and tracked under data quality missingness KPIs.
  2. **Reported Zero Policy:** Records with `DMS_FLAG == 'Reported'` and `TEACHERS == 0.0` (1,427 in 2018-19) represent validly reported administrative zeros. They are retained in the panel but flagged with `zero_teacher_anomaly = True`.
  3. **Ratio Denominator Policy:** When `teacher_fte == 0.0` or is null, `student_teacher_ratio` shall evaluate to null (`NaN`). Infinite ratios ($\infty$) are strictly prohibited.
* **Rationale:**
  - Coercing missing staff data to zero creates thousands of false-positive "critical staffing crises" (e.g., 500 students with 0 teachers). Conversely, discarding valid reported zeros conceals administrative units whose teachers are centralized at the LEA level.

---

### ADR-04: Robust File Ingestion and Encoding Fallback Policy

* **Date:** 2026-10-12
* **Context:** Header comparison covering all 15 source files and byte audits revealed that while raw CSVs predominantly use ASCII/UTF-8 compatible characters, byte `0x96` (Windows-1252 en-dash) appears in certain year extracts. Using `errors='ignore'` silently drops characters and corrupts school names; forcing strict `utf-8` causes fatal read crashes.
* **Decision:**
  - Ingestion readers must implement a deterministic multi-encoding cascade:
    1. Attempt strict `utf-8`.
    2. Fallback to `windows-1252` (or `cp1252`) if `UnicodeDecodeError` is encountered.
  - Latin-1 is strictly prohibited as a leading decoder because it decodes all 256 bytes without error, masking corruption. Silent decoding suppression (`errors='ignore'` or `errors='replace'`) is strictly prohibited.
* **Rationale:**
  - Preserves exact school and district legal entity names without silent truncation.

---

### ADR-05: Operational Status Scoping and Analytical Panel Cohorts

* **Date:** 2026-10-12
* **Context:** Directory file `029` contains schools with diverse operational statuses. NCES releases contain both initial status (`SY_STATUS_TEXT`, numeric `SY_STATUS`) and updated status (`UPDATED_STATUS_TEXT`, numeric `UPDATED_STATUS`). `UPDATED_STATUS` is a numeric integer code and must not be treated as a text category.
* **Decision:**
  - The processed analytical panel (`school_year_analytical_panel.parquet`) shall retain ALL schools present in the directory files to ensure 100% population coverage for auditability and join verification.
  - Define explicit scoping buckets based on `SY_STATUS_TEXT`:
    - **Active Operational Cohort:** `['Open', 'New']` (eligible for core operational KPIs).
    - **Inactive Cohort:** `['Closed', 'Inactive', 'Future']`.
    - **Transition Review Cohort:** `['Added', 'Changed Boundary/Agency', 'Reopened']` — must NOT automatically be presumed inactive, but represents structural boundary or organizational disruptions that cannot be evaluated with standard routine metrics without administrative vetting. Routed to Priority 1 (Administrative Status Review) in tier evaluation.
  - Add boolean cohort flags: `is_operational`, `is_balanced_panel`.
* **Rationale:**
  - Retaining closed/inactive schools in the primary panel avoids unrecorded record drops, while cohort flags prevent closed schools from biasing live staffing distributions without prematurely discarding re-opened or boundary-shifted facilities.

---

### ADR-06: Feasibility Boundary for Statistical Forecasting

* **Date:** 2026-10-12
* **Context:** The master plan mandates assessing the feasibility of forecasting. The available dataset contains exactly 5 annual time steps (2018-19 to 2022-23), which includes a major macroeconomic/epidemiological shock in 2020-21 (COVID-19). The current calendar year is 2026.
* **Decision:**
  1. **School-Level Forecasting:** Formally ruled out as scientifically invalid. No statistical or machine learning models shall be trained to forecast individual schools.
  2. **Aggregate-Level Forecasting:** Permitted strictly at the State aggregate level (`FIPST`).
  3. **Timeframe Framing:** Because the observation window ends in 2022-23 and current date is 2026, 2023-24 model projections are strictly framed as a retrospective projection based on available 2018-19 to 2022-23 data, not an upcoming forecast. Crucially, because actual 2023-24 outcomes are absent from this dataset, forecast accuracy CANNOT be evaluated for 2023-24 in this workspace. Accuracy (MAE, WAPE, MAPE) is evaluated exclusively on historical walk-forward backtesting folds (2021-22 and 2022-23) where actual ground truth exists.
  4. **Model Complexity:** Limited to transparent baseline benchmarks:
     - Naive Persistence ($y_{t+1} = y_t$)
     - Linear Drift ($y_{t+1} = y_t + \bar{\Delta}$)
     - 3-Year Moving Average
  5. **Validation Protocol:** Expanding-window walk-forward validation (Train 2018-19..2020-21 -> Test 2021-22; Train 2018-19..2021-22 -> Test 2022-23), reporting MAE, WAPE, and MAPE.
  6. **Scenario Bounds:** Provide deterministic sensitivity bands (+/- 1% and +/- 2%) alongside point projections.
* **Rationale:**
  - With T=5, estimating complex models (ARIMA with AR/MA terms, Prophet, neural networks) violates basic degrees-of-freedom principles and generates spurious projections. Aggregate benchmarks provide actionable retrospective benchmarks.

---

### ADR-07: Calculation of Longitudinal Growth Rates on Common Cohorts

* **Date:** 2026-10-12
* **Context:** Calculating annual percentage changes on unconstrained populations causes composition bias (e.g., an aggregate enrollment drop caused by schools failing to report or closing rather than actual student outflows).
* **Decision:**
  - All Year-over-Year (YoY) growth calculations (`enrollment_growth_yoy_pct`, `teacher_fte_growth_yoy_pct`, `ratio_growth_yoy_pct`) must be evaluated strictly on common-school longitudinal cohorts: facilities reporting valid data in both year $t$ and year $t-1$.
  - When prior-year denominator values are missing or zero, growth rates evaluate to null (`NaN`) and are flagged as unassessed rather than defaulting to stable.
* **Rationale:**
  - Eliminates artificial volatility caused by cohort entry and exit.

---

### ADR-08: Explicit Distinction Between Staffing Ratio and Class Size

* **Date:** 2026-10-12
* **Context:** The metric `student_teacher_ratio` is widely misconstrued by public stakeholders as "average class size."
* **Decision:**
  - Mandatory disclaimer on all tables, charts, reports, and UI views displaying `student_teacher_ratio`:
    > *"Notice: Student-to-teacher ratio measures institutional staffing allocation per enrolled student. It does not measure classroom class size, co-teaching staffing, or daily course period scheduling."*
* **Rationale:**
  - Prevents erroneous policy interpretations and maintains professional standards of educational measurement.

---

### ADR-09: Directory Spine Join Semantics and 1:0..1 Cardinality

* **Date:** 2026-10-12
* **Context:** In relational modeling, Directory `029` serves as the master facility spine. Not every school reported in the directory has a corresponding Staff `059` or Membership `052` record (~2-4% unmatched due to non-reporting, specialized administration, or state reporting omissions). Describing the join as `1:1` creates a false expectation that all schools have matches or that unmatched records indicate data pipeline failure.
* **Decision:**
  1. Mandate `1:0..1` (one-to-zero-or-one) left join cardinality from Directory to Staff and filtered Membership.
  2. Enforce unique composite join keys `[school_id, school_year]` in target tables to guarantee at most one match and prevent row multiplication.
  3. Permit unmatched spine records, preserving them in the analytical panel with null measure values and logging them in data quality audit reports.
* **Rationale:**
  - Reflects the empirical reality of federal administrative data while maintaining mathematical guarantees against Cartesian row explosion.

---

### ADR-10: Peer-Group Scope, Unbenchmarked School Handling, and Tier Interpretation

* **Date:** 2026-10-12
* **Context:** `config/kpi_definitions.yaml` specifies 90th percentile (P90) staffing ratio comparisons. NCES CCD contains non-regular school types (Special Education, Alternative, Career/Tech) and diverse non-standard instructional levels (observed levels include `Secondary`, `Other`, `Prekindergarten`, `Ungraded`, `Adult Education`, `Not applicable`, `Not reported`, and `Missing`). Pooling these into regular elementary/middle/high deciles severely distorts distributions.
* **Decision:**
  1. Restrict P90 peer-group ratio benchmarking strictly to `SCH_TYPE_TEXT == 'Regular School'` across the exact set of standard instructional levels (`Elementary`, `Middle`, `High`).
  2. Enforce a complete catch-all eligibility rule: any school level outside the exact set `{'Elementary', 'Middle', 'High'}` (including `Secondary`, `Adult Education`, `Not applicable`, or any newly observed string in raw data) and any non-regular school type is classified as `Unbenchmarked / Specialized Peer Group`.
  3. Remove unverified fixed sample-size assumptions (e.g. >15,000 schools); exploratory analysis and peer-group evaluation is assigned responsibility for profiling actual peer-group stratum sizes and assessing benchmarking suitability.
  4. Formally distinguish the orthogonal dimension `peer_group_status` (`Benchmarked Regular Peer Group` vs. `Unbenchmarked / Specialized Peer Group`) from `resource_pressure_tier`.
  5. For unbenchmarked schools evaluated into Priority 6 (`Stable / Balanced`), explicitly document that this classification denotes solely that available longitudinal trend indicators did not cross provisional escalation thresholds (`tau_ratio_rise`, `tau_growth_gap`). It does NOT imply or certify that absolute staffing levels have been shown to be adequate, balanced, or compliant with specialized program guidelines.
  6. The platform strictly refuses to invent arbitrary statutory ratio thresholds in the absence of authoritative standards.
* **Rationale:**
  - Adheres directly to master plan Section 1.3 and Section 3.5: never silently compare unlike school populations, and never represent unbenchmarked facilities as having verified staffing adequacy without authoritative evidence.
