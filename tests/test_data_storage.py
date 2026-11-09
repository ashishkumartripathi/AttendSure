"""Unit and integration tests for AttendSure SQLite persistence layer.

Verifies schema creation, CRUD operations, constraints, foreign keys,
atomicity/transactions, review status lifecycles, and E2E pipeline integration.
All tests use pytest tmp_path or :memory: databases to isolate from user data.
"""

from dataclasses import asdict
import sqlite3
import pytest
import pandas as pd

from attendsure.data.generator import generate_scenario_sessions
from attendsure.data.models import (
    Alert,
    SessionRecord,
)
from attendsure.data.storage import (
    DEFAULT_DB_PATH,
    AttendanceRepository,
)
from attendsure.detection.rules import detect_anomalies


# -------------------------------------------------------------------------
# Fixtures and Sample Data Helpers
# -------------------------------------------------------------------------


@pytest.fixture
def file_repo(tmp_path):
    """Provides an isolated file-based AttendanceRepository using tmp_path."""
    db_file = tmp_path / "test_attendsure.db"
    repo = AttendanceRepository(db_path=db_file)
    yield repo
    repo.close()


@pytest.fixture
def memory_repo():
    """Provides an isolated in-memory AttendanceRepository."""
    repo = AttendanceRepository(db_path=":memory:")
    yield repo
    repo.close()


def make_sample_session(
    session_id: str = "550e8400-e29b-41d4-a716-446655440001",
    class_id: str = "CLASS-01-A",
    session_date: str = "2026-10-20",
    expected_enrollment: int = 30,
    present_count: int = 28,
    absent_count: int = 2,
    webcam_status: str = "NOT_ATTEMPTED",
    webcam_count: int | None = None,
    record_source: str = "MANUAL_ENTRY",
    created_at: str = "2026-10-20T09:00:00Z",
) -> SessionRecord:
    """Helper to construct a valid SessionRecord."""
    return SessionRecord(
        session_id=session_id,
        class_id=class_id,
        session_date=session_date,
        expected_enrollment=expected_enrollment,
        present_count=present_count,
        absent_count=absent_count,
        webcam_status=webcam_status,  # type: ignore[arg-type]
        webcam_count=webcam_count,
        record_source=record_source,  # type: ignore[arg-type]
        created_at=created_at,
    )


def make_sample_alert(
    alert_id: str = "ALT-550e8400-e29b-41d4-a716-446655440001",
    session_id: str = "550e8400-e29b-41d4-a716-446655440001",
    class_id: str = "CLASS-01-A",
    session_date: str = "2026-10-20",
    rule_id: str = "RULE_ATTENDANCE_DROP",
    rule_title: str = "Unusual Attendance Drop",
    priority: str = "REVIEW_REQUIRED",
    observed_value: dict | None = None,
    baseline_reference: dict | None = None,
    threshold_applied: dict | None = None,
    explanation: str = "Test plain-language explanation.",
    review_status: str = "PENDING_REVIEW",
    created_at: str = "2026-10-20T10:00:00Z",
) -> Alert:
    """Helper to construct a valid Alert."""
    return Alert(
        alert_id=alert_id,
        session_id=session_id,
        class_id=class_id,
        session_date=session_date,
        rule_id=rule_id,
        rule_title=rule_title,
        priority=priority,  # type: ignore[arg-type]
        observed_value=observed_value or {"present_count": 14, "attendance_rate_pct": 46.7},
        baseline_reference=baseline_reference
        or {"baseline_type": "rolling_median", "baseline_rate_pct": 90.0},
        threshold_applied=threshold_applied
        or {"relative_decline_threshold_pct": 30.0, "observed_relative_decline_pct": 48.1},
        explanation=explanation,
        review_status=review_status,  # type: ignore[arg-type]
        created_at=created_at,
    )


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------


def test_default_db_path_resolution():
    """Verify DEFAULT_DB_PATH is resolved absolutely without relying on CWD."""
    assert DEFAULT_DB_PATH.is_absolute()
    assert DEFAULT_DB_PATH.name == "attendsure.db"
    assert DEFAULT_DB_PATH.parent.name == "data"


