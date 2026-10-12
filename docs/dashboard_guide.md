# User and Administrator Guide: Smart School Resource Planning Dashboard

## 1. System Overview & Purpose

The **Smart School Resource Planning Dashboard** is an interactive, evidence-based decision-support system built upon longitudinal National Center for Education Statistics (NCES) Common Core of Data (CCD) spanning five academic school years (**2018–19 through 2022–23**).

The dashboard translates complex administrative datasets (Directory, Membership, Staffing) into actionable intelligence for:
* **State Education Agencies (SEAs)**: Identifying reporting inconsistencies, missing teacher submissions, and structural reporting breaks.
* **District Superintendents & School Boards**: Pinpointing facilities experiencing severe resource pressure relative to empirical peer groups.
* **School Planners & Budget Analysts**: Simulating implied teacher demand under statutory or target student-to-teacher ratios and enrollment shifts.

---

## 2. Launching and Running the Application

### 2.1 Prerequisites
* Python 3.12+ with project dependencies installed via `uv`.
* Processed analytical datasets under `data/processed/` and summary tables under `outputs/tables/`.

### 2.2 Local Execution
To launch the Streamlit dashboard in your local browser:

```powershell
uv run streamlit run app/streamlit_app.py
```

By default, the dashboard initializes on `http://localhost:8501`.

---

## 3. Global Sidebar Controls & Filter Semantics

The sidebar persists across all dashboard pages, enabling dynamic slicing of the analytical panel:

1. **School Year**:
   * Options: `2018-19`, `2019-20`, `2020-21`, `2021-22`, `2022-23`, or `All Years`.
   * Default: `2022-23` (most recent baseline year).
   * **Semantics for "All Years"**: When `All Years` is selected, snapshot KPI indicator cards use the latest available school year (`2022-23`) as their explicitly labelled reference period. This prevents invalid cumulative summing of repeated annual school observations into impossible multi-year totals. The full 5-year historical trajectory remains available to longitudinal charts and summary tables.
   * **Prior-Year YoY Comparisons**: Prior-year comparisons evaluate against the immediate preceding year (`ref_year - 1`) applying the **exact same non-year filters** (same state, school level, charter, operational, and priority tier) as the current cohort, avoiding biased comparisons against unfiltered national cohorts.
2. **State / Jurisdiction**:
   * Multi-select filter covering all 57 states, territories, and jurisdictions.
   * **Entity Identity**: Backed by canonical NCES FIPS codes (`state_fips`) for entity grouping, drill-down, and queue matching, with `state_name` used as the display label.
   * Default: All jurisdictions.
3. **School Level**:
   * Filter by instructional span: `Primary`, `Middle`, `High`, or `Other`.
4. **Charter Status**:
   * Radio filter: `All Schools`, `Non-Charter Only`, or `Charter Only`.
   * **Explicit Observation Semantics**: `Non-Charter Only` selects explicitly observed non-charter records (`is_charter == False`), and `Charter Only` selects explicitly observed charter records (`is_charter == True`). Records with missing or unknown charter status are excluded from both single-category filters and are never coerced into either known category.
   * *Caveat*: Charter schools frequently utilize contracted or shared instructional providers that may be reported differently than traditional LEAs.
5. **Operational Status**:
   * Radio filter: `Operational Only` (default) vs. `Include Inactive / Closed`.
   * **Operational Cohort vs. All Reported Facilities Semantics**: The user's selection is consistently respected. When `Operational Only` is active, closed/inactive schools are filtered out. When `Include Inactive / Closed` is selected, inactive facilities remain visible for inspection. Metric tables and KPI cards strictly distinguish between `operational_schools` (which always counts facilities where `is_operational == True`) and `all_facilities` (total reported facilities in the selected cohort). Non-operational records do not inflate operational-cohort priority triage counts or tier percentage distributions.
6. **Resource Pressure Tier**:
   * Filter specifically to Priority 1, 2, 3, 4, 5, or 6.

---

## 4. Dashboard Tabs & Analytical Workflows

### Tab 1: 📊 System Overview
* **KPI Metrics**: Displays total operational schools (with total reported facilities noted in the subtitle when inactive facilities are included), aggregate student enrollment, total teacher FTE, and the weighted student-to-teacher ratio with year-over-year growth badges. When `All Years` is selected, the card header explicitly labels the reference snapshot year (`2022-23`). Unavailable values are rendered as `—` rather than coerced to `0.0`.
* **Longitudinal Trends**: Dual-metric line chart tracking student membership and staffing FTE from 2018–19 to 2022–23 for the user's selected non-year cohort (e.g. state or school level).
* **Level Distribution**: Box plot and summary table showing median ratios and interquartile ranges across Primary, Middle, High, and Specialized schools for the reference year.
* **System Summary Table**: Complete longitudinal audit showing operational school counts (and all reported facilities if inactive facilities are included) along with year-over-year percentage changes for the selected cohort.

