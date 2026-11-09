"""Tests for synthetic attendance data generator.

Verifies reproducibility, contract compliance, count invariants, edge cases,
and ground-truth scenarios for AttendSure Milestone M2.2.
"""

from datetime import datetime, timezone
import re
import pytest
import pandas as pd

from attendsure.data.generator import (
    GROUND_TRUTH_COLUMNS,
    SESSION_COLUMNS,
    generate_scenario_sessions,
    generate_synthetic_sessions,
)
from attendsure.data.validation import (
    validate_session_dataframe,
    validate_session_dict,
)


def test_generator_deterministic_reproducibility():
    """Generating sessions with identical parameters and seed produces identical DataFrames."""
    df1 = generate_synthetic_sessions(
        num_classes=3,
        num_days=10,
        anomaly_rate=0.1,
        random_seed=42,
        include_webcam=True,
    )
    df2 = generate_synthetic_sessions(
        num_classes=3,
        num_days=10,
        anomaly_rate=0.1,
        random_seed=42,
        include_webcam=True,
    )
    pd.testing.assert_frame_equal(df1, df2)


def test_generator_seed_variation():
    """Different seeds produce different synthetic values and session IDs."""
    df1 = generate_synthetic_sessions(num_classes=2, num_days=10, random_seed=42)
    df2 = generate_synthetic_sessions(num_classes=2, num_days=10, random_seed=999)

    # Session IDs must differ
    assert set(df1["session_id"]) != set(df2["session_id"])
    # Headcounts should differ
    assert list(df1["present_count"]) != list(df2["present_count"])


def test_empty_and_minimum_generation():
    """Zero classes or zero days returns empty DataFrame with expected schema."""
    df_empty_classes = generate_synthetic_sessions(num_classes=0, num_days=10)
    assert df_empty_classes.empty
    assert list(df_empty_classes.columns) == SESSION_COLUMNS + GROUND_TRUTH_COLUMNS

    df_empty_days = generate_synthetic_sessions(num_classes=5, num_days=0)
    assert df_empty_days.empty
    assert list(df_empty_days.columns) == SESSION_COLUMNS + GROUND_TRUTH_COLUMNS

    # Minimum generation: 1 class, 1 day
    df_min = generate_synthetic_sessions(num_classes=1, num_days=1, random_seed=123)
    assert len(df_min) == 1
    valid_df, rej_df = validate_session_dataframe(df_min)
    assert len(valid_df) == 1
    assert len(rej_df) == 0


def test_invalid_argument_rejection():
    """Generator rejects invalid parameter values with descriptive ValueErrors."""
    with pytest.raises(ValueError, match="num_classes"):
        generate_synthetic_sessions(num_classes=-1)

    with pytest.raises(ValueError, match="num_classes"):
        generate_synthetic_sessions(num_classes=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="num_days"):
        generate_synthetic_sessions(num_days=-5)

    with pytest.raises(ValueError, match="anomaly_rate"):
        generate_synthetic_sessions(anomaly_rate=-0.1)

    with pytest.raises(ValueError, match="anomaly_rate"):
        generate_synthetic_sessions(anomaly_rate=1.5)

    with pytest.raises(ValueError, match="random_seed"):
        generate_synthetic_sessions(random_seed="invalid")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="record_source"):
        generate_synthetic_sessions(record_source="UNKNOWN_SOURCE")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Invalid start_date"):
        generate_synthetic_sessions(start_date="2026/01/01")

    with pytest.raises(ValueError, match="Invalid start_date"):
        generate_synthetic_sessions(start_date=" 2026-01-01 ")

    with pytest.raises(ValueError, match="Invalid calendar date"):
        generate_synthetic_sessions(start_date="2026-02-30")

    with pytest.raises(ValueError, match="future"):
        # Explicit far future start date
        generate_synthetic_sessions(start_date="2099-01-01", num_days=5)


