# System Runbook & Operations Guide: Smart School Resource Planning

## 1. System Overview & Architecture

The **Smart School Resource Planning System** is a modular, evidence-based data analytics and decision-support platform built on five consecutive years of official National Center for Education Statistics (NCES) Common Core of Data (CCD) non-fiscal annual surveys (**2018–19 through 2022–23**).

The platform transforms raw administrative components (School Directory, Membership/Enrollment, and Staffing) into longitudinal analytical panels, reproducible KPI summaries, a six-tier deterministic resource-pressure triage hierarchy, constrained state-level forecasting benchmarks, executive and technical reports, and an interactive Streamlit decision-support dashboard.

### 1.1 Architecture & Data Flow

```text
Raw Sources (data/raw/)
  ├── 029 Directory CSVs (2018-19 to 2022-23)
  ├── 052 Membership CSVs (2018-19 to 2022-23, ~12M rows/yr)
  └── 059 Staff CSVs (2018-19 to 2022-23)
       │
       ▼ [Stage 1: scripts/01_audit_sources.py]
Source Inventory & SHA-256 Manifest (outputs/quality_reports/)
       │
       ▼ [Stage 2: scripts/02_normalize_data.py]
Interim Cleaned Parquet (data/interim/)
       │
       ▼ [Stage 3: scripts/03_build_panel.py]
Longitudinal Panel: school_year_panel.parquet (data/processed/) [Grain: school_id × school_year]
       │
       ▼ [Stage 4: scripts/04_run_analytics.py]
Augmented Panel & Triage Queues (outputs/tables/ & data/processed/)
       │
       ▼ [Stage 5: scripts/05_run_forecasting.py]
State Backtests & Retrospective 2023-24 Scenarios (outputs/tables/)
       │
       ▼ [Stage 6: scripts/06_generate_deliverables.py]
Publication Figures (outputs/figures/) & Deliverable Reports (deliverables/)
       │
       ▼ [Interactive UI: app/streamlit_app.py]
Streamlit Decision-Support Dashboard
```

---

## 2. Environment Setup & Prerequisites

### 2.1 Technical Prerequisites
* **Operating System**: Windows, macOS, or Linux.
* **Python**: Python 3.12+ (tested with CPython 3.12.11).
* **Package & Environment Manager**: `uv` (fast, deterministic dependency resolution).

### 2.2 Initial Installation
Clone the repository and synchronize dependencies using `uv`:

```powershell
# Synchronize environment with locked dependencies
uv sync --all-extras

# Verify Python version and installation
uv run python --version

# Verify test suite
uv run pytest -v
```

---

## 3. End-to-End Pipeline Execution

The system provides two modes of execution: an **automated orchestrator** (`run_pipeline.py`) that coordinates all pipeline stages sequentially, and **standalone execution scripts** (`scripts/01_*.py` through `scripts/06_*.py`) for targeted stage debugging.

### 3.1 Automated Pipeline Orchestrator

Execute all pipeline stages end-to-end:

```powershell
uv run python src/school_planning/pipeline/run_pipeline.py
```

The orchestrator executes stages 1 through 6 in sequence, logging progress, timings, and error states. If any stage fails, execution halts immediately with a non-zero exit code and displays the exact stderr output from the failed stage.

To run a specific subset of stages (for example, stages 4 to 6):

```powershell
# In Python code or interactive shell:
uv run python -c "from school_planning.pipeline.run_pipeline import run_pipeline; run_pipeline(start_stage=4, end_stage=6)"
```

### 3.2 Individual Pipeline Stages

