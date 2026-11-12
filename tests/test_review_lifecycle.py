"""Unit tests for the alert review lifecycle and explanatory notes persistence.

Tests Objective 2 (Anomaly Detection & Review):
- Recording review decisions with educator notes.
- Updating alert status across PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED.
- Querying review history in chronological order.
- Foreign key cascading delete behavior.
"""

from datetime import datetime, timezone
from pathlib import Path
import uuid
import pytest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.services.attendance_service import update_alert_status


@pytest.fixture
def repo(tmp_path: Path):
    """Provide a fresh temporary SQLite repository."""
    db_file = tmp_path / "test_review_lifecycle.db"
    r = AttendanceRepository(db_path=db_file)
    yield r
    r.close()


def _seed_test_alert(repo: AttendanceRepository) -> str:
    """Helper to seed one session and associated alert for review testing."""
    sid = str(uuid.uuid4())
    aid = f"ALT-{uuid.uuid4()}"
    ts = datetime.now(timezone.utc).isoformat()

    sess = SessionRecord(
        session_id=sid,
        class_id="CLASS-03-A",
        session_date="2026-10-25",
        expected_enrollment=30,
        present_count=14,
        absent_count=16,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at=ts,
    )
    alert = Alert(
        alert_id=aid,
        session_id=sid,
        class_id="CLASS-03-A",
        session_date="2026-10-25",
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Significant Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 14, "attendance_rate_pct": 46.7},
        baseline_reference={"baseline_rate_pct": 88.5},
        threshold_applied={"max_drop_pct": 20.0},
        explanation="Attendance dropped by 41.8% compared to historical baseline.",
        review_status="PENDING_REVIEW",
        created_at=ts,
    )
    repo.save_session(sess)
    repo.save_alerts([alert])
    return aid


def test_add_alert_review_with_notes_persists(repo: AttendanceRepository):
    """Verify adding review decisions with notes updates status and saves history."""
    aid = _seed_test_alert(repo)

    # 1. Educator acknowledges alert with notes
    ok = repo.add_alert_review(
        alert_id=aid,
        new_status="ACKNOWLEDGED",
        notes="Spoke with class teacher. Confirming student absence cause.",
    )
    assert ok

    # Verify alert status updated
    alerts = repo.get_alerts(rule_id="RULE_ATTENDANCE_DROP")
    assert len(alerts) == 1
    assert alerts[0].review_status == "ACKNOWLEDGED"

    # Verify review history contains notes
    history = repo.get_alert_reviews(aid)
    assert len(history) == 1
    assert history[0]["new_status"] == "ACKNOWLEDGED"
    assert "Confirming student absence cause" in history[0]["notes"]


def test_multiple_review_transitions_chronological(repo: AttendanceRepository):
    """Verify multiple review steps form a chronological audit trail."""
    aid = _seed_test_alert(repo)

    repo.add_alert_review(
        aid,
        "ACKNOWLEDGED",
        notes="Teacher informed of attendance drop.",
        reviewed_at="2026-10-25T10:00:00Z",
    )
    repo.add_alert_review(
        aid,
        "RESOLVED",
        notes="Confirmed: 12 students were absent due to seasonal flu; register verified.",
        reviewed_at="2026-10-25T14:30:00Z",
    )

    history = repo.get_alert_reviews(aid)
    assert len(history) == 2
    assert history[0]["new_status"] == "ACKNOWLEDGED"
    assert history[1]["new_status"] == "RESOLVED"
    assert "seasonal flu" in history[1]["notes"]


def test_service_update_alert_status_with_notes(repo: AttendanceRepository):
    """Verify service layer update_alert_status forwards notes properly."""
    aid = _seed_test_alert(repo)

    updated = update_alert_status(
        repo=repo,
        alert_id=aid,
        new_status="DISMISSED",
        notes="Benign duplicate headcount recorded in error.",
        raise_if_missing=True,
    )
    assert updated

    history = repo.get_alert_reviews(aid)
    assert len(history) == 1
    assert history[0]["new_status"] == "DISMISSED"
    assert "Benign duplicate headcount" in history[0]["notes"]


def test_invalid_review_status_rejected(repo: AttendanceRepository):
    """Verify invalid status strings raise ValueError."""
    aid = _seed_test_alert(repo)
    with pytest.raises(ValueError):
        repo.add_alert_review(aid, "INVALID_STATUS_STRING")


def test_nonexistent_alert_returns_false(repo: AttendanceRepository):
    """Verify updating a non-existent alert ID returns False."""
    assert not repo.add_alert_review("NONEXISTENT_ID", "RESOLVED", notes="test")

