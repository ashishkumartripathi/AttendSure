"""Application workflow service connecting validation, detection, and storage.

Provides coordinated services for manual session recording, historical anomaly
detection, and alert triage adhering to docs/data-contract.md.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional, Union
import uuid

import pandas as pd

from attendsure.data.models import (
    Alert,
    RecordSource,
    ReviewStatus,
    SessionRecord,
    ValidationResult,
    WebcamStatus,
)
from attendsure.data.storage import AttendanceRepository
from attendsure.data.validation import validate_session_dict
from attendsure.detection.rules import detect_anomalies


def _prepare_manual_candidate(data: dict) -> dict:
    """Prepare candidate session dictionary with approved defaults for omitted operational fields."""
    candidate = dict(data)

    if "session_id" not in candidate or not candidate["session_id"]:
        candidate["session_id"] = str(uuid.uuid4())

    if "record_source" not in candidate or not candidate["record_source"]:
        candidate["record_source"] = "MANUAL_ENTRY"

    if "webcam_status" not in candidate or not candidate["webcam_status"]:
        candidate["webcam_status"] = "NOT_ATTEMPTED"

    if "webcam_count" not in candidate and candidate["webcam_status"] != "SUCCESS":
        candidate["webcam_count"] = None

    if "created_at" not in candidate or not candidate["created_at"]:
        candidate["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if "absent_count" not in candidate:
        enrollment = candidate.get("expected_enrollment")
        present = candidate.get("present_count")
        if (
            isinstance(enrollment, int)
            and not isinstance(enrollment, bool)
            and isinstance(present, int)
            and not isinstance(present, bool)
        ):
            candidate["absent_count"] = enrollment - present

    return candidate


def validate_manual_session(data: dict) -> ValidationResult:
    """Validate a single manual attendance session dictionary.

    Supplies contract-compliant defaults for omitted operational fields
    (session_id, record_source, webcam_status, created_at, absent_count)
    and delegates directly to the authoritative contract validator in validation.py.
    Does not duplicate validation rules or mutate the input dictionary.

    Args:
        data: Dictionary of attendance session fields.

    Returns:
        ValidationResult containing is_valid, list of errors, and cleaned_record.
    """
    if not isinstance(data, dict):
        return ValidationResult(
            is_valid=False,
            errors=[f"Expected dict for session data, got {type(data).__name__}."],
            cleaned_record=None,
        )

    candidate = _prepare_manual_candidate(data)
    return validate_session_dict(candidate)


def record_session_with_detection(
    repo: AttendanceRepository,
    data: dict,
    run_detection: bool = True,
) -> tuple[SessionRecord, list[Alert]]:
    """Validate, record, and evaluate an attendance session with historical context.

    Workflow:
    1. Prepares candidate dictionary with contract-approved defaults for omitted
       operational fields (session_id, record_source, webcam_status, created_at).
    2. Validates candidate data via validate_session_dict. Rejects invalid input
       immediately with ValueError without writing anything to the database.
    3. If run_detection is True:
       - Loads stored history for the same class_id from SQLite.
       - Combines history with the candidate session.
       - Runs detect_anomalies() across the combined cohort timeline.
       - Isolates alerts specifically relevant to the newly submitted session_id.
       - Atomically persists the new session and its relevant alerts using
         repo.save_session_batch_with_alerts().
    4. If run_detection is False:
       - Persists the new session directly using repo.save_session().
    5. Always preserves existing alert review statuses via repository ON CONFLICT
       safeguards.

    Args:
        repo: Active AttendanceRepository instance.
        data: Dictionary of session fields (class_id, session_date, expected_enrollment,
            present_count, absent_count required; operational fields optional).
        run_detection: If True, executes the anomaly detection pipeline; if False,
            persists session without generating alerts.

    Returns:
        Tuple of (persisted SessionRecord, list of newly generated Alert objects).

    Raises:
        ValueError: If validation fails or input is malformed.
        sqlite3.IntegrityError: If session_id or (class_id, session_date) violates
            database uniqueness or CHECK constraints.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict for session data, got {type(data).__name__}.")

    candidate = _prepare_manual_candidate(data)

    # Validate candidate data; never mutate original data
    val_result = validate_session_dict(candidate)
    if not val_result.is_valid or val_result.cleaned_record is None:
        errors_str = "; ".join(val_result.errors)
        raise ValueError(f"Session validation failed: {errors_str}")

    clean = val_result.cleaned_record
    session = SessionRecord(
        session_id=str(clean["session_id"]),
        class_id=str(clean["class_id"]),
        session_date=str(clean["session_date"]),
        expected_enrollment=int(clean["expected_enrollment"]),
        present_count=int(clean["present_count"]),
        absent_count=int(clean["absent_count"]),
        webcam_status=clean["webcam_status"],
        webcam_count=int(clean["webcam_count"]) if clean["webcam_count"] is not None else None,
        record_source=clean["record_source"],
        created_at=str(clean["created_at"]),
    )

    if not run_detection:
        repo.save_session(session)
        return session, []

    # Retrieve historical cohort sessions for anomaly baseline evaluation
    history_df = repo.get_sessions(class_id=session.class_id, as_df=True)
    session_row_df = pd.DataFrame([asdict(session)])

    if history_df.empty:
        combined_df = session_row_df
    else:
        combined_df = pd.concat([history_df, session_row_df], ignore_index=True)

    # Run detection pipeline across cohort timeline
    all_alerts = detect_anomalies(combined_df)

    # Filter alerts strictly to those triggered on the newly submitted session
    session_alerts = [a for a in all_alerts if a.session_id == session.session_id]

    # Save session and alerts atomically in a single combined transaction
    repo.save_session_batch_with_alerts([session], session_alerts)

    return session, session_alerts


