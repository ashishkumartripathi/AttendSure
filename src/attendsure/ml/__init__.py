"""Machine learning module for Rural School Attendance Integrity and Intervention Decision System.

Implements supervised Decision Tree classification conforming to CSE276 Unit IV and Practical 7.
"""

from attendsure.ml.features import FEATURE_COLUMNS, extract_features_for_session, extract_session_features
from attendsure.ml.model import AttendanceDecisionTreeClassifier
from attendsure.ml.predictor import evaluate_session_ml, get_trained_model

__all__ = [
    "FEATURE_COLUMNS",
    "AttendanceDecisionTreeClassifier",
    "extract_session_features",
    "extract_features_for_session",
    "evaluate_session_ml",
    "get_trained_model",
]

