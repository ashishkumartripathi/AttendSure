"""Webcam image capture workflow and transparent headcount verification.

Implements Phase 2 genuine webcam capture using Streamlit camera input:
- Associates capture timestamp with class_id and session.
- Privacy by design: in-memory image processing without saving student photographs by default.
- Transparent human-in-the-loop: Image capture is NOT automatic counting.
  The educator inspects the frame and confirms the physical headcount.
- Enforces count invariants and handles camera permission denial/offline states gracefully.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from attendsure.data.models import WebcamStatus


@dataclass(frozen=True)
class WebcamCaptureEvent:
    """Represents a verified webcam capture and headcount confirmation event."""

    capture_id: str
    class_id: str
    session_date: str
    captured_at: str
    status: WebcamStatus
    teacher_confirmed_headcount: Optional[int]
    image_received: bool
    diagnostic_message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_webcam_capture_event(
    class_id: str,
    session_date: str,
    status: WebcamStatus,
    confirmed_headcount: Optional[int] = None,
    image_bytes: Optional[bytes] = None,
    expected_enrollment: Optional[int] = None,
    custom_timestamp: Optional[str] = None,
) -> WebcamCaptureEvent:
    """Create and validate a webcam capture event.

    Args:
        class_id: Cohort identifier.
        session_date: Date string (YYYY-MM-DD).
        status: WebcamStatus enum ("SUCCESS", "CAMERA_UNAVAILABLE", "NOT_ATTEMPTED", "DETECTION_FAILED").
        confirmed_headcount: Integer headcount entered/confirmed by teacher from capture.
        image_bytes: Raw bytes from camera input (kept in-memory for validation only).
        expected_enrollment: Total enrolled students for range validation.
        custom_timestamp: Optional fixed ISO 8601 timestamp for reproducible testing.

    Returns:
        WebcamCaptureEvent with validated counts and diagnostic messages.
    """
    now_ts = custom_timestamp or datetime.now(timezone.utc).isoformat()
    capture_id = f"CAP-{uuid.uuid4()}"
    has_image = image_bytes is not None and len(image_bytes) > 0

    if status == "SUCCESS":
        if confirmed_headcount is None:
            raise ValueError("When status is 'SUCCESS', confirmed_headcount must be provided.")
        if confirmed_headcount < 0:
            raise ValueError("Confirmed headcount cannot be negative.")
        if expected_enrollment is not None and confirmed_headcount > expected_enrollment:
            raise ValueError(
                f"Confirmed headcount ({confirmed_headcount}) cannot exceed enrollment ({expected_enrollment})."
            )

        msg = (
            f"Classroom image captured at {now_ts}. Teacher confirmed headcount of "
            f"{confirmed_headcount} students present."
        )
    elif status == "CAMERA_UNAVAILABLE":
        confirmed_headcount = None
        msg = "Camera device unavailable or permission denied by user browser."
    elif status == "DETECTION_FAILED":
        confirmed_headcount = None
        msg = "Image capture attempted but frame was obstructed, unreadable, or corrupted."
    else:  # NOT_ATTEMPTED
        confirmed_headcount = None
        msg = "Webcam headcount capture was not attempted for this session."

    return WebcamCaptureEvent(
        capture_id=capture_id,
        class_id=str(class_id).strip(),
        session_date=str(session_date).strip(),
        captured_at=now_ts,
        status=status,
        teacher_confirmed_headcount=confirmed_headcount,
        image_received=has_image,
        diagnostic_message=msg,
    )

