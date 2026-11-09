# AttendSure — Data Contract & Interface Specification

**Document Version:** 1.0.0-approved  
**Status:** APPROVED SPECIFICATION (PRE-IMPLEMENTATION BASELINE)  
**Lead Authors:** Member A (Core/Data Lead) & Member B (UI/Frontend Lead)  
**Target Stack:** Python >= 3.13, Pandas, SQLite, Streamlit, pytest  

---

## 1. Executive Summary & Core Principles

AttendSure is an offline-first academic prototype engineered to support attendance integrity monitoring in rural schools. This document serves as the authoritative, approved data contract defining shared schemas, validation rules, explainable alert structures, detection algorithms, evaluation protocols, and module interfaces for the AttendSure system.

### Core Architectural Principles
1. **Explainable Decision Support**: AttendSure provides signals for human educator and administrator review. An alert is **never** an automated accusation or proof of fraud or negligence.
2. **Strict Data Privacy**: Real student names, personal identifiers (PII), biometric identifiers, and facial recognition are strictly out of scope. All records use synthetic, anonymized group-level data.
3. **Offline-First Resilience**: All core data processing, rule engines, persistence, and dashboards operate completely locally without external network dependencies or paid third-party AI APIs.
4. **Decoupled Modularity**: Data ingestion and persistence (Member A) and Streamlit dashboard presentation (Member B) interact through stable, documented DataFrame and object contracts defined herein.

---

## 2. Attendance Session Record Schema

An **Attendance Session Record** represents the aggregated attendance count for a single classroom or student cohort during a distinct educational session (e.g., daily roll call).

### 2.1 Field Specification

| Field Name | Type | Required? | Validation Rules / Constraints | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `session_id` | `str` | **Required** | Standard RFC 4122 UUIDv4 string. Unique primary key. Pattern: `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` | Universally unique identifier for the attendance session. | `"550e8400-e29b-41d4-a716-446655440000"` |
| `class_id` | `str` | **Required** | Non-empty synthetic string. Regex: `^[A-Za-z0-9_-]{2,32}$` | Synthetic identifier for the classroom, grade, or student cohort. | `"CLASS-05-A"` |
| `session_date` | `str` | **Required** | ISO 8601 calendar date format `YYYY-MM-DD`. Must not be in the future relative to system time. | The calendar date on which the attendance session occurred. | `"2026-10-25"` |
| `expected_enrollment` | `int` | **Required** | Integer `>= 1`. Maximum realistic class size (e.g., `<= 150`). | Total registered student enrollment for the specific class. | `35` |
| `present_count` | `int` | **Required** | Integer `>= 0` and `<= expected_enrollment`. | Number of students recorded as physically present by the educator. | `31` |
| `absent_count` | `int` | **Required** | Integer `>= 0`. Must satisfy invariant: `present_count + absent_count == expected_enrollment`. | Number of students recorded as absent. Inconsistent records are rejected. | `4` |
| `webcam_count` | `int` / `null` | **Optional** | Nullable integer. If `webcam_status == "SUCCESS"`, must be integer `>= 0`. For all other statuses, must be `null` (`None`). | Estimated count of visible individuals detected by the non-identifying person counter. | `30` or `null` |
| `webcam_status` | `str` | **Required** | Enum: `["SUCCESS", "NOT_ATTEMPTED", "CAMERA_UNAVAILABLE", "DETECTION_FAILED"]`. | Operational status of the optional person-counting module for this session. | `"SUCCESS"` or `"NOT_ATTEMPTED"` |
| `record_source` | `str` | **Required** | Enum: `["SYNTHETIC", "MANUAL_ENTRY", "CSV_IMPORT"]`. | Origin channel through which the session was ingested into AttendSure. | `"SYNTHETIC"` |
| `created_at` | `str` | **Required** | ISO 8601 UTC timestamp: `YYYY-MM-DDTHH:MM:SSZ`. | Audit timestamp recording when the record was created locally. | `"2026-10-25T09:15:00Z"` |

### 2.2 Relational & Uniqueness Constraints
- **Primary Key**: `session_id` must be unique across all records.
- **Session Uniqueness per Cohort**: Only one attendance session is permitted per `class_id` and `session_date`. The composite key `(class_id, session_date)` must be strictly unique in storage and validation batches.
- **Strict Invariant Enforcement**: The condition `present_count + absent_count == expected_enrollment` is mandatory. Inconsistent records must be explicitly rejected with a validation error; the system must **not** silently alter or auto-correct counts.
- **Privacy Assurance**: No student names, personal identifiers, photos, facial recognition, or biometric data are captured, stored, or processed.

