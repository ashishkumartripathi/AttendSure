"""Unit and integration tests for AttendSure simulated visible-person webcam counter.

Tests all behaviors specified in AttendSure Milestone M5.2.2, docs/data-contract.md
Section 3.2, Section 5.3, Section 7, and Decision D10:
- Successful simulated counts (valid int >= 0, confidence in [0, 1]).
- Non-success results and null-count invariants (estimated_count is None).
- Discrepancy above and below approved thresholds.
- Zero manual attendance behavior without division by zero.
- Integration with the existing discrepancy detector (RULE_WEBCAM_DISCREPANCY).
- Preservation and immutability of manually recorded attendance.
- Deterministic behavior across repeated calls.
- Input validation and contract error handling.
"""

from copy import deepcopy
import pandas as pd
import pytest

from attendsure.data import (
    WebcamCounterResult,
    get_simulated_webcam_count,
    validate_session_dict,
)
from attendsure.detection import (
    DEFAULT_WEBCAM_ABS_THRESHOLD,
    DEFAULT_WEBCAM_REL_THRESHOLD_PCT,
    RULE_WEBCAM_DISCREPANCY,
    detect_anomalies,
    detect_webcam_discrepancy,
)


def _make_eval_session(
    class_id: str = "CLASS-01-A",
    session_date: str = "2026-10-25",
    enrollment: int = 30,
    present: int = 25,
    session_id: str = "550e8400-e29b-41d4-a716-446655440001",
    webcam_status: str = "SUCCESS",
    webcam_count: int | None = 25,
) -> dict:
    """Helper to assemble a valid session dictionary incorporating webcam estimation."""
    return {
        "session_id": session_id,
        "class_id": class_id,
        "session_date": session_date,
        "expected_enrollment": enrollment,
        "present_count": present,
        "absent_count": enrollment - present,
        "webcam_status": webcam_status,
        "webcam_count": webcam_count,
        "record_source": "MANUAL_ENTRY",
        "created_at": f"{session_date}T09:00:00Z",
    }


# =============================================================================
# 1. Successful Simulated Count
# =============================================================================


def test_successful_simulated_count_normal():
    """Verify NORMAL mode returns SUCCESS status, non-negative integer count, and valid confidence."""
    res = get_simulated_webcam_count(mode="NORMAL", reference_present=28)

    assert isinstance(res, WebcamCounterResult)
    assert res.status == "SUCCESS"
    assert isinstance(res.estimated_count, int)
    assert res.estimated_count >= 0
    assert res.estimated_count == 28
    assert isinstance(res.confidence_score, float)
    assert 0.0 <= res.confidence_score <= 1.0
    assert len(res.diagnostic_message) > 0


def test_successful_simulated_count_case_insensitive():
    """Verify mode string matching is case-insensitive and trims whitespace."""
    res1 = get_simulated_webcam_count(mode="normal", reference_present=20)
    res2 = get_simulated_webcam_count(mode="  Normal  ", reference_present=20)

    assert res1.status == "SUCCESS"
    assert res1.estimated_count == 20
    assert res2.status == "SUCCESS"
    assert res2.estimated_count == 20


# =============================================================================
# 2. Non-Success Results and Null-Count Invariants
# =============================================================================


@pytest.mark.parametrize(
    "mode,expected_status",
    [
        ("CAMERA_OFFLINE", "CAMERA_UNAVAILABLE"),
        ("CAMERA_UNAVAILABLE", "CAMERA_UNAVAILABLE"),
        ("DETECTION_FAILED", "DETECTION_FAILED"),
        ("NOT_ATTEMPTED", "NOT_ATTEMPTED"),
    ],
)
def test_non_success_results_and_null_count_invariants(mode, expected_status):
    """Verify that every non-success result enforces estimated_count is None and confidence is None."""
    res = get_simulated_webcam_count(mode=mode, reference_present=30)

    assert isinstance(res, WebcamCounterResult)
    assert res.status == expected_status
    # Contract Invariant: webcam_status != 'SUCCESS' => webcam_count is None
    assert res.estimated_count is None
    assert res.confidence_score is None
    assert "Manual attendance remains valid" in res.diagnostic_message


# =============================================================================
# 3. Discrepancy Below and Above Approved Thresholds
# =============================================================================


