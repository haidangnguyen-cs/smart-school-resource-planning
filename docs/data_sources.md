# Data Sources

**Last updated:** Initial source inspection and audit — 2026-10-12<br>
**Status:** Verified from actual files in `data/raw/nces_ccd/`

---

## 1. Primary Source

**National Center for Education Statistics (NCES) — Common Core of Data (CCD)**

The CCD is the U.S. Department of Education's primary database on public elementary and secondary education. Data are collected annually via the EDFacts collection system.

| Item | Value |
|------|-------|
| Program | Common Core of Data (CCD) |
| Publisher | National Center for Education Statistics (NCES), U.S. Dept of Education |
| Collection system | EDFacts |
| Official portal | https://nces.ed.gov/ccd/files.asp |
| Additional documentation | https://nces.ed.gov/ccd/pubschuniv.asp |
| EDFacts file specifications | https://www2.ed.gov/about/inits/ed/edfacts/file-specifications.html |
| NCES CCD Reference Library | https://nces.ed.gov/ccd/reference_library.asp |
| Access method | Direct CSV download (public domain) |
| License | U.S. Government Open Data (no copyright restriction) |

> **Note:** The NCES website was not reachable from the current network during the source audit.
> Source component definitions were verified via web search and official EDFacts documentation references.
> File schemas were verified directly from the actual downloaded files.

---

## 2. Files Present in Workspace

**Root location:** `data/raw/nces_ccd/`

File character encoding is **unverified** across all 15 raw CSV files. Strict UTF-8 validation has not been performed; non-UTF-8 bytes (such as Windows-1252 byte `0x96` en-dash in the 2018-19 Directory file) were observed in sample reads. Decoding errors must not be silently ignored (e.g. via `errors='ignore'`); robust encoding detection and handling is established in the data ingestion pipeline. No companion ZIP or SAS files were found in the workspace.

### Layout

```
data/raw/nces_ccd/
├── 2018-19/
│   ├── ccd_sch_029_1819_w_1a_091019.csv    (Directory, wide)
│   ├── ccd_SCH_052_1819_l_1a_091019.csv    (Membership, long)
│   └── ccd_sch_059_1819_l_1a_091019.csv    (Staff, long)
├── 2019-20/
│   ├── ccd_sch_029_1920_w_1a_082120.csv
│   ├── ccd_SCH_052_1920_l_1a_082120.csv
│   └── ccd_sch_059_1920_l_1a_082120.csv
├── 2020-21/
│   ├── ccd_sch_029_2021_w_1a_080621.csv
│   ├── ccd_SCH_052_2021_l_1a_080621.csv
│   └── ccd_sch_059_2021_l_1a_080621.csv
├── 2021-22/
│   ├── ccd_sch_029_2122_w_1a_071722.csv
│   ├── ccd_SCH_052_2122_l_1a_071722.csv
│   └── ccd_sch_059_2122_l_1a_071722.csv
└── 2022-23/
    ├── ccd_sch_029_2223_w_1a_083023.csv
    ├── ccd_sch_052_2223_l_1a_083023.csv
    └── ccd_sch_059_2223_l_1a_083023.csv
```

---

## 3. File-by-File Inventory

### 3.1 Filename Convention

```
ccd_sch_{component}_{year}_{layout}_{version}_{date}.csv
```

| Part | Meaning |
|------|---------|
| `ccd_sch` | CCD school-level data |
| `{component}` | EDFacts component code (029, 052, 059) |
| `{year}` | School year (e.g., `1819` = 2018-19) |
| `{layout}` | `w` = wide, `l` = long |
| `{version}` | Release version (e.g., `1a`) |
| `{date}` | Release date (MMDDYY, e.g., `091019` = Sep 10, 2019) |

> **Note:** The 2018-19 through 2021-22 Membership files use uppercase `SCH` in the filename; 2022-23 uses lowercase `sch`. This is a cosmetic inconsistency in the NCES filename convention, not a schema difference.

---

### 3.2 Component 029 — School Directory (Wide format)