| Stage | Script Entry Point | Description | Key Inputs | Primary Outputs |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1** | `scripts/01_audit_sources.py` | Audits raw source CSVs, verifies headers and encodings, calculates SHA-256 hashes, and builds the source manifest. | `data/raw/*/*.csv` | `outputs/quality_reports/source_manifest.json`, `outputs/quality_reports/source_audit_report.json` |
| **Stage 2** | `scripts/02_normalize_data.py` | Cleans directory, membership, and staff components. Standardizes IDs, recodes NCES negative codes to NaN, isolates primary membership indicator. | `data/raw/` | `data/interim/*_normalized.parquet` |
| **Stage 3** | `scripts/03_build_panel.py` | Joins normalized components onto Directory spine (`1:0..1` cardinality). Enforces unique composite key `[school_id, school_year]`. | `data/interim/` | `data/processed/school_year_panel.parquet` |
| **Stage 4** | `scripts/04_run_analytics.py` | Computes core KPIs, YoY growth, common-school cohorts, empirical peer group P90 thresholds, and 6-tier triage. | `school_year_panel.parquet` | `school_year_panel_augmented.parquet`, `outputs/tables/*.csv` |
| **Stage 5** | `scripts/05_run_forecasting.py` | Evaluates walk-forward backtests across state time series. Produces retrospective 2023-24 point projections and policy scenarios. | `school_year_panel_augmented.parquet` | `outputs/tables/backtest_model_comparison.csv`, `retrospective_2023_24_projections.csv` |
| **Stage 6** | `scripts/06_generate_deliverables.py` | Generates high-resolution publication charts and compiles markdown deliverable reports. | `school_year_panel_augmented.parquet`, `outputs/tables/` | `outputs/figures/*.png`, `deliverables/*.md` |

---

## 4. Artifact & Output Inventory

### 4.1 Processed Analytical Datasets (`data/processed/`)
* `school_year_panel.parquet`: Cleaned 5-year longitudinal panel (509,924 school-year observations). Primary key: `[school_id, school_year]`.
* `school_year_panel_augmented.parquet`: Analytical panel enriched with YoY growth rates, growth gaps, peer group P90 thresholds, and resource pressure priorities (1–6).

### 4.2 Analytical Tables (`outputs/tables/`)
* `state_annual_aggregates.csv`: Longitudinal state-level totals, student-to-teacher ratios, and triage flags (283 state-year records across 57 jurisdictions).
* `resource_pressure_tier_summary.csv`: Annual and aggregate distribution of facilities across Priority 1 through Priority 6.
* `resource_pressure_triage_queue_p1.csv`: Actionable inspection queue of facilities requiring Administrative Review (missing data, reported 0.0 teacher FTE, negative ratios, boundary shifts).
* `resource_pressure_triage_queue_p2.csv`: Extreme Pressure Queue (regular active schools with ratios at or above the 90th percentile of their state and instructional level peer group).
* `backtest_model_comparison.csv`: Walk-forward validation results (WAPE, MAE, RMSE) across 2 test folds comparing Naive Persistence, Linear Drift, and 3-Year Moving Average.
* `retrospective_2023_24_projections.csv`: Retrospective 2023-24 baseline projections, contraction (-2%) and expansion (+2%) scenario bounds, and implied teacher staffing requirements.

### 4.3 Static Publication Figures (`outputs/figures/`)
* `longitudinal_trends.png`: 5-year dual-axis line chart of national enrollment and teacher FTE trajectories.
* `ratio_distribution.png`: Box-and-whisker ratio distributions across Primary, Middle, High, and Specialized school levels.
* `resource_pressure_tiers.png`: Waterfall bar chart showing distribution of operational schools across Priority 1 through Priority 6.
* `backtest_model_comparison.png`: Bar chart comparing WAPE error rates across candidate forecasting models.
* `retrospective_scenario_projections.png`: Forecast scenario bounds and baseline projections for top state jurisdictions.

### 4.4 Stakeholder Deliverables (`deliverables/`)
* `executive_summary.md`: Non-technical synthesis for superintendents, state education chiefs, and school boards.
* `technical_report.md`: Complete engineering documentation, methodology, formulas, validation results, and data caveats.
* `recommendations.md`: Evidence-based, operational recommendations for staffing audits and resource planning.
* `presentation_outline.md`: Structured slide-by-slide presentation outline for briefings with academic lecturers or executive leadership.

