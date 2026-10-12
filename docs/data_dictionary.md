# Data Dictionary

**Last updated:** Phase 1 Data Contract — 2026-10-12<br>
**Status:** Phase 1 Data Contract established; configuration schemas and analytical field mappings formalized.<br>
**Ingestion Note:** Full multi-year 052 Membership parsing and filtering deferred to Phase 2 pipeline.

---

## Overview

This dictionary documents the fields in the three NCES CCD source components present in the workspace. All field names are taken directly from the CSV headers. Data types are inferred from observed sample values; official type specifications require the NCES record layout documents (not available locally during this audit).

**Character encoding note:** Character encoding across all raw source files is **unverified**. Strict UTF-8 validation has not been performed; non-UTF-8 bytes (such as Windows-1252 byte `0x96` en-dash in the 2018-19 Directory file) were observed. Decoding errors must not be silently discarded; robust encoding handling is deferred to the Phase 2 ingestion pipeline.

**Grain definitions:**
- **029 Directory:** One row per school per school year (`NCESSCH` + `SCHOOL_YEAR`)
- **059 Staff:** One row per school per school year (`NCESSCH` + `SCHOOL_YEAR`) — all rows have `TOTAL_INDICATOR = 'Education Unit Total'`
- **052 Membership (raw):** Multiple rows per school per year (disaggregated by grade, race/ethnicity, sex, and total-indicator level)
- **052 Membership (filtered):** One row per school per year when filtered to a designated school-level total indicator (`Education Unit Total` or `Derived - Education Unit Total minus Adult Education Count`)

---

## Component 029 — School Directory

**File format:** Wide CSV  
**Columns:** 65  
**Key:** `NCESSCH` (unique per year within this file)

