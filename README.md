# Smart School Resource Planning

Decision-support analytics for public school enrollment trends, teacher staffing allocations, and capacity-related resource pressure across US public elementary and secondary schools.

Based on official NCES Common Core of Data (CCD) annual non-fiscal surveys (school years 2018-19 through 2022-23).

## Implemented Capabilities

- **Configuration Contracts:** Formal machine-readable data contracts governing source specifications, column mappings, identifier standardization, data quality rules, and KPI formulas.
- **Robust Ingestion Pipeline:** Memory-efficient chunked streaming readers with an incremental decoder cascade (`utf-8` -> `windows-1252`) and automated SHA-256 source manifest generation.
- **Data Quality & Validation Suite:** Comprehensive integrity checks covering schema conformity, composite primary key uniqueness `[school_id, school_year]`, directory spine left-join relationship integrity (`1:0..1`), and domain business rules (zero-teacher anomalies, non-reported flags, negative value coercion).
- **Source Auditing & Verification:** Automated execution script (`scripts/01_audit_sources.py`) generating machine-readable audit reports and data quality logs across all 15 raw NCES CCD source files.

## Architecture Overview

The system is organized into modular layers governed by strict configuration data contracts:

```text
smart-school-resource-planning/
├── config/              # Contract layer: sources, mappings, quality rules, KPIs, forecasting
├── data/
│   ├── raw/             # Immutable NCES CCD source CSVs (029 Directory, 052 Membership, 059 Staff)
│   ├── interim/         # Normalized single-source Parquet extracts
│   └── processed/       # Validated longitudinal panel (school_id, school_year) & aggregate tables
├── src/school_planning/ # Core library: ingestion, cleaning, validation, analytics, forecasting
├── scripts/             # Deterministic pipeline execution scripts (01_audit_sources -> 06_generate)
├── app/                 # Interactive Streamlit decision-support dashboard
└── tests/               # Unit and integration test suites validating data contracts and pipeline logic
```

### Reproducible Setup

This project uses the `uv` package manager:

```bash
uv sync --all-extras
uv run pytest -v
uv run ruff check .
```