### 4.5 Data Quality & Audit Reports (`outputs/quality_reports/`)
* `source_manifest.json`: Machine-readable file manifest with SHA-256 checksums, byte sizes, row counts, and column schemas for all 15 raw CCD source files.
* `source_inventory.json`: Inventory mirror tracking file locations, year ranges, and component classifications.
* `source_audit_report.json`: Source quality audit findings, schema validations, key uniqueness checks, and Directory spine relationship validations (`status: PASSED`).
* `panel_reconciliation_report.json`: Reconciliation metrics confirming record counts (509,924), unique schools (107,296), and five-year coverage.

---

## 5. Interactive Streamlit Dashboard Operation

### 5.1 Launching the Application
Launch the dashboard locally:

```powershell
uv run streamlit run app/streamlit_app.py
```

By default, the application runs on `http://localhost:8501`.

### 5.2 Navigation & Feature Guide
1. **Sidebar Global Controls**:
   * **School Year**: Select a single year (`2022-23` default) or `All Years`. When `All Years` is selected, snapshot KPI indicator cards explicitly evaluate against the latest verified baseline year (`2022-23`) to prevent invalid cumulative summation of repeated annual counts.
   * **State / Jurisdiction**: Multi-select filter backed by canonical 2-digit NCES FIPS codes (`state_fips`) with state name display labels.
   * **School Level**: Filter by instructional level (`Primary`, `Middle`, `High`, `Other`).
   * **Charter Status**: Filter between `All Schools`, `Non-Charter Only`, and `Charter Only`. Explicit observation filtering excludes unknown/missing charter records without coersion.
   * **Operational Status**: Toggle between `Operational Only` (active schools) and `Include Inactive / Closed`. Metric columns strictly distinguish `operational_schools` from `all_facilities`.
   * **Resource Pressure Tier**: Filter to specific priority tiers (1 through 6).
2. **Dashboard Pages**:
   * **Tab 1: System Overview**: System KPI cards with YoY growth badges, longitudinal trend charts, and school-level ratio box plots.
   * **Tab 2: Geographic Analysis**: Sortable state rankings table and localized deep-dive drill-downs.
   * **Tab 3: Resource Pressure Triage**: Priority tier waterfall chart and interactive triage queues (P1 Administrative Review and P2 Extreme Pressure) with synchronized CSV exports.
   * **Tab 4: Data Quality & Caveats**: NCES negative code mappings, structural break audit documentation, and the class size distinction caveat.
   * **Tab 5: Forecasting & Scenarios**: Statistical feasibility assessment, walk-forward model backtesting comparisons, retrospective 2023-24 state projections, and an interactive policy staffing ratio slider.

---

## 6. Verification & Quality Assurance

Run the automated verification suite:

```powershell
# 1. Run all unit and integration tests (248 tests)
uv run pytest -v

# 2. Check code quality and style
uv run ruff check .

# 3. Verify code formatting
uv run ruff format --check .

# 4. Check Git whitespace and patch integrity
git diff --check
```

### Expected Test Suite Results
* Total tests: **254 passed** (0 failures, 0 errors).
* Test suites:
  * `tests/unit/test_config.py`: 56 configuration and data contract tests.
  * `tests/unit/test_readers.py`: 12 chunked reader, encoding cascade, and adapter tests.
  * `tests/unit/test_cleaning.py`: 17 normalization, missing data, and duplicate tests.
  * `tests/unit/test_validation.py`: 9 schema, primary key, and relationship tests.
  * `tests/unit/test_kpis.py`: 15 KPI formula, zero-denominator, and growth gap tests.
  * `tests/unit/test_resource_pressure.py`: 27 priority hierarchy, P90 peer bypass, and triage queue tests.
  * `tests/unit/test_forecasting.py`: 61 backtesting, temporal gap, entity FIPS key, and scenario tests.
  * `tests/unit/test_reporting.py`: 22 reporting table, chart, deliverable, and operational cohort tests.
  * `tests/unit/test_dashboard.py`: 12 Streamlit filter logic, snapshot semantics, queue alignment, and charter tests.
  * `tests/integration/test_join_integrity.py`: 9 Directory spine join cardinality and unmatched key tests.
  * `tests/integration/test_end_to_end_pipeline.py`: 14 pipeline orchestrator, data flow, output invariant, and skip-semantics tests.

