# Security Policy

## 1. Supported Versions

| Version | Supported          | Security Maintenance Status |
| :---    | :---:              | :---                        |
| 1.0.x   | :white_check_mark: | Active Security Updates     |
| < 1.0   | :x:                | Deprecated                  |

---

## 2. Security & Privacy Philosophy

The **Rural School Attendance Integrity and Intervention Decision System** is engineered with strict **Privacy-by-Design** and **Offline-First** principles:

1. **Zero Personally Identifiable Information (Zero-PII)**:
   - The database schema models attendance exclusively at the aggregate cohort level (`class_id`, `expected_enrollment`, `present_count`, `absent_count`).
   - The system does not collect, store, or process student names, national identification numbers, student roll numbers, or facial biometric templates.
2. **In-Memory Camera Processing**:
   - The browser-based classroom photo confirmation tool processes images strictly in-memory during roll call.
   - Raw image bytes and classroom photos are **never written to disk or stored in SQLite**.
3. **Offline Execution & Zero Network Egress**:
   - The core application operates entirely offline on a local SQLite database with zero outbound network calls, cloud tracking, or third-party telemetry.
4. **Non-Punitive Decision Support**:
   - System anomaly detection signals are advisory flags for administrative review, never automated accusations of fraud or grounds for automated punishment.

---

## 3. Machine Learning Model Deserialization Notice

The project bundles a serialized Decision Tree model artifact (`attendance_decision_tree.joblib`).

> [!CAUTION]
> **Arbitrary Code Execution Warning on Untrusted Models:**
> In Python, loading serialized pickle or Joblib files can execute arbitrary bytecode.
> - AttendSure loads only the locally bundled artifact from a static repository path (`DEFAULT_MODEL_PATH`).
> - The application provides **no user-facing upload endpoints** for external model binaries.
> - Never replace `attendance_decision_tree.joblib` with an untrusted third-party binary file.
> - Users who prefer not to load serialized binaries can regenerate the model directly from source code using synthetic data in under one second (`python scripts/reproduce_benchmarks.py`).

---

## 4. Reporting a Security Vulnerability

If you discover a security vulnerability or privacy concern in AttendSure:

1. **Do not disclose the issue publicly** in GitHub issues, pull requests, or public forums.
2. Please report the issue privately through **[GitHub Security Advisories](https://github.com/ashishkumartripathi/AttendSure/security/advisories)** or by emailing the project maintainers directly:
   - **Ashish Kumar Tripathi**: `ashishtripathi67991@gmail.com`
3. Include detailed reproduction steps, environment details, and potential impact.
4. Maintainers will acknowledge receipt within 48 hours and provide a coordinated remediation timeline.
