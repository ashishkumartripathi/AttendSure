"""Application services for AttendSure.

Provides workflow orchestration connecting data validation, anomaly detection,
and persistence conforming to docs/data-contract.md.
"""

from attendsure.services.attendance_service import (
    record_session_with_detection,
    run_full_detection_pipeline,
    update_alert_status,
    validate_manual_session,
)

__all__ = [
    "record_session_with_detection",
    "run_full_detection_pipeline",
    "update_alert_status",
    "validate_manual_session",
]
