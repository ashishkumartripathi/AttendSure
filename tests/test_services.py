"""Unit and integration tests for AttendSure application services.

Verifies manual session validation, recording with contextual historical detection,
full detection pipeline execution, review status updates, and transaction boundaries.
"""

import sqlite3
import pytest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.services.attendance_service import (
    record_session_with_detection,
    run_full_detection_pipeline,
    update_alert_status,
    validate_manual_session,
)


@pytest.fixture
def repo(tmp_path):
    """Provide an isolated file-based AttendanceRepository for testing."""
    db_file = tmp_path / "test_service.db"
    repository = AttendanceRepository(db_path=db_file)
    yield repository
    repository.close()


def make_valid_manual_input(
    class_id: str = "CLASS-01-A",
    session_date: str = "2026-10-20",
    expected_enrollment: int = 30,
    present_count: int = 28,
    absent_count: int = 2,
) -> dict:
    """Helper to create minimal valid manual session input dict."""
    return {
        "class_id": class_id,
        "session_date": session_date,
        "expected_enrollment": expected_enrollment,
        "present_count": present_count,
        "absent_count": absent_count,
    }


def test_validate_manual_session_valid():
    """Verify validate_manual_session returns valid result without mutating data."""
    data = make_valid_manual_input()
    data_copy = dict(data)
    result = validate_manual_session(data)
    assert result.is_valid is True
    assert result.errors == []
    assert data == data_copy


def test_validate_manual_session_invalid():
    """Verify validate_manual_session rejects invalid counts and dates."""
    bad_data = make_valid_manual_input(present_count=20, absent_count=5)  # 20 + 5 != 30
    result = validate_manual_session(bad_data)
    assert result.is_valid is False
    assert any("present_count + absent_count" in err for err in result.errors)


def test_record_session_valid_nominal_persisted(repo):
    """1. Valid manual session is persisted and returns (session, [])."""
    data = make_valid_manual_input()
    session, alerts = record_session_with_detection(repo, data)

    assert isinstance(session, SessionRecord)
    assert session.class_id == "CLASS-01-A"
    assert session.present_count == 28
    assert session.record_source == "MANUAL_ENTRY"
    assert session.webcam_status == "NOT_ATTEMPTED"
    assert session.webcam_count is None
    assert alerts == []

    # Verify session is in repository
    stored = repo.get_session_by_id(session.session_id)
    assert stored == session
    assert len(repo.get_sessions()) == 1


def test_record_session_invalid_input_creates_no_writes(repo):
    """2. Invalid input creates no database writes."""
    bad_data = make_valid_manual_input(present_count=20, absent_count=5)

    with pytest.raises(ValueError, match="Session validation failed"):
        record_session_with_detection(repo, bad_data)

    assert len(repo.get_sessions()) == 0
    assert len(repo.get_alerts()) == 0


def test_record_session_contextual_drop_detection_triggers(repo):
    """3 & 4. Attendance-drop detection triggers on a new session after 5 baseline sessions."""
    # Seed 5 baseline sessions with attendance around 90% (varying counts: 26, 27, 28, 27, 28)
    baseline_counts = [26, 27, 28, 27, 28]
    for day, pres in enumerate(baseline_counts, start=1):
        date_str = f"2026-10-{day:02d}"
        seed_data = make_valid_manual_input(
            session_date=date_str,
            expected_enrollment=30,
            present_count=pres,
            absent_count=30 - pres,
        )
        s, a = record_session_with_detection(repo, seed_data)
        assert len(a) == 0

    assert len(repo.get_sessions()) == 5

    # Day 6: Sharp drop to 30% attendance (9/30)
    drop_data = make_valid_manual_input(
        session_date="2026-10-06",
        expected_enrollment=30,
        present_count=9,
        absent_count=21,
    )
    drop_session, drop_alerts = record_session_with_detection(repo, drop_data)

    assert drop_session.session_date == "2026-10-06"
    assert len(drop_alerts) == 1
    alert = drop_alerts[0]
    assert alert.rule_id == "RULE_ATTENDANCE_DROP"
    assert alert.session_id == drop_session.session_id
    assert alert.class_id == "CLASS-01-A"
    assert alert.priority == "REVIEW_REQUIRED"

    # Both session and alert are persisted
    assert len(repo.get_sessions()) == 6
    stored_alerts = repo.get_alerts()
    assert len(stored_alerts) == 1
    assert stored_alerts[0].alert_id == alert.alert_id


def test_record_session_without_anomalies_still_persisted(repo):
    """5. A new session without anomalies is still saved."""
    data = make_valid_manual_input()
    session, alerts = record_session_with_detection(repo, data)
    assert alerts == []
    assert repo.get_session_by_id(session.session_id) is not None