def test_contract_validation_of_every_record():
    """Every generated synthetic record passes both validate_session_dict and validate_session_dataframe."""
    df = generate_synthetic_sessions(
        num_classes=4,
        num_days=15,
        anomaly_rate=0.2,
        random_seed=77,
        include_webcam=True,
    )
    assert len(df) == 60

    # Record-level validation
    for idx, row in df.iterrows():
        rec_dict = row.to_dict()
        val_result = validate_session_dict(rec_dict)
        assert val_result.is_valid, f"Row {idx} failed validation: {val_result.errors}"

    # Batch DataFrame validation
    valid_df, rej_df = validate_session_dataframe(df)
    assert len(valid_df) == 60
    assert len(rej_df) == 0


def test_batch_uniqueness_guarantees():
    """Batch session_id and composite (class_id, session_date) are strictly unique."""
    df = generate_synthetic_sessions(num_classes=5, num_days=20, random_seed=101)
    assert len(df) == 100

    # Unique session_id
    assert df["session_id"].nunique() == 100

    # Unique (class_id, session_date) pairs
    class_date_pairs = list(zip(df["class_id"], df["session_date"]))
    assert len(set(class_date_pairs)) == 100


def test_count_invariants_and_boundaries():
    """Enforces present_count + absent_count == expected_enrollment for 100% of rows."""
    df = generate_synthetic_sessions(
        num_classes=5,
        num_days=25,
        anomaly_rate=0.3,
        random_seed=888,
        include_webcam=True,
    )

    enrollment = df["expected_enrollment"]
    present = df["present_count"]
    absent = df["absent_count"]

    assert (present >= 0).all()
    assert (absent >= 0).all()
    assert (present <= enrollment).all()
    assert (absent <= enrollment).all()
    assert (present + absent == enrollment).all()


def test_webcam_invariants_consistency():
    """Webcam count is non-negative int when status is SUCCESS, and None otherwise."""
    # When webcam is disabled, all sessions must be NOT_ATTEMPTED with None count
    df_no_cam = generate_synthetic_sessions(num_classes=2, num_days=10, include_webcam=False)
    assert (df_no_cam["webcam_status"] == "NOT_ATTEMPTED").all()
    assert df_no_cam["webcam_count"].isna().all()

    # When webcam is enabled, SUCCESS has non-negative int; non-SUCCESS has None
    df_cam = generate_synthetic_sessions(
        num_classes=4,
        num_days=20,
        include_webcam=True,
        random_seed=555,
    )
    for _, row in df_cam.iterrows():
        status = row["webcam_status"]
        count = row["webcam_count"]
        if status == "SUCCESS":
            assert isinstance(count, (int, float)) and not pd.isna(count)
            assert int(count) >= 0
        else:
            assert pd.isna(count) or count is None


def test_chronological_ordering_and_no_future_dates():
    """Sessions within each class are strictly chronological and never in the future."""
    today_utc = datetime.now(timezone.utc).date()
    df = generate_synthetic_sessions(num_classes=3, num_days=12, random_seed=42)

    for class_id, group in df.groupby("class_id"):
        dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in group["session_date"]]
        # Strictly ascending
        assert dates == sorted(dates)
        # Never in the future relative to system execution time
        assert all(d <= today_utc for d in dates)


def test_class_id_regex_compliance():
    """All generated class IDs satisfy the contract regex ^[A-Za-z0-9_-]{2,32}$."""
    pattern = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
    df = generate_synthetic_sessions(num_classes=10, num_days=5, random_seed=42)
    for cid in df["class_id"].unique():
        assert pattern.match(cid), f"class_id '{cid}' violates contract regex"


def test_no_pii_or_biometrics_in_schema():
    """Generated dataset contains no student names, IDs, biometrics, or personal identifiers."""
    df = generate_synthetic_sessions(num_classes=3, num_days=5, include_webcam=True)
    forbidden_terms = ["name", "student", "photo", "face", "image", "biometric", "gender", "dob"]

    for col in df.columns:
        col_lower = col.lower()
        for term in forbidden_terms:
            assert term not in col_lower, f"Forbidden PII term '{term}' found in column '{col}'"


