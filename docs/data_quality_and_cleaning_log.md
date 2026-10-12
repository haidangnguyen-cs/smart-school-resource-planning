# Smart School Resource Planning — Data Quality and Ingestion Audit Log

**Scope:** NCES Data Ingestion and Quality Validation
**Execution Date:** 2026-10-12
**Status:** Validated and Passed
**Source Manifest:** `outputs/quality_reports/source_manifest.json`
**Audit Report:** `outputs/quality_reports/source_audit_report.json`

---

## 1. Executive Summary

This log records the verified ingestion and quality audit findings across all 15 raw National Center for Education Statistics (NCES) Common Core of Data (CCD) files covering the 5-year longitudinal baseline (2018-19 through 2022-23).

All 15 source files were audited for:
1. File integrity and SHA-256 checksums.
2. Character encoding and deterministic cascade verification (`utf-8` with fallback to `windows-1252`).
3. Schema conformity and expected column presence.
4. Composite primary key uniqueness `[school_id, school_year]`.
5. Join cardinality and relationship integrity with the Directory spine (`1:0..1`).
6. Domain business rules (zero-teacher anomalies, non-reported flags, enrollment non-negativity, operational status distribution).

---

## 2. Source Files and Verified Encodings

| School Year | Component | Raw Filename | Size (MB) | Verified Encoding | SHA-256 (Prefix) |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **2018-19** | Directory (029) | `ccd_sch_029_1819_w_1a_091019.csv` | 38.86 | `windows-1252` | `e2ef24b611...` |
| **2018-19** | Membership (052) | `ccd_SCH_052_1819_l_1a_091019.csv` | 2315.65 | `windows-1252` | `9d554a9918...` |
| **2018-19** | Staff (059) | `ccd_sch_059_1819_l_1a_091019.csv` | 26.68 | `windows-1252` | `883e4c44bc...` |
| **2019-20** | Directory (029) | `ccd_sch_029_1920_w_1a_082120.csv` | 38.60 | `windows-1252` | `878c773950...` |
| **2019-20** | Membership (052) | `ccd_SCH_052_1920_l_1a_082120.csv` | 2275.98 | `windows-1252` | `6256c7075c...` |
| **2019-20** | Staff (059) | `ccd_sch_059_1920_l_1a_082120.csv` | 26.60 | `windows-1252` | `c0fc2980fa...` |
| **2020-21** | Directory (029) | `ccd_sch_029_2021_w_1a_080621.csv` | 38.83 | `windows-1252` | `6a802521c7...` |
| **2020-21** | Membership (052) | `ccd_SCH_052_2021_l_1a_080621.csv` | 2253.94 | `windows-1252` | `d558b3e839...` |
| **2020-21** | Staff (059) | `ccd_sch_059_2021_l_1a_080621.csv` | 26.62 | `windows-1252` | `26514757e2...` |
| **2021-22** | Directory (029) | `ccd_sch_029_2122_w_1a_071722.csv` | 39.46 | `utf-8` | `2709232d6d...` |
| **2021-22** | Membership (052) | `ccd_SCH_052_2122_l_1a_071722.csv` | 2259.08 | `utf-8` | `829a8a7db3...` |
| **2021-22** | Staff (059) | `ccd_sch_059_2122_l_1a_071722.csv` | 26.96 | `utf-8` | `c1d5d140e6...` |
| **2022-23** | Directory (029) | `ccd_sch_029_2223_w_1a_083023.csv` | 39.69 | `utf-8` | `1e0a2944b2...` |
| **2022-23** | Membership (052) | `ccd_SCH_052_2223_l_1a_083023.csv` | 2242.06 | `utf-8` | `c2aeeaa95b...` |
| **2022-23** | Staff (059) | `ccd_sch_059_2223_l_1a_083023.csv` | 27.02 | `utf-8` | `225ad757fa...` |

### Key Ingestion Finding: Encoding Shift
- Releases for **2018-19, 2019-20, and 2020-21** contain non-UTF-8 characters (e.g. byte `0x96` en-dash in school names) requiring Windows-1252 decoding.
- Releases for **2021-22 and 2022-23** decode cleanly under strict UTF-8.
- The deterministic encoding cascade (`utf-8` -> `windows-1252`) correctly handles all files without data loss, error suppression (`errors='ignore'`), or silent mojibake.

---

## 3. Ingestion Row Counts and Key Uniqueness

| School Year | Directory Rows (Spine) | Staff Rows (Total) | Membership Filtered Rows (`Derived...`) | Key Duplicates (`[school_id, school_year]`) |
| :---: | :---: | :---: | :---: | :---: |
| **2018-19** | 102,176 | 99,911 | 99,533 | 0 (Directory: 0, Staff: 0, Mem: 0) |
| **2019-20** | 101,688 | 99,624 | 99,290 | 0 (Directory: 0, Staff: 0, Mem: 0) |
| **2020-21** | 101,662 | 99,763 | 99,310 | 0 (Directory: 0, Staff: 0, Mem: 0) |
| **2021-22** | 102,130 | 100,425 | 100,029 | 0 (Directory: 0, Staff: 0, Mem: 0) |
| **2022-23** | 102,268 | 100,571 | 99,860 | 0 (Directory: 0, Staff: 0, Mem: 0) |

