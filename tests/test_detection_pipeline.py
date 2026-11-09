"""End-to-end integration and regression test suite for the unified detection pipeline.

Tests AttendSure Milestone M3.5 requirements:
- Deterministic, collision-resistant alert ID generation across rules.
- Complete coverage of detect_anomalies() multi-rule coordination.
- active_rules filtering (None, single rule, multiple rules, empty list, unknown rules).
- Batch rejection of duplicate session_id and (class_id, session_date) records.
- Immutability of caller DataFrames.
- Idempotency / deterministic repeatability.
- Verification that all three rules operate in harmony without regressions.
"""

from copy import deepcopy
import re
import pandas as pd
import pytest

from attendsure.data.models import Alert
from attendsure.detection import (
    RULE_ATTENDANCE_DROP,
    RULE_ATTENDANCE_DROP_TITLE,
    RULE_REPEATED_HEADCOUNT,
    RULE_REPEATED_HEADCOUNT_TITLE,
    RULE_WEBCAM_DISCREPANCY,
    RULE_WEBCAM_DISCREPANCY_TITLE,
    detect_anomalies,
    detect_attendance_drop,
    detect_repeated_headcount,
    detect_webcam_discrepancy,
    generate_alert_id,
)

UUIDV4_ALERT_PATTERN = re.compile(
    r"^ALT-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _make_session(
    class_id: str,
    session_date: str,
    enrollment: int = 100,
    present: int = 80,
    session_id: str = "00000000-0000-4000-8000-000000000001",
    webcam_status: str = "NOT_ATTEMPTED",
    webcam_count: int | None = None,
    record_source: str = "MANUAL_ENTRY",
) -> dict:
    """Helper to construct a valid session dictionary conforming to data-contract.md."""
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


def _build_multi_anomaly_dataset() -> pd.DataFrame:
    """Constructs a composite dataset containing all three anomaly types:
    - Days 1..5: Baseline nominal attendance (80/100) -> Repeated headcount triggers on Day 4 & Day 5
    - Day 6: Attendance drop (40/100 vs baseline 80/100) -> Attendance drop triggers on Day 6
    - Day 7: Rebound (80/100), but visible person discrepancy (webcam=60 vs manual=80) -> Webcam discrepancy triggers
    """
    records = []
    # Days 1..5: 80 present
    for d in range(1, 6):
        records.append(
            _make_session(
                class_id="CLASS-01-A",
                session_date=f"2026-10-0{d}",
                enrollment=100,
                present=80,
                session_id=f"00000000-0000-4000-8000-00000000000{d}",
            )
        )
    # Day 6: Drop to 40
    records.append(
        _make_session(
            class_id="CLASS-01-A",
            session_date="2026-10-06",
            enrollment=100,
            present=40,
            session_id="00000000-0000-4000-8000-000000000006",
        )
    )
    # Day 7: Rebound to 80, webcam logs 60
    records.append(
        _make_session(
            class_id="CLASS-01-A",
            session_date="2026-10-07",
            enrollment=100,
            present=80,
            webcam_status="SUCCESS",
            webcam_count=60,
            session_id="00000000-0000-4000-8000-000000000007",
        )
    )
    df = pd.DataFrame(records)
    df["webcam_count"] = pd.Series([None, None, None, None, None, None, 60], dtype=object)
    return df


# =========================================================================
# Task 1: Alert Identity & Collision Resolution Tests
# =========================================================================


def test_generate_alert_id_format_and_rfc4122_compliance():
    """generate_alert_id satisfies contract regex, length, version 4, and RFC 4122 variant."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    alert_id = generate_alert_id(session_id, RULE_ATTENDANCE_DROP)

    assert UUIDV4_ALERT_PATTERN.match(alert_id), f"alert_id '{alert_id}' failed contract regex."
    assert alert_id.startswith("ALT-")
    assert len(alert_id) == 40  # 'ALT-' (4) + UUID string (36)


def test_alert_id_deterministic_repeatability():
    """Identical session_id and rule_id deterministically yield the exact same alert ID across runs."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    id1 = generate_alert_id(session_id, RULE_ATTENDANCE_DROP)
    id2 = generate_alert_id(session_id, RULE_ATTENDANCE_DROP)
    id3 = generate_alert_id(session_id, RULE_ATTENDANCE_DROP)

    assert id1 == id2 == id3


