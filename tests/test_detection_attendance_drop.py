"""Unit tests for RULE_ATTENDANCE_DROP detection rule.

Tests all criteria specified in AttendSure Milestone M3.1 and docs/data-contract.md Section 5.1.
"""

from copy import deepcopy
from datetime import datetime, timezone
import re
import pandas as pd
import pytest

from attendsure.data.generator import generate_scenario_sessions
from attendsure.detection import (
    RULE_ATTENDANCE_DROP,
    RULE_ATTENDANCE_DROP_TITLE,
    detect_anomalies,
    detect_attendance_drop,
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
        "webcam_status": "NOT_ATTEMPTED",
        "webcam_count": None,
        "record_source": record_source,
        "created_at": f"{session_date}T09:00:00Z",
    }


def _make_class_history(
    class_id: str,
    attendance_rates: list[float],
    start_day: int = 1,
    enrollment: int = 100,
    session_id_prefix: str = "00000000-0000-4000-8000-0000000000",
) -> list[dict]:
    """Helper to generate a sequence of daily sessions with specified attendance rates."""
    records = []
    for idx, rate in enumerate(attendance_rates):
        day_num = start_day + idx
        s_date = f"2026-10-{day_num:02d}"
        s_id = f"{session_id_prefix}{day_num:02d}"
        present = int(round((rate / 100.0) * enrollment))
        records.append(
            _make_session(
                class_id=class_id,
                session_date=s_date,
                enrollment=enrollment,
                present=present,
                session_id=s_id,
            )
        )
    return records


# =========================================================================
# 1. Fewer than Five Prior Sessions
# =========================================================================


def test_fewer_than_five_prior_sessions_generates_no_alert():
    """Rule must skip detection when fewer than 5 valid prior sessions exist."""
    # Test with 0, 1, 2, 3, 4 sessions
    for num_sessions in range(5):
        # Even with a 100% drop (0 present) on the last session, no alert should fire
        rates = [80.0] * (num_sessions - 1) + [0.0] if num_sessions > 0 else []
        records = _make_class_history("CLASS-01-A", rates)
        df = pd.DataFrame(records)

        alerts = detect_attendance_drop(df)
        assert len(alerts) == 0, f"Expected 0 alerts for {num_sessions} sessions, got {len(alerts)}"


# =========================================================================
# 2. Exactly Five Prior Sessions with Decline < 30%
# =========================================================================


def test_exactly_five_prior_sessions_decline_below_30_pct_no_alert():
    """Decline less than 30% relative to baseline must not trigger an alert."""
    # 5 prior sessions at 80% (baseline = 80%). Day 6 has 60% attendance.
    # Relative decline = (80 - 60) / 80 * 100 = 25.0% (< 30.0%)
    rates = [80.0, 80.0, 80.0, 80.0, 80.0, 60.0]
    df = pd.DataFrame(_make_class_history("CLASS-01-A", rates))

    alerts = detect_attendance_drop(df)
    assert len(alerts) == 0


# =========================================================================
# 3. Exactly 30% Relative Decline
# =========================================================================