def test_include_labels_toggle():
    """When include_labels is False, ground-truth columns are omitted."""
    df_with_labels = generate_synthetic_sessions(include_labels=True)
    for col in GROUND_TRUTH_COLUMNS:
        assert col in df_with_labels.columns

    df_without_labels = generate_synthetic_sessions(include_labels=False)
    for col in GROUND_TRUTH_COLUMNS:
        assert col not in df_without_labels.columns
    assert list(df_without_labels.columns) == SESSION_COLUMNS


# -----------------------------------------------------------------------------
# Scenario-Specific Tests
# -----------------------------------------------------------------------------


def test_scenario_nominal_sessions():
    """NOMINAL scenario generates realistic sessions with no injected anomalies."""
    for sc in ("NOMINAL", "NORMAL"):
        df = generate_scenario_sessions(sc, num_days=10, expected_enrollment=30)
        assert len(df) == 10
        assert not df["ground_truth_is_anomaly"].any()
        assert (df["ground_truth_anomaly_type"] == "NONE").all()

        valid_df, rej_df = validate_session_dataframe(df)
        assert len(valid_df) == 10
        assert len(rej_df) == 0


def test_scenario_attendance_drop_trigger():
    """ATTENDANCE_DROP scenario produces 5 nominal baseline sessions and a steep drop on day 6."""
    df = generate_scenario_sessions(
        "ATTENDANCE_DROP",
        num_days=10,
        expected_enrollment=30,
        random_seed=42,
    )
    assert len(df) == 10

    # Days 0 to 4 are baseline
    assert not df.iloc[0:5]["ground_truth_is_anomaly"].any()
    baseline_median = df.iloc[0:5]["present_count"].median()

    # Day 5 (6th session) is the injected drop
    drop_row = df.iloc[5]
    assert bool(drop_row["ground_truth_is_anomaly"]) is True
    assert drop_row["ground_truth_anomaly_type"] == "ATTENDANCE_DROP"

    drop_present = drop_row["present_count"]
    relative_decline = ((baseline_median - drop_present) / baseline_median) * 100.0
    assert relative_decline >= 30.0, f"Expected decline >= 30%, got {relative_decline:.2f}%"


def test_scenario_repeated_headcount_trigger():
    """REPEATED_HEADCOUNT scenario produces 4 consecutive sessions of identical count."""
    df = generate_scenario_sessions(
        "REPEATED_HEADCOUNT",
        num_days=10,
        expected_enrollment=30,
        random_seed=42,
    )
    assert len(df) == 10

    # Days 4, 5, 6, 7 (indices 4..7) have identical present_count
    repeated_slice = df.iloc[4:8]
    assert len(repeated_slice["present_count"].unique()) == 1
    assert repeated_slice["ground_truth_is_anomaly"].all()
    assert (repeated_slice["ground_truth_anomaly_type"] == "REPEATED_HEADCOUNT").all()

    # The repeated count must be less than enrollment (non-100% attendance, so K >= 4 rule applies)
    repeated_val = repeated_slice["present_count"].iloc[0]
    assert repeated_val < 30


def test_scenario_webcam_discrepancy_trigger():
    """WEBCAM_DISCREPANCY scenario produces a camera difference >= 5 and >= 20% on day 6."""
    df = generate_scenario_sessions(
        "WEBCAM_DISCREPANCY",
        num_days=10,
        expected_enrollment=30,
        random_seed=42,
    )
    assert len(df) == 10

    # Day 5 (index 5) is the injected discrepancy
    disc_row = df.iloc[5]
    assert bool(disc_row["ground_truth_is_anomaly"]) is True
    assert disc_row["ground_truth_anomaly_type"] == "WEBCAM_DISCREPANCY"
    assert disc_row["webcam_status"] == "SUCCESS"

    manual = disc_row["present_count"]
    camera = disc_row["webcam_count"]
    abs_diff = abs(camera - manual)
    rel_diff = (abs_diff / manual) * 100.0

    assert abs_diff >= 5, f"Expected abs_diff >= 5, got {abs_diff}"
    assert rel_diff >= 20.0, f"Expected rel_diff >= 20%, got {rel_diff:.2f}%"