---

## 3. Data Validation Rules & Error Handling

Data ingestion strictly distinguishes between **Invalid Records** (which must be rejected) and **Hardware Degradation** (which must be handled gracefully without invalidating manual attendance).

### 3.1 Hard Invalidation Rules (Record Rejected)
A record failing any of the following checks is invalid and must not be persisted to SQLite or processed by detector engines:
1. **Missing Required Fields**: Any record where `session_id`, `class_id`, `session_date`, `expected_enrollment`, `present_count`, `absent_count`, `webcam_status`, `record_source`, or `created_at` is missing, blank, or `None`.
2. **Duplicate Primary Key**: Any record whose `session_id` already exists in storage or within the ingestion batch.
3. **Duplicate Class-Date Pair**: Any record where `(class_id, session_date)` already exists in storage or appears more than once in the batch.
4. **Invalid Date Format or Temporal Bounds**: Dates that do not strictly match `YYYY-MM-DD`, represent invalid calendar dates (e.g., `2026-02-31`), or have `session_date > current_local_date`.
5. **Malformed Identifiers**: `session_id` not adhering to standard UUIDv4 syntax, or `class_id` failing allowed character/length regex.
6. **Negative Counts**: Any negative integer in `expected_enrollment`, `present_count`, `absent_count`, or `webcam_count`.
7. **Enrollment Boundary Violations**: `present_count > expected_enrollment` or `absent_count > expected_enrollment`.
8. **Count Inconsistency**: Any record where `present_count + absent_count != expected_enrollment`. Silent correction is forbidden.
9. **Invalid Webcam Count-State Mappings**:
   - `webcam_status == "SUCCESS"` but `webcam_count is None` or `webcam_count < 0`.
   - `webcam_status != "SUCCESS"` but `webcam_count is not None` (must be `null`).

### 3.2 Optional Hardware Fallback (Record Accepted)
The webcam person-counting module is strictly an **optional verification aid**:
- If the camera is disabled (`NOT_ATTEMPTED`), disconnected/unsupported (`CAMERA_UNAVAILABLE`), or obscured (`DETECTION_FAILED`):
  - **The manual attendance record remains 100% valid.**
  - `webcam_count` is set to `null` (`None`).
  - Core attendance detectors (`RULE_ATTENDANCE_DROP`, `RULE_REPEATED_HEADCOUNT`) execute without hindrance.
  - The webcam discrepancy detector is safely skipped.

---

## 4. Explainable Alert Structure & Review Workflow

Every detection rule outputs a standardized alert payload. An alert is an **evidence-backed review signal** for educators, providing transparent metrics and plain-language reasoning without accusatory language.

### 4.1 Alert Data Schema

| Field Name | Type | Required? | Constraints | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `alert_id` | `str` | **Required** | Unique identifier: `^ALT-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` or prefixed UUID. | Unique primary key for the alert. | `"ALT-550e8400-e29b-41d4-a716-446655440000"` |
| `session_id` | `str` | **Required** | References valid `session_id`. | Foreign identifier linking to the flagged session. | `"550e8400-e29b-41d4-a716-446655440000"` |
| `class_id` | `str` | **Required** | References valid `class_id`. | Classroom cohort associated with the alert. | `"CLASS-05-A"` |
| `session_date` | `str` | **Required** | ISO 8601 date `YYYY-MM-DD`. | Calendar date of the flagged session. | `"2026-10-25"` |
| `rule_id` | `str` | **Required** | Standard rule enum: `["RULE_ATTENDANCE_DROP", "RULE_REPEATED_HEADCOUNT", "RULE_WEBCAM_DISCREPANCY"]`. | Machine-readable rule identifier. | `"RULE_ATTENDANCE_DROP"` |
| `rule_title` | `str` | **Required** | Human-readable title string. | Clear descriptive title for UI presentation. | `"Unusual Attendance Drop"` |
| `priority` | `str` | **Required** | Enum: `["INFO", "REVIEW_REQUIRED"]`. | Review prioritization tier for educator workflow. | `"REVIEW_REQUIRED"` |
| `observed_value` | `dict` | **Required** | Structured dictionary of observed metrics. | Actual values detected in the session record. | `{"present_count": 14, "attendance_rate_pct": 40.0}` |
| `baseline_reference`| `dict` | **Required** | Structured dictionary of baseline metrics. | Baseline metrics used for comparison. | `{"baseline_type": "rolling_median", "window_sessions": 5, "baseline_rate_pct": 80.0}` |
| `threshold_applied` | `dict` | **Required** | Structured dictionary of thresholds applied. | Threshold criteria that triggered the alert. | `{"relative_decline_threshold_pct": 30.0, "observed_relative_decline_pct": 50.0}` |
| `explanation` | `str` | **Required** | Non-empty text string. | Plain-language, non-accusatory rationale explaining the alert. | `"Class CLASS-05-A recorded an attendance rate of 40.0% (14/35), representing a 50.0% relative decline from its 5-session baseline of 80.0% (threshold: 30.0% relative decline). Please review whether seasonal illness, transit issues, or reporting entry errors occurred."` |
| `review_status` | `str` | **Required** | Enum: `["PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]`. | Administrative tracking workflow state. Defaults to `"PENDING_REVIEW"`. | `"PENDING_REVIEW"` |
| `created_at` | `str` | **Required** | ISO 8601 UTC timestamp. | When the alert was generated locally. | `"2026-10-25T11:00:00Z"` |

