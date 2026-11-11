# Synthetic Demonstration Dataset for AttendSure

**Official Project Title:** Rural School Attendance Integrity and Intervention Decision System  
**Repository:** https://github.com/ashishkumartripathi/AttendSure  
**Dataset Directory:** `submission/demonstration/dataset/`  
**Dataset Purpose:** Academic demonstration and evaluation of anomaly detection, data invariants, and administrative review workflows.

---

## 1. Safety & Data Isolation Declaration

> [!IMPORTANT]
> **SYNTHETIC DATA DECLARATION:** Every record in this dataset is 100% synthetically generated for academic evaluation and demonstration.
> - **Zero Student PII:** Contains no student names, personal identifiers, roll numbers, or facial biometric data.
> - **Operational Database Isolation:** This dataset is completely decoupled from the operational database (`data/attendsure.db`) and the live Neon PostgreSQL database. Generating or inspecting this data does not alter production state.

---

## 2. Dataset Files & Record Counts

| Filename | Record Count | File Format | Description |
| :--- | :---: | :---: | :--- |
| `demo_attendance_sessions.csv` | **150** | CSV (UTF-8) | Class-level daily attendance sessions across 5 cohorts over 30 days ($5 \times 30$). |
| `demo_alerts.csv` | **6** | CSV (UTF-8) | Explainable anomaly detection signals triggered across the synthetic sessions. |
| `demo_alert_reviews.csv` | **3** | CSV (UTF-8) | Human-in-the-loop review actions demonstrating Acknowledged, Resolved, and Dismissed states. |

---

## 3. Schema & Column Definitions

### 3.1 `demo_attendance_sessions.csv`

| Column | Type | Allowed / Valid Range | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | String (UUIDv4) | RFC 4122 UUIDv4 | Primary key uniquely identifying the attendance roll-call session. |
| `class_id` | String | `CLASS-01-A` to `CLASS-05-A` | Monitored classroom cohort identifier. |
| `session_date` | Date | `YYYY-MM-DD` | Date of the attendance roll call (excluding Sundays). |
| `expected_enrollment` | Integer | $\ge 1$ (25 to 35) | Total enrolled students registered for the cohort. |
| `present_count` | Integer | $0 \le P \le E$ | Number of students marked present by the teacher. |
| `absent_count` | Integer | $0 \le A \le E$ | Number of students absent ($A = E - P$). |
| `webcam_status` | String | `SUCCESS`, `NOT_ATTEMPTED`, `CAMERA_UNAVAILABLE`, `DETECTION_FAILED` | Status of ephemeral camera estimation. |
| `webcam_count` | Integer / Null | $0 \le W \le E$ or null | Assistive headcount estimate from camera contour detection. |
| `record_source` | String | `SYNTHETIC` | Data provenance tracking. |
| `created_at` | Timestamp | ISO 8601 UTC | Timestamp of record insertion. |
| `ground_truth_is_anomaly` | Boolean | `True`, `False` | Ground truth label for evaluation. |
| `ground_truth_anomaly_type`| String | `NONE`, `ATTENDANCE_DROP`, `REPEATED_HEADCOUNT`, `WEBCAM_DISCREPANCY` | Ground truth anomaly category. |
| `ground_truth_notes` | String | Plain English text | Rationale for injected anomaly pattern. |
| `is_synthetic_demonstration`| Boolean | `True` | Safety marker preventing production ingestion. |

### 3.2 `demo_alerts.csv`

| Column | Type | Description |
| :--- | :--- | :--- |
| `alert_id` | String | Unique alert identifier (e.g., `ALT-3c834b35`). |
| `session_id` | String (UUIDv4) | Foreign key pointing to `demo_attendance_sessions.session_id`. |
| `class_id` | String | Cohort where anomaly occurred. |
| `session_date` | Date | Date when rule condition triggered. |
| `rule_id` | String | Identifier (`RULE_ATTENDANCE_DROP`, `RULE_REPEATED_HEADCOUNT`, `RULE_WEBCAM_DISCREPANCY`). |
| `rule_title` | String | Human-readable title of the detection rule. |
| `priority` | String | Institutional priority (`REVIEW_REQUIRED` or `INFO`). |
| `review_status` | String | Lifecycle state (`PENDING_REVIEW`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`). |
| `observed_value` | JSON String | Detected values (e.g., headcount, streak length, camera count). |
| `baseline_reference` | JSON String | Historical baseline used for evaluation (rolling median, window sessions). |
| `threshold_applied` | JSON String | Rule threshold (e.g., $\ge 30\%$ drop, $\ge 4$ days streak). |
| `explanation` | String | Plain-English explainable rationale for educators. |
| `created_at` | Timestamp | ISO 8601 UTC timestamp. |

### 3.3 `demo_alert_reviews.csv`

| Column | Type | Description |
| :--- | :--- | :--- |
| `review_id` | String | Unique audit review record identifier. |
| `alert_id` | String | Foreign key to `demo_alerts.alert_id`. |
| `reviewed_by` | String | Reviewing role and identifier (e.g., `Headmaster (HM-01)`). |
| `review_action` | String | Action taken (`ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`). |
| `notes` | String | Explanatory field note documenting the external justification. |
| `created_at` | Timestamp | ISO 8601 UTC timestamp of review decision. |

---

## 4. Injected Demonstration Anomaly Scenarios

The dataset embeds 11 positive anomaly sessions corresponding to:
1. **Multi-Day Repeated Headcount Episode 1 (`EVT-CLASS-02-A-1`):**
   - Cohort: `CLASS-02-A`, Dates: `2026-10-17` to `2026-10-20` (4 consecutive days).
   - Injected Pattern: Exactly 20 students marked present each day ($P=20, E=25$).
   - Detection: Alert fires on Day 4 session (`bc594585-9445-48c0-8ef8-c2d6f7fd5646`).
2. **Multi-Day Repeated Headcount Episode 2 (`EVT-CLASS-05-A-2`):**
   - Cohort: `CLASS-05-A`, Dates: `2026-10-20` to `2026-10-23` (4 consecutive days).
   - Injected Pattern: Exactly 27 students marked present each day ($P=27, E=32$).
   - Detection: Alert fires on Day 3 and Day 4 sessions.
3. **Severe Attendance Drop Anomaly:**
   - Cohort: `CLASS-02-A`, Date: `2026-11-03`.
   - Injected Pattern: Present count drops to 9 ($E=25$) vs. rolling median of 21.0 (57.1% drop).
   - Review Status: Marked `RESOLVED` with Headmaster note confirming localized monsoon flooding.
4. **Cross-Modal Camera Discrepancy (2 cases):**
   - Cohort: `CLASS-04-A`, Date: `2026-10-16` ($P=27, W=19$, discrepancy 8).
   - Cohort: `CLASS-02-A`, Date: `2026-10-26` ($P=23, W=17$, discrepancy 6).
   - Review Status: One marked `DISMISSED` due to window glare / shadow occlusion.

---

## 5. Independent Reproduction

To regenerate this demonstration dataset bit-for-bit:

```bash
cd AttendSure_Public_Release
python submission/demonstration/generate_demo_dataset.py
```
