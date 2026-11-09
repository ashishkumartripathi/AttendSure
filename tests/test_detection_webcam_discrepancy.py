"""Unit tests for RULE_WEBCAM_DISCREPANCY detection rule.

Tests all criteria specified in AttendSure Milestone M3.3, docs/data-contract.md
Section 5.3, and Decision D10.
"""

from copy import deepcopy
import re
import pandas as pd
import pytest

from attendsure.data.generator import generate_scenario_sessions
from attendsure.detection import (
    DEFAULT_WEBCAM_ABS_THRESHOLD,
    DEFAULT_WEBCAM_REL_THRESHOLD_PCT,
    RULE_ATTENDANCE_DROP,
    RULE_REPEATED_HEADCOUNT,
    RULE_WEBCAM_DISCREPANCY,
    RULE_WEBCAM_DISCREPANCY_TITLE,
    detect_anomalies,
    detect_attendance_drop,
    detect_repeated_headcount,
    detect_webcam_discrepancy,
)

UUIDV4_ALERT_PATTERN = re.compile(
    r"^ALT-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _make_session(
    class_id: str,
    session_date: str,
    enrollment: int = 30,
    present: int = 25,
    session_id: str = "550e8400-e29b-41d4-a716-446655440001",
    webcam_status: str = "SUCCESS",
    webcam_count: int | None = 25,
    record_source: str = "MANUAL_ENTRY",
) -> dict:
    """Helper to create a valid contract session dictionary."""
    return {
        "session_id": session_id,
        "class_id": class_id,
        "session_date": session_date,
        "expected_enrollment": enrollment,
        "present_count": present,
        "absent_count": enrollment - present,
        "webcam_status": webcam_status,
        "webcam_count": webcam_count,
        "record_source": record_source,
        "created_at": f"{session_date}T09:00:00Z",
    }


# =========================================================================
# 1. Successful Webcam Count with No Discrepancy: No Alert
# =========================================================================


def test_successful_webcam_count_no_discrepancy():
    """Identical manual and webcam counts produce 0 alerts."""
    session = _make_session("CLASS-01-A", "2026-10-01", enrollment=30, present=30, webcam_count=30)
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 0


# =========================================================================
# 2. Absolute Difference Below Five: No Alert
# =========================================================================


def test_absolute_difference_below_five_no_alert():
    """Even if relative difference is >= 20%, abs_diff < 5 must NOT trigger an alert."""
    # Case A: present = 10, webcam = 6 -> abs_diff = 4 (< 5), rel_diff = 40.0% (>= 20%)
    session_a = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=20,
        present=10,
        webcam_count=6,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    # Case B: present = 20, webcam = 16 -> abs_diff = 4 (< 5), rel_diff = 20.0% (>= 20%)
    session_b = _make_session(
        "CLASS-01-A",
        "2026-10-02",
        enrollment=30,
        present=20,
        webcam_count=16,
        session_id="00000000-0000-4000-8000-000000000002",
    )
    df = pd.DataFrame([session_a, session_b])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 0


# =========================================================================
# 3. Absolute Difference Exactly Five but Relative Difference Below 20%: No Alert
# =========================================================================


def test_absolute_difference_five_but_relative_below_20_pct_no_alert():
    """When abs_diff >= 5 but rel_diff < 20%, must NOT trigger an alert."""
    # Case A: present = 30, webcam = 25 -> abs_diff = 5 (>= 5), rel_diff = 16.67% (< 20%)
    session_a = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=35,
        present=30,
        webcam_count=25,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    # Case B: present = 100, webcam = 95 -> abs_diff = 5 (>= 5), rel_diff = 5.0% (< 20%)
    session_b = _make_session(
        "CLASS-01-A",
        "2026-10-02",
        enrollment=120,
        present=100,
        webcam_count=95,
        session_id="00000000-0000-4000-8000-000000000002",
    )
    df = pd.DataFrame([session_a, session_b])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 0