### 4.2 Approved Alert Priority Tiers
- `INFO`: Informational signal highlighting unusual conditions that do not immediately require operational intervention (e.g., small discrepancies within benign bounds, or isolated low-confidence variations).
- `REVIEW_REQUIRED`: Significant deviations meeting approved alert thresholds that warrant human verification and context checking by school staff.

### 4.3 Approved Review Status Workflow
```text
[ PENDING_REVIEW ] ──(Teacher/Admin opens queue)──> [ ACKNOWLEDGED ]
        │                                                    │
        ├──(Verified valid explanation, e.g. storm/bus)────> [ RESOLVED ]
        └──(Determined false trigger or normal variance)───> [ DISMISSED ]
```

---

## 5. Detection Rule Input & Logic Specifications

All detectors receive chronologically sorted session DataFrames and emit lists of `Alert` objects. Every alert must be traceable to the underlying records and parameters.

### 5.1 Rule 1: `RULE_ATTENDANCE_DROP` (Unusual Attendance Drop)

- **Objective**: Detect sharp, unexpected declines in class attendance relative to recent historical attendance for the same cohort.
- **Session Ordering**: All historical records for the specified `class_id` must be sorted strictly in ascending chronological order by `session_date`.
- **Baseline Window**:
  - The baseline is calculated from the **5 immediately preceding valid sessions** for the same `class_id` strictly prior to the current session (`session_date < current_session_date`).
  - **Self-Exclusion**: The current session is strictly excluded from its own baseline calculation.
  - **Minimum History Requirement**: Exactly 5 prior valid sessions are required. If fewer than 5 prior sessions exist in the dataset for that class, the rule is **skipped** without generating an alert.
- **Mathematical Formulation**:
  1. For each prior session $i \in [t-5, t-1]$:
     $$\text{rate}_i = \frac{\text{present\_count}_i}{\text{expected\_enrollment}_i} \times 100$$
  2. Compute baseline rate:
     $$\text{baseline\_rate} = \text{median}(\text{rate}_{t-5}, \dots, \text{rate}_{t-1})$$
  3. Compute current session rate:
     $$\text{current\_rate} = \frac{\text{present\_count}_t}{\text{expected\_enrollment}_t} \times 100$$
  4. Division by Zero Guard:
     - If $\text{baseline\_rate} == 0.0$, skip the relative decline calculation to avoid division by zero; do not generate an alert.
  5. Compute relative percentage decline:
     $$\text{relative\_decline} = \frac{\text{baseline\_rate} - \text{current\_rate}}{\text{baseline\_rate}} \times 100$$
- **Trigger Condition**:
  - The rule triggers if and only if $\text{relative\_decline} \ge 30.0\%$.
  - Negative decline ($\text{current\_rate} > \text{baseline\_rate}$, i.e., attendance improved) must **never** trigger an alert.