def run_full_detection_pipeline(
    repo: AttendanceRepository,
    class_id: Optional[str] = None,
    active_rules: Optional[list[str]] = None,
) -> list[Alert]:
    """Execute detection across stored attendance history and persist new alerts.

    Scope:
    - If class_id is provided: evaluates all historical sessions for that specific
      cohort, without cross-class leakage.
    - If class_id is None: evaluates all historical sessions in the repository across
      all cohorts.

    Persists generated alerts through repo.save_alerts(), using targeted ON CONFLICT
    safeguards to ensure existing educator review triage statuses (ACKNOWLEDGED,
    RESOLVED, DISMISSED) are preserved.

    Args:
        repo: Active AttendanceRepository instance.
        class_id: Optional classroom filter.
        active_rules: Optional list of specific rule IDs to execute (None runs all).

    Returns:
        List of generated Alert objects, sorted chronologically.
    """
    sessions_df = repo.get_sessions(class_id=class_id, as_df=True)
    if sessions_df.empty:
        return []

    alerts = detect_anomalies(sessions_df, active_rules=active_rules)
    if alerts:
        repo.save_alerts(alerts)

    return alerts


def update_alert_status(
    repo: AttendanceRepository,
    alert_id: str,
    new_status: str,
    raise_if_missing: bool = False,
) -> bool:
    """Update an alert's review status using the repository.

    Args:
        repo: Active AttendanceRepository instance.
        alert_id: Unique alert identifier.
        new_status: Target status (PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED).
        raise_if_missing: If True, raises KeyError when alert_id is not found;
            if False, returns False.

    Returns:
        True if the alert was found and updated; False if not found (when raise_if_missing=False).

    Raises:
        ValueError: If new_status is not an approved ReviewStatus value.
        KeyError: If raise_if_missing is True and alert_id does not exist.
    """
    updated = repo.update_alert_review_status(alert_id, new_status)
    if not updated and raise_if_missing:
        raise KeyError(f"Alert '{alert_id}' does not exist in storage.")
    return updated


def preview_csv_import(
    repo: AttendanceRepository,
    csv_source: Any,
    allow_partial: bool = False,
) -> Any:
    """Validate and preview sessions from CSV without writing to the database.

    Args:
        repo: Active AttendanceRepository instance for collision checks.
        csv_source: File path, CSV text string, or file-like object.
        allow_partial: If True, previews valid non-colliding rows while listing errors;
            if False, previews all-or-nothing acceptance criteria.

    Returns:
        CsvImportResult detailing total_rows, candidate sessions, and row-level errors.
    """
    from attendsure.data.csv_io import preview_sessions_from_csv

    return preview_sessions_from_csv(repo, csv_source, allow_partial=allow_partial)


def commit_csv_import(
    repo: AttendanceRepository,
    csv_source: Any,
    allow_partial: bool = False,
) -> Any:
    """Validate and persist CSV sessions to the database in an atomic transaction.

    Args:
        repo: Active AttendanceRepository instance.
        csv_source: File path, CSV text string, or file-like object.
        allow_partial: If True, persists valid rows and returns errors for bad rows;
            if False, enforces an all-or-nothing transaction.

    Returns:
        CsvImportResult detailing persisted sessions and any rejected row errors.
    """
    from attendsure.data.csv_io import import_sessions_from_csv

    return import_sessions_from_csv(repo, csv_source, allow_partial=allow_partial, dry_run=False)