# =========================================================================
# 4. Relative Difference Exactly 20% with Absolute Difference At Least Five: Alert
# =========================================================================


def test_relative_difference_exactly_20_pct_with_abs_diff_at_least_five_triggers():
    """Boundary test: abs_diff == 5 and rel_diff == 20.0% exactly triggers an alert."""
    # present = 25, webcam = 20 -> abs_diff = 5 (== 5), rel_diff = (5 / 25) * 100 = 20.0% (== 20.0%)
    session = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=30,
        present=25,
        webcam_count=20,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == RULE_WEBCAM_DISCREPANCY
    assert alert.observed_value["absolute_difference"] == 5
    assert alert.observed_value["relative_difference_pct"] == 20.0
    assert alert.threshold_applied["observed_absolute_difference"] == 5
    assert alert.threshold_applied["observed_relative_difference_pct"] == 20.0


def test_camera_count_higher_than_manual_count_triggers():
    """Discrepancy where camera count exceeds manual roll call (e.g., visitors, drift) triggers."""
    # present = 25, webcam = 30 -> abs_diff = 5, rel_diff = 20.0%
    session = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=35,
        present=25,
        webcam_count=30,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 1
    assert alerts[0].observed_value["absolute_difference"] == 5
    assert alerts[0].observed_value["relative_difference_pct"] == 20.0


# =========================================================================
# 5. Both Thresholds Exceeded: Alert
# =========================================================================


def test_both_thresholds_exceeded_triggers_alert():
    """abs_diff > 5 and rel_diff > 20% triggers an alert."""
    # present = 20, webcam = 12 -> abs_diff = 8 (> 5), rel_diff = 40.0% (> 20.0%)
    session = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=30,
        present=20,
        webcam_count=12,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.observed_value["absolute_difference"] == 8
    assert alert.observed_value["relative_difference_pct"] == 40.0


# =========================================================================
# 6. Zero Manual Attendance with Webcam Count Four: No Alert
# =========================================================================


def test_zero_manual_attendance_with_webcam_count_four_no_alert():
    """For present_count == 0, abs_diff = 4 < 5 must NOT trigger, with no division by zero."""
    session = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=20,
        present=0,
        webcam_count=4,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 0


# =========================================================================
# 7. Zero Manual Attendance with Webcam Count Five: Alert
# =========================================================================