def test_schema_creation_and_repeated_initialization(tmp_path):
    """Verify tables and indexes are created idempotently on file and in-memory databases."""
    db_file = tmp_path / "schema_test.db"
    repo = AttendanceRepository(db_path=db_file)

    # Calling init_schema multiple times must be a safe, idempotent no-op
    repo.init_schema()
    repo.init_schema()

    conn = repo.get_connection()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('attendance_sessions', 'alerts')"
    )
    tables = {row["name"] for row in cur.fetchall()}
    assert tables == {"attendance_sessions", "alerts"}

    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row["name"] for row in cur.fetchall()}
    assert "idx_sessions_class_date" in indexes
    assert "idx_alerts_session_id" in indexes
    repo.close()

    # Also test with :memory:
    mem_repo = AttendanceRepository(db_path=":memory:")
    mem_repo.init_schema()
    conn_mem = mem_repo.get_connection()
    cur_mem = conn_mem.execute("SELECT name FROM sqlite_master WHERE type='table'")
    mem_tables = {row["name"] for row in cur_mem.fetchall()}
    assert "attendance_sessions" in mem_tables
    mem_repo.close()


def test_session_round_trip_with_webcam_none_and_success(file_repo):
    """Verify session insert and retrieval round trip for both webcam None and SUCCESS states."""
    session_no_cam = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
    )
    session_with_cam = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        class_id="CLASS-02-A",
        session_date="2026-10-20",
        webcam_status="SUCCESS",
        webcam_count=28,
    )

    file_repo.save_session(session_no_cam)
    file_repo.save_session(session_with_cam)

    # Fetch by ID
    fetched_1 = file_repo.get_session_by_id(session_no_cam.session_id)
    assert fetched_1 == session_no_cam
    assert fetched_1.webcam_count is None

    fetched_2 = file_repo.get_session_by_id(session_with_cam.session_id)
    assert fetched_2 == session_with_cam
    assert fetched_2.webcam_count == 28

    # Fetch all as list
    all_sessions = file_repo.get_sessions()
    assert len(all_sessions) == 2
    assert all_sessions[0] == session_no_cam
    assert all_sessions[1] == session_with_cam

    # Fetch as DataFrame
    df = file_repo.get_sessions(as_df=True)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df["webcam_count"].iloc[0] is None
    assert df["webcam_count"].iloc[1] == 28


def test_alert_round_trip_with_nested_json_and_none(file_repo):
    """Verify alert persistence preserves nested dicts, numbers, booleans, and null values."""
    session = make_sample_session()
    file_repo.save_session(session)

    alert = make_sample_alert(
        observed_value={
            "present_count": 0,
            "webcam_count": 6,
            "relative_diff": None,  # None/null value
            "flagged": True,  # boolean value
        },
        baseline_reference={
            "baseline_type": "manual_roll_call",
            "reference_count": 0,
        },
        threshold_applied={
            "abs_diff_threshold": 5,
            "rel_diff_threshold_pct": 20.0,
            "zero_attendance_evaluation": True,
        },
    )

    file_repo.save_alerts([alert])

    fetched = file_repo.get_alert_by_id(alert.alert_id)
    assert fetched is not None
    assert fetched.alert_id == alert.alert_id
    assert fetched.session_id == alert.session_id
    assert fetched.observed_value == alert.observed_value
    assert fetched.observed_value["relative_diff"] is None
    assert fetched.observed_value["flagged"] is True
    assert fetched.threshold_applied["zero_attendance_evaluation"] is True
    assert fetched.threshold_applied["rel_diff_threshold_pct"] == 20.0

    # Fetch as DataFrame
    df_alerts = file_repo.get_alerts(as_df=True)
    assert isinstance(df_alerts, pd.DataFrame)
    assert len(df_alerts) == 1
    assert df_alerts["alert_id"].iloc[0] == alert.alert_id
    assert df_alerts["observed_value"].iloc[0]["relative_diff"] is None


def test_duplicate_session_id_rejection(file_repo):
    """Verify duplicate session_id raises sqlite3.IntegrityError."""
    session_1 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )
    file_repo.save_session(session_1)

    # Different class/date, but identical session_id
    session_dup = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-02-A",
        session_date="2026-10-21",
    )

    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_session(session_dup)

    # Verify only original session exists
    assert file_repo.get_sessions() == [session_1]