def test_exactly_30_percent_relative_decline_triggers_alert():
    """Decline of exactly 30.0% relative to baseline must trigger an alert."""
    # 5 prior sessions at 80% (baseline = 80.0%). Day 6 has 56% attendance.
    # Relative decline = (80.0 - 56.0) / 80.0 * 100 = 24.0 / 80.0 * 100 = 30.0%
    rates = [80.0, 80.0, 80.0, 80.0, 80.0, 56.0]
    df = pd.DataFrame(_make_class_history("CLASS-01-A", rates, enrollment=100))

    alerts = detect_attendance_drop(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == RULE_ATTENDANCE_DROP
    assert alert.threshold_applied["observed_relative_decline_pct"] == 30.0
    assert alert.threshold_applied["relative_decline_threshold_pct"] == 30.0
    assert alert.baseline_reference["baseline_rate_pct"] == 80.0
    assert alert.observed_value["attendance_rate_pct"] == 56.0


# =========================================================================
# 4. Decline Greater Than 30%
# =========================================================================


def test_decline_greater_than_30_percent_triggers_alert():
    """Decline strictly greater than 30% relative to baseline must trigger an alert."""
    # 5 prior sessions at 80.0%. Day 6 has 40.0% attendance.
    # Relative decline = (80.0 - 40.0) / 80.0 * 100 = 50.0%
    rates = [80.0, 80.0, 80.0, 80.0, 80.0, 40.0]
    df = pd.DataFrame(_make_class_history("CLASS-01-A", rates, enrollment=100))

    alerts = detect_attendance_drop(df)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.threshold_applied["observed_relative_decline_pct"] == 50.0
    assert alert.baseline_reference["baseline_rate_pct"] == 80.0
    assert alert.observed_value["attendance_rate_pct"] == 40.0


# =========================================================================
# 5. Stable or Increasing Attendance
# =========================================================================


def test_stable_or_increasing_attendance_no_alert():
    """Stable or improved attendance must never trigger an alert."""
    # Baseline 80%. Day 6 is 80% (stable), Day 7 is 90% (improved), Day 8 is 100%
    rates = [80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 90.0, 100.0]
    df = pd.DataFrame(_make_class_history("CLASS-01-A", rates))

    alerts = detect_attendance_drop(df)
    assert len(alerts) == 0


# =========================================================================
# 6. Zero Baseline
# =========================================================================


def test_zero_baseline_no_division_by_zero_and_no_alert():
    """When baseline attendance rate is 0.0%, rule must guard against division by zero."""
    # 5 prior sessions with 0 present (0.0%). Day 6 has 0.0%. Day 7 has 10.0%.
    rates = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 10.0]
    df = pd.DataFrame(_make_class_history("CLASS-01-A", rates))

    alerts = detect_attendance_drop(df)
    assert len(alerts) == 0


# =========================================================================
# 7. Multiple Classes History Isolation
# =========================================================================


def test_multiple_classes_history_must_not_leak():
    """Attendance history must be tracked independently per class cohort."""
    # Class A has 5 baseline sessions (80%) and a drop on day 6 (40% -> alert)
    class_a_records = _make_class_history(
        "CLASS-01-A",
        [80.0, 80.0, 80.0, 80.0, 80.0, 40.0],
        session_id_prefix="00000000-0000-4000-8000-0000000001",
    )

    # Class B only has 1 session with low attendance (10%) on day 6
    class_b_records = [
        _make_session(
            class_id="CLASS-02-B",
            session_date="2026-10-06",
            enrollment=30,
            present=3,  # 10% attendance
            session_id="00000000-0000-4000-8000-000000000206",
        )
    ]

    # Combine both classes into single DataFrame
    df = pd.DataFrame(class_a_records + class_b_records)

    alerts = detect_attendance_drop(df)

    # Only Class A should trigger an alert; Class B must not use Class A's history
    assert len(alerts) == 1
    assert alerts[0].class_id == "CLASS-01-A"
    assert alerts[0].session_date == "2026-10-06"


# =========================================================================
# 8. Unsorted Input Processing
# =========================================================================


def test_unsorted_input_chronological_processing():
    """Unsorted DataFrame input must be ordered chronologically before baseline calculation."""
    # Create 6 sessions (days 1..5 at 80%, day 6 drop to 40%)
    records = _make_class_history("CLASS-01-A", [80.0, 80.0, 80.0, 80.0, 80.0, 40.0])

    # Reverse order: Day 6 first, Day 1 last
    shuffled_records = list(reversed(records))
    df_shuffled = pd.DataFrame(shuffled_records)

    alerts = detect_attendance_drop(df_shuffled)
    assert len(alerts) == 1
    assert alerts[0].session_date == "2026-10-06"
    assert alerts[0].threshold_applied["observed_relative_decline_pct"] == 50.0


# =========================================================================
# 9. Current Session Self-Exclusion from Baseline
# =========================================================================