def test_record_session_isolates_new_session_alerts_only(repo):
    """6. Only alerts relevant to the newly submitted session are saved."""
    # Seed a repeated headcount run (4 days with count = 25)
    for day in range(1, 5):
        date_str = f"2026-10-{day:02d}"
        d = make_valid_manual_input(
            session_date=date_str,
            expected_enrollment=30,
            present_count=25,
            absent_count=5,
        )
        record_session_with_detection(repo, d)

    # 4th day triggered a repeated headcount alert
    assert len(repo.get_alerts()) == 1

    # Day 5: normal varying attendance (28/30)
    normal_data = make_valid_manual_input(
        session_date="2026-10-05",
        expected_enrollment=30,
        present_count=28,
        absent_count=2,
    )
    new_s, new_alerts = record_session_with_detection(repo, normal_data)

    # Day 5 has no anomaly
    assert new_alerts == []
    # Total alerts in database remains 1 (no re-saving or duplicates)
    assert len(repo.get_alerts()) == 1


def test_record_session_detection_disabled(repo):
    """Verify run_detection=False saves session without running detectors."""
    data = make_valid_manual_input()
    session, alerts = record_session_with_detection(repo, data, run_detection=False)
    assert alerts == []
    assert repo.get_session_by_id(session.session_id) is not None


def test_record_session_atomic_rollback_on_db_collision(repo):
    """10. Transaction failures (e.g. duplicate class-date) roll back completely."""
    data1 = make_valid_manual_input(session_date="2026-10-20")
    record_session_with_detection(repo, data1)

    # Attempting to insert duplicate (class_id, session_date) raises IntegrityError
    data_dup = make_valid_manual_input(session_date="2026-10-20")
    with pytest.raises(sqlite3.IntegrityError):
        record_session_with_detection(repo, data_dup)

    assert len(repo.get_sessions()) == 1


def test_run_full_detection_pipeline_and_review_preservation(repo):
    """7 & 8. Full detection pipeline, class filtering, and review status preservation."""
    # Seed 5 baseline sessions for CLASS-01-A with varying attendance around 90%
    c1_counts = [26, 27, 28, 27, 28]
    for day, pres in enumerate(c1_counts, start=1):
        record_session_with_detection(
            repo,
            make_valid_manual_input(
                class_id="CLASS-01-A",
                session_date=f"2026-10-{day:02d}",
                expected_enrollment=30,
                present_count=pres,
                absent_count=30 - pres,
            ),
            run_detection=False,
        )
    # Day 6 drop
    record_session_with_detection(
        repo,
        make_valid_manual_input(class_id="CLASS-01-A", session_date="2026-10-06", present_count=10, absent_count=20),
        run_detection=False,
    )

    # Seed 6 nominal sessions for CLASS-02-B with varying counts
    c2_counts = [25, 26, 25, 26, 25, 26]
    for day, pres in enumerate(c2_counts, start=1):
        record_session_with_detection(
            repo,
            make_valid_manual_input(
                class_id="CLASS-02-B",
                session_date=f"2026-10-{day:02d}",
                expected_enrollment=30,
                present_count=pres,
                absent_count=30 - pres,
            ),
            run_detection=False,
        )

    # Run detection on CLASS-01-A only
    c1_alerts = run_full_detection_pipeline(repo, class_id="CLASS-01-A")
    assert len(c1_alerts) == 1
    assert c1_alerts[0].class_id == "CLASS-01-A"
    assert c1_alerts[0].rule_id == "RULE_ATTENDANCE_DROP"

    # Triage the alert to ACKNOWLEDGED
    alert_id = c1_alerts[0].alert_id
    assert update_alert_status(repo, alert_id, "ACKNOWLEDGED") is True
    assert repo.get_alert_by_id(alert_id).review_status == "ACKNOWLEDGED"

    # Run full detection pipeline across ALL classes
    all_alerts = run_full_detection_pipeline(repo)
    assert len(all_alerts) == 1

    # Triage status in database MUST remain ACKNOWLEDGED
    persisted_alert = repo.get_alert_by_id(alert_id)
    assert persisted_alert.review_status == "ACKNOWLEDGED"


def test_update_alert_status_validation_and_missing(repo):
    """9. Missing alerts and invalid review statuses are handled clearly."""
    # Invalid status raises ValueError
    with pytest.raises(ValueError, match="Invalid review_status 'BOGUS'"):
        update_alert_status(repo, "ALT-123", "BOGUS")

    # Missing alert returns False by default
    assert update_alert_status(repo, "ALT-missing", "RESOLVED") is False

    # Missing alert with raise_if_missing=True raises KeyError
    with pytest.raises(KeyError, match="does not exist in storage"):
        update_alert_status(repo, "ALT-missing", "RESOLVED", raise_if_missing=True)