def test_duplicate_class_date_rejection(file_repo):
    """Verify duplicate (class_id, session_date) raises sqlite3.IntegrityError."""
    session_1 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )
    file_repo.save_session(session_1)

    # Different session_id, but identical (class_id, session_date)
    session_dup = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )

    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_session(session_dup)

    assert len(file_repo.get_sessions()) == 1


def test_database_level_check_constraints(file_repo):
    """Verify that SQLite CHECK constraints are active and reject inconsistent rows."""
    conn = file_repo.get_connection()

    # 1. present + absent != expected_enrollment
    with pytest.raises(sqlite3.IntegrityError, match="chk_sessions_count_invariant"):
        with conn:
            conn.execute(
                """
                INSERT INTO attendance_sessions (
                    session_id, class_id, session_date, expected_enrollment,
                    present_count, absent_count, webcam_status, webcam_count,
                    record_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "550e8400-e29b-41d4-a716-446655440010",
                    "CLASS-01-A",
                    "2026-10-20",
                    30,
                    20,
                    5,  # 20 + 5 != 30
                    "NOT_ATTEMPTED",
                    None,
                    "MANUAL_ENTRY",
                    "2026-10-20T09:00:00Z",
                ),
            )

    # 2. webcam_status == 'SUCCESS' but webcam_count is NULL
    with pytest.raises(sqlite3.IntegrityError, match="chk_sessions_webcam_mapping"):
        with conn:
            conn.execute(
                """
                INSERT INTO attendance_sessions (
                    session_id, class_id, session_date, expected_enrollment,
                    present_count, absent_count, webcam_status, webcam_count,
                    record_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "550e8400-e29b-41d4-a716-446655440011",
                    "CLASS-01-A",
                    "2026-10-21",
                    30,
                    28,
                    2,
                    "SUCCESS",
                    None,  # Invalid: SUCCESS requires webcam_count >= 0
                    "MANUAL_ENTRY",
                    "2026-10-21T09:00:00Z",
                ),
            )

    # 3. webcam_status != 'SUCCESS' but webcam_count is provided
    with pytest.raises(sqlite3.IntegrityError, match="chk_sessions_webcam_mapping"):
        with conn:
            conn.execute(
                """
                INSERT INTO attendance_sessions (
                    session_id, class_id, session_date, expected_enrollment,
                    present_count, absent_count, webcam_status, webcam_count,
                    record_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "550e8400-e29b-41d4-a716-446655440012",
                    "CLASS-01-A",
                    "2026-10-22",
                    30,
                    28,
                    2,
                    "NOT_ATTEMPTED",
                    15,  # Invalid: non-SUCCESS must have webcam_count NULL
                    "MANUAL_ENTRY",
                    "2026-10-22T09:00:00Z",
                ),
            )


def test_foreign_key_enforcement_and_cascade_delete(file_repo):
    """Verify alerts require a valid session_id and cascade delete when the session is removed."""
    # Attempt to insert alert without parent session via repository API raises ValueError
    orphan_alert = make_sample_alert(
        alert_id="ALT-550e8400-e29b-41d4-a716-446655440999",
        session_id="550e8400-e29b-41d4-a716-446655440999",  # Does not exist
    )
    with pytest.raises(ValueError, match="references non-existent session"):
        file_repo.save_alerts([orphan_alert])

    # Direct database insert of orphan alert also fails SQLite foreign key constraint
    conn = file_repo.get_connection()
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        with conn:
            conn.execute(
                """
                INSERT INTO alerts (
                    alert_id, session_id, class_id, session_date, rule_id,
                    rule_title, priority, observed_value, baseline_reference,
                    threshold_applied, explanation, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ALT-000",
                    "non-existent-session",
                    "CLASS-01-A",
                    "2026-10-20",
                    "RULE_ATTENDANCE_DROP",
                    "Unusual Attendance Drop",
                    "REVIEW_REQUIRED",
                    "{}",
                    "{}",
                    "{}",
                    "Explanation",
                    "PENDING_REVIEW",
                    "2026-10-20T10:00:00Z",
                ),
            )

    # Now create valid session and alert
    session = make_sample_session()
    file_repo.save_session(session)
    valid_alert = make_sample_alert(session_id=session.session_id)
    file_repo.save_alerts([valid_alert])

    assert file_repo.get_alert_by_id(valid_alert.alert_id) is not None

    # Test ON DELETE CASCADE consequence: deleting parent session deletes referencing alert
    with conn:
        conn.execute("DELETE FROM attendance_sessions WHERE session_id = ?", (session.session_id,))

    assert file_repo.get_session_by_id(session.session_id) is None
    assert file_repo.get_alert_by_id(valid_alert.alert_id) is None


