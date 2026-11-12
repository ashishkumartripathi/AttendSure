"""Headless automated UI integration tests for AttendSure Attendance Register screen.

Tests Milestone M5.3.2.2 requirements using Streamlit's native headless AppTest framework:
1. Register screen renders without exceptions on an empty database.
2. Valid manual roll-call entry is persisted atomically.
3. Invalid counts are rejected and not persisted to storage.
4. Duplicate class/date entry is reported gracefully without overwriting the existing session.
5. Simulated webcam success (with anomaly generation) and non-success (null counts) states are represented correctly.
6. Historical register filters render correctly with existing sessions (cohort and date range filters).
7. CSV all-or-nothing import reports errors without partially importing invalid batches.
8. CSV partial-import mode imports valid rows and reports invalid rows with line numbers and reasons.
9. Repeated reruns do not duplicate sessions or re-import the same file automatically.
"""

from datetime import date
import io
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_register(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Mark Attendance and run."""
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    try:
        at.sidebar.radio[0].set_value("Mark Attendance").run()
    except Exception:
        try:
            at.sidebar.radio[0].set_value("Attendance").run()
        except Exception:
            at.sidebar.radio[0].set_value("Attendance Register").run()


def test_register_screen_renders_without_exceptions_on_empty_db(tmp_path: Path):
    """Scenario 1: Verify Attendance Register renders cleanly on an empty database."""
    db_file = tmp_path / "empty_register.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    assert not at.exception
    assert len(at.error) == 0

    # Header and subheaders rendered
    assert at.header[0].value in ("Mark Attendance", "Attendance", "Attendance Register")
    subheaders = [s.value for s in at.subheader]
    assert any("Record" in s or "Manual" in s for s in subheaders)
    assert any("Recent" in s or "Historical" in s for s in subheaders)
    assert any("Upload" in s or "Batch" in s for s in subheaders)

    # Empty state info message in historical register
    info_texts = [i.value for i in at.info]
    assert any("No attendance records found" in text for text in info_texts)


def test_valid_manual_roll_call_entry_persisted(tmp_path: Path):
    """Scenario 2: Verify valid manual roll-call entry is persisted atomically."""
    db_file = tmp_path / "manual_valid.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    # Set roll-call fields: CLASS-01-A, 2026-10-24, enrollment=30, present=26 (absent auto 4)
    class_inputs = [t for t in at.text_input if "cohort" in t.label.lower() or "class" in t.label.lower()]
    assert len(class_inputs) > 0
    class_inputs[0].set_value("CLASS-01-A").run()

    date_inputs = [d for d in at.date_input if "date" in d.label.lower()]
    assert len(date_inputs) > 0
    date_inputs[0].set_value(date(2026, 10, 24)).run()

    enrollment_inputs = [n for n in at.number_input if "enrollment" in n.label.lower() or "student" in n.label.lower()]
    present_inputs = [n for n in at.number_input if "present" in n.label.lower()]
    enrollment_inputs[0].set_value(30).run()
    present_inputs[0].set_value(26).run()

    # Click Save Attendance button
    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0

    success_texts = [s.value for s in at.success]
    assert any("Attendance session recorded successfully" in text for text in success_texts)

    # Verify session persisted to the temporary SQLite database
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.class_id == "CLASS-01-A"
        assert s.session_date == "2026-10-24"
        assert s.expected_enrollment == 30
        assert s.present_count == 26
        assert s.absent_count == 4
        assert s.webcam_status == "NOT_ATTEMPTED"
        assert s.webcam_count is None
        assert s.record_source == "MANUAL_ENTRY"


def test_invalid_counts_rejected_and_not_persisted(tmp_path: Path):
    """Scenario 3: Verify invalid counts (present > enrollment) are rejected without DB writes."""
    db_file = tmp_path / "manual_invalid.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    enrollment_inputs = [n for n in at.number_input if "enrollment" in n.label.lower() or "student" in n.label.lower()]
    present_inputs = [n for n in at.number_input if "present" in n.label.lower()]
    enrollment_inputs[0].set_value(20).run()
    present_inputs[0].set_value(25).run()  # Invalid: 25 > 20

    # Warning banner is displayed immediately for educator awareness
    warning_texts = [w.value for w in at.warning]
    assert any("cannot be greater than" in text.lower() or "exceeds expected enrollment" in text.lower() for text in warning_texts)

    # Click Save button
    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    # Must display validation error
    error_texts = [e.value for e in at.error]
    assert any("validation error" in text.lower() for text in error_texts)

    # Database must remain empty
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0


def test_duplicate_class_date_reported_without_overwriting(tmp_path: Path):
    """Scenario 4: Verify duplicate (class_id, session_date) collision is handled gracefully."""
    db_file = tmp_path / "manual_duplicate.db"

    # Pre-seed existing session: CLASS-01-A on 2026-10-24 with present=25
    with get_repository(db_path=db_file) as repo:
        existing = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440001",
            class_id="CLASS-01-A",
            session_date="2026-10-24",
            expected_enrollment=30,
            present_count=25,
            absent_count=5,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-24T09:00:00Z",
        )
        repo.save_session(existing)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    # Attempt to record duplicate session for same cohort and date with different present count (28)
    class_inputs = [t for t in at.text_input if "cohort" in t.label.lower() or "class" in t.label.lower()]
    class_inputs[0].set_value("CLASS-01-A").run()

    date_inputs = [d for d in at.date_input if "date" in d.label.lower()]
    date_inputs[0].set_value(date(2026, 10, 24)).run()

    present_inputs = [n for n in at.number_input if "present" in n.label.lower()]
    present_inputs[0].set_value(28).run()

    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    # Must report collision and not crash
    assert not at.exception
    error_texts = [e.value for e in at.error]
    assert any("already exists in the database" in text.lower() or "already exists" in text.lower() for text in error_texts)

    # Verify original session in database was NOT overwritten
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions(class_id="CLASS-01-A")
        assert len(sessions) == 1
        assert sessions[0].present_count == 25  # Preserved original value


def test_simulated_webcam_success_and_nonsuccess_states(tmp_path: Path):
    """Scenario 5: Verify webcam simulation success (with discrepancy alert) and non-success states."""
    db_file = tmp_path / "webcam_simulation.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    # 1. Enable camera simulation
    cam_chk = [c for c in at.checkbox if "camera" in c.label.lower() or "headcount" in c.label.lower()][0]
    cam_chk.check().run()

    # 2. Select DISCREPANCY scenario and record session
    scenario_sb = [s for s in at.selectbox if "scenario" in s.label.lower() or "situation" in s.label.lower()][0]
    scenario_sb.select("DISCREPANCY").run()

    class_inputs = [t for t in at.text_input if "cohort" in t.label.lower() or "class" in t.label.lower()]
    class_inputs[0].set_value("CLASS-01-A").run()
    date_inputs = [d for d in at.date_input if "date" in d.label.lower()]
    date_inputs[0].set_value(date(2026, 10, 20)).run()

    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    assert not at.exception
    # Verify review signal warning is displayed
    warning_texts = [w.value for w in at.warning]
    assert any("review signal" in text.lower() for text in warning_texts)

    with get_repository(db_path=db_file) as repo:
        s1 = repo.get_sessions(class_id="CLASS-01-A")[0]
        assert s1.webcam_status == "SUCCESS"
        assert isinstance(s1.webcam_count, int)
        assert s1.webcam_count >= 0
        alerts = repo.get_alerts(class_id="CLASS-01-A")
        assert len(alerts) >= 1
        assert any(a.rule_id == "RULE_WEBCAM_DISCREPANCY" for a in alerts)

    # 3. Test non-success scenario: CAMERA_OFFLINE
    scenario_sb.select("CAMERA_OFFLINE").run()
    date_inputs[0].set_value(date(2026, 10, 21)).run()

    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions(class_id="CLASS-01-A")
        s2 = [s for s in sessions if s.session_date == "2026-10-21"][0]
        assert s2.webcam_status == "CAMERA_UNAVAILABLE"
        assert s2.webcam_count is None


def test_historical_register_cohort_and_date_filtering(tmp_path: Path):
    """Scenario 6: Verify Historical Register displays sessions and filters by cohort and date."""
    db_file = tmp_path / "historical_filters.db"

    # Pre-seed 3 sessions across 2 cohorts
    with get_repository(db_path=db_file) as repo:
        s1 = SessionRecord("550e8400-e29b-41d4-a716-446655440001", "CLASS-01-A", "2026-10-15", 30, 25, 5, "SUCCESS", 25, "MANUAL_ENTRY", "2026-10-15T09:00:00Z")
        s2 = SessionRecord("550e8400-e29b-41d4-a716-446655440002", "CLASS-01-A", "2026-10-18", 30, 27, 3, "SUCCESS", 27, "MANUAL_ENTRY", "2026-10-18T09:00:00Z")
        s3 = SessionRecord("550e8400-e29b-41d4-a716-446655440003", "CLASS-02-B", "2026-10-20", 20, 18, 2, "NOT_ATTEMPTED", None, "MANUAL_ENTRY", "2026-10-20T09:00:00Z")
        repo.save_sessions([s1, s2, s3])

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    assert len(at.dataframe) > 0
    initial_df = at.dataframe[0].value
    assert len(initial_df) == 3
    assert "Attendance Rate" in initial_df.columns
    cohort_col = "Class" if "Class" in initial_df.columns else "Cohort"
    assert cohort_col in initial_df.columns

    # Filter by cohort "CLASS-01-A"
    cohort_sb = [s for s in at.selectbox if "cohort" in s.label.lower() or "class" in s.label.lower()][0]
    cohort_sb.select("CLASS-01-A").run()

    filtered_df = at.dataframe[0].value
    assert len(filtered_df) == 2
    assert set(filtered_df[cohort_col].tolist()) == {"CLASS-01-A"}

    # Reset to "All Cohorts" or "All Classes"
    cohort_sb.select(cohort_sb.options[0]).run()
    assert len(at.dataframe[0].value) == 3

    # Enable date range filter
    date_filter_chk = [c for c in at.checkbox if "date range" in c.label.lower()][0]
    date_filter_chk.check().run()

    # Filter to start_date=2026-10-19 (should match only CLASS-02-B on 2026-10-20)
    start_date_input = [d for d in at.date_input if "start date" in d.label.lower()][0]
    start_date_input.set_value(date(2026, 10, 19)).run()

    date_filtered_df = at.dataframe[0].value
    assert len(date_filtered_df) == 1
    assert date_filtered_df.iloc[0][cohort_col] == "CLASS-02-B"
    assert date_filtered_df.iloc[0]["Date"] == "2026-10-20"


def test_csv_all_or_nothing_import_reports_errors_without_partial_persistence(tmp_path: Path):
    """Scenario 7: Verify all-or-nothing CSV import rejects invalid batch without partial writes."""
    db_file = tmp_path / "csv_aon.db"

    csv_content = (
        "class_id,session_date,expected_enrollment,present_count,absent_count\n"
        "CLASS-01-A,2026-10-20,30,25,5\n"
        "CLASS-02-B,2026-10-21,20,25,0\n"  # Invalid: 25 > 20
    )

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = io.BytesIO(csv_content.encode("utf-8"))
    at.run()

    _navigate_to_register(at)

    # Click Process CSV Import button with default allow_partial=False
    import_btn = [b for b in at.button if b.label == "Process CSV Import"][0]
    import_btn.click().run()

    assert not at.exception
    error_texts = [e.value for e in at.error]
    assert any("Import failed: 0 of 2" in text for text in error_texts)

    # Database must have 0 rows persisted (strict transaction rollback)
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0


def test_csv_partial_import_mode_persists_valid_rows_and_reports_errors(tmp_path: Path):
    """Scenario 8: Verify partial-import mode imports valid rows and reports invalid row details."""
    db_file = tmp_path / "csv_partial.db"

    csv_content = (
        "class_id,session_date,expected_enrollment,present_count,absent_count\n"
        "CLASS-01-A,2026-10-20,30,25,5\n"
        "CLASS-02-B,2026-10-21,20,25,0\n"  # Invalid: 25 > 20
    )

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = io.BytesIO(csv_content.encode("utf-8"))
    at.run()

    _navigate_to_register(at)

    # Enable allow_partial checkbox
    partial_chk = [c for c in at.checkbox if "partial" in c.label.lower()][0]
    partial_chk.check().run()

    import_btn = [b for b in at.button if b.label == "Process CSV Import"][0]
    import_btn.click().run()

    assert not at.exception
    warning_texts = [w.value for w in at.warning]
    assert any("Partial import completed: 1 record(s) imported, 1 record(s) rejected" in text for text in warning_texts)

    # Exactly 1 row persisted
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions()
        assert len(sessions) == 1
        assert sessions[0].class_id == "CLASS-01-A"
        assert sessions[0].record_source == "CSV_IMPORT"


def test_repeated_reruns_do_not_duplicate_sessions_or_reimport_automatically(tmp_path: Path):
    """Scenario 9: Verify repeated reruns do not automatically re-import files or duplicate records."""
    db_file = tmp_path / "csv_reruns.db"

    csv_content = (
        "class_id,session_date,expected_enrollment,present_count,absent_count\n"
        "CLASS-01-A,2026-10-20,30,25,5\n"
    )

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = io.BytesIO(csv_content.encode("utf-8"))
    at.run()

    _navigate_to_register(at)

    # First import execution
    import_btn = [b for b in at.button if b.label == "Process CSV Import"][0]
    import_btn.click().run()

    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 1

    # Simple rerun without button click must NOT re-import
    at.run()

    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 1

    # Second explicit button click triggers collision rejection, preserving existing record
    import_btn = [b for b in at.button if b.label == "Process CSV Import"][0]
    import_btn.click().run()

    error_texts = [e.value for e in at.error]
    assert any("collided with existing records" in text.lower() or "already exists" in text.lower() for text in error_texts)

    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 1


def test_historical_register_inverted_date_filter(tmp_path: Path):
    """Scenario 10: Verify Historical Register alerts user when start_date > end_date."""
    db_file = tmp_path / "reg_inverted_date.db"
    with get_repository(db_path=db_file) as repo:
        s1 = SessionRecord("550e8400-e29b-41d4-a716-446655440001", "CLASS-01-A", "2026-10-15", 30, 25, 5, "SUCCESS", 25, "MANUAL_ENTRY", "2026-10-15T09:00:00Z")
        repo.save_sessions([s1])

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    date_filter_chk = [c for c in at.checkbox if "date range" in c.label.lower()][0]
    date_filter_chk.check().run()

    start_date_input = [d for d in at.date_input if "start date" in d.label.lower()][0]
    end_date_input = [d for d in at.date_input if "end date" in d.label.lower()][0]

    # Set start_date > end_date
    start_date_input.set_value(date(2026, 10, 25)).run()
    end_date_input.set_value(date(2026, 10, 10)).run()

    assert not at.exception
    warnings = [w.value for w in at.warning]
    assert any("start date cannot be after end date" in w.lower() for w in warnings)


def test_simulated_webcam_camera_unavailable_mode(tmp_path: Path):
    """Scenario 11: Verify simulated webcam CAMERA_UNAVAILABLE mode records correct status and None count."""
    db_file = tmp_path / "reg_cam_unavail.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    cam_chk = [c for c in at.checkbox if "camera" in c.label.lower() or "headcount" in c.label.lower()][0]
    cam_chk.check().run()

    scenario_sb = [s for s in at.selectbox if "scenario" in s.label.lower() or "situation" in s.label.lower()][0]
    scenario_sb.select("CAMERA_UNAVAILABLE").run()

    class_inputs = [t for t in at.text_input if "cohort" in t.label.lower() or "class" in t.label.lower()]
    class_inputs[0].set_value("CLASS-01-A").run()
    date_inputs = [d for d in at.date_input if "date" in d.label.lower()]
    date_inputs[0].set_value(date(2026, 10, 22)).run()

    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    assert not at.exception
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions(class_id="CLASS-01-A")
        assert len(sessions) == 1
        assert sessions[0].webcam_status == "CAMERA_UNAVAILABLE"
        assert sessions[0].webcam_count is None


def test_absent_count_updates_immediately_and_persists_invariant(tmp_path: Path):
    """Scenario 12: Regression test for stale absent-count display bug.

    Verifies:
    1. Initial default state: enrollment=30, present=25 -> absent=5.
    2. Changing present count to 12 immediately updates absent count to 18 (30 - 12 = 18).
    3. Changing expected enrollment to 40 immediately updates absent count to 28 (40 - 12 = 28).
    4. Absent count widget is disabled (read-only).
    5. Saving the record recalculates absent count and verifies the invariant:
       present_count + absent_count == expected_enrollment.
    """
    db_file = tmp_path / "absent_count_regression.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    enrollment_inputs = [n for n in at.number_input if "enrollment" in n.label.lower() or "student" in n.label.lower()]
    present_inputs = [n for n in at.number_input if "present" in n.label.lower()]
    absent_inputs = [n for n in at.number_input if "absent" in n.label.lower()]

    assert len(enrollment_inputs) == 1
    assert len(present_inputs) == 1
    assert len(absent_inputs) == 1

    # 1. Initial defaults
    assert enrollment_inputs[0].value == 30
    assert present_inputs[0].value == 25
    assert absent_inputs[0].value == 5
    assert absent_inputs[0].disabled is True  # Read-only verification

    # 2. Change present count to 12 (as seen in screenshot)
    present_inputs[0].set_value(12).run()
    assert absent_inputs[0].value == 18, (
        f"Expected absent count to derive 18 (30 - 12), got {absent_inputs[0].value}"
    )

    # 3. Change expected enrollment to 40
    enrollment_inputs[0].set_value(40).run()
    assert absent_inputs[0].value == 28, (
        f"Expected absent count to derive 28 (40 - 12), got {absent_inputs[0].value}"
    )

    # 4. Set final test values: enrollment=30, present=12 -> absent=18
    enrollment_inputs[0].set_value(30).run()
    assert absent_inputs[0].value == 18

    class_inputs = [t for t in at.text_input if "cohort" in t.label.lower() or "class" in t.label.lower()]
    class_inputs[0].set_value("CLASS-01-A").run()

    date_inputs = [d for d in at.date_input if "date" in d.label.lower()]
    date_inputs[0].set_value(date(2026, 10, 25)).run()

    # 5. Save record
    save_btn = [b for b in at.button if b.key == "btn_save_roll_call" or "save" in b.label.lower()][0]
    save_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0
    success_texts = [s.value for s in at.success]
    assert any("Attendance session recorded successfully" in text for text in success_texts)

    # 6. Verify database persistence and count invariant
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions(class_id="CLASS-01-A")
        assert len(sessions) == 1
        s = sessions[0]
        assert s.expected_enrollment == 30
        assert s.present_count == 12
        assert s.absent_count == 18
        # Strictly verify invariant: present + absent == expected
        assert s.present_count + s.absent_count == s.expected_enrollment


def test_quick_action_mark_all_present_and_absent_repeated(tmp_path: Path):
    """Verify 'Mark All Present' and 'Mark All Absent' buttons work repeatedly without StreamlitWidgetAlreadyInstantiatedError."""
    db_file = tmp_path / "quick_actions.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    # 1. Click Mark All Present -> present=30, absent=0
    btn_present = [b for b in at.button if b.key == "btn_quick_all_present"][0]
    btn_present.click().run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 30
    assert at.number_input(key="manual_absent_count_display").value == 0

    # 2. Click Mark All Absent -> present=0, absent=30
    btn_absent = [b for b in at.button if b.key == "btn_quick_all_absent"][0]
    btn_absent.click().run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 0
    assert at.number_input(key="manual_absent_count_display").value == 30

    # 3. Click Mark All Present again -> present=30, absent=0 (verify repeatability)
    btn_present = [b for b in at.button if b.key == "btn_quick_all_present"][0]
    btn_present.click().run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 30
    assert at.number_input(key="manual_absent_count_display").value == 0

    # 4. Modify present manually -> absent updates
    at.number_input(key="manual_present_count").set_value(18).run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 18
    assert at.number_input(key="manual_absent_count_display").value == 12

    # 5. Modify expected enrollment -> absent derives correctly
    at.number_input(key="manual_expected_enrollment").set_value(45).run()
    assert not at.exception
    assert at.number_input(key="manual_absent_count_display").value == 27  # 45 - 18


def test_attendance_state_preservation_across_class_and_date_change(tmp_path: Path):
    """Verify entered attendance values are preserved when switching class or date without error."""
    db_file = tmp_path / "state_preservation.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_register(at)

    at.number_input(key="manual_expected_enrollment").set_value(35).run()
    at.number_input(key="manual_present_count").set_value(29).run()

    # Switch class
    at.text_input(key="manual_class_id").set_value("CLASS-05-B").run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 29

    # Switch date to a valid past/today date
    at.date_input(key="manual_session_date").set_value(date(2026, 11, 10)).run()
    assert not at.exception
    assert at.number_input(key="manual_present_count").value == 29

    # Save attendance session
    save_btn = [b for b in at.button if b.key == "btn_save_roll_call"][0]
    save_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0
    with get_repository(db_path=db_file) as repo:
        sessions = repo.get_sessions(class_id="CLASS-05-B")
        assert len(sessions) == 1
        assert sessions[0].present_count == 29
        assert sessions[0].absent_count == 6
        assert sessions[0].expected_enrollment == 35
