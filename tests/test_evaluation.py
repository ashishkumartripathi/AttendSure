"""Unit and integration tests for AttendSure evaluation metrics.

Verifies classification metric computations (TP, FP, TN, FN, Precision, Recall,
F1-score, Confusion Matrix), zero-division policies, empty datasets, synthetic
pipeline reproducibility, input immutability, per-rule independence, session vs event
evaluation semantics, duplicate session ID rejection, and missing column handling
conforming to docs/data-contract.md Section 6.2.
"""

import pandas as pd
import pytest

from attendsure.data.generator import (
    generate_scenario_sessions,
    generate_synthetic_sessions,
)
from attendsure.data.models import Alert
from attendsure.detection.rules import (
    RULE_ATTENDANCE_DROP,
    RULE_REPEATED_HEADCOUNT,
    RULE_WEBCAM_DISCREPANCY,
    detect_anomalies,
)
from attendsure.evaluation import (
    ClassificationCounts,
    compute_classification_scores,
    confusion_matrix_to_dataframe,
    evaluate_detector_performance,
    evaluate_rule_performance,
    evaluate_sequence_events,
    evaluate_webcam_estimation,
)



def _make_dummy_alert(session_id: str, rule_id: str = RULE_ATTENDANCE_DROP) -> Alert:
    """Helper to create a minimal valid Alert object for evaluation testing."""
    return Alert(
        alert_id=f"ALT-{session_id[:8]}-{rule_id[:8]}",
        session_id=session_id,
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        rule_id=rule_id,
        rule_title="Test Rule",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 10},
        baseline_reference={"median_rate_pct": 90.0},
        threshold_applied={"threshold_pct": 30.0},
        explanation="Test explanation.",
        review_status="PENDING_REVIEW",
        created_at="2026-10-20T10:00:00Z",
    )