| # | Field Name | Observed Type | Description | Notes |
|---|-----------|--------------|-------------|-------|
| 1 | `SCHOOL_YEAR` | String | School year label (e.g., `'2018-2019'`) | Format: YYYY-YYYY |
| 2 | `FIPST` | String (2-char) | State FIPS code | Leading zeros: `'01'` = Alabama |
| 3 | `STATENAME` | String | Full state name | |
| 4 | `ST` | String (2-char) | State abbreviation | |
| 5 | `SCH_NAME` | String | School name | |
| 6 | `LEA_NAME` | String | Local Education Agency (district) name | |
| 7 | `STATE_AGENCY_NO` | String | State agency number | |
| 8 | `UNION` | String | Union/cooperative identifier | Often empty |
| 9 | `ST_LEAID` | String | State-assigned LEA identifier | Format: `ST-NNN` |
| 10 | `LEAID` | String (7-char) | NCES LEA (district) identifier | 7-digit, zero-padded — **read as string** |
| 11 | `ST_SCHID` | String | State-assigned school identifier | Format: `ST-NNN-NNNN` |
| 12 | `NCESSCH` | String (12-char) | NCES school identifier (primary key) | 12-digit, zero-padded — **read as string** |
| 13 | `SCHID` | String (7-char) | NCES school identifier | Empirically observed as `FIPST + NCESSCH[-5:]` (7 chars). Note: Officially documented by NCES as a 5-digit code within LEAID; release-specific layout unconfirmed without official codebook. **Not** the last 7 chars of `NCESSCH`. |
| 14 | `MSTREET1` | String | Mailing address line 1 | |
| 15 | `MSTREET2` | String | Mailing address line 2 | Often empty |
| 16 | `MSTREET3` | String | Mailing address line 3 | Often empty |
| 17 | `MCITY` | String | Mailing city | |
| 18 | `MSTATE` | String (2-char) | Mailing state abbreviation | |
| 19 | `MZIP` | String (5-char) | Mailing ZIP code | Read as string to preserve leading zeros |
| 20 | `MZIP4` | String (4-char) | Mailing ZIP+4 extension | Often empty |
| 21 | `LSTREET1` | String | Location address line 1 | |
| 22 | `LSTREET2` | String | Location address line 2 | Often empty |
| 23 | `LSTREET3` | String | Location address line 3 | Often empty |
| 24 | `LCITY` | String | Location city | |
| 25 | `LSTATE` | String (2-char) | Location state abbreviation | |
| 26 | `LZIP` | String (5-char) | Location ZIP code | Read as string |
| 27 | `LZIP4` | String (4-char) | Location ZIP+4 extension | Often empty |
| 28 | `PHONE` | String | School phone number | |
| 29 | `WEBSITE` | String | School website URL | |
| 30 | `SY_STATUS` | Integer code | School operational status code | Numeric code; use `SY_STATUS_TEXT` for analysis |
| 31 | `SY_STATUS_TEXT` | String | School operational status label | See domain below |
| 32 | `UPDATED_STATUS` | Integer code | Updated operational status code | |
| 33 | `UPDATED_STATUS_TEXT` | String | Updated operational status label | |
| 34 | `EFFECTIVE_DATE` | String (date) | Date status became effective | Format: MM/DD/YYYY |
| 35 | `SCH_TYPE_TEXT` | String | School type label | See domain below |
| 36 | `SCH_TYPE` | Integer code | School type code | |
| 37 | `RECON_STATUS` | String | Reconciliation status | |
| 38 | `OUT_OF_STATE_FLAG` | String | Out-of-state school flag | `'Yes'` / `'No'` |
| 39 | `CHARTER_TEXT` | String | Charter school indicator | `'Yes'` / `'No'` |
| 40 | `CHARTAUTH1` | String | Charter authorization entity 1 | Often empty |
| 41 | `CHARTAUTHN1` | String | Charter authorization name 1 | Often empty |
| 42 | `CHARTAUTH2` | String | Charter authorization entity 2 | Often empty |
| 43 | `CHARTAUTHN2` | String | Charter authorization name 2 | Often empty |
| 44 | `NOGRADES` | String | School with no grade levels offered | `'Yes'` / `'No'` |
| 45 | `G_PK_OFFERED` | String | Pre-K grade offered | `'Yes'` / `'No'` |
| 46 | `G_KG_OFFERED` | String | Kindergarten offered | `'Yes'` / `'No'` |
| 47 | `G_1_OFFERED` | String | Grade 1 offered | `'Yes'` / `'No'` |
| 48 | `G_2_OFFERED` | String | Grade 2 offered | `'Yes'` / `'No'` |
| 49 | `G_3_OFFERED` | String | Grade 3 offered | `'Yes'` / `'No'` |
| 50 | `G_4_OFFERED` | String | Grade 4 offered | `'Yes'` / `'No'` |
| 51 | `G_5_OFFERED` | String | Grade 5 offered | `'Yes'` / `'No'` |
| 52 | `G_6_OFFERED` | String | Grade 6 offered | `'Yes'` / `'No'` |
| 53 | `G_7_OFFERED` | String | Grade 7 offered | `'Yes'` / `'No'` |
| 54 | `G_8_OFFERED` | String | Grade 8 offered | `'Yes'` / `'No'` |
| 55 | `G_9_OFFERED` | String | Grade 9 offered | `'Yes'` / `'No'` |
| 56 | `G_10_OFFERED` | String | Grade 10 offered | `'Yes'` / `'No'` |
| 57 | `G_11_OFFERED` | String | Grade 11 offered | `'Yes'` / `'No'` |
| 58 | `G_12_OFFERED` | String | Grade 12 offered | `'Yes'` / `'No'` |
| 59 | `G_13_OFFERED` | String | Grade 13 (post-secondary) offered | `'Yes'` / `'No'` |
| 60 | `G_UG_OFFERED` | String | Ungraded programs offered | `'Yes'` / `'No'` |
| 61 | `G_AE_OFFERED` | String | Adult education offered | `'Yes'` / `'No'` |
| 62 | `GSLO` | String | Lowest grade offered (e.g., `'07'`, `'KG'`, `'PK'`) | |
| 63 | `GSHI` | String | Highest grade offered | |
| 64 | `LEVEL` | String | School level classification | See domain below |
| 65 | `IGOFFERED` | String | Instruction grades offered indicator | e.g., `'As reported'` |

> **Note:** The header contains exactly 65 columns, verified across all 5 school years (2018-19 through 2022-23). Rows 1–65 above document each field in exact order.

### 029 Domain Values (Verified from 2022-23)

**`SY_STATUS_TEXT` (school operational status):**
| Value | Count (2022-23) | Meaning |
|-------|----------------|---------|
| `'Open'` | 99,528 | Active school |
| `'New'` | 890 | Newly opened this year |
| `'Closed'` | 878 | Closed this year |
| `'Inactive'` | 480 | Temporarily inactive |
| `'Future'` | 339 | Not yet open |
| `'Added'` | 74 | Added to CCD this year |
| `'Changed Boundary/Agency'` | 57 | Geographic or agency change |
| `'Reopened'` | 22 | Reopened after closure |