def test_discrepancy_above_approved_thresholds_triggers_alert():
    """Verify DISCREPANCY mode generates count exceeding both abs_diff >= 5 and rel_diff >= 20%."""
    ref_present = 30
    res = get_simulated_webcam_count(mode="DISCREPANCY", reference_present=ref_present)

    assert res.status == "SUCCESS"
    assert isinstance(res.estimated_count, int)

    abs_diff = abs(res.estimated_count - ref_present)
    rel_diff = (abs_diff / ref_present) * 100.0

    assert abs_diff >= DEFAULT_WEBCAM_ABS_THRESHOLD
    assert rel_diff >= DEFAULT_WEBCAM_REL_THRESHOLD_PCT

    # Integration with detector: must trigger RULE_WEBCAM_DISCREPANCY
    session = _make_eval_session(
        present=ref_present,
        webcam_status=res.status,
        webcam_count=res.estimated_count,
    )
    df = pd.DataFrame([session])
    alerts = detect_webcam_discrepancy(df)

    assert len(alerts) == 1
    assert alerts[0].rule_id == RULE_WEBCAM_DISCREPANCY
    assert alerts[0].observed_value["absolute_difference"] == abs_diff


def test_discrepancy_below_approved_thresholds_generates_no_alert():
    """Verify MINOR_DISCREPANCY mode generates count with abs_diff < 5, producing 0 alerts."""
    ref_present = 30
    res = get_simulated_webcam_count(mode="MINOR_DISCREPANCY", reference_present=ref_present)

    assert res.status == "SUCCESS"
    assert isinstance(res.estimated_count, int)

    abs_diff = abs(res.estimated_count - ref_present)
    assert abs_diff < DEFAULT_WEBCAM_ABS_THRESHOLD  # Below threshold: 2 < 5

    # Integration with detector: must NOT trigger alert
    session = _make_eval_session(
        present=ref_present,
        webcam_status=res.status,
        webcam_count=res.estimated_count,
    )
    df = pd.DataFrame([session])
    alerts = detect_webcam_discrepancy(df)

    assert len(alerts) == 0


def test_custom_delta_above_and_below_threshold():
    """Verify explicit delta parameter allows precise control of discrepancy magnitude."""
    # Delta of -3 (abs_diff = 3 < 5): Below threshold -> 0 alerts
    res_below = get_simulated_webcam_count("NORMAL", reference_present=25, delta=-3)
    assert res_below.estimated_count == 22
    df_below = pd.DataFrame(
        [_make_eval_session(present=25, webcam_count=res_below.estimated_count)]
    )
    assert len(detect_webcam_discrepancy(df_below)) == 0

    # Delta of -10 (abs_diff = 10 >= 5, rel_diff = 40% >= 20%): Above threshold -> 1 alert
    res_above = get_simulated_webcam_count("DISCREPANCY", reference_present=25, delta=-10)
    assert res_above.estimated_count == 15
    df_above = pd.DataFrame(
        [_make_eval_session(present=25, webcam_count=res_above.estimated_count)]
    )
    alerts_above = detect_webcam_discrepancy(df_above)
    assert len(alerts_above) == 1
    assert alerts_above[0].observed_value["absolute_difference"] == 10


def test_custom_delta_valid_integer_cases_and_clamping():
    """Verify valid positive, zero, and negative integer deltas clamp to non-negative int."""
    # Positive integer delta
    res_pos = get_simulated_webcam_count("NORMAL", reference_present=25, delta=5)
    assert res_pos.status == "SUCCESS"
    assert res_pos.estimated_count == 30
    assert isinstance(res_pos.estimated_count, int)
    assert not isinstance(res_pos.estimated_count, bool)

    # Zero integer delta
    res_zero = get_simulated_webcam_count("NORMAL", reference_present=25, delta=0)
    assert res_zero.status == "SUCCESS"
    assert res_zero.estimated_count == 25
    assert isinstance(res_zero.estimated_count, int)

    # Negative integer delta within bounds
    res_neg = get_simulated_webcam_count("NORMAL", reference_present=25, delta=-5)
    assert res_neg.status == "SUCCESS"
    assert res_neg.estimated_count == 20
    assert isinstance(res_neg.estimated_count, int)

    # Negative delta exceeding present count clamps to 0
    res_clamped = get_simulated_webcam_count("NORMAL", reference_present=25, delta=-50)
    assert res_clamped.status == "SUCCESS"
    assert res_clamped.estimated_count == 0
    assert isinstance(res_clamped.estimated_count, int)

    # Verify every successful mode returns int, never float
    for mode in ("NORMAL", "DISCREPANCY", "MINOR_DISCREPANCY", "BELOW_THRESHOLD"):
        for ref in (0, 1, 15, 30):
            r = get_simulated_webcam_count(mode, reference_present=ref)
            assert r.status == "SUCCESS"
            assert isinstance(r.estimated_count, int)
            assert not isinstance(r.estimated_count, (float, bool))
            assert r.estimated_count >= 0


