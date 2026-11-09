"""Supervised Decision Tree Classifier for attendance anomaly and integrity classification.

Conforms to CSE276 Unit IV (Supervised Learning) and Practical 7.
Provides interpretable tree-based classification into Normal vs. Needs Review,
with confidence scores, uncertainty guards, and feature contribution rationales.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text

from attendsure.ml.features import FEATURE_COLUMNS, extract_session_features

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "attendance_decision_tree.joblib"


@dataclass(frozen=True)
class MLPredictionResult:
    """Represents the explainable outcome of a machine learning inference."""

    prediction: str  # "NORMAL", "NEEDS_REVIEW", or "INSUFFICIENT_DATA"
    confidence_score: float  # [0.0, 1.0]
    is_uncertain: bool
    top_contributing_feature: str
    feature_values: dict[str, float]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AttendanceDecisionTreeClassifier:
    """Supervised Decision Tree Classifier for identifying unusual attendance sessions.

    Academic Design:
    - Uses scikit-learn's DecisionTreeClassifier.
    - Constrained max_depth=4 and min_samples_leaf=4 to preserve model interpretability
      and prevent overfitting on small rural school cohorts.
    - Handles class imbalance using balanced sample weights.
    - Integrates uncertainty guards: flags predictions with confidence < 0.65 as uncertain.
    - Provides human-readable decision explanations based on feature thresholds.
    """

    def __init__(
        self,
        max_depth: int = 4,
        min_samples_leaf: int = 4,
        random_state: int = 42,
    ):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.classifier = DecisionTreeClassifier(
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            class_weight="balanced",
            random_state=self.random_state,
        )
        self.is_trained: bool = False
        self.feature_names = list(FEATURE_COLUMNS)
        self.evaluation_metrics: dict[str, Any] = {}

    def fit(self, train_df: pd.DataFrame) -> "AttendanceDecisionTreeClassifier":
        """Train the Decision Tree on session records containing ground-truth 'label'.

        Args:
            train_df: DataFrame containing session columns and integer 'label' (0 or 1).

        Returns:
            Self (trained classifier).
        """
        feats_df = extract_session_features(train_df)
        if feats_df.empty or "label" not in feats_df.columns:
            raise ValueError("Training DataFrame must contain valid sessions with ground-truth 'label'.")

        # Exclude sessions with insufficient history during training to ensure high feature quality
        valid_train = feats_df[~feats_df["is_insufficient_history"]].copy()
        if len(valid_train) < 10:
            valid_train = feats_df.copy()

        X = valid_train[self.feature_names].values
        y = valid_train["label"].values.astype(int)

        self.classifier.fit(X, y)
        self.is_trained = True
        return self

    def evaluate(self, test_df: pd.DataFrame) -> dict[str, Any]:
        """Evaluate the trained Decision Tree on an independent test dataset.

        Calculates Precision, Recall, Specificity, F1-Score, and Confusion Matrix.

        Args:
            test_df: Independent test DataFrame with 'label' column.

        Returns:
            Dictionary containing metrics, confusion matrix, and feature importances.
        """
        if not self.is_trained:
            raise RuntimeError("Cannot evaluate an untrained model. Call fit() first.")

        feats_df = extract_session_features(test_df)
        if feats_df.empty or "label" not in feats_df.columns:
            raise ValueError("Test DataFrame must contain valid sessions with ground-truth 'label'.")

        valid_test = feats_df[~feats_df["is_insufficient_history"]].copy()
        if valid_test.empty:
            valid_test = feats_df.copy()

        X_test = valid_test[self.feature_names].values
        y_test = valid_test["label"].values.astype(int)

        y_pred = self.classifier.predict(X_test)

        tp = int(np.sum((y_test == 1) & (y_pred == 1)))
        fp = int(np.sum((y_test == 0) & (y_pred == 1)))
        tn = int(np.sum((y_test == 0) & (y_pred == 0)))
        fn = int(np.sum((y_test == 1) & (y_pred == 0)))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        importances = dict(
            zip(self.feature_names, [round(float(v), 4) for v in self.classifier.feature_importances_])
        )

        metrics = {
            "test_samples": int(len(y_test)),
            "class_distribution": {
                "normal_0": int(np.sum(y_test == 0)),
                "needs_review_1": int(np.sum(y_test == 1)),
            },
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "f1_score": round(f1, 4),
            "feature_importances": importances,
            "tree_rules_text": export_text(self.classifier, feature_names=self.feature_names),
        }

        self.evaluation_metrics = metrics
        return metrics

    def predict_session(self, features_dict: dict[str, Any]) -> MLPredictionResult:
        """Predict whether a candidate session requires review with an explainable rationale.

        Args:
            features_dict: Output of extract_features_for_session().

        Returns:
            MLPredictionResult with prediction, confidence, uncertainty flag, and rationale.
        """
        if not self.is_trained:
            raise RuntimeError("Model is not trained. Load or train a model before inference.")

        # Guard: Incomplete historical context
        if features_dict.get("is_insufficient_history", False):
            return MLPredictionResult(
                prediction="INSUFFICIENT_DATA",
                confidence_score=0.0,
                is_uncertain=True,
                top_contributing_feature="insufficient_history",
                feature_values={k: float(features_dict.get(k, 0.0)) for k in self.feature_names},
                explanation=(
                    "Insufficient past attendance history (< 3 sessions) for this class to establish "
                    "a reliable baseline. Rely on manual roll call verification."
                ),
            )

        row_vals = [float(features_dict.get(col, 0.0)) for col in self.feature_names]
        X = np.array([row_vals])

        pred_cls = int(self.classifier.predict(X)[0])
        probabilities = self.classifier.predict_proba(X)[0]
        confidence = float(np.max(probabilities))
        is_uncertain = confidence < 0.65

        # Identify most influential feature from feature importances and values
        importances = self.classifier.feature_importances_
        feature_scores = {
            col: abs(float(val)) * imp
            for col, val, imp in zip(self.feature_names, row_vals, importances)
        }
        top_feat = max(feature_scores.items(), key=lambda item: item[1])[0]

        # Generate human-readable explanation
        decline = float(features_dict.get("relative_decline_pct", 0.0))
        streak = int(features_dict.get("repeated_count_streak", 1))
        rate = float(features_dict.get("attendance_rate", 0.0))
        dev = float(features_dict.get("baseline_deviation", 0.0))

        if pred_cls == 1:
            prediction_label = "NEEDS_REVIEW"
            if decline >= 20.0 or dev >= 15.0:
                explanation = (
                    f"Machine learning model flagged this session: attendance ({rate:.1f}%) is "
                    f"{dev:.1f}% below the class's usual attendance (relative drop: {decline:.1f}%)."
                )
            elif streak >= 4:
                explanation = (
                    f"Machine learning model flagged this session: identical headcount repeated across "
                    f"{streak} consecutive sessions (reporting inertia pattern)."
                )
            else:
                explanation = (
                    f"Machine learning model detected an unusual statistical pattern based on recent "
                    f"attendance shifts (top indicator: '{top_feat}')."
                )
        else:
            prediction_label = "NORMAL"
            explanation = (
                f"Machine learning model classified this session as consistent with typical attendance patterns "
                f"(confidence: {confidence * 100:.1f}%)."
            )

        if is_uncertain:
            explanation += " (Note: Model confidence is borderline; human verification is advised)."

        return MLPredictionResult(
            prediction=prediction_label,
            confidence_score=round(confidence, 3),
            is_uncertain=is_uncertain,
            top_contributing_feature=top_feat,
            feature_values={k: round(float(v), 2) for k, v in zip(self.feature_names, row_vals)},
            explanation=explanation,
        )

    def save(self, filepath: Optional[Union[str, Path]] = None) -> Path:
        """Save trained model and evaluation artifacts to disk."""
        target = Path(filepath or DEFAULT_MODEL_PATH)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "classifier": self.classifier,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "random_state": self.random_state,
            "is_trained": self.is_trained,
            "feature_names": self.feature_names,
            "evaluation_metrics": self.evaluation_metrics,
        }
        joblib.dump(payload, target)
        return target

    @classmethod
    def load(cls, filepath: Optional[Union[str, Path]] = None) -> "AttendanceDecisionTreeClassifier":
        """Load a trained model from disk."""
        target = Path(filepath or DEFAULT_MODEL_PATH)
        if not target.exists():
            raise FileNotFoundError(f"Model file not found at: {target}")

        payload = joblib.load(target)
        instance = cls(
            max_depth=payload["max_depth"],
            min_samples_leaf=payload["min_samples_leaf"],
            random_state=payload["random_state"],
        )
        instance.classifier = payload["classifier"]
        instance.is_trained = payload.get("is_trained", True)
        instance.feature_names = payload.get("feature_names", list(FEATURE_COLUMNS))
        instance.evaluation_metrics = payload.get("evaluation_metrics", {})
        return instance