**`SCH_TYPE_TEXT` (school type):**
| Value | Count (2022-23) |
|-------|----------------|
| `'Regular School'` | 92,875 |
| `'Alternative School'` | 5,811 |
| `'Special Education School'` | 1,950 |
| `'Career and Technical School'` | 1,632 |

**`LEVEL` (school level):**
| Value | Count (2022-23) |
|-------|----------------|
| `'Elementary'` | 53,187 |
| `'High'` | 23,627 |
| `'Middle'` | 16,415 |
| `'Other'` | 4,475 |
| `'Not reported'` | 2,086 |
| `'Prekindergarten'` | 1,587 |
| `'Secondary'` | 443 |
| `'Not applicable'` | 287 |
| `'Ungraded'` | 140 |
| `'Adult Education'` | 21 |

---

## Component 059 — School Staff FTE

**File format:** Long CSV  
**Columns:** 15  
**Key:** `NCESSCH` + `SCHOOL_YEAR` (one row per school per year in these files)

| # | Field Name | Observed Type | Description | Notes |
|---|-----------|--------------|-------------|-------|
| 1 | `SCHOOL_YEAR` | String | School year label | Format: `'2018-2019'` |
| 2 | `FIPST` | String (2-char) | State FIPS code | |
| 3 | `STATENAME` | String | Full state name | |
| 4 | `ST` | String (2-char) | State abbreviation | |
| 5 | `SCH_NAME` | String | School name | |
| 6 | `STATE_AGENCY_NO` | String | State agency number | |
| 7 | `UNION` | String | Union/cooperative identifier | Often empty |
| 8 | `ST_LEAID` | String | State-assigned LEA identifier | |
| 9 | `LEAID` | String (7-char) | NCES LEA (district) identifier | **Read as string** |
| 10 | `ST_SCHID` | String | State-assigned school identifier | |
| 11 | `NCESSCH` | String (12-char) | NCES school identifier (primary key) | **Read as string** |
| 12 | `SCHID` | String (7-char) | NCES school identifier | Empirically observed as `FIPST + NCESSCH[-5:]` (7 chars). Note: Officially documented as 5-digit code within LEAID; release-specific layout unconfirmed without official codebook. **Not** the last 7 chars of `NCESSCH`. |
| 13 | `TEACHERS` | Float | Full-time equivalent (FTE) teacher count | See quality notes below |
| 14 | `TOTAL_INDICATOR` | String | Aggregation level | Always `'Education Unit Total'` in these files |
| 15 | `DMS_FLAG` | String | Data missingness/suppression flag | See domain below |

### 059 Quality Observations (2018-19 verified)

| Metric | Value |
|--------|-------|
| Total rows | 99,911 |
| Unique `NCESSCH` | 99,911 (each school appears exactly once) |
| `NCESSCH` nulls | 0 |
| `TOTAL_INDICATOR` values | `'Education Unit Total'` only |
| `TEACHERS` valid numeric rows | 96,780 |
| `TEACHERS` missing/null rows | 3,131 (3.1%) |
| `TEACHERS` minimum | 0.0 |
| `TEACHERS` maximum | 1,050.0 |
| `TEACHERS` median | 27.62 |
| `TEACHERS` zero values | 1,427 |
| `TEACHERS` negative values | 0 |

**`DMS_FLAG` domain (2018-19 and 2022-23 verified):**
| Value | 2018-19 count | 2022-23 count | Meaning |
|-------|--------------|--------------|---------|
| `'Reported'` | 96,780 | 97,537 | Valid numeric TEACHERS value |
| `'Missing'` | 2,225 | 1,733 | Data not collected or available |
| `'Not reported'` | 749 | 1,098 | State chose not to report |
| `'Suppressed'` | 157 | 203 | Withheld for privacy (small n) |

> **Critical:** Non-`'Reported'` DMS_FLAG rows must not have their `TEACHERS` value treated as zero. They must be handled as missing values in the analytical pipeline.

> **Note on TEACHERS = 0.0:** Zero FTE values when `DMS_FLAG = 'Reported'` represent schools that reported having zero teachers (e.g., schools in administrative transition or reporting anomalies). These are valid reported values but require interpretive care.

---

## Component 052 — School Membership (Enrollment)

**File format:** Long CSV  
**Columns:** 18  
**Key (raw):** `NCESSCH` + `SCHOOL_YEAR` + `GRADE` + `RACE_ETHNICITY` + `SEX` + `TOTAL_INDICATOR`  
**Key (filtered):** `NCESSCH` + `SCHOOL_YEAR` when filtered to a school-level total indicator (`Education Unit Total` or `Derived - Education Unit Total minus Adult Education Count`)

