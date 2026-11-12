# Technical Evaluation & Empirical Evidence Index

**Official Project Title:** Rural School Attendance Integrity and Intervention Decision System  
**Repository:** https://github.com/ashishkumartripathi/AttendSure  
**Branch:** `feature/modern-saas-ui`  
**Latest Verified Commit:** `359993cdf66aafe0ab91431fec4020a8e74dc2e3`  
**Target `main` Branch Status:** Strictly unchanged at `7324e9e067b7b0d01084b486adc04d0cc0a38c66`  
**Project Mentor:** Mr. Hitesh Jangid  
**Operational Database SHA256:** `46C22853EF5697DFE449FD0D61CFE5E719A84FF5C8260A2BA0F16935ED97F6AE`  

---

## 1. Master Evidence Map

| Evidence Domain | Primary Document / Code Artifact | Execution / Reproduction Command | Key Verified Metric / Finding |
| :--- | :--- | :--- | :--- |
| **Comprehensive Evaluation** | `docs/technical_evaluation_report.md` | N/A (Markdown Report) | Full empirical findings across all 5 verification pillars |
| **Automated Test Suite** | `tests/` (34 test files) | `pytest` | **417 of 417 passed in 79.90s** (0 errors, 0 warnings) |
| **Task 1: Functionality** | `scratch/verify_task1_functionality.py` | `python scratch/verify_task1_functionality.py` | 9 of 9 subtests passed (all 6 views + auth + persistence) |
| **Task 2: Database & Security** | `scratch/audit_task2_security.py` | `python scratch/audit_task2_security.py` | 6 of 6 subtests passed (6 check constraints, rollback, zero silent fallback) |
| **Task 3: Camera Benchmark** | `scratch/benchmark_task3_camera.py` | `python scratch/benchmark_task3_camera.py` | Clean MAE = **0.00**, Standard 7-case MAE = **0.14**, Overall numeric MAE = **0.44** |
| **Task 4: Anomaly Benchmarks** | `scripts/reproduce_benchmarks.py` | `python scripts/reproduce_benchmarks.py` | Rules: **96.67% Acc**, **100% Prec**, **54.55% Session Rec**, **100% Event Rec**; ML: **92.05% Acc**, **80% Rec** |
| **Task 5: Cloud Latency** | `scratch/measure_task5_latencies.py` | `python scratch/measure_task5_latencies.py` | Overview **343 ms**, Records **158 ms**, Needs Attention **2,000 ms**, Reports **3,684 ms** |
| **Demonstration Dataset** | `submission/demonstration/dataset/` | `python submission/demonstration/generate_demo_dataset.py` | 150 synthetic sessions, 6 explainable alerts, 3 review actions |
| **Live Demonstration Guide**| `submission/demonstration/DEMONSTRATION_GUIDE.md` | N/A (Presentation Walkthrough) | 5–7 minute script with 3-tier fallback procedures |
| **Academic Presentation** | `submission/presentation/` | `python scripts/generate_academic_presentation.py` | 16-slide PPTX deck with speaker notes script |
| **Comprehensive Report** | `submission/report/` | `python scripts/generate_academic_report.py` | 33-section report in DOCX and native PDF format |

---

## 2. Integrity & Cryptographic Checksums

```text
File:        data/attendsure.db
Algorithm:   SHA256
Hash:        46C22853EF5697DFE449FD0D61CFE5E719A84FF5C8260A2BA0F16935ED97F6AE
Status:      VERIFIED UNALTERED

Branch:      feature/modern-saas-ui
Head Commit: 359993cdf66aafe0ab91431fec4020a8e74dc2e3
Target main: 7324e9e067b7b0d01084b486adc04d0cc0a38c66 (STRICTLY UNCHANGED)
```

---

## 3. Database Check Constraint Evidence

```sql
-- 1. Enrollment Invariant
CONSTRAINT chk_sessions_enrollment CHECK (expected_enrollment >= 1)

-- 2. Present Count Boundary
CONSTRAINT chk_sessions_present CHECK (present_count >= 0 AND present_count <= expected_enrollment)

-- 3. Absent Count Boundary
CONSTRAINT chk_sessions_absent CHECK (absent_count >= 0 AND absent_count <= expected_enrollment)

-- 4. Fundamental Sum Invariant
CONSTRAINT chk_sessions_count_invariant CHECK (present_count + absent_count = expected_enrollment)

-- 5. Camera Status Enum
CONSTRAINT chk_sessions_webcam_status CHECK (webcam_status IN ('SUCCESS', 'NOT_ATTEMPTED', 'CAMERA_UNAVAILABLE', 'DETECTION_FAILED'))

-- 6. Record Source Provenance
CONSTRAINT chk_sessions_record_source CHECK (record_source IN ('SYNTHETIC', 'MANUAL_ENTRY', 'CSV_IMPORT'))
```
