"""AttendSure domain data models and contract types.

Follows the approved specification defined in docs/data-contract.md.
"""

from dataclasses import dataclass
from typing import Literal, Optional

# -------------------------------------------------------------------------
# Core Domain Types
# -------------------------------------------------------------------------

WebcamStatus = Literal["SUCCESS", "NOT_ATTEMPTED", "CAMERA_UNAVAILABLE", "DETECTION_FAILED"]
RecordSource = Literal["SYNTHETIC", "MANUAL_ENTRY", "CSV_IMPORT"]
AlertPriority = Literal["INFO", "REVIEW_REQUIRED"]
ReviewStatus = Literal["PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]


@dataclass(frozen=True)
class SessionRecord:
    """Represents an aggregated attendance count record for a cohort session."""

    session_id: str
    class_id: str
    session_date: str
    expected_enrollment: int
    present_count: int
    absent_count: int
    webcam_status: WebcamStatus
    webcam_count: Optional[int]
    record_source: RecordSource
    created_at: str


@dataclass(frozen=True)
class Alert:
    """Represents an explainable anomaly detection signal for review."""

    alert_id: str
    session_id: str
    class_id: str
    session_date: str
    rule_id: str
    rule_title: str
    priority: AlertPriority
    observed_value: dict
    baseline_reference: dict
    threshold_applied: dict
    explanation: str
    review_status: ReviewStatus
    created_at: str


@dataclass(frozen=True)
class ValidationResult:
    """Represents the outcome of validating an individual session record."""

    is_valid: bool
    errors: list[str]
    cleaned_record: Optional[dict]


@dataclass(frozen=True)
class WebcamCounterResult:
    """Represents the output of the optional visible-person estimation module."""

    status: WebcamStatus
    estimated_count: Optional[int]
    confidence_score: Optional[float]
    diagnostic_message: str