# =============================================================================
# 4. Zero Manual Attendance Behavior
# =============================================================================


def test_zero_manual_attendance_normal_mode():
    """Verify reference_present = 0 in NORMAL mode yields 0 count and triggers no alerts."""
    res = get_simulated_webcam_count("NORMAL", reference_present=0)

    assert res.status == "SUCCESS"
    assert res.estimated_count == 0

    session = _make_eval_session(enrollment=20, present=0, webcam_count=0)
    df = pd.DataFrame([session])
    alerts = detect_webcam_discrepancy(df)

    assert len(alerts) == 0


def test_zero_manual_attendance_discrepancy_mode():
    """Verify reference_present = 0 in DISCREPANCY mode yields count >= 5 and triggers alert without ZeroDivisionError."""
    res = get_simulated_webcam_count("DISCREPANCY", reference_present=0)

    assert res.status == "SUCCESS"
    assert res.estimated_count == 6  # Exceeds absolute threshold 5
    assert abs(res.estimated_count - 0) >= DEFAULT_WEBCAM_ABS_THRESHOLD

    session = _make_eval_session(
        enrollment=20,
        present=0,
        webcam_status=res.status,
        webcam_count=res.estimated_count,
    )
    df = pd.DataFrame([session])
    alerts = detect_webcam_discrepancy(df)

    assert len(alerts) == 1
    assert alerts[0].rule_id == RULE_WEBCAM_DISCREPANCY
    assert alerts[0].observed_value["present_count"] == 0
    assert alerts[0].observed_value["webcam_count"] == 6
    assert alerts[0].observed_value["relative_difference_pct"] is None
    assert "relative difference undefined" in alerts[0].explanation


def test_zero_manual_attendance_below_threshold():
    """Verify reference_present = 0 with camera count 4 (abs_diff < 5) generates no alert."""
    res = get_simulated_webcam_count("NORMAL", reference_present=0, delta=4)
    assert res.estimated_count == 4

    session = _make_eval_session(enrollment=20, present=0, webcam_count=4)
    df = pd.DataFrame([session])
    alerts = detect_webcam_discrepancy(df)

    assert len(alerts) == 0


# =============================================================================
# 5. Integration with Existing Detector and Contract Schema
# =============================================================================


def test_integration_with_detect_anomalies_pipeline():
    """Verify simulated webcam output integrates seamlessly into full detection pipeline."""
    res = get_simulated_webcam_count("DISCREPANCY", reference_present=25)

    session = _make_eval_session(
        class_id="CLASS-03-A",
        session_date="2026-10-25",
        enrollment=30,
        present=25,
        webcam_status=res.status,
        webcam_count=res.estimated_count,
    )
    df = pd.DataFrame([session])

    # Run full detection pipeline with all rules active
    alerts = detect_anomalies(df)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == RULE_WEBCAM_DISCREPANCY
    assert alert.priority == "REVIEW_REQUIRED"
    assert alert.class_id == "CLASS-03-A"
    assert alert.session_date == "2026-10-25"
    assert alert.review_status == "PENDING_REVIEW"
    # Explainability: Decision support, never accusation
    assert "Discrepancies may arise naturally from camera placement" in alert.explanation
    assert "fraud" not in alert.explanation.lower()
    assert "cheating" not in alert.explanation.lower()


def test_non_success_webcam_modes_produce_valid_contract_records_without_alerts():
    """Verify non-success webcam outputs validate against data contract and generate 0 alerts."""
    for mode in ("CAMERA_OFFLINE", "DETECTION_FAILED", "NOT_ATTEMPTED"):
        res = get_simulated_webcam_count(mode=mode, reference_present=25)

        session = _make_eval_session(
            present=25,
            webcam_status=res.status,
            webcam_count=res.estimated_count,
        )

        # 1. Validates against contract schema
        val_res = validate_session_dict(session)
        assert val_res.is_valid is True, f"Failed for {mode}: {val_res.errors}"

        # 2. Pipeline generates 0 discrepancy alerts
        df = pd.DataFrame([session])
        alerts = detect_anomalies(df, active_rules=[RULE_WEBCAM_DISCREPANCY])
        assert len(alerts) == 0, f"Unexpected alert for mode {mode}"