def test_review_status_updates(file_repo):
    """Verify review status workflow transitions and validation."""
    session = make_sample_session()
    file_repo.save_session(session)

    alert = make_sample_alert(session_id=session.session_id)
    file_repo.save_alerts([alert])
    assert file_repo.get_alert_by_id(alert.alert_id).review_status == "PENDING_REVIEW"

    # Transition to ACKNOWLEDGED
    assert file_repo.update_alert_review_status(alert.alert_id, "ACKNOWLEDGED") is True
    assert file_repo.get_alert_by_id(alert.alert_id).review_status == "ACKNOWLEDGED"

    # Transition to RESOLVED
    assert file_repo.update_alert_review_status(alert.alert_id, "RESOLVED") is True
    assert file_repo.get_alert_by_id(alert.alert_id).review_status == "RESOLVED"

    # Transition to DISMISSED
    assert file_repo.update_alert_review_status(alert.alert_id, "DISMISSED") is True
    assert file_repo.get_alert_by_id(alert.alert_id).review_status == "DISMISSED"

    # Invalid status raises ValueError
    with pytest.raises(ValueError, match="Invalid review_status 'INVALID_STATUS'"):
        file_repo.update_alert_review_status(alert.alert_id, "INVALID_STATUS")

    # Non-existent alert_id returns False
    assert file_repo.update_alert_review_status("ALT-nonexistent", "RESOLVED") is False


def test_atomic_batch_rollback_on_invalid_input(file_repo):
    """Verify save_sessions validates entire batch before insertion and persists nothing on error."""
    valid_1 = make_sample_session(session_id="550e8400-e29b-41d4-a716-446655440001", session_date="2026-10-20")
    invalid_2 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        session_date="2026-10-21",
        expected_enrollment=30,
        present_count=20,
        absent_count=5,  # 20 + 5 != 30, validation fails!
    )

    with pytest.raises(ValueError, match="Batch validation failed"):
        file_repo.save_sessions([valid_1, invalid_2])

    # Neither record should be persisted
    assert len(file_repo.get_sessions()) == 0


def test_atomic_batch_rollback_on_sql_uniqueness_failure(file_repo):
    """Verify that if database insertion fails mid-batch, all batch changes are rolled back."""
    existing = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )
    file_repo.save_session(existing)

    # Batch where 1st is new and valid, but 2nd duplicates existing's class_id and date
    new_valid = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        class_id="CLASS-02-A",
        session_date="2026-10-21",
    )
    colliding = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440003",
        class_id="CLASS-01-A",  # Collides with existing!
        session_date="2026-10-20",
    )

    with pytest.raises(sqlite3.IntegrityError):
        file_repo.save_sessions([new_valid, colliding])

    # new_valid must NOT have been saved
    assert file_repo.get_session_by_id(new_valid.session_id) is None
    assert len(file_repo.get_sessions()) == 1


def test_alert_insertion_idempotency_without_resetting_review_status(file_repo):
    """Verify that re-running detection does not overwrite manual review triage status."""
    session = make_sample_session()
    file_repo.save_session(session)

    alert = make_sample_alert(session_id=session.session_id)
    file_repo.save_alerts([alert])

    # Educator triages the alert
    file_repo.update_alert_review_status(alert.alert_id, "RESOLVED")
    assert file_repo.get_alert_by_id(alert.alert_id).review_status == "RESOLVED"

    # Re-running detection emits identical alert with default "PENDING_REVIEW"
    file_repo.save_alerts([alert])

    # The review status in database must remain "RESOLVED"
    current = file_repo.get_alert_by_id(alert.alert_id)
    assert current.review_status == "RESOLVED"