### Tab 2: 🗺️ Geographic Analysis
* **State Rankings Table**: Interactive sortable table displaying operational schools, all reported facilities (when inactive facilities are included), enrollment, staffing, ratio, and operational triage counts for all jurisdictions. All-missing student or staffing aggregates evaluate to `NaN` and render as `—`, while legitimate reported zeros (`0.0`) are preserved.
* **State Drill-Down**: Deep-dive selector keyed on canonical `state_fips` with `state_name` display labels. Displays localized KPIs, distinguishing operational schools from total cohort facilities and handling missing metrics gracefully with `—`.

### Tab 3: 🚨 Resource Pressure Triage
* **Triage Waterfall**: Visual breakdown of the six-tier deterministic classification algorithm.
* **Interactive Queues**:
  * **Priority 1 (Administrative Review Queue)**: Displays facilities with missing data, reported 0.0 teacher FTE, negative ratios, or boundary reconfigurations.
  * **Priority 2 (Extreme Pressure Queue)**: Active regular schools meeting or exceeding the 90th percentile (P90) ratio of their state and school-level peer group.
* **Queue Filtering Consistency**: Queue records are filtered by the reference school year and the active sidebar filters (state FIPS, school level, charter status, operational status). The displayed count, table rows, and downloadable CSV all represent the **identical filtered records**.
* **Graceful Missing-File Handling**: If queue CSV files are missing or empty, an informative warning or empty state is rendered without unhandled exceptions.

### Tab 4: 🔍 Data Quality & Caveats
* **NCES Negative Code Protocols**: Documentation of how special codes (`-1`, `-2`, `-9`, `-11`) are normalized to IEEE `NaN` rather than coerced to zero.
* **Structural Reporting Breaks**: Specific audit documentation for California (2019–20), Illinois (2020–21), Nevada (2018–19), and Washington (2021–22).
* **Core Policy Caveats**: Clear explanations distinguishing the student-to-teacher ratio from class size.

### Tab 5: 📈 Forecasting & Scenarios
* **Feasibility Notice**: Explains why individual school-level forecasting over $T=5$ is statistically invalid and why forecasting is restricted to state aggregates.
* **Walk-Forward Backtesting**: Model error comparisons (WAPE, MAE, RMSE) proving that simple drift and persistence baselines outperform complex models on short annual series.
* **Retrospective 2023–24 Scenarios**: State-level baseline projections with contraction (-2%) and expansion (+2%) bounds, filterable by selected state jurisdictions.
* **Interactive Policy Staffing Slider**: Dynamic slider allowing users to adjust the statutory target ratio (from 10.0:1 to 25.0:1) and immediately calculate implied teacher demand and hiring gaps.

---

## 5. Metric Definitions & Formulas

| Metric | Formula | Eligibility Rules |
| :--- | :--- | :--- |
| **Student-to-Teacher Ratio** | `total_students / teacher_fte` | `teacher_fte > 0` and `total_students >= 0`. Yields `NaN` if teacher_fte <= 0. |
| **Weighted Ratio** | `Σ(total_students) / Σ(teacher_fte)` | Aggregated across all eligible schools with non-null staffing. |
| **Enrollment Growth (YoY %)** | `[(students_t - students_t-1) / students_t-1] * 100` | Requires consecutive presence of the same school_id. |
| **Staffing Growth (YoY %)** | `[(teachers_t - teachers_t-1) / teachers_t-1] * 100` | Requires consecutive presence and positive prior-year FTE. |
| **Growth Gap (pp)** | `Enrollment Growth (%) - Staffing Growth (%)` | Positive values indicate enrollment outpacing staffing. |
| **Peer P90 Threshold** | 90th percentile of `(State × School Level)` | Evaluated on operational regular schools with valid ratios. |

---

## 6. Troubleshooting & FAQs

* **Q: Why does a school with 0 reported teachers show up in Priority 1 instead of having a huge ratio?**
  * *A*: Dividing by zero is mathematically undefined. In NCES data, zero reported teachers typically represents administrative non-reporting, contracted staffing, or shared-campus arrangements, which requires data verification.
* **Q: Can I use the forecasted student numbers as exact budget line items?**
  * *A*: No. Projections are baseline planning indicators bounded by scenario bands (+/-2%). Local demographic factors (housing permits, birth rates, local economic shifts) must inform final allocations.
* **Q: Why are American Samoa and Guam excluded from national forecast totals?**
  * *A*: Jurisdictions lacking verified baseline reporting in 2022–23 are explicitly flagged and excluded from forward projections to prevent distorting national totals.