def test_current_session_excluded_from_own_baseline():
    """The current session must strictly be excluded from its own baseline window."""
    # Cohort has 5 sessions total: Days 1..4 have 90% attendance; Day 5 has 10% attendance.
    # Because there are only 4 prior sessions before Day 5, Day 5 cannot be evaluated.
    # If Day 5 were included in its own baseline (evaluating 5 sessions including current),
    # an alert would incorrectly trigger on Day 5.
    five_sessions = _make_class_history("CLASS-01-A", [90.0, 90.0, 90.0, 90.0, 10.0])
    df_five = pd.DataFrame(five_sessions)

    alerts = detect_attendance_drop(df_five)
    assert len(alerts) == 0

    # Add Day 6 with 90% attendance:
    # Prior 5 sessions for Day 6 are [90, 90, 90, 90, 10].
    # Rolling median of [10, 90, 90, 90, 90] is 90.0%.
    # Day 6 rate is 90.0% -> decline = 0.0% -> no alert for Day 6.
    six_sessions = five_sessions + [
        _make_session(
            class_id="CLASS-01-A",
            session_date="2026-10-06",
            enrollment=100,
            present=90,
            session_id="00000000-0000-4000-8000-000000000006",
        )
    ]
    df_six = pd.DataFrame(six_sessions)
    assert len(detect_attendance_drop(df_six)) == 0


# =========================================================================
# 10. Invalid Records Not Treated as Valid History
# =========================================================================


def test_invalid_records_not_treated_as_valid_history():
    """Invalid records must be rejected and not counted toward baseline history."""
    # Create 6 sessions
    records = _make_class_history("CLASS-01-A", [80.0, 80.0, 80.0, 80.0, 80.0, 40.0])

    # Corrupt session 3 so it violates the invariant: present + absent != enrollment
    records[2]["present_count"] = 50
    records[2]["absent_count"] = 10  # 50 + 10 = 60 != 100

    df = pd.DataFrame(records)

    # Valid prior records before session 6 are now only 4 (sessions 1, 2, 4, 5).
    # Since fewer than 5 valid prior sessions exist, session 6 must not evaluate.
    alerts = detect_attendance_drop(df)
    assert len(alerts) == 0


def test_invalid_current_session_does_not_trigger_alert():
    """If the current session itself is invalid, it must not trigger an alert."""
    records = _make_class_history("CLASS-01-A", [80.0, 80.0, 80.0, 80.0, 80.0, 40.0])
    # Corrupt the 6th session (negative absent count)
    records[5]["absent_count"] = -5

    df = pd.DataFrame(records)
    alerts = detect_attendance_drop(df)
    assert len(alerts) == 0


# =========================================================================
# 11. Alert Fields & Non-Accusatory Explanation Contract Compliance
# =========================================================================


def test_alert_fields_and_explanation_contract_compliance():
    """Alert structure and explanation must strictly conform to docs/data-contract.md."""
    records = _make_class_history("CLASS-05-A", [80.0, 80.0, 80.0, 80.0, 80.0, 40.0])
    df = pd.DataFrame(records)

    fixed_timestamp = "2026-10-25T11:00:00Z"
    alerts = detect_attendance_drop(df, alert_created_at=fixed_timestamp)
    assert len(alerts) == 1
    alert = alerts[0]

    # Contract Schema Checks
    assert UUIDV4_ALERT_PATTERN.match(alert.alert_id), f"Invalid alert_id format: {alert.alert_id}"
    assert alert.session_id == records[5]["session_id"]
    assert alert.class_id == "CLASS-05-A"
    assert alert.session_date == "2026-10-06"
    assert alert.rule_id == "RULE_ATTENDANCE_DROP"
    assert alert.rule_title == "Attendance Drop — Manual Verification Recommended"
    assert alert.priority == "REVIEW_REQUIRED"
    assert alert.review_status == "PENDING_REVIEW"
    assert alert.created_at == fixed_timestamp

    # Observed value dictionary
    assert alert.observed_value["present_count"] == 40
    assert alert.observed_value["expected_enrollment"] == 100
    assert alert.observed_value["attendance_rate_pct"] == 40.0

    # Baseline reference dictionary
    assert alert.baseline_reference["baseline_type"] == "rolling_median"
    assert alert.baseline_reference["window_sessions"] == 5
    assert alert.baseline_reference["baseline_rate_pct"] == 80.0

    # Threshold applied dictionary
    assert alert.threshold_applied["relative_decline_threshold_pct"] == 30.0
    assert alert.threshold_applied["observed_relative_decline_pct"] == 50.0

    # Non-accusatory wording verification per AGENTS.md Section 2.2
    assert "fraud" not in alert.explanation.lower()
    assert "cheat" not in alert.explanation.lower()
    assert "negligence" not in alert.explanation.lower()
    assert "falsif" not in alert.explanation.lower()
    assert "guilty" not in alert.explanation.lower()
    assert "accused" not in alert.explanation.lower()
    assert "this signal does not establish misconduct" in alert.explanation.lower()

    # Exact template format verification
    expected_explanation = (
        "Class CLASS-05-A recorded 40 of 100 students present (40.0%) on 2026-10-06. "
        "This is a 50.0% decline from the five-session rolling baseline of 80.0%. "
        "Please verify the attendance register and check possible explanations, including "
        "weather, transport disruption, local health conditions, or a data-entry error. "
        "This signal does not establish misconduct."
    )
    assert alert.explanation == expected_explanation