def test_combined_session_and_alert_transaction_rollback(file_repo):
    """Verify save_session_batch_with_alerts rolls back all changes if either part fails."""
    new_session = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )
    # Alert with invalid rule_id triggers validation error
    invalid_alert_dict = asdict(make_sample_alert(session_id=new_session.session_id))
    invalid_alert_dict["rule_id"] = "INVALID_RULE_NAME"

    with pytest.raises(ValueError, match="Invalid rule_id 'INVALID_RULE_NAME'"):
        file_repo.save_session_batch_with_alerts([new_session], [invalid_alert_dict])

    # new_session must have been rolled back
    assert file_repo.get_session_by_id(new_session.session_id) is None
    assert len(file_repo.get_sessions()) == 0
    assert len(file_repo.get_alerts()) == 0

    # Successful combined transaction
    valid_alert = make_sample_alert(session_id=new_session.session_id)
    saved_sess, saved_alr = file_repo.save_session_batch_with_alerts(
        [new_session], [valid_alert]
    )
    assert len(saved_sess) == 1
    assert len(saved_alr) == 1
    assert file_repo.get_session_by_id(new_session.session_id) is not None
    assert file_repo.get_alert_by_id(valid_alert.alert_id) is not None


def test_filtering_and_stable_chronological_ordering(file_repo):
    """Verify sessions and alerts filtering by class, date range, rule, and stable ordering."""
    # Create 3 sessions across classes and dates
    s1 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-02-A",
        session_date="2026-10-22",
    )
    s2 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
    )
    s3 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440003",
        class_id="CLASS-01-A",
        session_date="2026-10-21",
    )
    file_repo.save_sessions([s1, s2, s3])

    # Unfiltered retrieval should be ordered by (session_date ASC, class_id ASC)
    ordered = file_repo.get_sessions()
    assert [s.session_id for s in ordered] == [s2.session_id, s3.session_id, s1.session_id]

    # Filter by class_id
    c1_sessions = file_repo.get_sessions(class_id="CLASS-01-A")
    assert [s.session_id for s in c1_sessions] == [s2.session_id, s3.session_id]

    # Filter by date range
    range_sessions = file_repo.get_sessions(start_date="2026-10-21", end_date="2026-10-22")
    assert [s.session_id for s in range_sessions] == [s3.session_id, s1.session_id]

    # Create alerts on s2 and s3
    a1 = make_sample_alert(
        alert_id="ALT-001",
        session_id=s2.session_id,
        class_id=s2.class_id,
        session_date=s2.session_date,
        rule_id="RULE_ATTENDANCE_DROP",
    )
    a2 = make_sample_alert(
        alert_id="ALT-002",
        session_id=s3.session_id,
        class_id=s3.class_id,
        session_date=s3.session_date,
        rule_id="RULE_REPEATED_HEADCOUNT",
    )
    file_repo.save_alerts([a1, a2])

    file_repo.update_alert_review_status("ALT-001", "ACKNOWLEDGED")

    # Filter alerts by review status
    ack_alerts = file_repo.get_alerts(review_status="ACKNOWLEDGED")
    assert len(ack_alerts) == 1
    assert ack_alerts[0].alert_id == "ALT-001"

    # Filter alerts by rule_id
    drop_alerts = file_repo.get_alerts(rule_id="RULE_ATTENDANCE_DROP")
    assert len(drop_alerts) == 1
    assert drop_alerts[0].alert_id == "ALT-001"


def test_closing_and_reopening_preserves_data(tmp_path):
    """Verify that closing and reopening a file-based repository preserves all records."""
    db_file = tmp_path / "persistence_test.db"
    repo1 = AttendanceRepository(db_path=db_file)

    session = make_sample_session()
    repo1.save_session(session)
    alert = make_sample_alert(session_id=session.session_id)
    repo1.save_alerts([alert])
    repo1.close()

    # Reopen in new repository instance
    repo2 = AttendanceRepository(db_path=db_file)
    fetched_sess = repo2.get_session_by_id(session.session_id)
    assert fetched_sess == session

    fetched_alert = repo2.get_alert_by_id(alert.alert_id)
    assert fetched_alert == alert
    repo2.close()