- **Critical Distinction: Relative Percentage Decline vs. Percentage-Point Difference**:
  - *Percentage-Point Difference*: $\Delta_{\text{pts}} = \text{baseline\_rate} - \text{current\_rate}$.
  - *Relative Percentage Decline*: $\text{relative\_decline} = (\Delta_{\text{pts}} / \text{baseline\_rate}) \times 100$.
  - *Illustrative Examples*:
    - **Example A**: Baseline = 80.0%, Current = 50.0%. Difference is 30.0 percentage points. Relative decline = $(30.0 / 80.0) \times 100 = 37.5\% \ge 30.0\% \rightarrow$ **TRIGGERS ALERT**.
    - **Example B**: Baseline = 20.0%, Current = 10.0%. Difference is only 10.0 percentage points. Relative decline = $(10.0 / 20.0) \times 100 = 50.0\% \ge 30.0\% \rightarrow$ **TRIGGERS ALERT**.
    - **Example C**: Baseline = 90.0%, Current = 70.0%. Difference is 20.0 percentage points. Relative decline = $(20.0 / 90.0) \times 100 = 22.2\% < 30.0\% \rightarrow$ **DOES NOT TRIGGER**.
- **Assigned Priority**: `REVIEW_REQUIRED`.
- **Non-Accusatory Explanation Template**:
  `"Class {class_id} recorded an attendance rate of {current_rate:.1f}% ({present_count}/{expected_enrollment}) on {session_date}, which represents a {relative_decline:.1f}% relative decline from its 5-session rolling baseline of {baseline_rate:.1f}%. Please verify whether external factors (e.g., weather, transit disruption, local health conditions) impacted attendance."`

---

### 5.2 Rule 2: `RULE_REPEATED_HEADCOUNT` (Repeated Identical Headcounts)

- **Objective**: Flag instances where an identical manual headcount is entered across multiple consecutive sessions, which may indicate static boilerplate reporting rather than verified daily roll calls.
- **Session Ordering**: Analyze sessions chronologically by `session_date` within each `class_id`.
- **Sequence Definition**:
  - The detector tracks consecutive sessions with identical `present_count` values within the same `class_id`.
  - **Enrollment Changes**: Changes in `expected_enrollment` across sessions do **not** reset the repeated-count sequence.
- **Trigger Conditions (Approved Option 1 Invariant)**:
  - **Standard Threshold ($K \ge 4$)**: 4 or more consecutive sessions with the exact same `present_count`.
  - **100% Attendance Exception ($K \ge 6$)**: If and only if **every** session in the consecutive sequence has `present_count == expected_enrollment` (100% attendance throughout the run), require 6 or more ($K \ge 6$) consecutive sessions to trigger an alert.
  - **Mixed or Non-Perfect Sequence**: If any session within the consecutive sequence has `present_count < expected_enrollment`, the standard threshold ($K \ge 4$) applies.
- **Illustrative Examples**:
  - *Example A (Constant Present Count, Changing Enrollment)*: A class logs `present_count = 24` on 4 consecutive dates, but enrollment shifts due to a roster update: Day 1 (24/28), Day 2 (24/28), Day 3 (24/29), Day 4 (24/29). Because `present_count` is identical across all 4 dates, the sequence run length is $K = 4$. Since attendance was not 100% throughout, the standard threshold ($K \ge 4$) applies $\rightarrow$ **TRIGGERS ALERT** on Day 4.
  - *Example B (Mixed Perfect and Non-Perfect Attendance)*: A class logs `present_count = 20` across 4 consecutive days: Day 1 (20/20, 100%), Day 2 (20/20, 100%), Day 3 (20/20, 100%), Day 4 (20/22, 90.9%). Because Day 4 is not 100% attendance, the sequence is not pure 100%; the standard threshold ($K \ge 4$) applies $\rightarrow$ **TRIGGERS ALERT** on Day 4.
  - *Example C (Pure 100% Attendance)*: A small cohort logs `present_count = 15` and `expected_enrollment = 15` (100% attendance) on 4 consecutive days. Because every session in the run has `present_count == expected_enrollment`, the $K \ge 6$ threshold governs $\rightarrow$ **DOES NOT TRIGGER** at $K = 4$ (triggers only if the sequence reaches $K \ge 6$).
- **Assigned Priority**: `REVIEW_REQUIRED`.
- **Alert Evidence & Explanation**:
  - The alert must explicitly state the repeated headcount, the consecutive run length $K$, and the inclusive date span $[ \text{start\_date}, \text{end\_date} ]$.
- **Non-Accusatory Explanation Template**:
  `"Class {class_id} recorded an identical headcount of {present_count} students across {K} consecutive sessions from {start_date} to {end_date}. This pattern warrants human confirmation to ensure daily roll-call verification is active."`