# =========================================================================
# 12. detect_anomalies Interface & Scenario Integration Tests
# =========================================================================


def test_detect_anomalies_active_rules_filter():
    """detect_anomalies honors active_rules parameter filtering."""
    # Use non-repeating baseline rates so RULE_REPEATED_HEADCOUNT does not fire on the baseline
    records = _make_class_history("CLASS-01-A", [80.0, 82.0, 81.0, 79.0, 80.0, 40.0])
    df = pd.DataFrame(records)

    # When active_rules is None, all active rules run (RULE_ATTENDANCE_DROP fires on day 6)
    alerts_default = detect_anomalies(df)
    assert len(alerts_default) == 1
    assert alerts_default[0].rule_id == "RULE_ATTENDANCE_DROP"

    # When active_rules explicitly includes RULE_ATTENDANCE_DROP
    alerts_explicit = detect_anomalies(df, active_rules=["RULE_ATTENDANCE_DROP"])
    assert len(alerts_explicit) == 1
    assert alerts_explicit[0].rule_id == "RULE_ATTENDANCE_DROP"

    # When active_rules excludes RULE_ATTENDANCE_DROP
    alerts_excluded = detect_anomalies(df, active_rules=["RULE_REPEATED_HEADCOUNT"])
    assert len(alerts_excluded) == 0


def test_integration_with_synthetic_scenarios():
    """detect_attendance_drop correctly flags synthetic ATTENDANCE_DROP scenario and stays silent on NOMINAL."""
    # 1. ATTENDANCE_DROP scenario: exactly 1 drop injected on day 6 (index 5)
    df_drop = generate_scenario_sessions("ATTENDANCE_DROP", num_days=10, expected_enrollment=30, random_seed=42)
    alerts = detect_attendance_drop(df_drop)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == "RULE_ATTENDANCE_DROP"
    assert alert.session_date == df_drop.iloc[5]["session_date"]
    assert alert.session_id == df_drop.iloc[5]["session_id"]

    # 2. NOMINAL scenario: no injected attendance drop anomalies -> 0 drop alerts
    df_nominal = generate_scenario_sessions("NOMINAL", num_days=15, expected_enrollment=30, random_seed=42)
    nominal_alerts = detect_attendance_drop(df_nominal)
    assert len(nominal_alerts) == 0


def test_input_type_validation_safety():
    """detect_attendance_drop and detect_anomalies reject non-DataFrame inputs."""
    for bad_input in (None, "string", [1, 2, 3], {"key": "val"}):
        with pytest.raises(TypeError, match="Expected pandas DataFrame"):
            detect_attendance_drop(bad_input)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Expected pandas DataFrame"):
            detect_anomalies(bad_input)  # type: ignore[arg-type]
