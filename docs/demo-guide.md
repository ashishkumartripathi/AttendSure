# AttendSure Demonstration Guide

A step-by-step guide for conducting live college evaluations and technical presentations of **AttendSure**, an explainable attendance integrity and anomaly detection system for rural school governance.

---

## 1. System Overview & Demonstration Objectives

AttendSure provides automated decision support for rural school administrators and educators. It detects aggregate attendance irregularities—such as unexpected roll-call drops, repetitive headcount submissions, and simulated headcount camera discrepancies—while maintaining strict explainability and data privacy.

### Key Demonstration Principles
1. **Decision Support, Never Accusation**: Alerts represent signals for administrative review, not conclusive proof of fraud or misconduct.
2. **Offline-First Privacy**: No biometrics, facial recognition, or student-level personally identifiable information (PII) are collected or stored.
3. **Database Isolation**: Demonstration workflows strictly isolate synthetic demonstration data from the school's operational database.

---

## 2. Environment Prerequisites

AttendSure requires:
- **Operating System**: Windows, Linux, or macOS.
- **Python**: Version 3.13 or higher.
- **Core Dependencies**: `streamlit`, `pandas`, `pytest`.

Verify the Python environment and package installation from the repository root:

```bash
python -c "import attendsure; print('AttendSure version/location:', attendsure.__file__)"
```

---

## 3. Safe Demonstration Database Preparation

To ensure the active operational database (`data/attendsure.db`) is never accidentally seeded, modified, or overwritten, AttendSure includes an explicit demonstration seeding script with hard-coded safety guards.

### Running the Demo Database Seeder

Run the dedicated preparation script, specifying an isolated destination file:

```bash
# Windows PowerShell / CMD / Bash
python scripts/prepare_demo_database.py --dest data/demo_showcase.db --seed 42
```

### Safety Guards Enforced
- **Operational Protection**: Refuses to target `data/attendsure.db`.
- **Overwrite Protection**: Halts with an error if `data/demo_showcase.db` already exists, preventing accidental loss of prior work.
- **Contract Schema Validation**: Validates every synthetic session against `docs/data-contract.md` before writing to SQLite.
- **Synthetic Marking**: Marks 100% of generated records with `record_source="SYNTHETIC"`.

### Output Summary
The script will output confirmation:
- Total sessions seeded (60 sessions across 5 cohorts).
- Anomaly alerts identified by the detection engine.
- Exact commands to launch AttendSure with the demonstration database.

---

## 4. Launching the Live Application

### Launch with the Demonstration Database

To launch Streamlit pointed at the newly prepared demonstration database:

**Windows PowerShell:**
```powershell
$env:ATTENDSURE_DB_PATH="data/demo_showcase.db"
python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

**Linux / macOS Bash:**
```bash
ATTENDSURE_DB_PATH="data/demo_showcase.db" python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

