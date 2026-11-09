"""Unit and integration tests for the Decision Tree machine learning module.

Conforms to CSE276 Unit IV and Practical 7 testing requirements.
"""

from pathlib import Path
import tempfile
import pandas as pd
import pytest

from attendsure.data.models import Alert
from attendsure.ml.dataset import create_train_test_split, generate_independent_ml_dataset
from attendsure.ml.features import (
    FEATURE_COLUMNS,
    extract_features_for_session,
    extract_session_features,
)
from attendsure.ml.model import (
    AttendanceDecisionTreeClassifier,
    MLPredictionResult,
)
from attendsure.ml.predictor import (
    CombinedDecisionResult,
    evaluate_session_ml,
    get_trained_model,
    synthesize_intervention_decision,
)


def test_feature_columns_defined():
    """Verify standard feature column definitions."""
    assert len(FEATURE_COLUMNS) == 6
    assert "attendance_rate" in FEATURE_COLUMNS
    assert "baseline_deviation" in FEATURE_COLUMNS
    assert "repeated_count_streak" in FEATURE_COLUMNS


def test_extract_session_features_empty():
    """Verify empty DataFrame handling."""
    empty_df = pd.DataFrame()
    feats = extract_session_features(empty_df)
    assert feats.empty
    assert "attendance_rate" in feats.columns


def test_extract_session_features_causal_no_leakage():
    """Verify that features only compute over strictly past and present sessions."""
    df = pd.DataFrame([
        {
            "session_id": "S1",
            "class_id": "C1",
            "session_date": "2026-10-01",
            "expected_enrollment": 30,
            "present_count": 27,
            "absent_count": 3,
        },
        {
            "session_id": "S2",
            "class_id": "C1",
            "session_date": "2026-10-02",
            "expected_enrollment": 30,
            "present_count": 27,
            "absent_count": 3,
        },
        {
            "session_id": "S3",
            "class_id": "C1",
            "session_date": "2026-10-03",
            "expected_enrollment": 30,
            "present_count": 15,
            "absent_count": 15,
        },
    ])
    feats = extract_session_features(df, min_history=2)
    assert len(feats) == 3

    # First session has streak 1
    assert feats.iloc[0]["repeated_count_streak"] == 1
    assert feats.iloc[0]["is_insufficient_history"] == True

    # Second session has repeated count (27 == 27) -> streak 2
    assert feats.iloc[1]["repeated_count_streak"] == 2

    # Third session drops to 15 -> streak resets to 1, relative decline is positive
    assert feats.iloc[2]["repeated_count_streak"] == 1
    assert feats.iloc[2]["attendance_rate"] == 50.0
    assert feats.iloc[2]["relative_decline_pct"] > 0.0


def test_independent_dataset_generation():
    """Verify synthetic dataset properties."""
    df = generate_independent_ml_dataset(num_classes=4, days_per_class=10, random_seed=42)
    assert not df.empty
    assert "label" in df.columns
    assert "scenario_type" in df.columns
    assert set(df["label"].unique()).issubset({0, 1})


def test_group_aware_train_test_split():
    """Verify that train and test sets do not share classroom cohorts (leakage prevention)."""
    split = create_train_test_split(num_classes=6, days_per_class=15, test_class_ratio=0.33, random_seed=42)
    train_cohorts = set(split.train_df["class_id"].unique())
    test_cohorts = set(split.test_df["class_id"].unique())

    assert len(train_cohorts.intersection(test_cohorts)) == 0
    assert len(split.train_df) > 0
    assert len(split.test_df) > 0


def test_model_training_and_evaluation():
    """Test Decision Tree training and evaluation workflow."""
    split = create_train_test_split(num_classes=8, days_per_class=25, random_seed=42)
    clf = AttendanceDecisionTreeClassifier(max_depth=3, min_samples_leaf=2, random_state=42)
    clf.fit(split.train_df)
    assert clf.is_trained

    metrics = clf.evaluate(split.test_df)
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1_score" in metrics
    assert "confusion_matrix" in metrics
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0


def test_model_save_and_load():
    """Verify serialization and restoration via joblib."""
    split = create_train_test_split(num_classes=4, days_per_class=15, random_seed=42)
    clf = AttendanceDecisionTreeClassifier(max_depth=3, random_state=42)
    clf.fit(split.train_df)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_model.joblib"
        clf.save(path)
        assert path.exists()

        loaded = AttendanceDecisionTreeClassifier.load(path)
        assert loaded.is_trained
        assert loaded.max_depth == 3


def test_predict_session_insufficient_history():
    """Verify uncertainty handling when insufficient history is available."""
    clf = get_trained_model()
    feats = {
        "attendance_rate": 80.0,
        "absence_rate": 20.0,
        "baseline_deviation": 0.0,
        "recent_delta_1d": 0.0,
        "repeated_count_streak": 1,
        "relative_decline_pct": 0.0,
        "is_insufficient_history": True,
    }
    pred = clf.predict_session(feats)
    assert pred.prediction == "INSUFFICIENT_DATA"
    assert pred.is_uncertain == True
    assert "Insufficient" in pred.explanation


def test_synthesize_intervention_decision_fusion():
    """Test multi-stream decision fusion logic."""
    # Mock normal ML result
    normal_ml = MLPredictionResult(
        prediction="NORMAL",
        confidence_score=0.92,
        is_uncertain=False,
        top_contributing_feature="attendance_rate",
        feature_values={},
        explanation="Typical attendance pattern.",
    )

    # 1. No rules, normal ML -> NORMAL
    dec1 = synthesize_intervention_decision([], normal_ml)
    assert dec1.overall_status == "NORMAL"
    assert not dec1.rule_flagged

    # 2. Rule flagged, normal ML -> NEEDS_VERIFICATION
    dummy_alert = Alert(
        alert_id="ALT-1",
        session_id="S1",
        class_id="C1",
        session_date="2026-10-01",
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Attendance Drop",
        priority="HIGH",
        observed_value={"current_rate": 50.0},
        baseline_reference={"median": 85.0},
        threshold_applied={"threshold": 30.0},
        explanation="Decline >= 30%",
        review_status="PENDING_REVIEW",
        created_at="2026-10-01T10:00:00Z",
    )
    dec2 = synthesize_intervention_decision([dummy_alert], normal_ml)
    assert dec2.overall_status == "NEEDS_VERIFICATION"
    assert dec2.rule_flagged
    assert "Rule Threshold Triggered" in dec2.combined_recommendation

    # 3. Rule flagged and ML review -> High confidence verification
    review_ml = MLPredictionResult(
        prediction="NEEDS_REVIEW",
        confidence_score=0.88,
        is_uncertain=False,
        top_contributing_feature="relative_decline_pct",
        feature_values={},
        explanation="Flagged by decision tree.",
    )
    dec3 = synthesize_intervention_decision([dummy_alert], review_ml)
    assert dec3.overall_status == "NEEDS_VERIFICATION"
    assert "High-Confidence Verification Needed" in dec3.combined_recommendation