def test_alert_id_distinct_for_different_rules_on_same_session():
    """Different rules triggering on the same session generate distinct, non-colliding alert IDs."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    id_drop = generate_alert_id(session_id, RULE_ATTENDANCE_DROP)
    id_repeated = generate_alert_id(session_id, RULE_REPEATED_HEADCOUNT)
    id_webcam = generate_alert_id(session_id, RULE_WEBCAM_DISCREPANCY)

    # All three must be mutually distinct
    assert len({id_drop, id_repeated, id_webcam}) == 3
    for aid in (id_drop, id_repeated, id_webcam):
        assert UUIDV4_ALERT_PATTERN.match(aid)


def test_alert_id_distinct_for_different_sessions_on_same_rule():
    """Different session records generate distinct alert IDs for the same rule."""
    s1 = "00000000-0000-4000-8000-000000000001"
    s2 = "00000000-0000-4000-8000-000000000002"

    id1 = generate_alert_id(s1, RULE_ATTENDANCE_DROP)
    id2 = generate_alert_id(s2, RULE_ATTENDANCE_DROP)

    assert id1 != id2


def test_compound_anomalies_same_session_no_alert_id_collision():
    """When a single session triggers both ATTENDANCE_DROP and WEBCAM_DISCREPANCY,
    both alerts are emitted with distinct alert_id values, avoiding SQLite PK collisions.
    """
    records = []
    # 5 prior baseline sessions at 80%
    for d in range(1, 6):
        records.append(
            _make_session(
                class_id="CLASS-01-A",
                session_date=f"2026-10-0{d}",
                enrollment=100,
                present=80,
                session_id=f"00000000-0000-4000-8000-00000000000{d}",
            )
        )
    # Day 6: Drops to 40 (50% drop) AND camera detects only 20 (abs=20, rel=50%)
    compound_session_id = "00000000-0000-4000-8000-000000000006"
    records.append(
        _make_session(
            class_id="CLASS-01-A",
            session_date="2026-10-06",
            enrollment=100,
            present=40,
            webcam_status="SUCCESS",
            webcam_count=20,
            session_id=compound_session_id,
        )
    )
    df = pd.DataFrame(records)
    df["webcam_count"] = pd.Series([None, None, None, None, None, 20], dtype=object)

    alerts = detect_anomalies(df)

    # Filter alerts belonging to the compound session (Day 6)
    day6_alerts = [a for a in alerts if a.session_id == compound_session_id]
    assert len(day6_alerts) == 2

    rule_ids = {a.rule_id for a in day6_alerts}
    assert rule_ids == {RULE_ATTENDANCE_DROP, RULE_WEBCAM_DISCREPANCY}

    # CRITICAL: Alert IDs must not collide
    alert_ids = [a.alert_id for a in day6_alerts]
    assert len(set(alert_ids)) == 2, f"Alert ID collision detected: {alert_ids}"
    for aid in alert_ids:
        assert UUIDV4_ALERT_PATTERN.match(aid)


# =========================================================================
# Task 2: Pipeline Coordination & Rule Selection Tests
# =========================================================================


def test_pipeline_clean_nominal_dataset_returns_no_alerts():
    """A clean nominal attendance stream with realistic daily variation triggers 0 alerts."""
    # Construct a dataset where daily attendance varies realistically between 82% and 88%
    # No 4-day repeated headcount, no 30% drop, and camera is NOT_ATTEMPTED
    headcounts = [85, 87, 84, 86, 88, 85, 83, 86, 87, 85]
    records = []
    for idx, count in enumerate(headcounts):
        records.append(
            _make_session(
                class_id="CLASS-01-A",
                session_date=f"2026-10-{idx + 1:02d}",
                enrollment=100,
                present=count,
                session_id=f"00000000-0000-4000-8000-0000000000{idx:02d}",
            )
        )
    df = pd.DataFrame(records)

    alerts = detect_anomalies(df)
    assert len(alerts) == 0


def test_pipeline_active_rules_none_runs_all_three_rules():
    """active_rules=None coordinates and executes all three implemented anomaly rules."""
    df = _build_multi_anomaly_dataset()

    alerts = detect_anomalies(df, active_rules=None)
    assert len(alerts) == 4

    rule_ids = [a.rule_id for a in alerts]
    assert rule_ids.count(RULE_REPEATED_HEADCOUNT) == 2  # Days 4 & 5
    assert rule_ids.count(RULE_ATTENDANCE_DROP) == 1     # Day 6
    assert rule_ids.count(RULE_WEBCAM_DISCREPANCY) == 1  # Day 7

    # All alert IDs across all rules must be globally unique
    all_alert_ids = [a.alert_id for a in alerts]
    assert len(set(all_alert_ids)) == len(all_alert_ids)


def test_pipeline_active_rules_empty_returns_no_alerts():
    """active_rules=[] returns an empty list without executing any detector."""
    df = _build_multi_anomaly_dataset()

    alerts = detect_anomalies(df, active_rules=[])
    assert len(alerts) == 0
    assert alerts == []


def test_pipeline_active_rules_single_rule_selection():
    """Selecting a single known rule runs exclusively that detector."""
    df = _build_multi_anomaly_dataset()

    # 1. Only Attendance Drop
    drop_alerts = detect_anomalies(df, active_rules=[RULE_ATTENDANCE_DROP])
    assert len(drop_alerts) == 1
    assert drop_alerts[0].rule_id == RULE_ATTENDANCE_DROP

    # 2. Only Repeated Headcount
    repeated_alerts = detect_anomalies(df, active_rules=[RULE_REPEATED_HEADCOUNT])
    assert len(repeated_alerts) == 2
    assert all(a.rule_id == RULE_REPEATED_HEADCOUNT for a in repeated_alerts)

    # 3. Only Webcam Discrepancy
    webcam_alerts = detect_anomalies(df, active_rules=[RULE_WEBCAM_DISCREPANCY])
    assert len(webcam_alerts) == 1
    assert webcam_alerts[0].rule_id == RULE_WEBCAM_DISCREPANCY


def test_pipeline_unknown_rule_id_handling():
    """Unknown or unrecognised rule IDs are safely ignored without error (documents existing API behavior)."""
    df = _build_multi_anomaly_dataset()

    # Pass an unknown rule string
    alerts_unknown = detect_anomalies(df, active_rules=["RULE_NONEXISTENT_FUTURE"])
    assert alerts_unknown == []

    # Pass an unknown rule mixed with a known rule -> only the known rule executes
    alerts_mixed = detect_anomalies(
        df, active_rules=["RULE_NONEXISTENT_FUTURE", RULE_WEBCAM_DISCREPANCY]
    )
    assert len(alerts_mixed) == 1
    assert alerts_mixed[0].rule_id == RULE_WEBCAM_DISCREPANCY


def test_pipeline_idempotency_identical_results_on_repeated_runs():
    """Running detect_anomalies twice on identical data with fixed timestamp produces equivalent alerts."""
    df = _build_multi_anomaly_dataset()
    fixed_ts = "2026-10-25T12:00:00Z"

    run_1 = detect_anomalies(df, alert_created_at=fixed_ts)
    run_2 = detect_anomalies(df, alert_created_at=fixed_ts)

    assert len(run_1) == len(run_2)
    assert run_1 == run_2


# =========================================================================
# Task 3: Invalidation, Immutability & Ordering Safety Tests
# =========================================================================


def test_pipeline_duplicate_session_id_batch_rejected_before_detection():
    """Batch records containing duplicate session_id are quarantined and generate 0 alerts."""
    rec1 = _make_session("CLASS-01-A", "2026-10-01", present=80, session_id="00000000-0000-4000-8000-000000000001")
    # Duplicate session_id on a different class/date
    rec2 = _make_session("CLASS-02-B", "2026-10-02", present=40, session_id="00000000-0000-4000-8000-000000000001")

    df = pd.DataFrame([rec1, rec2])
    alerts = detect_anomalies(df)

    assert len(alerts) == 0


def test_pipeline_duplicate_class_date_batch_rejected_before_detection():
    """Batch records with duplicate (class_id, session_date) pairs are quarantined and produce 0 alerts."""
    rec1 = _make_session(
        "CLASS-01-A", "2026-10-01", present=80, session_id="00000000-0000-4000-8000-000000000001"
    )
    # Duplicate (CLASS-01-A, 2026-10-01) with distinct session_id
    rec2 = _make_session(
        "CLASS-01-A", "2026-10-01", present=40, session_id="00000000-0000-4000-8000-000000000002"
    )

    df = pd.DataFrame([rec1, rec2])
    alerts = detect_anomalies(df)

    assert len(alerts) == 0


def test_pipeline_input_dataframe_immutability():
    """detect_anomalies() does not mutate caller DataFrame values, types, or row counts."""
    df = _build_multi_anomaly_dataset()

    df_copy = df.copy(deep=True)
    orig_shape = df.shape
    orig_columns = list(df.columns)
    orig_dtypes = dict(df.dtypes)

    _ = detect_anomalies(df)

    assert df.shape == orig_shape
    assert list(df.columns) == orig_columns
    assert dict(df.dtypes) == orig_dtypes
    pd.testing.assert_frame_equal(df, df_copy)


def test_pipeline_multi_rule_chronological_sorting():
    """Alerts from disparate rules and classes are sorted deterministically by (session_date, class_id, rule_id)."""
    # Create two classes across multiple dates
    # Class B Day 1: Webcam discrepancy
    s_b1 = _make_session(
        "CLASS-02-B",
        "2026-10-01",
        present=25,
        webcam_status="SUCCESS",
        webcam_count=15,
        session_id="00000000-0000-4000-8000-000000000001",
    )
    # Class A Day 2: Webcam discrepancy
    s_a2 = _make_session(
        "CLASS-01-A",
        "2026-10-02",
        present=25,
        webcam_status="SUCCESS",
        webcam_count=15,
        session_id="00000000-0000-4000-8000-000000000002",
    )
    # Class B Day 2: Webcam discrepancy
    s_b2 = _make_session(
        "CLASS-02-B",
        "2026-10-02",
        present=25,
        webcam_status="SUCCESS",
        webcam_count=15,
        session_id="00000000-0000-4000-8000-000000000003",
    )

    # Shuffled input order
    df = pd.DataFrame([s_b2, s_a2, s_b1])

    alerts = detect_anomalies(df)
    assert len(alerts) == 3

    # Expected order:
    # 1: 2026-10-01, CLASS-02-B
    assert alerts[0].session_date == "2026-10-01"
    assert alerts[0].class_id == "CLASS-02-B"

    # 2: 2026-10-02, CLASS-01-A
    assert alerts[1].session_date == "2026-10-02"
    assert alerts[1].class_id == "CLASS-01-A"

    # 3: 2026-10-02, CLASS-02-B
    assert alerts[2].session_date == "2026-10-02"
    assert alerts[2].class_id == "CLASS-02-B"
