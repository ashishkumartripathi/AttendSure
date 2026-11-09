"""Unit tests for AttendSure session record validation.

Tests validate_session_dict and validate_session_dataframe against contract specifications.
"""

from copy import deepcopy
import pandas as pd
import pytest

from attendsure.data.validation import (
    validate_session_dataframe,
    validate_session_dict,
)


@pytest.fixture
def valid_manual_record() -> dict:
    """Returns a valid manual-entry session record dictionary."""
    return {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "class_id": "CLASS-05-A",
        "session_date": "2026-10-25",
        "expected_enrollment": 35,
        "present_count": 31,
        "absent_count": 4,
        "webcam_status": "NOT_ATTEMPTED",
        "webcam_count": None,
        "record_source": "MANUAL_ENTRY",
        "created_at": "2026-10-25T09:15:00Z",
    }


# =========================================================================
# 1. Valid Record Scenarios
# =========================================================================


def test_valid_manual_entry_session(valid_manual_record):
    """Confirm a valid manual roll-call session passes validation cleanly."""
    result = validate_session_dict(valid_manual_record)
    assert result.is_valid is True
    assert result.errors == []
    assert result.cleaned_record is not None
    assert result.cleaned_record["session_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result.cleaned_record["present_count"] == 31
    assert result.cleaned_record["absent_count"] == 4


def test_valid_synthetic_session(valid_manual_record):
    """Confirm a valid synthetic record passes validation."""
    record = deepcopy(valid_manual_record)
    record["session_id"] = "a1b2c3d4-e5f6-4a1b-9c2d-3e4f5a6b7c8d"
    record["record_source"] = "SYNTHETIC"
    record["class_id"] = "GRADE-03-B"

    result = validate_session_dict(record)
    assert result.is_valid is True
    assert result.errors == []
    assert result.cleaned_record["record_source"] == "SYNTHETIC"


def test_valid_webcam_session(valid_manual_record):
    """Confirm a valid session with successful webcam count passes validation."""
    record = deepcopy(valid_manual_record)
    record["webcam_status"] = "SUCCESS"
    record["webcam_count"] = 30

    result = validate_session_dict(record)
    assert result.is_valid is True
    assert result.errors == []
    assert result.cleaned_record["webcam_status"] == "SUCCESS"
    assert result.cleaned_record["webcam_count"] == 30


def test_valid_hardware_fallback_states(valid_manual_record):
    """Confirm CAMERA_UNAVAILABLE and DETECTION_FAILED pass when webcam_count is null."""
    for fallback_status in ("CAMERA_UNAVAILABLE", "DETECTION_FAILED"):
        record = deepcopy(valid_manual_record)
        record["webcam_status"] = fallback_status
        record["webcam_count"] = None

        result = validate_session_dict(record)
        assert result.is_valid is True, f"Failed for {fallback_status}: {result.errors}"
        assert result.cleaned_record["webcam_status"] == fallback_status
        assert result.cleaned_record["webcam_count"] is None


def test_valid_boundary_counts(valid_manual_record):
    """Confirm boundary counts (0 present, 100% present) are valid."""
    # Zero present
    record_zero = deepcopy(valid_manual_record)
    record_zero["present_count"] = 0
    record_zero["absent_count"] = 35
    result_zero = validate_session_dict(record_zero)
    assert result_zero.is_valid is True

    # 100% present
    record_full = deepcopy(valid_manual_record)
    record_full["present_count"] = 35
    record_full["absent_count"] = 0
    result_full = validate_session_dict(record_full)
    assert result_full.is_valid is True


# =========================================================================
# 2. Invalid Record Scenarios
# =========================================================================


def test_invalid_uuid(valid_manual_record):
    """Confirm non-UUIDv4 and malformed identifiers are rejected."""
    # Malformed string
    rec1 = deepcopy(valid_manual_record)
    rec1["session_id"] = "not-a-uuid"
    assert validate_session_dict(rec1).is_valid is False

    # UUIDv1 (timestamp based, version != 4)
    rec2 = deepcopy(valid_manual_record)
    rec2["session_id"] = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    res2 = validate_session_dict(rec2)
    assert res2.is_valid is False
    assert any("version 4" in err or "UUIDv4" in err for err in res2.errors)


def test_missing_required_fields(valid_manual_record):
    """Confirm missing required fields are explicitly flagged."""
    required = (
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
    for field in required:
        rec = deepcopy(valid_manual_record)
        del rec[field]
        result = validate_session_dict(rec)
        assert result.is_valid is False
        assert any(field in err for err in result.errors)


def test_invalid_dates(valid_manual_record):
    """Confirm malformed, non-existent, and future dates are rejected."""
    # Bad format
    rec_bad_fmt = deepcopy(valid_manual_record)
    rec_bad_fmt["session_date"] = "25-10-2026"
    assert validate_session_dict(rec_bad_fmt).is_valid is False

    # Impossible calendar date
    rec_leap = deepcopy(valid_manual_record)
    rec_leap["session_date"] = "2026-02-31"
    assert validate_session_dict(rec_leap).is_valid is False

    # Future date
    rec_future = deepcopy(valid_manual_record)
    rec_future["session_date"] = "2099-01-01"
    res_future = validate_session_dict(rec_future)
    assert res_future.is_valid is False
    assert any("future" in err for err in res_future.errors)


def test_zero_or_negative_enrollment(valid_manual_record):
    """Confirm zero or negative enrollment is rejected."""
    for bad_enrollment in (0, -1, -50):
        rec = deepcopy(valid_manual_record)
        rec["expected_enrollment"] = bad_enrollment
        result = validate_session_dict(rec)
        assert result.is_valid is False
        assert any("expected_enrollment" in err for err in result.errors)


def test_negative_counts(valid_manual_record):
    """Confirm negative present or absent counts are rejected."""
    # Negative present
    rec_neg_present = deepcopy(valid_manual_record)
    rec_neg_present["present_count"] = -5
    assert validate_session_dict(rec_neg_present).is_valid is False

    # Negative absent
    rec_neg_absent = deepcopy(valid_manual_record)
    rec_neg_absent["absent_count"] = -2
    assert validate_session_dict(rec_neg_absent).is_valid is False


def test_count_mismatch_invariant(valid_manual_record):
    """Confirm present + absent != enrollment is strictly rejected."""
    rec = deepcopy(valid_manual_record)
    rec["expected_enrollment"] = 35
    rec["present_count"] = 30
    rec["absent_count"] = 10  # sum = 40 != 35

    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("mismatch" in err.lower() or "present_count + absent_count" in err for err in result.errors)


def test_count_exceeding_enrollment(valid_manual_record):
    """Confirm present_count > expected_enrollment is rejected."""
    rec = deepcopy(valid_manual_record)
    rec["expected_enrollment"] = 30
    rec["present_count"] = 35
    rec["absent_count"] = 0

    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("cannot exceed" in err for err in result.errors)


def test_invalid_record_source(valid_manual_record):
    """Confirm unsupported record_source is rejected."""
    rec = deepcopy(valid_manual_record)
    rec["record_source"] = "PORTAL_SYNC"
    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("record_source" in err for err in result.errors)


def test_invalid_webcam_status(valid_manual_record):
    """Confirm invalid webcam_status is rejected."""
    rec = deepcopy(valid_manual_record)
    rec["webcam_status"] = "PENDING_CAPTURE"
    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("webcam_status" in err for err in result.errors)


def test_webcam_success_missing_count(valid_manual_record):
    """Confirm webcam_status == SUCCESS requires non-null webcam_count."""
    rec = deepcopy(valid_manual_record)
    rec["webcam_status"] = "SUCCESS"
    rec["webcam_count"] = None
    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("webcam_count must be provided" in err for err in result.errors)


def test_webcam_non_success_with_count(valid_manual_record):
    """Confirm webcam_status != SUCCESS rejects a non-null webcam_count."""
    rec = deepcopy(valid_manual_record)
    rec["webcam_status"] = "CAMERA_UNAVAILABLE"
    rec["webcam_count"] = 28
    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("must be null/None" in err for err in result.errors)


def test_webcam_negative_count(valid_manual_record):
    """Confirm negative webcam_count is rejected even when status is SUCCESS."""
    rec = deepcopy(valid_manual_record)
    rec["webcam_status"] = "SUCCESS"
    rec["webcam_count"] = -5
    result = validate_session_dict(rec)
    assert result.is_valid is False
    assert any("cannot be negative" in err for err in result.errors)


def test_invalid_or_non_utc_created_at(valid_manual_record):
    """Confirm non-UTC, timezone-naive, and malformed timestamps are rejected."""
    # Naive timestamp (no timezone)
    rec_naive = deepcopy(valid_manual_record)
    rec_naive["created_at"] = "2026-10-25T09:15:00"
    assert validate_session_dict(rec_naive).is_valid is False

    # Non-UTC offset (+05:30)
    rec_offset = deepcopy(valid_manual_record)
    rec_offset["created_at"] = "2026-10-25T09:15:00+05:30"
    assert validate_session_dict(rec_offset).is_valid is False

    # Plain date or garbage
    rec_bad = deepcopy(valid_manual_record)
    rec_bad["created_at"] = "invalid-date"
    assert validate_session_dict(rec_bad).is_valid is False


# =========================================================================
# 3. Type Safety, Regression & Non-Mutation
# =========================================================================


def test_booleans_rejected_as_integers(valid_manual_record):
    """Ensure boolean True/False are not accepted as integer counts."""
    # present_count = True
    rec_bool_present = deepcopy(valid_manual_record)
    rec_bool_present["present_count"] = True
    res1 = validate_session_dict(rec_bool_present)
    assert res1.is_valid is False
    assert any("present_count" in err for err in res1.errors)

    # absent_count = False
    rec_bool_absent = deepcopy(valid_manual_record)
    rec_bool_absent["absent_count"] = False
    res2 = validate_session_dict(rec_bool_absent)
    assert res2.is_valid is False
    assert any("absent_count" in err for err in res2.errors)

    # expected_enrollment = True
    rec_bool_enrollment = deepcopy(valid_manual_record)
    rec_bool_enrollment["expected_enrollment"] = True
    res3 = validate_session_dict(rec_bool_enrollment)
    assert res3.is_valid is False
    assert any("expected_enrollment" in err for err in res3.errors)


def test_unhandled_exception_safety():
    """Ensure invalid top-level inputs return ValidationResult instead of raising."""
    for bad_input in (None, "string", [1, 2, 3], 123):
        result = validate_session_dict(bad_input)  # type: ignore[arg-type]
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert result.cleaned_record is None


def test_validation_does_not_mutate_input(valid_manual_record):
    """Confirm validating a record never mutates the original dictionary."""
    original_copy = deepcopy(valid_manual_record)
    result = validate_session_dict(valid_manual_record)

    assert result.is_valid is True
    assert valid_manual_record == original_copy


# =========================================================================
# 4. DataFrame Batch Validation
# =========================================================================


def test_validate_session_dataframe_success(valid_manual_record):
    """Confirm batch DataFrame validation with unique valid records."""
    rec1 = deepcopy(valid_manual_record)
    rec1["session_id"] = "550e8400-e29b-41d4-a716-446655440001"
    rec1["session_date"] = "2026-10-24"

    rec2 = deepcopy(valid_manual_record)
    rec2["session_id"] = "550e8400-e29b-41d4-a716-446655440002"
    rec2["session_date"] = "2026-10-25"

    df = pd.DataFrame([rec1, rec2])
    valid_df, rejected_df = validate_session_dataframe(df)

    assert len(valid_df) == 2
    assert len(rejected_df) == 0


def test_validate_session_dataframe_duplicate_session_id(valid_manual_record):
    """Confirm batch validation rejects duplicate session_id values."""
    rec1 = deepcopy(valid_manual_record)
    rec1["session_date"] = "2026-10-24"

    rec2 = deepcopy(valid_manual_record)
    rec2["session_date"] = "2026-10-25"
    # rec2 reuses same session_id as rec1

    df = pd.DataFrame([rec1, rec2])
    valid_df, rejected_df = validate_session_dataframe(df)

    assert len(valid_df) == 0
    assert len(rejected_df) == 2
    for errs in rejected_df["validation_errors"]:
        assert any("Duplicate session_id" in err for err in errs)


def test_validate_session_dataframe_duplicate_class_date(valid_manual_record):
    """Confirm batch validation rejects duplicate (class_id, session_date) pairs."""
    rec1 = deepcopy(valid_manual_record)
    rec1["session_id"] = "550e8400-e29b-41d4-a716-446655440001"
    rec1["class_id"] = "CLASS-05-A"
    rec1["session_date"] = "2026-10-25"

    rec2 = deepcopy(valid_manual_record)
    rec2["session_id"] = "550e8400-e29b-41d4-a716-446655440002"
    rec2["class_id"] = "CLASS-05-A"
    rec2["session_date"] = "2026-10-25"  # duplicate cohort on same date

    df = pd.DataFrame([rec1, rec2])
    valid_df, rejected_df = validate_session_dataframe(df)

    assert len(valid_df) == 0
    assert len(rejected_df) == 2
    for errs in rejected_df["validation_errors"]:
        assert any("Duplicate (class_id, session_date)" in err for err in errs)


def test_validate_session_dataframe_empty():
    """Confirm empty DataFrame handles cleanly without error."""
    empty_df = pd.DataFrame()
    valid_df, rejected_df = validate_session_dataframe(empty_df)
    assert len(valid_df) == 0
    assert len(rejected_df) == 0


# =========================================================================
# 5. Focused Edge-Case & Boundary Coverage
# =========================================================================


def test_valid_csv_import_session(valid_manual_record):
    """Confirm CSV_IMPORT record_source is accepted as valid."""
    rec = deepcopy(valid_manual_record)
    rec["session_id"] = "b2c3d4e5-f6a7-4b2c-8d3e-4f5a6b7c8d9e"
    rec["record_source"] = "CSV_IMPORT"

    result = validate_session_dict(rec)
    assert result.is_valid is True
    assert result.cleaned_record["record_source"] == "CSV_IMPORT"


def test_class_id_valid_length_boundaries(valid_manual_record):
    """Confirm class_id at minimum (2 chars) and maximum (32 chars) boundary lengths pass."""
    # Length 2 (minimum valid length)
    for min_cid in ("C1", "01", "A_", "B-"):
        rec_min = deepcopy(valid_manual_record)
        rec_min["class_id"] = min_cid
        result_min = validate_session_dict(rec_min)
        assert result_min.is_valid is True, f"Failed for valid length-2 class_id: {min_cid}"
        assert result_min.cleaned_record["class_id"] == min_cid

    # Length 32 (maximum valid length)
    max_cid = "CLASS-GRADE-05-ROOM-102-SEC-A-01"
    assert len(max_cid) == 32
    rec_max = deepcopy(valid_manual_record)
    rec_max["class_id"] = max_cid
    result_max = validate_session_dict(rec_max)
    assert result_max.is_valid is True, f"Failed for valid length-32 class_id: {max_cid}"
    assert result_max.cleaned_record["class_id"] == max_cid


def test_class_id_invalid_formats_and_spaces(valid_manual_record):
    """Confirm class_id values with spaces, invalid lengths, or illegal characters are rejected."""
    invalid_class_ids = (
        "A",  # Too short (1 char < 2)
        "A" * 33,  # Too long (33 chars > 32)
        " CLASS-05-A",  # Leading space (must not be silently stripped)
        "CLASS-05-A ",  # Trailing space
        "CLASS 05 A",  # Internal spaces
        "CLASS@05",  # Unsupported symbol @
        "CLASS.05",  # Unsupported symbol .
        "CLASS#05",  # Unsupported symbol #
        "CLASS/05",  # Unsupported symbol /
        "",  # Empty string
    )
    for bad_cid in invalid_class_ids:
        rec = deepcopy(valid_manual_record)
        rec["class_id"] = bad_cid
        result = validate_session_dict(rec)
        assert result.is_valid is False, f"Expected invalid for class_id='{bad_cid}'"
        assert any("class_id" in err for err in result.errors)


def test_non_string_identifiers_safety(valid_manual_record):
    """Ensure non-string types for session_id and class_id fail validation gracefully."""
    # session_id non-string
    for bad_sid in (12345, True, False, ["uuid-list"], {"id": 1}):
        rec = deepcopy(valid_manual_record)
        rec["session_id"] = bad_sid
        res = validate_session_dict(rec)
        assert res.is_valid is False
        assert any("session_id" in err for err in res.errors)

    # class_id non-string
    for bad_cid in (501, True, False, ["class-list"], {"name": "class"}):
        rec = deepcopy(valid_manual_record)
        rec["class_id"] = bad_cid
        res = validate_session_dict(rec)
        assert res.is_valid is False
        assert any("class_id" in err for err in res.errors)


def test_enrollment_boundary_according_to_contract(valid_manual_record):
    """Confirm enrollment boundary behavior strictly adheres to contract rules."""
    # Minimum valid positive enrollment: expected_enrollment = 1
    rec_min_1 = deepcopy(valid_manual_record)
    rec_min_1["expected_enrollment"] = 1
    rec_min_1["present_count"] = 1
    rec_min_1["absent_count"] = 0
    assert validate_session_dict(rec_min_1).is_valid is True

    rec_min_2 = deepcopy(valid_manual_record)
    rec_min_2["expected_enrollment"] = 1
    rec_min_2["present_count"] = 0
    rec_min_2["absent_count"] = 1
    assert validate_session_dict(rec_min_2).is_valid is True

    # Large enrollment (e.g. combined school auditorium assembly > 150):
    # Contract does not designate 150 as a hard rejection rule; any enrollment >= 1 is valid.
    rec_large = deepcopy(valid_manual_record)
    rec_large["expected_enrollment"] = 200
    rec_large["present_count"] = 180
    rec_large["absent_count"] = 20
    result_large = validate_session_dict(rec_large)
    assert result_large.is_valid is True
    assert result_large.cleaned_record["expected_enrollment"] == 200