---

## 7. Data Refresh & Maintenance Workflow

When a new academic school year of NCES CCD data is released (e.g., `2023-24`):

1. **Place Raw Files**:
   * Add raw CSVs under `data/raw/` adhering to existing subdirectories:
     * Directory: `data/raw/directory/ccd_sch_029_2324_w_*.csv`
     * Membership: `data/raw/membership/ccd_sch_052_2324_l_*.csv`
     * Staffing: `data/raw/staff/ccd_sch_059_2324_l_*.csv`
2. **Update Configuration Contracts**:
   * Add source file metadata to `config/sources.yaml`.
   * Verify header mapping in `config/column_mapping.yaml`.
   * Extend time range in `config/project.yaml` (`end_year: "2023-24"`).
3. **Execute Pipeline**:
   * Run `uv run python src/school_planning/pipeline/run_pipeline.py`.
4. **Inspect Validation Logs**:
   * Review `outputs/quality_reports/` for source manifests (`source_manifest.json`), source audit validations (`source_audit_report.json`), and panel reconciliation metrics (`panel_reconciliation_report.json`) for any new negative codes, schema variations, or join discrepancies.

---

## 8. Troubleshooting & Common Operational Scenarios

### 8.1 Memory Exhaustion on 052 Membership Files
* **Issue**: 052 Membership source files are large (~2.2–2.5 GB, ~12 million rows each). Reading the full file into memory at once can trigger `MemoryError` or system paging.
* **Resolution**: Ingestion uses `stream_csv_chunks()` in `src/school_planning/ingestion/readers.py` with `chunksize=100,000`. Only the primary indicator (`Derived - Education Unit Total minus Adult Education Count`) is retained, reducing memory footprint by >95%.

### 8.2 Character Encoding Exceptions
* **Issue**: NCES source files across different survey years mix UTF-8 and Windows-1252/ANSI encodings, leading to `UnicodeDecodeError`.
* **Resolution**: The readers implement a deterministic encoding cascade: UTF-8 is attempted first; on `UnicodeDecodeError`, it falls back to `windows-1252`. Leading `latin-1` is strictly prohibited.

### 8.3 State-Level Structural Reporting Breaks
* **Issue**: Historical teacher FTE reports in certain states exhibit abrupt non-reporting breaks (e.g., California 2019–20 reported 0.0 FTE statewide; Illinois 2020–21 did not collect teacher counts).
* **Resolution**: The pipeline detects zero and missing teacher submissions, routes affected facilities to Priority 1 (Administrative Review), and suppresses invalid growth rates (`NaN`) rather than computing misleading infinite or -100% changes.

### 8.4 Streamlit Port or Browser Connection Issues
* **Issue**: Port 8501 is occupied or running in a headless server environment.
* **Resolution**: Run with explicit port and headless flags:
  ```powershell
  uv run streamlit run app/streamlit_app.py --server.port 8502 --server.headless true
  ```

### 8.5 Source Manifest Verification and Quality Audit Inspection
* **Issue**: Operators need to verify source data integrity, SHA-256 checksums, schema column counts, or Directory spine join relationships after ingesting or modifying raw files.
* **Resolution**: Review the generated audit reports in `outputs/quality_reports/`:
  - `outputs/quality_reports/source_manifest.json`: Inspect computed SHA-256 hashes, file sizes, and raw row counts.
  - `outputs/quality_reports/source_audit_report.json`: Verify that `status` is `PASSED`, `errors` count is 0, and inspect relationship validation checks across components.
  - `outputs/quality_reports/panel_reconciliation_report.json`: Verify that the assembled longitudinal panel matches expected annual school counts and unique school identifier counts.