def test_e2e_generator_persistence_detection_alerts(tmp_path):
    """End-to-end integration: generator -> storage -> detection -> alert storage."""
    db_file = tmp_path / "e2e_pipeline.db"
    repo = AttendanceRepository(db_path=db_file)

    # 1. Generate synthetic scenario
    sessions_df = generate_scenario_sessions(
        scenario_type="ATTENDANCE_DROP",
        class_id="CLASS-01-A",
        num_days=10,
        expected_enrollment=30,
        include_labels=False,
    )

    # 2. Persist sessions
    saved_sessions = repo.save_sessions(sessions_df)
    assert len(saved_sessions) == 10

    # 3. Retrieve sessions as DataFrame
    loaded_df = repo.get_sessions(as_df=True)
    assert len(loaded_df) == 10

    # 4. Run detection pipeline
    detected_alerts = detect_anomalies(loaded_df)
    assert len(detected_alerts) > 0
    rule_ids = {a.rule_id for a in detected_alerts}
    assert "RULE_ATTENDANCE_DROP" in rule_ids

    # 5. Persist alerts
    saved_alerts = repo.save_alerts(detected_alerts)
    assert len(saved_alerts) == len(detected_alerts)

    # 6. Retrieve alerts from repository
    persisted_alerts = repo.get_alerts()
    assert len(persisted_alerts) == len(detected_alerts)
    assert persisted_alerts[0].session_id == detected_alerts[0].session_id

    repo.close()


def test_input_objects_and_dataframes_immutability(file_repo):
    """Verify that repository methods do not mutate input DataFrames or objects."""
    df_original = generate_scenario_sessions(
        scenario_type="NOMINAL",
        num_days=5,
        include_labels=False,
    )
    df_copy = df_original.copy(deep=True)

    file_repo.save_sessions(df_original)

    # DataFrame must be completely unchanged
    pd.testing.assert_frame_equal(df_original, df_copy)

    # Dict input to save_session must not be mutated
    dict_input = {
        "session_id": "550e8400-e29b-41d4-a716-446655440099",
        "class_id": "CLASS-09-A",
        "session_date": "2026-10-20",
        "expected_enrollment": 30,
        "present_count": 25,
        "absent_count": 5,
        "webcam_status": "NOT_ATTEMPTED",
        "webcam_count": None,
        "record_source": "MANUAL_ENTRY",
        "created_at": "2026-10-20T09:00:00Z",
    }
    dict_copy = dict(dict_input)
    file_repo.save_session(dict_input)
    assert dict_input == dict_copy


def test_context_manager_support(tmp_path):
    """Verify AttendanceRepository works as a context manager and closes properly."""
    db_file = tmp_path / "cm_test.db"
    with AttendanceRepository(db_path=db_file) as repo:
        session = make_sample_session()
        repo.save_session(session)
        assert repo.get_session_by_id(session.session_id) is not None

    # Connection should be closed after exiting context manager
    assert repo._conn is None


# -------------------------------------------------------------------------
# M4.4 Targeted Regression Tests: Fixes 1 through 5
# -------------------------------------------------------------------------


def test_alert_session_metadata_mismatched_class_id(file_repo):
    """Fix 1: Reject alert whose class_id contradicts the referenced session."""
    session = make_sample_session(class_id="CLASS-01-A")
    file_repo.save_session(session)

    mismatched_alert = make_sample_alert(
        session_id=session.session_id,
        class_id="CLASS-02-B",  # Does not match stored session!
        session_date=session.session_date,
    )
    with pytest.raises(ValueError, match="class_id 'CLASS-02-B' does not match"):
        file_repo.save_alerts([mismatched_alert])

    assert len(file_repo.get_alerts()) == 0


def test_alert_session_metadata_mismatched_date(file_repo):
    """Fix 1: Reject alert whose session_date contradicts the referenced session."""
    session = make_sample_session(session_date="2026-10-20")
    file_repo.save_session(session)

    mismatched_alert = make_sample_alert(
        session_id=session.session_id,
        class_id=session.class_id,
        session_date="2026-10-25",  # Does not match stored session!
    )
    with pytest.raises(ValueError, match="session_date '2026-10-25' does not match"):
        file_repo.save_alerts([mismatched_alert])

    assert len(file_repo.get_alerts()) == 0


