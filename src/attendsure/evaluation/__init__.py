"""Evaluation and benchmarking module for AttendSure.

Provides detector performance evaluation metrics conforming to docs/data-contract.md Section 6.2.
"""

from attendsure.evaluation.metrics import (
    ClassificationCounts,
    compute_classification_scores,
    confusion_matrix_to_dataframe,
    evaluate_detector_performance,
    evaluate_rule_performance,
    evaluate_sequence_events,
    evaluate_webcam_estimation,
)

__all__ = [
    "ClassificationCounts",
    "compute_classification_scores",
    "confusion_matrix_to_dataframe",
    "evaluate_detector_performance",
    "evaluate_rule_performance",
    "evaluate_sequence_events",
    "evaluate_webcam_estimation",
]