---

### 5.3 Rule 3: `RULE_WEBCAM_DISCREPANCY` (Optional Visible-Person Discrepancy)

- **Objective**: Cross-reference the teacher's manual headcount against the non-identifying visible-person count estimated by the camera module.
- **Phase 1 Scope**: Phase 1 uses a **mock/simulated interface**. Live camera capture hardware loops and third-party computer vision framework installations are deferred.
- **Execution Guard**:
  - Evaluated **only** when `webcam_status == "SUCCESS"` and `webcam_count is not None`.
  - If `webcam_status != "SUCCESS"`, the rule is safely skipped without generating an alert.
- **Discrepancy Formulations**:
  1. Absolute Difference:
     $$\text{abs\_diff} = |\text{webcam\_count} - \text{present\_count}|$$
  2. Relative Difference Calculation:
     - For positive manual counts ($\text{present\_count} > 0$):
       $$\text{relative\_diff} = \frac{|\text{webcam\_count} - \text{present\_count}|}{\text{present\_count}} \times 100$$
     - When manual count is zero ($\text{present\_count} == 0$):
       - Do **not** divide by zero. Relative difference is undefined; evaluate trigger using the absolute difference threshold only.
- **Trigger Conditions**:
  - If $\text{present\_count} > 0$: Triggers when **both** $\text{abs\_diff} \ge 5$ individuals **and** $\text{relative\_diff} \ge 20.0\%$.
  - If $\text{present\_count} == 0$: Triggers when $\text{abs\_diff} \ge 5$ individuals.
- **Assigned Priority**: `REVIEW_REQUIRED`.
- **Privacy & Non-Accusatory Principles**:
  - Visible-person counts represent anonymous geometric detections, **never** verified student identities.
  - Alerts must not be framed as evidence of falsification; occlusions, camera blind spots, movement, lighting, and students outside the field of view frequently cause natural discrepancies.
- **Non-Accusatory Explanation Template**:
  `"On {session_date}, manual roll call logged {present_count} students present, while the camera module estimated {webcam_count} visible individuals (difference of {abs_diff} people, {rel_diff_str}). Discrepancies may arise naturally from camera placement, physical occlusion, or students outside the camera's view."`

---

## 6. Evaluation Data Schema & Benchmarking Protocol

Detector performance is measured systematically using labelled synthetic datasets containing ground-truth annotations.

### 6.1 Evaluation Dataset Schema
Evaluation CSVs extend the standard session schema with ground-truth labels:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| *(All Session Fields)* | *(Section 2)* | Standard session data fields. |
| `ground_truth_is_anomaly` | `bool` | `True` if this session contains an injected synthetic anomaly; `False` for nominal baseline sessions. |
| `ground_truth_anomaly_type` | `str` | Enum: `["NONE", "ATTENDANCE_DROP", "REPEATED_HEADCOUNT", "WEBCAM_DISCREPANCY", "COMPOUND"]`. |
| `ground_truth_notes` | `str` | Plain-language documentation of the injected scenario (e.g., `"Injected 45% drop across 2 days"`). |

### 6.2 Benchmarking Metrics & Confusion Matrix
- **Prediction Matching**: A detector prediction is matched against ground truth for that specific session and rule.
- **Classification Categories**:
  - **True Positive (TP)**: Detector triggered an alert on a session where `ground_truth_is_anomaly == True` with matching anomaly type.
  - **False Positive (FP)**: Detector triggered an alert on a nominal session (`ground_truth_is_anomaly == False`).
  - **False Negative (FN)**: Detector failed to trigger an alert on an anomalous session (`ground_truth_is_anomaly == True`).
  - **True Negative (TN)**: Detector correctly remained silent on a nominal session (`ground_truth_is_anomaly == False`).