def test_scenario_validation_errors():
    """generate_scenario_sessions rejects invalid parameters."""
    with pytest.raises(ValueError, match="Invalid scenario_type"):
        generate_scenario_sessions("INVALID_SCENARIO")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Invalid class_id"):
        generate_scenario_sessions("NOMINAL", class_id="INVALID CLASS WITH SPACES")

    with pytest.raises(ValueError, match="num_days"):
        generate_scenario_sessions("NOMINAL", num_days=0)

    with pytest.raises(ValueError, match="num_days"):
        generate_scenario_sessions("NOMINAL", num_days=False)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="expected_enrollment"):
        generate_scenario_sessions("NOMINAL", expected_enrollment=0)

    with pytest.raises(ValueError, match="requires num_days >= 8"):
        generate_scenario_sessions("ATTENDANCE_DROP", num_days=5)

    with pytest.raises(ValueError, match="expected_enrollment >= 10"):
        generate_scenario_sessions("WEBCAM_DISCREPANCY", num_days=10, expected_enrollment=5)


def test_nominal_scenario_streak_bound_and_zero_false_positives():
    """Phase B Regression: NOMINAL scenario with seed 42 must not produce accidental streaks >= 4.

    Investigated in M5.8: Previously, unconstrained random selection from [-1, 0, 1]
    produced 4 consecutive 26s on seed 42, triggering an explainable repeated-headcount
    alert on a nominal baseline (counted as FP=1). With bounded streak sampling,
    the maximum consecutive streak remains < 4, and the detector produces 0 alerts (FP=0, TN=15).
    """
    from attendsure.detection.rules import detect_anomalies

    df = generate_scenario_sessions(
        "NOMINAL",
        num_days=15,
        expected_enrollment=30,
        random_seed=42,
    )
    assert len(df) == 15

    # Verify no streak of >= 4 identical present counts exists
    counts = df["present_count"].tolist()
    max_streak = 1
    curr_streak = 1
    for i in range(1, len(counts)):
        if counts[i] == counts[i - 1]:
            curr_streak += 1
            max_streak = max(max_streak, curr_streak)
        else:
            curr_streak = 1
    assert max_streak < 4, f"Expected nominal streak < 4, got {max_streak}: {counts}"

    # Verify detection pipeline produces 0 alerts on nominal baseline
    alerts = detect_anomalies(df)
    assert len(alerts) == 0, f"Expected 0 alerts in nominal scenario, got {len(alerts)}: {alerts}"

    # Verify evaluation metrics
    from attendsure.evaluation import evaluate_detector_performance
    eval_res = evaluate_detector_performance(df, alerts)
    assert eval_res["fp"] == 0
    assert eval_res["tn"] == 15
    assert eval_res["tp"] == 0
    assert eval_res["fn"] == 0
    assert eval_res["precision"] == 0.0
    assert eval_res["zero_division_applied"]["precision"] is True


def test_nominal_scenario_zero_false_positives_multi_seeds():
    """Verify NOMINAL scenario generates zero alerts across multiple deterministic seeds."""
    from attendsure.detection.rules import detect_anomalies

    for seed in [1, 7, 42, 100, 999, 2026]:
        df = generate_scenario_sessions("NOMINAL", num_days=15, random_seed=seed)
        alerts = detect_anomalies(df)
        assert len(alerts) == 0, f"Seed {seed} generated {len(alerts)} alerts in NOMINAL: {alerts}"


def test_nominal_synthetic_sessions_zero_false_positives():
    """Verify generate_synthetic_sessions with anomaly_rate=0.0 produces zero false positives."""
    from attendsure.detection.rules import detect_anomalies

    df = generate_synthetic_sessions(
        num_classes=3,
        num_days=20,
        anomaly_rate=0.0,
        random_seed=42,
    )
    alerts = detect_anomalies(df)
    assert len(alerts) == 0, f"Expected 0 alerts for anomaly_rate=0.0, got {len(alerts)}"
