"""Unit tests for the genuine webcam capture workflow and event validation."""

import pytest
from attendsure.data.webcam_capture import (
    WebcamCaptureEvent,
    create_webcam_capture_event,
)


def test_create_capture_event_success():
    """Verify valid capture event with teacher confirmed count."""
    event = create_webcam_capture_event(
        class_id="CLASS-01-A",
        session_date="2026-11-03",
        status="SUCCESS",
        confirmed_headcount=24,
        image_bytes=b"dummy_image_bytes",
        expected_enrollment=30,
        custom_timestamp="2026-11-03T10:00:00Z",
    )
    assert event.status == "SUCCESS"
    assert event.teacher_confirmed_headcount == 24
    assert event.image_received is True
    assert event.captured_at == "2026-11-03T10:00:00Z"
    assert "24 students present" in event.diagnostic_message


def test_create_capture_event_unavailable():
    """Verify camera unavailable status clears headcount."""
    event = create_webcam_capture_event(
        class_id="CLASS-01-A",
        session_date="2026-11-03",
        status="CAMERA_UNAVAILABLE",
        confirmed_headcount=25,  # Must be ignored/cleared when status != SUCCESS
    )
    assert event.status == "CAMERA_UNAVAILABLE"
    assert event.teacher_confirmed_headcount is None
    assert "unavailable" in event.diagnostic_message.lower()


def test_create_capture_event_validation_errors():
    """Verify boundary checks."""
    # SUCCESS requires confirmed headcount
    with pytest.raises(ValueError, match="confirmed_headcount must be provided"):
        create_webcam_capture_event(
            class_id="CLASS-01-A",
            session_date="2026-11-03",
            status="SUCCESS",
            confirmed_headcount=None,
        )

    # Headcount cannot exceed enrollment
    with pytest.raises(ValueError, match="cannot exceed enrollment"):
        create_webcam_capture_event(
            class_id="CLASS-01-A",
            session_date="2026-11-03",
            status="SUCCESS",
            confirmed_headcount=35,
            expected_enrollment=30,
        )