**EDFacts component:** C029 — School Universe Survey  
**Purpose:** One record per school per year. Identifies schools with addresses, operational status, type, grade range, charter status, and LEA affiliation.

| Year | Filename | Size (MB) | Rows (data) |
|------|----------|-----------|-------------|
| 2018-19 | `ccd_sch_029_1819_w_1a_091019.csv` | 38.9 | 102,176 |
| 2019-20 | `ccd_sch_029_1920_w_1a_082120.csv` | 38.8 | 101,688 |
| 2020-21 | `ccd_sch_029_2021_w_1a_080621.csv` | 38.9 | 101,662 |
| 2021-22 | `ccd_sch_029_2122_w_1a_071722.csv` | 38.8 | 102,130 |
| 2022-23 | `ccd_sch_029_2223_w_1a_083023.csv` | 39.0 | 102,268 |

- **Column count:** 65 columns (consistent across all 5 years — verified by header inspection)  
- **Grain:** One row per `NCESSCH` (school) per school year  
- **Primary key:** `NCESSCH` (12-character string, zero-padded)

---

### 3.3 Component 052 — School Membership / Enrollment (Long format)

**EDFacts component:** C052 — Membership (Enrollment)  
**Purpose:** Student enrollment counts, disaggregated by grade, race/ethnicity, and sex. Multiple rows per school due to disaggregation. Filtering to a designated school-level total indicator is required to obtain school-level totals without double-counting disaggregated rows (see section 4.2).

| Year | Filename | Size (GB) | Total rows (full file) | School-level total rows (EU Total / Derived without AE) |
|------|----------|-----------|------------------------|---------------------------------------------------------|
| 2018-19 | `ccd_SCH_052_1819_l_1a_091019.csv` | 2.34 | 11,948,167 | 99,533 (each total indicator) |
| 2019-20 | `ccd_SCH_052_1920_l_1a_082120.csv` | 2.33 | — (not yet scanned) | — |
| 2020-21 | `ccd_SCH_052_2021_l_1a_080621.csv` | 2.18 | — (not yet scanned) | — |
| 2021-22 | `ccd_SCH_052_2122_l_1a_071722.csv` | 2.19 | — (not yet scanned) | — |
| 2022-23 | `ccd_sch_052_2223_l_1a_083023.csv` | 2.20 | — (not yet scanned) | — |

> **Note on 2018-19 row count and school cohorts:** Full-file scan completed for 2018-19. Total rows: 11,948,167. Both `TOTAL_INDICATOR = 'Education Unit Total'` and `TOTAL_INDICATOR = 'Derived - Education Unit Total minus Adult Education Count'` yield **99,533** rows each. Set equality between the two indicators was explicitly verified for 2018-19: both contain the exact same set of 99,533 `NCESSCH` identifiers (0 set difference in either direction). For the remaining years (2019-20 through 2022-23), cohort equivalence is verified during streaming data ingestion.
> Remaining years were not fully scanned during initial source inspection given file size (~2.2–2.3 GB each). Based on file sizes and the 2022-23 staff row count (100,571), the school-level enrollment counts are expected to be in the 99,000–102,000 range per year.
> Full row counts are recorded in source manifests and audit reports during data ingestion.

- **Column count:** 18 columns (consistent across all 5 years — verified)  
- **Grain (raw):** One row per `NCESSCH` × `GRADE` × `RACE_ETHNICITY` × `SEX` × `TOTAL_INDICATOR`  
- **Grain (filtered):** One row per `NCESSCH` when filtering to a school-level total indicator (`Education Unit Total` or `Derived - Education Unit Total minus Adult Education Count`)  
- **Filtering requirement:** Filter out disaggregated detail rows before computing school enrollment totals. The choice between `Education Unit Total` (includes adult education) and `Derived - Education Unit Total minus Adult Education Count` (excludes adult education) represents differing enrollment concepts and is formalized in the data contract.
- **Primary key (filtered):** `NCESSCH` + `SCHOOL_YEAR`

---

### 3.4 Component 059 — School Staff FTE (Long format)