Open your browser to:
[http://localhost:8501](http://localhost:8501)

### Returning to the Operational Database

To return to the default operational database, unset the environment variable or omit it:

**Windows PowerShell:**
```powershell
Remove-Item env:ATTENDSURE_DB_PATH
python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

**Linux / macOS Bash:**
```bash
python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

---

## 5. Recommended Demonstration Sequence

Walk evaluators through the application using the six navigation views:

```
[Overview Dashboard] ➔ [Attendance Register] ➔ [Intelligence Centre] ➔ [Algorithm Laboratory] ➔ [Reports & Export] ➔ [Data & Settings]
```

### Step 1: Overview Dashboard
- **Objective**: Showcase high-level attendance health and immediate review triage.
- **Demonstration Points**:
  - Point out the KPI strip: Total Sessions (60), Overall Attendance Rate (~88%), and Pending Review signals.
  - Review the **High Priority Anomaly Signals** queue.
  - Show the **Cohort Attendance Trends** timeline chart.

### Step 2: Attendance Register
- **Objective**: Demonstrate daily roll-call recording, count validation, and simulated camera counter.
- **Demonstration Points**:
  - Show the **Record Attendance** form.
  - Explain the count invariant: `present_count + absent_count == expected_enrollment`.
  - Demonstrate entering an invalid count (e.g., 25 present + 10 absent when enrollment is 30) and show immediate client-side validation error preventing database write.
  - Show the simulated webcam counter mode selection (`NORMAL`, `DISCREPANCY_ABOVE_THRESHOLD`).

### Step 3: Intelligence Centre
- **Objective**: Explainable anomaly triage and human-in-the-loop review.
- **Demonstration Points**:
  - Filter alerts by rule (`RULE_ATTENDANCE_DROP`, `RULE_REPEATED_HEADCOUNT`, `RULE_WEBCAM_DISCREPANCY`).
  - Open an alert's expandable card to reveal the **Explanation**:
    1. **Observed Value**: Actual detected headcount or rate.
    2. **Baseline Reference**: Historical rolling median.
    3. **Threshold Applied**: Configured sensitivity parameter.
    4. **Rationale**: Plain-language justification.
  - Demonstrate changing status from `PENDING_REVIEW` to `ACKNOWLEDGED` or `RESOLVED`.
  - Explain that re-running scans preserves educator review decisions via repository conflict safeguards.

### Step 4: Algorithm Laboratory
- **Objective**: Interactive simulation, model benchmarking, and evidence evaluation.
- **Demonstration Points**:
  - Select benchmark scenarios:
    - `Nominal Attendance`: High nominal attendance with 0 false alarms.
    - `Attendance Drop`: Sudden drop triggering `RULE_ATTENDANCE_DROP`.
    - `Repeated Headcount`: 4-day identical headcount triggering `RULE_REPEATED_HEADCOUNT`.
    - `Webcam Discrepancy`: Simulated camera discrepancy triggering `RULE_WEBCAM_DISCREPANCY`.
  - Review the live **Confusion Matrix** (TP, FP, TN, FN) and metrics (Precision, Recall, F1).
  - Highlight the distinction between **Session-Level Classification** and **Event-Level Sequence Detection**.
  - Emphasize that Algorithm Laboratory executes purely in-memory and causes **zero database writes**.

### Step 5: Reports & Export
- **Objective**: Data portability, offline CSV reporting, and batch ingestion.
- **Demonstration Points**:
  - Click **Download Sessions CSV** and **Download Alerts CSV** to show audit export.
  - Demonstrate the **CSV Ingestion Workflow**:
    1. Select a file for **Preview**. Show that preview validates row-by-row and causes zero writes.
    2. Show the **All-or-Nothing** transaction safety: any row with invalid schema causes complete rollback.

### Step 6: Data & Settings
- **Objective**: System governance, database provenance, and operational health.
- **Demonstration Points**:
  - Verify the **Active Database File** indicator displaying the `Demonstration Database Override` badge.
  - Review the **Record Origin & Provenance Breakdown**:
    - Distinguishes Manual Roll-Call Entries, CSV Imports, and Synthetic Records.
  - Highlight the **Privacy & Ethics Governance** section confirming local-only processing and zero student PII.

---

## 6. Pre-Packaged Demonstration Scenarios

| Scenario | Cohort ID | Description | Expected Detector Output |
| :--- | :--- | :--- | :--- |
| **1. Nominal Baseline** | `CLASS-01-A` | 12 sessions of natural attendance (86%–96%). | 0 alerts (Nominal baseline verification). |
| **2. Attendance Drop** | `CLASS-02-B` | Day 6 exhibits a sharp drop to 11 students (~34%). | `RULE_ATTENDANCE_DROP` alert with rolling median baseline. |
| **3. Repeated Headcount** | `CLASS-03-C` | Days 5–8 submit identical headcount (22) for 4 consecutive days. | `RULE_REPEATED_HEADCOUNT` alert triggered on Day 8. |
| **4. Camera Discrepancy**| `CLASS-04-D` | Day 7 simulated camera count differs by 9 students (> 20%). | `RULE_WEBCAM_DISCREPANCY` review signal. |
| **5. Compound Mixture** | `CLASS-05-E` | Mixture of sudden drops and repeated runs. | Multiple review signals across temporal timeline. |

---

## 7. Troubleshooting

### "ModuleNotFoundError: No module named 'attendsure'"
Ensure AttendSure is installed in editable mode in your active Python environment:
```bash
pip install -e . --no-build-isolation
```

### "Safety Guard Violation: Destination database already exists"
The seeder refuses to overwrite existing files. Either specify a new path (e.g., `data/demo_run2.db`) or delete the old demonstration database manually:
```powershell
# PowerShell
Remove-Item data/demo_showcase.db
```

### Streamlit Port 8501 Already in Use
Specify a different port using the `--server.port` flag:
```bash
python -m streamlit run src/attendsure/ui/app.py --server.port 8502
```