| # | Field Name | Observed Type | Description | Notes |
|---|-----------|--------------|-------------|-------|
| 1 | `SCHOOL_YEAR` | String | School year label | Format: `'2018-2019'` |
| 2 | `FIPST` | String (2-char) | State FIPS code | |
| 3 | `STATENAME` | String | Full state name | |
| 4 | `ST` | String (2-char) | State abbreviation | |
| 5 | `SCH_NAME` | String | School name | |
| 6 | `STATE_AGENCY_NO` | String | State agency number | |
| 7 | `UNION` | String | Union/cooperative identifier | Often empty |
| 8 | `ST_LEAID` | String | State-assigned LEA identifier | |
| 9 | `LEAID` | String (7-char) | NCES LEA (district) identifier | **Read as string** |
| 10 | `ST_SCHID` | String | State-assigned school identifier | |
| 11 | `NCESSCH` | String (12-char) | NCES school identifier | **Read as string** |
| 12 | `SCHID` | String (7-char) | NCES school identifier | Empirically observed as `FIPST + NCESSCH[-5:]` (7 chars). Note: Officially documented as 5-digit code within LEAID; release-specific layout unconfirmed without official codebook. **Not** the last 7 chars of `NCESSCH`. |
| 13 | `GRADE` | String | Grade level label | e.g., `'Grade 3'`, `'Kindergarten'`, `'No Category Codes'` |
| 14 | `RACE_ETHNICITY` | String | Race/ethnicity category | e.g., `'American Indian or Alaska Native'` |
| 15 | `SEX` | String | Sex category | e.g., `'Female'`, `'Male'` |
| 16 | `STUDENT_COUNT` | Integer / Empty string | Student enrollment count for this disaggregation | Non-numeric entries observed as empty string `""` in CSV; suppression/missingness code recorded in `DMS_FLAG` |
| 17 | `TOTAL_INDICATOR` | String | Aggregation level of this row | Disaggregated rows must be excluded; school-level total choice (`Education Unit Total` vs `Derived - EU Total minus AE`) deferred to Phase 1 data contract |
| 18 | `DMS_FLAG` | String | Data missingness/suppression flag | Unverified full domain across 5 years; sample observations include `Reported`, `Missing`, `Not reported`, `Suppressed`, `Derived`, `Manual adjustment` |

### 052 Quality Observations (2018-19, full-file scan verified)

| Metric | Value |
|--------|-------|
| Total rows in file | 11,948,167 |
| `TOTAL_INDICATOR = 'Education Unit Total'` rows | 99,533 |
| `STUDENT_COUNT` valid (numeric) | 99,236 (99.7%) |
| `STUDENT_COUNT` missing | 297 (0.3%) |
| `STUDENT_COUNT` minimum | 0 |
| `STUDENT_COUNT` maximum | 14,306 |
| `STUDENT_COUNT` median | 430 |
| Schools with zero enrollment | 2,665 |

> **Note on zero-enrollment schools:** 2,665 schools report `STUDENT_COUNT = 0` with `TOTAL_INDICATOR = 'Education Unit Total'`. These may represent newly opened, recently closed, or administrative-only schools. They should not be automatically excluded — their `SY_STATUS_TEXT` in the directory should be checked to understand their status.



| Value | Count (2018-19, full file) | Meaning |
|-------|---------------------------|---------|
| `'Category Set A - By Race/Ethnicity; Sex; Grade'` | 9,528,008 | Disaggregated detail row |
| `'Derived - Subtotal by Race/Ethnicity and Sex minus Adult Education Count'` | 1,492,995 | Derived subtotal |
| `'Subtotal 4 - By Grade'` | 728,098 | Grade subtotal |
| `'Derived - Education Unit Total minus Adult Education Count'` | 99,533 | Derived school total (excluding Adult Education) |
| `'Education Unit Total'` | 99,533 | Education unit school total (including Adult Education) |

