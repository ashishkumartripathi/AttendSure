# AttendSure Evaluation Methodology & Benchmark Specification

This document details the evaluation framework, synthetic ground-truth generation, mathematical metric definitions, and validation constraints implemented in **AttendSure**.

---

## 1. Ground Truth & Synthetic Data Policy

AttendSure strictly adheres to an **offline-first synthetic data policy** for research and testing:

- **No Student PII**: Synthetic datasets contain zero student names, student IDs, biological characteristics, or biometric templates.
- **Deterministic Reproducibility**: All synthetic cohort sessions are generated using parameterized pseudorandom generators with explicit integer seeds.
- **Contract Conformance**: Every generated record conforms to the schema rules in [`docs/data-contract.md`](data-contract.md), including count invariants (`present_count + absent_count == expected_enrollment`), valid RFC 4122 UUIDv4 identifiers, and UTC timestamps.

---

## 2. Benchmark Scenarios

AttendSure provides five standardized synthetic benchmark scenarios implemented in `src/attendsure/data/generator.py`:

### 1. Nominal Attendance (`NOMINAL` / `NORMAL`)
- **Characteristics**: 15–30 consecutive school days of natural attendance variation (85%–95% attendance rate).
- **Target Anomaly Ground Truth**: `ground_truth_is_anomaly = False` for all sessions.
- **Evaluation Purpose**: Measures false alarm rates (Type I errors) under normal, benign school operations.

### 2. Sudden Attendance Drop (`ATTENDANCE_DROP`)
- **Characteristics**: 5 nominal baseline sessions followed by a steep drop on Day 6 (e.g., from 90% down to 35% attendance).
- **Target Rule**: `RULE_ATTENDANCE_DROP`.
- **Trigger Condition**: Session attendance rate drops >= 25 percentage points below the cohort's rolling median.
- **Evaluation Purpose**: Verifies sensitivity to localized attendance collapses (e.g., severe weather or localized illness).

### 3. Repeated Headcount (`REPEATED_HEADCOUNT`)
- **Characteristics**: A multi-day sequence where identical manual headcounts are submitted across 4 or more consecutive days.
- **Target Rule**: `RULE_REPEATED_HEADCOUNT`.
- **Trigger Condition**: Identical present count repeated across K >= 4 consecutive sessions.
- **Evaluation Purpose**: Validates sequential pattern tracking and streak detection.

### 4. Headcount Discrepancy (`WEBCAM_DISCREPANCY`)
- **Characteristics**: Nominal attendance records accompanied by simulated camera headcount estimates differing by >= 5 students and >= 20%.
- **Target Rule**: `RULE_WEBCAM_DISCREPANCY`.
- **Trigger Condition**: Dual-count discrepancy (|manual - camera| >= 5 AND |manual - camera| / manual >= 0.20).
- **Evaluation Purpose**: Verifies cross-verification logic between human roll-call and automated count sensors.

### 5. Multi-Cohort Compound Mixture (`COMPOUND`)
- **Characteristics**: Heterogeneous multi-cohort dataset containing nominal cohorts, isolated drops, repeated sequences, and optical discrepancies interspersed across a school term.
- **Evaluation Purpose**: End-to-end stress testing under mixed operational conditions.

---

## 3. Mathematical Metric Definitions

### 3.1 Binary Classification Metrics

Binary evaluation considers a session anomalous if an alert is emitted:

- **True Positive (TP)**: Detected session that is an actual ground-truth anomaly.
- **False Positive (FP)**: Detected session that is a nominal ground-truth session (False Alarm).
- **True Negative (TN)**: Nominal session correctly ignored by the detection engine.
- **False Negative (FN)**: Ground-truth anomaly missed by the detection engine.

$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$

$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$

$$\text{F1-Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 3.2 Zero-Denominator Fallback Policy
In sparse testing or nominal-only scenarios, zero denominators may occur:
- If $\text{TP} + \text{FP} = 0$ (no positive predictions), $\text{Precision}$ defaults to $0.0$.
- If $\text{TP} + \text{FN} = 0$ (no positive ground truth cases), $\text{Recall}$ defaults to $0.0$.
- If $\text{Precision} + \text{Recall} = 0.0$, $\text{F1-Score}$ defaults to $0.0$.
- AttendSure explicitly tracks and reports whether zero-division defaults were applied via `zero_division_applied` metadata.

### 3.3 Confusion Matrix Orientation
In AttendSure's reporting and UI displays, the confusion matrix is structured as:

| | Predicted Negative (No Alert) | Predicted Positive (Alert Fired) |
| :--- | :---: | :---: |
| **Actual Negative (Normal)** | **TN** | **FP** |
| **Actual Positive (Anomaly)**| **FN** | **TP** |

---

## 4. Sequence-Level vs. Session-Level Evaluation

A critical distinction exists between **Session-Level Classification** and **Event-Level Sequence Detection**:

1. **Session-Level Accounting**:
   - Evaluates every individual date row as an independent sample.
   - In a 4-day repeated headcount event, the online detector must accumulate evidence across Days 1–3 before firing on Day 4 (the threshold-reaching session).
   - In session-level accounting, Days 1, 2, and 3 are counted as False Negatives ($\text{FN} = 3$), and Day 4 is counted as a True Positive ($\text{TP} = 1$), resulting in a session-level recall of $1/4 = 25\%$.

2. **Event-Level Accounting**:
   - Evaluates whether the contiguous multi-day anomaly event as a whole was successfully identified.
   - Because the detector successfully flagged the anomaly on Day 4, the event as a whole is counted as a True Positive ($\text{TP}_{\text{event}} = 1, \text{FN}_{\text{event}} = 0$), yielding an event-level recall of $100\%$.

AttendSure's Algorithm Laboratory displays **both** perspectives to ensure complete evaluation transparency.

---

## 5. Optical Estimation Error Metrics

The simulated camera counter is evaluated against manual roll-call ground truth using:

- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |y_i - \hat{y}_i|$$
  where $y_i$ is manual headcount and $\hat{y}_i$ is estimated camera count.

- **Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{100\%}{M} \sum_{i=1, y_i > 0}^{M} \frac{|y_i - \hat{y}_i|}{y_i}$$
  Sessions where manual present count $y_i = 0$ are excluded from the MAPE denominator to prevent division-by-zero errors.

---

## 6. Limitations & Threats to Validity

1. **Synthetic Assumptions**: Synthetic models use simplified generative distributions (e.g., Gaussian variation, step functions). Real classroom attendance patterns may exhibit seasonal factors, agricultural labor cycles, or cultural holidays not captured in these models.
2. **Simulated Camera Sensing**: The camera subsystem is an educational numerical simulation. It does not run deep neural networks, YOLO object detection, or live video decoding.
3. **Threshold Sensitivity**: The default thresholds ($\ge 25\%$ drop, $\ge 4$ repeated days, $\ge 20\%$ camera delta) were selected for explainability and clear college demonstration. Production deployment would require calibration against empirical longitudinal data.
4. **Non-Generalizability**: High precision and recall on synthetic benchmarks demonstrate internal algorithmic correctness under constructed test conditions; they do **not** establish real-world diagnostic accuracy in operational schools.