def test_absent_count_default_auto_calculation(repo):
    """Verify that absent_count is auto-computed if omitted from manual data dict."""
    data = {
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-20",
        "expected_enrollment": 35,
        "present_count": 30,
        # absent_count omitted
    }
    session, _ = record_session_with_detection(repo, data)
    assert session.absent_count == 5
    assert session.expected_enrollment == 35
    assert session.present_count == 30


def test_manual_session_missing_present_count_rejected(repo):
    """1. Verify manual entry missing present_count is rejected without writing to storage."""
    data = {
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-20",
        "expected_enrollment": 30,
        # present_count omitted
    }
    # Direct validator check
    val_res = validate_manual_session(data)
    assert val_res.is_valid is False
    assert any("Missing required field: 'present_count'" in e for e in val_res.errors)

    # Workflow service submission check
    with pytest.raises(ValueError, match="Missing required field: 'present_count'"):
        record_session_with_detection(repo, data)

    assert len(repo.get_sessions()) == 0
    assert len(repo.get_alerts()) == 0


def test_manual_session_missing_expected_enrollment_rejected(repo):
    """2. Verify manual entry missing expected_enrollment is rejected without writing to storage."""
    data = {
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-20",
        "present_count": 28,
        # expected_enrollment omitted
    }
    # Direct validator check
    val_res = validate_manual_session(data)
    assert val_res.is_valid is False
    assert any("Missing required field: 'expected_enrollment'" in e for e in val_res.errors)

    # Workflow service submission check
    with pytest.raises(ValueError, match="Missing required field: 'expected_enrollment'"):
        record_session_with_detection(repo, data)

    assert len(repo.get_sessions()) == 0
    assert len(repo.get_alerts()) == 0


def test_manual_session_inconsistent_absent_count_rejected_without_writes(repo):
    """3. Verify explicitly inconsistent absent_count is rejected without writes or modification."""
    # Seed 1 existing valid session to verify existing data is untouched
    seed_data = make_valid_manual_input(
        session_date="2026-10-19",
        expected_enrollment=30,
        present_count=28,
        absent_count=2,
    )
    s_seed, _ = record_session_with_detection(repo, seed_data)
    assert len(repo.get_sessions()) == 1

    inconsistent_data = {
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-20",
        "expected_enrollment": 30,
        "present_count": 20,
        "absent_count": 5,  # 20 + 5 = 25 != 30
    }

    # Validate fails
    val_res = validate_manual_session(inconsistent_data)
    assert val_res.is_valid is False
    assert any("present_count + absent_count" in err for err in val_res.errors)

    # Service rejects
    with pytest.raises(ValueError, match="present_count \\+ absent_count"):
        record_session_with_detection(repo, inconsistent_data)

    # Database state unchanged: still only 1 session, 0 alerts
    sessions = repo.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == s_seed.session_id
    assert len(repo.get_alerts()) == 0


def test_manual_session_caller_dict_immutability(repo):
    """4. Verify caller's input dictionary is never mutated across validation and submission."""
    input_dict = {
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-20",
        "expected_enrollment": 32,
        "present_count": 30,
        # Operational fields intentionally omitted to verify defaults do not mutate caller
    }
    sentinel = dict(input_dict)

    # 1. validate_manual_session check
    val_res = validate_manual_session(input_dict)
    assert val_res.is_valid is True
    assert input_dict == sentinel
    assert "absent_count" not in input_dict
    assert "session_id" not in input_dict
    assert "created_at" not in input_dict

    # 2. record_session_with_detection check
    session, alerts = record_session_with_detection(repo, input_dict)
    assert input_dict == sentinel
    assert "absent_count" not in input_dict
    assert "session_id" not in input_dict
    assert "created_at" not in input_dict

    # Confirm session was saved correctly with derived values
    assert session.absent_count == 2
    assert session.expected_enrollment == 32
    assert session.present_count == 30
    stored = repo.get_session_by_id(session.session_id)
    assert stored is not None
    assert stored.absent_count == 2


def test_update_alert_status_invalid_status_raises_value_error(repo):
    """Verify update_alert_status raises ValueError when given an unapproved status string."""
    with pytest.raises(ValueError, match="Invalid review_status"):
        update_alert_status(repo, "nonexistent-id", "INVALID_STATUS")


def test_update_alert_status_missing_key_behavior(repo):
    """Verify update_alert_status return values and raise_if_missing parameter behavior."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"

    # Default raise_if_missing=False returns False
    res = update_alert_status(repo, non_existent_id, "RESOLVED", raise_if_missing=False)
    assert res is False

    # raise_if_missing=True raises KeyError
    with pytest.raises(KeyError, match="does not exist in storage"):
        update_alert_status(repo, non_existent_id, "RESOLVED", raise_if_missing=True)