> **Comparison of School-Level Totals:** In the 2018-19 file, `'Education Unit Total'` and `'Derived - Education Unit Total minus Adult Education Count'` each contain exactly 99,533 rows. Set equality of their school cohorts (`NCESSCH`) was explicitly verified for 2018-19 (both contain the identical 99,533 schools with 0 difference in either direction). Cohort equivalence across 2019-20 through 2022-23 remains unverified until Phase 2 ingestion. They embody two distinct enrollment concepts:
> - `'Education Unit Total'`: Comprehensive enrollment count across all programs at the school, including adult education students if reported.
> - `'Derived - Education Unit Total minus Adult Education Count'`: Enrollment count excluding adult education students, reflecting standard pre-K through grade 12 student body load.
>
> **Data Contract Decision (Phase 1):** Neither total should be asserted as universally the only valid school-level total. The choice of which indicator defines the primary enrollment KPI will be formally specified in the Phase 1 data contract based on business requirements.
>
> **Critical Filtering Rule:** Ingestion and cleaning pipelines must filter out all disaggregated detail and subtotal rows (`'Category Set A...'`, `'Subtotal 4...'`, and `'Derived - Subtotal...'`) to prevent double-counting. Aggregating across multiple indicator categories would inflate enrollment counts by ~120×.

### 052 GRADE Domain (first 200,000 rows, 2018-19)

`'Grade 1'` through `'Grade 12'`, `'Kindergarten'`, `'Pre-Kindergarten'`, `'No Category Codes'` (used in total rows), `'Not Specified'`

### 052 File Size Context

The 052 membership files are the largest in the workspace (~2.2–2.3 GB each). Full-file processing requires:
- Streaming/chunked reading — never load entirely into memory at once
- Filter to a designated school-level total indicator as early as possible in the pipeline
- Consider producing a pre-filtered interim Parquet file (~100K rows per year) in Phase 2

---

## Identifier Cross-Reference

| Field | Length | Type | Present in | Notes |
|-------|--------|------|-----------|-------|
| `NCESSCH` | 12 chars | String | 029, 052, 059 | Primary join key across all components |
| `LEAID` | 7 chars | String | 029, 052, 059 | District-level join key |
| `SCHID` | 7 chars | String | 029, 052, 059 | Empirically observed as `FIPST + NCESSCH[-5:]`. Officially defined as 5 digits. **Not** the last 7 chars of `NCESSCH`. |
| `FIPST` | 2 chars | String | 029, 052, 059 | State FIPS code |
| `ST` | 2 chars | String | 029, 052, 059 | State abbreviation |
| `ST_LEAID` | Variable | String | 029, 052, 059 | State-assigned LEA ID (format varies by state) |
| `ST_SCHID` | Variable | String | 029, 052, 059 | State-assigned school ID |
| `SCHOOL_YEAR` | 9 chars | String | 029, 052, 059 | Format: `'YYYY-YYYY'` |

### Identifier Structure and Relationships

- **`NCESSCH` (12 chars):** `FIPST` (2 chars) + LEA code (5 chars) + School code (5 chars) = `LEAID` (7 chars) + `SCHID[-5:]` (5 chars).
- **`LEAID` (7 chars):** `FIPST` (2 chars) + LEA code (5 chars) = `NCESSCH[:7]`.
- **`SCHID` distinction between official definition and empirical data:**
  - *Official definition:* In federal NCES CCD documentation, `SCHID` is defined as a 5-digit NCES-assigned school identifier within the LEA that appends to `LEAID` (7 chars) to produce `NCESSCH` (12 chars).
  - *Observed empirical data:* In the 15 raw CSV releases present in this workspace, `SCHID` is formatted as a 7-character string mathematically equal to `FIPST + NCESSCH[-5:]` (0 mismatches across 102k+ rows in 2018-19 and 2022-23). Note: `SCHID` does **not** equal the last 7 characters of `NCESSCH` (`NCESSCH[-7:]`). The exact release-specific layout reason remains unconfirmed without matching release codebooks.

### Joining the three components

The intended join strategy for the analytical panel is:

```
029 (Directory) 
  LEFT JOIN 059 (Staff)      ON NCESSCH + SCHOOL_YEAR
  LEFT JOIN 052 (Membership) ON NCESSCH + SCHOOL_YEAR  [pre-filtered to agreed school-level total indicator]
```

Expected cardinality:
- 029 → 059: Many-to-one (not all directory schools have a staff row) → left join preserves directory schools
- 029 → 052: Many-to-one after 052 filtering (not all directory schools have an enrollment row) → left join
- Result grain: one row per school per year (verified post-join — see Phase 2)

---

## Fields Proposed for the Analytical Panel

These are **candidate fields** for the school-year panel. Final inclusion depends on Phase 1 data contract decisions.