**EDFacts component:** C059 — Staff (School-level)  
**Purpose:** Staff full-time equivalent (FTE) counts by professional category. In the workspace files, only "Education Unit Total" appears in `TOTAL_INDICATOR`, so each file has exactly one row per school representing the total teacher FTE.

| Year | Filename | Size (MB) | Rows (data) |
|------|----------|-----------|-------------|
| 2018-19 | `ccd_sch_059_1819_l_1a_091019.csv` | 14.0 | 99,911 |
| 2019-20 | `ccd_sch_059_1920_l_1a_082120.csv` | 13.9 | 99,624 |
| 2020-21 | `ccd_sch_059_2021_l_1a_080621.csv` | 14.0 | 99,763 |
| 2021-22 | `ccd_sch_059_2122_l_1a_071722.csv` | 14.0 | 100,425 |
| 2022-23 | `ccd_sch_059_2223_l_1a_083023.csv` | 14.0 | 100,571 |

- **Column count:** 15 columns (consistent across all 5 years — verified)
- **Grain:** One row per `NCESSCH` (school) per school year (TOTAL_INDICATOR only = 'Education Unit Total' — confirmed in 2022-23)
- **Primary key:** `NCESSCH` + `SCHOOL_YEAR`
- **Teacher FTE (TEACHERS field):** Verified as numeric FTE (decimal), range 0–1050, median ~27.62 in 2018-19

---

## 4. Source Limitations and Caveats

### 4.1 School coverage gap
The 059 (Staff) files contain ~2–3% fewer rows than the 029 (Directory) files each year. Not all directory schools have a staff record. This creates left-join nulls when joining 029 to 059 on `NCESSCH`.

### 4.2 TOTAL_INDICATOR complexity (052)
The 052 membership file is a "long" format with heavy disaggregation. Five distinct `TOTAL_INDICATOR` values were observed in samples (and verified in 2018-19):
- `'Category Set A - By Race/Ethnicity; Sex; Grade'` (detailed disaggregation)
- `'Derived - Subtotal by Race/Ethnicity and Sex minus Adult Education Count'` (derived demographic subtotal)
- `'Subtotal 4 - By Grade'` (grade subtotal)
- `'Education Unit Total'` (comprehensive school total, inclusive of adult education)
- `'Derived - Education Unit Total minus Adult Education Count'` (derived school total, excluding adult education)

`'Education Unit Total'` and `'Derived - Education Unit Total minus Adult Education Count'` represent two distinct school-level enrollment definitions. In 2018-19, each yields exactly 99,533 rows, and set equality of their school cohorts (`NCESSCH`) was explicitly verified (cohort equivalence across 2019-20 through 2022-23 verified during data ingestion). Neither definition should be assumed to be universally the only valid total; the analytical choice depends on whether adult education is considered part of standard K-12 operational student load. The final KPI choice is formalized in the data contract. All other disaggregated rows must be excluded to prevent double-counting.

### 4.3 Missing and suppressed data
Data missingness and suppression are tracked via `DMS_FLAG`:
- **059 Staff FTE (`TEACHERS`):** Fully profiled across 2018-19 and 2022-23 into 4 verified categories:
  - `'Reported'`: valid numeric FTE
  - `'Missing'`: data not collected or unavailable
  - `'Not reported'`: state chose not to report
  - `'Suppressed'`: data withheld (usually for small n privacy)
  Non-`'Reported'` rows must not be treated as zero; they require explicit missing-value handling.
- **052 Membership (`STUDENT_COUNT`):** The full domain of `DMS_FLAG` across all 12 million rows and 5 years is **unverified**. In sampled rows, observed values include `'Reported'`, `'Missing'`, `'Not reported'`, `'Suppressed'`, `'Derived'`, and `'Manual adjustment'`. Full profiling is conducted during data ingestion. Non-numeric `STUDENT_COUNT` values in sampled records appear as empty strings (`""`) in CSV, with suppression/missingness explanations captured in `DMS_FLAG`.

### 4.4 School operational status
The 029 directory includes schools with `SY_STATUS_TEXT` values including:
`'Open'`, `'New'`, `'Closed'`, `'Inactive'`, `'Future'`, `'Added'`, `'Changed Boundary/Agency'`, `'Reopened'`