*Zero primary key duplicates* were found across any component in any year, confirming strict composite key uniqueness at the school-year grain.

---

## 4. Directory Spine Left Join Cardinality (`1:0..1`)

| School Year | Spine vs. Staff Match % | Unmatched Spine Records (Staff) | Spine vs. Mem Match % | Unmatched Spine Records (Mem) | Orphan Target Records |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2018-19** | 97.78% | 2,265 | 97.41% | 2,643 | 0 |
| **2019-20** | 97.97% | 2,064 | 97.64% | 2,398 | 0 |
| **2020-21** | 98.13% | 1,899 | 97.69% | 2,352 | 0 |
| **2021-22** | 98.33% | 1,705 | 97.94% | 2,101 | 0 |
| **2022-23** | 98.34% | 1,697 | 97.65% | 2,408 | 0 |

### Cardinality and Integrity Verification
- **Cardinality:** In both Staff and Membership target components, all join keys are strictly unique (`target_key_unique = True`). This guarantees that left-joining the Directory spine against Staff and Membership never produces Cartesian row multiplication.
- **Orphan Target Records:** Exactly **0** unmatched target records were found across all 5 school years. Every reported school record in Staff and Membership belongs to a valid Directory spine record.
- **Unmatched Spine Records:** 1.7% to 2.6% of Directory spine records do not appear in Staff or Membership. In accordance with ADR-09, these represent expected non-operating, inactive, closed, or newly established schools with no reported staffing or enrollment in the survey year.

---

## 5. Domain Quality & Business Rule Observations

### 5.1. Staffing (059) Anomaly and Missingness Distribution

| School Year | Total Staff Rows | Zero-Teacher Anomalies (`zero_teacher_anomaly`) | Missing Teacher FTE (`NaN` / Coerced) |
| :---: | :---: | :---: | :---: |
| **2018-19** | 99,911 | 1,427 | 3,131 |
| **2019-20** | 99,624 | 1,142 | 13,395 |
| **2020-21** | 99,763 | 1,135 | 8,543 |
| **2021-22** | 100,425 | 1,370 | 4,171 |
| **2022-23** | 100,571 | 1,872 | 3,034 |

*Note on Missing FTE:* In 2019-20 and 2020-21, missing teacher FTE increased significantly due to specific state-level non-reporting to CCD. In accordance with ADR-03, non-reported values (`DMS_FLAG != 'Reported'`) and negative sentinel codes (`-1`, `-2`) are strictly coerced to `NaN` and never treated as zero. Reported zeros (`TEACHERS == 0.0` with `DMS_FLAG == 'Reported'`) are preserved with `zero_teacher_anomaly = True` to prevent division-by-zero errors in ratio calculations.

### 5.2. Student Enrollment (052) Observations

| School Year | Filtered Enrollment Rows | Missing Enrollment (`total_students.isna()`) | Zero Enrollment (`total_students == 0`) | Negative Enrollment |
| :---: | :---: | :---: | :---: | :---: |
| **2018-19** | 99,533 | 522 | 2,449 | 0 |
| **2019-20** | 99,290 | 0 | 2,802 | 0 |
| **2020-21** | 99,310 | 659 | 2,464 | 0 |
| **2021-22** | 100,029 | 193 | 2,867 | 0 |
| **2022-23** | 99,860 | 141 | 2,763 | 0 |

### 5.3. Operational Status Distribution (Directory 029)

| School Year | Total Spine | Open | New | Closed | Inactive | Future | Added | Changed Boundary/Agency | Reopened |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2018-19** | 102,176 | 97,444 | 1,331 | 1,446 | 482 | 337 | 83 | 1,028 | 25 |
| **2019-20** | 101,688 | 98,411 | 1,004 | 1,233 | 459 | 372 | 55 | 137 | 17 |
| **2020-21** | 101,662 | 98,717 | 902 | 940 | 521 | 438 | 73 | 40 | 31 |
| **2021-22** | 102,130 | 99,010 | 1,168 | 852 | 483 | 370 | 188 | 31 | 28 |
| **2022-23** | 102,268 | 99,528 | 890 | 878 | 480 | 339 | 74 | 57 | 22 |

---

## 6. Audit Conclusion and Pipeline Readiness

The data ingestion and quality audit protocol has fully satisfied all defined acceptance criteria:
1. Ingestion readers stream and parse large multi-gigabyte files efficiently without memory exhaustion.
2. The deterministic encoding cascade resolves real-world encoding divergence across school years without data corruption.
3. Composite primary key uniqueness and 1:0..1 join integrity are empirically verified across 100% of source files.
4. Data quality reports and manifests are generated under `outputs/quality_reports/`.

The pipeline data layers are verified and ready for cleaning, reconciliation, and longitudinal panel construction.