def test_alert_session_missing_session(file_repo):
    """Fix 1: Reject alert referencing non-existent session with clear ValueError."""
    orphan = make_sample_alert(session_id="550e8400-e29b-41d4-a716-446655440888")
    with pytest.raises(ValueError, match="references non-existent session"):
        file_repo.save_alerts([orphan])

    assert len(file_repo.get_alerts()) == 0


def test_alert_session_consistency_in_combined_transaction(file_repo):
    """Fix 1: Combined transaction validates alerts against uncommitted batch and stored sessions."""
    s1 = make_sample_session(session_id="550e8400-e29b-41d4-a716-446655440001", class_id="CLASS-01-A")
    file_repo.save_session(s1)

    s2 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440002",
        class_id="CLASS-02-A",
        session_date="2026-10-21",
    )

    # Valid: a1 references stored s1, a2 references uncommitted s2 in same batch
    a1 = make_sample_alert(alert_id="ALT-001", session_id=s1.session_id, class_id=s1.class_id, session_date=s1.session_date)
    a2 = make_sample_alert(alert_id="ALT-002", session_id=s2.session_id, class_id=s2.class_id, session_date=s2.session_date)

    saved_s, saved_a = file_repo.save_session_batch_with_alerts([s2], [a1, a2])
    assert len(saved_s) == 1
    assert len(saved_a) == 2

    # Mismatched class_id against uncommitted session in batch
    s3 = make_sample_session(
        session_id="550e8400-e29b-41d4-a716-446655440003",
        class_id="CLASS-03-A",
        session_date="2026-10-22",
    )
    bad_a = make_sample_alert(
        alert_id="ALT-003",
        session_id=s3.session_id,
        class_id="WRONG-CLASS",
        session_date=s3.session_date,
    )
    with pytest.raises(ValueError, match="class_id 'WRONG-CLASS' does not match"):
        file_repo.save_session_batch_with_alerts([s3], [bad_a])

    # s3 must have been rolled back
    assert file_repo.get_session_by_id(s3.session_id) is None


def test_closed_in_memory_repository_raises_runtime_error():
    """Fix 2: Operations on a closed in-memory repository raise RuntimeError."""
    repo = AttendanceRepository(db_path=":memory:")
    repo.close()

    with pytest.raises(RuntimeError, match="Cannot perform operations on a closed in-memory repository"):
        repo.get_sessions()

    with pytest.raises(RuntimeError, match="Cannot perform operations on a closed in-memory repository"):
        repo.save_session(make_sample_session())

    with pytest.raises(RuntimeError, match="Cannot perform operations on a closed in-memory repository"):
        repo.get_connection()


def test_file_repository_reconnects_after_close(tmp_path):
    """Fix 2: File-based repository cleanly reconnects after close and initializes schema."""
    db_file = tmp_path / "reconnect_test.db"
    repo = AttendanceRepository(db_path=db_file)
    s = make_sample_session()
    repo.save_session(s)
    repo.close()

    # Reconnect via same repository instance
    reopened_sessions = repo.get_sessions()
    assert len(reopened_sessions) == 1
    assert reopened_sessions[0].session_id == s.session_id
    repo.close()


def test_context_manager_exit_closes_in_memory_safely():
    """Fix 2: Context manager exit closes in-memory repo and prevents subsequent use."""
    with AttendanceRepository(db_path=":memory:") as repo:
        repo.save_session(make_sample_session())
        assert len(repo.get_sessions()) == 1

    with pytest.raises(RuntimeError, match="Cannot perform operations on a closed in-memory repository"):
        repo.get_sessions()


def test_batch_alerts_rollback_when_later_alert_fails_foreign_key(file_repo):
    """Fix 3: Batch of alerts persists none if a later alert fails session validation."""
    session = make_sample_session()
    file_repo.save_session(session)

    valid_alert = make_sample_alert(
        alert_id="ALT-001",
        session_id=session.session_id,
        class_id=session.class_id,
        session_date=session.session_date,
    )
    orphan_alert = make_sample_alert(
        alert_id="ALT-002",
        session_id="550e8400-e29b-41d4-a716-446655440999",  # Does not exist
    )

    with pytest.raises(ValueError, match="references non-existent session"):
        file_repo.save_alerts([valid_alert, orphan_alert])

    # valid_alert must NOT be persisted
    assert file_repo.get_alert_by_id(valid_alert.alert_id) is None
    assert len(file_repo.get_alerts()) == 0


