# Smart School Resource Planning

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Environment: uv](https://img.shields.io/badge/environment-uv-purple.svg)](https://docs.astral.sh/uv/)
[![Code Style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-green.svg)](https://docs.pytest.org/)

An evidence-based decision-support system and analytical data pipeline for evaluating student enrollment trends, teacher staffing allocations, and capacity-related resource pressure across US public elementary and secondary schools.

Built upon five consecutive academic school years (**2018–19 through 2022–23**) of official National Center for Education Statistics (NCES) Common Core of Data (CCD) non-fiscal surveys.

---

## 1. Project Overview & Business Value

State Education Agencies (SEAs), district superintendents, and school boards face significant operational challenges balancing instructional capacity against shifting student populations. Administrative datasets often obscure actionable insights beneath reporting anomalies, structural breaks, and inconsistent definitions.

This system provides:
1. **Longitudinal System Auditing**: Tracks national and state-level enrollment and staffing trajectories across 509,924 school-year observations.
2. **Deterministic Resource Pressure Triage**: Implements a transparent, six-tier decision hierarchy that separates administrative non-reporting from empirical extreme pressure (P90 of national instructional level peer groups).
3. **Constrained Scenario Planning**: Delivers statistically defensible state-level retrospective forecasts and policy-driven implied staffing demand calculations.
4. **Interactive Decision Support**: Empowers stakeholders with a multi-page Streamlit application and comprehensive executive reporting deliverables.

---

## 2. Core Architectural Capabilities

* **Configuration Data Contracts (`config/`)**: Strict YAML schemas governing composite primary keys `[school_id, school_year]`, directory spine left-join cardinalities (`1:0..1`), ID zero-padding, indicator filtering, and KPI eligibility rules.
* **Memory-Efficient Streaming Ingestion (`src/school_planning/ingestion/`)**: Chunked streaming readers with an automatic encoding fallback cascade (`utf-8` -> `windows-1252`) capable of processing large membership files (~12M rows/yr) under low memory footprints.
* **Data Cleaning & Panel Construction (`src/school_planning/cleaning/`, `transformation/`)**: Deterministic recoding of NCES negative codes (`-1`, `-2`, `-9`, `-11` -> `NaN`), zero-teacher anomaly flags, and preservation of common-school cohorts for period-over-period growth.
* **Deterministic Triage Hierarchy (`src/school_planning/analytics/`)**: Six mutually exclusive priority tiers:
  * **Priority 1**: Administrative Data Review (missing values, 0.0 teacher FTE, boundary/agency changes, negative ratios).
  * **Priority 2**: Extreme Pressure (operational regular schools at or above the 90th percentile of their national peer group by school level and year).
  * **Priority 3**: Rapidly Rising Ratio ($\ge 15.0\%$ annual increase, provisional baseline).
  * **Priority 4**: Staffing Deficit Growth Gap (enrollment growth outpacing staffing growth by $\ge 5$ percentage points).
  * **Priority 5**: Growth Unassessed (new schools, boundary reconfigurations, or missing prior-year data).
  * **Priority 6**: Stable / Balanced Trend (verified non-escalating indicators).
* **Constrained Forecasting & Backtesting (`src/school_planning/forecasting/`)**: Statistical boundary analysis demonstrating why micro-level school forecasting over $T=5$ is invalid, paired with state-level walk-forward backtesting (WAPE, MAE, RMSE) and retrospective 2023–24 scenario bands.
* **Streamlit Decision Dashboard (`app/`)**: Full-featured interactive UI providing longitudinal trends, localized FIPS drill-downs, filtered triage queues with verified CSV downloads, data quality audits, and interactive policy ratio simulations.
* **Pipeline Orchestrator (`src/school_planning/pipeline/run_pipeline.py`)**: Central workflow runner coordinating sequential execution from raw source auditing to final document compilation.

---

## 3. Repository Structure

```text
smart-school-resource-planning/
├── app/                              # Streamlit decision-support application
│   ├── components/                   # Reusable UI modules (filters, KPI cards, charts)
│   └── streamlit_app.py              # Main dashboard entry point (5 tabs)
├── config/                           # Machine-readable data contracts & configuration
│   ├── column_mapping.yaml           # Canonical header normalization mappings
│   ├── forecasting.yaml              # Feasibility bounds, backtest folds & scenario rules
│   ├── kpi_definitions.yaml          # Mathematical KPI formulas & triage criteria
│   ├── project.yaml                  # Primary keys, temporal scope & scoping buckets
│   ├── quality_rules.yaml            # Validation thresholds & anomaly rules
│   └── sources.yaml                  # Source file inventory & SHA-256 contracts
├── data/                             # Data directory (managed & Git-ignored)
│   ├── raw/                          # Raw NCES CCD CSVs (029 Directory, 052 Membership, 059 Staff)
│   ├── interim/                      # Normalized single-component Parquet extracts
│   └── processed/                    # Validated analytical panels (school_year_panel.parquet)
├── deliverables/                     # Compiled stakeholder reports
│   ├── executive_summary.md          # High-level findings for superintendents & boards
│   ├── technical_report.md           # Engineering documentation & methodology
│   ├── recommendations.md            # Actionable resource allocation recommendations
│   └── presentation_outline.md       # Executive briefing slide structure
├── docs/                             # Architecture & operations documentation
│   ├── assumptions_and_decisions.md  # Architectural Decision Records (ADRs)
│   ├── business_requirements.md      # Stakeholder requirements & BQs
│   ├── dashboard_guide.md            # User & administrator dashboard guide
│   ├── data_dictionary.md            # Schema definitions, grains & data types
│   ├── data_quality_and_cleaning_log.md # Historical audit log of anomalies & cleaning actions
│   ├── data_sources.md               # Source URLs, survey notes & retrieval details
│   ├── project_charter.md            # Product purpose, scope & boundaries
│   ├── runbook.md                    # Complete operations and troubleshooting runbook
│   └── stakeholder_workflows.md      # Decision trees & stakeholder role workflows
├── outputs/                          # Generated analytical outputs (Git-ignored)
│   ├── figures/                      # High-resolution publication figures (PNG)
│   └── tables/                       # Processed summary tables & triage queue CSVs
├── scripts/                          # Deterministic pipeline execution entry points
│   ├── 01_audit_sources.py           # Stage 1: Inspect raw inputs & build manifest
│   ├── 02_normalize_data.py          # Stage 2: Normalize components to interim Parquet
│   ├── 03_build_panel.py             # Stage 3: Build validated analytical panel
│   ├── 04_run_analytics.py           # Stage 4: Calculate KPIs & triage queues
│   ├── 05_run_forecasting.py         # Stage 5: Run backtesting & 2023-24 scenarios
│   └── 06_generate_deliverables.py   # Stage 6: Produce figures & assemble reports
├── src/school_planning/              # Core reusable Python library
│   ├── analytics/                    # KPIs, growth, distributions, resource pressure
│   ├── cleaning/                     # Normalization, missing values, duplicates
│   ├── forecasting/                  # Baselines, models, backtesting, scenarios
│   ├── ingestion/                    # Readers, source adapters, manifest builder
│   ├── pipeline/                     # Workflow coordinator (run_pipeline.py)
│   ├── reporting/                    # Tables, charts, report assembly
│   ├── transformation/               # Directory, membership, staff normalization
│   └── validation/                   # Schema, key, relationship, business rule checks
├── tests/                            # Automated test suite (255 tests)
│   ├── fixtures/                     # Synthetic test CSVs
│   ├── integration/                  # Join integrity & end-to-end pipeline tests
│   └── unit/                         # Focused unit test suites
├── pyproject.toml                    # Package metadata & tool configurations
└── uv.lock                           # Deterministic dependency lockfile
```

---

## 4. Quick Start & Execution

### 4.1 Prerequisites & Installation
Ensure Python 3.12+ and `uv` are installed:

```powershell
# Synchronize environment with locked dependencies
uv sync --all-extras
```

### 4.2 Running the End-to-End Pipeline
Execute the full data pipeline from raw source verification to deliverable report assembly:

```powershell
uv run python src/school_planning/pipeline/run_pipeline.py
```

### 4.3 Launching the Interactive Dashboard
Launch the decision-support Streamlit application locally:

```powershell
uv run python -m streamlit run app/streamlit_app.py
```
Open `http://localhost:8501` in your browser.

### 4.4 Running Verification & Quality Checks
Execute the automated test suite and static analysis:

```powershell
# Run the complete test suite (255 tests)
uv run pytest -v

# Run Ruff linter
uv run ruff check .

# Check formatting
uv run ruff format --check .
```

---

## 5. Methodological Notes & Key Caveats

1. **Student-to-Teacher Ratio vs. Class Size**: The student-to-teacher ratio is an aggregate resource allocation metric (total enrolled students divided by total instructional teacher FTE). It does **not** measure average class size. It includes specialized, itinerant, and non-classroom instructional staff.
2. **Forecasting Feasibility Boundary**: With annual observations over $T=5$ school years, micro-level school forecasting exhibits high parameter instability and noise. Forecasting is strictly constrained to state-level aggregates, using simple, transparent benchmarks (Naive Persistence and Linear Drift) verified through walk-forward backtesting.
3. **Operational Cohort Semantics**: Metric columns strictly distinguish `operational_schools` (active facilities where `is_operational == True`) from `all_facilities`. Inactive/closed facilities do not inflate operational-cohort priority distributions.
4. **Structural Reporting Breaks**: Specific historical anomalies (e.g., California 2019–20 reporting 0.0 teacher FTE; Illinois 2020–21 missing teacher collections) are explicitly flagged and routed to Priority 1 (Administrative Review) rather than generating misleading growth metrics.

---

## 6. License & Citation
* **Data Sources**: US Department of Education, National Center for Education Statistics (NCES), Common Core of Data (CCD), 2018–19 through 2022–23.
* **Code License**: Open source for research, evaluation, and portfolio demonstration.