def test_evaluate_empty_dataset():
    """Verify evaluation handles empty DataFrame without exceptions or zero-division errors."""
    empty_df = pd.DataFrame(columns=["session_id", "ground_truth_is_anomaly"])
    metrics = evaluate_detector_performance(empty_df, [])

    assert metrics["total_samples"] == 0
    assert metrics["tp"] == 0
    assert metrics["fp"] == 0
    assert metrics["tn"] == 0
    assert metrics["fn"] == 0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["confusion_matrix"] == {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    assert metrics["zero_division_applied"]["precision"] is True
    assert metrics["zero_division_applied"]["recall"] is True
    assert metrics["zero_division_applied"]["f1_score"] is True


def test_evaluate_no_positive_labels():
    """Verify evaluation on nominal datasets with no positive labels (denominator = 0)."""
    df = pd.DataFrame(
        {
            "session_id": [f"sess-{i}" for i in range(5)],
            "ground_truth_is_anomaly": [False] * 5,
        }
    )

    # 1. No alerts generated -> All true negatives
    res_clean = evaluate_detector_performance(df, [])
    assert res_clean["total_samples"] == 5
    assert res_clean["tp"] == 0
    assert res_clean["fp"] == 0
    assert res_clean["tn"] == 5
    assert res_clean["fn"] == 0
    assert res_clean["precision"] == 0.0
    assert res_clean["recall"] == 0.0
    assert res_clean["f1_score"] == 0.0
    assert res_clean["zero_division_applied"]["precision"] is True
    assert res_clean["zero_division_applied"]["recall"] is True

    # 2. Spurious alert on sess-0 -> False positive on nominal data
    alert = _make_dummy_alert("sess-0")
    res_spurious = evaluate_detector_performance(df, [alert])
    assert res_spurious["tp"] == 0
    assert res_spurious["fp"] == 1
    assert res_spurious["tn"] == 4
    assert res_spurious["fn"] == 0
    assert res_spurious["precision"] == 0.0  # 0 / (0 + 1) = 0.0
    assert res_spurious["recall"] == 0.0  # 0 / 0 -> zero division 0.0
    assert res_spurious["zero_division_applied"]["recall"] is True


def test_evaluate_perfect_predictions():
    """Verify evaluation when detector achieves 100% precision, recall, and F1."""
    sids = [f"sess-{i}" for i in range(10)]
    # First 5 are anomalous, last 5 are nominal
    labels = [True] * 5 + [False] * 5
    df = pd.DataFrame({"session_id": sids, "ground_truth_is_anomaly": labels})

    # Alerts generated for exactly the 5 anomalous sessions
    alerts = [_make_dummy_alert(sid) for sid in sids[:5]]

    metrics = evaluate_detector_performance(df, alerts)
    assert metrics["total_samples"] == 10
    assert metrics["tp"] == 5
    assert metrics["fp"] == 0
    assert metrics["tn"] == 5
    assert metrics["fn"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["zero_division_applied"] == {
        "precision": False,
        "recall": False,
        "f1_score": False,
    }


def test_evaluate_false_positives_only():
    """Verify evaluation when detector produces false positives on all-nominal data."""
    sids = [f"sess-{i}" for i in range(5)]
    df = pd.DataFrame({"session_id": sids, "ground_truth_is_anomaly": [False] * 5})

    # Detector falsely flags sess-0 and sess-1
    alerts = [_make_dummy_alert("sess-0"), _make_dummy_alert("sess-1")]

    metrics = evaluate_detector_performance(df, alerts)
    assert metrics["tp"] == 0
    assert metrics["fp"] == 2
    assert metrics["tn"] == 3
    assert metrics["fn"] == 0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0


def test_evaluate_false_negatives_only():
    """Verify evaluation when detector fails to detect any existing anomalies."""
    sids = [f"sess-{i}" for i in range(6)]
    # 3 anomalous, 3 nominal
    df = pd.DataFrame(
        {
            "session_id": sids,
            "ground_truth_is_anomaly": [True, True, True, False, False, False],
        }
    )

    # Zero alerts generated
    metrics = evaluate_detector_performance(df, [])
    assert metrics["tp"] == 0
    assert metrics["fp"] == 0
    assert metrics["tn"] == 3
    assert metrics["fn"] == 3
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0


def test_evaluate_mixed_outcomes_mathematical_precision():
    """Verify exact mathematical calculation of Precision, Recall, and F1 on mixed outcomes."""
    # Build distribution: TP=3, FP=1, TN=4, FN=2 (Total = 10)
    # Sessions:
    # 0, 1, 2: Actual True, Pred True  -> TP=3
    # 3:       Actual False, Pred True -> FP=1
    # 4, 5:    Actual True, Pred False -> FN=2
    # 6, 7, 8, 9: Actual False, Pred False -> TN=4
    sids = [f"sess-{i}" for i in range(10)]
    labels = [True, True, True, False, True, True, False, False, False, False]
    df = pd.DataFrame({"session_id": sids, "ground_truth_is_anomaly": labels})

    alerts = [
        _make_dummy_alert("sess-0"),
        _make_dummy_alert("sess-1"),
        _make_dummy_alert("sess-2"),
        _make_dummy_alert("sess-3"),  # FP
    ]

    metrics = evaluate_detector_performance(df, alerts)

    assert metrics["total_samples"] == 10
    assert metrics["tp"] == 3
    assert metrics["fp"] == 1
    assert metrics["tn"] == 4
    assert metrics["fn"] == 2

    # Precision: 3 / (3 + 1) = 0.75
    assert pytest.approx(metrics["precision"], rel=1e-4) == 0.75

    # Recall: 3 / (3 + 2) = 0.60
    assert pytest.approx(metrics["recall"], rel=1e-4) == 0.60

    # F1-Score: 2 * (0.75 * 0.60) / (0.75 + 0.60) = 0.90 / 1.35 = 2/3 ≈ 0.6667
    assert pytest.approx(metrics["f1_score"], rel=1e-4) == 2.0 / 3.0


def test_zero_division_custom_fallback():
    """Verify zero_division parameter customizes fallback value when denominators are zero."""
    empty_df = pd.DataFrame(columns=["session_id", "ground_truth_is_anomaly"])
    metrics_custom = evaluate_detector_performance(empty_df, [], zero_division=1.0)

    assert metrics_custom["precision"] == 1.0
    assert metrics_custom["recall"] == 1.0
    assert metrics_custom["f1_score"] == 1.0


def test_reproducible_evaluation_on_synthetic_scenarios():
    """Verify evaluation operates seamlessly with data generated by generate_scenario_sessions."""
    # 1. Nominal scenario: should produce zero alerts and 100% TN
    nominal_df = generate_scenario_sessions(
        "NOMINAL",
        num_days=15,
        random_seed=0,
        include_labels=True,
    )
    nominal_alerts = detect_anomalies(nominal_df)
    nominal_metrics = evaluate_detector_performance(nominal_df, nominal_alerts)

    assert nominal_metrics["total_samples"] == 15
    assert nominal_metrics["fp"] == 0
    assert nominal_metrics["tn"] == 15
    assert nominal_metrics["tp"] == 0
    assert nominal_metrics["fn"] == 0

    # 2. Drop scenario: contains 1 drop anomaly on Day 6
    drop_df = generate_scenario_sessions(
        "ATTENDANCE_DROP",
        num_days=15,
        random_seed=42,
        include_labels=True,
    )
    # Run specifically with RULE_ATTENDANCE_DROP active
    drop_alerts = detect_anomalies(drop_df, active_rules=[RULE_ATTENDANCE_DROP])
    drop_metrics = evaluate_detector_performance(drop_df, drop_alerts)

    assert drop_metrics["total_samples"] == 15
    assert drop_metrics["tp"] == 1
    assert drop_metrics["fp"] == 0
    assert drop_metrics["fn"] == 0
    assert drop_metrics["tn"] == 14
    assert drop_metrics["precision"] == 1.0
    assert drop_metrics["recall"] == 1.0
    assert drop_metrics["f1_score"] == 1.0

    # Rule breakdown also reflects 100% precision/recall on attendance drop
    drop_rule_metrics = drop_metrics["by_rule"][RULE_ATTENDANCE_DROP]
    assert drop_rule_metrics["tp"] == 1
    assert drop_rule_metrics["fp"] == 0
    assert drop_rule_metrics["precision"] == 1.0
    assert drop_rule_metrics["recall"] == 1.0


def test_per_rule_and_aggregate_metrics():
    """Verify per-rule breakdown correctly isolates individual rule performance."""
    sids = ["s1", "s2", "s3", "s4"]
    df = pd.DataFrame(
        {
            "session_id": sids,
            "ground_truth_is_anomaly": [True, True, False, False],
            "ground_truth_anomaly_type": [
                "ATTENDANCE_DROP",
                "REPEATED_HEADCOUNT",
                "NONE",
                "NONE",
            ],
        }
    )

    alerts = [
        _make_dummy_alert("s1", rule_id=RULE_ATTENDANCE_DROP),
        _make_dummy_alert("s2", rule_id=RULE_REPEATED_HEADCOUNT),
    ]

    metrics = evaluate_detector_performance(df, alerts)

    # Overall: 2 actual anomalies, both alerted -> TP=2, FP=0, TN=2, FN=0
    assert metrics["tp"] == 2
    assert metrics["fp"] == 0
    assert metrics["tn"] == 2
    assert metrics["fn"] == 0

    # By-rule breakdown
    by_rule = metrics["by_rule"]
    assert RULE_ATTENDANCE_DROP in by_rule
    assert RULE_REPEATED_HEADCOUNT in by_rule

    drop_rule = by_rule[RULE_ATTENDANCE_DROP]
    assert drop_rule["tp"] == 1  # s1
    assert drop_rule["fp"] == 0
    assert drop_rule["fn"] == 0
    assert drop_rule["tn"] == 3  # s2, s3, s4 are not drop anomalies

    repeat_rule = by_rule[RULE_REPEATED_HEADCOUNT]
    assert repeat_rule["tp"] == 1  # s2
    assert repeat_rule["fp"] == 0
    assert repeat_rule["fn"] == 0
    assert repeat_rule["tn"] == 3


def test_deterministic_results():
    """Verify that evaluate_detector_performance produces identical outputs on repeated runs."""
    df = generate_synthetic_sessions(num_classes=3, num_days=10, random_seed=42)
    alerts = detect_anomalies(df)

    res1 = evaluate_detector_performance(df, alerts)
    res2 = evaluate_detector_performance(df, alerts)

    assert res1 == res2


def test_input_dataframe_immutability():
    """Verify evaluate_detector_performance does not mutate the caller's DataFrame."""
    df = generate_synthetic_sessions(num_classes=2, num_days=10, random_seed=42)
    cols_before = list(df.columns)
    shape_before = df.shape
    df_copy = df.copy(deep=True)

    _ = evaluate_detector_performance(df, [])

    assert list(df.columns) == cols_before
    assert df.shape == shape_before
    pd.testing.assert_frame_equal(df, df_copy)


def test_missing_required_columns_raises():
    """Verify ValueError is raised if required evaluation columns are missing."""
    df_no_gt = pd.DataFrame({"session_id": ["s1", "s2"]})
    with pytest.raises(ValueError, match="missing required evaluation column 'ground_truth_is_anomaly'"):
        evaluate_detector_performance(df_no_gt, [])

    df_no_sid = pd.DataFrame({"ground_truth_is_anomaly": [True, False]})
    with pytest.raises(ValueError, match="missing required evaluation column 'session_id'"):
        evaluate_detector_performance(df_no_sid, [])

    with pytest.raises(TypeError, match="Expected labelled_sessions_df to be pandas DataFrame"):
        evaluate_detector_performance({"session_id": "s1"}, [])  # type: ignore


def test_confusion_matrix_to_dataframe():
    """Verify confusion_matrix_to_dataframe formats correctly per contract Section 6.2."""
    cm = {"tp": 12, "fp": 2, "tn": 40, "fn": 1}
    df_cm = confusion_matrix_to_dataframe(cm)

    assert isinstance(df_cm, pd.DataFrame)
    assert list(df_cm.columns) == ["Actual Positive", "Actual Negative"]
    assert list(df_cm.index) == ["Pred Positive", "Pred Negative"]
    assert df_cm.loc["Pred Positive", "Actual Positive"] == 12
    assert df_cm.loc["Pred Positive", "Actual Negative"] == 2
    assert df_cm.loc["Pred Negative", "Actual Positive"] == 1
    assert df_cm.loc["Pred Negative", "Actual Negative"] == 40


def test_alerts_as_dataframe_and_dicts_support():
    """Verify evaluate_detector_performance supports alerts passed as DataFrame or list of dicts."""
    sids = ["s1", "s2", "s3"]
    df = pd.DataFrame({"session_id": sids, "ground_truth_is_anomaly": [True, False, False]})

    # Alerts as dicts
    dict_alerts = [{"session_id": "s1", "rule_id": RULE_ATTENDANCE_DROP}]
    metrics_dict = evaluate_detector_performance(df, dict_alerts)
    assert metrics_dict["tp"] == 1
    assert metrics_dict["tn"] == 2

    # Alerts as DataFrame
    df_alerts = pd.DataFrame([{"session_id": "s1", "rule_id": RULE_ATTENDANCE_DROP}])
    metrics_df = evaluate_detector_performance(df, df_alerts)
    assert metrics_df["tp"] == 1
    assert metrics_df["tn"] == 2


def test_repeated_headcount_session_level_vs_event_level_semantics():
    """Demonstrate session-level metrics vs event-level detection on repeated headcounts.

    In a 15-day repeated-headcount scenario:
    - 4 consecutive days (days 5, 6, 7, 8) have identical present counts and are all labelled
      as anomalous (ground_truth_is_anomaly = True).
    - The online detector fires an alert when K >= 4 (on Day 8).
    - Event-level detection: 1 alert was raised covering the multi-day event (event detected).
    - Session-level classification:
        * Days 5, 6, 7 (indices 4, 5, 6): Actual Positive, Pred Negative -> 3 False Negatives
        * Day 8 (index 7):               Actual Positive, Pred Positive -> 1 True Positive
        * Days 1-4, 9-15 (11 sessions):  Actual Negative, Pred Negative -> 11 True Negatives
        * False Positives: 0
    - This results in session-level recall of 1/4 (0.25) and precision of 1.0.
    """
    df = generate_scenario_sessions(
        "REPEATED_HEADCOUNT",
        num_days=15,
        random_seed=42,
        include_labels=True,
    )

    # Confirm ground truth labels: exactly 4 sessions are marked anomalous
    gt_anomalous = df[df["ground_truth_is_anomaly"] == True]
    assert len(gt_anomalous) == 4
    assert list(gt_anomalous["ground_truth_anomaly_type"]) == ["REPEATED_HEADCOUNT"] * 4

    # Run online repeated headcount detector
    alerts = detect_anomalies(df, active_rules=[RULE_REPEATED_HEADCOUNT])

    # Event-level check: exactly one alert is triggered on day 8 (the threshold-reaching session)
    assert len(alerts) == 1
    assert alerts[0].rule_id == RULE_REPEATED_HEADCOUNT
    assert alerts[0].session_id == df.iloc[7]["session_id"]  # 4th session of the repeated run

    # Evaluate at session level
    metrics = evaluate_detector_performance(df, alerts)

    # Assert exact session-level confusion counts
    assert metrics["total_samples"] == 15
    assert metrics["tp"] == 1
    assert metrics["fn"] == 3
    assert metrics["fp"] == 0
    assert metrics["tn"] == 11
    assert pytest.approx(metrics["precision"], rel=1e-4) == 1.0
    assert pytest.approx(metrics["recall"], rel=1e-4) == 0.25

    # Rule-specific breakdown produces identical isolated counts
    repeat_rule = metrics["by_rule"][RULE_REPEATED_HEADCOUNT]
    assert repeat_rule["tp"] == 1
    assert repeat_rule["fn"] == 3
    assert repeat_rule["fp"] == 0
    assert repeat_rule["tn"] == 11
    assert pytest.approx(repeat_rule["recall"], rel=1e-4) == 0.25


def test_duplicate_session_ids_rejected():
    """Verify DataFrames containing duplicate session_id values are rejected with ValueError."""
    dup_df = pd.DataFrame(
        {
            "session_id": ["sess-001", "sess-001", "sess-002"],
            "ground_truth_is_anomaly": [True, True, False],
            "ground_truth_anomaly_type": ["ATTENDANCE_DROP", "ATTENDANCE_DROP", "NONE"],
        }
    )

    with pytest.raises(ValueError, match="labelled_sessions_df contains duplicate session_id values"):
        evaluate_detector_performance(dup_df, [])

    with pytest.raises(ValueError, match="labelled_sessions_df contains duplicate session_id values"):
        evaluate_rule_performance(RULE_ATTENDANCE_DROP, dup_df, [])


def test_missing_anomaly_type_per_rule_raises_value_error():
    """Verify per-rule evaluation raises ValueError when ground_truth_anomaly_type is absent."""
    df_no_type = pd.DataFrame(
        {
            "session_id": ["s1", "s2"],
            "ground_truth_is_anomaly": [True, False],
        }
    )

    # 1. Direct evaluate_rule_performance call
    with pytest.raises(ValueError, match="requires 'ground_truth_anomaly_type' column"):
        evaluate_rule_performance(RULE_ATTENDANCE_DROP, df_no_type, [])

    # 2. Explicit evaluated_rules request in evaluate_detector_performance
    with pytest.raises(
        ValueError,
        match="Per-rule evaluation was requested via evaluated_rules, but labelled_sessions_df is missing",
    ):
        evaluate_detector_performance(df_no_type, [], evaluated_rules=[RULE_ATTENDANCE_DROP])


def test_missing_anomaly_type_preserves_aggregate_and_omits_by_rule():
    """Verify evaluate_detector_performance succeeds on aggregate metrics and sets by_rule to {} when anomaly type is absent."""
    df_no_type = pd.DataFrame(
        {
            "session_id": ["s1", "s2", "s3"],
            "ground_truth_is_anomaly": [True, False, False],
        }
    )
    alert = _make_dummy_alert("s1")

    metrics = evaluate_detector_performance(df_no_type, [alert])

    # Aggregate metrics compute cleanly
    assert metrics["total_samples"] == 3
    assert metrics["tp"] == 1
    assert metrics["fp"] == 0
    assert metrics["tn"] == 2
    assert metrics["fn"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0

    # by_rule is safely omitted to prevent cross-rule false negative inflation
    assert metrics["by_rule"] == {}


def test_evaluate_rule_performance_empty_and_nominal():
    """Verify evaluate_rule_performance works correctly on empty and nominal datasets."""
    # Empty dataset
    empty_df = pd.DataFrame(
        columns=["session_id", "ground_truth_is_anomaly", "ground_truth_anomaly_type"]
    )
    empty_res = evaluate_rule_performance(RULE_ATTENDANCE_DROP, empty_df, [])
    assert empty_res["total_samples"] == 0
    assert empty_res["tp"] == 0
    assert empty_res["zero_division_applied"]["precision"] is True

    # Nominal dataset
    nominal_df = generate_scenario_sessions("NOMINAL", num_days=10, random_seed=0, include_labels=True)
    nom_res = evaluate_rule_performance(RULE_ATTENDANCE_DROP, nominal_df, [])
    assert nom_res["total_samples"] == 10
    assert nom_res["tp"] == 0
    assert nom_res["fp"] == 0
    assert nom_res["tn"] == 10
    assert nom_res["fn"] == 0
    assert nom_res["precision"] == 0.0
    assert nom_res["recall"] == 0.0


def test_webcam_estimation_empty_dataframe():
    """Verify evaluate_webcam_estimation handles empty DataFrames safely."""
    empty_df = pd.DataFrame(columns=["present_count", "webcam_status", "webcam_count"])
    res = evaluate_webcam_estimation(empty_df)
    assert res["total_sessions"] == 0
    assert res["evaluated_pairs"] == 0
    assert res["mae"] is None
    assert res["mape"] is None
    assert res["zero_division_applied"]["mae"] is True
    assert res["zero_division_applied"]["mape"] is True


def test_webcam_estimation_perfect_alignment():
    """Verify MAE and MAPE are 0.0 when webcam counts match roll call perfectly."""
    df = pd.DataFrame(
        {
            "present_count": [20, 25, 30],
            "webcam_status": ["SUCCESS", "SUCCESS", "SUCCESS"],
            "webcam_count": [20, 25, 30],
        }
    )
    res = evaluate_webcam_estimation(df)
    assert res["total_sessions"] == 3
    assert res["evaluated_pairs"] == 3
    assert res["mae"] == 0.0
    assert res["mape"] == 0.0
    assert res["zero_actual_count"] == 0
    assert res["zero_division_applied"]["mae"] is False
    assert res["zero_division_applied"]["mape"] is False


def test_webcam_estimation_with_zero_actual_protection():
    """Verify ground truth 0 present is included in MAE but excluded from MAPE to prevent division by zero."""
    df = pd.DataFrame(
        {
            "present_count": [20, 25, 0],
            "webcam_status": ["SUCCESS", "SUCCESS", "SUCCESS"],
            "webcam_count": [22, 20, 2],  # Errors: 2, 5, 2 -> MAE = (2 + 5 + 2) / 3 = 3.0
        }
    )
    res = evaluate_webcam_estimation(df)
    assert res["total_sessions"] == 3
    assert res["evaluated_pairs"] == 3
    assert res["mae"] == 3.0
    assert res["zero_actual_count"] == 1
    # MAPE calculated on rows 0 and 1: (2/20 + 5/25) / 2 * 100 = (0.10 + 0.20) / 2 * 100 = 15.0%
    assert res["mape"] == 15.0
    assert res["zero_division_applied"]["mape"] is False


def test_webcam_estimation_all_zero_actuals():
    """Verify MAPE defaults to None when all ground truth counts are zero."""
    df = pd.DataFrame(
        {
            "present_count": [0, 0],
            "webcam_status": ["SUCCESS", "SUCCESS"],
            "webcam_count": [1, 2],
        }
    )
    res = evaluate_webcam_estimation(df)
    assert res["evaluated_pairs"] == 2
    assert res["mae"] == 1.5
    assert res["mape"] is None
    assert res["zero_actual_count"] == 2
    assert res["zero_division_applied"]["mape"] is True


def test_webcam_estimation_non_success_statuses_excluded():
    """Verify CAMERA_OFFLINE, CAMERA_UNAVAILABLE, NOT_ATTEMPTED are excluded from evaluation."""
    df = pd.DataFrame(
        {
            "present_count": [25, 28, 20, 30],
            "webcam_status": ["SUCCESS", "CAMERA_OFFLINE", "CAMERA_UNAVAILABLE", "NOT_ATTEMPTED"],
            "webcam_count": [26, None, None, None],
        }
    )
    res = evaluate_webcam_estimation(df)
    assert res["total_sessions"] == 4
    assert res["evaluated_pairs"] == 1
    assert res["mae"] == 1.0
    assert pytest.approx(res["mape"], rel=1e-4) == 4.0


def test_webcam_estimation_missing_required_columns():
    """Verify ValueError is raised if any required camera column is missing."""
    df = pd.DataFrame({"present_count": [20]})
    with pytest.raises(ValueError, match="missing required column 'webcam_status'"):
        evaluate_webcam_estimation(df)

    with pytest.raises(TypeError, match="Expected sessions_df to be pandas DataFrame"):
        evaluate_webcam_estimation([{"present_count": 20}])  # type: ignore


def test_sequence_events_evaluation_repeated_headcount():
    """Verify evaluate_sequence_events captures 100% event recall on 4-day repeated sequence."""
    df = generate_scenario_sessions("REPEATED_HEADCOUNT", num_days=15, random_seed=42, include_labels=True)
    alerts = detect_anomalies(df, active_rules=[RULE_REPEATED_HEADCOUNT])

    seq_res = evaluate_sequence_events(df, alerts, RULE_REPEATED_HEADCOUNT)
    assert seq_res["target_rule_id"] == RULE_REPEATED_HEADCOUNT
    assert seq_res["total_events"] == 1
    assert seq_res["tp"] == 1
    assert seq_res["fn"] == 0
    assert seq_res["fp"] == 0
    assert seq_res["precision"] == 1.0
    assert seq_res["recall"] == 1.0
    assert seq_res["f1_score"] == 1.0
    assert len(seq_res["events"]) == 1
    assert seq_res["events"][0]["detected"] is True
    assert seq_res["events"][0]["length"] == 4


def test_sequence_events_evaluation_undetected_event():
    """Verify evaluate_sequence_events records FN when no alerts fire on an anomaly event."""
    df = generate_scenario_sessions("REPEATED_HEADCOUNT", num_days=15, random_seed=42, include_labels=True)
    # Zero alerts provided
    seq_res = evaluate_sequence_events(df, [], RULE_REPEATED_HEADCOUNT)
    assert seq_res["total_events"] == 1
    assert seq_res["tp"] == 0
    assert seq_res["fn"] == 1
    assert seq_res["fp"] == 0
    assert seq_res["recall"] == 0.0
    assert seq_res["events"][0]["detected"] is False


def test_sequence_events_spurious_alert():
    """Verify evaluate_sequence_events records FP when alert fires on normal sessions outside events."""
    df = generate_scenario_sessions("NOMINAL", num_days=10, random_seed=0, include_labels=True)
    spurious_alert = _make_dummy_alert(df.iloc[0]["session_id"], rule_id=RULE_REPEATED_HEADCOUNT)

    seq_res = evaluate_sequence_events(df, [spurious_alert], RULE_REPEATED_HEADCOUNT)
    assert seq_res["total_events"] == 0
    assert seq_res["tp"] == 0
    assert seq_res["fn"] == 0
    assert seq_res["fp"] == 1
    assert seq_res["precision"] == 0.0
    assert seq_res["zero_division_applied"]["precision"] is False
