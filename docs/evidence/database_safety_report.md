# AttendSure — Database Safety & Storage Isolation Report

**Date:** October 2026  
**Auditor:** AttendSure Storage Architecture Subsystem  
**Canonical Operational Path:** `data/attendsure.db`  
**Dedicated Demonstration Path:** `data/demo_showcase.db`  

---

## 1. Storage Safeguards & Guarantees

AttendSure strictly adheres to the principle of **Zero Accidental Operational Mutation**:
1. **Separation of Concerns:** The active operational database (`data/attendsure.db`) is never seeded, truncated, reset, or modified by demonstration scripts or evaluation tests.
2. **Hard Destination Guards in `demo_seed.py`:**
   ```python
   # Rejects attempts to target canonical operational database
   if dest_path.resolve() == DEFAULT_DB_PATH.resolve():
       raise ValueError("Safety rejection: Cannot target operational database for demonstration seeding.")
   ```
3. **Overwrite Prevention:** `prepare_demo_database()` strictly refuses to overwrite existing files unless the user manually removes them, preventing accidental data loss.
4. **Source Auditing:** Every session record contains a mandatory `record_source` column tagged with `"MANUAL_ENTRY"`, `"CSV_IMPORT"`, or `"SYNTHETIC"`. 100% of demonstration rows are tagged `"SYNTHETIC"`.

---

## 2. Cryptographic Integrity Verification

To prove conclusively that the operational database remained untouched throughout the M5.8 development and evaluation cycle, we record SHA-256 checksums:

```powershell
Get-FileHash data/attendsure.db -Algorithm SHA256
```

- **M5.7 Reported SHA-256:** `46c22853ef5697dfe449fd0d61cfe5e719a84ff5c8260a2ba0f16935ed97f6ae`
- **M5.8 Current SHA-256:**  `46c22853ef5697dfe449fd0d61cfe5e719a84ff5c8260a2ba0f16935ed97f6ae`
- **Verification Verdict:** **VERIFIED UNCHANGED — ZERO BYTES MUTATED**

---

## 3. Demonstration Database Verification (`data/demo_showcase.db`)

The dedicated demonstration database was inspected and verified with the following characteristics:
- **Total Seeded Sessions:** 60
- **Total Monitored Cohorts:** 5 (`CLASS-01-A`, `CLASS-02-B`, `CLASS-03-C`, `CLASS-04-D`, `CLASS-05-E`)
- **Total Generated Alerts:** 14
- **Alert Breakdown by Rule:**
  - `RULE_REPEATED_HEADCOUNT`: 11 signals
  - `RULE_ATTENDANCE_DROP`: 2 signals
  - `RULE_WEBCAM_DISCREPANCY`: 1 signal
- **Review Statuses:** All 14 alerts initialized to `PENDING_REVIEW` for live examiner triage.

---

## 4. ACID Concurrency & Integrity Verification

- **WAL Mode Active:** Verified via `PRAGMA journal_mode;` returning `wal`. WAL allows multi-reader non-blocking concurrent reads during Streamlit dashboard operations.
- **Foreign Key Cascade:** Enabled via `PRAGMA foreign_keys = ON;`. Deleting a session record automatically cascades and cleans up associated alerts.
- **Count Invariants:** SQLite table `CHECK` constraints reject negative counts or records where `present_count + absent_count != expected_enrollment` at the database engine level.