# =============================================================================
# 6. No Mutation of Manually Recorded Attendance
# =============================================================================


def test_manual_attendance_immutability():
    """Verify simulated webcam helper never mutates caller input dictionary or manual attendance."""
    manual_data = {
        "session_id": "550e8400-e29b-41d4-a716-446655440001",
        "class_id": "CLASS-01-A",
        "session_date": "2026-10-25",
        "expected_enrollment": 35,
        "present_count": 31,
        "absent_count": 4,
        "record_source": "MANUAL_ENTRY",
    }
    snapshot = deepcopy(manual_data)

    res = get_simulated_webcam_count(
        mode="DISCREPANCY",
        reference_present=manual_data["present_count"],
    )

    # Caller dictionary remains strictly unmodified
    assert manual_data == snapshot
    assert manual_data["present_count"] == 31
    assert manual_data["absent_count"] == 4
    assert manual_data["present_count"] + manual_data["absent_count"] == 35

    # Simulated count differs, but manual records are invariant
    assert res.estimated_count != manual_data["present_count"]


# =============================================================================
# 7. Deterministic Behavior
# =============================================================================


def test_deterministic_output_across_repeated_calls():
    """Verify get_simulated_webcam_count is 100% deterministic for identical inputs."""
    # NORMAL mode
    normal_results = [
        get_simulated_webcam_count("NORMAL", reference_present=25) for _ in range(5)
    ]
    assert all(r == normal_results[0] for r in normal_results)

    # DISCREPANCY mode
    discrepancy_results = [
        get_simulated_webcam_count("DISCREPANCY", reference_present=25) for _ in range(5)
    ]
    assert all(r == discrepancy_results[0] for r in discrepancy_results)

    # Explicit random_seed
    seed_results = [
        get_simulated_webcam_count("NORMAL", reference_present=25, random_seed=42)
        for _ in range(5)
    ]
    assert all(r == seed_results[0] for r in seed_results)


# =============================================================================
# 8. Input Validation & Error Handling
# =============================================================================


def test_negative_reference_present_raises_value_error():
    """Verify negative reference_present raises ValueError."""
    with pytest.raises(ValueError, match="reference_present must be non-negative"):
        get_simulated_webcam_count("NORMAL", reference_present=-1)


def test_non_integer_reference_present_raises_type_error():
    """Verify non-integer reference_present raises TypeError."""
    with pytest.raises(TypeError, match="reference_present must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present="25")  # type: ignore

    with pytest.raises(TypeError, match="reference_present must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=True)  # type: ignore


def test_invalid_mode_raises_value_error():
    """Verify unrecognized mode string raises ValueError with allowed mode list."""
    with pytest.raises(ValueError, match="Invalid mode 'UNKNOWN_MODE'"):
        get_simulated_webcam_count(mode="UNKNOWN_MODE", reference_present=25)


def test_invalid_confidence_score_raises():
    """Verify confidence_score outside [0.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
        get_simulated_webcam_count("NORMAL", reference_present=25, confidence_score=1.5)

    with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
        get_simulated_webcam_count("NORMAL", reference_present=25, confidence_score=-0.1)

    with pytest.raises(TypeError, match="confidence_score must be a float"):
        get_simulated_webcam_count("NORMAL", reference_present=25, confidence_score="high")  # type: ignore


def test_invalid_delta_raises_type_error():
    """Verify non-integer or boolean delta values raise TypeError."""
    # Booleans explicitly rejected
    with pytest.raises(TypeError, match="delta must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=25, delta=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="delta must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=25, delta=False)  # type: ignore[arg-type]

    # Floating-point values rejected
    with pytest.raises(TypeError, match="delta must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=25, delta=2.5)  # type: ignore[arg-type]

    # Strings rejected
    with pytest.raises(TypeError, match="delta must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=25, delta="5")  # type: ignore[arg-type]

    # Other non-integer types rejected
    with pytest.raises(TypeError, match="delta must be an integer"):
        get_simulated_webcam_count("NORMAL", reference_present=25, delta=[1])  # type: ignore[arg-type]