- **Standard Metrics**:
  $$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad \text{F1-Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
- **Confusion Matrix Format**:
  ```text
                  Actual Positive    Actual Negative
  Pred Positive        TP                 FP
  Pred Negative        FN                 TN
  ```
- **Rule Independence**: `RULE_ATTENDANCE_DROP` and `RULE_REPEATED_HEADCOUNT` must be evaluated individually as well as in aggregate.

### 6.3 Decoupled Webcam Evaluation
Webcam estimation accuracy is evaluated completely independently from attendance integrity:
- Evaluated as a continuous numerical estimation task using:
  - **Mean Absolute Error (MAE)**: $\frac{1}{M}\sum |\text{webcam\_count}_j - \text{actual\_visible\_people}_j|$
  - **Mean Absolute Percentage Error (MAPE)**
- This ensures webcam estimation error does not corrupt attendance anomaly evaluation metrics.

---

## 7. Python Module Interfaces & Type Signatures

To ensure seamless integration between Member A's data/detector backend and Member B's Streamlit frontend, all code must adhere to these interfaces.

```python
"""
AttendSure Standard Data Contracts and Interfaces
Target: Python >= 3.13
"""
from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd

# -------------------------------------------------------------------------
# Core Domain Types
# -------------------------------------------------------------------------

WebcamStatus = Literal["SUCCESS", "NOT_ATTEMPTED", "CAMERA_UNAVAILABLE", "DETECTION_FAILED"]
RecordSource = Literal["SYNTHETIC", "MANUAL_ENTRY", "CSV_IMPORT"]
AlertPriority = Literal["INFO", "REVIEW_REQUIRED"]
ReviewStatus = Literal["PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]

@dataclass(frozen=True)
class SessionRecord:
    session_id: str                      # UUIDv4 string
    class_id: str                        # Synthetic class identifier
    session_date: str                    # ISO date YYYY-MM-DD
    expected_enrollment: int             # >= 1
    present_count: int                   # >= 0 and <= expected_enrollment
    absent_count: int                    # present_count + absent_count == expected_enrollment
    webcam_status: WebcamStatus          # SUCCESS, NOT_ATTEMPTED, etc.
    webcam_count: Optional[int]          # Non-negative int if SUCCESS, else None
    record_source: RecordSource          # SYNTHETIC, MANUAL_ENTRY, CSV_IMPORT
    created_at: str                      # ISO 8601 UTC timestamp

@dataclass(frozen=True)
class Alert:
    alert_id: str                        # Unique alert ID
    session_id: str                      # References SessionRecord.session_id
    class_id: str                        # References SessionRecord.class_id
    session_date: str                    # ISO date YYYY-MM-DD
    rule_id: str                         # e.g., "RULE_ATTENDANCE_DROP"
    rule_title: str                      # Human-readable title
    priority: AlertPriority              # INFO or REVIEW_REQUIRED
    observed_value: dict                 # Measured session metrics
    baseline_reference: dict             # Comparison baseline metrics
    threshold_applied: dict              # Trigger threshold details
    explanation: str                     # Plain-language explanation
    review_status: ReviewStatus          # PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED
    created_at: str                      # ISO 8601 UTC timestamp

@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str]
    cleaned_record: Optional[dict]

# -------------------------------------------------------------------------
# Module Interface: Data Validation (Member A)
# -------------------------------------------------------------------------
def validate_session_dict(record_data: dict) -> ValidationResult:
    """Validates a single session dictionary against the contract schema."""
    ...

def validate_session_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validates a batch DataFrame of sessions.
    Returns:
        (valid_df, rejected_df_with_errors)
    """
    ...

# -------------------------------------------------------------------------
# Module Interface: Synthetic Generator (Member A)
# -------------------------------------------------------------------------
def generate_synthetic_sessions(
    num_classes: int = 5,
    num_days: int = 30,
    anomaly_rate: float = 0.05,
    random_seed: int = 42,
    include_webcam: bool = False
) -> pd.DataFrame:
    """Generates synthetic session DataFrame containing labelled anomalies for evaluation."""
    ...

# -------------------------------------------------------------------------
# Module Interface: Anomaly Detection Engine (Member A)
# -------------------------------------------------------------------------
def detect_anomalies(
    sessions_df: pd.DataFrame,
    active_rules: Optional[list[str]] = None
) -> list[Alert]:
    """
    Runs configured rule-based detectors across validated session records.
    Returns a list of explainable Alert objects.
    """
    ...

# -------------------------------------------------------------------------
# Module Interface: Evaluation Engine (Member A)
# -------------------------------------------------------------------------
def evaluate_detector_performance(
    labelled_sessions_df: pd.DataFrame,
    generated_alerts: list[Alert]
) -> dict:
    """
    Computes TP, FP, TN, FN, Precision, Recall, F1, and Confusion Matrix.
    Returns summary dictionary suitable for Streamlit display.
    """
    ...

# -------------------------------------------------------------------------
# Module Interface: Mock Webcam Person-Counter (Phase 1 Shared)
# -------------------------------------------------------------------------
@dataclass(frozen=True)
class WebcamCounterResult:
    status: WebcamStatus
    estimated_count: Optional[int]
    confidence_score: Optional[float]
    diagnostic_message: str

def get_simulated_webcam_count(
    mode: Literal["NORMAL", "CAMERA_OFFLINE", "DISCREPANCY"] = "NORMAL",
    reference_present: int = 30
) -> WebcamCounterResult:
    """
    Phase 1 simulated person counter.
    Returns controlled mock results without hardware or heavy CV dependencies.
    """
    ...
```

---

## 8. Streamlit UI Integration Contract (Member B)

Member B's Streamlit frontend connects directly to Member A's backend interfaces using pandas DataFrames and `Alert` dataclass objects:

1. **Dashboard Overview Page**:
   - Ingests `sessions_df` to plot longitudinal attendance trends per `class_id`.
   - Displays alert metric cards grouped by `priority` (`REVIEW_REQUIRED`, `INFO`) and `rule_id`.
2. **Review & Audit Queue Page**:
   - Renders interactive table of `Alert` objects with clear column headers: Date, Class, Rule, Observed vs. Baseline, Priority, Plain-Language Explanation, and Review Status.
   - Allows educators to update `review_status` (`ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`) and export the audit trail to CSV.
3. **Model Evaluation & Benchmarking Page**:
   - Displays confusion matrix tables, Precision, Recall, and F1-Scores generated by `evaluate_detector_performance()`.
4. **Manual Record Entry Page**:
   - Web form mapping to `SessionRecord` fields. Enforces `present_count + absent_count == expected_enrollment` before submission.
   - Includes a "Simulate Camera Count" button linking to `get_simulated_webcam_count()`.

---

## 9. Record of Approved Architectural Decisions & Deferred Scope

The following decisions have been formally approved by Member A and Member B:

| # | Topic | Approved Decision | Rationale |
| :- | :--- | :--- | :--- |
| **D1** | **`absent_count` Persistence** | Explicitly persist `absent_count` with validation check `present + absent == enrollment`. | Enforces strict data integrity at the ingestion boundary; rejects conflicting manual sheets. |
| **D2** | **Session ID Format** | Standard RFC 4122 UUIDv4 string. | Industry-standard collision prevention; decoupled from business keys. |
| **D3** | **Session Uniqueness** | Enforce composite uniqueness on `(class_id, session_date)`. | Prevents multiple conflicting roll calls for the same class on the same day. |
| **D4** | **Drop Baseline Window** | 5-session rolling median per class, strictly excluding the current session. | Robust against past single-day anomalies; requires 5 prior sessions or skips. |
| **D5** | **Drop Relative Decline Formula** | Trigger on relative decline $\ge 30\%$: `(baseline - current) / baseline * 100`. Guard against division by zero if baseline is zero. | Correctly measures proportional drop rather than simple percentage-point difference. |
| **D6** | **Repeated Headcount Exception** | Require $K \ge 4$ consecutive sessions in general; require $K \ge 6$ consecutive sessions for 100% attendance. | Accommodates small cohorts where perfect attendance legitimately repeats across consecutive days. |
| **D7** | **Alert Priority Levels** | 2-tier: `INFO` and `REVIEW_REQUIRED`. | Provides clean, unambiguous operational triage for educators in Streamlit. |
| **D8** | **Alert Review Statuses** | 4-tier: `PENDING_REVIEW`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`. | Enables complete, audit-compliant review lifecycles. |
| **D9** | **Webcam Phase 1 Scope** | Mock / simulated interface in Phase 1; live camera dependencies deferred. | Keeps Phase 1 lightweight, offline, and reliable on all development machines without external CV packages. |
| **D10**| **Webcam Discrepancy Formula** | Trigger when `abs_diff >= 5` AND `rel_diff >= 20%`. For `present == 0`, use `abs_diff >= 5` only. | Avoids division by zero and eliminates false positives on minor single-student differences. |
| **D11**| **Repeated Headcount Enrollment Invariant (Approved Option 1)** | Consecutive runs track identical `present_count` within a class; changes in `expected_enrollment` do not reset the run. If every session in the sequence has `present_count == expected_enrollment`, require $K \ge 6$; otherwise, standard $K \ge 4$ applies. | Approved by Lead in M1 final verification audit to resolve ambiguity; ensures boilerplate headcounts are caught even during mid-term roster shifts, while strictly preserving 100% attendance leniency. |