Including only `'Open'` and `'New'` schools represents a candidate scoping rule evaluated and formally decided in the data contract, rather than an automatic default. Handling of Closed, Inactive, Future, Added, Changed Boundary, and Reopened schools will be explicitly defined in that contract.

### 4.5 Identifier structure, empirical observations, and official definitions
- `NCESSCH` is a 12-character zero-padded string composed of: State FIPS (2 chars) + LEA code (5 chars) + School code (5 chars).
- `LEAID` is a 7-character string composed of: State FIPS (2 chars) + LEA code (5 chars).
- `SCHID` distinction between official definition and observed data:
  - **Official NCES definition:** In federal NCES CCD specifications, `SCHID` is documented as a 5-digit NCES-assigned school identifier that appends to `LEAID` (7 chars) to form `NCESSCH` (12 chars).
  - **Observed empirical data in downloaded files:** In the 15 raw CSV releases present in this workspace, the `SCHID` column contains a 7-character string that strictly equals `FIPST + NCESSCH[-5:]` (verified across 102k+ records in 2018-19 and 2022-23 with 0 mismatches). It is **not** the last 7 characters of `NCESSCH` (`NCESSCH[-7:]` would overlap `LEAID` and the school code).
  - **Status:** We preserve this empirical finding, but distinguish it from the official 5-digit definition. Without official companion record layouts for these specific file releases, the exact reason for this 7-character layout (e.g., whether NCES prepended `FIPST` in this extract) remains officially unconfirmed.
- All identifiers must be read and stored as strings to preserve leading zeros.

### 4.6 Year 2020-21 potential anomaly
The 2020-21 school year corresponds to the COVID-19 pandemic period. Enrollment and staffing data from this year may reflect temporary school closures, hybrid models, and reporting anomalies. This year requires additional interpretive caution in trend analysis.

### 4.7 NCES website not reachable
The NCES website (nces.ed.gov) was not reachable from the current development environment during this audit. Official column-level documentation could not be directly accessed. Field definitions were verified from:
- Actual file headers
- Sample data rows
- Web search referencing official EDFacts documentation

### 4.8 No companion documentation files
No PDF record layouts, codebooks, or companion SAS files were found in the workspace alongside the CSV files. If available, these should be downloaded and stored in `data/external/` or `docs/`.

---

## 5. Time Coverage

| School Year | Files Present | Year Code |
|-------------|--------------|-----------|
| 2018-2019 | Directory, Membership, Staff | 1819 |
| 2019-2020 | Directory, Membership, Staff | 1920 |
| 2020-2021 | Directory, Membership, Staff | 2021 |
| 2021-2022 | Directory, Membership, Staff | 2122 |
| 2022-2023 | Directory, Membership, Staff | 2223 |

**Span:** 5 consecutive school years (2018-19 through 2022-23)  
**All 3 components are present for all 5 years** — compatibility is confirmed at the schema level.

---

## 6. Schema Stability Across Years

| Component | Schema consistent across 5 years? | Evidence |
|-----------|-----------------------------------|----------|
| 029 Directory | **Yes** — identical 65-column header | Headers inspected across all 5 school years (2018-19 through 2022-23) |
| 052 Membership | **Yes** — identical 18-column header | Headers inspected across all 5 school years (2018-19 through 2022-23) |
| 059 Staff | **Yes** — identical 15-column header | Headers inspected across all 5 school years (2018-19 through 2022-23) |

No schema changes detected across any of the 15 raw files. Column count, names, and ordering are identical year-to-year within each component.

---

## 7. Retrieval Metadata

| Field | Value |
|-------|-------|
| Data already downloaded by | User (prior to workspace audit) |
| Exact download date | Unknown — not recorded |
| Checksum verification | Not performed — no reference checksums available in workspace |
| Download method | Unknown — no download script or metadata file in workspace |
| File modification times | Not inspected (not relevant to content integrity at this stage) |

> **Reproducibility Verification:** A SHA-256 checksum of each raw file is stored in `outputs/quality_reports/source_manifest.json` to support reproducibility verification.
