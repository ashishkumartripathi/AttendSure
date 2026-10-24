# AGENTS.md — Development Guidelines for AttendSure

This document defines core behavioral constraints, development practices, and project philosophy for all automated coding agents contributing to **AttendSure**.

---

## 1. Core Operating Principles

### 1.1 Inspect Before Editing
- Always read existing files, verify directory contents, and understand context before suggesting or executing code modifications.
- Never assume a file exists or is in a specific state; confirm with inspection tools first.

### 1.2 Preserve Existing Work
- Do not delete, overwrite, or discard existing user work or working code unless explicitly requested by the user.
- Preserve existing comments, docstrings, and documentation unless directly superseded by updated implementation.

### 1.3 Small, Reviewable Increments
- Structure tasks into discrete, modular steps.
- Avoid massive, monolithic diffs that mix refactoring with feature development.
- Ensure every step leaves the workspace in a consistent, testable state.

---

## 2. Domain & System Guidelines

### 2.1 Transparent & Explainable Anomaly Detection
- Every detection rule or anomaly signal **must produce a clear, human-interpretable explanation**.
- Explanations must explicitly specify:
  1. **Rule Name**: Identifier and description of the detection rule triggered.
  2. **Observed Values**: The actual values detected in the session/record (e.g., observed headcount = 12).
  3. **Baseline Reference**: The historical or expected baseline used for comparison (e.g., rolling median = 35).
  4. **Rationale**: Plain-language justification explaining why this pattern was flagged.
- Do not implement opaque heuristics, uncalibrated black-box models, or unexplained anomaly score thresholds.

### 2.2 Decision Support, Never Accusation
- All system outputs, alert strings, UI labels, and documentations must treat anomalies strictly as **signals for human review**.
- **Never** frame alerts as automatic accusations, proof of fraud, or conclusive evidence of misconduct. School administrators and educators must make all final determinations.

### 2.3 No Unsupported Security or Compliance Claims
- Do not claim that AttendSure is "tamper-proof," "blockchain-secured," "military-grade encrypted," or "certified compliant" (with FERPA, GDPR, etc.) unless such mechanisms have been formally implemented, validated, and tested.
- State security, privacy, and storage characteristics accurately according to what is actually built (e.g., local unencrypted SQLite file, offline file processing).

---

## 3. Engineering & Quality Standards

### 3.1 Test-Driven Detectors
- Every detector function or rule must be accompanied by comprehensive tests in `tests/`.
- Tests must cover:
  - Baseline nominal scenarios (no false alarms on normal attendance).
  - Positive triggers (reliable detection of known anomalies).
  - Boundary and edge cases (empty inputs, single-entry sessions, missing columns, zero attendance).
- Use `pytest` for all unit and integration tests.

### 3.2 Data Privacy & Synthetic Data Policy
- **Never commit real student data, personally identifiable information (PII), or live school credentials** to the repository.
- Use only synthetic data generators or strictly anonymized mock records for development, testing, and demonstrations.
- Ensure `.env`, local database files (`*.db`, `*.sqlite`), and data artifacts remain untracked per `.gitignore`.

### 3.3 Technology Stack & Compatibility
- Keep core dependencies minimal: Python (>= 3.13), Streamlit, SQLite, Pandas, and pytest.
- Ensure all libraries and dependencies maintain compatibility with Python 3.13 on standard operating systems (Windows, Linux, macOS).
- Maintain the offline-first design: core processing must never require outbound internet calls or paid third-party AI APIs.
