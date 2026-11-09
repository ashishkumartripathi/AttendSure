"""Unit tests for AttendSure data models."""

from dataclasses import FrozenInstanceError
import pytest

from attendsure.data.models import (
    Alert,
    SessionRecord,
    ValidationResult,
    WebcamCounterResult,
)


def test_session_record_instantiation_and_immutability():
    """Verify that SessionRecord initializes correctly and is strictly immutable."""
    record = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440000",
        class_id="CLASS-05-A",
        session_date="2026-10-25",
        expected_enrollment=35,
        present_count=31,
        absent_count=4,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-25T09:15:00Z",
    )

    assert record.session_id == "550e8400-e29b-41d4-a716-446655440000"
    assert record.class_id == "CLASS-05-A"
    assert record.session_date == "2026-10-25"
    assert record.expected_enrollment == 35
    assert record.present_count == 31
    assert record.absent_count == 4
    assert record.webcam_status == "NOT_ATTEMPTED"
    assert record.webcam_count is None
    assert record.record_source == "MANUAL_ENTRY"
    assert record.created_at == "2026-10-25T09:15:00Z"

    with pytest.raises(FrozenInstanceError):
        record.present_count = 32  # type: ignore[misc]


def test_alert_instantiation_and_immutability():
    """Verify that Alert initializes with expected schema and is immutable."""
    alert = Alert(
        alert_id="ALT-550e8400-e29b-41d4-a716-446655440000",
        session_id="550e8400-e29b-41d4-a716-446655440000",
        class_id="CLASS-05-A",
        session_date="2026-10-25",
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Unusual Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 14, "attendance_rate_pct": 40.0},
        baseline_reference={"baseline_type": "rolling_median", "baseline_rate_pct": 80.0},
        threshold_applied={"relative_decline_threshold_pct": 30.0},
        explanation="Test explanation",
        review_status="PENDING_REVIEW",
        created_at="2026-10-25T11:00:00Z",
    )

    assert alert.priority == "REVIEW_REQUIRED"
    assert alert.review_status == "PENDING_REVIEW"
    assert alert.rule_id == "RULE_ATTENDANCE_DROP"

    with pytest.raises(FrozenInstanceError):
        alert.review_status = "ACKNOWLEDGED"  # type: ignore[misc]


def test_validation_result_instantiation():
    """Verify that ValidationResult stores boolean validity and error list."""
    res_valid = ValidationResult(is_valid=True, errors=[], cleaned_record={"key": "val"})
    assert res_valid.is_valid is True
    assert res_valid.errors == []
    assert res_valid.cleaned_record == {"key": "val"}

    res_invalid = ValidationResult(
        is_valid=False, errors=["Error 1", "Error 2"], cleaned_record=None
    )
    assert res_invalid.is_valid is False
    assert len(res_invalid.errors) == 2
    assert res_invalid.cleaned_record is None


def test_webcam_counter_result_instantiation():
    """Verify that WebcamCounterResult stores diagnostic state properly."""
    result = WebcamCounterResult(
        status="SUCCESS",
        estimated_count=30,
        confidence_score=0.92,
        diagnostic_message="Normal visibility",
    )
    assert result.status == "SUCCESS"
    assert result.estimated_count == 30
    assert result.confidence_score == 0.92
