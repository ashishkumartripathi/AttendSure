"""Inference and multi-stream decision support integration for attendance ML.

Fuses production rule findings with machine learning predictions to formulate
transparent, non-accusatory intervention recommendations.
"""

from dataclasses import asdict, dataclass
import functools
from pathlib import Path
from typing import Any, Optional, Sequence
import pandas as pd

from attendsure.data.models import Alert
from attendsure.ml.dataset import create_train_test_split
from attendsure.ml.features import extract_features_for_session
from attendsure.ml.model import (
    DEFAULT_MODEL_PATH,
    AttendanceDecisionTreeClassifier,
    MLPredictionResult,
)


@dataclass(frozen=True)
class CombinedDecisionResult:
    """Represents a fused decision-support finding combining rule and ML signals."""

    overall_status: str  # "NORMAL", "NEEDS_VERIFICATION", "INSUFFICIENT_DATA"
    rule_flagged: bool
    rule_summaries: list[str]
    ml_prediction: str  # "NORMAL", "NEEDS_REVIEW", "INSUFFICIENT_DATA"
    ml_confidence: float
    ml_explanation: str
    combined_recommendation: str
    actionable_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@functools.lru_cache(maxsize=1)
def get_trained_model(
    model_path: Optional[str] = None,
    auto_bootstrap: bool = True,
) -> AttendanceDecisionTreeClassifier:
    """Retrieve or bootstrap the trained Attendance Decision Tree model.

    If an artifact already exists at model_path (or DEFAULT_MODEL_PATH), it is loaded.
    If not, it trains a fresh model on the reproducible synthetic split (seed=42)
    and saves it to disk once.
    """
    target = Path(model_path) if model_path else DEFAULT_MODEL_PATH

    if target.exists():
        try:
            return AttendanceDecisionTreeClassifier.load(target)
        except Exception:
            pass  # Fall through to bootstrapping if corrupted

    if not auto_bootstrap:
        raise FileNotFoundError(f"Model artifact not found at {target} and auto_bootstrap is False.")

    # Bootstrap model
    split = create_train_test_split(num_classes=12, days_per_class=35, random_seed=42)
    model = AttendanceDecisionTreeClassifier(max_depth=4, min_samples_leaf=4, random_state=42)
    model.fit(split.train_df)
    model.evaluate(split.test_df)
    model.save(target)
    return model


def evaluate_session_ml(
    class_id: str,
    enrollment: int,
    present: int,
    history_df: pd.DataFrame,
    model: Optional[AttendanceDecisionTreeClassifier] = None,
) -> MLPredictionResult:
    """Run supervised Decision Tree inference on a candidate session."""
    clf = model or get_trained_model()
    feats = extract_features_for_session(
        class_id=class_id,
        enrollment=enrollment,
        present=present,
        historical_sessions_df=history_df,
    )
    return clf.predict_session(feats)


def synthesize_intervention_decision(
    rule_alerts: Sequence[Alert],
    ml_result: MLPredictionResult,
) -> CombinedDecisionResult:
    """Fuse rule-based findings with ML predictions into a unified intervention decision.

    Guarantees:
    - Rule-based finding is never silently overridden.
    - ML prediction is clearly identified as a separate data stream.
    - Recommendation treats findings as opportunities for verification, never accusations.
    """
    has_rules = len(rule_alerts) > 0
    rule_titles = [f"{a.rule_title}: {a.explanation}" for a in rule_alerts]
    ml_pred = ml_result.prediction
    is_ml_review = ml_pred == "NEEDS_REVIEW"

    # Case 1: Both Rule and ML flag the session
    if has_rules and is_ml_review:
        overall_status = "NEEDS_VERIFICATION"
        recommendation = (
            "High-Confidence Verification Needed: Both deterministic rule thresholds and the supervised "
            "Decision Tree classifier identified this session as unusual."
        )
        next_step = (
            "Verify the physical classroom register, recheck attendance headcounts, and check if legitimate "
            "external disruptions (e.g. weather, transport delays, school health issues) occurred."
        )

    # Case 2: Specific Rule flagged, ML is Normal or Uncertain
    elif has_rules and not is_ml_review:
        overall_status = "NEEDS_VERIFICATION"
        recommendation = (
            f"Rule Threshold Triggered: Specific attendance integrity rule ({rule_alerts[0].rule_title}) was met, "
            f"while the Decision Tree pattern model observed mild aggregate shifts."
        )
        next_step = (
            "Inspect the specific condition flagged by the rule (e.g. historical baseline drop or repeated count streak)."
        )

    # Case 3: ML flagged, but no specific hard rule triggered
    elif not has_rules and is_ml_review:
        overall_status = "NEEDS_VERIFICATION"
        recommendation = (
            "Statistical Pattern Alert: The supervised Decision Tree identified a notable attendance shift based on "
            "recent history, though no single hard rule boundary was crossed."
        )
        next_step = (
            "Review recent attendance records for this cohort to confirm whether student attendance is gradually shifting."
        )

    # Case 4: Insufficient History
    elif ml_pred == "INSUFFICIENT_DATA":
        overall_status = "INSUFFICIENT_DATA"
        recommendation = (
            "Insufficient Historical Context: Less than 3 sessions exist for this cohort. "
            "Model-based baselines cannot yet be established."
        )
        next_step = (
            "Rely on manual roll-call confirmation. Continue logging sessions to build baseline history."
        )

    # Case 5: Normal
    else:
        overall_status = "NORMAL"
        recommendation = (
            "Normal Attendance Pattern: Both deterministic rule checks and the supervised Decision Tree "
            "indicate attendance is within expected bounds."
        )
        next_step = "No administrative intervention required."

    return CombinedDecisionResult(
        overall_status=overall_status,
        rule_flagged=has_rules,
        rule_summaries=rule_titles,
        ml_prediction=ml_pred,
        ml_confidence=ml_result.confidence_score,
        ml_explanation=ml_result.explanation,
        combined_recommendation=recommendation,
        actionable_next_step=next_step,
    )

