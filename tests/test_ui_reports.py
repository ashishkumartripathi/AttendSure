"""Headless automated UI integration tests for AttendSure Reports & Export.

Verifies:
1. Initial render without exceptions and clean empty states.
2. Sessions export formatting, summary metrics, and download control.
3. Sessions export cohort and date range filtering.
4. Alerts audit export formatting, filter controls, and decision-support disclaimers.
5. CSV import validation and preview without database persistence.
6. CSV import validation error reporting on malformed data.
7. CSV import all-or-nothing atomic commitment.
8. CSV import all-or-nothing rollback on errors.
9. CSV import partial mode persistence and error isolation.
10. Rerun idempotency and storage read-only safety.
"""

from datetime import date
import io
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_reports(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Reports & Export and run."""
    try:
        at.sidebar.radio[0].set_value("Reports").run()
    except Exception:
        at.sidebar.radio[0].set_value("Reports & Export").run()


def test_reports_initial_render_on_empty_db(tmp_path: Path):
    """Scenario 1: Reports & Export renders cleanly on empty database with zero writes."""
    db_file = tmp_path / "reports_empty.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    assert not at.exception
    assert len(at.error) == 0

    assert at.header[0].value in ("Reports", "Reports & Export")

    # Read-only notice is displayed
    markdown_texts = [m.value for m in at.markdown]
    assert any("Data Export Guarantee" in text for text in markdown_texts)
    assert any("Decision-Support Audit Notice" in text for text in markdown_texts)

    # Info message for empty sessions
    info_texts = [i.value for i in at.info]
    assert any("No attendance sessions found" in text for text in info_texts)

    # Verify zero writes to database
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_reports_sessions_export_with_data(tmp_path: Path):
    """Scenario 2: Sessions export displays metrics, preview table, and functional download button."""
    db_file = tmp_path / "reports_sessions.db"
    repository = AttendanceRepository(db_path=db_file)

    session_1 = SessionRecord(
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
    session_2 = SessionRecord(
        session_id="00000000-0000-4000-8000-000000000002",
        class_id="CLASS-02-B",
        session_date="2026-10-20",
        expected_enrollment=25,
        present_count=25,
        absent_count=0,
        webcam_status="SUCCESS",
        webcam_count=25,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    repository.save_session(session_1)
    repository.save_session(session_2)
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Matching Sessions"] == "2"
    assert metrics_by_label["Cumulative Enrolled"] == "55"

    # Preview dataframe rendered with 2 rows
    assert len(at.dataframe) > 0
    df = at.dataframe[0].value
    assert len(df) == 2
    assert "Cohort" in df.columns
    assert "Enrollment" in df.columns

    # Download button present
    download_buttons = at.get("download_button")
    assert len(download_buttons) >= 1


def test_reports_sessions_export_filtering(tmp_path: Path):
    """Scenario 3: Sessions export filters by cohort and updates download data."""
    db_file = tmp_path / "reports_filter.db"
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
        session_date="2026-10-21",
        expected_enrollment=25,
        present_count=25,
        absent_count=0,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-21T09:00:00Z",
    )
    repository.save_session(s1)
    repository.save_session(s2)
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    # Filter to CLASS-01-A
    cohort_sb = [s for s in at.selectbox if s.key == "export_sessions_cohort_filter"][0]
    cohort_sb.select("CLASS-01-A").run()

    assert not at.exception
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Matching Sessions"] == "1"
    assert metrics_by_label["Cumulative Enrolled"] == "30"


def test_reports_alerts_export(tmp_path: Path):
    """Scenario 4: Alerts audit export displays metrics, filters, and download control."""
    db_file = tmp_path / "reports_alerts.db"
    repository = AttendanceRepository(db_path=db_file)

    session = SessionRecord(
        session_id="00000000-0000-4000-8000-000000000001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        expected_enrollment=30,
        present_count=12,
        absent_count=18,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    alert = Alert(
        alert_id="alert-001",
        session_id="00000000-0000-4000-8000-000000000001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Unusual Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 12},
        baseline_reference={"rolling_median": 28.0},
        threshold_applied={"percentage_drop": 30.0},
        explanation="Attendance dropped 57.1% below the 5-day rolling median.",
        review_status="PENDING_REVIEW",
        created_at="2026-10-20T09:00:00Z",
    )
    repository.save_session(session)
    repository.save_alerts([alert])
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert "Matching Alerts" in metrics_by_label
    assert metrics_by_label["Matching Alerts"] == "1"
    assert metrics_by_label["Pending Review"] == "1"
    assert metrics_by_label["Review Required"] == "1"

    download_buttons = at.get("download_button")
    assert len(download_buttons) >= 1


def test_reports_csv_import_preview_without_persistence(tmp_path: Path):
    """Scenario 5: Validate & Preview parses file and shows candidate rows with zero DB writes."""
    db_file = tmp_path / "reports_import_prev.db"
    valid_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,27,3
"""
    uploaded_file = io.StringIO(valid_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    # Click Validate & Preview
    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    assert not at.exception
    assert len(at.error) == 0

    # Preview result displayed
    assert "reports_csv_preview_res" in at.session_state
    res = at.session_state["reports_csv_preview_res"]
    assert res.total_rows == 2
    assert res.imported_count == 2
    assert res.failed_count == 0

    # Ensure database remains completely untouched (zero writes on preview)
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0


def test_reports_csv_import_preview_validation_errors(tmp_path: Path):
    """Scenario 6: Validate & Preview detects invalid counts and collisions without writes."""
    db_file = tmp_path / "reports_import_bad.db"
    bad_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-02-B,2026-10-20,30,20,5
"""
    uploaded_file = io.StringIO(bad_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    assert not at.exception
    res = at.session_state["reports_csv_preview_res"]
    assert res.total_rows == 2
    assert res.failed_count == 1
    assert len(res.errors) == 1
    assert res.errors[0].line_number == 3

    # Zero writes
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0


def test_reports_csv_import_all_or_nothing_commit(tmp_path: Path):
    """Scenario 7: Confirm & Commit persists all valid records in all-or-nothing mode."""
    db_file = tmp_path / "reports_import_commit.db"
    valid_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,27,3
"""
    uploaded_file = io.StringIO(valid_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    # Step 1: Preview
    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    # Step 2: Commit
    btn_commit = [b for b in at.button if b.key == "btn_commit_csv"][0]
    assert not btn_commit.disabled
    btn_commit.click().run()

    assert not at.exception
    assert len(at.error) == 0

    # Success message displayed
    success_texts = [s.value for s in at.success]
    assert any("Import Successful" in text for text in success_texts)

    # Verify records written to SQLite
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions()
        assert len(sessions) == 2
        assert {s.class_id for s in sessions} == {"CLASS-01-A"}


def test_reports_csv_import_all_or_nothing_rollback_on_errors(tmp_path: Path):
    """Scenario 8: All-or-nothing mode disables commit button when errors exist, preventing partial writes."""
    db_file = tmp_path / "reports_import_aon_err.db"
    mixed_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-02-B,2026-10-20,30,20,5
"""
    uploaded_file = io.StringIO(mixed_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    # Commit button must be disabled in all-or-nothing mode when failed_count > 0
    btn_commit = [b for b in at.button if b.key == "btn_commit_csv"][0]
    assert btn_commit.disabled

    # Database has 0 records
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0


def test_reports_csv_import_partial_mode(tmp_path: Path):
    """Scenario 9: Partial import mode allows committing valid records while rejecting bad rows."""
    db_file = tmp_path / "reports_import_part.db"
    mixed_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-02-B,2026-10-20,30,20,5
"""
    uploaded_file = io.StringIO(mixed_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    # Enable partial import
    chk_partial = [c for c in at.checkbox if c.key == "reports_chk_allow_partial"][0]
    chk_partial.check().run()

    # Preview
    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    # Commit button should now be enabled for the 1 valid record
    btn_commit = [b for b in at.button if b.key == "btn_commit_csv"][0]
    assert not btn_commit.disabled
    btn_commit.click().run()

    assert not at.exception
    # Exactly 1 record persisted to SQLite
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions()
        assert len(sessions) == 1
        assert sessions[0].class_id == "CLASS-01-A"


def test_reports_rerun_idempotency_and_no_unintended_writes(tmp_path: Path):
    """Scenario 10: Streamlit reruns preserve state and do not repeat imports or writes."""
    db_file = tmp_path / "reports_rerun.db"
    valid_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
"""
    uploaded_file = io.StringIO(valid_csv)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    _navigate_to_reports(at)

    # Preview and commit
    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    btn_commit = [b for b in at.button if b.key == "btn_commit_csv"][0]
    btn_commit.click().run()

    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 1

    # Rerun app without button click
    at.run()
    assert not at.exception

    # Still exactly 1 record, no duplicate writes on rerun
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 1


def test_reports_sessions_export_inverted_date_filter(tmp_path: Path):
    """Scenario 11: Sessions export displays warning when start date > end date."""
    db_file = tmp_path / "reports_inv_date.db"
    repository = AttendanceRepository(db_path=db_file)
    s1 = SessionRecord("550e8400-e29b-41d4-a716-446655440001", "CLASS-01-A", "2026-10-20", 30, 28, 2, "NOT_ATTEMPTED", None, "MANUAL_ENTRY", "2026-10-20T09:00:00Z")
    repository.save_session(s1)
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    # Enable date filter
    chk = [c for c in at.checkbox if c.key == "export_sessions_enable_date_filter"][0]
    chk.check().run()

    # Invert date: start=2026-10-25, end=2026-10-20
    s_date = [d for d in at.date_input if d.key == "export_sessions_start_date"][0]
    e_date = [d for d in at.date_input if d.key == "export_sessions_end_date"][0]
    s_date.set_value(date(2026, 10, 25)).run()
    e_date.set_value(date(2026, 10, 20)).run()

    assert not at.exception
    assert any("Start Date cannot be after End Date" in w.value for w in at.warning)
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Matching Sessions"] == "0"


def test_reports_alerts_export_inverted_date_filter(tmp_path: Path):
    """Scenario 12: Alerts export displays warning when start date > end date."""
    db_file = tmp_path / "reports_inv_alerts.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run()

    _navigate_to_reports(at)

    # Enable alerts date filter
    chk = [c for c in at.checkbox if c.key == "export_alerts_enable_date_filter"][0]
    chk.check().run()

    # Invert date
    s_date = [d for d in at.date_input if d.key == "export_alerts_start_date"][0]
    e_date = [d for d in at.date_input if d.key == "export_alerts_end_date"][0]
    s_date.set_value(date(2026, 10, 25)).run()
    e_date.set_value(date(2026, 10, 20)).run()

    assert not at.exception
    assert any("Start Date cannot be after End Date" in w.value for w in at.warning)
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Matching Alerts"] == "0"
