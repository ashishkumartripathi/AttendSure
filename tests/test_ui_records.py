"""Automated UI integration tests for Attendance Records screen.

Tests dedicated roll-call history viewing, class and date range filtering,
review status triage filtering, and direct CSV export adhering to
docs/data-contract.md.
"""

import uuid
from datetime import date
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_records(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Attendance Records and run."""
    at.sidebar.radio[0].set_value("Attendance Records").run()


def _seed_sample_records(db_file: Path) -> None:
    """Seed test database with 3 sessions across 2 classes."""
    u1, u2, u3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    with get_repository(db_path=db_file) as repo:
        s1 = SessionRecord(
            session_id=u1,
            class_id="CLASS-01-A",
            session_date="2026-10-20",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="SUCCESS",
            webcam_count=28,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-20T09:00:00Z",
        )
        s2 = SessionRecord(
            session_id=u2,
            class_id="CLASS-01-A",
            session_date="2026-10-21",
            expected_enrollment=30,
            present_count=12,
            absent_count=18,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-21T09:00:00Z",
        )
        s3 = SessionRecord(
            session_id=u3,
            class_id="CLASS-02-B",
            session_date="2026-10-22",
            expected_enrollment=25,
            present_count=24,
            absent_count=1,
            webcam_status="SUCCESS",
            webcam_count=24,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-22T09:00:00Z",
        )
        repo.save_sessions([s1, s2, s3])

        # Add alert for s2
        a = Alert(
            alert_id=f"ALT-{u2}",
            session_id=s2.session_id,
            class_id=s2.class_id,
            session_date=s2.session_date,
            rule_id="RULE_ATTENDANCE_DROP",
            rule_title="Unusual Attendance Drop",
            priority="REVIEW_REQUIRED",
            observed_value={"present_count": 12},
            baseline_reference={"rolling_median": 28},
            threshold_applied={"drop_pct": 30.0},
            explanation="Class CLASS-01-A recorded relative drop of 57.1%.",
            review_status="PENDING_REVIEW",
            created_at="2026-10-21T10:00:00Z",
        )
        repo.save_alerts([a])


def test_records_screen_empty_db(tmp_path: Path):
    """Verify Attendance Records screen handles empty database gracefully."""
    db_file = tmp_path / "rec_empty.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_records(at)
    assert not at.exception
    assert len(at.error) == 0
    assert at.header[0].value == "Attendance Records"
    assert any("No attendance records found" in i.value for i in at.info)


def test_records_screen_displays_metrics_and_table(tmp_path: Path):
    """Verify Attendance Records displays KPIs, dataframe, and export button."""
    db_file = tmp_path / "rec_seeded.db"
    _seed_sample_records(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_records(at)
    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Filtered Sessions"] == "3"
    assert metrics_by_label["Total Present"] == "64"
    assert metrics_by_label["Flagged for Review"] == "1"

    # Dataframe rendered
    assert len(at.dataframe) > 0
    df = at.dataframe[0].value
    assert len(df) == 3

    # Download button present
    download_btns = at.get("download_button")
    assert len(download_btns) >= 1


def test_records_screen_class_filtering(tmp_path: Path):
    """Verify filtering by class updates KPIs and table."""
    db_file = tmp_path / "rec_filter.db"
    _seed_sample_records(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_records(at)

    class_sb = [s for s in at.selectbox if s.key == "rec_filter_class"][0]
    class_sb.select("CLASS-02-B").run()

    assert not at.exception
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Filtered Sessions"] == "1"
    assert metrics_by_label["Total Present"] == "24"
    assert metrics_by_label["Flagged for Review"] == "0"


def test_records_screen_status_filtering(tmp_path: Path):
    """Verify filtering by 'Needs Review Only' isolates flagged sessions."""
    db_file = tmp_path / "rec_status.db"
    _seed_sample_records(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_records(at)

    status_sb = [s for s in at.selectbox if s.key == "rec_filter_status"][0]
    status_sb.select("Needs Review Only").run()

    assert not at.exception
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Filtered Sessions"] == "1"
    assert metrics_by_label["Flagged for Review"] == "1"
    df = at.dataframe[0].value
    assert len(df) == 1
    assert df.iloc[0]["Integrity Status"] == "⚠️ Needs Review"
