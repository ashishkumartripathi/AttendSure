# Rural School Attendance Integrity and Intervention Decision System

**An Offline-First Explainable AI and Decision-Support Platform for Rural Schools**  
*Open-Source Technical Repository: [https://github.com/ashishkumartripathi/AttendSure](https://github.com/ashishkumartripathi/AttendSure)*

---

## 1. Project Purpose & Problem Formulation

Rural primary and middle schools in developing regions face structural challenges with attendance reporting, including clerical recording delays, proxy reporting, and subsidy leakage (e.g., Mid-Day Meal allocations). Traditional biometric systems (fingerprint, iris, facial recognition) frequently fail in rural field settings due to:
- High hardware cost and reliance on stable internet connectivity.
- Biometric sensor degradation (dust, student finger wear).
- Severe child privacy and surveillance concerns.

The **Rural School Attendance Integrity and Intervention Decision System** provides an offline-first, privacy-by-design solution. It operates on standard consumer hardware, collecting only aggregate cohort headcount data without collecting or storing individual student biometrics or personal identifying information.

---

## 2. System Architecture & Dual-Stream AI Engine

The application implements a dual-stream analytical architecture combining symbolic reasoning with supervised statistical machine learning:

1. **Supervised Machine Learning (Stream A - Decision Tree Classifier)**:
   - Built with `scikit-learn` (`max_depth=4`, `min_samples_leaf=4`, balanced class weighting).
   - Classifies roll-call sessions into `Normal` versus `Needs Review`.
   - Uses six non-leaking, causal features derived from historical cohort timelines (`attendance_rate`, `absence_rate`, `baseline_deviation`, `recent_delta_1d`, `repeated_count_streak`, `relative_decline_pct`).
   - Generates transparent, human-interpretable leaf-node paths with confidence scores and uncertainty guards.

2. **Deterministic Production Rules (Stream B - Expert Rule Detectors)**:
   - Three deterministic production rules enforce operational sanity checks:
     - `RULE_ATTENDANCE_DROP`: Detects significant drops compared to the cohort's rolling 5-day median (>= 30% relative drop).
     - `RULE_REPEATED_HEADCOUNT`: Flags identical headcounts reported over multiple consecutive days (>= 4 days), identifying reporting inertia.
     - `RULE_WEBCAM_DISCREPANCY`: Identifies discrepancies between teacher-recorded headcounts and optional photo confirmation counts.

3. **Multi-Stream Decision Fusion**:
   - `synthesize_intervention_decision()` merges predictions into plain-language, non-accusatory operational guidance.

> **Ethical AI & Non-Punitive Philosophy**: All system alerts represent decision-support signals for supportive administrative review, never automated accusations of fraud or grounds for student punishment. Real-world rural attendance drops frequently stem from monsoons, agricultural harvest seasons, or community health events.

---

## 3. User Interface & Progressive Disclosure

The application interface adheres to the principle of **Progressive Disclosure**: *Simple by default, powerful when needed*.

- **Teacher View (Default)**: Clean, card-based interface using familiar, plain-English terms. Teachers take roll call, review plain-English alert cards, and log attendance without seeing machine learning formulas or statistical metrics.
- **Global Developer Mode**: A centralized toggle in **Settings -> Advanced Settings** reveals detailed technical diagnostics, Decision Tree evaluations, feature weights, confusion matrices, and database inspection tools across all screens.

### Six Core Screens:
1. **Overview**: Schoolwide attendance summary, active alerts, and today's roll-call status.
2. **Take Attendance**: Daily roll-call register with automatic headcount validation and optional in-memory classroom photo capture.
3. **Attendance Records**: Historical attendance log with multi-criteria filtering and RFC 4180 CSV export.
4. **Needs Attention**: Review triage showing non-accusatory alert cards with plain-English rationales.
5. **Reports & Analytics**: Analytical breakdown across cohorts, trends, daily logs, and audit trails (+ ML Evaluation in Developer Mode).
6. **Settings**: School profile, database maintenance, backup utilities, synthetic data generator, and Developer Mode toggle.

---

## 4. Technical Stack & Invariants

- **Language & Runtime**: Python >= 3.13
- **Machine Learning Engine**: `scikit-learn 1.7.2`, `joblib 1.5.2`
- **Frontend Layer**: `streamlit 1.51.0`, `altair 5.5.0`
- **Data Modeling & Analytics**: `pandas 2.3.3`
- **Local Persistence**: `sqlite3` (ACID compliant, Write-Ahead Logging [WAL] mode, zero external network dependency)
- **Quality Assurance**: `pytest 8.4.2` (359 automated tests with 100% pass rate)

---

## 5. Quick Start Guide

### 5.1 Installation
```bash
# Clone the repository
git clone https://github.com/ashishkumartripathi/AttendSure.git
cd AttendSure

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux / macOS

# Install dependencies and editable package
pip install -r requirements.txt
pip install -e .
```

### 5.2 Seeding a Demonstration Database
```bash
# Populate an isolated synthetic showcase database
python scripts/prepare_demo_database.py --dest data/demo_showcase.db --seed 42
```

### 5.3 Launching the Application
```bash
streamlit run src/attendsure/ui/app.py
```
*Access the application at `http://localhost:8501`.*

### 5.4 Running Automated Tests
```bash
# Run all 359 automated tests
pytest
```

---

## 6. Reproducing Evaluation Benchmarks

The project includes a standalone script to reproduce all evaluation benchmarks directly from the command line:

```bash
python scripts/reproduce_benchmarks.py
```

### Benchmark 1: Supervised Machine Learning Benchmark (88 Holdout Test Sessions)
- **Dataset**: 12 cohorts over 35 calendar days (excluding weekends = 25 school days/class = 300 raw sessions).
- **Split**: 8 training cohorts (200 records), 4 holdout test cohorts (100 records).
- **Burn-in**: 3-day history window excludes the first 3 sessions per cohort for causal rolling baseline computation, resulting in 176 valid training sessions and 88 independent test sessions (Random Seed = 42).
- **Results**:
  - **Accuracy**: 92.05% (81 / 88)
  - **Recall (Sensitivity)**: 80.00% (4 / 5)
  - **Specificity**: 92.77% (77 / 83)
  - **Precision**: 40.00% (4 / 10)
  - **F1-Score**: 53.33%
  - **Confusion Matrix**: TP=4, FP=6, TN=77, FN=1
- **Trade-Off**: Balanced class weighting intentionally prioritizes high recall (80.0%) and specificity (92.8%) over precision (40.0%) due to low synthetic anomaly prevalence (~5.7%).

### Benchmark 2: Deterministic Production Rules Benchmark (150 Sessions)
- **Parameters**: 5 classes x 30 school days = 150 sessions total (5% anomaly injection rate, Random Seed = 42).
- **Results**:
  - **Accuracy**: 96.67% (145 / 150)
  - **Precision**: 100.00% (6 / 6)
  - **Recall (Session-Level)**: 54.55% (6 / 11)
  - **Recall (Event-Level)**: 100.00% (2 of 2 multi-day episodes flagged on Day 4 of 4)
  - **Specificity**: 100.00% (139 / 139)
  - **F1-Score**: 70.59%
  - **Confusion Matrix**: TP=6, FP=0, TN=139, FN=5
- **Operational Note**: Session recall is 54.55% due to chronological prefix accumulation delay on repeated runs. Event-level detection is 100.0%.

---

## 7. Limitations & Technical Boundaries

To maintain rigorous scientific accuracy:
1. **Camera Scope**: Browser photo capture (`st.camera_input`) provides an in-memory visual confirmation tool where the teacher confirms the headcount. Automated computer vision, facial recognition, and automated people counting are **not implemented**.
2. **Synthetic Data**: All benchmarks were evaluated on independently generated synthetic datasets. No live pilot was conducted in operating schools.
3. **RFID / NFC Hardware Readers**: Physical contactless card tap-in was evaluated and formally deferred due to rural school hardware cost and proxy risks. The database schema maintains forward-compatible event fields (`record_source='NFC_SCAN'`) for future integration.
4. **Data Privacy Model**: Local SQLite database stores aggregate cohort headcounts (`class_id`, `expected_enrollment`, `present_count`, `absent_count`). No student names, roll numbers, or biometrics are collected or stored.
5. **Deployment Status**: Local offline execution and Streamlit Community Cloud hosting configurations are validated; live public deployment is not yet launched.

---

## 8. License & Authors

- **License**: MIT License (see `LICENSE`)
- **Authors**: Ashish Kumar Tripathi & Harsh Jakhar
- **Repository**: [https://github.com/ashishkumartripathi/AttendSure](https://github.com/ashishkumartripathi/AttendSure)