| Internal Name | Source File | Source Column | Notes |
|---------------|------------|---------------|-------|
| `school_id` | 029 | `NCESSCH` | Primary identifier |
| `district_id` | 029 | `LEAID` | District identifier |
| `state_code` | 029 | `ST` | State abbreviation |
| `state_fips` | 029 | `FIPST` | State FIPS code |
| `school_year` | 029 | `SCHOOL_YEAR` | Standardized year label |
| `school_name` | 029 | `SCH_NAME` | School name |
| `district_name` | 029 | `LEA_NAME` | District name |
| `school_status` | 029 | `SY_STATUS_TEXT` | Operational status (candidate scoping rule, e.g. Open/New vs Inactive/Closed, to be decided in Phase 1 contract) |
| `school_type` | 029 | `SCH_TYPE_TEXT` | School type category |
| `school_level` | 029 | `LEVEL` | Level (Elementary/Middle/High/etc.) |
| `grade_low` | 029 | `GSLO` | Lowest grade offered |
| `grade_high` | 029 | `GSHI` | Highest grade offered |
| `is_charter` | 029 | `CHARTER_TEXT` | Charter school flag |
| `total_students` | 052 | `STUDENT_COUNT` (filtered) | School-level enrollment total (choice between EU Total and Derived without AE deferred to Phase 1 data contract) |
| `teacher_fte` | 059 | `TEACHERS` | Teacher FTE |
| `teacher_data_flag` | 059 | `DMS_FLAG` | Missingness/suppression flag for TEACHERS |

---

## Fields Marked for Further Investigation

| Field / Topic | Component | Status | Phase 1 Contract Decision / Investigation |
|---------------|-----------|--------|-------------------------------------------|
| `TOTAL_INDICATOR` | 052 | Resolved (Phase 1) | **Contract Decision:** Primary operational indicator is `Derived - Education Unit Total minus Adult Education Count`. `Education Unit Total` retained for comparative audit. Excludes adult education from K-12 operational headcount. |
| `DMS_FLAG` | 052 | Deferred (Phase 2) | Full domain across 12M rows and 5 years is unverified; sample rows show `Reported`, `Missing`, `Not reported`, `Suppressed`, `Derived`, `Manual adjustment`. Full profiling deferred to Phase 2. |
| `STUDENT_COUNT` | 052 | Deferred (Phase 2) | Non-numeric entries observed as empty strings `""` in CSV with suppression/missingness code in `DMS_FLAG`. Full 5-year missingness counts deferred to Phase 2. |
| `Character encoding` | All (029, 052, 059) | Resolved (Phase 1) | **Contract Policy:** Multi-encoding cascade (strict UTF-8 with fallback to Windows-1252). Silent error suppression (`errors='ignore'`) prohibited in Phase 2 ingestion. |
| `SCHID formatting` | All (029, 052, 059) | Resolved (Phase 1) | **Contract Policy:** `NCESSCH` (12 chars) is the primary key. `SCHID` retained as raw audit string but prohibited as join key due to empirical discrepancy (`FIPST + NCESSCH[-5:]`). |
| `TEACHERS = 0.0` | 059 | Resolved (Phase 1) | **Contract Decision:** Valid reported zeros retained in panel with flag `zero_teacher_anomaly = True`. Ratio denominator evaluates to null (`NaN`), never infinite. Non-reported flags remain null. |
| `SY_STATUS_TEXT` | 029 | Resolved (Phase 1) | **Contract Decision:** Full population preserved in analytical panel with boolean scoping flag `is_operational = (SY_STATUS_TEXT in ['Open', 'New'])`. Core operational KPIs filter on operational cohort. |
| `LEVEL = 'Not reported'` | 029 | Deferred (Phase 2) | ~2,000 schools per year without school level classification. Detailed imputation or grouping evaluated during Phase 2 profiling. |
| `RECON_STATUS` | 029 | Deferred (Phase 2) | Not yet characterized; may affect which records are canonical. Full profiling in Phase 2. |
| `UPDATED_STATUS_TEXT` | 029 | Deferred (Phase 2) | Relationship to `SY_STATUS_TEXT` to be profiled during Phase 2. |
| `G_13_OFFERED` | 029 | Resolved (Phase 1) | Passthrough attribute; does not affect regular K-12 enrollment totals. |
| `G_AE_OFFERED` | 029 | Resolved (Phase 1) | Aligns with 052 `TOTAL_INDICATOR` decision: adult education programs separated from regular K-12 student headcounts. |
