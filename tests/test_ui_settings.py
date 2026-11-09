"""Headless automated UI integration tests for AttendSure Data & Settings.

Verifies:
1. Initial render without exceptions and clean empty state guidance.
2. Accurate live metrics and record source provenance breakdown.
3. Database connection diagnostics and health re-check.
4. Data governance, student privacy, and non-destructive storage disclosures.
5. Strict read-only guarantee (zero database writes or modifications).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_settings(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Data & Settings and run."""
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    try:
        at.sidebar.radio[0].set_value("Settings").run()
    except Exception:
        at.sidebar.radio[0].set_value("Data & Settings").run()


def test_settings_initial_render_on_empty_db(tmp_path: Path):
    """Scenario 1: Data & Settings renders cleanly on empty database with zero writes."""
    db_file = tmp_path / "settings_empty.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_settings(at)

    assert not at.exception
    assert len(at.error) == 0

    assert at.header[0].value in ("Settings", "Data & Settings")

    # Verify active DB path is rendered and tagged as override
    markdown_texts = [m.value for m in at.markdown]
    assert any(str(db_file) in text for text in markdown_texts)
    assert any("Runtime Test Override" in text for text in markdown_texts)

    # Health check is green
    success_texts = [s.value for s in at.success]
    assert any("Database Connection Healthy" in text for text in success_texts)

    # Metrics on empty db
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Attendance Records", metrics_by_label.get("Total Sessions")) == "0"
    assert metrics_by_label.get("Total Alerts", metrics_by_label.get("Total Anomaly Signals")) == "0"
    assert metrics_by_label.get("Needs Attention", metrics_by_label.get("Pending Review Alerts")) == "0"

    # Empty DB guidance displayed
    info_texts = [i.value for i in at.info]
    assert any("Empty Database Notice" in text for text in info_texts)

    # Verify strict zero database writes
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_settings_metrics_with_populated_data(tmp_path: Path):
    """Scenario 2: Accurate live counts and record source provenance breakdown."""
    db_file = tmp_path / "settings_populated.db"
    repository = AttendanceRepository(db_path=db_file)

    s1 = SessionRecord(
        session_id="00000000-0000-4000-8000-000000000001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        expected_enrollment=30,
        present_count=28,
        absent_count=2,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    s2 = SessionRecord(
        session_id="00000000-0000-4000-8000-000000000002",
        class_id="CLASS-02-B",
        session_date="2026-10-20",
        expected_enrollment=25,
        present_count=24,
        absent_count=1,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="CSV_IMPORT",
        created_at="2026-10-20T09:00:00Z",
    )
    s3 = SessionRecord(
        session_id="00000000-0000-4000-8000-000000000003",
        class_id="CLASS-03-C",
        session_date="2026-10-20",
        expected_enrollment=35,
        present_count=30,
        absent_count=5,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="SYNTHETIC",
        created_at="2026-10-20T09:00:00Z",
    )
    a1 = Alert(
        alert_id="alert-001",
        session_id="00000000-0000-4000-8000-000000000001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Unusual Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 28},
        baseline_reference={"rolling_median": 30.0},
        threshold_applied={"percentage_drop": 30.0},
        explanation="Test explanation",
        review_status="PENDING_REVIEW",
        created_at="2026-10-20T09:00:00Z",
    )
    a2 = Alert(
        alert_id="alert-002",
        session_id="00000000-0000-4000-8000-000000000002",
        class_id="CLASS-02-B",
        session_date="2026-10-20",
        rule_id="RULE_REPEATED_HEADCOUNT",
        rule_title="Repeated Identical Headcounts",
        priority="INFO",
        observed_value={"present_count": 24},
        baseline_reference={"run_length": 4},
        threshold_applied={"k_threshold": 4},
        explanation="Test explanation 2",
        review_status="RESOLVED",
        created_at="2026-10-20T09:00:00Z",
    )
    repository.save_session(s1)
    repository.save_session(s2)
    repository.save_session(s3)
    repository.save_alerts([a1, a2])
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_settings(at)

    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Attendance Records", metrics_by_label.get("Total Sessions")) == "3"
    assert metrics_by_label.get("Total Alerts", metrics_by_label.get("Total Anomaly Signals")) == "2"
    assert metrics_by_label.get("Needs Attention", metrics_by_label.get("Pending Review Alerts")) == "1"
    assert metrics_by_label.get("Checked Alerts", metrics_by_label.get("Resolved Alerts")) == "1"

    # Record source breakdown
    assert metrics_by_label.get("Entered by Hand", metrics_by_label.get("Manual Roll-Call Entries")) == "1"
    assert metrics_by_label.get("Uploaded from File", metrics_by_label.get("Batch CSV Imports")) == "1"
    assert metrics_by_label.get("Sample Records", metrics_by_label.get("Synthetic Benchmark Records")) == "1"


def test_settings_connection_recheck_button(tmp_path: Path):
    """Scenario 3: Connection re-check button executes cleanly and preserves state."""
    db_file = tmp_path / "settings_recheck.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_settings(at)

    btn_recheck = [b for b in at.button if b.key == "btn_recheck_db"][0]
    btn_recheck.click().run()

    assert not at.exception
    assert len(at.error) == 0

    success_texts = [s.value for s in at.success]
    assert any("Database Connection Healthy" in text for text in success_texts)


def test_settings_governance_and_privacy_disclosures(tmp_path: Path):
    """Scenario 4: Governance standards, zero biometrics, and seeding policies are rendered."""
    db_file = tmp_path / "settings_gov.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_settings(at)

    markdown_texts = [m.value for m in at.markdown]

    # Offline-first notice
    assert any("Offline-First & Local Storage Architecture" in text for text in markdown_texts)
    # Privacy / Zero biometrics
    assert any("Student Privacy & Zero Biometrics Policy" in text for text in markdown_texts)
    assert any("No PII Collected" in text for text in markdown_texts)
    assert any("Zero Biometric Data" in text for text in markdown_texts)
    # Non-destructive policy & deferred seeding
    assert any("Non-Destructive Storage & Seeding Policy" in text for text in markdown_texts)
    assert any("No Destructive Database Controls" in text for text in markdown_texts)
    assert any("Synthetic Data Seeding Deferred" in text for text in markdown_texts)


def test_settings_read_only_safety_across_reruns(tmp_path: Path):
    """Scenario 5: Navigating to and interacting with Data & Settings performs zero database writes."""
    db_file = tmp_path / "settings_readonly.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_settings(at)

    # Initial check
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0

    # Click recheck button
    btn_recheck = [b for b in at.button if b.key == "btn_recheck_db"][0]
    btn_recheck.click().run()

    # Repeated rerun
    at.run()

    # Verify database remains pristine with zero writes
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0