def test_zero_manual_attendance_with_webcam_count_five_triggers_alert():
    """For present_count == 0, abs_diff = 5 >= 5 triggers an alert safely without division by zero."""
    session = _make_session(
        "CLASS-01-A",
        "2026-10-01",
        enrollment=20,
        present=0,
        webcam_count=5,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    df = pd.DataFrame([session])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == RULE_WEBCAM_DISCREPANCY
    assert alert.observed_value["present_count"] == 0
    assert alert.observed_value["webcam_count"] == 5
    assert alert.observed_value["absolute_difference"] == 5
    assert alert.observed_value["relative_difference_pct"] is None
    assert alert.threshold_applied["zero_attendance_evaluation"] is True
    assert alert.threshold_applied["observed_relative_difference_pct"] is None
    assert "relative difference undefined" in alert.explanation


# =========================================================================
# 8. Non-SUCCESS Webcam Statuses: No Alert
# =========================================================================


def test_non_success_webcam_statuses_generate_no_alerts():
    """Optional hardware fallback: non-SUCCESS webcam statuses never trigger discrepancy alerts."""
    statuses = ["NOT_ATTEMPTED", "CAMERA_UNAVAILABLE", "DETECTION_FAILED"]
    records = []
    for idx, status in enumerate(statuses):
        s = _make_session(
            "CLASS-01-A",
            f"2026-10-{idx + 1:02d}",
            enrollment=30,
            present=25,
            webcam_status=status,
            webcam_count=None,
            session_id=f"00000000-0000-4000-8000-00000000000{idx + 1}",
        )
        records.append(s)

    df = pd.DataFrame(records)
    # Ensure webcam_count has object dtype for nulls
    df["webcam_count"] = pd.Series([None, None, None], dtype=object)

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 0


# =========================================================================
# 9. Missing, Null, Negative, or Invalid Webcam Counts
# =========================================================================


def test_invalid_webcam_counts_rejected_and_generate_no_alerts():
    """Invalid records rejected by contract validation must not generate alerts."""
    # Case A: SUCCESS with None webcam_count (violates count-state mapping)
    rec_a = _make_session("CLASS-01-A", "2026-10-01", enrollment=30, present=20, webcam_count=None)
    rec_a["webcam_status"] = "SUCCESS"

    # Case B: SUCCESS with negative webcam_count
    rec_b = _make_session("CLASS-01-A", "2026-10-02", enrollment=30, present=20, webcam_count=-1)

    # Case C: CAMERA_UNAVAILABLE with non-null webcam_count
    rec_c = _make_session("CLASS-01-A", "2026-10-03", enrollment=30, present=20, webcam_count=20)
    rec_c["webcam_status"] = "CAMERA_UNAVAILABLE"

    # Case D: Malformed non-integer webcam_count
    rec_d = _make_session("CLASS-01-A", "2026-10-04", enrollment=30, present=20, webcam_count=None)
    rec_d["webcam_status"] = "SUCCESS"
    rec_d["webcam_count"] = "invalid_string"  # type: ignore[typeddict-item]

    for rec in (rec_a, rec_b, rec_c, rec_d):
        df = pd.DataFrame([rec])
        alerts = detect_webcam_discrepancy(df)
        assert len(alerts) == 0, f"Expected 0 alerts for invalid record {rec}, got {len(alerts)}"


# =========================================================================
# 10. Multiple Sessions and Multiple Classes
# =========================================================================


def test_multiple_classes_and_sessions_chronological_ordering():
    """Multiple sessions and classes are evaluated independently and sorted chronologically."""
    # Class A, Day 1: Discrepancy (present=25, webcam=15 -> abs=10, rel=40%)
    s_a1 = _make_session(
        "CLASS-01-A",
        "2026-10-02",
        present=25,
        webcam_count=15,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    # Class A, Day 2: No discrepancy (present=25, webcam=24 -> abs=1)
    s_a2 = _make_session(
        "CLASS-01-A",
        "2026-10-03",
        present=25,
        webcam_count=24,
        session_id="00000000-0000-4000-8000-000000000002",
    )
    # Class B, Day 1: Discrepancy (present=20, webcam=12 -> abs=8, rel=40%)
    s_b1 = _make_session(
        "CLASS-02-B",
        "2026-10-01",
        present=20,
        webcam_count=12,
        session_id="00000000-0000-4000-8000-000000000003",
    )
    # Class B, Day 2: Discrepancy (present=20, webcam=10 -> abs=10, rel=50%)
    s_b2 = _make_session(
        "CLASS-02-B",
        "2026-10-02",
        present=20,
        webcam_count=10,
        session_id="00000000-0000-4000-8000-000000000004",
    )

    # Shuffled input order
    df = pd.DataFrame([s_a2, s_b2, s_a1, s_b1])

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 3

    # Sorted by (session_date, class_id):
    # 1. 2026-10-01, CLASS-02-B
    assert alerts[0].session_date == "2026-10-01"
    assert alerts[0].class_id == "CLASS-02-B"

    # 2. 2026-10-02, CLASS-01-A
    assert alerts[1].session_date == "2026-10-02"
    assert alerts[1].class_id == "CLASS-01-A"

    # 3. 2026-10-02, CLASS-02-B
    assert alerts[2].session_date == "2026-10-02"
    assert alerts[2].class_id == "CLASS-02-B"


# =========================================================================
# 11. Alert Metadata, Fields, and Non-Accusatory Explanation
# =========================================================================


def test_alert_metadata_and_non_accusatory_explanation():
    """Alert metadata and explanation strictly conform to contract requirements."""
    session = _make_session(
        "CLASS-05-A",
        "2026-10-25",
        enrollment=35,
        present=30,
        webcam_count=22,
        session_id="550e8400-e29b-41d4-a716-446655440000",
    )
    df = pd.DataFrame([session])

    fixed_timestamp = "2026-10-25T11:00:00Z"
    alerts = detect_webcam_discrepancy(df, alert_created_at=fixed_timestamp)
    assert len(alerts) == 1
    alert = alerts[0]

    # Schema & Identifiers
    assert UUIDV4_ALERT_PATTERN.match(alert.alert_id), f"Invalid alert_id: {alert.alert_id}"
    assert alert.session_id == "550e8400-e29b-41d4-a716-446655440000"
    assert alert.class_id == "CLASS-05-A"
    assert alert.session_date == "2026-10-25"
    assert alert.rule_id == "RULE_WEBCAM_DISCREPANCY"
    assert alert.rule_title == "Visible-Person Discrepancy"
    assert alert.priority == "REVIEW_REQUIRED"
    assert alert.review_status == "PENDING_REVIEW"
    assert alert.created_at == fixed_timestamp

    # Observed values (abs_diff = 8, rel_diff = 8 / 30 * 100 = 26.67%)
    assert alert.observed_value["present_count"] == 30
    assert alert.observed_value["webcam_count"] == 22
    assert alert.observed_value["absolute_difference"] == 8
    assert alert.observed_value["relative_difference_pct"] == 26.67

    # Baseline reference
    assert alert.baseline_reference["baseline_type"] == "manual_roll_call"
    assert alert.baseline_reference["reference_count"] == 30

    # Threshold applied
    assert alert.threshold_applied["absolute_difference_threshold"] == 5
    assert alert.threshold_applied["relative_difference_threshold_pct"] == 20.0
    assert alert.threshold_applied["observed_absolute_difference"] == 8
    assert alert.threshold_applied["observed_relative_difference_pct"] == 26.67
    assert alert.threshold_applied["zero_attendance_evaluation"] is False

    # Exact non-accusatory explanation template from contract Section 5.3
    expected_explanation = (
        "On 2026-10-25, manual roll call logged 30 students present, "
        "while the camera module estimated 22 visible individuals "
        "(difference of 8 people, 26.7% relative difference). "
        "Discrepancies may arise naturally from camera placement, physical occlusion, "
        "or students outside the camera's view."
    )
    assert alert.explanation == expected_explanation

    # Non-accusatory verification
    forbidden_terms = ["fraud", "cheat", "negligence", "misconduct", "falsif", "guilty", "accused"]
    for term in forbidden_terms:
        assert term not in alert.explanation.lower()


# =========================================================================
# 12. Attendance-Drop and Repeated-Headcount Invariance
# =========================================================================


def test_attendance_drop_and_repeated_headcount_behavior_unchanged():
    """All three detectors operate independently and can be coordinated via detect_anomalies."""
    # Construct a composite dataset with:
    # Days 1..5: Baseline attendance (80/100) -> K=5 repeated headcount triggers on day 4 & 5
    # Day 6: Attendance drop (40/100) -> 50% decline triggers attendance drop
    # Day 7: Webcam discrepancy (present=40, webcam=20 -> abs=20, rel=50%)
    records = []
    for day in range(1, 6):
        records.append(
            _make_session(
                "CLASS-01-A",
                f"2026-10-{day:02d}",
                enrollment=100,
                present=80,
                webcam_status="NOT_ATTEMPTED",
                webcam_count=None,
                session_id=f"00000000-0000-4000-8000-00000000000{day}",
            )
        )
    # Day 6: Attendance drop
    records.append(
        _make_session(
            "CLASS-01-A",
            "2026-10-06",
            enrollment=100,
            present=40,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            session_id="00000000-0000-4000-8000-000000000006",
        )
    )
    # Day 7: Attendance rebounds to 80, but camera has discrepancy (webcam=60 -> abs=20, rel=25%)
    records.append(
        _make_session(
            "CLASS-01-A",
            "2026-10-07",
            enrollment=100,
            present=80,
            webcam_status="SUCCESS",
            webcam_count=60,
            session_id="00000000-0000-4000-8000-000000000007",
        )
    )

    df = pd.DataFrame(records)
    df["webcam_count"] = pd.Series([None, None, None, None, None, None, 60], dtype=object)

    # 1. detect_attendance_drop finds exactly Day 6 drop
    drop_alerts = detect_attendance_drop(df)
    assert len(drop_alerts) == 1
    assert drop_alerts[0].rule_id == RULE_ATTENDANCE_DROP
    assert drop_alerts[0].session_date == "2026-10-06"

    # 2. detect_repeated_headcount finds Day 4 and Day 5 repeated 80s
    repeated_alerts = detect_repeated_headcount(df)
    assert len(repeated_alerts) == 2
    assert all(a.rule_id == RULE_REPEATED_HEADCOUNT for a in repeated_alerts)

    # 3. detect_webcam_discrepancy finds exactly Day 7 discrepancy
    webcam_alerts = detect_webcam_discrepancy(df)
    assert len(webcam_alerts) == 1
    assert webcam_alerts[0].rule_id == RULE_WEBCAM_DISCREPANCY
    assert webcam_alerts[0].session_date == "2026-10-07"

    # 4. detect_anomalies runs all 3 rules by default -> 4 alerts total
    all_alerts = detect_anomalies(df)
    assert len(all_alerts) == 4
    rule_ids = [a.rule_id for a in all_alerts]
    assert rule_ids.count(RULE_REPEATED_HEADCOUNT) == 2
    assert rule_ids.count(RULE_ATTENDANCE_DROP) == 1
    assert rule_ids.count(RULE_WEBCAM_DISCREPANCY) == 1

    # 5. active_rules filtering
    webcam_filtered = detect_anomalies(df, active_rules=[RULE_WEBCAM_DISCREPANCY])
    assert len(webcam_filtered) == 1
    assert webcam_filtered[0].rule_id == RULE_WEBCAM_DISCREPANCY

    drop_repeated_filtered = detect_anomalies(
        df, active_rules=[RULE_ATTENDANCE_DROP, RULE_REPEATED_HEADCOUNT]
    )
    assert len(drop_repeated_filtered) == 3


# =========================================================================
# 13. Integration with Synthetic WEBCAM_DISCREPANCY Scenario
# =========================================================================


def test_synthetic_webcam_discrepancy_scenario_integration():
    """detect_webcam_discrepancy correctly flags injected discrepancy in synthetic generator."""
    # Generate 10 days of WEBCAM_DISCREPANCY scenario
    df = generate_scenario_sessions(
        "WEBCAM_DISCREPANCY",
        num_days=10,
        expected_enrollment=30,
        random_seed=42,
    )

    alerts = detect_webcam_discrepancy(df)
    assert len(alerts) == 1
    alert = alerts[0]

    # Injected discrepancy is on day 6 (index 5)
    injected_row = df.iloc[5]
    assert alert.rule_id == RULE_WEBCAM_DISCREPANCY
    assert alert.session_date == injected_row["session_date"]
    assert alert.session_id == injected_row["session_id"]
    assert alert.observed_value["present_count"] == injected_row["present_count"]
    assert alert.observed_value["webcam_count"] == injected_row["webcam_count"]
    assert alert.observed_value["absolute_difference"] >= 5
    assert alert.observed_value["relative_difference_pct"] >= 20.0


# =========================================================================
# 14. Input Type Safety
# =========================================================================


def test_input_type_validation_safety():
    """detect_webcam_discrepancy rejects non-DataFrame inputs."""
    for bad_input in (None, "string", [1, 2, 3], {"key": "val"}):
        with pytest.raises(TypeError, match="Expected pandas DataFrame"):
            detect_webcam_discrepancy(bad_input)  # type: ignore[arg-type]
