"""Session record data validation logic for AttendSure.

Implements the contract validation rules defined in docs/data-contract.md.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any
import uuid

import pandas as pd

from attendsure.data.models import (
    RecordSource,
    SessionRecord,
    ValidationResult,
    WebcamStatus,
)

# -------------------------------------------------------------------------
# Validation Constants and Allowed Sets
# -------------------------------------------------------------------------

UUIDV4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
CLASS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

VALID_WEBCAM_STATUSES = {
    "SUCCESS",
    "NOT_ATTEMPTED",
    "CAMERA_UNAVAILABLE",
    "DETECTION_FAILED",
}
VALID_RECORD_SOURCES = {"SYNTHETIC", "MANUAL_ENTRY", "CSV_IMPORT"}

REQUIRED_FIELDS = (
    "session_id",
    "class_id",
    "session_date",
    "expected_enrollment",
    "present_count",
    "absent_count",
    "webcam_status",
    "record_source",
    "created_at",
)


def _is_valid_int(val: Any) -> bool:
    """Return True if val is a standard Python int and not a boolean."""
    return isinstance(val, int) and not isinstance(val, bool)


def _is_valid_iso_utc_timestamp(val: Any) -> bool:
    """Validate that val is a valid ISO 8601 UTC timestamp string without extraneous whitespace."""
    if not isinstance(val, str) or not val:
        return False
    # Strict ISO 8601 UTC string must not contain leading or trailing whitespace
    if val != val.strip():
        return False
    # Must explicitly indicate UTC offset (Z, +00:00, or -00:00)
    if not (val.endswith("Z") or val.endswith("+00:00") or val.endswith("-00:00")):
        return False
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return False
        return dt.utcoffset() == timedelta(0)
    except (ValueError, TypeError):
        return False


def validate_session_dict(record_data: dict) -> ValidationResult:
    """Validates a single session dictionary against the contract schema.

    This function never mutates the input record_data dictionary.
    """
    if not isinstance(record_data, dict):
        return ValidationResult(
            is_valid=False,
            errors=["Input record must be a dictionary."],
            cleaned_record=None,
        )

    errors: list[str] = []

    # 1. Required Fields Check
    for field in REQUIRED_FIELDS:
        if field not in record_data or record_data[field] is None:
            errors.append(f"Missing required field: '{field}'.")

    # 2. session_id (RFC 4122 UUIDv4)
    session_id = record_data.get("session_id")
    if session_id is not None:
        if not isinstance(session_id, str):
            errors.append(f"session_id must be a string, got {type(session_id).__name__}.")
        elif not UUIDV4_PATTERN.match(session_id):
            errors.append(
                f"session_id '{session_id}' must be a valid RFC 4122 UUIDv4 string."
            )
        else:
            try:
                parsed_u = uuid.UUID(session_id)
                if parsed_u.version != 4:
                    errors.append(f"session_id '{session_id}' must be a version 4 UUID.")
            except (ValueError, AttributeError):
                errors.append(
                    f"session_id '{session_id}' could not be parsed as a valid UUID."
                )

    # 3. class_id
    class_id = record_data.get("class_id")
    if class_id is not None:
        if not isinstance(class_id, str):
            errors.append(f"class_id must be a string, got {type(class_id).__name__}.")
        elif not CLASS_ID_PATTERN.match(class_id):
            errors.append(
                f"class_id '{class_id}' must be an alphanumeric identifier between 2 and 32 characters (pattern: ^[A-Za-z0-9_-]{{2,32}}$)."
            )

    # 4. session_date
    session_date = record_data.get("session_date")
    parsed_date = None
    if session_date is not None:
        if not isinstance(session_date, str):
            errors.append(f"session_date must be a string, got {type(session_date).__name__}.")
        elif not DATE_PATTERN.match(session_date):
            errors.append(
                f"session_date '{session_date}' must follow ISO 8601 calendar format YYYY-MM-DD."
            )
        else:
            try:
                parsed_date = datetime.strptime(session_date, "%Y-%m-%d").date()
                # Must not be in the future relative to system date
                max_today = max(datetime.now(timezone.utc).date(), datetime.now().date())
                if parsed_date > max_today:
                    errors.append(
                        f"session_date '{session_date}' cannot be in the future relative to system date '{max_today}'."
                    )
            except ValueError:
                errors.append(f"session_date '{session_date}' is not a valid calendar date.")

    # 5. Counts: expected_enrollment, present_count, absent_count
    enrollment = record_data.get("expected_enrollment")
    present = record_data.get("present_count")
    absent = record_data.get("absent_count")

    valid_enrollment = False
    if enrollment is not None:
        if not _is_valid_int(enrollment):
            errors.append(
                f"expected_enrollment must be an integer, got {type(enrollment).__name__}."
            )
        elif enrollment <= 0:
            errors.append(f"expected_enrollment must be greater than zero, got {enrollment}.")
        else:
            valid_enrollment = True

    valid_present = False
    if present is not None:
        if not _is_valid_int(present):
            errors.append(f"present_count must be an integer, got {type(present).__name__}.")
        elif present < 0:
            errors.append(f"present_count cannot be negative, got {present}.")
        elif valid_enrollment and present > enrollment:
            errors.append(
                f"present_count ({present}) cannot exceed expected_enrollment ({enrollment})."
            )
        else:
            valid_present = True

    valid_absent = False
    if absent is not None:
        if not _is_valid_int(absent):
            errors.append(f"absent_count must be an integer, got {type(absent).__name__}.")
        elif absent < 0:
            errors.append(f"absent_count cannot be negative, got {absent}.")
        elif valid_enrollment and absent > enrollment:
            errors.append(
                f"absent_count ({absent}) cannot exceed expected_enrollment ({enrollment})."
            )
        else:
            valid_absent = True

    # 6. Strict Count Invariant: present + absent == enrollment
    if valid_enrollment and valid_present and valid_absent:
        if present + absent != enrollment:
            errors.append(
                f"Attendance count mismatch: present_count ({present}) + absent_count ({absent}) = "
                f"{present + absent}, which does not equal expected_enrollment ({enrollment}). "
                "Attendance records must strictly satisfy present_count + absent_count == expected_enrollment."
            )

    # 7. record_source
    record_source = record_data.get("record_source")
    if record_source is not None:
        if not isinstance(record_source, str):
            errors.append(f"record_source must be a string, got {type(record_source).__name__}.")
        elif record_source not in VALID_RECORD_SOURCES:
            errors.append(
                f"Invalid record_source '{record_source}'. Allowed values are: {sorted(VALID_RECORD_SOURCES)}."
            )

    # 8. webcam_status and webcam_count nullability invariant
    webcam_status = record_data.get("webcam_status")
    webcam_count = record_data.get("webcam_count")

    if webcam_status is not None:
        if not isinstance(webcam_status, str):
            errors.append(f"webcam_status must be a string, got {type(webcam_status).__name__}.")
        elif webcam_status not in VALID_WEBCAM_STATUSES:
            errors.append(
                f"Invalid webcam_status '{webcam_status}'. Allowed values are: {sorted(VALID_WEBCAM_STATUSES)}."
            )
        else:
            if webcam_status == "SUCCESS":
                if webcam_count is None:
                    errors.append(
                        "webcam_count must be provided as a non-negative integer when webcam_status is 'SUCCESS'."
                    )
                elif not _is_valid_int(webcam_count):
                    errors.append(
                        f"webcam_count must be an integer when webcam_status is 'SUCCESS', got {type(webcam_count).__name__}."
                    )
                elif webcam_count < 0:
                    errors.append(f"webcam_count cannot be negative, got {webcam_count}.")
            else:
                if webcam_count is not None:
                    errors.append(
                        f"webcam_count must be null/None when webcam_status is '{webcam_status}', got {webcam_count}."
                    )

    # 9. created_at (ISO 8601 UTC timestamp)
    created_at = record_data.get("created_at")
    if created_at is not None:
        if not isinstance(created_at, str):
            errors.append(f"created_at must be a string, got {type(created_at).__name__}.")
        elif not _is_valid_iso_utc_timestamp(created_at):
            errors.append(
                f"created_at '{created_at}' must be a valid ISO 8601 UTC timestamp (e.g., 'YYYY-MM-DDTHH:MM:SSZ' or '+00:00')."
            )

    if errors:
        return ValidationResult(is_valid=False, errors=errors, cleaned_record=None)

    # Build standardized cleaned record
    cleaned_record = {
        "session_id": str(session_id),
        "class_id": str(class_id),
        "session_date": str(session_date),
        "expected_enrollment": int(enrollment),
        "present_count": int(present),
        "absent_count": int(absent),
        "webcam_status": str(webcam_status),
        "webcam_count": int(webcam_count) if webcam_count is not None else None,
        "record_source": str(record_source),
        "created_at": str(created_at),
    }

    # Verify model instantiability
    try:
        _ = SessionRecord(
            session_id=cleaned_record["session_id"],
            class_id=cleaned_record["class_id"],
            session_date=cleaned_record["session_date"],
            expected_enrollment=cleaned_record["expected_enrollment"],
            present_count=cleaned_record["present_count"],
            absent_count=cleaned_record["absent_count"],
            webcam_status=cleaned_record["webcam_status"],  # type: ignore[arg-type]
            webcam_count=cleaned_record["webcam_count"],
            record_source=cleaned_record["record_source"],  # type: ignore[arg-type]
            created_at=cleaned_record["created_at"],
        )
    except Exception as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Failed to instantiate SessionRecord: {exc}"],
            cleaned_record=None,
        )

    return ValidationResult(is_valid=True, errors=[], cleaned_record=cleaned_record)


def validate_session_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validates a batch DataFrame of sessions.

    Enforces record-level validation rules as well as batch-level uniqueness:
    - Unique session_id within the batch.
    - Unique (class_id, session_date) pair within the batch.

    Returns:
        (valid_df, rejected_df_with_errors)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}.")

    if df.empty:
        empty_valid = pd.DataFrame(
            columns=[
                "session_id",
                "class_id",
                "session_date",
                "expected_enrollment",
                "present_count",
                "absent_count",
                "webcam_status",
                "webcam_count",
                "record_source",
                "created_at",
            ]
        )
        empty_rejected = df.copy()
        empty_rejected["validation_errors"] = []
        return empty_valid, empty_rejected

    # Identify duplicate session_id values across batch
    dup_session_ids = set()
    if "session_id" in df.columns:
        s_ids = df["session_id"].dropna().astype(str)
        dup_session_ids = set(s_ids[s_ids.duplicated()].unique())

    # Identify duplicate (class_id, session_date) pairs across batch
    dup_class_date_pairs = set()
    if "class_id" in df.columns and "session_date" in df.columns:
        pairs = df[["class_id", "session_date"]].dropna()
        dup_mask = pairs.duplicated(subset=["class_id", "session_date"], keep=False)
        for _, r in pairs[dup_mask].iterrows():
            dup_class_date_pairs.add((str(r["class_id"]), str(r["session_date"])))

    valid_rows = []
    rejected_rows = []

    for _, row in df.iterrows():
        # Clean row into standard dictionary, converting NaN/NaT to None
        row_dict: dict[str, Any] = {}
        for k, v in row.items():
            if pd.isna(v):
                row_dict[k] = None
            else:
                row_dict[k] = v

        result = validate_session_dict(row_dict)
        row_errors = list(result.errors)

        # Batch-level uniqueness checks
        s_id = row_dict.get("session_id")
        if s_id is not None and str(s_id) in dup_session_ids:
            row_errors.append(f"Duplicate session_id '{s_id}' found in validation batch.")

        c_id = row_dict.get("class_id")
        s_date = row_dict.get("session_date")
        if c_id is not None and s_date is not None and (str(c_id), str(s_date)) in dup_class_date_pairs:
            row_errors.append(
                f"Duplicate (class_id, session_date) pair ('{c_id}', '{s_date}') found in validation batch."
            )

        if not row_errors and result.cleaned_record is not None:
            valid_rows.append(result.cleaned_record)
        else:
            rej_dict = dict(row_dict)
            rej_dict["validation_errors"] = row_errors
            rejected_rows.append(rej_dict)

    valid_df = (
        pd.DataFrame(valid_rows)
        if valid_rows
        else pd.DataFrame(
            columns=[
                "session_id",
                "class_id",
                "session_date",
                "expected_enrollment",
                "present_count",
                "absent_count",
                "webcam_status",
                "webcam_count",
                "record_source",
                "created_at",
            ]
        )
    )

    rejected_df = (
        pd.DataFrame(rejected_rows)
        if rejected_rows
        else pd.DataFrame(
            columns=list(df.columns)
            + (["validation_errors"] if "validation_errors" not in df.columns else [])
        )
    )

    return valid_df, rejected_df
