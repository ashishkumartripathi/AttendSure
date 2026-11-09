# AttendSure — Feature-to-Test Traceability Matrix

**Project Title:** AttendSure: Explainable Attendance Integrity System  
**Test Framework:** pytest 8.4.2  
**Total Test Cases:** 328  
**Pass Rate:** 100.0% (328/328)  

---

## Traceability Matrix

| Functional Area | Requirement / Feature | Source File | Automated Test File | Test Cases | Verification Focus |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Data Contracts & Validation** | Count Invariant: $P + A = E$ | `data/validation.py` | `tests/test_data_validation.py` | 30 | Arithmetic identity, negative counts, non-int rejection |
| **Data Contracts & Validation** | UUIDv4 & Date Format Checking | `data/validation.py` | `tests/test_data_validation.py` | Included | RFC 4122 regex, non-future calendar dates |
| **Data Models & Types** | Domain Dataclasses | `data/models.py` | `tests/test_data_models.py` | 4 | Frozen dataclass immutability, literal type constraints |
| **SQLite Persistence** | Repository ACID & WAL Mode | `data/storage.py` | `tests/test_data_storage.py` | 31 | Schema migrations, composite unique indices, WAL activation |
| **SQLite Persistence** | Transaction Rollback & Cascades | `data/storage.py` | `tests/test_data_storage.py` | Included | Integrity error rollback, foreign key cascade delete |
| **CSV I/O** | Safe CSV Ingestion & Error Quarantining | `data/csv_io.py` | `tests/test_data_csv.py` | 25 | Line-by-line syntax validation, missing column checks |
| **CSV I/O** | Audit Export Engine | `data/csv_io.py` | `tests/test_data_csv.py` | Included | Zero-PII export serialization, alerts export |
| **Synthetic Generator** | Bit-for-Bit Seeded Scenarios | `data/generator.py` | `tests/test_data_generator.py` | 20 | Reproducibility across seeds, boundary constraints |
| **Synthetic Generator** | Nominal FP Streak Bounding (M5.8) | `data/generator.py` | `tests/test_data_generator.py` | Included | Capping nominal streaks < 4, 100% nominal specificity |
| **Demo Seeding** | Isolated Demo DB Generator | `data/demo_seed.py` | `tests/test_demo_seed.py` | 9 | Operational DB safety block, deterministic seed 42 cohorts |
| **Webcam Simulation** | Visible-Person Counter Simulation | `data/webcam.py` | `tests/test_webcam_counter.py` | 20 | NORMAL, DISCREPANCY, OFFLINE, FAILED states, immutability |
| **Detection Engine** | `RULE_ATTENDANCE_DROP` | `detection/rules.py` | `tests/test_detection_attendance_drop.py` | 15 | 5-session rolling median, 30% drop threshold, small classes |
| **Detection Engine** | `RULE_REPEATED_HEADCOUNT` | `detection/rules.py` | `tests/test_detection_repeated_headcount.py` | 19 | K >= 4 sub-100%, K >= 6 perfect attendance, reset on delta |
| **Detection Engine** | `RULE_WEBCAM_DISCREPANCY` | `detection/rules.py` | `tests/test_detection_webcam_discrepancy.py` | 15 | Dual threshold (diff >= 5 AND >= 20%), non-success handling |
| **Detection Engine** | Composite Anomaly Pipeline | `detection/rules.py` | `tests/test_detection_pipeline.py` | 15 | Multi-rule orchestration, alert ID deterministic SHA-256 |
| **Evaluation Engine** | Confusion Matrix & Metrics | `evaluation/metrics.py` | `tests/test_evaluation.py` | 28 | TP/FP/TN/FN counts, precision, recall, F1, zero-division |
| **Evaluation Engine** | Event vs. Session Level Recall | `evaluation/metrics.py` | `tests/test_evaluation.py` | Included | Multi-day sequence event scoring (100% event recall) |
| **Evaluation Engine** | Webcam MAE and MAPE Metrics | `evaluation/metrics.py` | `tests/test_evaluation.py` | Included | Evaluation over SUCCESS pairs, noise vs discrepancy error |
| **Service Layer** | Application Service Coordinator | `services/attendance_service.py`| `tests/test_services.py` | 18 | Session registration, alert status transitions, audit notes |
| **UI Layer (Streamlit)** | Overview Dashboard | `ui/views/overview.py` | `tests/test_ui_overview.py` | 5 | KPI cards, longitudinal trend plots, session history |
| **UI Layer (Streamlit)** | Attendance Register | `ui/views/register.py` | `tests/test_ui_register.py` | 11 | Manual entry, count invariant block, camera mock integration |
| **UI Layer (Streamlit)** | Intelligence Center | `ui/views/intelligence.py` | `tests/test_ui_intelligence.py` | 10 | Explainable alert cards, review status updates, filtering |
| **UI Layer (Streamlit)** | Reports & Ingestion | `ui/views/reports.py` | `tests/test_ui_reports.py` | 12 | Summary tables, CSV download buttons, CSV file uploader |
| **UI Layer (Streamlit)** | Algorithm Laboratory | `ui/views/laboratory.py` | `tests/test_ui_laboratory.py` | 12 | Real-time synthetic evaluation, confusion matrix display |
| **UI Layer (Streamlit)** | System Settings | `ui/views/settings.py` | `tests/test_ui_settings.py` | 5 | Threshold inspection, DB path status, schema diagnostic |
| **UI Layer (Streamlit)** | Cross-View State Integration | `ui/app.py`, `ui/state.py`| `tests/test_ui_integration.py` | 5 | Session state persistence, view navigation, clean styling |
| **End-to-End Workflows** | Complete User Demonstration | All Subsystems | `tests/test_demo_e2e.py` | 14 | Register session -> Detect -> Triage -> Export audit log |
| **Packaging & Metadata** | Package Definition | `pyproject.toml` | `tests/test_package.py` | 3 | Version consistency, module exports, clean import structure |
