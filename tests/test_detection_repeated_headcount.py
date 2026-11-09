"""Unit tests for RULE_REPEATED_HEADCOUNT detection rule.

Tests all criteria specified in AttendSure Milestone M3.2, docs/data-contract.md
Section 5.2, and Decision D11.
"""

from copy import deepcopy
from datetime import datetime, timezone
import re
import pandas as pd
import pytest

from attendsure.data.generator import generate_scenario_sessions
from attendsure.detection import (
    DEFAULT_REPEATED_THRESHOLD,
    PERFECT_ATTENDANCE_REPEATED_THRESHOLD,
    RULE_ATTENDANCE_DROP,
    RULE_REPEATED_HEADCOUNT,
    RULE_REPEATED_HEADCOUNT_TITLE,
    detect_anomalies,
    detect_attendance_drop,
    detect_repeated_headcount,
)

UUIDV4_ALERT_PATTERN = re.compile(
    r"^ALT-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _make_session(
    class_id: str,
    session_date: str,
    enrollment: int = 30,
    present: int = 24,
    session_id: str = "550e8400-e29b-41d4-a716-446655440001",
    webcam_status: str = "NOT_ATTEMPTED",
    webcam_count: int | None = None,
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


def _make_repeated_sequence(
    class_id: str,
    headcounts: list[int],
    enrollments: list[int] | int = 30,
    start_day: int = 1,
    session_id_prefix: str = "00000000-0000-4000-8000-0000000000",
) -> list[dict]:
    """Helper to generate a sequence of daily sessions with given present counts."""
    records = []
    for idx, present in enumerate(headcounts):
        day_num = start_day + idx
        s_date = f"2026-10-{day_num:02d}"
        s_id = f"{session_id_prefix}{day_num:02d}"
        enr = enrollments[idx] if isinstance(enrollments, list) else enrollments
        records.append(
            _make_session(
                class_id=class_id,
                session_date=s_date,
                enrollment=enr,
                present=present,
                session_id=s_id,
            )
        )
    return records


# =========================================================================
# 1. Three Identical Non-Perfect Sessions: No Alert
# =========================================================================


def test_three_identical_non_perfect_sessions_no_alert():
    """Three consecutive non-perfect sessions (K = 3 < 4) must not trigger an alert."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24], enrollments=30)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 0


# =========================================================================
# 2. Four Identical Non-Perfect Sessions: Alert
# =========================================================================


def test_four_identical_non_perfect_sessions_triggers_alert():
    """Four consecutive non-perfect sessions (K = 4 >= 4) must trigger an alert."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24], enrollments=30)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 1
    alert = alerts[0]

    assert alert.rule_id == RULE_REPEATED_HEADCOUNT
    assert alert.session_id == records[3]["session_id"]
    assert alert.session_date == "2026-10-04"
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.observed_value["repeated_headcount"] == 24
    assert alert.observed_value["start_date"] == "2026-10-01"
    assert alert.observed_value["end_date"] == "2026-10-04"
    assert alert.threshold_applied["consecutive_sessions_threshold"] == 4
    assert alert.threshold_applied["observed_consecutive_sessions"] == 4
    assert alert.threshold_applied["is_100_pct_attendance_run"] is False


# =========================================================================
# 3. Five Identical Perfect-Attendance Sessions: No Alert
# =========================================================================


def test_five_identical_perfect_attendance_sessions_no_alert():
    """Five consecutive perfect attendance sessions (K = 5 < 6) must not trigger an alert."""
    # Enrollment = 20, Present = 20 for 5 consecutive days (100% attendance throughout)
    records = _make_repeated_sequence("CLASS-01-A", [20, 20, 20, 20, 20], enrollments=20)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 0


# =========================================================================
# 4. Six Identical Perfect-Attendance Sessions: Alert
# =========================================================================


def test_six_identical_perfect_attendance_sessions_triggers_alert():
    """Six consecutive perfect attendance sessions (K = 6 >= 6) must trigger an alert."""
    records = _make_repeated_sequence("CLASS-01-A", [20, 20, 20, 20, 20, 20], enrollments=20)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 1
    alert = alerts[0]

    assert alert.rule_id == RULE_REPEATED_HEADCOUNT
    assert alert.session_id == records[5]["session_id"]
    assert alert.session_date == "2026-10-06"
    assert alert.observed_value["consecutive_sessions"] == 6
    assert alert.observed_value["repeated_headcount"] == 20
    assert alert.observed_value["start_date"] == "2026-10-01"
    assert alert.observed_value["end_date"] == "2026-10-06"
    assert alert.threshold_applied["consecutive_sessions_threshold"] == 6
    assert alert.threshold_applied["observed_consecutive_sessions"] == 6
    assert alert.threshold_applied["is_100_pct_attendance_run"] is True


# =========================================================================
# 5. Sequence with Enrollment Changes but Preserved Headcount (Decision D11)
# =========================================================================


def test_sequence_with_enrollment_change_preserves_run():
    """Decision D11 & Example A: Changing enrollment does not reset repeated present_count run."""
    # Day 1: 24/28, Day 2: 24/28, Day 3: 24/29, Day 4: 24/29
    headcounts = [24, 24, 24, 24]
    enrollments = [28, 28, 29, 29]
    records = _make_repeated_sequence("CLASS-01-A", headcounts, enrollments=enrollments)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.session_date == "2026-10-04"
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.observed_value["repeated_headcount"] == 24
    assert alert.threshold_applied["consecutive_sessions_threshold"] == 4


def test_mixed_perfect_and_non_perfect_sequence():
    """Example B: A run with mixed 100% and non-100% applies standard threshold (K >= 4)."""
    # Day 1: 20/20 (100%), Day 2: 20/20 (100%), Day 3: 20/20 (100%), Day 4: 20/22 (90.9%)
    headcounts = [20, 20, 20, 20]
    enrollments = [20, 20, 20, 22]
    records = _make_repeated_sequence("CLASS-01-A", headcounts, enrollments=enrollments)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.session_date == "2026-10-04"
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.threshold_applied["consecutive_sessions_threshold"] == 4
    assert alert.threshold_applied["is_100_pct_attendance_run"] is False


# =========================================================================
# 6. Sequence Broken by a Different Present Count
# =========================================================================


def test_sequence_broken_by_different_present_count():
    """A change in present_count resets the sequence run length to 1."""
    # 3 sessions of 24, then 1 session of 25, then 2 sessions of 25
    # Sequence of 24 has length 3 (< 4) -> no alert
    # Sequence of 25 has length 3 (< 4) -> no alert
    headcounts = [24, 24, 24, 25, 25, 25]
    records = _make_repeated_sequence("CLASS-01-A", headcounts, enrollments=30)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 0


def test_sequence_broken_and_new_run_reaches_threshold():
    """A broken sequence correctly resets and triggers on the second distinct run."""
    # 2 sessions of 24 (Day 1..2), then 4 sessions of 22 (Day 3..6)
    headcounts = [24, 24, 22, 22, 22, 22]
    records = _make_repeated_sequence("CLASS-01-A", headcounts, enrollments=30)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.session_date == "2026-10-06"
    assert alert.observed_value["repeated_headcount"] == 22
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.observed_value["start_date"] == "2026-10-03"
    assert alert.observed_value["end_date"] == "2026-10-06"


# =========================================================================
# 7. Multiple Classes with Independent Histories
# =========================================================================


def test_multiple_classes_independent_histories():
    """Each class cohort's repeated sequence is tracked strictly independently."""
    # Class A: 4 sessions of 24 (Day 1..4) -> triggers alert on Day 4
    class_a_records = _make_repeated_sequence(
        "CLASS-01-A",
        [24, 24, 24, 24],
        enrollments=30,
        session_id_prefix="00000000-0000-4000-8000-0000000001",
    )

    # Class B: 2 sessions of 24 (Day 3..4) -> length 2 < 4 -> no alert
    class_b_records = _make_repeated_sequence(
        "CLASS-02-B",
        [24, 24],
        enrollments=30,
        start_day=3,
        session_id_prefix="00000000-0000-4000-8000-0000000002",
    )

    df = pd.DataFrame(class_a_records + class_b_records)
    alerts = detect_repeated_headcount(df)

    assert len(alerts) == 1
    assert alerts[0].class_id == "CLASS-01-A"
    assert alerts[0].session_date == "2026-10-04"


# =========================================================================
# 8. Unsorted Input Processing
# =========================================================================


def test_unsorted_input_chronological_processing():
    """Unsorted DataFrame input must be ordered chronologically before evaluating sequence."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24], enrollments=30)
    # Reverse input order: Day 4 first, Day 1 last
    df_shuffled = pd.DataFrame(list(reversed(records)))

    alerts = detect_repeated_headcount(df_shuffled)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.session_date == "2026-10-04"
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.observed_value["start_date"] == "2026-10-01"
    assert alert.observed_value["end_date"] == "2026-10-04"


# =========================================================================
# 9. Invalid Sessions Not Contributing to Sequence
# =========================================================================


def test_invalid_sessions_do_not_contribute_to_sequence():
    """Invalid records must be filtered out and cannot contribute to the run length."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24], enrollments=30)

    # Corrupt session 3 so it violates count invariant (present + absent != enrollment)
    records[2]["present_count"] = 24
    records[2]["absent_count"] = 10  # 24 + 10 = 34 != 30

    df = pd.DataFrame(records)
    # Only 3 valid sessions remain (days 1, 2, 4). Run length is at most 3.
    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 0


def test_invalid_current_session_does_not_trigger():
    """If the 4th session itself is invalid, it must not trigger an alert."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24], enrollments=30)
    # Corrupt 4th session
    records[3]["absent_count"] = -1

    df = pd.DataFrame(records)
    alerts = detect_repeated_headcount(df)
    assert len(alerts) == 0


# =========================================================================
# 10. Webcam Fields Have No Effect on This Rule
# =========================================================================


def test_webcam_fields_have_no_effect_on_repeated_headcount():
    """Webcam status, webcam count, and hardware errors do not alter repeated headcount logic."""
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24], enrollments=30)

    # Vary webcam fields across all valid contract states
    records[0]["webcam_status"] = "NOT_ATTEMPTED"
    records[0]["webcam_count"] = None

    records[1]["webcam_status"] = "SUCCESS"
    records[1]["webcam_count"] = 15  # major camera difference

    records[2]["webcam_status"] = "CAMERA_UNAVAILABLE"
    records[2]["webcam_count"] = None

    records[3]["webcam_status"] = "DETECTION_FAILED"
    records[3]["webcam_count"] = None

    df = pd.DataFrame(records)
    # Ensure webcam_count maintains object dtype so None + int is not cast to float by pandas
    df["webcam_count"] = pd.Series([None, 15, None, None], dtype=object)
    alerts = detect_repeated_headcount(df)

    assert len(alerts) == 1
    assert alerts[0].rule_id == RULE_REPEATED_HEADCOUNT
    assert alerts[0].observed_value["consecutive_sessions"] == 4


# =========================================================================
# 11. Alert Fields, Dates, Threshold, and Non-Accusatory Explanation
# =========================================================================


def test_alert_fields_and_non_accusatory_explanation():
    """Alert structure and explanation must strictly conform to contract requirements."""
    records = _make_repeated_sequence("CLASS-05-A", [24, 24, 24, 24], enrollments=30)
    df = pd.DataFrame(records)

    fixed_timestamp = "2026-10-25T11:00:00Z"
    alerts = detect_repeated_headcount(df, alert_created_at=fixed_timestamp)
    assert len(alerts) == 1
    alert = alerts[0]

    # Contract schema requirements
    assert UUIDV4_ALERT_PATTERN.match(alert.alert_id), f"Invalid alert_id: {alert.alert_id}"
    assert alert.session_id == records[3]["session_id"]
    assert alert.class_id == "CLASS-05-A"
    assert alert.session_date == "2026-10-04"
    assert alert.rule_id == "RULE_REPEATED_HEADCOUNT"
    assert alert.rule_title == "Repeated Identical Headcounts"
    assert alert.priority == "REVIEW_REQUIRED"
    assert alert.review_status == "PENDING_REVIEW"
    assert alert.created_at == fixed_timestamp

    # Observed value
    assert alert.observed_value["repeated_headcount"] == 24
    assert alert.observed_value["consecutive_sessions"] == 4
    assert alert.observed_value["start_date"] == "2026-10-01"
    assert alert.observed_value["end_date"] == "2026-10-04"

    # Baseline reference & Threshold
    assert alert.baseline_reference["expected_behavior"] == "daily_headcount_variation"
    assert alert.threshold_applied["consecutive_sessions_threshold"] == 4
    assert alert.threshold_applied["observed_consecutive_sessions"] == 4
    assert alert.threshold_applied["is_100_pct_attendance_run"] is False

    # Exact non-accusatory explanation template matching contract Section 5.2
    expected_explanation = (
        "Class CLASS-05-A recorded an identical headcount of 24 students across 4 consecutive sessions "
        "from 2026-10-01 to 2026-10-04. This pattern warrants human confirmation to ensure "
        "daily roll-call verification is active."
    )
    assert alert.explanation == expected_explanation

    # Non-accusatory verification
    forbidden_terms = ["fraud", "cheat", "negligence", "misconduct", "falsif", "guilty", "accused"]
    for term in forbidden_terms:
        assert term not in alert.explanation.lower()


# =========================================================================
# 12. Continuing Sequence Behavior (Explicit Contract Invariant)
# =========================================================================


def test_continuing_sequence_emits_alert_for_each_consecutive_session():
    """Explicitly verifies how alerts are emitted for a continuing sequence.

    Under contract trigger condition K >= threshold, each session that meets or
    exceeds the threshold generates an alert for that session with accumulated K.
    """
    # 5 consecutive sessions with present_count = 24 (non-100% attendance, threshold = 4)
    records = _make_repeated_sequence("CLASS-01-A", [24, 24, 24, 24, 24], enrollments=30)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)

    # Day 1..3: K < 4 (no alert)
    # Day 4: K = 4 >= 4 -> Alert 1 (K=4, span: Oct 01 to Oct 04)
    # Day 5: K = 5 >= 4 -> Alert 2 (K=5, span: Oct 01 to Oct 05)
    assert len(alerts) == 2

    assert alerts[0].session_date == "2026-10-04"
    assert alerts[0].observed_value["consecutive_sessions"] == 4
    assert alerts[0].observed_value["start_date"] == "2026-10-01"
    assert alerts[0].observed_value["end_date"] == "2026-10-04"

    assert alerts[1].session_date == "2026-10-05"
    assert alerts[1].observed_value["consecutive_sessions"] == 5
    assert alerts[1].observed_value["start_date"] == "2026-10-01"
    assert alerts[1].observed_value["end_date"] == "2026-10-05"


def test_continuing_perfect_attendance_sequence():
    """Explicitly verifies continuing sequence for perfect attendance runs (threshold = 6)."""
    # 7 consecutive sessions of 100% attendance (20/20)
    records = _make_repeated_sequence("CLASS-01-A", [20, 20, 20, 20, 20, 20, 20], enrollments=20)
    df = pd.DataFrame(records)

    alerts = detect_repeated_headcount(df)

    # Days 1..5: K < 6 (no alert)
    # Day 6: K = 6 >= 6 -> Alert 1 (K=6, span: Oct 01 to Oct 06)
    # Day 7: K = 7 >= 6 -> Alert 2 (K=7, span: Oct 01 to Oct 07)
    assert len(alerts) == 2

    assert alerts[0].session_date == "2026-10-06"
    assert alerts[0].observed_value["consecutive_sessions"] == 6

    assert alerts[1].session_date == "2026-10-07"
    assert alerts[1].observed_value["consecutive_sessions"] == 7


# =========================================================================
# 13. Attendance-Drop Detector Behavior Unchanged & detect_anomalies Integration
# =========================================================================


def test_attendance_drop_behavior_remains_unchanged():
    """Attendance drop detector continues to function with identical behavior."""
    # 5 baseline sessions at 80% and a drop to 40% on day 6
    records = _make_repeated_sequence("CLASS-01-A", [80, 80, 80, 80, 80, 40], enrollments=100)
    df = pd.DataFrame(records)

    # Repeated headcount will trigger on Day 4 and Day 5 (80 repeated across 5 days)
    repeated_alerts = detect_repeated_headcount(df)
    assert len(repeated_alerts) == 2

    # Attendance drop triggers on Day 6
    drop_alerts = detect_attendance_drop(df)
    assert len(drop_alerts) == 1
    assert drop_alerts[0].rule_id == RULE_ATTENDANCE_DROP
    assert drop_alerts[0].session_date == "2026-10-06"


def test_detect_anomalies_rule_filtering():
    """detect_anomalies correctly coordinates both active rules and filters."""
    # Data with both a repeated run (days 1..4) and an attendance drop (day 6)
    # Days 1..5: 80/100; Day 6: 40/100
    records = _make_repeated_sequence("CLASS-01-A", [80, 80, 80, 80, 80, 40], enrollments=100)
    df = pd.DataFrame(records)

    # 1. Run all rules (active_rules = None)
    all_alerts = detect_anomalies(df)
    # Repeated headcount on day 4 & day 5, drop on day 6 -> 3 alerts total
    assert len(all_alerts) == 3
    rule_ids = [a.rule_id for a in all_alerts]
    assert rule_ids.count(RULE_REPEATED_HEADCOUNT) == 2
    assert rule_ids.count(RULE_ATTENDANCE_DROP) == 1

    # 2. Filter active_rules = [RULE_REPEATED_HEADCOUNT]
    repeated_only = detect_anomalies(df, active_rules=[RULE_REPEATED_HEADCOUNT])
    assert len(repeated_only) == 2
    assert all(a.rule_id == RULE_REPEATED_HEADCOUNT for a in repeated_only)

    # 3. Filter active_rules = [RULE_ATTENDANCE_DROP]
    drop_only = detect_anomalies(df, active_rules=[RULE_ATTENDANCE_DROP])
    assert len(drop_only) == 1
    assert drop_only[0].rule_id == RULE_ATTENDANCE_DROP


def test_synthetic_repeated_headcount_scenario_integration():
    """Integrates with generate_scenario_sessions('REPEATED_HEADCOUNT')."""
    # Injected 4-day repeated headcount across days index 4, 5, 6, 7 (days 5, 6, 7, 8)
    df = generate_scenario_sessions("REPEATED_HEADCOUNT", num_days=10, expected_enrollment=30, random_seed=42)

    alerts = detect_repeated_headcount(df)
    # Run reaches K=4 on day index 7 (day 8 of the session dates)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == RULE_REPEATED_HEADCOUNT
    assert alert.session_date == df.iloc[7]["session_date"]
    assert alert.session_id == df.iloc[7]["session_id"]
    assert alert.observed_value["consecutive_sessions"] == 4