def test_combined_transaction_rolls_back_sessions_on_sql_alert_failure(file_repo, monkeypatch):
    """Fix 3: Combined transaction rolls back inserted sessions if SQL alert insert fails."""
    s = make_sample_session(session_id="550e8400-e29b-41d4-a716-446655440077")
    a = make_sample_alert(session_id=s.session_id, class_id=s.class_id, session_date=s.session_date)

    # Force alert SQL insertion to fail after session insert
    def mock_fail_insert(conn, params):
        raise sqlite3.IntegrityError("Simulated database failure during alert insertion")

    monkeypatch.setattr(file_repo, "_insert_alert_records", mock_fail_insert)

    with pytest.raises(sqlite3.IntegrityError, match="Simulated database failure"):
        file_repo.save_session_batch_with_alerts([s], [a])

    # Session must be completely rolled back
    assert file_repo.get_session_by_id(s.session_id) is None
    assert len(file_repo.get_sessions()) == 0

    # Ensure repository connection remains in a clean, usable state
    monkeypatch.undo()
    saved_s = file_repo.save_session(s)
    assert saved_s.session_id == s.session_id
    assert file_repo.get_session_by_id(s.session_id) is not None


def test_empty_batches_return_empty_without_error(file_repo):
    """Fix 4: Empty batches return empty collections without opening write transactions."""
    assert file_repo.save_sessions([]) == []
    assert file_repo.save_sessions(pd.DataFrame()) == []
    assert file_repo.save_alerts([]) == []
    assert file_repo.save_session_batch_with_alerts([], []) == ([], [])
    assert file_repo.save_session_batch_with_alerts(pd.DataFrame(), []) == ([], [])


def test_unsupported_json_values_rejected(file_repo):
    """Fix 4: Non-JSON serializable values in alert metrics raise TypeError before write."""
    s = make_sample_session()
    file_repo.save_session(s)

    bad_alert = make_sample_alert(
        session_id=s.session_id,
        class_id=s.class_id,
        session_date=s.session_date,
        observed_value={"unsupported_set": {1, 2, 3}},  # Python set is not JSON-serializable
    )
    with pytest.raises(TypeError, match="non-JSON-serializable metric values"):
        file_repo.save_alerts([bad_alert])

    assert len(file_repo.get_alerts()) == 0


def test_invalid_alert_objects_and_dictionaries_rejected(file_repo):
    """Fix 4: Reject non-Alert/dict objects and dictionaries missing required fields."""
    with pytest.raises(TypeError, match="Expected Alert or dict, got int"):
        file_repo.save_alerts([12345])  # type: ignore[list-item]

    incomplete_dict = {
        "alert_id": "ALT-001",
        "session_id": "550e8400-e29b-41d4-a716-446655440001",
        # Missing class_id, session_date, rule_id, etc.
    }
    with pytest.raises(ValueError, match="missing required fields"):
        file_repo.save_alerts([incomplete_dict])


def test_reopened_file_connection_enforces_foreign_keys(tmp_path):
    """Fix 5: Reopened file-based connection retains PRAGMA foreign_keys = ON and rejects orphans."""
    db_file = tmp_path / "fk_reopen.db"
    repo1 = AttendanceRepository(db_path=db_file)
    s = make_sample_session()
    repo1.save_session(s)
    repo1.close()

    # Reopen connection via new repository instance
    repo2 = AttendanceRepository(db_path=db_file)
    conn = repo2.get_connection()

    # Direct SQL insert of an orphan alert must fail SQLite foreign key check
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        with conn:
            conn.execute(
                """
                INSERT INTO alerts (
                    alert_id, session_id, class_id, session_date, rule_id,
                    rule_title, priority, observed_value, baseline_reference,
                    threshold_applied, explanation, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ALT-999",
                    "non-existent-session-id",
                    "CLASS-01-A",
                    "2026-10-20",
                    "RULE_ATTENDANCE_DROP",
                    "Unusual Attendance Drop",
                    "REVIEW_REQUIRED",
                    "{}",
                    "{}",
                    "{}",
                    "Explanation",
                    "PENDING_REVIEW",
                    "2026-10-20T10:00:00Z",
                ),
            )
    repo2.close()
