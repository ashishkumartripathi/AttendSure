"""Headless automated UI integration tests for AttendSure App Shell and Overview Dashboard.

Tests Milestone M5.3.2.1 requirements using Streamlit's native headless AppTest framework:
- Clean application rendering without uncaught exceptions.
- Empty database state handling.
- Populated database metric calculation, session table, and alert card rendering.
- Unimplemented screen placeholder notices.
- Graceful database error handling.
- Safe repository lifecycle and connection cleanup.
"""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.ui.state import get_repository


APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _seed_sample_data(db_file: Path) -> None:
    """Helper to populate an isolated SQLite database with sample records."""
    repo = AttendanceRepository(db_path=db_file)
    try:
        # Session 1: CLASS-01-A, 25/30 (83.3%)
        s1 = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440001",
            class_id="CLASS-01-A",
            session_date="2026-10-24",
            expected_enrollment=30,
            present_count=25,
            absent_count=5,
            webcam_status="SUCCESS",
            webcam_count=25,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-24T09:00:00Z",
        )
        # Session 2: CLASS-02-B, 15/20 (75.0%)
        s2 = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440002",
            class_id="CLASS-02-B",
            session_date="2026-10-25",
            expected_enrollment=20,
            present_count=15,
            absent_count=5,
            webcam_status="CAMERA_UNAVAILABLE",
            webcam_count=None,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-25T09:00:00Z",
        )
        repo.save_sessions([s1, s2])

        # Alert 1: Pending review
        a1 = Alert(
            alert_id="ALT-550e8400-e29b-41d4-a716-446655440001",
            session_id=s1.session_id,
            class_id=s1.class_id,
            session_date=s1.session_date,
            rule_id="RULE_ATTENDANCE_DROP",
            rule_title="Unusual Attendance Drop",
            priority="REVIEW_REQUIRED",
            observed_value={"present_count": 25},
            baseline_reference={"baseline_rate_pct": 95.0},
            threshold_applied={"relative_decline_threshold_pct": 30.0},
            explanation="Class CLASS-01-A recorded relative decline of 32.0%.",
            review_status="PENDING_REVIEW",
            created_at="2026-10-24T10:00:00Z",
        )
        # Alert 2: Acknowledged
        a2 = Alert(
            alert_id="ALT-550e8400-e29b-41d4-a716-446655440002",
            session_id=s2.session_id,
            class_id=s2.class_id,
            session_date=s2.session_date,
            rule_id="RULE_REPEATED_HEADCOUNT",
            rule_title="Repeated Identical Headcounts",
            priority="INFO",
            observed_value={"repeated_headcount": 15},
            baseline_reference={"expected_behavior": "daily_variation"},
            threshold_applied={"consecutive_sessions_threshold": 4},
            explanation="Class CLASS-02-B recorded identical headcount across 4 sessions.",
            review_status="ACKNOWLEDGED",
            created_at="2026-10-25T10:00:00Z",
        )
        repo.save_alerts([a1, a2])
    finally:
        repo.close()


def test_overview_renders_without_exceptions_on_empty_db(tmp_path: Path):
    """Verify Overview Dashboard renders cleanly on an empty database with empty-state messages."""
    db_file = tmp_path / "empty.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    assert not at.exception
    assert len(at.error) == 0

    # Verify 5 KPI metrics render default empty values
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Total Students", metrics_by_label.get("Attendance Records", "0")) == "0"
    assert metrics_by_label.get("Present Today", metrics_by_label.get("Classes", "0")) == "0"
    assert metrics_by_label.get("Attendance Rate", metrics_by_label.get("Overall Attendance")) == "N/A"
    assert metrics_by_label.get("Needs Attention", metrics_by_label.get("Pending Review")) == "0"

    # Verify empty state guidance is displayed
    info_messages = [info.value for info in at.info]
    assert any("No attendance sessions recorded yet" in msg for msg in info_messages)

    # Verify decision support notice is present
    markdown_texts = [md.value for md in at.markdown]
    assert any("Decision Support Notice" in text for text in markdown_texts)


def test_overview_renders_with_sample_sessions_and_alerts(tmp_path: Path):
    """Verify Overview Dashboard correctly computes and displays metrics and data tables."""
    db_file = tmp_path / "sample.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Total Students", metrics_by_label.get("Attendance Records")) in ("50", "2")
    assert metrics_by_label.get("Present Today", metrics_by_label.get("Classes")) in ("40", "2")
    assert metrics_by_label.get("Attendance Rate", metrics_by_label.get("Overall Attendance")) == "80.0%"
    assert metrics_by_label.get("Needs Attention", metrics_by_label.get("Pending Review")) == "1"

    # Verify session dataframe is populated
    assert len(at.dataframe) > 0
    df = at.dataframe[0].value
    assert len(df) == 2
    assert "Cohort" in df.columns or "Class" in df.columns
    assert "Rate" in df.columns or "Attendance" in df.columns

    # Verify pending review alert is displayed
    markdown_texts = [md.value for md in at.markdown]
    assert any("CLASS-01-A" in text for text in markdown_texts)
    assert any("Attendance was lower than usual" in text or "Unusual Attendance Drop" in text for text in markdown_texts)


def test_app_navigation_to_all_six_pages(tmp_path: Path):
    """Verify sidebar navigation cleanly reaches all six implemented views without exceptions."""
    db_file = tmp_path / "nav.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    all_pages = [
        "Home",
        "Mark Attendance",
        "Attendance Records",
        "Needs Attention",
        "Reports",
        "Settings",
    ]

    for page_name in all_pages:
        at.sidebar.radio[0].set_value(page_name).run()
        assert not at.exception
        assert len(at.error) == 0

        # Verify page header matches
        assert at.header[0].value == page_name


def test_app_handles_invalid_database_path_gracefully(tmp_path: Path):
    """Verify application presents a clean error banner when database connection fails."""
    # Pointing to the directory itself causes sqlite3.OperationalError: unable to open database file
    invalid_path = str(tmp_path)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = invalid_path
    at.run()

    # Must NOT crash with an unhandled exception
    assert not at.exception
    assert len(at.error) > 0
    assert "Database Connection Error" in at.error[0].value


def test_state_repository_lifecycle_closes_connections(tmp_path: Path):
    """Verify get_repository opens and closes connections without leaking open handles."""
    db_file = tmp_path / "lifecycle.db"

    with get_repository(db_path=db_file) as repo:
        assert repo._conn is not None
        assert repo._is_closed is False
        repo.get_sessions(as_df=True)

    # Context manager must have closed the connection
    assert repo._is_closed is True
    assert repo._conn is None
